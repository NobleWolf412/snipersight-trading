"""
Uniform response envelope for the observability HTTP layer.

Every observability route wraps its data in `Envelope[T]` so the
diagnostic loop has one structural skeleton across all endpoints.

Shape (in JSON):
  {
    "data":   <T | null>,
    "metadata": {
      "ts":         1700000000.5,
      "source":     "trace_buffer",
      "status":     "OK" | "PARTIAL" | "DEGRADED",
      "cost_class": "cheap" | "moderate"
    },
    "warnings": ["string", ...]
  }

Status codes:
  OK       — data present and trustworthy
  PARTIAL  — data partially missing (e.g. signal_id known but breakdown evicted from cache)
  DEGRADED — underlying audit detected drift / failure conditions; data
             present but caller should treat with caution.

Schema stability (CLAUDE.md §15):
  Same rule as observability.py — extra="forbid" + frozen. Adding fields
  is breaking. New consumers must pin to the current shape OR the API
  must ship a versioned route.
"""

from __future__ import annotations

from typing import Any, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field


_STRICT_CONFIG = ConfigDict(extra="forbid", frozen=True)

ResponseStatus = Literal["OK", "PARTIAL", "DEGRADED"]
CostClass = Literal["cheap", "moderate", "expensive"]


class ResponseMetadata(BaseModel):
    """Per-response metadata describing trust and cost of the payload."""

    model_config = _STRICT_CONFIG

    ts: float = Field(..., examples=[1700000000.5], description="Server timestamp in epoch seconds")
    source: str = Field(..., examples=["trace_buffer", "snapshot_cache", "live_audit"])
    status: ResponseStatus = "OK"
    cost_class: CostClass = "cheap"
    reason: Optional[str] = Field(
        None,
        description=(
            "Set when status != OK. e.g. 'breakdown_evicted', 'plans_emitted_collapsed', "
            "'wall_ms_doubled'. Human-readable, stable enum across endpoints."
        ),
    )


T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    """Uniform response envelope. Every observability route returns this."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    data: Optional[T] = None
    metadata: ResponseMetadata
    warnings: List[str] = Field(default_factory=list)


def ok_envelope(data: Any, source: str, cost_class: CostClass = "cheap") -> Envelope:
    """Construct a status=OK envelope."""
    import time
    return Envelope[Any](
        data=data,
        metadata=ResponseMetadata(
            ts=time.time(),
            source=source,
            status="OK",
            cost_class=cost_class,
        ),
        warnings=[],
    )


def partial_envelope(
    source: str, reason: str, cost_class: CostClass = "cheap", warnings: Optional[List[str]] = None
) -> Envelope:
    """Construct a status=PARTIAL envelope (id known, data unavailable)."""
    import time
    return Envelope[Any](
        data=None,
        metadata=ResponseMetadata(
            ts=time.time(),
            source=source,
            status="PARTIAL",
            cost_class=cost_class,
            reason=reason,
        ),
        warnings=warnings or [],
    )


def degraded_envelope(
    data: Any, source: str, reason: str,
    warnings: Optional[List[str]] = None,
    cost_class: CostClass = "cheap",
) -> Envelope:
    """Construct a status=DEGRADED envelope (data present but audit flagged drift)."""
    import time
    return Envelope[Any](
        data=data,
        metadata=ResponseMetadata(
            ts=time.time(),
            source=source,
            status="DEGRADED",
            cost_class=cost_class,
            reason=reason,
        ),
        warnings=warnings or [],
    )
