"""
Paper Trading Service

Orchestrates the full paper trading workflow:
- Scanner integration (using Orchestrator)
- Paper order execution
- Position management with SL/TP monitoring
- Trade lifecycle tracking

This service ties together the scanner logic with paper execution,
allowing users to test trading strategies without real capital.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
import asyncio
import json
import logging
import uuid
from pathlib import Path
import time

from backend.strategy.smc.sessions import get_current_kill_zone
from backend.bot.executor.paper_executor import PaperExecutor, OrderStatus, OrderType
from backend.bot.executor.position_manager import PositionManager, PositionStatus
from backend.bot.telemetry.storage import TelemetryStorage
from backend.bot.telemetry.events import TelemetryEvent, EventType
from backend.engine.orchestrator import Orchestrator
from backend.engine.decision import is_fresh_entry_price, is_thesis_mode
from backend.shared.config.scanner_modes import get_mode, ScannerMode
from backend.shared.config.defaults import ScanConfig
from backend.shared.models.planner import TradePlan
from backend.data.adapters.phemex import PhemexAdapter
from backend.analysis.regime_policies import get_regime_policy
from backend.shared.utils.math_utils import round_to_lot
from backend.diagnostics.logger import DiagnosticLogger, ProbeCategory, Severity
from backend.diagnostics.report import ReportGenerator, ModeStats
from backend.bot.trade_journal import get_trade_journal

logger = logging.getLogger(__name__)

# Pending order TTL by trade type. Swing limit orders targeting HTF demand zones
# may not get retested for hours; the old flat 10-min TTL was silently killing them.
_PENDING_TTL_MINUTES: Dict[str, float] = {
    "swing": 240.0,    # 4 hours
    "intraday": 120.0, # 2 hours — crypto intraday pullbacks often take 90–120 min
    "scalp": 10.0,     # 2 scan cycles
}
# Max number of adaptive TTL extensions per order (each extension = 50% of original TTL)
_MAX_TTL_EXTENSIONS = 2

# Maximum distance (%) a limit order can be placed from current price.
# If the OB entry zone is further away, the limit is "snapped" closer to price
# so the order actually has a chance of filling within the TTL window.
# For high-confluence signals (>= 70%), the max distance is halved.
_MAX_LIMIT_DISTANCE_PCT: Dict[str, float] = {
    "scalp": 0.15,     # ~$0.20 on a $130 coin
    "intraday": 0.40,  # ~$0.52 on a $130 coin
    "swing": 1.00,     # wider — retests can take hours
}


def _entry_realized_rr(entry: float, stop: float, targets: List[float]) -> float:
    """Realized risk:reward at the ACTUAL fill — reward to the nearest target vs risk
    to the stop, both measured from ``entry``.

    Differs from the plan's ``risk_reward_ratio`` (computed off ``entry_zone.midpoint``
    in the planner) whenever the fill deviates from plan — e.g. a snap_taker entry that
    chased the tape and collapsed reward-to-TP1 while widening risk-to-stop. Single
    source of truth for both the entry RR-floor gate and the journal ``realized_rr``
    key so the two cannot drift. Symmetric: abs() handles LONG (risk=entry-stop,
    reward=tp-entry) and SHORT (risk=stop-entry, reward=entry-tp) identically.

    Returns 0.0 when geometry is unavailable (missing entry/stop/targets or zero risk).
    See decisions/2026-06-13__fill-geometry-distortion.md.
    """
    if not entry or not stop or not targets:
        return 0.0
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    nearest_tp = min(targets, key=lambda t: abs(t - entry))
    reward = abs(nearest_tp - entry)
    return reward / risk


def _rr_bounded_snap(
    side: str,
    desired_limit: float,
    raw_limit: float,
    stop: float,
    nearest_tp: float,
    rr_floor: float,
) -> float:
    """Clamp a snapped limit price so realized RR stays >= ``rr_floor`` (heart-change Form-B fix).

    The limit snap chases the entry toward market to improve fill odds; it keeps $-risk constant
    but SHRINKS reward (entry nears TP1, stop widens), which can invert geometry to a sub-floor RR
    the entry gate then rejects — wasting a valid setup. This caps the snap at the price where
    realized RR == rr_floor, so it goes as far toward market as the floor allows and no further.

    Geometry: RR == rr_floor  <=>  |tp - limit| / |limit - stop| == rr_floor
              =>  limit == (rr_floor*stop + tp) / (1 + rr_floor)   (one root, both directions).
    BUY (long): higher limit -> lower RR, so cap ABOVE at the bound, never snap BELOW the OB.
    SELL (short): lower limit -> lower RR, so floor BELOW at the bound, never snap ABOVE the OB.
    If even ``raw_limit`` (the OB edge) is already sub-floor, the clamp returns ``raw_limit`` (no
    snap) and the downstream RR gate correctly rejects (genuinely bad geometry, not snap-induced).
    Symmetric by construction; returns ``desired_limit`` unchanged when geometry is unusable.
    """
    if rr_floor <= 0 or stop <= 0 or nearest_tp <= 0 or raw_limit <= 0:
        return desired_limit
    rr_bound = (rr_floor * stop + nearest_tp) / (1.0 + rr_floor)
    if str(side).upper() == "BUY":
        return max(min(desired_limit, rr_bound), raw_limit)
    return min(max(desired_limit, rr_bound), raw_limit)


def _pool_price_swept(node: Any) -> "tuple[Optional[float], Optional[bool]]":
    """Resolve (price, swept) from a single KeyLevels.to_dict() pool node.

    Mirrors risk_engine._pool_price's robustness (dict {"price","swept"} | flat float |
    KeyLevel-like .price) but ALSO surfaces the ``swept`` flag so the journal can record
    whether the nearest pool was already swept liquidity at entry (the adversarial review
    flagged that discarding ``swept`` would let the audit attribute a stop-out to a pool
    that no longer held liquidity). Returns (None, None) on anything malformed — never raises.
    """
    if node is None:
        return None, None
    if isinstance(node, dict):
        price = node.get("price")
        swept = node.get("swept")
    else:
        price = getattr(node, "price", node)
        swept = getattr(node, "swept", None)
    if isinstance(price, (int, float)) and price > 0:
        return float(price), (bool(swept) if swept is not None else None)
    return None, None


def _nearest_same_side_pool(
    key_levels: Any, entry_ref: float, direction: str, atr: float
) -> "tuple[Optional[str], Optional[float], Optional[float], Optional[bool]]":
    """Find the nearest STATIC liquidity pool on the side the STOP sits, in ATR units.

    Direction-aware and MIRROR-SYMMETRIC (standing fix — bull/bear symmetry):
      - LONG  -> stop sits BELOW entry -> consider pools below entry_ref: pwl, pdl
      - SHORT -> stop sits ABOVE entry -> consider pools above entry_ref: pwh, pdh
    This matches risk_engine._buffer_stop_from_liquidity's ``_attrs`` and side guards
    exactly (pwl/pdl for bullish, pwh/pdh for bearish), so the journal's distance is on
    the same basis the buffer measures. Pool universe is the SMCSnapshot.key_levels dict
    (pwl/pwh/pdh/pdl only) — EQH/EQL pools are NOT here (separate multi_tf scan), so this
    distance is "nearest static prior-week/day pool", not "nearest of ALL pools".

    Returns (label, price, dist_atr, swept) for the nearest qualifying pool, or
    (None, None, None, None) if key_levels is missing/malformed, atr<=0, or no pool sits
    on the stop side. NEVER raises (loud WARNING on malformed input is the caller's job).
    Distance is computed regardless of the ``swept`` status (swept is reported, not filtered).
    """
    if not key_levels or not isinstance(key_levels, dict):
        return None, None, None, None
    if not atr or atr <= 0 or not entry_ref:
        return None, None, None, None

    _dir = str(direction).upper()
    if _dir not in ("LONG", "SHORT"):
        # Loud-failure guard: the helper accepts only the two canonical directions the
        # callers emit. An unexpected token must NOT silently default to one side
        # (would break mirror symmetry). Return all-None rather than guess.
        logger.warning(
            "_nearest_same_side_pool: unexpected direction %r — returning null pool context",
            direction,
        )
        return None, None, None, None
    is_long = _dir == "LONG"
    attrs = ("pwl", "pdl") if is_long else ("pwh", "pdh")

    best_label: Optional[str] = None
    best_price: Optional[float] = None
    best_dist: Optional[float] = None
    best_swept: Optional[bool] = None
    for attr in attrs:
        price, swept = _pool_price_swept(key_levels.get(attr))
        if price is None:
            continue
        # Side guard: LONG keeps pools below entry; SHORT keeps pools above entry.
        on_stop_side = (price < entry_ref) if is_long else (price > entry_ref)
        if not on_stop_side:
            continue
        dist_atr = abs(entry_ref - price) / atr
        if best_dist is None or dist_atr < best_dist:
            best_label, best_price, best_dist, best_swept = attr.upper(), price, dist_atr, swept

    return best_label, best_price, best_dist, best_swept


# Signal Sensitivity preset definitions.
# gate  = minimum score for full-size entry
# floor = minimum score for near-miss half-size entry; below floor = skipped
# Tier ordering: aggressive < balanced < conservative (tightening direction)
_SENSITIVITY_PRESETS: Dict[str, Dict[str, float]] = {
    "conservative": {"gate": 72.0, "floor": 62.0},
    "balanced":     {"gate": 65.0, "floor": 55.0},
    "aggressive":   {"gate": 58.0, "floor": 48.0},
}
# One tier up from each preset (for drawdown-linked tightening)
_PRESET_TIER_UP: Dict[str, str] = {
    "aggressive":   "balanced",
    "balanced":     "conservative",
    "conservative": "conservative",   # already at top
    "custom":       "conservative",   # custom always caps at conservative
}



class PaperBotStatus(Enum):
    """Paper trading bot status."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class PaperTradingConfig:
    """
    Configuration for paper trading session.

    Attributes:
        exchange: Exchange profile for pricing
        sniper_mode: Bot strategy mode (stealth, surgical, strike, overwatch)
        initial_balance: Starting paper money (USDT)
        risk_per_trade: % of balance to risk per trade (0-100)
        max_positions: Maximum concurrent open positions
        leverage: Leverage multiplier
        duration_hours: Auto-stop after X hours (0 = manual)
        scan_interval_minutes: How often to run scanner
        trailing_stop: Enable trailing stops
        trailing_activation: R-multiple to activate trailing
        breakeven_after_target: Move SL to entry after Nth target
        min_confluence: Minimum confluence score for full-size entry (None = use mode default).
            Part of the Signal Sensitivity system — acts as the "full-size gate".
        confluence_soft_floor: Signals between this and min_confluence execute at half size.
            Signals below the floor are skipped entirely. None = no near-miss band
            (hard gate only). Resolved automatically from sensitivity_preset if not set.
        sensitivity_preset: Which preset the user chose — "conservative", "balanced",
            "aggressive", or "custom". Drives gate/floor defaults and appears in logs.
        symbols: Specific pairs to trade (empty = use scanner defaults)
        exclude_symbols: Pairs to exclude
        slippage_bps: Flat slippage fallback (basis points). Prefer major_slippage_bps /
            alt_slippage_bps for per-class accuracy; this field kept for testnet path compat.
        fee_rate: Legacy flat fee rate. Use taker_fee_rate / maker_fee_rate for paper sessions.
        taker_fee_rate: Phemex taker fee (0.06%) — used for snap_taker paper sessions.
        maker_fee_rate: Phemex maker fee (0.01%) — used for rest_maker paper sessions.
        major_slippage_bps: Slippage for BTC/ETH (tighter spread, ~10 bps).
        alt_slippage_bps: Slippage for all other alts (wider spread, ~35 bps).
    """

    exchange: str = "phemex"
    sniper_mode: str = "stealth"  # Fixed: stealth mode is the optimal balance for paper trading (adaptive scalp/swing)
    initial_balance: float = 10000.0
    risk_per_trade: float = 1.0  # Reduced from 2.0%: safer for automated trading (3 positions * 1% = 3% max risk)
    max_positions: int = 3
    leverage: int = 1
    duration_hours: int = 24
    scan_interval_minutes: int = 2
    trailing_stop: bool = True
    trailing_activation: float = 1.5
    breakeven_after_target: int = 1
    min_confluence: Optional[float] = None
    confluence_soft_floor: Optional[float] = None
    sensitivity_preset: str = "balanced"
    symbols: List[str] = field(default_factory=list)
    exclude_symbols: List[str] = field(default_factory=list)
    majors: bool = True
    altcoins: bool = False
    meme_mode: bool = False
    slippage_bps: float = 15.0  # Fallback / testnet-path compat (was 5.0 → bumped 2026)
    fee_rate: float = 0.001  # Legacy flat rate (testnet/LiveExecutor path); paper uses taker/maker below
    taker_fee_rate: float = 0.0006  # Phemex taker 0.06% — snap_taker paper sessions
    maker_fee_rate: float = 0.0001  # Phemex maker 0.01% — rest_maker paper sessions
    major_slippage_bps: float = 10.0  # BTC/ETH (tight spread)
    alt_slippage_bps: float = 35.0   # All other alts (wider spread)
    max_hours_open: float = 72.0
    max_pending_scans: int = 2  # Cancel pending limit orders after this many scan cycles
    max_drawdown_pct: Optional[float] = 10.0  # Kill switch: stop session if peak-to-trough drawdown exceeds X%
    use_testnet: bool = False  # Route orders through Phemex testnet instead of simulating
    # Execution mode (maker-execution experiment, decisions/2026-06-06__maker-execution-experiment-design.md):
    #   "snap_taker" (default) = current behavior: snap the limit to ~market + fill immediately (taker).
    #   "rest_maker" = rest the limit at the OB (entry_zone), no snap, fill only when price retraces (maker).
    # PAPER ONLY: rest_maker is forced to snap_taker when use_testnet=True (live-executor bleed guard).
    execution_mode: str = "snap_taker"
    ml_gate_threshold: float = 0.40  # Reject signals with ML win probability below this (0 = disabled)
    universe_size: int = 20  # How many pairs to scan per cycle (dynamic selection pulls top N by volume/momentum)
    # Macro/dominance overlay (BTC.D / stable.D / alt.D → directional score adj, scorer.py:3114).
    # Default True = back-compat (orchestrator default is True at defaults.py:40; surfacing the
    # toggle does NOT change behavior). Operator can set False to run pure-technicals (see ledger T19).
    macro_overlay_enabled: bool = True
    # Realized-RR floor at entry (fill-geometry guard, decisions/2026-06-13__fill-geometry-distortion.md).
    # Reject an entry whose realized reward-to-TP1 / risk-to-stop at the ACTUAL fill (snapped
    # limit_price) falls below this floor — catches snap_taker chasing that inverts the planned
    # geometry (the snap recomputes size for risk but never re-checks reward). 1.0 = empirical
    # breakpoint where the historical cohort flips net-negative (baseline n=101: <1.0 avg -1.27,
    # >=1.0 avg +5.02). 0 disables the gate.
    rr_floor_at_entry: float = 1.0
    # Account-aware symbol admission (decisions/2026-06-28__account-aware-liquidity-admission.md).
    # Replaces the fixed liquidity floor with one scaled to the user's market FOOTPRINT
    # (balance × leverage) — a $20 order can't move a $2M book, so a small account may trade thinner
    # Phemex pairs, while a leveraged/large account is held to deeper books ("$1k at 20× IS a $20k
    # position"). Flag-gated: "fixed" (default) runs the existing scanner_modes.min_24h_volume_usdt
    # path BYTE-IDENTICALLY; "account_aware" derives the floor + applies the min-order / liquidation
    # guards. §15/§9-A "don't trade illiquid pairs" standing rule — paper-only first (live deferred).
    liquidity_mode: str = "fixed"  # "fixed" | "account_aware"
    participation_rate: float = 0.005  # position should be <= 0.5% of 24h volume (Gate 1)
    hard_min_volume_usdt: float = 500_000.0  # absolute floor; small accounts governed by this (never a dead/wash market)
    min_order_stop_pct_assumption: float = 0.01  # Gate 2 coarse universe pre-filter stop% (precise check is per-plan)
    thin_book_liq_buffer_mult: float = 1.5  # Gate 3 extra liquidation cushion on thin-book symbols
    # Depth-aware admission (the real fix for volume!=depth — NEAR ran $5M/24h with ~$2 at the touch).
    # Within account_aware mode, after the volume floor, fetch the order book for the SURVIVORS and
    # require an acceptable spread + near-touch depth vs position notional. depth_aware_admission=False
    # falls back to the volume-floor-only gate. Only runs in account_aware mode (bounded survivor set).
    depth_aware_admission: bool = True  # apply the order-book spread/depth gate inside account_aware
    max_spread_bps: float = 15.0  # drop books wider than this at the touch
    min_depth_mult: float = 3.0  # require near-touch depth >= position_notional × this
    depth_band_bps: float = 10.0  # measure resting depth within this band of mid
    # Gate 2 — min-order risk guard: drop a pair whose smallest allowed order × stop% exceeds the
    # per-trade risk budget (balance × risk%). Leverage-independent. Near-inert on Phemex (mins $1-60).
    min_order_risk_guard: bool = True  # apply the min-order risk gate inside account_aware
    # Gate 3 — liquidation-safety guard (leverage-driven): drop a pair where no viable stop could sit
    # safely inside the liquidation price at the configured leverage (thin books need a bigger cushion —
    # wick-liquidation). INERT at leverage<=1 (no liquidation). Complements the plan-time
    # _adjust_stop_for_leverage backstop. Covers both the no-leverage and the leverage user.
    liquidation_safety_guard: bool = True  # apply the liquidation-safety gate inside account_aware
    liquidation_min_stop_pct: float = 0.015  # tightest plausible stop for the universe pre-screen

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PaperTradingConfig":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @property
    def rest_maker_active(self) -> bool:
        """True iff resting-maker execution is active: execution_mode is "rest_maker" AND NOT
        use_testnet. The maker experiment is PAPER-ONLY — under testnet the executor is a
        LiveExecutor, so rest_maker is force-disabled (§15 live-path guard, design entry
        2026-06-06__maker-execution-experiment-design.md). Single source of truth for the toggle."""
        return self.execution_mode == "rest_maker" and not self.use_testnet


@dataclass
class CompletedTrade:
    """
    Record of a completed paper trade.

    Attributes:
        trade_id: Unique trade identifier
        symbol: Trading pair
        direction: LONG or SHORT
        entry_price: Average entry price
        exit_price: Average exit price (or current if still open)
        quantity: Position size
        entry_time: When position was opened
        exit_time: When position was closed
        pnl: Profit/loss in USDT
        pnl_pct: Profit/loss percentage
        exit_reason: Why the trade was closed (target, stop, manual)
        targets_hit: List of targets that were hit
        max_favorable: Maximum favorable excursion (MFE)
        max_adverse: Maximum adverse excursion (MAE)
    """

    trade_id: str
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: datetime
    exit_time: Optional[datetime]
    pnl: float
    pnl_pct: float
    exit_reason: str
    targets_hit: List[int] = field(default_factory=list)
    max_favorable: float = 0.0
    max_adverse: float = 0.0
    trade_type: str = "intraday"  # "scalp", "intraday", "swing"

    # ML feature snapshot — populated from PositionState (which captures from TradePlan at open)
    confidence_score: float = 0.0
    conviction_class: str = "B"
    plan_type: str = "SMC"
    risk_reward_ratio: float = 0.0
    stop_distance_atr: float = 0.0
    timeframe: str = "1h"
    regime: str = "unknown"
    pullback_probability: float = 0.0
    kill_zone: str = "no_session"

    # Diagnostics for the "stagnation-because-targets-stripped" silent-bug class.
    # final_targets_remaining: count of structurally-valid targets still in
    # position.targets at close time (0 means no TP exit was reachable).
    # targets_stripped_count: how many targets the executor's geometry guard
    # removed across the position's lifetime. Both fields let trade-autopsy
    # answer "did this stagnation have a real TP path?" retroactively.
    final_targets_remaining: int = 0
    targets_stripped_count: int = 0

    # Tier 2 — macro snapshot at ENTRY time (not exit) so post-run autopsy
    # can correlate trade outcomes against macro context that was visible
    # to the bot when the decision was made.
    btc_velocity_1h_at_entry: float = 0.0
    alt_velocity_1h_at_entry: float = 0.0
    macro_state_at_entry: str = "unknown"
    regime_trend_at_entry: str = "sideways"  # global regime.dimensions.trend at open
    # Provenance marker (decisions/2026-06-16 §11.6 bug #1): "entry" = `regime` and
    # `regime_trend_at_entry` were captured at OPEN (correct). Journal rows written
    # BEFORE the fix lack this key — edge_by_regime must treat a missing value as
    # CLOSE-labeled (regime bucketing untrustworthy) and exclude such rows from clean
    # regime-conditional cohorts.
    regime_labeled_at: str = "entry"
    # Tier 2 — HTF + setup-archetype snapshot. htf_aligned answers "was the
    # trade counter-HTF at entry?". setup_qualifier ("Soft"/"Strong"/"Unknown")
    # joins trade outcomes against the setup-quality cohort.
    htf_aligned_at_entry: bool = False
    setup_qualifier: str = "Unknown"

    # Calculated stop/target geometry at open (2026-06-02). Persisted so a trade's
    # planned levels are auditable from the journal alone — previously only
    # stop_distance_atr + risk_reward_ratio were stored, not the actual prices.
    #   stop_loss_level — calculated SL price (initial, pre-trail).
    #   target_levels   — calculated TP ladder prices (pre strip/hit).
    #   stop_loss_rationale — encodes the stop branch (structural/cap/fallback).
    #   tp1_clamped / tp1_realized_rr — TP1 reachability-clamp provenance.
    stop_loss_level: float = 0.0
    target_levels: List[float] = field(default_factory=list)
    stop_loss_rationale: str = ""
    tp1_clamped: bool = False
    tp1_realized_rr: float = 0.0
    execution_mode: str = "snap_taker"  # maker-execution experiment arm (T14): snap_taker | rest_maker

    # Entry-time SMC liquidity-pool context (2026-06-13, observability-only) — closes the
    # stop_in_pool_audit data wall: the full static pool set at entry was persisted nowhere.
    #   entry_key_levels — the SMCSnapshot.key_levels dict at entry
    #     {pwl/pwh/pdh/pdl: {"price","swept"} | None} (pwl/pwh/pdh/pdl ONLY; EQH/EQL are
    #     from a separate risk_engine multi_tf scan and are NOT in this dict — the
    #     buffer-fire rationale string still records those).
    #   nearest_same_side_pool_* — the nearest static pool on the STOP side (LONG→below,
    #     SHORT→above), the field that lets the audit ask "was the stop near/inside a pool".
    #     dist measured in ATR on the same basis as risk_engine's buffer. swept flag
    #     reported (NOT filtered) so a spent-liquidity pool is distinguishable post-hoc.
    # decisions/2026-06-13__journal-entry-pool-instrumentation.md
    entry_key_levels: Optional[Dict[str, Any]] = None
    nearest_same_side_pool_dist_atr: Optional[float] = None
    nearest_same_side_pool_label: Optional[str] = None
    nearest_same_side_pool_price: Optional[float] = None
    nearest_same_side_pool_swept: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "exit_reason": self.exit_reason,
            "targets_hit": self.targets_hit,
            "max_favorable": self.max_favorable,
            "max_adverse": self.max_adverse,
            "trade_type": self.trade_type,
            "confidence_score": self.confidence_score,
            "conviction_class": self.conviction_class,
            "plan_type": self.plan_type,
            "risk_reward_ratio": self.risk_reward_ratio,
            # Realized RR at the ACTUAL fill (reward-to-TP1 / risk-to-stop). Differs from
            # risk_reward_ratio (planned, off entry_zone.midpoint) when the fill deviated
            # from plan — makes fill-geometry distortion auditable from the journal alone.
            # decisions/2026-06-13__fill-geometry-distortion.md
            "realized_rr": _entry_realized_rr(
                self.entry_price, self.stop_loss_level, list(self.target_levels or [])
            ),
            "stop_distance_atr": self.stop_distance_atr,
            "timeframe": self.timeframe,
            "regime": self.regime,
            "pullback_probability": self.pullback_probability,
            "kill_zone": self.kill_zone,
            "final_targets_remaining": self.final_targets_remaining,
            "targets_stripped_count": self.targets_stripped_count,
            "btc_velocity_1h_at_entry": self.btc_velocity_1h_at_entry,
            "alt_velocity_1h_at_entry": self.alt_velocity_1h_at_entry,
            "macro_state_at_entry": self.macro_state_at_entry,
            "regime_trend_at_entry": self.regime_trend_at_entry,
            "regime_labeled_at": self.regime_labeled_at,
            "htf_aligned_at_entry": self.htf_aligned_at_entry,
            "setup_qualifier": self.setup_qualifier,
            # Calculated stop/target geometry (2026-06-02) — auditable from journal alone.
            "stop_loss_level": self.stop_loss_level,
            "target_levels": self.target_levels,
            "stop_loss_rationale": self.stop_loss_rationale,
            "tp1_clamped": self.tp1_clamped,
            "tp1_realized_rr": self.tp1_realized_rr,
            "execution_mode": self.execution_mode,
            # Entry-time SMC liquidity-pool context (2026-06-13) — see field docstring above
            # and decisions/2026-06-13__journal-entry-pool-instrumentation.md.
            "entry_key_levels": self.entry_key_levels,
            "nearest_same_side_pool_dist_atr": self.nearest_same_side_pool_dist_atr,
            "nearest_same_side_pool_label": self.nearest_same_side_pool_label,
            "nearest_same_side_pool_price": self.nearest_same_side_pool_price,
            "nearest_same_side_pool_swept": self.nearest_same_side_pool_swept,
        }


@dataclass
class PaperTradingStats:
    """
    Statistics for paper trading session.

    Attributes:
        total_trades: Number of completed trades
        winning_trades: Number of profitable trades
        losing_trades: Number of losing trades
        win_rate: Winning percentage
        total_pnl: Total profit/loss
        total_pnl_pct: Total P&L as percentage of initial balance
        avg_win: Average winning trade P&L
        avg_loss: Average losing trade P&L
        avg_rr: Average risk-reward ratio achieved
        best_trade: Largest winning trade P&L
        worst_trade: Largest losing trade P&L
        max_drawdown: Maximum drawdown experienced
        current_streak: Current win/loss streak (positive=wins, negative=losses)
        scans_completed: Number of scanner runs
        signals_generated: Total signals from scanner
        signals_taken: Signals that passed filters and were executed
        exit_reasons: Count of trades by exit reason (target/stop_loss/stagnation/etc.)
        by_trade_type: Per-type breakdown (scalp/intraday/swing) with wins, losses,
                       win_rate, total_pnl, avg_win, avg_loss
    """

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    scratch_trades: int = 0
    win_rate: float = 0.0
    expectancy: float = 0.0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_rr: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    max_drawdown: float = 0.0
    current_streak: int = 0
    scans_completed: int = 0
    signals_generated: int = 0
    signals_taken: int = 0
    exit_reasons: Dict[str, int] = field(default_factory=dict)
    by_trade_type: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class PaperTradingService:
    """
    Main paper trading orchestration service.

    Integrates:
    - Orchestrator for signal generation
    - PaperExecutor for order simulation
    - PositionManager for SL/TP management

    Usage:
        service = PaperTradingService()
        await service.start(config)

        # Check status
        status = service.get_status()

        # Stop
        await service.stop()
    """

    def __init__(self):
        """Initialize paper trading service."""
        self.config: Optional[PaperTradingConfig] = None
        self.status: PaperBotStatus = PaperBotStatus.IDLE
        self.session_id: Optional[str] = None

        # Core components (initialized on start)
        self.executor: Optional[PaperExecutor] = None
        self.position_manager: Optional[PositionManager] = None
        self.orchestrator: Optional[Orchestrator] = None
        self.mode: Optional[ScannerMode] = None
        self.active_mode: str = "stealth"  # Current adaptive mode (e.g. overwatch)
        self.active_profile: str = "stealth"  # Current logic fusion profile (e.g. surgical)

        # Tracking
        self.completed_trades: List[CompletedTrade] = []
        self._completed_trade_ids: set = set()  # O(1) dedup for _sync_closed_positions
        self.activity_log: List[Dict[str, Any]] = []
        self.stats: PaperTradingStats = PaperTradingStats()
        self._peak_equity: float = 0.0
        self._last_drawdown_check: datetime = datetime.now(timezone.utc)

        # Session timing
        self.started_at: Optional[datetime] = None
        self.stopped_at: Optional[datetime] = None
        self.last_scan_at: Optional[datetime] = None
        self.current_scan: Optional[Dict[str, Any]] = None

        # Background task
        self._scan_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False

        # Price cache for P&L calculations
        self._price_cache: Dict[str, float] = {}
        self._price_cache_refreshed_at: Optional[datetime] = None
        # Detailed signal processing log (every signal, not just recent activity)
        self.signal_log: List[Dict[str, Any]] = []

        # Regime state (updated each scan cycle for position sizing adjustments)
        self._current_regime_composite: str = "unknown"
        self._current_regime_score: float = 50.0
        self._current_regime_policy = None
        self._current_regime_trend: str = "sideways"
        self._current_regime_volatility: str = "normal"
        # Previous regime trend — used to detect BTC pump transitions mid-session.
        # None on startup: prevents a false transition trigger when BTC is already
        # in an up regime on the very first scan (no prior state to compare against).
        self._prev_regime_trend: Optional[str] = None

        # Session log directory for persistent diagnostic output
        self._session_log_dir: Optional[Path] = None

        # Track limit orders that are waiting to fill
        self._pending_plans: Dict[str, TradePlan] = {}
        self._pending_placed_at: Dict[str, datetime] = {}
        self._pending_placed_price: Dict[str, float] = {}  # price at time of placement
        self._pending_extended: Dict[str, int] = {}        # order_id → extension count
        self._expired_symbols: set = set()                 # symbols whose order just expired → priority re-scan

        # Diagnostics
        self.diagnostic_logger: Optional[DiagnosticLogger] = None

        # Telemetry persistence (initialized on start)
        self.telemetry_storage: Optional[TelemetryStorage] = None

        logger.info("PaperTradingService initialized")

    async def start(self, config: PaperTradingConfig) -> Dict[str, Any]:
        """
        Start paper trading session.

        Args:
            config: Paper trading configuration

        Returns:
            Session info including session_id
        """
        if self.status == PaperBotStatus.RUNNING:
            raise ValueError("Paper trading already running")

        self.config = config
        self.session_id = str(uuid.uuid4())[:8]

        # Preload any trades already written for this session (crash recovery).
        # In normal first-start scenarios the journal has no entries for this brand-new
        # session_id, so this is effectively a no-op with zero overhead.
        try:
            prior = get_trade_journal().query(session_id=self.session_id, limit=1000)
            if prior:
                logger.info("Reloaded %d trades from journal for session %s", len(prior), self.session_id)
                # (full reconstruction path would rebuild stats too — left for future work)
        except Exception as _je:
            logger.warning("Could not preload journal on start: %s", _je)

        # Paper trading always uses stealth mode — it's the optimal balance:
        # - Covers D→5m timeframes (full range)
        # - Allows all trade types (scalp, intraday, swing) adaptively
        # - Requires solid 1.5 R:R minimum
        # - Can trade both directions (long + short)
        # If the caller requested a different mode, log it so the user knows it was overridden.
        if config.sniper_mode != "stealth":
            logger.info(
                f"Paper trading overrides sniper_mode '{config.sniper_mode}' → 'stealth'. "
                "Stealth is the only supported mode for paper trading (adaptive scalp/intraday/swing)."
            )
        config.sniper_mode = "stealth"
        self.mode = get_mode("stealth")
        if not self.mode:
            raise ValueError("Failed to load stealth mode")

        # Initialize executor — testnet routes real orders through Phemex testnet,
        # simulation uses internal fill math (no API keys required)
        if config.use_testnet:
            from backend.bot.executor.live_executor import LiveExecutor
            from backend.shared.config.live_trading_config import load_phemex_credentials
            from backend.data.adapters.phemex import PhemexAdapter as _PhemexAdapter
            _api_key, _api_secret = load_phemex_credentials()
            if not _api_key:
                raise ValueError(
                    "Testnet mode requires PHEMEX_API_KEY and PHEMEX_API_SECRET in your .env file."
                )
            _testnet_adapter = _PhemexAdapter(testnet=True, api_key=_api_key, api_secret=_api_secret)
            self.executor = LiveExecutor(
                adapter=_testnet_adapter,
                fee_rate=config.fee_rate,
                max_position_size_usd=10000.0,  # generous cap for paper sessions
                max_total_exposure_usd=100000.0,
                min_balance_usd=0.0,
                dry_run=False,
            )
            logger.info("Paper trading using PHEMEX TESTNET executor")
            if getattr(config, "execution_mode", "snap_taker") == "rest_maker":
                logger.warning(
                    "execution_mode=rest_maker IGNORED → forced snap_taker because use_testnet=True "
                    "(LiveExecutor path; the maker experiment is PAPER-ONLY per §15 design entry)."
                )
        else:
            # Select fee rate based on execution mode:
            # rest_maker → maker rate (0.01%); snap_taker → taker rate (0.06%).
            _active_fee = config.maker_fee_rate if config.rest_maker_active else config.taker_fee_rate
            self.executor = PaperExecutor(
                initial_balance=config.initial_balance,
                fee_rate=_active_fee,
                slippage_bps=config.alt_slippage_bps,  # conservative base; per-symbol lookup inside executor
                major_slippage_bps=config.major_slippage_bps,
                enable_partial_fills=True,
                partial_fill_prob=0.3,
                min_fill_pct=0.3,
                max_fill_pct=0.7,
            )
            if getattr(config, "execution_mode", "snap_taker") == "rest_maker":
                logger.info(
                    "Paper executor in REST_MAKER mode — limits rest at the OB (no snap), filled only "
                    "on retrace (maker). Expect lower fill rate (experiment T14)."
                )

        # Initialize position manager
        self.position_manager = PositionManager(
            price_fetcher=self._get_price,
            order_executor=self._execute_exit_order,
            check_interval=1.0,
            breakeven_after_target=config.breakeven_after_target,
            trailing_stop_activation=config.trailing_activation,
            trailing_stop_distance=0.75,  # WAS 0.5 - increased to 0.75 to give trade more room to breathe
            max_hours_open=config.max_hours_open,
        )

        # Initialize orchestrator with exchange adapter
        try:
            adapter = PhemexAdapter()  # Default to Phemex

            # Get min_rr from mode overrides or use default
            min_rr = 1.0  # Default
            if self.mode.overrides and "min_rr_ratio" in self.mode.overrides:
                min_rr = self.mode.overrides["min_rr_ratio"]

            # Paper trading should be able to tune planner behavior without affecting
            # the main scanner. We attach a session-local PlannerConfig to this ScanConfig.
            from backend.shared.config.planner_config import PlannerConfig

            planner_cfg = PlannerConfig.defaults_for_mode("stealth")
            # Training Ground tuning:
            # - don't hard-reject on PD (use confluence + structure instead)
            # - widen stop buffers to reduce noise stop-outs
            planner_cfg.pd_compliance_required = False
            planner_cfg.stop_buffer_by_regime = {
                "calm": 0.35,
                "normal": 0.45,
                "elevated": 0.55,
                "explosive": 0.65,
            }

            # Create ScanConfig from paper trading config.
            # NOTE: use explicit None-check instead of ``or`` — a legitimate
            # override of ``min_confluence=0`` (used when forcing raw signals
            # through for diagnostics) is falsy and would otherwise silently
            # fall back to the mode default.
            _min_conf = (
                config.min_confluence
                if config.min_confluence is not None
                else self.mode.min_confluence_score
            )

            # Resolve soft floor from sensitivity preset using module-level dict.
            # "custom" uses the explicit confluence_soft_floor value;
            # named presets carry their own floor regardless of min_confluence.
            _preset = (config.sensitivity_preset or "balanced").lower()
            if _preset in _SENSITIVITY_PRESETS:
                # Named preset: override gate + floor with preset values unless
                # the user also sent an explicit min_confluence override (custom gate).
                _preset_gate  = _SENSITIVITY_PRESETS[_preset]["gate"]
                _preset_floor = _SENSITIVITY_PRESETS[_preset]["floor"]
                if config.min_confluence is None:
                    _min_conf = _preset_gate
                _soft_floor = _preset_floor
            else:
                # "custom" preset: use explicit floor if provided, else 10-point band
                _soft_floor = config.confluence_soft_floor if config.confluence_soft_floor is not None else max(0.0, _min_conf - 10.0)

            scan_config = ScanConfig(
                profile=self.mode.profile,
                timeframes=tuple(self.mode.timeframes),
                min_confluence_score=_min_conf,
                confluence_soft_floor=_soft_floor,
                sensitivity_preset=_preset,
                min_rr_ratio=min_rr,
                max_symbols=20,
            )
            scan_config.planner = planner_cfg
            scan_config.enable_fusion = True  # Bot uses Dynamic Logic Fusion — scanner stays on pure Stealth weights
            # Macro/dominance overlay toggle (operator-controllable; scorer.py:3114 reads config.macro_overlay_enabled).
            # Mirrors scanner_service.py:281. Default True = back-compat; False = pure technicals (ledger T19).
            scan_config.macro_overlay_enabled = config.macro_overlay_enabled
            logger.info(f"Macro overlay: {'ON' if config.macro_overlay_enabled else 'OFF'} (config.macro_overlay_enabled)")

            self.orchestrator = Orchestrator(config=scan_config, exchange_adapter=adapter)
        except Exception as e:
            logger.error(f"Failed to initialize orchestrator: {e}")
            raise ValueError(f"Failed to initialize scanner: {e}")

        # Reset tracking
        self.completed_trades = []
        self._completed_trade_ids = set()
        self.activity_log = []
        self.signal_log = []
        self.stats = PaperTradingStats()
        self._pending_plans = {}
        self._pending_placed_at = {}
        self._pending_placed_price = {}
        self._pending_extended = {}
        self._expired_symbols = set()
        self._price_cache = {}
        self._peak_equity = config.initial_balance
        self._prev_regime_trend = None
        self._current_regime_trend = None

        # Create session log directory for persistent output
        project_root = Path(__file__).parent.parent.parent
        self._session_log_dir = project_root / "logs" / "paper_trading" / f"session_{self.session_id}"
        self._session_log_dir.mkdir(parents=True, exist_ok=True)

        # Initialize telemetry DB persistence
        try:
            self.telemetry_storage = TelemetryStorage()  # default: backend/cache/telemetry.db
        except Exception as e:
            logger.error(f"Failed to initialize telemetry storage: {e}")
            self.telemetry_storage = None

        # Start session
        self.started_at = datetime.now(timezone.utc)
        self.stopped_at = None
        self.status = PaperBotStatus.RUNNING
        self.active_mode = "stealth"
        self.active_profile = "stealth"
        self._running = True

        # Initialize diagnostics
        try:
            diagnostic_path = Path("logs/paper_trading") / f"session_{self.session_id}"
            self.diagnostic_logger = DiagnosticLogger(output_dir=diagnostic_path)
            self.diagnostic_logger.set_context(mode=config.sniper_mode)
            logger.info(f"Diagnostic logging initialized at {diagnostic_path}")
        except Exception as e:
            logger.error(f"Failed to initialize diagnostic logger: {e}")

        # Log activity
        self._log_activity(
            "session_started", {"session_id": self.session_id, "config": config.to_dict()}
        )

        # Start background tasks. Both tasks run for the lifetime of the
        # session; attach a done-callback so exceptions surface immediately
        # instead of being swallowed by the event loop.
        self._scan_task = asyncio.create_task(
            self._scan_loop(), name=f"paper_scan_loop_{self.session_id}"
        )
        self._scan_task.add_done_callback(self._task_done_callback)
        self._monitor_task = asyncio.create_task(
            self._monitor_loop(), name=f"paper_monitor_loop_{self.session_id}"
        )
        self._monitor_task.add_done_callback(self._task_done_callback)

        logger.info(f"Paper trading started: session={self.session_id}, mode={config.sniper_mode}")

        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "config": config.to_dict(),
        }

    async def stop(self) -> Dict[str, Any]:
        """
        Stop paper trading session.

        Returns:
            Final session statistics
        """
        if self.status != PaperBotStatus.RUNNING:
            return {"status": self.status.value, "message": "Not running"}

        self._running = False
        self.status = PaperBotStatus.STOPPED
        self.stopped_at = datetime.now(timezone.utc)

        # Cancel background tasks
        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Close all open positions
        await self._close_all_positions("session_stopped")

        # Generate diagnostic report
        if self.diagnostic_logger:
            try:
                diag_stats = self.diagnostic_logger.get_stats()
                mode_name = self.config.sniper_mode if self.config else "unknown"
                
                mode_stats = {
                    mode_name: ModeStats(
                        mode=mode_name,
                        trades=self.stats.total_trades,
                        wins=self.stats.winning_trades,
                        losses=self.stats.losing_trades,
                        win_rate=self.stats.win_rate,
                        avg_rr=self.stats.avg_rr,
                        total_pnl_pct=self.stats.total_pnl_pct,
                        issues_found=diag_stats["counts"]["total"],
                        critical_issues=diag_stats["counts"]["critical"],
                        warnings=diag_stats["counts"]["warning"]
                    )
                }
                
                report_gen = ReportGenerator(
                    output_dir=self.diagnostic_logger.output_dir,
                    logger=self.diagnostic_logger
                )
                
                report_path = report_gen.generate(
                    mode_stats=mode_stats,
                    regime_stats={},
                    config=self.config.to_dict() if self.config else {},
                    start_time=self.started_at or self.stopped_at,
                    end_time=self.stopped_at
                )
                
                logger.info(f"Diagnostic report generated at: {report_path}")
                self._log_activity("diagnostic_report_generated", {"path": str(report_path)})
            except Exception as e:
                logger.error(f"Failed to generate diagnostic report: {e}")

        # Log activity
        self._log_activity(
            "session_stopped", {"session_id": self.session_id, "final_stats": self.stats.to_dict()}
        )

        # Final state checkpoint before session report (captures last balance/stats)
        self._save_state()

        # Generate comprehensive session report on disk
        report_path = self._generate_session_report()
        if report_path:
            logger.info(f"Session report: {report_path}")

        logger.info(f"Paper trading stopped: session={self.session_id}")

        status = self.get_status()
        if report_path:
            status["report_path"] = str(report_path)
        return status

    def reset(self) -> Dict[str, Any]:
        """
        Reset paper trading to fresh state.

        Returns:
            Reset confirmation
        """
        if self.status == PaperBotStatus.RUNNING:
            raise ValueError("Cannot reset while running. Stop first.")

        self.config = None
        self.session_id = None
        self.executor = None
        self.position_manager = None
        self.orchestrator = None
        self.mode = None

        self.completed_trades = []
        self._completed_trade_ids = set()
        self.activity_log = []
        self.signal_log = []
        self.stats = PaperTradingStats()
        self._price_cache = {}
        self._pending_plans = {}
        self._pending_placed_at = {}
        self._pending_placed_price = {}
        self._pending_extended = {}
        self._expired_symbols = set()

        self.started_at = None
        self.stopped_at = None
        self.status = PaperBotStatus.IDLE

        logger.info("Paper trading reset")

        return {"status": "reset", "message": "Paper trading reset to initial state"}

    def get_status(self) -> Dict[str, Any]:
        """
        Get current paper trading status.

        Returns:
            Comprehensive status including balance, positions, stats
        """
        # Calculate next scan time
        next_scan_in = None
        if self.status == PaperBotStatus.RUNNING and self.config and self.last_scan_at:
            interval_seconds = self.config.scan_interval_minutes * 60
            next_scan_at = self.last_scan_at + timedelta(seconds=interval_seconds)
            next_scan_in = max(0, (next_scan_at - datetime.now(timezone.utc)).total_seconds())

        # Basic status
        result = {
            "status": self.status.value,
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "uptime_seconds": self._get_uptime_seconds(),
            "config": self.config.to_dict() if self.config else None,
            "last_scan_at": self.last_scan_at.isoformat() if self.last_scan_at else None,
            "next_scan_in_seconds": next_scan_in,
            "current_scan": self.current_scan,
            "active_mode": self.active_mode,
            "active_profile": self.active_profile,
            # Heart-change flag surface (so the UI can reflect the actual decision core): in thesis
            # mode the confluence score is DEMOTED (the structure-led thesis decides direction; the
            # min_confluence "gate" no longer rejects). Lets the setup page relabel/grey that control.
            "decision_mode": "thesis" if is_thesis_mode() else "legacy",
            "fresh_entry_price": is_fresh_entry_price(),
            "regime": {
                "composite": self._current_regime_composite,
                "score": self._current_regime_score,
                "trend": self._current_regime_trend,
                "volatility": self._current_regime_volatility,
            },
        }

        # Active positions — must be computed first so unrealized_pnl on each
        # PositionState is refreshed from the price cache before equity is summed.
        # Previously equity was summed from pos.unrealized_pnl (set by the last
        # monitor tick) while the positions list was built from a newer cache read
        # — the two could reflect different price snapshots.
        active_positions = self._get_active_positions()
        result["positions"] = active_positions

        # Balance info
        if self.executor:
            initial = self.config.initial_balance if self.config else 0

            # Pure cash balance (executor handles fees and ALL realized PnL)
            current = self.executor.get_balance()

            # Sum unrealized PnL from PositionState — already refreshed by
            # _get_active_positions() above, so equity and positions are consistent.
            unrealized_pnl = 0.0
            if self.position_manager:
                unrealized_pnl = sum(
                    pos.unrealized_pnl
                    for pos in self.position_manager.positions.values()
                    if pos.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]
                )

            equity = current + unrealized_pnl

            prices_age_seconds = None
            if self._price_cache_refreshed_at:
                prices_age_seconds = round(
                    (datetime.now(timezone.utc) - self._price_cache_refreshed_at).total_seconds(), 1
                )

            result["balance"] = {
                "initial": initial,
                "current": current,
                "equity": equity,
                "pnl": equity - initial,
                "pnl_pct": ((equity - initial) / initial * 100) if initial > 0 else 0,
                "prices_age_seconds": prices_age_seconds,
            }
        else:
            # Return a fully-populated schema instead of ``None`` so the
            # frontend can always read ``status.balance.equity`` without
            # null-guarding every field. Values all default to zero when
            # the bot is not running / executor is not initialized.
            initial = self.config.initial_balance if self.config else 0
            result["balance"] = {
                "initial": initial,
                "current": initial,
                "equity": initial,
                "pnl": 0.0,
                "pnl_pct": 0.0,
                "prices_age_seconds": None,
            }

        # Statistics
        result["statistics"] = self.stats.to_dict()

        # Recent activity (last 50 for better visibility)
        result["recent_activity"] = self.activity_log[-50:]

        # Pending limit orders
        result["pending_orders"] = []
        if self.executor:
            for order_id, plan in self._pending_plans.items():
                order = self.executor.get_order(order_id)
                if order and order.status in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]:
                    result["pending_orders"].append({
                        "order_id": order_id,
                        "symbol": order.symbol,
                        "direction": plan.direction,
                        "limit_price": order.price,
                        "quantity": order.quantity,
                        "filled_qty": order.filled_quantity,
                        "status": order.status.value,
                        "confluence": plan.confidence_score,
                        "trade_type": getattr(plan, "trade_type", "intraday"),
                        "current_price": self._price_cache.get(order.symbol, 0.0),
                        "stop_loss": float(plan.stop_loss.level) if plan.stop_loss else 0.0,
                        # Emit None (not 0.0) on missing TP — see _get_active_positions
                        # for the full rationale (geometry guard / payload symmetry).
                        "tp1": float(plan.targets[0].level) if plan.targets else None,
                        "tp2": float(plan.targets[1].level) if len(plan.targets) > 1 else None,
                        "tp_final": float(plan.targets[-1].level) if plan.targets else None,
                    })

        # Signal processing log (every signal with full details)
        result["signal_log"] = self.signal_log[-100:]

        # OHLCV cache stats (for monitoring efficiency)
        try:
            from backend.data.ohlcv_cache import get_ohlcv_cache

            cache = get_ohlcv_cache()
            cache_stats = cache.get_stats()
            result["cache_stats"] = {
                "hit_rate_pct": cache_stats["hit_rate_pct"],
                "entries": cache_stats["entries"],
                "candles_cached": cache_stats["total_candles_cached"],
            }
        except Exception:
            result["cache_stats"] = None

        return result

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get active positions with real-time P&L."""
        return self._get_active_positions()

    def get_trade_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get completed trade history.

        Args:
            limit: Maximum number of trades to return

        Returns:
            List of completed trades (newest first)
        """
        trades = sorted(
            self.completed_trades, key=lambda t: t.exit_time or t.entry_time, reverse=True
        )[:limit]

        return [t.to_dict() for t in trades]

    def get_activity_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get activity log.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of activity events (newest first)
        """
        return list(reversed(self.activity_log[-limit:]))

    # -------------------- Private Methods --------------------

    async def _scan_loop(self):
        """Background loop for running scanner at intervals."""
        while self._running:
            # Re-read config each iteration so mid-session changes take effect
            config = self.config
            if not config:
                await asyncio.sleep(5)
                continue

            interval = (config.scan_interval_minutes or 2) * 60

            try:
                await self._run_scan()
            except Exception as e:
                logger.error(f"Scan error: {e}")
                self._log_activity("scan_error", {"error": str(e)})

            # Check duration limit
            if config.duration_hours > 0:
                elapsed = self._get_uptime_seconds()
                if elapsed >= config.duration_hours * 3600:
                    logger.info("Duration limit reached, stopping")
                    _stop_task = asyncio.create_task(
                        self.stop(), name="paper_stop_duration_limit"
                    )
                    _stop_task.add_done_callback(self._task_done_callback)
                    break

            # Max drawdown kill switch — use peak-to-trough (same metric as monitor loop)
            if config.max_drawdown_pct is not None:
                self._update_drawdown()  # ensure stats are fresh after each scan cycle
                if self.stats.max_drawdown >= config.max_drawdown_pct:
                    logger.warning(
                        f"Max drawdown kill switch triggered (scan loop): "
                        f"{self.stats.max_drawdown:.1f}% >= {config.max_drawdown_pct}% limit"
                    )
                    self._log_activity("session_stopped", {
                        "reason": "max_drawdown_kill_switch",
                        "drawdown_pct": round(self.stats.max_drawdown, 2),
                        "limit_pct": config.max_drawdown_pct,
                    })
                    _stop_task = asyncio.create_task(
                        self.stop(), name="paper_stop_max_drawdown_scan"
                    )
                    _stop_task.add_done_callback(self._task_done_callback)
                    break

            # Wait for next interval
            await asyncio.sleep(interval)

    async def _monitor_loop(self):
        """Background loop for monitoring positions."""
        while self._running:
            try:
                if self.position_manager:
                    # Refresh prices for all open positions before monitoring
                    await self._refresh_price_cache()

                    # Process open limit orders
                    executor = self.executor
                    if executor:
                        open_orders = executor.get_open_orders()
                        for order in open_orders:
                            if order.order_type == OrderType.LIMIT:
                                current_price = self._price_cache.get(order.symbol)
                                if current_price:
                                    fill = executor.execute_limit_order(order.order_id, current_price)
                                    if fill:
                                        # Check if this order is linked to an existing position
                                        position = self.position_manager.find_position_by_order_id(order.order_id)
                                        if position:
                                            # Add volume to existing position
                                            self.position_manager.add_position_volume(
                                                position.position_id, fill.price, fill.quantity
                                            )
                                            logger.info(
                                                f"PARTIAL FILL SYNCED: {position.symbol} +{fill.quantity:.6f} "
                                                f"| New Size: {position.quantity:.6f}"
                                            )
                                        # Handle filled orders that were waiting in _pending_plans
                                        elif order.order_id in self._pending_plans and order.status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
                                            plan = self._pending_plans.get(order.order_id)
                                            if plan:
                                                # Re-check position cap at fill time. Multiple pending orders
                                                # can fill in the same monitor tick, bypassing the cap that
                                                # was checked when the signal was originally processed.
                                                active_count_now = len(self._get_active_positions())
                                                cap = self.config.max_positions if self.config else 3
                                                if active_count_now >= cap:
                                                    try:
                                                        executor.cancel_order(order.order_id)
                                                    except Exception as _ce:
                                                        logger.warning("cancel_order %s failed: %s", order.order_id, _ce)
                                                    self._pending_plans.pop(order.order_id, None)
                                                    self._pending_placed_at.pop(order.order_id, None)
                                                    logger.info(
                                                        f"PENDING FILL BLOCKED (cap): {plan.symbol} "
                                                        f"| active={active_count_now}/{cap} — order cancelled"
                                                    )
                                                    self._log_activity("pending_fill_blocked", {
                                                        "order_id": order.order_id,
                                                        "symbol": plan.symbol,
                                                        "direction": plan.direction,
                                                        "reason": "max_positions_reached_at_fill",
                                                        "active_count": active_count_now,
                                                        "cap": cap,
                                                    })
                                                else:
                                                    position_id = self.position_manager.open_position(
                                                        trade_plan=plan,
                                                        entry_price=fill.price,
                                                        quantity=fill.quantity,
                                                        entry_order_id=order.order_id
                                                    )

                                                    self.stats.signals_taken += 1
                                                    logger.info(
                                                        f"PENDING ORDER FILLED: {plan.symbol} @ {fill.price:.2f} "
                                                        f"| Opening position {position_id}"
                                                    )

                                                    # Position opened — remove from pending tracking
                                                    self._pending_plans.pop(order.order_id, None)
                                                    self._pending_placed_at.pop(order.order_id, None)

                                                    # Mark the signal as executed now that the fill happened.
                                                    # The original _log_signal call used result="pending"; this
                                                    # second entry with result="executed" lets the diagnostic
                                                    # report and per-symbol stats correctly count the trade.
                                                    self._log_signal(
                                                        plan,
                                                        "executed",
                                                        f"Pending order filled @ {fill.price:.6g}",
                                                        fill_price=fill.price,
                                                        fill_qty=fill.quantity,
                                                        position_id=position_id,
                                                    )

                                                    self._log_activity("trade_opened", {
                                                        "position_id": position_id,
                                                        "symbol": plan.symbol,
                                                        "direction": plan.direction,
                                                        "entry_price": fill.price,
                                                        "quantity": fill.quantity,
                                                        "status": "pending_filled"
                                                    })
                                        elif not self._has_position(order.symbol) and order.status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
                                            # This case handles orders that filled but haven't opened a position yet
                                            # (though _process_signal should handle most of these)
                                            pass

                        # Expire stale pending orders that have outlived their per-type TTL.
                        if self._pending_plans and self.config:
                            now = datetime.now(timezone.utc)
                            for order_id in list(self._pending_plans.keys()):
                                placed_at = self._pending_placed_at.get(order_id)
                                if not placed_at:
                                    continue
                                plan = self._pending_plans[order_id]
                                trade_type = getattr(plan, "trade_type", "intraday") or "intraday"
                                ttl_minutes = _PENDING_TTL_MINUTES.get(
                                    trade_type,
                                    self.config.scan_interval_minutes * self.config.max_pending_scans,
                                )
                                max_age = timedelta(minutes=ttl_minutes)
                                if (now - placed_at) > max_age:
                                    # ── Adaptive TTL: extend if price is pulling back ─
                                    # Before cancelling, check whether price has already
                                    # started moving toward the limit.  Cancelling right
                                    # as a pullback begins wastes the setup.
                                    _placed_price = self._pending_placed_price.get(order_id)
                                    _cur_price = self._price_cache.get(plan.symbol, 0.0)
                                    _lim_price = self._get_limit_price_for_order(order_id, plan)
                                    _ext_count = self._pending_extended.get(order_id, 0)
                                    _can_extend = _ext_count < _MAX_TTL_EXTENSIONS

                                    _pullback_in_progress = False
                                    if _placed_price and _cur_price and _lim_price and _can_extend:
                                        if plan.direction == "LONG":
                                            # Price has dropped closer to the buy limit
                                            _gap_now = _cur_price - _lim_price
                                            _gap_orig = _placed_price - _lim_price
                                            _pullback_in_progress = _gap_now < _gap_orig * 0.6  # 40%+ closer
                                        else:
                                            # Price has risen closer to the sell limit
                                            _gap_now = _lim_price - _cur_price
                                            _gap_orig = _lim_price - _placed_price
                                            _pullback_in_progress = _gap_now < _gap_orig * 0.6

                                    if _pullback_in_progress:
                                        # Extend by 50% of original TTL (up to _MAX_TTL_EXTENSIONS times)
                                        _extension = timedelta(minutes=ttl_minutes * 0.5)
                                        self._pending_placed_at[order_id] = now - max_age + _extension
                                        self._pending_extended[order_id] = _ext_count + 1
                                        logger.info(
                                            "⏳ TTL EXTENDED [%d/%d]: %s [%s] | price %.4f moving toward limit %.4f "
                                            "(was %.4f at placement) | +%.0fmin extension",
                                            _ext_count + 1, _MAX_TTL_EXTENSIONS,
                                            plan.symbol, trade_type,
                                            _cur_price, _lim_price, _placed_price,
                                            ttl_minutes * 0.5,
                                        )
                                        self._log_activity("pending_order_ttl_extended", {
                                            "order_id": order_id,
                                            "symbol": plan.symbol,
                                            "direction": plan.direction,
                                            "current_price": _cur_price,
                                            "limit_price": _lim_price,
                                            "placed_price": _placed_price,
                                            "extension_minutes": ttl_minutes * 0.5,
                                            "extension_count": _ext_count + 1,
                                            "max_extensions": _MAX_TTL_EXTENSIONS,
                                        })
                                        continue  # Skip cancellation this cycle

                                    try:
                                        executor.cancel_order(order_id)
                                    except Exception as _ce:
                                        logger.warning("cancel_order %s failed (already gone?): %s", order_id, _ce)
                                    self._pending_plans.pop(order_id, None)
                                    self._pending_placed_at.pop(order_id, None)
                                    self._pending_placed_price.pop(order_id, None)
                                    self._pending_extended.pop(order_id, None)
                                    # Flag for priority re-scan so fresh price is used immediately
                                    self._expired_symbols.add(plan.symbol)

                                    # Ghost-position cleanup: if this order was PARTIALLY_FILLED
                                    # before expiry, the executor still holds the partial in its
                                    # positions dict. Zero it out so equity calculations don't
                                    # include an unmanaged phantom position.
                                    expired_order = executor.get_order(order_id)
                                    if (
                                        expired_order is not None
                                        and expired_order.filled_quantity > 0
                                    ):
                                        ghost_qty = executor.positions.get(plan.symbol, 0.0)
                                        if abs(ghost_qty) > 1e-9:
                                            # Prefer live price; fall back to the partial fill
                                            # price recorded on the order so cleanup never
                                            # silently skips when the price cache is cold.
                                            ghost_price = (
                                                self._price_cache.get(plan.symbol)
                                                or getattr(expired_order, "avg_fill_price", 0.0)
                                                or getattr(expired_order, "fill_price", 0.0)
                                                or 0.0
                                            )
                                            logger.warning(
                                                f"GHOST POSITION CLEANUP: {plan.symbol} "
                                                f"| partial fill {expired_order.filled_quantity:.6f} "
                                                f"from expired order {order_id} "
                                                f"| zeroing executor position {ghost_qty:.6f} "
                                                f"@ {ghost_price:.4f}"
                                            )
                                            # Settle the ghost at current market price
                                            # so balance reflects the real outcome.
                                            if ghost_price > 0:
                                                close_side = "SELL" if ghost_qty > 0 else "BUY"
                                                close_order = executor.place_order(
                                                    symbol=plan.symbol,
                                                    side=close_side,
                                                    order_type="MARKET",
                                                    quantity=abs(ghost_qty),
                                                    price=ghost_price,
                                                )
                                                executor.execute_market_order(
                                                    close_order.order_id, ghost_price
                                                )
                                            else:
                                                # No price available — force zero directly
                                                executor.positions[plan.symbol] = 0.0
                                                executor.position_avg_price[plan.symbol] = 0.0

                                    _expired_limit_price = self._get_limit_price_for_order(order_id, plan)
                                    logger.info(
                                        f"PENDING ORDER EXPIRED: {plan.symbol} [{trade_type}] | "
                                        f"limit={_expired_limit_price:.4f} | "
                                        f"age={(now - placed_at).total_seconds() / 60:.1f}min "
                                        f"(ttl={ttl_minutes:.0f}min)"
                                    )
                                    self._log_activity("pending_order_expired", {
                                        "order_id": order_id,
                                        "symbol": plan.symbol,
                                        "direction": plan.direction,
                                        "trade_type": trade_type,
                                        "confluence": plan.confidence_score,
                                        "limit_price": _expired_limit_price,
                                        "age_minutes": (now - placed_at).total_seconds() / 60,
                                        "ttl_minutes": ttl_minutes,
                                    })

                    await self.position_manager.monitor_all_positions()

                    # Check for closed positions
                    await self._sync_closed_positions()

                    # Update drawdown in real-time (every 10s) to capture open-position
                    # underwater equity, not only at trade-close time.
                    _now = datetime.now(timezone.utc)
                    if (_now - self._last_drawdown_check).total_seconds() >= 10:
                        self._update_drawdown()
                        self._last_drawdown_check = _now

                        # Check for drawdown limit
                        if (self.config
                                and self.config.max_drawdown_pct is not None
                                and self.stats.max_drawdown >= self.config.max_drawdown_pct):
                            logger.warning(
                                f"🛑 MAX DRAWDOWN LIMIT REACHED ({self.stats.max_drawdown:.2f}% >= {self.config.max_drawdown_pct}%)"
                            )
                            self._log_activity("drawdown_limit_reached", {
                                "drawdown": self.stats.max_drawdown,
                                "limit": self.config.max_drawdown_pct
                            })
                            _stop_task = asyncio.create_task(
                                self.stop(), name="paper_stop_max_drawdown_monitor"
                            )
                            _stop_task.add_done_callback(self._task_done_callback)
                            break

            except Exception as e:
                logger.error(f"Monitor error: {e}")

            await asyncio.sleep(1)  # Check every second

    async def _refresh_price_cache(self):
        """Fetch current prices for all open positions and pending orders, update the cache."""
        if not self.position_manager:
            return

        open_positions = self.position_manager.get_open_positions()
        pending_symbols = {plan.symbol for plan in self._pending_plans.values()}
        symbols = {pos.symbol for pos in open_positions} | pending_symbols

        for symbol in symbols:
            try:
                price = await self._fetch_price(symbol)
                if price > 0:
                    self._price_cache[symbol] = price
            except Exception as e:
                logger.debug(f"Price refresh failed for {symbol}: {e}")

        if symbols:
            self._price_cache_refreshed_at = datetime.now(timezone.utc)

    async def _run_scan(self):
        """Run a single scanner iteration."""
        if not self.orchestrator or not self.config or not self.mode:
            return

        conf = self.config
        assert conf is not None  # For type checker
        
        self.last_scan_at = datetime.now(timezone.utc)
        
        # Check for dynamic mode adaptation if base mode is "stealth"
        actual_scan_mode = getattr(conf, "sniper_mode", "stealth")
        if actual_scan_mode == "stealth":
            try:
                from backend.analysis.regime_detector import get_regime_detector  # type: ignore
                from backend.strategy.planner.regime_engine import get_mode_recommendation  # type: ignore
                
                detector = get_regime_detector("stealth_balanced")
                global_regime = detector.get_confirmed_regime()
                
                if global_regime and global_regime.composite != "unknown":
                    rec = get_mode_recommendation(
                        global_regime.trend, 
                        global_regime.volatility, 
                        global_regime.risk_appetite
                    )
                    recommended_mode = rec.get("mode", "stealth")
                    if recommended_mode != "stealth":
                        logger.info(
                            f"🧠 ADAPTIVE MODE: Regime is {global_regime.composite}. "
                            f"Adapting scan mode from stealth → {recommended_mode} ({rec.get('reason')})"
                        )
                        # NOTE: For paper trading, execution stays locked to STEALTH to avoid
                        # accidentally switching into stricter modes (e.g., Overwatch 78% gate)
                        # which can starve trade frequency.  actual_scan_mode is only used for
                        # display/logging — the orchestrator always scans with self.mode (stealth).
                        actual_scan_mode = recommended_mode
                        self.active_mode = actual_scan_mode
                        
                        # Set active profile for fusion visibility
                        # If recommended is Strike/Surgical, use that; otherwise stealth
                        if recommended_mode in ["strike", "surgical"]:
                           self.active_profile = recommended_mode
                        else:
                           self.active_profile = "stealth"

                        # Log the recommendation to the UI Activity Feed.
                        # Explicitly note the scan remains in stealth to avoid misleading users.
                        self._log_activity("system_update", {
                            "message": (
                                f"Regime Advisory: {recommended_mode.upper()} conditions detected "
                                f"(scan stays in STEALTH)."
                            ),
                            "details": rec.get("reason", "")
                        })
            except Exception as e:
                logger.error(f"Failed to calculate adaptive regime mode: {e}")

        self._log_activity("scan_started", {"mode": actual_scan_mode})
        self.stats.scans_completed += 1


        try:
            # Build symbol list — single code path (fixes dual-path bug)
            # Priority: user-specified symbols > category selection > defaults
            if self.config.symbols:
                # User specified exact pairs to trade (pair-of-choice feature)
                scan_symbols = list(self.config.symbols)
                logger.info(f"Using user-specified pairs: {scan_symbols}")
            else:
                # Auto-select from exchange using category toggles
                try:
                    from backend.analysis.pair_selection import select_symbols
                    limit = self.config.universe_size  # Configurable scan universe (default 20)
                    scan_symbols = select_symbols(
                        adapter=self.orchestrator.exchange_adapter,
                        limit=limit,
                        majors=getattr(self.config, "majors", True),
                        altcoins=getattr(self.config, "altcoins", False),
                        meme_mode=getattr(self.config, "meme_mode", False),
                        leverage=self.config.leverage,
                        market_type=self.orchestrator.config.market_type if hasattr(self.orchestrator.config, "market_type") else "perp"
                    )
                except Exception as e:
                    logger.warning(f"Pair selection failed ({e}), using default majors")
                    scan_symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]

            # Apply stale-symbol drop regardless of how scan_symbols was built.
            # The user-pinned path (config.symbols) bypasses select_symbols(), so
            # the Stage-0 stale filter inside _select_symbols_impl never sees those
            # symbols — without this call, symbols past _NO_DATA_DROP_THRESHOLD keep
            # getting scanned and wasting orchestrator budget. See decisions log
            # 2026-05-25__stale_symbol_drop_userpinned.md.
            try:
                from backend.analysis.pair_selection import filter_stale_symbols
                scan_symbols, _stale_dropped = filter_stale_symbols(
                    scan_symbols, context="paper_trading_service"
                )
            except Exception as _stale_exc:
                # Loud-by-default per CLAUDE.md §11 / §15: a silent debug-level
                # emit on this path would hide regressions in is_symbol_stale or
                # the mass-conservation assert. Scan continues with the unfiltered
                # list — graceful degradation, NOT silent failure.
                logger.warning(f"filter_stale_symbols failed: {_stale_exc}")

            # Apply the LIQUIDITY floor regardless of how scan_symbols was built — covers
            # user-pinned AND auto-selected (operator decision 2026-06-18: pinned symbols ARE
            # liquidity-filtered; an illiquid pinned pair blows through stops on exit).
            # regime-strategy-router §9-A "don't trade illiquid pairs". Loud per CLAUDE.md §11.
            try:
                from backend.analysis.pair_selection import (
                    filter_illiquid_symbols, derive_account_aware_floor, filter_by_book_quality,
                    filter_by_min_order_risk, filter_by_liquidation_safety,
                )
                # Liquidity floor: "fixed" (default) is BYTE-IDENTICAL to the prior behavior; only
                # "account_aware" (Gate 1) derives the floor from the account's balance×leverage
                # footprint. decisions/2026-06-28__account-aware-liquidity-admission.md (§15/§9-A).
                if getattr(self.config, "liquidity_mode", "fixed") == "account_aware":
                    _liq_floor = derive_account_aware_floor(
                        balance=getattr(self.config, "initial_balance", 0.0) or 0.0,
                        leverage=getattr(self.config, "leverage", 1) or 1,
                        participation_rate=getattr(self.config, "participation_rate", 0.005),
                        hard_min=getattr(self.config, "hard_min_volume_usdt", 500_000.0),
                    )
                    logger.info(
                        "LIQUIDITY mode=account_aware: floor=${:,.0f} (balance ${:,.0f} x lev {} / {:.2%})",
                        _liq_floor, getattr(self.config, "initial_balance", 0.0),
                        getattr(self.config, "leverage", 1), getattr(self.config, "participation_rate", 0.005),
                    )
                else:
                    _liq_floor = getattr(self.mode, "min_24h_volume_usdt", 5_000_000.0)
                _vols = self.orchestrator.exchange_adapter.get_symbol_volumes(scan_symbols)
                if _vols:
                    scan_symbols, _illiquid_dropped = filter_illiquid_symbols(
                        scan_symbols, _vols, _liq_floor, context="paper_trading_service"
                    )
                elif scan_symbols:
                    logger.warning(
                        "LIQUIDITY gate SKIPPED this scan: volume lookup returned no data; "
                        "trading {} symbol(s) unfiltered (existing gates still apply)",
                        len(scan_symbols),
                    )
                # Account-aware order-book gates (depth + liquidation) share ONE book fetch for the
                # bounded survivor set — fetched once if either gate is active.
                _aware = getattr(self.config, "liquidity_mode", "fixed") == "account_aware"
                _pos_notional = ((getattr(self.config, "initial_balance", 0.0) or 0.0)
                                 * (getattr(self.config, "leverage", 1) or 1))
                _want_depth = _aware and getattr(self.config, "depth_aware_admission", True)
                _want_liq = _aware and getattr(self.config, "liquidation_safety_guard", True)
                _book: Dict[str, Dict[str, float]] = {}
                if (_want_depth or _want_liq) and scan_symbols:
                    _book = self.orchestrator.exchange_adapter.get_book_quality(
                        scan_symbols, band_bps=getattr(self.config, "depth_band_bps", 10.0)
                    )
                # Depth-aware admission: volume is a cheap first screen, but volume != depth (NEAR
                # $5M/24h, ~$2 at the touch). Drop wide-spread / thin-depth books vs position notional.
                if _want_depth and scan_symbols:
                    if _book:
                        scan_symbols, _book_dropped = filter_by_book_quality(
                            scan_symbols, _book, _pos_notional,
                            max_spread_bps=getattr(self.config, "max_spread_bps", 15.0),
                            min_depth_mult=getattr(self.config, "min_depth_mult", 3.0),
                            context="paper_trading_service",
                        )
                    elif scan_symbols:
                        logger.warning(
                            "DEPTH gate SKIPPED this scan: order-book lookup returned no data; "
                            "trading {} symbol(s) on the volume floor alone", len(scan_symbols),
                        )
                # Gate 2 — min-order risk guard (account_aware only): drop a pair whose smallest allowed
                # order × stop% would exceed the per-trade risk budget (forced over-risk). Leverage-
                # independent. Near-inert on Phemex (mins $1-60); protects tiny accounts / other venues.
                if (_aware and getattr(self.config, "min_order_risk_guard", True)
                        and scan_symbols):
                    _risk_budget = ((getattr(self.config, "initial_balance", 0.0) or 0.0)
                                    * (getattr(self.config, "risk_per_trade", 1.0) or 0.0) / 100.0)
                    _specs = self.orchestrator.exchange_adapter.get_min_order_specs(scan_symbols)
                    if _specs:
                        _pre = list(scan_symbols)
                        _kept, _minord_dropped = filter_by_min_order_risk(
                            scan_symbols, _specs, _risk_budget,
                            getattr(self.config, "min_order_stop_pct_assumption", 0.01),
                            context="paper_trading_service",
                        )
                        # Guard: a min-order gate that drops EVERY survivor is almost certainly a
                        # spec-data glitch (Phemex always carries minOrderValueRv), not a real verdict —
                        # skip it loudly rather than trading nothing (volume+depth already vetted these).
                        if _kept or not _pre:
                            scan_symbols = _kept
                        else:
                            logger.warning(
                                "MIN_ORDER gate SKIPPED: would have dropped ALL {} survivor(s) "
                                "(likely missing min-order specs, not a real verdict)", len(_pre),
                            )
                # Gate 3 — liquidation-safety guard (leverage-driven; INERT at leverage<=1). Drop a pair
                # where no viable stop could sit safely inside the liquidation price at the configured
                # leverage (thin books need a bigger cushion — wick-liquidation). Reuses the _book fetch;
                # complements the plan-time _adjust_stop_for_leverage backstop.
                if _want_liq and scan_symbols:
                    _lev = getattr(self.config, "leverage", 1) or 1
                    # At lev<=1 the gate is inert (keep-all, no book needed). At lev>1 we NEED real book
                    # data — if the fetch failed (_book empty), SKIP loudly (parity with the depth gate)
                    # rather than treating every symbol as thin and over-dropping on a transient glitch;
                    # the plan-time _adjust_stop_for_leverage cushion still backstops admitted trades.
                    if _lev <= 1 or _book:
                        scan_symbols, _liq_dropped = filter_by_liquidation_safety(
                            scan_symbols, _lev, _book, _pos_notional,
                            min_stop_pct=getattr(self.config, "liquidation_min_stop_pct", 0.015),
                            context="paper_trading_service",
                        )
                    else:
                        logger.warning(
                            "LIQUIDATION gate SKIPPED this scan: leverage {}x but order-book lookup "
                            "returned no data; relying on the plan-time liquidation cushion", _lev,
                        )
            except Exception as _liq_exc:
                # Graceful degradation, NOT silent (CLAUDE.md §11/§15): a ticker/order-book fetch or
                # mass-conservation regression stays visible; scan continues on existing gates. Covers
                # BOTH the volume floor and the depth gate (don't mis-attribute a depth fault).
                logger.warning(f"liquidity/depth admission gate failed: {_liq_exc}")

            # Filter out excluded symbols
            if self.config.exclude_symbols:
                scan_symbols = [s for s in scan_symbols if s not in self.config.exclude_symbols]

            # Prioritise symbols whose pending order just expired — they need fresh
            # analysis with current price immediately rather than being shuffled to
            # wherever they land in the normal scan order.
            if self._expired_symbols:
                _priority = [s for s in self._expired_symbols if s in scan_symbols]
                _rest = [s for s in scan_symbols if s not in self._expired_symbols]
                scan_symbols = _priority + _rest
                if _priority:
                    logger.info(
                        "🔄 PRIORITY RE-SCAN: %s (pending expired, refreshing entry zones)",
                        ", ".join(_priority),
                    )
                self._expired_symbols.clear()

            logger.info(f"Starting scan: {len(scan_symbols)} symbols, mode={self.config.sniper_mode}")

            self.current_scan = {
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "actual_mode": actual_scan_mode,
                "completed": 0,
                "total": len(scan_symbols),
                "current_symbol": None,
                "progress_pct": 0,
                "passed": 0,
                "rejected": 0,
                "recent_symbols": []
            }

            def _progress_callback(completed: int, total: int, sym: str, passed: bool, rejection_info: Optional[Dict[str, Any]]):
                if self.current_scan is None:
                    return
                from typing import cast
                cs = cast(Dict[str, Any], self.current_scan)
                cs["completed"] = completed
                cs["total"] = total
                cs["current_symbol"] = sym
                cs["progress_pct"] = int((completed / total) * 100) if total > 0 else 0
                if passed:
                    cs["passed"] += 1
                else:
                    cs["rejected"] += 1

                # Keep last 5 symbols for the UI ticker
                status_obj = {
                    "symbol": sym,
                    "passed": passed,
                    "reason": rejection_info.get("reason", "Unknown") if rejection_info else None
                }
                
                # Log to diagnostics
                if self.diagnostic_logger:
                    category = ProbeCategory.CONF_BREAKDOWN_MISMATCH
                    if rejection_info:
                        rtype = rejection_info.get("reason_type")
                        if rtype == "low_confluence":
                            category = ProbeCategory.CONF_BREAKDOWN_MISMATCH
                        elif rtype == "risk_validation":
                            category = ProbeCategory.RISK_REJECTION_UNCLEAR
                        elif rtype == "no_data":
                            category = ProbeCategory.DATA_MISSING
                        elif rtype == "missing_critical_tf":
                            category = ProbeCategory.MTF_MISSING_CRITICAL
                    
                    if passed:
                        # Only log passed if you want verbose logs, info level
                        pass
                    else:
                        reason = rejection_info.get("reason", "Unknown") if rejection_info else "Unknown"
                        if self.diagnostic_logger:
                            from backend.diagnostics.logger import Severity
                            self.diagnostic_logger.log(
                                probe_id="SCAN_002", 
                                category=category, 
                                severity=Severity.WARNING,
                                message=f"Rejected: {sym} | {reason}", 
                                context=rejection_info,
                                symbol=sym
                            )

                recent = cs.setdefault("recent_symbols", [])  # pyre-ignore
                recent.insert(0, status_obj)
                cs["recent_symbols"] = recent[:5]  # pyre-ignore

            # Run scanner
            orch = self.orchestrator
            assert orch is not None
            orch.apply_mode(self.mode)
            
            # Apply sensitivity preset or explicit min_confluence override
            _rt_preset = (getattr(conf, "sensitivity_preset", None) or "").lower()
            _rt_min_conf = getattr(conf, "min_confluence", None)
            if _rt_min_conf is not None:
                # Explicit numeric override wins
                orch.config.min_confluence_score = _rt_min_conf
                _rt_floor = getattr(conf, "confluence_soft_floor", None)
                if _rt_floor is not None:
                    orch.config.confluence_soft_floor = _rt_floor
                else:
                    orch.config.confluence_soft_floor = max(0.0, _rt_min_conf - 10.0)
            elif _rt_preset in _SENSITIVITY_PRESETS:
                orch.config.min_confluence_score = _SENSITIVITY_PRESETS[_rt_preset]["gate"]
                orch.config.confluence_soft_floor = _SENSITIVITY_PRESETS[_rt_preset]["floor"]
            if _rt_preset:
                orch.config.sensitivity_preset = _rt_preset
                
            loop = asyncio.get_running_loop()
            trade_plans, rejection_summary = await loop.run_in_executor(
                None,
                lambda: self.orchestrator.scan_with_heartbeat(
                    symbols=scan_symbols,
                    progress_callback=_progress_callback,
                ),
            )

            # Graduated regime filtering using RegimePolicy system
            # Instead of a nuclear veto that kills ALL signals, apply per-mode
            # policies that adjust position sizing and filter only truly chaotic regimes.
            # Use `or {}` rather than a default arg: the orchestrator explicitly packs
            # "regime": None when BTC data fails, so .get("regime", {}) would still
            # return None (key exists). `or {}` handles the None case correctly.
            regime = (rejection_summary.get("regime") if isinstance(rejection_summary, dict) else None) or {}
            regime_composite = regime.get("composite", "unknown")
            regime_score = regime.get("score", 0)

            try:
                score_val = float(regime_score)
            except (ValueError, TypeError):
                score_val = 0.0

            # Get the regime policy for current mode (defines min_score, adjustments)
            regime_policy = get_regime_policy(self.config.sniper_mode)

            # Only veto in truly extreme conditions (chaotic + very low score)
            is_extreme = regime_composite in ["chaotic_volatile"] and score_val < 20

            if is_extreme and len(trade_plans) > 0:
                logger.info(
                    f"REGIME VETO (extreme only): Market is {regime_composite} "
                    f"(Score: {regime_score}). Vetoing {len(trade_plans)} signals."
                )
                veto_reason = f"Extreme Regime Veto: {regime_composite} ({regime_score}/100)"
                for plan in trade_plans:
                    self._log_signal(plan, "filtered", veto_reason, reason_type="regime_veto")
                trade_plans = []
            elif score_val < regime_policy.min_regime_score and len(trade_plans) > 0:
                # Below mode's minimum: log warning but DON'T veto — let position
                # sizing adjustments handle the risk reduction instead
                logger.info(
                    f"REGIME WARNING: Score {score_val:.0f} below mode min "
                    f"{regime_policy.min_regime_score:.0f} for {self.config.sniper_mode}. "
                    f"Position sizes will be reduced. Keeping {len(trade_plans)} signals."
                )

            # Store regime context for position sizing adjustments in _process_signal
            self._current_regime_composite = regime_composite
            self._current_regime_score = score_val
            self._current_regime_policy = regime_policy
            self._current_regime_trend = regime.get("trend", "sideways") if regime else "sideways"
            self._current_regime_volatility = regime.get("volatility", "normal") if regime else "normal"

            # Detect BTC regime flip to strong upside — protect existing alt shorts
            _btc_strong_up = self._current_regime_trend in ("strong_up", "up")
            _was_strong_up = self._prev_regime_trend in ("strong_up", "up")
            if _btc_strong_up and not _was_strong_up and self._prev_regime_trend is not None and self.position_manager:
                _protect_actions = self.position_manager.protect_alt_shorts_on_btc_pump(
                    self._price_cache
                )
                if _protect_actions:
                    self._log_activity("btc_pump_protective_tighten", {
                        "new_trend": self._current_regime_trend,
                        "prev_trend": self._prev_regime_trend,
                        "positions_protected": len(_protect_actions),
                        "actions": [
                            {"symbol": sym, "position_id": pid, "action": act}
                            for sym, pid, act in _protect_actions
                        ],
                    })
                    logger.warning(
                        "BTC_PUMP_PROTECT: Regime flipped %s→%s. Tightened stops on %d alt SHORT(s): %s",
                        self._prev_regime_trend, self._current_regime_trend,
                        len(_protect_actions),
                        [a[0] for a in _protect_actions],
                    )
            self._prev_regime_trend = self._current_regime_trend

            # Update open positions with latest regime data so adaptive
            # stagnation adjusts to current market conditions, not just entry-time
            self._update_position_regimes()
            
            self.stats.signals_generated += len(trade_plans)
            
            if self.current_scan:
                self.current_scan["status"] = "completed"
                # Store rejection funnel for UI monitoring
                if isinstance(rejection_summary, dict):
                    _by_reason = rejection_summary.get("by_reason", {})
                    self.current_scan["rejection_funnel"] = {
                        k: v for k, v in _by_reason.items() if isinstance(v, (int, float))
                    }
                    self.current_scan["total_scanned"] = len(scan_symbols)
                    self.current_scan["total_passed"] = len(trade_plans)

            # Log rejections
            rejections_details = rejection_summary.get("details", {}) if isinstance(rejection_summary, dict) else {}
            for reason_type, items in rejections_details.items():
                for item in items:
                    # Convert rejection_info to a format _log_signal understands
                    # Create unique nested objects per item to avoid shared-state corruption
                    from types import SimpleNamespace
                    
                    entry_zone = SimpleNamespace(
                        near_entry=item.get('entry_price', 0.0) or item.get('current_price', 0.0),
                        far_entry=0.0
                    )
                    
                    stop_loss = SimpleNamespace(
                        level=item.get('stop_loss', 0.0)
                    )
                    
                    mock_plan = SimpleNamespace(
                        symbol=item.get('symbol', 'Unknown'),
                        direction=item.get('direction', 'LONG'),
                        confidence_score=item.get('score', 0.0),
                        setup_type='filtered',
                        entry_zone=entry_zone,
                        stop_loss=stop_loss,
                        risk_reward=0.0
                    )
                    
                    # Sub-gate scored signals (low_confluence) carry the scorer's
                    # full per-factor breakdown as `all_factors`; thread it so the
                    # 40–69 band lands in signals.jsonl WITH factors. gate_cleared
                    # is False for every rejection-funnel row (no plan was built).
                    _all_factors = item.get('all_factors')
                    if reason_type == 'low_confluence' and not _all_factors:
                        # §THE LOOP loud-failure: a SCORED signal reached the funnel
                        # without its breakdown — surface it, never silently drop.
                        logger.warning(
                            "SIGNAL_LOG: low_confluence reject %s (%.1f) missing "
                            "all_factors — breakdown absent from rejection funnel",
                            item.get('symbol'), item.get('score', 0.0) or 0.0,
                        )
                    self._log_signal(
                        mock_plan,
                        result="filtered",
                        reason=item.get('reason', f"Scanner Filter: {reason_type}"),
                        gate_cleared=False,  # rejection-funnel row → never cleared the gate
                        sub_gate_factors=_all_factors,  # scorer breakdown for the 40–69 band
                        gate_name=reason_type,  # machine-readable gate label for shutdown report analysis
                        # Gate category — surfaces as badge in Signal Intelligence panel
                        reason_type=reason_type,
                        # Score vs threshold — lets the UI draw a gap bar
                        threshold=item.get('threshold'),
                        # Conflict density details — list of specific conflicting
                        # structural breaks + OBs, empty for non-conflict gates
                        conflict_conditions=item.get('conflict_conditions', []),
                        conflict_count=item.get('conflict_count'),
                        # Critical factor convergence — surface DEVELOPING/WATCHING in UI
                        setup_state=item.get('setup_state', 'NOISE'),
                        convergence_score=item.get('convergence_score', 0),
                        convergence_critical_count=item.get('convergence_critical_count', 0),
                        convergence_critical_total=item.get('convergence_critical_total'),
                        convergence_missing=item.get('convergence_missing'),
                        veto_blocked=item.get('veto_blocked', False),
                        active_vetoes=item.get('active_vetoes', []),
                        # Crash traceback hint — non-empty only for 'errors' reason_type
                        traceback_hint=item.get('traceback_hint', ''),
                    )

            _rej_by_reason = {r: len(items) for r, items in rejections_details.items() if items}
            _rej_total = sum(_rej_by_reason.values())
            self._log_activity(
                "scan_completed",
                {
                    "signals_found": len(trade_plans),
                    "symbols_scanned": len(scan_symbols),
                    "rejections": _rej_total,
                    "rejections_by_reason": _rej_by_reason,
                },
            )

            # Process valid signal plans.
            # Per-scan directional cap: sort by confluence (best first), then allow at most
            # MAX_SAME_DIR_PER_SCAN new entries per direction. Excess signals are deferred to
            # the next scan rather than entered immediately as a correlated batch — prevents
            # 5 correlated shorts from opening in 90 seconds on a single BTC move.
            _MAX_SAME_DIR_PER_SCAN = 3
            # Heart-change leftover-gate demotion #8 — KEEP the per-direction correlation cap, but in
            # thesis mode rank which signals survive it by RR (geometry), not the demoted confluence
            # score. Legacy mode still ranks by confidence_score.
            if is_thesis_mode():
                _sorted_plans = sorted(
                    trade_plans, key=lambda p: getattr(p, "risk_reward_ratio", 0.0) or 0.0, reverse=True
                )
            else:
                _sorted_plans = sorted(trade_plans, key=lambda p: p.confidence_score, reverse=True)
            _dir_counts: dict = {}
            _capped_plans = []
            for _p in _sorted_plans:
                _d = _p.direction
                if _dir_counts.get(_d, 0) < _MAX_SAME_DIR_PER_SCAN:
                    _capped_plans.append(_p)
                    _dir_counts[_d] = _dir_counts.get(_d, 0) + 1
                else:
                    _defer_reason = (
                        f"Directional cap: max {_MAX_SAME_DIR_PER_SCAN} {_d} entries per scan — "
                        f"deferred to next scan (confluence {_p.confidence_score:.1f}%)"
                    )
                    logger.info(f"SIGNAL DEFERRED: {_p.symbol} {_p.direction} | {_defer_reason}")
                    self._log_signal(_p, "filtered", _defer_reason, reason_type="directional_cap")

            for plan in _capped_plans:
                await self._process_signal(plan)

        except Exception as e:
            import traceback

            error_details = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Scanner error: {error_details}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self._log_activity("scan_error", {"error": error_details})

    def _log_signal(self, plan: TradePlan, result: str, reason: str, **extra):
        """Record every signal's processing result for the Signal Intelligence panel."""
        _meta = getattr(plan, "metadata", None) or {}
        _pb = _meta.get("pullback_probability") if isinstance(_meta, dict) else None
        if _pb is None:
            _pb = getattr(plan.entry_zone, "pullback_probability", 0) if plan.entry_zone else 0
        _now = datetime.now(timezone.utc)
        try:
            _kz_raw = get_current_kill_zone(_now)
            _kz = (_kz_raw.value if hasattr(_kz_raw, "value") else str(_kz_raw)) if _kz_raw else "no_session"
        except Exception:
            _kz = "no_session"
        entry = {
            "timestamp": _now.isoformat(),
            "scan_number": self.stats.scans_completed,
            "symbol": plan.symbol,
            "direction": plan.direction,
            "confluence": round(plan.confidence_score, 1),
            "setup_type": getattr(plan, "setup_type", "unknown"),
            "trade_type": getattr(plan, "trade_type", "unknown"),
            "timeframe": getattr(plan, "primary_timeframe", None) or getattr(plan, "signal_timeframe", None),
            "entry_zone": round(plan.entry_zone.near_entry, 6),
            "stop_loss": round(plan.stop_loss.level, 6),
            "rr": round(plan.risk_reward, 2) if hasattr(plan, "risk_reward") else None,
            "result": result,  # "executed", "filtered", "error"
            "reason": reason,
            "conviction_class": getattr(plan, "conviction_class", "B"),
            "plan_type": getattr(plan, "plan_type", "SMC"),
            "regime": self._current_regime_composite if hasattr(self, "_current_regime_composite") else "unknown",
            "pullback_probability": float(_pb or 0),
            "kill_zone": _kz,
            "execution_mode": getattr(self.config, "execution_mode", "snap_taker"),
        }
        # Confluence breakdown features (Tier 1 ML enrichment)
        _cb = getattr(plan, "confluence_breakdown", None)
        if _cb is not None:
            entry["synergy_bonus"] = round(float(getattr(_cb, "synergy_bonus", 0) or 0), 2)
            entry["conflict_penalty"] = round(float(getattr(_cb, "conflict_penalty", 0) or 0), 2)
            entry["htf_aligned"] = int(bool(getattr(_cb, "htf_aligned", False)))
            entry["htf_proximity_atr"] = round(float(getattr(_cb, "htf_proximity_atr", 0) or 0), 3)
            entry["macro_score"] = round(float(getattr(_cb, "macro_score", 0) or 0), 1)
            # Per-factor breakdown — enables full decision reconstruction in analysis scripts
            _factors = getattr(_cb, "factors", None)
            if _factors:
                entry["factors"] = [
                    {
                        "name": f.name,
                        "score": round(float(f.score), 1),
                        "weight": round(float(f.weight), 4),
                        "weighted": round(float(f.weighted_score), 2),
                        "rationale": f.rationale,
                    }
                    for f in _factors
                ]
        # Gate-cleared flag + sub-gate factor fallback (OBSERVABILITY ONLY — does
        # NOT touch scoring/gating). A real TradePlan exists only AFTER the
        # confluence gate passes, so a plan-attached breakdown == gate cleared.
        # Sub-gate rejects arrive via the rejection-funnel caller as a mock_plan
        # (no plan, no breakdown); that caller threads the scorer-computed
        # breakdown in as `sub_gate_factors` so the 40–69 band is logged WITH
        # factors and calibration (phase4f / pd_direction_efficacy, which filter
        # on `factors` presence) gets 3–5× the sample instead of gate-clearers only.
        entry["gate_cleared"] = bool(extra.pop("gate_cleared", True))
        _sub_factors = extra.pop("sub_gate_factors", None)
        if _cb is None and _sub_factors and "factors" not in entry:
            # Normalize to the SAME shape gate-clearers emit above (name/score/
            # weight/weighted/rationale) so downstream parsers are key-identical.
            # Orchestrator's all_factors uses `weighted_contribution`; map it.
            entry["factors"] = [
                {
                    "name": _f.get("name"),
                    "score": round(float(_f.get("score", 0) or 0), 1),
                    "weight": round(float(_f.get("weight", 0) or 0), 4),
                    "weighted": round(
                        float(_f.get("weighted", _f.get("weighted_contribution", 0)) or 0), 2
                    ),
                    "rationale": _f.get("rationale", ""),
                }
                for _f in _sub_factors
            ]
        # Indicator snapshot features attached by orchestrator
        _ml_inds = (_meta.get("ml_indicators") or {}) if isinstance(_meta, dict) else {}
        if _ml_inds:
            for _k in ("rsi", "adx", "bb_percent_b", "volume_ratio",
                       "macd_histogram", "obv_trend", "atr_percent", "volume_acceleration"):
                _v = _ml_inds.get(_k)
                if _v is not None:
                    entry[_k] = _v
        entry.update(extra)
        self.signal_log.append(entry)
        # Keep last 200 entries in memory for UI
        if len(self.signal_log) > 200:
            self.signal_log = self.signal_log[-200:]
        # Persist every signal to disk so nothing is lost on long runs
        if self._session_log_dir:
            try:
                with open(self._session_log_dir / "signals.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
            except Exception:
                pass  # Don't let logging failure crash the bot

        # Log to diagnostics
        if self.diagnostic_logger:
            diag_sev = Severity.INFO if result == "executed" else Severity.WARNING
            # FIX: was using PLAN_RR_LOW for ALL non-executed results (including "filtered"),
            # which spammed anomalies.jsonl with 440+ false plan-quality warnings.
            # Now: executed→EXEC_SUCCESS, filtered→SIGNAL_FILTERED, other (bad R:R)→PLAN_RR_LOW
            if result == "executed":
                diag_cat = ProbeCategory.EXEC_SUCCESS
            elif result == "filtered":
                diag_cat = ProbeCategory.SIGNAL_FILTERED
            else:
                diag_cat = ProbeCategory.PLAN_RR_LOW

            self.diagnostic_logger.log(
                probe_id="SIG_001",
                category=diag_cat,
                severity=diag_sev,
                message=f"Signal {result}: {plan.symbol} ({plan.direction}) | Reason: {reason}",
                context={"plan": str(plan), "result": result, "reason": reason},
                symbol=plan.symbol
            )

    async def _process_signal(self, plan: TradePlan):
        """
        Process a trade signal and potentially execute it.

        Args:
            plan: Trade plan from scanner
        """
        # Capture core components locally for the duration of this method to prevent
        # AttributeErrors if the session is stopped/reset while processing.
        config = self.config
        executor = self.executor
        position_manager = self.position_manager

        if not config or not executor or not position_manager:
            return

        # Explicitly assert for the linter (though None-check above already covers it)
        assert executor is not None
        assert config is not None
        assert position_manager is not None



        # R:R sanity cap — reject plans with unreachable targets.
        # A scalp with R:R > 4 means targets are at HTF structural levels that a
        # 15-minute scalp cannot reach; the trade will stagnate or stop out with no
        # target hits. Intraday cap is 7R, swing 15R.
        _MAX_RR_BY_TYPE = {"scalp": 4.0, "intraday": 7.0, "swing": 15.0}
        _plan_rr = getattr(plan, "risk_reward", 0.0) or 0.0
        _plan_trade_type = getattr(plan, "trade_type", "intraday") or "intraday"
        _rr_cap = _MAX_RR_BY_TYPE.get(_plan_trade_type, 7.0)
        if _plan_rr > _rr_cap:
            _rr_reason = f"R:R {_plan_rr:.1f}R exceeds {_plan_trade_type} cap ({_rr_cap}R) — targets unreachable"
            logger.info(f"SIGNAL FILTERED: {plan.symbol} {plan.direction} | {_rr_reason}")
            self._log_signal(plan, "filtered", _rr_reason, reason_type="rr_too_wide")
            self._log_activity("signal_filtered", {
                "symbol": plan.symbol, "direction": plan.direction,
                "confluence": plan.confidence_score, "reason": _rr_reason,
                "risk_reward": _plan_rr, "cap": _rr_cap,
            })
            return

        # Check if we can take more positions.
        # Only count ACTIVE (filled) positions against the cap — pending limit orders
        # hold no capital and are already deduplicated per-symbol by Gate 3.
        # Counting pending here caused valid signals to be blocked whenever the book
        # was full of stale unfilled limits, even with zero actual exposure.
        active_count = len(self._get_active_positions())
        if active_count >= config.max_positions:
            reason = f"Max positions reached ({active_count}/{config.max_positions})"
            logger.info(f"SIGNAL FILTERED: {plan.symbol} {plan.direction} | {reason}")
            self._log_signal(plan, "filtered", reason, reason_type="max_positions")
            self._log_activity("signal_filtered", {
                "symbol": plan.symbol, "direction": plan.direction,
                "confluence": plan.confidence_score, "reason": reason,
            })
            return

        # Check if already in position for this symbol.
        # If the new signal is in the OPPOSITE direction, market structure has flipped —
        # close the active position at the current market price and fall through to take
        # the new signal. Same-direction signals are dropped (no pyramid on paper).
        if self._has_position(plan.symbol):
            existing_pos = next(
                (p for p in self.position_manager.positions.values()
                 if p.symbol == plan.symbol
                 and p.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]),
                None,
            )
            existing_direction = getattr(existing_pos, "direction", None) if existing_pos else None
            direction_flipped = existing_direction is not None and existing_direction != plan.direction

            if direction_flipped and existing_pos is not None:
                # Fetch price for the close; fall back to cached price so we always have a value.
                try:
                    close_price = await self._fetch_price(plan.symbol)
                    self._price_cache[plan.symbol] = close_price
                except Exception:
                    close_price = self._price_cache.get(plan.symbol)

                # IMPORTANT: fire the exit order through the executor BEFORE
                # closing in the PositionManager so the executor's positions dict
                # and balance accounting are reconciled with the close.
                if executor and existing_pos.remaining_quantity > 0 and close_price:
                    close_side = "SELL" if existing_direction == "LONG" else "BUY"
                    try:
                        await self._execute_exit_order(
                            symbol=plan.symbol,
                            side=close_side,
                            quantity=existing_pos.remaining_quantity,
                            price=close_price,
                        )
                    except Exception as _ex:
                        logger.warning(
                            f"DIRECTION FLIP: executor close failed for {plan.symbol}: {_ex} — "
                            f"continuing with PositionManager close"
                        )

                self.position_manager.close_position(
                    existing_pos.position_id,
                    reason="direction_flip",
                    current_price=close_price,
                )
                logger.info(
                    f"DIRECTION FLIP (active): {plan.symbol} | closed {existing_direction} position "
                    f"{existing_pos.position_id} @ {close_price} | taking new {plan.direction} signal"
                )
                self._log_activity("position_closed_direction_flip", {
                    "position_id": existing_pos.position_id,
                    "symbol": plan.symbol,
                    "closed_direction": existing_direction,
                    "new_direction": plan.direction,
                    "close_price": close_price,
                    "new_confluence": plan.confidence_score,
                })
                # Fall through — continue to execute the new signal below.
            else:
                reason = "Already in position for symbol"
                logger.info(f"SIGNAL FILTERED: {plan.symbol} {plan.direction} | {reason}")
                self._log_signal(plan, "filtered", reason, reason_type="has_position")
                self._log_activity("signal_filtered", {
                    "symbol": plan.symbol, "direction": plan.direction,
                    "confluence": plan.confidence_score, "reason": reason,
                })
                return

        # Check for existing pending orders for this symbol
        _old_placed_at = None     # Used by Fix 2 (TTL preservation)
        _old_limit_price = None
        existing_order_id = next(
            (oid for oid, p in self._pending_plans.items() if p.symbol == plan.symbol), None
        )
        if existing_order_id:
            existing_plan = self._pending_plans[existing_order_id]
            direction_flipped = existing_plan.direction != plan.direction

            if direction_flipped:
                # Market structure has flipped — always cancel the stale opposite-direction
                # pending and take the new signal regardless of confluence comparison.
                logger.info(
                    f"DIRECTION FLIP: {plan.symbol} | cancelling stale {existing_plan.direction} "
                    f"pending ({existing_plan.confidence_score:.1f}%), taking {plan.direction} "
                    f"({plan.confidence_score:.1f}%)"
                )
                try:
                    executor.cancel_order(existing_order_id)
                except Exception as _ce:
                    logger.warning("cancel_order %s failed (already gone?): %s", existing_order_id, _ce)
                self._pending_plans.pop(existing_order_id, None)
                self._pending_placed_at.pop(existing_order_id, None)
                self._log_activity("pending_order_replaced", {
                    "symbol": plan.symbol,
                    "reason": "direction_flip",
                    "old_direction": existing_plan.direction,
                    "new_direction": plan.direction,
                    "old_confluence": existing_plan.confidence_score,
                    "new_confluence": plan.confidence_score,
                    "limit_price": plan.entry_zone.near_entry,
                })
            elif is_thesis_mode() or plan.confidence_score <= existing_plan.confidence_score:
                # Same direction: keep existing. Heart-change leftover-gate demotion #7 — in thesis
                # mode the demoted confluence score must NOT arbitrate between two thesis-approved
                # same-direction signals; keep the existing pending (no score-churn). Legacy mode
                # still replaces on higher confluence.
                reason = (
                    f"Pending order already exists with equal/higher confluence "
                    f"({existing_plan.confidence_score:.1f}% >= {plan.confidence_score:.1f}%)"
                )
                logger.info(f"SIGNAL FILTERED: {plan.symbol} {plan.direction} | {reason}")
                self._log_signal(plan, "filtered", reason, reason_type="pending_order")
                return
            else:
                # Same direction, better confluence — replace
                # Save old TTL/price for Fix 2 (TTL preservation on same-price replacement)
                _old_placed_at = self._pending_placed_at.get(existing_order_id)
                _old_limit_price = existing_plan.entry_zone.near_entry
                logger.info(
                    f"REPLACING PENDING ORDER: {plan.symbol} | "
                    f"old confluence={existing_plan.confidence_score:.1f}% → "
                    f"new confluence={plan.confidence_score:.1f}%"
                )
                try:
                    executor.cancel_order(existing_order_id)
                except Exception as _ce:
                    logger.warning("cancel_order %s failed (already gone?): %s", existing_order_id, _ce)
                self._pending_plans.pop(existing_order_id, None)
                self._pending_placed_at.pop(existing_order_id, None)
                self._log_activity("pending_order_replaced", {
                    "symbol": plan.symbol,
                    "reason": "higher_confluence",
                    "old_confluence": existing_plan.confidence_score,
                    "new_confluence": plan.confidence_score,
                    "limit_price": plan.entry_zone.near_entry,
                })

        # ── ML Edge Gate ──────────────────────────────────────────────────────
        # If the ML model is trained, score this signal. Reject if win
        # probability falls below threshold. This uses all available training
        # data (signals + trades) to predict which setups have real edge.
        try:
            from backend.ml.model_store import get_model_store
            _ml_store = get_model_store()
            # Heart-change leftover-gate demotion #1 — the ML edge model is trained on the OLD
            # score>=70 distribution (confidence_score / conviction_class features), so in thesis
            # mode it silently re-gates thesis-approved low-score trades on a stale prior. Skip it in
            # thesis mode (legacy unchanged). Re-introduce once retrained on thesis-era fills.
            if not is_thesis_mode() and _ml_store.status().get("trained"):
                _ml_record = {
                    "confidence_score": plan.confidence_score,
                    "risk_reward_ratio": plan.risk_reward if hasattr(plan, "risk_reward") else 0,
                    "stop_distance_atr": 0,
                    "pullback_probability": float((getattr(plan, "metadata", {}) or {}).get("pullback_probability", 0) or getattr(getattr(plan, "entry_zone", None), "pullback_probability", 0) or 0),
                    "entry_time": datetime.now(timezone.utc).isoformat(),
                    "conviction_class": getattr(plan, "conviction_class", "B"),
                    "plan_type": getattr(plan, "plan_type", "SMC"),
                    "trade_type": getattr(plan, "trade_type", "intraday"),
                    "direction": plan.direction,
                    "kill_zone": (lambda kz: kz.value if hasattr(kz, "value") else (str(kz) if kz else "no_session"))(get_current_kill_zone(datetime.now(timezone.utc))),
                    "regime": self._current_regime_composite if hasattr(self, "_current_regime_composite") else "unknown",
                }
                _win_prob = _ml_store.predict_proba(_ml_record)
                ml_threshold = getattr(config, "ml_gate_threshold", 0.40)
                if _win_prob is not None and _win_prob < ml_threshold:
                    reason = f"ML edge model: {_win_prob:.1%} win probability < {ml_threshold:.0%} threshold"
                    logger.info(f"SIGNAL FILTERED: {plan.symbol} {plan.direction} | {reason}")
                    self._log_signal(plan, "filtered", reason, reason_type="ml_gate", ml_win_prob=round(_win_prob, 3))
                    self._log_activity("signal_filtered", {
                        "symbol": plan.symbol, "direction": plan.direction,
                        "confluence": plan.confidence_score, "reason": reason,
                        "ml_win_prob": round(_win_prob, 3),
                    })
                    return
                if _win_prob is not None:
                    logger.info(f"ML PASS: {plan.symbol} {plan.direction} | win_prob={_win_prob:.1%}")
        except Exception as _ml_err:
            logger.debug("ML gate skipped: %s", _ml_err)

        # ── Signal Sensitivity gate (three-tier) ─────────────────────────────
        # Replaces the old binary threshold with a gate + soft-floor band:
        #   score >= gate       → full position size  (size_modifier = 1.0)
        #   floor <= score < gate → half position size (size_modifier = 0.5)  "near-miss"
        #   score < floor       → skip entirely
        #
        # gate and floor come from the sensitivity preset chosen at session start
        # (conservative/balanced/aggressive/custom) and are stored on ScanConfig.
        # Explicit None-check: a caller may set min_confluence=0 to force all
        # signals through for diagnostics; ``or`` would silently swallow that.
        min_score = (
            config.min_confluence
            if config.min_confluence is not None
            else (self.mode.min_confluence_score if self.mode else 60)
        )
        soft_floor = getattr(config, "confluence_soft_floor", None)
        if soft_floor is None:
            soft_floor = max(0.0, min_score - 10.0)   # fallback: 10-point band

        _preset = getattr(config, "sensitivity_preset", "balanced")

        # Apply dynamic adjustments (Phase 2: drawdown tightening,
        # Phase 3: kill zone floor relaxation)
        gate_r, floor_r, _adjustments = self._get_effective_sensitivity_thresholds(
            base_gate=min_score,
            base_floor=soft_floor,
            preset=_preset,
        )
        gate_r  = round(gate_r, 1)
        floor_r = round(floor_r, 1)
        score_r = round(plan.confidence_score, 1)

        if _adjustments:
            logger.debug(
                "Sensitivity thresholds adjusted for %s %s: %s",
                plan.symbol, plan.direction, " | ".join(_adjustments),
            )

        if score_r >= gate_r:
            size_modifier = 1.0   # full conviction — normal execution
        elif score_r >= floor_r:
            size_modifier = 0.5   # near-miss — half size, still trade
            _adj_note = f" [{'; '.join(_adjustments)}]" if _adjustments else ""
            logger.info(
                f"NEAR-MISS ENTRY: {plan.symbol} {plan.direction} "
                f"| confluence {score_r:.1f}% in band [{floor_r:.0f}–{gate_r:.0f}%]{_adj_note} "
                f"| taking at 50% position size"
            )
        elif is_thesis_mode():
            # Heart-change chunk 4: in thesis mode the confluence score is DEMOTED — the orchestrator
            # already gated go/no-go on the structural thesis (FLAT rejects upstream). A below-floor
            # score no longer SKIPS here; it takes at minimum (half) size — the score informs SIZING,
            # not the trade/no-trade decision. This is the bot's half of the dual-gate demotion
            # (must move WITH the orchestrator gate or it secretly re-score-gates the thesis trades).
            size_modifier = 0.5
            logger.info(
                f"THESIS ENTRY: {plan.symbol} {plan.direction} "
                f"| confluence {score_r:.1f}% below floor {floor_r:.0f}% (score demoted) "
                f"| taking at 50% position size"
            )
        else:
            _adj_note = f" [{'; '.join(_adjustments)}]" if _adjustments else ""
            reason = (
                f"Confluence {score_r:.1f}% below floor {floor_r:.0f}% "
                f"(gate={gate_r:.0f}%, preset={_preset}{_adj_note})"
            )
            logger.info(f"SIGNAL FILTERED: {plan.symbol} {plan.direction} | {reason}")
            self._log_signal(
                plan, "filtered", reason,
                reason_type="low_confluence",
                threshold=gate_r,
            )
            self._log_activity("signal_filtered", {
                "symbol": plan.symbol, "direction": plan.direction,
                "confluence": plan.confidence_score, "reason": reason,
            })
            return

        # ── Regime counter-trend gate ──────────────────────────────────────────
        # Block or half-size counter-trend entries based on regime strength.
        # The confluence gate alone is insufficient — a 67% B-class counter-trend
        # intraday in an up_compressed regime loses because regime-aligned
        # institutional flow absorbs the stop before the setup can work.
        #
        # Rules:
        #   strong_up / strong_down → block ALL counter-trend (no edge at any R:R)
        #   up / down / up_compressed / down_compressed → block counter-trend intraday
        #     and swing; allow scalp only at ≥70% confluence, half-sized
        #   scalp counter-trend that passes → half-size via size_modifier *= 0.5
        _ct_trend = getattr(self, "_current_regime_trend", "sideways") or "sideways"
        _ct_dir = plan.direction
        _ct_type = getattr(plan, "trade_type", "scalp") or "scalp"
        _is_ct = (
            (_ct_trend in ("up", "strong_up", "up_compressed") and _ct_dir == "SHORT") or
            (_ct_trend in ("down", "strong_down", "down_compressed") and _ct_dir == "LONG")
        )
        # Heart-change chunk 4b: honor a thesis CHoCH-reversal across the gate axis collision.
        # This gate works the GLOBAL regime; ThesisPolicy works PER-SYMBOL structure and only emits a
        # counter-trend LONG/SHORT off a genuine CHoCH (change-of-character) — it already vetoed
        # BOS-vs-strong-opposite to FLAT upstream. Re-blocking that reversal here on the global axis
        # would force a down-only bot (the adversarial-review finding). So in thesis mode, exempt a
        # CHoCH-basis reversal from the block — but HALF-SIZE it (a counter-trend reversal carries
        # risk). Legacy mode: decision_basis is absent -> _thesis_reversal False -> byte-identical.
        _ct_basis = (getattr(plan, "metadata", None) or {}).get("decision_basis")
        _thesis_reversal = is_thesis_mode() and _ct_basis == "choch"
        if _is_ct and _thesis_reversal:
            size_modifier *= 0.5
            logger.info(
                f"THESIS REVERSAL (counter-trend CHoCH, half-sized): {plan.symbol} {_ct_dir} "
                f"| global regime={_ct_trend} | per-symbol CHoCH override | size_modifier → {size_modifier:.2f}"
            )
        elif _is_ct:
            if _ct_trend in ("strong_up", "strong_down"):
                # Decisive momentum — counter-trend has near-zero EV at any timeframe
                _ct_reason = (
                    f"Counter-trend {_ct_dir} blocked: regime={_ct_trend} is decisively "
                    f"one-directional (type={_ct_type})"
                )
                logger.info(f"SIGNAL FILTERED (regime_counter_trend): {plan.symbol} | {_ct_reason}")
                self._log_signal(plan, "filtered", _ct_reason, reason_type="regime_counter_trend")
                self._log_activity("signal_filtered", {
                    "symbol": plan.symbol, "direction": plan.direction,
                    "confluence": plan.confidence_score, "reason": _ct_reason,
                    "reason_type": "regime_counter_trend",
                })
                return
            elif _ct_type in ("intraday", "swing"):
                # Directional regime: intraday/swing counter-trend has no structural support
                _ct_reason = (
                    f"Counter-trend {_ct_dir} {_ct_type} blocked: regime={_ct_trend} — "
                    f"only scalp counter-trends allowed in directional regimes"
                )
                logger.info(f"SIGNAL FILTERED (regime_counter_trend): {plan.symbol} | {_ct_reason}")
                self._log_signal(plan, "filtered", _ct_reason, reason_type="regime_counter_trend")
                self._log_activity("signal_filtered", {
                    "symbol": plan.symbol, "direction": plan.direction,
                    "confluence": plan.confidence_score, "reason": _ct_reason,
                    "reason_type": "regime_counter_trend",
                })
                return
            else:
                # Counter-trend scalp in directional regime — allowed at ≥70% only, half-sized.
                # Heart-change leftover-gate demotion #2 (operator-flagged): in thesis mode the
                # demoted confluence score must NOT gate a counter-trend scalp the thesis already
                # adjudicated (structure-led + the strong-trend block above + CHoCH exemption are the
                # controls); the trade still takes at half size. Legacy keeps the ≥70% floor.
                if not is_thesis_mode() and plan.confidence_score < 70.0:
                    _ct_reason = (
                        f"Counter-trend {_ct_dir} scalp requires ≥70% confluence in "
                        f"{_ct_trend} regime (got {plan.confidence_score:.1f}%)"
                    )
                    logger.info(f"SIGNAL FILTERED (regime_counter_trend): {plan.symbol} | {_ct_reason}")
                    self._log_signal(plan, "filtered", _ct_reason, reason_type="regime_counter_trend")
                    self._log_activity("signal_filtered", {
                        "symbol": plan.symbol, "direction": plan.direction,
                        "confluence": plan.confidence_score, "reason": _ct_reason,
                        "reason_type": "regime_counter_trend",
                    })
                    return
                # Passed: run at half size regardless of confluence tier
                size_modifier *= 0.5
                logger.info(
                    f"COUNTER-TREND SCALP (half-sized): {plan.symbol} {_ct_dir} "
                    f"| regime={_ct_trend} | conf={plan.confidence_score:.1f}% ≥70% "
                    f"| size_modifier → {size_modifier:.2f}"
                )

        # Calculate position size (size_modifier applies near-miss halving)
        balance = executor.get_balance()
        position_size = self._calculate_position_size(plan, size_modifier=size_modifier)
        if position_size <= 0:
            reason = (
                f"Invalid position size (balance={balance:.2f}, "
                f"entry={plan.entry_zone.near_entry:.2f}, "
                f"stop={plan.stop_loss.level:.2f})"
            )
            # WARNING not INFO — zero size means a valid setup was silently skipped.
            # Common cause: lot_size rounding floors a small quantity to 0.
            # Operator needs to know this is happening to diagnose sizing constraints.
            logger.warning(f"⚠️ SIGNAL SKIPPED (zero size): {plan.symbol} {plan.direction} | {reason}")
            self._log_signal(plan, "filtered", reason, reason_type="position_size", balance=balance)
            self._log_activity("signal_filtered", {
                "symbol": plan.symbol, "direction": plan.direction,
                "confluence": plan.confidence_score, "reason": reason,
            })
            return


        # Get current price
        try:
            current_price = await self._fetch_price(plan.symbol)
            self._price_cache[plan.symbol] = current_price
            if current_price <= 0:
                raise ValueError("Price is zero or negative")
        except Exception as e:
            reason = f"Price fetch failed: {e}"
            logger.error(f"SIGNAL FILTERED: {plan.symbol} {plan.direction} | {reason}")
            self._log_signal(plan, "filtered", reason, reason_type="price_fetch")
            self._log_activity("signal_filtered", {
                "symbol": plan.symbol, "direction": plan.direction,
                "confluence": plan.confidence_score, "reason": reason,
            })
            return

        # If entry is far from price and unlikely to be reached, don't clog the book with
        # low-probability pending limits. This directly improves trade frequency/quality:
        # - fewer “12h → 1 pending that never fills”
        # - frees slots for intraday/scalp setups that are actually reachable
        try:
            # Note: TradePlan.metadata defaults to ``{}`` (empty dict, falsy),
            # so a truthy check silently skips lookups on plans that simply
            # happen to carry no metadata yet. Use an explicit isinstance
            # check so an empty dict is still probed (and returns None
            # naturally via .get).
            pullback_prob = None
            _meta = getattr(plan, "metadata", None)
            if isinstance(_meta, dict):
                pullback_prob = _meta.get("pullback_probability")
            if pullback_prob is None:
                # Backward compat: some plans may carry it on the entry_zone
                pullback_prob = getattr(plan.entry_zone, "pullback_probability", None)

            # Determine if the placed limit would be fillable right now.
            side = "BUY" if plan.direction == "LONG" else "SELL"
            limit_price = float(plan.entry_zone.near_entry)
            would_fill_now = (current_price <= limit_price) if side == "BUY" else (current_price >= limit_price)

            # If it won't fill now and probability is low, skip instead of placing.
            if not would_fill_now and pullback_prob is not None:
                try:
                    pb = float(pullback_prob)
                except (TypeError, ValueError):
                    pb = None

                if pb is not None and pb < 0.45:
                    reason = f"Low pullback probability ({pb:.2f}) for limit entry @ {limit_price:.4f} (price={current_price:.4f})"
                    logger.info(f"SIGNAL FILTERED: {plan.symbol} {plan.direction} | {reason}")
                    self._log_signal(plan, "filtered", reason, reason_type="pullback_prob")
                    self._log_activity("signal_filtered", {
                        "symbol": plan.symbol,
                        "direction": plan.direction,
                        "confluence": plan.confidence_score,
                        "reason": reason,
                    })
                    return
        except Exception as _e:
            # Never let heuristics block execution; fall back to original behavior.
            pass

        # Execute entry
        try:
            side = "BUY" if plan.direction == "LONG" else "SELL"

            # Maker-execution experiment (decisions/2026-06-06__maker-execution-experiment-design.md):
            # in rest_maker we DON'T snap to market and DON'T fill immediately — we rest the limit at
            # the OB (entry_zone) and let the monitor loop fill it only when price retraces (maker).
            # HARD GUARD: forced off when use_testnet (the executor is a LiveExecutor then — §15
            # paper-only). The mismatch is logged loudly once at session start (see _start).
            _rest_maker = self.config.rest_maker_active

            # ── Limit proximity snap ──────────────────────────────────────
            # If the OB entry zone is too far from current price, the limit
            # order will sit pending and expire without filling.  Snap the
            # limit closer so it has a realistic chance of executing within
            # the TTL window.  The plan object is NOT mutated — we use a
            # local `limit_price` for placement & logging.
            _trade_type = getattr(plan, "trade_type", "intraday") or "intraday"
            _raw_limit = float(plan.entry_zone.near_entry)
            _max_dist = _MAX_LIMIT_DISTANCE_PCT.get(_trade_type, 0.40)
            if plan.confidence_score >= 70.0:
                _max_dist /= 2.0  # High-confluence → tighter snap → faster fill
            _gap_pct = abs(_raw_limit - current_price) / current_price * 100 if current_price else 0

            if _gap_pct > _max_dist and current_price > 0 and not _rest_maker:
                if side == "BUY":
                    limit_price = current_price * (1 - _max_dist / 100)
                else:
                    limit_price = current_price * (1 + _max_dist / 100)

                # ── Form-B fix (thesis mode, paper-only): bound the snap by the RR floor ──
                # Unbounded, the snap manufactures a sub-floor geometry the RR gate below then
                # rejects (planned RR 2.70 -> realized 0.60). Cap the snap at the RR-floor price so
                # it goes as far toward market as the floor allows and still fills. If even the OB
                # (_raw_limit) is sub-floor, the clamp is a no-op (no snap) and the gate rejects.
                # Paper-only: the live snap (live_trading_service) is separate code, NOT touched.
                _rr_floor_snap = float(getattr(self.config, "rr_floor_at_entry", 1.0) or 0.0)
                _stop_lvl = float(plan.stop_loss.level) if plan.stop_loss else 0.0
                if is_thesis_mode() and _rr_floor_snap > 0 and plan.targets and _stop_lvl:
                    _near_tp = min(
                        (float(t.level) for t in plan.targets), key=lambda t: abs(t - _raw_limit)
                    )
                    _pre_bound = limit_price
                    limit_price = _rr_bounded_snap(
                        side, limit_price, _raw_limit, _stop_lvl, _near_tp, _rr_floor_snap
                    )
                    if abs(limit_price - _pre_bound) > 1e-12:
                        logger.info(
                            "LIMIT SNAP RR-BOUND: %s %s | %.6g → %.6g (preserve RR floor %.2f)",
                            plan.symbol, plan.direction, _pre_bound, limit_price, _rr_floor_snap,
                        )

                # ── Recalculate position size for the wider stop distance ──
                # The snap moved entry away from the OB, increasing the distance
                # to the stop loss.  If we keep the original position size, we'd
                # risk more $ than configured.  Recalculate so risk stays constant.
                _stop = plan.stop_loss.level
                _new_risk_per_unit = abs(limit_price - _stop) if _stop else 0
                _old_risk_per_unit = abs(_raw_limit - _stop) if _stop else 0
                if _new_risk_per_unit > 0 and _old_risk_per_unit > 0:
                    _size_ratio = _old_risk_per_unit / _new_risk_per_unit
                    _orig_size = position_size
                    position_size = position_size * _size_ratio
                    logger.info(
                        "LIMIT SNAP: %s %s | entry snapped %.4f → %.4f "
                        "(gap %.2f%% > max %.2f%% for %s, conf=%.1f%%) "
                        "| size adjusted %.4f → %.4f (risk/unit %.4f → %.4f)",
                        plan.symbol, plan.direction, _raw_limit, limit_price,
                        _gap_pct, _max_dist, _trade_type, plan.confidence_score,
                        _orig_size, position_size, _old_risk_per_unit, _new_risk_per_unit,
                    )
                else:
                    logger.info(
                        "LIMIT SNAP: %s %s | entry snapped %.4f → %.4f "
                        "(gap %.2f%% > max %.2f%% for %s, conf=%.1f%%)",
                        plan.symbol, plan.direction, _raw_limit, limit_price,
                        _gap_pct, _max_dist, _trade_type, plan.confidence_score,
                    )
            else:
                limit_price = _raw_limit

            # ── Realized-RR floor (fill-geometry guard) ───────────────────────
            # The limit snap above keeps $-risk constant (it recomputes position
            # size for the wider stop) but does NOT protect the reward side: if the
            # snap pushed the entry toward a nearby TP1, reward-to-target collapses
            # while risk-to-stop widens, inverting the trade's geometry (planned RR
            # 2.1 → realized 0.3). The signal was approved on its planned edge; once
            # execution inverts the geometry that edge is gone. The gate measures the
            # TRUE post-fill RR off limit_price — which IS the actual fill price in
            # every mode (snap_taker snaps it toward market; rest_maker/no-snap rests
            # it at near_entry) — so it is correct regardless of execution_mode. NOTE:
            # this is deliberately measured off the fill, NOT entry_zone.midpoint (the
            # planner's RR reference). A rest_maker fill at near_entry — the OB edge
            # nearest target / farthest from stop — therefore reads structurally lower
            # than the midpoint-based planned RR, so the gate CAN fire on a rest_maker
            # entry (by design: near_entry IS its real geometry, not a false reject).
            # Baseline (2026-06-13, n=101, off actual journal fills — same basis as
            # this gate): 33% opened at realized RR <1.0, that cohort averaged -1.27
            # PnL vs +5.02 for >=1.0.
            # decisions/2026-06-13__fill-geometry-distortion.md
            _rr_floor = float(getattr(self.config, "rr_floor_at_entry", 1.0) or 0.0)
            if _rr_floor > 0:
                try:
                    _tgt_levels = [float(t.level) for t in (plan.targets or [])]
                    _realized_rr = _entry_realized_rr(
                        limit_price, float(plan.stop_loss.level), _tgt_levels
                    )
                    if _tgt_levels and _realized_rr > 0 and _realized_rr < _rr_floor:
                        _planned_rr = float(getattr(plan, "risk_reward_ratio", 0.0) or 0.0)
                        reason = (
                            f"Realized RR {_realized_rr:.2f} < floor {_rr_floor:.2f} at fill "
                            f"{limit_price:.6g} (planned RR {_planned_rr:.2f}) — entry geometry "
                            f"collapsed: reward-to-TP1 too small vs risk-to-stop"
                        )
                        logger.warning(
                            "ENTRY RR-FLOOR REJECT: %s %s | %s",
                            plan.symbol, plan.direction, reason,
                        )
                        self._log_signal(
                            plan, "filtered", reason,
                            reason_type="rr_collapsed_at_entry",
                            realized_rr=round(_realized_rr, 3),
                        )
                        self._log_activity("signal_filtered", {
                            "symbol": plan.symbol,
                            "direction": plan.direction,
                            "reason": "rr_collapsed_at_entry",
                            "realized_rr": round(_realized_rr, 3),
                            "planned_rr": round(_planned_rr, 3),
                            "fill_price": limit_price,
                        })
                        return
                except Exception as _rr_e:
                    # Never let the guard's own failure block execution silently — log loud,
                    # fall through to the original behavior (matches the heuristics convention).
                    logger.warning(
                        "RR-floor check errored for %s (allowing entry): %s",
                        getattr(plan, "symbol", "?"), _rr_e,
                    )

            # Use LIMIT to allow the executor to simulate realistic partial fills
            order = executor.place_order(
                symbol=plan.symbol,
                side=side,
                order_type="LIMIT",
                quantity=position_size,
                price=limit_price,
            )


            # snap_taker: fill immediately at ~market (taker). rest_maker: leave the limit RESTING at
            # the OB → fill=None routes to the pending branch, filled later by the monitor loop only
            # when price retraces to the level (maker). The execute_limit_order fill-gate
            # (paper_executor passive check) means this never crosses the spread for rest_maker.
            fill = None if _rest_maker else executor.execute_limit_order(order.order_id, current_price)

            if fill and order.status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
                # Open position in manager using the ACTUALLY filled quantity
                position_id = position_manager.open_position(
                    trade_plan=plan,
                    entry_price=fill.price,
                    quantity=fill.quantity,
                    entry_order_id=order.order_id
                )

                # ── Entry-time liquidity-pool snapshot (2026-06-13, observability-only) ──
                # Capture the SMC static pool context at entry and stash it on the live
                # PositionState so _sync_closed_positions can persist it into the journal
                # (closes the stop_in_pool_audit data wall). Read-only: NO stop/scoring/
                # execution change. Stashed via setattr because PositionState lives in the
                # out-of-bounds executor/position_manager.py — the close path reads it back
                # off the same long-lived object. NOTE (asdict caveat): _save_state's
                # asdict(pos) crash-recovery checkpoint enumerates only DECLARED dataclass
                # fields, so these setattr attrs are absent from state.json — acceptable for
                # a close-path observability field (recomputable at open), documented in the
                # decisions entry. Loud WARNING (never silent) if key_levels is missing.
                try:
                    _pos = position_manager.positions.get(position_id)
                    _meta_kl = (getattr(plan, "metadata", None) or {})
                    _entry_kl = _meta_kl.get("entry_key_levels")
                    _entry_atr = float(_meta_kl.get("atr", 0.0) or 0.0)
                    if _pos is not None:
                        if isinstance(_entry_kl, dict):
                            _np_label, _np_price, _np_dist, _np_swept = _nearest_same_side_pool(
                                _entry_kl, fill.price, plan.direction, _entry_atr
                            )
                            setattr(_pos, "entry_key_levels", _entry_kl)
                            setattr(_pos, "nearest_same_side_pool_dist_atr", _np_dist)
                            setattr(_pos, "nearest_same_side_pool_label", _np_label)
                            setattr(_pos, "nearest_same_side_pool_price", _np_price)
                            setattr(_pos, "nearest_same_side_pool_swept", _np_swept)
                        else:
                            # Absent/malformed key_levels — persist null, log loud (never skip).
                            logger.warning(
                                "ENTRY-POOL SNAPSHOT MISSING: %s %s pos=%s | plan.metadata "
                                "carried no usable entry_key_levels dict (got %s) — journal pool "
                                "context will be null for this trade",
                                plan.symbol, plan.direction, position_id, type(_entry_kl).__name__,
                            )
                            setattr(_pos, "entry_key_levels", None)
                            setattr(_pos, "nearest_same_side_pool_dist_atr", None)
                            setattr(_pos, "nearest_same_side_pool_label", None)
                            setattr(_pos, "nearest_same_side_pool_price", None)
                            setattr(_pos, "nearest_same_side_pool_swept", None)
                except Exception as _pool_e:
                    # Never let observability capture block or crash the trade.
                    logger.warning(
                        "Entry-pool snapshot capture failed for %s (trade proceeds): %s",
                        getattr(plan, "symbol", "?"), _pool_e,
                    )

                self.stats.signals_taken += 1
                
                # ... already handled by immediate fill logic ...

                _is_near_miss = size_modifier < 1.0
                logger.info(
                    f"TRADE OPENED{'  ⚡ NEAR-MISS' if _is_near_miss else ''}: "
                    f"{plan.symbol} {plan.direction} @ {fill.price:.2f} "
                    f"| qty={fill.quantity:.6f} (Requested: {position_size:.6f}) | SL={plan.stop_loss.level:.2f} "
                    f"| confluence={plan.confidence_score:.1f}% | size={size_modifier*100:.0f}%"
                )
                self._log_signal(
                    plan, "executed",
                    "Near-miss entry at 50% size" if _is_near_miss else "Trade opened successfully",
                    fill_price=fill.price, fill_qty=fill.quantity,
                    position_id=position_id,
                )
                self._log_activity("trade_opened", {
                    "position_id": position_id,
                    "symbol": plan.symbol,
                    "direction": plan.direction,
                    "entry_price": fill.price,
                    "quantity": fill.quantity,
                    "stop_loss": plan.stop_loss.level,
                    "targets": [t.level for t in plan.targets],
                    "confluence": plan.confidence_score,
                    "trade_type": getattr(plan, "trade_type", "unknown"),
                    "size_modifier": size_modifier,
                    "near_miss": _is_near_miss,
                    "sensitivity_preset": getattr(self.config, "sensitivity_preset", "balanced"),
                })
                self._save_state()
            else:
                order_status = order.status.value if order.status else "unknown"
                reason = (
                    f"Waiting for limit fill (price={current_price:.2f}, "
                    f"limit={limit_price:.2f})"
                )
                logger.info(
                    f"PENDING ORDER: {plan.symbol} {plan.direction} | {reason}"
                )
                self._log_signal(plan, "pending", reason, order_status=order_status)
                self._log_activity("pending_order_placed", {
                    "order_id": order.order_id,
                    "symbol": plan.symbol,
                    "direction": plan.direction,
                    "confluence": plan.confidence_score,
                    "limit_price": limit_price,
                    "original_entry": _raw_limit,
                    "snapped": limit_price != _raw_limit,
                    "current_price": current_price,
                })

                # Keep the plan so _monitor_loop can pick it up if it fills later
                self._pending_plans[order.order_id] = plan
                self._pending_placed_at[order.order_id] = datetime.now(timezone.utc)
                self._pending_placed_price[order.order_id] = current_price  # for adaptive TTL

                # ── Fix 2: TTL preservation on same-price replacement ─────
                # If this order replaces one at the same entry price, the
                # original placed_at should be kept so the TTL isn't reset
                # on every scan cycle (which effectively made orders immortal).
                if _old_placed_at is not None and _old_limit_price is not None:
                    _price_delta_pct = (
                        abs(limit_price - _old_limit_price) / _old_limit_price * 100
                        if _old_limit_price > 0 else 999
                    )
                    if _price_delta_pct <= 0.1:
                        self._pending_placed_at[order.order_id] = _old_placed_at
                        logger.info(
                            "TTL PRESERVED: %s | same limit price (%.4f), "
                            "keeping original placed_at (%s)",
                            plan.symbol, limit_price, _old_placed_at.isoformat(),
                        )

        except Exception as e:
            import traceback
            reason = f"Execution error: {type(e).__name__}: {e}"
            logger.error(f"SIGNAL ERROR: {plan.symbol} {plan.direction} | {reason}")
            logger.error(traceback.format_exc())
            self._log_signal(plan, "error", reason)
            self._log_activity("trade_error", {"symbol": plan.symbol, "error": str(e)})

    def _update_position_regimes(self):
        """
        Update open positions with the latest regime data.

        This ensures adaptive stagnation uses current market conditions,
        not just the regime at position entry time. A trade entered during
        a trend that later becomes choppy should have its patience reduced.
        """
        if not self.position_manager:
            return

        open_positions = self.position_manager.get_open_positions()
        for pos in open_positions:
            pos.regime_trend = self._current_regime_trend
            pos.regime_volatility = self._current_regime_volatility

    def _get_current_drawdown_pct(self) -> float:
        """Return the live peak-to-trough drawdown for the current session (0.0 if none).

        Distinct from stats.max_drawdown (session worst-ever) — this reflects the
        current drawdown from peak so dynamic gate tightening responds to live
        conditions rather than a historical worst-case that may have recovered.
        """
        if not self.executor or self._peak_equity <= 0:
            return 0.0
        current_equity = self.executor.get_balance()
        if self.position_manager:
            current_equity += sum(
                pos.unrealized_pnl
                for pos in self.position_manager.positions.values()
                if pos.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]
            )
        current_equity = max(0.0, current_equity)
        if current_equity >= self._peak_equity:
            return 0.0
        return (self._peak_equity - current_equity) / self._peak_equity * 100

    def _get_effective_sensitivity_thresholds(
        self,
        base_gate: float,
        base_floor: float,
        preset: str,
    ) -> tuple:
        """Apply dynamic adjustments to the sensitivity gate and floor.

        Two automatic adjustments run on every signal evaluation:

        Phase 2 — Drawdown-linked gate tightening:
          current drawdown ≥ 8% → hard cap to conservative (gate=72, floor=62)
            regardless of chosen preset — prevents digging deeper with weak setups.
          current drawdown ≥ 5% → shift up one preset tier automatically.
            aggressive → balanced, balanced → conservative, conservative stays.

        Phase 3 — Kill zone floor relaxation:
          Active kill zone detected → floor -= 3 (min 40).
          Kill zone timing is already a quality signal confirmed by time-of-day;
          the floor can widen slightly to capture setups that timing has validated.
          Gate is unchanged — full-size entries still need the same quality bar.

        Returns:
            (effective_gate, effective_floor, adjustments: list[str])
            adjustments is a list of human-readable strings describing what fired,
            empty list if no adjustments were made.
        """
        gate  = base_gate
        floor = base_floor
        adjustments: list = []

        # ── Phase 2: Drawdown-linked gate tightening ──────────────────────────
        current_dd = self._get_current_drawdown_pct()
        if current_dd >= 8.0:
            new_gate, new_floor = 72.0, 62.0   # hard cap to conservative
            if gate != new_gate or floor != new_floor:
                adjustments.append(
                    f"drawdown {current_dd:.1f}% ≥ 8% → hard-capped at conservative "
                    f"(gate {gate:.0f}→{new_gate:.0f}, floor {floor:.0f}→{new_floor:.0f})"
                )
            gate, floor = new_gate, new_floor
        elif current_dd >= 5.0:
            tier_name = _PRESET_TIER_UP.get(preset, "conservative")
            tier = _SENSITIVITY_PRESETS.get(tier_name, _SENSITIVITY_PRESETS["conservative"])
            new_gate, new_floor = tier["gate"], tier["floor"]
            if gate != new_gate or floor != new_floor:
                adjustments.append(
                    f"drawdown {current_dd:.1f}% ≥ 5% → shifted to {tier_name} "
                    f"(gate {gate:.0f}→{new_gate:.0f}, floor {floor:.0f}→{new_floor:.0f})"
                )
            gate, floor = new_gate, new_floor

        # ── Phase 3: Kill zone floor relaxation ───────────────────────────────
        try:
            active_kz = get_current_kill_zone(datetime.now(timezone.utc))
            if active_kz is not None:
                relaxed_floor = max(40.0, floor - 3.0)
                if relaxed_floor != floor:
                    adjustments.append(
                        f"kill zone active ({active_kz}) → floor {floor:.0f}→{relaxed_floor:.0f}"
                    )
                floor = relaxed_floor
        except Exception:
            pass  # never let kill zone lookup block a signal

        return gate, floor, adjustments

    def _calculate_position_size(self, plan: TradePlan, size_modifier: float = 1.0) -> float:
        """
        Calculate position size based on risk parameters with regime-aware adjustment.

        Risk is calculated correctly for leveraged positions:
        - risk_amount = balance * risk_pct (e.g., 1% of $10,000 = $100)
        - position_size = risk_amount / risk_per_unit (how many units to risk $100)
        - Leverage only affects MARGIN required, NOT risk amount
        - Regime policy adjusts position size up/down based on market conditions
        - size_modifier: 1.0 = full size, 0.5 = near-miss half-size (Signal Sensitivity band)

        Args:
            plan: Trade plan with stop loss
            size_modifier: Multiplier from signal sensitivity tier (1.0 full, 0.5 near-miss)

        Returns:
            Position size in base currency
        """
        config = self.config
        executor = self.executor
        if not config or not executor:
            return 0.0

        balance = executor.get_balance()
        # Include unrealized P&L so we don't oversize into an existing drawdown
        if self.position_manager:
            balance += sum(
                pos.unrealized_pnl
                for pos in self.position_manager.get_open_positions()
            )
        balance = max(balance, 0.0)  # Never size off negative effective equity

        # Apply streak-based risk adaptation, then signal-sensitivity modifier.
        # size_modifier=0.5 (near-miss band) stacks with streak adaptation:
        # e.g. 3-loss streak (50%) + near-miss (50%) = 25% of configured risk.
        effective_risk_pct = self._get_adapted_risk_pct() * size_modifier
        risk_amount = balance * (effective_risk_pct / 100)

        # Calculate risk per unit
        entry = plan.entry_zone.near_entry
        stop = plan.stop_loss.level

        if entry == 0 or stop == 0:
            return 0.0

        risk_per_unit = abs(entry - stop)
        if risk_per_unit == 0:
            return 0.0

        # Base position size from risk calculation
        position_size = risk_amount / risk_per_unit

        # FIX: Leverage affects MARGIN required, not position size.
        # With 5x leverage, you need 1/5th margin but risk stays the same.
        # Do NOT multiply position_size by leverage — that was causing
        # actual risk to be leverage * intended_risk (e.g., 5x * 2% = 10%).
        # The position_size already represents the correct number of units
        # to risk exactly risk_amount dollars.

        # Apply regime-aware position size adjustment (Fix #7)
        regime_multiplier = self._get_regime_size_multiplier()
        position_size *= regime_multiplier

        # Ensure we don't exceed available balance (accounting for leverage on margin)
        # With leverage, margin required = position_value / leverage
        margin_factor = max(1, config.leverage)

        max_position_value = balance * 0.5 * margin_factor  # 50% of balance * leverage
        max_size = max_position_value / entry if entry > 0 else 0

        final_size = min(position_size, max_size)
        
        # Apply lot size rounding to align with exchange requirements
        if hasattr(plan, 'lot_size') and plan.lot_size > 0:
            final_size = round_to_lot(final_size, plan.lot_size)

        if regime_multiplier != 1.0:
            logger.info(
                f"Position sized: {plan.symbol} | risk={effective_risk_pct:.1f}% "
                f"| regime_mult={regime_multiplier:.2f} | size={final_size:.6f}"
            )

        return final_size

    def _get_adapted_risk_pct(self) -> float:
        """
        Get risk percentage adapted by recent win/loss streak.

        Reduces risk after consecutive losses, increases slightly after wins.
        This prevents the bot from bleeding out during drawdowns.

        Returns:
            Adjusted risk percentage
        """
        if not self.config:
            return 1.0

        base_risk = self.config.risk_per_trade
        streak = self.stats.current_streak

        if streak <= -3:
            # 3+ consecutive losses: cut risk to 50%
            adapted = base_risk * 0.5
            logger.info(f"RISK ADAPTED: Losing streak {streak}, risk reduced {base_risk:.1f}% → {adapted:.1f}%")
            return adapted
        elif streak <= -2:
            # 2 consecutive losses: cut risk to 75%
            adapted = base_risk * 0.75
            return adapted
        # NOTE: Winning streak risk increase removed.
        # Crypto winning streaks often precede mean-reversion / regime flips.
        # Sizing up into a hot streak adds correlated exposure at the worst time.

        return base_risk

    def _get_regime_size_multiplier(self) -> float:
        """
        Get position size multiplier based on current regime and mode policy.

        Uses the RegimePolicy system to adjust position sizes:
        - Strong trends aligned with trade: size up
        - Choppy/sideways: size down
        - Chaotic: minimal size

        Returns:
            Multiplier (0.3 to 1.3, where 1.0 = no adjustment)
        """
        policy = getattr(self, '_current_regime_policy', None)
        composite = getattr(self, '_current_regime_composite', 'unknown')
        score = getattr(self, '_current_regime_score', 50.0)

        if not policy or not policy.position_size_adjustment:
            return 1.0

        # Try exact composite match first
        multiplier = policy.position_size_adjustment.get(composite)

        if multiplier is None:
            # Try trend-level match (extract trend from composite like "bullish_risk_on" → "up")
            trend_map = {
                "strong_up": "strong_up", "bullish": "up", "up": "up",
                "sideways": "sideways", "neutral": "sideways", "range": "sideways",
                "bearish": "down", "down": "down",
                "strong_down": "strong_down", "chaotic": "sideways",
            }
            for key, trend_key in trend_map.items():
                if key in composite.lower():
                    multiplier = policy.position_size_adjustment.get(trend_key)
                    if multiplier is not None:
                        break

        if multiplier is None:
            # Low score fallback: reduce size proportionally
            if score < 40:
                multiplier = 0.5
            elif score < 50:
                multiplier = 0.75
            else:
                multiplier = 1.0

        # Clamp to safe range
        return max(0.3, min(1.3, multiplier))

    def _get_limit_price_for_order(self, order_id: str, plan: "TradePlan") -> float:
        """Return the actual limit price placed for an order (executor's record)."""
        if self.executor:
            order = self.executor.get_order(order_id)
            if order and order.price:
                return float(order.price)
        # Fallback to plan's near_entry
        return float(plan.entry_zone.near_entry) if plan.entry_zone else 0.0

    def _has_position(self, symbol: str) -> bool:
        """Check if already in position for symbol."""
        if not self.position_manager:
            return False

        for pos in self.position_manager.positions.values():
            if pos.symbol == symbol and pos.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]:
                return True

        return False

    def _get_active_positions(self) -> List[Dict[str, Any]]:
        """Get list of active positions with current P&L."""
        if not self.position_manager:
            return []

        positions = []
        for pos in self.position_manager.positions.values():
            if pos.status not in [PositionStatus.OPEN, PositionStatus.PARTIAL]:
                continue

            current_price = self._price_cache.get(pos.symbol, pos.entry_price)
            pos.update_unrealized_pnl(current_price)

            # Reconstruct full target ladder: hit targets first (in execution order),
            # then remaining. Preserves TP1/TP2/TP3 labels even after partial exits.
            _all_tgts = list(pos.targets_hit) + list(pos.targets)

            positions.append(
                {
                    "position_id": pos.position_id,
                    "symbol": pos.symbol,
                    "direction": pos.direction,
                    "entry_price": pos.entry_price,
                    "current_price": current_price,
                    "quantity": pos.quantity,
                    "remaining_quantity": pos.remaining_quantity,
                    "stop_loss": pos.stop_loss,
                    "targets_remaining": len(pos.targets),
                    "targets_hit": len(pos.targets_hit),
                    # Tier 1.3: surface lifetime strip count + current valid TP
                    # count on the live payload so the modal NO-TP chip fires
                    # in-flight (was previously only on closed-trade journal
                    # rows). When final_targets_remaining=0 OR
                    # targets_stripped_count>0, the executor's structural-
                    # validity guard has stripped targets and the position
                    # can exit only via SL / stagnation / max_hours_open.
                    "final_targets_remaining": len(getattr(pos, "targets", []) or []),
                    "targets_stripped_count": getattr(pos, "targets_stripped_count", 0),
                    "unrealized_pnl": pos.unrealized_pnl,
                    "unrealized_pnl_pct": pos.pnl_percentage,
                    "target_pnl": pos.target_pnl,
                    "risk_pnl": pos.risk_pnl,
                    "breakeven_active": pos.breakeven_active,
                    "trailing_active": pos.trailing_active,
                    "opened_at": pos.created_at.isoformat(),
                    # Emit None (not 0.0) when targets are missing — a 0.0 in
                    # the payload is indistinguishable from a real TP at price 0
                    # and breaks the frontend's `??` fallback. Mirrors
                    # live_trading_service._get_active_positions().
                    # Empty `_all_tgts` typically means position_manager's
                    # structural-validity guard stripped every target as
                    # geometrically invalid (see position_manager.py
                    # _check_target_hit ~L985). The position can still exit via
                    # SL / stagnation / max_hours_open, but never via TP.
                    "tp1": _all_tgts[0].level if _all_tgts else None,
                    "tp2": _all_tgts[1].level if len(_all_tgts) > 1 else None,
                    "tp_final": _all_tgts[-1].level if _all_tgts else None,
                    "trade_type": getattr(pos, "trade_type", "intraday"),
                    "initial_stop_loss": getattr(pos, "initial_stop_loss", pos.stop_loss),
                }
            )

        return positions

    def _journal_pnl_for(self, pos) -> float:
        """Journal P&L = the executor's ACTUAL realized cash for this position (net of fees, on the
        actually-filled qty), so the journal matches the account and edge measurement is trustworthy.
        Falls back to pos.total_pnl when the executor doesn't track it (live executor / simulation),
        leaving those paths unchanged. (2026-06-27 journal-vs-executor reconciliation, paper-only.)"""
        _exec = getattr(self, "executor", None)
        if _exec is not None and hasattr(_exec, "pop_position_realized"):
            _actual = _exec.pop_position_realized(getattr(pos, "symbol", None))
            if _actual is not None:
                return float(_actual)
        return pos.total_pnl

    async def _sync_closed_positions(self):
        """Check for positions that have been closed and record them."""
        if not self.position_manager:
            return

        for pos in list(self.position_manager.positions.values()):
            if pos.status in [
                PositionStatus.CLOSED,
                PositionStatus.STOPPED_OUT,
                PositionStatus.EMERGENCY_EXIT,
            ]:
                # Check if already recorded (O(1) set lookup)
                if pos.position_id in self._completed_trade_ids:
                    continue

                # Record completed trade
                exit_reason = pos.exit_reason or ("target" if pos.status == PositionStatus.CLOSED else "stop_loss")
                if pos.status == PositionStatus.EMERGENCY_EXIT:
                    exit_reason = "emergency"

                # MFE/MAE as % of entry price.
                # highest_price and lowest_price are now tracked for all directions
                # (both initialized to entry_price in __post_init__).
                _entry = pos.entry_price
                _high = pos.highest_price or _entry
                _low = pos.lowest_price or _entry
                if pos.direction == "LONG":
                    _mfe = max(0.0, (_high - _entry) / _entry * 100) if _entry else 0.0
                    _mae = max(0.0, (_entry - _low) / _entry * 100) if _entry else 0.0
                else:  # SHORT
                    _mfe = max(0.0, (_entry - _low) / _entry * 100) if _entry else 0.0
                    _mae = max(0.0, (_high - _entry) / _entry * 100) if _entry else 0.0

                trade = CompletedTrade(
                    trade_id=pos.position_id,
                    symbol=pos.symbol,
                    direction=pos.direction,
                    entry_price=pos.entry_price,
                    exit_price=pos.exit_price or self._price_cache.get(pos.symbol, pos.entry_price),
                    quantity=pos.quantity,
                    entry_time=pos.created_at,
                    exit_time=pos.updated_at,
                    pnl=self._journal_pnl_for(pos),
                    pnl_pct=pos.pnl_percentage,
                    exit_reason=exit_reason,
                    targets_hit=[i for i, _ in enumerate(pos.targets_hit)],
                    max_favorable=_mfe,
                    max_adverse=_mae,
                    trade_type=getattr(pos, "trade_type", "intraday"),
                    confidence_score=getattr(pos, "confidence_score", 0.0),
                    conviction_class=getattr(pos, "conviction_class", "B"),
                    plan_type=getattr(pos, "plan_type", "SMC"),
                    risk_reward_ratio=getattr(pos, "risk_reward_ratio", 0.0),
                    stop_distance_atr=getattr(pos, "stop_distance_atr", 0.0),
                    timeframe=getattr(pos, "timeframe", "1h"),
                    # Bucket by ENTRY regime, not the close-time value the stagnation
                    # updater clobbers into regime_trend/regime_volatility every scan.
                    # decisions/2026-06-16 §11.6 bug #1.
                    regime=f"{getattr(pos, 'entry_regime_trend', 'unknown')}_{getattr(pos, 'entry_regime_volatility', 'unknown')}",
                    pullback_probability=getattr(pos, "pullback_probability", 0.0),
                    kill_zone=getattr(pos, "kill_zone", "no_session"),
                    final_targets_remaining=len(getattr(pos, "targets", []) or []),
                    targets_stripped_count=getattr(pos, "targets_stripped_count", 0),
                    # Tier 2 macro snapshot pass-through (populated at open_position
                    # from plan.metadata["macro"] / ["global_regime"]).
                    btc_velocity_1h_at_entry=getattr(pos, "btc_velocity_1h_at_entry", 0.0),
                    alt_velocity_1h_at_entry=getattr(pos, "alt_velocity_1h_at_entry", 0.0),
                    macro_state_at_entry=getattr(pos, "macro_state_at_entry", "unknown"),
                    regime_trend_at_entry=getattr(pos, "entry_regime_trend", "sideways"),
                    regime_labeled_at=getattr(pos, "regime_labeled_at", "entry"),
                    htf_aligned_at_entry=getattr(pos, "htf_aligned_at_entry", False),
                    setup_qualifier=getattr(pos, "setup_qualifier", "Unknown"),
                    # Calculated stop/target geometry captured at open (2026-06-02).
                    # initial_stop_loss = original SL (pre-trail); initial_target_levels =
                    # original TP ladder (pre strip/hit). See PositionState.__post_init__.
                    stop_loss_level=float(getattr(pos, "initial_stop_loss", 0.0) or 0.0),
                    target_levels=list(getattr(pos, "initial_target_levels", []) or []),
                    stop_loss_rationale=str(getattr(pos, "stop_loss_rationale", "") or ""),
                    tp1_clamped=bool(getattr(pos, "tp1_clamped", False)),
                    tp1_realized_rr=float(getattr(pos, "tp1_realized_rr", 0.0) or 0.0),
                    execution_mode=getattr(self.config, "execution_mode", "snap_taker"),
                    # Entry-time liquidity-pool context, stashed on the position at open
                    # (2026-06-13 observability). getattr defaults keep older/recovered
                    # positions (whose state.json lacked these setattr attrs) null-safe.
                    entry_key_levels=getattr(pos, "entry_key_levels", None),
                    nearest_same_side_pool_dist_atr=getattr(pos, "nearest_same_side_pool_dist_atr", None),
                    nearest_same_side_pool_label=getattr(pos, "nearest_same_side_pool_label", None),
                    nearest_same_side_pool_price=getattr(pos, "nearest_same_side_pool_price", None),
                    nearest_same_side_pool_swept=getattr(pos, "nearest_same_side_pool_swept", None),
                )

                self.completed_trades.append(trade)
                self._completed_trade_ids.add(trade.trade_id)

                # Persist trade to telemetry DB for queryable historical data
                if self.telemetry_storage:
                    try:
                        _evt_type = (
                            EventType.STOP_LOSS_HIT
                            if exit_reason == "stop_loss"
                            else EventType.POSITION_CLOSED
                        )
                        self.telemetry_storage.store_event(TelemetryEvent(
                            event_type=_evt_type,
                            timestamp=trade.exit_time or datetime.now(timezone.utc),
                            run_id=self.session_id,
                            symbol=trade.symbol,
                            data={
                                "trade_id": trade.trade_id,
                                "direction": trade.direction,
                                "entry_price": trade.entry_price,
                                "exit_price": trade.exit_price,
                                "quantity": trade.quantity,
                                "pnl": trade.pnl,
                                "pnl_pct": trade.pnl_pct,
                                "exit_reason": trade.exit_reason,
                                "trade_type": trade.trade_type,
                                "targets_hit": trade.targets_hit,
                                "max_favorable": trade.max_favorable,
                                "max_adverse": trade.max_adverse,
                            },
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to persist trade to telemetry DB: {e}")

                # CRITICAL: Remove from position manager to prevent "Zombie" active
                # positions and memory leaks. The trade is now in completed_trades.
                # Use the public, lock-guarded helper instead of mutating the
                # underlying dict directly — otherwise this races with the
                # monitor loop's iteration over get_open_positions().
                self.position_manager.remove_position(pos.position_id)
                logger.info(f"💾 Trade {pos.position_id} archived and removed from active tracking")
                self._update_stats(trade)

                # Register stop-loss cooldown in orchestrator so the symbol is
                # locked out of re-entry for _cooldown_hours. Without this call the
                # orchestrator's CooldownManager never learns about runtime stop-outs
                # (which are fired by the position_manager, not the orchestrator itself),
                # so the same broken level can be re-entered seconds later.
                if exit_reason == "stop_loss" and self.orchestrator:
                    try:
                        self.orchestrator.register_stop_out(
                            symbol=pos.symbol,
                            direction=pos.direction,
                            price=trade.exit_price or pos.entry_price,
                            trade_type=getattr(pos, "trade_type", "intraday"),
                        )
                    except Exception as _e:
                        logger.warning(
                            f"Failed to register stop-out cooldown for {pos.symbol}: {_e}"
                        )
                elif exit_reason in ("target", "stagnation", "target_strip") and self.orchestrator:
                    # Short cooldown after target/stagnation exit — prevents the bot from
                    # immediately re-entering the same level and churning. Shorter than
                    # stop-out cooldown; the level isn't invalidated, just recently resolved.
                    _target_cooldown_hours = {"scalp": 0.25, "intraday": 0.5, "swing": 1.0}
                    _hours = _target_cooldown_hours.get(
                        getattr(pos, "trade_type", "scalp"), 0.25
                    )
                    try:
                        self.orchestrator.cooldown_manager.add_cooldown(
                            symbol=pos.symbol,
                            direction=pos.direction,
                            price=trade.exit_price or pos.entry_price,
                            reason="target_exit",
                            duration_hours=_hours,
                        )
                        logger.debug(
                            f"TARGET COOLDOWN: {pos.symbol} {pos.direction} locked "
                            f"{_hours * 60:.0f}min after {exit_reason} exit"
                        )
                    except Exception as _e:
                        logger.warning(
                            f"Failed to register target-exit cooldown for {pos.symbol}: {_e}"
                        )

                self._log_activity(
                    "trade_closed",
                    {
                        "position_id": pos.position_id,
                        "symbol": pos.symbol,
                        "direction": pos.direction,
                        "entry_price": pos.entry_price,
                        "exit_price": trade.exit_price,
                        "pnl": trade.pnl,
                        "pnl_pct": trade.pnl_pct,
                        "exit_reason": exit_reason,
                        "trade_type": getattr(pos, "trade_type", "unknown"),
                        "regime_at_close": {
                            "trend": getattr(pos, "regime_trend", "unknown"),
                            "volatility": getattr(pos, "regime_volatility", "unknown"),
                        },
                    },
                )
                self._save_state()

    async def _close_all_positions(self, reason: str):
        """Close all open positions."""
        if not self.position_manager:
            return

        for pos in list(self.position_manager.positions.values()):
            if pos.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]:
                current_price = self._price_cache.get(pos.symbol, pos.entry_price)
                self.position_manager.close_position(pos.position_id, reason, current_price)

        # Sync to completed trades
        await self._sync_closed_positions()

    def _update_stats(self, trade: CompletedTrade):
        """Update statistics after a trade completes."""
        try:
            get_trade_journal().append(trade.to_dict(), self.session_id or "unknown")
        except Exception as _je:
            logger.warning("Failed to write trade to journal: %s", _je)

        self.stats.total_trades += 1

        # Scratch: |P&L| < $1 (negligible result, usually slippage/commission noise).
        # Classified separately — not counted in winning_trades or losing_trades.
        _SCRATCH_THRESHOLD = 1.0
        _is_scratch = abs(trade.pnl) < _SCRATCH_THRESHOLD

        if _is_scratch:
            self.stats.scratch_trades += 1
            # Streak is unaffected by scratches
        elif trade.pnl > 0:
            self.stats.winning_trades += 1
            self.stats.current_streak = (
                max(1, self.stats.current_streak + 1) if self.stats.current_streak >= 0 else 1
            )

            if self.stats.winning_trades > 0:
                self.stats.avg_win = (
                    self.stats.avg_win * (self.stats.winning_trades - 1) + trade.pnl
                ) / self.stats.winning_trades

            if trade.pnl > self.stats.best_trade:
                self.stats.best_trade = trade.pnl
        else:
            self.stats.losing_trades += 1
            self.stats.current_streak = (
                min(-1, self.stats.current_streak - 1) if self.stats.current_streak <= 0 else -1
            )

            if self.stats.losing_trades > 0:
                self.stats.avg_loss = (
                    self.stats.avg_loss * (self.stats.losing_trades - 1) + trade.pnl
                ) / self.stats.losing_trades

            if trade.pnl < self.stats.worst_trade:
                self.stats.worst_trade = trade.pnl

        self.stats.total_pnl += trade.pnl

        if self.config:
            self.stats.total_pnl_pct = (self.stats.total_pnl / self.config.initial_balance) * 100

        if self.stats.total_trades > 0:
            # win_rate denominator includes scratch trades by design: a scratch is
            # a real trading decision with no meaningful profit. Excluding scratches
            # would inflate the win rate in choppy sessions (e.g. 5W/5S/0L → 100%
            # instead of the correct 50%). Use winning_trades + losing_trades for
            # a "decisive-trade" ratio if needed separately.
            self.stats.win_rate = (self.stats.winning_trades / self.stats.total_trades) * 100
            self.stats.expectancy = self.stats.total_pnl / self.stats.total_trades

        if abs(self.stats.avg_loss) > 0.01:
            self.stats.avg_rr = abs(self.stats.avg_win / self.stats.avg_loss)

        # --- Exit reason breakdown ---
        reason = trade.exit_reason or "unknown"
        self.stats.exit_reasons[reason] = self.stats.exit_reasons.get(reason, 0) + 1

        # --- Per-trade-type breakdown ---
        tt = trade.trade_type or "unknown"
        if tt not in self.stats.by_trade_type:
            self.stats.by_trade_type[tt] = {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
            }
        bucket = self.stats.by_trade_type[tt]
        bucket["trades"] += 1
        bucket["total_pnl"] += trade.pnl
        if trade.pnl > 0:
            bucket["wins"] += 1
            bucket["avg_win"] = (
                bucket["avg_win"] * (bucket["wins"] - 1) + trade.pnl
            ) / bucket["wins"]
        else:
            bucket["losses"] += 1
            bucket["avg_loss"] = (
                bucket["avg_loss"] * (bucket["losses"] - 1) + trade.pnl
            ) / bucket["losses"]
        bucket["win_rate"] = (bucket["wins"] / bucket["trades"]) * 100

        # Update max drawdown on each trade close
        self._update_drawdown()

    def _save_state(self) -> None:
        """Write a crash-recovery checkpoint to state.json in the session log dir.

        Called after every position open/close and on session stop so that a server
        restart can show what was happening. Uses an atomic write (tmp → rename) to
        avoid a corrupt checkpoint if the process dies mid-write.

        Restoring from this file is a manual/future operation — it does not
        automatically resume the session, but it gives enough context to reconstruct
        what happened and what the final balance / open exposure was.
        """
        if not self._session_log_dir:
            return
        try:
            # Serialize open/partial positions
            positions_data = []
            if self.position_manager:
                for pos in self.position_manager.positions.values():
                    if pos.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]:
                        positions_data.append(asdict(pos))

            # Serialize pending orders — simplified (no full TradePlan graph needed)
            pending_data = []
            for order_id, plan in self._pending_plans.items():
                placed_at = self._pending_placed_at.get(order_id)
                pending_data.append({
                    "order_id": order_id,
                    "symbol": plan.symbol,
                    "direction": plan.direction,
                    "limit_price": getattr(plan.entry_zone, "near_entry", None),
                    "stop_loss": getattr(plan.stop_loss, "level", None),
                    "targets": [
                        {"level": t.level, "percentage": t.percentage, "label": getattr(t, "label", "")}
                        for t in (plan.targets or [])
                    ],
                    "trade_type": getattr(plan, "trade_type", "intraday"),
                    "confluence": getattr(plan, "confidence_score", None),
                    "placed_at": placed_at.isoformat() if placed_at else None,
                })

            state = {
                "session_id": self.session_id,
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "config": self.config.to_dict() if self.config else None,
                "balance": self.executor.get_balance() if self.executor else None,
                "stats": self.stats.to_dict(),
                "positions": positions_data,
                "pending_orders": pending_data,
            }

            state_path = self._session_log_dir / "state.json"
            tmp_path = state_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, default=str)
            tmp_path.rename(state_path)

        except Exception as e:
            logger.warning(f"State checkpoint save failed: {e}")

    def _update_drawdown(self) -> None:
        """Recompute peak equity and max drawdown from current balance + unrealized PnL.

        Called both on trade close (via _update_stats) and on every monitor loop tick
        so that drawdown is captured in real-time, not only when positions close.
        """
        if not self.executor or not self.config:
            return
        # Equity = realized balance + all unrealized PnL on open/partial positions
        current_equity = self.executor.get_balance()
        if self.position_manager:
            current_equity += sum(
                pos.unrealized_pnl
                for pos in self.position_manager.positions.values()
                if pos.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]
            )
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity
        elif self._peak_equity > 0:
            drawdown = (self._peak_equity - current_equity) / self._peak_equity * 100
            if drawdown > self.stats.max_drawdown:
                self.stats.max_drawdown = drawdown

    def _task_done_callback(self, task: "asyncio.Task") -> None:
        """
        Done-callback for fire-and-forget ``asyncio.create_task`` jobs.

        Without this, exceptions raised by background tasks (scan loop,
        monitor loop, self-stop triggers) are swallowed by the event loop
        and only emitted at GC time as ``Task exception was never retrieved``.
        This makes real failures invisible in the activity log / UI.
        """
        try:
            if task.cancelled():
                return
            exc = task.exception()
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.exception(f"Error reading background task result: {e}")
            return

        if exc is not None:
            task_name = getattr(task, "get_name", lambda: "<task>")()
            logger.exception(
                f"Background task {task_name!r} failed: {exc}",
                exc_info=exc,
            )
            try:
                self._log_activity(
                    "background_task_error",
                    {"task_name": task_name, "error": str(exc)},
                )
            except Exception:
                # _log_activity must never re-raise from inside a callback
                pass

    def _log_activity(self, event_type: str, data: Dict[str, Any]):
        """Add event to activity log."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "data": data,
        }
        self.activity_log.append(entry)

        # Keep log manageable in memory
        if len(self.activity_log) > 1000:
            self.activity_log = self.activity_log[-500:]

        # Persist to disk so nothing is lost
        if self._session_log_dir:
            try:
                with open(self._session_log_dir / "activity.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, default=str) + "\n")
            except Exception:
                pass

    def _generate_session_report(self) -> Optional[Path]:
        """
        Generate a comprehensive diagnostic report from the live session data.

        Writes a markdown report + raw JSONL data to the session log directory.
        Designed to be AI-readable for automated investigation and fixes.
        """
        if not self._session_log_dir:
            return None

        log_dir = self._session_log_dir
        report_path = log_dir / "diagnostic_report.md"

        # --- Persist raw data files ---
        try:
            # Completed trades
            with open(log_dir / "trades.jsonl", "w", encoding="utf-8") as f:
                for trade in self.completed_trades:
                    f.write(json.dumps(trade.to_dict(), default=str) + "\n")

            # Full signal log from disk (already written incrementally)
            # signals.jsonl is already populated by _log_signal

            # Stats snapshot
            with open(log_dir / "stats.json", "w", encoding="utf-8") as f:
                json.dump(self.stats.to_dict(), f, indent=2)

            # Config
            if self.config:
                with open(log_dir / "config.json", "w", encoding="utf-8") as f:
                    json.dump(self.config.to_dict(), f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to persist raw session data: {e}")

        # --- Build the markdown report ---
        try:
            lines = []
            now = datetime.now(timezone.utc)
            started = self.started_at or now
            stopped = self.stopped_at or now
            duration_h = (stopped - started).total_seconds() / 3600

            lines.append("# SniperSight Paper Trading Session Report\n")
            lines.append(f"*Session:* `{self.session_id}`  ")
            lines.append(f"*Generated:* {now.isoformat()}Z  ")
            lines.append(f"*Duration:* {duration_h:.1f} hours  ")
            lines.append(f"*Mode:* {self.config.sniper_mode if self.config else 'unknown'}\n")

            # --- Executive Summary ---
            lines.append("\n## Executive Summary\n")
            s = self.stats
            initial = self.config.initial_balance if self.config else 0
            final_equity = initial  # fallback
            if self.executor:
                unrealized = 0.0
                if self.position_manager:
                    unrealized = sum(
                        p.unrealized_pnl for p in self.position_manager.positions.values()
                        if p.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]
                    )
                final_equity = self.executor.get_balance() + unrealized

            pnl = final_equity - initial
            pnl_pct = (pnl / initial * 100) if initial > 0 else 0

            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Starting Balance | ${initial:,.2f} |")
            lines.append(f"| Final Equity | ${final_equity:,.2f} |")
            lines.append(f"| Net P&L | ${pnl:,.2f} ({pnl_pct:+.2f}%) |")
            lines.append(f"| Total Trades | {s.total_trades} |")
            lines.append(f"| Expectancy | ${s.expectancy:+.2f}/trade |")
            lines.append(f"| Outcome Split | {s.winning_trades}W / {s.scratch_trades}S / {s.losing_trades}L (win rate {s.win_rate:.1f}%) |")
            lines.append(f"| Avg R:R | {s.avg_rr:.2f} |")
            lines.append(f"| Best Trade | ${s.best_trade:,.2f} |")
            lines.append(f"| Worst Trade | ${s.worst_trade:,.2f} |")
            lines.append(f"| Max Drawdown | {s.max_drawdown:.2f}% |")
            lines.append(f"| Scans Completed | {s.scans_completed} |")
            lines.append(f"| Signals Generated | {s.signals_generated} |")
            lines.append(f"| Signals Taken | {s.signals_taken} |")
            lines.append(f"| Signal Pass Rate | {(s.signals_taken / s.signals_generated * 100) if s.signals_generated > 0 else 0:.1f}% |")
            lines.append("")

            # --- Trade Log ---
            lines.append("\n## Completed Trades\n")
            if self.completed_trades:
                lines.append("| # | Symbol | Dir | Entry | Exit | P&L % | Exit Reason | Type | Duration |")
                lines.append("|---|--------|-----|-------|------|-------|-------------|------|----------|")
                for i, t in enumerate(self.completed_trades, 1):
                    dur = ""
                    if t.entry_time and t.exit_time:
                        dur_h = (t.exit_time - t.entry_time).total_seconds() / 3600
                        dur = f"{dur_h:.1f}h"
                    icon = "+" if t.pnl >= 0 else ""
                    lines.append(
                        f"| {i} | {t.symbol} | {t.direction} | "
                        f"${t.entry_price:.2f} | ${t.exit_price:.2f} | "
                        f"{icon}{t.pnl_pct:.2f}% | {t.exit_reason} | {t.trade_type} | {dur} |"
                    )
                lines.append("")
            else:
                lines.append("*No completed trades this session.*\n")

            # --- Signal Rejection Analysis ---
            lines.append("\n## Signal Rejection Analysis\n")
            # Read the full signal log from disk (not the truncated in-memory version)
            all_signals = []
            signals_file = log_dir / "signals.jsonl"
            if signals_file.exists():
                with open(signals_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            all_signals.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass

            if all_signals:
                total_signals = len(all_signals)
                executed = [s for s in all_signals if s.get("result") == "executed"]
                filtered = [s for s in all_signals if s.get("result") == "filtered"]
                pending  = [s for s in all_signals if s.get("result") == "pending"]

                lines.append(f"**Total signals processed:** {total_signals}  ")
                lines.append(f"**Executed:** {len(executed)} | **Filtered:** {len(filtered)} | **Pending:** {len(pending)}\n")

                # ── Macro Context Snapshot ─────────────────────────────────────────────
                if hasattr(self, "_orchestrator") and self._orchestrator:
                    _mc = getattr(self._orchestrator, "macro_context", None)
                    if _mc:
                        lines.append("### Macro Context (Last Scan)\n")
                        lines.append(f"| Field | Value |")
                        lines.append(f"|-------|-------|")
                        lines.append(f"| State | **{getattr(_mc, 'macro_state', 'N/A')}** |")
                        lines.append(f"| BTC Dom | {getattr(_mc, 'btc_dom', 0):.1f}% |")
                        lines.append(f"| ALT Dom | {getattr(_mc, 'alt_dom', 0):.1f}% |")
                        lines.append(f"| Stable Dom | {getattr(_mc, 'stable_dom', 0):.1f}% |")
                        lines.append(f"| BTC Dir | {getattr(_mc, 'btc_dir', '?')} |")
                        lines.append(f"| ALT Dir | {getattr(_mc, 'alt_dir', '?')} |")
                        lines.append(f"| Cluster Score | {getattr(_mc, 'cluster_score', 0)} |")
                        lines.append(f"| Macro Score | {getattr(_mc, 'macro_score', 0)} |")
                        _notes = getattr(_mc, "notes", [])
                        if _notes:
                            lines.append(f"| Notes | {'; '.join(str(n) for n in _notes[-5:])} |")
                        lines.append("")

                # ── Gate Kill Breakdown ──────────────────────────────────────────────────
                gate_counts: Dict[str, int] = {}
                for sig in filtered:
                    gate = sig.get("gate_name") or sig.get("reason_type") or "unknown"
                    gate_counts[gate] = gate_counts.get(gate, 0) + 1
                if gate_counts:
                    lines.append("### Gate Kill Breakdown\n")
                    lines.append("| Gate | Count | % of Filtered |")
                    lines.append("|------|-------|---------------|")
                    for gate, count in sorted(gate_counts.items(), key=lambda x: -x[1]):
                        pct = count / len(filtered) * 100 if filtered else 0
                        lines.append(f"| {gate} | {count} | {pct:.1f}% |")
                    lines.append("")

                # ── Score Distribution Histogram ─────────────────────────────────────────
                score_buckets = {"<40%": 0, "40–50%": 0, "50–55%": 0, "55–60%": 0, "60–65%": 0, "65–70%": 0, "≥70%": 0}
                for sig in filtered:
                    sc = sig.get("confluence", 0) or 0
                    if sc < 40:   score_buckets["<40%"] += 1
                    elif sc < 50: score_buckets["40–50%"] += 1
                    elif sc < 55: score_buckets["50–55%"] += 1
                    elif sc < 60: score_buckets["55–60%"] += 1
                    elif sc < 65: score_buckets["60–65%"] += 1
                    elif sc < 70: score_buckets["65–70%"] += 1
                    else:         score_buckets["≥70%"] += 1
                lines.append("### Score Distribution (Filtered Signals)\n")
                lines.append("| Band | Count |")
                lines.append("|------|-------|")
                for band, cnt in score_buckets.items():
                    bar = "█" * min(cnt, 20)
                    lines.append(f"| {band} | {cnt} {bar} |")
                lines.append("")

                # ── Near-Miss Signals ────────────────────────────────────────────────────
                # Signals that passed soft floor (55%) but didn't reach hard gate (65%) — closest-to-firing
                gate_threshold = getattr(self.orchestrator.config, "min_confluence_score", 65.0) if self.orchestrator else 65.0
                soft_floor     = getattr(self.orchestrator.config, "confluence_soft_floor", None) if self.orchestrator else None
                if soft_floor is None:
                    soft_floor = max(0.0, gate_threshold - 10.0)
                near_misses = [
                    s for s in filtered
                    if (s.get("confluence") or 0) >= soft_floor
                    and (s.get("confluence") or 0) < gate_threshold
                ]
                if near_misses:
                    lines.append(f"### Near-Miss Signals ({len(near_misses)} signals scored {soft_floor:.0f}–{gate_threshold:.0f}%)\n")
                    lines.append("| Symbol | Dir | Score | Missing Factors | Gate |")
                    lines.append("|--------|-----|-------|-----------------|------|")
                    for nm in sorted(near_misses, key=lambda x: -(x.get("confluence") or 0))[:20]:
                        missing = ", ".join(nm.get("convergence_missing", [])[:3]) or "—"
                        lines.append(
                            f"| {nm.get('symbol','?')} | {nm.get('direction','?')} | "
                            f"{nm.get('confluence',0):.1f}% | {missing} | {nm.get('gate_name','?')} |"
                        )
                    if len(near_misses) > 20:
                        lines.append(f"\n*...and {len(near_misses) - 20} more near-miss signals.*")
                    lines.append("")
                else:
                    lines.append(f"*No near-miss signals in the {soft_floor:.0f}–{gate_threshold:.0f}% band.*\n")

                # ── Missing Critical Factor Frequency ────────────────────────────────────
                factor_absent: Dict[str, int] = {}
                for sig in filtered:
                    for f in sig.get("convergence_missing", []):
                        factor_absent[f] = factor_absent.get(f, 0) + 1
                if factor_absent:
                    lines.append("### Most Frequently Missing Critical Factors\n")
                    lines.append("| Factor | Absent In | % of Filtered |")
                    lines.append("|--------|-----------|---------------|")
                    for factor, cnt in sorted(factor_absent.items(), key=lambda x: -x[1])[:10]:
                        pct = cnt / len(filtered) * 100 if filtered else 0
                        lines.append(f"| {factor} | {cnt} | {pct:.1f}% |")
                    lines.append("")

                # ── Per-Symbol Closest Approach ───────────────────────────────────────────
                symbol_best: Dict[str, dict] = {}
                all_symbols = set(s.get("symbol") for s in all_signals)
                for sym in all_symbols:
                    sym_signals = [s for s in all_signals if s.get("symbol") == sym]
                    best = max(sym_signals, key=lambda x: x.get("confluence") or 0)
                    symbol_best[sym] = best
                if symbol_best:
                    lines.append("### Per-Symbol Closest Approach\n")
                    lines.append("| Symbol | Best Score | Gate | Top Missing | Executed? |")
                    lines.append("|--------|------------|------|-------------|-----------|")
                    for sym, best in sorted(symbol_best.items(), key=lambda x: -(x[1].get("confluence") or 0)):
                        missing_top = (best.get("convergence_missing", []) or [])
                        missing_str = missing_top[0] if missing_top else "—"
                        did_exec = "✅" if any(s.get("symbol") == sym and s.get("result") == "executed" for s in all_signals) else "❌"
                        lines.append(
                            f"| {sym} | {best.get('confluence', 0):.1f}% | "
                            f"{best.get('gate_name', '?')} | {missing_str} | {did_exec} |"
                        )
                    lines.append("")

                # ── Rejections by Symbol ─────────────────────────────────────────────────
                symbol_rejected: Dict[str, int] = {}
                for sig in filtered:
                    sym = sig.get("symbol", "?")
                    symbol_rejected[sym] = symbol_rejected.get(sym, 0) + 1
                if symbol_rejected:
                    lines.append("### Rejections by Symbol\n")
                    lines.append("| Symbol | Rejected | Executed |")
                    lines.append("|--------|----------|----------|")
                    for sym in sorted(all_symbols):
                        rej = symbol_rejected.get(sym, 0)
                        exe = len([s for s in executed if s.get("symbol") == sym])
                        lines.append(f"| {sym} | {rej} | {exe} |")
                    lines.append("")
            else:
                lines.append("*No signal data recorded.*\n")

            # --- Issues & Anomalies ---
            lines.append("\n## Issues Detected During Session\n")
            # Scan activity log for errors/warnings
            activity_file = log_dir / "activity.jsonl"
            errors = []
            if activity_file.exists():
                with open(activity_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            evt = json.loads(line)
                            if evt.get("event_type") in ("scan_error", "monitor_error"):
                                errors.append(evt)
                        except json.JSONDecodeError:
                            pass

            if errors:
                lines.append(f"**{len(errors)} error events recorded:**\n")
                for err in errors[:20]:
                    ts = err.get("timestamp", "?")
                    msg = err.get("data", {}).get("error", str(err.get("data", "")))
                    lines.append(f"- `{ts}` {msg}")
                if len(errors) > 20:
                    lines.append(f"\n*... and {len(errors) - 20} more in `activity.jsonl`*")
                lines.append("")
            else:
                lines.append("No errors detected during this session.\n")

            # --- Positions Still Open at Stop ---
            lines.append("\n## Positions at Session End\n")
            if self.position_manager:
                still_open = [
                    p for p in self.position_manager.positions.values()
                    if p.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]
                ]
                if still_open:
                    lines.append(f"**{len(still_open)} positions were force-closed on stop:**\n")
                    for p in still_open:
                        lines.append(
                            f"- {p.symbol} {p.direction} | Entry: ${p.entry_price:.2f} | "
                            f"P&L: {p.pnl_percentage:.2f}% | Status: {p.status.value}"
                        )
                    lines.append("")
                else:
                    lines.append("All positions were closed before session end.\n")

            # --- AI Recommendations Section ---
            lines.append("\n## Recommendations for AI Investigation\n")
            lines.append(
                "Use the raw data files alongside this report for deeper analysis:\n"
            )
            lines.append(f"- `{log_dir / 'signals.jsonl'}` — Every signal processed (full history, not truncated)")
            lines.append(f"- `{log_dir / 'activity.jsonl'}` — Every lifecycle event (scans, fills, closes, errors)")
            lines.append(f"- `{log_dir / 'trades.jsonl'}` — Completed trade details with P&L")
            lines.append(f"- `{log_dir / 'stats.json'}` — Final session statistics")
            lines.append(f"- `{log_dir / 'config.json'}` — Configuration used\n")

            recs = []
            if s.total_trades == 0 and s.signals_generated > 0:
                recs.append(
                    "**Zero trades executed despite signals** — Check confluence thresholds, "
                    "risk sizing, and position limit gates. Review `signals.jsonl` for "
                    "the `reason` field on filtered signals."
                )
            if s.expectancy < 0 and s.total_trades >= 5:
                recs.append(
                    f"**Negative expectancy (${s.expectancy:.2f}/trade)** — Review entry zone quality, "
                    "stop placement, and whether trades are being opened against the trend."
                )
            if s.max_drawdown > 10:
                recs.append(
                    f"**High drawdown ({s.max_drawdown:.1f}%)** — Consider reducing risk_per_trade "
                    "or tightening position limits."
                )
            if s.signals_generated > 0 and s.signals_taken / s.signals_generated < 0.05:
                recs.append(
                    f"**Very low signal pass rate ({s.signals_taken}/{s.signals_generated})** — "
                    "Filters may be too aggressive. Check confluence gate, R:R minimum, and "
                    "trade type restrictions in `signals.jsonl`."
                )

            # Check for specific rejection patterns
            if all_signals:
                confluence_fails = len([s for s in all_signals if "confluence" in s.get("reason", "").lower()])
                if confluence_fails > len(all_signals) * 0.5:
                    recs.append(
                        f"**{confluence_fails}/{len(all_signals)} signals failed confluence** — "
                        "The min_confluence_score threshold may be too high for current market conditions."
                    )

            if recs:
                for i, rec in enumerate(recs, 1):
                    lines.append(f"{i}. {rec}")
            else:
                lines.append("No critical recommendations — session performed within expected parameters.")
            lines.append("")

            # --- Write report ---
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            logger.info(f"Session report saved: {report_path}")
            return report_path

        except Exception as e:
            logger.error(f"Failed to generate session report: {e}")
            return None

    def _get_uptime_seconds(self) -> int:
        """Get session uptime in seconds."""
        if not self.started_at:
            return 0

        end_time = self.stopped_at or datetime.now(timezone.utc)
        return int((end_time - self.started_at).total_seconds())

    def _get_price(self, symbol: str) -> float:
        """Synchronous price fetcher for position manager."""
        return self._price_cache.get(symbol, 0.0)

    async def _fetch_price(self, symbol: str) -> float:
        """Fetch current price from exchange adapter, falling back to OHLCV cache."""
        if not self.orchestrator or not hasattr(self.orchestrator, 'exchange_adapter'):
            raise ValueError("No exchange adapter available")

        # Primary: live ticker from exchange — run in executor so the sync ccxt
        # call doesn't block the entire async event loop.
        try:
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(
                None, self.orchestrator.exchange_adapter.fetch_ticker, symbol
            )
            price = ticker.get("last", ticker.get("close", 0.0))
            if price and price > 0:
                return float(price)
        except Exception as e:
            logger.warning(f"Live ticker failed for {symbol}, trying OHLCV cache: {e}")

        # Fallback: use latest close from the OHLCV cache populated during scan
        try:
            from backend.data.ohlcv_cache import get_ohlcv_cache
            cache = get_ohlcv_cache()
            for tf in ("1m", "5m", "15m", "1h"):
                df = cache.get(symbol, tf)
                if df is not None and not df.empty:
                    price = float(df["close"].iloc[-1])
                    if price > 0:
                        logger.info(f"Using OHLCV cache price for {symbol} ({tf}): {price:.4f}")
                        return price
        except Exception as e:
            logger.warning(f"OHLCV cache fallback failed for {symbol}: {e}")

        raise ValueError(f"Could not get price for {symbol} from ticker or OHLCV cache")

    async def _execute_exit_order(
        self, symbol: str, side: str, quantity: float, price: float
    ) -> bool:
        """
        Execute exit order (called by position manager).

        Returns True on successful fill, False on any failure. The position
        manager checks the return value to decide whether to clear the
        position state — swallowing exceptions silently here previously
        left positions in a "half-closed" state where internal bookkeeping
        thought the exit had executed but the paper executor never filled.
        """
        if not self.executor:
            logger.error(
                f"_execute_exit_order: no executor configured for {symbol} "
                f"{side} qty={quantity} price={price}"
            )
            return False

        if quantity <= 0 or price <= 0:
            logger.error(
                f"_execute_exit_order: invalid args for {symbol} "
                f"side={side} qty={quantity} price={price}"
            )
            return False

        try:
            order = self.executor.place_order(
                symbol=symbol,
                side=side,
                order_type="MARKET",
                quantity=quantity,
                price=price,
            )
            if order is None:
                logger.error(
                    f"_execute_exit_order: place_order returned None for {symbol} "
                    f"side={side} qty={quantity} price={price}"
                )
                return False

            fill = self.executor.execute_market_order(order.order_id, price)
            if not fill:
                logger.error(
                    f"_execute_exit_order: execute_market_order returned falsy fill "
                    f"for {symbol} order_id={order.order_id} price={price}"
                )
                return False

            logger.info(
                f"✅ Exit order filled: {symbol} {side} qty={quantity} @ {price:.6f} "
                f"order_id={order.order_id}"
            )
            return True
        except Exception as e:
            logger.exception(
                f"_execute_exit_order failed for {symbol} side={side} "
                f"qty={quantity} price={price}: {e}"
            )
            return False


# Global instance for API endpoints
_paper_trading_service: Optional[PaperTradingService] = None


def get_paper_trading_service() -> PaperTradingService:
    """Get or create global paper trading service instance."""
    global _paper_trading_service
    if _paper_trading_service is None:
        _paper_trading_service = PaperTradingService()
    return _paper_trading_service
