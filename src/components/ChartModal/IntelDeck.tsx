import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Target, ShieldWarning, Brain, TrendUp, Wallet, ArrowRight, Copy } from '@phosphor-icons/react';
import type { ScanResult } from '@/utils/mockData';
import { getSignalTier } from '@/utils/signalTiers';

interface IntelDeckProps {
    result: ScanResult;
}

export function IntelDeck({ result }: IntelDeckProps) {
    const tier = getSignalTier(result.confidenceScore);
    const profitPotential = ((result.takeProfits[2] - result.entryZone.high) / result.entryZone.high * 100);
    const riskPercent = ((result.entryZone.high - result.stopLoss) / result.entryZone.high * 100);

    return (
        <div className="h-full flex flex-col bg-card/50">
            {/* 1. The Numbers (Top Fixed) */}
            <div className="p-4 border-b border-border/40 space-y-4 bg-background/40">
                <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1">
                        <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Entry Zone</span>
                        <div className="font-mono font-bold text-lg text-primary">
                            ${result.entryZone.low.toFixed(4)} - {result.entryZone.high.toFixed(4)}
                        </div>
                    </div>
                    <div className="space-y-1 text-right">
                        <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Stop Loss</span>
                        <div className="font-mono font-bold text-lg text-destructive">
                            ${result.stopLoss.toFixed(4)}
                        </div>
                    </div>
                </div>

                <div className="space-y-2">
                    <div className="flex justify-between items-center text-xs">
                        <span className="text-muted-foreground">TP1 (${result.takeProfits[0].toFixed(4)})</span>
                        <span className="font-mono text-success">1:{((result.takeProfits[0] - result.entryZone.high) / (result.entryZone.high - result.stopLoss)).toFixed(1)}R</span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                        <span className="text-muted-foreground">TP2 (${result.takeProfits[1].toFixed(4)})</span>
                        <span className="font-mono text-success">1:{((result.takeProfits[1] - result.entryZone.high) / (result.entryZone.high - result.stopLoss)).toFixed(1)}R</span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                        <span className="text-muted-foreground">TP3 (${result.takeProfits[2].toFixed(4)})</span>
                        <span className="font-mono text-success">1:{((result.takeProfits[2] - result.entryZone.high) / (result.entryZone.high - result.stopLoss)).toFixed(1)}R</span>
                    </div>
                </div>
            </div>

            {/* 2. Signal Brief (Scrollable Content) */}
            <ScrollArea className="flex-1">
                <div className="p-4 space-y-6">
                    {/* Setup Quality */}
                    <div className="space-y-3">
                        <h4 className="text-xs font-semibold flex items-center gap-2 text-accent">
                            <Brain size={14} />
                            SETUP INTELLIGENCE
                        </h4>

                        <div className="grid grid-cols-2 gap-2">
                            <div className="bg-muted/30 p-2 rounded border border-border/50">
                                <div className="text-[10px] text-muted-foreground">CONFIDENCE</div>
                                <div className={`text-lg font-bold font-mono ${tier.color}`}>
                                    {result.confidenceScore.toFixed(1)}%
                                </div>
                            </div>
                            <div className="bg-muted/30 p-2 rounded border border-border/50">
                                <div className="text-[10px] text-muted-foreground">EXPECTED VALUE</div>
                                <div className="text-lg font-bold font-mono text-foreground">
                                    {result.riskReward ? (result.riskReward * (result.confidenceScore / 100)).toFixed(2) : '-'}R
                                </div>
                            </div>
                        </div>

                        {/* Factor Tags */}
                        <div className="flex flex-wrap gap-1.5">
                            {result.orderBlocks.length > 0 && (
                                <Badge variant="outline" className="text-[10px] border-primary/30 text-primary">
                                    {result.orderBlocks.length} Order Blocks
                                </Badge>
                            )}
                            {result.fairValueGaps.length > 0 && (
                                <Badge variant="outline" className="text-[10px] border-accent/30 text-accent">
                                    {result.fairValueGaps.length} FVGs
                                </Badge>
                            )}
                            <Badge variant="outline" className="text-[10px] border-border text-muted-foreground">
                                {result.plan_type} Entry
                            </Badge>
                        </div>
                    </div>

                    {/* AI Analysis Brief */}
                    <div className="space-y-2">
                        <h4 className="text-xs font-semibold flex items-center gap-2 text-primary">
                            <TrendUp size={14} />
                            STRATEGY BRIEF
                        </h4>
                        <div className="text-xs text-muted-foreground leading-relaxed bg-muted/20 p-3 rounded-lg border border-border/40">
                            {result.rationale ? (
                                result.rationale.length > 300
                                    ? result.rationale.substring(0, 300) + '...'
                                    : result.rationale
                            ) : (
                                "Automated analysis indicates a confluence of factors supporting this setup. Review key levels and manage risk accordingly."
                            )}
                        </div>
                    </div>

                    {/* Risk Profile */}
                    <div className="space-y-3">
                        <h4 className="text-xs font-semibold flex items-center gap-2 text-destructive">
                            <ShieldWarning size={14} />
                            RISK PROFILE
                        </h4>
                        <div className="space-y-2">
                            <div className="flex justify-between text-xs">
                                <span>Risk Score</span>
                                <span className="font-mono font-bold">{result.riskScore.toFixed(1)}/10</span>
                            </div>
                            <Progress value={result.riskScore * 10} className="h-1.5 bg-muted" />
                            <p className="text-[10px] text-muted-foreground pt-1">
                                Max drawdown risk to stop loss is {riskPercent.toFixed(2)}%.
                                {result.riskScore > 7 && " High risk setup - reduce position size."}
                            </p>
                        </div>
                    </div>
                </div>
            </ScrollArea>

            {/* 3. Execution (Bottom Fixed) */}
            <div className="p-4 border-t border-border/40 bg-muted/10">
                <div className="grid grid-cols-2 gap-2 mb-2">
                    <Button className="w-full bg-accent text-accent-foreground hover:bg-accent/90">
                        <Wallet size={16} className="mr-2" />
                        Execute
                    </Button>
                    <Button variant="outline" className="w-full">
                        <Copy size={16} className="mr-2" />
                        Copy
                    </Button>
                </div>
                <div className="text-center">
                    <span className="text-[10px] text-muted-foreground">
                        Recommended Size: <span className="font-mono text-foreground">1.0%</span>
                    </span>
                </div>
            </div>
        </div>
    );
}
