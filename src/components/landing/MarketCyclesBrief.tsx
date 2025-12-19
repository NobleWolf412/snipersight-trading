import { useState, useEffect, useCallback } from 'react';
import {
  Clock,
  ChartLine,
  Warning,
  CheckCircle,
  Question,
  Activity,
} from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { api } from '@/utils/api';
import {
  CyclePhaseGraphic,
  TranslationGraphic,
  StochRSIGraphic,
  type CyclePhase,
  type Translation,
  type StochZone,
} from './CycleGraphics';

// Types matching the API response
interface CycleData {
  symbol: string;
  dcl: {
    days_since: number | null;
    confirmation: string;
    expected_window: { min_days: number; max_days: number };
  } | null;
  wcl: {
    days_since: number | null;
    confirmation: string;
    expected_window: { min_days: number; max_days: number };
  } | null;
  phase: CyclePhase;
  translation: Translation;
  trade_bias: 'LONG' | 'SHORT' | 'NEUTRAL';
  stochastic_rsi: {
    k: number | null;
    d: number | null;
    zone: StochZone;
  };
  timestamp: string;
}

export function MarketCyclesBrief() {
  const [cycleData, setCycleData] = useState<CycleData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCycleData = useCallback(async () => {
    try {
      const response = await api.getMarketCycles('BTCUSDT');
      if (response.data) {
        setCycleData(response.data);
        setError(null);
      } else if (response.error) {
        setError(response.error);
      }
    } catch (err) {
      setError('Cycle data unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCycleData();
    const interval = setInterval(fetchCycleData, 60000);
    return () => clearInterval(interval);
  }, [fetchCycleData]);

  // Loading state
  if (loading) {
    return (
      <div className="relative p-6 rounded-xl border border-border/40 bg-card/50 backdrop-blur-sm">
        <div className="flex items-center justify-center gap-3 py-4">
          <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <span className="text-sm tracking-wider text-muted-foreground">Analyzing cycles...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !cycleData) {
    return null; // Silently hide if no data
  }

  // Get confirmation status (check WCL first, fallback to DCL)
  const isConfirmed = (cycleData.wcl?.confirmation === 'confirmed') || (cycleData.dcl?.confirmation === 'confirmed');
  const translationStatus = cycleData.translation === 'UNKNOWN' ? 'pending' : 'identified';

  // Get StochRSI interpretation
  const getStochInterpretation = () => {
    const zone = cycleData.stochastic_rsi.zone;
    const k = cycleData.stochastic_rsi.k || 0;
    const d = cycleData.stochastic_rsi.d || 0;

    if (zone === 'oversold') {
      // Oversold = bullish reversal potential
      const crossingUp = k > d;
      return {
        signal: crossingUp ? 'Bullish Cross Forming' : 'Waiting for K/D Cross',
        description: crossingUp
          ? 'K line crossed above D - bullish momentum building'
          : 'Oversold zone - watch for K/D crossover for long entries',
        bias: 'LONG',
        color: 'text-success'
      };
    }

    if (zone === 'overbought') {
      // Overbought = bearish reversal potential
      const crossingDown = k < d;
      return {
        signal: crossingDown ? 'Bearish Cross Forming' : 'Waiting for K/D Cross',
        description: crossingDown
          ? 'K line crossed below D - bearish momentum building'
          : 'Overbought zone - watch for K/D crossover for short entries',
        bias: 'SHORT',
        color: 'text-destructive'
      };
    }

    // Neutral
    return {
      signal: 'Neutral Zone',
      description: 'No extreme reading - wait for clear signal',
      bias: 'NEUTRAL',
      color: 'text-muted-foreground'
    };
  };

  const stochInterp = getStochInterpretation();

  // Calculate WCL timing
  const wclDaysMin = cycleData.wcl?.expected_window.min_days || 0;
  const wclDaysMax = cycleData.wcl?.expected_window.max_days || 0;
  const wclText = wclDaysMax > 0 ? `${wclDaysMin}-${wclDaysMax} days` : 'Unknown';

  return (
    <div className="relative rounded-xl border border-border/40 bg-card/50 backdrop-blur-sm overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border/30 bg-muted/10 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ChartLine size={16} className="text-accent" weight="bold" />
          <span className="text-xs font-bold tracking-[0.15em]">CYCLE INTELLIGENCE</span>
          <span className="text-[10px] text-muted-foreground font-mono">BTC/USDT • WEEKLY</span>
        </div>
        <div className="flex items-center gap-2">
          {isConfirmed ? (
            <div className="flex items-center gap-1 text-[10px] text-success">
              <CheckCircle size={12} weight="fill" />
              <span>Confirmed</span>
            </div>
          ) : (
            <div className="flex items-center gap-1 text-[10px] text-warning">
              <Question size={12} weight="fill" />
              <span>Pending Confirmation</span>
            </div>
          )}
          <span className="text-[10px] text-muted-foreground font-mono">
            {new Date(cycleData.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      </div>

      {/* Visual Graphics Grid - Integrated Information */}
      <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* Column 1: Cycle Status (Phase & Timing) */}
        <div className="space-y-4 p-4 rounded-xl bg-muted/10 border border-border/20">
          <div className="flex items-center gap-2 mb-2">
            <Clock size={16} className="text-muted-foreground" />
            <span className="text-xs font-bold tracking-wider text-muted-foreground">CYCLE TIMING</span>
          </div>

          <div className="flex items-start gap-4">
            <div className="shrink-0">
              <TranslationGraphic translation={cycleData.translation} compact={true} />
            </div>

            <div className="flex-1 space-y-3">
              <div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">CURRENT PHASE</div>
                <div className={cn(
                  "text-lg font-bold",
                  cycleData.phase === 'MARKUP' && 'text-success',
                  cycleData.phase === 'MARKDOWN' && 'text-destructive',
                  cycleData.phase === 'ACCUMULATION' && 'text-accent',
                  cycleData.phase === 'DISTRIBUTION' && 'text-warning'
                )}>
                  {cycleData.phase}
                </div>
                <div className="text-xs text-muted-foreground leading-relaxed">
                  {cycleData.phase === 'ACCUMULATION' && 'Smart money accumulating'}
                  {cycleData.phase === 'MARKUP' && 'Price discovery mode'}
                  {cycleData.phase === 'DISTRIBUTION' && 'Profit taking active'}
                  {cycleData.phase === 'MARKDOWN' && 'Correction in progress'}
                </div>
              </div>

              <div className="pt-3 border-t border-border/10">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] text-muted-foreground">STRUCTURE</span>
                  <span className={cn(
                    "text-xs font-bold",
                    cycleData.translation === 'RIGHT_TRANSLATED' ? 'text-success' : 'text-warning'
                  )}>
                    {cycleData.translation === 'RIGHT_TRANSLATED' ? 'BULLISH' : 'NEUTRAL/BEARISH'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-muted-foreground">NEXT WCL WINDOW</span>
                  <span className="text-xs font-bold text-accent">⏳ {wclText}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Column 2: Momentum & Bias */}
        <div className="space-y-4 p-4 rounded-xl bg-muted/10 border border-border/20">
          <div className="flex items-center gap-2 mb-2">
            <Activity size={16} className="text-muted-foreground" />
            <span className="text-xs font-bold tracking-wider text-muted-foreground">MOMENTUM & BIAS</span>
          </div>

          <div className="flex items-start gap-4">
            <div className="shrink-0">
              <StochRSIGraphic
                k={cycleData.stochastic_rsi.k}
                d={cycleData.stochastic_rsi.d}
                zone={cycleData.stochastic_rsi.zone}
                compact={true}
              />
            </div>

            <div className="flex-1 space-y-3">
              <div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">STOCH RSI signal</div>
                <div className={cn("text-lg font-bold", stochInterp.color)}>
                  {stochInterp.signal}
                </div>
                <div className="text-xs text-muted-foreground leading-relaxed">
                  {stochInterp.description}
                </div>
              </div>

              <div className="pt-3 border-t border-border/10">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-muted-foreground">TRADING BIAS</span>
                  <div className={cn(
                    "px-2 py-0.5 rounded text-xs font-bold",
                    stochInterp.bias === 'LONG' ? 'bg-success/20 text-success' :
                      stochInterp.bias === 'SHORT' ? 'bg-destructive/20 text-destructive' : 'bg-muted/30 text-muted-foreground'
                  )}>
                    {stochInterp.bias} ENTRIES
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-border/30 bg-muted/5 flex items-center justify-center">
        <span className="text-[10px] text-muted-foreground">Based on Camel Finance methodology</span>
      </div>
    </div>
  );
}
