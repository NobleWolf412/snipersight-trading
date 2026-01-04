import { CaretLeft } from '@phosphor-icons/react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';

interface TacticalReturnButtonProps {
    to?: string;
    label?: string;
    className?: string;
}

export function TacticalReturnButton({ to = "/", label = "RETURN TO BASE", className }: TacticalReturnButtonProps) {
    const navigate = useNavigate();

    return (
        <button
            onClick={() => navigate(to)}
            className={cn(
                "group relative flex items-center gap-3 px-5 py-2.5",
                "bg-black/40 backdrop-blur-md border border-zinc-800/50",
                "hover:bg-zinc-900/60 hover:border-[#00ff88]/50",
                "transition-all duration-300 ease-out",
                // Clip path for tactical angled look
                "[clip-path:polygon(0_0,100%_0,100%_70%,90%_100%,0_100%)]",
                "before:absolute before:inset-0 before:bg-gradient-to-r before:from-[#00ff88]/0 before:via-[#00ff88]/5 before:to-transparent before:opacity-0 before:group-hover:opacity-100 before:transition-opacity",
                className
            )}
        >
            {/* Glow Effect Container */}
            <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 shadow-[0_0_20px_rgba(0,255,136,0.15)] pointer-events-none" />

            {/* Icon with animated slide */}
            <div className="relative z-10 p-1.5 rounded-md bg-zinc-900/80 border border-zinc-700/50 text-zinc-400 group-hover:text-[#00ff88] group-hover:border-[#00ff88]/30 transition-all group-hover:-translate-x-1">
                <CaretLeft size={18} weight="bold" />
            </div>

            {/* Label Text */}
            <div className="relative z-10 flex flex-col items-start">
                <span className="text-[10px] font-bold tracking-[0.2em] text-[#00ff88]/40 group-hover:text-[#00ff88]/80 transition-colors uppercase">
                    Command
                </span>
                <span className="text-sm font-bold font-mono tracking-wider text-zinc-300 group-hover:text-white transition-colors shadow-black drop-shadow-md">
                    {label}
                </span>
            </div>

            {/* Decorative corner accent */}
            <div className="absolute bottom-0 right-0 w-3 h-3 border-r-2 border-b-2 border-zinc-800/50 group-hover:border-[#00ff88]/50 transition-colors" />
        </button>
    );
}
