
import { ScanResult } from '@/utils/mockData';
import { TechPanel, SignalStrength } from '@/components/ui/TacticalComponents';
import { Target, TrendUp, TrendDown, Lightning, Crosshair } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

interface DashboardHomeProps {
    signal: ScanResult;
    metadata?: any;
}

export function DashboardHome({ signal, metadata }: DashboardHomeProps) {
    const isBullish = signal.trendBias === 'BULLISH';

    return (
        <div className="h-full w-full grid grid-cols-1 lg:grid-cols-2 gap-6 p-6 lg:p-10 animate-in fade-in slide-in-from-bottom-4 duration-500">

            {/* LEFT: FEATURED SIGNAL HERO */}
            <div className="flex flex-col gap-4">
                <TechPanel
                    className="flex-1 relative overflow-hidden group min-h-[400px]"
                    variant="scanner"
                    cornerAccents
                    scanline
                >
                    {/* Background Hero Image/Texture */}
                    <div className="absolute inset-0 bg-gradient-to-br from-black/40 to-transparent z-0" />
                    <div className="absolute -right-20 -top-20 opacity-10 text-white pointer-events-none">
                        <Target size={400} />
                    </div>

                    <div className="relative z-10 h-full flex flex-col justify-between">
                        {/* Header */}
                        <div className="flex justify-between items-start">
                            <div>
                                <div className="flex items-center gap-3 mb-2">
                                    <h2 className="text-6xl font-bold font-mono text-white tracking-tighter">
                                        {signal.pair}
                                    </h2>
                                    <div className={cn(
                                        "px-3 py-1 rounded text-sm font-bold border uppercase tracking-wider flex items-center gap-2",
                                        isBullish ? "bg-green-500/10 text-green-400 border-green-500/30" : "bg-red-500/10 text-red-400 border-red-500/30"
                                    )}>
                                        {isBullish ? <TrendUp weight="bold" /> : <TrendDown weight="bold" />}
                                        {signal.trendBias}
                                    </div>
                                </div>
                                <span className="text-sm text-muted-foreground font-mono">
                                    TIMEFRAME: <span className="text-white">{signal.timeframe || '1H'}</span> // CLASS: <span className="text-white">{signal.classification || 'SWING'}</span>
                                </span>
                            </div>

                            <div className="text-right">
                                <div className="text-6xl font-bold hud-text-green tabular-nums">
                                    {signal.confidenceScore}%
                                </div>
                                <div className="text-xs text-[#00ff88]/60 uppercase tracking-widest mt-1">
                                    PROBABILITY
                                </div>
                            </div>
                        </div>

                        {/* Middle Action Area (Mock Chart) */}
                        <div className="flex-1 border border-white/10 rounded-lg my-6 bg-black/20 flex items-center justify-center relative overflow-hidden group/chart">
                            <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-[#00ff88]/10 to-transparent" />
                            <span className="text-xs font-mono text-muted-foreground z-10 group-hover/chart:scale-110 transition-transform duration-300">
                                ► INTERACTIVE CHART PREVIEW
                            </span>
                        </div>

                        {/* Footer Controls */}
                        <div className="flex items-center gap-4">
                            <Button className="flex-1 bg-[#00ff88] text-black hover:bg-[#00ff88]/90 h-12 font-bold font-mono tracking-widest text-lg md:text-xl shadow-[0_0_20px_rgba(0,255,136,0.3)]">
                                EXECUTE STARTEGY
                            </Button>
                            <Button variant="outline" className="h-12 w-12 border-white/20 hover:bg-white/10">
                                <Crosshair size={24} />
                            </Button>
                        </div>
                    </div>
                </TechPanel>
            </div>

            {/* RIGHT: STAT QUADRANT */}
            <div className="grid grid-cols-2 gap-4 h-full">
                {/* Quadrant 1: Risk/Reward */}
                <TechPanel title="RISK PROFILE" className="flex flex-col justify-center items-center text-center">
                    <div className="text-5xl font-bold text-white font-mono mb-2">
                        1:{signal.riskReward}
                    </div>
                    <span className="text-xs font-mono text-muted-foreground uppercase tracking-widest">
                        RISK / REWARD RATIO
                    </span>
                    <div className="w-full h-2 bg-white/10 rounded-full mt-4 overflow-hidden">
                        <div className="h-full bg-cyan-400 w-[60%]" />
                    </div>
                </TechPanel>

                {/* Quadrant 2: Signal Strength */}
                <TechPanel title="SIGNAL POWER" className="flex flex-col justify-center items-center">
                    <div className="scale-150 mb-4">
                        <SignalStrength score={signal.confidenceScore} />
                    </div>
                    <span className="text-xs font-mono text-muted-foreground uppercase tracking-widest text-center mt-2">
                        TOP 5% OF SCANS
                    </span>
                </TechPanel>

                {/* Quadrant 3: Confluence */}
                <TechPanel title="CONFLUENCE" className="flex flex-col justify-center items-center">
                    <div className="relative w-24 h-24 flex items-center justify-center">
                        <div className="absolute inset-0 border-2 border-[#00ff88]/30 rounded-full animate-spin-slow-reverse" />
                        <div className="absolute inset-2 border border-white/10 rounded-full animate-spin-slow" />
                        <span className="text-3xl font-bold font-mono text-white">7/7</span>
                    </div>
                    <span className="text-xs font-mono text-muted-foreground uppercase tracking-widest mt-2">
                        FACTORS ALIGNED
                    </span>
                </TechPanel>

                {/* Quadrant 4: Market Context */}
                <TechPanel title="CONTEXT" className="flex flex-col justify-center items-center">
                    <div className="flex items-center gap-2 text-yellow-400 mb-2">
                        <Lightning size={32} weight="fill" />
                    </div>
                    <span className="text-lg font-bold text-white font-mono">HIGH VOL</span>
                    <span className="text-xs font-mono text-muted-foreground uppercase tracking-widest mt-1">
                        MARKET REGIME
                    </span>
                </TechPanel>
            </div>

        </div>
    );
}
