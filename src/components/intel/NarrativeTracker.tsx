
import { cn } from '@/lib/utils';
import { Fire, Trophy, TrendUp, Warning } from '@phosphor-icons/react';

interface Narrative {
    name: string;
    strength: 'extreme' | 'strong' | 'moderate' | 'weak';
    trend: 'up' | 'down' | 'flat';
    tickers: string[];
}

interface Props {
    className?: string;
}

export function NarrativeTracker({ className }: Props) {
    const narratives: Narrative[] = [
        { name: 'AI Agents', strength: 'strong', trend: 'up', tickers: ['FET', 'TAO', 'WLD'] },
        { name: 'RWA', strength: 'moderate', trend: 'flat', tickers: ['ONDO', 'PENDLE'] },
        { name: 'Meme Coins', strength: 'weak', trend: 'down', tickers: ['PEPE', 'WIF'] },
        { name: 'L2 Scaling', strength: 'moderate', trend: 'up', tickers: ['OP', 'ARB'] },
        { name: 'Gaming', strength: 'weak', trend: 'flat', tickers: ['IMX', 'BEAM'] },
    ];

    const getStrengthColor = (s: string) => {
        switch (s) {
            case 'extreme': return 'text-red-500 bg-red-500/10 border-red-500/20';
            case 'strong': return 'text-orange-500 bg-orange-500/10 border-orange-500/20';
            case 'moderate': return 'text-yellow-500 bg-yellow-500/10 border-yellow-500/20';
            case 'weak': return 'text-muted-foreground bg-muted/10 border-muted/20';
            default: return 'text-muted-foreground';
        }
    };

    return (
        <div className={cn(
            "rounded-xl border border-border/40 bg-card/20 backdrop-blur-sm p-4",
            className
        )}>
            <div className="flex items-center justify-between mb-4">
                <div className="text-xs font-bold text-muted-foreground tracking-widest uppercase">
                    ACTIVE NARRATIVES
                </div>
                <Fire className="text-orange-500 animate-pulse" weight="fill" />
            </div>

            <div className="space-y-2">
                {narratives.map((n, idx) => {
                    const colorClass = getStrengthColor(n.strength);

                    return (
                        <div key={idx} className="flex items-center justify-between p-2 rounded-lg hover:bg-white/5 transition-colors border border-transparent hover:border-white/5">
                            <div className="flex items-center gap-3">
                                <div className={cn(
                                    "w-1.5 h-1.5 rounded-full",
                                    n.strength === 'strong' ? "bg-orange-500" :
                                        n.strength === 'moderate' ? "bg-yellow-500" : "bg-muted-foreground"
                                )} />
                                <div>
                                    <div className="text-sm font-bold text-foreground">{n.name}</div>
                                    <div className="text-[10px] text-muted-foreground font-mono">
                                        {n.tickers.join(', ')}
                                    </div>
                                </div>
                            </div>

                            <div className={cn("px-2 py-0.5 rounded text-[10px] font-mono border uppercase", colorClass)}>
                                {n.strength}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
