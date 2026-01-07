import { ArrowRight, TrendUp, TrendDown, Crosshair } from '@phosphor-icons/react';
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

    // For now using confidence as the primary metric displayed

    return (
        <div
            onClick={() => onClick?.(result.id)}
            className="group relative w-full p-6 mb-4 bg-[#0a0f0a] border border-zinc-800/60 hover:border-[#00ff88]/60 rounded-xl cursor-pointer transition-all duration-300 hover:bg-zinc-900/50 hover:shadow-[0_0_20px_rgba(0,255,136,0.15)]"
        >
            <div className="flex items-center justify-between">

                {/* Left: Symbol & Direction */}
                <div className="flex items-center gap-6">
                    <div className={cn(
                        "flex items-center justify-center w-14 h-14 rounded-xl bg-black/40 border",
                        isLong ? "border-green-500/20 text-green-400" : "border-red-500/20 text-red-400"
                    )}>
                        {isLong ? <TrendUp size={32} weight="bold" /> : <TrendDown size={32} weight="bold" />}
                    </div>

                    <div>
                        <div className="flex items-center gap-3">
                            <span className="text-2xl font-bold tracking-tight text-zinc-100">{result.pair}</span>
                            <span className={cn(
                                "px-2 py-0.5 text-xs font-mono uppercase tracking-wider rounded border",
                                isLong
                                    ? "bg-green-500/10 border-green-500/20 text-green-400"
                                    : "bg-red-500/10 border-red-500/20 text-red-400"
                            )}>
                                {result.classification}
                            </span>
                        </div>
                        <div className="text-sm text-zinc-500 font-mono flex items-center gap-2 mt-1">
                            <span>{result.timeframe || 'H4'}</span>
                            <span className="w-1.5 h-1.5 rounded-full bg-zinc-700" />
                            <span>{result.plan_type}</span>
                            {result.metadata?.leverage && result.metadata.leverage > 1 && (
                                <>
                                    <span className="w-1.5 h-1.5 rounded-full bg-zinc-700" />
                                    <span className="text-[#00ff88]">{result.metadata.leverage}x</span>
                                    {result.metadata.leverage_stop_adjustment && (
                                        <span className="text-amber-400 text-xs">⚡ STOP ADJ</span>
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                </div>

                {/* Center: Key Metrics */}
                <div className="flex items-center gap-12 hidden md:flex">
                    <div className="flex flex-col items-end">
                        <span className="text-xs text-zinc-500 uppercase tracking-wider font-bold mb-0.5">Prob</span>
                        <span className={cn(
                            "font-mono text-2xl font-bold",
                            confidence >= 80 ? "text-[#00ff88]" : "text-zinc-300"
                        )}>
                            {confidence.toFixed(0)}%
                        </span>
                    </div>

                    <div className="flex flex-col items-end">
                        <span className="text-xs text-zinc-500 uppercase tracking-wider font-bold mb-0.5">R:R</span>
                        <span className="font-mono text-2xl font-bold text-zinc-300">
                            {rr.toFixed(1)}R
                        </span>
                    </div>

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

            {/* Hover Glow Effect */}
            <div className="absolute inset-x-0 bottom-0 h-[1px] bg-gradient-to-r from-transparent via-[#00ff88]/0 to-transparent group-hover:via-[#00ff88]/50 transition-all duration-300" />
        </div>
    );
}
