import { ArrowUp, ArrowDown, Target, ChartLine, Gauge } from '@phosphor-icons/react';
import { motion } from 'framer-motion';
import type { ScanResult } from '@/utils/mockData';

interface MissionStatsProps {
    results: ScanResult[];
    metadata?: any;
}

export function MissionStats({ results, metadata }: MissionStatsProps) {
    // Calculate stats
    const totalTargets = results.length;
    const longCount = results.filter(r => r.trendBias === 'BULLISH').length;
    const shortCount = results.filter(r => r.trendBias === 'BEARISH').length;

    const avgRR = results.length > 0
        ? results.reduce((acc, r) => acc + (r.riskReward || 0), 0) / results.length
        : 0;

    const avgConfidence = results.length > 0
        ? results.reduce((acc, r) => acc + (r.confidenceScore || 0), 0) / results.length
        : 0;

    // Calculate avg EV
    const getEV = (r: ScanResult) => {
        const metaEV = (r as any)?.metadata?.ev?.expected_value;
        if (typeof metaEV === 'number') return metaEV;
        const rr = (r as any)?.riskReward ?? 1.5;
        const pRaw = (r.confidenceScore ?? 50) / 100;
        const p = Math.max(0.2, Math.min(0.85, pRaw));
        return p * rr - (1 - p) * 1.0;
    };

    const avgEV = results.length > 0
        ? results.reduce((acc, r) => acc + getEV(r), 0) / results.length
        : 0;

    const stats = [
        {
            label: 'TARGETS LOCKED',
            value: totalTargets,
            format: (v: number) => v.toString(),
            icon: <Target size={28} weight="fill" />,
            color: '#00ff88',
            glowClass: 'glow-border-green',
        },
        {
            label: 'LONG / SHORT',
            value: longCount,
            format: () => `${longCount} / ${shortCount}`,
            icon: (
                <div className="flex items-center gap-1">
                    <ArrowUp size={20} weight="bold" className="text-success" />
                    <ArrowDown size={20} weight="bold" className="text-destructive" />
                </div>
            ),
            color: '#00ff88',
            glowClass: 'glow-border-green',
        },
        {
            label: 'AVG R:R',
            value: avgRR,
            format: (v: number) => `${v.toFixed(1)}:1`,
            icon: <ChartLine size={28} weight="duotone" />,
            color: avgRR >= 2 ? '#00ff88' : avgRR >= 1.5 ? '#fbbf24' : '#ef4444',
            glowClass: avgRR >= 2 ? 'glow-border-green' : avgRR >= 1.5 ? 'glow-border-amber' : 'glow-border-red',
        },
        {
            label: 'AVG CONFLUENCE',
            value: avgConfidence,
            format: (v: number) => `${v.toFixed(0)}%`,
            icon: <Gauge size={28} weight="duotone" />,
            color: avgConfidence >= 75 ? '#00ff88' : avgConfidence >= 65 ? '#fbbf24' : '#ef4444',
            glowClass: avgConfidence >= 75 ? 'glow-border-green' : avgConfidence >= 65 ? 'glow-border-amber' : 'glow-border-red',
        },
    ];

    return (
        <section className="space-y-6">
            {/* Section Header */}
            <div className="flex items-center gap-4">
                <h2 className="text-xl lg:text-2xl font-bold hud-headline hud-text-green tracking-wide">
                    MISSION BRIEFING
                </h2>
                <div className="h-px flex-1 bg-gradient-to-r from-[#00ff88]/40 to-transparent" />
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {stats.map((stat, index) => (
                    <motion.div
                        key={stat.label}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.1, duration: 0.4 }}
                        className={`glass-card ${stat.glowClass} p-5 rounded-xl relative overflow-hidden group`}
                    >
                        {/* Background glow on hover */}
                        <div
                            className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
                            style={{
                                background: `radial-gradient(ellipse at center, ${stat.color}10 0%, transparent 70%)`
                            }}
                        />

                        {/* Icon */}
                        <div
                            className="mb-3 transition-colors"
                            style={{ color: stat.color }}
                        >
                            {stat.icon}
                        </div>

                        {/* Value */}
                        <div
                            className="text-3xl lg:text-4xl font-bold font-mono tabular-nums mb-1"
                            style={{ color: stat.color, textShadow: `0 0 20px ${stat.color}40` }}
                        >
                            {stat.format(stat.value)}
                        </div>

                        {/* Label */}
                        <div className="text-xs text-muted-foreground uppercase tracking-widest font-mono">
                            {stat.label}
                        </div>

                        {/* Corner accent */}
                        <div
                            className="absolute top-0 right-0 w-12 h-12"
                            style={{
                                background: `linear-gradient(135deg, transparent 50%, ${stat.color}15 50%)`,
                            }}
                        />
                    </motion.div>
                ))}
            </div>

            {/* Scan metadata summary */}
            {metadata && (
                <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground font-mono">
                    <span className="px-2 py-1 bg-white/5 rounded border border-white/10">
                        MODE: <span className="text-accent uppercase">{metadata.mode}</span>
                    </span>
                    <span className="px-2 py-1 bg-white/5 rounded border border-white/10">
                        SCANNED: <span className="text-warning">{metadata.scanned}</span> PAIRS
                    </span>
                    {metadata.effectiveMinScore && (
                        <span className="px-2 py-1 bg-white/5 rounded border border-white/10">
                            MIN SCORE: <span className="text-success">{metadata.effectiveMinScore}%</span>
                        </span>
                    )}
                </div>
            )}
        </section>
    );
}
