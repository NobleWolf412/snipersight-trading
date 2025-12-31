
import { cn } from '@/lib/utils';
import {
    FileText,
    Target,
    Warning,
    ShieldCheck,
    Crosshair,
    CaretRight
} from '@phosphor-icons/react';

interface BriefingSection {
    title: string;
    content: string;
    type: 'context' | 'bias' | 'mission';
}

interface Props {
    className?: string;
}

export function DailyBriefing({ className }: Props) {
    // Mock data - eventually this would come from an AI synthesis endpoint
    const dateStr = new Date().toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    }).toUpperCase();

    const briefing: BriefingSection[] = [
        {
            type: 'context',
            title: 'SITUATION REPORT',
            content: 'BTC is currently sweeping 4H lows while dominance (BTC.D) grinds higher. Liquidity is thinning out on altcoins as capital rotates back into Bitcoin and stablecoins in a defensive posture.'
        },
        {
            type: 'bias',
            title: 'TACTICAL BIAS',
            content: 'DEFENSIVE / RISK-OFF. The market structure suggests further consolidation. Longs on altcoins are low-probability until BTC reclaims the $68.5k level. Short-term bounces are likely to be sold.'
        },
        {
            type: 'mission',
            title: 'MISSION PARAMETERS',
            content: 'Deploy "SURGICAL" or "RECON" modes only. Focus fire on Top 10 liquid assets. Avoid meme coin exposure (high invalidation risk). Look for shorts on bearish retests of resistance.'
        }
    ];

    return (
        <div className={cn(
            "relative overflow-hidden rounded-2xl border border-border/50 bg-card/40 backdrop-blur-md",
            "p-6 md:p-8",
            "group hover:border-accent/30 transition-colors duration-500",
            className
        )}>
            {/* Background Decor */}
            <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none">
                <FileText size={200} weight="thin" />
            </div>
            <div className="absolute bottom-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-accent/20 to-transparent opacity-50" />

            {/* Header */}
            <div className="relative z-10 mb-8 border-b border-white/5 pb-4">
                <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2 text-accent">
                        <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                        <span className="text-xs font-mono tracking-[0.2em] font-bold">CLASSIFIED INTELLIGENCE</span>
                    </div>
                    <span className="text-xs font-mono text-muted-foreground">{dateStr}</span>
                </div>
                <h2 className="text-3xl md:text-4xl font-bold font-mono tracking-tight text-foreground uppercase">
                    DAILY TACTICAL BRIEF
                </h2>
            </div>

            {/* Briefing Grid */}
            <div className="relative z-10 grid gap-8 md:grid-cols-3">
                {briefing.map((section, idx) => {
                    const isMission = section.type === 'mission';
                    const isBias = section.type === 'bias';

                    return (
                        <div key={idx} className={cn(
                            "space-y-3 relative",
                            idx !== 2 && "md:border-r md:border-white/5 md:pr-6"
                        )}>
                            <div className="flex items-center gap-2 mb-1">
                                {isMission ? (
                                    <Crosshair weight="bold" className="text-red-400" size={18} />
                                ) : isBias ? (
                                    <ShieldCheck weight="bold" className="text-amber-400" size={18} />
                                ) : (
                                    <Target weight="bold" className="text-blue-400" size={18} />
                                )}
                                <h3 className={cn(
                                    "text-sm font-bold tracking-widest uppercase",
                                    isMission ? "text-red-400" : isBias ? "text-amber-400" : "text-blue-400"
                                )}>
                                    {section.title}
                                </h3>
                            </div>
                            <p className="text-sm md:text-base text-muted-foreground leading-relaxed font-mono">
                                {section.content}
                            </p>
                        </div>
                    );
                })}
            </div>

            {/* Footer / CTA */}
            <div className="relative z-10 mt-8 pt-4 border-t border-white/5 flex items-center justify-between">
                <div className="text-xs text-muted-foreground font-mono">
          // AUTHORIZED EYES ONLY
                </div>
                <div className="flex items-center gap-2 text-xs font-bold text-accent cursor-pointer hover:underline">
                    VIEW FULL DOSSIER <CaretRight weight="bold" />
                </div>
            </div>
        </div>
    );
}
