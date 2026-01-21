import { useState } from 'react';
import { XCircle, WarningCircle, Prohibit, Bug, CaretDown, Pulse, Copy, Check } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

export interface RejectionInfo {
    symbol: string;
    reason_type: 'low_confluence' | 'no_data' | 'missing_critical_tf' | 'risk_validation' | 'no_trade_plan' | 'cooldown_active' | 'errors';
    reason: string;
    trace_id?: string;
    // Confluence-specific fields
    score?: number;
    threshold?: number;
    all_factors?: Array<{
        name: string;
        score: number;
        weight: number;
        weighted_contribution: number;
        rationale?: string;
    }>;
    synergy_bonus?: number;
    conflict_penalty?: number;
    // Dual-direction fields (for tied scores)
    bullish_score?: number;
    bearish_score?: number;
    gap?: number;
    bullish_factors?: Array<{
        name: string;
        score: number;
        weight: number;
        weighted_contribution: number;
        rationale?: string;
    }>;
    bearish_factors?: Array<{
        name: string;
        score: number;
        weight: number;
        weighted_contribution: number;
        rationale?: string;
    }>;
    bullish_synergy?: number;
    bullish_conflict?: number;
    bearish_synergy?: number;
    bearish_conflict?: number;
    // Other rejection-specific fields
    missing_timeframes?: string[];
    required_timeframes?: string[];
    [key: string]: any;
}

interface RejectionCardProps {
    rejection: RejectionInfo;
}

const REASON_CONFIG = {
    low_confluence: { icon: WarningCircle, color: 'text-amber-400', border: 'border-amber-500/20', bg: 'bg-amber-500/10', glow: 'hover:shadow-[0_0_15px_rgba(251,191,36,0.15)] hover:border-amber-500/40' },
    no_data: { icon: Prohibit, color: 'text-zinc-400', border: 'border-zinc-500/20', bg: 'bg-zinc-500/10', glow: 'hover:shadow-[0_0_15px_rgba(113,113,122,0.15)] hover:border-zinc-500/40' },
    missing_critical_tf: { icon: Prohibit, color: 'text-orange-400', border: 'border-orange-500/20', bg: 'bg-orange-500/10', glow: 'hover:shadow-[0_0_15px_rgba(251,146,60,0.15)] hover:border-orange-500/40' },
    risk_validation: { icon: XCircle, color: 'text-red-400', border: 'border-red-500/20', bg: 'bg-red-500/10', glow: 'hover:shadow-[0_0_15px_rgba(248,113,113,0.15)] hover:border-red-500/40' },
    no_trade_plan: { icon: XCircle, color: 'text-zinc-400', border: 'border-zinc-500/20', bg: 'bg-zinc-500/10', glow: 'hover:shadow-[0_0_15px_rgba(161,161,170,0.15)] hover:border-zinc-500/40' },
    cooldown_active: { icon: Prohibit, color: 'text-blue-400', border: 'border-blue-500/20', bg: 'bg-blue-500/10', glow: 'hover:shadow-[0_0_15px_rgba(96,165,250,0.15)] hover:border-blue-500/40' },
    errors: { icon: Bug, color: 'text-pink-400', border: 'border-pink-500/20', bg: 'bg-pink-500/10', glow: 'hover:shadow-[0_0_15px_rgba(244,114,182,0.15)] hover:border-pink-500/40' },
};

export function RejectionCard({ rejection }: RejectionCardProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [showDebug, setShowDebug] = useState(false);
    const [copied, setCopied] = useState(false);
    const config = REASON_CONFIG[rejection.reason_type] || REASON_CONFIG.errors;
    const Icon = config.icon;

    const hasDetails =
        (rejection.reason_type === 'low_confluence' && (rejection.all_factors?.length || (rejection.bullish_factors?.length && rejection.bearish_factors?.length))) ||
        (rejection.reason_type === 'missing_critical_tf' && rejection.missing_timeframes?.length) ||
        rejection.trace_id ||
        Object.keys(rejection).length > 4; // Has extra metadata

    const toggleExpand = () => {
        if (hasDetails) {
            setIsExpanded(!isExpanded);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            toggleExpand();
        }
    };

    const copyToClipboard = async () => {
        const data = JSON.stringify(rejection, null, 2);
        try {
            await navigator.clipboard.writeText(data);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error('Failed to copy:', err);
        }
    };

    return (
        <div
            className={cn(
                "w-full p-6 mb-4 bg-[#0a0f0a] border border-zinc-800/60 rounded-xl transition-all duration-300",
                config.glow,
                hasDetails && "cursor-pointer hover:border-zinc-700/80"
            )}
            onClick={toggleExpand}
            onKeyDown={handleKeyDown}
            tabIndex={hasDetails ? 0 : undefined}
            role={hasDetails ? "button" : undefined}
            aria-expanded={isExpanded}
        >
            <div className="flex items-start gap-6">
                <div className={cn("flex items-center justify-center w-12 h-12 rounded-xl border flex-shrink-0", config.bg, config.border, config.color)}>
                    <Icon size={28} weight="bold" />
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-xl font-bold tracking-tight text-zinc-200">{rejection.symbol}</span>
                        <div className="flex items-center gap-2">
                            <span className={cn("text-xs font-mono uppercase px-2 py-1 rounded border", config.bg, config.border, config.color)}>
                                {rejection.reason_type.replace(/_/g, ' ')}
                            </span>
                            {hasDetails && (
                                <CaretDown
                                    size={16}
                                    className={cn(
                                        "transition-transform duration-200 text-zinc-500",
                                        isExpanded && "rotate-180"
                                    )}
                                />
                            )}
                        </div>
                    </div>

                    <p className="text-zinc-400 text-lg leading-relaxed font-mono">
                        {rejection.reason}
                    </p>

                    {/* Expanded Details with Animation */}
                    <div
                        className={cn(
                            "grid transition-all duration-300 overflow-hidden",
                            isExpanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
                        )}
                    >
                        <div className="min-h-0">
                            {isExpanded && hasDetails && (
                                <div className="mt-6 pt-6 border-t border-zinc-800/60 space-y-4" onClick={(e) => e.stopPropagation()}>
                                    {/* Type-specific breakdowns */}
                                    {rejection.reason_type === 'low_confluence' && rejection.bullish_factors && rejection.bearish_factors ? (
                                        <DualDirectionBreakdown rejection={rejection} config={config} />
                                    ) : rejection.reason_type === 'low_confluence' ? (
                                        <ConfluenceBreakdown rejection={rejection} config={config} />
                                    ) : null}
                                    {rejection.reason_type === 'missing_critical_tf' && (
                                        <TimeframeBreakdown rejection={rejection} />
                                    )}
                                    {rejection.reason_type === 'risk_validation' && (
                                        <GenericBreakdown rejection={rejection} title="Risk Validation Details" />
                                    )}
                                    {rejection.reason_type === 'no_trade_plan' && (
                                        <GenericBreakdown rejection={rejection} title="Trade Plan Validation" />
                                    )}
                                    {rejection.reason_type === 'errors' && (
                                        <GenericBreakdown rejection={rejection} title="Error Details" />
                                    )}

                                    {/* Debug Mode Toggle & Actions */}
                                    <div className="flex items-center justify-between pt-4 border-t border-zinc-800/40">
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setShowDebug(!showDebug);
                                            }}
                                            className="text-xs font-mono text-zinc-500 hover:text-zinc-300 transition-colors"
                                        >
                                            {showDebug ? '▼ Hide' : '▶'} Debug Info
                                        </button>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                copyToClipboard();
                                            }}
                                            className={cn(
                                                "flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-mono transition-all",
                                                copied
                                                    ? "bg-green-500/10 border-green-500/30 text-green-400"
                                                    : "bg-zinc-800/50 border-zinc-700/50 text-zinc-400 hover:bg-zinc-700/50 hover:border-zinc-600"
                                            )}
                                        >
                                            {copied ? (
                                                <>
                                                    <Check size={14} weight="bold" />
                                                    Copied!
                                                </>
                                            ) : (
                                                <>
                                                    <Copy size={14} />
                                                    Copy JSON
                                                </>
                                            )}
                                        </button>
                                    </div>

                                    {/* Debug Info */}
                                    {showDebug && (
                                        <div className="bg-black/40 rounded-lg p-4 border border-zinc-800/60">
                                            <div className="text-xs font-mono text-zinc-500 mb-2">DEBUG METADATA</div>
                                            {rejection.trace_id && (
                                                <div className="mb-2">
                                                    <span className="text-zinc-600">Trace ID:</span>{' '}
                                                    <span className="text-zinc-400">{rejection.trace_id}</span>
                                                </div>
                                            )}
                                            <div className="max-h-48 overflow-y-auto">
                                                <pre className="text-xs text-zinc-400 whitespace-pre-wrap break-all">
                                                    {JSON.stringify(rejection, null, 2)}
                                                </pre>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>

                    {rejection.trace_id && !isExpanded && (
                        <div className="mt-3 text-xs text-zinc-600 font-mono">
                            Trace ID: {rejection.trace_id}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function ConfluenceBreakdown({ rejection, config }: { rejection: RejectionInfo; config: typeof REASON_CONFIG[keyof typeof REASON_CONFIG] }) {
    const score = rejection.score || 0;
    const threshold = rejection.threshold || 60;
    const percentage = (score / threshold) * 100;

    return (
        <div className="space-y-4">
            {/* Score Progress */}
            <div>
                <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-mono text-zinc-400 uppercase tracking-wider">Confluence Score</span>
                    <span className="text-sm font-mono text-zinc-300">
                        {score.toFixed(1)} / {threshold.toFixed(1)}
                    </span>
                </div>
                <div className="h-2 bg-zinc-900 rounded-full overflow-hidden">
                    <div
                        className={cn("h-full transition-all duration-500", config.bg)}
                        style={{ width: `${Math.min(percentage, 100)}%` }}
                    />
                </div>
            </div>

            {/* Factor Breakdown Table */}
            {rejection.all_factors && rejection.all_factors.length > 0 && (
                <div>
                    <div className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                        <Pulse size={12} weight="fill" />
                        Factor Breakdown
                    </div>
                    <div className="bg-zinc-900/50 rounded-lg border border-zinc-800/40 overflow-hidden">
                        <div className="max-h-64 overflow-y-auto">
                            {rejection.all_factors.map((factor, idx) => (
                                <div
                                    key={idx}
                                    className={cn(
                                        "px-4 py-3 border-b border-zinc-800/40 last:border-0 hover:bg-zinc-800/30 transition-colors",
                                        "grid grid-cols-[1fr_auto_auto_auto] gap-4 items-center"
                                    )}
                                >
                                    <div className="min-w-0">
                                        <div className="text-sm font-mono text-zinc-200 truncate">{factor.name}</div>
                                        {factor.rationale && (
                                            <div className="text-xs text-zinc-500 mt-1 truncate" title={factor.rationale}>
                                                {factor.rationale}
                                            </div>
                                        )}
                                    </div>
                                    <div className="text-xs font-mono text-zinc-400 text-right">
                                        {factor.score.toFixed(1)}
                                    </div>
                                    <div className="text-xs font-mono text-zinc-500 text-right">
                                        ×{factor.weight.toFixed(2)}
                                    </div>
                                    <div className="text-xs font-mono text-zinc-300 font-bold text-right">
                                        ={factor.weighted_contribution.toFixed(1)}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            {/* Adjustments */}
            {(rejection.synergy_bonus !== undefined || rejection.conflict_penalty !== undefined) && (
                <div className="grid grid-cols-2 gap-3">
                    {rejection.synergy_bonus !== undefined && rejection.synergy_bonus !== 0 && (
                        <div className="px-3 py-2 rounded-lg border border-green-500/20 bg-green-500/5">
                            <div className="text-xs text-green-400/70 uppercase tracking-wider">Synergy Bonus</div>
                            <div className="text-lg font-mono text-green-400 font-bold">+{rejection.synergy_bonus.toFixed(1)}</div>
                        </div>
                    )}
                    {rejection.conflict_penalty !== undefined && rejection.conflict_penalty !== 0 && (
                        <div className="px-3 py-2 rounded-lg border border-red-500/20 bg-red-500/5">
                            <div className="text-xs text-red-400/70 uppercase tracking-wider">Conflict Penalty</div>
                            <div className="text-lg font-mono text-red-400 font-bold">-{rejection.conflict_penalty.toFixed(1)}</div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

function TimeframeBreakdown({ rejection }: { rejection: RejectionInfo }) {
    return (
        <div>
            <div className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-3">Missing Timeframes</div>
            <div className="flex flex-wrap gap-2">
                {rejection.missing_timeframes?.map((tf, idx) => (
                    <span key={idx} className="px-2 py-1 bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-mono rounded">
                        {tf}
                    </span>
                ))}
            </div>
            {rejection.required_timeframes && (
                <div className="mt-3">
                    <div className="text-xs font-mono text-zinc-600 mb-2">Required:</div>
                    <div className="flex flex-wrap gap-2">
                        {rejection.required_timeframes.map((tf, idx) => (
                            <span key={idx} className="px-2 py-1 bg-zinc-800/50 border border-zinc-700/50 text-zinc-400 text-xs font-mono rounded">
                                {tf}
                            </span>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

function GenericBreakdown({ rejection, title }: { rejection: RejectionInfo; title: string }) {
    // Extract relevant metadata (exclude standard fields)
    const excludeKeys = ['symbol', 'reason_type', 'reason', 'trace_id'];
    const metadata = Object.entries(rejection)
        .filter(([key]) => !excludeKeys.includes(key))
        .filter(([, value]) => value !== undefined && value !== null);

    if (metadata.length === 0) {
        return null;
    }

    return (
        <div>
            <div className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-3">{title}</div>
            <div className="bg-zinc-900/50 rounded-lg border border-zinc-800/40 p-4 space-y-2">
                {metadata.map(([key, value]) => (
                    <div key={key} className="flex justify-between items-start gap-4">
                        <span className="text-xs font-mono text-zinc-400 capitalize">
                            {key.replace(/_/g, ' ')}:
                        </span>
                        <span className="text-xs font-mono text-zinc-200 text-right max-w-xs break-all">
                            {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}

function DualDirectionBreakdown({ rejection, config }: { rejection: RejectionInfo; config: typeof REASON_CONFIG[keyof typeof REASON_CONFIG] }) {
    const bullishScore = rejection.bullish_score || 0;
    const bearishScore = rejection.bearish_score || 0;
    const gap = rejection.gap || 0;
    const threshold = rejection.threshold || 60;

    return (
        <div className="space-y-4">
            {/* Header: Gap Warning */}
            <div className="flex items-center justify-between p-4 bg-amber-500/5 border border-amber-500/30 rounded-lg">
                <div>
                    <div className="text-sm font-mono text-amber-400 font-bold uppercase tracking-wider">Conflicted Market</div>
                    <div className="text-xs text-amber-400/70 mt-1">Bullish and bearish scores too close to call</div>
                </div>
                <div className="text-right">
                    <div className="text-2xl font-mono font-bold text-amber-400">{gap.toFixed(1)}pts</div>
                    <div className="text-xs text-amber-400/70">gap (need 8pts)</div>
                </div>
            </div>

            {/* Side-by-Side Score Comparison */}
            <div className="grid grid-cols-2 gap-4">
                {/* Bullish Column */}
                <div className="space-y-3">
                    <div className="flex items-center justify-between">
                        <span className="text-sm font-mono text-green-400 uppercase tracking-wider font-bold">Bullish</span>
                        <span className="text-sm font-mono text-green-400">{bullishScore.toFixed(1)} / {threshold.toFixed(1)}</span>
                    </div>
                    <div className="h-2 bg-zinc-900 rounded-full overflow-hidden">
                        <div
                            className="h-full transition-all duration-500 bg-green-500/30"
                            style={{ width: `${Math.min((bullishScore / threshold) * 100, 100)}%` }}
                        />
                    </div>

                    {/* Bullish Factors */}
                    {rejection.bullish_factors && rejection.bullish_factors.length > 0 && (
                        <div className="bg-green-500/5 border border-green-500/20 rounded-lg p-3 space-y-2 max-h-48 overflow-y-auto">
                            {rejection.bullish_factors.slice(0, 5).map((factor, idx) => (
                                <div key={idx} className="text-xs">
                                    <div className="flex justify-between items-center">
                                        <span className="text-green-300 font-mono truncate flex-1">{factor.name}</span>
                                        <span className="text-green-400 font-mono font-bold ml-2">{factor.weighted_contribution.toFixed(1)}</span>
                                    </div>
                                    {factor.rationale && (
                                        <div className="text-green-400/50 mt-0.5 truncate" title={factor.rationale}>
                                            {factor.rationale}
                                        </div>
                                    )}
                                </div>
                            ))}
                            {rejection.bullish_factors.length > 5 && (
                                <div className="text-xs text-green-400/50 italic">
                                    +{rejection.bullish_factors.length - 5} more factors...
                                </div>
                            )}
                        </div>
                    )}

                    {/* Bullish Adjustments */}
                    {(rejection.bullish_synergy !== undefined || rejection.bullish_conflict !== undefined) && (
                        <div className="space-y-1">
                            {rejection.bullish_synergy !== undefined && rejection.bullish_synergy !== 0 && (
                                <div className="flex justify-between text-xs">
                                    <span className="text-green-400/70">Synergy:</span>
                                    <span className="text-green-400 font-mono">+{rejection.bullish_synergy.toFixed(1)}</span>
                                </div>
                            )}
                            {rejection.bullish_conflict !== undefined && rejection.bullish_conflict !== 0 && (
                                <div className="flex justify-between text-xs">
                                    <span className="text-red-400/70">Conflict:</span>
                                    <span className="text-red-400 font-mono">-{rejection.bullish_conflict.toFixed(1)}</span>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Bearish Column */}
                <div className="space-y-3">
                    <div className="flex items-center justify-between">
                        <span className="text-sm font-mono text-red-400 uppercase tracking-wider font-bold">Bearish</span>
                        <span className="text-sm font-mono text-red-400">{bearishScore.toFixed(1)} / {threshold.toFixed(1)}</span>
                    </div>
                    <div className="h-2 bg-zinc-900 rounded-full overflow-hidden">
                        <div
                            className="h-full transition-all duration-500 bg-red-500/30"
                            style={{ width: `${Math.min((bearishScore / threshold) * 100, 100)}%` }}
                        />
                    </div>

                    {/* Bearish Factors */}
                    {rejection.bearish_factors && rejection.bearish_factors.length > 0 && (
                        <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3 space-y-2 max-h-48 overflow-y-auto">
                            {rejection.bearish_factors.slice(0, 5).map((factor, idx) => (
                                <div key={idx} className="text-xs">
                                    <div className="flex justify-between items-center">
                                        <span className="text-red-300 font-mono truncate flex-1">{factor.name}</span>
                                        <span className="text-red-400 font-mono font-bold ml-2">{factor.weighted_contribution.toFixed(1)}</span>
                                    </div>
                                    {factor.rationale && (
                                        <div className="text-red-400/50 mt-0.5 truncate" title={factor.rationale}>
                                            {factor.rationale}
                                        </div>
                                    )}
                                </div>
                            ))}
                            {rejection.bearish_factors.length > 5 && (
                                <div className="text-xs text-red-400/50 italic">
                                    +{rejection.bearish_factors.length - 5} more factors...
                                </div>
                            )}
                        </div>
                    )}

                    {/* Bearish Adjustments */}
                    {(rejection.bearish_synergy !== undefined || rejection.bearish_conflict !== undefined) && (
                        <div className="space-y-1">
                            {rejection.bearish_synergy !== undefined && rejection.bearish_synergy !== 0 && (
                                <div className="flex justify-between text-xs">
                                    <span className="text-green-400/70">Synergy:</span>
                                    <span className="text-green-400 font-mono">+{rejection.bearish_synergy.toFixed(1)}</span>
                                </div>
                            )}
                            {rejection.bearish_conflict !== undefined && rejection.bearish_conflict !== 0 && (
                                <div className="flex justify-between text-xs">
                                    <span className="text-red-400/70">Conflict:</span>
                                    <span className="text-red-400 font-mono">-{rejection.bearish_conflict.toFixed(1)}</span>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

