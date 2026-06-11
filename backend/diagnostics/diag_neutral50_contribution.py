"""
diag_neutral50_contribution.py - measure-first diagnostic for scoring-normalization fix T3-2.

OPERATOR QUESTION (2026-06-09): how many confluence points do (a) neutral-50 default
factors and (b) absent-factor weight redistribution contribute to currently-PASSING
signals? This number sizes the gate recalibration that must accompany the T3-2 fix
(fixed weights, no redistribution, no neutral-50s). Per plan: no fix code until this
diagnostic has produced baseline numbers.

WHAT IT MEASURES - three counterfactual policies per scored signal:
  A  SHIPPED      : redistribution + neutral-50s (reproduced from the stored factor
                    list; post-normalization weights ARE the shipped weights, so
                    policy A is exact, not reconstructed).
  B  NO-NEUTRALS  : neutral-50 marker factors zeroed, redistribution kept.
                    (A - B) = points contributed by neutral-50 defaults.
  C  TARGET       : original fixed mode weights, absent factors contribute 0,
                    neutral-50s zeroed, NO redistribution.
                    (A - C) = total inflation the T3-2 fix will remove.
  Synergy / conflict / coverage / macro adjustments are held constant across
  policies (they are additive on top of the weighted component and not the subject
  of T3-2). Final-score estimates: X_final = shipped_total - (A - X).

NEUTRAL-50 MARKERS (verified against scorer.py rationale literals - exact match):
  OB Precision: no longer a neutral-50 marker after Fix 4d (2026-06-11). Old "Inside Order
  Block" emitted score=50.0 floor even when not inside an OB. Merged "OB Precision" emits
  score=0.0 when not inside an OB — a true zero, not inflation. No longer in NEUTRAL_MARKERS.
  Premium/Discount Zone score==50  rationale=="Equilibrium zone"        (scorer.py:2871,
                        fallback-only: real equilibrium overwrites the rationale)
  Regime Alignment      score==50  rationale=="Neutral regime"          (scorer.py:2887)
  Other factors at exactly 50 are reported as AMBIGUOUS-neutral, never zeroed.

KNOWN INSTRUMENTATION GAP (surfaced as a finding, not fixed here): the dedicated
breakdown logger (scorer.py:49-76, logs/confluence_breakdown.log) is created but never
written - zero .info() call sites - and SIGNAL_GENERATED telemetry persists only
confidence_score, not the factor list (bot/telemetry/events.py:146-152). There is
therefore NO persisted factor-level record to parse; this tool captures breakdowns at
runtime via a hook, or parses a saved scan-API JSON. Closing the gap = one
BREAKDOWN_LOG_FILE.info(json.dumps(...)) call at the end of calculate_confluence_score;
that is a scorer edit -> symmetry-guard, so it ships with T3-2, not here.

READ-ONLY with respect to engine behavior: the hook wraps and delegates; it never
alters arguments or return values. No engine files are modified.

USAGE
    python -m backend.diagnostics.diag_neutral50_contribution --synthetic
    python -m backend.diagnostics.diag_neutral50_contribution --scan-json scan_output.json
    python -m backend.diagnostics.diag_neutral50_contribution --hook backend.diagnostics.pipeline_smoke
    python -m backend.diagnostics.diag_neutral50_contribution --hook backend.cli -- scan --mode stealth
"""
from __future__ import annotations

import argparse
import json
import runpy
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Factor-name -> mode-weight-key map. Names are the exact ConfluenceFactor name
# strings in scorer.py (grep-extracted 2026-06-09). Unknown names fall back to
# the factor's own stored weight and are counted in the "unmapped" report line.
# ---------------------------------------------------------------------------
NAME_TO_WEIGHT_KEY: Dict[str, str] = {
    "Order Block": "order_block",
    "Fair Value Gap": "fvg",
    "Market Structure": "market_structure",
    "Liquidity Sweep": "liquidity_sweep",
    "Kill Zone Timing": "kill_zone",
    "Momentum": "momentum",
    "Price-Indicator Divergence": "divergence",
    "Volume": "volume",
    "VWAP Alignment": "vwap",
    "Volatility": "volatility",
    "Close Momentum": "close_momentum",
    "Multi-Candle Confirmation": "multi_close_confirm",
    "MACD Veto": "macd_veto",
    "HTF Composite": "htf_composite",
    "Regime Alignment": "regime_alignment",
    "BTC Impulse Gate": "btc_impulse",
    "Weekly StochRSI Bonus": "weekly_stoch_rsi",
    "Fibonacci Proximity": "fibonacci",
    "Premium/Discount Zone": "premium_discount",
    "OB Precision": "ob_precision",  # Fix 4d: merged inside_ob + nested_ob into ob_precision
    "Opposing Structure": "opposing_structure",
    "Institutional Sequence": "institutional_sequence",
    "Liquidity Draw": "liquidity_draw",
    "MTF Indicator Alignment": "multi_tf_reversal",  # closest key; flagged if absent
}
GATE_ARTIFACT_NAMES = {"Structural Minimum"}  # gate echo, excluded from all policies

NEUTRAL_MARKERS: List[Tuple[str, float, str]] = [
    # "OB Precision" removed from NEUTRAL_MARKERS (Fix 4d): old Inside Order Block
    # emitted score=50.0 floor; merged OB Precision emits 0.0 — a true zero, not inflation.
    ("Premium/Discount Zone", 50.0, "Equilibrium zone"),
    ("Regime Alignment", 50.0, "Neutral regime"),
]

PROFILE_GATES = {  # scanner_modes.py MODES min_confluence_score (canonical + alias)
    "macro_surveillance": 72.0, "overwatch": 72.0,
    "intraday_aggressive": 68.0, "strike": 68.0,
    "precision": 70.0, "surgical": 70.0,
    "stealth_balanced": 70.0, "stealth": 70.0,
}


@dataclass
class FactorRow:
    name: str
    score: float
    weight_post: float  # weight as stored on the breakdown (post-normalization)
    rationale: str

    @property
    def is_gate_artifact(self) -> bool:
        return self.name in GATE_ARTIFACT_NAMES

    @property
    def is_neutral_marker(self) -> bool:
        return any(
            self.name == n and abs(self.score - s) < 1e-9 and self.rationale.strip() == r
            for (n, s, r) in NEUTRAL_MARKERS
        )

    @property
    def is_ambiguous_50(self) -> bool:
        return (not self.is_neutral_marker) and abs(self.score - 50.0) < 1e-9


@dataclass
class SignalAnalysis:
    label: str
    profile: str
    shipped_total: Optional[float]
    a_weighted: float
    b_weighted: float
    c_weighted: float
    neutral_names: List[str]
    ambiguous_names: List[str]
    unmapped_names: List[str]
    gate: Optional[float]

    @property
    def neutral_contribution(self) -> float:
        return self.a_weighted - self.b_weighted

    @property
    def total_inflation(self) -> float:
        return self.a_weighted - self.c_weighted

    def final_estimate(self, weighted: float) -> Optional[float]:
        if self.shipped_total is None:
            return None
        return max(0.0, min(100.0, self.shipped_total - (self.a_weighted - weighted)))

    def passes(self, weighted: float) -> Optional[bool]:
        fe = self.final_estimate(weighted)
        if fe is None or self.gate is None:
            return None
        return fe >= self.gate


def _mode_weights(profile: str) -> Dict[str, float]:
    """Original (pre-normalization) weights for the profile, from the live scorer."""
    from backend.strategy.confluence.scorer import MODE_FACTOR_WEIGHTS

    return MODE_FACTOR_WEIGHTS.get((profile or "").lower(), {})


def analyze_signal(
    label: str,
    profile: str,
    factors: List[FactorRow],
    shipped_total: Optional[float],
) -> SignalAnalysis:
    weights = _mode_weights(profile)
    rows = [f for f in factors if not f.is_gate_artifact]

    def orig_w(f: FactorRow) -> Tuple[float, bool]:
        key = NAME_TO_WEIGHT_KEY.get(f.name)
        if key and key in weights:
            return weights[key], True
        # Fallback: post-norm weight if informative, else a conservative default.
        return (f.weight_post if f.weight_post > 0 else 0.05), False

    unmapped = sorted({f.name for f in rows if not orig_w(f)[1]})

    # Policy A - shipped: post-normalization weights are the shipped weights, exact.
    a = sum(f.score * f.weight_post for f in rows)

    # Policy B - drop neutral markers, then redistribute original weights over score>0.
    b_rows = [f for f in rows if not f.is_neutral_marker]
    b_inf = [(f, orig_w(f)[0]) for f in b_rows if f.score > 0]
    b_wsum = sum(w for _, w in b_inf)
    b = (sum(f.score * w for f, w in b_inf) / b_wsum) if b_wsum > 0 else 0.0

    # Policy C - fixed weights over ALL evaluated factors; neutrals scored 0; no
    # redistribution. Denominator = sum of original weights of evaluated factors.
    c_pairs = [(0.0 if f.is_neutral_marker else f.score, orig_w(f)[0]) for f in rows]
    c_wsum = sum(w for _, w in c_pairs)
    c = (sum(s * w for s, w in c_pairs) / c_wsum) if c_wsum > 0 else 0.0

    return SignalAnalysis(
        label=label,
        profile=profile,
        shipped_total=shipped_total,
        a_weighted=a,
        b_weighted=b,
        c_weighted=c,
        neutral_names=[f.name for f in rows if f.is_neutral_marker],
        ambiguous_names=[f.name for f in rows if f.is_ambiguous_50],
        unmapped_names=unmapped,
        gate=PROFILE_GATES.get((profile or "").lower()),
    )


# ---------------------------------------------------------------------------
# Input adapters
# ---------------------------------------------------------------------------
def rows_from_breakdown(breakdown: Any) -> List[FactorRow]:
    out = []
    for f in getattr(breakdown, "factors", []) or []:
        out.append(
            FactorRow(
                name=getattr(f, "name", "?"),
                score=float(getattr(f, "score", 0.0)),
                weight_post=float(getattr(f, "weight", 0.0)),
                rationale=str(getattr(f, "rationale", "") or ""),
            )
        )
    return out


def _walk_for_factor_lists(node: Any, path: str, hits: List[Tuple[str, list, dict]]) -> None:
    """Tolerant scan-JSON walker: find any list of {name, score, weight} dicts."""
    if isinstance(node, dict):
        for k, v in node.items():
            _walk_for_factor_lists(v, f"{path}.{k}", hits)
        if isinstance(node.get("factors"), list):
            fl = node["factors"]
            if fl and all(isinstance(x, dict) and "name" in x and "score" in x for x in fl):
                hits.append((path, fl, node))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk_for_factor_lists(v, f"{path}[{i}]", hits)


def analyses_from_scan_json(path: str, default_profile: str) -> List[SignalAnalysis]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    hits: List[Tuple[str, list, dict]] = []
    _walk_for_factor_lists(data, "$", hits)
    analyses = []
    for jpath, factor_dicts, parent in hits:
        rows = [
            FactorRow(
                name=str(d.get("name", "?")),
                score=float(d.get("score", 0.0)),
                weight_post=float(d.get("weight", 0.0)),
                rationale=str(d.get("rationale", "") or ""),
            )
            for d in factor_dicts
        ]
        profile = str(
            parent.get("profile") or parent.get("mode") or default_profile
        )
        total = parent.get("total_score") or parent.get("confluence_score") or parent.get("score")
        label = str(parent.get("symbol") or parent.get("label") or jpath)
        analyses.append(
            analyze_signal(label, profile, rows, float(total) if total is not None else None)
        )
    return analyses


# ---------------------------------------------------------------------------
# Hook mode - wrap the live scorer, run a target module, collect breakdowns.
# Patches BOTH binding sites: the scorer module attr and confluence_service's
# name-import (services/confluence_service.py:26 - the only production caller).
# ---------------------------------------------------------------------------
CAPTURED: List[SignalAnalysis] = []


def install_hook() -> None:
    import backend.strategy.confluence.scorer as scorer_mod

    real = scorer_mod.calculate_confluence_score

    def wrapper(*args, **kwargs):
        bd = real(*args, **kwargs)
        try:
            config = kwargs.get("config", args[2] if len(args) > 2 else None)
            profile = str(getattr(config, "profile", "stealth_balanced"))
            symbol = str(kwargs.get("symbol", "Unknown"))
            direction = str(kwargs.get("direction", args[3] if len(args) > 3 else "?"))
            CAPTURED.append(
                analyze_signal(
                    f"{symbol} {direction}",
                    profile,
                    rows_from_breakdown(bd),
                    float(getattr(bd, "total_score", 0.0)),
                )
            )
        except Exception as e:  # diagnostics must never alter engine behavior
            print(f"[diag_neutral50] capture failed (engine unaffected): {e}", file=sys.stderr)
        return bd

    scorer_mod.calculate_confluence_score = wrapper
    try:
        import backend.services.confluence_service as csvc

        if getattr(csvc, "calculate_confluence_score", None) is real:
            csvc.calculate_confluence_score = wrapper
    except Exception:
        pass  # service not importable in this context; scorer-module patch still active


# ---------------------------------------------------------------------------
# Synthetic fixtures - prove the counterfactual math anywhere, no engine needed
# beyond MODE_FACTOR_WEIGHTS import.
# ---------------------------------------------------------------------------
def synthetic_analyses() -> List[SignalAnalysis]:
    def F(name, score, wpost, rationale=""):
        return FactorRow(name, score, wpost, rationale)

    # Case 1: sparse setup - one strong factor + the three neutral-50 defaults.
    # Post-norm weights sum to 1.0 across score>0 factors (replicates shipped math).
    sparse = [
        F("Order Block", 85.0, 0.45, "OB (A): Grade A(+40), Fresh OB(+15)"),
        F("OB Precision", 0.0, 0.20, "Not inside order block"),  # Fix 4d: 0.0 default, no floor
        F("Premium/Discount Zone", 50.0, 0.18, "Equilibrium zone"),
        F("Regime Alignment", 50.0, 0.19, "Neutral regime"),
        F("Fair Value Gap", 0.0, 0.0, "No fair value gaps identified"),
        F("Market Structure", 0.0, 0.0, "Structure bias neutral"),
        F("Liquidity Sweep", 0.0, 0.0, "No recent liquidity sweep detected"),
        F("Momentum", 0.0, 0.0, "Weak momentum bias"),
        F("HTF Composite", 0.0, 0.0, "No HTF data"),
    ]
    # Case 2: dense setup - many real factors, no neutral defaults.
    dense_names = [
        ("Order Block", 70.0), ("Fair Value Gap", 65.0), ("Market Structure", 75.0),
        ("Liquidity Sweep", 60.0), ("Momentum", 68.0), ("Volume", 62.0),
        ("HTF Composite", 71.0), ("Institutional Sequence", 70.0),
        ("Premium/Discount Zone", 75.0),
    ]
    wpost = 1.0 / len(dense_names)
    dense = [F(n, s, wpost, "real") for n, s in dense_names]

    # Case 3: opposing-structure inversion exhibit - threat far away contributes.
    inv = [
        F("Order Block", 80.0, 0.40, "OB (A)"),
        F("Opposing Structure", 47.5, 0.20, "Bearish 4h OB 1.9 ATR above - resistance threat"),
        F("Premium/Discount Zone", 50.0, 0.20, "Equilibrium zone"),
        F("Regime Alignment", 50.0, 0.20, "Neutral regime"),
    ]
    out = []
    for label, profile, rows in [
        ("SYNTH sparse+neutrals", "stealth_balanced", sparse),
        ("SYNTH dense", "stealth_balanced", dense),
        ("SYNTH opposing-inversion", "intraday_aggressive", inv),
    ]:
        a = sum(f.score * f.weight_post for f in rows)
        out.append(analyze_signal(label, profile, rows, shipped_total=a))  # total ~= weighted
    return out


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def report(analyses: List[SignalAnalysis]) -> int:
    if not analyses:
        print("No scored signals captured/parsed - nothing to report.")
        print("If using --hook: confirm the target run actually reaches scoring "
              "(pre-scoring gate rejects produce no breakdown).")
        return 1

    print("=" * 88)
    print("NEUTRAL-50 + REDISTRIBUTION CONTRIBUTION  (measure-first for T3-2)")
    print("Policies: A=shipped  B=A minus neutral-50s  C=fixed weights, no redistribution")
    print("=" * 88)
    hdr = (f"{'signal':<28}{'prof':<10}{'A':>7}{'B':>7}{'C':>7}"
           f"{'neut.pts':>9}{'infl.pts':>9}{'pass A/B/C':>12}")
    print(hdr)
    print("-" * 88)

    pass_a = pass_b = pass_c = gated = 0
    for s in analyses:
        pa, pb, pc = s.passes(s.a_weighted), s.passes(s.b_weighted), s.passes(s.c_weighted)
        if pa is not None:
            gated += 1
            pass_a += bool(pa); pass_b += bool(pb); pass_c += bool(pc)
        flag = "".join("Y" if p else "n" if p is not None else "?" for p in (pa, pb, pc))
        print(f"{s.label[:27]:<28}{s.profile[:9]:<10}"
              f"{s.a_weighted:>7.1f}{s.b_weighted:>7.1f}{s.c_weighted:>7.1f}"
              f"{s.neutral_contribution:>9.1f}{s.total_inflation:>9.1f}{flag:>12}")

    n = len(analyses)
    mean_neut = sum(s.neutral_contribution for s in analyses) / n
    mean_infl = sum(s.total_inflation for s in analyses) / n
    neut_hits = sum(1 for s in analyses if s.neutral_names)
    print("-" * 88)
    print(f"signals analyzed:                {n}")
    print(f"with >=1 neutral-50 marker:      {neut_hits}  ({100.0*neut_hits/n:.0f}%)")
    print(f"mean neutral-50 contribution:    {mean_neut:+.2f} pts   (A - B)")
    print(f"mean total inflation vs target:  {mean_infl:+.2f} pts   (A - C)  <-- gate recal input")
    if gated:
        print(f"gate pass rate  A / B / C:       {pass_a}/{gated}  {pass_b}/{gated}  {pass_c}/{gated}")
    b_gt_a = sum(1 for s in analyses if s.b_weighted > s.a_weighted + 1e-9)
    if b_gt_a:
        print(f"INTERPRETATION: {b_gt_a} signal(s) score HIGHER under B than A - neutral-50s were")
        print("  diluting a sparse strong factor; removing them under redistribution concentrates")
        print("  all weight on it. Confirms policy B (drop neutrals, keep redistribution) is NOT a")
        print("  safe standalone fix - C (fixed weights) is the only coherent target. Ship together.")
    amb = sorted({nm for s in analyses for nm in s.ambiguous_names})
    if amb:
        print(f"AMBIGUOUS score==50 (not zeroed, review): {', '.join(amb)}")
    unm = sorted({nm for s in analyses for nm in s.unmapped_names})
    if unm:
        print(f"UNMAPPED factor names (post-norm weight used as fallback): {', '.join(unm)}")
    print()
    print("INSTRUMENTATION GAP: breakdown logger (scorer.py:49-76) is never written; "
          "SIGNAL_GENERATED telemetry has no factor list. Persisting breakdowns ships "
          "with T3-2 (scorer edit -> symmetry-guard), enabling historical replay here.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Counterfactual scoring-policy measurement (read-only).")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--synthetic", action="store_true", help="run built-in fixtures (self-test)")
    src.add_argument("--scan-json", metavar="FILE", help="parse a saved scan API response")
    src.add_argument("--hook", metavar="MODULE", help="wrap live scorer, then run MODULE "
                     "(args after '--' are passed through)")
    ap.add_argument("--profile", default="stealth_balanced",
                    help="default profile for scan-json entries lacking one")
    args, passthrough = ap.parse_known_args()
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]

    if args.synthetic:
        return report(synthetic_analyses())
    if args.scan_json:
        return report(analyses_from_scan_json(args.scan_json, args.profile))

    install_hook()
    sys.argv = [args.hook] + passthrough
    try:
        runpy.run_module(args.hook, run_name="__main__")
    except SystemExit:
        pass
    return report(CAPTURED)


if __name__ == "__main__":
    raise SystemExit(main())
