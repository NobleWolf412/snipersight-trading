
import { ScanResult } from '@/utils/mockData';
import { cn } from '@/lib/utils';
import { TrendUp, TrendDown, Crosshair, SortAscending, Funnel, CaretRight } from '@phosphor-icons/react';
import { Badge } from '@/components/ui/badge';
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { SignalStrength } from '@/components/ui/TacticalComponents';

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
        <div className={cn("flex flex-col h-full bg-black/20 border-r border-white/5", className)}>
            {/* Sidebar Header */}
            <div className="p-4 border-b border-white/10 bg-black/40 backdrop-blur-md sticky top-0 z-20">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2 text-[#00ff88]">
                        <Crosshair weight="bold" className="animate-pulse" />
                        <span className="font-mono font-bold tracking-widest text-xs">INCOMING FEED</span>
                    </div>
                    <Badge variant="outline" className="bg-[#00ff88]/10 text-[#00ff88] border-[#00ff88]/30 font-mono text-[10px]">
                        {filteredResults.length} / {results.length}
                    </Badge>
                </div>

                {/* Tactical Filter Switch */}
                <div className="flex gap-1 p-1 bg-black/60 rounded-lg border border-white/5 relative">
                    {/* Animated Glint */}
                    <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-white/20 to-transparent pointer-events-none" />

                    {(['ALL', 'LONG', 'SHORT'] as const).map(f => (
                        <button
                            key={f}
                            onClick={() => setFilter(f)}
                            className={cn(
                                "flex-1 text-[10px] py-2 rounded font-bold transition-all uppercase tracking-wider relative overflow-hidden group",
                                filter === f
                                    ? "bg-[#00ff88] text-black shadow-[0_0_15px_rgba(0,255,136,0.3)]"
                                    : "text-muted-foreground hover:text-white hover:bg-white/5"
                            )}
                        >
                            <span className="relative z-10">{f}</span>
                            {filter === f && (
                                <span className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent pointer-events-none" />
                            )}
                        </button>
                    ))}
                </div>
            </div>

            {/* Scrollable List */}
            <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                {filteredResults.length > 0 ? (
                    <div className="flex flex-col gap-1 p-2">
                        <AnimatePresence mode="popLayout">
                            {filteredResults.map((result) => (
                                <TargetCard
                                    key={result.id}
                                    result={result}
                                    isSelected={selectedId === result.id}
                                    onClick={() => onSelect(result)}
                                />
                            ))}
                        </AnimatePresence>
                    </div>
                ) : (
                    <div className="p-12 flex flex-col items-center justify-center text-center opacity-40">
                        <div className="w-16 h-16 rounded-full border border-white/20 flex items-center justify-center mb-4">
                            <Funnel size={24} />
                        </div>
                        <span className="text-xs font-mono tracking-widest">NO SIGNALS DETECTED</span>
                    </div>
                )}
            </div>

            {/* Footer Controls */}
            <div className="p-3 border-t border-white/10 bg-black/40 backdrop-blur-sm text-[10px] flex justify-between items-center text-muted-foreground font-mono sticky bottom-0 z-20">

                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setSortBy(prev => prev === 'SCORE' ? 'RR' : 'SCORE')}
                        className="flex items-center gap-1 hover:text-white transition-colors uppercase"
                    >
                        <SortAscending size={14} />
                        SORT: <span className="text-white">{sortBy}</span>
                    </button>
                    <button
                        onClick={() => setSortOrder(prev => prev === 'DESC' ? 'ASC' : 'DESC')}
                        className="hover:text-white transition-colors font-bold"
                    >
                        {sortOrder}
                    </button>
                </div>

                <div className="flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-[#00ff88] animate-pulse" />
                    LIVE
                </div>
            </div>
        </div>
    );
}


function TargetCard({ result, isSelected, onClick }: { result: ScanResult; isSelected: boolean; onClick: () => void }) {
    const isBullish = result.trendBias === 'BULLISH';
    const confidenceColor = result.confidenceScore >= 80 ? "#00ff88" : result.confidenceScore >= 60 ? "#00ffff" : "#facc15";

    return (
        <motion.div
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            layout
            onClick={onClick}
            className={cn(
                "w-full relative overflow-hidden cursor-pointer transition-all duration-300 group rounded-xl border mb-2",
                isSelected
                    ? "bg-white/10 border-white/20 shadow-[0_0_20px_rgba(0,0,0,0.5)] scale-[1.02]"
                    : "bg-black/40 border-white/5 hover:border-white/20 hover:bg-white/5 hover:scale-[1.01]"
            )}
        >
            {/* Selection Glow */}
            {isSelected && (
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent animate-pulse opacity-50" />
            )}

            <div className="p-3 relative z-10 flex gap-3">

                {/* Confidence Ring Visual */}
                <div className="relative w-12 h-12 flex-shrink-0 flex items-center justify-center">
                    {/* Outer Ring */}
                    <svg className="absolute inset-0 w-full h-full rotate-90" viewBox="0 0 36 36">
                        <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#333" strokeWidth="3" />
                        <motion.path
                            initial={{ pathLength: 0 }}
                            animate={{ pathLength: result.confidenceScore / 100 }}
                            transition={{ duration: 1.5, ease: "easeOut" }}
                            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                            fill="none"
                            stroke={confidenceColor}
                            strokeWidth="3"
                            strokeDasharray="100, 100"
                        />
                    </svg>
                    {/* Inner Score */}
                    <div className="text-[10px] font-bold font-mono text-white tabular-nums z-10">
                        {result.confidenceScore}
                    </div>
                </div>

                {/* Card Content */}
                <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-start mb-0.5">
                        <h4 className={cn(
                            "font-bold font-mono text-sm tracking-wide truncate",
                            isSelected ? "text-white" : "text-white/70 group-hover:text-white"
                        )}>
                            {result.pair}
                        </h4>

                        {/* Direction Badge */}
                        <div className={cn(
                            "px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider flex items-center gap-1",
                            isBullish ? "text-[#00ff88] bg-[#00ff88]/10" : "text-red-400 bg-red-400/10"
                        )}>
                            {isBullish ? <TrendUp weight="bold" /> : <TrendDown weight="bold" />}
                            {result.trendBias === 'BULLISH' ? 'LONG' : 'SHORT'}
                        </div>
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-muted-foreground font-mono">
                        <span>{result.timeframe} // {result.classification}</span>
                        <span className={cn(
                            "flex items-center gap-1",
                            result.riskReward && result.riskReward > 2 ? "text-cyan-400" : "text-zinc-500"
                        )}>
                            R:R <b className="text-white">{result.riskReward}</b>
                        </span>
                    </div>
                </div>
            </div>

            {/* Corner Accent */}
            <div className={cn(
                "absolute top-0 right-0 w-2 h-2 border-t border-r transition-all duration-300",
                isSelected ? "border-white opacity-100" : "border-white/30 opacity-0 group-hover:opacity-100"
            )} />

        </motion.div>
    );
}
