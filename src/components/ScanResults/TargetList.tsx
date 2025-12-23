
import { ScanResult } from '@/utils/mockData';
import { cn } from '@/lib/utils';
import { TrendUp, TrendDown, Crosshair, SortAscending, Funnel } from '@phosphor-icons/react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useState } from 'react';

interface TargetListProps {
    results: ScanResult[];
    selectedId: string | null;
    onSelect: (result: ScanResult) => void;
    className?: string;
}

export function TargetList({ results, selectedId, onSelect, className }: TargetListProps) {
    const [filter, setFilter] = useState<'ALL' | 'LONG' | 'SHORT'>('ALL');

    const filteredResults = results.filter(r => {
        if (filter === 'ALL') return true;
        return r.trendBias === (filter === 'LONG' ? 'BULLISH' : 'BEARISH');
    });

    return (
        <div className={cn("flex flex-col h-full bg-black/20 border-r border-[#00ff88]/10", className)}>
            {/* Sidebar Header */}
            <div className="p-4 border-b border-[#00ff88]/20 bg-[#00ff88]/5 backdrop-blur-md">
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2 text-[#00ff88]">
                        <Crosshair weight="bold" className="animate-pulse" />
                        <span className="font-mono font-bold tracking-widest text-xs">INCOMING FEED</span>
                    </div>
                    <Badge variant="outline" className="bg-[#00ff88]/10 text-[#00ff88] border-[#00ff88]/30 font-mono text-[10px]">
                        {filteredResults.length} / {results.length}
                    </Badge>
                </div>

                {/* Filter Tabs */}
                <div className="flex gap-1 p-1 bg-black/40 rounded-lg">
                    {(['ALL', 'LONG', 'SHORT'] as const).map(f => (
                        <button
                            key={f}
                            onClick={() => setFilter(f)}
                            className={cn(
                                "flex-1 text-[10px] py-1.5 rounded font-bold transition-all uppercase tracking-wider",
                                filter === f
                                    ? "bg-[#00ff88]/20 text-[#00ff88] shadow-[0_0_10px_rgba(0,255,136,0.1)]"
                                    : "text-muted-foreground hover:bg-white/5"
                            )}
                        >
                            {f}
                        </button>
                    ))}
                </div>
            </div>

            {/* Scrollable List */}
            <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-[#00ff88]/20 scrollbar-track-transparent">
                {filteredResults.length > 0 ? (
                    <div className="divide-y divide-white/5">
                        {filteredResults.map((result) => (
                            <TargetListItem
                                key={result.id}
                                result={result}
                                isSelected={selectedId === result.id}
                                onClick={() => onSelect(result)}
                            />
                        ))}
                    </div>
                ) : (
                    <div className="p-8 text-center text-muted-foreground text-xs font-mono">
                        NO TARGETS MATCHING FILTER
                    </div>
                )}
            </div>

            {/* Footer Controls */}
            <div className="p-3 border-t border-[#00ff88]/20 bg-black/40 text-[10px] flex justify-between text-muted-foreground font-mono">
                <button className="flex items-center gap-1 hover:text-[#00ff88] transition-colors">
                    <SortAscending size={14} /> SORT: SCORE
                </button>
                <button className="flex items-center gap-1 hover:text-[#00ff88] transition-colors">
                    <Funnel size={14} /> FILTERS
                </button>
            </div>
        </div>
    );
}

function TargetListItem({ result, isSelected, onClick }: { result: ScanResult; isSelected: boolean; onClick: () => void }) {
    const isBullish = result.trendBias === 'BULLISH';
    const scoreColor = result.confidenceScore >= 80 ? 'text-[#00ff88]' : result.confidenceScore >= 60 ? 'text-amber-400' : 'text-red-400';

    return (
        <div
            onClick={onClick}
            className={cn(
                "w-full p-4 cursor-pointer transition-all group relative overflow-hidden",
                isSelected
                    ? "bg-[#00ff88]/10 shadow-[inset_4px_0_0_#00ff88]"
                    : "hover:bg-white/5 border-l-4 border-transparent hover:border-white/10"
            )}
        >
            {/* Selection Glow - Only visible when selected */}
            {isSelected && (
                <div className="absolute inset-0 bg-gradient-to-r from-[#00ff88]/10 to-transparent pointer-events-none" />
            )}

            <div className="flex justify-between items-start mb-1 relative z-10">
                <div className="font-bold text-sm tracking-wide group-hover:text-white transition-colors">
                    {result.pair}
                </div>
                <div className={cn("font-mono font-bold text-sm tabular-nums", scoreColor)}>
                    {result.confidenceScore}%
                </div>
            </div>

            <div className="flex justify-between items-center relative z-10">
                <div className={cn(
                    "text-[10px] font-bold flex items-center gap-1 px-1.5 py-0.5 rounded border",
                    isBullish
                        ? "text-green-400 border-green-500/30 bg-green-500/10"
                        : "text-red-400 border-red-500/30 bg-red-500/10"
                )}>
                    {isBullish ? <TrendUp size={12} weight="bold" /> : <TrendDown size={12} weight="bold" />}
                    {result.trendBias}
                </div>

                <div className="text-[10px] font-mono text-muted-foreground group-hover:text-white/70 transition-colors">
                    EV: <span className={result.riskReward && result.riskReward > 2 ? "text-green-400" : ""}>+{result.riskReward}R</span>
                </div>
            </div>
        </div>
    );
}
