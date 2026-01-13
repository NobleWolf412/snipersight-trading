import { ArrowRight, TrendUp, TrendDown, Crosshair, Target, Shield, ChartLine, Stack } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { ScanResult } from '@/utils/mockData';

interface ResultCardProps {
    result: ScanResult;
    onClick?: (id: string) => void;
}

export function ResultCard({ result, onClick }: ResultCardProps) {
    const isLong = result.trendBias === 'BULLISH';
    const confidence = result.confidenceScore || 0;
    const rr = result.riskReward || 0;

    // Extract archetype from metadata
    const archetype = String(result.metadata?.archetype || result.metadata?.setup_archetype || 'UNKNOWN');
    const tradeType = result.classification; // SWING/SCALP

    // Get HTF alignment status
    const htfAligned = result.metadata?.htf_aligned ?? result.confluence_breakdown?.htf_aligned ?? null;

    // DEBUG: Check what targets we're receiving
    console.log(`🎯 ${result.pair} targets:`, result.takeProfits, `(length: ${result.takeProfits?.length || 0})`);

    // Get top 3 confluence factors
    const topFactors = result.confluence_breakdown?.factors
        ?.sort((a, b) => (b.score * b.weight) - (a.score * a.weight))
        ?.slice(0, 3) || [];

    // Calculate entry proximity
    // Use metadata live_price if available, else estimate from entry zone
    const currentPrice = Number(result.metadata?.live_price || result.metadata?.current_price ||
        (result.entryZone.high + result.entryZone.low) / 2);
    const entryMid = (result.entryZone.high + result.entryZone.low) / 2;
    const proximityPct = Math.abs((currentPrice - entryMid) / currentPrice) * 100;

    // Time sensitivity badge
    const getProximityBadge = (): { label: string; color: string; icon: string } | null => {
        if (proximityPct <= 0.5) return {
            label: 'HOT',
            color: 'bg-red-500/20 border-red-500/40 text-red-400 animate-pulse',
            icon: '🔥'
        };
        if (proximityPct <= 1.0) return {
            label: 'WARM',
            color: 'bg-orange-500/20 border-orange-500/40 text-orange-400',
            icon: '⚡'
        };
        if (proximityPct <= 2.0) return {
            label: 'READY',
            color: 'bg-yellow-500/20 border-yellow-500/40 text-yellow-400',
            icon: '👀'
        };
        return null; // Too far - don't show badge
    };

    const proximityBadge = getProximityBadge();

    // === PHASE 3: METADATA BADGES ===

    // 1. Structure Quality Badges (from confluence factors)
    const structureQuality: string[] = [];
    const confluenceFactorNames = result.confluence_breakdown?.factors?.map(f => f.name.toLowerCase()) || [];

    if (confluenceFactorNames.some(n => n.includes('fresh') && n.includes('order block'))) {
        structureQuality.push('FRESH OB');
    }
    if (confluenceFactorNames.some(n => n.includes('nested') && n.includes('order block'))) {
        structureQuality.push('NESTED OB');
    }
    if (confluenceFactorNames.some(n => n.includes('inside') && n.includes('order block'))) {
        structureQuality.push('INSIDE OB');
    }

    // 2. Setup Characteristic Badges
    const setupCharacteristics: string[] = [];

    if (confluenceFactorNames.some(n => n.includes('liquidity') && n.includes('sweep'))) {
        setupCharacteristics.push('SWEEP');
    }
    if (confluenceFactorNames.some(n => n.includes('bos') || n.includes('break of structure'))) {
        setupCharacteristics.push('BOS');
    }
    if (confluenceFactorNames.some(n => n.includes('choch') || n.includes('change of character'))) {
        setupCharacteristics.push('CHoCH');
    }
    if (confluenceFactorNames.some(n => n.includes('fvg') || n.includes('fair value gap'))) {
        setupCharacteristics.push('FVG');
    }
    if (confluenceFactorNames.some(n => n.includes('premium') || n.includes('discount'))) {
        setupCharacteristics.push('PD ARRAY');
    }

    // 3. Cycle Phase Badge (from cycle_context)
    const cyclePhase = result.cycle_context?.phase ? String(result.cycle_context.phase).toUpperCase() :
        result.metadata?.cycle_phase ? String(result.metadata.cycle_phase).toUpperCase() : null;

    const getCycleBadgeColor = (phase: string): string => {
        if (phase.includes('ACCUM')) return 'bg-blue-500/10 border-blue-500/20 text-blue-400';
        if (phase.includes('MARKUP') || phase.includes('DISTRIBUTION')) return 'bg-purple-500/10 border-purple-500/20 text-purple-400';
        return 'bg-cyan-500/10 border-cyan-500/20 text-cyan-400';
    };

    // Probability heatmap color
    const getProbColor = (prob: number): string => {
        if (prob >= 90) return 'text-emerald-400';
        if (prob >= 80) return 'text-green-400';
        if (prob >= 70) return 'text-lime-400';
        return 'text-yellow-400';
    };

    // R:R visual percentage (capped at 10R for UI)
    const rrPercent = Math.min(100, (rr / 10) * 100);

    return (
        <div
            onClick={() => onClick?.(result.id)}
            className="group relative w-full p-6 mb-4 bg-[#0a0f0a] border border-zinc-800/60 hover:border-[#00ff88]/60 rounded-xl cursor-pointer transition-all duration-300 hover:bg-zinc-900/50 hover:shadow-[0_0_20px_rgba(0,255,136,0.15)]"
        >
            {/* Main Content Row */}
            <div className="flex items-start justify-between gap-6 mb-4">

                {/* Left: Symbol & Direction */}
                <div className="flex items-center gap-6">
                    <div className={cn(
                        "flex items-center justify-center w-14 h-14 rounded-xl bg-black/40 border",
                        isLong ? "border-green-500/20 text-green-400" : "border-red-500/20 text-red-400"
                    )}>
                        {isLong ? <TrendUp size={32} weight="bold" /> : <TrendDown size={32} weight="bold" />}
                    </div>

                    <div>
                        <div className="flex items-center gap-3 mb-2">
                            <span className="text-2xl font-bold tracking-tight text-zinc-100">{result.pair}</span>
                            <span className={cn(
                                "px-2 py-0.5 text-xs font-mono uppercase tracking-wider rounded border",
                                isLong
                                    ? "bg-green-500/10 border-green-500/20 text-green-400"
                                    : "bg-red-500/10 border-red-500/20 text-red-400"
                            )}>
                                {isLong ? 'LONG' : 'SHORT'}
                            </span>

                            {/* Trade Type Badge */}
                            <span className={cn(
                                "px-2 py-0.5 text-xs font-mono uppercase tracking-wider rounded border",
                                tradeType === 'SWING'
                                    ? "bg-blue-500/10 border-blue-500/20 text-blue-400"
                                    : "bg-purple-500/10 border-purple-500/20 text-purple-400"
                            )}>
                                {tradeType}
                            </span>

                            {/* HTF Alignment Badge */}
                            {htfAligned !== null && (
                                <span className={cn(
                                    "px-2 py-0.5 text-xs font-mono uppercase tracking-wider rounded border flex items-center gap-1",
                                    htfAligned
                                        ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                                        : "bg-amber-500/10 border-amber-500/20 text-amber-400"
                                )}>
                                    <Stack size={12} weight="bold" />
                                    {htfAligned ? 'HTF ALIGNED' : 'HTF NEUTRAL'}
                                </span>
                            )}

                            {/* Macro Bonus Badge */}
                            {(() => {
                                const macroFactor = result.confluence_breakdown?.factors.find(f => f.name === "Macro Overlay");
                                const bonus = macroFactor ? macroFactor.score - 50 : 0;
                                if (bonus > 0) return (
                                    <span className="flex items-center gap-1 px-2 py-0.5 text-xs font-bold font-mono tracking-wider rounded border border-blue-400/30 bg-blue-500/10 text-blue-400 shadow-[0_0_10px_rgba(96,165,250,0.3)] animate-pulse">
                                        +{bonus.toFixed(0)} MACRO
                                    </span>
                                );
                                return null;
                            })()}

                            {/* Proximity Badge (HOT/WARM/READY) */}
                            {proximityBadge && (
                                <span className={cn(
                                    "flex items-center gap-1 px-2 py-0.5 text-xs font-bold font-mono uppercase tracking-wider rounded border",
                                    proximityBadge.color
                                )}>
                                    <span>{proximityBadge.icon}</span>
                                    {proximityBadge.label}
                                </span>
                            )}
                        </div>

                        {/* Setup Archetype */}
                        <div className="flex items-center gap-2 text-sm text-zinc-500 font-mono">
                            <ChartLine size={14} className="text-zinc-600" />
                            <span className="text-zinc-400">{archetype.replace(/_/g, ' ')}</span>
                            <span className="w-1.5 h-1.5 rounded-full bg-zinc-700" />
                            <span>{result.timeframe || 'H4'}</span>
                            {result.metadata?.leverage && result.metadata.leverage > 1 && (
                                <>
                                    <span className="w-1.5 h-1.5 rounded-full bg-zinc-700" />
                                    <span className="text-[#00ff88]">{result.metadata.leverage}x</span>
                                </>
                            )}
                        </div>
                    </div>
                </div>

                {/* Center: Key Metrics */}
                <div className="flex items-center gap-8">
                    {/* Probability */}
                    <div className="flex flex-col items-end">
                        <span className="text-xs text-zinc-500 uppercase tracking-wider font-bold mb-0.5">Prob</span>
                        <span className={cn("font-mono text-2xl font-bold", getProbColor(confidence))}>
                            {confidence.toFixed(0)}%
                        </span>
                    </div>

                    {/* R:R with Visual Bar */}
                    <div className="flex flex-col items-end min-w-[100px]">
                        <span className="text-xs text-zinc-500 uppercase tracking-wider font-bold mb-0.5">R:R</span>
                        <span className="font-mono text-2xl font-bold text-zinc-300 mb-1">
                            {rr.toFixed(1)}R
                        </span>
                        {/* R:R Visual Bar */}
                        <div className="w-full h-1 bg-zinc-800 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-gradient-to-r from-emerald-500 to-green-400 transition-all duration-300"
                                style={{ width: `${rrPercent}%` }}
                            />
                        </div>
                    </div>

                    {/* Entry */}
                    <div className="flex flex-col items-end min-w-[100px]">
                        <span className="text-xs text-zinc-500 uppercase tracking-wider font-bold mb-0.5">Entry</span>
                        <span className="font-mono text-xl text-zinc-300">
                            {result.entryZone.high.toFixed(result.pair.includes('JPY') ? 2 : 4)}
                        </span>
                    </div>
                </div>

                {/* Right: Action */}
                <div className="flex items-center gap-4">
                    <div className="hidden sm:block px-4 py-2 rounded bg-[#00ff88]/5 border border-[#00ff88]/20 text-[#00ff88] text-sm font-mono opacity-0 group-hover:opacity-100 transition-opacity">
                        VIEW INTEL
                    </div>
                    <ArrowRight size={24} className="text-zinc-600 group-hover:text-[#00ff88] transition-colors" />
                </div>

            </div>

            {/* Metadata Badges Row */}
            {(structureQuality.length > 0 || setupCharacteristics.length > 0 || cyclePhase) && (
                <div className="flex items-center gap-2 flex-wrap mb-4 pb-4 border-b border-zinc-800/40">
                    {/* Structure Quality Badges */}
                    {structureQuality.map((badge, idx) => (
                        <span
                            key={`struct-${idx}`}
                            className="px-2 py-1 text-xs font-mono uppercase tracking-wider rounded border bg-violet-500/10 border-violet-500/20 text-violet-400"
                        >
                            {badge}
                        </span>
                    ))}

                    {/* Setup Characteristic Badges */}
                    {setupCharacteristics.map((badge, idx) => (
                        <span
                            key={`setup-${idx}`}
                            className="px-2 py-1 text-xs font-mono uppercase tracking-wider rounded border bg-teal-500/10 border-teal-500/20 text-teal-400"
                        >
                            {badge}
                        </span>
                    ))}

                    {/* Cycle Phase Badge */}
                    {cyclePhase && (
                        <span
                            className={cn(
                                "px-2 py-1 text-xs font-mono uppercase tracking-wider rounded border",
                                getCycleBadgeColor(cyclePhase)
                            )}
                        >
                            {cyclePhase}
                        </span>
                    )}
                </div>
            )}

            {/* Bottom Row: Stop/Targets & Factors */}
            <div className="flex items-start justify-between gap-8 pt-4 border-t border-zinc-800/40">

                {/* Left: Stop & Targets */}
                <div className="flex items-center gap-6 text-sm font-mono">
                    {/* Stop Loss */}
                    <div className="flex items-center gap-2">
                        <Shield size={16} className="text-red-400" />
                        <span className="text-zinc-500">Stop:</span>
                        <span className="text-red-400 font-semibold">
                            {result.stopLoss.toFixed(result.pair.includes('JPY') ? 2 : 4)}
                        </span>
                    </div>

                    {/* Targets */}
                    <div className="flex items-center gap-2">
                        <Target size={16} className="text-emerald-400" />
                        <span className="text-zinc-500">Targets:</span>
                        <div className="flex items-center gap-2">
                            {result.takeProfits.slice(0, 3).map((tp, idx) => (
                                <span key={idx} className="text-emerald-400 font-semibold">
                                    {tp.toFixed(result.pair.includes('JPY') ? 2 : 4)}
                                    {idx < Math.min(result.takeProfits.length, 3) - 1 && <span className="text-zinc-600 mx-1">→</span>}
                                </span>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Right: Top Factors */}
                {topFactors.length > 0 && (
                    <div className="flex items-center gap-2 text-xs">
                        <span className="text-zinc-500 uppercase tracking-wider font-bold">Top Factors:</span>
                        <div className="flex items-center gap-2">
                            {topFactors.map((factor, idx) => (
                                <span
                                    key={idx}
                                    className={cn(
                                        "px-2 py-0.5 rounded border font-mono",
                                        factor.score >= 80
                                            ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                                            : factor.score >= 60
                                                ? "bg-yellow-500/10 border-yellow-500/20 text-yellow-400"
                                                : "bg-orange-500/10 border-orange-500/20 text-orange-400"
                                    )}
                                >
                                    {factor.name.replace(/_/g, ' ')} ({factor.score.toFixed(0)})
                                </span>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {/* Hover Glow Effect */}
            <div className="absolute inset-x-0 bottom-0 h-[1px] bg-gradient-to-r from-transparent via-[#00ff88]/0 to-transparent group-hover:via-[#00ff88]/50 transition-all duration-300" />
        </div>
    );
}
