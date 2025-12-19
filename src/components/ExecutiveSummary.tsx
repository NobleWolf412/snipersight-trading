import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendUp, TrendDown, ChartLine, Timer, CheckCircle, Gauge, Target } from '@phosphor-icons/react';
import { calculateScanStats } from '@/utils/signalTiers';
import { CircularProgress, MiniPieChart } from '@/components/ui/CircularProgress';
import type { ScanResult } from '@/utils/mockData';

interface ExecutiveSummaryProps {
    results: ScanResult[];
    rejections: any;
    metadata: any;
}

/**
 * Executive Summary - Shows at-a-glance scan quality metrics with visual gauges
 */
export function ExecutiveSummary({ results, rejections, metadata }: ExecutiveSummaryProps) {
    const stats = calculateScanStats(results, rejections, metadata);

    // Determine status indicators
    const passRateStatus = stats.passRate >= 50 ? 'good' : stats.passRate >= 30 ? 'ok' : 'low';
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

                {/* Quick Stats Banner */}
                <div className="flex flex-wrap items-center gap-4 mb-6 p-3 bg-background/60 rounded-lg border border-border/40">
                    <div className="flex items-center gap-2">
                        <span className="text-success font-bold">✓ {stats.total}/{stats.scanned}</span>
                        <span className="text-muted-foreground text-sm">Passed</span>
                    </div>
                    <span className="text-border">|</span>
                    <div className="flex items-center gap-2">
                        <span className="text-accent font-bold">{stats.avgConfidence.toFixed(0)}%</span>
                        <span className="text-muted-foreground text-sm">Avg Conf</span>
                    </div>
                    <span className="text-border">|</span>
                    <div className="flex items-center gap-2">
                        <span className={`font-bold ${stats.avgEV >= 0 ? 'text-success' : 'text-destructive'}`}>
                            {stats.avgEV.toFixed(2)}R
                        </span>
                        <span className="text-muted-foreground text-sm">EV</span>
                    </div>
                    <span className="text-border">|</span>
                    <div className="flex items-center gap-2">
                        <span className="text-success">{stats.longCount}↑</span>
                        <span className="text-muted-foreground">/</span>
                        <span className="text-destructive">{stats.shortCount}↓</span>
                    </div>
                </div>

                {/* Metrics Grid with Visual Gauges */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {/* Pass Rate - Circular Gauge */}
                    <div className="bg-background/60 rounded-lg p-4 border border-border/40 flex flex-col items-center justify-center">
                        <CircularProgress
                            value={stats.passRate}
                            size={90}
                            strokeWidth={10}
                            colorScheme="gradient"
                            label="PASS"
                        />
                        <div className="text-xs text-muted-foreground mt-2">
                            {stats.total}/{stats.scanned} symbols
                        </div>
                    </div>

                    {/* Average Confluence - Circular Gauge */}
                    <div className="bg-background/60 rounded-lg p-4 border border-border/40 flex flex-col items-center justify-center">
                        <CircularProgress
                            value={stats.avgConfidence}
                            size={90}
                            strokeWidth={10}
                            colorScheme="gradient"
                            label="CONF"
                        />
                        <div className="text-xs text-muted-foreground mt-2">
                            Quality score
                        </div>
                    </div>

                    {/* Bias Split - Mini Pie Chart */}
                    <div className="bg-background/60 rounded-lg p-4 border border-border/40 flex flex-col items-center justify-center">
                        <div className="flex items-center gap-3">
                            <MiniPieChart
                                segments={[
                                    { value: stats.longCount, color: '#22c55e', label: 'Long' },
                                    { value: stats.shortCount, color: '#ef4444', label: 'Short' },
                                ]}
                                size={60}
                            />
                            <div className="flex flex-col gap-1">
                                <div className="flex items-center gap-1.5">
                                    <div className="w-2 h-2 rounded-full bg-success" />
                                    <span className="text-success font-bold">{stats.longCount}</span>
                                    <span className="text-xs text-muted-foreground">Long</span>
                                </div>
                                <div className="flex items-center gap-1.5">
                                    <div className="w-2 h-2 rounded-full bg-destructive" />
                                    <span className="text-destructive font-bold">{stats.shortCount}</span>
                                    <span className="text-xs text-muted-foreground">Short</span>
                                </div>
                            </div>
                        </div>
                        <div className="text-xs text-muted-foreground mt-2 uppercase tracking-wide">
                            Direction Split
                        </div>
                    </div>

                    {/* EV & Tiers Combined */}
                    <div className="bg-background/60 rounded-lg p-4 border border-border/40">
                        <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                                <ChartLine size={18} className="text-success" />
                                <span className="text-xs text-muted-foreground uppercase tracking-wide">Edge</span>
                            </div>
                            <div className={`text-2xl font-bold font-mono ${stats.avgEV >= 0 ? 'text-success' : 'text-destructive'}`}>
                                {stats.avgEV.toFixed(2)}R
                            </div>
                        </div>
                        <div className="border-t border-border/30 pt-3 mt-3">
                            <div className="flex items-center gap-2 mb-2">
                                <span className="text-xs text-muted-foreground uppercase tracking-wide">Tier Split</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <Badge className="bg-success/20 text-success border-success/50 text-xs font-bold">
                                    {stats.tierCounts.TOP} TOP
                                </Badge>
                                <Badge className="bg-accent/20 text-accent border-accent/50 text-xs font-bold">
                                    {stats.tierCounts.HIGH} HIGH
                                </Badge>
                                <Badge className="bg-primary/20 text-primary border-primary/50 text-xs font-bold">
                                    {stats.tierCounts.SOLID} SOLID
                                </Badge>
                            </div>
                        </div>
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
