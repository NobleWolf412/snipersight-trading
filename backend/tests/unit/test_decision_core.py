"""Decision-core foundation (heart-change chunk 1). Pins the value layer + LegacyScorePolicy's
behavior-preserving mapping. See decisions/2026-06-18__decision-core-heart-change-spec.md."""
from types import SimpleNamespace

from backend.engine.decision import Decision, DecisionPolicy, Direction, LegacyScorePolicy


# ---- Direction.coerce: legacy vocabulary -> Direction ----

def test_coerce_long_synonyms():
    for v in ("LONG", "long", "bullish", "buy", Direction.LONG):
        assert Direction.coerce(v) is Direction.LONG


def test_coerce_short_synonyms():
    for v in ("SHORT", "short", "bearish", "sell", Direction.SHORT):
        assert Direction.coerce(v) is Direction.SHORT


def test_coerce_unknown_or_missing_is_flat():
    for v in (None, "", "UNKNOWN", "sideways", "????"):
        assert Direction.coerce(v) is Direction.FLAT


# ---- Decision value object ----

def test_decision_flags_and_legacy_str():
    long_d = Decision(Direction.LONG, reason="x")
    short_d = Decision(Direction.SHORT, reason="x")
    flat_d = Decision(Direction.FLAT, reason="x")
    assert long_d.is_actionable and not long_d.is_flat and long_d.legacy_str == "LONG"
    assert short_d.is_actionable and short_d.legacy_str == "SHORT"
    assert flat_d.is_flat and not flat_d.is_actionable and flat_d.legacy_str is None


def test_decision_reason_required():
    # reason is a required positional — a Decision can never be silent (CLAUDE.md §11)
    d = Decision(Direction.FLAT, reason="no_thesis")
    assert d.reason and d.source == "legacy_score"


# ---- LegacyScorePolicy: behavior-preserving wrapper of the current decision ----

def _ctx(chosen_direction):
    return SimpleNamespace(metadata={"chosen_direction": chosen_direction})


def test_legacy_policy_maps_long_short():
    pol = LegacyScorePolicy()
    assert pol.decide(_ctx("LONG")).direction is Direction.LONG
    assert pol.decide(_ctx("SHORT")).direction is Direction.SHORT


def test_legacy_policy_no_direction_is_flat():
    pol = LegacyScorePolicy()
    # the legacy 'no directional edge' path leaves chosen_direction unset -> FLAT (first-class)
    assert pol.decide(_ctx(None)).is_flat
    assert pol.decide(SimpleNamespace(metadata={})).is_flat
    assert pol.decide(SimpleNamespace()).is_flat  # no metadata at all -> FLAT, not a crash


def test_legacy_policy_is_a_decisionpolicy():
    assert isinstance(LegacyScorePolicy(), DecisionPolicy)
    assert LegacyScorePolicy().name == "legacy_score"


def test_legacy_policy_reason_always_populated():
    pol = LegacyScorePolicy()
    for ctx in (_ctx("LONG"), _ctx("SHORT"), _ctx(None)):
        assert pol.decide(ctx).reason  # never empty
