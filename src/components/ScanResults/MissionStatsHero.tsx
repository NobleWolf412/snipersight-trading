// Visual Overhaul: Mission Stats Hero (Centered & Beautiful)
import { useRef } from 'react';
import { motion } from 'framer-motion';
import { ScanResult } from '@/utils/mockData';
import { Target, Lightning, Crosshair, Globe, CheckCircle, WifiHigh, ChartLineUp, TrendUp, TrendDown } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { TechPanel } from '@/components/ui/TacticalComponents';
import { TacticalScanScene } from '@/components/ScanResults/TacticalScanScene';
import { TacticalGauge } from '@/components/charts/TacticalGauge';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';

interface MissionStatsHeroProps {
    results: ScanResult[];
    metadata?: any;
}


export function MissionStatsHero({ results, metadata }: MissionStatsHeroProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const totalTargets = results.length;
    const longCount = results.filter(r => r.trendBias === 'BULLISH').length;
    const shortCount = results.filter(r => r.trendBias === 'BEARISH').length;

    // Sort by confidence desceding and take top 3
    const topTargets = [...results].sort((a, b) => b.confidenceScore - a.confidenceScore).slice(0, 3);

    // --- CINEMATIC BOOT SEQUENCE ---
    useGSAP(() => {
        const tl = gsap.timeline({ defaults: { ease: "power3.out" } });

        // 1. Initial State: Hidden
        gsap.set(".scan-scene", { opacity: 0 });
        gsap.set(".tech-border", { scaleX: 0 });

        // 2. Scene Flicker On
        tl.to(".scan-scene", { opacity: 0.4, duration: 0.1, yoyo: true, repeat: 3 })
            .to(".scan-scene", { opacity: 0.4, duration: 1 });

        // 3. Borders Expand
        tl.to(".tech-border", { scaleX: 1, duration: 0.8, stagger: 0.1 }, "-=0.5");

        // 4. Header Elements Scramble/Fade In
        tl.to(".header-item", {
            autoAlpha: 1,
            y: 0,
            duration: 0.5,
            stagger: 0.1,
            onStart: function () {
                // Simple text scramble effect could go here if we had a split text plugin
            }
        }, "-=0.3");

        // 5. Priority Cards Slam In
        tl.to(".card-item", {
            autoAlpha: 1,
            y: 0,
            duration: 0.4,
            stagger: 0.1,
            ease: "back.out(1.7)"
        }, "-=0.2");

    }, { scope: containerRef });

    return (
        <div ref={containerRef} className="h-full w-full flex items-center justify-center p-6 lg:p-12 relative overflow-hidden">

            {/* Ambient Background Glows */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-accent/5 rounded-full blur-[100px]" />
                <div className="absolute top-0 right-0 w-[400px] h-[400px] bg-accent/5 rounded-full blur-[100px]" />
                <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-accent/5 rounded-full blur-[100px]" />
            </div>

            {/* MAIN CENTRAL CONTAINER */}
            <div className="relative z-10 w-full h-full flex flex-col">

                {/* ADVANCED TECH FRAME */}
                <div className="flex-1 h-full flex flex-col bg-black/80 backdrop-blur-xl rounded-2xl overflow-hidden relative group border border-white/10 shadow-2xl">

                    {/* 3D TACTICAL SCENE (BACKGROUND) */}
                    <div className="scan-scene absolute inset-0 z-0 opacity-0 mix-blend-screen pointer-events-none overflow-hidden">
                        <TacticalScanScene blips={results.map(r => ({
                            symbol: r.pair,
                            score: r.confidenceScore,
                            angle: Math.random() * Math.PI * 2,
                            distance: 0.5 + Math.random() * 0.5
                        }))} />
                    </div>

                    {/* Corner Borders SVGs (Larger & Thicker) */}
                    <div className="tech-border absolute top-0 left-0 w-24 h-24 border-l-4 border-t-4 border-accent/40 rounded-tl-3xl z-20 origin-left" />
                    <div className="tech-border absolute top-0 right-0 w-24 h-24 border-r-4 border-t-4 border-accent/40 rounded-tr-3xl z-20 origin-right" />
                    <div className="tech-border absolute bottom-0 left-0 w-24 h-24 border-l-4 border-b-4 border-accent/40 rounded-bl-3xl z-20 origin-left" />
                    <div className="tech-border absolute bottom-0 right-0 w-24 h-24 border-r-4 border-b-4 border-accent/40 rounded-br-3xl z-20 origin-right" />

                    {/* Decorative Notches */}
                    <div className="absolute top-0 left-1/2 -translate-x-1/2 w-64 h-2 bg-accent/20 clips-path-notch-bottom" />
                    <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-64 h-2 bg-accent/20 clips-path-notch-top" />

                    {/* INNER CONTENT - FLEX COLUMN FOR FULL HEIGHT */}
                    <div className="flex-1 p-8 md:p-12 lg:p-16 flex flex-col relative z-30 justify-between h-full min-h-0">

                        {/* HEADER SECTION (Spaced Out) */}
                        <div className="flex flex-col xl:flex-row items-start xl:items-center justify-between gap-8 shrink-0">
                            <div className="header-item flex items-center gap-8 opacity-0 translate-y-4">
                                <div className="relative w-24 h-24 flex items-center justify-center shrink-0">
                                    <div className="absolute inset-0 bg-accent/10 rounded-full animate-ping opacity-20" />
                                    <div className="absolute inset-0 border-2 border-accent/40 rounded-full animate-spin-slow-reverse border-dashed" />
                                    <CheckCircle weight="fill" className="text-accent w-12 h-12 drop-shadow-[0_0_20px_rgba(0,255,170,0.6)]" />
                                </div>
                                <div className="text-left">
                                    <div className="flex items-center gap-3 mb-2">
                                        <div className="w-2.5 h-2.5 bg-accent animate-pulse shadow-[0_0_10px_#00ff88]" />
                                        <div className="text-sm font-bold tracking-[0.4em] text-accent uppercase opacity-90 drop-shadow-md">MISSION STATUS</div>
                                    </div>
                                    <h1 className="text-5xl md:text-7xl font-bold font-mono text-white tracking-tighter bg-gradient-to-r from-white via-white to-white/50 bg-clip-text text-transparent drop-shadow-sm">
                                        SCAN COMPLETE
                                    </h1>
                                </div>
                            </div>

                            {/* STATS ROW (Floating Card) */}
                            <div className="header-item flex items-center gap-8 p-6 bg-black/40 backdrop-blur-xl rounded-2xl border border-white/10 opacity-0 translate-y-4 shadow-xl">
                                <StatPill label="TARGETS IDENTIFIED" value={totalTargets} icon={<Target />} size="lg" />

                                <div className="hidden md:block w-px h-16 bg-gradient-to-b from-transparent via-white/20 to-transparent" />

                                {/* Market Bias Gauge */}
                                <div className="w-48 h-28 relative hidden md:block">
                                    <div className="absolute inset-0 bg-white/5 rounded-xl border border-white/5 overflow-hidden">
                                        <div className="w-full h-full p-2">
                                            <TacticalGauge
                                                value={Math.round((longCount / (totalTargets || 1)) * 100)}
                                                label={longCount >= shortCount ? "BULLISH" : "BEARISH"}
                                                color={longCount >= shortCount ? "#00ff88" : "#ef4444"}
                                            />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* SEPARATOR (Glowing Line) */}
                        <div className="tech-border relative h-px w-full bg-gradient-to-r from-transparent via-accent/30 to-transparent my-10 shrink-0 opacity-50">
                            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-32 h-1 bg-accent shadow-[0_0_15px_#00ff88]" />
                        </div>

                        {/* PRIORITY TARGETS GRID (TOP 3) - MAXIMUM EXPANSION */}
                        {topTargets.length > 0 && (
                            <div className="flex-1 flex flex-col min-h-0 pt-4">
                                <div className="header-item text-sm text-accent font-bold tracking-[0.3em] uppercase mb-8 opacity-80 flex items-center gap-4 shrink-0 opacity-0 translate-y-4">
                                    <div className="w-12 h-px bg-accent/50" />
                                    <Target size={20} weight="fill" />
                                    PRIORITY INTERCEPTS /// TOP 3
                                    <div className="flex-1 h-px bg-gradient-to-r from-accent/50 to-transparent" />
                                </div>

                                <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-8 min-h-0 h-full">
                                    {topTargets.map((target, i) => (
                                        <div
                                            key={target.id}
                                            className="card-item group relative bg-gradient-to-b from-white/5 to-transparent hover:bg-white/10 border border-white/10 hover:border-accent/60 rounded-xl p-8 xl:p-10 transition-all duration-500 cursor-pointer flex flex-col overflow-hidden hover:-translate-y-2 hover:shadow-[0_0_50px_-10px_rgba(0,255,136,0.2)] opacity-0 translate-y-4 h-full justify-between"
                                        >
                                            {/* Hover Glow Gradient */}
                                            <div className="absolute inset-0 bg-gradient-to-tr from-accent/0 via-accent/0 to-accent/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

                                            {/* Tech Corners (Mini) */}
                                            <div className="absolute top-0 left-0 w-4 h-4 border-l-2 border-t-2 border-white/20 group-hover:border-accent transition-colors duration-300" />
                                            <div className="absolute top-0 right-0 w-4 h-4 border-r-2 border-t-2 border-white/20 group-hover:border-accent transition-colors duration-300" />
                                            <div className="absolute bottom-0 left-0 w-4 h-4 border-l-2 border-b-2 border-white/20 group-hover:border-accent transition-colors duration-300" />
                                            <div className="absolute bottom-0 right-0 w-4 h-4 border-r-2 border-b-2 border-white/20 group-hover:border-accent transition-colors duration-300" />

                                            {/* Card Header & Score */}
                                            <div className="flex justify-between items-start relative z-10 w-full mb-auto">
                                                <div className="flex flex-col">
                                                    <div className="text-6xl xl:text-8xl font-black text-accent tabular-nums tracking-tighter drop-shadow-[0_0_15px_rgba(0,255,170,0.3)]">{target.confidenceScore}%</div>
                                                    <div className="text-xs text-muted-foreground tracking-[0.3em] uppercase font-bold pl-1">Probability</div>
                                                </div>
                                                <div className="w-16 h-16 rounded-xl bg-accent/10 border border-accent/30 flex items-center justify-center text-accent shadow-[0_0_15px_rgba(0,255,170,0.15)] group-hover:scale-110 transition-transform duration-300">
                                                    <Target size={36} weight="duotone" />
                                                </div>
                                            </div>

                                            {/* Card Main: Symbol */}
                                            <div className="relative z-10 my-10 pl-4 border-l-4 border-white/10 group-hover:border-accent transition-all duration-300 group-hover:pl-6">
                                                <div className="text-5xl xl:text-6xl font-black text-white font-mono mb-4 tracking-tighter shadow-black drop-shadow-lg">{target.pair}</div>

                                                <div className="flex flex-wrap gap-3">
                                                    <div className={cn(
                                                        "inline-flex items-center gap-2 px-4 py-2 rounded text-xs font-bold border uppercase tracking-widest bg-black/50 backdrop-blur-sm",
                                                        target.trendBias === 'BULLISH' ? "border-green-500/50 text-green-400 shadow-[0_0_10px_rgba(74,222,128,0.2)]" : "border-red-500/50 text-red-400 shadow-[0_0_10px_rgba(248,113,113,0.2)]"
                                                    )}>
                                                        {target.trendBias === 'BULLISH' ? <TrendUp weight="bold" size={16} /> : <TrendDown weight="bold" size={16} />}
                                                        {target.trendBias}
                                                    </div>
                                                </div>
                                            </div>

                                            {/* Card Footer: Metrics */}
                                            <div className="relative z-10 pt-6 border-t border-dashed border-white/10 grid grid-cols-2 gap-6 bg-black/20 -mx-8 -mb-10 p-8 mt-auto backdrop-blur-sm group-hover:bg-accent/5 transition-colors">
                                                <div>
                                                    <div className="text-[10px] text-zinc-500 uppercase tracking-widest mb-1 font-bold">Risk:Reward</div>
                                                    <div className="text-2xl font-mono text-white font-bold tracking-tight">{target.riskReward}</div>
                                                </div>
                                                <div>
                                                    <div className="text-[10px] text-zinc-500 uppercase tracking-widest mb-1 font-bold">Status</div>
                                                    <div className="text-xl font-mono text-white font-bold flex items-center gap-3">
                                                        <div className="w-2.5 h-2.5 rounded-full bg-accent animate-pulse shadow-[0_0_10px_#00ff88]" />
                                                        ACTIVE
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                    </div>

                    {/* Bottom Status Bar */}
                    <div className="bg-black/90 border-t border-white/10 py-3 px-8 flex justify-between items-center text-[10px] font-mono text-zinc-500 uppercase shrink-0 z-40 relative">
                        <div className="flex items-center gap-6">
                            <span>ID: {metadata?.scanId || 'UNK-001'}</span>
                            <span className="text-accent/50">///</span>
                            <span className="flex items-center gap-2">
                                <WifiHigh size={14} />
                                SECURE CONNECTION ESTABLISHED
                            </span>
                        </div>
                        <div className="flex gap-1.5 opacity-50">
                            {[1, 2, 3, 4, 5, 6, 7, 8].map(i => <div key={i} className={`w-1 h-3 bg-accent/${Math.min(i * 15 + 10, 100)} rounded-full`} />)}
                        </div>
                    </div>

                </div>
            </div>
        </div>
    );
}

function StatPill({ label, value, icon, size = 'md', color = 'default' }: { label: string, value: string | number, icon: any, size?: 'md' | 'lg', color?: string }) {
    return (
        <div className={cn(
            "flex items-center gap-4 rounded-xl bg-white/5 border border-white/5",
            size === 'lg' ? "px-6 py-4" : "px-5 py-3"
        )}>
            <span className={cn(
                size === 'lg' ? "text-2xl" : "text-lg",
                color === 'green' ? "text-green-400" : color === 'red' ? "text-red-400" : "text-white"
            )}>{icon}</span>
            <div className="flex flex-col items-start">
                <span className="text-[10px] font-bold text-zinc-500 tracking-wider uppercase">{label}</span>
                <span className={cn(
                    "font-bold font-mono tracking-tighter",
                    size === 'lg' ? "text-2xl md:text-3xl" : "text-sm",
                    color === 'green' ? "text-green-400" : color === 'red' ? "text-red-400" : "text-white"
                )}>{value}</span>
            </div>
        </div>
    )
}

