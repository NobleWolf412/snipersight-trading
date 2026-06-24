"""Decision core — the seam that replaces argmax-score-as-gate (heart-change chunk 1).

Per decisions/2026-06-18__decision-core-heart-change-spec.md. The bot's decision today is:
direction = argmax of two confluence scores; "no directional edge" is a raised exception, not a
first-class outcome. This module introduces:

  * Direction{LONG, SHORT, FLAT}  — FLAT is a FIRST-CLASS "no thesis / sit out" decision (the
    router's required NO_TRADE state), not an exception.
  * Decision{direction, reason, source, ...}  — what a policy returns.
  * DecisionPolicy  — the pluggable seam. Swap the policy, not the orchestrator.
  * LegacyScorePolicy  — reproduces CURRENT behavior (reads chosen_direction; maps no-direction to
    FLAT). This is the default, so wiring the seam (chunk 2) changes nothing live.

A future ThesisPolicy (chunk 3) derives direction from regime + structure and returns FLAT on
disagreement — that is the actual heart-change. This module is additive and behavior-neutral until
the orchestrator is wired to consume a Decision and a non-legacy policy is enabled behind a flag.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"  # first-class no-trade / no-thesis — the thing the current engine cannot express

    @classmethod
    def coerce(cls, value: Any) -> "Direction":
        """Map the legacy string vocabulary ('LONG'/'long'/'SHORT'/... or None) onto a Direction."""
        if isinstance(value, Direction):
            return value
        v = str(value or "").strip().lower()
        if v in ("long", "bullish", "buy"):
            return cls.LONG
        if v in ("short", "bearish", "sell"):
            return cls.SHORT
        return cls.FLAT


@dataclass(frozen=True)
class Decision:
    """What a DecisionPolicy returns. `reason` is ALWAYS populated (no silent decisions, CLAUDE.md §11)."""
    direction: Direction
    reason: str
    source: str = "legacy_score"          # which policy produced it (for shadow/attribution logging)
    trade_type: Optional[str] = None      # scalp/intraday/swing, or None to let the cascade decide
    meta: dict = field(default_factory=dict)

    @property
    def is_flat(self) -> bool:
        return self.direction is Direction.FLAT

    @property
    def is_actionable(self) -> bool:
        return self.direction in (Direction.LONG, Direction.SHORT)

    @property
    def legacy_str(self) -> Optional[str]:
        """The legacy 'LONG'/'SHORT' string (or None for FLAT) — for seam back-compat with code that
        still reads context.metadata['chosen_direction']."""
        return self.direction.value if self.is_actionable else None


class DecisionPolicy:
    """Given a scored SniperContext, decide LONG / SHORT / FLAT. The pluggable seam at the heart of
    the pipeline — replaces the in-scorer argmax + the score>=threshold gate (consumers read the
    Decision, not the raw score)."""

    name: str = "base"

    def decide(self, context: Any) -> Decision:  # pragma: no cover - interface
        raise NotImplementedError


class LegacyScorePolicy(DecisionPolicy):
    """Behavior-preserving default. Reproduces the CURRENT decision: confluence_service.score() has
    already set context.metadata['chosen_direction'] ('LONG'/'SHORT') via argmax + tiebreakers; the
    'no directional edge' path raised an exception (so chosen_direction is absent) -> FLAT.

    Wiring the orchestrator seam to this policy is a no-op behaviorally; it only makes FLAT a
    first-class, loggable outcome and creates the plug point for ThesisPolicy.
    """

    name = "legacy_score"

    def decide(self, context: Any) -> Decision:
        meta = getattr(context, "metadata", None) or {}
        raw = meta.get("chosen_direction")
        d = Direction.coerce(raw)
        if d is Direction.FLAT:
            return Decision(d, reason=f"legacy_no_directional_edge:{raw!r}", source=self.name)
        return Decision(d, reason=f"legacy_argmax:{d.value.lower()}", source=self.name)
