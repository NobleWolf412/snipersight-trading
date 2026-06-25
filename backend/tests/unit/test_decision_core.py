"""Decision-core foundation (heart-change chunk 1). Pins the value layer + LegacyScorePolicy's
behavior-preserving mapping. See decisions/2026-06-18__decision-core-heart-change-spec.md."""
from types import SimpleNamespace

from backend.engine.decision import (
    Decision,
    DecisionPolicy,
    Direction,
    LegacyScorePolicy,
    ThesisPolicy,
)


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


# ---- ThesisPolicy: structure-led, CHoCH-aware, abstain-capable (chunk 3) ----

def _brk(break_type, direction):
    return SimpleNamespace(break_type=break_type, direction=direction)


def _tctx(breaks, trend="sideways"):
    smc = SimpleNamespace(structural_breaks=breaks)
    regime = SimpleNamespace(trend=trend)
    return SimpleNamespace(smc_snapshot=smc, metadata={"symbol_regime": regime})


def test_thesis_bos_direction_symmetry():
    pol = ThesisPolicy()
    # BOS continuation: bullish -> LONG, bearish -> SHORT (symmetric)
    assert pol.decide(_tctx([_brk("BOS", "bullish")])).direction is Direction.LONG
    assert pol.decide(_tctx([_brk("BOS", "bearish")])).direction is Direction.SHORT


def test_thesis_choch_direction_symmetry():
    pol = ThesisPolicy()
    assert pol.decide(_tctx([_brk("CHoCH", "bullish")])).direction is Direction.LONG
    assert pol.decide(_tctx([_brk("CHoCH", "bearish")])).direction is Direction.SHORT


def test_thesis_choch_overrides_bos_both_directions():
    pol = ThesisPolicy()
    # bearish BOS (old continuation) + bullish CHoCH (the turn) -> LONG (reversal wins)
    d = pol.decide(_tctx([_brk("BOS", "bearish"), _brk("CHoCH", "bullish")]))
    assert d.direction is Direction.LONG and d.meta["basis"] == "choch"
    # mirror: bullish BOS + bearish CHoCH -> SHORT
    d2 = pol.decide(_tctx([_brk("BOS", "bullish"), _brk("CHoCH", "bearish")]))
    assert d2.direction is Direction.SHORT and d2.meta["basis"] == "choch"


def test_thesis_no_structure_is_flat():
    pol = ThesisPolicy()
    assert pol.decide(_tctx([])).is_flat
    assert pol.decide(SimpleNamespace(smc_snapshot=None, metadata={})).is_flat
    # breaks with unrecognized direction contribute nothing -> FLAT
    assert pol.decide(_tctx([_brk("BOS", "sideways")])).is_flat


def test_thesis_conflicting_structure_is_flat():
    pol = ThesisPolicy()
    # both-direction CHoCH -> FLAT
    assert pol.decide(_tctx([_brk("CHoCH", "bullish"), _brk("CHoCH", "bearish")])).reason == "conflicting_choch"
    # both-direction BOS (no CHoCH) -> FLAT
    assert pol.decide(_tctx([_brk("BOS", "bullish"), _brk("BOS", "bearish")])).reason == "conflicting_bos"


def test_thesis_bos_vetoed_by_strong_opposite_regime_symmetry():
    pol = ThesisPolicy()
    # BOS-long fighting a strong_down regime -> FLAT (continuation can't override strong opposite)
    assert pol.decide(_tctx([_brk("BOS", "bullish")], trend="strong_down")).is_flat
    # mirror: BOS-short vs strong_up -> FLAT
    assert pol.decide(_tctx([_brk("BOS", "bearish")], trend="strong_up")).is_flat


def test_thesis_choch_NOT_vetoed_by_strong_opposite_regime():
    pol = ThesisPolicy()
    # a CHoCH IS allowed to call the reversal against a strong opposite regime (basis=choch, no veto)
    d = pol.decide(_tctx([_brk("CHoCH", "bullish")], trend="strong_down"))
    assert d.direction is Direction.LONG
    d2 = pol.decide(_tctx([_brk("CHoCH", "bearish")], trend="strong_up"))
    assert d2.direction is Direction.SHORT


def test_thesis_bos_with_aligned_regime_passes():
    pol = ThesisPolicy()
    # BOS-long with an up regime is fine (only a STRONG opposite vetoes)
    assert pol.decide(_tctx([_brk("BOS", "bullish")], trend="up")).direction is Direction.LONG
    assert pol.decide(_tctx([_brk("BOS", "bearish")], trend="down")).direction is Direction.SHORT


def test_thesis_never_raises_returns_flat():
    pol = ThesisPolicy()

    class _Boom:
        @property
        def structural_breaks(self):
            raise RuntimeError("boom")

    d = pol.decide(SimpleNamespace(smc_snapshot=_Boom(), metadata={}))
    assert d.is_flat and d.reason.startswith("thesis_error")


def test_thesis_leaves_trade_type_none_and_is_a_policy():
    pol = ThesisPolicy()
    assert isinstance(pol, DecisionPolicy) and pol.name == "thesis_structure"
    d = pol.decide(_tctx([_brk("BOS", "bullish")]))
    assert d.trade_type is None  # cascade decides geometry
    assert d.source == "thesis_structure" and d.reason
