import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { ScanResult } from '@/utils/mockData';
import { getSignalTier } from '@/utils/signalTiers';
import { ChartLineUp, Eye, Target, TrendUp, TrendDown } from '@phosphor-icons/react';
import { TierBadge } from '@/components/TierBadge';
import { RegimeIndicator } from '@/components/RegimeIndicator';

interface HeatmapGridProps {
    results: ScanResult[];
    onViewChart: (result: ScanResult) => void;
    regimes: Record<string, any>;
    globalRegime: any;
    selectedIds?: string[];
    onToggleSelection?: (id: string, e: React.MouseEvent) => void;
}

export function HeatmapGrid({ results, onViewChart, regimes, globalRegime, selectedIds = [], onToggleSelection }: HeatmapGridProps) {

    // Sort logic handled by parent if needed, or we can sort by score here for heatmap effectiveness
    // For now, assume results are passed in desired order, but for a true heatmap, score sorting is visual key
    const gridResults = [...results].sort((a, b) => b.confidenceScore - a.confidenceScore);

    const getGlowColor = (score: number) => {
        if (score >= 80) return 'shadow-[0_0_15px_rgba(34,197,94,0.3)] border-success/50';
        if (score >= 65) return 'shadow-[0_0_12px_rgba(0,255,255,0.2)] border-accent/40';
        return 'shadow-none border-border/40';
    };

    const getBgTint = (score: number) => {
        if (score >= 80) return 'bg-gradient-to-br from-success/10 to-transparent';
        if (score >= 65) return 'bg-gradient-to-br from-accent/5 to-transparent';
        return 'bg-card/40';
    };

    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 p-1">
            {gridResults.map((result) => {
                const tier = getSignalTier(result.confidenceScore);
                const regime = regimes[result.pair] || result.regime || globalRegime;
                const profitPotential = ((result.takeProfits[1] - result.entryZone.high) / result.entryZone.high * 100);

                const isSelected = selectedIds.includes(result.id);

                const handleCardClick = (e: React.MouseEvent) => {
                    if (onToggleSelection && e.ctrlKey) {
                        onToggleSelection(result.id, e);
                    } else if (!e.defaultPrevented) {
                        onViewChart(result);
                    }
                };

                return (
                    <Card
                        key={result.id}
                        className={`card-3d cursor-pointer group transition-all duration-300 hover:scale-[1.02] ${isSelected ? 'ring-2 ring-accent bg-accent/5' : ''} ${getGlowColor(result.confidenceScore)} ${getBgTint(result.confidenceScore)}`}
                        onClick={handleCardClick}
                    >
                        <CardHeader className="p-4 pb-2">
                            <div className="flex items-center justify-between mb-1">
                                <div className="flex items-center gap-2">
                                    {onToggleSelection && (
                                        <div
                                            className="cursor-pointer"
                                            onClick={(e) => { e.stopPropagation(); onToggleSelection(result.id, e); }}
                                        >
                                            <div className={`w-4 h-4 rounded border ${isSelected ? 'bg-accent border-accent' : 'border-muted-foreground'} flex items-center justify-center`}>
                                                {isSelected && <div className="w-2 h-2 bg-background rounded-sm" />}
                                            </div>
                                        </div>
                                    )}
                                    <span className="font-bold text-lg tracking-tight">{result.pair}</span>
                                    {/* Small bias indicator */}
                                    {result.trendBias === 'BULLISH' ? (
                                        <TrendUp weight="bold" className="text-success w-4 h-4" />
                                    ) : (
                                        <TrendDown weight="bold" className="text-destructive w-4 h-4" />
                                    )}
                                </div>
                                <TierBadge confidenceScore={result.confidenceScore} size="sm" showLabel={false} />
                            </div>

                            <div className="flex items-center justify-between">
                                <span className="text-xs text-muted-foreground font-mono">
                                    {result.classification}
                                </span>
                                <span className={`text-xl font-mono font-bold ${tier.color}`}>
                                    {result.confidenceScore.toFixed(0)}%
                                </span>
                            </div>
                        </CardHeader>

                        <CardContent className="p-4 pt-2 space-y-3">
                            {/* Key Stats Row */}
                            <div className="grid grid-cols-2 gap-2 text-xs">
                                <div className="bg-background/40 rounded p-1.5 border border-border/30">
                                    <span className="text-muted-foreground block text-[10px] uppercase">R:R Ratio</span>
                                    <span className={`font-mono font-semibold ${result.riskReward && result.riskReward >= 2.5 ? 'text-accent' : 'text-foreground'}`}>
                                        {result.riskReward ? result.riskReward.toFixed(1) : '-'}R
                                    </span>
                                </div>
                                <div className="bg-background/40 rounded p-1.5 border border-border/30">
                                    <span className="text-muted-foreground block text-[10px] uppercase">Potential</span>
                                    <span className="font-mono font-semibold text-success">
                                        +{profitPotential.toFixed(1)}%
                                    </span>
                                </div>
                            </div>

                            {/* Mini Sparkline Placeholder - CSS for now */}
                            <div className="h-8 w-full bg-background/30 rounded flex items-center justify-center relative overflow-hidden group-hover:bg-background/50 transition-colors">
                                <div className="absolute inset-0 flex items-center justify-between px-2 opacity-30">
                                    <div className="w-[10%] h-[40%] bg-current rounded-sm" />
                                    <div className="w-[10%] h-[60%] bg-current rounded-sm" />
                                    <div className="w-[10%] h-[30%] bg-current rounded-sm" />
                                    <div className="w-[10%] h-[80%] bg-current rounded-sm" />
                                    <div className="w-[10%] h-[50%] bg-current rounded-sm" />
                                </div>
                                <span className="text-[10px] text-muted-foreground z-10 font-mono">
                                    ${result.entryZone.high.toFixed(result.entryZone.high < 1 ? 4 : 2)}
                                </span>
                            </div>

                            <div className="flex items-center justify-between pt-1">
                                <RegimeIndicator regime={regime} size="xs" compact />
                                <Button size="sm" variant="ghost" className="h-6 w-6 p-0 hover:bg-accent/20 hover:text-accent">
                                    <Eye size={14} />
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                );
            })}
        </div>
    );
}
