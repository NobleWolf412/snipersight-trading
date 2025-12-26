// Visual Overhaul: Mission Stats Hero (Centered & Beautiful)
import { useRef } from 'react';
import { motion } from 'framer-motion';
import { ScanResult } from '@/utils/mockData';
import { Target, Lightning, Crosshair, Globe, CheckCircle, WifiHigh, ChartLineUp, TrendUp, TrendDown, Warning, ShieldWarning, XCircle } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { TechPanel } from '@/components/ui/TacticalComponents';
import { TacticalScanScene } from '@/components/ScanResults/TacticalScanScene';
import { RejectionDossier, RejectionSummary } from '@/components/ScanResults/RejectionDossier';
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

        // 5. Priority Cards Slam In (only if they exist)
        if (document.querySelectorAll('.card-item').length > 0) {
            tl.to(".card-item", {
                autoAlpha: 1,
                y: 0,
                duration: 0.4,
                stagger: 0.1,
                ease: "back.out(1.7)"
            }, "-=0.2");
        }

    }, { scope: containerRef });

    return (
        <div ref={containerRef} className="h-full w-full flex flex-col p-6 lg:p-12 relative overflow-y-auto">

            {/* Ambient Background Glows */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-accent/5 rounded-full blur-[100px]" />
                <div className="absolute top-0 right-0 w-[400px] h-[400px] bg-accent/5 rounded-full blur-[100px]" />
                <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-accent/5 rounded-full blur-[100px]" />
            </div>

            {/* MAIN CENTRAL CONTAINER */}
            <div className="relative z-10 w-full flex-1 flex flex-col gap-6">

                {/* ═══════════════════════════════════════════════════════════════ */}
                {/* SCAN COMPLETE BADGE - Outside main container, centered on top */}
                {/* ═══════════════════════════════════════════════════════════════ */}
                <div className="header-item flex items-center justify-center opacity-0 translate-y-4">
                    <div className="relative">
                        {/* Outer Glow */}
                        <div className="absolute inset-0 bg-accent/20 rounded-2xl blur-xl animate-pulse" />

                        {/* Badge Container */}
                        <div className="relative flex items-center gap-6 px-10 py-6 bg-gradient-to-r from-accent/20 via-accent/10 to-accent/20 border-2 border-accent/50 rounded-2xl backdrop-blur-xl shadow-[0_0_40px_rgba(0,255,136,0.3)]">

                            {/* Animated Check Icon */}
                            <div className="relative w-16 h-16 flex items-center justify-center shrink-0">
                                <div className="absolute inset-0 bg-accent/20 rounded-full animate-ping opacity-30" />
                                <div className="absolute inset-0 border-2 border-accent/50 rounded-full animate-spin-slow-reverse border-dashed" />
                                <CheckCircle weight="fill" className="text-accent w-10 h-10 drop-shadow-[0_0_25px_rgba(0,255,170,0.8)]" />
                            </div>

                            {/* Text */}
                            <div className="text-left">
                                <div className="flex items-center gap-2 mb-1">
                                    <div className="w-2 h-2 bg-accent animate-pulse shadow-[0_0_10px_#00ff88] rounded-full" />
                                    <span className="text-xs font-bold tracking-[0.4em] text-accent uppercase">MISSION STATUS</span>
                                </div>
                                <h1 className="text-4xl md:text-5xl lg:text-6xl font-black font-mono text-white tracking-tight drop-shadow-[0_0_20px_rgba(255,255,255,0.3)]">
                                    SCAN COMPLETE
                                </h1>
                            </div>

                            {/* Decorative Corner Accents */}
                            <div className="absolute top-0 left-0 w-6 h-6 border-l-2 border-t-2 border-accent rounded-tl-xl" />
                            <div className="absolute top-0 right-0 w-6 h-6 border-r-2 border-t-2 border-accent rounded-tr-xl" />
                            <div className="absolute bottom-0 left-0 w-6 h-6 border-l-2 border-b-2 border-accent rounded-bl-xl" />
                            <div className="absolute bottom-0 right-0 w-6 h-6 border-r-2 border-b-2 border-accent rounded-br-xl" />
                        </div>
                    </div>
                </div>

                {/* ═══════════════════════════════════════════════════════════════ */}
                {/* MAIN CONTENT FRAME */}
                {/* ═══════════════════════════════════════════════════════════════ */}
                <div className="flex flex-col bg-black/80 backdrop-blur-xl rounded-2xl overflow-visible relative group border border-white/10 shadow-2xl min-h-fit">

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
                    <div className="p-8 md:p-10 lg:p-12 flex flex-col relative z-30 gap-6">

                        {/* Stats Row - Now at top of this container */}
                        <div className="header-item flex flex-wrap items-center justify-center gap-4 opacity-0 translate-y-4">
                            <StatPill label="TARGETS" value={totalTargets} icon={<Target />} size="lg" />
                            <div className="hidden md:block w-px h-12 bg-gradient-to-b from-transparent via-white/20 to-transparent" />
                            <StatPill label="LONGS" value={longCount} icon={<TrendUp />} size="lg" color="green" />
                            <div className="hidden md:block w-px h-12 bg-gradient-to-b from-transparent via-white/20 to-transparent" />
                            <StatPill label="SHORTS" value={shortCount} icon={<TrendDown />} size="lg" color="red" />
                        </div>

                        {/* SEPARATOR (Glowing Line) */}
                        <div className="tech-border relative h-px w-full bg-gradient-to-r from-transparent via-accent/30 to-transparent my-6 shrink-0 opacity-50">
                            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-32 h-1 bg-accent shadow-[0_0_15px_#00ff88]" />
                        </div>

                        {/* PRIORITY TARGETS GRID (TOP 3) - MAXIMUM EXPANSION */}
                        {topTargets.length > 0 ? (
                            <div className="flex-1 flex flex-col min-h-0 pt-4">
                                <div className="header-item text-sm text-accent font-bold tracking-[0.3em] uppercase mb-8 opacity-80 flex items-center gap-4 shrink-0 opacity-0 translate-y-4">
                                    <div className="w-12 h-px bg-accent/50" />
                                    <Target size={20} weight="fill" />
                                    PRIORITY INTERCEPTS /// TOP 3
                                    <div className="flex-1 h-px bg-gradient-to-r from-accent/50 to-transparent" />
                                </div>

                                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                                    {topTargets.map((target, i) => (
                                        <div
                                            key={target.id}
                                            className="card-item group relative rounded-xl p-[3px] cursor-pointer overflow-hidden hover:-translate-y-2 transition-all duration-500 opacity-0 translate-y-4"
                                        >
                                            {/* Gradient Border Background - fills the 3px padding */}
                                            <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-accent/70 via-white/40 to-accent/70 opacity-60 group-hover:opacity-100 transition-opacity duration-500" />

                                            {/* Animated Sweep Glow */}
                                            <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-transparent via-accent to-transparent opacity-0 group-hover:opacity-80 blur-sm animate-[sweep_2s_linear_infinite] transition-opacity duration-300" />

                                            {/* Inner Card Content - sits inside the padding, creating the border effect */}
                                            <div className="relative bg-[#080808] rounded-[9px] p-8 lg:p-10 xl:p-12 h-full flex flex-col overflow-hidden group-hover:shadow-[0_0_60px_-10px_rgba(0,255,136,0.4)]">

                                                {/* Hover Glow Gradient */}
                                                <div className="absolute inset-0 bg-gradient-to-tr from-accent/0 via-accent/5 to-accent/10 opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-xl" />

                                                {/* Animated Corner Accents */}
                                                <div className="absolute top-0 left-0 w-8 h-8 border-l-2 border-t-2 border-accent/30 group-hover:border-accent group-hover:w-12 group-hover:h-12 transition-all duration-300 rounded-tl-lg" />
                                                <div className="absolute top-0 right-0 w-8 h-8 border-r-2 border-t-2 border-accent/30 group-hover:border-accent group-hover:w-12 group-hover:h-12 transition-all duration-300 rounded-tr-lg" />
                                                <div className="absolute bottom-0 left-0 w-8 h-8 border-l-2 border-b-2 border-accent/30 group-hover:border-accent group-hover:w-12 group-hover:h-12 transition-all duration-300 rounded-bl-lg" />
                                                <div className="absolute bottom-0 right-0 w-8 h-8 border-r-2 border-b-2 border-accent/30 group-hover:border-accent group-hover:w-12 group-hover:h-12 transition-all duration-300 rounded-br-lg" />

                                                {/* Top edge glow line */}
                                                <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

                                                {/* Card Header & Score */}
                                                <div className="flex justify-between items-start relative z-10 w-full mb-auto">
                                                    <div className="flex flex-col">
                                                        <div className="text-6xl xl:text-7xl font-black text-accent tabular-nums tracking-tighter drop-shadow-[0_0_20px_rgba(0,255,170,0.4)] group-hover:drop-shadow-[0_0_30px_rgba(0,255,170,0.6)] transition-all">
                                                            {Math.round(target.confidenceScore)}%
                                                        </div>
                                                        <div className="text-xs text-muted-foreground tracking-[0.3em] uppercase font-bold pl-1">Probability</div>
                                                    </div>
                                                    <div className="w-16 h-16 rounded-xl bg-accent/10 border border-accent/40 flex items-center justify-center text-accent shadow-[0_0_20px_rgba(0,255,170,0.2)] group-hover:scale-110 group-hover:shadow-[0_0_30px_rgba(0,255,170,0.4)] transition-all duration-300">
                                                        <Target size={36} weight="duotone" />
                                                    </div>
                                                </div>

                                                {/* Card Main: Symbol */}
                                                <div className="relative z-10 my-8 pl-4 border-l-4 border-accent/20 group-hover:border-accent group-hover:pl-6 transition-all duration-300">
                                                    <div className="text-4xl xl:text-5xl font-black text-white font-mono mb-4 tracking-tight">{target.pair}</div>

                                                    <div className="flex flex-wrap gap-3">
                                                        <div className={cn(
                                                            "inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold border uppercase tracking-widest backdrop-blur-sm",
                                                            target.trendBias === 'BULLISH'
                                                                ? "border-green-500/50 text-green-400 bg-green-500/10 shadow-[0_0_15px_rgba(74,222,128,0.2)]"
                                                                : "border-red-500/50 text-red-400 bg-red-500/10 shadow-[0_0_15px_rgba(248,113,113,0.2)]"
                                                        )}>
                                                            {target.trendBias === 'BULLISH' ? <TrendUp weight="bold" size={16} /> : <TrendDown weight="bold" size={16} />}
                                                            {target.trendBias === 'BULLISH' ? 'LONG' : 'SHORT'}
                                                        </div>
                                                    </div>
                                                </div>

                                                {/* Card Footer: Metrics */}
                                                <div className="relative z-10 pt-6 border-t border-dashed border-white/10 grid grid-cols-2 gap-6 bg-black/50 -mx-8 lg:-mx-10 xl:-mx-12 -mb-8 lg:-mb-10 xl:-mb-12 p-8 mt-auto backdrop-blur-sm group-hover:bg-accent/5 transition-colors rounded-b-lg">
                                                    <div>
                                                        <div className="text-[10px] text-zinc-500 uppercase tracking-widest mb-1 font-bold">Risk:Reward</div>
                                                        <div className="text-2xl font-mono text-white font-bold tracking-tight">
                                                            {typeof target.riskReward === 'number' ? target.riskReward.toFixed(1) : target.riskReward}R
                                                        </div>
                                                    </div>
                                                    <div>
                                                        <div className="text-[10px] text-zinc-500 uppercase tracking-widest mb-1 font-bold">Status</div>
                                                        <div className="text-lg font-mono text-white font-bold flex items-center gap-3">
                                                            <div className="w-2.5 h-2.5 rounded-full bg-accent animate-pulse shadow-[0_0_12px_#00ff88]" />
                                                            ACTIVE
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            /* NO SIGNALS - REJECTION DOSSIER (TABBED ANALYSIS) */
                            <div className="flex-1 flex flex-col min-h-0">
                                <RejectionDossier
                                    rejections={metadata?.rejections || {}}
                                    scanned={metadata?.scanned || 0}
                                    rejected={metadata?.rejected || 0}
                                    mode={metadata?.mode || 'unknown'}
                                />
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

