import { ConfluenceBreakdown, ConfluenceFactor } from '@/types/confluence';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { AlertTriangle, TrendingUp, Shield, Zap, Target } from 'lucide-react';
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from "@/components/ui/accordion"

interface TargetIntelScorecardProps {
    breakdown: ConfluenceBreakdown;
}

export function TargetIntelScorecard({ breakdown }: TargetIntelScorecardProps) {
    // Sort factors: red flags (<40) separate from others
    const sortedFactors = [...breakdown.factors].sort((a, b) => b.score - a.score);
    const redFlags = sortedFactors.filter(f => f.score < 40);
    const regularFactors = sortedFactors.filter(f => f.score >= 40);

    const getGrade = (score: number) => {
        if (score >= 85) return { grade: 'A', color: 'bg-green-500 text-white', label: 'LOCKED' };
        if (score >= 60) return { grade: 'B', color: 'bg-emerald-500/80 text-white', label: 'ACQUIRED' };
        if (score >= 40) return { grade: 'C', color: 'bg-yellow-500/80 text-white', label: 'WEAK' };
        return { grade: 'F', color: 'bg-destructive/90 text-white', label: 'MISSING' };
    };

    const getProgressColor = (score: number) => {
        if (score >= 70) return 'bg-green-500';
        if (score >= 40) return 'bg-yellow-500';
        return 'bg-destructive';
    };

    return (
        <div className="space-y-6 font-sans">

            {/* Header Stat Block */}
            <div className="bg-muted/30 rounded-lg p-4 border border-border/50">
                <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2 text-muted-foreground uppercase text-xs tracking-widest font-bold">
                        <Target size={14} />
                        Confluence Score
                    </div>
                    <div className="text-2xl font-black font-mono tracking-tighter">
                        {breakdown.total_score.toFixed(0)}<span className="text-muted-foreground text-sm font-normal">/100</span>
                    </div>
                </div>

                {/* Regime & Safety Tags */}
                <div className="flex flex-wrap gap-2">
                    {breakdown.htf_aligned && (
                        <Badge variant="outline" className="border-green-500/30 text-green-500 bg-green-500/10 text-[10px] tracking-wide">
                            <Shield size={10} className="mr-1" />
                            HTF ALIGNED
                        </Badge>
                    )}
                    {breakdown.btc_impulse_gate && (
                        <Badge variant="outline" className="border-blue-500/30 text-blue-500 bg-blue-500/10 text-[10px] tracking-wide">
                            <TrendingUp size={10} className="mr-1" />
                            BTC IMPULSE
                        </Badge>
                    )}
                    <Badge variant="outline" className="text-[10px] tracking-wide text-muted-foreground">
                        REGIME: {breakdown.regime.toUpperCase()}
                    </Badge>
                </div>
            </div>

            {/* Red Flags Section */}
            {redFlags.length > 0 && (
                <div className="space-y-3 animate-in fade-in slide-in-from-top-2 duration-300">
                    <h4 className="flex items-center gap-2 text-xs font-bold text-destructive uppercase tracking-widest">
                        <AlertTriangle size={14} />
                        Mission Risks / Red Flags
                    </h4>
                    <div className="space-y-2">
                        {redFlags.map(factor => (
                            <div key={factor.name} className="bg-destructive/10 border border-destructive/20 rounded px-3 py-2 flex items-center justify-between">
                                <div>
                                    <div className="text-sm font-bold text-destructive">{factor.name}</div>
                                    <div className="text-[10px] text-destructive/80 font-mono uppercase">Status: MISSING ({factor.score.toFixed(0)}%)</div>
                                </div>
                                <div className="text-xs text-muted-foreground max-w-[50%] text-right truncate">
                                    {factor.rationale}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <Separator className="bg-border/40" />

            {/* Main Scorecard */}
            <div className="space-y-3">
                <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
                    <Target size={14} />
                    Precision Factors
                </h4>

                <Accordion type="single" collapsible className="w-full">
                    {regularFactors.map((factor) => {
                        const metrics = getGrade(factor.score);
                        return (
                            <AccordionItem key={factor.name} value={factor.name} className="border-b-0 mb-2">
                                <AccordionTrigger className="hover:no-underline py-2 px-3 bg-muted/20 hover:bg-muted/40 rounded-lg border border-transparent hover:border-border/30 transition-all">
                                    <div className="flex flex-col w-full gap-2">
                                        <div className="flex items-center justify-between w-full">
                                            <span className="font-semibold text-sm">{factor.name}</span>
                                            <Badge className={`${metrics.color} border-0 text-[10px] font-mono w-20 justify-center`}>
                                                {metrics.label}
                                            </Badge>
                                        </div>
                                        {/* Progress Bar Row */}
                                        <div className="flex items-center gap-3 w-full">
                                            <Progress
                                                value={factor.score}
                                                className="h-1.5 bg-muted flex-1"
                                                indicatorClassName={getProgressColor(factor.score)}
                                            />
                                            <span className="text-[10px] font-mono text-muted-foreground w-8 text-right">
                                                {factor.score.toFixed(0)}%
                                            </span>
                                        </div>
                                    </div>
                                </AccordionTrigger>
                                <AccordionContent className="px-3 pt-2 pb-3 text-xs text-muted-foreground leading-relaxed">
                                    <div className="pl-2 border-l-2 border-primary/20">
                                        {factor.rationale}
                                    </div>
                                </AccordionContent>
                            </AccordionItem>
                        );
                    })}
                </Accordion>
            </div>

            {(breakdown.synergy_bonus > 0 || breakdown.conflict_penalty > 0) && (
                <>
                    <Separator className="bg-border/40" />
                    <div className="grid grid-cols-2 gap-4">
                        {breakdown.synergy_bonus > 0 && (
                            <div className="space-y-1">
                                <div className="text-[10px] uppercase tracking-wider text-green-500 font-bold flex items-center gap-1">
                                    <Zap size={12} fill="currentColor" /> Synergy
                                </div>
                                <div className="text-sm font-mono">+{breakdown.synergy_bonus.toFixed(1)}</div>
                            </div>
                        )}

                        {breakdown.conflict_penalty > 0 && (
                            <div className="space-y-1 text-right">
                                <div className="text-[10px] uppercase tracking-wider text-orange-500 font-bold flex items-center justify-end gap-1">
                                    <AlertTriangle size={12} fill="currentColor" /> Conflict
                                </div>
                                <div className="text-sm font-mono text-destructive">-{breakdown.conflict_penalty.toFixed(1)}</div>
                            </div>
                        )}
                    </div>
                </>
            )}

        </div>
    );
}
