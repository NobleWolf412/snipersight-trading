/**
 * RejectionDossier - Tabbed analysis UI for rejected signals
 * 
 * Shows when no signals are generated, with detailed breakdown by rejection category.
 */

import React, { useState } from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import {
    Warning,
    ShieldWarning,
    XCircle,
    Target,
    Lightbulb,
    ChartLineUp,
    TrendDown,
    Info,
    Crosshair,
    Clock,
    ArrowsClockwise,
    CaretDown,
    CaretUp,
    Scales,
    Bug,
    Lightning,
    ShieldCheck
} from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

// Types for rejection data from backend
interface RejectionFactor {
    name: string;
    score: number;
    weight: number;
    weighted_contribution: number;
    rationale: string;
}

interface LowConfluenceRejection {
    symbol: string;
    score: number;
    threshold: number;
    all_factors?: RejectionFactor[];
    top_factors?: string[];
    synergy_bonus?: number;
    conflict_penalty?: number;
}

interface RiskRejection {
    symbol: string;
    reason: string;
    risk_reward?: number;
}

interface NoPlanRejection {
    symbol: string;
    reason: string;
}

interface MissingTFRejection {
    symbol: string;
    missing_timeframes: string[];
    required_timeframes: string[];
}

export interface RejectionSummary {
    low_confluence?: LowConfluenceRejection[];
    risk_validation?: RiskRejection[];
    no_trade_plan?: NoPlanRejection[];
    missing_critical_tf?: MissingTFRejection[];
    errors?: Array<{ symbol: string; reason: string }>;
}

interface RejectionDossierProps {
    rejections: RejectionSummary;
    scanned: number;
    rejected: number;
    mode: string;
}

// Sub-components
const MetricCard = ({ label, value, icon: Icon, color }: { label: string; value: string | number; icon: React.ElementType; color: string }) => (
    <div className="bg-black/40 rounded-lg p-4 border border-white/5">
        <div className={cn("flex items-center gap-2 mb-2", `text-${color}-400`)}>
            <Icon size={18} weight="bold" />
            <span className="text-xs font-bold uppercase tracking-wider">{label}</span>
        </div>
        <div className="text-2xl font-mono font-bold text-white">{value}</div>
    </div>
);

const RejectionCard = ({ symbol, reason, score, icon: Icon = XCircle, iconColor = "red" }: {
    symbol: string;
    reason: string;
    score?: number;
    icon?: React.ElementType;
    iconColor?: string;
}) => (
    <div className="bg-black/40 rounded-lg p-4 border border-white/5 hover:border-white/10 transition-colors">
        <div className="flex items-start justify-between mb-2">
            <div className="flex items-center gap-2">
                <Icon size={16} weight="bold" className={`text-${iconColor}-400`} />
                <span className="font-mono font-bold text-white">{symbol}</span>
            </div>
            {score !== undefined && (
                <span className={cn(
                    "px-2 py-0.5 rounded text-xs font-mono font-bold",
                    score >= 60 ? "bg-yellow-500/20 text-yellow-400" : "bg-red-500/20 text-red-400"
                )}>
                    {score.toFixed(1)}%
                </span>
            )}
        </div>
        <p className="text-xs text-zinc-400 leading-relaxed">{reason}</p>
    </div>
);

// Enhanced Confluence Card with Expandable Factor Details
const ConfluenceDetailCard = ({ rejection }: { rejection: LowConfluenceRejection }) => {
    const [expanded, setExpanded] = useState(false);
    const hasFactors = rejection.all_factors && rejection.all_factors.length > 0;
    const gapToThreshold = rejection.threshold - rejection.score;

    return (
        <div className="bg-black/40 rounded-lg border border-yellow-500/10 hover:border-yellow-500/30 transition-all overflow-hidden">
            {/* Header - Always Visible */}
            <div
                className={cn("p-4 cursor-pointer transition-colors", hasFactors && "hover:bg-yellow-500/5")}
                onClick={() => hasFactors && setExpanded(!expanded)}
            >
                <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-yellow-500/10 flex items-center justify-center">
                            <TrendDown size={16} weight="bold" className="text-yellow-400" />
                        </div>
                        <div>
                            <span className="font-mono font-bold text-white text-lg">{rejection.symbol}</span>
                            <div className="flex items-center gap-2 mt-0.5">
                                <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Gap to threshold:</span>
                                <span className="text-xs font-mono font-bold text-red-400">-{gapToThreshold.toFixed(1)}%</span>
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <div className="text-right">
                            <div className={cn(
                                "px-3 py-1 rounded-lg text-sm font-mono font-bold",
                                rejection.score >= 60 ? "bg-yellow-500/20 text-yellow-400" : "bg-red-500/20 text-red-400"
                            )}>
                                {rejection.score.toFixed(1)}%
                            </div>
                            <div className="text-[10px] text-zinc-500 mt-1">of {rejection.threshold}% required</div>
                        </div>
                        {hasFactors && (
                            <div className="text-zinc-500">
                                {expanded ? <CaretUp size={20} /> : <CaretDown size={20} />}
                            </div>
                        )}
                    </div>
                </div>

                {/* Progress bar */}
                <div className="h-2 bg-black/60 rounded-full overflow-hidden">
                    <div
                        className={cn(
                            "h-full rounded-full transition-all relative",
                            rejection.score >= 60 ? "bg-yellow-500" : "bg-red-500"
                        )}
                        style={{ width: `${Math.min(100, (rejection.score / rejection.threshold) * 100)}%` }}
                    >
                        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
                    </div>
                </div>

                {/* Quick Stats Row */}
                <div className="flex flex-wrap items-center gap-3 mt-3">
                    {rejection.synergy_bonus !== undefined && rejection.synergy_bonus > 0 && (
                        <span className="flex items-center gap-1.5 px-2 py-1 rounded bg-green-500/10 border border-green-500/20">
                            <Lightning size={12} className="text-green-400" />
                            <span className="text-[10px] font-mono text-green-400">+{rejection.synergy_bonus.toFixed(1)} synergy</span>
                        </span>
                    )}
                    {rejection.conflict_penalty !== undefined && rejection.conflict_penalty > 0 && (
                        <span className="flex items-center gap-1.5 px-2 py-1 rounded bg-red-500/10 border border-red-500/20">
                            <Warning size={12} className="text-red-400" />
                            <span className="text-[10px] font-mono text-red-400">-{rejection.conflict_penalty.toFixed(1)} penalty</span>
                        </span>
                    )}
                    {rejection.top_factors && rejection.top_factors.length > 0 && !expanded && (
                        <div className="flex flex-wrap gap-1.5 ml-auto">
                            {rejection.top_factors.slice(0, 2).map((f, j) => (
                                <span key={j} className="px-2 py-0.5 rounded bg-black/60 text-[10px] text-zinc-400 font-mono">
                                    {f}
                                </span>
                            ))}
                            {rejection.top_factors.length > 2 && (
                                <span className="text-[10px] text-zinc-500">+{rejection.top_factors.length - 2} more</span>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* Expanded Factor Details */}
            {expanded && hasFactors && (
                <div className="border-t border-yellow-500/10 bg-black/20 p-4 space-y-2">
                    <div className="flex items-center gap-2 mb-3">
                        <ChartLineUp size={14} className="text-yellow-400" />
                        <span className="text-xs font-bold text-yellow-400 uppercase tracking-widest">Factor Breakdown</span>
                    </div>
                    {rejection.all_factors!
                        .sort((a, b) => b.weighted_contribution - a.weighted_contribution)
                        .map((factor, idx) => (
                            <div key={idx} className="flex items-center gap-3 p-3 bg-black/40 rounded-lg border border-white/5">
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center justify-between mb-1">
                                        <span className="text-sm font-mono font-bold text-white truncate">{factor.name}</span>
                                        <div className="flex items-center gap-2 shrink-0">
                                            <span className="text-[10px] text-zinc-500">w={factor.weight.toFixed(2)}</span>
                                            <span className={cn(
                                                "px-2 py-0.5 rounded text-xs font-mono font-bold",
                                                factor.score >= 70 ? "bg-green-500/20 text-green-400" :
                                                    factor.score >= 40 ? "bg-yellow-500/20 text-yellow-400" :
                                                        "bg-red-500/20 text-red-400"
                                            )}>
                                                {factor.score.toFixed(0)}
                                            </span>
                                        </div>
                                    </div>
                                    {/* Factor progress bar */}
                                    <div className="h-1 bg-black/60 rounded-full overflow-hidden mb-2">
                                        <div
                                            className={cn(
                                                "h-full rounded-full transition-all",
                                                factor.score >= 70 ? "bg-green-500" :
                                                    factor.score >= 40 ? "bg-yellow-500" :
                                                        "bg-red-500"
                                            )}
                                            style={{ width: `${factor.score}%` }}
                                        />
                                    </div>
                                    {factor.rationale && (
                                        <p className="text-[11px] text-zinc-500 leading-relaxed">{factor.rationale}</p>
                                    )}
                                </div>
                            </div>
                        ))}
                </div>
            )}
        </div>
    );
};

// Enhanced Risk Rejection Card with R:R Display
const RiskDetailCard = ({ rejection }: { rejection: RiskRejection }) => {
    return (
        <div className="bg-black/40 rounded-lg p-4 border border-orange-500/10 hover:border-orange-500/30 transition-colors">
            <div className="flex items-start gap-4">
                {/* R:R Badge */}
                {rejection.risk_reward !== undefined && (
                    <div className="shrink-0 w-16 h-16 rounded-xl bg-orange-500/10 border border-orange-500/20 flex flex-col items-center justify-center">
                        <span className="text-lg font-mono font-bold text-orange-400">
                            {rejection.risk_reward.toFixed(1)}
                        </span>
                        <span className="text-[9px] text-orange-400/60 uppercase tracking-wider">R:R</span>
                    </div>
                )}

                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                        <Scales size={16} weight="bold" className="text-orange-400" />
                        <span className="font-mono font-bold text-white text-lg">{rejection.symbol}</span>
                    </div>
                    <p className="text-sm text-zinc-400 leading-relaxed">{rejection.reason}</p>

                    {/* Risk indicators */}
                    <div className="flex flex-wrap gap-2 mt-3">
                        {rejection.risk_reward !== undefined && rejection.risk_reward < 1 && (
                            <span className="flex items-center gap-1 px-2 py-1 rounded bg-red-500/10 border border-red-500/20">
                                <XCircle size={12} className="text-red-400" />
                                <span className="text-[10px] font-mono text-red-400">Below 1:1 R:R</span>
                            </span>
                        )}
                        {rejection.risk_reward !== undefined && rejection.risk_reward >= 1 && rejection.risk_reward < 2 && (
                            <span className="flex items-center gap-1 px-2 py-1 rounded bg-yellow-500/10 border border-yellow-500/20">
                                <Warning size={12} className="text-yellow-400" />
                                <span className="text-[10px] font-mono text-yellow-400">Low R:R ratio</span>
                            </span>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

// Enhanced Structure Rejection Card
const StructureDetailCard = ({ rejection }: { rejection: NoPlanRejection }) => {
    // Parse the reason to detect common issues
    const hasNoOB = rejection.reason.toLowerCase().includes('order block') || rejection.reason.toLowerCase().includes('ob');
    const hasNoFVG = rejection.reason.toLowerCase().includes('fvg') || rejection.reason.toLowerCase().includes('fair value');
    const hasNoEntry = rejection.reason.toLowerCase().includes('entry');
    const hasATRIssue = rejection.reason.toLowerCase().includes('atr') || rejection.reason.toLowerCase().includes('fallback');

    return (
        <div className="bg-black/40 rounded-lg p-4 border border-red-500/10 hover:border-red-500/30 transition-colors">
            <div className="flex items-start gap-3 mb-3">
                <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center shrink-0">
                    <Target size={16} weight="bold" className="text-red-400" />
                </div>
                <div>
                    <span className="font-mono font-bold text-white text-lg">{rejection.symbol}</span>
                    <p className="text-sm text-zinc-400 leading-relaxed mt-1">{rejection.reason}</p>
                </div>
            </div>

            {/* Issue Tags */}
            <div className="flex flex-wrap gap-2 ml-11">
                {hasNoOB && (
                    <span className="px-2 py-1 rounded bg-red-500/10 border border-red-500/20 text-[10px] font-mono text-red-400">
                        No Valid OB
                    </span>
                )}
                {hasNoFVG && (
                    <span className="px-2 py-1 rounded bg-red-500/10 border border-red-500/20 text-[10px] font-mono text-red-400">
                        No FVG Found
                    </span>
                )}
                {hasNoEntry && (
                    <span className="px-2 py-1 rounded bg-red-500/10 border border-red-500/20 text-[10px] font-mono text-red-400">
                        Entry Zone Invalid
                    </span>
                )}
                {hasATRIssue && (
                    <span className="px-2 py-1 rounded bg-orange-500/10 border border-orange-500/20 text-[10px] font-mono text-orange-400">
                        ATR Fallback Required
                    </span>
                )}
            </div>
        </div>
    );
};

export function RejectionDossier({ rejections, scanned, rejected, mode }: RejectionDossierProps) {
    const [activeTab, setActiveTab] = useState('summary');

    // Categorize rejections
    const lowConfluence = rejections.low_confluence || [];
    const riskIssues = rejections.risk_validation || [];
    const noPlan = rejections.no_trade_plan || [];
    const missingTF = rejections.missing_critical_tf || [];
    const errors = rejections.errors || [];

    // Calculate category counts
    const categoryStats = {
        confluence: lowConfluence.length,
        risk: riskIssues.length,
        structure: noPlan.length,
        timeframes: missingTF.length,
        errors: errors.length,
    };

    const totalCategorized = Object.values(categoryStats).reduce((a, b) => a + b, 0);

    return (
        <div className="min-h-full flex flex-col glass-card relative">
            {/* Hero Header - Warning Theme */}
            <div className="p-4 md:p-6 border-b border-yellow-500/20 bg-gradient-to-r from-yellow-500/10 via-orange-500/5 to-transparent relative overflow-hidden">
                {/* Subtle animated scan line */}
                <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-30">
                    <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-yellow-500 to-transparent animate-scan-line" />
                </div>

                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 relative z-10">
                    <div className="flex items-center gap-4">
                        <div className="w-14 h-14 rounded-xl bg-yellow-500/10 border border-yellow-500/30 flex items-center justify-center text-yellow-500 shadow-[0_0_20px_rgba(234,179,8,0.2)]">
                            <ShieldWarning size={32} weight="fill" />
                        </div>
                        <div>
                            <div className="flex items-center gap-3 mb-1">
                                <h1 className="text-xl md:text-2xl font-bold text-white font-mono tracking-tight">REJECTION ANALYSIS</h1>
                            </div>
                            <div className="flex items-center gap-4 text-sm text-muted-foreground font-mono">
                                <span><span className="text-yellow-400 font-bold">{rejected}</span>/{scanned} filtered</span>
                                <span className="w-px h-3 bg-white/20" />
                                <span className="text-zinc-500">{mode.toUpperCase()} mode</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Tabs Container */}
            <div className="flex-1 overflow-hidden flex flex-col">
                <Tabs.Root value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
                    {/* Tab Navigation */}
                    <div className="px-4 md:px-6 pt-4 pb-3 border-b border-yellow-500/20 bg-black/40">
                        <Tabs.List className="flex flex-wrap gap-2">
                            <Tabs.Trigger value="summary" className="tab-trigger flex items-center gap-2">
                                <ChartLineUp size={16} weight="bold" /> SUMMARY
                            </Tabs.Trigger>
                            <Tabs.Trigger value="confluence" className="tab-trigger flex items-center gap-2">
                                <TrendDown size={16} weight="bold" />
                                CONFLUENCE
                                {categoryStats.confluence > 0 && (
                                    <span className="px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400 text-[10px] font-bold">{categoryStats.confluence}</span>
                                )}
                            </Tabs.Trigger>
                            <Tabs.Trigger value="risk" className="tab-trigger flex items-center gap-2">
                                <XCircle size={16} weight="bold" />
                                RISK/RR
                                {categoryStats.risk > 0 && (
                                    <span className="px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-400 text-[10px] font-bold">{categoryStats.risk}</span>
                                )}
                            </Tabs.Trigger>
                            <Tabs.Trigger value="structure" className="tab-trigger flex items-center gap-2">
                                <Target size={16} weight="bold" />
                                STRUCTURE
                                {categoryStats.structure > 0 && (
                                    <span className="px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 text-[10px] font-bold">{categoryStats.structure}</span>
                                )}
                            </Tabs.Trigger>
                            <Tabs.Trigger value="suggestions" className="tab-trigger flex items-center gap-2">
                                <Lightbulb size={16} weight="bold" /> SUGGESTIONS
                            </Tabs.Trigger>
                            {categoryStats.errors > 0 && (
                                <Tabs.Trigger value="errors" className="tab-trigger flex items-center gap-2">
                                    <Bug size={16} weight="bold" />
                                    ERRORS
                                    <span className="px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 text-[10px] font-bold">{categoryStats.errors}</span>
                                </Tabs.Trigger>
                            )}
                        </Tabs.List>
                    </div>

                    {/* Tab Content - Scrollable */}
                    <div className="flex-1 overflow-y-auto p-4 md:p-6 scrollbar-thin scrollbar-thumb-yellow-500/20 scrollbar-track-transparent">

                        {/* ================================================================ */}
                        {/* TAB: SUMMARY */}
                        {/* ================================================================ */}
                        <Tabs.Content value="summary" className="mt-0 space-y-6 animate-in fade-in duration-200">
                            {/* Metrics Grid */}
                            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                                <MetricCard label="Scanned" value={scanned} icon={Crosshair} color="zinc" />
                                <MetricCard label="Rejected" value={rejected} icon={XCircle} color="red" />
                                <MetricCard label="Pass Rate" value={`${scanned > 0 ? ((scanned - rejected) / scanned * 100).toFixed(0) : 0}%`} icon={ChartLineUp} color="yellow" />
                                <MetricCard label="Mode" value={mode.toUpperCase()} icon={Target} color="cyan" />
                            </div>

                            {/* Breakdown by Category */}
                            <div className="space-y-3">
                                <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest flex items-center gap-2">
                                    <div className="w-8 h-px bg-zinc-700" />
                                    Rejection Breakdown
                                </h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    {categoryStats.confluence > 0 && (
                                        <div className="bg-yellow-500/5 border border-yellow-500/20 rounded-lg p-4 flex items-center gap-4">
                                            <div className="w-12 h-12 rounded-lg bg-yellow-500/10 flex items-center justify-center text-yellow-500">
                                                <TrendDown size={24} weight="bold" />
                                            </div>
                                            <div>
                                                <div className="text-2xl font-mono font-bold text-white">{categoryStats.confluence}</div>
                                                <div className="text-xs text-zinc-400">Low Confluence</div>
                                            </div>
                                        </div>
                                    )}
                                    {categoryStats.risk > 0 && (
                                        <div className="bg-orange-500/5 border border-orange-500/20 rounded-lg p-4 flex items-center gap-4">
                                            <div className="w-12 h-12 rounded-lg bg-orange-500/10 flex items-center justify-center text-orange-500">
                                                <XCircle size={24} weight="bold" />
                                            </div>
                                            <div>
                                                <div className="text-2xl font-mono font-bold text-white">{categoryStats.risk}</div>
                                                <div className="text-xs text-zinc-400">Risk/RR Issues</div>
                                            </div>
                                        </div>
                                    )}
                                    {categoryStats.structure > 0 && (
                                        <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-4 flex items-center gap-4">
                                            <div className="w-12 h-12 rounded-lg bg-red-500/10 flex items-center justify-center text-red-500">
                                                <Target size={24} weight="bold" />
                                            </div>
                                            <div>
                                                <div className="text-2xl font-mono font-bold text-white">{categoryStats.structure}</div>
                                                <div className="text-xs text-zinc-400">No Valid Structure</div>
                                            </div>
                                        </div>
                                    )}
                                    {categoryStats.timeframes > 0 && (
                                        <div className="bg-purple-500/5 border border-purple-500/20 rounded-lg p-4 flex items-center gap-4">
                                            <div className="w-12 h-12 rounded-lg bg-purple-500/10 flex items-center justify-center text-purple-500">
                                                <Clock size={24} weight="bold" />
                                            </div>
                                            <div>
                                                <div className="text-2xl font-mono font-bold text-white">{categoryStats.timeframes}</div>
                                                <div className="text-xs text-zinc-400">Missing Timeframes</div>
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {totalCategorized === 0 && (
                                    <div className="bg-black/40 rounded-lg p-6 border border-white/5 text-center">
                                        <Info size={32} className="mx-auto mb-3 text-zinc-600" />
                                        <p className="text-sm text-zinc-500">No detailed rejection data available.</p>
                                        <p className="text-xs text-zinc-600 mt-1">Try running a fresh scan to see breakdown.</p>
                                    </div>
                                )}
                            </div>
                        </Tabs.Content>

                        {/* ================================================================ */}
                        {/* TAB: LOW CONFLUENCE */}
                        {/* ================================================================ */}
                        <Tabs.Content value="confluence" className="mt-0 space-y-4 animate-in fade-in duration-200">
                            <div className="bg-yellow-500/5 border border-yellow-500/20 rounded-lg p-4 mb-4">
                                <div className="flex items-start gap-3">
                                    <Info size={18} className="text-yellow-400 mt-0.5 shrink-0" />
                                    <p className="text-sm text-zinc-400">
                                        These symbols didn't meet the confidence threshold. Multiple factors need to align:
                                        SMC patterns, HTF structure, volume profile, and momentum indicators.
                                    </p>
                                </div>
                            </div>

                            {lowConfluence.length === 0 ? (
                                <div className="bg-black/40 rounded-lg p-8 border border-white/5 text-center">
                                    <TrendDown size={40} className="mx-auto mb-3 text-zinc-700" />
                                    <p className="text-sm text-zinc-500">No low confluence rejections</p>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {lowConfluence.map((rej, i) => (
                                        <ConfluenceDetailCard key={i} rejection={rej} />
                                    ))}
                                </div>
                            )}
                        </Tabs.Content>

                        {/* ================================================================ */}
                        {/* TAB: RISK/RR ISSUES */}
                        {/* ================================================================ */}
                        <Tabs.Content value="risk" className="mt-0 space-y-4 animate-in fade-in duration-200">
                            <div className="bg-orange-500/5 border border-orange-500/20 rounded-lg p-4 mb-4">
                                <div className="flex items-start gap-3">
                                    <Info size={18} className="text-orange-400 mt-0.5 shrink-0" />
                                    <p className="text-sm text-zinc-400">
                                        These passed confluence but failed risk checks. Entry zones may have collapsed,
                                        R:R ratio was too low, or stop distance exceeded safe limits.
                                    </p>
                                </div>
                            </div>

                            {riskIssues.length === 0 ? (
                                <div className="bg-black/40 rounded-lg p-8 border border-white/5 text-center">
                                    <XCircle size={40} className="mx-auto mb-3 text-zinc-700" />
                                    <p className="text-sm text-zinc-500">No risk validation failures</p>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {riskIssues.map((rej, i) => (
                                        <RiskDetailCard key={i} rejection={rej} />
                                    ))}
                                </div>
                            )}
                        </Tabs.Content>

                        {/* ================================================================ */}
                        {/* TAB: STRUCTURE */}
                        {/* ================================================================ */}
                        <Tabs.Content value="structure" className="mt-0 space-y-4 animate-in fade-in duration-200">
                            <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-4 mb-4">
                                <div className="flex items-start gap-3">
                                    <Info size={18} className="text-red-400 mt-0.5 shrink-0" />
                                    <p className="text-sm text-zinc-400">
                                        No valid trade plan could be generated. This usually means no Order Blocks, FVGs,
                                        or valid entry zones were found within acceptable distance from current price.
                                    </p>
                                </div>
                            </div>

                            {noPlan.length === 0 && missingTF.length === 0 ? (
                                <div className="bg-black/40 rounded-lg p-8 border border-white/5 text-center">
                                    <Target size={40} className="mx-auto mb-3 text-zinc-700" />
                                    <p className="text-sm text-zinc-500">No structure-related rejections</p>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {/* No Trade Plan Section */}
                                    {noPlan.length > 0 && (
                                        <div className="space-y-3">
                                            <h4 className="text-xs font-bold text-red-400 uppercase tracking-widest flex items-center gap-2">
                                                <Target size={14} />
                                                No Valid Entry ({noPlan.length} symbols)
                                            </h4>
                                            <div className="space-y-3">
                                                {noPlan.map((rej, i) => (
                                                    <StructureDetailCard key={i} rejection={rej} />
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Missing Timeframes Section */}
                                    {missingTF.length > 0 && (
                                        <div className="space-y-3">
                                            <h4 className="text-xs font-bold text-purple-400 uppercase tracking-widest">Missing Critical Timeframes</h4>
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                                {missingTF.map((rej, i) => (
                                                    <div key={i} className="bg-black/40 rounded-lg p-4 border border-purple-500/10">
                                                        <div className="flex items-center gap-2 mb-2">
                                                            <Clock size={16} className="text-purple-400" />
                                                            <span className="font-mono font-bold text-white">{rej.symbol}</span>
                                                        </div>
                                                        <div className="flex flex-wrap gap-1.5">
                                                            {rej.missing_timeframes.map((tf, j) => (
                                                                <span key={j} className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-400 text-[10px] font-mono font-bold">
                                                                    {tf}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </Tabs.Content>

                        {/* ================================================================ */}
                        {/* TAB: SUGGESTIONS */}
                        {/* ================================================================ */}
                        <Tabs.Content value="suggestions" className="mt-0 space-y-4 animate-in fade-in duration-200">
                            <div className="bg-accent/5 border border-accent/20 rounded-lg p-6">
                                <h3 className="text-sm font-bold text-accent uppercase tracking-widest mb-4 flex items-center gap-2">
                                    <Lightbulb size={18} weight="fill" />
                                    Recommendations
                                </h3>

                                <div className="space-y-4">
                                    {/* Dynamic suggestions based on rejection patterns */}
                                    {categoryStats.confluence > categoryStats.risk + categoryStats.structure && (
                                        <div className="flex items-start gap-3 p-3 bg-black/40 rounded-lg border border-white/5">
                                            <div className="w-8 h-8 rounded-lg bg-yellow-500/10 flex items-center justify-center text-yellow-400 shrink-0">
                                                <TrendDown size={16} weight="bold" />
                                            </div>
                                            <div>
                                                <h4 className="text-sm font-bold text-white mb-1">Lower Confluence Threshold</h4>
                                                <p className="text-xs text-zinc-400">
                                                    Most rejections are confluence-based. Try <span className="text-accent font-mono">Recon</span> mode
                                                    for lower thresholds, or wait for clearer market structure.
                                                </p>
                                            </div>
                                        </div>
                                    )}

                                    {categoryStats.structure > 0 && (
                                        <div className="flex items-start gap-3 p-3 bg-black/40 rounded-lg border border-white/5">
                                            <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center text-red-400 shrink-0">
                                                <Target size={16} weight="bold" />
                                            </div>
                                            <div>
                                                <h4 className="text-sm font-bold text-white mb-1">Structure Not Forming</h4>
                                                <p className="text-xs text-zinc-400">
                                                    Market may be ranging or consolidating. Wait for HTF breakouts or try
                                                    <span className="text-accent font-mono"> Strike</span> mode for intraday LTF structures.
                                                </p>
                                            </div>
                                        </div>
                                    )}

                                    <div className="flex items-start gap-3 p-3 bg-black/40 rounded-lg border border-white/5">
                                        <div className="w-8 h-8 rounded-lg bg-cyan-500/10 flex items-center justify-center text-cyan-400 shrink-0">
                                            <ArrowsClockwise size={16} weight="bold" />
                                        </div>
                                        <div>
                                            <h4 className="text-sm font-bold text-white mb-1">Try Different Mode</h4>
                                            <p className="text-xs text-zinc-400">
                                                Each mode has different thresholds. <span className="text-accent font-mono">Stealth</span> balances quality/quantity.
                                                <span className="text-accent font-mono"> Overwatch</span> is strictest for HTF swings.
                                            </p>
                                        </div>
                                    </div>

                                    <div className="flex items-start gap-3 p-3 bg-black/40 rounded-lg border border-white/5">
                                        <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center text-accent shrink-0">
                                            <Clock size={16} weight="bold" />
                                        </div>
                                        <div>
                                            <h4 className="text-sm font-bold text-white mb-1">Timing Matters</h4>
                                            <p className="text-xs text-zinc-400">
                                                Best signals form during high-volatility sessions (US/London open).
                                                Weekend and low-volume periods often show fewer valid setups.
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </Tabs.Content>

                        {/* ================================================================ */}
                        {/* TAB: ERRORS */}
                        {/* ================================================================ */}
                        {errors.length > 0 && (
                            <Tabs.Content value="errors" className="mt-0 space-y-4 animate-in fade-in duration-200">
                                <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-4 mb-4">
                                    <div className="flex items-start gap-3">
                                        <Bug size={18} className="text-red-400 mt-0.5 shrink-0" />
                                        <p className="text-sm text-zinc-400">
                                            These symbols encountered processing errors during the scan. This may be due to
                                            data issues, API timeouts, or internal processing failures.
                                        </p>
                                    </div>
                                </div>

                                <div className="space-y-3">
                                    {errors.map((err, i) => (
                                        <div key={i} className="bg-black/40 rounded-lg p-4 border border-red-500/10 hover:border-red-500/30 transition-colors">
                                            <div className="flex items-start gap-3">
                                                <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center shrink-0">
                                                    <Bug size={16} weight="bold" className="text-red-400" />
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <span className="font-mono font-bold text-white text-lg">{err.symbol}</span>
                                                    <p className="text-sm text-red-400/80 leading-relaxed mt-1 font-mono bg-red-500/5 p-2 rounded border border-red-500/10">
                                                        {err.reason}
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </Tabs.Content>
                        )}

                    </div>
                </Tabs.Root>
            </div>
        </div>
    );
}

export default RejectionDossier;
