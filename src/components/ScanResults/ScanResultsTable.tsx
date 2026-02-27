import React from 'react';
import { ScanResult } from '@/utils/mockData';
import { cn } from '@/lib/utils';
import { ArrowUpRight, ArrowDownRight, CaretDown, CaretUp, Info } from '@phosphor-icons/react';

interface ScanResultsTableProps {
    results: ScanResult[];
    onResultClick: (id: string) => void;
    selectedId?: string;
}

export function ScanResultsTable({ results, onResultClick, selectedId }: ScanResultsTableProps) {
    const [expandedId, setExpandedId] = React.useState<string | null>(null);

    return (
        <div className="w-full overflow-hidden rounded-xl border border-zinc-800/60 bg-black/40 backdrop-blur-sm shadow-2xl">
            <table className="w-full border-collapse text-left text-sm font-mono">
                <thead>
                    <tr className="border-b border-zinc-800 bg-zinc-900/50">
                        <th className="px-6 py-4 text-xs font-bold uppercase tracking-widest text-zinc-500">Pair</th>
                        <th className="px-6 py-4 text-xs font-bold uppercase tracking-widest text-zinc-500">Direction</th>
                        <th className="px-6 py-4 text-xs font-bold uppercase tracking-widest text-zinc-500">Score</th>
                        <th className="px-6 py-4 text-xs font-bold uppercase tracking-widest text-zinc-500">R:R</th>
                        <th className="px-6 py-4 text-xs font-bold uppercase tracking-widest text-zinc-500">Rationale</th>
                        <th className="px-6 py-4 text-xs font-bold uppercase tracking-widest text-zinc-500 text-right">Action</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                    {results.map((result) => {
                        const isLong = result.trendBias === 'BULLISH';
                        const isSelected = selectedId === result.id;
                        const isExpanded = expandedId === result.id;

                        return (
                            <React.Fragment key={result.id}>
                                <tr
                                    onClick={() => onResultClick(result.id)}
                                    className={cn(
                                        "group cursor-pointer transition-colors duration-200",
                                        isSelected ? "bg-[#00ff88]/5" : "hover:bg-zinc-800/30",
                                        isExpanded && "bg-zinc-800/20"
                                    )}
                                >
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-3">
                                            <div className={cn(
                                                "w-2 h-2 rounded-full",
                                                isLong ? "bg-green-400 shadow-[0_0_8px_rgba(74,222,128,0.5)]" : "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.5)]"
                                            )} />
                                            <span className="text-lg font-bold text-zinc-100">{result.pair}</span>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className={cn(
                                            "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold tracking-widest border",
                                            isLong
                                                ? "bg-green-500/10 border-green-500/20 text-green-400"
                                                : "bg-red-500/10 border-red-500/20 text-red-400"
                                        )}>
                                            {isLong ? <ArrowUpRight size={12} weight="bold" /> : <ArrowDownRight size={12} weight="bold" />}
                                            {isLong ? 'LONG' : 'SHORT'}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <span className={cn(
                                            "text-lg font-bold",
                                            result.confidenceScore >= 80 ? "text-[#00ff88]" :
                                                result.confidenceScore >= 65 ? "text-yellow-400" : "text-amber-500"
                                        )}>
                                            {result.confidenceScore.toFixed(0)}%
                                        </span>
                                    </td>
                                    <td className="px-6 py-4">
                                        <span className="text-lg font-medium text-zinc-300">
                                            {result.riskReward?.toFixed(1) || '0.0'}R
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 max-w-md">
                                        <p className="text-xs text-zinc-400 truncate leading-relaxed">
                                            {result.rationale || "No specific mission rationale provided."}
                                        </p>
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <div className="flex items-center justify-end gap-2">
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    setExpandedId(isExpanded ? null : result.id);
                                                }}
                                                className="p-1.5 rounded-lg bg-zinc-800/50 border border-zinc-700 hover:border-[#00ff88]/50 text-zinc-400 hover:text-[#00ff88] transition-all"
                                            >
                                                {isExpanded ? <CaretUp size={16} /> : <CaretDown size={16} />}
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                                {isExpanded && (
                                    <tr className="bg-zinc-900/40 border-t border-zinc-800/40 shadow-inner">
                                        <td colSpan={6} className="px-8 py-8">
                                            <div className="space-y-8">

                                                {/* ── ZONE 1: Top Row — Mission Thesis + Technical Specs ── */}
                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-start">

                                                    {/* Left: Mission Thesis (bullet-point rationale) */}
                                                    <div className="space-y-4">
                                                        <div className="flex items-center gap-3">
                                                            <div className="w-1 h-4 bg-[#00ff88] rounded-full shadow-[0_0_8px_#00ff88]" />
                                                            <h4 className="text-sm font-black uppercase tracking-[0.2em] text-zinc-100">Mission Thesis</h4>
                                                        </div>
                                                        <div className="space-y-3">
                                                            {result.rationale
                                                                ? result.rationale.split('\n\n').map((line, i) => {
                                                                    const colonIdx = line.indexOf(':');
                                                                    if (colonIdx === -1) return (
                                                                        <div key={i} className="text-xs text-zinc-400 pl-4">{line}</div>
                                                                    );
                                                                    const label = line.substring(0, colonIdx).trim();
                                                                    const rest = line.substring(colonIdx + 1).trim();
                                                                    const pipeIdx = rest.indexOf(' | ');
                                                                    const desc = pipeIdx !== -1 ? rest.substring(0, pipeIdx).trim() : rest;
                                                                    const stats = pipeIdx !== -1 ? rest.substring(pipeIdx + 3).trim() : null;
                                                                    return (
                                                                        <div key={i} className="flex flex-col gap-1 pl-3 border-l-2 border-zinc-800 hover:border-[#00ff88]/40 transition-colors group/bullet">
                                                                            <span className="text-[10px] font-black uppercase tracking-widest text-[#00ff88]/70 group-hover/bullet:text-[#00ff88] transition-colors">{label}</span>
                                                                            <span className="text-xs text-zinc-300 leading-relaxed">{desc}</span>
                                                                            {stats && (
                                                                                <span className="inline-block mt-0.5 px-2 py-0.5 rounded bg-zinc-800/80 border border-zinc-700 text-[10px] font-mono text-zinc-400 w-fit">{stats}</span>
                                                                            )}
                                                                        </div>
                                                                    );
                                                                })
                                                                : <p className="text-xs text-zinc-500 italic pl-3">Strategic command has not filed a manual rationale.</p>
                                                            }
                                                        </div>
                                                    </div>

                                                    {/* Right: Technical Specs 2x2 grid + Deployment Checklist */}
                                                    <div className="space-y-5">
                                                        <div className="flex items-center gap-3">
                                                            <div className="w-1 h-4 bg-zinc-500 rounded-full" />
                                                            <h4 className="text-sm font-black uppercase tracking-[0.2em] text-zinc-100">Technical Specs</h4>
                                                        </div>
                                                        <div className="grid grid-cols-2 gap-3">
                                                            <div className="p-3 rounded-xl bg-zinc-900/60 border border-zinc-800/50 group/stat">
                                                                <div className="text-[10px] uppercase text-zinc-500 font-bold mb-1 tracking-widest">Trade Type</div>
                                                                <div className="text-xs font-black text-zinc-200 uppercase font-mono group-hover/stat:text-[#00ff88] transition-colors">
                                                                    {result.trade_type || result.classification || "Intraday"}
                                                                </div>
                                                            </div>
                                                            <div className="p-3 rounded-xl bg-zinc-900/60 border border-zinc-800/50 group/stat">
                                                                <div className="text-[10px] uppercase text-zinc-500 font-bold mb-1 tracking-widest">Regime</div>
                                                                <div className="text-xs font-black text-yellow-400 uppercase font-mono">
                                                                    {result.regime_label || result.atrRegimeLabel || "Trending"}
                                                                </div>
                                                            </div>
                                                            <div className="p-3 rounded-xl bg-zinc-900/60 border border-zinc-800/50 group/stat">
                                                                <div className="text-[10px] uppercase text-zinc-500 font-bold mb-1 tracking-widest">Target Yield</div>
                                                                <div className="text-xs font-black text-[#00ff88] font-mono">
                                                                    {(result.riskReward || 0).toFixed(1)}R
                                                                </div>
                                                            </div>
                                                            <div className="p-3 rounded-xl bg-zinc-900/60 border border-zinc-800/50 group/stat">
                                                                <div className="text-[10px] uppercase text-zinc-500 font-bold mb-1 tracking-widest">Confidence</div>
                                                                <div className="text-xs font-black text-zinc-100 font-mono">
                                                                    {result.confidenceScore.toFixed(0)}%
                                                                </div>
                                                            </div>
                                                        </div>
                                                        {/* Deployment Checklist */}
                                                        <div className="p-3 rounded-xl bg-black/20 border border-zinc-800/30">
                                                            <h5 className="text-[10px] font-bold uppercase tracking-widest text-[#00ff88] mb-3 flex items-center gap-2">
                                                                <div className="w-1 h-1 rounded-full bg-[#00ff88]" />
                                                                Deployment Checklist
                                                            </h5>
                                                            <ul className="space-y-2">
                                                                <li className="flex items-center gap-2 text-[11px] text-zinc-400">
                                                                    <div className="w-1 h-1 rounded-full bg-zinc-600 flex-shrink-0" />
                                                                    Enter only within defined zones. No chasing.
                                                                </li>
                                                                <li className="flex items-center gap-2 text-[11px] text-zinc-400">
                                                                    <div className="w-1 h-1 rounded-full bg-zinc-600 flex-shrink-0" />
                                                                    Scale 50% at TP1. Move stop to breakeven.
                                                                </li>
                                                            </ul>
                                                        </div>
                                                    </div>
                                                </div>

                                                {/* ── ZONE 2: Full-Width Confluence Grid ── */}
                                                {result.confluence_breakdown?.factors && result.confluence_breakdown.factors.length > 0 && (
                                                    <div className="space-y-3 pt-6 border-t border-zinc-800/50">
                                                        <div className="flex items-center justify-between">
                                                            <div className="flex items-center gap-3">
                                                                <div className="w-1 h-4 bg-zinc-500 rounded-full" />
                                                                <h4 className="text-sm font-black uppercase tracking-[0.2em] text-zinc-100">Confluence Breakdown</h4>
                                                            </div>
                                                            <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">
                                                                {result.confluence_breakdown.factors.length} layers • Total {result.confidenceScore.toFixed(0)}%
                                                            </span>
                                                        </div>
                                                        {/* Compact horizontal grid — 3 columns, each row is one factor */}
                                                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                                                            {result.confluence_breakdown.factors
                                                                .sort((a, b) => (b.score * b.weight) - (a.score * a.weight))
                                                                .map((factor, idx) => (
                                                                    <div
                                                                        key={idx}
                                                                        className="flex flex-col gap-1 p-3 rounded-lg bg-zinc-900/40 border border-zinc-800/60 hover:border-[#00ff88]/20 transition-all group/factor"
                                                                    >
                                                                        <div className="flex items-center justify-between gap-2">
                                                                            <span className="text-[10px] font-black uppercase tracking-wider text-zinc-300 group-hover/factor:text-zinc-100 transition-colors truncate">
                                                                                {factor.name.replace(/_/g, ' ')}
                                                                            </span>
                                                                            <span className={cn(
                                                                                "text-[10px] font-mono font-bold flex-shrink-0",
                                                                                factor.score >= 80 ? "text-green-400" : factor.score >= 50 ? "text-yellow-400" : "text-zinc-500"
                                                                            )}>
                                                                                {factor.score.toFixed(0)}%
                                                                            </span>
                                                                        </div>
                                                                        {/* Score bar */}
                                                                        <div className="h-0.5 w-full bg-zinc-800 rounded-full overflow-hidden">
                                                                            <div
                                                                                className={cn("h-full rounded-full transition-all", factor.score >= 80 ? "bg-green-400/60" : factor.score >= 50 ? "bg-yellow-400/60" : "bg-zinc-600")}
                                                                                style={{ width: `${factor.score}%` }}
                                                                            />
                                                                        </div>
                                                                        {factor.rationale && (
                                                                            <p className="text-[10px] text-zinc-500 leading-snug mt-0.5 line-clamp-2">
                                                                                {factor.rationale}
                                                                            </p>
                                                                        )}
                                                                    </div>
                                                                ))}
                                                        </div>
                                                    </div>
                                                )}

                                            </div>
                                        </td>
                                    </tr>
                                )}
                            </React.Fragment>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}
