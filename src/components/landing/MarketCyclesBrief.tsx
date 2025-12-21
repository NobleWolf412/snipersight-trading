import {
  Clock,
  ChartLine,
  CheckCircle,
  Question,
  Pulse,
  Lightning,
} from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { useLandingData } from '@/context/LandingContext';
import {
  TranslationGraphic,
  StochRSIGraphic,
} from './CycleGraphics';

export function MarketCyclesBrief() {
  const { cycles: cycleData } = useLandingData();

  // If data isn't ready yet (shouldn't happen if parent handles loading, but good safety)
  if (!cycleData) {
    return null;
  }

  // Get confirmation status (check WCL first, fallback to DCL)
  const isConfirmed = (cycleData.wcl?.confirmation === 'confirmed') || (cycleData.dcl?.confirmation === 'confirmed');

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

  // WCL variables
  const wclDaysSince = cycleData.wcl?.days_since || 0;
  const wclStatus = cycleData.wcl?.confirmation || 'pending';

  // Temporal Intelligence
  const temporal = cycleData.temporal;
  const isHighProb = temporal?.is_active_window;
  const temporalScore = temporal?.score || 0;
  const dayName = temporal?.day_of_week || 'Unknown';

  return (
    <div className="relative rounded-xl border border-border/40 bg-card/50 backdrop-blur-sm overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border/30 bg-muted/10 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ChartLine size={16} className="text-accent" weight="bold" />
          <span className="text-xs font-bold tracking-[0.15em]">CYCLE INTELLIGENCE</span>
          <span className="text-xs text-muted-foreground font-mono">BTC/USDT • WEEKLY</span>
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
          {isHighProb && (
            <div className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-accent/20 border border-accent/40 text-[10px] text-accent font-bold animate-pulse">
              <Lightning size={12} weight="fill" />
              <span>HIGH PROB</span>
            </div>
          )}
          <span className="text-[10px] text-muted-foreground font-mono pl-2 border-l border-border/20">
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
            <span className="text-xs font-bold tracking-wider text-muted-foreground">WEEKLY CYCLE TIMING</span>
          </div>

          <div className="flex flex-col gap-4">
            {/* Temporal Timing (Day/Window) */}
            <div className="relative pt-2">
              <div className="flex justify-between text-[10px] text-muted-foreground mb-1 font-mono uppercase">
                <span className="flex items-center gap-1">
                  <span>Day {wclDaysSince}</span>
                  {dayName !== 'Unknown' && (
                    <span className={cn(
                      "text-[9px] px-1 rounded",
                      temporalScore >= 20 ? "bg-accent/10 text-accent" : "bg-muted/20"
                    )}>
                      {dayName.slice(0, 3).toUpperCase()} {temporalScore > 0 && `+${temporalScore}%`}
                    </span>
                  )}
                </span>
                <span>Window: {wclText}</span>
              </div>
              {/* Tactical Progress Track */}
              <div className="h-2 w-full bg-black/40 rounded-full border border-white/5 overflow-hidden flex relative">
                {/* Safe Zone */}
                {(() => {
                  const maxDisplay = wclDaysMax * 1.2;
                  const currentPct = Math.min((wclDaysSince / maxDisplay) * 100, 100);
                  const minWindowPct = (wclDaysMin / maxDisplay) * 100;
                  const maxWindowPct = (wclDaysMax / maxDisplay) * 100;

                  return (
                    <>
                      {/* Expected Window Zone */}
                      <div
                        className="absolute top-0 bottom-0 bg-accent/5 border-x border-accent/20"
                        style={{ left: `${minWindowPct}%`, width: `${maxWindowPct - minWindowPct}%` }}
                      />
                      {/* Progress Bar */}
                      <div
                        className={cn(
                          "h-full relative transition-all duration-1000",
                          wclDaysSince > wclDaysMax ? "bg-destructive" : "bg-accent"
                        )}
                        style={{ width: `${currentPct}%` }}
                      >
                        <div className="absolute right-0 top-0 bottom-0 w-[1px] bg-white/50 shadow-[0_0_8px_white]" />
                      </div>
                    </>
                  );
                })()}
              </div>
            </div>

            {/* Translation Graphic (Visualizing Weekly Structure) */}
            <div className="pt-2">
              <TranslationGraphic
                translation={cycleData.translation}
                compact={true}
                timeframeLabel="WEEKLY CYCLE STRUCTURE"
              />
              <div className="mt-2 flex items-center justify-between text-[10px] text-muted-foreground uppercase tracking-widest px-1">
                <span>PHASE:</span>
                <span className={cn(
                  "font-bold",
                  cycleData.phase === 'MARKUP' && 'text-success',
                  cycleData.phase === 'MARKDOWN' && 'text-destructive',
                  cycleData.phase === 'ACCUMULATION' && 'text-accent',
                  cycleData.phase === 'DISTRIBUTION' && 'text-warning'
                )}>{cycleData.phase}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Column 2: Momentum & Bias */}
        <div className="space-y-4 p-4 rounded-xl bg-muted/10 border border-border/20">
          <div className="flex items-center gap-2 mb-2">
            <Pulse size={16} className="text-muted-foreground" />
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

            <div className="flex-1 flex flex-col justify-center gap-4 py-2">
              <div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">STOCH RSI SIGNAL</div>
                <div className={cn("text-2xl font-bold leading-none tracking-tight", stochInterp.color)}>
                  {stochInterp.signal}
                </div>
                <div className="text-sm text-muted-foreground mt-2 leading-snug">
                  {stochInterp.description}
                </div>
              </div>

              <div className="pt-4 border-t border-border/10 w-full">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-muted-foreground uppercase tracking-widest">BIAS</span>
                  <div className={cn(
                    "px-3 py-1 rounded text-sm font-bold tracking-wide",
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
