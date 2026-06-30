"""CvdTracker unit tests — pure rolling-CVD logic (decisions/2026-06-30__cvd-experiment, Phase A).

Pins: de-dup by timestamp (Phemex has no trade id), coverage/gap detection, the DIRECTION-SIGNED
symmetry (LONG/SHORT mirror — CLAUDE.md §10 / Rubric 12), and the imbalance/divergence math.
"""
from __future__ import annotations

from backend.bot.cvd.cvd_tracker import CvdTracker

MIN = 60 * 1000
HOUR = 60 * MIN


def _trades(start_ts, specs):
    # specs: list of (offset_min, signed_vol, price) -> (ts, signed_vol, price)
    return [(start_ts + int(off * MIN), sv, px) for off, sv, px in specs]


def test_dedup_by_timestamp():
    t = CvdTracker()
    base = 10 * HOUR
    tr = _trades(base, [(0, 5.0, 100.0), (1, -3.0, 100.0)])
    t.ingest("X", tr)
    t.ingest("X", tr)  # same trades again — must NOT double count (id is None, dedup by ts)
    f = t.snapshot_features("X", "LONG", base + 2 * MIN)
    # net = 5 - 3 = 2, tot = 8 -> imbalance 0.25; counted once
    assert abs(f["cvd_slope_1h"] - 0.25) < 1e-9
    assert f["cvd_n_trades"] == 2.0


def test_direction_signed_symmetry():
    # identical flow: LONG and SHORT must get EXACTLY mirrored slope/z signs (no self-cancel)
    base = 10 * HOUR
    tr = _trades(base, [(0, 10.0, 100.0), (10, 8.0, 101.0)])  # net buy pressure
    tL = CvdTracker(); tL.ingest("X", tr)
    tS = CvdTracker(); tS.ingest("X", tr)
    fL = tL.snapshot_features("X", "LONG", base + 20 * MIN)
    fS = tS.snapshot_features("X", "SHORT", base + 20 * MIN)
    assert fL["cvd_slope_1h"] > 0          # buy flow agrees with a long
    assert fS["cvd_slope_1h"] == -fL["cvd_slope_1h"]  # exact mirror for the short
    assert fS["cvd_z"] == -fL["cvd_z"]


def test_imbalance_buy_vs_sell():
    base = 10 * HOUR
    t = CvdTracker()
    t.ingest("X", _trades(base, [(0, 9.0, 100.0), (5, -1.0, 100.0)]))  # net +8 / tot 10 -> 0.8
    f = t.snapshot_features("X", "LONG", base + 10 * MIN)
    assert abs(f["cvd_slope_1h"] - 0.8) < 1e-9


def test_divergence_favors_short_when_price_up_flow_down():
    # price RISES but net flow is SELL -> bearish divergence -> favors a SHORT (+1), opposes a LONG (-1)
    base = 10 * HOUR
    tr = _trades(base, [(0, -5.0, 100.0), (30, -4.0, 105.0)])  # price 100->105 up, flow net -9 (sell)
    t = CvdTracker(); t.ingest("X", tr)
    fS = t.snapshot_features("X", "SHORT", base + 40 * MIN)
    fL = t.snapshot_features("X", "LONG", base + 40 * MIN)
    assert fS["cvd_divergence"] == 1.0
    assert fL["cvd_divergence"] == -1.0


def test_coverage_full_vs_partial():
    base = 10 * HOUR
    t = CvdTracker()
    # trades spanning ~the full hour
    t.ingest("X", _trades(base, [(0, 1.0, 100.0), (58, 1.0, 100.0)]))
    f_full = t.snapshot_features("X", "LONG", base + 59 * MIN)
    assert f_full["cvd_coverage"] > 0.9
    # a fresh symbol with only 10 min of span -> low coverage
    t.ingest("Y", _trades(base, [(0, 1.0, 50.0), (10, 1.0, 50.0)]))
    f_part = t.snapshot_features("Y", "LONG", base + 10 * MIN)
    assert f_part["cvd_coverage"] < 0.25


def test_gap_detection_zeros_coverage():
    base = 10 * HOUR
    t = CvdTracker()
    t.ingest("X", _trades(base, [(0, 1.0, 100.0), (5, 1.0, 100.0)]))
    # next poll's OLDEST trade is far newer than last-seen -> trades were missed between -> gap
    t.ingest("X", _trades(base, [(40, 1.0, 100.0), (45, 1.0, 100.0)]))
    f = t.snapshot_features("X", "LONG", base + 46 * MIN)
    assert f["cvd_coverage"] == 0.0  # gap landed in-window -> excluded downstream


def test_cold_symbol_returns_zeros():
    t = CvdTracker()
    f = t.snapshot_features("NEVER", "LONG", 10 * HOUR)
    assert f == {"cvd_slope_1h": 0.0, "cvd_divergence": 0.0, "cvd_z": 0.0, "cvd_coverage": 0.0, "cvd_n_trades": 0.0}
