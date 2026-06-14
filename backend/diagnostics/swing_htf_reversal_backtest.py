"""
Backtest: does a SWING REVERSAL at a major HTF range extreme actually win?

Premise under test (operator 2026-06-14): the current swing tier shorts the BOTTOM of the
range (avg entry pos 0.11, 0/44 at the correct extreme) and bleeds -7.21/trade. The proposed
fix: only take swings AT a major HTF level — short at RESISTANCE (range top), long at SUPPORT
(range bottom), targeting back toward equilibrium. The bot has 0 such trades, so this can only
be tested against raw price history.

Method (lookahead-safe):
  - For each 4h candle i, the macro range is built from candles [i-WIN : i-1] (STRICTLY prior).
    range_high = max prior high (major resistance), range_low = min prior low (major support),
    eq = midpoint, atr = ATR(prior).
  - SHORT trigger: this candle's high reaches within TOUCH of the prior range_high (price tagged
    resistance). Entry = range_high. Stop = range_high + STOP_ATR*atr (above). Target = eq.
  - LONG trigger: low reaches within TOUCH of prior range_low. Entry = range_low. Stop below.
    Target = eq.
  - Outcome: walk forward up to HOLD candles; whichever of {stop, target} the path hits first.
    Ties within a candle resolve pessimistically (stop first). Timeout = mark-to-close.
  - COOLDOWN candles after any signal per symbol+direction (avoid re-entering the same tag).
  - R = realized_move / initial_risk. Fees: taker round-trip on notional-as-1R-risk basis.

NOT the full strategy — location only, no confirmations (those get tested next, individually,
only if this base premise wins). READ-ONLY. Honest caveats printed.
"""
from __future__ import annotations
import argparse, json, sys
from collections import Counter
import pandas as pd

WIN=120        # trailing 4h candles for the macro range (~20 days)
TOUCH=0.004    # within 0.4% of the level = "tagged"
STOP_ATR=1.0   # stop this many ATR beyond the level
HOLD=42        # max hold (4h candles ~ 7 days)
COOLDOWN=12    # candles to wait before re-signalling same symbol+dir
TAKER=0.0006   # per side


def _atr(df, i, n=14):
    s=df.iloc[max(0,i-n):i]
    if len(s)<2: return None
    h,l,c=s['high'],s['low'],s['close']; pc=c.shift(1)
    tr=pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    a=tr.tail(n).mean(); return a if a and a>0 else None


def backtest(df):
    """Return list of trade dicts for one symbol's 4h frame."""
    out=[]; cd={'LONG':-10**9,'SHORT':-10**9}
    H,L=df['high'].values, df['low'].values
    for i in range(WIN, len(df)-1):
        prior=df.iloc[i-WIN:i]
        rh,rl=float(prior['high'].max()), float(prior['low'].min())
        if rh<=rl: continue
        eq=(rh+rl)/2.0; atr=_atr(df,i)
        if not atr: continue
        # SHORT at resistance
        if H[i]>=rh*(1-TOUCH) and i-cd['SHORT']>=COOLDOWN:
            entry=rh; stop=rh+STOP_ATR*atr; tgt=eq
            risk=stop-entry; reward=entry-tgt
            if risk>0 and reward>0:
                cd['SHORT']=i
                out.append(_walk(df,i,'SHORT',entry,stop,tgt,risk))
        # LONG at support
        if L[i]<=rl*(1+TOUCH) and i-cd['LONG']>=COOLDOWN:
            entry=rl; stop=rl-STOP_ATR*atr; tgt=eq
            risk=entry-stop; reward=tgt-entry
            if risk>0 and reward>0:
                cd['LONG']=i
                out.append(_walk(df,i,'LONG',entry,stop,tgt,risk))
    return out


def _walk(df,i,d,entry,stop,tgt,risk):
    for j in range(i+1, min(i+1+HOLD, len(df))):
        hi,lo=float(df['high'].iloc[j]), float(df['low'].iloc[j])
        if d=='SHORT':
            if hi>=stop: return _t(d,entry,stop,'stop',-(stop-entry)/risk)
            if lo<=tgt:  return _t(d,entry,tgt,'target',(entry-tgt)/risk)
        else:
            if lo<=stop: return _t(d,entry,stop,'stop',-(entry-stop)/risk)
            if hi>=tgt:  return _t(d,entry,tgt,'target',(tgt-entry)/risk)
    close=float(df['close'].iloc[min(i+HOLD,len(df)-1)])
    r=((entry-close) if d=='SHORT' else (close-entry))/risk
    return _t(d,entry,close,'timeout',r)


def _t(d,entry,exit_,reason,r):
    fee_r=(entry+exit_)*TAKER/abs(entry-exit_) if entry!=exit_ else 0  # rough: fee in R units
    return {'dir':d,'reason':reason,'R':r}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap=argparse.ArgumentParser()
    ap.add_argument('--symbols', nargs='+', default=None)
    args=ap.parse_args()
    # universe = symbols the bot actually traded (from journal) + majors
    rows=[json.loads(l) for l in open('backend/cache/trade_journal.jsonl',encoding='utf-8')]
    syms=args.symbols or sorted({r['symbol'] for r in rows if r.get('symbol')})
    from backend.data.adapters.phemex import PhemexAdapter
    from backend.data.ingestion_pipeline import IngestionPipeline
    pipe=IngestionPipeline(PhemexAdapter())
    trades=[]; ok=0
    for s in syms:
        sx=s if ':' in s else f"{s}:USDT"
        try:
            mtf=pipe.fetch_multi_timeframe(sx,['4h']); df=getattr(mtf,'timeframes',mtf).get('4h')
        except Exception: df=None
        if df is None or len(df)<WIN+20: continue
        ok+=1; trades+=backtest(df)

    n=len(trades)
    if not n:
        print("no simulated trades"); return
    wins=[t for t in trades if t['R']>0]
    exp=sum(t['R'] for t in trades)/n
    # fee drag estimate: ~0.12% round-trip; typical risk ~1 ATR ~ a few %, so ~0.05-0.1 R/trade
    print("SWING HTF-REVERSAL BACKTEST (location only, no confirmations)")
    print(f"params: macro_win={WIN}x4h  touch={TOUCH*100:.1f}%  stop={STOP_ATR}ATR  hold={HOLD}x4h  cooldown={COOLDOWN}")
    print(f"symbols with data: {ok}/{len(syms)}  |  simulated trades: {n}")
    print()
    print(f"  WIN RATE: {100*len(wins)/n:.0f}%")
    print(f"  EXPECTANCY: {exp:+.2f} R / trade (gross)")
    print(f"  exits: {dict(Counter(t['reason'] for t in trades))}")
    for d in ('SHORT','LONG'):
        dd=[t for t in trades if t['dir']==d]
        if dd:
            w=sum(1 for t in dd if t['R']>0)
            print(f"  {d}: n={len(dd)} win {100*w/len(dd):.0f}% exp {sum(t['R'] for t in dd)/len(dd):+.2f}R")
    print()
    print("BENCHMARK — bot's actual swing tier (post-clamp): 46 trades, 46% win, -7.39/trade (shorts the BOTTOM).")
    print("CAVEATS: location-only (no confirmations); fees/slippage NOT in R; fixed eq-target;")
    print("  range def = 120x4h rolling extremes; results are premise-screening, not a live system.")


if __name__=='__main__':
    raise SystemExit(main())
