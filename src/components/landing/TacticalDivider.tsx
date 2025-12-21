import { motion } from 'framer-motion';

interface TacticalDividerProps {
    className?: string;
    height?: string;
}

export function TacticalDivider({ className = '', height = 'h-24' }: TacticalDividerProps) {
    return (
        <div className={`relative w-full flex items-center justify-center overflow-hidden ${className} ${height}`}>
            <div className="relative w-full max-w-7xl px-4 flex flex-col items-center justify-center">

                {/* Hologram Base Glow */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-3/4 h-1 bg-accent/50 blur-[20px]" />

                {/* The Structure */}
                <div className="relative w-full h-[2px] bg-gradient-to-r from-transparent via-accent/40 to-transparent">
                    {/* Moving Scan Blip */}
                    <div className="absolute top-0 left-0 w-20 h-full bg-accent blur-[4px] animate-scan-fast" />
                </div>

                {/* Holographic Projection Plane */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-12 border-x border-accent/10 bg-accent/5 backdrop-blur-[2px] skew-x-12 flex items-center justify-between px-4 overflow-hidden">
                    {/* Scanlines */}
                    <div className="absolute inset-0 bg-[url('/grid-pattern.png')] opacity-10" />
                    <div className="absolute inset-0 bg-gradient-to-b from-transparent via-accent/10 to-transparent animate-pulse" />

                    {/* HUD Text */}
                    <span className="text-[10px] font-mono text-accent/60 tracking-[0.2em]">SYS.01</span>

                    {/* Center Graphic */}
                    <div className="flex gap-1">
                        {[1, 2, 3].map(i => (
                            <div key={i} className={`w-1 h-1 bg-accent/60 rounded-full animate-ping delay-${i * 100}`} />
                        ))}
                    </div>

                    <span className="text-[10px] font-mono text-accent/60 tracking-[0.2em] text-right">ACTIVE</span>
                </div>

                {/* Decorative Brackets */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[640px] h-8 border-x border-accent/20 skew-x-12" />

            </div>

            <style>{`
        @keyframes scan-fast {
            0% { left: 0%; opacity: 0; }
            20% { opacity: 1; }
            80% { opacity: 1; }
            100% { left: 100%; opacity: 0; }
        }
        .animate-scan-fast {
            animation: scan-fast 3s linear infinite;
        }
      `}</style>
        </div>
    );
}
