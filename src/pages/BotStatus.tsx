/**
 * BotStatus — Phase 3g.i.b (HUD rewrite, default tab)
 *
 * Port of `prototype/bot-shell.jsx` status view adapted to TSX with the
 * existing real-data wiring preserved. Renders the live deployment surface
 * — command center, position table, signal log, statistics, footer —
 * using the project's HUD primitives.
 *
 * Plan reference: peppy-sniffing-owl §3e.
 *   3g.i (this commit's range) covers: BotSetup HUD rewrite (3g.i.a, done),
 *   BotStatus default-tab HUD rewrite (3g.i.b, this file), Phemex healthz
 *   modal trigger (3g.i.c, next).
 *   3g.ii covers the deeper observability surfaces — Gauntlet expanded,
 *   Pipeline Tracer drawer, Confluence panel, Universe modal, Diagnose
 *   wizard, Mode-delta tooltip — and the first directional snapshot pair
 *   (`bot_position_open__long`/`__short`).
 *
 * Real-data wiring (preserved from the previous Tailwind version):
 *   - `liveTradingService.getStatus()` — primary state source. Adaptive
 *     2s/10s polling: 2s while a scan is running OR positions are open,
 *     10s otherwise (fast-poll ref preserved verbatim).
 *   - `liveTradingService.getHistory(50)` — completed-trade history for
 *     the equity sparkline + per-trade-type stats.
 *   - `liveTradingService.stop()` — graceful stop CTA.
 *   - `liveTradingService.killSwitch()` — kill-switch CTA (gated behind a
 *     confirmation panel — never one-click).
 *   - `liveTradingService.reset()` — reset and route back to /bot/setup.
 *   - `liveTradingService.analyzeSession()` — run the analyze-session
 *     pipeline; output and error each surface inline.
 *
 * Empty-state rendering (snapshot-fixture path):
 *   The capture fixture (`tests/visual/fixtures/bot-status.json`) returns
 *   `status: 'idle'` with empty `positions`, `signal_log`, statistics, no
 *   `current_scan`, no `regime`, null `config`. The default state must
 *   render this gracefully — no NaN, no "loading" forever, no fake rows.
 *   Each panel shows its own empty-state (`— no positions —`, `— signal
 *   log empty —`, `— awaiting trades —`).
 *
 * Phase 3g.ii.d landed: ConfluenceBreakdown panel (rolling factor
 * stacked-bar over last N signals + by-direction breakdown, sourced
 * from /api/signals/confluence/distribution).
 *
 * Phase 3g.ii.e landed: UniversePanel — qualified + dropped pair list
 * with click-to-open modal, sourced from /api/scanner/universe.
 *
 * Phase 3g.ii.f landed: DiagnoseWizard — 9-step playbook modal
 * orchestrating phemex / universe / cycles / signals_per_stage / fills
 * checks. Failed steps surface CTAs that deep-link to the right tuning
 * surface (Intel for regime, Scanner for confluence-mode tuning, etc.).
 *
 * Phase 3g.ii.g landed: Mode-delta strip on the GauntletBreakdown
 * bottleneck pill — when CONFLUENCE is the bottleneck, shows for each
 * other scanner mode how many of the rejected signals would have passed
 * its `min_confluence_score`. Direction-agnostic per CLAUDE.md §10 #3.
 *
 * Deferred to Phase 3g.ii (with inline `◌ deferred` placeholders):
 *   - PositionChartModal — chart-level modal on each open position row.
 *
 * Synthetic-but-disclosed: none. Every value rendered is sourced from
 * the live status payload or shows an explicit empty marker.
 *
 * Determinism for snapshots:
 *   - No `Math.random`, no `setInterval`. The polling loop uses
 *     `setTimeout` recursion which fires once-per-cycle and consumes the
 *     fixture's deterministic body, so the captured frame is stable.
 *   - Static `now` captured once at mount via useState initializer for
 *     the footer build/timestamp.
 *
 * Snapshot-ready handshake:
 *   StrictMode-safe — set on mount, unset on cleanup. Idempotent across
 *   the React 18 dev double-invoke; final state stays set, which is what
 *   Playwright's `data-snapshot-ready` waiter observes.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Chip,
  ConfluenceBreakdown,
  DiagnoseWizard,
  FooterStatus,
  GauntletBreakdown,
  PageHead,
  PipelineTracer,
  Reticle,
  SectionHead,
  UniversePanel,
} from '@/components/hud';
import {
  liveTradingService,
  type CompletedLiveTrade,
  type LivePosition,
  type LiveTradingStatus,
} from '@/services/liveTradingService';
import { useScanner } from '@/context/ScannerContext';

// ─── Formatters ─────────────────────────────────────────────────────────
function fmtDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}m ${s}s`;
  }
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function fmtCurrency(v: number, decimals = 2): string {
  if (!Number.isFinite(v)) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(v);
}

function fmtPct(v: number, decimals = 2): string {
  if (!Number.isFinite(v)) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(decimals)}%`;
}

// ─── Equity Sparkline ──────────────────────────────────────────────────
function EquitySparkline({
  trades,
  initialBalance,
}: {
  trades: CompletedLiveTrade[];
  initialBalance: number;
}) {
  const points = useMemo(() => {
    if (!trades || trades.length === 0) return [];
    const sorted = [...trades].reverse();
    let equity = initialBalance;
    const pts = [{ x: 0, y: equity }];
    sorted.forEach((t, i) => {
      equity += t.pnl;
      pts.push({ x: i + 1, y: equity });
    });
    return pts;
  }, [trades, initialBalance]);

  if (points.length < 2) {
    return (
      <div
        className="mono"
        style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 10,
          color: 'var(--fg-4)',
          letterSpacing: '.18em',
          textTransform: 'uppercase',
        }}
      >
        — awaiting trades —
      </div>
    );
  }

  const minY = Math.min(...points.map((p) => p.y));
  const maxY = Math.max(...points.map((p) => p.y));
  const rangeY = maxY - minY || 1;
  const w = 280;
  const h = 56;
  const pad = 2;

  const pathD = points
    .map((p, i) => {
      const x = pad + (p.x / (points.length - 1)) * (w - 2 * pad);
      const y = h - pad - ((p.y - minY) / rangeY) * (h - 2 * pad);
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');

  const lastPt = points[points.length - 1];
  const isUp = lastPt.y >= initialBalance;
  const strokeColor = isUp ? '#34d399' : '#f87171';
  const fillGradId = 'lv-eq-grad';
  const lastPtX = pad + (lastPt.x / (points.length - 1)) * (w - 2 * pad);
  const lastPtY = h - pad - ((lastPt.y - minY) / rangeY) * (h - 2 * pad);
  const areaD = `${pathD} L ${lastPtX.toFixed(1)} ${h} L ${pad.toFixed(1)} ${h} Z`;

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 64 }}>
      <defs>
        <linearGradient id={fillGradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={strokeColor} stopOpacity="0.18" />
          <stop offset="100%" stopColor={strokeColor} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaD} fill={`url(#${fillGradId})`} />
      <path
        d={pathD}
        fill="none"
        stroke={strokeColor}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={lastPtX} cy={lastPtY} r="3" fill={strokeColor} />
    </svg>
  );
}

// ─── Metric Tile ───────────────────────────────────────────────────────
function MetricTile({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: 'green' | 'red' | 'amber' | 'blue';
}) {
  const valueColor =
    accent === 'green'
      ? 'var(--green)'
      : accent === 'red'
        ? 'var(--red)'
        : accent === 'amber'
          ? 'var(--amber)'
          : accent === 'blue'
            ? 'var(--blue)'
            : 'var(--fg-1)';
  return (
    <div
      style={{
        padding: '12px 14px',
        border: '1px solid var(--border-soft)',
        borderRadius: 10,
        background: 'rgba(0,0,0,.35)',
      }}
    >
      <div
        className="mono"
        style={{
          fontSize: 9,
          color: 'var(--fg-4)',
          letterSpacing: '.18em',
          textTransform: 'uppercase',
          marginBottom: 8,
        }}
      >
        {label}
      </div>
      <div
        className="mono"
        style={{
          fontSize: 22,
          fontWeight: 800,
          color: valueColor,
          letterSpacing: '-0.01em',
          lineHeight: 1,
          marginBottom: 4,
        }}
      >
        {value}
      </div>
      {sub && (
        <div
          className="mono"
          style={{
            fontSize: 10,
            color: 'var(--fg-4)',
          }}
        >
          {sub}
        </div>
      )}
    </div>
  );
}

// ─── Position Row ──────────────────────────────────────────────────────
function PositionRow({ position }: { position: LivePosition }) {
  const isLong = position.direction === 'LONG';
  const isProfit = position.unrealized_pnl >= 0;
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '90px 70px 1fr 1fr 1fr 1fr',
        gap: 10,
        padding: '10px 12px',
        borderTop: '1px solid var(--border-soft)',
        alignItems: 'center',
      }}
    >
      <span className="mono" style={{ fontWeight: 700 }}>
        {position.symbol}
      </span>
      <Chip kind={isLong ? 'green' : 'red'}>{isLong ? 'LONG' : 'SHORT'}</Chip>
      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-2)' }}>
        entry {position.entry_price}
      </span>
      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-2)' }}>
        mark {position.current_price}
      </span>
      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-2)' }}>
        sl {position.stop_loss}
      </span>
      <span
        className="mono"
        style={{
          fontWeight: 700,
          color: isProfit ? 'var(--green)' : 'var(--red)',
          textAlign: 'right',
        }}
      >
        {fmtCurrency(position.unrealized_pnl)} ({fmtPct(position.unrealized_pnl_pct)})
      </span>
    </div>
  );
}

// ─── Mode Pill ─────────────────────────────────────────────────────────
function ModePill({ mode }: { mode: LiveTradingStatus['trading_mode'] }) {
  if (mode === 'live') return <Chip kind="red">● LIVE — REAL MONEY</Chip>;
  if (mode === 'testnet') return <Chip kind="amber">● TESTNET</Chip>;
  if (mode === 'dry_run') return <Chip kind="blue">● DRY RUN</Chip>;
  return <Chip>● IDLE</Chip>;
}

// ─── Status Pill ───────────────────────────────────────────────────────
function StatusPill({ status }: { status: LiveTradingStatus['status'] }) {
  if (status === 'running') return <Chip kind="green">● RUNNING</Chip>;
  if (status === 'kill_switched') return <Chip kind="red">● KILL-SWITCHED</Chip>;
  if (status === 'error') return <Chip kind="red">● ERROR</Chip>;
  if (status === 'stopped') return <Chip kind="amber">● STOPPED</Chip>;
  return <Chip>● IDLE</Chip>;
}

// ─── Main Component ────────────────────────────────────────────────────
export function BotStatus() {
  const navigate = useNavigate();
  // Scanner-mode catalog drives the GauntletBreakdown mode-delta strip.
  // Selector is intentionally wide — useScanner is mounted at the App
  // root so this is always available; if it ever isn't (test harness),
  // GauntletBreakdown gracefully no-ops the strip when modes are empty.
  const { scannerModes, selectedMode } = useScanner();
  const [status, setStatus] = useState<LiveTradingStatus | null>(null);
  const [trades, setTrades] = useState<CompletedLiveTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [stopping, setStopping] = useState(false);
  const [killing, setKilling] = useState(false);
  const [showKillConfirm, setShowKillConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeOutput, setAnalyzeOutput] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [tradesError, setTradesError] = useState<string | null>(null);
  // Phase 3g.ii.c — PipelineTracer drawer state. Non-null = drawer open.
  const [tracerSignalId, setTracerSignalId] = useState<string | null>(null);
  // Phase 3g.ii.f — DiagnoseWizard modal state.
  // `diagnoseOpenedAtMs` captures Date.now() at the instant the operator
  // clicks RUN DIAGNOSE so stale-cycle checks use a fresh reference time
  // every open (rather than the page-mount `now`). Snapshot tests freeze
  // the global Date constructor before goto so this still yields the
  // deterministic frozen ts during capture.
  const [diagnoseOpen, setDiagnoseOpen] = useState(false);
  const [diagnoseOpenedAtMs, setDiagnoseOpenedAtMs] = useState<number>(() => Date.now());

  const fetchFailCount = useRef(0);
  const fastPollRef = useRef(false);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const connectionErrorRef = useRef<string | null>(null);
  connectionErrorRef.current = connectionError;

  // Static now for snapshot determinism. Footer renders this once.
  const [now] = useState(() => new Date());

  // Snapshot-ready handshake — StrictMode-safe.
  useEffect(() => {
    document.body.setAttribute('data-snapshot-ready', 'true');
    return () => {
      document.body.removeAttribute('data-snapshot-ready');
    };
  }, []);

  const loadStatus = useCallback(async () => {
    try {
      const data = await liveTradingService.getStatus();
      setStatus(data);
      fastPollRef.current =
        (data.positions?.length ?? 0) > 0 || data.current_scan?.status === 'running';
      fetchFailCount.current = 0;
      if (connectionErrorRef.current) setConnectionError(null);
    } catch (e) {
      fetchFailCount.current += 1;
      const detail = e instanceof Error ? e.message : 'Unknown error';
      setConnectionError(`Backend unreachable: ${detail}`);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTrades = useCallback(async () => {
    try {
      const data = await liveTradingService.getHistory(50);
      if (data && Array.isArray(data.trades)) {
        setTrades(data.trades);
        setTradesError(null);
      } else {
        setTradesError('Trade history response missing trades array');
      }
    } catch (e) {
      setTradesError(e instanceof Error ? e.message : 'Could not load trade history');
    }
  }, []);

  useEffect(() => {
    loadStatus();
    loadTrades();
    const schedule = () => {
      const delay = fastPollRef.current ? 2000 : 10000;
      pollTimerRef.current = setTimeout(async () => {
        await Promise.all([loadStatus(), loadTrades()]);
        schedule();
      }, delay);
    };
    schedule();
    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, [loadStatus, loadTrades]);

  const handleStop = async () => {
    setStopping(true);
    try {
      await liveTradingService.stop();
      await loadStatus();
      await loadTrades();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setStopping(false);
    }
  };

  const handleKillSwitch = async () => {
    setKilling(true);
    setShowKillConfirm(false);
    try {
      await liveTradingService.killSwitch();
      await loadStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setKilling(false);
    }
  };

  const handleReset = async () => {
    try {
      await liveTradingService.reset();
      navigate('/bot/setup');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setAnalyzeOutput(null);
    setAnalyzeError(null);
    try {
      const result = await liveTradingService.analyzeSession();
      setAnalyzeOutput(result.output || '(no output)');
      if (result.error) setAnalyzeError(result.error);
    } catch (e) {
      setAnalyzeError(e instanceof Error ? e.message : String(e));
    } finally {
      setAnalyzing(false);
    }
  };

  const isRunning = status?.status === 'running';
  const isKilled = status?.status === 'kill_switched';
  const tradingMode = status?.trading_mode ?? 'idle';
  const isLive = tradingMode === 'live';
  const stats = status?.statistics;
  const balance = status?.balance;
  const initialBalance = balance?.initial ?? 0;
  const positions = status?.positions ?? [];
  const signalLog = status?.signal_log ?? [];
  const cfg = status?.config;

  const subtitleText = isLive
    ? 'real money — phemex perpetuals'
    : tradingMode === 'testnet'
      ? 'testnet — simulated fills'
      : tradingMode === 'dry_run'
        ? 'dry run — no orders sent'
        : 'idle — awaiting deployment';

  return (
    <div className="page-shell" id="main-content">
      <Reticle />

      <PageHead
        icon="●"
        title="Live Deployment"
        subtitle={subtitleText}
        accent={isLive ? 'red' : 'amber'}
        badges={
          <>
            <ModePill mode={tradingMode} />
            <StatusPill status={status?.status ?? 'idle'} />
          </>
        }
      />

      {/* ── Error banners ─────────────────────────────────────────── */}
      {connectionError && (
        <div
          style={{
            margin: '14px 0',
            padding: '12px 14px',
            border: '1px solid var(--amber)',
            borderRadius: 10,
            background: 'rgba(234,179,8,.08)',
            color: 'var(--amber)',
            fontSize: 12,
          }}
        >
          ⚠ {connectionError}
        </div>
      )}
      {error && (
        <div
          style={{
            margin: '14px 0',
            padding: '12px 14px',
            border: '1px solid var(--red)',
            borderRadius: 10,
            background: 'rgba(239,68,68,.08)',
            color: 'var(--red)',
            fontSize: 12,
          }}
        >
          ⚠ {error}
        </div>
      )}

      {loading && !status && (
        <div
          className="panel"
          style={{
            margin: '14px 0',
            padding: 32,
            textAlign: 'center',
            color: 'var(--fg-3)',
          }}
        >
          <span className="mono" style={{ letterSpacing: '.2em' }}>
            ESTABLISHING UPLINK…
          </span>
        </div>
      )}

      {status && (
        <div style={{ display: 'grid', gap: 14, marginTop: 14 }}>
          {/* ── Command Center ─────────────────────────────────── */}
          <section
            className="panel panel-accent"
            style={{
              padding: 18,
              borderColor: isRunning
                ? 'rgba(74,222,128,.35)'
                : isLive
                  ? 'rgba(239,68,68,.35)'
                  : 'rgba(234,179,8,.25)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                gap: 14,
                flexWrap: 'wrap',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
                <div
                  style={{
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    background: isRunning
                      ? 'var(--green)'
                      : isLive
                        ? 'var(--red)'
                        : 'var(--amber)',
                    boxShadow: isRunning
                      ? '0 0 14px rgba(74,222,128,.9)'
                      : isLive
                        ? '0 0 14px rgba(239,68,68,.9)'
                        : '0 0 14px rgba(234,179,8,.9)',
                    flexShrink: 0,
                  }}
                />
                <div>
                  <div
                    className="mono"
                    style={{
                      fontSize: 16,
                      fontWeight: 800,
                      letterSpacing: '.04em',
                      textTransform: 'uppercase',
                      color: 'var(--fg-1)',
                    }}
                  >
                    Phantom Engine
                  </div>
                  <div
                    className="mono"
                    style={{
                      fontSize: 10,
                      color: 'var(--fg-4)',
                      letterSpacing: '.16em',
                      marginTop: 4,
                      textTransform: 'uppercase',
                    }}
                  >
                    uptime {fmtDuration(status.uptime_seconds || 0)}
                    {status.session_id && (
                      <>
                        {' · '}
                        session {status.session_id.slice(0, 8)}
                      </>
                    )}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {isRunning ? (
                  <>
                    <button
                      type="button"
                      className="btn btn-red"
                      onClick={handleStop}
                      disabled={stopping}
                      style={{ fontSize: 11 }}
                    >
                      {stopping ? '↻ STOPPING' : '■ STOP'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-red"
                      onClick={() => setShowKillConfirm(true)}
                      style={{ fontSize: 11 }}
                    >
                      ☠ KILL
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      className="btn btn-green"
                      onClick={() => navigate('/bot/setup')}
                      style={{ fontSize: 11 }}
                    >
                      ▶ RECONFIGURE
                    </button>
                    <button
                      type="button"
                      className="btn"
                      onClick={handleReset}
                      style={{ fontSize: 11 }}
                    >
                      ↺ RESET
                    </button>
                  </>
                )}
                <button
                  type="button"
                  className="btn btn-blue"
                  onClick={handleAnalyze}
                  disabled={analyzing}
                  style={{ fontSize: 11 }}
                >
                  {analyzing ? '↻ ANALYZING' : '⊞ ANALYZE'}
                </button>
              </div>
            </div>

            {/* Kill confirm */}
            {showKillConfirm && (
              <div
                style={{
                  marginTop: 14,
                  padding: 14,
                  border: '1px solid var(--red)',
                  borderRadius: 10,
                  background: 'rgba(239,68,68,.08)',
                }}
              >
                <div
                  className="mono"
                  style={{
                    fontWeight: 700,
                    color: 'var(--red)',
                    fontSize: 12,
                    marginBottom: 6,
                  }}
                >
                  ☠ CONFIRM KILL SWITCH
                </div>
                <div style={{ fontSize: 11, color: 'var(--fg-2)', marginBottom: 10 }}>
                  Immediately cancel all orders and close all positions at market price.
                  {isLive && ' This uses real money.'}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => setShowKillConfirm(false)}
                    style={{ fontSize: 10 }}
                  >
                    CANCEL
                  </button>
                  <button
                    type="button"
                    className="btn btn-red"
                    onClick={handleKillSwitch}
                    disabled={killing}
                    style={{ fontSize: 10 }}
                  >
                    {killing ? '↻ EXECUTING' : '☠ CONFIRM KILL SWITCH'}
                  </button>
                </div>
              </div>
            )}

            {isKilled && (
              <div
                style={{
                  marginTop: 14,
                  padding: 12,
                  border: '1px solid var(--red)',
                  borderRadius: 10,
                  background: 'rgba(239,68,68,.08)',
                  color: 'var(--red)',
                  fontSize: 12,
                  fontWeight: 700,
                }}
              >
                ☠ KILL SWITCH ACTIVATED — all positions closed
              </div>
            )}

            {/* Metric grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
                gap: 10,
                marginTop: 14,
              }}
            >
              <MetricTile
                label="Uptime"
                value={fmtDuration(status.uptime_seconds || 0)}
                sub="session running"
              />
              <MetricTile
                label="Regime"
                value={
                  status.regime && status.regime.composite !== 'unknown'
                    ? status.regime.composite.replace(/_/g, ' ').split(' ')[0].toUpperCase()
                    : '—'
                }
                sub={status.regime?.composite?.replace(/_/g, ' ') ?? 'no read'}
                accent="blue"
              />
              <MetricTile
                label="Next Scan"
                value={
                  isRunning && status.next_scan_in_seconds != null
                    ? fmtDuration(Math.round(status.next_scan_in_seconds))
                    : '—'
                }
                sub="until next sweep"
                accent={isRunning ? 'amber' : undefined}
              />
              <MetricTile
                label="Min Score"
                value={cfg?.min_confluence != null ? `≥${cfg.min_confluence}` : 'AUTO'}
                sub="confluence threshold"
              />
            </div>

            {/* Config pills (when present) */}
            {cfg && (
              <div
                style={{
                  display: 'flex',
                  gap: 6,
                  flexWrap: 'wrap',
                  marginTop: 14,
                  paddingTop: 12,
                  borderTop: '1px solid var(--border-soft)',
                }}
              >
                {cfg.sniper_mode && <Chip>{cfg.sniper_mode.toUpperCase()}</Chip>}
                {cfg.duration_hours != null && <Chip>{cfg.duration_hours}H</Chip>}
                {cfg.max_positions != null && <Chip>{cfg.max_positions} SLOTS</Chip>}
                {cfg.risk_per_trade != null && <Chip>{cfg.risk_per_trade}% RISK</Chip>}
                {cfg.leverage != null && cfg.leverage !== 1 && (
                  <Chip>{cfg.leverage}× LEVERAGE</Chip>
                )}
              </div>
            )}
          </section>

          {/* Analyze output */}
          {(analyzeOutput || analyzeError) && (
            <section className="panel" style={{ padding: 14 }}>
              <SectionHead title="Analyze Session" />
              {analyzeError && (
                <div style={{ color: 'var(--red)', fontSize: 11, marginBottom: 8 }}>
                  ⚠ {analyzeError}
                </div>
              )}
              {analyzeOutput && (
                <pre
                  className="mono"
                  style={{
                    fontSize: 10,
                    color: 'var(--fg-2)',
                    whiteSpace: 'pre-wrap',
                    margin: 0,
                  }}
                >
                  {analyzeOutput}
                </pre>
              )}
            </section>
          )}

          {/* ── Two-column: Equity + Statistics ──────────────────── */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 14,
            }}
          >
            <section className="panel" style={{ padding: 14 }}>
              <SectionHead
                title="Equity Curve"
                right={
                  <span
                    className="mono"
                    style={{ fontSize: 10, color: 'var(--fg-4)' }}
                  >
                    {trades.length} trades
                  </span>
                }
              />
              {tradesError && (
                <div style={{ color: 'var(--amber)', fontSize: 10, marginBottom: 6 }}>
                  ⚠ {tradesError}
                </div>
              )}
              <EquitySparkline trades={trades} initialBalance={initialBalance} />
              <div
                className="mono"
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: 10,
                  color: 'var(--fg-4)',
                  marginTop: 8,
                  textTransform: 'uppercase',
                  letterSpacing: '.14em',
                }}
              >
                <span>start {fmtCurrency(initialBalance)}</span>
                <span>now {fmtCurrency(balance?.equity ?? initialBalance)}</span>
                <span
                  style={{
                    color:
                      (balance?.pnl ?? 0) >= 0 ? 'var(--green)' : 'var(--red)',
                  }}
                >
                  {fmtCurrency(balance?.pnl ?? 0)} ({fmtPct(balance?.pnl_pct ?? 0)})
                </span>
              </div>
            </section>

            <section className="panel" style={{ padding: 14 }}>
              <SectionHead title="Statistics" />
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: 10,
                }}
              >
                <MetricTile
                  label="Trades"
                  value={String(stats?.total_trades ?? 0)}
                  sub={`${stats?.winning_trades ?? 0}W / ${stats?.losing_trades ?? 0}L`}
                />
                <MetricTile
                  label="Win Rate"
                  value={
                    stats?.win_rate != null
                      ? `${(stats.win_rate * 100).toFixed(0)}%`
                      : '—'
                  }
                  sub="of closed"
                  accent={
                    stats && stats.win_rate >= 0.5 ? 'green' : undefined
                  }
                />
                <MetricTile
                  label="Avg R:R"
                  value={
                    stats?.avg_rr != null ? `${stats.avg_rr.toFixed(2)}R` : '—'
                  }
                  sub="realised"
                />
                <MetricTile
                  label="Best"
                  value={fmtCurrency(stats?.best_trade ?? 0)}
                  accent="green"
                />
                <MetricTile
                  label="Worst"
                  value={fmtCurrency(stats?.worst_trade ?? 0)}
                  accent="red"
                />
                <MetricTile
                  label="Max DD"
                  value={
                    stats?.max_drawdown != null
                      ? fmtPct(stats.max_drawdown * 100)
                      : '—'
                  }
                  accent="amber"
                />
              </div>
            </section>
          </div>

          {/* ── Open Positions ───────────────────────────────────── */}
          <section className="panel" style={{ padding: 14 }}>
            <SectionHead
              title="Open Positions"
              right={
                <span
                  className="mono"
                  style={{ fontSize: 10, color: 'var(--fg-4)' }}
                >
                  {positions.length} active
                </span>
              }
            />
            {positions.length === 0 ? (
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
                — no open positions —
              </div>
            ) : (
              <div>
                <div
                  className="mono"
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '90px 70px 1fr 1fr 1fr 1fr',
                    gap: 10,
                    padding: '8px 12px',
                    fontSize: 9,
                    color: 'var(--fg-4)',
                    letterSpacing: '.18em',
                    textTransform: 'uppercase',
                  }}
                >
                  <span>Symbol</span>
                  <span>Side</span>
                  <span>Entry</span>
                  <span>Mark</span>
                  <span>Stop</span>
                  <span style={{ textAlign: 'right' }}>uPnL</span>
                </div>
                {positions.map((p) => (
                  <PositionRow key={p.position_id} position={p} />
                ))}
              </div>
            )}
          </section>

          {/* ── Signal Log ────────────────────────────────────────── */}
          <section className="panel" style={{ padding: 14 }}>
            <SectionHead
              title="Signal Log"
              right={
                <span
                  className="mono"
                  style={{ fontSize: 10, color: 'var(--fg-4)' }}
                >
                  {signalLog.length} entries
                </span>
              }
            />
            {signalLog.length === 0 ? (
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
                — signal log empty —
              </div>
            ) : (
              <div style={{ display: 'grid', gap: 6 }}>
                {signalLog.slice(0, 10).map((entry, i) => {
                  const ok = entry.result === 'executed';
                  const filtered = entry.result === 'filtered';
                  return (
                    <div
                      key={`${entry.symbol}-${i}`}
                      className="mono"
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '90px 1fr 80px',
                        gap: 8,
                        padding: '6px 8px',
                        fontSize: 11,
                        borderBottom: '1px solid var(--border-soft)',
                      }}
                    >
                      <span style={{ fontWeight: 700 }}>{entry.symbol}</span>
                      <span style={{ color: 'var(--fg-3)' }}>
                        {entry.reason || entry.setup_type || '—'}
                      </span>
                      <span
                        style={{
                          textAlign: 'right',
                          color: ok
                            ? 'var(--green)'
                            : filtered
                              ? 'var(--red)'
                              : 'var(--fg-4)',
                        }}
                      >
                        {ok ? '✓ exec' : filtered ? '✗ filter' : '⚠ err'}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* ── Gauntlet Breakdown — Phase 3g.ii.b ─────────────────── */}
          {/* Per-row click opens the PipelineTracer drawer (3g.ii.c).   */}
          <GauntletBreakdown
            signals={signalLog}
            onSignalClick={(id) => setTracerSignalId(id)}
            scannerModes={scannerModes}
            currentModeName={selectedMode?.name ?? null}
          />

          {/* ── Confluence Distribution — Phase 3g.ii.d ───────────── */}
          <ConfluenceBreakdown />

          {/* ── Deferred surfaces row ────────────────────────────── */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: 14,
            }}
          >
            <UniversePanel />
            <section className="panel" style={{ padding: 14 }}>
              <SectionHead title="Diagnose" />
              <div style={{ padding: '10px 4px 4px' }}>
                <div
                  className="mono"
                  style={{
                    fontSize: 10,
                    color: 'var(--fg-3)',
                    letterSpacing: '.10em',
                    marginBottom: 10,
                  }}
                >
                  9-step playbook orchestrating phemex / universe / cycles /
                  signals_per_stage / fills checks. Failed steps deep-link
                  to the right tuning surface.
                </div>
                <button
                  type="button"
                  className="btn"
                  onClick={() => {
                    setDiagnoseOpenedAtMs(Date.now());
                    setDiagnoseOpen(true);
                  }}
                  style={{ width: '100%', fontSize: 10, letterSpacing: '.16em' }}
                >
                  RUN DIAGNOSE →
                </button>
              </div>
            </section>
          </div>
        </div>
      )}

      <FooterStatus latency={32} build={`${now.toISOString().slice(0, 10)}`} />

      {/* PipelineTracer drawer — Phase 3g.ii.c. Renders only when a
          signal id is selected via Gauntlet detail row click. */}
      <PipelineTracer
        signalId={tracerSignalId}
        onClose={() => setTracerSignalId(null)}
      />

      {/* DiagnoseWizard — Phase 3g.ii.f. 9-step playbook modal. nowSec
          is captured at modal open time (Date.now() snapshot in the click
          handler) so stale-cycle checks use a fresh reference each time;
          the wizard's effect re-fetches all three observability endpoints
          each time `open` flips true. */}
      <DiagnoseWizard
        open={diagnoseOpen}
        onClose={() => setDiagnoseOpen(false)}
        status={status}
        nowSec={diagnoseOpenedAtMs / 1000}
      />
    </div>
  );
}

export default BotStatus;
