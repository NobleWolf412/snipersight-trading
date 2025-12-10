import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import type { ScanResult } from '@/utils/mockData';
import { RegimeIndicator } from '@/components/RegimeIndicator';
import { ConvictionBadge } from '@/components/ConvictionBadge';
import { CycleIndicator } from '@/components/CycleIndicator';
import { TrendUp, TrendDown, Activity, Shield, Warning, Recycle, Target, Crosshair, Money, ChartLineUp } from '@phosphor-icons/react';
import { TargetIntelScorecard } from '@/components/TargetIntelScorecard/TargetIntelScorecard';

function formatAtrLabel(label: string, atrPct?: number) {
  const raw = (label || '').toString();
  const normalized = raw.trim().toUpperCase();
  // Hide opaque codes like "LOCAL53" or "SYMBOL53"; show friendly volatility bands
  const isOpaque = /^(LOCAL|SYMBOL)[0-9]+$/.test(normalized);
  if (isOpaque) {
    const pct = typeof atrPct === 'number' ? atrPct : undefined;
    if (typeof pct === 'number') {
      if (pct >= 3.0) return 'Volatility: Chaotic';
      if (pct >= 2.0) return 'Volatility: Elevated';
      if (pct >= 1.2) return 'Volatility: Normal';
      return 'Volatility: Compressed';
    }
    return 'Volatility: Unknown';
  }
  // Map known regime labels if provided by backend
  const map: Record<string, string> = {
    COMPRESSED: 'Volatility: Compressed',
    NORMAL: 'Volatility: Normal',
    ELEVATED: 'Volatility: Elevated',
    CHAOTIC: 'Volatility: Chaotic',
  };
  return map[normalized] || normalized;
}

interface DetailsModalProps {
  isOpen: boolean;
  onClose: () => void;
  result: ScanResult;
}

export function DetailsModal({ isOpen, onClose, result }: DetailsModalProps) {
  const adaptiveDigits = (v: number) => {
    if (v >= 1000) return 5; // large numbers - show more precision
    if (v >= 100) return 5;
    if (v >= 10) return 5;
    if (v >= 1) return 5; // mid-priced
    if (v >= 0.1) return 5; // low-priced
    if (v >= 0.01) return 6; // micro-priced
    return 7; // ultra low
  };
  const formatNum = (value: number | undefined | null, digits?: number) => {
    if (value === undefined || value === null || Number.isNaN(value as number)) return '-';
    const v = value as number;
    const d = typeof digits === 'number' ? digits : adaptiveDigits(v);
    try {
      return v.toFixed(d);
    } catch {
      return '-';
    }
  };

  const calculateRR = () => {
    try {
      const avgEntry = (result.entryZone.high + result.entryZone.low) / 2;
      const risk = Math.abs(avgEntry - result.stopLoss);
      const firstTarget = result.takeProfits && result.takeProfits.length > 0 ? result.takeProfits[0] : undefined;
      if (!firstTarget || risk <= 0) return 0;
      const reward = Math.abs(firstTarget - avgEntry);
      return reward / risk;
    } catch {
      return 0;
    }
  };

  const rrRatio = calculateRR();

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="w-full max-w-[85vw] lg:max-w-5xl max-h-[80vh] flex flex-col p-0 gap-0 overflow-hidden bg-background/95 backdrop-blur-xl border-border/60 shadow-2xl">
        <DialogHeader className="p-6 border-b border-border/40 shrink-0 bg-background/50">
          <div className="flex items-center justify-between pr-8">
            <div>
              <DialogTitle className="text-2xl font-bold flex items-center gap-3 tracking-tighter">
                <span className="text-primary">{result.pair}</span>
                <span className="text-muted-foreground font-normal text-lg">Analysis</span>
                {result.sniper_mode && (
                  <Badge variant="secondary" className="text-xs font-mono uppercase tracking-wider bg-secondary/50 border-secondary-foreground/20">
                    {result.sniper_mode}
                  </Badge>
                )}
              </DialogTitle>
              <DialogDescription className="mt-1 flex items-center gap-2">
                <span className="flex items-center gap-1.5">
                  <ChartLineUp size={14} />
                  Smart Money Concepts
                </span>
                <span className="text-muted-foreground/40">•</span>
                <span className="flex items-center gap-1.5">
                  <Crosshair size={14} />
                  Automated Planning
                </span>
              </DialogDescription>
            </div>

            {(() => {
              const metaEV = (result as any)?.metadata?.ev?.expected_value as number | undefined;
              let ev: number | undefined = undefined;
              if (typeof metaEV === 'number') {
                ev = metaEV;
              } else {
                try {
                  const score = typeof result.confidenceScore === 'number' ? result.confidenceScore : 0;
                  const pWin = Math.max(0.2, Math.min(0.85, score / 100.0));
                  const avgEntry = (result.entryZone.high + result.entryZone.low) / 2;
                  const risk = Math.abs(avgEntry - result.stopLoss);
                  const firstTarget = result.takeProfits && result.takeProfits.length > 0 ? result.takeProfits[0] : undefined;
                  if (firstTarget && risk > 0) {
                    const reward = Math.abs(firstTarget - avgEntry);
                    const R = reward / risk;
                    ev = pWin * R - (1 - pWin) * 1.0;
                  }
                } catch { }
              }
              if (ev === undefined) return null;
              const positive = ev >= 0;
              const cls = positive
                ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20 shadow-[0_0_10px_-3px_rgba(16,185,129,0.3)]'
                : 'bg-rose-500/10 text-rose-500 border-rose-500/20';
              return (
                <div className={`flex flex-col items-end px-3 py-1.5 rounded-md border ${cls}`}>
                  <span className="text-[10px] uppercase tracking-wider font-semibold opacity-80">Expected Value</span>
                  <span className="font-mono text-lg font-bold leading-none">{ev > 0 ? '+' : ''}{ev.toFixed(2)}R</span>
                </div>
              );
            })()}
          </div>
        </DialogHeader>

        <ScrollArea className="flex-1 bg-muted/5">
          <div className="p-4 lg:p-5 grid grid-cols-1 lg:grid-cols-12 gap-4 lg:gap-5">

            {/* LEFT COLUMN: Analysis & Scoring (5 cols) */}
            <div className="lg:col-span-5 space-y-4">
              {/* Target Intel Scorecard or Legacy Fallback */}
              {result.confluence_breakdown ? (
                <TargetIntelScorecard breakdown={result.confluence_breakdown} />
              ) : (
                <Card className="border-border/60 shadow-sm overflow-hidden">
                  <CardHeader className="bg-muted/10 pb-4 border-b border-border/40">
                    <CardTitle className="text-lg font-bold flex items-center gap-2">
                      <Shield size={20} className="text-primary" />
                      Signal Quality
                    </CardTitle>
                    <CardDescription>
                      Aggregated conviction metrics
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-6 space-y-6">
                    <div className="grid grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <label className="text-xs text-muted-foreground font-medium uppercase tracking-wider">Conviction Class</label>
                        <div>
                          {result.conviction_class && result.plan_type ? (
                            <ConvictionBadge conviction={result.conviction_class} planType={result.plan_type} size="lg" />
                          ) : (
                            <Badge variant="outline" className="text-muted-foreground">Unclassified</Badge>
                          )}
                        </div>
                      </div>
                      <div className="space-y-2">
                        <label className="text-xs text-muted-foreground font-medium uppercase tracking-wider">Confluence Score</label>
                        <div className="flex flex-col gap-1.5">
                          <div className="flex items-end gap-1.5">
                            <span className="text-3xl font-bold font-mono text-primary leading-none">
                              {formatNum(result.confidenceScore, 0)}
                            </span>
                            <span className="text-sm text-muted-foreground mb-0.5">%</span>
                          </div>
                          <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary rounded-full transition-all duration-500 ease-out"
                              style={{ width: `${typeof result.confidenceScore === 'number' ? result.confidenceScore : 0}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Fallback Rationale if available */}
                    {result.rationale && (
                      <div className="bg-muted/20 p-4 rounded-lg border border-border/40">
                        <h4 className="text-xs font-bold text-muted-foreground mb-2 flex items-center gap-1.5">
                          <Activity size={14} /> Logic Summary
                        </h4>
                        <p className="text-sm text-muted-foreground leading-relaxed">
                          {result.rationale.split('\n')[0]}...
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </div>

            {/* RIGHT COLUMN: Execution, Context, Cycle (7 cols) */}
            <div className="lg:col-span-7 space-y-4">

              {/* Top Row: Context & Regime */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Regime Card */}
                <Card className="border-border/60 shadow-sm h-full">
                  <CardHeader className="py-4 px-5 border-b border-border/40 bg-muted/10">
                    <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                      <Activity size={16} /> Market Context
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-5">
                    <div className="space-y-4">
                      <RegimeIndicator regime={result.regime} size="md" />
                      {result.regime && (
                        <div className="grid grid-cols-2 gap-3 text-xs">
                          <div className="bg-muted/30 p-2.5 rounded border border-border/30">
                            <span className="block text-muted-foreground mb-1">Global</span>
                            <span className="font-semibold text-foreground">{result.regime.global_regime?.composite || 'N/A'}</span>
                          </div>
                          <div className="bg-muted/30 p-2.5 rounded border border-border/30">
                            <span className="block text-muted-foreground mb-1">Local</span>
                            <span className="font-semibold text-foreground">
                              {result.regime.symbol_regime?.trend || 'N/A'} / {result.regime.symbol_regime?.volatility || 'N/A'}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>

                {/* Cycle/Bias Card */}
                <Card className="border-border/60 shadow-sm h-full">
                  <CardHeader className="py-4 px-5 border-b border-border/40 bg-muted/10">
                    <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                      <Recycle size={16} /> Cycle & Bias
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-5">
                    {result.cycle_context ? (
                      <CycleIndicator cycle={result.cycle_context} size="sm" />
                    ) : (
                      <div className="flex items-center justify-center h-20 text-muted-foreground text-sm italic">
                        No cycle data available
                      </div>
                    )}
                    <Separator className="my-3 opacity-50" />
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground font-medium uppercase">Trend Bias</span>
                      <Badge variant="outline" className={`px-2 py-0.5 ${result.trendBias === 'BULLISH' ? 'text-emerald-500 border-emerald-500/20 bg-emerald-500/5' : result.trendBias === 'BEARISH' ? 'text-rose-500 border-rose-500/20 bg-rose-500/5' : ''}`}>
                        {result.trendBias === 'BULLISH' ? <TrendUp size={14} className="mr-1.5" /> : result.trendBias === 'BEARISH' ? <TrendDown size={14} className="mr-1.5" /> : <Activity size={14} className="mr-1.5" />}
                        {result.trendBias}
                      </Badge>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Execution Card (Wide) */}
              <Card className="border-border/60 shadow-sm border-l-4 border-l-primary/60">
                <CardHeader className="py-4 px-6 border-b border-border/40 bg-gradient-to-r from-primary/5 to-transparent">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base font-bold flex items-center gap-2">
                      <Crosshair size={18} className="text-primary" />
                      Execution Plan
                    </CardTitle>
                    {/* Warning Badge for Missing Data */}
                    {result.missing_critical_timeframes && result.missing_critical_timeframes.length > 0 && (
                      <div className="flex items-center gap-1.5 text-amber-500 text-xs font-bold px-2 py-1 rounded bg-amber-500/10 border border-amber-500/20">
                        <Warning size={14} weight="fill" />
                        <span>Incomplete Data</span>
                      </div>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="p-6">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

                    {/* Entry */}
                    <div className="flex flex-col gap-1.5 p-3 rounded-lg hover:bg-muted/30 transition-colors">
                      <span className="text-xs text-muted-foreground font-medium uppercase tracking-wider flex items-center gap-1.5">
                        <Target size={14} /> Entry Zone
                      </span>
                      <div className="font-mono text-lg font-bold text-foreground">
                        ${formatNum(result.entryZone.low)} <span className="text-muted-foreground text-sm font-normal">to</span> ${formatNum(result.entryZone.high)}
                      </div>
                    </div>

                    {/* Stop */}
                    <div className="flex flex-col gap-1.5 p-3 rounded-lg hover:bg-muted/30 transition-colors">
                      <span className="text-xs text-muted-foreground font-medium uppercase tracking-wider flex items-center gap-1.5">
                        <Shield size={14} /> Stop Loss
                      </span>
                      <div className="font-mono text-lg font-bold text-rose-500">
                        ${formatNum(result.stopLoss)}
                      </div>
                    </div>

                    {/* RR */}
                    <div className="flex flex-col gap-1.5 p-3 rounded-lg hover:bg-muted/30 transition-colors">
                      <span className="text-xs text-muted-foreground font-medium uppercase tracking-wider flex items-center gap-1.5">
                        <Money size={14} /> Risk:Reward
                      </span>
                      <div className="font-mono text-lg font-bold text-emerald-500">
                        {rrRatio > 0 ? `${formatNum(rrRatio, 2)}:1` : 'N/A'}
                      </div>
                    </div>

                  </div>

                  {/* Liquidation Risk Footer */}
                  {result.liqPrice && (
                    <div className="mt-4 pt-4 border-t border-border/40 flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Warning size={14} /> Est. Liq: <span className="font-mono text-foreground">${formatNum(result.liqPrice)}</span>
                      </div>
                      {typeof result.liqCushionPct === 'number' && (
                        <div className={`px-2 py-0.5 rounded-full font-mono text-[10px] uppercase font-bold border ${result.liqRiskBand === 'high' ? 'bg-rose-500/10 text-rose-500 border-rose-500/20' : 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'}`}>
                          {formatNum(result.liqCushionPct, 1)}% Cushion
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Targets List */}
              <Card className="border-border/60 shadow-sm">
                <CardHeader className="py-4 px-5 border-b border-border/40 bg-muted/10">
                  <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                    Profit Objectives
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="divide-y divide-border/30">
                    {result.takeProfits.map((price, idx) => {
                      const percentGain = ((price - result.entryZone.high) / result.entryZone.high) * 100;
                      const isFirst = idx === 0;
                      return (
                        <div key={idx} className={`flex items-center justify-between px-6 py-4 hover:bg-muted/20 transition-colors ${isFirst ? 'bg-emerald-500/5' : ''}`}>
                          <div className="flex items-center gap-4">
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-mono font-bold border ${isFirst ? 'bg-emerald-500 text-white border-emerald-600' : 'bg-background text-muted-foreground border-border'}`}>
                              TP{idx + 1}
                            </div>
                            <div className="font-mono text-base font-semibold">
                              ${formatNum(price)}
                            </div>
                          </div>
                          <div className={`text-sm font-mono font-bold ${isFirst ? 'text-emerald-500' : 'text-muted-foreground'}`}>
                            +{formatNum(percentGain, 2)}%
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>

              {/* Raw Data (Collapsible) */}
              <div className="pt-2">
                <details className="group">
                  <summary className="flex items-center gap-2 text-xs font-bold text-muted-foreground uppercase tracking-wider cursor-pointer hover:text-primary transition-colors p-2 rounded hover:bg-muted/20 w-fit">
                    <div className="w-4 h-4 rounded-sm border border-muted-foreground/50 flex items-center justify-center group-open:bg-muted-foreground group-open:text-background transition-all">
                      <span className="text-[10px] group-open:rotate-90 transition-transform">▸</span>
                    </div>
                    View Raw Analysis Data
                  </summary>
                  <Card className="mt-2 bg-muted/10 border-dashed">
                    <CardContent className="p-4">
                      <pre className="text-[10px] font-mono text-muted-foreground overflow-x-auto max-h-[300px] overflow-y-auto">
                        {JSON.stringify(result, null, 2)}
                      </pre>
                    </CardContent>
                  </Card>
                </details>
              </div>

            </div>
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
