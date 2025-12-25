
import { motion, AnimatePresence } from 'framer-motion';
import { useState } from 'react';
import { ScanResult } from '@/utils/mockData';
import { cn } from '@/lib/utils';
import { CheckCircle, Warning, XCircle } from '@phosphor-icons/react';
import { TechPanel } from '@/components/ui/TacticalComponents';

interface ConfluenceVisualizerProps {
    signal: ScanResult;
}

export function ConfluenceVisualizer({ signal }: ConfluenceVisualizerProps) {
    const [hoveredFactor, setHoveredFactor] = useState<string | null>(null);

    // Mock Factors based on signal score (real app would pass this in)
    const factors = [
        { id: 'smc', label: 'SMART MONEY', status: 'pass', score: 100, desc: 'Price actively testing a validated Order Block.' },
        { id: 'trend', label: 'HTF TREND', status: 'pass', score: 90, desc: '4H and Daily Trend alignment confirmed.' },
        { id: 'vol', label: 'VOLUME', status: 'pass', score: 85, desc: 'expansion volume > 1.5x average.' },
        { id: 'mom', label: 'MOMENTUM', status: 'pass', score: 95, desc: 'RSI divergence detected on entry timeframe.' },
        { id: 'liq', label: 'LIQUIDITY', status: 'warn', score: 60, desc: 'Internal liquidity sweep pending.' },
        { id: 'fvg', label: 'FVG FILL', status: 'pass', score: 100, desc: 'Entry overlaps with H1 Fair Value Gap.' },
    ];

    return (
        <div className="h-full w-full grid grid-cols-1 lg:grid-cols-3 gap-6 p-6 lg:p-10 animate-in fade-in relative overflow-hidden">

            {/* Background Texture */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-[#00ff88]/5 via-[#0a0f0a] to-[#0a0f0a] pointer-events-none" />

            {/* LEFT: VISUALIZER */}
            <div className="lg:col-span-2 relative flex items-center justify-center min-h-[400px]">
                {/* Central Core */}
                <motion.div
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ duration: 1 }}
                    className="relative z-10 w-40 h-40 rounded-full flex items-center justify-center bg-black/80 backdrop-blur-xl border border-[#00ff88]/30 shadow-[0_0_50px_rgba(0,255,136,0.15)] hover:shadow-[0_0_80px_rgba(0,255,136,0.3)] transition-shadow duration-500 cursor-default"
                >
                    <div className="absolute inset-0 rounded-full border border-dashed border-[#00ff88]/30 animate-spin-slow" />
                    <div className="absolute inset-4 rounded-full border border-white/10 animate-spin-reverse-slower" />

                    <div className="flex flex-col items-center">
                        <span className="text-4xl font-bold font-mono text-white tracking-tighter tabular-nums">
                            {signal.confidenceScore}%
                        </span>
                        <span className="text-[10px] font-mono text-[#00ff88] uppercase tracking-widest mt-1">
                            PROBABILITY
                        </span>
                    </div>
                </motion.div>

                {/* Orbiting Factors */}
                <div className="absolute inset-0 flex items-center justify-center">
                    {factors.map((factor, i) => {
                        const count = factors.length;
                        const angle = (i / count) * 360;
                        const radius = 160; // Distance from center

                        return (
                            <motion.div
                                key={factor.id}
                                className="absolute"
                                initial={{ rotate: angle, opacity: 0 }}
                                animate={{ rotate: angle + 360, opacity: 1 }}
                                transition={{
                                    rotate: { duration: 60, repeat: Infinity, ease: "linear" },
                                    opacity: { duration: 0.5, delay: i * 0.1 }
                                }}
                                style={{
                                    width: radius * 2,
                                    height: radius * 2,
                                }}
                            >
                                <motion.div
                                    className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2"
                                    whileHover={{ scale: 1.2 }}
                                >
                                    {/* The Node Itself */}
                                    <div
                                        className={cn(
                                            "relative group cursor-pointer transition-all duration-300",
                                            hoveredFactor === factor.id ? "z-50" : "z-20"
                                        )}
                                        onMouseEnter={() => setHoveredFactor(factor.id)}
                                        onMouseLeave={() => setHoveredFactor(null)}
                                    >
                                        <div className={cn(
                                            "w-12 h-12 rounded-full border border-white/20 flex items-center justify-center backdrop-blur-md transition-all duration-300",
                                            factor.status === 'pass' ? "bg-[#00ff88]/10 border-[#00ff88]/50 shadow-[0_0_15px_rgba(0,255,136,0.3)]" : "bg-amber-500/10 border-amber-500/50 shadow-[0_0_15px_rgba(245,158,11,0.3)]",
                                            hoveredFactor === factor.id && "scale-110 bg-black border-white"
                                        )}>
                                            {factor.status === 'pass'
                                                ? <CheckCircle size={20} className="text-[#00ff88]" weight="fill" />
                                                : <Warning size={20} className="text-amber-500" weight="fill" />
                                            }
                                        </div>

                                        {/* Label (Always Visible) */}
                                        <div className="absolute top-14 left-1/2 -translate-x-1/2 w-32 text-center pointer-events-none">
                                            <span className="text-[10px] font-bold font-mono text-white/60 bg-black/80 px-2 py-0.5 rounded border border-white/5 uppercase">
                                                {factor.label}
                                            </span>
                                        </div>
                                    </div>
                                </motion.div>
                            </motion.div>
                        );
                    })}
                </div>
            </div>

            {/* RIGHT: FACTOR INTEL CARD (Dynamic) */}
            <div className="h-full flex flex-col justify-center">
                <TechPanel className="h-[400px] flex flex-col" title="FACTOR INTELLIGENCE">
                    <AnimatePresence mode="wait">
                        {hoveredFactor ? (
                            <motion.div
                                key="detail"
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -20 }}
                                className="flex-1 flex flex-col gap-4 pt-4"
                            >
                                {(() => {
                                    const f = factors.find(f => f.id === hoveredFactor)!;
                                    return (
                                        <>
                                            <div className="flex items-center gap-3 pb-4 border-b border-white/10">
                                                <div className={cn(
                                                    "w-10 h-10 rounded flex items-center justify-center",
                                                    f.status === 'pass' ? "bg-green-500/20 text-green-400" : "bg-amber-500/20 text-amber-400"
                                                )}>
                                                    {f.status === 'pass' ? <CheckCircle size={24} weight="fill" /> : <Warning size={24} weight="fill" />}
                                                </div>
                                                <div>
                                                    <h3 className="text-xl font-bold text-white font-mono">{f.label}</h3>
                                                    <span className={cn("text-xs uppercase tracking-widest", f.status === 'pass' ? "text-[#00ff88]" : "text-amber-500")}>
                                                        STATUS: {f.status.toUpperCase()}
                                                    </span>
                                                </div>
                                            </div>

                                            <div className="flex-1">
                                                <p className="text-muted-foreground font-mono text-sm leading-relaxed">
                                                    {f.desc}
                                                </p>

                                                <div className="mt-6 p-4 rounded bg-white/5 border border-white/5">
                                                    <div className="flex justify-between text-xs mb-2">
                                                        <span>FACTOR WEIGHT</span>
                                                        <span>{f.score}/100</span>
                                                    </div>
                                                    <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                                                        <div className="h-full bg-[#00ff88]" style={{ width: `${f.score}%` }} />
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="text-[10px] text-muted-foreground font-mono border-t border-white/10 pt-4">
                                                // SOURCE: SMC_ENGINE_V2.1<br />
                                                // VERIFIED: {new Date().toLocaleTimeString()}
                                            </div>
                                        </>
                                    );
                                })()}
                            </motion.div>
                        ) : (
                            <motion.div
                                key="empty"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="flex-1 flex flex-col items-center justify-center text-center text-muted-foreground opacity-50"
                            >
                                <div className="w-16 h-16 rounded-full border border-dashed border-white/20 flex items-center justify-center mb-4">
                                    <div className="w-2 h-2 bg-white/50 rounded-full animate-ping" />
                                </div>
                                <p className="font-mono text-xs tracking-widest">
                                    HOVER OVER NODES<br />FOR INTEL BREAKDOWN
                                </p>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </TechPanel>
            </div>
        </div>
    );
}
