import { useLandingData } from '@/context/LandingContext';
import { cn } from '@/lib/utils';

export function LandingLoader() {
    const { progress } = useLandingData();

    // Create segments for the progress bar
    const totalSegments = 20;
    const filledSegments = Math.floor((progress / 100) * totalSegments);

    return (
        <div className="min-h-screen w-full flex flex-col items-center justify-center bg-background relative overflow-hidden">
            {/* Background Grid */}
            <div className="fixed inset-0 tactical-grid opacity-10 pointer-events-none" />

            {/* Central Content */}
            <div className="relative z-10 flex flex-col items-center gap-8 w-full max-w-md px-8">

                {/* Animated Icon */}
                {/* Animated Target Reticle (CSS Only) */}
                <div className="relative mb-6">
                    {/* Outer glow */}
                    <div className="absolute inset-0 bg-accent/20 blur-xl rounded-full" />

                    {/* Rotating outer rings */}
                    <div className="relative w-24 h-24 flex items-center justify-center">
                        {/* Ring 1 - Fast Scan */}
                        <div className="absolute inset-0 border border-accent/30 rounded-full border-t-accent border-r-transparent animate-spin duration-1000" />

                        {/* Ring 2 - Slow Counter-Scan */}
                        <div className="absolute inset-2 border border-accent/20 rounded-full border-b-accent border-l-transparent animate-[spin_3s_linear_infinite_reverse]" />

                        {/* Inner Crosshair */}
                        <div className="absolute w-full h-[1px] bg-accent/30" />
                        <div className="absolute h-full w-[1px] bg-accent/30" />

                        {/* Center Dot */}
                        <div className="w-2 h-2 bg-accent rounded-full animate-pulse shadow-[0_0_10px_rgba(0,255,170,0.8)]" />
                    </div>
                </div>

                {/* Text Status */}
                <div className="text-center space-y-2 w-full">
                    <div className="text-sm font-bold tracking-[0.2em] text-accent font-mono animate-pulse">
                        INITIALIZING TACTICAL SYSTEMS
                    </div>
                    <div className="text-[10px] text-muted-foreground font-mono flex justify-between px-1">
                        <span>ESTABLISHING FEED</span>
                        <span>{Math.floor(progress)}%</span>
                    </div>
                </div>

                {/* Tactical Progress Bar */}
                <div className="w-full space-y-2">
                    {/* Segmented Bar */}
                    <div className="flex gap-1 h-2 w-full">
                        {Array.from({ length: totalSegments }).map((_, i) => (
                            <div
                                key={i}
                                className={cn(
                                    "flex-1 h-full rounded-[1px] transition-all duration-300",
                                    i < filledSegments
                                        ? "bg-accent shadow-[0_0_8px_rgba(0,255,170,0.6)]"
                                        : "bg-accent/10"
                                )}
                            />
                        ))}
                    </div>

                    {/* Hex Code Decor */}
                    <div className="flex justify-between text-[8px] font-mono text-accent/40 tracking-widest">
                        <span>0x7F2A...9C</span>
                        <span>SYNC::ACTIVE</span>
                    </div>
                </div>

            </div>
        </div>
    );
}
