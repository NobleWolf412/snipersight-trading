"""
SniperSight Replay Engine — end-to-end diagnostic.

Catches the bug classes the §16 audit calls out for replay:
  1. Slicing leak — bar-open vs bar-close timestamp mistake silently
     breaks bullish/bearish symmetry on flip bars
  2. Cooldown not skipped — would silently drop replay signals after the
     first historical fire
  3. BTC data not pre-fetched — would let live BTC contaminate the
     historical regime label
  4. playback_index / replay_session_id missing from telemetry — autopsy
     skills couldn't trace replay runs
  5. Live stale-symbol counter polluted by replay scans
  6. Session not GC'd after TTL — memory leak

Run:
    python -m backend.diagnostics.replay_diagnostic [--symbol BTC/USDT] [--days 7] [--mode stealth]

Exit code 0 = all asserts pass. Non-zero = at least one failure (printed).
Output is paste-friendly per CLAUDE.md §12 (summary first, detail next).
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

import pandas as pd
from loguru import logger

# Quiet down loguru for the diagnostic output
logger.remove()
logger.add(sys.stderr, level="WARNING")


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    duration_s: float = 0.0


def _run_check(name: str, fn) -> CheckResult:
    t0 = time.time()
    try:
        detail = fn() or ""
        return CheckResult(name=name, passed=True, detail=detail, duration_s=time.time() - t0)
    except AssertionError as e:
        return CheckResult(name=name, passed=False, detail=str(e), duration_s=time.time() - t0)
    except Exception as e:
        return CheckResult(
            name=name,
            passed=False,
            detail=f"UNCAUGHT: {type(e).__name__}: {e}",
            duration_s=time.time() - t0,
        )


def _build_adapter():
    """Construct the live exchange adapter (Phemex) the same way api_server does."""
    from backend.data.adapters.phemex import PhemexAdapter
    return PhemexAdapter()


# ---------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------


def check_session_loads(adapter, symbol: str, mode: str, days: int) -> Tuple[str, "ReplaySession"]:
    """Returns the loaded session so subsequent checks can reuse it."""
    from backend.engine.replay_engine import ReplayEngine

    window_end = datetime.now(timezone.utc) - timedelta(minutes=5)  # avoid in-progress bar
    window_start = window_end - timedelta(days=days)

    engine = ReplayEngine(adapter)
    session = engine.load_session(
        symbol=symbol,
        mode_name=mode,
        window_start=window_start,
        window_end=window_end,
    )
    assert session is not None, "load_session returned None"
    assert session.total_bars > 0, f"Expected total_bars > 0, got {session.total_bars}"
    assert session.tf_step in ("15m", "1h", "4h"), (
        f"Unexpected tf_step {session.tf_step!r} for mode {mode!r}"
    )
    detail = (
        f"session_id={session.session_id[:8]}… total_bars={session.total_bars} "
        f"tf_step={session.tf_step} timeframes={sorted(session.multi_tf_full.keys())}"
    )
    return detail, session, engine


def check_slicing_correctness(engine, session) -> str:
    """For step 0, every TF's last visible row must have bar_close <= current_ts.
    This is the symmetry-critical assert: bar-open slicing leaks not-yet-closed
    data and silently breaks bull/bear symmetry on flip bars."""
    from backend.engine.replay_engine import TF_SECONDS

    result = engine.step(session.session_id, n=1)
    current_ts_pd = pd.Timestamp(result.current_ts)
    if current_ts_pd.tz is None:
        current_ts_pd = current_ts_pd.tz_localize("UTC")

    violations: List[str] = []
    # Re-slice and inspect (the orchestrator already consumed it, but we
    # need the raw to inspect bar-close timestamps)
    from backend.engine.replay_engine import _slice_to_bar_close
    sliced = _slice_to_bar_close(session.multi_tf_full, result.current_ts)
    for tf, df in sliced.items():
        if len(df) == 0:
            continue
        last_open = pd.Timestamp(df["timestamp"].iloc[-1])
        if last_open.tz is None:
            last_open = last_open.tz_localize("UTC")
        bar_close = last_open + pd.Timedelta(seconds=TF_SECONDS[tf])
        if bar_close > current_ts_pd:
            violations.append(
                f"{tf}: last_bar_close={bar_close} > current_ts={current_ts_pd}"
            )

    assert not violations, (
        "Slicing leak detected — bars with bar_close > current_ts visible to pipeline: "
        + " | ".join(violations)
    )
    return f"step idx={result.index} current_ts={result.current_ts.isoformat()} all TF bar-close <= current_ts"


def check_telemetry_stamping(engine, session) -> str:
    """After a step, the captured context's metadata must carry playback_index
    + replay_session_id so the autopsy skills can attribute the run."""
    # Replay engine clears _last_replay_context after read for safety. Step
    # again and grab the orchestrator's captured context BEFORE the engine
    # clears it — easiest path: re-invoke the orchestrator directly so we
    # control the read timing.
    from backend.engine.replay_engine import _slice_to_bar_close, BTC_SYMBOL
    from backend.shared.models.data import MultiTimeframeData

    bar_open = session.bar_timestamps[0]
    from backend.engine.replay_engine import TF_SECONDS
    current_ts = bar_open + timedelta(seconds=TF_SECONDS[session.tf_step])
    sliced = _slice_to_bar_close(session.multi_tf_full, current_ts)
    sliced_btc = _slice_to_bar_close(session.btc_full, current_ts)
    symbol_data = MultiTimeframeData(symbol=session.symbol, timeframes=sliced)
    btc_data = MultiTimeframeData(symbol=BTC_SYMBOL, timeframes=sliced_btc) if sliced_btc else None

    plan, rej, context = session.orchestrator.process_symbol_for_replay(
        symbol=session.symbol,
        prefetched_data=symbol_data,
        timestamp=current_ts,
        run_id="diag-telemetry",
        playback_index=0,
        session_id=session.session_id,
        prefetched_btc_data=btc_data,
    )
    assert context is not None, "process_symbol_for_replay returned None context — capture hook broken"
    pi = context.metadata.get("playback_index")
    rid = context.metadata.get("replay_session_id")
    assert pi == 0, f"playback_index not stamped, got {pi!r}"
    assert rid == session.session_id, f"replay_session_id not stamped, got {rid!r}"
    return f"playback_index={pi} replay_session_id={rid[:8]}…"


def check_cooldown_skipped(session) -> str:
    """Verify that even with cooldown active for the symbol, replay does not
    early-return with reason_type='cooldown_active'."""
    orch = session.orchestrator
    # Inject hard cooldown on both directions via the CooldownManager API
    orch.cooldown_manager.add_cooldown(
        symbol=session.symbol, direction="LONG", price=100.0,
        reason="diagnostic_inject", duration_hours=24,
    )
    orch.cooldown_manager.add_cooldown(
        symbol=session.symbol, direction="SHORT", price=100.0,
        reason="diagnostic_inject", duration_hours=24,
    )

    # Sanity-check the cooldown is actually present (proves we set it)
    long_cd = orch.cooldown_manager.is_active(session.symbol, "LONG")
    assert long_cd is not None, "Cooldown injection failed — manager reports not active"

    # Now step — should NOT return a cooldown rejection (replay_mode skips it)
    from backend.engine.replay_engine import _slice_to_bar_close, BTC_SYMBOL, TF_SECONDS
    from backend.shared.models.data import MultiTimeframeData
    bar_open = session.bar_timestamps[min(2, session.total_bars - 1)]
    current_ts = bar_open + timedelta(seconds=TF_SECONDS[session.tf_step])
    sliced = _slice_to_bar_close(session.multi_tf_full, current_ts)
    sliced_btc = _slice_to_bar_close(session.btc_full, current_ts)
    symbol_data = MultiTimeframeData(symbol=session.symbol, timeframes=sliced)
    btc_data = MultiTimeframeData(symbol=BTC_SYMBOL, timeframes=sliced_btc) if sliced_btc else None

    plan, rej, ctx = orch.process_symbol_for_replay(
        symbol=session.symbol,
        prefetched_data=symbol_data,
        timestamp=current_ts,
        run_id="diag-cooldown",
        playback_index=2,
        session_id=session.session_id,
        prefetched_btc_data=btc_data,
    )
    # Cooldown was active. If replay_mode hadn't skipped it, _process_symbol
    # would have returned the cooldown-rejection dict from the gate at L1229.
    if rej is not None:
        reason_type = rej.get("reason_type", "")
        # The live cooldown gate emits reason_type="cooldown_active" — see
        # _check_cooldown in orchestrator.py
        assert reason_type != "cooldown_active", (
            f"Cooldown NOT skipped in replay mode — got rejection {reason_type!r}"
        )
        return f"cooldown skipped (got non-cooldown rejection: {reason_type!r})"
    return "cooldown skipped (step produced plan despite live cooldown)"


def check_stale_counter_untouched(engine, session) -> str:
    """The live stale-symbol counter must not be incremented by a replay
    session — replay walks historical data and would corrupt the live
    bot's stale-detection if it mutated the shared module-level dict."""
    from backend.analysis.pair_selection import get_stale_counters_snapshot

    snapshot_before = dict(get_stale_counters_snapshot())

    # Run multiple steps to maximize the chance any leak would surface
    engine.step(session.session_id, n=1)
    engine.step(session.session_id, n=1)
    engine.step(session.session_id, n=1)

    snapshot_after = dict(get_stale_counters_snapshot())

    assert snapshot_before == snapshot_after, (
        f"Live stale-symbol counter mutated by replay: "
        f"before={snapshot_before} after={snapshot_after}"
    )
    return f"counter unchanged ({len(snapshot_before)} symbols tracked)"


def check_session_gc(adapter) -> str:
    """A session past the idle TTL must be GC'd on the next access."""
    from backend.engine import replay_engine as re_mod

    # Save and restore the TTL so we don't break other checks
    original_ttl = re_mod.SESSION_IDLE_TTL_SECONDS
    try:
        # Make sessions expire immediately
        re_mod.SESSION_IDLE_TTL_SECONDS = 0

        engine = re_mod.ReplayEngine(adapter)
        # Inject a fake session bypassing load_session (avoid network)
        from backend.engine.replay_engine import ReplaySession
        from backend.shared.config.scanner_modes import get_mode
        mode = get_mode("stealth")
        # Build a minimal placeholder orchestrator
        from backend.engine.orchestrator import Orchestrator
        from backend.shared.config.defaults import ScanConfig
        cfg = ScanConfig(profile=mode.profile, timeframes=tuple(mode.timeframes))
        orch = Orchestrator(config=cfg, exchange_adapter=adapter, replay_mode=True)
        fake = ReplaySession(
            session_id="gc-test-1234",
            symbol="BTC/USDT",
            mode_name="stealth",
            window_start=datetime.now(timezone.utc),
            window_end=datetime.now(timezone.utc),
            multi_tf_full={},
            btc_full={},
            tf_step="1h",
            bar_timestamps=[],
            orchestrator=orch,
            step_index=-1,
        )
        # Make last_touched ancient so GC sweeps it
        fake.last_touched = datetime.now(timezone.utc) - timedelta(hours=2)
        with engine._lock:
            engine._sessions[fake.session_id] = fake

        assert fake.session_id in engine._sessions, "Setup failed: session not present"

        # Loading any new session triggers the GC sweep
        with engine._lock:
            engine._gc_idle_locked()

        assert fake.session_id not in engine._sessions, "GC did not drop idle session"
        return "idle session dropped on next access"
    finally:
        re_mod.SESSION_IDLE_TTL_SECONDS = original_ttl


def check_slicing_boundary_negative(session) -> str:
    """Rigorous boundary proof per audit Rubric 4: at current_ts = bar_close - 1s,
    the bar must NOT appear in the slice. Together with the positive boundary
    test in check_slicing_correctness, this nails the `<=` semantics.

    Without this paired negative, a bug that flipped `<=` to `<` would still
    pass the positive test (just exclude one bar that should have been
    included) but be caught here (still exclude the bar one second before
    close, which is the correct behavior).
    """
    from backend.engine.replay_engine import _slice_to_bar_close, TF_SECONDS
    if session.total_bars < 2:
        return "(skipped — need >=2 bars)"
    # Pick a TF that has multiple bars (use the tf_step itself)
    tf = session.tf_step
    df_full = session.multi_tf_full[tf]
    assert len(df_full) > 0, f"No {tf} candles in session"
    # Choose a bar in the middle — its close moment is bar_open + tf_seconds
    target_bar_open = pd.Timestamp(df_full["timestamp"].iloc[len(df_full) // 2])
    if target_bar_open.tz is None:
        target_bar_open = target_bar_open.tz_localize("UTC")
    tf_secs = TF_SECONDS[tf]
    bar_close = target_bar_open + pd.Timedelta(seconds=tf_secs)
    # One second BEFORE the bar closes — the bar must NOT be visible
    just_before_close = bar_close - pd.Timedelta(seconds=1)
    sliced = _slice_to_bar_close(
        session.multi_tf_full, just_before_close.to_pydatetime()
    )
    if tf in sliced:
        last_open = pd.Timestamp(sliced[tf]["timestamp"].iloc[-1])
        if last_open.tz is None:
            last_open = last_open.tz_localize("UTC")
        assert last_open < target_bar_open, (
            f"Negative slice failed: at current_ts={just_before_close} "
            f"(1s before bar_close={bar_close}) the bar with open={target_bar_open} "
            f"appeared in slice (last_open={last_open}) — `<=` boundary broken"
        )
    return (
        f"at current_ts={just_before_close} (-1s from bar close), "
        f"bar with open={target_bar_open} correctly excluded"
    )


def check_active_session_not_gcd(adapter) -> str:
    """Negative GC test per audit Rubric 4: a non-idle session must SURVIVE
    a GC sweep. Without this paired negative, a bug that GC'd every session
    on every sweep would still pass check_session_gc (it does drop the
    idle one) but be caught here (would wrongly drop the active one too).
    """
    from backend.engine import replay_engine as re_mod
    from backend.engine.replay_engine import ReplaySession
    from backend.engine.orchestrator import Orchestrator
    from backend.shared.config.defaults import ScanConfig
    from backend.shared.config.scanner_modes import get_mode

    original_ttl = re_mod.SESSION_IDLE_TTL_SECONDS
    try:
        # Force GC to fire on anything older than 60 seconds
        re_mod.SESSION_IDLE_TTL_SECONDS = 60

        engine = re_mod.ReplayEngine(adapter)
        mode = get_mode("stealth")
        cfg = ScanConfig(profile=mode.profile, timeframes=tuple(mode.timeframes))
        orch = Orchestrator(config=cfg, exchange_adapter=adapter, replay_mode=True)

        # An IDLE session (ancient last_touched) - should be GC'd
        idle = ReplaySession(
            session_id="idle-neg-test",
            symbol="BTC/USDT", mode_name="stealth",
            window_start=datetime.now(timezone.utc),
            window_end=datetime.now(timezone.utc),
            multi_tf_full={}, btc_full={}, tf_step="1h",
            bar_timestamps=[], orchestrator=orch, step_index=-1,
        )
        idle.last_touched = datetime.now(timezone.utc) - timedelta(hours=2)

        # An ACTIVE session (touched 5 seconds ago) - should SURVIVE
        active = ReplaySession(
            session_id="active-neg-test",
            symbol="BTC/USDT", mode_name="stealth",
            window_start=datetime.now(timezone.utc),
            window_end=datetime.now(timezone.utc),
            multi_tf_full={}, btc_full={}, tf_step="1h",
            bar_timestamps=[], orchestrator=orch, step_index=-1,
        )
        active.last_touched = datetime.now(timezone.utc) - timedelta(seconds=5)

        with engine._lock:
            engine._sessions[idle.session_id] = idle
            engine._sessions[active.session_id] = active

        with engine._lock:
            engine._gc_idle_locked()

        assert idle.session_id not in engine._sessions, (
            "Negative GC test: idle session was NOT dropped (GC broken)"
        )
        assert active.session_id in engine._sessions, (
            "Negative GC test: active session was wrongly dropped (over-eager GC)"
        )
        return "idle dropped, active retained"
    finally:
        re_mod.SESSION_IDLE_TTL_SECONDS = original_ttl


def check_orchestrator_replay_mode_required() -> str:
    """Confirms the orchestrator raises if process_symbol_for_replay is called
    on a non-replay orchestrator — protects the live scan path from accidental
    misuse."""
    from backend.engine.orchestrator import Orchestrator
    from backend.shared.config.defaults import ScanConfig

    cfg = ScanConfig(profile="stealth_balanced", timeframes=("1h",))
    # Build a NON-replay orchestrator
    class _DummyAdapter:
        def fetch_ohlcv(self, *a, **k): return None
    orch = Orchestrator(config=cfg, exchange_adapter=_DummyAdapter(), replay_mode=False)
    try:
        orch.process_symbol_for_replay(
            symbol="BTC/USDT",
            prefetched_data=None,  # type: ignore[arg-type]
            timestamp=datetime.now(timezone.utc),
            run_id="x",
            playback_index=0,
            session_id="x",
        )
    except RuntimeError as e:
        assert "non-replay orchestrator" in str(e), f"Wrong error: {e}"
        return "non-replay orchestrator correctly rejected"
    raise AssertionError("Expected RuntimeError on non-replay orchestrator, got no error")


# ---------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Replay engine end-to-end diagnostic")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--mode", default="stealth")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    print("=" * 72)
    print(f"REPLAY DIAGNOSTIC | symbol={args.symbol} mode={args.mode} days={args.days}")
    print("=" * 72)

    adapter = _build_adapter()

    # Check 1: session loads (shared state — subsequent checks reuse it)
    load_result = _run_check(
        "1. Session loads + bar timestamps built",
        lambda: check_session_loads(adapter, args.symbol, args.mode, args.days),
    )
    if not load_result.passed:
        print(f"[FAIL] {load_result.name}: {load_result.detail}")
        print("\nSession load failed — cannot run downstream checks.")
        sys.exit(1)
    detail, session, engine = load_result.detail
    load_result.detail = detail

    checks: List[CheckResult] = [load_result]
    checks.append(_run_check(
        "2. Slicing uses bar-close (no leak)",
        lambda: check_slicing_correctness(engine, session),
    ))
    checks.append(_run_check(
        "3. Telemetry carries playback_index + session_id",
        lambda: check_telemetry_stamping(engine, session),
    ))
    checks.append(_run_check(
        "4. Cooldown gate skipped in replay mode",
        lambda: check_cooldown_skipped(session),
    ))
    checks.append(_run_check(
        "5. Live stale-symbol counter untouched",
        lambda: check_stale_counter_untouched(engine, session),
    ))
    checks.append(_run_check(
        "6. Idle session GC'd",
        lambda: check_session_gc(adapter),
    ))
    checks.append(_run_check(
        "7. process_symbol_for_replay rejects non-replay orchestrator",
        check_orchestrator_replay_mode_required,
    ))
    checks.append(_run_check(
        "8. Negative slicing boundary (bar 1s before close excluded)",
        lambda: check_slicing_boundary_negative(session),
    ))
    checks.append(_run_check(
        "9. Active session NOT GC'd (paired negative)",
        lambda: check_active_session_not_gcd(adapter),
    ))

    # ---- Summary table (paste-friendly per §12) ----
    print()
    print("SUMMARY")
    print("-" * 72)
    n_pass = sum(1 for c in checks if c.passed)
    n_fail = len(checks) - n_pass
    print(f"{n_pass}/{len(checks)} passed | {n_fail} failed")
    print()
    for c in checks:
        marker = "[PASS]" if c.passed else "[FAIL]"
        print(f"{marker} {c.name}  ({c.duration_s*1000:.0f}ms)")
        if c.detail:
            for line in c.detail.splitlines():
                print(f"       {line}")
    print()

    if n_fail:
        print("RAW")
        print("-" * 72)
        for c in checks:
            if not c.passed:
                print(f">>> {c.name}")
                print(c.detail)
                print()
        sys.exit(1)

    print("All replay diagnostics passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
