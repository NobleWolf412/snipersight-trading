/**
 * ConfluenceBreakdown — rolling factor-distribution panel (Phase 3g.ii.d)
 *
 * Plan reference: peppy-sniffing-owl §3e.
 *
 *   "NEW: Confluence Breakdown panel as a tab inside Bot Status (sibling
 *    to the Gauntlet view): rolling factor distribution stacked-bar over
 *    last N signals, sourced from /api/signals/confluence/distribution."
 *
 * Layout
 * ──────
 *   ┌───────────────────────────────────────────────────────────────┐
 *   │ ◇ CONFLUENCE DISTRIBUTION  · 184 SAMPLES · AVG 71.4         │
 *   │ ─────────────────────────────────────────────────────────── │
 *   │ STACKED BAR (avg_weighted_score per factor, sorted desc)    │
 *   │ ─────────────────────────────────────────────────────────── │
 *   │ // BY DIRECTION                                              │
 *   │   LONG  · 92 samples · avg 72.1 · synergy +4.2 · conflict -1.8│
 *   │   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓                       │
 *   │   SHORT · 92 samples · avg 70.7 · synergy +3.8 · conflict -2.0│
 *   │   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓                       │
 *   └───────────────────────────────────────────────────────────────┘
 *
 * Real-data wiring
 * ────────────────
 *   - Polls `/api/signals/confluence/distribution?n=200&direction=all`
 *     once on mount + every 30s (cheap-poll cadence — moderate-cost
 *     endpoint). The breakdown ring buffer on the backend is updated
 *     as scoring runs, so 30s is plenty for an at-a-glance trend
 *     surface.
 *   - Empty buffer (`sample_count===0`) renders the awaiting state with
 *     an amber `◌ awaiting` chip — same convention as the Gauntlet.
 *   - Surfaces `metadata.status !== 'OK'` and `warnings[]` via a strip
 *     above the stacked bar.
 *
 * Synthetic-but-disclosed: none. Component renders ONLY backend data.
 *
 * Symmetry (CLAUDE.md §10 #3)
 * ───────────────────────────
 *   - The `by_direction` field is always two entries (long + short).
 *     Both are rendered with identical chrome, side by side; only the
 *     accent color differs (green for long, red for short — a UI affordance,
 *     not a data branch).
 *   - Asymmetric sample counts are surfaced verbatim — that's a real
 *     signal of bias and is the whole reason the §10 #3 audit exists.
 *
 * Determinism for snapshots
 * ─────────────────────────
 *   - Factor list iteration order is the wire order (backend sorts by
 *     `-avg_weighted_score`).
 *   - No `Date.now`, no `toLocaleTimeString`. Sample-count and avg-score
 *     numbers are formatted with `.toFixed(1)`.
 *
 * StrictMode safety
 * ─────────────────
 *   - The polling loop captures a `cancelled` flag in the effect closure.
 *     React 18 dev double-invoke is tolerated (cancelled flag drops
 *     stale resolutions).
 */
import { useEffect, useState } from 'react';
import { api, type ConfluenceDistribution, type DirectionDistribution, type FactorContribution, type ResponseMetadata } from '@/utils/api';
import { Chip } from './Chip';
import { SectionHead } from './SectionHead';

// Polling cadence — distribution is moderate-cost; 30s is fine.
const POLL_MS = 30_000;

// Stable per-factor color palette. Keys mirror what the scorer emits
// (`structure`, `volume`, `momentum`, etc.). Anything not listed falls
// back to the neutral `--fg-3` tone.
const FACTOR_COLORS: Record<string, string> = {
  structure:   'var(--green-soft)',
  volume:      'var(--accent)',
  momentum:    '#7dd3fc',  // light blue
  trend:       '#a78bfa',  // purple
  smc:         '#fbbf24',  // amber
  regime:      '#f472b6',  // pink
  liquidity:   '#4ade80',
  sweep:       '#22d3ee',
  rsi:         '#facc15',
  macd:        '#fb923c',
};
function factorColor(name: string): string {
  return FACTOR_COLORS[name.toLowerCase()] ?? 'var(--fg-3)';
}

export function ConfluenceBreakdown() {
  const [dist, setDist] = useState<ConfluenceDistribution | null>(null);
  const [meta, setMeta] = useState<ResponseMetadata | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      const res = await api.getConfluenceDistribution(200, 'all');
      if (cancelled) return;
      setLoaded(true);
      if (res.error || !res.data) {
        setError(res.error || 'no response body');
        setDist(null);
      } else {
        setMeta(res.data.metadata);
        setWarnings(res.data.warnings ?? []);
        if (res.data.data) {
          setDist(res.data.data);
          setError(null);
        } else {
          setError(res.data.metadata.reason || 'distribution unavailable');
          setDist(null);
        }
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

  // ─── Empty / loading states ───────────────────────────────────────
  if (!loaded) {
    return (
      <section className="panel" style={{ padding: 14 }}>
        <SectionHead title="Confluence Distribution" right={<Chip kind="amber">{'\u25CC'} loading</Chip>} />
        <div
          className="mono"
          style={{
            padding: 18,
            textAlign: 'center',
            fontSize: 11,
            color: 'var(--fg-4)',
            letterSpacing: '.16em',
          }}
        >
          — fetching distribution —
        </div>
      </section>
    );
  }

  if (error || !dist) {
    return (
      <section className="panel" style={{ padding: 14 }}>
        <SectionHead
          title="Confluence Distribution"
          right={<Chip kind="amber">{'\u25CC'} {meta?.status ?? 'error'}</Chip>}
        />
        <div
          className="mono"
          style={{
            padding: 18,
            textAlign: 'center',
            fontSize: 11,
            color: 'var(--fg-4)',
            letterSpacing: '.10em',
          }}
        >
          — {error ?? 'no distribution data'} —
        </div>
      </section>
    );
  }

  if (dist.sample_count === 0) {
    return (
      <section className="panel" style={{ padding: 14 }}>
        <SectionHead title="Confluence Distribution" right={<Chip kind="amber">{'\u25CC'} awaiting</Chip>} />
        <div
          className="mono"
          style={{
            padding: 18,
            textAlign: 'center',
            fontSize: 11,
            color: 'var(--fg-4)',
            letterSpacing: '.16em',
            textTransform: 'uppercase',
          }}
        >
          — no scored signals yet · distribution buffer empty —
        </div>
      </section>
    );
  }

  // ─── Populated render ─────────────────────────────────────────────
  return (
    <section className="panel">
      <div className="sec-head">
        <div className="sec-title"><span className="dot" /> Confluence Distribution</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Chip>{`${dist.sample_count} SAMPLES · AVG ${dist.avg_total_score.toFixed(1)}`}</Chip>
          {meta?.status && meta.status !== 'OK' && (
            <Chip kind="amber">{'\u25CC'} {meta.status}</Chip>
          )}
        </div>
      </div>

      <div style={{ padding: '14px 18px' }}>
        {warnings.length > 0 && (
          <div
            className="mono"
            style={{
              marginBottom: 12,
              padding: '8px 12px',
              border: '1px solid var(--amber-border)',
              borderRadius: 6,
              background: 'var(--amber-bg)',
              fontSize: 10,
              color: 'var(--amber-2)',
              letterSpacing: '.08em',
            }}
          >
            {'\u26A0'} warnings: {warnings.join(' · ')}
          </div>
        )}

        {/* Aggregate stacked bar */}
        {renderStackedBar(dist.factors, 'AGGREGATE')}

        {/* Synergy / conflict summary */}
        <div
          className="mono"
          style={{
            display: 'flex',
            gap: 18,
            marginTop: 10,
            fontSize: 10,
            color: 'var(--fg-3)',
            letterSpacing: '.10em',
          }}
        >
          <span>SYNERGY <span style={{ color: 'var(--green-soft)', fontWeight: 700 }}>+{dist.avg_synergy_bonus.toFixed(1)}</span></span>
          <span>CONFLICT <span style={{ color: 'var(--red-2)', fontWeight: 700 }}>{dist.avg_conflict_penalty.toFixed(1)}</span></span>
        </div>

        {/* Per-direction breakdown — symmetry standing-fix surface */}
        <div
          className="mono"
          style={{
            marginTop: 18,
            paddingTop: 12,
            borderTop: '1px dashed var(--border-soft)',
            fontSize: 9,
            color: 'var(--fg-4)',
            letterSpacing: '.20em',
            marginBottom: 8,
          }}
        >
          // BY DIRECTION
        </div>
        {dist.by_direction.map((bd) => renderDirectionRow(bd))}
      </div>
    </section>
  );
}

// ─── Subviews ────────────────────────────────────────────────────────

function renderStackedBar(factors: FactorContribution[], label: string) {
  const total = factors.reduce((s, f) => s + Math.max(0, f.avg_weighted_score), 0);
  if (total === 0) {
    return (
      <div
        className="mono"
        style={{ fontSize: 10, color: 'var(--fg-4)', letterSpacing: '.10em' }}
      >
        {label} — no contribution data
      </div>
    );
  }
  return (
    <div>
      <div
        className="mono"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 6,
          fontSize: 9,
          color: 'var(--fg-4)',
          letterSpacing: '.18em',
        }}
      >
        <span>{label}</span>
        <span>{total.toFixed(1)} TOTAL</span>
      </div>
      {/* Stacked bar */}
      <div
        style={{
          display: 'flex',
          height: 18,
          width: '100%',
          borderRadius: 3,
          overflow: 'hidden',
          border: '1px solid var(--border-soft)',
          background: 'rgba(0,0,0,.35)',
        }}
      >
        {factors.map((f) => {
          const pct = (Math.max(0, f.avg_weighted_score) / total) * 100;
          if (pct < 0.5) return null;
          return (
            <div
              key={f.name}
              title={`${f.name} · avg ${f.avg_weighted_score.toFixed(2)} · ${pct.toFixed(1)}%`}
              style={{
                width: `${pct}%`,
                background: factorColor(f.name),
                opacity: 0.85,
              }}
            />
          );
        })}
      </div>
      {/* Legend rows */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
          gap: 4,
          marginTop: 8,
        }}
      >
        {factors.map((f) => (
          <div
            key={f.name}
            className="mono"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 9,
              color: 'var(--fg-3)',
              letterSpacing: '.06em',
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                background: factorColor(f.name),
                borderRadius: 1,
                flexShrink: 0,
              }}
            />
            <span style={{ textTransform: 'uppercase', fontWeight: 700 }}>{f.name}</span>
            <span style={{ marginLeft: 'auto', color: 'var(--fg-2)' }}>
              {f.avg_weighted_score.toFixed(1)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function renderDirectionRow(bd: DirectionDistribution) {
  const accent = bd.direction === 'long' ? 'var(--green-soft)' : 'var(--red-2)';
  return (
    <div
      key={bd.direction}
      style={{
        marginTop: 8,
        padding: '8px 10px',
        border: '1px solid var(--border-soft)',
        borderRadius: 4,
        background: 'rgba(255,255,255,.02)',
      }}
    >
      <div
        className="mono"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 12,
          fontSize: 10,
          color: 'var(--fg-3)',
          letterSpacing: '.10em',
          marginBottom: 6,
        }}
      >
        <span style={{ color: accent, fontWeight: 700, letterSpacing: '.16em' }}>
          {bd.direction.toUpperCase()}
        </span>
        <span>{bd.sample_count} samples</span>
        <span>avg <span style={{ color: 'var(--fg-2)', fontWeight: 700 }}>{bd.avg_total_score.toFixed(1)}</span></span>
        <span>synergy <span style={{ color: 'var(--green-soft)' }}>+{bd.avg_synergy_bonus.toFixed(1)}</span></span>
        <span>conflict <span style={{ color: 'var(--red-2)' }}>{bd.avg_conflict_penalty.toFixed(1)}</span></span>
      </div>
      {bd.sample_count > 0 ? (
        renderStackedBar(bd.factors, '')
      ) : (
        <div
          className="mono"
          style={{ fontSize: 10, color: 'var(--fg-4)', letterSpacing: '.10em' }}
        >
          — no {bd.direction} samples in window —
        </div>
      )}
    </div>
  );
}

export default ConfluenceBreakdown;
