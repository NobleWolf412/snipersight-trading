"""
SniperSight Replay Engine — historical candle-by-candle pipeline playback.

The engine pre-fetches a multi-timeframe window of historical OHLCV data
for a chosen symbol (+ BTC for regime context), then on each `step()` call
slices each timeframe's DataFrame to the rows whose bars have FULLY CLOSED
at the synthetic playback timestamp and feeds the sliced snapshot into a
replay-mode Orchestrator. The Orchestrator runs the full scoring /
SMC / planning / risk pipeline and stashes the populated SniperContext for
the engine to render back to the operator.

Slicing semantics (correctness-critical, see CLAUDE.md §10):

    A bar OPENED at t0 is fully CLOSED at t0 + tf_seconds. The slice
    includes all rows where bar_open + tf_seconds <= current_ts. Using
    bar_open <= current_ts would leak the not-yet-closed bar's data into
    indicators and silently break bullish/bearish symmetry on flip bars.

Scope (per the approved plan):
    - Scanner-only (no paper-trader integration this phase)
    - Single-symbol per session
    - 30-day max window
    - Ring buffer of last 20 step results for instant back-scrub

Session storage is an in-memory dict + threading.Lock. Sessions are pinned
to one FastAPI worker process; deployments using --workers > 1 will not
share session state across workers (acceptable for single-operator local
use; sticky-routing by session_id is deferred per the plan).

Six-concern table (CLAUDE.md §16 Rubric 1):
    1. Collision-free keys: session_id = uuid4 hex (32 chars, 128 bits) —
       collision probability negligible. Run-ids prefixed with "replay-".
    2. Concurrency: (a) _REPLAY_ENGINE singleton guarded by _REPLAY_ENGINE_LOCK
       at module level. (b) ReplayEngine._sessions dict guarded by self._lock.
       (c) Per-session state (step_index, ring_buffer, orchestrator) is NOT
       lock-guarded — the router contract is single-threaded per session_id
       (frontend issues serial step calls, never parallel). Documented here
       and in ReplaySession docstring. If a future change introduces parallel
       per-session traffic, add a session-scoped lock.
    3. Silent-failure: _slice_to_bar_close asserts mass conservation runtime
       (catches "row vanished" bug class). _serialize_smc logs every
       per-item exception (no silent suppression per CLAUDE.md §15).
       Adapter fetch errors raise loudly via _fetch_window.
    4. Retrieval: get_session returns Optional, callers handle None.
       Idle TTL sweep on every step prevents zombie sessions.
    5. Diagnostic: backend/diagnostics/replay_diagnostic.py exercises
       7 end-to-end checks with loud failures (slice correctness,
       cooldown skip, telemetry stamping, GC, stale-counter isolation,
       non-replay-orchestrator rejection).
    6. Schema/symmetry: _slice_to_bar_close, _candles_to_payload,
       _serialize_confluence/smc/plan/regime are all direction-agnostic
       (they handle the data shape, not its directional interpretation —
       scoring symmetry lives entirely in the scorer, which replay does
       not touch). Bull/bear paths receive identical treatment.
"""

from __future__ import annotations

import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Deque, Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger

from backend.data.ingestion_pipeline import IngestionPipeline
from backend.engine.context import SniperContext
from backend.engine.orchestrator import Orchestrator
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import (
    MODES,
    ScannerMode,
    get_mode,
)
from backend.shared.models.data import MultiTimeframeData


# Bar-period seconds per timeframe label. Matches the table in
# backend/data/ingestion_pipeline.py:444 (kept independent here so a
# typo in one file can't silently break replay slicing).
TF_SECONDS: Dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "8h": 28800,
    "12h": 43200,
    "1d": 86400,
    "3d": 259200,
    "1w": 604800,
}

# Hard cap on replay window length (operator-locked; enforced at load_session)
MAX_WINDOW_DAYS = 30

# In-memory session TTL — sessions idle past this are GC'd on the next step
SESSION_IDLE_TTL_SECONDS = 30 * 60

# Ring-buffer depth for instant back-scrub (deeper scrub triggers recompute)
RING_BUFFER_DEPTH = 20

# BTC/USDT must be prefetched alongside the chosen symbol so the regime
# detector sees historical BTC, not live. Mandatory per the audit plan.
BTC_SYMBOL = "BTC/USDT"


@dataclass
class StepResult:
    """Per-bar replay output. Engine-internal shape; the router maps to a
    Pydantic DTO before sending over the wire."""

    index: int
    bar_open_ts: datetime  # Open of the playback TF bar at this index
    current_ts: datetime  # Close of that bar (= bar_open + tf_step_seconds)
    candles_by_tf: Dict[str, List[Dict[str, Any]]]
    confluence: Optional[Dict[str, Any]] = None
    plan: Optional[Dict[str, Any]] = None
    rejection: Optional[Dict[str, Any]] = None
    smc_snapshot: Optional[Dict[str, Any]] = None
    regime: Optional[Dict[str, Any]] = None
    signal_fired: bool = False


@dataclass
class ReplaySession:
    """Per-operator replay state. One per symbol/window/mode combo."""

    session_id: str
    symbol: str
    mode_name: str  # "stealth", "overwatch", "strike", "surgical"
    window_start: datetime
    window_end: datetime
    multi_tf_full: Dict[str, pd.DataFrame]  # All TFs, full window + warmup
    btc_full: Dict[str, pd.DataFrame]  # BTC, for regime detector
    tf_step: str  # mode.primary_planning_timeframe (e.g. "1h" for stealth)
    bar_timestamps: List[datetime]  # tf_step bar opens inside the window
    orchestrator: Orchestrator
    step_index: int = -1  # -1 = not yet stepped (no current bar)
    ring_buffer: Deque[StepResult] = field(
        default_factory=lambda: deque(maxlen=RING_BUFFER_DEPTH)
    )
    last_touched: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_bars(self) -> int:
        return len(self.bar_timestamps)


def _to_jsonable(v: Any) -> Any:
    """Coerce numpy / pandas / datetime scalars to JSON-native Python types
    so Pydantic v2's response serializer doesn't choke on the response model.

    Without this, payload fields that come straight off a pandas DataFrame
    or numpy scalar (e.g. numpy.bool_ from a boolean column) bubble up
    untouched and the FastAPI response serializer raises
    PydanticSerializationError: Unable to serialize unknown type.
    """
    import numpy as np

    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    if isinstance(v, np.ndarray):
        return [_to_jsonable(x) for x in v.tolist()]
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if isinstance(v, (list, tuple)):
        return [_to_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _to_jsonable(x) for k, x in v.items()}
    return v


def _candles_to_payload(df: pd.DataFrame, max_rows: int = 1000) -> List[Dict[str, Any]]:
    """Serialize the last `max_rows` of an OHLCV DataFrame to the chart
    payload shape ({time:int, open, high, low, close, volume}). The chart
    library expects unix seconds for `time`."""
    if df is None or len(df) == 0:
        return []
    tail = df.tail(max_rows)
    out: List[Dict[str, Any]] = []
    for ts, row in tail.iterrows():
        # tail timestamp may live as index OR as a column — try both
        ts_val = row.get("timestamp", ts)
        ts_pd = pd.Timestamp(ts_val)
        if ts_pd.tz is None:
            ts_pd = ts_pd.tz_localize("UTC")
        out.append(
            {
                "time": int(ts_pd.timestamp()),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
        )
    return out


def _slice_to_bar_close(
    full_by_tf: Dict[str, pd.DataFrame], current_ts: datetime
) -> Dict[str, pd.DataFrame]:
    """Slice each TF's DataFrame to rows whose bar has fully closed at
    current_ts. Bar with open=t0 closes at t0 + tf_seconds; include row
    iff t0 + tf_seconds <= current_ts.

    Uses pandas Timestamp arithmetic for tz-safe comparison.

    Mass conservation: every row in the source DataFrame is either
    included or excluded — no row is silently dropped. Asserted runtime
    per CLAUDE.md §16 Rubric 3 (catches the failure shape that the
    filter_stale_symbols silent-drop bug was written to prevent).
    """
    ts_pd = pd.Timestamp(current_ts)
    if ts_pd.tz is None:
        ts_pd = ts_pd.tz_localize("UTC")
    sliced: Dict[str, pd.DataFrame] = {}
    for tf, df in full_by_tf.items():
        tf_lower = tf.lower()
        if tf_lower not in TF_SECONDS:
            logger.warning("Replay slice: unknown TF '%s', skipping", tf)
            continue
        if df is None or len(df) == 0:
            continue
        tf_delta = pd.Timedelta(seconds=TF_SECONDS[tf_lower])
        # Use the timestamp column (always present after normalize_and_validate)
        # NOT df.index — DatetimeIndex may carry timezone-naive timestamps in
        # some adapter paths and break the tz comparison.
        ts_col = pd.to_datetime(df["timestamp"], utc=True)
        mask = (ts_col + tf_delta) <= ts_pd
        included = int(mask.sum())
        if mask.any():
            sliced_df = df[mask].copy()
            # Mass conservation: the .copy() must produce exactly `included`
            # rows. Catches indexing misalignment or row loss between mask
            # computation and downstream consumption (the failure shape
            # Rubric 3 exists to prevent — see filter_stale_symbols incident).
            assert len(sliced_df) == included, (
                f"Replay slice row count drift for TF {tf_lower}: "
                f"mask selected {included} rows but sliced DataFrame has "
                f"{len(sliced_df)} — silent row loss between mask and copy"
            )
            # Bar-close invariant: every retained row's bar_close must be
            # <= current_ts. Catches mask-vs-comparison drift (e.g. if a
            # future refactor breaks the <= → < flip the operator's first
            # symmetry concern).
            retained_close = pd.to_datetime(sliced_df["timestamp"], utc=True) + tf_delta
            assert (retained_close <= ts_pd).all(), (
                f"Replay slice bar-close invariant broken for TF {tf_lower}: "
                f"row with bar_close > current_ts={ts_pd} retained "
                f"(max retained close = {retained_close.max()})"
            )
            sliced[tf] = sliced_df
        # else: no bars closed yet, skip (downstream rejects "no data")
    return sliced


def _serialize_confluence(breakdown) -> Optional[Dict[str, Any]]:
    if breakdown is None:
        return None
    return {
        "total_score": float(breakdown.total_score),
        "synergy_bonus": float(breakdown.synergy_bonus),
        "conflict_penalty": float(breakdown.conflict_penalty),
        "regime": breakdown.regime,
        "htf_aligned": bool(breakdown.htf_aligned),
        "btc_impulse_gate": bool(breakdown.btc_impulse_gate),
        "direction": breakdown.direction,
        "factors": [
            {
                "name": f.name,
                "score": float(f.score),
                "weight": float(f.weight),
                "weighted_contribution": float(f.score * f.weight),
                "rationale": f.rationale,
            }
            for f in breakdown.factors
        ],
        # Metadata is a free-form dict; coerce nested numpy/datetime scalars
        # so the Pydantic response serializer doesn't raise on them.
        "metadata": _to_jsonable(dict(breakdown.metadata or {})),
    }


def _serialize_smc(snapshot) -> Optional[Dict[str, Any]]:
    if snapshot is None:
        return None

    def _safe_list(items):
        """Serialize each SMC snapshot list item. Items may be either
        dataclass-like objects (OrderBlock, FVG, StructuralBreak,
        LiquiditySweep, HTFLevel — have __dict__) or plain price scalars
        (equal_highs/equal_lows are float lists). Handle both shapes so
        we don't silently drop the scalar lists (the earlier bug)."""
        out = []
        skipped = 0
        for item in items or []:
            try:
                if hasattr(item, "__dict__"):
                    out.append({
                        k: _to_jsonable(v)
                        for k, v in item.__dict__.items()
                        if not k.startswith("_")
                    })
                elif isinstance(item, dict):
                    out.append({
                        str(k): _to_jsonable(v)
                        for k, v in item.items()
                        if not str(k).startswith("_")
                    })
                else:
                    # Scalar (float price level) — coerce numpy → Python
                    out.append(_to_jsonable(item))
            except Exception as e:
                # Skip this item but DON'T silently eat it — log the type +
                # error so a replay payload with shape regressions surfaces
                # in the operator's console instead of becoming an
                # invisible empty list. CLAUDE.md §15 forbids silent
                # exception suppression.
                skipped += 1
                logger.debug(
                    "Replay SMC serialize skipped {}: {}",
                    type(item).__name__, e,
                )
        if skipped:
            logger.warning(
                "Replay SMC serialize: {}/{} items skipped (see debug log)",
                skipped, skipped + len(out),
            )
        return out

    return {
        "order_blocks": _safe_list(getattr(snapshot, "order_blocks", [])),
        "fvgs": _safe_list(getattr(snapshot, "fvgs", [])),
        "structural_breaks": _safe_list(getattr(snapshot, "structural_breaks", [])),
        "liquidity_sweeps": _safe_list(getattr(snapshot, "liquidity_sweeps", [])),
        "equal_highs": _safe_list(getattr(snapshot, "equal_highs", [])),
        "equal_lows": _safe_list(getattr(snapshot, "equal_lows", [])),
        "htf_levels": _safe_list(getattr(snapshot, "htf_levels", [])),
    }


def _serialize_plan(plan) -> Optional[Dict[str, Any]]:
    if plan is None:
        return None
    try:
        return {
            "direction": plan.direction,
            "setup_type": getattr(plan, "setup_type", None),
            "confidence_score": float(getattr(plan, "confidence_score", 0)),
            "risk_reward": float(getattr(plan, "risk_reward", 0)),
            "entry_zone": {
                "near": float(plan.entry_zone.near_entry),
                "far": float(plan.entry_zone.far_entry),
            },
            "stop_loss": (
                {
                    "level": float(plan.stop_loss.level),
                    "distance_atr": float(getattr(plan.stop_loss, "distance_atr", 0)),
                    "rationale": getattr(plan.stop_loss, "rationale", ""),
                }
                if getattr(plan, "stop_loss", None)
                else None
            ),
            "targets": [
                {"level": float(t.level), "label": getattr(t, "label", "")}
                for t in (getattr(plan, "targets", []) or [])
            ],
        }
    except Exception as e:
        logger.warning("Replay plan serialization failed: %s", e)
        return {"direction": getattr(plan, "direction", None), "_serialization_error": str(e)}


def _serialize_regime(regime) -> Optional[Dict[str, Any]]:
    if regime is None:
        return None
    return {
        "composite": getattr(regime, "composite", None),
        "score": float(getattr(regime, "score", 0)),
        "trend": getattr(regime, "trend", None),
        "volatility": getattr(regime, "volatility", None),
    }


class ReplayEngine:
    """Holds replay sessions and orchestrates per-step slicing + pipeline
    execution. Singleton-style: one ReplayEngine per FastAPI process,
    instantiated at router configuration time."""

    def __init__(self, exchange_adapter):
        self._adapter = exchange_adapter
        # Cache enabled so historical HTF candles populated by the live bot
        # don't need to be re-fetched (Phemex limits 1d/4h fetches to ~500
        # candles per request, and the live cache typically holds far more).
        self._pipeline = IngestionPipeline(exchange_adapter, use_cache=True)
        self._sessions: Dict[str, ReplaySession] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def load_session(
        self,
        symbol: str,
        mode_name: str,
        window_start: datetime,
        window_end: datetime,
    ) -> ReplaySession:
        """Pre-fetch all required multi-TF data + BTC for the window, build
        the bar timestamp index, and register a session. Returns the session
        for the router to expose."""
        # Normalize timezone-naive inputs to UTC (frontend may send naive ISO)
        if window_start.tzinfo is None:
            window_start = window_start.replace(tzinfo=timezone.utc)
        if window_end.tzinfo is None:
            window_end = window_end.replace(tzinfo=timezone.utc)

        if window_end <= window_start:
            raise ValueError("window_end must be after window_start")
        window_days = (window_end - window_start).total_seconds() / 86400
        if window_days > MAX_WINDOW_DAYS:
            raise ValueError(
                f"Window {window_days:.1f}d exceeds {MAX_WINDOW_DAYS}d cap"
            )

        try:
            mode: ScannerMode = get_mode(mode_name)
        except ValueError as e:
            raise ValueError(f"Unknown mode '{mode_name}': {e}")

        tf_step = mode.primary_planning_timeframe.lower()
        if tf_step not in TF_SECONDS:
            raise ValueError(f"Mode '{mode_name}' has unsupported tf_step '{tf_step}'")

        logger.info(
            "Replay session loading: symbol=%s mode=%s window=%s→%s days=%.1f tf_step=%s",
            symbol, mode_name, window_start.isoformat(),
            window_end.isoformat(), window_days, tf_step,
        )

        # Pre-fetch all TFs for symbol + BTC. Warmup buffer pulled implicitly
        # because we fetch `limit` candles ending at window_end (or now), then
        # filter to the window after.
        multi_tf_full = self._fetch_window(symbol, list(mode.timeframes), window_end, mode.profile)
        btc_full = self._fetch_window(BTC_SYMBOL, list(mode.timeframes), window_end, mode.profile)

        if tf_step not in multi_tf_full:
            raise ValueError(
                f"Required tf_step '{tf_step}' not fetched for {symbol}. "
                f"Got: {list(multi_tf_full.keys())}"
            )

        # Build bar timestamps for the playback TF — opens that fall inside
        # [window_start, window_end). Each becomes an addressable step index.
        tf_step_df = multi_tf_full[tf_step]
        ts_col = pd.to_datetime(tf_step_df["timestamp"], utc=True)
        window_start_pd = pd.Timestamp(window_start)
        window_end_pd = pd.Timestamp(window_end)
        in_window = (ts_col >= window_start_pd) & (ts_col < window_end_pd)
        bar_opens_pd = ts_col[in_window].sort_values().tolist()
        bar_timestamps = [pd.Timestamp(t).to_pydatetime() for t in bar_opens_pd]

        if not bar_timestamps:
            raise ValueError(
                f"No {tf_step} bars in window {window_start.isoformat()}→{window_end.isoformat()} "
                f"for {symbol}. Fetched {len(tf_step_df)} {tf_step} candles "
                f"({ts_col.min()} → {ts_col.max()}). Window may pre-date exchange data."
            )

        # Per-session orchestrator with replay_mode=True
        orchestrator = self._build_orchestrator(mode)

        session_id = uuid.uuid4().hex
        session = ReplaySession(
            session_id=session_id,
            symbol=symbol,
            mode_name=mode.name,
            window_start=window_start,
            window_end=window_end,
            multi_tf_full=multi_tf_full,
            btc_full=btc_full,
            tf_step=tf_step,
            bar_timestamps=bar_timestamps,
            orchestrator=orchestrator,
            step_index=-1,
        )

        with self._lock:
            self._gc_idle_locked()
            self._sessions[session_id] = session
            logger.info(
                "Replay session loaded: id=%s symbol=%s mode=%s bars=%d sessions_active=%d",
                session_id, symbol, mode.name, len(bar_timestamps), len(self._sessions),
            )
        return session

    def get_session(self, session_id: str) -> Optional[ReplaySession]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.last_touched = datetime.now(timezone.utc)
            return session

    def end_session(self, session_id: str) -> bool:
        with self._lock:
            removed = self._sessions.pop(session_id, None)
        if removed:
            logger.info("Replay session ended: id=%s", session_id)
        return removed is not None

    # ------------------------------------------------------------------
    # Per-bar stepping
    # ------------------------------------------------------------------

    def step(self, session_id: str, n: int = 1) -> StepResult:
        """Advance (or retreat) the playback by `n` bars and return the
        StepResult for the new position. Negative `n` goes back; within the
        ring buffer the cached result is returned, otherwise the engine
        recomputes from window_start to the target index."""
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(f"Session {session_id} not found or expired")

        target = session.step_index + n
        # Clamp target into valid range. Index 0 = first bar; -1 means "not started"
        if target < 0:
            target = 0
        if target >= session.total_bars:
            target = session.total_bars - 1

        return self._goto_index(session, target)

    def goto(self, session_id: str, index: int) -> StepResult:
        """Jump to absolute index (used by timeline-scrub and jump-to-signal)."""
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(f"Session {session_id} not found or expired")
        if index < 0 or index >= session.total_bars:
            raise IndexError(
                f"Index {index} out of range [0, {session.total_bars - 1}] for session {session_id}"
            )
        return self._goto_index(session, index)

    def jump_to_next_signal(
        self, session_id: str, max_lookahead: int = 100
    ) -> Tuple[Optional[StepResult], int]:
        """Step forward up to `max_lookahead` bars until a signal fires
        (plan is not None). Returns (StepResult, bars_advanced). If no
        signal fires within the lookahead, returns (None, bars_advanced)
        with the session positioned at the final scanned bar."""
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(f"Session {session_id} not found or expired")

        bars_advanced = 0
        # Start from the bar after the current position
        start = session.step_index + 1
        end = min(start + max_lookahead, session.total_bars)
        for idx in range(start, end):
            result = self._goto_index(session, idx)
            bars_advanced += 1
            if result.signal_fired:
                return result, bars_advanced
        # No signal found
        return None, bars_advanced

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _goto_index(self, session: ReplaySession, target: int) -> StepResult:
        """Move to absolute `target` index. Honors ring buffer; recomputes
        if target is outside the cached range."""
        # Ring buffer lookup — only valid for back-scrubs within depth
        if target < session.step_index:
            for cached in reversed(session.ring_buffer):
                if cached.index == target:
                    session.step_index = target
                    logger.debug(
                        "Replay: back-scrub hit ring buffer at idx=%d (session=%s)",
                        target, session.session_id,
                    )
                    return cached
            # Back-scrub beyond ring → reset and recompute up to target
            logger.info(
                "Replay: back-scrub beyond ring depth — recomputing 0..%d (session=%s)",
                target, session.session_id,
            )
            session.ring_buffer.clear()
            session.step_index = -1

        # Compute the missing bars sequentially up to target. For a single
        # forward step this is just one compute. For a deep back-scrub it
        # may be many — frontend shows the "recomputing…" indicator.
        result: Optional[StepResult] = None
        while session.step_index < target:
            session.step_index += 1
            result = self._compute_step(session, session.step_index)
            session.ring_buffer.append(result)
        assert result is not None, "Should have computed at least one bar"
        return result

    def _compute_step(self, session: ReplaySession, index: int) -> StepResult:
        """Slice data, run orchestrator, return StepResult. Pure of side
        effects on the session (caller manages step_index + ring buffer)."""
        bar_open = session.bar_timestamps[index]
        tf_step_secs = TF_SECONDS[session.tf_step]
        current_ts = bar_open + timedelta(seconds=tf_step_secs)

        sliced_symbol = _slice_to_bar_close(session.multi_tf_full, current_ts)
        sliced_btc = _slice_to_bar_close(session.btc_full, current_ts)

        candles_payload: Dict[str, List[Dict[str, Any]]] = {}
        for tf, df in sliced_symbol.items():
            candles_payload[tf] = _candles_to_payload(df)

        # If a critical TF didn't make it through slicing (e.g. very early
        # in the window before the HTF bar has formed), surface an empty
        # rejection rather than calling the orchestrator with garbage.
        if not sliced_symbol:
            return StepResult(
                index=index,
                bar_open_ts=bar_open,
                current_ts=current_ts,
                candles_by_tf=candles_payload,
                rejection={
                    "reason_type": "no_data_at_replay_index",
                    "reason": "No closed bars yet at this index — try a later bar",
                },
                signal_fired=False,
            )

        # Wrap sliced dicts as MultiTimeframeData (the orchestrator's
        # downstream consumers expect that shape)
        symbol_data = MultiTimeframeData(symbol=session.symbol, timeframes=sliced_symbol)
        btc_data = (
            MultiTimeframeData(symbol=BTC_SYMBOL, timeframes=sliced_btc) if sliced_btc else None
        )

        run_id = f"replay-{session.session_id}-{index}"
        try:
            plan, rejection, context = session.orchestrator.process_symbol_for_replay(
                symbol=session.symbol,
                prefetched_data=symbol_data,
                timestamp=current_ts,
                run_id=run_id,
                playback_index=index,
                session_id=session.session_id,
                prefetched_btc_data=btc_data,
            )
        except Exception as e:
            # Loud failure (CLAUDE.md §12) but don't kill the session —
            # surface as a structured rejection so the operator can see it
            logger.exception("Replay step failed at index=%d: %s", index, e)
            return StepResult(
                index=index,
                bar_open_ts=bar_open,
                current_ts=current_ts,
                candles_by_tf=candles_payload,
                rejection={"reason_type": "replay_pipeline_error", "reason": str(e)},
                signal_fired=False,
            )

        return StepResult(
            index=index,
            bar_open_ts=bar_open,
            current_ts=current_ts,
            candles_by_tf=candles_payload,
            confluence=_serialize_confluence(
                context.confluence_breakdown if context else None
            ),
            plan=_serialize_plan(plan),
            rejection=rejection,
            smc_snapshot=_serialize_smc(context.smc_snapshot if context else None),
            regime=_serialize_regime(session.orchestrator.current_regime),
            signal_fired=plan is not None,
        )

    def _build_orchestrator(self, mode: ScannerMode) -> Orchestrator:
        """Construct a dedicated Orchestrator for a replay session. The
        instance is replay_mode=True (sticky) — never re-used for live scans."""
        # Build a config aligned with the mode. ScanConfig is constructed by
        # apply_mode internally, but we need a starting config.
        config = ScanConfig(
            profile=mode.profile,
            timeframes=tuple(mode.timeframes),
            min_confluence_score=mode.min_confluence_score,
        )
        # The Orchestrator constructor will call apply_mode() and stamp the
        # mode-specific overrides into config.
        return Orchestrator(
            config=config,
            exchange_adapter=self._adapter,
            concurrency_workers=1,
            replay_mode=True,
        )

    def _fetch_window(
        self,
        symbol: str,
        timeframes: List[str],
        window_end: datetime,
        mode_profile: str,
    ) -> Dict[str, pd.DataFrame]:
        """Fetch + normalize each TF up to window_end. Reuses the
        IngestionPipeline so the live OHLCV cache is consulted first
        (historical HTF candles accumulated by the live bot avoid the
        Phemex ~500-candle-per-request ceiling that limits cold cold-starts).

        For windows beyond what the cache holds, the adapter request is
        capped at 500 candles (Phemex error 30000 threshold). 30-day stealth
        replay typically cache-hits because the bot has been streaming
        those TFs continuously; a cold cache may force shorter windows.
        """
        # The pipeline's fetch_multi_timeframe handles cache + adapter call
        # + normalize_and_validate in one shot. Use mode profile so per-TF
        # limits scale (swing modes get more HTF candles).
        try:
            mtf = self._pipeline.fetch_multi_timeframe(
                symbol=symbol,
                timeframes=[tf.lower() for tf in timeframes],
                limit=500,  # Phemex error-30000-safe ceiling; cache fills the rest
            )
        except Exception as e:
            raise ValueError(f"Pipeline fetch failed for {symbol}: {e}")

        out: Dict[str, pd.DataFrame] = {}
        window_end_pd = pd.Timestamp(window_end)
        for tf, df in mtf.timeframes.items():
            if df is None or len(df) == 0:
                logger.warning("Replay fetch returned empty for %s %s", symbol, tf)
                continue
            # Filter to <= window_end (drop any bar opening after window_end)
            ts_col = pd.to_datetime(df["timestamp"], utc=True)
            filtered = df[ts_col <= window_end_pd].copy()
            if len(filtered):
                out[tf] = filtered
                logger.debug(
                    "Replay window %s %s: %d candles (range %s → %s)",
                    symbol, tf, len(filtered),
                    filtered["timestamp"].iloc[0],
                    filtered["timestamp"].iloc[-1],
                )
            else:
                logger.warning(
                    "Replay %s %s: all %d fetched candles after window_end=%s, dropped",
                    symbol, tf, len(df), window_end,
                )

        if not out:
            raise ValueError(
                f"No timeframes survived window filter for {symbol}. "
                f"Window end {window_end} may be too far in the past for the "
                f"OHLCV cache + 500-candle adapter limit."
            )
        return out

    def _gc_idle_locked(self) -> int:
        """Drop sessions idle past SESSION_IDLE_TTL_SECONDS. Caller must hold
        self._lock. Returns count removed."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=SESSION_IDLE_TTL_SECONDS)
        stale = [sid for sid, s in self._sessions.items() if s.last_touched < cutoff]
        for sid in stale:
            self._sessions.pop(sid, None)
            logger.info("Replay GC: dropped idle session %s", sid)
        return len(stale)


# Singleton accessor — router configures it at startup with the live adapter
_REPLAY_ENGINE: Optional[ReplayEngine] = None
_REPLAY_ENGINE_LOCK = threading.Lock()


def configure_replay_engine(exchange_adapter) -> ReplayEngine:
    """Initialize the process-wide replay engine. Called once from
    api_server startup with the live exchange adapter."""
    global _REPLAY_ENGINE
    with _REPLAY_ENGINE_LOCK:
        _REPLAY_ENGINE = ReplayEngine(exchange_adapter)
    return _REPLAY_ENGINE


def get_replay_engine() -> ReplayEngine:
    if _REPLAY_ENGINE is None:
        raise RuntimeError(
            "Replay engine not configured. Call configure_replay_engine(adapter) at startup."
        )
    return _REPLAY_ENGINE
