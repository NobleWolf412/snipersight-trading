import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import type { ScanResult } from '@/utils/mockData';
import { RegimeIndicator } from '@/components/RegimeIndicator';
import { ConvictionBadge } from '@/components/ConvictionBadge';
import { TrendUp, TrendDown, Activity, Shield, Warning } from '@phosphor-icons/react';

interface DetailsModalProps {
  isOpen: boolean;
  onClose: () => void;
  result: ScanResult;
}

export function DetailsModal({ isOpen, onClose, result }: DetailsModalProps) {
  const formatNum = (value: number | undefined | null, digits = 2) => {
    if (value === undefined || value === null || Number.isNaN(value as number)) return '-';
    try {
      return (value as number).toFixed(digits);
    } catch {
      return '-';
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh]">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">Signal Details: {result.pair}</DialogTitle>
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
                    ${formatNum(result.entryZone.low, 2)} - ${formatNum(result.entryZone.high, 2)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Stop Loss</div>
                  <div className="font-mono text-sm text-red-500">${formatNum(result.stopLoss, 2)}</div>
                </div>
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
                          <div className="font-mono text-sm font-semibold">${formatNum(price, 2)}</div>
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
