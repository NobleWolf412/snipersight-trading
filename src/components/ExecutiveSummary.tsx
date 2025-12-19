import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendUp, TrendDown, ChartLine, Timer, CheckCircle, Gauge, Target } from '@phosphor-icons/react';
import { calculateScanStats } from '@/utils/signalTiers';
import type { ScanResult } from '@/utils/mockData';

interface ExecutiveSummaryProps {
    results: ScanResult[];
    rejections: any;
    metadata: any;
}

/**
 * Executive Summary - Shows at-a-glance scan quality metrics
 */
export function ExecutiveSummary({ results, rejections, metadata }: ExecutiveSummaryProps) {
    const stats = calculateScanStats(results, rejections, metadata);

    // Determine status indicators
    const passRateStatus = stats.passRate >= 50 ? 'good' : stats.passRate >= 30 ? 'ok' : 'low';
    const biasStatus = stats.biasRatio >= 0.8 ? 'directional' : stats.biasRatio >= 0.6 ? 'leaning' : 'balanced';
    const evStatus = stats.avgEV >= 1.0 ? 'excellent' : stats.avgEV >= 0.5 ? 'good' : stats.avgEV >= 0.2 ? 'ok' : 'weak';

    return (
        <Card className="bg-gradient-to-br from-accent/10 via-background to-success/5 border-accent/40 overflow-hidden">
            <CardContent className="p-6">
                {/* Header */}
                <div className="flex items-start justify-between mb-6">
                    <div>
                        <h2 className="text-2xl font-bold text-foreground flex items-center gap-2">
                            <CheckCircle size={28} weight="fill" className="text-success" />
                            {stats.total} High-Probability Setup{stats.total !== 1 ? 's' : ''} Identified
                        </h2>
                        <p className="text-muted-foreground mt-1">
                            Confidence: <span className="text-accent font-semibold">{stats.qualityGrade} Tier</span>
                            {metadata?.mode && (
                                <span className="ml-2">
                                    • Mode: <span className="text-primary font-semibold uppercase">{metadata.mode}</span>
                                </span>
                            )}
                        </p>
                    </div>
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                    {/* Pass Rate */}
                    <div className="bg-background/60 rounded-lg p-4 border border-border/40">
                        <div className="flex items-center gap-2 mb-2">
                            <Target size={18} className="text-accent" />
                            <span className="text-xs text-muted-foreground uppercase tracking-wide">Pass Rate</span>
                        </div>
                        <div className="text-2xl font-bold font-mono text-foreground">
                            {stats.passRate.toFixed(0)}%
                        </div>
                        <div className="text-xs text-muted-foreground">
                            {stats.total}/{stats.scanned} symbols
                        </div>
                        <Badge
                            variant="outline"
                            className={`mt-2 text-[10px] ${passRateStatus === 'good' ? 'text-success border-success/50' :
                                    passRateStatus === 'ok' ? 'text-warning border-warning/50' :
                                        'text-muted-foreground border-border'
                                }`}
                        >
                            {passRateStatus === 'good' ? '✓ Good Efficiency' :
                                passRateStatus === 'ok' ? '⚠ Moderate' :
                                    '⚠ Low Yield'}
                        </Badge>
                    </div>

                    {/* Average Confluence */}
                    <div className="bg-background/60 rounded-lg p-4 border border-border/40">
                        <div className="flex items-center gap-2 mb-2">
                            <Gauge size={18} className="text-primary" />
                            <span className="text-xs text-muted-foreground uppercase tracking-wide">Avg Confidence</span>
                        </div>
                        <div className="text-2xl font-bold font-mono text-primary">
                            {stats.avgConfidence.toFixed(1)}%
                        </div>
                        <div className="text-xs text-muted-foreground">
                            Quality score
                        </div>
                        <Badge
                            variant="outline"
                            className={`mt-2 text-[10px] ${stats.avgConfidence >= 80 ? 'text-success border-success/50' :
                                    stats.avgConfidence >= 70 ? 'text-accent border-accent/50' :
                                        'text-warning border-warning/50'
                                }`}
                        >
                            {stats.avgConfidence >= 80 ? '✓ Strong Confluence' :
                                stats.avgConfidence >= 70 ? '✓ Solid Quality' :
                                    '⚠ Watch Quality'}
                        </Badge>
                    </div>

                    {/* Bias Split */}
                    <div className="bg-background/60 rounded-lg p-4 border border-border/40">
                        <div className="flex items-center gap-2 mb-2">
                            {stats.dominantBias === 'LONG' ?
                                <TrendUp size={18} className="text-success" /> :
                                <TrendDown size={18} className="text-destructive" />
                            }
                            <span className="text-xs text-muted-foreground uppercase tracking-wide">Bias Split</span>
                        </div>
                        <div className="text-2xl font-bold font-mono">
                            <span className="text-success">{stats.longCount}</span>
                            <span className="text-muted-foreground mx-1">/</span>
                            <span className="text-destructive">{stats.shortCount}</span>
                        </div>
                        <div className="text-xs text-muted-foreground">
                            Long / Short
                        </div>
                        <Badge
                            variant="outline"
                            className={`mt-2 text-[10px] ${biasStatus === 'balanced' ? 'text-success border-success/50' :
                                    biasStatus === 'leaning' ? 'text-accent border-accent/50' :
                                        'text-warning border-warning/50'
                                }`}
                        >
                            {biasStatus === 'balanced' ? '✓ Balanced' :
                                biasStatus === 'leaning' ? 'ℹ Leaning ' + stats.dominantBias :
                                    '⚠ Directional'}
                        </Badge>
                    </div>

                    {/* Average EV */}
                    <div className="bg-background/60 rounded-lg p-4 border border-border/40">
                        <div className="flex items-center gap-2 mb-2">
                            <ChartLine size={18} className="text-success" />
                            <span className="text-xs text-muted-foreground uppercase tracking-wide">Avg EV</span>
                        </div>
                        <div className={`text-2xl font-bold font-mono ${stats.avgEV >= 0 ? 'text-success' : 'text-destructive'}`}>
                            {stats.avgEV.toFixed(2)}R
                        </div>
                        <div className="text-xs text-muted-foreground">
                            Expected Value
                        </div>
                        <Badge
                            variant="outline"
                            className={`mt-2 text-[10px] ${evStatus === 'excellent' ? 'text-success border-success/50' :
                                    evStatus === 'good' ? 'text-accent border-accent/50' :
                                        evStatus === 'ok' ? 'text-warning border-warning/50' :
                                            'text-muted-foreground border-border'
                                }`}
                        >
                            {evStatus === 'excellent' ? '✓ Excellent Edge' :
                                evStatus === 'good' ? '✓ Healthy Edge' :
                                    evStatus === 'ok' ? '⚠ Moderate' :
                                        '⚠ Thin Edge'}
                        </Badge>
                    </div>

                    {/* Tier Distribution */}
                    <div className="bg-background/60 rounded-lg p-4 border border-border/40">
                        <div className="flex items-center gap-2 mb-2">
                            <span className="text-lg">⭐</span>
                            <span className="text-xs text-muted-foreground uppercase tracking-wide">Tier Split</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Badge className="bg-success/20 text-success border-success/50 text-sm font-bold">
                                {stats.tierCounts.TOP}
                            </Badge>
                            <Badge className="bg-accent/20 text-accent border-accent/50 text-sm font-bold">
                                {stats.tierCounts.HIGH}
                            </Badge>
                            <Badge className="bg-primary/20 text-primary border-primary/50 text-sm font-bold">
                                {stats.tierCounts.SOLID}
                            </Badge>
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                            Top / High / Solid
                        </div>
                        <Badge
                            variant="outline"
                            className="mt-2 text-[10px] text-muted-foreground border-border"
                        >
                            ℹ {stats.tierCounts.TOP + stats.tierCounts.HIGH} priority signals
                        </Badge>
                    </div>

                    {/* Rejected */}
                    <div className="bg-background/60 rounded-lg p-4 border border-border/40">
                        <div className="flex items-center gap-2 mb-2">
                            <span className="text-lg">🚫</span>
                            <span className="text-xs text-muted-foreground uppercase tracking-wide">Rejected</span>
                        </div>
                        <div className="text-2xl font-bold font-mono text-muted-foreground">
                            {stats.rejected}
                        </div>
                        <div className="text-xs text-muted-foreground">
                            Did not qualify
                        </div>
                        <Badge
                            variant="outline"
                            className="mt-2 text-[10px] text-muted-foreground border-border"
                        >
                            ℹ Filter working
                        </Badge>
                    </div>
                </div>

                {/* Config Applied */}
                {metadata && (
                    <div className="mt-4 pt-4 border-t border-border/30">
                        <p className="text-xs text-muted-foreground">
                            📊 <span className="font-medium">Config Applied:</span>{' '}
                            Mode: {metadata.mode?.toUpperCase() || 'N/A'} |
                            Min Confluence: {metadata.effectiveMinScore || 0}% |
                            Timeframes: {metadata.appliedTimeframes?.length || 0}
                            {metadata.leverage && ` | Leverage: ${metadata.leverage}x`}
                        </p>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
