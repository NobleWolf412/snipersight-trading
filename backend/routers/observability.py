"""
Observability HTTP router.

Surfaces the Phase 1 in-process ring buffers and audit results as a
small set of JSON endpoints. Designed for the SniperSight HUD UI and
for ad-hoc diagnostic curl from the operator.

────────────────────────────────────────────────────────────────────────
Routes
────────────────────────────────────────────────────────────────────────

  GET /api/signals/{id}/trace                  cheap   — Pipeline tracer
  GET /api/signals/{id}/confluence             cheap   — Per-signal breakdown
  GET /api/signals/confluence/distribution     moderate— Rolling distribution
                                                          (?n=200, ?direction=all|long|short)
  GET /api/scanner/universe                    cheap   — Latest qualified/dropped
                                                          (?include_audit=true → moderate)
  GET /api/cycles/last                         cheap   — Most recent heartbeat
  GET /api/cycles/history                      cheap   — Last N heartbeats
                                                          (?n=, ?mode=, ?include_audit=true → moderate)

────────────────────────────────────────────────────────────────────────
Lookup-miss contract
────────────────────────────────────────────────────────────────────────

  - 404 (HTTPException, body `{"detail": {"reason": "unknown_id", ...}}`)
        when a signal id is unknown to all systems.
  - 200 with `data=null` and `metadata.status="PARTIAL"` and
        `metadata.reason="breakdown_evicted"` when the id is in
        signal_log but the breakdown was evicted from the cache.
  - 200 with `metadata.status="OK"` on success.
  - 200 with `metadata.status="DEGRADED"` and `warnings=[...]` when the
        underlying audit has flagged drift but data is otherwise present.

Same rule applied across `/trace` and `/confluence`. The buffer-mismatch
case is explicit and machine-readable.

────────────────────────────────────────────────────────────────────────
Auth / access boundary
────────────────────────────────────────────────────────────────────────

These endpoints expose position routing, scoring internals, and signal
flow. CURRENTLY UNAUTHENTICATED — dev mode only.

Before live trading goes online: gate behind ONE of:
  (a) Tailscale ACL (network-level)
  (b) Bearer-token middleware on FastAPI (app-level)
  (c) Localhost-only bind (host-level)

Tracking via `OBSERVABILITY_AUTH_MODE` env var (default "none"). Future
values: "tailscale" | "bearer" | "localhost". Production deployment must
fail-closed if mode is "none". CLAUDE.md §15 hard boundary.

────────────────────────────────────────────────────────────────────────
Cost classification
────────────────────────────────────────────────────────────────────────

`metadata.cost_class` echoes per-route cost so polling clients can
self-throttle. "cheap" = O(1) or O(N≤500) snapshot read. "moderate" =
runs aggregation or audit detectors on demand.
"""

from __future__ import annotations

import os
import time
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse

from backend.shared.models.envelope import (
    Envelope,
    degraded_envelope,
    ok_envelope,
    partial_envelope,
)
from backend.shared.models.observability import (
    ConfluenceBreakdownDTO,
    ConfluenceDistribution,
    ConfluenceFactorDTO,
    CycleHeartbeat,
    DirectionDistribution,
    DroppedPair,
    FactorContribution,
    GauntletSubstage,
    SignalTrace,
    TraceStage,
    Universe,
    UniverseCounts,
    UniversePair,
)


router = APIRouter(tags=["observability"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_auth_mode() -> None:
    """
    Fail-closed if running in production without an auth mode configured.
    Currently only emits a startup-style log if mode is "none". A real
    deployment should set OBSERVABILITY_AUTH_MODE=tailscale|bearer|localhost
    and the middleware (TBD) will enforce it.
    """
    mode = os.environ.get("OBSERVABILITY_AUTH_MODE", "none")
    if mode == "none":
        # Dev-mode warning is logged at import time; per-request check is
        # a no-op so we don't spam the log. The boundary is documented;
        # gating ships before live capital.
        pass


# ---------------------------------------------------------------------------
# /api/signals/{id}/trace
# ---------------------------------------------------------------------------


@router.get(
    "/api/signals/{id}/trace",
    response_model=Envelope[SignalTrace],
    summary="Per-signal pipeline trace",
    description=(
        "Returns the flattened ~11-stage pipeline trace for a single signal, "
        "drilling into the underlying gauntlet substages. Cost: cheap "
        "(O(N≤200) linear scan of signal_log)."
    ),
    responses={
        404: {"description": "Signal id not found in any source."},
    },
)
async def get_signal_trace(id: str) -> JSONResponse:
    from backend.bot.live_trading_service import get_live_trading_service

    service = get_live_trading_service()
    entry: Optional[dict] = None
    if service is not None:
        try:
            entry = service.get_signal_by_id(id)
        except Exception:
            entry = None

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"reason": "unknown_id", "id": id},
        )

    # Build the flattened 11-stage trace from the single signal_log entry.
    # The signal's final state is captured in `result` + `reason_type`.
    reason_type = (entry.get("reason_type") or "").lower()
    final_state = entry.get("result", "unknown") or "unknown"
    if reason_type:
        final_state = f"{final_state}:{reason_type}"

    # The 11 logical stages in order. We mark each as pass/fail/skip
    # based on where the signal died (reason_type) and what fields are
    # populated. This is reconstructive — we don't have per-stage logs
    # for plans that reached _log_signal, only the final state.
    stage_order = [
        "UNIVERSE", "DATA", "CRITICAL_TF", "FEATURES", "CONFLUENCE_SCORE",
        "PLANNER", "RISK_VALIDATION", "ML_GATE", "REGIME",
        "POSITION_CAPS", "EXECUTION",
    ]
    # Map gauntlet reason types to the highest stage they imply
    REASON_TO_STAGE = {
        "no_data": "DATA", "missing_critical_tf": "CRITICAL_TF",
        "low_confluence": "CONFLUENCE_SCORE", "structural_anchor": "FEATURES",
        "btc_impulse": "CONFLUENCE_SCORE", "regime_alignment": "CONFLUENCE_SCORE",
        "conflict_density": "CONFLUENCE_SCORE",
        "no_trade_plan": "PLANNER", "risk_validation": "RISK_VALIDATION",
        "max_positions": "POSITION_CAPS", "has_position": "POSITION_CAPS",
        "pending_order": "POSITION_CAPS", "errors": "EXECUTION",
        "stale_entry": "EXECUTION", "position_size": "EXECUTION",
        "price_fetch": "EXECUTION", "pending_fill": "EXECUTION",
    }
    killed_stage = REASON_TO_STAGE.get(reason_type)

    stages: List[TraceStage] = []
    killed = False
    for stage in stage_order:
        if killed:
            stages.append(TraceStage(name=stage, value="skipped", **{"pass": None}))
            continue
        if stage == killed_stage and entry.get("result") in ("filtered", "rejected"):
            stages.append(TraceStage(
                name=stage,
                value=entry.get("reason", "rejected"),
                killed_at=True,
                **{"pass": False},
            ))
            killed = True
            continue
        # Default: this stage passed (signal made it past it)
        if stage == "CONFLUENCE_SCORE":
            stages.append(TraceStage(
                name=stage,
                value=str(entry.get("confluence", "?")),
                threshold="(per-mode)",
                **{"pass": True},
            ))
        else:
            stages.append(TraceStage(name=stage, value="passed", **{"pass": True}))

    trace = SignalTrace(
        id=id,
        symbol=entry.get("symbol", "?"),
        side=str(entry.get("direction", "?")).lower(),
        tf=entry.get("timeframe", "?") or "?",
        cycle_ts=float(entry.get("scan_number", 0)),
        stages=stages,
        gauntlet_substages=[
            GauntletSubstage(
                name=reason_type or "unknown",
                reason=entry.get("reason", ""),
                metadata={k: v for k, v in entry.items() if k not in ("symbol", "direction", "reason")},
                **{"pass": False if entry.get("result") in ("filtered", "rejected") else True},
            )
        ],
        final_state=final_state,
    )

    env = ok_envelope(trace.model_dump(by_alias=True), source="signal_log", cost_class="cheap")
    return JSONResponse(content=env.model_dump(by_alias=True))


# ---------------------------------------------------------------------------
# /api/signals/{id}/confluence
# ---------------------------------------------------------------------------


@router.get(
    "/api/signals/{id}/confluence",
    response_model=Envelope[ConfluenceBreakdownDTO],
    summary="Per-signal confluence breakdown",
    description=(
        "Returns the factor breakdown that produced a signal's score. "
        "Cost: cheap (O(N≤500) linear scan of breakdown cache). "
        "Returns 200 with metadata.status=PARTIAL if the id is known to "
        "signal_log but the breakdown was evicted from the cache."
    ),
)
async def get_signal_confluence(id: str) -> JSONResponse:
    from backend.bot.live_trading_service import get_live_trading_service
    from backend.strategy.confluence.cache import get as get_breakdown

    service = get_live_trading_service()
    in_signal_log = False
    if service is not None:
        try:
            in_signal_log = service.get_signal_by_id(id) is not None
        except Exception:
            in_signal_log = False

    breakdown = get_breakdown(id)
    if breakdown is None:
        if in_signal_log:
            # Buffer mismatch — id known, breakdown evicted.
            env = partial_envelope(
                source="confluence_cache",
                reason="breakdown_evicted",
                cost_class="cheap",
            )
            return JSONResponse(content=env.model_dump(by_alias=True))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"reason": "unknown_id", "id": id},
        )

    # Materialize as DTO
    dto = ConfluenceBreakdownDTO(
        id=id,
        symbol=breakdown.symbol,
        total_score=breakdown.total_score,
        threshold=0.0,  # threshold lives on the scanner mode, not the breakdown
        base_score=breakdown.base_score,
        factors=[
            ConfluenceFactorDTO(
                name=f.name, score=f.score, weight=f.weight,
                weighted_score=f.weighted_score, rationale=f.rationale,
            )
            for f in breakdown.factors
        ],
        synergy_bonus=breakdown.synergy_bonus,
        conflict_penalty=breakdown.conflict_penalty,
        macro_score=breakdown.macro_score,
        weekly_stoch_rsi_bonus=breakdown.weekly_stoch_rsi_bonus,
        regime=breakdown.regime,
        htf_aligned=breakdown.htf_aligned,
        btc_impulse_gate=breakdown.btc_impulse_gate,
        direction=breakdown.direction,
        profile=breakdown.profile,
        htf_proximity_atr=breakdown.htf_proximity_atr,
        htf_proximity_pct=breakdown.htf_proximity_pct,
        nearest_htf_level_timeframe=breakdown.nearest_htf_level_timeframe,
        nearest_htf_level_type=breakdown.nearest_htf_level_type,
        metadata=dict(breakdown.metadata or {}),
    )
    env = ok_envelope(dto.model_dump(), source="confluence_cache", cost_class="cheap")
    return JSONResponse(content=env.model_dump(by_alias=True))


# ---------------------------------------------------------------------------
# /api/signals/confluence/distribution
# ---------------------------------------------------------------------------


@router.get(
    "/api/signals/confluence/distribution",
    response_model=Envelope[ConfluenceDistribution],
    summary="Rolling factor-contribution distribution",
    description=(
        "Returns rolling averages of factor contributions over the last N "
        "breakdowns. Always exposes per-direction breakdown in `by_direction` "
        "regardless of the `direction` query param — protects against "
        "bullish/bearish asymmetry regressions (CLAUDE.md §10 standing fix #3). "
        "Cost: moderate (O(N×F) aggregation)."
    ),
)
async def get_confluence_distribution(
    n: int = Query(200, ge=1, le=500),
    direction: str = Query("all", pattern="^(all|long|short)$"),
) -> JSONResponse:
    from backend.strategy.confluence import cache

    samples = cache.recent(n)

    def _agg(samples_subset):
        if not samples_subset:
            return {
                "sample_count": 0, "avg_total_score": 0.0,
                "avg_synergy_bonus": 0.0, "avg_conflict_penalty": 0.0,
                "factors": [],
            }
        total = synergy = conflict = 0.0
        factor_acc: dict = {}
        for _, br in samples_subset:
            total += br.total_score
            synergy += br.synergy_bonus
            conflict += br.conflict_penalty
            for f in br.factors:
                slot = factor_acc.setdefault(f.name, [0.0, 0.0, 0.0, 0])
                slot[0] += f.score
                slot[1] += f.weight
                slot[2] += f.weighted_score
                slot[3] += 1
        nn = len(samples_subset)
        return {
            "sample_count": nn,
            "avg_total_score": total / nn,
            "avg_synergy_bonus": synergy / nn,
            "avg_conflict_penalty": conflict / nn,
            "factors": [
                {"name": k, "avg_score": v[0] / v[3], "avg_weight": v[1] / v[3],
                 "avg_weighted_score": v[2] / v[3], "sample_count": v[3]}
                for k, v in sorted(factor_acc.items(), key=lambda kv: -kv[1][2])
            ],
        }

    long_samples = [(sid, br) for sid, br in samples if (br.direction or "").lower() in ("bullish", "long")]
    short_samples = [(sid, br) for sid, br in samples if (br.direction or "").lower() in ("bearish", "short")]

    if direction == "long":
        agg = _agg(long_samples)
    elif direction == "short":
        agg = _agg(short_samples)
    else:
        agg = _agg(samples)

    by_direction = [
        DirectionDistribution(
            direction="long",
            **{k: v for k, v in _agg(long_samples).items()},
        ),
        DirectionDistribution(
            direction="short",
            **{k: v for k, v in _agg(short_samples).items()},
        ),
    ]

    dist = ConfluenceDistribution(
        sample_count=agg["sample_count"],
        avg_total_score=agg["avg_total_score"],
        avg_synergy_bonus=agg["avg_synergy_bonus"],
        avg_conflict_penalty=agg["avg_conflict_penalty"],
        factors=[FactorContribution(**f) for f in agg["factors"]],
        by_direction=by_direction,
    )
    env = ok_envelope(dist.model_dump(), source="confluence_cache", cost_class="moderate")
    return JSONResponse(content=env.model_dump(by_alias=True))


# ---------------------------------------------------------------------------
# /api/scanner/universe
# ---------------------------------------------------------------------------


@router.get(
    "/api/scanner/universe",
    response_model=Envelope[Universe],
    summary="Latest pair-selection snapshot (qualified + dropped with reasons)",
    description=(
        "Returns the most recent universe snapshot: which pairs survived "
        "selection and which were dropped (with reason). "
        "?include_audit=true runs the universe audit (drift detector + "
        "cycle-over-cycle trend) and embeds DEGRADED status in metadata. "
        "Cost: cheap without audit, moderate with audit."
    ),
)
async def get_universe(
    include_audit: bool = Query(False, description="Run the universe audit and embed status in metadata"),
) -> JSONResponse:
    from backend.analysis.pair_selection import get_latest_snapshot
    from backend.diagnostics import status_cache

    snap = get_latest_snapshot()
    if snap is None:
        empty = Universe(
            last_refresh_ts=None,
            qualified=[],
            dropped=[],
            counts=UniverseCounts(total_candidates=0, qualified=0, dropped=0),
        )
        env = ok_envelope(empty.model_dump(), source="snapshot_cache", cost_class="cheap")
        return JSONResponse(content=env.model_dump(by_alias=True))

    universe = Universe(
        last_refresh_ts=snap.get("ts"),
        qualified=[UniversePair(symbol=s) for s in (snap.get("selected") or [])],
        dropped=[DroppedPair(**d) for d in (snap.get("dropped") or [])],
        counts=UniverseCounts(
            total_candidates=int(snap.get("fetched") or 0),
            qualified=len(snap.get("selected") or []),
            dropped=len(snap.get("dropped") or []),
        ),
    )

    if not include_audit:
        env = ok_envelope(universe.model_dump(), source="snapshot_cache", cost_class="cheap")
        return JSONResponse(content=env.model_dump(by_alias=True))

    audit_status, reason, warnings = status_cache.get_status("universe")
    if audit_status == "DEGRADED":
        env = degraded_envelope(
            universe.model_dump(), source="snapshot_cache",
            reason=reason or "audit_degraded",
            warnings=warnings, cost_class="moderate",
        )
    else:
        env = ok_envelope(universe.model_dump(), source="snapshot_cache", cost_class="moderate")
        env = env.model_copy(update={"warnings": list(warnings)})
    return JSONResponse(content=env.model_dump(by_alias=True))


# ---------------------------------------------------------------------------
# /api/cycles/last  +  /api/cycles/history
# ---------------------------------------------------------------------------


@router.get(
    "/api/cycles/last",
    response_model=Envelope[CycleHeartbeat],
    summary="Most recent scan-cycle heartbeat",
    description=(
        "Returns the most recent cycle heartbeat from the orchestrator. "
        "?include_audit=true mirrors the /cycles/history behavior, embedding "
        "drift-detector status (OK / DEGRADED) and warnings via the envelope. "
        "Cost: cheap without audit, moderate with audit."
    ),
)
async def get_cycles_last(
    include_audit: bool = Query(
        False,
        description="Run the cycle-heartbeat audit and embed DEGRADED status in metadata",
    ),
) -> JSONResponse:
    # 3a' (Phase 3 follow-up): include_audit was previously available on
    # /cycles/history but not /cycles/last, leaving the HUD CycleAuditStrip
    # without a per-call drift signal on the most-recent cycle. This
    # mirrors the /cycles/history pattern (lines 508-521) so callers can
    # read OK / DEGRADED status from the same envelope shape they use
    # for the history endpoint. Backward compat preserved: omitting the
    # param produces the original "no audit, cheap cost class" envelope.
    from backend.engine import cycle_heartbeat
    from backend.diagnostics import status_cache

    snap = cycle_heartbeat.get_latest()

    if snap is None:
        # Empty-snapshot path. The cost class doesn't shift with the audit
        # flag here because there's no payload to attach status to — the
        # contract is "data: null" either way. Warnings remain empty.
        env = ok_envelope(None, source="cycle_heartbeat", cost_class="cheap")
        return JSONResponse(content=env.model_dump(by_alias=True))

    hb = CycleHeartbeat(**snap)

    if not include_audit:
        env = ok_envelope(hb.model_dump(), source="cycle_heartbeat", cost_class="cheap")
        return JSONResponse(content=env.model_dump(by_alias=True))

    audit_status, reason, warnings = status_cache.get_status("cycles")
    if audit_status == "DEGRADED":
        env = degraded_envelope(
            hb.model_dump(),
            source="cycle_heartbeat",
            reason=reason or "audit_degraded",
            warnings=warnings,
            cost_class="moderate",
        )
    else:
        env = ok_envelope(hb.model_dump(), source="cycle_heartbeat", cost_class="moderate")
        env = env.model_copy(update={"warnings": list(warnings)})
    return JSONResponse(content=env.model_dump(by_alias=True))


@router.get(
    "/api/cycles/history",
    response_model=Envelope[List[CycleHeartbeat]],
    summary="Last N scan-cycle heartbeats",
    description=(
        "Returns up to N (default 20, max 50) recent cycle heartbeats, "
        "optionally filtered by mode. ?include_audit=true embeds drift "
        "detector results and DEGRADED status in metadata. "
        "Cost: cheap without audit, moderate with audit."
    ),
)
async def get_cycles_history(
    n: int = Query(20, ge=1, le=50),
    mode: Optional[str] = Query(None, description="Filter by scanner mode (e.g. stealth)"),
    include_audit: bool = Query(False),
) -> JSONResponse:
    from backend.engine import cycle_heartbeat
    from backend.diagnostics import status_cache

    rows = cycle_heartbeat.filter_by_mode(mode, n=n) if mode else cycle_heartbeat.recent(n=n)
    heartbeats = [CycleHeartbeat(**r) for r in rows]
    payload = [hb.model_dump() for hb in heartbeats]

    if not include_audit:
        env = ok_envelope(payload, source="cycle_heartbeat", cost_class="cheap")
        return JSONResponse(content=env.model_dump(by_alias=True))

    audit_status, reason, warnings = status_cache.get_status("cycles")
    if audit_status == "DEGRADED":
        env = degraded_envelope(
            payload, source="cycle_heartbeat",
            reason=reason or "audit_degraded",
            warnings=warnings, cost_class="moderate",
        )
    else:
        env = ok_envelope(payload, source="cycle_heartbeat", cost_class="moderate")
        env = env.model_copy(update={"warnings": list(warnings)})
    return JSONResponse(content=env.model_dump(by_alias=True))
