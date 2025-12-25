
import { motion } from 'framer-motion';
import { ScanResult } from '@/utils/mockData';
import { cn } from '@/lib/utils';
import { TrendUp, TrendDown } from '@phosphor-icons/react';

interface SignalCarouselProps {
    signals: ScanResult[];
    selectedId: string | null;
    onSelect: (signal: ScanResult) => void;
}

export function SignalCarousel({ signals, selectedId, onSelect }: SignalCarouselProps) {
    return (
        <div className="w-full h-full overflow-x-auto overflow-y-hidden no-scrollbar flex items-center gap-4 px-6 md:px-10 pb-4">
            {signals.map((signal) => {
                const isSelected = selectedId === signal.id;
                const isBullish = signal.trendBias === 'BULLISH';

                return (
                    <motion.div
                        key={signal.id}
                        layoutId={`card-${signal.id}`}
                        onClick={() => onSelect(signal)}
                        className={cn(
                            "flex-shrink-0 w-[220px] h-[140px] rounded-xl border cursor-pointer relative group overflow-hidden transition-all duration-300",
                            isSelected
                                ? "border-[#00ff88] bg-[#00ff88]/10 shadow-[0_0_20px_rgba(0,255,136,0.2)]"
                                : "border-white/10 bg-black/40 hover:border-white/30 hover:bg-white/5"
                        )}
                        whileHover={{ y: -5 }}
                    >
                        {/* Status Bar */}
                        <div className={cn(
                            "absolute top-0 left-0 right-0 h-1",
                            isBullish ? "bg-[#00ff88]" : "bg-red-500"
                        )} />

                        <div className="p-4 flex flex-col justify-between h-full">
                            <div className="flex justify-between items-start">
                                <span className="font-bold font-mono text-lg text-white group-hover:text-[#00ff88] transition-colors">
                                    {signal.pair}
                                </span>
                                <span className={cn(
                                    "text-xs font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider",
                                    isBullish
                                        ? "text-green-400 border-green-500/30 bg-green-500/10"
                                        : "text-red-400 border-red-500/30 bg-red-500/10"
                                )}>
                                    {signal.timeframe || '1H'}
                                </span>
                            </div>

                            {/* Mini Chart Placeholder */}
                            <div className="flex-1 w-full my-2 opacity-30 flex items-center justify-center border border-white/5 rounded border-dashed">
                                <span className="text-[10px] font-mono text-muted-foreground">CHART PREVIEW</span>
                            </div>

                            <div className="flex justify-between items-end">
                                <div className="flex flex-col">
                                    <span className="text-[10px] text-muted-foreground font-mono">CONFIDENCE</span>
                                    <span className="text-xl font-bold font-mono text-white tabular-nums">
                                        {signal.confidenceScore}%
                                    </span>
                                </div>
                                <div className="flex flex-col items-end">
                                    <span className="text-[10px] text-muted-foreground font-mono">R:R</span>
                                    <span className={cn(
                                        "text-sm font-bold font-mono",
                                        (signal.riskReward || 0) > 2 ? "text-[#00ff88]" : "text-white"
                                    )}>
                                        {signal.riskReward}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </motion.div>
                );
            })}
        </div>
    );
}
