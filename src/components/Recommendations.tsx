import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Lightbulb, ArrowRight, Star, Target, ChartLine, Clock, ShieldCheck, CaretDown, CaretUp } from '@phosphor-icons/react';
import type { ScanResult } from '@/utils/mockData';
import { getSignalTier } from '@/utils/signalTiers';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { useState } from 'react';

interface RecommendationsProps {
    results: ScanResult[];
    rejections: any;
    metadata: any;
}

interface Recommendation {
    priority: 'action' | 'consider' | 'tip';
    title: string;
    description: string;
    icon: React.ReactNode;
}

/**
 * Recommendations - Actionable next steps based on scan results
 */
export function Recommendations({ results, rejections, metadata }: RecommendationsProps) {
    const [isExpanded, setIsExpanded] = useState(false);

    const recommendations: Recommendation[] = [];

    // Prioritize TOP tier signals
    const topTier = results.filter(r => getSignalTier(r.confidenceScore).tier === 'TOP');
    if (topTier.length > 0) {
        const topSymbols = topTier.slice(0, 3).map(r => r.pair).join(', ');
        recommendations.push({
            priority: 'action',
            title: 'Focus on Top-Tier Signals',
            description: `${topTier.length} signal(s) have 80%+ confluence. Prioritize: ${topSymbols}${topTier.length > 3 ? ', ...' : ''}`,
            icon: <Star size={18} weight="fill" className="text-success" />
        });
    }

    // Best R:R opportunities
    const sortedByRR = [...results].sort((a, b) => ((b as any).riskReward || 0) - ((a as any).riskReward || 0));
    const bestRR = sortedByRR[0];
    if (bestRR && (bestRR as any).riskReward >= 2.5) {
        recommendations.push({
            priority: 'action',
            title: 'Best Risk-Reward Setup',
            description: `${bestRR.pair} has ${((bestRR as any).riskReward).toFixed(1)}:1 R:R - highest opportunity cost potential.`,
            icon: <Target size={18} className="text-accent" />
        });
    }

    // If high rejection rate, suggest adjustments
    const totalScanned = metadata?.scanned || (results.length + (rejections?.total_rejected || 0));
    const passRate = (results.length / totalScanned) * 100;
    if (passRate < 20 && rejections?.total_rejected > 5) {
        recommendations.push({
            priority: 'consider',
            title: 'Consider Lowering Threshold',
            description: `Only ${passRate.toFixed(0)}% pass rate. Switch to RECON or STRIKE mode for more signals.`,
            icon: <ChartLine size={18} className="text-warning" />
        });
    }

    // If low confluence signals present, suggest caution
    const solidOnly = results.filter(r => getSignalTier(r.confidenceScore).tier === 'SOLID');
    if (solidOnly.length > 0 && topTier.length === 0) {
        recommendations.push({
            priority: 'consider',
            title: 'Use Smaller Position Sizes',
            description: `All signals are SOLID tier (sub-75%). Consider half-sizing entries or waiting for better setups.`,
            icon: <ShieldCheck size={18} className="text-primary" />
        });
    }

    // Time-based recommendations
    const hour = new Date().getHours();
    if (hour >= 0 && hour < 8) {
        recommendations.push({
            priority: 'tip',
            title: 'Asian Session Active',
            description: 'Lower volatility expected. Crypto may see consolidation before London/NY opens.',
            icon: <Clock size={18} className="text-muted-foreground" />
        });
    } else if (hour >= 13 && hour < 17) {
        recommendations.push({
            priority: 'tip',
            title: 'NY Session Peak',
            description: 'High volatility window. Good for breakout entries but watch for fakeouts.',
            icon: <Clock size={18} className="text-warning" />
        });
    }

    // Suggest re-scan if results are sparse
    if (results.length <= 2 && totalScanned >= 20) {
        recommendations.push({
            priority: 'consider',
            title: 'Expand Symbol Universe',
            description: 'Few qualifying signals. Try scanning more pairs or different timeframes.',
            icon: <ArrowRight size={18} className="text-accent" />
        });
    }

    // General trading tip
    recommendations.push({
        priority: 'tip',
        title: 'Verify Before Entry',
        description: 'Always confirm price action at entry zone. Use chart view to validate structure is intact.',
        icon: <Lightbulb size={18} className="text-yellow-400" />
    });

    if (recommendations.length === 0) return null;

    const actionItems = recommendations.filter(r => r.priority === 'action');

    return (
        <Card className="bg-gradient-to-br from-blue-500/5 via-background to-accent/5 border-blue-500/30 overflow-hidden">
            <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
                <CollapsibleTrigger className="w-full">
                    <CardHeader className="cursor-pointer hover:bg-blue-500/5 transition-colors">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-lg flex items-center gap-3">
                                <div className="p-2 rounded-lg bg-blue-500/20">
                                    <Lightbulb size={22} weight="fill" className="text-blue-400" />
                                </div>
                                <div className="text-left">
                                    <span className="text-foreground">Recommendations & Next Steps</span>
                                    <p className="text-xs text-muted-foreground font-normal mt-0.5">
                                        {recommendations.length} suggestion{recommendations.length !== 1 ? 's' : ''} based on your scan
                                    </p>
                                </div>
                            </CardTitle>
                            <div className="flex items-center gap-2">
                                {actionItems.length > 0 && (
                                    <Badge className="bg-success/20 text-success border-success/50">
                                        {actionItems.length} action{actionItems.length !== 1 ? 's' : ''}
                                    </Badge>
                                )}
                                {isExpanded ? (
                                    <CaretUp size={20} className="text-muted-foreground" />
                                ) : (
                                    <CaretDown size={20} className="text-muted-foreground" />
                                )}
                            </div>
                        </div>
                    </CardHeader>
                </CollapsibleTrigger>

                <CollapsibleContent>
                    <CardContent className="pt-0 animate-in fade-in slide-in-from-top-2 duration-300">
                        <div className="space-y-3">
                            {recommendations.sort((a, b) => {
                                const priorityOrder = { action: 0, consider: 1, tip: 2 };
                                return priorityOrder[a.priority] - priorityOrder[b.priority];
                            }).map((rec, idx) => (
                                <div
                                    key={idx}
                                    className={`p-3 rounded-lg border flex items-start gap-3 ${rec.priority === 'action'
                                            ? 'bg-success/10 border-success/30'
                                            : rec.priority === 'consider'
                                                ? 'bg-accent/10 border-accent/30'
                                                : 'bg-background/60 border-border/40'
                                        }`}
                                >
                                    <div className="mt-0.5">{rec.icon}</div>
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="text-sm font-medium text-foreground">
                                                {rec.title}
                                            </span>
                                            <Badge
                                                variant="outline"
                                                className={`text-[10px] uppercase ${rec.priority === 'action'
                                                        ? 'text-success border-success/50'
                                                        : rec.priority === 'consider'
                                                            ? 'text-accent border-accent/50'
                                                            : 'text-muted-foreground border-border'
                                                    }`}
                                            >
                                                {rec.priority}
                                            </Badge>
                                        </div>
                                        <p className="text-xs text-muted-foreground">
                                            {rec.description}
                                        </p>
                                    </div>
                                </div>
                            ))}
                        </div>

                        <div className="mt-4 pt-3 border-t border-border/30">
                            <p className="text-xs text-muted-foreground">
                                📈 Focus on ACTION items first, then review CONSIDER suggestions for optimization.
                            </p>
                        </div>
                    </CardContent>
                </CollapsibleContent>
            </Collapsible>
        </Card>
    );
}
