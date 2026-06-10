"""TEMP perception probe: dump the bot's BTC order blocks + structural breaks (BOS/CHoCH)
with zones/levels, to compare against a TradingView/LuxAlgo chart. Read-only."""
import sys
from collections import defaultdict
from backend.data.adapters.phemex import PhemexAdapter
from backend.data.ingestion_pipeline import IngestionPipeline
from backend.services.smc_service import SMCDetectionService
from backend.shared.config.smc_config import SMCConfig

sym = sys.argv[1] if len(sys.argv) > 1 else "BTC/USDT"
pipe = IngestionPipeline(PhemexAdapter())
mtf = pipe.fetch_multi_timeframe(sym, ["15m", "1h", "4h", "1d"])
cp = None
for tf in ["1h", "4h"]:
    df = mtf.timeframes.get(tf)
    if df is not None and len(df):
        cp = float(df["close"].iloc[-1]); break
import json, urllib.request
try:
    resp = json.load(urllib.request.urlopen("http://localhost:8001/api/config/smc", timeout=8))
    live = resp.get("smc_config", {})
    smc_cfg = SMCConfig.from_dict(live)
    print(f"using LIVE bot smc_config: min_disp_atr={live.get('min_displacement_atr')} "
          f"ob_lookback={live.get('ob_lookback_candles')} struct_swing_lb={live.get('structure_swing_lookback')}")
except Exception as e:
    smc_cfg = SMCConfig.defaults()
    print(f"WARN: live config fetch failed ({e}) — using SMCConfig.defaults()")
smc = SMCDetectionService(smc_config=smc_cfg, mode="stealth")
snap = smc.detect(mtf, cp)
print(f"=== {sym} current {cp:.0f} | OBs {len(snap.order_blocks)} | breaks {len(snap.structural_breaks)} ===")

# introspect field names once
if snap.order_blocks:
    print("OB fields:", list(vars(snap.order_blocks[0]).keys()))
if snap.structural_breaks:
    print("break fields:", list(vars(snap.structural_breaks[0]).keys()))

def g(o, *names, default="?"):
    for n in names:
        if hasattr(o, n):
            return getattr(o, n)
    return default

# ORDER BLOCKS — grouped by TF, nearest to price first
by_tf = defaultdict(list)
for o in snap.order_blocks:
    by_tf[g(o, "timeframe", default="?")].append(o)
for tf in sorted(by_tf, key=lambda t: {"1D": 0, "4H": 1, "1H": 2, "15m": 3}.get(t, 9)):
    lst = sorted(by_tf[tf], key=lambda o: abs((o.high + o.low) / 2 - cp))
    print(f"\n-- {tf} ORDER BLOCKS ({len(lst)}) [nearest to {cp:.0f} first] --")
    for o in lst[:6]:
        print(f"  {o.direction:7} {o.low:>8.0f}-{o.high:<8.0f} disp={g(o,'displacement_strength',default=0):>3.0f} "
              f"mit={g(o,'mitigation_level',default=0):.2f} fresh={g(o,'freshness_score',default=0):>3.0f} @ {g(o,'timestamp')}")

# STRUCTURAL BREAKS — grouped by TF, most recent last
by_tf_b = defaultdict(list)
for b in snap.structural_breaks:
    by_tf_b[g(b, "timeframe", default="?")].append(b)
for tf in sorted(by_tf_b, key=lambda t: {"1D": 0, "4H": 1, "1H": 2, "15m": 3}.get(t, 9)):
    lst = by_tf_b[tf]
    print(f"\n-- {tf} STRUCTURE BREAKS ({len(lst)}) [most recent 6] --")
    for b in lst[-6:]:
        print(f"  {g(b,'break_type','type'):6} {str(g(b,'direction')):8} lvl={g(b,'price','level','break_level','broken_level')} @ {g(b,'timestamp')}")
