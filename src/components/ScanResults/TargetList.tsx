
import { ScanResult } from '@/utils/mockData';
import { cn } from '@/lib/utils';
import { TrendUp, TrendDown, Crosshair, SortAscending, Funnel, Lightning, Target } from '@phosphor-icons/react';
import { Badge } from '@/components/ui/badge';
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface TargetListProps {
    results: ScanResult[];
    selectedId: string | null;
    onSelect: (result: ScanResult) => void;
    className?: string;
}

export function TargetList({ results, selectedId, onSelect, className }: TargetListProps) {
    const [filter, setFilter] = useState<'ALL' | 'LONG' | 'SHORT'>('ALL');
    const [sortBy, setSortBy] = useState<'SCORE' | 'RR'>('SCORE');
    const [sortOrder, setSortOrder] = useState<'ASC' | 'DESC'>('DESC');

    const filteredResults = results
        .filter(r => {
            if (filter === 'ALL') return true;
            return r.trendBias === (filter === 'LONG' ? 'BULLISH' : 'BEARISH');
        })
        .sort((a, b) => {
            let valA = sortBy === 'SCORE' ? a.confidenceScore : (a.riskReward || 0);
            let valB = sortBy === 'SCORE' ? b.confidenceScore : (b.riskReward || 0);
            return sortOrder === 'DESC' ? valB - valA : valA - valB;
        });

    return (
        <div className={cn("flex flex-col h-full min-h-0 overflow-hidden bg-black/30 border-r border-white/5", className)}>
            {/* Header */}
            <div className="px-4 py-3 border-b border-white/10 bg-black/60 backdrop-blur-md sticky top-0 z-20">
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2 text-[#00ff88]">
                        <Target weight="fill" size={18} className="animate-pulse drop-shadow-[0_0_8px_rgba(0,255,136,0.8)]" />
                        <span className="font-mono font-black tracking-[0.2em] text-xs uppercase">Targets</span>
                    </div>
                    <Badge variant="outline" className="bg-[#00ff88]/20 text-[#00ff88] border-[#00ff88]/50 font-mono text-xs px-2 py-0.5 shadow-[0_0_10px_rgba(0,255,136,0.3)]">
                        {filteredResults.length}
                    </Badge>
                </div>

                {/* Filter Pills */}
                <div className="flex gap-1 p-1 bg-black/80 rounded-lg border border-white/10 relative overflow-hidden">
                    {/* Animated Sweep */}
                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[#00ff88]/10 to-transparent animate-[sweep_3s_ease-in-out_infinite] pointer-events-none" />

                    {(['ALL', 'LONG', 'SHORT'] as const).map(f => (
                        <button
                            key={f}
                            onClick={() => setFilter(f)}
                            className={cn(
                                "flex-1 text-[10px] py-1.5 rounded font-black transition-all uppercase tracking-widest relative",
                                filter === f
                                    ? "bg-gradient-to-b from-[#00ff88] to-[#00cc6a] text-black shadow-[0_0_12px_rgba(0,255,136,0.5),inset_0_1px_0_rgba(255,255,255,0.3)]"
                                    : "text-zinc-500 hover:text-white hover:bg-white/10"
                            )}
                        >
                            {f}
                        </button>
                    ))}
                </div>
            </div>

            {/* Scrollable List */}
            <div className="flex-1 min-h-0 overflow-y-auto scrollbar-thin scrollbar-thumb-[#00ff88]/30 scrollbar-track-transparent">
                {filteredResults.length > 0 ? (
                    <div className="flex flex-col gap-2 p-3">
                        <AnimatePresence mode="popLayout">
                            {filteredResults.map((result, idx) => (
                                <TargetCard
                                    key={result.id}
                                    result={result}
                                    isSelected={selectedId === result.id}
                                    onClick={() => onSelect(result)}
                                    index={idx}
                                />
                            ))}
                        </AnimatePresence>
                    </div>
                ) : (
                    <div className="p-12 flex flex-col items-center justify-center text-center opacity-40">
                        <div className="w-14 h-14 rounded-full border border-white/20 flex items-center justify-center mb-3">
                            <Funnel size={24} />
                        </div>
                        <span className="text-xs font-mono tracking-widest">NO SIGNALS</span>
                    </div>
                )}
            </div>

            {/* Footer */}
            <div className="px-3 py-2 border-t border-white/10 bg-black/60 backdrop-blur-sm text-[10px] flex justify-between items-center text-zinc-600 font-mono sticky bottom-0 z-20">
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setSortBy(prev => prev === 'SCORE' ? 'RR' : 'SCORE')}
                        className="flex items-center gap-1 hover:text-white transition-colors uppercase"
                    >
                        <SortAscending size={12} />
                        <span className="text-zinc-400">{sortBy}</span>
                    </button>
                    <button
                        onClick={() => setSortOrder(prev => prev === 'DESC' ? 'ASC' : 'DESC')}
                        className="hover:text-white transition-colors font-black text-zinc-500"
                    >
                        {sortOrder === 'DESC' ? '↓' : '↑'}
                    </button>
                </div>

                <div className="flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-[#00ff88] animate-pulse shadow-[0_0_6px_rgba(0,255,136,0.8)]" />
                    <span className="text-[#00ff88]/70">LIVE</span>
                </div>
            </div>
        </div>
    );
}


function TargetCard({ result, isSelected, onClick, index }: { result: ScanResult; isSelected: boolean; onClick: () => void; index: number }) {
    const isBullish = result.trendBias === 'BULLISH';
    const score = result.confidenceScore;
    const confidenceColor = score >= 80 ? "#00ff88" : score >= 60 ? "#00ffff" : "#facc15";
    const glowColor = isBullish ? "rgba(0,255,136,0.5)" : "rgba(255,68,68,0.5)";
    const borderColor = isBullish ? "#00ff88" : "#ff4444";

    return (
        <motion.div
            initial={{ opacity: 0, x: -20, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            transition={{ delay: index * 0.03 }}
            layout
            onClick={onClick}
            className={cn(
                "relative cursor-pointer transition-all duration-300 group rounded-xl p-[2px] overflow-hidden",
                isSelected ? "scale-[1.02]" : "hover:scale-[1.01]"
            )}
        >
            {/* Gradient Border Background */}
            <div className={cn(
                "absolute inset-0 rounded-xl transition-opacity duration-300",
                isBullish ? "bg-gradient-to-br from-[#00ff88]/70 via-white/30 to-[#00ff88]/70" : "bg-gradient-to-br from-red-500/70 via-white/30 to-red-500/70",
                isSelected ? "opacity-100" : "opacity-50 group-hover:opacity-90"
            )} />

            {/* Animated Sweep Glow on Hover */}
            <div className={cn(
                "absolute inset-0 rounded-xl bg-gradient-to-r from-transparent via-white/30 to-transparent opacity-0 group-hover:opacity-60 blur-sm animate-[sweep_2s_linear_infinite] transition-opacity",
                isSelected && "opacity-40"
            )} />

            {/* Inner Card */}
            <div className={cn(
                "relative rounded-[10px] transition-all duration-300",
                isSelected
                    ? "bg-gradient-to-br from-[#0a0a0a] via-black to-[#0a0a0a]"
                    : "bg-gradient-to-br from-[#0d0d0d] via-[#080808] to-[#0d0d0d] group-hover:from-[#111] group-hover:via-[#0a0a0a] group-hover:to-[#111]"
            )}
                style={{
                    boxShadow: isSelected ? `0 0 30px ${glowColor}, inset 0 0 20px ${glowColor}` : undefined
                }}
            >
                {/* Top Edge Glow */}
                <div className={cn(
                    "absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent to-transparent transition-opacity",
                    isSelected ? "via-white/60 opacity-100" : "via-white/30 opacity-0 group-hover:opacity-100"
                )} style={{ background: isSelected ? `linear-gradient(to right, transparent, ${borderColor}60, transparent)` : undefined }} />

                {/* Content */}
                <div className="p-5 relative z-10 flex items-center gap-4">

                    {/* Score Ring with Enhanced Glow */}
                    <div className="relative w-14 h-14 flex-shrink-0 flex items-center justify-center">
                        {/* Outer Glow Ring */}
                        <div className={cn(
                            "absolute inset-0 rounded-full transition-opacity duration-300",
                            isSelected ? "opacity-60" : "opacity-0 group-hover:opacity-40"
                        )} style={{ boxShadow: `0 0 20px ${confidenceColor}, inset 0 0 10px ${confidenceColor}40` }} />

                        <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 36 36">
                            <circle cx="18" cy="18" r="14" fill="none" stroke="#1a1a1a" strokeWidth="3" />
                            <motion.circle
                                initial={{ strokeDashoffset: 88 }}
                                animate={{ strokeDashoffset: 88 - (88 * score / 100) }}
                                transition={{ duration: 1, ease: "easeOut" }}
                                cx="18" cy="18" r="14"
                                fill="none"
                                stroke={confidenceColor}
                                strokeWidth="3"
                                strokeDasharray="88"
                                strokeLinecap="round"
                                style={{
                                    filter: `drop-shadow(0 0 8px ${confidenceColor})`
                                }}
                            />
                        </svg>
                        <div className="text-base font-black font-mono text-white tabular-nums z-10" style={{ textShadow: `0 0 12px ${confidenceColor}` }}>
                            {Math.round(score)}
                        </div>
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2 mb-1.5">
                            <h4 className={cn(
                                "font-black font-mono text-lg tracking-wide truncate transition-colors",
                                isSelected ? "text-white" : "text-zinc-200 group-hover:text-white"
                            )}>
                                {result.pair}
                            </h4>

                            {/* Direction Badge with Glow */}
                            <div className={cn(
                                "px-2.5 py-1 rounded-lg text-[10px] font-black uppercase tracking-wider flex items-center gap-1.5 shrink-0 border transition-all",
                                isBullish
                                    ? "text-[#00ff88] bg-[#00ff88]/15 border-[#00ff88]/40 shadow-[0_0_15px_rgba(0,255,136,0.3)] group-hover:shadow-[0_0_20px_rgba(0,255,136,0.5)]"
                                    : "text-red-400 bg-red-500/15 border-red-500/40 shadow-[0_0_15px_rgba(255,68,68,0.3)] group-hover:shadow-[0_0_20px_rgba(255,68,68,0.5)]"
                            )}>
                                {isBullish ? <TrendUp weight="bold" size={12} /> : <TrendDown weight="bold" size={12} />}
                                {isBullish ? 'LONG' : 'SHORT'}
                            </div>
                        </div>

                        <div className="flex items-center justify-between text-xs text-zinc-400 font-mono">
                            <span className="truncate">{result.timeframe} · {result.classification}</span>
                            <span className={cn(
                                "flex items-center gap-1 shrink-0",
                                result.riskReward && result.riskReward >= 2 ? "text-cyan-400" : "text-zinc-300"
                            )}>
                                <Lightning weight="fill" size={12} className="text-yellow-400" />
                                <b className="text-white">{result.riskReward?.toFixed(1)}R</b>
                            </span>
                        </div>
                    </div>
                </div>

                {/* Animated Corner Accents */}
                <div className={cn(
                    "absolute top-0 right-0 w-4 h-4 border-t-2 border-r-2 rounded-tr-lg transition-all duration-300",
                    isSelected ? `border-[${borderColor}] opacity-100 w-6 h-6` : "border-white/20 opacity-0 group-hover:opacity-100 group-hover:w-5 group-hover:h-5"
                )} style={{ borderColor: isSelected ? borderColor : undefined }} />
                <div className={cn(
                    "absolute bottom-0 left-0 w-4 h-4 border-b-2 border-l-2 rounded-bl-lg transition-all duration-300",
                    isSelected ? `border-[${borderColor}] opacity-100 w-6 h-6` : "border-white/20 opacity-0 group-hover:opacity-100 group-hover:w-5 group-hover:h-5"
                )} style={{ borderColor: isSelected ? borderColor : undefined }} />
                <div className={cn(
                    "absolute top-0 left-0 w-4 h-4 border-t-2 border-l-2 rounded-tl-lg transition-all duration-300",
                    isSelected ? `border-[${borderColor}] opacity-100 w-6 h-6` : "border-white/20 opacity-0 group-hover:opacity-100 group-hover:w-5 group-hover:h-5"
                )} style={{ borderColor: isSelected ? borderColor : undefined }} />
                <div className={cn(
                    "absolute bottom-0 right-0 w-4 h-4 border-b-2 border-r-2 rounded-br-lg transition-all duration-300",
                    isSelected ? `border-[${borderColor}] opacity-100 w-6 h-6` : "border-white/20 opacity-0 group-hover:opacity-100 group-hover:w-5 group-hover:h-5"
                )} style={{ borderColor: isSelected ? borderColor : undefined }} />
            </div>
        </motion.div>
    );
}

