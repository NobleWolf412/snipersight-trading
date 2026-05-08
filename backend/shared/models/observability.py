"""
Observability response models (Pydantic v2).

Wire types for the Phase 1 observability surfaces:

  - GET /api/signals/{id}/trace
  - GET /api/signals/{id}/confluence
  - GET /api/signals/confluence/distribution
  - GET /api/scanner/universe
  - GET /api/cycles/last
  - GET /api/cycles/history

────────────────────────────────────────────────────────────────────────
Schema stability rules — IMPORTANT
────────────────────────────────────────────────────────────────────────
Every model below is `frozen=True`, `extra="forbid"`. Once shipped, these
shapes become a contract that external scripts and the SniperSight UI
will depend on.

  ADDING a field is a BREAKING CHANGE.
  REMOVING a field is a BREAKING CHANGE.
  RENAMING a field is a BREAKING CHANGE.

To extend a model, choose ONE:
  (a) Ship a versioned route (`/api/v2/signals/...`) — preferred for
      structural changes that affect multiple consumers.
  (b) Coordinate explicit consumer migration before merging — preferred
      for additive changes consumed by a known small set of clients.

Do NOT relax `extra="forbid"` to "soft-add" fields. The whole point of
strict mode is that an external script written today still works in
six months OR fails loudly with a clear validation error — never
silently drifts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


_STRICT_CONFIG = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


# ---------------------------------------------------------------------------
# Pipeline trace
# ---------------------------------------------------------------------------


class TraceStage(BaseModel):
    """One stage in the flattened ~11-stage pipeline trace."""

    model_config = _STRICT_CONFIG

    name: str = Field(..., examples=["CONFLUENCE_SCORE"])
    pass_: Optional[bool] = Field(
        None, alias="pass",
        description=(
            "True = stage cleared, False = stage rejected the signal, "
            "None = stage skipped (signal already dead from earlier stage)."
        ),
    )
    value: str = Field(..., examples=["74.2"])
    threshold: Optional[str] = Field(None, examples=["70"])
    killed_at: bool = False


class GauntletSubstage(BaseModel):
    """Raw 21-stage gauntlet substage record (drill-down inside Pipeline Tracer)."""

    model_config = _STRICT_CONFIG

    name: str
    reason: str
    pass_: Optional[bool] = Field(None, alias="pass")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SignalTrace(BaseModel):
    """Per-signal pipeline trace returned by /api/signals/{id}/trace."""

    model_config = _STRICT_CONFIG

    id: str = Field(..., examples=["BTC/USDT_42_15m_long"])
    symbol: str = Field(..., examples=["BTC/USDT"])
    side: str = Field(..., examples=["long"])
    tf: str = Field(..., examples=["15m"])
    cycle_ts: float = Field(..., examples=[1700000000.5])
    stages: List[TraceStage]
    gauntlet_substages: List[GauntletSubstage] = Field(default_factory=list)
    final_state: str = Field("unknown", examples=["EXECUTED", "REGIME_VETO"])


# ---------------------------------------------------------------------------
# Confluence breakdown wire format
# ---------------------------------------------------------------------------


class ConfluenceFactorDTO(BaseModel):
    """Factor entry in the wire format."""

    model_config = _STRICT_CONFIG

    name: str = Field(..., examples=["structure"])
    score: float = Field(..., examples=[80.0])
    weight: float = Field(..., examples=[0.4])
    weighted_score: float = Field(..., examples=[32.0])
    rationale: str = Field(..., examples=["BOS confirmed on 4h"])


class ConfluenceBreakdownDTO(BaseModel):
    """
    Wire format for /api/signals/{id}/confluence.

    Mirror of backend.shared.models.scoring.ConfluenceBreakdown but
    without strict __post_init__ validation — historical / partial
    breakdowns can still serialize.
    """

    model_config = _STRICT_CONFIG

    id: str
    symbol: str
    total_score: float
    threshold: float
    base_score: float
    factors: List[ConfluenceFactorDTO]
    synergy_bonus: float
    conflict_penalty: float
    macro_score: float
    weekly_stoch_rsi_bonus: float
    regime: str
    htf_aligned: bool
    btc_impulse_gate: bool
    direction: str = "bullish"
    profile: str = "balanced"
    htf_proximity_atr: Optional[float] = None
    htf_proximity_pct: Optional[float] = None
    nearest_htf_level_timeframe: Optional[str] = None
    nearest_htf_level_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FactorContribution(BaseModel):
    """Rolling-average contribution for a single factor name."""

    model_config = _STRICT_CONFIG

    name: str
    avg_score: float
    avg_weight: float
    avg_weighted_score: float
    sample_count: int


class DirectionDistribution(BaseModel):
    """Per-direction aggregate slice of the distribution."""

    model_config = _STRICT_CONFIG

    direction: str  # "long" | "short"
    sample_count: int
    avg_total_score: float
    avg_synergy_bonus: float
    avg_conflict_penalty: float
    factors: List[FactorContribution]


class ConfluenceDistribution(BaseModel):
    """
    Wire format for /api/signals/confluence/distribution.

    Always exposes both directions in `by_direction` regardless of the
    `direction` query param. The query param scopes the `aggregate` field;
    the breakdown stays so callers can spot bullish/bearish asymmetries
    (CLAUDE.md §10 standing fix #3).
    """

    model_config = _STRICT_CONFIG

    sample_count: int
    avg_total_score: float
    avg_synergy_bonus: float
    avg_conflict_penalty: float
    factors: List[FactorContribution]
    by_direction: List[DirectionDistribution] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Scanner universe
# ---------------------------------------------------------------------------


class UniversePair(BaseModel):
    """A pair that survived selection."""

    model_config = _STRICT_CONFIG

    symbol: str = Field(..., examples=["BTC/USDT"])
    sector: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class DroppedPair(BaseModel):
    """A pair filtered out during selection, with the reason."""

    model_config = _STRICT_CONFIG

    symbol: str
    reason: str = Field(
        ..., examples=["stable_base", "non_perp", "bucket_excluded", "limit_exhausted"]
    )


class UniverseCounts(BaseModel):
    model_config = _STRICT_CONFIG

    total_candidates: int
    qualified: int
    dropped: int


class Universe(BaseModel):
    """Wire format for /api/scanner/universe."""

    model_config = _STRICT_CONFIG

    last_refresh_ts: Optional[float]
    qualified: List[UniversePair]
    dropped: List[DroppedPair]
    counts: UniverseCounts


# ---------------------------------------------------------------------------
# Cycle heartbeat
# ---------------------------------------------------------------------------


class CycleHeartbeat(BaseModel):
    """Wire format for /api/cycles/last and entries in /api/cycles/history."""

    model_config = _STRICT_CONFIG

    ts_start: float
    ts_end: Optional[float]
    wall_ms: Optional[int]
    run_id: str
    mode: Optional[str]
    symbols_scanned: int
    plans_emitted: int
    total_rejected: int
    signals_per_stage: Dict[str, int]
    bottleneck_stage: Optional[str]
    direction_stats: Dict[str, Any] = Field(default_factory=dict)
    regime: Optional[Dict[str, Any]] = None
    next_cycle_eta_ts: Optional[float] = Field(
        None,
        description=(
            "PREDICTED next-cycle start. Bot pause, dynamic interval, or manual "
            "stop all invalidate this estimate. Treat as 'expected by'."
        ),
    )
    failed: bool
    exception_class: Optional[str] = None
