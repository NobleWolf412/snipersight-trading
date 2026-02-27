import { cn } from "@/lib/utils";

/**
 * A bracket-style corner border common in tactical UIs.
 * Supports 'corner-only' or 'full-frame' modes.
 */
export function TechFrame({ children, className, color = "accent" }: { children: React.ReactNode, className?: string, color?: "accent" | "red" | "white" }) {
    const borderColor = color === "accent" ? "#00ff88" : color === "red" ? "#ff4444" : "#ffffff";

    return (
        <div className={cn("relative p-6 group", className)}>
            {/* Top Left Corner */}
            <svg className="absolute top-0 left-0 w-8 h-8 pointer-events-none" viewBox="0 0 32 32" fill="none">
                <path d="M1 31V1H31" stroke={borderColor} strokeWidth="2" strokeOpacity="0.5" />
                <rect x="0" y="0" width="4" height="4" fill={borderColor} />
            </svg>

            {/* Top Right Corner */}
            <svg className="absolute top-0 right-0 w-8 h-8 pointer-events-none" viewBox="0 0 32 32" fill="none">
                <path d="M1 1H31V31" stroke={borderColor} strokeWidth="2" strokeOpacity="0.5" />
                <rect x="28" y="0" width="4" height="4" fill={borderColor} />
            </svg>

            {/* Bottom Right Corner */}
            <svg className="absolute bottom-0 right-0 w-8 h-8 pointer-events-none" viewBox="0 0 32 32" fill="none">
                <path d="M31 1V31H1" stroke={borderColor} strokeWidth="2" strokeOpacity="0.5" />
                <rect x="28" y="28" width="4" height="4" fill={borderColor} />
            </svg>

            {/* Bottom Left Corner */}
            <svg className="absolute bottom-0 left-0 w-8 h-8 pointer-events-none" viewBox="0 0 32 32" fill="none">
                <path d="M31 31H1V1" stroke={borderColor} strokeWidth="2" strokeOpacity="0.5" />
                <rect x="0" y="28" width="4" height="4" fill={borderColor} />
            </svg>

            {/* Content */}
            <div className="relative z-10">
                {children}
            </div>
        </div>
    );
}

/**
 * A horizontal separator with a "tech" look (notches and fading lines).
 */
export function TechSeparator({ className, color = "accent" }: { className?: string, color?: "accent" | "white" }) {
    const strokeColor = color === "accent" ? "#00ff88" : "#ffffff";

    return (
        <div className={cn("relative h-4 w-full flex items-center justify-center my-4 opacity-70", className)}>
            <svg className="w-full h-full absolute inset-0 text-white" preserveAspectRatio="none">
                {/* Center Diamond */}
                <rect x="50%" y="50%" width="8" height="8" transform="translate(-4, -4) rotate(45)" fill={strokeColor} fillOpacity="0.2" stroke={strokeColor} strokeWidth="1" />

                {/* Left Line */}
                <line x1="0" y1="50%" x2="calc(50% - 16px)" y2="50%" stroke={`url(#fade-left-${color})`} strokeWidth="1" />
                {/* Right Line */}
                <line x1="calc(50% + 16px)" y1="50%" x2="100%" y2="50%" stroke={`url(#fade-right-${color})`} strokeWidth="1" />

                <defs>
                    <linearGradient id={`fade-left-${color}`} x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor={strokeColor} stopOpacity="0" />
                        <stop offset="100%" stopColor={strokeColor} stopOpacity="0.5" />
                    </linearGradient>
                    <linearGradient id={`fade-right-${color}`} x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor={strokeColor} stopOpacity="0.5" />
                        <stop offset="100%" stopColor={strokeColor} stopOpacity="0" />
                    </linearGradient>
                </defs>
            </svg>
        </div>
    );
}

/**
 * A decorative "Caution" strip pattern border.
 */
export function HazardBorder({ className }: { className?: string }) {
    return (
        <div className={cn("h-2 w-full bg-[repeating-linear-gradient(45deg,transparent,transparent_10px,rgba(255,194,10,0.1)_10px,rgba(255,194,10,0.1)_20px)] border-t border-b border-yellow-500/10", className)} />
    );
}

/**
 * A corner bracket simple used for smaller elements.
 */
export function CornerBrackets({ className, color = "accent" }: { className?: string, color?: string }) {
    const c = color === "accent" ? "text-accent" : "text-white";
    return (
        <div className={cn("absolute inset-0 pointer-events-none", className)}>
            <div className={cn("absolute top-0 left-0 w-2 h-2 border-l border-t", c)} />
            <div className={cn("absolute top-0 right-0 w-2 h-2 border-r border-t", c)} />
            <div className={cn("absolute bottom-0 left-0 w-2 h-2 border-l border-b", c)} />
            <div className={cn("absolute bottom-0 right-0 w-2 h-2 border-r border-b", c)} />
        </div>
    );
}
