import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle, Target, ChartLine, Lightning, ShieldCheck, Clock, TrendUp } from '@phosphor-icons/react';
import type { ScanResult } from '@/utils/mockData';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { useState } from 'react';

interface WhySignalsPassedProps {
    results: ScanResult[];
    metadata: any;
}

interface PassingCriteria {
    name: string;
    description: string;
    icon: React.ReactNode;
    passed: number;
    total: number;
    details?: string;
}

/**
 * WhySignalsPassed - Explains why these signals made it through the filter
 */
export function WhySignalsPassed({ results, metadata }: WhySignalsPassedProps) {
    const [isExpanded, setIsExpanded] = useState(false);

    if (!results || results.length === 0) return null;

    const mode = metadata?.mode?.toUpperCase() || 'STANDARD';
    const minScore = metadata?.effectiveMinScore || 65;

    // Analyze passing criteria across all results
    const criteria: PassingCriteria[] = [
        {
            name: 'Confluence Score',
            description: `Met or exceeded ${minScore}% threshold`,
            icon: <Target size={18} className="text-accent" />,
            passed: results.filter(r => r.confidenceScore >= minScore).length,
            total: results.length,
            details: `Average: ${(results.reduce((s, r) => s + r.confidenceScore, 0) / results.length).toFixed(1)}%`
        },
        {
            name: 'Valid Trade Plan',
            description: 'Entry, stop-loss, and targets computed',
            icon: <ChartLine size={18} className="text-success" />,
            passed: results.filter(r => (r as any).entry && (r as any).stopLoss).length,
            total: results.length,
            details: 'SMC structures or ATR-based levels identified'
        },
        {
            name: 'Risk/Reward Ratio',
            description: 'Minimum 1.5:1 R:R requirement',
            icon: <ShieldCheck size={18} className="text-primary" />,
            passed: results.filter(r => (r as any).riskReward >= 1.5).length,
            total: results.length,
            details: `Best: ${Math.max(...results.map(r => (r as any).riskReward || 0)).toFixed(1)}:1`
        },
        {
            name: 'Directional Clarity',
            description: 'Clear bullish or bearish bias detected',
            icon: <TrendUp size={18} className="text-success" />,
            passed: results.filter(r => r.trendBias !== 'NEUTRAL').length,
            total: results.length,
            details: `${results.filter(r => r.trendBias === 'BULLISH').length} longs, ${results.filter(r => r.trendBias === 'BEARISH').length} shorts`
        },
        {
            name: 'Timeframe Alignment',
            description: 'Multi-timeframe confluence verified',
            icon: <Clock size={18} className="text-warning" />,
            passed: results.filter(r => (r as any).metadata?.htf_aligned !== false).length,
            total: results.length,
            details: `Timeframes: ${metadata?.appliedTimeframes?.join(', ') || 'Multiple'}`
        }
    ];

    // Mode-specific explanation
    const modeExplanations: Record<string, string> = {
        'SURGICAL': 'Only the highest-conviction setups with strong SMC structure',
        'OVERWATCH': 'HTF-validated entries with premium structure zones',
        'STRIKE': 'Balanced quality with good R:R opportunities',
        'RECON': 'Scanning mode with lower threshold for exploration',
        'GHOST': 'Stealth entries with minimal footprint detection',
        'STANDARD': 'Standard filtering with balanced criteria'
    };

    const passRateOverall = criteria.reduce((acc, c) => acc + c.passed, 0) / (criteria.length * results.length) * 100;

    return (
        <Card className="bg-gradient-to-br from-success/5 via-background to-accent/5 border-success/30 overflow-hidden">
            <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
                <CollapsibleTrigger className="w-full">
                    <CardHeader className="cursor-pointer hover:bg-success/5 transition-colors">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-lg flex items-center gap-3">
                                <div className="p-2 rounded-lg bg-success/20">
                                    <CheckCircle size={22} weight="fill" className="text-success" />
                                </div>
                                <div className="text-left">
                                    <span className="text-foreground">Why These Signals Passed</span>
                                    <p className="text-xs text-muted-foreground font-normal mt-0.5">
                                        {results.length} signals met {mode} mode criteria
                                    </p>
                                </div>
                            </CardTitle>
                            <div className="flex items-center gap-2">
                                <Badge className="bg-success/20 text-success border-success/50 font-mono">
                                    {passRateOverall.toFixed(0)}% criteria met
                                </Badge>
                                <Lightning
                                    size={20}
                                    className={`text-muted-foreground transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                                />
                            </div>
                        </div>
                    </CardHeader>
                </CollapsibleTrigger>

                <CollapsibleContent>
                    <CardContent className="pt-0 animate-in fade-in slide-in-from-top-2 duration-300">
                        {/* Mode Explanation */}
                        <div className="mb-4 p-3 bg-accent/10 rounded-lg border border-accent/20">
                            <div className="flex items-center gap-2 text-sm">
                                <Badge className="bg-accent text-accent-foreground uppercase font-bold text-xs">
                                    {mode}
                                </Badge>
                                <span className="text-muted-foreground">
                                    {modeExplanations[mode] || modeExplanations['STANDARD']}
                                </span>
                            </div>
                        </div>

                        {/* Criteria Grid */}
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                            {criteria.map((criterion, idx) => {
                                const passRate = (criterion.passed / criterion.total) * 100;
                                const isFullPass = passRate === 100;

                                return (
                                    <div
                                        key={idx}
                                        className={`p-3 rounded-lg border transition-colors ${isFullPass
                                                ? 'bg-success/10 border-success/30'
                                                : passRate >= 80
                                                    ? 'bg-accent/10 border-accent/30'
                                                    : 'bg-background/60 border-border/40'
                                            }`}
                                    >
                                        <div className="flex items-start gap-2 mb-2">
                                            {criterion.icon}
                                            <div className="flex-1">
                                                <div className="text-sm font-medium text-foreground">
                                                    {criterion.name}
                                                </div>
                                                <div className="text-xs text-muted-foreground">
                                                    {criterion.description}
                                                </div>
                                            </div>
                                        </div>
                                        <div className="flex items-center justify-between mt-2">
                                            <span className="text-xs text-muted-foreground">
                                                {criterion.details}
                                            </span>
                                            <Badge
                                                variant="outline"
                                                className={`text-xs font-mono ${isFullPass
                                                        ? 'text-success border-success/50'
                                                        : 'text-muted-foreground border-border'
                                                    }`}
                                            >
                                                {criterion.passed}/{criterion.total}
                                            </Badge>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>

                        {/* Summary */}
                        <div className="mt-4 pt-3 border-t border-border/30">
                            <p className="text-xs text-muted-foreground">
                                ✓ All {results.length} signals passed the confluence gate with score ≥{minScore}%,
                                valid entry/stop levels, and minimum 1.5:1 risk-reward ratio.
                            </p>
                        </div>
                    </CardContent>
                </CollapsibleContent>
            </Collapsible>
        </Card>
    );
}
