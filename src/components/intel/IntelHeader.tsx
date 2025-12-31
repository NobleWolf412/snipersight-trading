
import { cn } from '@/lib/utils';
import { Broadcast, Circle } from '@phosphor-icons/react';

export function IntelHeader() {
    return (
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 py-6">
            <div className="space-y-1">
                <div className="flex items-center gap-2">
                    <Broadcast size={24} weight="bold" className="text-accent" />
                    <h1 className="text-2xl font-bold tracking-tight heading-hud">THE WAR ROOM</h1>
                </div>
                <p className="text-sm text-muted-foreground font-mono">
                    MKR-INTEL-V2 // GLOBAL COMMAND CENTER
                </p>
            </div>

            <div className="flex items-center gap-4">
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent/10 border border-accent/20">
                    <div className="relative">
                        <Circle size={8} weight="fill" className="text-accent animate-pulse" />
                        <div className="absolute inset-0 bg-accent rounded-full animate-ping opacity-75" />
                    </div>
                    <span className="text-xs font-bold text-accent tracking-wider">LIVE FEED</span>
                </div>
                <div className="text-right hidden md:block">
                    <div className="text-xs font-mono text-muted-foreground">Session ID</div>
                    <div className="text-xs font-bold font-mono">A7-X99-BRAVO</div>
                </div>
            </div>
        </div>
    );
}
