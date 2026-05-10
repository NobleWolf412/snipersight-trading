/**
 * MacroScoreTile — composite regime score (Phase 5 polish).
 *
 * Plan reference: peppy-sniffing-owl §5b — "Macro-score widget — already
 * in 3c — verify it appears on /scanner too." Was misdiagnosed as a
 * backend gap; the existing `/api/market/regime` already exposes the
 * composite `score` (0–100) and `composite` label. This tile just
 * renders them with a tone bucket.
 *
 * Layout (drops into existing .metric-tile grid)
 * ──────────────────────────────────────────────
 *   ┌── MACRO SCORE ─────────┐
 *   │  64.5                  │  ← color tinted by tone bucket
 *   │  BTC_DRIVE             │  ← composite label
 *   └────────────────────────┘
 *
 * Tone buckets (mirrors useMarketRegime visibility cutoffs)
 *   ≥75 = green (HIGH visibility)
 *   ≥50 = blue  (MEDIUM)
 *   ≥30 = amber (LOW)
 *   <30 = red   (very low / risk-off)
 *
 * Real-data wiring
 *   - Single fetch on mount via api.getMarketRegime(); the backend
 *     caches 60s already, so further client-side polling is unnecessary
 *     for a slow-moving macro signal.
 *   - On error or empty response → `◌ awaiting` chip in the sub-line,
 *     value renders as `—` in muted text. No fake numbers, ever.
 *
 * Synthetic-but-disclosed: none.
 *
 * Symmetry (CLAUDE.md §10 #3)
 *   - Direction-agnostic — macro regime is a composite, not directional.
 *
 * StrictMode safety
 *   - mounted flag captured in effect; cleanup flips it so a late resolve
 *     after unmount cannot setState on a torn-down node.
 */
import { useEffect, useState } from 'react';
import { api } from '@/utils/api';

interface RegimeShape {
  composite?: string;
  score?: number;
}

type Tone = 'green' | 'blue' | 'amber' | 'red';

function pickTone(score: number): Tone {
  if (score >= 75) return 'green';
  if (score >= 50) return 'blue';
  if (score >= 30) return 'amber';
  return 'red';
}

const TONE_COLOR: Record<Tone, string> = {
  green: 'var(--green-soft)',
  blue: 'var(--blue)',
  amber: 'var(--amber-2)',
  red: 'var(--red-2)',
};

export function MacroScoreTile() {
  const [data, setData] = useState<RegimeShape | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let mounted = true;
    api
      .getMarketRegime()
      .then((res) => {
        if (!mounted) return;
        if (res.error) {
          setError(res.error);
        } else if (res.data) {
          setData(res.data as RegimeShape);
        }
      })
      .catch((e) => {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : 'fetch failed');
      })
      .finally(() => {
        if (mounted) setLoaded(true);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const score = typeof data?.score === 'number' ? data.score : null;
  const composite = typeof data?.composite === 'string' ? data.composite.toUpperCase() : null;
  const tone: Tone | null = score == null ? null : pickTone(score);

  const valueText = score == null ? '—' : score.toFixed(1);
  const valueColor = tone ? TONE_COLOR[tone] : 'var(--fg-3)';

  let subText: React.ReactNode;
  if (error) {
    subText = (
      <>
        <span style={{ color: 'var(--amber)' }}>◌</span> awaiting · {error}
      </>
    );
  } else if (!loaded) {
    subText = (
      <>
        <span style={{ color: 'var(--amber)' }}>◌</span> loading
      </>
    );
  } else if (composite) {
    subText = composite;
  } else {
    subText = (
      <>
        <span style={{ color: 'var(--amber)' }}>◌</span> awaiting regime signal
      </>
    );
  }

  return (
    <div className="metric-tile">
      <div className="metric-label">Macro Score</div>
      <div className="metric-value" style={{ color: valueColor }}>
        {valueText}
      </div>
      <div className="metric-sub">{subText}</div>
    </div>
  );
}
