/**
 * CycleAuditStrip — Scanner page §11 cycle observability surface (3a').
 *
 * Renders one row with four data points:
 *   1. run_id of the most-recent cycle
 *   2. bottleneck_stage (the stage with the highest rejection count)
 *   3. wall_ms with comparison to the prior-5 median (relative metric
 *      per §16 rubric 5 — never absolute thresholds)
 *   4. audit status — OK | DEGRADED — sourced from the envelope metadata
 *      of /api/cycles/last?include_audit=true. DEGRADED implies the
 *      cycle-heartbeat drift detector flagged something (collapsed
 *      bottleneck, gap, etc.) and surfaces the warnings inline.
 *
 * Data sources:
 *   - api.getLastCycle({ include_audit: true }) — primary (poll 5s)
 *   - api.getCyclesHistory(5) — for the prior-5 median (poll 30s; the
 *     median doesn't shift fast enough to require tighter cadence)
 *
 * StrictMode-safe: cancelled flag + timer Set, same pattern as
 * CycleHeartbeat / ScanController.
 *
 * Why a sibling of CycleHeartbeat instead of an extension?
 *   - CycleHeartbeat is mounted on /bot/status and renders a different
 *     visual chrome (full ASCII frame). The Scanner page asked for a
 *     compact strip with audit-specific signals.
 *   - Extending CycleHeartbeat with an `audit` mode toggle was the other
 *     option; the duplication here is intentional to keep each surface's
 *     responsibilities legible. Both components hit the same backend
 *     endpoint family so shape drift is bounded.
 *
 * Direction-agnostic — cycle metadata is loop-level, no bull/bear split.
 */
import { useEffect, useMemo, useState } from 'react';
import { api } from '@/utils/api';
import { Chip } from './Chip';

const POLL_MS = 5_000;
const HISTORY_POLL_MS = 30_000;
// Number of prior cycles to compute the median against. 5 is the briefing
// spec ("wall_ms vs prior-5 median") — large enough to smooth noise, small
// enough that a regime shift surfaces within ~10 cycles instead of being
// drowned by stale outliers.
const HISTORY_N = 5;

// Cycle history endpoint isn't wrapped in api.ts — we hit it directly.
async function fetchCycleHistory(n: number): Promise<Array<{ wall_ms: number | null }>> {
  // Direct fetch to keep this strip self-contained without forcing a new
  // api.ts method. Same fetch path as the proxied /api/* routes. We treat
  // any non-2xx / non-JSON / shape mismatch as "no history available"
  // and let the strip render without the median band.
  try {
    const r = await fetch(`/api/cycles/history?n=${n}`);
    if (!r.ok) throw new Error(`history ${r.status}`);
    const ct = r.headers.get('content-type') ?? '';
    if (!ct.includes('application/json')) throw new Error('history non-JSON');
    const env = await r.json();
    if (Array.isArray(env?.data)) return env.data as Array<{ wall_ms: number | null }>;
    return [];
  } catch (e) {
    console.warn('[CycleAuditStrip] history fetch failed:', e);
    return [];
  }
}

function median(values: number[]): number | null {
  const finite = values.filter((v) => Number.isFinite(v));
  if (finite.length === 0) return null;
  const sorted = [...finite].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

function fmtWall(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

interface CycleLite {
  run_id: string;
  mode: string | null;
  wall_ms: number | null;
  bottleneck_stage: string | null;
  failed: boolean;
  exception_class: string | null;
}

interface AuditMeta {
  status: 'OK' | 'DEGRADED' | 'PARTIAL' | string;
  warnings: string[];
}

export function CycleAuditStrip() {
  const [cycle, setCycle] = useState<CycleLite | null>(null);
  const [audit, setAudit] = useState<AuditMeta | null>(null);
  const [history, setHistory] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  // Latest-cycle poll loop (5s).
  useEffect(() => {
    let cancelled = false;
    const timers = new Set<ReturnType<typeof setTimeout>>();

    const schedule = (fn: () => void, ms: number) => {
      const t = setTimeout(() => {
        timers.delete(t);
        if (cancelled) return;
        fn();
      }, ms);
      timers.add(t);
    };

    const tick = async () => {
      try {
        const res = await api.getLastCycle({ include_audit: true });
        if (cancelled) return;
        setLoaded(true);
        if (res.error || !res.data) {
          setError(res.error || 'no response body');
          setCycle(null);
          setAudit(null);
        } else if (res.data.data) {
          const c = res.data.data;
          setCycle({
            run_id: c.run_id,
            mode: c.mode ?? null,
            wall_ms: c.wall_ms ?? null,
            bottleneck_stage: c.bottleneck_stage ?? null,
            failed: c.failed,
            exception_class: c.exception_class ?? null,
          });
          setAudit({
            status: res.data.metadata?.status ?? 'OK',
            warnings: Array.isArray(res.data.warnings) ? res.data.warnings : [],
          });
          setError(null);
        } else {
          setError(res.data.metadata?.reason ?? 'cycle unavailable');
          setCycle(null);
          setAudit({
            status: res.data.metadata?.status ?? 'OK',
            warnings: Array.isArray(res.data.warnings) ? res.data.warnings : [],
          });
        }
      } catch (e) {
        console.warn('[CycleAuditStrip] last-cycle poll error:', e);
        if (!cancelled) setError(String(e));
      } finally {
        if (!cancelled) schedule(() => void tick(), POLL_MS);
      }
    };

    void tick();
    return () => {
      cancelled = true;
      for (const t of timers) clearTimeout(t);
    };
  }, []);

  // History poll loop (30s) — median drift is slow.
  useEffect(() => {
    let cancelled = false;
    const timers = new Set<ReturnType<typeof setTimeout>>();
    const schedule = (fn: () => void, ms: number) => {
      const t = setTimeout(() => {
        timers.delete(t);
        if (cancelled) return;
        fn();
      }, ms);
      timers.add(t);
    };

    const tick = async () => {
      const rows = await fetchCycleHistory(HISTORY_N);
      if (cancelled) return;
      const walls = rows
        .map((r) => r.wall_ms)
        .filter((v): v is number => typeof v === 'number' && Number.isFinite(v));
      setHistory(walls);
      if (!cancelled) schedule(() => void tick(), HISTORY_POLL_MS);
    };

    void tick();
    return () => {
      cancelled = true;
      for (const t of timers) clearTimeout(t);
    };
  }, []);

  const view = useMemo(() => {
    if (!cycle) return null;
    const med = median(history);
    let wallVsMedian: string | null = null;
    if (med != null && cycle.wall_ms != null && med > 0) {
      const delta = ((cycle.wall_ms - med) / med) * 100;
      const sign = delta >= 0 ? '+' : '';
      wallVsMedian = `${fmtWall(med)} median (${sign}${delta.toFixed(0)}%)`;
    }
    return {
      wallLabel: fmtWall(cycle.wall_ms),
      wallVsMedian,
    };
  }, [cycle, history]);

  // ─── Render ────────────────────────────────────────────────────────────
  // Stable shape across all states (loading / error / cold / running)
  // so the layout doesn't jump as data arrives. §11 — surface what's
  // available, mark gaps explicitly, never silent.

  if (!loaded) {
    return (
      <StripFrame>
        <Chip kind="amber">◌ LOADING</Chip>
        <span style={detailStyle}>fetching cycle audit…</span>
      </StripFrame>
    );
  }

  if (error || !cycle) {
    return (
      <StripFrame>
        <Chip kind="amber">◌ AWAITING</Chip>
        <span style={detailStyle}>{error || 'no cycle yet — orchestrator idle'}</span>
      </StripFrame>
    );
  }

  const isDegraded = audit?.status === 'DEGRADED' || cycle.failed;

  return (
    <StripFrame degraded={isDegraded}>
      <Chip kind={cycle.failed ? 'red' : isDegraded ? 'amber' : 'green'}>
        {cycle.failed ? '✕' : isDegraded ? '◌' : '●'}{' '}
        {cycle.run_id.slice(0, 8).toUpperCase()}
      </Chip>
      <span style={detailStyle}>
        {cycle.mode?.toUpperCase() ?? '—'} · wall {view?.wallLabel ?? '—'}
        {view?.wallVsMedian && (
          <span style={{ color: 'var(--fg-4)' }}> · {view.wallVsMedian}</span>
        )}
      </span>
      <span style={{ ...detailStyle, color: 'var(--fg-4)' }}>
        bottleneck · {cycle.bottleneck_stage ?? 'none'}
      </span>
      <Chip kind={isDegraded ? 'amber' : 'green'}>
        {isDegraded ? '◌ DEGRADED' : '● OK'}
      </Chip>
      {audit?.warnings && audit.warnings.length > 0 && (
        <span style={{ ...detailStyle, color: 'var(--amber)' }}>
          {audit.warnings.slice(0, 2).join(' · ')}
          {audit.warnings.length > 2 ? '…' : ''}
        </span>
      )}
    </StripFrame>
  );
}

// ─── Tiny local atoms ─────────────────────────────────────────────────────

const detailStyle: React.CSSProperties = {
  fontFamily: 'JetBrains Mono, monospace',
  fontSize: 10,
  color: 'var(--fg-3)',
  letterSpacing: '.12em',
  textTransform: 'uppercase',
};

function StripFrame({
  children,
  degraded = false,
}: {
  children: React.ReactNode;
  degraded?: boolean;
}) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 12,
        alignItems: 'center',
        flexWrap: 'wrap',
        padding: '8px 14px',
        border: `1px solid ${degraded ? 'var(--amber-border, rgba(251,191,36,.35))' : 'var(--border-soft)'}`,
        borderRadius: 4,
        background: degraded ? 'rgba(251,191,36,.05)' : 'rgba(0,0,0,.35)',
      }}
    >
      {children}
    </div>
  );
}
