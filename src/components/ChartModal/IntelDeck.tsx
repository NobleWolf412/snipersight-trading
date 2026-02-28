import { useState, useMemo } from 'react';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Input } from '@/components/ui/input';
import { ShieldWarning, Brain, TrendUp, Wallet, Copy, Calculator, Warning } from '@phosphor-icons/react';
import type { ScanResult } from '@/utils/mockData';
import { getSignalTier } from '@/utils/signalTiers';

interface IntelDeckProps {
    result: ScanResult;
}

export function IntelDeck({ result }: IntelDeckProps) {
    const tier = getSignalTier(result.confidenceScore);
    const riskPercent = ((result.entryZone.high - result.stopLoss) / result.entryZone.high * 100);

    // Position Sizing Calculator State
    const [accountBalance, setAccountBalance] = useState<string>('');
    const [riskDollars, setRiskDollars] = useState<string>('');
    const [leverage, setLeverage] = useState<string>(
        result.metadata?.leverage ? String(result.metadata.leverage) : '10'
    );

    const entryPrice = result.entryZone.high;
    const stopLoss = result.stopLoss;
    const lev = parseFloat(leverage) || 1;
    const balance = parseFloat(accountBalance) || 0;
    const riskAmt = parseFloat(riskDollars) || 0;
    const isLong = result.trendBias !== 'BEARISH';

    const calc = useMemo(() => {
        if (!entryPrice || !stopLoss || !balance || !riskAmt) return null;
        const stopDistancePct = Math.abs(entryPrice - stopLoss) / entryPrice;
        if (stopDistancePct === 0) return null;

        const positionSize = riskAmt / stopDistancePct;
        const marginRequired = positionSize / lev;
        const qty = positionSize / entryPrice;

        // Liquidation price (isolated margin, ~0.5% maintenance margin)
        const mmr = 0.005;
        const liqPrice = isLong
            ? entryPrice * (1 - (1 / lev) + mmr)
            : entryPrice * (1 + (1 / lev) - mmr);

        const liqCushionPct = Math.abs(liqPrice - entryPrice) / entryPrice * 100;

        const dir = isLong ? 1 : -1;
        const tp1Profit = (result.takeProfits[0] - entryPrice) / entryPrice * positionSize * dir;
        const tp2Profit = (result.takeProfits[1] - entryPrice) / entryPrice * positionSize * dir;
        const tp3Profit = (result.takeProfits[2] - entryPrice) / entryPrice * positionSize * dir;

        const riskPct = (riskAmt / balance) * 100;

        return {
            positionSize,
            marginRequired,
            qty,
            liqPrice,
            liqCushionPct,
            tp1Profit,
            tp2Profit,
            tp3Profit,
            riskPct,
            stopDistancePct: stopDistancePct * 100,
        };
    }, [accountBalance, riskDollars, leverage, entryPrice, stopLoss, result, isLong, lev, balance, riskAmt]);

    const liqWarning = calc && calc.liqCushionPct < 5;
    const liqDanger = calc && calc.liqCushionPct < 2;

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
                        <span className="font-mono text-green-400">1:{((result.takeProfits[0] - result.entryZone.high) / (result.entryZone.high - result.stopLoss)).toFixed(1)}R</span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                        <span className="text-muted-foreground">TP2 (${result.takeProfits[1].toFixed(4)})</span>
                        <span className="font-mono text-green-400">1:{((result.takeProfits[1] - result.entryZone.high) / (result.entryZone.high - result.stopLoss)).toFixed(1)}R</span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                        <span className="text-muted-foreground">TP3 (${result.takeProfits[2].toFixed(4)})</span>
                        <span className="font-mono text-green-400">1:{((result.takeProfits[2] - result.entryZone.high) / (result.entryZone.high - result.stopLoss)).toFixed(1)}R</span>
                    </div>
                </div>
            </div>

            {/* 2. Scrollable Content */}
            <ScrollArea className="flex-1">
                <div className="p-4 space-y-6">

                    {/* ── POSITION CALCULATOR ── */}
                    <div className="space-y-3">
                        <h4 className="text-xs font-semibold flex items-center gap-2 text-yellow-400 uppercase tracking-wider">
                            <Calculator size={14} />
                            POSITION CALCULATOR
                        </h4>

                        <div className="grid grid-cols-3 gap-2">
                            <div className="space-y-1.5">
                                <label className="text-[10px] text-muted-foreground uppercase px-1">Balance ($)</label>
                                <Input
                                    className="h-10 text-xs font-mono bg-muted/30 border-border/50 px-3"
                                    placeholder="10000"
                                    value={accountBalance}
                                    onChange={e => setAccountBalance(e.target.value)}
                                    type="number"
                                    min="0"
                                />
                            </div>
                            <div className="space-y-1.5">
                                <label className="text-[10px] text-muted-foreground uppercase px-1">Risk ($)</label>
                                <Input
                                    className="h-10 text-xs font-mono bg-muted/30 border-border/50 px-3"
                                    placeholder="100"
                                    value={riskDollars}
                                    onChange={e => setRiskDollars(e.target.value)}
                                    type="number"
                                    min="0"
                                />
                            </div>
                            <div className="space-y-1.5">
                                <label className="text-[10px] text-muted-foreground uppercase px-1">Leverage</label>
                                <Input
                                    className="h-10 text-xs font-mono bg-muted/30 border-border/50 px-3"
                                    placeholder="10"
                                    value={leverage}
                                    onChange={e => setLeverage(e.target.value)}
                                    type="number"
                                    min="1"
                                    max="125"
                                />
                            </div>
                        </div>

                        {calc ? (
                            <div className="space-y-2 bg-muted/20 rounded-lg p-3 border border-border/40">

                                {calc.riskPct > 3 && (
                                    <div className="flex items-center gap-1.5 text-[10px] text-yellow-400 bg-yellow-400/10 px-2 py-1 rounded border border-yellow-400/20">
                                        <Warning size={12} />
                                        Risk is {calc.riskPct.toFixed(1)}% of account — above recommended 1–2%
                                    </div>
                                )}

                                <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Position Size</span>
                                        <span className="font-mono font-bold">${calc.positionSize.toFixed(2)}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Margin Used</span>
                                        <span className="font-mono font-bold">${calc.marginRequired.toFixed(2)}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Qty</span>
                                        <span className="font-mono font-bold">{calc.qty.toFixed(4)}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Stop Dist.</span>
                                        <span className="font-mono font-bold">{calc.stopDistancePct.toFixed(2)}%</span>
                                    </div>
                                </div>

                                {/* Liquidation Price Block */}
                                <div className={`mt-1.5 p-3 rounded-lg border flex flex-col gap-2 ${liqDanger
                                    ? 'border-red-500/50 bg-red-500/10'
                                    : liqWarning
                                        ? 'border-yellow-400/40 bg-yellow-400/10'
                                        : 'border-orange-500/30 bg-orange-500/5'
                                    }`}>
                                    <div className="flex justify-between items-center">
                                        <span className={`text-[10px] uppercase tracking-wider font-semibold ${liqDanger ? 'text-red-400' : liqWarning ? 'text-yellow-400' : 'text-orange-400'
                                            }`}>
                                            {liqDanger ? '⚠ LIQ DANGER' : liqWarning ? '⚠ LIQ NEARBY' : 'Liquidation Price'}
                                        </span>
                                        <span className={`font-mono font-bold text-sm ${liqDanger ? 'text-red-400' : liqWarning ? 'text-yellow-400' : 'text-orange-400'
                                            }`}>
                                            ${calc.liqPrice.toFixed(4)}
                                        </span>
                                    </div>
                                    <div className="flex justify-between items-center">
                                        <span className="text-[10px] text-muted-foreground">Cushion from entry</span>
                                        <span className={`text-[10px] font-mono font-bold ${liqDanger ? 'text-red-400' : liqWarning ? 'text-yellow-400' : 'text-muted-foreground'
                                            }`}>
                                            {calc.liqCushionPct.toFixed(2)}%
                                        </span>
                                    </div>
                                    {liqWarning && (
                                        <p className="text-[10px] text-yellow-400/80 leading-tight">
                                            {liqDanger ? 'Stop is BEYOND liquidation.' : 'Stop is approaching liquidation.'} Lower leverage.
                                        </p>
                                    )}
                                </div>

                                {/* Profit Projections */}
                                <div className="space-y-1 pt-1 border-t border-border/30">
                                    <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Profit Projections</span>
                                    <div className="flex justify-between text-xs">
                                        <span className="text-muted-foreground">TP1</span>
                                        <span className="font-mono font-bold text-green-400">+${calc.tp1Profit.toFixed(2)}</span>
                                    </div>
                                    <div className="flex justify-between text-xs">
                                        <span className="text-muted-foreground">TP2</span>
                                        <span className="font-mono font-bold text-green-400">+${calc.tp2Profit.toFixed(2)}</span>
                                    </div>
                                    <div className="flex justify-between text-xs">
                                        <span className="text-muted-foreground">TP3</span>
                                        <span className="font-mono font-bold text-green-400">+${calc.tp3Profit.toFixed(2)}</span>
                                    </div>
                                    <div className="flex justify-between text-xs border-t border-border/40 pt-1">
                                        <span className="text-muted-foreground">Max Loss</span>
                                        <span className="font-mono font-bold text-destructive">-${riskAmt.toFixed(2)}</span>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <p className="text-[10px] text-muted-foreground italic text-center py-2">
                                Enter balance, risk amount &amp; leverage to calculate
                            </p>
                        )}
                    </div>

                    {/* Setup Quality */}
                    <div className="space-y-3">
                        <h4 className="text-xs font-semibold flex items-center gap-2 text-accent">
                            <Brain size={14} />
                            SETUP INTELLIGENCE
                        </h4>

                        <div className="grid grid-cols-2 gap-3">
                            <div className="bg-muted/30 p-3 rounded-lg border border-border/50 flex flex-col gap-1">
                                <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Confidence</div>
                                <div className={`text-xl font-bold font-mono ${tier.color}`}>
                                    {result.confidenceScore.toFixed(1)}%
                                </div>
                            </div>
                            <div className="bg-muted/30 p-3 rounded-lg border border-border/50 flex flex-col gap-1">
                                <div className="text-xl font-bold font-mono text-foreground">
                                    {result.riskReward ? (result.riskReward * (result.confidenceScore / 100)).toFixed(2) : '-'}R
                                </div>
                            </div>
                        </div>

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

                    {/* Strategy Brief */}
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
                                {result.riskScore > 7 && " High risk setup — reduce position size."}
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
                        {result.metadata?.leverage && (
                            <span className="ml-2 text-yellow-400/80">@ {result.metadata.leverage}x</span>
                        )}
                    </span>
                </div>
            </div>
        </div>
    );
}

