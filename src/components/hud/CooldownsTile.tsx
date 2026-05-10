/**
 * CooldownsTile — count + soonest-expiry of active trade cooldowns
 * (Phase 5 polish).
 *
 * Plan reference: peppy-sniffing-owl §3d / §5b — "Cooldown timer on
 * rejected symbols". Closes the deferred entry in Scanner.tsx docblock
 * §30 ("needs cooldown ttl"). Backend gap addressed via new
 * `/api/cooldowns` endpoint exposing CooldownManager.list_active().
 *
 * Layout (drops into existing .metric-tile grid)
 *   ┌── COOLDOWNS ───────────┐
 *   │  3                     │  ← active count (red ≥1, muted when 0)
 *   │  next: 2h 14m          │  ← soonest TTL or "none"
 *   └────────────────────────┘
 *
 * Real-data wiring
 *   - Polls /api/cooldowns every 15s. Cooldowns tick down by the second
 *     but they're 24h locks; per-second precision is unnecessary, so a
 *     coarser cadence keeps cost minimal while keeping the soonest-TTL
 *     label meaningfully accurate.
 *   - On error → muted `—` with amber `◌` chip; no fake counts.
 *
 * Synthetic-but-disclosed: none.
 *
 * Symmetry (CLAUDE.md §10 #3)
 *   - Direction-agnostic at the tile level. The underlying data carries
 *     direction per cooldown but this surface aggregates count.
 *
 * StrictMode safety
 *   - cancelled flag + setTimeout cleanup, mirrors CycleHeartbeat /
 *     UniversePanel pattern.
 */
import { useEffect, useMemo, useState } from 'react';
import { api, type ActiveCooldownsResponse } from '@/utils/api';

const POLL_MS = 15_000;

function fmtRemaining(s: number | null): string {
  if (s == null || s <= 0) return 'none';
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

export function CooldownsTile() {
  const [data, setData] = useState<ActiveCooldownsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      try {
        const res = await api.getActiveCooldowns();
        if (cancelled) return;
        if (res.error) {
          setError(res.error);
        } else if (res.data) {
          setData(res.data);
          setError(null);
        }
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'fetch failed');
      } finally {
        if (!cancelled) setLoaded(true);
        if (!cancelled) timer = setTimeout(tick, POLL_MS);
      }
    };

    tick();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  const view = useMemo(() => {
    if (!data) return null;
    return {
      count: data.count,
      nextLabel: fmtRemaining(data.next_expiry_seconds),
    };
  }, [data]);

  let valueNode: React.ReactNode;
  let subNode: React.ReactNode;
  let valueColor = 'var(--fg)';

  if (error) {
    valueNode = '—';
    subNode = (
      <>
        <span style={{ color: 'var(--amber)' }}>◌</span> awaiting · {error.slice(0, 32)}
      </>
    );
    valueColor = 'var(--fg-3)';
  } else if (!loaded || !view) {
    valueNode = '—';
    subNode = (
      <>
        <span style={{ color: 'var(--amber)' }}>◌</span> loading
      </>
    );
    valueColor = 'var(--fg-3)';
  } else {
    valueNode = view.count;
    valueColor = view.count > 0 ? 'var(--red-2)' : 'var(--fg-3)';
    subNode = view.count > 0 ? `next: ${view.nextLabel}` : 'none active';
  }

  return (
    <div className="metric-tile">
      <div className="metric-label">Cooldowns</div>
      <div className="metric-value" style={{ color: valueColor }}>
        {valueNode}
      </div>
      <div className="metric-sub">{subNode}</div>
    </div>
  );
}
