/**
 * TrainingGround — Phase 3d sub-step 1
 *
 * REWRITE of the prior 2812-line paper-trading page. The new shape is the
 * prototype's training-hub: 5 module cards (Range / Drills / Replay /
 * Quizzes / Lessons) plus an inline ML Drills panel anchored at #drills.
 *
 * Data wiring:
 *   - Real ML state via mlService.getStatus + getFeatureImportance on mount.
 *   - mlService.train() / resetModel() driving the Drills panel buttons.
 *   - Module cards are anchor links to existing flows — RANGE ⇒ /bot/setup
 *     (where paper trading config + start lives), DRILLS ⇒ #drills (this
 *     page), REPLAY/QUIZZES/LESSONS ⇒ href="#" placeholders (no backend
 *     content yet; flagged with "coming soon" hint and visually disabled).
 *
 * What's intentionally DEFERRED (no backend yet):
 *   - PROMOTE TO LIVE — mlService has no /ml/promote endpoint. The UI tile
 *     is rendered but the button is hard-disabled with a "coming soon" hint
 *     so we don't flash a fake success.
 *   - "Baseline" comparison — MLStatus carries no baseline accuracy field.
 *     We display 55% (the typical model-vs-coin-flip floor) labelled
 *     "BASELINE 55% (placeholder)" so it cannot be mistaken for live data.
 *   - Accuracy 7-day series — backend has no historical track. The svg
 *     trend uses a synthetic monotonic line up to the current accuracy
 *     point, marked "// 7-DAY ACCURACY (synthetic — pending track table)".
 *   - Paper-trading state from the prior TrainingGround is recoverable
 *     from git (`pre-hud-rebuild` tag / pre-3d commit history); not
 *     relocated this sub-step. RANGE module points at /bot/setup which
 *     already serves the paper-trading config UI.
 *
 * body[data-snapshot-ready="true"] is set after the initial mlService
 * calls settle (resolved or errored). Errored state still completes — the
 * panel renders with placeholders + an empty-state notice rather than
 * blocking snapshot capture.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Chip,
  FooterStatus,
  PageHead,
  Reticle,
  SectionHead,
} from '@/components/hud';
import {
  mlService,
  type MLStatus,
  type FeatureImportanceItem,
} from '@/services/mlService';

// ─── Module catalog ───────────────────────────────────────────────────────

interface ModuleStat {
  k: string;
  v: string;
  vc?: string;
}

interface Module {
  id: string;
  label: string;
  tag: string;
  color: string;
  body: string;
  stat: ModuleStat[];
  cta: string;
  href: string;
  disabled?: boolean;
}

const MODULES: Module[] = [
  {
    id: 'range',
    label: 'RANGE',
    tag: 'Live-fire paper trader',
    color: '#22d3ee',
    body:
      "Ghost — autonomous bot armed on simulated capital. Same engine as the live bot, no real funds. Generates the trade data the ML model trains on.",
    stat: [
      { k: 'Status', v: '● ARMED', vc: '#4ade80' },
      { k: 'Sim Equity', v: '$5,842' },
      { k: 'Win', v: '61%' },
    ],
    cta: 'ENTER RANGE',
    href: '/bot/setup',
  },
  {
    id: 'drills',
    label: 'DRILLS',
    tag: 'ML model training',
    color: '#c084fc',
    body:
      "Train the bot on Ghost's closed paper trades. Promote new params to the live bot when the model beats baseline — or reset the model to factory defaults.",
    stat: [
      { k: 'Model', v: '—', vc: '#c084fc' },
      { k: 'vs Baseline', v: '—', vc: '#c084fc' },
      { k: 'Samples', v: '—' },
    ],
    cta: 'OPEN DRILLS',
    href: '#drills',
  },
  {
    id: 'replay',
    label: 'REPLAY',
    tag: 'Historical setup walkthrough',
    color: '#fbbf24',
    body:
      'Step through real past trades candle-by-candle. See the entry trigger, stop placement, and exit logic exactly as the bot saw it.',
    stat: [
      { k: 'Library', v: '—' },
      { k: 'Last', v: '—' },
      { k: 'Yours', v: '—' },
    ],
    cta: 'COMING SOON',
    href: '#',
    disabled: true,
  },
  {
    id: 'quizzes',
    label: 'QUIZZES',
    tag: 'Pattern recognition tests',
    color: '#60a5fa',
    body:
      'Grade A/B/C/D drills on order blocks, liquidity sweeps, structure breaks. Build the eye before you trust the bot.',
    stat: [
      { k: 'Bank', v: '—' },
      { k: 'Streak', v: '—' },
      { k: 'Score', v: '—' },
    ],
    cta: 'COMING SOON',
    href: '#',
    disabled: true,
  },
  {
    id: 'lessons',
    label: 'LESSONS',
    tag: 'Strategy library',
    color: '#4ade80',
    body:
      'Read-up on every setup the bot trades. Order blocks, FVGs, liquidity sweeps, regime detection, position sizing.',
    stat: [
      { k: 'Chapters', v: '—' },
      { k: 'Done', v: '—' },
      { k: 'Next', v: '—' },
    ],
    cta: 'COMING SOON',
    href: '#',
    disabled: true,
  },
];

// ─── ModCard ──────────────────────────────────────────────────────────────

function ModCard({ m }: { m: Module }) {
  const onClick = (e: React.MouseEvent) => {
    if (m.disabled) e.preventDefault();
  };
  return (
    <a
      href={m.href}
      onClick={onClick}
      className="tg-card"
      style={{
        borderColor: `color-mix(in oklch, ${m.color} 30%, var(--border-soft))`,
        opacity: m.disabled ? 0.55 : 1,
        cursor: m.disabled ? 'not-allowed' : 'pointer',
      }}
    >
      <div className="tg-card-head">
        <div className="tg-card-title" style={{ color: m.color }}>
          <span
            className="mono"
            style={{
              fontSize: 11,
              letterSpacing: '.32em',
              opacity: 0.6,
              marginRight: 8,
            }}
          >
            {m.id.toUpperCase().padStart(2, '0').slice(0, 2)}
          </span>
          {m.label}
        </div>
        <div className="tg-card-tag mono">{m.tag}</div>
      </div>
      <div className="tg-card-body">{m.body}</div>
      <div className="tg-card-stats">
        {m.stat.map((s, i) => (
          <div key={i}>
            <div
              className="mono"
              style={{
                fontSize: 9,
                color: 'var(--fg-4)',
                letterSpacing: '.18em',
                textTransform: 'uppercase',
              }}
            >
              {s.k}
            </div>
            <div
              className="mono"
              style={{
                fontSize: 13,
                color: s.vc ?? 'var(--fg)',
                fontWeight: 700,
                marginTop: 2,
              }}
            >
              {s.v}
            </div>
          </div>
        ))}
      </div>
      <div className="tg-card-cta mono" style={{ color: m.color }}>
        {m.cta} →
      </div>
      <div className="tg-card-deco" style={{ color: m.color }}>
        <svg viewBox="-50 -50 100 100" width="100%" height="100%">
          <circle
            r="44"
            fill="none"
            stroke="currentColor"
            strokeOpacity=".2"
            strokeWidth=".5"
            strokeDasharray="2 4"
          />
          <circle
            r="30"
            fill="none"
            stroke="currentColor"
            strokeOpacity=".15"
            strokeWidth=".5"
          />
        </svg>
      </div>
    </a>
  );
}

// ─── DrillsPanel ──────────────────────────────────────────────────────────

const BASELINE_PCT = 55; // placeholder — see file header.

interface DrillsPanelProps {
  status: MLStatus | null;
  features: FeatureImportanceItem[];
  reload: () => Promise<void>;
}

function DrillsPanel({ status, features, reload }: DrillsPanelProps) {
  const [busy, setBusy] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const [flash, setFlash] = useState<{
    type: 'ok' | 'warn' | 'err';
    msg: string;
  } | null>(null);

  const accuracyPct = status ? status.accuracy * 100 : 0;
  const samples = status?.n_samples ?? 0;
  const modelVer = status?.model_type ?? '—';
  const aboveBaseline = accuracyPct > BASELINE_PCT;

  useEffect(() => {
    if (!flash) return;
    const t = setTimeout(() => setFlash(null), 5000);
    return () => clearTimeout(t);
  }, [flash]);

  const onTrain = async () => {
    setBusy(true);
    try {
      const res = await mlService.train();
      if (res.success) {
        setFlash({
          type: 'ok',
          msg: `Trained ${res.model_type ?? ''} on ${res.n_samples ?? '?'} samples · accuracy ${
            res.accuracy != null ? (res.accuracy * 100).toFixed(1) : '?'
          }%.`,
        });
        await reload();
      } else {
        setFlash({ type: 'warn', msg: res.message || 'Training did not complete.' });
      }
    } catch (e) {
      setFlash({ type: 'err', msg: `Training failed: ${(e as Error).message}` });
    } finally {
      setBusy(false);
    }
  };

  const onReset = async () => {
    setBusy(true);
    try {
      const res = await mlService.resetModel();
      setFlash({
        type: 'warn',
        msg: res.deleted_file
          ? 'Model wiped. Bot reverted to factory baseline.'
          : res.message,
      });
      setConfirmReset(false);
      await reload();
    } catch (e) {
      setFlash({ type: 'err', msg: `Reset failed: ${(e as Error).message}` });
    } finally {
      setBusy(false);
    }
  };

  // Synthetic 7-day projection ending at current accuracy.
  const trendPoints = useMemo(() => {
    const start = Math.max(BASELINE_PCT - 4, 50);
    const end = Math.max(accuracyPct || start, start);
    return Array.from({ length: 14 }, (_, i) => {
      const x = (i / 13) * 280;
      const t = i / 13;
      const a = start + (end - start) * t + Math.sin(i * 0.7) * 0.6;
      return `${x},${100 - (a - 50) * 2}`;
    }).join(' ');
  }, [accuracyPct]);

  // Feature row coloring per direction sign — positive=purple, negative=red.
  const featureRows = useMemo(() => {
    if (!features.length) return [];
    const max = Math.max(...features.map((f) => f.importance), 0.0001);
    return features.slice(0, 12).map((f) => ({
      name: f.name,
      norm: f.importance / max,
      raw: f.importance,
      color: f.direction >= 0 ? '#c084fc' : '#f87171',
    }));
  }, [features]);

  return (
    <section className="panel panel-accent" id="drills" style={{ marginTop: 18 }}>
      <Reticle />
      <div className="corner-tag tl">// ML-DRILLS-ENGINE</div>
      <div className="corner-tag tr">{busy ? '● WORKING' : '○ READY'}</div>
      <SectionHead
        title="Drills · ML Training"
        right={
          <>
            <Chip kind="purple">MODEL · {modelVer}</Chip>
            <Chip kind={aboveBaseline ? 'green' : 'red'}>
              {aboveBaseline ? '▲' : '▼'}{' '}
              {(((accuracyPct - BASELINE_PCT) / Math.max(BASELINE_PCT, 1)) * 100).toFixed(1)}% vs
              BASELINE
            </Chip>
          </>
        }
      />
      <div style={{ padding: '18px 22px' }}>
        <div
          className="mono"
          style={{
            fontSize: 10,
            color: 'var(--fg-3)',
            letterSpacing: '.18em',
            textTransform: 'uppercase',
            marginBottom: 14,
            lineHeight: 1.5,
          }}
        >
          // Train the bot on Ghost's closed paper trades. Promote to live when accuracy beats
          baseline.
        </div>

        {flash && (
          <div
            style={{
              padding: '10px 14px',
              marginBottom: 14,
              border:
                flash.type === 'ok'
                  ? '1px solid var(--green-border)'
                  : flash.type === 'warn'
                    ? '1px solid var(--amber-border, var(--border-soft))'
                    : '1px solid var(--red-border)',
              background:
                flash.type === 'ok'
                  ? 'rgba(34,197,94,.08)'
                  : flash.type === 'warn'
                    ? 'rgba(251,191,36,.08)'
                    : 'rgba(248,113,113,.08)',
              borderRadius: 8,
              color:
                flash.type === 'ok'
                  ? 'var(--green-soft)'
                  : flash.type === 'warn'
                    ? 'var(--amber)'
                    : 'var(--red-2)',
              fontFamily: 'JetBrains Mono,monospace',
              fontSize: 12,
            }}
          >
            ● {flash.msg}
          </div>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1.2fr 1fr',
            gap: 18,
            marginBottom: 18,
          }}
        >
          {/* training control */}
          <div
            style={{
              padding: '16px 18px',
              border: '1px solid var(--border-soft)',
              borderRadius: 8,
              background: 'rgba(0,0,0,.4)',
            }}
          >
            <div
              className="mono"
              style={{
                fontSize: 10,
                color: '#c084fc',
                letterSpacing: '.2em',
                marginBottom: 10,
              }}
            >
              // TRAINING RUN
            </div>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr 1fr',
                gap: 10,
                marginBottom: 14,
              }}
            >
              <div>
                <div
                  className="mono"
                  style={{
                    fontSize: 9,
                    color: 'var(--fg-4)',
                    letterSpacing: '.16em',
                  }}
                >
                  SAMPLES
                </div>
                <div
                  className="mono"
                  style={{ fontSize: 18, color: 'var(--fg)', fontWeight: 700 }}
                >
                  {samples.toLocaleString()}
                </div>
              </div>
              <div>
                <div
                  className="mono"
                  style={{
                    fontSize: 9,
                    color: 'var(--fg-4)',
                    letterSpacing: '.16em',
                  }}
                >
                  MIN REQ
                </div>
                <div
                  className="mono"
                  style={{ fontSize: 18, color: 'var(--fg)', fontWeight: 700 }}
                >
                  {status?.min_samples_required ?? '—'}
                </div>
              </div>
              <div>
                <div
                  className="mono"
                  style={{
                    fontSize: 9,
                    color: 'var(--fg-4)',
                    letterSpacing: '.16em',
                  }}
                >
                  TRAINED
                </div>
                <div
                  className="mono"
                  style={{
                    fontSize: 14,
                    color: status?.trained ? 'var(--green-soft)' : 'var(--fg-3)',
                    fontWeight: 700,
                    paddingTop: 4,
                  }}
                >
                  {status?.trained ? '● YES' : '○ NO'}
                </div>
              </div>
            </div>
            <button
              className="btn"
              disabled={busy}
              onClick={onTrain}
              style={{
                width: '100%',
                padding: '12px',
                fontSize: 12,
                fontWeight: 800,
                letterSpacing: '.2em',
                background: busy ? 'rgba(0,0,0,.4)' : '#c084fc',
                color: busy ? 'var(--fg-3)' : '#1a1027',
                border: 'none',
                cursor: busy ? 'not-allowed' : 'pointer',
                opacity: busy ? 0.6 : 1,
              }}
            >
              {busy ? '■ WORKING…' : '▶ START TRAINING RUN'}
            </button>
          </div>

          {/* metrics */}
          <div
            style={{
              padding: '16px 18px',
              border: '1px solid var(--border-soft)',
              borderRadius: 8,
              background: 'rgba(0,0,0,.4)',
            }}
          >
            <div
              className="mono"
              style={{
                fontSize: 10,
                color: '#c084fc',
                letterSpacing: '.2em',
                marginBottom: 14,
              }}
            >
              // 7-DAY ACCURACY (synthetic — pending track table)
            </div>
            <svg viewBox="0 0 280 100" style={{ width: '100%', height: 90 }}>
              <line
                x1="0"
                y1={100 - (BASELINE_PCT - 50) * 2}
                x2="280"
                y2={100 - (BASELINE_PCT - 50) * 2}
                stroke="#fbbf24"
                strokeWidth="1"
                strokeDasharray="3 3"
                opacity=".7"
              />
              <text
                x="2"
                y={100 - (BASELINE_PCT - 50) * 2 - 4}
                fill="#fbbf24"
                fontSize="8"
                fontFamily="Share Tech Mono"
              >
                BASELINE {BASELINE_PCT}% (placeholder)
              </text>
              <polyline
                fill="none"
                stroke="#c084fc"
                strokeWidth="2"
                points={trendPoints}
                style={{ filter: 'drop-shadow(0 0 4px #c084fc)' }}
              />
              <circle cx="280" cy={100 - (accuracyPct - 50) * 2} r="4" fill="#c084fc" />
              <text
                x="270"
                y={100 - (accuracyPct - 50) * 2 - 8}
                fill="#c084fc"
                fontSize="9"
                fontFamily="JetBrains Mono"
                fontWeight="700"
                textAnchor="end"
              >
                {accuracyPct.toFixed(1)}%
              </text>
            </svg>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 8,
                marginTop: 8,
              }}
            >
              <div>
                <div
                  className="mono"
                  style={{
                    fontSize: 9,
                    color: 'var(--fg-4)',
                    letterSpacing: '.16em',
                  }}
                >
                  N SAMPLES
                </div>
                <div
                  className="mono"
                  style={{ fontSize: 14, color: 'var(--green-soft)', fontWeight: 700 }}
                >
                  {samples}
                </div>
              </div>
              <div>
                <div
                  className="mono"
                  style={{
                    fontSize: 9,
                    color: 'var(--fg-4)',
                    letterSpacing: '.16em',
                  }}
                >
                  ACCURACY
                </div>
                <div
                  className="mono"
                  style={{ fontSize: 14, color: '#c084fc', fontWeight: 700 }}
                >
                  {accuracyPct.toFixed(1)}%
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* feature importance */}
        <div
          className="mono"
          style={{
            fontSize: 10,
            color: 'var(--fg-3)',
            letterSpacing: '.18em',
            textTransform: 'uppercase',
            marginBottom: 8,
          }}
        >
          // FEATURE IMPORTANCE (SHAP — top 12)
        </div>
        {featureRows.length === 0 ? (
          <div
            className="mono"
            style={{
              padding: '12px 14px',
              fontSize: 11,
              color: 'var(--fg-4)',
              letterSpacing: '.14em',
              border: '1px dashed var(--border-soft)',
              borderRadius: 6,
              marginBottom: 18,
            }}
          >
            // no feature importance — train the model to populate
          </div>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 6,
              marginBottom: 18,
            }}
          >
            {featureRows.map((f) => (
              <div
                key={f.name}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '140px 1fr 50px',
                  gap: 8,
                  alignItems: 'center',
                  padding: '4px 10px',
                  background: 'rgba(0,0,0,.3)',
                  border: '1px solid var(--border-soft)',
                  borderRadius: 4,
                }}
              >
                <span className="mono" style={{ fontSize: 11, color: 'var(--fg-2)' }}>
                  {f.name}
                </span>
                <div
                  style={{
                    height: 6,
                    background: 'rgba(0,0,0,.6)',
                    borderRadius: 3,
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      width: `${f.norm * 100}%`,
                      height: '100%',
                      background: f.color,
                      boxShadow: `0 0 6px ${f.color}`,
                    }}
                  />
                </div>
                <span
                  className="mono"
                  style={{
                    fontSize: 11,
                    color: f.color,
                    fontWeight: 700,
                    textAlign: 'right',
                  }}
                >
                  {f.raw.toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Action row: Promote (deferred) + Reset */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          {/* promote — deferred (no backend endpoint) */}
          <div
            style={{
              padding: '16px 18px',
              border: '1.5px solid var(--green-border)',
              borderRadius: 8,
              background: 'rgba(34,197,94,.06)',
            }}
          >
            <div
              className="mono"
              style={{
                fontSize: 10,
                color: 'var(--green-soft)',
                letterSpacing: '.2em',
                marginBottom: 6,
              }}
            >
              // PROMOTE TO LIVE BOT
            </div>
            <div
              style={{
                fontSize: 12,
                color: 'var(--fg-2)',
                lineHeight: 1.5,
                marginBottom: 12,
              }}
            >
              Push trained model parameters to the live Bot. Existing positions stay untouched;
              next signal uses new weights.
            </div>
            <button
              className="btn btn-green"
              disabled
              style={{
                width: '100%',
                padding: '10px',
                fontWeight: 800,
                letterSpacing: '.18em',
                fontSize: 11,
                opacity: 0.5,
                cursor: 'not-allowed',
              }}
            >
              ↑ PROMOTE TO LIVE
            </button>
            <div
              className="mono"
              style={{
                fontSize: 9,
                color: 'var(--amber)',
                letterSpacing: '.14em',
                marginTop: 8,
              }}
            >
              ⚠ promote endpoint pending — coming soon
            </div>
          </div>

          {/* reset */}
          <div
            style={{
              padding: '16px 18px',
              border: '1.5px solid var(--red-border)',
              borderRadius: 8,
              background: 'rgba(248,113,113,.06)',
            }}
          >
            <div
              className="mono"
              style={{
                fontSize: 10,
                color: 'var(--red-2)',
                letterSpacing: '.2em',
                marginBottom: 6,
              }}
            >
              // RESET ML MEMORY
            </div>
            <div
              style={{
                fontSize: 12,
                color: 'var(--fg-2)',
                lineHeight: 1.5,
                marginBottom: 12,
              }}
            >
              Wipe all trained weights. Returns the bot to factory baseline. All Ghost trade
              history retained — only the model resets.
            </div>
            {!confirmReset ? (
              <button
                className="btn btn-red"
                disabled={busy}
                onClick={() => setConfirmReset(true)}
                style={{
                  width: '100%',
                  padding: '10px',
                  fontWeight: 800,
                  letterSpacing: '.18em',
                  fontSize: 11,
                }}
              >
                ↺ RESET TO FACTORY
              </button>
            ) : (
              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  className="btn"
                  style={{ flex: 1, padding: '10px', fontSize: 11 }}
                  onClick={() => setConfirmReset(false)}
                  disabled={busy}
                >
                  CANCEL
                </button>
                <button
                  className="btn btn-red"
                  style={{ flex: 1, padding: '10px', fontSize: 11, fontWeight: 800 }}
                  onClick={onReset}
                  disabled={busy}
                >
                  ↺ CONFIRM RESET
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────

export function TrainingGround() {
  const [status, setStatus] = useState<MLStatus | null>(null);
  const [features, setFeatures] = useState<FeatureImportanceItem[]>([]);
  const readyRef = useRef(false);

  const reload = async () => {
    const [statusRes, featuresRes] = await Promise.allSettled([
      mlService.getStatus(),
      mlService.getFeatureImportance(),
    ]);
    if (statusRes.status === 'fulfilled') setStatus(statusRes.value);
    if (featuresRes.status === 'fulfilled') setFeatures(featuresRes.value);
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await reload();
      } finally {
        if (!cancelled && !readyRef.current) {
          readyRef.current = true;
          document.body.setAttribute('data-snapshot-ready', 'true');
        }
      }
    })();
    return () => {
      cancelled = true;
      document.body.removeAttribute('data-snapshot-ready');
    };
  }, []);

  // Inject DRILLS module stat values once status loads.
  const modules = useMemo(() => {
    return MODULES.map((m) => {
      if (m.id !== 'drills' || !status) return m;
      const versus = (status.accuracy * 100 - BASELINE_PCT).toFixed(1);
      const above = status.accuracy * 100 > BASELINE_PCT;
      return {
        ...m,
        stat: [
          { k: 'Model', v: status.model_type, vc: '#c084fc' },
          {
            k: 'vs Baseline',
            v: `${above ? '+' : ''}${versus}%`,
            vc: above ? '#4ade80' : '#f87171',
          },
          { k: 'Samples', v: status.n_samples.toLocaleString() },
        ],
      };
    });
  }, [status]);

  const modelChip = status ? `MODEL · ${status.model_type}` : 'MODEL · —';

  return (
    <div className="page">
      <PageHead
        icon={
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <circle
              cx="12"
              cy="12"
              r="9"
              stroke="currentColor"
              strokeWidth="1.5"
              style={{ color: 'var(--accent)' }}
            />
            <circle
              cx="12"
              cy="12"
              r="5"
              stroke="currentColor"
              strokeWidth="1"
              strokeDasharray="2 2"
              style={{ color: 'var(--accent)' }}
            />
            <circle
              cx="12"
              cy="12"
              r="1.5"
              fill="currentColor"
              style={{ color: 'var(--accent)' }}
            />
          </svg>
        }
        title="Training Ground"
        subtitle="Hub · Range · Drills · Replay · Quizzes · Lessons — practice the system, train the model"
        badges={
          <>
            <Chip kind="cyan">● 5 MODULES</Chip>
            <Chip kind="green">GHOST · ARMED</Chip>
            <Chip kind="purple">{modelChip}</Chip>
          </>
        }
      />

      <div
        className="mono"
        style={{
          fontSize: 10,
          color: 'var(--fg-3)',
          letterSpacing: '.24em',
          textTransform: 'uppercase',
          margin: '10px 4px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: 14,
        }}
      >
        <div
          style={{
            flex: 1,
            height: 1,
            background: 'linear-gradient(90deg,transparent,var(--border-soft),transparent)',
          }}
        />
        <span>// SELECT A TRAINING MODULE</span>
        <div
          style={{
            flex: 1,
            height: 1,
            background: 'linear-gradient(90deg,transparent,var(--border-soft),transparent)',
          }}
        />
      </div>

      <div className="tg-grid">
        {modules.map((m) => (
          <ModCard key={m.id} m={m} />
        ))}
      </div>

      <DrillsPanel status={status} features={features} reload={reload} />

      <FooterStatus latency={36} />

      <style>{`
        .tg-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
        @media (max-width:1100px){.tg-grid{grid-template-columns:repeat(2,1fr)}}
        @media (max-width:700px){.tg-grid{grid-template-columns:1fr}}
        .tg-card{position:relative;display:flex;flex-direction:column;gap:10px;padding:18px 20px;border:1px solid var(--border-soft);border-radius:12px;background:linear-gradient(135deg,rgba(0,0,0,.55),oklch(0.22 0.010 125 / .55));text-decoration:none;color:inherit;overflow:hidden;transition:transform .2s,box-shadow .2s;min-height:230px}
        .tg-card:hover{transform:translateY(-2px);box-shadow:0 8px 32px rgba(0,0,0,.4)}
        .tg-card-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
        .tg-card-title{font-family:'Share Tech Mono',monospace;font-size:24px;letter-spacing:.16em;text-transform:uppercase}
        .tg-card-tag{font-size:10px;color:var(--fg-4);letter-spacing:.2em;text-transform:uppercase;text-align:right;max-width:140px;line-height:1.4}
        .tg-card-body{font-size:13px;color:var(--fg-2);line-height:1.5;flex:1}
        .tg-card-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:10px 0;border-top:1px dashed var(--border-soft);border-bottom:1px dashed var(--border-soft)}
        .tg-card-cta{font-size:11px;letter-spacing:.24em;font-weight:700;padding-top:4px}
        .tg-card-deco{position:absolute;right:-30px;bottom:-30px;width:130px;height:130px;opacity:.5;pointer-events:none}
      `}</style>
    </div>
  );
}

export default TrainingGround;
