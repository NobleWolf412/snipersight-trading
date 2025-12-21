import { useRef } from 'react';

interface TacticalDividerProps {
    className?: string;
    height?: string;
}

export function TacticalDivider({ className = '', height = 'h-32' }: TacticalDividerProps) {
    return (
        <div className={`relative w-full ${height} ${className} flex items-center justify-center overflow-visible`}>
            {/* Added h-full to ensure positioning context has height */}
            <div className="relative w-full h-full max-w-[1920px] px-0 flex items-center justify-center">

                {/* 1. Core Plasma Beam (The Fissure) */}
                <div className="absolute top-1/2 left-0 -translate-y-1/2 w-full h-[2px] bg-white shadow-[0_0_20px_rgba(255,200,100,0.8)] z-20">
                    {/* Inner hot core pulsation */}
                    <div className="absolute inset-0 bg-orange-400 animate-pulse-fast" />
                </div>

                {/* 2. Neon Glow Field (Massive Spread) */}
                <div className="absolute top-1/2 left-0 -translate-y-1/2 w-full h-[4px] bg-orange-500 blur-[4px] opacity-80 z-10 shadow-[0_0_60px_rgba(255,100,0,0.6)]" />

                {/* 3. Atmospheric Halo (Fades into darkness) */}
                <div
                    className="absolute top-1/2 left-0 -translate-y-1/2 w-full h-32 bg-gradient-to-r from-transparent via-orange-500/10 to-transparent blur-[40px] z-0 transform scale-y-50 origin-center"
                    style={{ maskImage: 'linear-gradient(to right, transparent, black 20%, black 80%, transparent)' }}
                />

                {/* 4. Scanning Filament (Movement) */}
                <div className="absolute top-1/2 left-0 -translate-y-1/2 w-1/2 h-[1px] bg-gradient-to-r from-transparent via-white/80 to-transparent z-30 animate-scan-bounce blur-[1px]" />

                {/* 5. Hard Border Fallback (Safety Line) */}
                <div className="absolute top-1/2 left-0 -translate-y-1/2 w-full h-[1px] bg-orange-500/20" />

            </div>

            <style>{`
        @keyframes scan-bounce {
            0% { transform: translateX(-50%) scaleX(0.2); opacity: 0; }
            50% { transform: translateX(0%) scaleX(1); opacity: 1; }
            100% { transform: translateX(50%) scaleX(0.2); opacity: 0; }
        }
        .animate-scan-bounce {
            animation: scan-bounce 4s ease-in-out infinite alternate;
        }
        .animate-pulse-fast {
            animation: pulse 0.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }
      `}</style>
        </div>
    );
}
