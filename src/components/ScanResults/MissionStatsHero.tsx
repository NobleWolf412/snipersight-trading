
// Visual Overhaul: Mission Stats Hero (Centered & Beautiful)
import { motion } from 'framer-motion';
import { ScanResult } from '@/utils/mockData';
import { Target, Lightning, Crosshair, Globe, CheckCircle, WifiHigh, ChartLineUp, TrendUp, TrendDown } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { TechPanel } from '@/components/ui/TacticalComponents';

interface MissionStatsHeroProps {
    results: ScanResult[];
    metadata?: any;
}


export function MissionStatsHero({ results, metadata }: MissionStatsHeroProps) {
    const totalTargets = results.length;
    const longCount = results.filter(r => r.trendBias === 'BULLISH').length;
    const shortCount = results.filter(r => r.trendBias === 'BEARISH').length;

    // Sort by confidence desceding and take top 3
    const topTargets = [...results].sort((a, b) => b.confidenceScore - a.confidenceScore).slice(0, 3);

    return (
        <div className="h-full w-full flex items-center justify-center p-6 relative overflow-hidden overflow-y-auto no-scrollbar">

            {/* Ambient Background Glows */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none sticky top-0">
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-accent/5 rounded-full blur-[100px]" />
                <div className="absolute top-0 right-0 w-[300px] h-[300px] bg-accent/5 rounded-full blur-[80px]" />
            </div>

            {/* MAIN CENTRAL CONTAINER */}
            <motion.div
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, ease: "backOut" }}
                className="relative z-10 w-full h-full flex flex-col p-2"
            >
                {/* ADVANCED TECH FRAME */}
                <div className="flex-1 flex flex-col bg-black/40 backdrop-blur-xl rounded-lg overflow-hidden relative group">

                    {/* Corner Borders SVGs */}
                    <div className="absolute top-0 left-0 w-12 h-12 border-l-2 border-t-2 border-accent/30 rounded-tl-xl" />
                    <div className="absolute top-0 right-0 w-12 h-12 border-r-2 border-t-2 border-accent/30 rounded-tr-xl" />
                    <div className="absolute bottom-0 left-0 w-12 h-12 border-l-2 border-b-2 border-accent/30 rounded-bl-xl" />
                    <div className="absolute bottom-0 right-0 w-12 h-12 border-r-2 border-b-2 border-accent/30 rounded-br-xl" />

                    {/* Decorative Notches */}
                    <div className="absolute top-0 left-1/2 -translate-x-1/2 w-32 h-1 bg-accent/20" />
                    <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-32 h-1 bg-accent/20" />

                    <div className="flex-1 p-8 md:p-14 flex flex-col relative z-10">

                        {/* HEADER SECTION */}
                        <div className="flex flex-col md:flex-row items-center justify-between mb-8 shrink-0">
                            <div className="flex items-center gap-6">
                                <div className="relative w-20 h-20 flex items-center justify-center">
                                    <div className="absolute inset-0 bg-accent/10 rounded-full animate-ping opacity-20" />
                                    <div className="absolute inset-0 border border-accent/40 rounded-full animate-spin-slow-reverse border-dashed" />
                                    <CheckCircle weight="fill" className="text-accent w-10 h-10 drop-shadow-[0_0_15px_rgba(0,255,170,0.5)]" />
                                </div>
                                <div className="text-left">
                                    <div className="flex items-center gap-2 mb-1">
                                        <div className="w-2 h-2 bg-accent animate-pulse" />
                                        <div className="text-xs font-bold tracking-[0.3em] text-accent uppercase opacity-80">MISSION STATUS</div>
                                    </div>
                                    <h1 className="text-4xl md:text-5xl font-bold font-mono text-white tracking-tighter bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">
                                        SCAN COMPLETE
                                    </h1>
                                </div>
                            </div>

                            {/* STATS ROW */}
                            <div className="flex items-center gap-4 mt-4 md:mt-0 p-4 bg-white/5 rounded-xl border border-white/5">
                                <StatPill label="TARGETS IDENTIFIED" value={totalTargets} icon={<Target />} />
                                <div className="w-px h-8 bg-white/10" />
                                <StatPill label="MARKET BIAS" value={longCount > shortCount ? "BULLISH" : "BEARISH"} icon={<ChartLineUp />} color={longCount > shortCount ? 'green' : 'red'} />
                            </div>
                        </div>

                        {/* SEPARATOR */}
                        <div className="relative h-px w-full bg-gradient-to-r from-transparent via-accent/30 to-transparent my-6">
                            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 rotate-45 border border-accent bg-black" />
                        </div>

                        {/* PRIORITY TARGETS GRID (TOP 3) - EXPANDED */}
                        {topTargets.length > 0 && (
                            <div className="flex-1 flex flex-col min-h-0 pt-4">
                                <div className="text-xs text-accent font-bold tracking-[0.3em] uppercase mb-6 opacity-80 flex items-center gap-4 shrink-0">
                                    <Target size={16} />
                                    PRIORITY INTERCEPTS
                                </div>

                                <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-8 min-h-0">
                                    {topTargets.map((target, i) => (
                                        <motion.div
                                            key={target.id}
                                            initial={{ y: 20, opacity: 0 }}
                                            animate={{ y: 0, opacity: 1 }}
                                            transition={{ delay: 0.2 + (i * 0.1) }}
                                            className="group relative bg-[#0A0A0A] hover:bg-white/5 border border-white/10 hover:border-accent/50 rounded-lg p-8 transition-all duration-300 cursor-pointer flex flex-col overflow-hidden hover:-translate-y-1 hover:shadow-[0_0_30px_-5px_rgba(0,255,136,0.15)]"
                                        >
                                            {/* Tech Corners (Mini) */}
                                            <div className="absolute top-0 left-0 w-3 h-3 border-l-2 border-t-2 border-white/20 group-hover:border-accent transition-colors" />
                                            <div className="absolute top-0 right-0 w-3 h-3 border-r-2 border-t-2 border-white/20 group-hover:border-accent transition-colors" />
                                            <div className="absolute bottom-0 left-0 w-3 h-3 border-l-2 border-b-2 border-white/20 group-hover:border-accent transition-colors" />
                                            <div className="absolute bottom-0 right-0 w-3 h-3 border-r-2 border-b-2 border-white/20 group-hover:border-accent transition-colors" />

                                            {/* Card Header */}
                                            <div className="flex justify-between items-start mb-auto relative z-10">
                                                <div className="w-12 h-12 rounded bg-accent/5 border border-accent/20 flex items-center justify-center text-accent">
                                                    <Target size={24} weight="bold" />
                                                </div>
                                                <div className="text-right">
                                                    <div className="text-4xl font-bold text-accent tabular-nums tracking-tighter">{target.confidenceScore}%</div>
                                                    <div className="text-[10px] text-muted-foreground tracking-widest uppercase font-bold">Probability</div>
                                                </div>
                                            </div>

                                            {/* Card Main */}
                                            <div className="relative z-10 my-8 pl-2 border-l-2 border-white/10 group-hover:border-accent/50 transition-colors">
                                                <div className="text-4xl md:text-5xl font-bold text-white font-mono mb-2 tracking-tighter">{target.pair}</div>

                                                <div className="flex flex-wrap gap-2">
                                                    <div className={cn(
                                                        "inline-flex items-center gap-1.5 px-3 py-1 rounded-none text-xs font-bold border-l-2 uppercase tracking-wider bg-white/5",
                                                        target.trendBias === 'BULLISH' ? "border-green-500 text-green-400" : "border-red-500 text-red-400"
                                                    )}>
                                                        {target.trendBias === 'BULLISH' ? <TrendUp weight="bold" /> : <TrendDown weight="bold" />}
                                                        {target.trendBias}
                                                    </div>
                                                </div>
                                            </div>

                                            {/* Card Footer */}
                                            <div className="relative z-10 pt-4 border-t border-dashed border-white/10 grid grid-cols-2 gap-4">
                                                <div>
                                                    <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Risk:Reward</div>
                                                    <div className="text-xl font-mono text-white font-bold">{target.riskReward}</div>
                                                </div>
                                                <div>
                                                    <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Status</div>
                                                    <div className="text-xl font-mono text-white font-bold flex items-center gap-2">
                                                        <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                                                        ACTIVE
                                                    </div>
                                                </div>
                                            </div>
                                        </motion.div>
                                    ))}
                                </div>
                            </div>
                        )}

                    </div>

                    {/* Bottom Status Bar */}
                    <div className="bg-black/80 border-t border-white/10 py-2 px-6 flex justify-between items-center text-[10px] font-mono text-zinc-500 uppercase shrink-0">
                        <div className="flex items-center gap-4">
                            <span>ID: {metadata?.scanId || 'UNK-001'}</span>
                            <span className="text-accent/50">///</span>
                            <span>SECURE CONNECTION ESTABLISHED</span>
                        </div>
                        <div className="flex gap-1">
                            {[1, 2, 3, 4, 5].map(i => <div key={i} className={`w-1 h-2 bg-accent/${i * 20}`} />)}
                        </div>
                    </div>

                </div>
            </motion.div>
        </div>
    );
}

function StatPill({ label, value, icon, color = 'default' }: { label: string, value: string | number, icon: any, color?: string }) {
    return (
        <div className="flex items-center gap-3 px-5 py-3 rounded-lg bg-white/5 border border-white/5">
            <span className={cn(
                "text-lg",
                color === 'green' ? "text-green-400" : color === 'red' ? "text-red-400" : "text-white"
            )}>{icon}</span>
            <div className="flex flex-col items-start">
                <span className="text-[10px] font-bold text-zinc-500 tracking-wider uppercase">{label}</span>
                <span className={cn(
                    "text-sm font-bold font-mono",
                    color === 'green' ? "text-green-400" : color === 'red' ? "text-red-400" : "text-white"
                )}>{value}</span>
            </div>
        </div>
    )
}
