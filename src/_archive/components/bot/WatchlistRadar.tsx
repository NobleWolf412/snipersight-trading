/**
 * WatchlistRadar — Live per-symbol setup health panel
 *
 * Shows every pair on the bot's watchlist with its latest convergence
 * state from the most recent scan. Replaces the generic activity feed
 * on BotStatus so you can see at a glance what's building vs noise.
 *
 * Data flow:
 *   status.config.symbols         → the watchlist
 *   status.signal_log             → latest scan results per symbol
 *   entry.setup_state             → DEVELOPING / WATCHING / NOISE / READY
 *   entry.convergence_score       → % of 8 critical factors firing
 *   entry.convergence_critical_count / total
 *   entry.veto_blocked / active_vetoes
 *   entry.convergence_missing     → which critical factors are below threshold
 */

import { useMemo, useState } from 'react';
import { PaperTradingStatusResponse, SignalLogEntry } from '@/utils/api';

// ─── Setup state config ───────────────────────────────────────────────────────

type SetupState = 'READY' | 'DEVELOPING' | 'WATCHING' | 'NOISE' | 'PENDING';

interface StateConfig {
  label: string;
  color: string;
  bg: string;
  border: string;
  sortOrder: number;
}

const STATE_CONFIG: Record<SetupState, StateConfig> = {
  READY:      { label: 'READY',  color: 'text-green-400',  bg: 'bg-green-500/15',  border: 'border-green-500/40',  sortOrder: 0 },
  DEVELOPING: { label: 'DEV',    color: 'text-amber-300',  bg: 'bg-amber-500/15',  border: 'border-amber-400/40',  sortOrder: 1 },
  WATCHING:   { label: 'WATCH',  color: 'text-sky-400',    bg: 'bg-sky-500/15',    border: 'border-sky-500/40',    sortOrder: 2 },
  NOISE:      { label: 'NOISE',  color: 'text-zinc-500',   bg: 'bg-zinc-800/20',   border: 'border-zinc-700/25',   sortOrder: 3 },
  PENDING:    { label: '—',      color: 'text-zinc-600',   bg: 'bg-zinc-900/20',   border: 'border-zinc-800/20',   sortOrder: 4 },
};

// ─── Per-symbol derived data ──────────────────────────────────────────────────

interface SymbolHealth {
  symbol: string;
  shortName: string;
  state: SetupState;
  direction: string | null;
  confluence: number | null;
  criticalCount: number;
  criticalTotal: number;
  convergenceScore: number;
  vetoBlocked: boolean;
  activeVetoes: string[];
  missing: string[];
  lastSeen: string | null;
  scanNumber: number | null;
}

function deriveSymbolHealth(
  symbol: string,
  entries: SignalLogEntry[]
): SymbolHealth {
  const shortName = symbol.replace('/USDT', '').replace(':USDT', '');

  if (entries.length === 0) {
    return {
      symbol, shortName,
      state: 'PENDING',
      direction: null,
      confluence: null,
      criticalCount: 0,
      criticalTotal: 8,
      convergenceScore: 0,
      vetoBlocked: false,
      activeVetoes: [],
      missing: [],
      lastSeen: null,
      scanNumber: null,
    };
  }

  // Latest entry for this symbol (highest scan_number wins, then timestamp)
  const latest = entries.reduce((best, e) =>
    (e.scan_number ?? 0) > (best.scan_number ?? 0) ? e : best
  );

  const rawState = latest.setup_state ?? 'NOISE';
  const state: SetupState =
    rawState === 'READY' ? 'READY' :
    rawState === 'DEVELOPING' ? 'DEVELOPING' :
    rawState === 'WATCHING' ? 'WATCHING' : 'NOISE';

  return {
    symbol,
    shortName,
    state,
    direction: latest.direction ?? null,
    confluence: latest.confluence ?? null,
    criticalCount: latest.convergence_critical_count ?? 0,
    criticalTotal: latest.convergence_critical_total ?? 8,
    convergenceScore: latest.convergence_score ?? 0,
    vetoBlocked: latest.veto_blocked ?? false,
    activeVetoes: latest.active_vetoes ?? [],
    missing: latest.convergence_missing ?? [],
    lastSeen: latest.timestamp,
    scanNumber: latest.scan_number ?? null,
  };
}

// ─── Convergence bar ──────────────────────────────────────────────────────────

function ConvergenceBar({ count, total, state }: { count: number; total: number; state: SetupState }) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  const barColor =
    state === 'READY'      ? 'bg-green-500/70' :
    state === 'DEVELOPING' ? 'bg-amber-400/70' :
    state === 'WATCHING'   ? 'bg-sky-500/70'   : 'bg-zinc-700/50';

  return (
    <div className="flex items-center gap-1.5 flex-1 min-w-0">
      <div className="flex-1 h-1 bg-zinc-800/60 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${Math.max(pct, count > 0 ? 3 : 0)}%` }}
        />
      </div>
      <span className="text-[9px] font-mono text-muted-foreground/50 shrink-0 w-6 text-right">
        {count}/{total}
      </span>
    </div>
  );
}

// ─── Single symbol row ────────────────────────────────────────────────────────

function SymbolRow({ h, isScanning }: { h: SymbolHealth; isScanning: boolean }) {
  const [open, setOpen] = useState(false);
  const cfg = STATE_CONFIG[h.state];
  const isLong = h.direction === 'LONG';
  const isShort = h.direction === 'SHORT';

  const rowBg =
    h.state === 'READY'      ? 'bg-green-500/5 border-green-500/20 hover:border-green-500/35' :
    h.state === 'DEVELOPING' ? 'bg-amber-500/5 border-amber-500/20 hover:border-amber-400/35' :
    h.state === 'WATCHING'   ? 'bg-sky-500/5   border-sky-500/20   hover:border-sky-400/35'   :
    h.state === 'PENDING'    ? 'bg-transparent border-zinc-800/30  hover:border-zinc-700/50'   :
                               'bg-transparent border-zinc-800/20  hover:border-zinc-700/40';

  return (
    <div
      className={`rounded-lg border cursor-pointer transition-all ${open ? `${cfg.bg} ${cfg.border}` : rowBg}`}
      onClick={() => h.state !== 'PENDING' && setOpen(!open)}
    >
      <div className="flex items-center gap-2 px-3 py-2 text-xs font-mono">

        {/* Setup state badge */}
        <span className={`shrink-0 text-[8px] font-bold tracking-widest px-1.5 py-0.5 rounded border w-11 text-center ${cfg.bg} ${cfg.border} ${cfg.color}`}>
          {cfg.label}
        </span>

        {/* Direction arrow */}
        <span className={`shrink-0 text-[10px] w-3 ${isLong ? 'text-green-400' : isShort ? 'text-red-400' : 'text-zinc-600'}`}>
          {isLong ? '▲' : isShort ? '▼' : '·'}
        </span>

        {/* Symbol name */}
        <span className={`font-bold w-14 shrink-0 ${h.state === 'NOISE' || h.state === 'PENDING' ? 'text-zinc-500' : 'text-foreground'}`}>
          {h.shortName}
        </span>

        {/* Confluence score */}
        <span className={`shrink-0 w-9 text-right text-[10px] ${
          h.confluence === null ? 'text-zinc-600' :
          h.confluence >= 75 ? 'text-green-400' :
          h.confluence >= 55 ? 'text-yellow-400' : 'text-zinc-500'
        }`}>
          {h.confluence !== null ? `${h.confluence.toFixed(0)}%` : '—'}
        </span>

        {/* Convergence bar */}
        {h.state !== 'PENDING' ? (
          <ConvergenceBar count={h.criticalCount} total={h.criticalTotal} state={h.state} />
        ) : (
          <div className="flex-1" />
        )}

        {/* Veto indicator */}
        {h.vetoBlocked && (
          <span className="shrink-0 text-[8px] text-red-400 font-bold tracking-wider">VETO</span>
        )}

        {/* Scan indicator pulse (only when actively scanning this symbol) */}
        {isScanning && h.state === 'PENDING' && (
          <span className="shrink-0 w-1.5 h-1.5 bg-zinc-600 rounded-full animate-pulse" />
        )}

      </div>

      {/* Expanded detail */}
      {open && h.state !== 'PENDING' && (
        <div className="px-3 pb-3 pt-1 border-t border-border/15 space-y-1.5 text-[10px] font-mono">

          {/* Convergence detail */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-muted-foreground/40">convergence</span>
            <span className={`font-bold ${
              h.convergenceScore >= 62.5 ? 'text-amber-300' :
              h.convergenceScore >= 50   ? 'text-sky-400'   : 'text-zinc-500'
            }`}>
              {h.criticalCount}/{h.criticalTotal} critical ({h.convergenceScore.toFixed(0)}%)
            </span>
            {h.vetoBlocked && (
              <span className="text-red-400 font-bold">
                🚫 {h.activeVetoes.join(', ')}
              </span>
            )}
          </div>

          {/* Missing factors */}
          {h.missing.length > 0 && (
            <div>
              <span className="text-muted-foreground/40">missing </span>
              <span className="text-zinc-500">{h.missing.join(' · ')}</span>
            </div>
          )}

          {/* Last seen */}
          {h.lastSeen && (
            <div className="text-zinc-600">
              <span className="text-muted-foreground/40">scan# </span>{h.scanNumber}
              <span className="ml-3 text-muted-foreground/40">at </span>
              {new Date(h.lastSeen).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  status: PaperTradingStatusResponse;
}

export function WatchlistRadar({ status }: Props) {
  const isRunning = status.status === 'running';
  const isScanning = status.current_scan?.status === 'running';
  const signalLog: SignalLogEntry[] = status.signal_log ?? [];

  // config.symbols is empty when the bot uses auto pair selection.
  // In that case, derive the watchlist from symbols seen in the signal log
  // so the radar always shows what's actually being scanned.
  const configSymbols: string[] = status.config?.symbols ?? [];
  const logSymbols: string[] = useMemo(
    () => Array.from(new Set(signalLog.map(e => e.symbol))).sort(),
    [signalLog]
  );
  const watchlist: string[] = configSymbols.length > 0 ? configSymbols : logSymbols;

  // Build a map of symbol → all its signal log entries
  const signalsBySymbol = useMemo(() => {
    const map = new Map<string, SignalLogEntry[]>();
    for (const entry of signalLog) {
      const arr = map.get(entry.symbol) ?? [];
      arr.push(entry);
      map.set(entry.symbol, arr);
    }
    return map;
  }, [signalLog]);

  // Derive health for every symbol on the watchlist
  const symbolHealth = useMemo(() => {
    const health = watchlist.map(sym =>
      deriveSymbolHealth(sym, signalsBySymbol.get(sym) ?? [])
    );
    // Sort: READY → DEVELOPING → WATCHING → NOISE → PENDING
    // Within same state, sort by convergence score descending
    return health.sort((a, b) => {
      const orderDiff = STATE_CONFIG[a.state].sortOrder - STATE_CONFIG[b.state].sortOrder;
      if (orderDiff !== 0) return orderDiff;
      return b.convergenceScore - a.convergenceScore;
    });
  }, [watchlist, signalsBySymbol]);

  // Counts per state for the header summary
  const stateCounts = useMemo(() => {
    const counts: Partial<Record<SetupState, number>> = {};
    for (const h of symbolHealth) {
      counts[h.state] = (counts[h.state] ?? 0) + 1;
    }
    return counts;
  }, [symbolHealth]);

  // ── Empty state ──────────────────────────────────────────────────────────────
  if (watchlist.length === 0) {
    return (
      <div className="glass-card p-5 rounded-2xl border border-zinc-700/30 text-center text-muted-foreground text-sm py-10">
        No watchlist configured — add symbols to start scanning.
      </div>
    );
  }

  return (
    <section className="glass-card p-5 rounded-2xl border border-purple-500/20 relative overflow-hidden">
      {/* Header glow */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,_var(--tw-gradient-stops))] from-purple-500/5 via-transparent to-transparent opacity-40 pointer-events-none" />
      <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-purple-400/40 to-transparent" />

      {/* ── Header ── */}
      <div className="relative z-10 flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="text-xl font-semibold hud-headline tracking-wide flex items-center gap-2 text-purple-400 drop-shadow-[0_0_8px_rgba(168,85,247,0.4)]">
          {/* radar icon */}
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" className="shrink-0">
            <circle cx="9" cy="9" r="7.5" stroke="currentColor" strokeWidth="1" strokeOpacity="0.4"/>
            <circle cx="9" cy="9" r="4.5" stroke="currentColor" strokeWidth="1" strokeOpacity="0.5"/>
            <circle cx="9" cy="9" r="1.5" fill="currentColor"/>
            <line x1="9" y1="9" x2="9" y2="1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" className="origin-center animate-[spin_3s_linear_infinite]" style={{ transformOrigin: '9px 9px' }}/>
          </svg>
          WATCHLIST RADAR
        </h2>

        {/* State summary chips */}
        <div className="flex items-center gap-2 flex-wrap">
          {isScanning && (
            <span className="text-[9px] font-mono text-purple-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-pulse" />
              SCANNING
            </span>
          )}
          {!isRunning && (
            <span className="text-[9px] font-mono text-zinc-500 uppercase tracking-widest">bot idle</span>
          )}
          {(stateCounts.READY ?? 0) > 0 && (
            <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border bg-green-500/15 border-green-500/40 text-green-400">
              {stateCounts.READY} READY
            </span>
          )}
          {(stateCounts.DEVELOPING ?? 0) > 0 && (
            <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border bg-amber-500/15 border-amber-400/40 text-amber-300">
              {stateCounts.DEVELOPING} DEV
            </span>
          )}
          {(stateCounts.WATCHING ?? 0) > 0 && (
            <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border bg-sky-500/15 border-sky-500/40 text-sky-400">
              {stateCounts.WATCHING} WATCH
            </span>
          )}
          <span className="text-[9px] font-mono text-zinc-600">
            {watchlist.length} pairs
          </span>
        </div>
      </div>

      {/* ── Column headers ── */}
      <div className="relative z-10 flex items-center gap-2 px-3 pb-1.5 text-[8px] font-mono uppercase tracking-widest text-muted-foreground/30">
        <span className="w-11 shrink-0">state</span>
        <span className="w-3 shrink-0" />
        <span className="w-14 shrink-0">pair</span>
        <span className="w-9 shrink-0 text-right">score</span>
        <span className="flex-1 pl-1">critical factors</span>
      </div>

      {/* ── Symbol rows ── */}
      <div className="relative z-10 space-y-1.5">
        {symbolHealth.map(h => (
          <SymbolRow key={h.symbol} h={h} isScanning={isScanning ?? false} />
        ))}
      </div>

      {/* ── Footer: last scan time ── */}
      {status.last_scan_at && (
        <div className="relative z-10 mt-3 pt-2 border-t border-border/10 text-[9px] font-mono text-zinc-600 flex items-center justify-between">
          <span>last scan {new Date(status.last_scan_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
          {status.next_scan_in_seconds != null && status.next_scan_in_seconds > 0 && (
            <span>next in {Math.round(status.next_scan_in_seconds)}s</span>
          )}
        </div>
      )}
    </section>
  );
}
