/**
 * Drills — ML training page (extracted from TrainingGround inline panel)
 *
 * Operator intent: clicking DRILLS in Training Ground should navigate to a
 * dedicated page rather than scroll to an in-page anchor. Mirrors the
 * /training/range split that gave the Range module its own page.
 *
 * Content is the prior DrillsPanel verbatim — training run controls, 7-day
 * accuracy trend (synthetic, pending track table), SHAP feature importance
 * (top 12), PROMOTE TO LIVE (deferred — no backend endpoint yet), RESET TO
 * FACTORY (mlService.resetModel).
 *
 * body[data-snapshot-ready="true"] set after initial mlService calls settle.
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

const BASELINE_PCT = 55; // placeholder — backend has no baseline-accuracy field yet.

export function Drills() {
  const [status, setStatus] = useState<MLStatus | null>(null);
  const [features, setFeatures] = useState<FeatureImportanceItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const [flash, setFlash] = useState<{
    type: 'ok' | 'warn' | 'err';
    msg: string;
  } | null>(null);
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

  useEffect(() => {
    if (!flash) return;
    const t = setTimeout(() => setFlash(null), 5000);
    return () => clearTimeout(t);
  }, [flash]);

  const accuracyPct = status ? status.accuracy * 100 : 0;
  const samples = status?.n_samples ?? 0;
  const modelVer = status?.model_type ?? '—';
  const aboveBaseline = accuracyPct > BASELINE_PCT;

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
              style={{ color: '#c084fc' }}
            />
            <path
              d="M8 12l3 3 5-6"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{ color: '#c084fc' }}
            />
          </svg>
        }
        title="Drills · ML Training"
        subtitle="Train the bot on Ghost's closed paper trades — promote to live when accuracy beats baseline"
        badges={
          <>
            <Chip kind="purple">MODEL · {modelVer}</Chip>
            <Chip kind={aboveBaseline ? 'green' : 'red'}>
              {aboveBaseline ? '▲' : '▼'}{' '}
              {(((accuracyPct - BASELINE_PCT) / Math.max(BASELINE_PCT, 1)) * 100).toFixed(1)}% vs
              BASELINE
            </Chip>
            <Chip kind="cyan">SAMPLES · {samples.toLocaleString()}</Chip>
          </>
        }
      />

      <section className="panel panel-accent" style={{ marginTop: 14 }}>
        <Reticle />
        <div className="corner-tag tl">// ML-DRILLS-ENGINE</div>
        <div className="corner-tag tr">{busy ? '● WORKING' : '○ READY'}</div>
        <SectionHead
          title="Training Run · Metrics · Features"
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

      <FooterStatus latency={36} />
    </div>
  );
}

export default Drills;
