
import { motion } from 'framer-motion';
import { ScanResult } from '@/utils/mockData';
import { Target, TrendUp, TrendDown, Warning, Lightning } from '@phosphor-icons/react';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface MissionStatsHeroProps {
    results: ScanResult[];
    metadata?: any;
}

export function MissionStatsHero({ results, metadata }: MissionStatsHeroProps) {
    const totalTargets = results.length;
    const longCount = results.filter(r => r.trendBias === 'BULLISH').length;
    const shortCount = results.filter(r => r.trendBias === 'BEARISH').length;

    const avgConfidence = totalTargets > 0
        ? Math.round(results.reduce((acc, r) => acc + r.confidenceScore, 0) / totalTargets)
        : 0;

    const avgRR = totalTargets > 0
        ? (results.reduce((acc, r) => acc + (r.riskReward || 0), 0) / totalTargets).toFixed(1)
        : '0.0';

    const bestTarget = totalTargets > 0
        ? results.reduce((prev, current) => (prev.confidenceScore > current.confidenceScore) ? prev : current)
        : null;

    return (
        <div className="h-full flex flex-col p-6 animate-in fade-in duration-500">
            {/* Header */}
            <div className="mb-8 text-center space-y-2">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[#00ff88]/30 bg-[#00ff88]/5 text-[#00ff88] text-xs font-mono tracking-widest uppercase mb-2">
                    <Lightning size={14} weight="fill" />
                    Mission Debrief
                </div>
                <h2 className="text-3xl md:text-4xl font-bold hud-headline hud-text-green tracking-wide">
                    SCAN COMPLETE
                </h2>
                <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
                    Analysis finished. {totalTargets} high-probability opportunities identified matching your tactical profile.
                </p>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                <StatCard
                    label="TOTAL TARGETS"
                    value={totalTargets}
                    icon={<Target size={24} weight="duotone" />}
                    color="green"
                    subValue={`${metadata?.scanned || 0} Scanned`}
                />
                <StatCard
                    label="MARKET BIAS"
                    value={longCount > shortCount ? 'BULLISH' : shortCount > longCount ? 'BEARISH' : 'NEUTRAL'}
                    icon={longCount > shortCount ? <TrendUp size={24} weight="duotone" /> : <TrendDown size={24} weight="duotone" />}
                    color={longCount > shortCount ? 'green' : shortCount > longCount ? 'red' : 'amber'}
                    subValue={`${longCount}L / ${shortCount}S`}
                />
                <StatCard
                    label="AVG CONFIDENCE"
                    value={`${avgConfidence}%`}
                    icon={<Lightning size={24} weight="duotone" />}
                    color="accent"
                    subValue="Confluence Score"
                />
                <StatCard
                    label="AVG R:R RATIO"
                    value={avgRR}
                    icon={<TrendUp size={24} weight="duotone" />}
                    color="cyan"
                    subValue="Risk/Reward"
                />
            </div>

            {/* Best Target Highlight */}
            {bestTarget && (
                <div className="mt-auto glass-card glow-border-green p-6 rounded-xl relative overflow-hidden group cursor-pointer hover:bg-white/5 transition-colors">
                    <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                        <Target size={120} weight="fill" />
                    </div>

                    <div className="relative z-10 flex items-center justify-between">
                        <div className="space-y-1">
                            <div className="text-xs font-mono text-[#00ff88] uppercase tracking-widest mb-1">
                                ★ TOP PRIORITY TARGET
                            </div>
                            <div className="text-4xl font-bold font-mono text-white">
                                {bestTarget.pair}
                            </div>
                            <div className="flex items-center gap-4 text-sm text-muted-foreground">
                                <span className={cn(
                                    "flex items-center gap-1 font-bold",
                                    bestTarget.trendBias === 'BULLISH' ? "text-green-400" : "text-red-400"
                                )}>
                                    {bestTarget.trendBias === 'BULLISH' ? <TrendUp /> : <TrendDown />}
                                    {bestTarget.trendBias}
                                </span>
                                <span>Entry: ${bestTarget.entryZone?.low.toFixed(2)}</span>
                                <span>R:R {bestTarget.riskReward}</span>
                            </div>
                        </div>

                        <div className="text-right">
                            <div className="text-5xl font-bold hud-text-green tabular-nums">
                                {bestTarget.confidenceScore}%
                            </div>
                            <div className="text-xs text-[#00ff88]/60 uppercase tracking-widest">
                                CONFIDENCE
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

function StatCard({ label, value, icon, color, subValue }: {
    label: string;
    value: string | number;
    icon: React.ReactNode;
    color: 'green' | 'red' | 'amber' | 'accent' | 'cyan';
    subValue?: string;
}) {
    const colors = {
        green: 'text-[#00ff88] border-[#00ff88]/20 bg-[#00ff88]/5',
        red: 'text-red-400 border-red-500/20 bg-red-500/5',
        amber: 'text-amber-400 border-amber-500/20 bg-amber-500/5',
        accent: 'text-cyan-400 border-cyan-500/20 bg-cyan-500/5',
        cyan: 'text-cyan-400 border-cyan-500/20 bg-cyan-500/5',
    };

    return (
        <div className={cn("p-4 rounded-xl border flex flex-col items-center justify-center text-center gap-2 transition-all hover:scale-[1.02]", colors[color])}>
            <div className={cn("opacity-80 mb-1", color === 'green' ? "text-[#00ff88]" : "")}>
                {icon}
            </div>
            <div className="text-2xl font-bold font-mono tracking-tight tabular-nums">
                {value}
            </div>
            <div className="text-[10px] uppercase tracking-widest opacity-60 font-semibold">
                {label}
            </div>
            {subValue && (
                <div className="text-[10px] opacity-40 font-mono border-t border-white/10 pt-1 w-full mt-1">
                    {subValue}
                </div>
            )}
        </div>
    );
}
