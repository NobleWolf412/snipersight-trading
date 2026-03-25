/**
 * GauntletBreakdown — Phase 3 Signal Filter Visualizer
 *
 * Consumes signal_log[] from PaperTradingService and maps each filtered
 * signal's reason string to its exact gauntlet stage. Shows a live funnel
 * so you can see exactly where pairs are dying.
 *
 * Drop-in usage:
 *   <GauntletBreakdown signals={status.signal_log} />
 *
 * Replace the existing SignalIntelligencePanel in TrainingGround.tsx with this,
 * or render both side by side — they use the same signal_log prop.
 */

import { useState, useMemo } from 'react';
import { SignalLogEntry } from '@/utils/api';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';

// ─── Gauntlet stage definitions (same order as _process_signal) ─────────────

export type GauntletStage =
  | 'REGIME_VETO'
  | 'MAX_POSITIONS'
  | 'HAS_POSITION'
  | 'PENDING_ORDER'
  | 'CONFLUENCE'
  | 'POSITION_SIZE'
  | 'PULLBACK_PROB'
  | 'PRICE_FETCH'
  | 'EXEC_ERROR'
  | 'EXECUTED'
  | 'PENDING_FILL'
  | 'UNKNOWN';

interface StageConfig {
  label: string;
  shortLabel: string;
  color: string;       // tailwind text color
  bgColor: string;     // tailwind bg color
  borderColor: string; // tailwind border color
  description: string;
  gate: number;        // 1-indexed position in funnel
}

const STAGE_CONFIG: Record<GauntletStage, StageConfig> = {
  REGIME_VETO: {
    label: 'Regime veto',
    shortLabel: 'REGIME',
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/30',
    description: 'chaotic_volatile + score < 20 — market too dangerous',
    gate: 1,
  },
  MAX_POSITIONS: {
    label: 'Max positions',
    shortLabel: 'MAX POS',
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/10',
    borderColor: 'border-orange-500/30',
    description: 'open + pending count already at cap',
    gate: 2,
  },
  HAS_POSITION: {
    label: 'Already in position',
    shortLabel: 'IN POS',
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
    borderColor: 'border-amber-500/30',
    description: 'existing open/partial position on this symbol',
    gate: 3,
  },
  PENDING_ORDER: {
    label: 'Pending order exists',
    shortLabel: 'PENDING',
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-500/10',
    borderColor: 'border-yellow-500/30',
    description: 'lower-confluence pending order exists for symbol',
    gate: 4,
  },
  CONFLUENCE: {
    label: 'Confluence gate',
    shortLabel: 'CONF',
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/10',
    borderColor: 'border-purple-500/30',
    description: 'score below min_confluence threshold',
    gate: 5,
  },
  POSITION_SIZE: {
    label: 'Position size invalid',
    shortLabel: 'SIZE',
    color: 'text-pink-400',
    bgColor: 'bg-pink-500/10',
    borderColor: 'border-pink-500/30',
    description: 'risk math returns 0 — entry/stop too close or balance too low',
    gate: 6,
  },
  PULLBACK_PROB: {
    label: 'Pullback probability',
    shortLabel: 'PB PROB',
    color: 'text-sky-400',
    bgColor: 'bg-sky-500/10',
    borderColor: 'border-sky-500/30',
    description: 'limit entry pullback probability < 0.45',
    gate: 7,
  },
  PRICE_FETCH: {
    label: 'Price fetch failed',
    shortLabel: 'NO PRICE',
    color: 'text-red-300',
    bgColor: 'bg-red-400/10',
    borderColor: 'border-red-400/30',
    description: 'live ticker + OHLCV cache both failed',
    gate: 8,
  },
  EXEC_ERROR: {
    label: 'Execution error',
    shortLabel: 'EXEC ERR',
    color: 'text-red-500',
    bgColor: 'bg-red-600/10',
    borderColor: 'border-red-600/30',
    description: 'exception thrown during order placement',
    gate: 9,
  },
  PENDING_FILL: {
    label: 'Pending — awaiting fill',
    shortLabel: 'WAIT FILL',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/30',
    description: 'limit placed but price hasn\'t reached entry yet',
    gate: 0, // not a filter — informational
  },
  EXECUTED: {
    label: 'Executed',
    shortLabel: 'EXEC',
    color: 'text-green-400',
    bgColor: 'bg-green-500/10',
    borderColor: 'border-green-500/30',
    description: 'passed all gates — position opened',
    gate: 0,
  },
  UNKNOWN: {
    label: 'Unknown reason',
    shortLabel: '?',
    color: 'text-muted-foreground',
    bgColor: 'bg-muted/10',
    borderColor: 'border-muted/30',
    description: 'reason string didn\'t match a known gate',
    gate: 99,
  },
};

// ─── Reason string → stage classifier ────────────────────────────────────────

export function classifyStage(signal: SignalLogEntry): GauntletStage {
  if (signal.result === 'executed') return 'EXECUTED';
  if (signal.result === 'error') return 'EXEC_ERROR';

  const r = signal.reason.toLowerCase();

  // Pending fill — reason-based since result type only allows executed/filtered/error
  if (r.includes('waiting for limit fill') || (r.includes('pending') && r.includes('fill')))
    return 'PENDING_FILL';

  if (r.includes('regime veto') || r.includes('extreme regime') || r.includes('chaotic'))
    return 'REGIME_VETO';
  if (r.includes('max position'))
    return 'MAX_POSITIONS';
  if (r.includes('already in position') || r.includes('position already'))
    return 'HAS_POSITION';
  if (r.includes('pending order') && (r.includes('equal') || r.includes('higher') || r.includes('exists')))
    return 'PENDING_ORDER';
  if (r.includes('confluence') || r.includes('below min'))
    return 'CONFLUENCE';
  if (r.includes('invalid position size') || r.includes('position size'))
    return 'POSITION_SIZE';
  if (r.includes('pullback probability') || r.includes('low pullback'))
    return 'PULLBACK_PROB';
  if (r.includes('price fetch') || r.includes('no price') || r.includes('price is zero'))
    return 'PRICE_FETCH';

  return 'UNKNOWN';
}

// ─── Per-symbol last-known stage tracker ─────────────────────────────────────

interface SymbolLastSeen {
  symbol: string;
  direction: string;
  stage: GauntletStage;
  reason: string;
  confluence: number;
  rr: number | null;
  entry_zone: number;
  stop_loss: number;
  timestamp: string;
  scan_number: number;
  // Critical factor convergence
  setup_state?: 'READY' | 'DEVELOPING' | 'WATCHING' | 'NOISE';
  convergence_score?: number;
  convergence_critical_count?: number;
  convergence_critical_total?: number;
  convergence_missing?: string[];
  veto_blocked?: boolean;
  active_vetoes?: string[];
}

// ─── Funnel bar ───────────────────────────────────────────────────────────────

function FunnelBar({
  stage,
  count,
  total,
  isSelected,
  onClick,
  threshold,
}: {
  stage: GauntletStage;
  count: number;
  total: number;
  isSelected: boolean;
  onClick: () => void;
  threshold?: number;
}) {
  const cfg = STAGE_CONFIG[stage];
  const pct = total > 0 ? (count / total) * 100 : 0;

  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-2 rounded-lg border transition-all ${
        isSelected
          ? `${cfg.bgColor} ${cfg.borderColor} shadow-sm`
          : 'bg-background/40 border-border/30 hover:border-border/60'
      }`}
    >
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className={`text-[10px] font-mono font-bold tracking-widest uppercase ${cfg.color}`}>
            {cfg.shortLabel}
          </span>
          <span className="text-[10px] text-muted-foreground hidden sm:inline">
            {cfg.label} {threshold !== undefined && stage === 'CONFLUENCE' ? `(<${threshold}%)` : ''}
          </span>
        </div>
        <span className={`text-xs font-mono font-bold ${cfg.color}`}>{count}</span>
      </div>
      <div className="h-1.5 bg-background/60 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${cfg.bgColor.replace('/10', '/60')}`}
          style={{ width: `${Math.max(pct, count > 0 ? 2 : 0)}%` }}
        />
      </div>
    </button>
  );
}

// ─── Setup state badge config ─────────────────────────────────────────────────

const SETUP_STATE_CONFIG = {
  READY:      { label: 'READY',      color: 'text-green-400',  bg: 'bg-green-500/15',  border: 'border-green-500/40' },
  DEVELOPING: { label: 'DEV',        color: 'text-amber-300',  bg: 'bg-amber-500/15',  border: 'border-amber-400/40' },
  WATCHING:   { label: 'WATCH',      color: 'text-sky-400',    bg: 'bg-sky-500/15',    border: 'border-sky-500/40'  },
  NOISE:      { label: 'NOISE',      color: 'text-zinc-500',   bg: 'bg-zinc-800/30',   border: 'border-zinc-700/30' },
} as const;

// ─── Signal row ───────────────────────────────────────────────────────────────

function SignalRow({ entry }: { entry: SymbolLastSeen }) {
  const [open, setOpen] = useState(false);
  const cfg = STAGE_CONFIG[entry.stage];
  const isLong = entry.direction === 'LONG';
  const ss = entry.setup_state ? SETUP_STATE_CONFIG[entry.setup_state] : null;

  // For CONFLUENCE-filtered signals, if setup_state is DEVELOPING or WATCHING
  // we highlight the row slightly to make it stand out from NOISE
  const isDeveloping = entry.stage === 'CONFLUENCE' && (entry.setup_state === 'DEVELOPING' || entry.setup_state === 'WATCHING');

  return (
    <div
      className={`rounded-lg border cursor-pointer transition-all ${
        open
          ? `${cfg.bgColor} ${cfg.borderColor}`
          : isDeveloping
            ? 'bg-amber-500/5 border-amber-500/20 hover:border-amber-400/40'
            : 'bg-background/40 border-border/30 hover:border-border/60'
      }`}
      onClick={() => setOpen(!open)}
    >
      <div className="flex items-center gap-2 px-3 py-2 text-xs font-mono">
        {/* Stage badge */}
        <span className={`shrink-0 text-[9px] font-bold tracking-widest px-1.5 py-0.5 rounded border ${cfg.bgColor} ${cfg.borderColor} ${cfg.color}`}>
          {cfg.shortLabel}
        </span>

        {/* Setup state badge — only show for confluence-filtered signals */}
        {ss && entry.stage === 'CONFLUENCE' && (
          <span className={`shrink-0 text-[8px] font-bold tracking-widest px-1 py-0.5 rounded border ${ss.bg} ${ss.border} ${ss.color}`}>
            {ss.label}
          </span>
        )}

        {/* Direction + Symbol */}
        <span className={`font-bold shrink-0 ${isLong ? 'text-green-400' : 'text-red-400'}`}>
          {isLong ? '▲' : '▼'}
        </span>
        <span className="font-bold text-foreground w-20 truncate shrink-0">
          {entry.symbol.replace('/USDT', '').replace(':USDT', '')}
        </span>

        {/* Confluence */}
        <span className={`shrink-0 w-10 text-right ${entry.confluence >= 75 ? 'text-green-400' : entry.confluence >= 60 ? 'text-yellow-400' : 'text-red-400'}`}>
          {entry.confluence.toFixed(0)}%
        </span>

        {/* R:R — only show when a real trade plan exists (rr > 0) */}
        <span className="text-muted-foreground shrink-0 w-12 text-right">
          {entry.rr != null && entry.rr > 0 ? `${entry.rr.toFixed(1)}R` : '—'}
        </span>

        {/* Reason truncated */}
        <span className="flex-1 truncate text-muted-foreground/70 pl-2 border-l border-border/20 italic">
          {entry.reason}
        </span>

        {/* Time */}
        <span className="text-muted-foreground/40 shrink-0 text-[9px]">
          {new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </span>
      </div>

      {open && (
        <div className="px-3 pb-3 pt-1 border-t border-border/20 grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-1 text-[10px] font-mono text-muted-foreground">
          <div><span className="text-muted-foreground/50">scan# </span>{entry.scan_number}</div>
          <div><span className="text-muted-foreground/50">entry </span>{entry.entry_zone > 0 ? `$${entry.entry_zone.toFixed(4)}` : '—'}</div>
          <div><span className="text-muted-foreground/50">stop </span>{entry.stop_loss > 0 ? `$${entry.stop_loss.toFixed(4)}` : '—'}</div>
          {entry.rr != null && entry.rr > 0 && (
            <div><span className="text-muted-foreground/50">r:r </span>{entry.rr.toFixed(2)}</div>
          )}

          {/* Critical factor convergence — only for confluence-filtered signals */}
          {entry.stage === 'CONFLUENCE' && entry.convergence_score !== undefined && (
            <>
              <div className="col-span-full pt-1 flex items-center gap-2 flex-wrap">
                <span className="text-muted-foreground/50">convergence </span>
                <span className={`font-bold ${
                  (entry.convergence_score ?? 0) >= 62.5 ? 'text-amber-300' :
                  (entry.convergence_score ?? 0) >= 50   ? 'text-sky-400'   : 'text-zinc-500'
                }`}>
                  {entry.convergence_critical_count ?? 0}/{entry.convergence_critical_total ?? 8} critical
                  ({(entry.convergence_score ?? 0).toFixed(0)}%)
                </span>
                {entry.veto_blocked && (
                  <span className="text-red-400 font-bold">
                    🚫 {(entry.active_vetoes ?? []).join(', ')}
                  </span>
                )}
              </div>
              {(entry.convergence_missing ?? []).length > 0 && (
                <div className="col-span-full text-zinc-500">
                  <span className="text-muted-foreground/50">missing </span>
                  {(entry.convergence_missing ?? []).join(' · ')}
                </div>
              )}
            </>
          )}

          <div className="col-span-full pt-1">
            <span className="text-muted-foreground/50">reason </span>
            <span className={cfg.color}>{entry.reason}</span>
          </div>
          <div className="col-span-full text-muted-foreground/40 pt-0.5">{cfg.description}</div>
        </div>
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  signals: SignalLogEntry[];
  minConfluence?: number;
}

export function GauntletBreakdown({ signals, minConfluence }: Props) {
  const [selectedStage, setSelectedStage] = useState<GauntletStage | null>(null);
  const [showAll, setShowAll] = useState(false);

  // Map each signal to its stage
  const staged = useMemo(() => signals.map(s => ({ ...s, stage: classifyStage(s) })), [signals]);

  // Count per stage (filtered only — exclude EXECUTED and PENDING_FILL from funnel)
  const filterStages: GauntletStage[] = [
    'REGIME_VETO', 'MAX_POSITIONS', 'HAS_POSITION', 'PENDING_ORDER',
    'CONFLUENCE', 'POSITION_SIZE', 'PULLBACK_PROB', 'PRICE_FETCH', 'EXEC_ERROR',
  ];

  const stageCounts = useMemo(() => {
    const counts: Partial<Record<GauntletStage, number>> = {};
    for (const s of staged) {
      counts[s.stage] = (counts[s.stage] ?? 0) + 1;
    }
    return counts;
  }, [staged]);

  const totalFiltered = filterStages.reduce((acc, s) => acc + (stageCounts[s] ?? 0), 0);
  const totalExecuted = stageCounts['EXECUTED'] ?? 0;
  const totalPending = stageCounts['PENDING_FILL'] ?? 0;
  const totalSignals = staged.length;

  // Deduplicated per-symbol last-seen entries (latest per symbol+direction)
  const symbolMap = useMemo(() => {
    const map = new Map<string, SymbolLastSeen>();
    for (const s of staged) {
      const key = `${s.symbol}:${s.direction}`;
      const existing = map.get(key);
      if (!existing || new Date(s.timestamp) > new Date(existing.timestamp)) {
        map.set(key, {
          symbol: s.symbol,
          direction: s.direction,
          stage: s.stage,
          reason: s.reason,
          confluence: s.confluence,
          rr: s.rr,
          entry_zone: s.entry_zone,
          stop_loss: s.stop_loss,
          timestamp: s.timestamp,
          scan_number: s.scan_number,
          setup_state: s.setup_state,
          convergence_score: s.convergence_score,
          convergence_critical_count: s.convergence_critical_count,
          convergence_critical_total: s.convergence_critical_total,
          convergence_missing: s.convergence_missing,
          veto_blocked: s.veto_blocked,
          active_vetoes: s.active_vetoes,
        });
      }
    }
    return map;
  }, [staged]);

  // Filtered view for right panel
  const visibleEntries = useMemo(() => {
    const all = Array.from(symbolMap.values()).sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
    if (selectedStage) return all.filter(e => e.stage === selectedStage);
    return all;
  }, [symbolMap, selectedStage]);

  const displayEntries = showAll ? visibleEntries : visibleEntries.slice(0, 40);

  if (signals.length === 0) {
    return (
      <div className="glass-card p-5 rounded-2xl border border-purple-500/20 text-center text-muted-foreground text-sm py-10">
        No signals yet — gauntlet data will appear once the scanner runs.
      </div>
    );
  }

  return (
    <section className="glass-card p-5 rounded-2xl border border-purple-500/20 relative overflow-hidden">
      {/* header glow */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,_var(--tw-gradient-stops))] from-purple-500/5 via-transparent to-transparent opacity-40 pointer-events-none" />
      <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-purple-400/40 to-transparent" />

      {/* ── Title row ── */}
      <div className="relative z-10 flex flex-wrap items-center justify-between gap-3 mb-5">
        <h2 className="text-xl font-semibold hud-headline tracking-wide flex items-center gap-2 text-purple-400 drop-shadow-[0_0_8px_rgba(168,85,247,0.4)]">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" className="shrink-0">
            <path d="M3 4h14M5 8h10M7 12h6M9 16h2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          GAUNTLET BREAKDOWN
        </h2>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] font-mono text-muted-foreground/60 uppercase tracking-widest">
            {totalSignals} signals
          </span>
          <Badge variant="outline" className="font-mono text-[10px] bg-green-500/10 text-green-400 border-green-500/30">
            {totalExecuted} EXEC
          </Badge>
          {totalPending > 0 && (
            <Badge variant="outline" className="font-mono text-[10px] bg-blue-500/10 text-blue-400 border-blue-500/30">
              {totalPending} WAIT
            </Badge>
          )}
          <Badge variant="outline" className="font-mono text-[10px] bg-red-500/10 text-red-400 border-red-500/30">
            {totalFiltered} FILT
          </Badge>
        </div>
      </div>

      <div className="relative z-10 flex flex-col lg:flex-row gap-4">

        {/* ── Left: funnel ── */}
        <div className="lg:w-64 shrink-0 space-y-1.5">
          <div className="text-[9px] uppercase tracking-widest text-muted-foreground/50 font-bold mb-2 pl-1">
            Filter gates (click to filter)
          </div>

          {/* pass-through row */}
          <button
            onClick={() => setSelectedStage(selectedStage === 'EXECUTED' ? null : 'EXECUTED')}
            className={`w-full text-left p-2 rounded-lg border transition-all ${
              selectedStage === 'EXECUTED'
                ? 'bg-green-500/10 border-green-500/30'
                : 'bg-background/40 border-border/30 hover:border-border/60'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono font-bold tracking-widest text-green-400">EXECUTED</span>
              <span className="text-xs font-mono font-bold text-green-400">{totalExecuted}</span>
            </div>
          </button>

          {totalPending > 0 && (
            <button
              onClick={() => setSelectedStage(selectedStage === 'PENDING_FILL' ? null : 'PENDING_FILL')}
              className={`w-full text-left p-2 rounded-lg border transition-all ${
                selectedStage === 'PENDING_FILL'
                  ? 'bg-blue-500/10 border-blue-500/30'
                  : 'bg-background/40 border-border/30 hover:border-border/60'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono font-bold tracking-widest text-blue-400">WAIT FILL</span>
                <span className="text-xs font-mono font-bold text-blue-400">{totalPending}</span>
              </div>
            </button>
          )}

          <div className="my-2 border-t border-border/30" />

          {filterStages.map(stage => {
            const count = stageCounts[stage] ?? 0;
            if (count === 0) return null;
            return (
              <FunnelBar
                key={stage}
                stage={stage}
                count={count}
                total={totalFiltered}
                threshold={minConfluence}
                isSelected={selectedStage === stage}
                onClick={() => setSelectedStage(selectedStage === stage ? null : stage)}
              />
            );
          })}

          {selectedStage && (
            <button
              onClick={() => setSelectedStage(null)}
              className="w-full text-[10px] font-mono text-muted-foreground/60 hover:text-muted-foreground pt-1 text-center"
            >
              ✕ clear filter
            </button>
          )}

          {/* pass rate */}
          <div className="mt-3 pt-3 border-t border-border/30 text-[10px] font-mono text-muted-foreground space-y-1">
            <div className="flex justify-between">
              <span>pass rate</span>
              <span className="text-green-400">
                {totalSignals > 0 ? ((totalExecuted / totalSignals) * 100).toFixed(1) : '0'}%
              </span>
            </div>
            <div className="h-1.5 bg-background/60 rounded-full overflow-hidden">
              <div
                className="h-full bg-green-500/50 rounded-full"
                style={{ width: `${totalSignals > 0 ? (totalExecuted / totalSignals) * 100 : 0}%` }}
              />
            </div>
            <div className="flex justify-between opacity-60">
              <span>top killer</span>
              <span>
                {totalFiltered > 0
                  ? STAGE_CONFIG[
                      filterStages.reduce((a, b) =>
                        (stageCounts[a] ?? 0) >= (stageCounts[b] ?? 0) ? a : b
                      )
                    ].shortLabel
                  : '—'}
              </span>
            </div>
          </div>
        </div>

        {/* ── Right: symbol list ── */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-2">
            <div className="text-[9px] uppercase tracking-widest text-muted-foreground/50 font-bold">
              {selectedStage
                ? `${STAGE_CONFIG[selectedStage].label} — ${visibleEntries.length} symbols`
                : `all symbols — ${visibleEntries.length} unique`}
            </div>
            {visibleEntries.length > 40 && (
              <button
                onClick={() => setShowAll(!showAll)}
                className="text-[10px] font-mono text-purple-400/70 hover:text-purple-400"
              >
                {showAll ? 'show less' : `show all ${visibleEntries.length}`}
              </button>
            )}
          </div>
          <ScrollArea className="h-[420px]">
            <div className="space-y-1 pr-2">
              {displayEntries.map((entry, idx) => (
                <SignalRow key={`${entry.symbol}:${entry.direction}:${idx}`} entry={entry} />
              ))}
              {displayEntries.length === 0 && (
                <div className="text-center text-muted-foreground/50 text-xs py-10 italic">
                  no signals for this stage yet
                </div>
              )}
            </div>
          </ScrollArea>
        </div>

      </div>
    </section>
  );
}
