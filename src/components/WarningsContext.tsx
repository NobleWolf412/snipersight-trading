import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Warning, Info, Lightning, ShieldWarning, Clock, TrendDown, Pulse, CaretDown, CaretUp } from '@phosphor-icons/react';
import type { ScanResult } from '@/utils/mockData';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { useState } from 'react';

interface WarningsContextProps {
    results: ScanResult[];
    metadata: any;
    embedded?: boolean;
    className?: string;
}

interface WarningItem {
    type: 'warning' | 'caution' | 'info';
    title: string;
    description: string;
    icon: React.ReactNode;
    affectedSymbols?: string[];
    severity: 'high' | 'medium' | 'low';
}

/**
 * WarningsContext - Displays risk alerts and important context for the scan
 */
export function WarningsContext({ results, metadata, embedded = false, className = '' }: WarningsContextProps) {
    const [isExpanded, setIsExpanded] = useState(true);

    if (!results || results.length === 0) return null;

    const warnings: WarningItem[] = [];

    // Check for ATR fallback entries (less precise)
    const atrEntries = results.filter(r => (r as any).plan_type === 'ATR_FALLBACK');
    if (atrEntries.length > 0) {
        warnings.push({
            type: 'caution',
            title: 'ATR-Based Entries Detected',
            description: `${atrEntries.length} signal(s) using ATR fallback instead of SMC structure. Entry precision may be lower.`,
            icon: <ShieldWarning size={18} className="text-warning" />,
            affectedSymbols: atrEntries.map(r => r.pair),
            severity: 'medium'
        });
    }

    // Check for borderline confidence scores
    const minScore = metadata?.effectiveMinScore || 65;
    const borderline = results.filter(r => r.confidenceScore < minScore + 5 && r.confidenceScore >= minScore);
    if (borderline.length > 0) {
        warnings.push({
            type: 'warning',
            title: 'Borderline Confidence',
            description: `${borderline.length} signal(s) just above threshold. Consider position sizing carefully.`,
            icon: <TrendDown size={18} className="text-yellow-400" />,
            affectedSymbols: borderline.map(r => r.pair),
            severity: 'medium'
        });
    }

    // Check for low R:R trades
    const lowRR = results.filter(r => {
        const rr = (r as any).riskReward;
        return rr && rr < 2.0 && rr >= 1.5;
    });
    if (lowRR.length > 0) {
        warnings.push({
            type: 'info',
            title: 'Modest Risk-Reward',
            description: `${lowRR.length} signal(s) with R:R between 1.5-2.0. Higher win-rate needed for profitability.`,
            icon: <Pulse size={18} className="text-primary" />,
            affectedSymbols: lowRR.map(r => r.pair),
            severity: 'low'
        });
    }

    // Check for reversal context signals (higher risk)
    const reversals = results.filter(r => (r as any).reversal_context?.is_reversal);
    if (reversals.length > 0) {
        warnings.push({
            type: 'caution',
            title: 'Counter-Trend Entries',
            description: `${reversals.length} signal(s) are potential reversals. These carry higher risk as they trade against momentum.`,
            icon: <Lightning size={18} className="text-orange-400" />,
            affectedSymbols: reversals.map(r => r.pair),
            severity: 'high'
        });
    }

    // Check for high volatility warnings from regime
    const highVol = results.filter(r => {
        const regime = (r as any).regime;
        return regime?.symbol_regime?.volatility === 'HIGH' || regime?.global_regime?.volatility === 'HIGH';
    });
    if (highVol.length > 0) {
        warnings.push({
            type: 'warning',
            title: 'High Volatility Environment',
            description: `${highVol.length} signal(s) in high volatility conditions. Consider tighter stops or reduced size.`,
            icon: <Warning size={18} className="text-orange-400" />,
            affectedSymbols: highVol.map(r => r.pair),
            severity: 'high'
        });
    }

    // Check for stale data warning
    const scanTime = metadata?.timestamp;
    if (scanTime) {
        const ageMinutes = (Date.now() - new Date(scanTime).getTime()) / 60000;
        if (ageMinutes > 30) {
            warnings.push({
                type: 'warning',
                title: 'Scan Data May Be Stale',
                description: `Scan was ${Math.floor(ageMinutes)} minutes ago. Market conditions may have changed.`,
                icon: <Clock size={18} className="text-yellow-400" />,
                severity: 'medium'
            });
        }
    }

    // If no warnings, show all-clear message
    if (warnings.length === 0) {
        if (embedded) return null; // Don't show "all clear" in embedded mode to save space
        return (
            <Card className="bg-gradient-to-br from-success/5 via-background to-success/5 border-success/30">
                <CardContent className="p-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-success/20">
                            <Info size={20} className="text-success" />
                        </div>
                        <div>
                            <span className="text-sm font-medium text-foreground">No Major Concerns</span>
                            <p className="text-xs text-muted-foreground">
                                All signals have strong confluence, good R:R, and clean structure.
                            </p>
                        </div>
                    </div>
                </CardContent>
            </Card>
        );
    }

    const highSeverityCount = warnings.filter(w => w.severity === 'high').length;

    // Embedded mode renders a simpler list without the Card wrapper
    if (embedded) {
        return (
            <div className={`space-y-3 ${className}`}>
                {warnings.sort((a, b) => {
                    const severityOrder = { high: 0, medium: 1, low: 2 };
                    return severityOrder[a.severity] - severityOrder[b.severity];
                }).map((warning, idx) => (
                    <div
                        key={idx}
                        className={`p-3 rounded-lg border ${warning.severity === 'high'
                            ? 'bg-warning/10 border-warning/30'
                            : warning.severity === 'medium'
                                ? 'bg-yellow-500/10 border-yellow-500/30'
                                : 'bg-blue-500/10 border-blue-500/30'
                            }`}
                    >
                        <div className="flex items-start gap-3">
                            <div className="mt-0.5">{warning.icon}</div>
                            <div className="flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="text-sm font-medium text-foreground">
                                        {warning.title}
                                    </span>
                                    <Badge
                                        variant="outline"
                                        className={`text-[10px] uppercase ${warning.severity === 'high'
                                            ? 'text-warning border-warning/50'
                                            : warning.severity === 'medium'
                                                ? 'text-yellow-400 border-yellow-400/50'
                                                : 'text-blue-400 border-blue-400/50'
                                            }`}
                                    >
                                        {warning.severity}
                                    </Badge>
                                </div>
                                <p className="text-xs text-muted-foreground">
                                    {warning.description}
                                </p>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        );
    }

    return (
        <Card className={`border overflow-hidden ${highSeverityCount > 0
            ? 'bg-gradient-to-br from-warning/10 via-background to-orange-500/5 border-warning/40'
            : 'bg-gradient-to-br from-yellow-500/5 via-background to-accent/5 border-yellow-500/30'
            } ${className}`}>
            <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
                <CollapsibleTrigger className="w-full">
                    <CardHeader className="cursor-pointer hover:bg-warning/5 transition-colors">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-lg flex items-center gap-3">
                                <div className={`p-2 rounded-lg ${highSeverityCount > 0 ? 'bg-warning/20' : 'bg-yellow-500/20'}`}>
                                    <Warning size={22} weight="fill" className={highSeverityCount > 0 ? 'text-warning' : 'text-yellow-400'} />
                                </div>
                                <div className="text-left">
                                    <span className="text-foreground">Warnings & Context</span>
                                    <p className="text-xs text-muted-foreground font-normal mt-0.5">
                                        {warnings.length} item{warnings.length !== 1 ? 's' : ''} to review before trading
                                    </p>
                                </div>
                            </CardTitle>
                            <div className="flex items-center gap-2">
                                {highSeverityCount > 0 && (
                                    <Badge className="bg-warning/20 text-warning border-warning/50">
                                        {highSeverityCount} high priority
                                    </Badge>
                                )}
                                {isExpanded ? (
                                    <CaretUp size={20} className="text-muted-foreground" />
                                ) : (
                                    <CaretDown size={20} className="text-muted-foreground" />
                                )}
                            </div>
                        </div>
                    </CardHeader>
                </CollapsibleTrigger>

                <CollapsibleContent>
                    <CardContent className="pt-0 animate-in fade-in slide-in-from-top-2 duration-300">
                        <div className="space-y-3">
                            {warnings.sort((a, b) => {
                                const severityOrder = { high: 0, medium: 1, low: 2 };
                                return severityOrder[a.severity] - severityOrder[b.severity];
                            }).map((warning, idx) => (
                                <div
                                    key={idx}
                                    className={`p-3 rounded-lg border ${warning.severity === 'high'
                                        ? 'bg-warning/10 border-warning/30'
                                        : warning.severity === 'medium'
                                            ? 'bg-yellow-500/10 border-yellow-500/30'
                                            : 'bg-blue-500/10 border-blue-500/30'
                                        }`}
                                >
                                    <div className="flex items-start gap-3">
                                        <div className="mt-0.5">{warning.icon}</div>
                                        <div className="flex-1">
                                            <div className="flex items-center gap-2 mb-1">
                                                <span className="text-sm font-medium text-foreground">
                                                    {warning.title}
                                                </span>
                                                <Badge
                                                    variant="outline"
                                                    className={`text-[10px] uppercase ${warning.severity === 'high'
                                                        ? 'text-warning border-warning/50'
                                                        : warning.severity === 'medium'
                                                            ? 'text-yellow-400 border-yellow-400/50'
                                                            : 'text-blue-400 border-blue-400/50'
                                                        }`}
                                                >
                                                    {warning.severity}
                                                </Badge>
                                            </div>
                                            <p className="text-xs text-muted-foreground">
                                                {warning.description}
                                            </p>
                                            {warning.affectedSymbols && warning.affectedSymbols.length > 0 && (
                                                <div className="flex flex-wrap gap-1 mt-2">
                                                    {warning.affectedSymbols.slice(0, 5).map((sym, i) => (
                                                        <Badge
                                                            key={i}
                                                            variant="outline"
                                                            className="text-[10px] font-mono text-muted-foreground"
                                                        >
                                                            {sym}
                                                        </Badge>
                                                    ))}
                                                    {warning.affectedSymbols.length > 5 && (
                                                        <Badge variant="outline" className="text-[10px] text-muted-foreground">
                                                            +{warning.affectedSymbols.length - 5} more
                                                        </Badge>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>

                        <div className="mt-4 pt-3 border-t border-border/30">
                            <p className="text-xs text-muted-foreground">
                                💡 <strong>Tip:</strong> Review high-priority warnings before placing trades.
                                Consider reducing position size for signals with multiple warnings.
                            </p>
                        </div>
                    </CardContent>
                </CollapsibleContent>
            </Collapsible>
        </Card>
    );
}
