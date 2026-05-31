"""
SniperSight Replay router.

Five endpoints serving the candle-by-candle replay UX:

    POST   /api/replay/sessions
    GET    /api/replay/sessions/{id}
    POST   /api/replay/sessions/{id}/step
    POST   /api/replay/sessions/{id}/jump-to-next-signal
    DELETE /api/replay/sessions/{id}

Session state is in-memory inside the ReplayEngine singleton (initialized
at startup via configure_replay_router). Deployments running multiple
uvicorn workers must either (a) `--workers 1` or (b) sticky-route by
session_id — sessions are pinned to one worker process. See
backend/engine/replay_engine.py module docstring for the rationale.

The router does NOT mutate live scan state. The ReplayEngine constructs
its own dedicated replay-mode Orchestrator per session; the live
orchestrator singleton in api_server is untouched.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from backend.engine.replay_engine import (
    MAX_WINDOW_DAYS,
    ReplaySession,
    StepResult,
    configure_replay_engine,
    get_replay_engine,
)

router = APIRouter(tags=["Replay"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    symbol: str = Field(..., description="Trading pair, e.g. BTC/USDT")
    mode: str = Field(..., description="Scanner mode: stealth, overwatch, strike, surgical")
    window_start: datetime = Field(..., description="ISO 8601 UTC; cannot be > 30d before window_end")
    window_end: datetime = Field(..., description="ISO 8601 UTC; should be slightly before now")

    @field_validator("symbol")
    @classmethod
    def _symbol_format(cls, v: str) -> str:
        v = v.strip().upper()
        if "/" not in v:
            raise ValueError("symbol must be in 'BASE/QUOTE' format, e.g. 'BTC/USDT'")
        return v

    @field_validator("mode")
    @classmethod
    def _mode_lower(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in {"stealth", "overwatch", "strike", "surgical"}:
            raise ValueError(
                f"unknown mode '{v}'; must be one of stealth, overwatch, strike, surgical"
            )
        return v


class CreateSessionResponse(BaseModel):
    session_id: str
    symbol: str
    mode: str
    total_bars: int
    tf_step: str
    window_start: datetime
    window_end: datetime
    bar_timestamps: List[datetime] = Field(
        ...,
        description=(
            "All replayable bar opens for the playback TF. Frontend builds the"
            " scrub timeline + signal-fire marker index from this list."
        ),
    )


class SessionStatusResponse(BaseModel):
    session_id: str
    symbol: str
    mode: str
    current_index: int
    total_bars: int
    tf_step: str


class StepRequest(BaseModel):
    n: int = Field(default=1, description="Bars to advance (or retreat if negative)")


class JumpToSignalRequest(BaseModel):
    max_lookahead: int = Field(
        default=100, ge=1, le=720,
        description=(
            "Max bars to scan forward looking for a signal-fire. Capped at 720"
            " (a full 30-day stealth window). Larger values risk request"
            " timeouts; the frontend should chunk if needed."
        ),
    )


class StepResponse(BaseModel):
    session_id: str
    index: int
    bar_open_ts: datetime
    current_ts: datetime
    candles_by_tf: Dict[str, List[Dict[str, Any]]]
    confluence: Optional[Dict[str, Any]] = None
    plan: Optional[Dict[str, Any]] = None
    rejection: Optional[Dict[str, Any]] = None
    smc_snapshot: Optional[Dict[str, Any]] = None
    regime: Optional[Dict[str, Any]] = None
    signal_fired: bool


class JumpToSignalResponse(BaseModel):
    found: bool
    bars_advanced: int
    step: Optional[StepResponse] = None


class DeleteSessionResponse(BaseModel):
    ok: bool
    session_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _step_to_response(session_id: str, step: StepResult) -> StepResponse:
    return StepResponse(
        session_id=session_id,
        index=step.index,
        bar_open_ts=step.bar_open_ts,
        current_ts=step.current_ts,
        candles_by_tf=step.candles_by_tf,
        confluence=step.confluence,
        plan=step.plan,
        rejection=step.rejection,
        smc_snapshot=step.smc_snapshot,
        regime=step.regime,
        signal_fired=step.signal_fired,
    )


def _session_to_create_response(session: ReplaySession) -> CreateSessionResponse:
    return CreateSessionResponse(
        session_id=session.session_id,
        symbol=session.symbol,
        mode=session.mode_name,
        total_bars=session.total_bars,
        tf_step=session.tf_step,
        window_start=session.window_start,
        window_end=session.window_end,
        bar_timestamps=list(session.bar_timestamps),
    )


def _engine_or_500():
    """Wrap get_replay_engine to convert RuntimeError into a clear HTTP 503."""
    try:
        return get_replay_engine()
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Replay engine not initialized at startup: {e}",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/api/replay/sessions", response_model=CreateSessionResponse)
async def create_session(req: CreateSessionRequest) -> CreateSessionResponse:
    """Pre-fetch the window for symbol + BTC, build the bar timeline, and
    register an in-memory session. Returns the full bar_timestamps list so
    the frontend can render the scrub bar before any step is taken."""
    engine = _engine_or_500()
    try:
        session = engine.load_session(
            symbol=req.symbol,
            mode_name=req.mode,
            window_start=req.window_start,
            window_end=req.window_end,
        )
    except ValueError as e:
        # Window-cap exceeded, unknown mode, no data fetched, etc.
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Replay session creation failed for %s", req.symbol)
        raise HTTPException(status_code=500, detail=f"Session load failed: {e}")
    logger.info(
        "Replay session created: id={} symbol={} mode={} bars={}",
        session.session_id, session.symbol, session.mode_name, session.total_bars,
    )
    return _session_to_create_response(session)


@router.get("/api/replay/sessions/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(session_id: str) -> SessionStatusResponse:
    engine = _engine_or_500()
    session = engine.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found or expired")
    return SessionStatusResponse(
        session_id=session.session_id,
        symbol=session.symbol,
        mode=session.mode_name,
        current_index=session.step_index,
        total_bars=session.total_bars,
        tf_step=session.tf_step,
    )


@router.post(
    "/api/replay/sessions/{session_id}/step",
    response_model=StepResponse,
)
async def step_session(session_id: str, req: StepRequest) -> StepResponse:
    """Advance (or retreat with negative n) by n bars. Returns the step
    result for the new position. Within the 20-bar ring buffer back-scrub
    is instant; deeper scrub recomputes from window_start (slow)."""
    engine = _engine_or_500()
    try:
        step = engine.step(session_id, n=req.n)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found or expired")
    except IndexError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _step_to_response(session_id, step)


@router.post(
    "/api/replay/sessions/{session_id}/jump-to-next-signal",
    response_model=JumpToSignalResponse,
)
async def jump_to_next_signal(
    session_id: str, req: JumpToSignalRequest
) -> JumpToSignalResponse:
    """Step forward up to max_lookahead bars until a signal fires. If none
    found within the lookahead, returns found=false with the session
    positioned at the last scanned bar so the frontend can update its
    cursor without losing the operator's place."""
    engine = _engine_or_500()
    try:
        step, bars = engine.jump_to_next_signal(session_id, max_lookahead=req.max_lookahead)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found or expired")
    if step is None:
        return JumpToSignalResponse(found=False, bars_advanced=bars, step=None)
    return JumpToSignalResponse(
        found=True, bars_advanced=bars, step=_step_to_response(session_id, step)
    )


@router.delete(
    "/api/replay/sessions/{session_id}",
    response_model=DeleteSessionResponse,
)
async def delete_session(session_id: str) -> DeleteSessionResponse:
    engine = _engine_or_500()
    removed = engine.end_session(session_id)
    if not removed:
        # Idempotent: 404 only if the session id is meaningful but missing.
        # Frontend Esc-handler may call delete twice; treat as success.
        return DeleteSessionResponse(ok=True, session_id=session_id)
    return DeleteSessionResponse(ok=True, session_id=session_id)


# ---------------------------------------------------------------------------
# Startup configuration
# ---------------------------------------------------------------------------


def configure_replay_router(exchange_adapter) -> None:
    """Initialize the process-wide replay engine. Called by api_server
    startup with the live exchange adapter — the engine instantiates its
    own dedicated per-session orchestrators (replay_mode=True) so the
    live orchestrator state is never touched."""
    configure_replay_engine(exchange_adapter)
    logger.info(
        "Replay router configured with adapter={} (MAX_WINDOW_DAYS={})",
        type(exchange_adapter).__name__, MAX_WINDOW_DAYS,
    )
