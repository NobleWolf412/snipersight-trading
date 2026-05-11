/**
 * RangeBot — Phase 3 follow-up 3z.e
 *
 * Paper-trading control surface mounted at /training/range. Closes the
 * §11 hidden-bug class identified in 3z.e: the Training Ground RANGE
 * card previously routed to /bot/setup (the LIVE bot interface) while
 * its body copy claimed "no real funds" — silent mode confusion.
 *
 * Operator intent (verbatim from 3z.e briefing): "Real data, real
 * scanner, real signals, real prices — paper money for position
 * simulation. Same engine as live bot, no capital at risk. Stay
 * within the Training Ground context, not Bot Setup."
 *
 * §15 boundary:
 *   - All API calls dispatch through paperTradingService, which is
 *     structurally distinct from liveTradingService (no shared base,
 *     no `mode` parameter that could flip the destination). The
 *     component is incapable of dispatching to live execution.
 *   - sniper_mode hardcoded to 'stealth' below. The brief notes this
 *     value should ultimately come from `botConfig.sniperMode` (Phase
 *     3g forward-track), but that field does not yet exist in the
 *     codebase. Until Phase 3g lands, 'stealth' is the safe default
 *     (matches CLAUDE.md §15 line 117 — "Bot production mode is
 *     STEALTH").
 *   - No reads or writes to `ScannerContext.selectedMode`. Scanner
 *     mode picker is for inspection only and must not influence bot
 *     state per §15 line 117.
 *
 * PAPER MODE banner is always visible. Not behind a toggle. Same
 * prominence as the page title — visual prominence is the entire
 * point of the rebuild.
 *
 * Real-data wiring:
 *   - paperTradingService.getStatus() — primary state source.
 *     Adaptive polling: 3s while running OR positions are open, 10s
 *     otherwise.
 *   - paperTradingService.start(config) — armed-state trigger with a
 *     minimal default config (initial_balance 10000, sniper_mode
 *     'stealth', risk 2%, leverage 1×, max 3 positions, 2-min scan
 *     cadence, 24h duration, majors universe, balanced sensitivity).
 *     Operator can override via Bot Setup later (post-Phase-3g).
 *   - paperTradingService.stop() — graceful stop.
 *   - paperTradingService.reset() — clears history once stopped.
 *
 * Empty-state: when getStatus returns status='idle' with no session,
 * the page renders the IDLE banner + start CTA + empty equity tile
 * (initial 10k placeholder, labelled as such) + "— no paper trades
 * yet —" history empty-state. Backend-offline renders the same shape
 * plus a console.warn at §15 level.
 *
 * Direction-agnostic per CLAUDE.md §10 #3: the page renders both
 * LONG and SHORT positions identically. The PositionRow component
 * tints chip color by direction but the logic is fully symmetric.
 *
 * StrictMode-safe: cancelled flag + setTimeout recursion. Standard
 * pattern from CycleHeartbeat / UniversePanel / BotStatus.
 *
 * Snapshot-ready handshake: body[data-snapshot-ready="true"] is set
 * after the first getStatus call settles (resolved or errored).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Chip, FooterStatus, PageHead, Reticle, SectionHead } from '@/components/hud';
import {
  paperTradingService,
  type CompletedPaperTrade,
  type PaperPosition,
  type PaperTradingStatus,
} from '@/services/paperTradingService';

// ─── Default paper config ───────────────────────────────────────────────
// Phase 3g forward-track: sniper_mode should come from botConfig.sniperMode
// read-only once that field lands. Hardcoded to 'stealth' for now per
// CLAUDE.md §15 line 117 ("Bot production mode is STEALTH").
const DEFAULT_PAPER_CONFIG = {
  exchange: 'phemex',
  sniper_mode: 'stealth',
  initial_balance: 10000,
  risk_per_trade: 2.0,
  max_positions: 3,
  leverage: 1,
  duration_hours: 24,
  scan_interval_minutes: 2,
  trailing_stop: true,
  trailing_activation: 1.5,
  breakeven_after_target: 1,
  sensitivity_preset: 'balanced' as const,
  symbols: [],
  exclude_symbols: [],
  majors: true,
  altcoins: false,
  meme_mode: false,
  slippage_bps: 5.0,
  fee_rate: 0.001,
  use_testnet: false,
  universe_size: 20,
};

const FAST_POLL_MS = 3_000;
const SLOW_POLL_MS = 10_000;

// ─── Formatters ─────────────────────────────────────────────────────────
function fmtMoney(n: number | null | undefined, sign = false): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return '—';
  const sgn = sign && n > 0 ? '+' : '';
  return `${sgn}$${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}${n < 0 ? '' : ''}`;
}

function fmtPct(n: number | null | undefined, sign = false): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return '—';
  const sgn = sign && n > 0 ? '+' : '';
  return `${sgn}${n.toFixed(2)}%`;
}

function fmtDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

// ─── PAPER MODE banner ─────────────────────────────────────────────────
function PaperModeBanner() {
  return (
    <div
      role="banner"
      aria-label="paper mode disclosure"
      style={{
        background: 'rgba(34, 211, 238, 0.08)',
        border: '1px solid rgba(34, 211, 238, 0.4)',
        borderRadius: 4,
        padding: '10px 14px',
        marginBottom: 14,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}
    >
      <span className="mono" style={{ fontSize: 11, color: '#22d3ee', fontWeight: 700, letterSpacing: 1.5 }}>
        ◉ PAPER MODE
      </span>
      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-2)' }}>
        simulated capital · no real funds · same scanner/engine as live bot
      </span>
    </div>
  );
}

// ─── Position row ──────────────────────────────────────────────────────
function PositionRow({ pos }: { pos: PaperPosition }) {
  const isLong = pos.direction === 'LONG';
  const pnlColor = pos.unrealized_pnl >= 0 ? 'var(--green-soft)' : 'var(--red-2)';
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1.2fr 0.8fr 1fr 1fr 1fr',
        gap: 8,
        padding: '8px 12px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        alignItems: 'center',
      }}
    >
      <div>
        <div className="mono" style={{ fontSize: 12, color: 'var(--fg)' }}>{pos.symbol}</div>
        <div className="mono" style={{ fontSize: 10, color: 'var(--fg-3)' }}>{pos.trade_type}</div>
      </div>
      <Chip kind={isLong ? 'green' : 'red'}>{pos.direction}</Chip>
      <div className="mono" style={{ fontSize: 11, color: 'var(--fg-2)' }}>
        entry {pos.entry_price.toFixed(pos.entry_price < 1 ? 4 : 2)}
        <br />
        now {pos.current_price.toFixed(pos.current_price < 1 ? 4 : 2)}
      </div>
      <div className="mono" style={{ fontSize: 11, color: pnlColor }}>
        {fmtMoney(pos.unrealized_pnl, true)}
        <br />
        {fmtPct(pos.unrealized_pnl_pct, true)}
      </div>
      <div className="mono" style={{ fontSize: 10, color: 'var(--fg-3)' }}>
        {pos.trailing_active ? '⟫ trailing' : pos.breakeven_active ? '⊥ be' : 'sl set'}
      </div>
    </div>
  );
}

// ─── Trade history row ─────────────────────────────────────────────────
function TradeHistoryRow({ trade }: { trade: CompletedPaperTrade }) {
  const isWin = trade.pnl > 0;
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1.2fr 0.8fr 1fr 1fr',
        gap: 8,
        padding: '6px 12px',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
        alignItems: 'center',
      }}
    >
      <div className="mono" style={{ fontSize: 11, color: 'var(--fg)' }}>{trade.symbol}</div>
      <Chip kind={trade.direction === 'LONG' ? 'green' : 'red'}>{trade.direction}</Chip>
      <div className="mono" style={{ fontSize: 10, color: isWin ? 'var(--green-soft)' : 'var(--red-2)' }}>
        {fmtMoney(trade.pnl, true)} · {fmtPct(trade.pnl_pct, true)}
      </div>
      <div className="mono" style={{ fontSize: 10, color: 'var(--fg-3)' }}>{trade.exit_reason}</div>
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────
export function RangeBot() {
  const [status, setStatus] = useState<PaperTradingStatus | null>(null);
  const [history, setHistory] = useState<CompletedPaperTrade[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [ready, setReady] = useState(false);
  const cancelledRef = useRef(false);

  // Snapshot-ready handshake — set after first poll resolves.
  useEffect(() => {
    if (ready) {
      document.body.setAttribute('data-snapshot-ready', 'true');
      return () => {
        document.body.removeAttribute('data-snapshot-ready');
      };
    }
  }, [ready]);

  // Adaptive polling — 3s when running or positions open, 10s otherwise.
  useEffect(() => {
    cancelledRef.current = false;
    let tid: number | undefined;

    async function tick() {
      if (cancelledRef.current) return;
      try {
        const [s, h] = await Promise.all([
          paperTradingService.getStatus(),
          paperTradingService.getHistory(20).then((r) => r.trades).catch(() => [] as CompletedPaperTrade[]),
        ]);
        if (cancelledRef.current) return;
        setStatus(s);
        setHistory(h);
        setErr(null);
      } catch (e) {
        if (cancelledRef.current) return;
        console.warn('[RangeBot] poll error:', e);
        setErr(String((e as Error)?.message ?? e));
      } finally {
        if (!ready) setReady(true);
        if (cancelledRef.current) return;
        const isActive =
          status?.status === 'running' ||
          (status?.positions?.length ?? 0) > 0;
        const delay = isActive ? FAST_POLL_MS : SLOW_POLL_MS;
        tid = window.setTimeout(tick, delay);
      }
    }

    void tick();

    return () => {
      cancelledRef.current = true;
      if (tid !== undefined) window.clearTimeout(tid);
    };
    // status?.status is intentionally NOT a dep — adaptive cadence is
    // recomputed inside tick(); listing it as a dep would cause the
    // poll loop to re-arm on every status change and double-fire.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleStart = useCallback(async () => {
    setWorking(true);
    setErr(null);
    try {
      await paperTradingService.start(DEFAULT_PAPER_CONFIG);
    } catch (e) {
      console.warn('[RangeBot] start error:', e);
      setErr(String((e as Error)?.message ?? e));
    } finally {
      setWorking(false);
    }
  }, []);

  const handleStop = useCallback(async () => {
    setWorking(true);
    setErr(null);
    try {
      await paperTradingService.stop();
    } catch (e) {
      console.warn('[RangeBot] stop error:', e);
      setErr(String((e as Error)?.message ?? e));
    } finally {
      setWorking(false);
    }
  }, []);

  const handleReset = useCallback(async () => {
    setWorking(true);
    setErr(null);
    try {
      await paperTradingService.reset();
    } catch (e) {
      console.warn('[RangeBot] reset error:', e);
      setErr(String((e as Error)?.message ?? e));
    } finally {
      setWorking(false);
    }
  }, []);

  const isRunning = status?.status === 'running';
  const isIdle = !status || status.status === 'idle' || status.status === 'stopped';
  const positions = status?.positions ?? [];
  const equity = status?.balance?.equity ?? DEFAULT_PAPER_CONFIG.initial_balance;
  const pnl = status?.balance?.pnl ?? 0;
  const pnlPct = status?.balance?.pnl_pct ?? 0;
  const stats = status?.statistics;

  return (
    <div className="page">
      <Reticle />
      <PageHead
        title="GHOST · paper-trading range"
        subtitle="TRAINING / RANGE · real signals · simulated capital"
        badges={
          <Chip kind={isRunning ? 'green' : 'cyan'}>
            {isRunning ? '● ARMED' : '○ IDLE'}
          </Chip>
        }
      />

      <PaperModeBanner />

      {err ? (
        <div
          className="panel"
          style={{
            borderColor: 'rgba(248, 113, 113, 0.3)',
            background: 'rgba(248, 113, 113, 0.04)',
            padding: '8px 12px',
            marginBottom: 12,
          }}
        >
          <span className="mono" style={{ fontSize: 11, color: 'var(--red-2)' }}>
            ◌ {err}
          </span>
        </div>
      ) : null}

      {/* Control row: status + start/stop + reset */}
      <div className="panel" style={{ marginBottom: 14 }}>
        <SectionHead title="// CONTROL" />
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr 1fr',
            gap: 12,
            padding: 12,
          }}
        >
          <div>
            <div className="metric-label">STATUS</div>
            <div className="metric-value" style={{ color: isRunning ? 'var(--green-soft)' : 'var(--fg-2)' }}>
              {isRunning ? 'RUNNING' : isIdle ? 'IDLE' : (status?.status ?? 'unknown').toUpperCase()}
            </div>
            <div className="mono" style={{ fontSize: 10, color: 'var(--fg-3)', marginTop: 4 }}>
              {status?.uptime_seconds ? `uptime ${fmtDuration(status.uptime_seconds)}` : '—'}
            </div>
          </div>
          <div>
            <div className="metric-label">SIM EQUITY</div>
            <div className="metric-value">{fmtMoney(equity)}</div>
            <div className="mono" style={{ fontSize: 10, color: pnl >= 0 ? 'var(--green-soft)' : 'var(--red-2)', marginTop: 4 }}>
              {fmtMoney(pnl, true)} · {fmtPct(pnlPct, true)}
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, justifyContent: 'center' }}>
            {isRunning ? (
              <button
                className="btn btn-red"
                onClick={handleStop}
                disabled={working}
              >
                {working ? '…' : '◼ STOP'}
              </button>
            ) : (
              <button
                className="btn btn-cyan"
                onClick={handleStart}
                disabled={working}
              >
                {working ? '…' : '▶ ARM PAPER BOT'}
              </button>
            )}
            <button
              className="btn"
              onClick={handleReset}
              disabled={working || isRunning}
              title={isRunning ? 'stop the bot before resetting' : 'clear paper history + reset balance'}
              style={{ fontSize: 10, opacity: isRunning ? 0.4 : 1 }}
            >
              ⟲ RESET
            </button>
          </div>
        </div>
      </div>

      {/* Open positions */}
      <div className="panel" style={{ marginBottom: 14 }}>
        <SectionHead title="// OPEN POSITIONS" right={<Chip kind="cyan">{positions.length}</Chip>} />
        {positions.length === 0 ? (
          <div className="mono" style={{ padding: '14px 12px', fontSize: 11, color: 'var(--fg-3)' }}>
            // no positions open
          </div>
        ) : (
          <div>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1.2fr 0.8fr 1fr 1fr 1fr',
                gap: 8,
                padding: '6px 12px',
                borderBottom: '1px solid rgba(255,255,255,0.1)',
              }}
            >
              <span className="metric-label">SYMBOL</span>
              <span className="metric-label">SIDE</span>
              <span className="metric-label">PRICE</span>
              <span className="metric-label">P&amp;L</span>
              <span className="metric-label">STATE</span>
            </div>
            {positions.map((p) => (
              <PositionRow key={p.position_id} pos={p} />
            ))}
          </div>
        )}
      </div>

      {/* Statistics summary */}
      {stats && stats.total_trades > 0 ? (
        <div className="panel" style={{ marginBottom: 14 }}>
          <SectionHead title="// STATS" />
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: 12,
              padding: 12,
            }}
          >
            <div>
              <div className="metric-label">TOTAL</div>
              <div className="metric-value">{stats.total_trades}</div>
            </div>
            <div>
              <div className="metric-label">WIN RATE</div>
              <div className="metric-value">{fmtPct(stats.win_rate)}</div>
            </div>
            <div>
              <div className="metric-label">EXPECTANCY</div>
              <div className="metric-value">{fmtMoney(stats.expectancy)}</div>
            </div>
            <div>
              <div className="metric-label">MAX DD</div>
              <div className="metric-value">{fmtPct(stats.max_drawdown)}</div>
            </div>
          </div>
        </div>
      ) : null}

      {/* Recent paper trades */}
      <div className="panel" style={{ marginBottom: 14 }}>
        <SectionHead title="// RECENT PAPER TRADES" right={<Chip kind="cyan">{history.length}</Chip>} />
        {history.length === 0 ? (
          <div className="mono" style={{ padding: '14px 12px', fontSize: 11, color: 'var(--fg-3)' }}>
            // no paper trades yet — arm the paper bot to start generating sample trades
          </div>
        ) : (
          <div>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1.2fr 0.8fr 1fr 1fr',
                gap: 8,
                padding: '6px 12px',
                borderBottom: '1px solid rgba(255,255,255,0.1)',
              }}
            >
              <span className="metric-label">SYMBOL</span>
              <span className="metric-label">SIDE</span>
              <span className="metric-label">P&amp;L</span>
              <span className="metric-label">EXIT</span>
            </div>
            {history.map((t) => (
              <TradeHistoryRow key={t.trade_id} trade={t} />
            ))}
          </div>
        )}
      </div>

      <FooterStatus />
    </div>
  );
}
