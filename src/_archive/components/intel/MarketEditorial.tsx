
import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { Quotes, Warning, CheckCircle, Brain } from '@phosphor-icons/react';

interface Props {
    className?: string;
    regime: any;
    btcContext: any;
}

export function MarketEditorial({ className, regime, btcContext }: Props) {

    // Editorial Logic (Simulated "AI Analyst")
    const editorialContent = useMemo(() => {
        const bias = btcContext?.four_year_cycle?.macro_bias || 'NEUTRAL';
        const phase = btcContext?.four_year_cycle?.phase || 'UNKNOWN';
        const daysSinceHigh = btcContext?.dcl?.days_since || 0;

        // Generate dynamic "Bottom Line"
        let bottomLine = "Market direction is ambiguous. Proceed with caution.";
        if (bias === 'BULLISH') {
            bottomLine = "The structural trend remains unequivocally bullish. Pullbacks are for buying, not for shorting.";
        } else if (bias === 'BEARISH') {
            bottomLine = "Structure has broken. The path of least resistance is down until proven otherwise.";
        }

        // Generate "Cycle Insight"
        let cycleInsight = "We are currently tracking the daily cycle development.";
        if (daysSinceHigh > 20) {
            cycleInsight = "The daily cycle is extended. A local top is likely forming or has already formed. Expect volatility.";
        } else if (daysSinceHigh < 10) {
            cycleInsight = "We are early in the new daily cycle. This is typically the safest window for long entries.";
        }

        return {
            title: `MARKET BRIEF: ${bias} STRUCTURE`,
            date: new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' }),
            bottomLine,
            cycleInsight,
            bias, // Include bias in the returned object
            phase, // Include phase too for the JSX
            axiom: "In a bull market, bad news is ignored. In a bear market, good news is sold."
        };
    }, [btcContext]);

    return (
        <div className={cn(
            "relative overflow-hidden",
            className
        )}>
            <div className="flex flex-col gap-6">

                {/* Header Section */}
                <div className="border-l-4 border-accent pl-6 py-2">
                    <h2 className="text-3xl font-bold tracking-tight text-foreground mb-1">
                        {editorialContent.title}
                    </h2>
                    <p className="text-sm font-mono text-muted-foreground uppercase tracking-wider">
                        {editorialContent.date} // SNIPERSIGHT INTEL
                    </p>
                </div>

                {/* The Executive Summary */}
                <div className="prose prose-invert max-w-none">
                    <p className="text-lg leading-relaxed text-foreground/90 font-medium">
                        <span className="text-accent font-bold">THE BOTTOM LINE: </span>
                        {editorialContent.bottomLine}
                    </p>

                    <div className="my-6 grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Cycle Analysis Card */}
                        <div className="bg-blue-500/5 p-5 rounded-xl border border-blue-500/20 hover:border-blue-500/40 transition-colors">
                            <h4 className="flex items-center gap-2 text-sm font-bold text-blue-400 uppercase mb-3 tracking-wide">
                                <Brain size={18} weight="duotone" /> Cycle Analysis
                            </h4>
                            <p className="text-sm leading-relaxed text-foreground/80">
                                {editorialContent.cycleInsight}
                            </p>
                            <p className="text-sm leading-relaxed text-foreground/60 mt-3 pt-3 border-t border-blue-500/10">
                                Our proprietary 4-Year Cycle Gauge (<span className="text-blue-400 font-semibold">{editorialContent.phase}</span>) indicates we are structurally positioned for <span className="font-semibold">{(editorialContent.bias || 'neutral').toLowerCase()}</span> continuation.
                            </p>
                        </div>

                        {/* Risk Assessment Card */}
                        <div className="bg-amber-500/5 p-5 rounded-xl border border-amber-500/20 hover:border-amber-500/40 transition-colors">
                            <h4 className="flex items-center gap-2 text-sm font-bold text-amber-400 uppercase mb-3 tracking-wide">
                                <Warning size={18} weight="duotone" /> Risk Assessment
                            </h4>
                            <p className="text-sm leading-relaxed text-foreground/80">
                                Volatility remains elevated. Leverage should be reduced.
                            </p>
                            <p className="text-sm leading-relaxed text-foreground/60 mt-3 pt-3 border-t border-amber-500/10">
                                The primary risk at this moment is <span className="font-semibold text-amber-400">{editorialContent.bias === 'BULLISH' ? 'over-leveraged late longs flushing out' : 'short squeezes on relief rallies'}</span>.
                            </p>
                        </div>
                    </div>

                    <p className="text-base text-muted-foreground leading-relaxed">
                        Structuring your trades around the higher timeframe bias is critical. Do not let hourly noise distract you from the weekly reality. Remember the Camel Finance axiom: <em>market structure precedes narrative.</em> If the structure is broken, the "news" will eventually turn bad to explain the drop.
                    </p>
                </div>

                {/* Quote / Footer */}
                <div className="flex items-start gap-4 mt-4 p-4 bg-accent/5 rounded-lg border border-accent/20">
                    <Quotes size={24} className="text-accent flex-shrink-0" weight="fill" />
                    <div>
                        <p className="text-sm font-medium italic text-foreground/80">
                            "{editorialContent.axiom}"
                        </p>
                        <p className="text-xs font-bold text-accent mt-2 uppercase tracking-wide">
                            - Trading Philosophy
                        </p>
                    </div>
                </div>

            </div>
        </div>
    );
}
