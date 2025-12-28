import React from 'react';
import { House, Crosshair, ChartBar, ClockCounterClockwise, Gear, UserCircle, SignOut } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

export function NavigationRail() {
    const navItems = [
        { icon: House, label: 'COMMAND', active: false },
        { icon: Crosshair, label: 'SCANNER', active: true },
        { icon: ChartBar, label: 'MARKETS', active: false },
        { icon: ClockCounterClockwise, label: 'HISTORY', active: false },
    ];

    const bottomItems = [
        { icon: Gear, label: 'SYSTEM', active: false },
        { icon: UserCircle, label: 'OPERATOR', active: false },
    ];

    return (
        <div className="h-full w-[64px] border-r border-white/10 bg-black flex flex-col items-center py-6 z-50 relative">
            {/* Logo / Brand */}
            <div className="mb-8 relative group cursor-pointer">
                <div className="w-8 h-8 rounded bg-accent/20 border border-accent/50 flex items-center justify-center text-accent shadow-[0_0_15px_rgba(0,255,170,0.3)] group-hover:bg-accent/30 transition-all">
                    <div className="w-2 h-2 bg-accent rounded-full animate-pulse" />
                </div>
            </div>

            {/* Main Nav */}
            <div className="flex flex-col gap-4 w-full">
                {navItems.map((item) => (
                    <NavItem key={item.label} {...item} />
                ))}
            </div>

            <div className="flex-1" />

            {/* Bottom Nav */}
            <div className="flex flex-col gap-4 w-full mb-4">
                {bottomItems.map((item) => (
                    <NavItem key={item.label} {...item} />
                ))}
                <div className="w-8 h-px bg-white/10 mx-auto my-2" />
                <button className="w-10 h-10 rounded-lg flex items-center justify-center text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition-colors mx-auto">
                    <SignOut size={20} />
                </button>
            </div>

            {/* Decorative Line */}
            <div className="absolute left-0 top-0 bottom-0 w-[1px] bg-gradient-to-b from-transparent via-accent/20 to-transparent" />
        </div>
    );
}

function NavItem({ icon: Icon, label, active }: { icon: any, label: string, active: boolean }) {
    return (
        <div className="relative group w-full flex justify-center">
            {active && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 bg-accent shadow-[0_0_10px_#00ff88]" />
            )}

            <button className={cn(
                "w-10 h-10 rounded-lg flex items-center justify-center transition-all duration-200 group-hover:scale-105",
                active
                    ? "text-accent bg-accent/10"
                    : "text-zinc-500 hover:text-white hover:bg-white/5"
            )}>
                <Icon size={24} weight={active ? "duotone" : "regular"} />
            </button>

            {/* Tooltip */}
            <div className="absolute left-full top-1/2 -translate-y-1/2 ml-4 px-2 py-1 bg-black/90 border border-white/10 rounded text-[9px] font-bold tracking-widest text-white whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 backdrop-blur-md translate-x-1 group-hover:translate-x-0">
                {label}
            </div>
        </div>
    )
}
