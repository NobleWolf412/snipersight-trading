import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import type { ScanResult } from '@/utils/mockData';
import { RegimeIndicator } from '@/components/RegimeIndicator';
import { ConvictionBadge } from '@/components/ConvictionBadge';
import { CycleIndicator } from '@/components/CycleIndicator';
import { TrendUp, TrendDown, Activity, Shield, Warning, Recycle } from '@phosphor-icons/react';

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

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh]">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <DialogTitle className="text-xl font-bold">Signal Details: {result.pair}</DialogTitle>
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
                } catch {}
              }
              if (ev === undefined) return null;
              const positive = ev >= 0;
              const cls = positive ? 'bg-success/20 text-success border-success/50' : 'bg-destructive/20 text-destructive border-destructive/50';
              return (
                <Badge variant="outline" className={`font-mono font-bold ${cls}`}>EV {ev.toFixed(2)}</Badge>
              );
            })()}
          </div>
          <DialogDescription>Complete Smart Money Concepts analysis</DialogDescription>
        </DialogHeader>

        <ScrollArea className="h-[600px] pr-4">
          <div className="space-y-6">
            {/* Signal Quality Section */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Signal Quality</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <div className="text-xs text-muted-foreground">Conviction Class</div>
                  {result.conviction_class && result.plan_type ? (
                    <ConvictionBadge conviction={result.conviction_class} planType={result.plan_type} size="md" />
                  ) : (
                    <span className="text-sm text-muted-foreground">Not classified</span>
                  )}
                </div>
                <div className="space-y-2">
                  <div className="text-xs text-muted-foreground">Confidence Score</div>
                  <div className="flex items-center gap-2">
                    <div className="w-32 bg-muted rounded-full h-3">
                      <div
                        className="bg-accent h-3 rounded-full transition-all duration-500"
                        style={{ width: `${typeof result.confidenceScore === 'number' ? result.confidenceScore : 0}%` }}
                      />
                    </div>
                    <span className="text-lg font-bold font-mono text-accent">{formatNum(result.confidenceScore, 0)}%</span>
                  </div>
                  <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
                    <div className="bg-muted/40 rounded p-2">
                      <div className="text-muted-foreground">Confluence</div>
                      <div className="font-mono text-sm">
                        {(() => {
                          const fromAnalysis = (result as any)?.analysis?.confluence_score as number | undefined;
                          const score = typeof fromAnalysis === 'number' ? fromAnalysis : result.confidenceScore;
                          return formatNum(score, 0);
                        })()}%
                      </div>
                    </div>
                    <div className="bg-muted/40 rounded p-2">
                      <div className="text-muted-foreground">R:R</div>
                      <div className="font-mono text-sm">
                        {(() => {
                          const rr = (result as any)?.analysis?.risk_reward as number | undefined;
                          if (typeof rr === 'number' && rr > 0) return `${formatNum(rr, 2)}:1`;
                          // Fallback to local computation
                          const avgEntry = (result.entryZone.high + result.entryZone.low) / 2;
                          const risk = Math.abs(avgEntry - result.stopLoss);
                          const firstTarget = result.takeProfits && result.takeProfits.length > 0 ? result.takeProfits[0] : undefined;
                          if (!firstTarget || risk <= 0) return '-';
                          const reward = Math.abs(firstTarget - avgEntry);
                          return `${formatNum(reward / risk, 2)}:1`;
                        })()}
                      </div>
                    </div>
                    <div className="bg-muted/40 rounded p-2">
                      <div className="text-muted-foreground">EV</div>
                      <div className="font-mono text-sm">
                        {(() => {
                          const ev = (result as any)?.analysis?.expected_value as number | undefined;
                          if (typeof ev === 'number') return formatNum(ev, 2);
                          // Fallback approximation (existing logic)
                          try {
                            const score = typeof result.confidenceScore === 'number' ? result.confidenceScore : 0;
                            const pWin = Math.max(0.35, Math.min(0.70, 0.35 + (score / 100.0) * (0.70 - 0.35)));
                            const avgEntry = (result.entryZone.high + result.entryZone.low) / 2;
                            const risk = Math.abs(avgEntry - result.stopLoss);
                            const firstTarget = result.takeProfits && result.takeProfits.length > 0 ? result.takeProfits[0] : undefined;
                            if (!firstTarget || risk <= 0) return '-';
                            const reward = Math.abs(firstTarget - avgEntry);
                            const R = reward / risk;
                            const evCalc = pWin * R - (1 - pWin) * 1.0;
                            return `${evCalc.toFixed(2)}`;
                          } catch { return '-'; }
                        })()}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <Separator />

            {/* Market Regime Section */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Market Context</h3>
              <RegimeIndicator regime={result.regime} size="lg" />
              {result.regime && (
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Global Regime:</span>{' '}
                    <Badge variant="outline" className="ml-2">
                      {result.regime.global_regime?.composite || 'N/A'}
                    </Badge>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Symbol Regime:</span>{' '}
                    <Badge variant="outline" className="ml-2">
                      {result.regime.symbol_regime?.trend || 'N/A'} / {result.regime.symbol_regime?.volatility || 'N/A'}
                    </Badge>
                  </div>
                </div>
              )}
            </div>

            <Separator />

            {/* Cycle Theory Context (Phase 7) */}
            {result.cycle_context && (
              <>
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                    <Recycle size={16} weight="bold" />
                    Cycle Analysis
                  </h3>
                  <CycleIndicator cycle={result.cycle_context} size="md" />
                  {result.reversal_context && (
                    <div className="bg-muted/40 rounded-lg p-3 mt-2">
                      <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
                        Reversal Context
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">Structure Broken:</span>
                          <Badge variant="outline" className={result.reversal_context.structure_broken ? 'text-success' : 'text-muted-foreground'}>
                            {result.reversal_context.structure_broken ? 'Yes' : 'No'}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">Volume Displacement:</span>
                          <Badge variant="outline" className={result.reversal_context.volume_displacement ? 'text-success' : 'text-muted-foreground'}>
                            {result.reversal_context.volume_displacement ? 'Yes' : 'No'}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">At Cycle Extreme:</span>
                          <Badge variant="outline" className={result.reversal_context.at_cycle_extreme ? 'text-warning' : 'text-muted-foreground'}>
                            {result.reversal_context.at_cycle_extreme ? 'Yes' : 'No'}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">Reversal Score:</span>
                          <Badge variant="outline" className="font-mono text-accent">
                            {result.reversal_context.reversal_score}%
                          </Badge>
                        </div>
                      </div>
                      {result.reversal_context.reversal_rationale && (
                        <div className="text-sm text-muted-foreground mt-2 italic">
                          {result.reversal_context.reversal_rationale}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                <Separator />
              </>
            )}

            {/* Critical Timeframes Warning */}
            {result.missing_critical_timeframes && result.missing_critical_timeframes.length > 0 && (
              <>
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-warning uppercase tracking-wider flex items-center gap-2">
                    <Warning size={16} weight="fill" />
                    Missing Critical Timeframes
                  </h3>
                  <div className="bg-warning/10 border border-warning/30 rounded-lg p-3">
                    <div className="flex flex-wrap gap-2">
                      {result.missing_critical_timeframes.map((tf) => (
                        <Badge key={tf} variant="outline" className="border-warning text-warning">
                          {tf}
                        </Badge>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground mt-2">
                      Signal generated without complete timeframe coverage - exercise caution
                    </p>
                  </div>
                </div>
                <Separator />
              </>
            )}

            {/* Trade Setup Section */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Trade Setup</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Trend Bias</div>
                  <Badge variant="outline" className={result.trendBias === 'BULLISH' ? 'text-green-500' : result.trendBias === 'BEARISH' ? 'text-red-500' : ''}>
                    {result.trendBias === 'BULLISH' ? <TrendUp size={14} className="mr-1" /> : result.trendBias === 'BEARISH' ? <TrendDown size={14} className="mr-1" /> : <Activity size={14} className="mr-1" />}
                    {result.trendBias}
                  </Badge>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Classification</div>
                  <Badge variant="outline">{result.classification}</Badge>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Entry Range</div>
                  <div className="font-mono text-sm">
                    ${formatNum(result.entryZone.low)} - ${formatNum(result.entryZone.high)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Stop Loss</div>
                  <div className="font-mono text-sm text-red-500">${formatNum(result.stopLoss)}</div>
                </div>
                {result.liqPrice && (
                  <div className="col-span-2 mt-2 bg-muted/40 rounded p-3 border border-border/40">
                    <div className="flex flex-wrap items-center gap-3">
                      <div className="text-xs text-muted-foreground">Approx Liq Price:</div>
                      <div className="font-mono text-sm">${formatNum(result.liqPrice)}</div>
                      {typeof result.liqCushionPct === 'number' && (
                        <div className="flex items-center gap-1">
                          <span className="text-xs text-muted-foreground">Cushion</span>
                          <div
                            className={
                              `px-2 py-1 rounded text-xxs font-mono border ` +
                              (result.liqRiskBand === 'high'
                                ? 'bg-red-500/15 text-red-400 border-red-500/40'
                                : result.liqRiskBand === 'moderate'
                                ? 'bg-amber-500/15 text-amber-400 border-amber-500/40'
                                : 'bg-green-500/15 text-green-400 border-green-500/40')
                            }
                            title="(Stop − Liq) / (Entry − Liq) for longs; inverse for shorts"
                          >
                            {formatNum(result.liqCushionPct, 2)}% {result.liqRiskBand?.toUpperCase()}
                          </div>
                        </div>
                      )}
                      <div className="text-[10px] text-muted-foreground ml-auto">
                        Maintenance margin assumed 0.4%; actual exchange tiers vary.
                      </div>
                    </div>
                    {/* ATR Regime & Alt Stop Suggestion */}
                    {result.atrRegimeLabel && (
                      <div className="mt-3 flex flex-wrap items-center gap-3">
                        <div className="text-xs text-muted-foreground">ATR Regime:</div>
                        <Badge variant="outline" className="font-mono">
                          {formatAtrLabel(result.atrRegimeLabel, result.atrPct)} • {formatNum(result.atrPct, 2)}%
                        </Badge>
                        <div className="text-xs text-muted-foreground flex items-center gap-1">
                          <span>Buffer (used/recommended):</span>
                          <span className="font-mono">{formatNum(result.usedStopBufferAtr, 2)} ATR / {formatNum(result.recommendedStopBufferAtr, 2)} ATR</span>
                        </div>
                        {result.altStopLevel && (
                          <div className="flex items-center gap-2 ml-auto">
                            <Badge variant="outline" className="bg-warning/15 border-warning/40 text-warning font-mono" title={result.altStopRationale || 'Alternative stop suggestion'}>
                              ALT STOP ${formatNum(result.altStopLevel)}
                            </Badge>
                            <span className="text-[10px] text-muted-foreground">Suggestion due to high liquidation risk.</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
                <div className="col-span-2">
                  <div className="text-xs text-muted-foreground mb-1">Risk/Reward (computed)</div>
                  <div className="font-mono text-sm">
                    {(() => {
                      const avgEntry = (result.entryZone.high + result.entryZone.low) / 2;
                      const risk = Math.abs(avgEntry - result.stopLoss);
                      const firstTarget = result.takeProfits && result.takeProfits.length > 0 ? result.takeProfits[0] : undefined;
                      if (!firstTarget || risk <= 0) return '-';
                      const reward = Math.abs(firstTarget - avgEntry);
                        const rr = reward / risk;
                        return `${formatNum(rr, 2)}:1`;
                    })()}
                  </div>
                </div>
                <div className="col-span-2">
                  <div className="text-xs text-muted-foreground mb-1">Expected Value (approx)</div>
                  <div className="font-mono text-sm">
                    {(() => {
                      try {
                        const score = typeof result.confidenceScore === 'number' ? result.confidenceScore : 0;
                        const pWin = Math.max(0.35, Math.min(0.70, 0.35 + (score / 100.0) * (0.70 - 0.35)));
                        const avgEntry = (result.entryZone.high + result.entryZone.low) / 2;
                        const risk = Math.abs(avgEntry - result.stopLoss);
                        const firstTarget = result.takeProfits && result.takeProfits.length > 0 ? result.takeProfits[0] : undefined;
                        if (!firstTarget || risk <= 0) return '-';
                        const reward = Math.abs(firstTarget - avgEntry);
                        const R = reward / risk;
                        const ev = pWin * R - (1 - pWin) * 1.0;
                        return `${ev.toFixed(2)}`;
                      } catch {
                        return '-';
                      }
                    })()}
                  </div>
                </div>
              </div>
            </div>

            <Separator />

            {/* Targets Section */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Profit Targets</h3>
              <div className="space-y-2">
                {result.takeProfits.map((price, idx) => {
                  const percentGain = ((price - result.entryZone.high) / result.entryZone.high) * 100;
                  return (
                    <div key={idx} className="flex items-center justify-between bg-muted/50 rounded-lg p-3">
                      <div className="flex items-center gap-3">
                        <Badge variant="outline" className="w-8 h-8 flex items-center justify-center">
                          {idx + 1}
                        </Badge>
                        <div>
                          <div className="font-mono text-sm font-semibold">${formatNum(price)}</div>
                          <div className="text-xs text-muted-foreground">Target {idx + 1}</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-mono text-sm text-accent">{percentGain > 0 ? '+' : ''}{formatNum(percentGain, 1)}%</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <Separator />

            <Separator />

            {/* Raw Data Section (Collapsible) */}
            <details className="space-y-3">
              <summary className="text-sm font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer hover:text-foreground transition-colors">
                Raw Data (JSON)
              </summary>
              <pre className="bg-card border border-border rounded-lg p-4 text-xs font-mono overflow-x-auto mt-3">
                {JSON.stringify(result, null, 2)}
              </pre>
            </details>
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
