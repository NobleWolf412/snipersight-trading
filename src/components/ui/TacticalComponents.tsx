import React from 'react';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';

// ==========================================
// TECH PANEL - The foundational building block
// ==========================================
interface TechPanelProps extends React.HTMLAttributes<HTMLDivElement> {
    title?: string;
    rightElement?: React.ReactNode;
    variant?: 'default' | 'scanner' | 'alert' | 'success';
    cornerAccents?: boolean;
    scanline?: boolean;
}

export function TechPanel({
    children,
    className,
    title,
    rightElement,
    variant = 'default',
    cornerAccents = true,
    scanline = false,
    ...props
}: TechPanelProps) {
    const variants = {
        default: "border-white/10 bg-black/40",
        scanner: "border-[#00ff88]/30 bg-[#00ff88]/5 shadow-[0_0_15px_rgba(0,255,136,0.05)]",
        alert: "border-red-500/30 bg-red-500/5 shadow-[0_0_15px_rgba(239,68,68,0.05)]",
        success: "border-blue-500/30 bg-blue-500/5 shadow-[0_0_15px_rgba(59,130,246,0.05)]",
    };

    return (
        <div
            className={cn(
                "relative rounded-xl border backdrop-blur-md overflow-hidden transition-all duration-300",
                variants[variant],
                className
            )}
            {...props}
        >
            {/* Scanline Effect */}
            {scanline && (
                <div className="absolute inset-0 pointer-events-none opacity-[0.03] z-0"
                    style={{ backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, #fff 2px, #fff 4px)' }}
                />
            )}

            {/* Corner Accents */}
            {cornerAccents && (
                <>
                    <div className="absolute top-0 left-0 w-2 h-2 border-t-2 border-l-2 border-white/20 rounded-tl-sm" />
                    <div className="absolute top-0 right-0 w-2 h-2 border-t-2 border-r-2 border-white/20 rounded-tr-sm" />
                    <div className="absolute bottom-0 left-0 w-2 h-2 border-b-2 border-l-2 border-white/20 rounded-bl-sm" />
                    <div className="absolute bottom-0 right-0 w-2 h-2 border-b-2 border-r-2 border-white/20 rounded-br-sm" />
                </>
            )}

            {/* Header */}
            {title && (
                <div className="relative z-10 flex items-center justify-between px-4 py-3 border-b border-white/5 bg-white/5">
                    <div className="flex items-center gap-2">
                        <div className={cn("w-1 h-3 rounded-full",
                            variant === 'scanner' ? 'bg-[#00ff88]' :
                                variant === 'alert' ? 'bg-red-500' :
                                    'bg-white/50'
                        )} />
                        <h3 className="font-mono font-bold text-xs uppercase tracking-[0.2em] text-white/80">
                            {title}
                        </h3>
                    </div>
                    {rightElement}
                </div>
            )}

            {/* Content */}
            <div className="relative z-10 p-4">
                {children}
            </div>
        </div>
    );
}

// ==========================================
// SIGNAL STRENGTH - 5-bar visualizer
// ==========================================
export function SignalStrength({ score, max = 100 }: { score: number; max?: number }) {
    const bars = 5;
    const filledBars = Math.ceil((score / max) * bars);

    // Determine color based on score
    const getColor = () => {
        if (score >= 80) return 'bg-[#00ff88] shadow-[0_0_8px_#00ff88]';
        if (score >= 60) return 'bg-amber-400 shadow-[0_0_8px_#fbbf24]';
        return 'bg-red-500 shadow-[0_0_8px_#ef4444]';
    };

    return (
        <div className="flex items-end gap-1 h-4">
            {[...Array(bars)].map((_, i) => (
                <div
                    key={i}
                    className={cn(
                        "w-1 rounded-sm transition-all duration-300",
                        i < filledBars ? getColor() : "bg-white/10"
                    )}
                    style={{ height: `${(i + 1) * 20}%` }}
                />
            ))}
        </div>
    );
}

// ==========================================
// LIVE BADGE - Pulsing recording light
// ==========================================
export function LiveBadge({ label = "LIVE", className }: { label?: string; className?: string }) {
    return (
        <div className={cn("flex items-center gap-2 px-2 py-1 rounded bg-red-500/10 border border-red-500/20", className)}>
            <div className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
            </div>
            <span className="text-[10px] font-mono font-bold text-red-400 tracking-wider">
                {label}
            </span>
        </div>
    );
}

// ==========================================
// DATA PILL - Monospace data display
// ==========================================
export function DataPill({ label, value, variant = 'default' }: { label?: string; value: string | React.ReactNode; variant?: 'default' | 'accent' | 'warning' }) {
    const colors = {
        default: "text-white/80 border-white/10 bg-white/5",
        accent: "text-[#00ff88] border-[#00ff88]/30 bg-[#00ff88]/10",
        warning: "text-amber-400 border-amber-500/30 bg-amber-500/10",
    };

    return (
        <div className={cn("flex flex-col rounded border px-3 py-1.5 min-w-[80px]", colors[variant])}>
            {label && <span className="text-[9px] uppercase tracking-wider opacity-60 font-mono mb-0.5">{label}</span>}
            <span className="font-mono font-bold text-sm tracking-tight">{value}</span>
        </div>
    );
}
