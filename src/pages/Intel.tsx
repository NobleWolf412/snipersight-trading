import { useState, useEffect, useCallback } from 'react';
import { api } from '@/utils/api';
import { useMultiplePrices } from '@/hooks/usePriceData';
import { ArrowUp, ArrowDown, Warning, CircleNotch } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { formatPrice } from '@/utils/formatters';

// ─── Types ────────────────────────────────────────────────────────────────────

interface RegimeData {
  composite: string;
  score: number;
  dimensions: {
    trend: string;
    volatility: string;
    liquidity: string;
    risk_appetite: string;
    derivatives: string;
  };
  dominance?: {
    btc_d: number;
    alt_d: number;
    stable_d: number;
  };
  timestamp: string;
}

interface FearGreedData {
  value: number;
  classification: string;
  sentiment: string;
  bottom_line: string;
  risk_text: string;
  timestamp: string;
}

interface CycleData {
  phase: string;
  translation: string;
  trade_bias: string;
  confidence: number;
  interpretation: {
    messages: string[];
    severity: string;
    summary: string;
  };
  stochastic_rsi?: {
    k: number | null;
    d: number | null;
    zone: string;
  };
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function useIntelData() {
  const [regime, setRegime] = useState<RegimeData | null>(null);
  const [fearGreed, setFearGreed] = useState<FearGreedData | null>(null);
  const [cycle, setCycle] = useState<CycleData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [regimeRes, fgRes, cycleRes] = await Promise.allSettled([
        api.getMarketRegime(),
        api.getFearGreedIndex(),
        api.getBTCCycleContext(),
      ]);

      if (regimeRes.status === 'fulfilled' && regimeRes.value.data) {
        setRegime(regimeRes.value.data as RegimeData);
      }
      if (fgRes.status === 'fulfilled' && fgRes.value.data) {
        setFearGreed(fgRes.value.data as FearGreedData);
      }
      if (cycleRes.status === 'fulfilled' && cycleRes.value.data) {
        const d = (cycleRes.value.data as any).data ?? cycleRes.value.data;
        if (d) {
          const ctxD = d as any;
          setCycle({
            phase: ctxD.macro_phase ?? ctxD.phase ?? 'UNKNOWN',
            translation: ctxD.translation ?? 'UNKNOWN',
            trade_bias: ctxD.trade_bias ?? ctxD.bias ?? 'NEUTRAL',
            confidence: ctxD.confidence ?? 0,
            interpretation: ctxD.interpretation ?? { messages: [], severity: 'neutral', summary: '' },
            stochastic_rsi: ctxD.stochastic_rsi,
          });
        }
      }
    } catch (e) {
      setError('Failed to load market data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 60_000);
    return () => clearInterval(id);
  }, [refresh]);

  return { regime, fearGreed, cycle, loading, error, refresh };
}

function regimeColor(composite: string): string {
  const c = composite.toUpperCase();
  if (c.includes('ALTSEASON')) return 'text-success';
  if (c.includes('BTC') || c.includes('DRIVE')) return 'text-blue-400';
  if (c.includes('PANIC') || c.includes('CRASH')) return 'text-destructive';
  if (c.includes('DEFENSIVE')) return 'text-warning';
  return 'text-muted-foreground';
}

function fearGreedColor(value: number): string {
  if (value < 25) return 'text-destructive';
  if (value < 45) return 'text-warning';
  if (value < 55) return 'text-muted-foreground';
  if (value < 75) return 'text-success/80';
  return 'text-success';
}

function biasColor(bias: string): string {
  if (bias === 'LONG') return 'text-success';
  if (bias === 'SHORT') return 'text-destructive';
  return 'text-muted-foreground';
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  valueClass = '',
  accent = false,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  valueClass?: string;
  accent?: boolean;
}) {
  return (
    <div
      className={cn(
        'rounded-lg border bg-card/60 p-4 backdrop-blur-sm',
        accent ? 'border-primary/40' : 'border-border/50',
      )}
    >
      <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">{label}</div>
      <div className={cn('text-2xl font-bold tabular-nums', valueClass)}>{value}</div>
      {sub && <div className="text-[11px] text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  );
}

function FearGreedGauge({ value }: { value: number }) {
  const label =
    value < 25 ? 'EXTREME FEAR' : value < 45 ? 'FEAR' : value < 55 ? 'NEUTRAL' : value < 75 ? 'GREED' : 'EXTREME GREED';
  const pct = value / 100;
  const color = fearGreedColor(value);

  return (
    <div className="rounded-lg border border-border/50 bg-card/60 p-4 backdrop-blur-sm flex flex-col items-center gap-2">
      <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Fear &amp; Greed Index</div>
      {/* Semi-circle gauge */}
      <svg viewBox="0 0 120 70" className="w-32 overflow-visible">
        {/* Track */}
        <path
          d="M10,60 A50,50 0 0,1 110,60"
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth="8"
          strokeLinecap="round"
        />
        {/* Fill */}
        <path
          d="M10,60 A50,50 0 0,1 110,60"
          fill="none"
          stroke="currentColor"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${pct * 157} 157`}
          className={color}
          style={{ transition: 'stroke-dasharray 0.8s ease' }}
        />
        {/* Value text */}
        <text x="60" y="52" textAnchor="middle" className="fill-foreground" fontSize="18" fontWeight="bold">
          {value}
        </text>
      </svg>
      <div className={cn('text-xs font-bold tracking-widest uppercase', color)}>{label}</div>
    </div>
  );
}

function DimensionRow({ label, value }: { label: string; value: string }) {
  const color =
    value === 'bullish' || value === 'trending_up' || value === 'low'
      ? 'text-success'
      : value === 'bearish' || value === 'trending_down' || value === 'high'
      ? 'text-destructive'
      : 'text-muted-foreground';
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border/20 last:border-0">
      <span className="text-[11px] uppercase tracking-widest text-muted-foreground">{label}</span>
      <span className={cn('text-xs font-bold uppercase', color)}>{value?.replace(/_/g, ' ') ?? '—'}</span>
    </div>
  );
}

function PriceRow({ symbol }: { symbol: string }) {
  const { prices } = useMultiplePrices([symbol]);
  const data = prices.get(symbol);
  const isUp = (data?.changePercent24h ?? 0) >= 0;

  return (
    <div className="flex items-center justify-between py-2 border-b border-border/20 last:border-0">
      <span className="text-sm font-bold text-foreground">{symbol.split('/')[0]}</span>
      <div className="flex items-center gap-3">
        {data ? (
          <>
            <span className="text-sm tabular-nums text-foreground">${formatPrice(data.price)}</span>
            <span
              className={cn(
                'flex items-center gap-0.5 text-xs font-medium tabular-nums',
                isUp ? 'text-success' : 'text-destructive',
              )}
            >
              {isUp ? <ArrowUp size={11} weight="bold" /> : <ArrowDown size={11} weight="bold" />}
              {Math.abs(data.changePercent24h).toFixed(2)}%
            </span>
          </>
        ) : (
          <span className="h-4 w-28 bg-muted/30 animate-pulse rounded" />
        )}
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export function Intel() {
  const { regime, fearGreed, cycle, loading, error, refresh } = useIntelData();

  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <CircleNotch size={32} className="animate-spin text-primary" />
      </div>
    );
  }

  const compositeLabel = regime?.composite?.toUpperCase().replace(/_/g, ' ') ?? 'LOADING';
  const regScore = regime?.score ?? 0;

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* ── HEADER ── */}
      <header className="sticky top-0 z-40 border-b border-border/50 bg-background/90 backdrop-blur-md px-6 py-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="text-xs uppercase tracking-[0.25em] text-muted-foreground">Market Intelligence</div>
          {regime && (
            <div
              className={cn(
                'text-xs font-bold tracking-[0.2em] uppercase px-2 py-0.5 rounded border',
                regScore >= 70
                  ? 'text-success border-success/40 bg-success/10'
                  : regScore >= 45
                  ? 'text-warning border-warning/40 bg-warning/10'
                  : 'text-destructive border-destructive/40 bg-destructive/10',
              )}
            >
              {compositeLabel}
            </div>
          )}
        </div>
        <div className="flex items-center gap-4 text-xs font-mono text-muted-foreground">
          <span>{now.toUTCString().slice(17, 25)} UTC</span>
          <button
            onClick={refresh}
            className="text-primary hover:text-primary/80 transition-colors tracking-widest uppercase"
          >
            Refresh
          </button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">

        {error && (
          <div className="flex items-center gap-2 text-warning text-sm p-3 rounded-lg border border-warning/30 bg-warning/10">
            <Warning size={16} />
            {error} — showing cached data where available
          </div>
        )}

        {/* ── ROW 1: Regime overview ── */}
        <section className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard
            label="Market Regime"
            value={compositeLabel}
            sub={`Score: ${regScore}`}
            valueClass={regimeColor(regime?.composite ?? '')}
            accent
          />
          <StatCard
            label="Regime Score"
            value={`${regScore}/100`}
            valueClass={
              regScore >= 70 ? 'text-success' : regScore >= 45 ? 'text-warning' : 'text-destructive'
            }
          />
          <StatCard
            label="Cycle Phase"
            value={cycle?.phase?.replace(/_/g, ' ') ?? '—'}
            sub={`Confidence: ${cycle ? Math.round(cycle.confidence * 100) : '—'}%`}
            valueClass={
              cycle?.trade_bias === 'LONG'
                ? 'text-success'
                : cycle?.trade_bias === 'SHORT'
                ? 'text-destructive'
                : 'text-muted-foreground'
            }
          />
          <StatCard
            label="Trade Bias"
            value={cycle?.trade_bias ?? '—'}
            sub={cycle?.translation?.replace(/_/g, ' ')}
            valueClass={biasColor(cycle?.trade_bias ?? '')}
          />
        </section>

        {/* ── ROW 2: Regime dimensions + Fear&Greed + BTC dominance ── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

          {/* Dimensions */}
          <div className="rounded-lg border border-border/50 bg-card/60 p-4 backdrop-blur-sm">
            <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-3">Regime Dimensions</div>
            {regime?.dimensions ? (
              <>
                <DimensionRow label="Trend" value={regime.dimensions.trend} />
                <DimensionRow label="Volatility" value={regime.dimensions.volatility} />
                <DimensionRow label="Liquidity" value={regime.dimensions.liquidity} />
                <DimensionRow label="Risk Appetite" value={regime.dimensions.risk_appetite} />
                <DimensionRow label="Derivatives" value={regime.dimensions.derivatives} />
              </>
            ) : (
              <div className="text-xs text-muted-foreground">Awaiting regime data…</div>
            )}
          </div>

          {/* Fear & Greed */}
          {fearGreed ? (
            <div className="space-y-3">
              <FearGreedGauge value={fearGreed.value} />
              {fearGreed.bottom_line && (
                <div className="rounded-lg border border-border/40 bg-card/40 p-3 text-xs text-muted-foreground leading-relaxed">
                  {fearGreed.bottom_line}
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-lg border border-border/50 bg-card/60 p-4 flex items-center justify-center text-muted-foreground text-sm">
              Fear &amp; Greed unavailable
            </div>
          )}

          {/* BTC Dominance + Stoch RSI */}
          <div className="space-y-3">
            {regime?.dominance && (
              <div className="rounded-lg border border-border/50 bg-card/60 p-4 backdrop-blur-sm">
                <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-3">Dominance</div>
                <DimensionRow label="BTC.D" value={`${regime.dominance.btc_d?.toFixed(1) ?? '—'}%`} />
                <DimensionRow label="ALT.D" value={`${regime.dominance.alt_d?.toFixed(1) ?? '—'}%`} />
                <DimensionRow label="USDT.D" value={`${regime.dominance.stable_d?.toFixed(1) ?? '—'}%`} />
              </div>
            )}
            {cycle?.stochastic_rsi && (
              <div className="rounded-lg border border-border/50 bg-card/60 p-4 backdrop-blur-sm">
                <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-3">
                  BTC Stochastic RSI
                </div>
                <DimensionRow label="K" value={cycle.stochastic_rsi.k?.toFixed(1) ?? '—'} />
                <DimensionRow label="D" value={cycle.stochastic_rsi.d?.toFixed(1) ?? '—'} />
                <DimensionRow label="Zone" value={cycle.stochastic_rsi.zone} />
              </div>
            )}
          </div>
        </div>

        {/* ── ROW 3: Cycle interpretation + Live prices ── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

          {/* Cycle interpretation */}
          <div className="rounded-lg border border-border/50 bg-card/60 p-4 backdrop-blur-sm">
            <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-3">
              Cycle Analysis
            </div>
            {cycle?.interpretation ? (
              <div className="space-y-2">
                {cycle.interpretation.summary && (
                  <div
                    className={cn(
                      'text-sm font-bold uppercase tracking-wide',
                      cycle.interpretation.severity === 'bullish'
                        ? 'text-success'
                        : cycle.interpretation.severity === 'bearish'
                        ? 'text-destructive'
                        : cycle.interpretation.severity === 'caution'
                        ? 'text-warning'
                        : 'text-muted-foreground',
                    )}
                  >
                    {cycle.interpretation.summary}
                  </div>
                )}
                <ul className="space-y-1.5 mt-2">
                  {cycle.interpretation.messages.map((msg, i) => (
                    <li key={i} className="flex gap-2 text-xs text-foreground/80 leading-snug">
                      <span className="text-primary mt-0.5 shrink-0">◉</span>
                      {msg}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="text-xs text-muted-foreground">Cycle data loading…</div>
            )}
          </div>

          {/* Live prices */}
          <div className="rounded-lg border border-border/50 bg-card/60 p-4 backdrop-blur-sm">
            <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-3">
              Live Prices
            </div>
            {['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'AVAX/USDT'].map((sym) => (
              <PriceRow key={sym} symbol={sym} />
            ))}
          </div>
        </div>

        {/* ── ROW 4: Regime guidance ── */}
        {fearGreed?.risk_text && (
          <div className="rounded-lg border border-warning/30 bg-warning/5 p-4">
            <div className="text-[10px] uppercase tracking-[0.2em] text-warning mb-2">Risk Assessment</div>
            <div className="text-sm text-foreground/90">{fearGreed.risk_text}</div>
          </div>
        )}

      </div>
    </div>
  );
}

export default Intel;
