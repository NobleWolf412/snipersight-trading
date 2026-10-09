import { BotStrategySettings } from '@/components/hud/BotStrategySettings';
import { paperSessionNeedsAttention } from '@/services/paperTradingService';
/**
 * RangeBot — full paper-trading equivalent of the live bot
 *
 * Operator intent: "a page just like bot but for paper trading — this is
 * a simulated version of the bot. Including bot setup, but like for paper trading."
 *
 * Tabbed shell: #setup / #status — mirrors the live bot's /bot/setup + /bot/status
 * split, but in one page under /training/range.
 *
 * Setup tab:
 *   - Paper-specific config: initial_balance slider (not real money)
 *   - Same execution sliders as BotSetup: risk%, leverage, max positions,
 *     duration, scan interval, confluence threshold
 *   - Execution toggles: trailing stop, breakeven
 *   - Universe scope: majors/altcoins + size
 *   - Paper-specific: slippage_bps, fee_rate (simulated fill realism)
 *   - ARM button — starts paper bot + switches to #status tab
 *   - No preflight check, no kill-switch acknowledgment (simulated capital)
 *
 * Status tab:
 *   - PAPER MODE banner (always visible)
 *   - CycleHeartbeat strip
 *   - Command Center (glowing dot, uptime, STOP/RESET buttons, metric grid, config pills)
 *   - Equity Curve + Statistics (2-column)
 *   - Open Positions (6-column, direction-symmetric)
 *   - Activity Log (recent_activity — paper bot logs signals, fills, exits)
 *   - Exit Reasons + By-Trade-Type breakdown (2-column)
 *
 * §15 boundary:
 *   - ALL API calls go through paperTradingService (hits /api/paper-trading/*).
 *   - No shared code with liveTradingService; structurally incapable of
 *     dispatching live orders.
 *   - sniper_mode sourced from botConfig.sniperMode (read-only consumer).
 *
 * Direction-agnostic: LONG/SHORT positions rendered by identical code paths.
 * Chip color differs; logic is fully symmetric per CLAUDE.md §10 #3.
 *
 * StrictMode-safe: cancelled flag + setTimeout recursion.
 * Snapshot-ready: body[data-snapshot-ready="true"] after first poll.
 */
import {
Chip,
CycleHeartbeat,
FooterStatus,
PageHead,
Reticle
} from '@/components/hud';
import { useScanner } from '@/context/ScannerContext';
import {
paperTradingService,
type CompletedPaperTrade,
type PaperTradingConfigRequest,
type PaperTradingStatus
} from '@/services/paperTradingService';
import { tradeJournalService,type JournalAggregate } from '@/services/tradeJournalService';
import { useCallback,useEffect,useRef,useState } from 'react';
import { useLocation,useNavigate } from 'react-router-dom';

// ─── Constants ─────────────────────────────────────────────────────────
const FAST_POLL_MS = 2_000;
const SLOW_POLL_MS = 10_000;

import { DEFAULT_SETUP,PaperConfig,PaperModeBanner,SetupTab,StatusTab } from './RangeBotViews';

export function RangeBot() {
  const [draft, setDraft] = useState<PaperConfig>(DEFAULT_SETUP);
  const { botConfig, setBotConfig } = useScanner();
  const location = useLocation();
  const navigate = useNavigate();

  // Tab state — #setup or #status; default: setup when idle, status when running
  const [status, setStatus] = useState<PaperTradingStatus | null>(null);
  const [trades, setTrades] = useState<CompletedPaperTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [armErr, setArmErr] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [connErr, setConnErr] = useState<string | null>(null);
  const [tradesErr, setTradesErr] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  // Cross-session lifetime aggregate (matches /bot/status). Sourced from
  // the journal so it survives bot restarts and reflects every closed
  // trade — distinct from balance.pnl (current-session equity − initial)
  // and stats.total_pnl (current-session realized only).
  const [lifetime, setLifetime] = useState<JournalAggregate | null>(null);
  const [lifetimeErr, setLifetimeErr] = useState<string | null>(null);

  const cancelledRef = useRef(false);
  const fastPollRef = useRef(false);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const connErrRef = useRef<string | null>(null);
  connErrRef.current = connErr;

  // Compute active tab from hash; default to setup when idle, status when running
  const isRunning = status?.status === 'running';
  const hashTab = location.hash === '#status' ? 'status' : location.hash === '#setup' ? 'setup' : null;
  const activeTab = hashTab ?? (paperSessionNeedsAttention(status) ? 'status' : 'setup');

  // Snapshot-ready handshake
  useEffect(() => {
    if (ready) {
      document.body.setAttribute('data-snapshot-ready', 'true');
      return () => { document.body.removeAttribute('data-snapshot-ready'); };
    }
  }, [ready]);

  const loadStatus = useCallback(async () => {
    try {
      const data = await paperTradingService.getStatus();
      setStatus(data);
      fastPollRef.current = data.status === 'running' || (data.positions?.length ?? 0) > 0;
      if (connErrRef.current) setConnErr(null);
    } catch (e) {
      setConnErr(`Backend unreachable: ${e instanceof Error ? e.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
      if (!ready) setReady(true);
    }
  }, [ready]);

  const loadTrades = useCallback(async () => {
    try {
      const data = await paperTradingService.getHistory(50);
      if (data && Array.isArray(data.trades)) {
        setTrades(data.trades);
        setTradesErr(null);
      } else {
        setTradesErr('Trade history response missing trades array');
      }
    } catch (e) {
      setTradesErr(e instanceof Error ? e.message : 'Could not load trade history');
    }
  }, []);

  const loadLifetime = useCallback(async () => {
    try {
      // limit=1 keeps the trades payload tiny — the aggregate envelope is
      // always computed over the full journal regardless of limit.
      const data = await tradeJournalService.getJournal({ limit: 1 });
      if (data && data.aggregate) {
        setLifetime(data.aggregate);
        setLifetimeErr(null);
      } else {
        setLifetimeErr('Journal aggregate missing');
      }
    } catch (e) {
      setLifetimeErr(e instanceof Error ? e.message : 'Could not load lifetime totals');
    }
  }, []);

  useEffect(() => {
    cancelledRef.current = false;
    loadStatus();
    loadTrades();
    loadLifetime();
    const schedule = () => {
      if (cancelledRef.current) return;
      const delay = fastPollRef.current ? FAST_POLL_MS : SLOW_POLL_MS;
      pollTimerRef.current = setTimeout(async () => {
        if (cancelledRef.current) return;
        await Promise.all([loadStatus(), loadTrades(), loadLifetime()]);
        schedule();
      }, delay);
    };
    schedule();
    return () => {
      cancelledRef.current = true;
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleArm = useCallback(async (cfg: PaperConfig) => {
    setWorking(true);
    setArmErr(null);
    try {
      const req: PaperTradingConfigRequest = {
        exchange: 'phemex',
        sniper_mode: botConfig.sniperMode ?? 'stealth',
        selection_mode: botConfig.selectionMode ?? 'fixed',
        allowed_modes: botConfig.allowedModes ?? ['strike', 'surgical', 'stealth'],
        initial_balance: cfg.initial_balance,
        risk_per_trade: cfg.risk_per_trade,
        max_positions: cfg.max_positions,
        leverage: cfg.leverage,
        duration_hours: cfg.duration_hours,
        scan_interval_minutes: cfg.scan_interval_minutes,
        min_confluence: cfg.min_confluence,
        trailing_stop: cfg.trailing_stop,
        trailing_activation: cfg.trailing_activation,
        breakeven_after_target: cfg.breakeven_after_target,
        majors: cfg.majors,
        altcoins: cfg.altcoins,
        meme_mode: cfg.meme_mode,
        universe_size: cfg.universe_size,
        slippage_bps: cfg.slippage_bps,
        fee_rate: cfg.fee_rate / 100, // slider is in %, service expects decimal
        use_testnet: false,
        sensitivity_preset: 'custom',
        execution_mode: cfg.execution_mode,
        macro_overlay_enabled: cfg.macro_overlay_enabled,
        liquidity_mode: cfg.liquidity_mode,
        participation_rate: cfg.participation_rate,
        hard_min_volume_usdt: cfg.hard_min_volume_usdt,
        depth_aware_admission: cfg.depth_aware_admission,
        min_order_risk_guard: cfg.min_order_risk_guard,
        liquidation_safety_guard: cfg.liquidation_safety_guard,
      };
      await paperTradingService.start(req);
      await Promise.all([loadStatus(), loadTrades()]);
      navigate('/training/range#status', { replace: true });
    } catch (e) {
      console.warn('[RangeBot] arm error:', e);
      setArmErr(String((e as Error)?.message ?? e));
    } finally {
      setWorking(false);
    }
  }, [botConfig, loadStatus, loadTrades, navigate]);

  const handleStop = useCallback(async () => {
    setWorking(true);
    setActionErr(null);
    try {
      await paperTradingService.stop();
      await Promise.all([loadStatus(), loadTrades()]);
    } catch (e) {
      console.warn('[RangeBot] stop error:', e);
      setActionErr(String((e as Error)?.message ?? e));
    } finally {
      setWorking(false);
    }
  }, [loadStatus, loadTrades]);

  const handleReset = useCallback(async () => {
    setWorking(true);
    setActionErr(null);
    try {
      await paperTradingService.reset();
      await Promise.all([loadStatus(), loadTrades()]);
      navigate('/training/range#setup', { replace: true });
    } catch (e) {
      console.warn('[RangeBot] reset error:', e);
      setActionErr(String((e as Error)?.message ?? e));
    } finally {
      setWorking(false);
    }
  }, [loadStatus, loadTrades, navigate]);

  return (
    <div className="page-shell" id="main-content">
      <Reticle />

      <PageHead
        icon="◉"
        title="Paper session"
        subtitle="Configure and monitor simulated execution"
        accent="amber"
        badges={
          <>
            <Chip kind="amber">◉ PAPER MODE</Chip>
            <Chip kind={isRunning ? 'green' : undefined}>
              {isRunning ? '● RUNNING' : '○ IDLE'}
            </Chip>
          </>
        }
      />

      <PaperModeBanner />

      {/* Tab switcher */}
      <div
        style={{
          display: 'flex',
          gap: 4,
          marginBottom: 14,
          borderBottom: '1px solid var(--border-soft)',
          paddingBottom: 0,
        }}
      >
        {(['setup', 'status'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => navigate(`/training/range#${tab}`, { replace: true })}
            style={{
              padding: '8px 18px',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === tab ? '2px solid var(--amber)' : '2px solid transparent',
              color: activeTab === tab ? 'var(--amber)' : 'var(--fg-3)',
              fontFamily: 'Share Tech Mono,monospace',
              fontSize: 12,
              letterSpacing: '.16em',
              textTransform: 'uppercase',
              cursor: 'pointer',
              transition: 'color .15s',
              marginBottom: -1,
            }}
          >
            {tab === 'setup' ? '// SETUP' : '// STATUS'}
          </button>
        ))}
      </div>

      {/* Cycle heartbeat — both tabs */}
      <CycleHeartbeat />

      {activeTab === 'setup' && <BotStrategySettings config={botConfig} onChange={setBotConfig} paper />}
      {/* Tab content */}
      {activeTab === 'setup' ? (
        <SetupTab cfg={draft} setCfg={setDraft}
          sniperMode={botConfig.selectionMode === 'adaptive' ? 'adaptive' : botConfig.sniperMode ?? 'stealth'}
          onArm={handleArm}
          working={working}
          armErr={armErr}
          decisionMode={status?.decision_mode}
        />
      ) : (
        <StatusTab
          status={status}
          trades={trades}
          tradesErr={tradesErr}
          connErr={connErr}
          actionErr={actionErr}
          loading={loading}
          working={working}
          lifetime={lifetime}
          lifetimeErr={lifetimeErr}
          onStop={handleStop}
          onReset={handleReset}
        />
      )}

      <FooterStatus />
    </div>
  );
}
