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

import os
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


# Break direction vocabulary — mirrors the scorer's regime-blind BOS arbitration
# (scorer.py:2903-2908, the P/D bug #2 fix). Direction comes from STRUCTURE, never the
# (lag-prone) regime label.
_BULL_WORDS = ("bullish", "up", "long")
_BEAR_WORDS = ("bearish", "down", "short")


def _break_dir(sb: Any) -> Optional[Direction]:
    """LONG/SHORT for a StructuralBreak's .direction, or None if unrecognized."""
    d = str(getattr(sb, "direction", "") or "").strip().lower()
    if d in _BULL_WORDS:
        return Direction.LONG
    if d in _BEAR_WORDS:
        return Direction.SHORT
    return None


def _break_type(sb: Any) -> str:
    return str(getattr(sb, "break_type", "") or "").strip().upper()


class ThesisPolicy(DecisionPolicy):
    """Structure-led, CHoCH-aware, abstain-capable direction thesis (heart-change chunk 3).

    Replaces argmax-of-confluence-score for DIRECTION. Rationale (operator-approved config
    2026-06-24, see project_v1_salvage_regime_router): the confluence score has measured no edge
    (1/26 factors predict); the one profitable cohort ever found was the BOS-continuation override
    (decisions/2026-06-13__pd-factor-inverted-in-trends-finding.md). So direction comes from
    confirmed market STRUCTURE, NOT the regime label (which lags at trend flips — "41/44 swings
    were shorts in the bottom 20% of range", §11.5).

    Rules (symmetric by construction — bull/bear mirror):
      1. CHoCH (reversal) takes priority over BOS (continuation) — a change-of-character catches the
         turn EARLIER than either a stale BOS or the lagging regime label.
      2. BOS (continuation) decides when there is no CHoCH.
      3. FLAT (first-class abstain) when: no structure · conflicting structure (both directions) ·
         ANY counter-trend entry (BOS continuation OR CHoCH reversal) that fights a STRONG trend
         (chunk 5a: "never trade against the trend" is strongest in a strong trend — a bare CHoCH
         against it is usually a trap; a genuine cycle-low reversal needs the sweep->CHoCH sequence,
         not yet built). In NORMAL/sideways trends, structure wins — the lag-prone label does not
         override confirmed structure when the trend is not decisive.
      4. Any internal failure -> FLAT with a clear reason (NOT a raise — the orchestrator's
         exception handler would miscategorize a raise; backend-integrity guard, chunk-2 note).

    This is a STEP toward the §11.5 sequence setup (sweep->CHoCH->OB->retest), not the destination:
    it is structure-LED direction, still largely a snapshot. trade_type is left None (the cascade
    decides geometry). The score is intentionally NOT read — demoting it from gate to context is
    the whole point.
    """

    name = "thesis_structure"

    def decide(self, context: Any) -> Decision:
        try:
            smc = getattr(context, "smc_snapshot", None)
            breaks = list(getattr(smc, "structural_breaks", None) or []) if smc else []
            if not breaks:
                return Decision(Direction.FLAT, reason="no_structure", source=self.name)

            # Classify confirmed breaks by (type, direction). Direction is regime-blind.
            choch = {Direction.LONG: False, Direction.SHORT: False}
            bos = {Direction.LONG: False, Direction.SHORT: False}
            for sb in breaks:
                d = _break_dir(sb)
                if d is None:
                    continue
                t = _break_type(sb)
                if t == "CHOCH":
                    choch[d] = True
                elif t == "BOS":
                    bos[d] = True

            # 1+2: CHoCH (reversal) priority, else BOS (continuation).
            if choch[Direction.LONG] and choch[Direction.SHORT]:
                return Decision(Direction.FLAT, reason="conflicting_choch", source=self.name)
            if choch[Direction.LONG]:
                struct_dir, basis = Direction.LONG, "choch"
            elif choch[Direction.SHORT]:
                struct_dir, basis = Direction.SHORT, "choch"
            elif bos[Direction.LONG] and bos[Direction.SHORT]:
                return Decision(Direction.FLAT, reason="conflicting_bos", source=self.name)
            elif bos[Direction.LONG]:
                struct_dir, basis = Direction.LONG, "bos"
            elif bos[Direction.SHORT]:
                struct_dir, basis = Direction.SHORT, "bos"
            else:
                return Decision(Direction.FLAT, reason="no_directional_structure", source=self.name)

            # 3: strong-trend discipline (chunk 5a) — in a STRONG trend, WITH-TREND ONLY. Veto ANY
            # counter-trend entry, BOS continuation OR CHoCH reversal. "Never trade against the trend"
            # is strongest here; a bare CHoCH against a strong trend is usually a trap, and a genuine
            # cycle-low reversal needs the sweep->CHoCH sequence (not yet built). In NORMAL/sideways
            # trends there is NO veto — structure wins (the lag-prone label must not override confirmed
            # structure when the trend is not decisive). Symmetric; basis-agnostic.
            meta = getattr(context, "metadata", None) or {}
            regime = meta.get("symbol_regime")
            regime_trend = str(getattr(regime, "trend", "sideways") or "sideways").strip().lower()
            if struct_dir is Direction.LONG and regime_trend == "strong_down":
                return Decision(Direction.FLAT, reason=f"counter_strong_down:{basis}", source=self.name)
            if struct_dir is Direction.SHORT and regime_trend == "strong_up":
                return Decision(Direction.FLAT, reason=f"counter_strong_up:{basis}", source=self.name)

            return Decision(
                struct_dir,
                reason=f"structure_led:{basis}:regime={regime_trend}",
                source=self.name,
                meta={"basis": basis, "regime_trend": regime_trend},
            )
        except Exception as e:  # never raise — orchestrator would miscategorize it
            return Decision(Direction.FLAT, reason=f"thesis_error:{type(e).__name__}:{e}", source=self.name)


# --- Flag (heart-change chunk 4) ---------------------------------------------
# SS_DECISION_POLICY selects the decision core AND couples the gate behavior:
#   "legacy" (default) -> LegacyScorePolicy + the score>=min_confluence_score gate is authoritative
#                         (byte-identical to pre-heart-change behavior).
#   "thesis"           -> ThesisPolicy is the go/no-go authority: FLAT rejects, actionable proceeds,
#                         and the score-gate is DEMOTED to logged context at BOTH gate sites
#                         (orchestrator + paper_trading_service). The 4 pre-scoring gates still apply.
# Env-var (not config) on purpose: no SniperContext/ScanConfig field => no contract drift. Enabling
# requires a hard backend restart (the bot's long-lived parent stays stale), which matches the
# "flip on in a deliberate, watched paper session" plan.
_THESIS = "thesis"
_LEGACY = "legacy"


def decision_mode() -> str:
    """'thesis' or 'legacy' (default). Single source of truth for the heart-change flag."""
    return _THESIS if os.getenv("SS_DECISION_POLICY", _LEGACY).strip().lower() == _THESIS else _LEGACY


def is_thesis_mode() -> bool:
    return decision_mode() == _THESIS


def active_decision_policy() -> DecisionPolicy:
    """The policy selected by SS_DECISION_POLICY. Default LegacyScorePolicy (no behavior change)."""
    return ThesisPolicy() if is_thesis_mode() else LegacyScorePolicy()


def is_fresh_entry_price() -> bool:
    """SS_FRESH_ENTRY_PRICE flag (default OFF, heart-change Form-A). When on, the plan geometry
    (OB selection, entry zone, stop, targets) is built against a FRESH tick at plan time instead of
    the stale scan-time candle close, so a retrace zone the market has already walked through stops
    qualifying. INDEPENDENT of SS_DECISION_POLICY (separate flag = clean attribution of which lever
    moved the needle). Default off -> live byte-identical. §15 design entry 2026-06-25-DESIGN-fresh-
    entry-price-geometry. Touches shared/live entry-geometry code → gated; promotion to live default
    is a separate approval."""
    return os.getenv("SS_FRESH_ENTRY_PRICE", "0").strip().lower() in ("1", "true", "yes", "on")


# --- Regime -> trade-type preference (heart-change chunk 5b) ------------------
# Replaces the cascade's score+swing bonus (_CASCADE_TYPE_BONUS, which preferred the proven-loser
# swing) for selecting WHICH trade type to take. SEEDED HYPOTHESIS from operator priors (2026-06-24),
# every cell MUST-EARN — validated forward, no real capital until a per-cell Deflated-Sharpe gate
# clears (project_v1_salvage_regime_router §11.6 guardrails). Direction-AGNOSTIC (type only).
#   - range/chop (sideways) -> SCALP (fade the edges; no sustained move to ride)
#   - trend, normal OR strong (up/down/strong_*) -> INTRADAY (with-trend continuation; strong-trend
#     reversals are already vetoed upstream by ThesisPolicy rule 3, so a trend here means with-trend)
#   - SWING is DEFERRED (operator decision 2026-06-24): rank 0 everywhere, never preferred — it earns
#     its way back only at a confirmed cycle extreme via the (unbuilt) sweep->CHoCH sequence.
_REGIME_TYPE_PREF = {
    "sideways":    {"scalp": 2, "intraday": 1, "swing": 0},
    "up":          {"intraday": 2, "scalp": 1, "swing": 0},
    "down":        {"intraday": 2, "scalp": 1, "swing": 0},
    "strong_up":   {"intraday": 2, "scalp": 1, "swing": 0},
    "strong_down": {"intraday": 2, "scalp": 1, "swing": 0},
}


def regime_type_rank(regime_trend: Any, trade_type: Any) -> int:
    """Preference rank (higher = more preferred) of a trade TYPE for a regime — the chunk-5b
    cascade winner criterion. Unknown regime -> neutral scalp/intraday; swing or unknown type -> 0
    (deferred / never preferred). Direction-agnostic."""
    rt = str(regime_trend or "sideways").strip().lower()
    tt = str(trade_type or "").strip().lower()
    return _REGIME_TYPE_PREF.get(rt, {"scalp": 1, "intraday": 1}).get(tt, 0)
