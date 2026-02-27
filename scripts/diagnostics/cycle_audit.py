"""
Cycle Detection Audit + Analysis - Clean ASCII version
Fetches BTC/ETH/SOL daily data, runs both cycle detectors
across every bar, collects results, saves CSVs, and prints findings.
"""
import sys
import os
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from datetime import datetime

# ── yfinance ──────────────────────────────────────────────────────────────────
try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    print("ERROR: yfinance not installed. Run: pip install yfinance")
    sys.exit(1)

# ── Project imports ───────────────────────────────────────────────────────────
from backend.strategy.smc.cycle_detector import detect_cycle_context, CycleConfig, CRYPTO_CYCLE_CONFIG
from backend.strategy.smc.symbol_cycle_detector import detect_symbol_cycles
from backend.shared.models.smc import CyclePhase, CycleTranslation, CycleConfirmation

SYMBOLS = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD"}
LOOKBACK_DAYS = 365
MIN_BARS = 60
OUT_DIR = Path("cycle_audit_results")
OUT_DIR.mkdir(exist_ok=True)
CONFIG = CRYPTO_CYCLE_CONFIG


def fetch(yf_sym, days=LOOKBACK_DAYS):
    ticker = yf.download(yf_sym, period=f"{days}d", interval="1d", progress=False, ignore_tz=False)
    if ticker.empty:
        raise RuntimeError(f"No data for {yf_sym}")
    if isinstance(ticker.columns, pd.MultiIndex):
        ticker.columns = ticker.columns.get_level_values(0)
    ticker = ticker.reset_index()
    ts_col = "Date" if "Date" in ticker.columns else "Datetime"
    ticker = ticker.rename(columns={ts_col: "timestamp", "Open": "open", "High": "high",
                                    "Low": "low", "Close": "close", "Volume": "volume"})
    ticker["timestamp"] = pd.to_datetime(ticker["timestamp"], utc=True)
    ticker = ticker.set_index("timestamp")[["open", "high", "low", "close", "volume"]]
    ticker.index = ticker.index.tz_localize(None)
    return ticker.sort_index().dropna()


def scan_bar(df, i, cfg):
    window = df.iloc[:i+1]
    price = float(window["close"].iloc[-1])
    date_val = window.index[-1]
    if hasattr(date_val, "strftime"):
        date_str = date_val.strftime("%Y-%m-%d")
    else:
        date_str = str(date_val)[:10]

    row = {"date": date_str, "close": round(price, 2), "bars": len(window)}

    # ── cycle_detector ────────────────────────────────────────────────────────
    try:
        ctx = detect_cycle_context(window, config=cfg, current_price=price)
        row["cd_phase"] = ctx.phase.value
        row["cd_translation"] = ctx.translation.value
        row["cd_trade_bias"] = ctx.trade_bias
        row["cd_confidence"] = round(float(ctx.confidence), 1)
        row["cd_dcl_days"] = ctx.dcl_days_since
        row["cd_dcl_status"] = ctx.dcl_confirmation.value
        row["cd_wcl_days"] = ctx.wcl_days_since
        row["cd_in_dcl_zone"] = bool(ctx.in_dcl_zone)
        row["cd_in_wcl_zone"] = bool(ctx.in_wcl_zone)
        row["cd_dcl_price"] = round(float(ctx.dcl_price), 2) if ctx.dcl_price else None
        row["cd_wcl_price"] = round(float(ctx.wcl_price), 2) if ctx.wcl_price else None
        row["cd_dcl_failed"] = bool(ctx.dcl_price and price < ctx.dcl_price)
        row["cd_wcl_failed"] = bool(ctx.wcl_price and price < ctx.wcl_price)
        # Flag: confirmed DCL before early zone threshold
        row["FLAG_early_dcl"] = bool(
            ctx.dcl_confirmation == CycleConfirmation.CONFIRMED
            and ctx.dcl_days_since is not None
            and ctx.dcl_days_since < cfg.dcl_early_zone
        )
    except Exception as e:
        row["cd_error"] = str(e)[:120]

    # ── symbol_cycle_detector ─────────────────────────────────────────────────
    try:
        sc = detect_symbol_cycles(window, symbol="AUDIT", current_price=price)
        row["sc_dcl_translation"] = sc.dcl.translation.value
        row["sc_dcl_bars"] = sc.dcl.bars_since_low
        row["sc_dcl_failed"] = bool(sc.dcl.is_failed)
        row["sc_dcl_window"] = bool(sc.dcl.is_in_window)
        row["sc_dcl_status"] = sc.dcl.status.value
        row["sc_dcl_bias"] = sc.dcl.bias
        row["sc_wcl_translation"] = sc.wcl.translation.value
        row["sc_wcl_bars"] = sc.wcl.bars_since_low
        row["sc_wcl_failed"] = bool(sc.wcl.is_failed)
        row["sc_wcl_window"] = bool(sc.wcl.is_in_window)
        row["sc_wcl_status"] = sc.wcl.status.value
        row["sc_wcl_bias"] = sc.wcl.bias
        row["sc_overall_bias"] = sc.overall_bias
        row["sc_alignment"] = sc.alignment

        # Flags
        cd_bias = row.get("cd_trade_bias", "NEUTRAL")
        sc_bias = sc.overall_bias
        row["FLAG_disagree"] = bool(cd_bias != sc_bias and cd_bias != "NEUTRAL" and sc_bias != "NEUTRAL")
        row["FLAG_wcl_silent"] = bool(sc.wcl.is_failed and sc.overall_bias != "SHORT")
    except Exception as e:
        row["sc_error"] = str(e)[:120]

    return row


def audit_sym(name, df):
    print(f"  Scanning {name}: {len(df)} bars...")
    rows = []
    n = len(df)
    for i in range(MIN_BARS, n):
        rows.append(scan_bar(df, i, CONFIG))
        if (i - MIN_BARS) % 60 == 0:
            pct = int((i - MIN_BARS) / (n - MIN_BARS) * 100)
            print(f"    {pct}%...", end="\r")
    print(f"    Done ({n} bars)     ")
    return pd.DataFrame(rows)


def analyze(df, name):
    total = len(df)
    print(f"\n========== {name} ({total} bars, {df['date'].iloc[0]} to {df['date'].iloc[-1]}) ==========")

    # Finding 1: early DCL confirmations
    if "FLAG_early_dcl" in df.columns:
        early = df[df["FLAG_early_dcl"] == True]
        pct = len(early) / total * 100
        print(f"\nFINDING 1 - Early Confirmed DCLs (timing window bug, day < 15):")
        print(f"  Count: {len(early)} / {total} ({pct:.1f}%)")
        if len(early) > 0:
            print(f"  BUG IS ACTIVE - false DCL confirmations are happening")
            if "cd_dcl_days" in df.columns:
                print(f"  Min day confirmed: {early['cd_dcl_days'].min()}")
                print(f"  Avg day confirmed: {early['cd_dcl_days'].mean():.1f}")
                print(f"  Sample (date / close / dcl_day / phase):")
                for _, r in early[["date","close","cd_dcl_days","cd_phase"]].head(6).iterrows():
                    print(f"    {r['date']}  ${r['close']}  day={r['cd_dcl_days']}  {r['cd_phase']}")
        else:
            print(f"  No early false confirmations detected")

    # Finding 2: WCL failures
    print(f"\nFINDING 2 - WCL Failures:")
    if "cd_wcl_failed" in df.columns:
        wf = int(df["cd_wcl_failed"].sum())
        print(f"  cycle_detector   WCL failures: {wf} / {total} ({wf/total*100:.1f}%)")
    if "sc_wcl_failed" in df.columns:
        wf2 = int(df["sc_wcl_failed"].sum())
        print(f"  symbol_detector  WCL failures: {wf2} / {total} ({wf2/total*100:.1f}%)")
        failed = df[df["sc_wcl_failed"] == True]
        if len(failed) > 0 and "sc_overall_bias" in df.columns:
            bias_when_failed = failed["sc_overall_bias"].value_counts().to_dict()
            print(f"  Bias when WCL failed: {bias_when_failed}")
    if "FLAG_wcl_silent" in df.columns:
        silent = int(df["FLAG_wcl_silent"].sum())
        print(f"  Silent WCL failures (no SHORT signaled): {silent}")
        if silent > 0:
            print(f"  WARNING: WCL failure is NOT reliably switching to SHORT bias")

    # Finding 3: Detector disagreement
    print(f"\nFINDING 3 - Bias Disagreement (cycle_detector vs symbol_detector):")
    if "FLAG_disagree" in df.columns:
        dis = int(df["FLAG_disagree"].sum())
        print(f"  Disagreements: {dis} / {total} ({dis/total*100:.1f}%)")
        if dis > 0:
            sample = df[df["FLAG_disagree"] == True][["date","close","cd_trade_bias","sc_overall_bias"]].head(6)
            for _, r in sample.iterrows():
                print(f"    {r['date']}  ${r['close']}  cd={r['cd_trade_bias']}  sc={r['sc_overall_bias']}")

    # Finding 4: Phase dist
    print(f"\nFINDING 4 - Phase Distribution:")
    if "cd_phase" in df.columns:
        for phase, cnt in df["cd_phase"].value_counts().items():
            print(f"  {phase:<22} {cnt:>4} bars ({cnt/total*100:.1f}%)")

    # Finding 5: Translation
    print(f"\nFINDING 5 - Translation:")
    if "cd_translation" in df.columns:
        for t, cnt in df["cd_translation"].value_counts().items():
            print(f"  cd {t:<25} {cnt:>4} ({cnt/total*100:.1f}%)")
    if "sc_dcl_translation" in df.columns:
        for t, cnt in df["sc_dcl_translation"].value_counts().items():
            print(f"  sc {t:<25} {cnt:>4} ({cnt/total*100:.1f}%)")

    # Finding 6: DCL zone hit rate
    print(f"\nFINDING 6 - DCL Zone Hit Rate:")
    if "cd_in_dcl_zone" in df.columns:
        iz = int(df["cd_in_dcl_zone"].sum())
        print(f"  In DCL zone: {iz} / {total} ({iz/total*100:.1f}%) [healthy target: 40-60%]")

    # Finding 7: DCL confirmation
    print(f"\nFINDING 7 - DCL Confirmation Status:")
    if "cd_dcl_status" in df.columns:
        for s, cnt in df["cd_dcl_status"].value_counts().items():
            print(f"  {s:<20} {cnt:>4} ({cnt/total*100:.1f}%)")

    # Finding 8: Trade bias
    print(f"\nFINDING 8 - Trade Bias Summary:")
    if "cd_trade_bias" in df.columns:
        for b, cnt in df["cd_trade_bias"].value_counts().items():
            print(f"  cd  {b:<10} {cnt:>4} ({cnt/total*100:.1f}%)")
    if "sc_overall_bias" in df.columns:
        for b, cnt in df["sc_overall_bias"].value_counts().items():
            print(f"  sc  {b:<10} {cnt:>4} ({cnt/total*100:.1f}%)")

    # Recent 5 bars
    print(f"\nRECENT 5 BARS:")
    cols = ["date","close","cd_phase","cd_translation","cd_trade_bias",
            "cd_dcl_days","cd_dcl_status","cd_in_dcl_zone","cd_dcl_failed","cd_wcl_failed","sc_overall_bias"]
    avail = [c for c in cols if c in df.columns]
    print(df[avail].tail(5).to_string(index=False))


# ── MAIN ──────────────────────────────────────────────────────────────────────
print("=" * 60)
print("SNIPERSIGHT CYCLE DETECTION AUDIT")
print("=" * 60)

all_results = {}

for sym_name, yf_sym in SYMBOLS.items():
    print(f"\n[{sym_name}] Fetching data from yfinance...")
    try:
        df_raw = fetch(yf_sym)
        print(f"  Got {len(df_raw)} bars ({df_raw.index[0].date()} to {df_raw.index[-1].date()})")
        result = audit_sym(sym_name, df_raw)
        all_results[sym_name] = result
        out = OUT_DIR / f"{sym_name}_cycle_audit.csv"
        result.to_csv(out, index=False, encoding="utf-8")
        print(f"  Saved to {out}")
    except Exception as e:
        import traceback
        print(f"  FAILED: {e}")
        traceback.print_exc()

print("\n\n" + "=" * 60)
print("ANALYSIS")
print("=" * 60)

for sym_name, result in all_results.items():
    analyze(result, sym_name)

print("\n\n" + "=" * 60)
print("CROSS-SYMBOL SUMMARY")
print("=" * 60)
for sym_name, df in all_results.items():
    total = len(df)
    early = int(df.get("FLAG_early_dcl", pd.Series(dtype=bool)).sum())
    wcl_f = int(df.get("sc_wcl_failed", pd.Series(dtype=bool)).sum())
    silent = int(df.get("FLAG_wcl_silent", pd.Series(dtype=bool)).sum())
    dis = int(df.get("FLAG_disagree", pd.Series(dtype=bool)).sum())
    print(f"\n  {sym_name}:")
    print(f"    Early confirmed DCLs (bug):    {early:>3} / {total} ({early/total*100:.1f}%)")
    print(f"    WCL failures detected:         {wcl_f:>3} / {total} ({wcl_f/total*100:.1f}%)")
    print(f"    Silent WCL failures (no SHORT):{silent:>3}")
    print(f"    Detector disagreements:        {dis:>3} / {total} ({dis/total*100:.1f}%)")

print("\nAUDIT COMPLETE")
print(f"CSVs saved to: {OUT_DIR}/")
