import { ScanResult } from '@/utils/mockData';
import { LightweightChart } from '@/components/charts/LightweightChart';
import { Target, ShieldWarning, Crosshair, TrendUp, TrendDown, X } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

interface IntelDossierProps {
    result: ScanResult;
    onClose: () => void;
}

export function IntelDossier({ result, onClose }: IntelDossierProps) {
    const isLong = result.trendBias === 'BULLISH';

    // Determine the optimal single chart timeframe based on mode
    // Overwatch -> 4h, Surgical -> 15m, Strike -> 1h, Stealth -> 4h
    const mode = result.sniper_mode?.toLowerCase() || 'tactical';

    let chartTimeframe = '4h'; // Default
    if (mode.includes('surgical')) chartTimeframe = '15m';
    if (mode.includes('strike')) chartTimeframe = '1h';
    if (mode.includes('stealth')) chartTimeframe = '4h';
    if (mode.includes('overwatch')) chartTimeframe = '4h';

    // Format prices for display
    const formatPrice = (p: number) => p.toFixed(result.pair.includes('JPY') ? 2 : 4);

    return (
        <div className="w-full mt-8 animate-in slide-in-from-top-4 duration-500 fade-in">
            {/* Page Break / Divider */}
            <div className="flex items-center gap-4 mb-8">
                <div className="h-px flex-1 bg-gradient-to-r from-transparent via-[#00ff88]/50 to-transparent" />
                <div className="px-4 py-1 rounded-full border border-[#00ff88]/30 bg-[#00ff88]/5 text-[#00ff88] text-xs font-mono font-bold tracking-[0.2em] shadow-[0_0_15px_rgba(0,255,136,0.2)]">
                    MISSION INTEL
                </div>
                <div className="h-px flex-1 bg-gradient-to-r from-transparent via-[#00ff88]/50 to-transparent" />
            </div>

            <div className="relative w-full bg-[#050505] border border-zinc-800 rounded-2xl overflow-hidden shadow-2xl">

                {/* Close Button */}
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 z-20 p-2 rounded-lg bg-black/40 text-zinc-500 hover:text-white hover:bg-zinc-800 transition-colors border border-transparent hover:border-zinc-700"
                >
                    <X size={20} />
                </button>

                {/* 1. MISSION HEADER */}
                <div className="p-8 border-b border-zinc-800/60 bg-zinc-900/20">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                        <div className="flex items-center gap-6">
                            <div className={cn(
                                "flex items-center justify-center w-20 h-20 rounded-2xl border-2 shadow-[0_0_30px_-5px_rgba(0,0,0,0.5)]",
                                isLong ? "bg-green-500/10 border-green-500/30 text-green-400" : "bg-red-500/10 border-red-500/30 text-red-400"
                            )}>
                                {isLong ? <TrendUp size={40} weight="fill" /> : <TrendDown size={40} weight="fill" />}
                            </div>
                            <div>
                                <h2 className="text-4xl md:text-5xl font-black tracking-tighter text-white mb-2">
                                    {result.pair}
                                </h2>
                                <div className="flex items-center gap-3">
                                    <span className={cn(
                                        "px-2.5 py-1 text-sm font-bold font-mono uppercase tracking-wider rounded border",
                                        isLong ? "text-green-400 border-green-500/30 bg-green-500/5" : "text-red-400 border-red-500/30 bg-red-500/5"
                                    )}>
                                        {result.trendBias}
                                    </span>
                                    <span className="w-1.5 h-1.5 rounded-full bg-zinc-700" />
                                    <span className="text-zinc-400 font-mono text-base tracking-wide uppercase">
                                        {result.classification} PROTOCOL
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Quick Score */}
                        <div className="flex items-end flex-col">
                            <div className="text-xs uppercase tracking-[0.2em] text-zinc-400 font-bold mb-1">Confidence Score</div>
                            <div className="text-6xl font-mono font-bold text-[#00ff88] tracking-tighter drop-shadow-[0_0_15px_rgba(0,255,136,0.3)]">
                                {result.confidenceScore}%
                            </div>
                        </div>
                    </div>
                </div>

                <div className="flex flex-col">

                    {/* TOP ROW: Analysis & Execution */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-zinc-800/60 border-b border-zinc-800/60">
                        {/* 2. SECTOR 1: THE WHY (Confluence) */}
                        <div className="p-8 space-y-6">
                            <div className="flex items-center gap-3 mb-6 relative">
                                <h3 className="text-xl font-bold hud-headline hud-text-green tracking-wide">SECTOR 1: ANALYSIS</h3>
                            </div>

                            <div className="space-y-4">
                                {/* Mock Scorecard Items based on score */}
                                <ScoreItem label="Market Structure" value={result.confidenceScore > 70 ? "ALIGNED" : "MIXED"} active={result.confidenceScore > 70} />
                                <ScoreItem label="Momentum" value="CONFIRMED" active={true} />
                                <ScoreItem label="Key Level" value="RECLAIMED" active={true} />
                                <ScoreItem label="Volatility" value="EXPANDING" active={false} />
                            </div>

                            <div className="pt-6 border-t border-zinc-800">
                                <h4 className="text-[#00ff88] text-sm font-bold font-mono uppercase tracking-widest mb-3 opacity-80">Primary Driver</h4>
                                <p className="text-zinc-200 leading-relaxed text-lg font-light border-l-2 border-[#00ff88]/50 pl-4">
                                    Price action indicates a strong <span className={isLong ? "text-green-400 font-bold" : "text-red-400 font-bold"}>{isLong ? 'demand' : 'supply'}</span> imbalance on the <span className="text-white font-mono">{chartTimeframe.toUpperCase()}</span> timeframe.
                                    {result.riskReward && result.riskReward > 3 ? <span className="text-[#00ff88]"> High R:R opportunity detected.</span> : ""}
                                </p>
                            </div>
                        </div>

                        {/* 3. SECTOR 2: THE PLAN (Execution) */}
                        <div className="p-8 space-y-6 bg-zinc-900/10">
                            <div className="flex items-center gap-3 mb-6 relative">
                                <h3 className="text-xl font-bold hud-headline text-amber-400 tracking-wide drop-shadow-[0_0_4px_rgba(251,191,36,0.5)]">SECTOR 2: EXECUTION PLAN</h3>
                            </div>

                            <div className="space-y-6">
                                <div className="grid grid-cols-2 gap-8">
                                    <div>
                                        <div className="text-xs uppercase text-cyan-400 font-bold mb-1 font-mono tracking-wider">Entry Zone</div>
                                        <div className="text-2xl font-mono text-cyan-300 tracking-tight">
                                            {formatPrice(result.entryZone.low)}
                                        </div>
                                        <div className="text-sm font-mono text-cyan-400/60">to {formatPrice(result.entryZone.high)}</div>
                                    </div>
                                    <div className="text-right">
                                        <div className="text-xs uppercase text-red-400 font-bold mb-1 font-mono tracking-wider">Stop Loss</div>
                                        <div className="text-2xl font-mono text-red-400 tracking-tight">
                                            {formatPrice(result.stopLoss)}
                                        </div>
                                        {result.stopLossRationale && (
                                            <div className="text-[10px] text-zinc-500 font-mono mt-1 max-w-[150px] leading-tight ml-auto">
                                                {result.stopLossRationale}
                                            </div>
                                        )}
                                    </div>
                                </div>

                                <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800 shadow-inner">
                                    <div className="flex justify-between items-center mb-2">
                                        <span className="text-sm font-bold text-[#00ff88] font-mono tracking-wide uppercase">Target 1</span>
                                        <span className="font-mono text-[#00ff88] text-lg">{formatPrice(result.takeProfits[0])}</span>
                                    </div>
                                    <div className="flex justify-between items-center opacity-70">
                                        <span className="text-sm font-bold text-[#00ff88]/70 font-mono tracking-wide uppercase">Target 2</span>
                                        <span className="font-mono text-[#00ff88]/70">{formatPrice(result.takeProfits[1] || result.takeProfits[0] * 1.02)}</span>
                                    </div>
                                </div>

                                <div className="flex items-center justify-between pt-2">
                                    <div className="text-sm uppercase font-bold text-zinc-400 font-mono tracking-wider">Risk : Reward</div>
                                    <div className="text-3xl font-mono font-bold text-zinc-200">1 : {(result.riskReward || 2.5).toFixed(1)}</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* 4. SECTOR 3: SURVEILLANCE (Chart) - Full Width Bottom */}
                    <div className="w-full h-[500px] border-t border-zinc-800 bg-black relative flex flex-col">
                        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 flex items-center gap-3">
                            <h3 className="text-xl font-bold hud-headline text-blue-400 tracking-wide drop-shadow-[0_0_4px_rgba(96,165,250,0.5)]">
                                SECTOR 3: SURVEILLANCE ({chartTimeframe.toUpperCase()})
                            </h3>
                        </div>

                        <div className="flex-1 w-full h-full relative">
                            <LightweightChart
                                symbol={result.pair}
                                timeframe={chartTimeframe}
                                orderBlocks={result.orderBlocks ? result.orderBlocks.map(ob => ({
                                    ...ob,
                                    price_high: (ob as any).high || ob.price * 1.001,
                                    price_low: (ob as any).low || ob.price * 0.999,
                                    timestamp: Math.floor(Date.now() / 1000), // Mock timestamp if missing
                                })) : []}
                                entryPrice={result.entryZone.high}
                                stopLoss={result.stopLoss}
                                takeProfit={result.takeProfits[0]}
                                className="h-full w-full border-none"
                                showLegend={false}
                                uniformOBColor={true}
                            />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

function ScoreItem({ label, value, active }: { label: string, value: string, active: boolean }) {
    // Determine color based on value/active state
    // User requested "Mixed", "Expanding" etc to be glowing yellow
    const isNeutral = value === "MIXED" || value === "RANGING" || value === "EXPANDING";
    const colorClass = isNeutral ? "text-yellow-400 border-yellow-400/30 bg-yellow-400/10 shadow-[0_0_10px_rgba(250,204,21,0.2)]" :
        active ? "text-[#00ff88] border-[#00ff88]/30 bg-[#00ff88]/10 shadow-[0_0_10px_rgba(0,255,136,0.2)]" :
            "text-zinc-400 border-zinc-700 bg-zinc-800";

    return (
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800/40 last:border-0">
            <span className="text-xs font-bold font-mono tracking-widest text-zinc-400 uppercase">{label}</span>
            <div className={cn(
                "flex items-center gap-2 px-3 py-1 rounded text-xs font-bold tracking-wider border",
                colorClass
            )}>
                {active && !isNeutral && <span className="w-1.5 h-1.5 rounded-full bg-[#00ff88] animate-pulse" />}
                {isNeutral && <span className="w-1.5 h-1.5 rounded-full bg-yellow-400" />}
                {value}
            </div>
        </div>
    )
}
