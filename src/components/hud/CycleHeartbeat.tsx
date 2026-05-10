/**
 * CycleHeartbeat — last-scan-cycle status strip (Phase 5 polish).
 *
 * Plan reference: peppy-sniffing-owl §3d (Scanner) + §3e (Bot Status).
 *
 *   "NEW: Cycle heartbeat strip at top — 'last cycle: 3s ago · 184
 *    symbols · 2.4s wall · 12 plans emitted · next sweep 47s' —
 *    reading /api/cycles/last."
 *
 * Layout
 * ──────
 *   ┌── ◇ CYCLE_42 · STEALTH ─────────────────────────────────────┐
 *   │  LAST 3s AGO · 184 SYM · 2.4s WALL · 12 PLANS · ETA 47s     │
 *   └─────────────────────────────────────────────────────────────┘
 *
 * Real-data wiring
 * ────────────────
 *   - Polls `/api/cycles/last` every 5s (cycles run on the same order
 *     of magnitude; 5s is short enough to surface stalls quickly while
 *     keeping cost cheap — this is an in-memory backend read).
 *   - `failed === true` → renders a red `◌ FAILED` chip with the
 *     `exception_class` as the right-aligned detail. The whole strip
 *     uses the destructive-tinted panel border in this state so the
 *     operator can't miss it.
 *   - `ts_end === null` (cycle in flight) → "RUNNING" pill replaces
 *     the duration; ETA replaced with "—".
 *   - More than 120s since `ts_end` → strip tinted amber and the
 *     "LAST" label goes amber to flag staleness.
 *   - On endpoint failure → amber `◌ awaiting` chip, no strip body.
 *
 * Synthetic-but-disclosed: none. Strip renders ONLY backend data.
 *
 * Symmetry (CLAUDE.md §10 #3)
 * ───────────────────────────
 *   - Direction-agnostic. Cycle metadata is the loop-level heartbeat;
 *     bull/bear distinctions live in the per-signal payloads downstream.
 *
 * Determinism for snapshots
 * ─────────────────────────
 *   - All time-since/eta computations derive from the live wall clock
 *     against the wire-supplied epochs. tests/visual/states.ts freezes
 *     Date for the existing cycles-last.json fixture (ts_end=1746792020,
 *     frozen=1746792074), producing a stable "54s ago · ETA 6s" render.
 *   - No setInterval-driven UI state aside from the polling timer; the
 *     strip's text is computed at render-time from `cycle` + `Date.now()`.
 *
 * StrictMode safety
 * ─────────────────
 *   - Polling loop captures a `cancelled` flag; cleanup clears the
 *     pending timer. Mirrors the UniversePanel pattern for consistency.
 */
import { useEffect, useMemo, useState } from 'react';
import { api, type CycleHeartbeat as CH } from '@/utils/api';
import { Chip } from './Chip';

// Cycles run frequently enough that 5s polling keeps stalls visible
// without wasting CPU. The endpoint is in-memory cheap.
const POLL_MS = 5_000;
// Operator-visible staleness threshold. Beyond this, the strip tints
// amber to flag that the orchestrator may have stalled. Aligned with
// DiagnoseWizard step 3's threshold for consistency.
const STALE_S = 120;

function fmtSecondsAgo(epochSec: number, nowMs: number): string {
  const ageS = Math.max(0, Math.round(nowMs / 1000 - epochSec));
  if (ageS < 60) return `${ageS}s`;
  const m = Math.floor(ageS / 60);
  const s = ageS % 60;
  return `${m}m${s ? ` ${s}s` : ''}`;
}

function fmtEtaSeconds(etaSec: number, nowMs: number): string {
  const remS = Math.max(0, Math.round(etaSec - nowMs / 1000));
  if (remS < 60) return `${remS}s`;
  const m = Math.floor(remS / 60);
  const s = remS % 60;
  return `${m}m${s ? ` ${s}s` : ''}`;
}

function fmtWall(ms: number | null): string {
  if (ms == null) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function CycleHeartbeat() {
  const [cycle, setCycle] = useState<CH | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      const res = await api.getLastCycle();
      if (cancelled) return;
      setLoaded(true);
      if (res.error || !res.data) {
        setError(res.error || 'no response body');
        setCycle(null);
      } else if (res.data.data) {
        setCycle(res.data.data);
        setError(null);
      } else {
        setError(res.data.metadata.reason || 'cycle unavailable');
        setCycle(null);
      }
      if (!cancelled) {
        timer = setTimeout(tick, POLL_MS);
      }
    };

    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  // Render-time derivations (kept in useMemo only to avoid recomputing
  // on unrelated renders — the strip itself doesn't tick, but the
  // parent page re-renders frequently).
  const view = useMemo(() => {
    if (!cycle) return null;
    const now = Date.now();
    const running = cycle.ts_end == null;
    const ageS = running ? 0 : Math.max(0, Math.round(now / 1000 - (cycle.ts_end ?? 0)));
    const stale = !running && ageS > STALE_S;
    return {
      running,
      stale,
      ageLabel: running ? 'RUNNING' : fmtSecondsAgo(cycle.ts_end ?? 0, now),
      etaLabel:
        cycle.next_cycle_eta_ts != null && !running
          ? fmtEtaSeconds(cycle.next_cycle_eta_ts, now)
          : '—',
      wallLabel: fmtWall(cycle.wall_ms),
    };
  }, [cycle]);

  // ─── Loading / error states ─────────────────────────────────────────
  if (!loaded) {
    return (
      <div style={stripBaseStyle('idle')}>
        <Chip kind="amber" style={{ fontSize: 9 }}>
          {'\u25CC'} loading
        </Chip>
        <span style={detailStyle}>fetching cycle heartbeat…</span>
      </div>
    );
  }
  if (error || !cycle || !view) {
    return (
      <div style={stripBaseStyle('idle')}>
        <Chip kind="amber" style={{ fontSize: 9 }}>
          {'\u25CC'} awaiting
        </Chip>
        <span style={detailStyle}>{error || 'no cycle yet — orchestrator idle'}</span>
      </div>
    );
  }

  const tone = cycle.failed ? 'failed' : view.stale ? 'stale' : view.running ? 'running' : 'ok';

  return (
    <div style={stripBaseStyle(tone)}>
      <div style={leftClusterStyle}>
        <span style={runIdStyle(tone)}>
          {'\u25C7'} {cycle.run_id.toUpperCase()}
        </span>
        {cycle.mode && (
          <Chip kind="blue" style={{ fontSize: 9 }}>
            {cycle.mode.toUpperCase()}
          </Chip>
        )}
        {cycle.failed && (
          <Chip kind="red" style={{ fontSize: 9 }}>
            {'\u25CC'} FAILED
          </Chip>
        )}
        {!cycle.failed && view.stale && (
          <Chip kind="amber" style={{ fontSize: 9 }}>
            {'\u25CC'} STALE
          </Chip>
        )}
      </div>
      <div style={rightClusterStyle}>
        <Stat label="LAST" value={view.ageLabel} accent={view.stale ? 'amber' : 'fg'} />
        <Sep />
        <Stat label="SYM" value={String(cycle.symbols_scanned)} />
        <Sep />
        <Stat label="WALL" value={view.wallLabel} />
        <Sep />
        <Stat label="PLANS" value={String(cycle.plans_emitted)} />
        <Sep />
        <Stat label="ETA" value={view.etaLabel} />
        {cycle.failed && cycle.exception_class && (
          <>
            <Sep />
            <span style={{ ...detailStyle, color: 'var(--red-2)' }}>
              {cycle.exception_class}
            </span>
          </>
        )}
      </div>
    </div>
  );
}

// ─── Sub-renderers ─────────────────────────────────────────────────────

function Stat({
  label,
  value,
  accent = 'fg',
}: {
  label: string;
  value: string;
  accent?: 'fg' | 'amber';
}) {
  const color = accent === 'amber' ? 'var(--amber-2)' : 'var(--fg-1, #cdd5e0)';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 5 }}>
      <span
        className="mono"
        style={{
          fontSize: 9,
          color: 'var(--fg-4)',
          letterSpacing: '.18em',
        }}
      >
        {label}
      </span>
      <span
        className="mono"
        style={{ fontSize: 11, color, fontWeight: 600 }}
      >
        {value}
      </span>
    </span>
  );
}

function Sep() {
  return <span style={{ color: 'var(--fg-4)', opacity: 0.4 }}>·</span>;
}

// ─── Styles ─────────────────────────────────────────────────────────────

type Tone = 'ok' | 'running' | 'stale' | 'failed' | 'idle';

function stripBaseStyle(tone: Tone): React.CSSProperties {
  const borderColor =
    tone === 'failed'
      ? 'rgba(248,113,113,.45)'
      : tone === 'stale'
        ? 'rgba(251,191,36,.35)'
        : tone === 'running'
          ? 'rgba(34,211,238,.30)'
          : 'var(--border-soft)';
  const bg =
    tone === 'failed'
      ? 'rgba(248,113,113,.06)'
      : tone === 'stale'
        ? 'rgba(251,191,36,.05)'
        : 'rgba(255,255,255,.02)';
  return {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    padding: '8px 14px',
    border: `1px solid ${borderColor}`,
    borderRadius: 8,
    background: bg,
    marginBottom: 14,
    flexWrap: 'wrap',
  };
}

const leftClusterStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 8,
};

const rightClusterStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 8,
  flexWrap: 'wrap',
};

const detailStyle: React.CSSProperties = {
  fontFamily: 'JetBrains Mono, monospace',
  fontSize: 10,
  color: 'var(--fg-4)',
  letterSpacing: '.06em',
};

function runIdStyle(tone: Tone): React.CSSProperties {
  return {
    fontFamily: 'Share Tech Mono, monospace',
    fontSize: 12,
    letterSpacing: '.08em',
    color:
      tone === 'failed'
        ? 'var(--red-2)'
        : tone === 'stale'
          ? 'var(--amber-2)'
          : 'var(--accent)',
  };
}
