/**
 * MacroBand — "Cycle Compass · Macro Band" HUD strip.
 *
 * A read-only GUIDE showing where price sits in the Bitcoin 4-year halving
 * cycle (accumulation → markup → distribution → markdown). It is NOT a signal
 * and is deliberately NOT wired into trade scoring — the FYC→scoring hook
 * (`backend/strategy/smc/four_year_cycle.py::get_fyc_confluence_modifier`)
 * stays dormant by design (see decisions/2026-05-31__cascade-scalp-monoculture
 * -regime-compressed-saturation.md). This surface only mirrors the backend's
 * macro readout so the operator has cycle context while watching the bot.
 *
 * Layout
 *   // CYCLE COMPASS · MACRO BAND  [GUIDE]      MARKUP · BULLISH 74% · HALVING ~2.9y
 *   ┌ ACCUM ──┬──── MARKUP ────┬ DIST ┬ MARKDOWN ┐
 *   └──────────────▲ 41.9% ────────────────────────┘
 *   phase 38% · — neutral zone
 *
 * Real-data wiring
 *   - Single fetch on mount. The 4YC is date-anchored (computed from fixed
 *     historical anchors vs today), advancing ~0.07%/day — client polling is
 *     pointless, mirroring MacroScoreTile's single-fetch precedent. The
 *     backend also caches the readout.
 *   - On error / pre-load → muted strip with amber `◌` chip; no fake bands
 *     (CooldownsTile / KillZoneStrip pattern).
 *
 * Symmetry (CLAUDE.md §10 #3)
 *   - Direction-agnostic surface. Macro bias is a cycle-position readout, not
 *     a long/short signal, so there is no bull/bear pair to mirror.
 *
 * StrictMode safety
 *   - cancelled flag + cleanup, mirrors KillZoneStrip / MacroScoreTile.
 */
import { useEffect, useState } from 'react';
import { api, type BTCCycleContextData } from '@/utils/api';
import { Chip, type ChipKind } from './Chip';

// Phase segments on the 0–100% cycle scale (four_year_cycle.py PHASE_BOUNDARIES:
// ACCUMULATION 0–35, MARKUP 35–65, DISTRIBUTION 65–80, MARKDOWN 80–100).
const PHASE_SEGMENTS: Array<{ key: string; label: string; left: number; width: number; color: string }> = [
  { key: 'ACCUMULATION', label: 'ACCUM', left: 0, width: 35, color: '#60a5fa' },
  { key: 'MARKUP', label: 'MARKUP', left: 35, width: 30, color: '#22c55e' },
  { key: 'DISTRIBUTION', label: 'DIST', left: 65, width: 15, color: '#fbbf24' },
  { key: 'MARKDOWN', label: 'MARKDOWN', left: 80, width: 20, color: '#f87171' },
];

const PHASE_CHIP: Record<string, ChipKind> = {
  ACCUMULATION: 'blue',
  MARKUP: 'green',
  DISTRIBUTION: 'amber',
  MARKDOWN: 'red',
};

const BIAS_CHIP: Record<string, ChipKind> = {
  BULLISH: 'green',
  NEUTRAL: 'amber',
  BEARISH: 'red',
};

function fmtHalving(days: number | null | undefined): string {
  if (days == null || days <= 0) return '—';
  if (days < 365) return `~${days}d`;
  return `~${(days / 365).toFixed(1)}y`;
}

export function MacroBand() {
  const [data, setData] = useState<BTCCycleContextData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.getBTCCycleContext();
        if (cancelled) return;
        if (res.error) {
          setError(res.error);
        } else if (res.data?.data) {
          setData(res.data.data);
          setError(null);
        } else {
          setError('no data');
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'fetch failed');
      } finally {
        if (!cancelled) setLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error || !loaded || !data) {
    const reason = error ? `awaiting · ${error.slice(0, 48)}` : 'loading';
    return (
      <div
        className="mono"
        style={{
          marginBottom: 10,
          fontSize: 9,
          color: 'var(--amber)',
          letterSpacing: '.18em',
          textTransform: 'uppercase',
        }}
      >
        ◌ cycle compass · macro band · {reason}
      </div>
    );
  }

  const fyc = data.four_year_cycle;
  const phase = fyc.phase ?? 'UNKNOWN';
  const pos = Math.max(0, Math.min(100, fyc.cycle_position_pct ?? 0));
  const bias = fyc.macro_bias ?? 'NEUTRAL';
  const zone = fyc.zones?.is_danger_zone
    ? { kind: 'red' as ChipKind, label: '⚠ DANGER ZONE' }
    : fyc.zones?.is_opportunity_zone
    ? { kind: 'green' as ChipKind, label: '◎ OPPORTUNITY ZONE' }
    : { kind: undefined, label: '— NEUTRAL ZONE' };

  return (
    <div className="panel" style={{ marginBottom: 12, padding: '10px 12px' }}>
      {/* Header row: identity + GUIDE tag (left), macro readout chips (right) */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 8,
          justifyContent: 'space-between',
          marginBottom: 8,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            className="mono"
            style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.20em', textTransform: 'uppercase' }}
          >
            // CYCLE COMPASS · MACRO BAND
          </span>
          <Chip kind="cyan" style={{ fontSize: 8 }}>
            GUIDE
          </Chip>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <Chip kind={PHASE_CHIP[phase] ?? 'accent'}>{phase}</Chip>
          <Chip kind={BIAS_CHIP[bias] ?? 'amber'}>{bias}</Chip>
          <span className="mono" style={{ fontSize: 10, color: 'var(--fg-3)' }}>
            {fyc.confidence != null ? `${Math.round(fyc.confidence)}% CONF` : '—'}
          </span>
          <span className="mono" style={{ fontSize: 10, color: 'var(--fg-4)' }}>
            · HALVING {fmtHalving(data.halving?.days_until_halving)}
          </span>
        </div>
      </div>

      {/* The cycle band: four phase segments, active phase glows, playhead at position */}
      <div
        style={{
          position: 'relative',
          height: 26,
          border: '1px solid var(--border-soft)',
          borderRadius: 4,
          background: 'rgba(0,0,0,.35)',
          overflow: 'hidden',
        }}
      >
        {PHASE_SEGMENTS.map((seg) => {
          const active = seg.key === phase;
          return (
            <div
              key={seg.key}
              title={seg.key}
              style={{
                position: 'absolute',
                top: 4,
                bottom: 4,
                left: `${seg.left}%`,
                width: `${seg.width}%`,
                background: active
                  ? `linear-gradient(90deg, ${seg.color}55, ${seg.color}aa)`
                  : `${seg.color}1a`,
                border: `1px solid ${seg.color}${active ? 'cc' : '33'}`,
                borderRadius: 2,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: active ? `0 0 6px ${seg.color}88` : 'none',
                overflow: 'hidden',
              }}
            >
              {seg.width > 8 && (
                <span
                  className="mono"
                  style={{
                    fontSize: 8,
                    letterSpacing: '.12em',
                    color: active ? seg.color : 'var(--fg-4)',
                    fontWeight: active ? 700 : 400,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {seg.label}
                </span>
              )}
            </div>
          );
        })}
        {/* Playhead at current cycle position */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            left: `${pos}%`,
            width: 2,
            background: 'var(--accent)',
            boxShadow: '0 0 6px var(--accent)',
            zIndex: 2,
          }}
        />
      </div>

      {/* Sub-caption: cycle position, phase progress, zone tag */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          flexWrap: 'wrap',
          marginTop: 6,
        }}
      >
        <span
          className="mono"
          style={{ fontSize: 9, letterSpacing: '.16em', textTransform: 'uppercase', color: 'var(--fg-3)' }}
        >
          ▲ {pos.toFixed(1)}% INTO CYCLE
          {fyc.phase_progress_pct != null && (
            <span style={{ color: 'var(--fg-4)' }}> · phase {Math.round(fyc.phase_progress_pct)}%</span>
          )}
        </span>
        <Chip kind={zone.kind} style={{ fontSize: 8 }}>
          {zone.label}
        </Chip>
      </div>
    </div>
  );
}
