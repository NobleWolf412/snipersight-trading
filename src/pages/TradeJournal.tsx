/**
 * TradeJournal — Phase 3b sub-step 1
 *
 * HUD chrome rewrite of the closed-trade analytics page. Path B:
 * keep ALL backend wiring (tradeJournalService, mlService, filters,
 * sort, CSV export, loading/error states); replace ONLY the visual
 * shell with the prototype/journal.jsx HUD design.
 *
 * What's NEW vs prior shadcn version:
 *   - Equity + drawdown dual-curve SVG (drawdown computed client-side
 *     from aggregate.equity_curve — backend doesn't ship it).
 *   - PnL Calendar (daily heatmap, computed client-side from trades).
 *   - Per-symbol / per-type breakdown as bar-style cards (not table).
 *   - Stat tiles in 8-wide grid; profit factor + expectancy computed
 *     client-side from aggregate fields.
 *
 * What's DEFERRED (backend lacks fields, will land in 3b sub-step 2):
 *   - Tag cloud — JournalTrade has no `tags`.
 *   - MFE-vs-R distribution scatter — no `rr` per trade.
 *   - Trade detail modal with notes — notes aren't persisted backend-side.
 *
 * MLPanel is the ML-gate boundary: visual restyled, behavior identical
 * (train / reset / clear / SHAP feature importance) — per "no live capital
 * before auth" the ML signal-quality gate must NOT regress.
 *
 * body[data-snapshot-ready="true"] is set after first successful load so
 * the visual capture framework knows when to capture.
 */
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { Chip, FooterStatus, PageHead, Reticle, SectionHead, fmtMoney } from '@/components/hud';
import {
  tradeJournalService,
  type JournalTrade,
  type JournalAggregate,
  type JournalFilters,
} from '@/services/tradeJournalService';
import { mlService, type MLStatus, type FeatureImportanceItem } from '@/services/mlService';

// ─── helpers ──────────────────────────────────────────────────────────────

function fmt(n: number, decimals = 2) {
  return n.toFixed(decimals);
}

function fmtDate(iso: string | null) {
  if (!iso) return '—';
  const d = new Date(iso);
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

const EXIT_REASON_LABELS: Record<string, string> = {
  target: 'TARGET',
  stop_loss: 'STOP',
  stagnation: 'STALE',
  manual: 'MANUAL',
  max_hours: 'TIMEOUT',
};

// ─── StatTile ─────────────────────────────────────────────────────────────

function StatTile({
  label,
  value,
  sub,
  color,
  big,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  color?: string;
  big?: boolean;
}) {
  return (
    <div className="metric-tile">
      <div className="metric-label">{label}</div>
      <div
        className="metric-value"
        style={{ color: color || 'var(--fg)', fontSize: big ? 22 : 16 }}
      >
        {value}
      </div>
      {sub && (
        <div className="metric-sub" style={{ color: color || 'var(--fg-3)', opacity: 0.7 }}>
          {sub}
        </div>
      )}
    </div>
  );
}

// ─── EquityCurve (equity + drawdown SVG) ──────────────────────────────────

function EquityCurve({
  equityCurve,
  initial,
}: {
  equityCurve: { time: string; value: number }[];
  initial: number;
}) {
  const W = 800;
  const H = 180;
  const padL = 4;
  const padR = 10;
  const padT = 10;
  const padB = 20;

  const { eqPts } = useMemo(() => {
    let peak = initial;
    const eqPts = equityCurve.map((p, i) => {
      const y = initial + p.value;
      peak = Math.max(peak, y);
      return { x: i + 1, y, dd: peak > 0 ? -((peak - y) / peak) * 100 : 0 };
    });
    eqPts.unshift({ x: 0, y: initial, dd: 0 });
    return { eqPts };
  }, [equityCurve, initial]);

  if (eqPts.length < 2) return null;

  const minY = Math.min(...eqPts.map(p => p.y));
  const maxY = Math.max(...eqPts.map(p => p.y));
  const yRng = maxY - minY || 1;
  const last = eqPts[eqPts.length - 1];
  const isUp = last.y >= initial;
  const stroke = isUp ? 'var(--green-soft)' : 'var(--red-2)';

  const xOf = (i: number) => padL + (i / (eqPts.length - 1)) * (W - padL - padR);
  const yOf = (y: number) => padT + (1 - (y - minY) / yRng) * (H - padT - padB);

  const line = eqPts
    .map((p, i) => (i ? 'L' : 'M') + xOf(p.x).toFixed(1) + ' ' + yOf(p.y).toFixed(1))
    .join(' ');
  const area =
    line + ` L ${xOf(eqPts.length - 1).toFixed(1)} ${H - padB} L ${padL} ${H - padB} Z`;

  const minDD = Math.min(...eqPts.map(p => p.dd));
  const ddH = 60;
  const ddYof = (dd: number) => H + 8 + (-dd / Math.abs(minDD || 1)) * ddH;
  const ddPath = eqPts
    .map((p, i) => (i ? 'L' : 'M') + xOf(p.x).toFixed(1) + ' ' + ddYof(p.dd).toFixed(1))
    .join(' ');
  const ddArea = ddPath + ` L ${xOf(eqPts.length - 1).toFixed(1)} ${H + 8} L ${padL} ${H + 8} Z`;

  return (
    <svg viewBox={`0 0 ${W} ${H + 8 + ddH + 12}`} style={{ width: '100%', height: 'auto' }}>
      <defs>
        <linearGradient id="eqg-journal" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity=".25" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
        <linearGradient id="ddg-journal" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--red-2)" stopOpacity=".05" />
          <stop offset="100%" stopColor="var(--red-2)" stopOpacity=".25" />
        </linearGradient>
      </defs>
      {[0, 0.25, 0.5, 0.75, 1].map(g => (
        <line
          key={g}
          x1={padL}
          x2={W - padR}
          y1={padT + g * (H - padT - padB)}
          y2={padT + g * (H - padT - padB)}
          stroke="rgba(255,255,255,.05)"
          strokeDasharray="2 3"
        />
      ))}
      <path d={area} fill="url(#eqg-journal)" />
      <path d={line} stroke={stroke} strokeWidth={1.6} fill="none" />
      <text
        x={padL + 4}
        y={padT + 10}
        fill="var(--fg-4)"
        fontSize="9"
        fontFamily="JetBrains Mono,monospace"
        letterSpacing=".18em"
      >
        EQUITY
      </text>
      <text
        x={W - padR}
        y={padT + 10}
        fill={stroke}
        fontSize="11"
        fontFamily="JetBrains Mono,monospace"
        textAnchor="end"
        fontWeight={700}
      >
        {fmtMoney(last.y)}
      </text>
      <path d={ddArea} fill="url(#ddg-journal)" />
      <path d={ddPath} stroke="var(--red-2)" strokeWidth={1.2} fill="none" opacity={0.8} />
      <text
        x={padL + 4}
        y={H + 18}
        fill="var(--fg-4)"
        fontSize="9"
        fontFamily="JetBrains Mono,monospace"
        letterSpacing=".18em"
      >
        DRAWDOWN
      </text>
      <text
        x={W - padR}
        y={H + 18}
        fill="var(--red-2)"
        fontSize="11"
        fontFamily="JetBrains Mono,monospace"
        textAnchor="end"
        fontWeight={700}
      >
        {minDD.toFixed(2)}%
      </text>
    </svg>
  );
}

// ─── PnLCalendar ──────────────────────────────────────────────────────────

function PnLCalendar({ trades }: { trades: JournalTrade[] }) {
  const byDay = useMemo(() => {
    const map: Record<string, number> = {};
    trades.forEach(t => {
      const day = (t.exit_time ?? t.entry_time).slice(0, 10);
      map[day] = (map[day] ?? 0) + t.pnl;
    });
    return map;
  }, [trades]);
  const entries = Object.entries(byDay).sort();
  if (entries.length === 0) {
    return (
      <div style={{ fontSize: 11, color: 'var(--fg-4)', fontFamily: 'JetBrains Mono,monospace' }}>
        // no closed-trade days in window
      </div>
    );
  }
  const max = Math.max(...entries.map(([, v]) => Math.abs(v))) || 1;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)', gap: 4 }}>
      {entries.map(([d, v]) => {
        const intensity = Math.abs(v) / max;
        const bg =
          v >= 0
            ? `rgba(34,197,94,${0.15 + 0.55 * intensity})`
            : `rgba(248,113,113,${0.15 + 0.55 * intensity})`;
        const bd = v >= 0 ? `rgba(34,197,94,.5)` : `rgba(248,113,113,.5)`;
        return (
          <div
            key={d}
            style={{
              background: bg,
              border: `1px solid ${bd}`,
              borderRadius: 4,
              padding: '8px 6px',
              textAlign: 'center',
            }}
          >
            <div
              className="mono"
              style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.1em' }}
            >
              {d.slice(5)}
            </div>
            <div
              className="mono"
              style={{
                fontSize: 12,
                fontWeight: 800,
                color: v >= 0 ? 'var(--green-soft)' : 'var(--red-2)',
                marginTop: 2,
              }}
            >
              {v >= 0 ? '+' : ''}
              {v.toFixed(0)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── GroupBreakdown (per-symbol / per-type bars) ──────────────────────────

type GroupRow = { label: string; trades: number; wins: number; pnl: number; win_rate: number };

function GroupBreakdown({ rows }: { rows: GroupRow[] }) {
  if (rows.length === 0) {
    return (
      <div style={{ fontSize: 11, color: 'var(--fg-4)', fontFamily: 'JetBrains Mono,monospace' }}>
        // no data
      </div>
    );
  }
  const max = Math.max(...rows.map(r => Math.abs(r.pnl))) || 1;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {rows.map(g => {
        const profit = g.pnl >= 0;
        const w = (Math.abs(g.pnl) / max) * 100;
        return (
          <div
            key={g.label}
            style={{
              padding: '10px 12px',
              border: '1px solid var(--border-soft)',
              borderRadius: 8,
              background: 'rgba(0,0,0,.3)',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                position: 'absolute',
                top: 0,
                bottom: 0,
                left: 0,
                width: w + '%',
                background: profit ? 'rgba(34,197,94,.05)' : 'rgba(248,113,113,.05)',
                borderRight: `1px solid ${profit ? 'rgba(34,197,94,.3)' : 'rgba(248,113,113,.3)'}`,
              }}
            />
            <div
              style={{
                position: 'relative',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 6,
              }}
            >
              <span
                style={{
                  fontFamily: 'Share Tech Mono,monospace',
                  fontSize: 13,
                  letterSpacing: '.06em',
                }}
              >
                {g.label}
              </span>
              <span
                className="mono"
                style={{
                  fontSize: 13,
                  fontWeight: 800,
                  color: profit ? 'var(--green-soft)' : 'var(--red-2)',
                }}
              >
                {(profit ? '+' : '') + fmtMoney(g.pnl)}
              </span>
            </div>
            <div
              style={{
                position: 'relative',
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: 10,
                fontFamily: 'JetBrains Mono,monospace',
                color: 'var(--fg-4)',
                letterSpacing: '.14em',
              }}
            >
              <span>{g.trades} TRADES</span>
              <span
                style={{
                  color:
                    g.win_rate >= 60
                      ? 'var(--green-soft)'
                      : g.win_rate >= 40
                      ? 'var(--amber)'
                      : 'var(--red-2)',
                }}
              >
                WR {g.win_rate.toFixed(0)}%
              </span>
              <span>
                {g.wins}W / {g.trades - g.wins}L
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── MLPanel ──────────────────────────────────────────────────────────────
// Visual restyle only — train / reset / clear / SHAP behavior unchanged.

function MLPanel() {
  const [status, setStatus] = useState<MLStatus | null>(null);
  const [importance, setImportance] = useState<FeatureImportanceItem[]>([]);
  const [training, setTraining] = useState(false);
  const [trainMsg, setTrainMsg] = useState<string | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [clearing, setClearing] = useState(false);
  const [clearConfirm, setClearConfirm] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [resetConfirm, setResetConfirm] = useState(false);

  const fetchStatus = async () => {
    try {
      const s = await mlService.getStatus();
      setStatus(s);
      if (s.trained) {
        const feats = await mlService.getFeatureImportance();
        setImportance(feats.slice(0, 12));
      }
    } catch {
      // backend may not be running yet
    } finally {
      setLoadingStatus(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleResetModel = async () => {
    if (!resetConfirm) {
      setResetConfirm(true);
      setTimeout(() => setResetConfirm(false), 4000);
      return;
    }
    setResetConfirm(false);
    setResetting(true);
    setTrainMsg(null);
    try {
      const result = await mlService.resetModel();
      setTrainMsg(result.message);
      setImportance([]);
      await fetchStatus();
    } catch (e) {
      setTrainMsg(e instanceof Error ? e.message : 'Reset failed');
    } finally {
      setResetting(false);
    }
  };

  const handleClearLogs = async () => {
    if (!clearConfirm) {
      setClearConfirm(true);
      setTimeout(() => setClearConfirm(false), 4000);
      return;
    }
    setClearConfirm(false);
    setClearing(true);
    setTrainMsg(null);
    try {
      const result = await mlService.clearSessionLogs();
      setTrainMsg(result.message);
      await fetchStatus();
    } catch (e) {
      setTrainMsg(e instanceof Error ? e.message : 'Clear failed');
    } finally {
      setClearing(false);
    }
  };

  const handleTrain = async () => {
    setTraining(true);
    setTrainMsg(null);
    try {
      const result = await mlService.train();
      setTrainMsg(result.message);
      await fetchStatus();
    } catch (e) {
      setTrainMsg(e instanceof Error ? e.message : 'Training failed');
    } finally {
      setTraining(false);
    }
  };

  const accuracy = status?.accuracy ?? 0;
  const accuracyColor =
    accuracy >= 0.65 ? 'var(--green-soft)' : accuracy >= 0.55 ? 'var(--amber)' : 'var(--red-2)';

  // SHAP bar dimensions
  const maxImportance = importance.length ? Math.max(...importance.map(i => i.importance)) : 1;

  return (
    <section className="panel">
      <SectionHead
        title="Edge Model"
        right={
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <button
              className="btn"
              style={{
                padding: '4px 10px',
                fontSize: 10,
                color: resetConfirm ? 'var(--red-2)' : undefined,
                borderColor: resetConfirm ? 'rgba(248,113,113,.6)' : undefined,
              }}
              disabled={resetting || training || clearing}
              onClick={handleResetModel}
              title="Delete trained model — ML gate becomes inactive until retrained"
            >
              {resetting ? 'RESETTING…' : resetConfirm ? 'CONFIRM RESET?' : 'RESET MODEL'}
            </button>
            <button
              className="btn"
              style={{
                padding: '4px 10px',
                fontSize: 10,
                color: clearConfirm ? 'var(--red-2)' : undefined,
                borderColor: clearConfirm ? 'rgba(248,113,113,.6)' : undefined,
              }}
              disabled={clearing || training || resetting}
              onClick={handleClearLogs}
              title="Clear all session signal logs (trained model is preserved)"
            >
              {clearing ? 'CLEARING…' : clearConfirm ? 'CONFIRM CLEAR?' : 'CLEAR LOGS'}
            </button>
            <button
              className="btn btn-cyan"
              style={{ padding: '4px 10px', fontSize: 10 }}
              disabled={training || clearing || resetting}
              onClick={handleTrain}
            >
              {training ? 'TRAINING…' : 'TRAIN MODEL'}
            </button>
          </div>
        }
      />
      <div style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {loadingStatus ? (
          <div className="mono" style={{ fontSize: 11, color: 'var(--fg-4)' }}>
            // loading model status…
          </div>
        ) : !status ? (
          <div className="mono" style={{ fontSize: 11, color: 'var(--fg-4)' }}>
            // backend not reachable
          </div>
        ) : (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
              <StatTile
                label="Status"
                value={status.trained ? 'TRAINED' : 'UNTRAINED'}
                color={status.trained ? 'var(--green-soft)' : 'var(--fg-3)'}
              />
              <StatTile
                label="Model"
                value={status.model_type === 'none' ? '—' : status.model_type}
              />
              <StatTile
                label="Samples"
                value={String(status.n_samples)}
                sub={`min ${status.min_samples_required}`}
              />
              <StatTile
                label="CV Accuracy"
                value={status.trained ? `${(accuracy * 100).toFixed(1)}%` : '—'}
                sub={status.trained ? 'purged walk-fwd' : undefined}
                color={accuracyColor}
              />
            </div>

            {(status as { available_signals?: number }).available_signals != null && (
              <div
                style={{
                  border: '1px solid var(--border-soft)',
                  borderRadius: 6,
                  padding: '8px 12px',
                  background: 'rgba(0,0,0,.3)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontFamily: 'JetBrains Mono,monospace',
                  fontSize: 11,
                  color: 'var(--fg-3)',
                }}
              >
                <span>Training data available</span>
                <span
                  style={{
                    color:
                      ((status as { available_signals?: number }).available_signals ?? 0) >= 10
                        ? 'var(--green-soft)'
                        : 'var(--amber)',
                    fontWeight: 700,
                  }}
                >
                  {(status as { available_signals?: number }).available_signals} signals ·{' '}
                  {(status as { available_trades?: number }).available_trades ?? 0} trades
                </span>
              </div>
            )}

            {!status.trained &&
              ((status as { available_signals?: number }).available_signals ?? 0) < 10 && (
                <div
                  style={{
                    border: '1px solid rgba(245,158,11,.3)',
                    borderRadius: 6,
                    padding: '8px 12px',
                    background: 'rgba(245,158,11,.05)',
                    fontSize: 11,
                    fontFamily: 'JetBrains Mono,monospace',
                    color: 'var(--amber)',
                  }}
                >
                  Let the bot run a bit longer — need at least 10 signals to train. Currently have{' '}
                  {(status as { available_signals?: number }).available_signals ?? 0}.
                </div>
              )}
            {status.trained && accuracy < 0.55 && (
              <div
                style={{
                  border: '1px solid rgba(248,113,113,.3)',
                  borderRadius: 6,
                  padding: '8px 12px',
                  background: 'rgba(248,113,113,.05)',
                  fontSize: 11,
                  fontFamily: 'JetBrains Mono,monospace',
                  color: 'var(--red-2)',
                }}
              >
                Accuracy below 55% — gather more diverse trades before relying on predictions.
              </div>
            )}
            {status.trained && accuracy >= 0.65 && (
              <div
                style={{
                  border: '1px solid rgba(34,197,94,.3)',
                  borderRadius: 6,
                  padding: '8px 12px',
                  background: 'rgba(34,197,94,.05)',
                  fontSize: 11,
                  fontFamily: 'JetBrains Mono,monospace',
                  color: 'var(--green-soft)',
                }}
              >
                Model looks solid. Green bars = conditions that help your win rate. Red = conditions
                that hurt it.
              </div>
            )}
            {status.trained && accuracy >= 0.55 && accuracy < 0.65 && (
              <div
                style={{
                  border: '1px solid rgba(245,158,11,.3)',
                  borderRadius: 6,
                  padding: '8px 12px',
                  background: 'rgba(245,158,11,.05)',
                  fontSize: 11,
                  fontFamily: 'JetBrains Mono,monospace',
                  color: 'var(--amber)',
                }}
              >
                Moderate accuracy — more trades will sharpen the model. Use feature directions as
                guidance only.
              </div>
            )}

            {trainMsg && (
              <div
                style={{
                  border: '1px solid var(--border-soft)',
                  borderRadius: 6,
                  padding: '8px 12px',
                  background: 'rgba(0,0,0,.3)',
                  fontSize: 11,
                  fontFamily: 'JetBrains Mono,monospace',
                  fontWeight: 700,
                  color: trainMsg.toLowerCase().includes('success') || trainMsg.toLowerCase().includes('trained')
                    ? 'var(--green-soft)'
                    : trainMsg.toLowerCase().includes('no training') || trainMsg.toLowerCase().includes('need')
                    ? 'var(--amber)'
                    : 'var(--red-2)',
                }}
              >
                {trainMsg}
              </div>
            )}

            {importance.length > 0 && (
              <div>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: 8,
                  }}
                >
                  <div
                    className="mono"
                    style={{
                      fontSize: 9,
                      color: 'var(--fg-4)',
                      letterSpacing: '.18em',
                      textTransform: 'uppercase',
                    }}
                  >
                    // SHAP feature importance
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      gap: 12,
                      fontSize: 9,
                      fontFamily: 'JetBrains Mono,monospace',
                      color: 'var(--fg-4)',
                    }}
                  >
                    <span>
                      <span
                        style={{
                          display: 'inline-block',
                          width: 8,
                          height: 8,
                          background: 'var(--green-soft)',
                          marginRight: 4,
                        }}
                      />
                      helps win rate
                    </span>
                    <span>
                      <span
                        style={{
                          display: 'inline-block',
                          width: 8,
                          height: 8,
                          background: 'var(--red-2)',
                          marginRight: 4,
                        }}
                      />
                      hurts win rate
                    </span>
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {importance.map(item => {
                    const w = (item.importance / maxImportance) * 100;
                    const c = item.direction >= 0 ? 'var(--green-soft)' : 'var(--red-2)';
                    return (
                      <div
                        key={item.name}
                        style={{
                          display: 'grid',
                          gridTemplateColumns: '160px 1fr 60px',
                          gap: 8,
                          alignItems: 'center',
                          fontFamily: 'JetBrains Mono,monospace',
                          fontSize: 10,
                        }}
                      >
                        <span style={{ color: 'var(--fg-2)', textAlign: 'right' }}>
                          {item.name}
                        </span>
                        <div
                          style={{
                            position: 'relative',
                            height: 14,
                            background: 'rgba(0,0,0,.3)',
                            border: '1px solid var(--border-soft)',
                            borderRadius: 2,
                          }}
                        >
                          <div
                            style={{
                              position: 'absolute',
                              top: 0,
                              bottom: 0,
                              left: 0,
                              width: w + '%',
                              background: c,
                              opacity: 0.7,
                              borderRadius: '0 2px 2px 0',
                            }}
                          />
                        </div>
                        <span style={{ color: c, fontWeight: 700, textAlign: 'right' }}>
                          {item.importance.toFixed(3)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────

type SortKey = 'exit_time' | 'symbol' | 'pnl' | 'trade_type' | 'exit_reason';
type SortDir = 'asc' | 'desc';

const INITIAL_EQUITY = 5000;

export function TradeJournal() {
  const navigate = useNavigate();

  const [trades, setTrades] = useState<JournalTrade[]>([]);
  const [aggregate, setAggregate] = useState<JournalAggregate | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [filters, setFilters] = useState<JournalFilters>({ limit: 200 });
  const [symbolInput, setSymbolInput] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [exitFilter, setExitFilter] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  // Sort
  const [sortKey, setSortKey] = useState<SortKey>('exit_time');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  // Group toggle for breakdown
  const [groupBy, setGroupBy] = useState<'symbol' | 'type'>('symbol');

  const load = async (f: JournalFilters) => {
    setLoading(true);
    setError(null);
    try {
      const data = await tradeJournalService.getJournal(f);
      setTrades(data.trades);
      setAggregate(data.aggregate);
      setTotal(data.total);
    } catch {
      setError('Could not load journal — is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(filters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Snapshot-ready flag — set after first load resolves (success or error).
  useEffect(() => {
    if (!loading) {
      document.body.setAttribute('data-snapshot-ready', 'true');
    }
    return () => {
      document.body.removeAttribute('data-snapshot-ready');
    };
  }, [loading]);

  const applyFilters = () => {
    const f: JournalFilters = {
      limit: 200,
      symbol: symbolInput || undefined,
      trade_type: typeFilter || undefined,
      exit_reason: exitFilter || undefined,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
    };
    setFilters(f);
    load(f);
  };

  const resetFilters = () => {
    setSymbolInput('');
    setTypeFilter('');
    setExitFilter('');
    setStartDate('');
    setEndDate('');
    const f: JournalFilters = { limit: 200 };
    setFilters(f);
    load(f);
  };

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sorted = useMemo(() => {
    return [...trades].sort((a, b) => {
      let av: string | number = a[sortKey] ?? '';
      let bv: string | number = b[sortKey] ?? '';
      if (sortKey === 'pnl') {
        av = a.pnl;
        bv = b.pnl;
      }
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [trades, sortKey, sortDir]);

  const symbolRows = useMemo<GroupRow[]>(() => {
    if (!aggregate) return [];
    return Object.entries(aggregate.by_symbol)
      .map(([label, v]) => ({ label, ...v }))
      .sort((a, b) => Math.abs(b.pnl) - Math.abs(a.pnl));
  }, [aggregate]);

  const typeRows = useMemo<GroupRow[]>(() => {
    if (!aggregate) return [];
    return Object.entries(aggregate.by_type)
      .map(([label, v]) => ({ label: label.toUpperCase(), ...v }))
      .sort((a, b) => Math.abs(b.pnl) - Math.abs(a.pnl));
  }, [aggregate]);

  // Computed stats (profit factor + expectancy not in aggregate envelope)
  const profitFactor = useMemo(() => {
    if (!aggregate) return 0;
    const winsTotal = aggregate.avg_win * aggregate.winning_trades;
    const lossTotal = Math.abs(aggregate.avg_loss) * aggregate.losing_trades;
    return lossTotal > 0 ? winsTotal / lossTotal : Infinity;
  }, [aggregate]);

  const expectancy = useMemo(() => {
    if (!aggregate) return 0;
    const wr = aggregate.win_rate / 100;
    return wr * aggregate.avg_win - (1 - wr) * Math.abs(aggregate.avg_loss);
  }, [aggregate]);

  return (
    <div className="shell">
      <PageHead
        icon={
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
            <rect
              x="4"
              y="3"
              width="14"
              height="18"
              rx="1.5"
              stroke="var(--green)"
              strokeWidth="1.7"
            />
            <line x1="8" y1="7" x2="14" y2="7" stroke="var(--green)" strokeWidth="1.5" />
            <line x1="8" y1="11" x2="14" y2="11" stroke="var(--green)" strokeWidth="1.5" />
            <line x1="8" y1="15" x2="11" y2="15" stroke="var(--green)" strokeWidth="1.5" />
            <circle cx="20" cy="20" r="3" stroke="var(--accent)" strokeWidth="1.4" />
            <line x1="22" y1="22" x2="24" y2="24" stroke="var(--accent)" strokeWidth="1.4" />
          </svg>
        }
        title="Journal"
        subtitle={`${total} closed trades · all sessions`}
        badges={
          <>
            {aggregate && (
              <>
                <Chip kind={aggregate.total_pnl >= 0 ? 'green' : 'red'}>
                  NET {aggregate.total_pnl >= 0 ? '+' : ''}
                  {fmtMoney(aggregate.total_pnl)}
                </Chip>
                <Chip kind="green">WR {aggregate.win_rate.toFixed(0)}%</Chip>
                <Chip kind="accent">PF {profitFactor.toFixed(2)}</Chip>
              </>
            )}
            <button
              className="btn"
              style={{ padding: '4px 10px', fontSize: 10 }}
              onClick={() =>
                window.open(tradeJournalService.getExportUrl(filters), '_blank')
              }
            >
              EXPORT CSV
            </button>
          </>
        }
      />

      {/* Tab nav */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 18 }}>
        <button
          className="btn"
          style={{ padding: '6px 14px', fontSize: 10 }}
          onClick={() => navigate('/training')}
        >
          TRAINING GROUND
        </button>
        <span
          className="btn btn-cyan"
          style={{ padding: '6px 14px', fontSize: 10, cursor: 'default' }}
        >
          JOURNAL &amp; ML
        </span>
      </div>

      {error && (
        <div
          style={{
            border: '1px solid rgba(248,113,113,.3)',
            background: 'rgba(248,113,113,.08)',
            color: 'var(--red-2)',
            padding: '10px 14px',
            borderRadius: 6,
            fontFamily: 'JetBrains Mono,monospace',
            fontSize: 12,
            marginBottom: 18,
          }}
        >
          {error}
        </div>
      )}

      {/* Stats command center */}
      {aggregate && (
        <section className="panel panel-accent" style={{ marginBottom: 18 }}>
          <Reticle />
          <div className="corner-tag tl">// PERFORMANCE-METRICS</div>
          <div className="corner-tag tr">ALL-SESSIONS WINDOW</div>
          <div style={{ padding: '22px 22px 18px' }}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(8, minmax(0,1fr))',
                gap: 10,
                marginBottom: 18,
              }}
            >
              <StatTile
                label="Net P&L"
                value={
                  (aggregate.total_pnl >= 0 ? '+' : '') + fmtMoney(aggregate.total_pnl)
                }
                sub="across all closed"
                color={aggregate.total_pnl >= 0 ? 'var(--green-soft)' : 'var(--red-2)'}
                big
              />
              <StatTile
                label="Win Rate"
                value={aggregate.win_rate.toFixed(1) + '%'}
                sub={`${aggregate.winning_trades} / ${aggregate.total_trades}`}
                color="var(--green-soft)"
                big
              />
              <StatTile
                label="Profit Fctr"
                value={Number.isFinite(profitFactor) ? profitFactor.toFixed(2) : '∞'}
                sub={
                  profitFactor > 1.5 ? 'healthy' : profitFactor > 1 ? 'thin' : 'losing'
                }
                color={
                  profitFactor > 1.5
                    ? 'var(--green-soft)'
                    : profitFactor > 1
                    ? 'var(--amber)'
                    : 'var(--red-2)'
                }
                big
              />
              <StatTile
                label="Avg R"
                value={(aggregate.avg_rr >= 0 ? '+' : '') + aggregate.avg_rr.toFixed(2) + 'R'}
                sub="per trade"
                color={aggregate.avg_rr >= 0 ? 'var(--green-soft)' : 'var(--red-2)'}
                big
              />
              <StatTile
                label="Expectancy"
                value={(expectancy >= 0 ? '+' : '') + fmtMoney(expectancy)}
                sub="per trade EV"
                color={expectancy >= 0 ? 'var(--green-soft)' : 'var(--red-2)'}
                big
              />
              <StatTile
                label="Avg Win"
                value={'+' + fmtMoney(aggregate.avg_win)}
                sub={`${aggregate.winning_trades} wins`}
                color="var(--green-soft)"
              />
              <StatTile
                label="Avg Loss"
                value={fmtMoney(aggregate.avg_loss)}
                sub={`${aggregate.losing_trades} losses`}
                color="var(--red-2)"
              />
              <StatTile
                label="Max DD"
                value={fmtMoney(aggregate.max_drawdown)}
                sub="peak-to-trough"
                color="var(--red-2)"
              />
            </div>

            <div
              style={{ paddingTop: 14, borderTop: '1px solid var(--border-soft)' }}
            >
              <div
                className="mono"
                style={{
                  fontSize: 10,
                  color: 'var(--fg-4)',
                  letterSpacing: '.20em',
                  textTransform: 'uppercase',
                  marginBottom: 10,
                }}
              >
                // EQUITY · DRAWDOWN
              </div>
              {aggregate.equity_curve.length > 1 ? (
                <EquityCurve
                  equityCurve={aggregate.equity_curve}
                  initial={INITIAL_EQUITY}
                />
              ) : (
                <div
                  className="mono"
                  style={{ fontSize: 11, color: 'var(--fg-4)' }}
                >
                  // not enough closed trades for equity curve
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Two-column layout: trade log + breakdowns */}
      <div className="layout-grid">
        {/* Left col: trade log + calendar */}
        <div className="col">
          <section className="panel">
            <SectionHead
              title={
                <>
                  Trade Log <span style={{ color: 'var(--accent)' }}>{sorted.length}</span>
                </>
              }
              right={
                <Chip kind="accent">
                  SORT · {sortKey.toUpperCase()} {sortDir === 'desc' ? '↓' : '↑'}
                </Chip>
              }
            />
            <div
              style={{
                padding: '10px 18px',
                borderBottom: '1px solid var(--border-soft)',
                display: 'grid',
                gridTemplateColumns: 'repeat(5, 1fr) auto auto',
                gap: 8,
                alignItems: 'center',
              }}
            >
              <input
                style={{
                  background: 'rgba(0,0,0,.4)',
                  border: '1px solid var(--border-soft)',
                  color: 'var(--fg)',
                  padding: '6px 10px',
                  borderRadius: 4,
                  fontFamily: 'JetBrains Mono,monospace',
                  fontSize: 10,
                  outline: 'none',
                }}
                placeholder="// SYMBOL"
                value={symbolInput}
                onChange={e => setSymbolInput(e.target.value.toUpperCase())}
              />
              <select
                style={{
                  background: 'rgba(0,0,0,.4)',
                  border: '1px solid var(--border-soft)',
                  color: 'var(--fg)',
                  padding: '6px 10px',
                  borderRadius: 4,
                  fontFamily: 'JetBrains Mono,monospace',
                  fontSize: 10,
                  outline: 'none',
                }}
                value={typeFilter}
                onChange={e => setTypeFilter(e.target.value)}
              >
                <option value="">// ALL TYPES</option>
                <option value="scalp">SCALP</option>
                <option value="intraday">INTRADAY</option>
                <option value="swing">SWING</option>
              </select>
              <select
                style={{
                  background: 'rgba(0,0,0,.4)',
                  border: '1px solid var(--border-soft)',
                  color: 'var(--fg)',
                  padding: '6px 10px',
                  borderRadius: 4,
                  fontFamily: 'JetBrains Mono,monospace',
                  fontSize: 10,
                  outline: 'none',
                }}
                value={exitFilter}
                onChange={e => setExitFilter(e.target.value)}
              >
                <option value="">// ALL EXITS</option>
                <option value="target">TARGET</option>
                <option value="stop_loss">STOP</option>
                <option value="stagnation">STALE</option>
                <option value="manual">MANUAL</option>
              </select>
              <input
                type="date"
                style={{
                  background: 'rgba(0,0,0,.4)',
                  border: '1px solid var(--border-soft)',
                  color: 'var(--fg)',
                  padding: '6px 10px',
                  borderRadius: 4,
                  fontFamily: 'JetBrains Mono,monospace',
                  fontSize: 10,
                  outline: 'none',
                }}
                value={startDate}
                onChange={e => setStartDate(e.target.value)}
              />
              <input
                type="date"
                style={{
                  background: 'rgba(0,0,0,.4)',
                  border: '1px solid var(--border-soft)',
                  color: 'var(--fg)',
                  padding: '6px 10px',
                  borderRadius: 4,
                  fontFamily: 'JetBrains Mono,monospace',
                  fontSize: 10,
                  outline: 'none',
                }}
                value={endDate}
                onChange={e => setEndDate(e.target.value)}
              />
              <button
                className="btn btn-cyan"
                style={{ padding: '6px 10px', fontSize: 10 }}
                onClick={applyFilters}
              >
                APPLY
              </button>
              <button
                className="btn"
                style={{ padding: '6px 10px', fontSize: 10 }}
                onClick={resetFilters}
              >
                RESET
              </button>
            </div>
            <div style={{ maxHeight: 520, overflowY: 'auto' }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '90px 1fr 50px 70px 90px 70px 70px 90px',
                  gap: 8,
                  padding: '10px 18px',
                  fontFamily: 'JetBrains Mono,monospace',
                  fontSize: 9,
                  color: 'var(--fg-4)',
                  letterSpacing: '.18em',
                  textTransform: 'uppercase',
                  position: 'sticky',
                  top: 0,
                  background: 'var(--card)',
                  zIndex: 1,
                  borderBottom: '1px solid var(--border-soft)',
                }}
              >
                <span
                  onClick={() => toggleSort('exit_time')}
                  style={{
                    cursor: 'pointer',
                    color: sortKey === 'exit_time' ? 'var(--accent)' : 'var(--fg-4)',
                  }}
                >
                  TIME
                  {sortKey === 'exit_time' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                </span>
                <span
                  onClick={() => toggleSort('symbol')}
                  style={{
                    cursor: 'pointer',
                    color: sortKey === 'symbol' ? 'var(--accent)' : 'var(--fg-4)',
                  }}
                >
                  SYMBOL
                  {sortKey === 'symbol' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                </span>
                <span>DIR</span>
                <span
                  onClick={() => toggleSort('trade_type')}
                  style={{
                    cursor: 'pointer',
                    color: sortKey === 'trade_type' ? 'var(--accent)' : 'var(--fg-4)',
                  }}
                >
                  TYPE
                  {sortKey === 'trade_type' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                </span>
                <span
                  onClick={() => toggleSort('pnl')}
                  style={{
                    cursor: 'pointer',
                    color: sortKey === 'pnl' ? 'var(--accent)' : 'var(--fg-4)',
                  }}
                >
                  P&amp;L
                  {sortKey === 'pnl' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                </span>
                <span>MFE</span>
                <span>MAE</span>
                <span
                  onClick={() => toggleSort('exit_reason')}
                  style={{
                    cursor: 'pointer',
                    color: sortKey === 'exit_reason' ? 'var(--accent)' : 'var(--fg-4)',
                    textAlign: 'right',
                  }}
                >
                  EXIT
                  {sortKey === 'exit_reason' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                </span>
              </div>
              {loading ? (
                <div
                  style={{
                    padding: '36px 18px',
                    textAlign: 'center',
                    color: 'var(--fg-4)',
                    fontSize: 11,
                    fontFamily: 'JetBrains Mono,monospace',
                  }}
                >
                  // loading journal…
                </div>
              ) : sorted.length === 0 ? (
                <div
                  style={{
                    padding: '36px 18px',
                    textAlign: 'center',
                    color: 'var(--fg-4)',
                    fontSize: 11,
                    fontFamily: 'JetBrains Mono,monospace',
                  }}
                >
                  // no trades found
                </div>
              ) : (
                sorted.map(tr => {
                  const profit = tr.pnl >= 0;
                  return (
                    <div
                      key={tr.trade_id}
                      style={{
                        display: 'grid',
                        gridTemplateColumns:
                          '90px 1fr 50px 70px 90px 70px 70px 90px',
                        gap: 8,
                        padding: '10px 18px',
                        borderBottom: '1px solid var(--border-soft)',
                        alignItems: 'center',
                        fontFamily: 'JetBrains Mono,monospace',
                        fontSize: 11,
                      }}
                    >
                      <span style={{ color: 'var(--fg-3)' }}>{fmtDate(tr.exit_time)}</span>
                      <span
                        style={{
                          color: 'var(--fg)',
                          fontWeight: 600,
                          letterSpacing: '.04em',
                        }}
                      >
                        {tr.symbol}
                      </span>
                      <span
                        style={{
                          color:
                            tr.direction === 'LONG' ? 'var(--green-soft)' : 'var(--red-2)',
                          fontWeight: 700,
                        }}
                      >
                        {tr.direction === 'LONG' ? '▲L' : '▼S'}
                      </span>
                      <span style={{ color: 'var(--fg-2)', fontSize: 10 }}>
                        {tr.trade_type.toUpperCase()}
                      </span>
                      <span
                        style={{
                          color: profit ? 'var(--green-soft)' : 'var(--red-2)',
                          fontWeight: 800,
                        }}
                      >
                        {(profit ? '+' : '') + fmtMoney(tr.pnl)}
                        <span
                          style={{
                            fontSize: 9,
                            opacity: 0.6,
                            marginLeft: 4,
                            fontWeight: 500,
                          }}
                        >
                          ({fmt(tr.pnl_pct, 2)}%)
                        </span>
                      </span>
                      <span style={{ color: 'var(--green-soft)' }}>
                        +{fmt(tr.max_favorable, 1)}
                      </span>
                      <span style={{ color: 'var(--red-2)' }}>
                        -{fmt(tr.max_adverse, 1)}
                      </span>
                      <span
                        style={{
                          color: 'var(--fg-4)',
                          fontSize: 9,
                          textAlign: 'right',
                          letterSpacing: '.1em',
                        }}
                      >
                        {EXIT_REASON_LABELS[tr.exit_reason] ?? tr.exit_reason.toUpperCase()}
                      </span>
                    </div>
                  );
                })
              )}
            </div>
          </section>

          <section className="panel">
            <SectionHead title="P&L Calendar" right={<Chip>DAILY</Chip>} />
            <div style={{ padding: '14px 18px' }}>
              <PnLCalendar trades={trades} />
            </div>
          </section>
        </div>

        {/* Right col: breakdowns + ML */}
        <div className="col">
          <section className="panel">
            <SectionHead
              title={`Per-${groupBy === 'symbol' ? 'Symbol' : 'Type'} Breakdown`}
              right={
                <div style={{ display: 'flex', gap: 6 }}>
                  <button
                    className={`btn ${groupBy === 'symbol' ? 'btn-cyan' : ''}`}
                    style={{ padding: '4px 10px', fontSize: 10 }}
                    onClick={() => setGroupBy('symbol')}
                  >
                    SYMBOL
                  </button>
                  <button
                    className={`btn ${groupBy === 'type' ? 'btn-cyan' : ''}`}
                    style={{ padding: '4px 10px', fontSize: 10 }}
                    onClick={() => setGroupBy('type')}
                  >
                    TYPE
                  </button>
                </div>
              }
            />
            <div style={{ padding: '14px 18px' }}>
              <GroupBreakdown rows={groupBy === 'symbol' ? symbolRows : typeRows} />
            </div>
          </section>

          <MLPanel />
        </div>
      </div>

      <FooterStatus latency={36} />
    </div>
  );
}
