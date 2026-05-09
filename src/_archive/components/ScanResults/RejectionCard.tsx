import { useState } from 'react';
import { XCircle, WarningCircle, Prohibit, Bug, CaretDown, Pulse, Copy, Check, Lightning, ArrowDown, ArrowUp, GitFork } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

export interface RejectionInfo {
    symbol: string;
    reason_type: 'low_confluence' | 'no_data' | 'missing_critical_tf' | 'risk_validation' | 'no_trade_plan' | 'cooldown_active' | 'errors'
        | 'btc_impulse' | 'structural_anchor' | 'regime_alignment' | 'conflict_density';
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
    // Conflict density specific fields
    conflict_conditions?: string[];
    conflict_count?: number;
    // Other rejection-specific fields
    missing_timeframes?: string[];
    required_timeframes?: string[];
    [key: string]: any;
}

interface RejectionCardProps {
    rejection: RejectionInfo;
}

const REASON_CONFIG = {
    // ── Post-scoring gauntlet gates ─────────────────────────────────────────
    low_confluence: {
        icon: WarningCircle,
        color: 'text-amber-400',
        border: 'border-amber-500/20',
        bg: 'bg-amber-500/10',
        glow: 'hover:shadow-[0_0_15px_rgba(251,191,36,0.15)] hover:border-amber-500/40',
    },
    no_data: {
        icon: Prohibit,
        color: 'text-zinc-400',
        border: 'border-zinc-500/20',
        bg: 'bg-zinc-500/10',
        glow: 'hover:shadow-[0_0_15px_rgba(113,113,122,0.15)] hover:border-zinc-500/40',
    },
    missing_critical_tf: {
        icon: Prohibit,
        color: 'text-orange-400',
        border: 'border-orange-500/20',
        bg: 'bg-orange-500/10',
        glow: 'hover:shadow-[0_0_15px_rgba(251,146,60,0.15)] hover:border-orange-500/40',
    },
    risk_validation: {
        icon: XCircle,
        color: 'text-red-400',
        border: 'border-red-500/20',
        bg: 'bg-red-500/10',
        glow: 'hover:shadow-[0_0_15px_rgba(248,113,113,0.15)] hover:border-red-500/40',
    },
    no_trade_plan: {
        icon: XCircle,
        color: 'text-zinc-400',
        border: 'border-zinc-500/20',
        bg: 'bg-zinc-500/10',
        glow: 'hover:shadow-[0_0_15px_rgba(161,161,170,0.15)] hover:border-zinc-500/40',
    },
    cooldown_active: {
        icon: Prohibit,
        color: 'text-blue-400',
        border: 'border-blue-500/20',
        bg: 'bg-blue-500/10',
        glow: 'hover:shadow-[0_0_15px_rgba(96,165,250,0.15)] hover:border-blue-500/40',
    },
    errors: {
        icon: Bug,
        color: 'text-pink-400',
        border: 'border-pink-500/20',
        bg: 'bg-pink-500/10',
        glow: 'hover:shadow-[0_0_15px_rgba(244,114,182,0.15)] hover:border-pink-500/40',
    },
    // ── Pre-scoring hard gates (orchestrator, before confluence scoring) ────
    btc_impulse: {
        icon: Lightning,
        color: 'text-yellow-400',
        border: 'border-yellow-500/20',
        bg: 'bg-yellow-500/10',
        glow: 'hover:shadow-[0_0_15px_rgba(234,179,8,0.15)] hover:border-yellow-500/40',
    },
    structural_anchor: {
        icon: XCircle,
        color: 'text-rose-400',
        border: 'border-rose-500/20',
        bg: 'bg-rose-500/10',
        glow: 'hover:shadow-[0_0_15px_rgba(251,113,133,0.15)] hover:border-rose-500/40',
    },
    regime_alignment: {
        icon: ArrowDown,
        color: 'text-orange-400',
        border: 'border-orange-500/20',
        bg: 'bg-orange-500/10',
        glow: 'hover:shadow-[0_0_15px_rgba(251,146,60,0.15)] hover:border-orange-500/40',
    },
    conflict_density: {
        icon: GitFork,
        color: 'text-fuchsia-400',
        border: 'border-fuchsia-500/20',
        bg: 'bg-fuchsia-500/10',
        glow: 'hover:shadow-[0_0_15px_rgba(232,121,249,0.15)] hover:border-fuchsia-500/40',
    },
};

// ── Pre-scoring gate descriptors ──────────────────────────────────────────────

const GATE_DESCRIPTOR: Record<string, {
    title: string;
    subtitle: string;
    what: string;
    fix: string;
}> = {
    btc_impulse: {
        title: 'BTC Impulse Veto',
        subtitle: 'Hard gate — fires before confluence scoring',
        what: 'Blocks alt trades when BTC is in a strong opposing impulse. Entering an alt LONG while BTC is dumping hard produces correlated drawdowns — this gate prevents that.',
        fix: 'Wait for BTC to stabilise or show a reversal signal (CHoCH / BOS on the 1h or 4h). Once BTC\'s impulse tag clears, alt longs will be re-evaluated.',
    },
    structural_anchor: {
        title: 'No Structural Anchor',
        subtitle: 'Hard gate — fires before confluence scoring',
        what: 'Every valid entry needs an anchor: a bullish/bearish order block, a fair value gap, or a confirmed liquidity sweep. Without one, there\'s no price level to target an entry from.',
        fix: 'Wait for a sweep of an obvious high/low, or for price to create and mitigate a new FVG or OB on the primary timeframe.',
    },
    regime_alignment: {
        title: 'Regime Alignment Failed',
        subtitle: 'Hard gate — fires before confluence scoring',
        what: 'The trade direction is counter to a confirmed strong regime. A LONG in a strong_down regime (or SHORT in strong_up) requires a CHoCH (Change of Character) to justify the counter-trend move — none was detected.',
        fix: 'Either wait for a structural CHoCH confirmation on the primary timeframe, or let the regime shift before re-scanning.',
    },
    conflict_density: {
        title: 'Conflict Density Too High',
        subtitle: 'Hard gate — fires before confluence scoring',
        what: 'Too many opposing BOS (Break of Structure) signals and order blocks are active at the same time. Note: CHoCH (Change of Character) patterns are intentionally excluded — they are reversal markers that may have created the setup, not active opposing conditions.',
        fix: 'Wait for opposing BOS structures to be mitigated or invalidated. A clean sweep of a key level or a confirmed BOS in the trade direction will reduce conflict count and allow the setup to pass.',
    },
};

// ── Parse helpers ─────────────────────────────────────────────────────────────

/** Extract direction + BTC state from btc_impulse reason string */
function parseBtcImpulse(reason: string): { direction: string; btcState: string } {
    const dirMatch = reason.match(/^(LONG|SHORT)/i);
    const stateMatch = reason.match(/\(([^)]+)\)/);
    return {
        direction: dirMatch?.[1]?.toUpperCase() ?? 'LONG',
        btcState: stateMatch?.[1] ?? 'strong_down',
    };
}

/** Extract conflict count from conflict_density reason string */
function parseConflictCount(reason: string): number | null {
    const m = reason.match(/(\d+)\s+simultaneous/i);
    return m ? parseInt(m[1], 10) : null;
}

/** Extract regime from regime_alignment reason string */
function parseRegime(reason: string): string {
    const m = reason.match(/regime is\s+(\S+)/i);
    return m?.[1] ?? 'unknown';
}

export function RejectionCard({ rejection }: RejectionCardProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [showDebug, setShowDebug] = useState(false);
    const [copied, setCopied] = useState(false);

    const config = REASON_CONFIG[rejection.reason_type as keyof typeof REASON_CONFIG] ?? REASON_CONFIG.errors;
    const Icon = config.icon;
    const isConflicted = !!(rejection.bullish_score !== undefined && rejection.bearish_score !== undefined);

    // Pre-scoring hard gates always have something useful to show when expanded
    const isPreScoringGate = ['btc_impulse', 'structural_anchor', 'regime_alignment', 'conflict_density'].includes(rejection.reason_type);

    const hasDetails =
        isPreScoringGate ||
        (rejection.reason_type === 'low_confluence' && (
            rejection.all_factors?.length ||
            (rejection.bullish_factors?.length && rejection.bearish_factors?.length) ||
            (rejection.bullish_score !== undefined && rejection.bearish_score !== undefined)
        )) ||
        rejection.detail ||
        (rejection.reason_type === 'missing_critical_tf' && rejection.missing_timeframes?.length) ||
        rejection.trace_id ||
        Object.keys(rejection).length > 4;

    const toggleExpand = () => {
        if (hasDetails) setIsExpanded(!isExpanded);
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
                'w-full p-6 mb-4 bg-[#0a0f0a] border border-zinc-800/60 rounded-xl transition-all duration-300',
                config.glow,
                hasDetails && 'cursor-pointer hover:border-zinc-700/80'
            )}
            onClick={toggleExpand}
            onKeyDown={handleKeyDown}
            tabIndex={hasDetails ? 0 : undefined}
            role={hasDetails ? 'button' : undefined}
            aria-expanded={isExpanded}
        >
            <div className="flex items-start gap-6">
                <div className={cn('flex items-center justify-center w-12 h-12 rounded-xl border flex-shrink-0', config.bg, config.border, config.color)}>
                    <Icon size={28} weight="bold" />
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-xl font-bold tracking-tight text-zinc-200">{rejection.symbol}</span>
                        <div className="flex items-center gap-2">
                            <span className={cn(
                                'text-xs font-mono uppercase px-2 py-1 rounded border',
                                isConflicted
                                    ? 'bg-orange-500/10 border-orange-500/30 text-orange-400'
                                    : cn(config.bg, config.border, config.color)
                            )}>
                                {isConflicted ? 'CONFLICTED' : rejection.reason_type.replace(/_/g, ' ')}
                            </span>
                            {hasDetails && (
                                <CaretDown
                                    size={16}
                                    className={cn('transition-transform duration-200 text-zinc-500', isExpanded && 'rotate-180')}
                                />
                            )}
                        </div>
                    </div>

                    <p className="text-zinc-400 text-lg leading-relaxed font-mono">
                        {rejection.reason}
                    </p>

                    {/* Expanded Details */}
                    <div className={cn(
                        'grid transition-all duration-300 overflow-hidden',
                        isExpanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
                    )}>
                        <div className="min-h-0">
                            {isExpanded && hasDetails && (
                                <div className="mt-6 pt-6 border-t border-zinc-800/60 space-y-4" onClick={e => e.stopPropagation()}>

                                    {/* ── Pre-scoring hard gate breakdowns ── */}
                                    {isPreScoringGate && (
                                        <GateRejectionBreakdown rejection={rejection} config={config} />
                                    )}

                                    {/* ── Low confluence breakdowns ── */}
                                    {rejection.reason_type === 'low_confluence' && (
                                        isConflicted
                                            ? <DualDirectionBreakdown rejection={rejection} config={config} />
                                            : rejection.score !== undefined
                                                ? <ConfluenceBreakdown rejection={rejection} config={config} />
                                                : null
                                    )}

                                    {/* ── Other type-specific breakdowns ── */}
                                    {rejection.detail && !rejection.bullish_factors && !rejection.all_factors && (
                                        <div className="p-3 bg-zinc-800/30 rounded border border-zinc-700/30 text-xs text-zinc-300 mb-4">
                                            {rejection.detail}
                                        </div>
                                    )}
                                    {rejection.reason_type === 'missing_critical_tf' && (
                                        <TimeframeBreakdown rejection={rejection} />
                                    )}
                                    {rejection.reason_type === 'risk_validation' && (
                                        <RiskValidationBreakdown rejection={rejection} />
                                    )}
                                    {rejection.reason_type === 'no_trade_plan' && (
                                        <GenericBreakdown rejection={rejection} title="Trade Plan Validation" />
                                    )}
                                    {rejection.reason_type === 'errors' && (
                                        <GenericBreakdown rejection={rejection} title="Error Details" />
                                    )}

                                    {/* ── Debug / Copy footer ── */}
                                    <div className="flex items-center justify-between pt-4 border-t border-zinc-800/40">
                                        <button
                                            onClick={e => { e.stopPropagation(); setShowDebug(!showDebug); }}
                                            className="text-xs font-mono text-zinc-500 hover:text-zinc-300 transition-colors"
                                        >
                                            {showDebug ? '▼ Hide' : '▶'} Debug Info
                                        </button>
                                        <button
                                            onClick={e => { e.stopPropagation(); copyToClipboard(); }}
                                            className={cn(
                                                'flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-mono transition-all',
                                                copied
                                                    ? 'bg-green-500/10 border-green-500/30 text-green-400'
                                                    : 'bg-zinc-800/50 border-zinc-700/50 text-zinc-400 hover:bg-zinc-700/50 hover:border-zinc-600'
                                            )}
                                        >
                                            {copied ? <><Check size={14} weight="bold" /> Copied!</> : <><Copy size={14} /> Copy JSON</>}
                                        </button>
                                    </div>

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
                        <div className="mt-3 text-xs text-zinc-600 font-mono">Trace ID: {rejection.trace_id}</div>
                    )}
                </div>
            </div>
        </div>
    );
}

// ─── Pre-scoring gate breakdown ───────────────────────────────────────────────

function GateRejectionBreakdown({ rejection, config }: {
    rejection: RejectionInfo;
    config: typeof REASON_CONFIG[keyof typeof REASON_CONFIG];
}) {
    const descriptor = GATE_DESCRIPTOR[rejection.reason_type];
    if (!descriptor) return null;

    return (
        <div className="space-y-4">
            {/* Gate identity card */}
            <div className={cn('p-4 rounded-lg border', config.bg, config.border)}>
                <div className={cn('text-sm font-mono font-bold uppercase tracking-wider mb-0.5', config.color)}>
                    {descriptor.title}
                </div>
                <div className="text-xs text-zinc-500">{descriptor.subtitle}</div>
            </div>

            {/* Type-specific inline detail */}
            {rejection.reason_type === 'btc_impulse' && <BtcImpulseDetail rejection={rejection} config={config} />}
            {rejection.reason_type === 'conflict_density' && <ConflictDensityDetail rejection={rejection} config={config} />}
            {rejection.reason_type === 'regime_alignment' && <RegimeAlignmentDetail rejection={rejection} config={config} />}
            {rejection.reason_type === 'structural_anchor' && <StructuralAnchorDetail />}

            {/* What this gate checks */}
            <div className="space-y-2">
                <div className="text-xs font-mono text-zinc-500 uppercase tracking-wider">What this gate checks</div>
                <p className="text-sm text-zinc-400 leading-relaxed">{descriptor.what}</p>
            </div>

            {/* What to do */}
            <div className="p-3 bg-zinc-900/60 rounded-lg border border-zinc-800/40">
                <div className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-1.5">How to get past this gate</div>
                <p className="text-sm text-zinc-300 leading-relaxed">{descriptor.fix}</p>
            </div>
        </div>
    );
}

function BtcImpulseDetail({ rejection, config }: { rejection: RejectionInfo; config: any }) {
    const { direction, btcState } = parseBtcImpulse(rejection.reason);
    const isDown = btcState.includes('down');
    const isLong = direction === 'LONG';

    return (
        <div className="grid grid-cols-2 gap-3">
            <div className={cn('p-3 rounded-lg border', isLong ? 'bg-green-500/5 border-green-500/20' : 'bg-red-500/5 border-red-500/20')}>
                <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mb-1">Trade direction</div>
                <div className={cn('text-lg font-mono font-bold flex items-center gap-1.5', isLong ? 'text-green-400' : 'text-red-400')}>
                    {isLong ? <ArrowUp size={18} weight="bold" /> : <ArrowDown size={18} weight="bold" />}
                    {direction}
                </div>
            </div>
            <div className={cn('p-3 rounded-lg border', isDown ? 'bg-red-500/5 border-red-500/20' : 'bg-green-500/5 border-green-500/20')}>
                <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mb-1">BTC impulse state</div>
                <div className={cn('text-lg font-mono font-bold', isDown ? 'text-red-400' : 'text-green-400')}>
                    {btcState.replace(/_/g, ' ')}
                </div>
            </div>
        </div>
    );
}

function ConflictDensityDetail({ rejection, config }: { rejection: RejectionInfo; config: any }) {
    const count = rejection.conflict_count ?? parseConflictCount(rejection.reason);
    const conditions = rejection.conflict_conditions ?? [];
    const severity = count == null ? 'unknown' : count >= 8 ? 'extreme' : count >= 5 ? 'high' : 'elevated';
    const severityColor = severity === 'extreme' ? 'text-red-400 border-red-500/30 bg-red-500/5'
        : severity === 'high' ? 'text-orange-400 border-orange-500/30 bg-orange-500/5'
        : 'text-yellow-400 border-yellow-500/30 bg-yellow-500/5';

    return (
        <div className="space-y-3">
            <div className={cn('p-4 rounded-lg border flex items-center justify-between', severityColor)}>
                <div>
                    <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mb-1">Active conflict conditions</div>
                    <div className="text-xs text-zinc-400">Opposing structural signals simultaneously active</div>
                </div>
                {count != null && (
                    <div className="text-right">
                        <div className="text-3xl font-mono font-bold">{count}</div>
                        <div className={cn('text-[10px] font-mono uppercase tracking-wider', severityColor.split(' ')[0])}>
                            {severity}
                        </div>
                    </div>
                )}
            </div>

            {conditions.length > 0 && (
                <div className="space-y-1.5">
                    <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                        Conflicting structures ({conditions.length})
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                        {conditions.map((cond, i) => (
                            <span
                                key={i}
                                className="px-2 py-1 rounded text-xs font-mono bg-fuchsia-500/10 border border-fuchsia-500/20 text-fuchsia-300"
                            >
                                {cond}
                            </span>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

function RegimeAlignmentDetail({ rejection, config }: { rejection: RejectionInfo; config: any }) {
    const regime = parseRegime(rejection.reason);
    const isBearish = regime.includes('down');
    const isBullish = regime.includes('up');

    return (
        <div className={cn(
            'p-3 rounded-lg border flex items-center gap-3',
            isBearish ? 'bg-red-500/5 border-red-500/20' : isBullish ? 'bg-green-500/5 border-green-500/20' : 'bg-zinc-800/30 border-zinc-700/30'
        )}>
            <div className="flex-1">
                <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mb-1">Detected regime</div>
                <div className={cn('text-base font-mono font-bold', isBearish ? 'text-red-400' : isBullish ? 'text-green-400' : 'text-zinc-300')}>
                    {regime.replace(/_/g, ' ')}
                </div>
            </div>
            <div className="text-xs text-zinc-500 text-right max-w-[160px]">
                {isBearish ? 'Strong downtrend — longs need CHoCH confirmation'
                    : isBullish ? 'Strong uptrend — shorts need CHoCH confirmation'
                    : 'Regime misaligned with trade direction'}
            </div>
        </div>
    );
}

function StructuralAnchorDetail() {
    return (
        <div className="grid grid-cols-3 gap-2 text-xs font-mono text-center">
            {['Order Block', 'Fair Value Gap', 'Liquidity Sweep'].map(label => (
                <div key={label} className="p-2 rounded-lg border border-red-500/20 bg-red-500/5">
                    <div className="text-red-400/50 line-through">{label}</div>
                    <div className="text-[9px] text-zinc-600 mt-0.5">not found</div>
                </div>
            ))}
        </div>
    );
}

// ─── Confluence breakdown ─────────────────────────────────────────────────────

/** Single factor row — compact, never overflows */
function FactorRow({ factor }: { factor: NonNullable<RejectionInfo['all_factors']>[number] }) {
    const scoreColor = factor.score >= 70 ? 'text-green-400' : factor.score >= 40 ? 'text-amber-400' : 'text-red-400';
    const barColor   = factor.score >= 70 ? 'bg-green-500/50' : factor.score >= 40 ? 'bg-amber-500/50' : 'bg-red-500/40';
    const contrib    = factor.weighted_contribution;
    const contribPos = contrib >= 0;

    return (
        <div className="px-3 py-1.5 border-b border-zinc-800/30 last:border-0 hover:bg-zinc-800/20 transition-colors">
            {/* name · bar · score · contrib */}
            <div className="flex items-center gap-2 min-w-0">
                <span
                    className="text-[11px] font-mono text-zinc-300 shrink-0 w-[7.5rem] truncate"
                    title={factor.name}
                >
                    {factor.name}
                </span>
                <div className="flex-1 h-1 bg-zinc-800/80 rounded-full overflow-hidden min-w-0">
                    <div
                        className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                        style={{ width: `${Math.min(Math.max(factor.score, 0), 100)}%` }}
                    />
                </div>
                <span className={`text-[11px] font-mono tabular-nums w-7 text-right shrink-0 ${scoreColor}`}>
                    {factor.score.toFixed(0)}
                </span>
                <span className={`text-[11px] font-mono tabular-nums w-10 text-right shrink-0 ${contribPos ? 'text-zinc-400' : 'text-red-400/70'}`}>
                    {contribPos ? '+' : ''}{contrib.toFixed(1)}
                </span>
            </div>
            {/* rationale — wraps, never clips */}
            {factor.rationale && (
                <p className="text-[9px] text-zinc-600 leading-snug mt-0.5 pl-[7.75rem] break-words">
                    {factor.rationale}
                </p>
            )}
        </div>
    );
}

function ConfluenceBreakdown({ rejection, config }: {
    rejection: RejectionInfo;
    config: typeof REASON_CONFIG[keyof typeof REASON_CONFIG];
}) {
    const score     = rejection.score ?? 0;
    const threshold = rejection.threshold ?? 60;
    const gap       = threshold - score;
    const pct       = Math.min((score / Math.max(threshold, 1)) * 100, 100);

    const hasSynergy  = rejection.synergy_bonus  != null && rejection.synergy_bonus  !== 0;
    const hasConflict = rejection.conflict_penalty != null && rejection.conflict_penalty !== 0;

    return (
        <div className="space-y-3">
            {/* ── compact score header ── */}
            <div className="flex items-center gap-3 px-1">
                <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1 text-[10px] font-mono">
                        <span className="text-zinc-500 uppercase tracking-widest">confluence</span>
                        <span className="text-zinc-400 tabular-nums">
                            <span className={gap > 0 ? 'text-amber-400' : 'text-green-400'}>{score.toFixed(1)}</span>
                            <span className="text-zinc-600"> / </span>
                            <span className="text-zinc-500">{threshold.toFixed(0)}</span>
                        </span>
                    </div>
                    <div className="h-2 bg-zinc-900 rounded-full overflow-hidden">
                        <div
                            className={cn('h-full rounded-full transition-all duration-500', config.bg)}
                            style={{ width: `${pct}%` }}
                        />
                    </div>
                </div>
                <div className="shrink-0 text-right">
                    <div className="text-lg font-mono font-bold text-amber-400 tabular-nums">−{gap.toFixed(1)}</div>
                    <div className="text-[9px] text-zinc-600 uppercase tracking-wider">pts short</div>
                </div>
            </div>

            {/* ── synergy / conflict badges inline ── */}
            {(hasSynergy || hasConflict) && (
                <div className="flex gap-2 px-1">
                    {hasSynergy && (
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded border border-green-500/20 bg-green-500/5 text-green-400">
                            synergy +{rejection.synergy_bonus!.toFixed(1)}
                        </span>
                    )}
                    {hasConflict && (
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded border border-red-500/20 bg-red-500/5 text-red-400">
                            conflict −{rejection.conflict_penalty!.toFixed(1)}
                        </span>
                    )}
                </div>
            )}

            {/* ── factor table ── */}
            {rejection.all_factors && rejection.all_factors.length > 0 && (
                <div className="rounded-lg border border-zinc-800/40 overflow-hidden">
                    {/* column headers */}
                    <div className="flex items-center gap-2 px-3 py-1 bg-zinc-900/60 border-b border-zinc-800/40">
                        <span className="text-[9px] font-mono text-zinc-600 uppercase tracking-widest w-[7.5rem] shrink-0 flex items-center gap-1">
                            <Pulse size={9} weight="fill" /> factor
                        </span>
                        <div className="flex-1" />
                        <span className="text-[9px] font-mono text-zinc-600 w-7 text-right shrink-0">scr</span>
                        <span className="text-[9px] font-mono text-zinc-600 w-10 text-right shrink-0">pts</span>
                    </div>
                    <div className="max-h-72 overflow-y-auto">
                        {rejection.all_factors.map((factor, idx) => (
                            <FactorRow key={idx} factor={factor} />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

// ─── Timeframe breakdown ──────────────────────────────────────────────────────

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

// ─── Risk validation breakdown ────────────────────────────────────────────────

function RiskValidationBreakdown({ rejection }: { rejection: RejectionInfo }) {
    const rr = rejection.risk_reward;
    return (
        <div className="space-y-3">
            {rr !== undefined && (
                <div className="flex items-center justify-between p-4 bg-red-500/5 border border-red-500/20 rounded-lg">
                    <div>
                        <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mb-1">Actual R:R ratio</div>
                        <div className="text-xs text-zinc-500">Minimum required: 1.5:1</div>
                    </div>
                    <div className="text-right">
                        <div className={cn('text-2xl font-mono font-bold', rr >= 1.5 ? 'text-green-400' : 'text-red-400')}>
                            {rr.toFixed(2)}:1
                        </div>
                    </div>
                </div>
            )}
            <GenericBreakdown rejection={rejection} title="Risk Validation Details" />
        </div>
    );
}

// ─── Generic breakdown ────────────────────────────────────────────────────────

function GenericBreakdown({ rejection, title }: { rejection: RejectionInfo; title: string }) {
    const excludeKeys = ['symbol', 'reason_type', 'reason', 'trace_id'];
    const metadata = Object.entries(rejection)
        .filter(([key]) => !excludeKeys.includes(key))
        .filter(([, value]) => value !== undefined && value !== null);

    if (metadata.length === 0) return null;

    return (
        <div>
            <div className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-3">{title}</div>
            <div className="bg-zinc-900/50 rounded-lg border border-zinc-800/40 p-4 space-y-2">
                {metadata.map(([key, value]) => (
                    <div key={key} className="flex justify-between items-start gap-4">
                        <span className="text-xs font-mono text-zinc-400 capitalize shrink-0">
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

// ─── Dual direction breakdown ─────────────────────────────────────────────────

function DualDirectionBreakdown({ rejection, config }: {
    rejection: RejectionInfo;
    config: typeof REASON_CONFIG[keyof typeof REASON_CONFIG];
}) {
    const bullishScore = rejection.bullish_score ?? 0;
    const bearishScore = rejection.bearish_score ?? 0;
    const gap = rejection.gap ?? 0;
    const threshold = rejection.threshold ?? 60;

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-orange-500/5 border border-orange-500/30 rounded-lg">
                <div className="flex-1">
                    <div className="text-sm font-mono text-orange-400 font-bold uppercase tracking-wider">Conflicted Market</div>
                    <div className="text-xs text-orange-400/70 mt-1">
                        Both directions are within the minimum margin — no decisive directional edge detected.
                    </div>
                    <div className="text-xs text-orange-300/50 mt-1.5 italic">
                        Wait for a sweep, BOS confirmation, or volume catalyst to break the tie before re-scanning.
                    </div>
                </div>
                <div className="text-right flex-shrink-0 ml-4">
                    <div className="text-2xl font-mono font-bold text-orange-400">{gap.toFixed(1)}pts</div>
                    <div className="text-xs text-orange-400/70">gap (need 8pts)</div>
                </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
                {/* Bullish */}
                <div className="space-y-3">
                    <div className="flex items-center justify-between">
                        <span className="text-sm font-mono text-green-400 uppercase tracking-wider font-bold">Bullish</span>
                        <span className="text-sm font-mono text-green-400">{bullishScore.toFixed(1)} / {threshold.toFixed(1)}</span>
                    </div>
                    <div className="h-2 bg-zinc-900 rounded-full overflow-hidden">
                        <div className="h-full transition-all duration-500 bg-green-500/30" style={{ width: `${Math.min((bullishScore / threshold) * 100, 100)}%` }} />
                    </div>
                    {rejection.bullish_factors && rejection.bullish_factors.length > 0 && (
                        <div className="rounded-lg border border-green-500/20 overflow-hidden max-h-48 overflow-y-auto">
                            {rejection.bullish_factors.map((factor, idx) => (
                                <div key={idx} className="px-2 py-1 border-b border-green-500/10 last:border-0 hover:bg-green-500/5 transition-colors">
                                    <div className="flex items-center gap-1.5 min-w-0">
                                        <span className="text-[10px] font-mono text-green-300 flex-1 min-w-0 truncate" title={factor.name}>{factor.name}</span>
                                        <span className="text-[10px] font-mono text-green-400 font-bold shrink-0 tabular-nums">+{factor.weighted_contribution.toFixed(1)}</span>
                                    </div>
                                    {factor.rationale && (
                                        <p className="text-[9px] text-green-400/40 mt-0.5 leading-snug break-words">{factor.rationale}</p>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
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

                {/* Bearish */}
                <div className="space-y-3">
                    <div className="flex items-center justify-between">
                        <span className="text-sm font-mono text-red-400 uppercase tracking-wider font-bold">Bearish</span>
                        <span className="text-sm font-mono text-red-400">{bearishScore.toFixed(1)} / {threshold.toFixed(1)}</span>
                    </div>
                    <div className="h-2 bg-zinc-900 rounded-full overflow-hidden">
                        <div className="h-full transition-all duration-500 bg-red-500/30" style={{ width: `${Math.min((bearishScore / threshold) * 100, 100)}%` }} />
                    </div>
                    {rejection.bearish_factors && rejection.bearish_factors.length > 0 && (
                        <div className="rounded-lg border border-red-500/20 overflow-hidden max-h-48 overflow-y-auto">
                            {rejection.bearish_factors.map((factor, idx) => (
                                <div key={idx} className="px-2 py-1 border-b border-red-500/10 last:border-0 hover:bg-red-500/5 transition-colors">
                                    <div className="flex items-center gap-1.5 min-w-0">
                                        <span className="text-[10px] font-mono text-red-300 flex-1 min-w-0 truncate" title={factor.name}>{factor.name}</span>
                                        <span className="text-[10px] font-mono text-red-400 font-bold shrink-0 tabular-nums">+{factor.weighted_contribution.toFixed(1)}</span>
                                    </div>
                                    {factor.rationale && (
                                        <p className="text-[9px] text-red-400/40 mt-0.5 leading-snug break-words">{factor.rationale}</p>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
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
