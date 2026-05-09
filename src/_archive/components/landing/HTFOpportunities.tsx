import { Target, Lightning, Crosshair, TrendUp, Info, ArrowRight, Pulse } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { Link } from 'react-router-dom';
import { useLandingData } from '@/context/LandingContext';

// Circular progress ring for confidence
function ConfidenceRing({ value, size = 56 }: { value: number; size?: number }) {
    const radius = (size - 8) / 2;
    const circumference = 2 * Math.PI * radius;
    const strokeDasharray = `${(value / 100) * circumference} ${circumference}`;

    const color = value >= 80 ? 'text-success' : value >= 60 ? 'text-accent' : 'text-warning';

    return (
        <div className="relative" style={{ width: size, height: size }}>
            <svg className="w-full h-full -rotate-90" viewBox={`0 0 ${size} ${size}`}>
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="4"
                    className="text-muted/20"
                />
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="4"
                    strokeLinecap="round"
                    strokeDasharray={strokeDasharray}
                    className={cn('transition-all duration-700', color)}
                />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
                <span className={cn('text-sm font-bold tabular-nums', color)}>
                    {Math.round(value)}%
                </span>
            </div>
        </div>
    );
}

// Mode badge with icon
function ModeBadge({ mode }: { mode: string }) {
    const modeConfig: Record<string, { icon: any; color: string; bgColor: string }> = {
        overwatch: { icon: Crosshair, color: 'text-cyan-400', bgColor: 'bg-cyan-500/20' },
        strike: { icon: Lightning, color: 'text-amber-400', bgColor: 'bg-amber-500/20' },
        surgical: { icon: Target, color: 'text-purple-400', bgColor: 'bg-purple-500/20' },
        stealth: { icon: Pulse, color: 'text-violet-400', bgColor: 'bg-violet-500/20' },
    };

    const config = modeConfig[mode.toLowerCase()] || modeConfig.overwatch;
    const Icon = config.icon;

    return (
        <div className={cn('inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-bold', config.bgColor, config.color)}>
            <Icon size={10} weight="bold" />
            {mode.toUpperCase()}
        </div>
    );
}

export function HTFOpportunities() {
    const { htf: data } = useLandingData();

    // No opportunities or not loaded yet
    if (!data || data.opportunities.length === 0) {
        return null;
    }

    // Show top 3 opportunities
    const topOpportunities = data.opportunities.slice(0, 3);

    return (
        <div className="relative rounded-xl border-2 border-accent/40 bg-gradient-to-br from-card/90 to-card/60 backdrop-blur-sm overflow-hidden">
            {/* Pulsing glow effect */}
            <div className="absolute inset-0 bg-gradient-to-r from-accent/5 via-accent/10 to-accent/5 animate-pulse pointer-events-none" />

            {/* Header */}
            <div className="relative px-4 py-3 border-b border-border/50 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-2 h-2 bg-accent rounded-full animate-pulse" />
                    <span className="text-xs font-bold tracking-[0.15em]">HTF TACTICAL OPPORTUNITIES</span>
                    <span className="text-[10px] text-muted-foreground font-mono">// LIVE</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-bold bg-accent/20 text-accent">
                        <div className="w-1.5 h-1.5 bg-accent rounded-full animate-pulse" />
                        {data.total} ACTIVE
                    </div>
                    <span className="text-[10px] text-muted-foreground font-mono">
                        {new Date(data.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                </div>
            </div>

            {/* Opportunities Grid */}
            <div className="relative p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {topOpportunities.map((opp, idx) => (
                    <div
                        key={idx}
                        className="relative p-4 rounded-xl bg-background/50 border border-border/50 hover:border-accent/50 hover:bg-background/70 transition-all duration-200 group"
                    >
                        {/* Symbol & Confidence */}
                        <div className="flex items-start justify-between mb-3">
                            <div>
                                <div className="font-mono text-lg font-bold text-primary">
                                    {opp.symbol.replace('/USDT', '').replace(':USDT', '')}
                                </div>
                                <div className="text-[10px] text-muted-foreground font-mono">
                                    {opp.level.timeframe} {opp.level.level_type}
                                </div>
                            </div>
                            <ConfidenceRing value={opp.confidence} size={48} />
                        </div>

                        {/* Expected Move */}
                        <div className="mb-3 pb-3 border-b border-border/30">
                            <div className="text-[10px] text-muted-foreground mb-1">EXPECTED MOVE</div>
                            <div className="flex items-center gap-2">
                                <TrendUp size={16} className="text-success" weight="bold" />
                                <span className="text-xl font-bold text-success">+{opp.expected_move_pct.toFixed(1)}%</span>
                            </div>
                        </div>

                        {/* Recommended Mode */}
                        <div className="mb-3">
                            <div className="text-[10px] text-muted-foreground mb-1.5">RECOMMENDED MODE</div>
                            <ModeBadge mode={opp.recommended_mode} />
                        </div>

                        {/* Rationale */}
                        <div className="text-xs text-muted-foreground leading-relaxed mb-3">
                            {opp.rationale}
                        </div>

                        {/* View Details Link */}
                        <Link
                            to={`/scanner/setup?mode=${opp.recommended_mode.toLowerCase()}`}
                            className="flex items-center justify-center gap-2 w-full py-2 rounded-lg bg-accent/10 hover:bg-accent/20 border border-accent/30 hover:border-accent/50 text-accent text-xs font-bold transition-all group-hover:shadow-lg group-hover:shadow-accent/20"
                        >
                            <span>DEPLOY SCANNER</span>
                            <ArrowRight size={14} weight="bold" className="group-hover:translate-x-0.5 transition-transform" />
                        </Link>
                    </div>
                ))}
            </div>

            {/* Footer */}
            {data.total > 3 && (
                <div className="px-4 py-2 border-t border-border/50 bg-muted/5 flex items-center justify-center">
                    <Link
                        to="/intel"
                        className="flex items-center gap-2 text-[10px] text-accent hover:underline group"
                    >
                        <Info size={12} />
                        <span>+{data.total - 3} more opportunities in Market Intel</span>
                        <ArrowRight size={10} className="group-hover:translate-x-0.5 transition-transform" />
                    </Link>
                </div>
            )}
        </div>
    );
}
