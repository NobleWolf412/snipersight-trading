import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { TrendUp, TrendDown, Minus, Target, ShieldWarning, ChartBar } from '@phosphor-icons/react';
import type { ScanResult } from '@/utils/mockData';
import { getSignalTier } from '@/utils/signalTiers';
import { RegimeIndicator } from '@/components/RegimeIndicator';

interface ComparisonModalProps {
    isOpen: boolean;
    onClose: () => void;
    results: ScanResult[];
    regimes: Record<string, any>;
}

export function ComparisonModal({ isOpen, onClose, results, regimes }: ComparisonModalProps) {
    if (!results || results.length < 2) return null;

    // Limit to 3 items for display sanity
    const items = results.slice(0, 3);

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-5xl h-[90vh] flex flex-col p-0 overflow-hidden">
                <DialogHeader className="p-6 pb-2 border-b border-border/40 shrink-0">
                    <DialogTitle className="flex items-center gap-2">
                        <ChartBar className="text-accent" size={24} />
                        Tactical Comparison
                    </DialogTitle>
                    <DialogDescription>
                        Side-by-side analysis of {items.length} targets
                    </DialogDescription>
                </DialogHeader>

                <ScrollArea className="flex-1">
                    <div className="grid grid-cols-[120px_1fr] min-w-[800px]">
                        {/* Labels Column */}
                        <div className="border-r border-border/40 bg-muted/10">
                            {/* Header Spacer */}
                            <div className="h-40 border-b border-border/40 flex items-center justify-end px-4 text-xs font-semibold text-muted-foreground">
                                ASSET
                            </div>

                            {/* Metrics Rows */}
                            <div className="flex flex-col">
                                <div className="h-16 border-b border-border/40 flex items-center justify-end px-4 text-xs font-medium text-muted-foreground">Confidence</div>
                                <div className="h-16 border-b border-border/40 flex items-center justify-end px-4 text-xs font-medium text-muted-foreground">Bias</div>
                                <div className="h-16 border-b border-border/40 flex items-center justify-end px-4 text-xs font-medium text-muted-foreground">R:R Ratio</div>
                                <div className="h-16 border-b border-border/40 flex items-center justify-end px-4 text-xs font-medium text-muted-foreground">Max Risk</div>
                                <div className="h-32 border-b border-border/40 flex items-center justify-end px-4 text-xs font-medium text-muted-foreground">Structure</div>
                                <div className="h-24 border-b border-border/40 flex items-center justify-end px-4 text-xs font-medium text-muted-foreground">Regime</div>
                                <div className="h-40 flex items-center justify-end px-4 text-xs font-medium text-muted-foreground">Key Levels</div>
                            </div>
                        </div>

                        {/* Data Columns */}
                        <div className={`grid grid-cols-${items.length} divide-x divide-border/40`}>
                            {items.map((result) => {
                                const tier = getSignalTier(result.confidenceScore);
                                const riskPct = ((result.entryZone.high - result.stopLoss) / result.entryZone.high * 100);
                                const profitPct = ((result.takeProfits[2] - result.entryZone.high) / result.entryZone.high * 100);
                                const regime = regimes[result.pair] || result.regime;

                                return (
                                    <div key={result.id} className="flex flex-col min-w-[200px]">
                                        {/* Header */}
                                        <div className="h-40 p-4 border-b border-border/40 flex flex-col items-center justify-center gap-2 bg-muted/5">
                                            <div className="text-xl font-bold font-mono">{result.pair}</div>
                                            <Badge variant="outline" className={`${tier.color} bg-background`}>
                                                {tier.tier} TIER
                                            </Badge>
                                            <div className="flex gap-2 mt-1">
                                                <Badge variant="secondary" className="text-[10px]">
                                                    {result.classification}
                                                </Badge>
                                            </div>
                                        </div>

                                        {/* Confidence Row */}
                                        <div className="h-16 p-3 border-b border-border/40 flex flex-col justify-center">
                                            <div className="flex items-center justify-between mb-1.5">
                                                <span className={`text-lg font-bold font-mono ${tier.color}`}>
                                                    {result.confidenceScore.toFixed(0)}%
                                                </span>
                                            </div>
                                            <Progress value={result.confidenceScore} className="h-2" />
                                        </div>

                                        {/* Bias Row */}
                                        <div className="h-16 p-3 border-b border-border/40 flex items-center justify-center">
                                            {result.trendBias === 'BULLISH' ? (
                                                <Badge variant="outline" className="bg-success/20 text-success border-success/50 px-3 py-1">
                                                    <TrendUp weight="bold" className="mr-1" /> LONG
                                                </Badge>
                                            ) : result.trendBias === 'BEARISH' ? (
                                                <Badge variant="outline" className="bg-destructive/20 text-destructive border-destructive/50 px-3 py-1">
                                                    <TrendDown weight="bold" className="mr-1" /> SHORT
                                                </Badge>
                                            ) : (
                                                <Badge variant="outline" className="text-muted-foreground">
                                                    <Minus weight="bold" className="mr-1" /> NEUTRAL
                                                </Badge>
                                            )}
                                        </div>

                                        {/* R:R Row */}
                                        <div className="h-16 p-3 border-b border-border/40 flex flex-col justify-center items-center">
                                            <div className="text-xl font-mono font-bold text-accent">
                                                {result.riskReward ? result.riskReward.toFixed(2) : '-'}R
                                            </div>
                                            <div className="text-xs text-success font-medium">
                                                +{profitPct.toFixed(1)}% Max Gain
                                            </div>
                                        </div>

                                        {/* Risk Row */}
                                        <div className="h-16 p-3 border-b border-border/40 flex flex-col justify-center items-center">
                                            <div className="text-lg font-mono font-bold text-destructive">
                                                -{riskPct.toFixed(2)}%
                                            </div>
                                            <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                                                <ShieldWarning size={12} />
                                                Score: {result.riskScore.toFixed(1)}/10
                                            </div>
                                        </div>

                                        {/* Structure Row */}
                                        <div className="h-32 p-4 border-b border-border/40 flex flex-col gap-2 text-xs">
                                            <div className="flex justify-between items-center py-1 border-b border-border/30">
                                                <span className="text-muted-foreground">Order Blocks</span>
                                                <span className="font-mono font-bold">{result.orderBlocks.length}</span>
                                            </div>
                                            <div className="flex justify-between items-center py-1 border-b border-border/30">
                                                <span className="text-muted-foreground">FVGs</span>
                                                <span className="font-mono font-bold">{result.fairValueGaps.length}</span>
                                            </div>
                                            <div className="flex justify-between items-center py-1">
                                                <span className="text-muted-foreground">Entry Type</span>
                                                <span className="font-mono font-bold text-primary">{result.plan_type}</span>
                                            </div>
                                        </div>

                                        {/* Regime Row */}
                                        <div className="h-24 p-4 border-b border-border/40 flex items-center justify-center">
                                            <RegimeIndicator regime={regime} size="sm" />
                                        </div>

                                        {/* Key Levels Row */}
                                        <div className="h-40 p-4 flex flex-col justify-center gap-2">
                                            <div className="bg-success/10 rounded p-2 border border-success/20">
                                                <div className="text-[10px] text-success font-bold uppercase mb-1">Entry Zone</div>
                                                <div className="font-mono text-xs text-foreground">
                                                    ${result.entryZone.low.toFixed(4)} - ${result.entryZone.high.toFixed(4)}
                                                </div>
                                            </div>
                                            <div className="bg-destructive/10 rounded p-2 border border-destructive/20">
                                                <div className="text-[10px] text-destructive font-bold uppercase mb-1">Stop Loss</div>
                                                <div className="font-mono text-xs text-foreground">
                                                    ${result.stopLoss.toFixed(4)}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </ScrollArea>

                {/* Footer Action */}
                <div className="p-4 border-t border-border/40 bg-muted/10 flex justify-end">
                    <Button variant="outline" onClick={onClose}>
                        Close Comparison
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}
