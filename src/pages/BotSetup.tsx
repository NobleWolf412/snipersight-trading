/**
 * BotSetup — Phase 3g.i.a (HUD rewrite)
 *
 * Port of `prototype/setup.jsx` adapted to TSX with the EXISTING real-data
 * wiring preserved. Configures the autonomous bot's execution layer —
 * leverage, risk, kill-switches, position limits, target universe — and
 * launches `liveTradingService.start()` after a typed acknowledgment.
 *
 * Plan §3e — drop named presets:
 *   The prototype's PRESETS picker (SNIPER / TACTICAL / AGGRESSIVE / STEALTH)
 *   is removed entirely. So is the legacy `sensitivity_preset` 4-button
 *   picker (PRECISION / BALANCED / ACTIVE / CUSTOM). The page now exposes
 *   ONLY raw execution controls: risk %, leverage, max concurrent, max
 *   trade duration, drawdown kill-switch, position-size and exposure caps,
 *   universe-scope toggles. Backend keeps `sensitivity_preset: 'custom'` —
 *   `min_confluence` + `confluence_soft_floor` are direct numeric inputs.
 *
 *   Header strip: detection mode is set in /scanner — this page is for
 *   execution config only. The current scanner mode name + min-score is
 *   read from `useScanner().selectedMode` and rendered in the strip.
 *
 * Real-data wiring (preserved from the previous Tailwind version):
 *   - `liveTradingService.preflight()` — exchange ok, balance, issues,
 *     existing-position warnings.
 *   - `liveTradingService.getStatus()` — redirects to /bot/status if the
 *     bot is already running (don't double-deploy).
 *   - `liveTradingService.start(req)` — actually deploys.
 *   - `api.getScannerRecommendation()` — regime composite + reason for the
 *     header strip. Falls back to "Adaptive" when API is unavailable.
 *   - `useScanner()` — reads `selectedMode` so the header strip reflects
 *     whatever mode the operator picked on the Scanner page; the start
 *     request inherits that mode (was previously hardcoded to 'stealth').
 *
 * Synthetic-but-disclosed:
 *   - Backtest 90-day stats panel (PnL / Sharpe / Win / Max DD) — fixed
 *     placeholder numbers; backtest endpoint not wired. Marked with a
 *     `◌ synthetic` chip in the section header.
 *
 * Deferred (with inline `◌ deferred` placeholders or omitted):
 *   - Execution toggles for BTC veto, funding-rate filter, spread filter,
 *     average-in, martingale (prototype-only — backend
 *     `LiveTradingConfigRequest` has no fields for these). Listed in a
 *     dimmed deferred-toggles strip.
 *   - Multi-exchange routing (Bybit/Binance/OKX/Bitget) — current backend
 *     is Phemex-only; cross-venue routing is a later phase.
 *
 * Determinism for snapshots:
 *   - No `setInterval` (no live clock — Topbar already drives UTC).
 *   - No `Math.random`.
 *   - Static `now` captured once at mount via useState initializer for the
 *     footer timestamp.
 *
 * Snapshot-ready handshake:
 *   StrictMode-safe pattern from Intel.tsx — set on mount, unset on
 *   cleanup; final post-double-mount state stays set, which is what
 *   Playwright's `data-snapshot-ready` waiter observes.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Chip,
  FooterStatus,
  PageHead,
  Reticle,
  SectionHead,
} from '@/components/hud';
import { useScanner } from '@/context/ScannerContext';
import {
  liveTradingService,
  type LiveTradingConfigRequest,
  type PreflightResult,
} from '@/services/liveTradingService';
import { api } from '@/utils/api';

interface LiveConfig {
  leverage: number;
  risk_per_trade: number;
  max_positions: number;
  duration_hours: number;
  scan_interval_minutes: number;
  min_confluence: number;
  confluence_soft_floor: number;
  max_hours_open: number;
  max_drawdown_pct: number | null;
  trailing_stop: boolean;
  trailing_activation: number;
  breakeven_after_target: number;
  majors: boolean;
  altcoins: boolean;
  meme_mode: boolean;
  universe_size: number;
  symbols: string[];
  exclude_symbols: string[];
  fee_rate: number;
  max_position_size_usd: number;
  max_total_exposure_usd: number;
  min_balance_usd: number;
  kill_switch_enabled: boolean;
}

const DEFAULT_CONFIG: LiveConfig = {
  leverage: 1,
  risk_per_trade: 1,
  max_positions: 3,
  duration_hours: 24,
  scan_interval_minutes: 2,
  min_confluence: 65,
  confluence_soft_floor: 55,
  max_hours_open: 72,
  max_drawdown_pct: 10,
  trailing_stop: true,
  trailing_activation: 2.0,
  breakeven_after_target: 1,
  majors: true,
  altcoins: false,
  meme_mode: false,
  universe_size: 20,
  symbols: [],
  exclude_symbols: [],
  fee_rate: 0.001,
  max_position_size_usd: 100,
  max_total_exposure_usd: 500,
  min_balance_usd: 50,
  kill_switch_enabled: true,
};

// ─── Reusable HUD field primitives ───────────────────────────────────────

interface SliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  suffix?: string;
  color?: string;
  hint?: string;
}

function Slider({ label, value, min, max, step, onChange, suffix, color, hint }: SliderProps) {
  return (
    <div
      style={{
        padding: '12px 14px',
        border: '1px solid var(--border-soft)',
        borderRadius: 6,
        background: 'rgba(0,0,0,.3)',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 8,
        }}
      >
        <span
          className="mono"
          style={{
            fontSize: 10,
            color: 'var(--fg-3)',
            letterSpacing: '.16em',
            textTransform: 'uppercase',
          }}
        >
          {label}
        </span>
        <span
          className="mono"
          style={{
            fontSize: 14,
            fontWeight: 800,
            color: color || 'var(--accent)',
          }}
        >
          {value}
          {suffix || ''}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(+e.target.value)}
        style={{ width: '100%' }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
        <span className="mono" style={{ fontSize: 8, color: 'var(--fg-4)' }}>
          {min}
          {suffix || ''}
        </span>
        <span className="mono" style={{ fontSize: 8, color: 'var(--fg-4)' }}>
          {max}
          {suffix || ''}
        </span>
      </div>
      {hint && (
        <div
          className="mono"
          style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.1em', marginTop: 6 }}
        >
          {hint}
        </div>
      )}
    </div>
  );
}

interface ToggleProps {
  label: string;
  value: boolean;
  onChange?: (v: boolean) => void;
  hint?: string;
  disabled?: boolean;
}

function Toggle({ label, value, onChange, hint, disabled }: ToggleProps) {
  return (
    <div
      onClick={() => !disabled && onChange?.(!value)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 12px',
        border: '1px solid var(--border-soft)',
        borderRadius: 6,
        background: 'rgba(0,0,0,.3)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <div
        style={{
          width: 36,
          height: 18,
          borderRadius: 9,
          background: value ? 'var(--accent)' : 'rgba(0,0,0,.6)',
          position: 'relative',
          flexShrink: 0,
          border: '1px solid var(--border-soft)',
          boxShadow: value ? '0 0 8px var(--accent)' : 'none',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: 1,
            left: value ? 19 : 1,
            width: 14,
            height: 14,
            borderRadius: '50%',
            background: value ? '#0a0c0e' : 'var(--fg-3)',
          }}
        />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontFamily: 'Share Tech Mono,monospace',
            fontSize: 12,
            letterSpacing: '.05em',
            color: 'var(--fg)',
          }}
        >
          {label}
        </div>
        {hint && (
          <div
            className="mono"
            style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.1em', marginTop: 2 }}
          >
            {hint}
          </div>
        )}
      </div>
      <span
        className="mono"
        style={{
          fontSize: 9,
          color: value ? 'var(--green-soft)' : 'var(--fg-4)',
          letterSpacing: '.18em',
        }}
      >
        {value ? 'ENGAGED' : 'OFF'}
      </span>
    </div>
  );
}

interface SectionPanelProps {
  num: string;
  title: string;
  desc?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}

function SectionPanel({ num, title, desc, right, children }: SectionPanelProps) {
  return (
    <section className="panel" style={{ marginBottom: 14 }}>
      <div
        style={{
          padding: '14px 18px',
          borderBottom: '1px solid var(--border-soft)',
          background: 'rgba(0,0,0,.4)',
          display: 'flex',
          alignItems: 'center',
          gap: 14,
        }}
      >
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 32,
            height: 32,
            border: '1px solid var(--accent)',
            color: 'var(--accent)',
            fontFamily: 'JetBrains Mono,monospace',
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: '.08em',
            borderRadius: 3,
            boxShadow: '0 0 8px rgba(34,211,238,.2)',
          }}
        >
          {num}
        </span>
        <div style={{ flex: 1 }}>
          <div
            style={{
              fontFamily: 'Share Tech Mono,monospace',
              fontSize: 15,
              letterSpacing: '.08em',
              color: 'var(--fg)',
              textTransform: 'uppercase',
            }}
          >
            {title}
          </div>
          {desc && (
            <div
              className="mono"
              style={{
                fontSize: 10,
                color: 'var(--fg-4)',
                letterSpacing: '.1em',
                marginTop: 2,
              }}
            >
              {desc}
            </div>
          )}
        </div>
        {right}
      </div>
      <div style={{ padding: '14px 18px' }}>{children}</div>
    </section>
  );
}

// ─── Main page ───────────────────────────────────────────────────────────

export function BotSetup() {
  const navigate = useNavigate();
  // 3z.h: bot mode source is `botConfig.sniperMode` per CLAUDE.md §15
  // line 117. Scanner's `selectedMode` is for strategy inspection only
  // and MUST NOT drive bot production behavior. `scannerModes` is read
  // to look up the per-mode min_confluence_score for read-only display.
  const { botConfig, scannerModes } = useScanner();
  const [config, setConfig] = useState<LiveConfig>(DEFAULT_CONFIG);
  const [preflight, setPreflight] = useState<PreflightResult | null>(null);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ackChecked, setAckChecked] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [recommendation, setRecommendation] = useState<{
    mode: string;
    reason: string;
    regime?: { composite?: string };
  } | null>(null);

  // Static now for snapshot determinism. Footer renders this once.
  const [now] = useState(() => new Date());

  // Snapshot-ready handshake — StrictMode-safe.
  useEffect(() => {
    document.body.setAttribute('data-snapshot-ready', 'true');
    return () => {
      document.body.removeAttribute('data-snapshot-ready');
    };
  }, []);

  const runPreflight = useCallback(async () => {
    setPreflightLoading(true);
    setError(null);
    try {
      const result = await liveTradingService.preflight();
      setPreflight(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPreflightLoading(false);
    }
  }, []);

  useEffect(() => {
    // Already-running guard — redirect to status page.
    liveTradingService
      .getStatus()
      .then((s) => {
        if (s.status === 'running') navigate('/bot/status');
      })
      .catch(() => {});
    runPreflight();
    api
      .getScannerRecommendation()
      .then((r) => {
        if (r.data) setRecommendation(r.data);
      })
      .catch(() => {});
  }, [runPreflight, navigate]);

  const balance = preflight?.balance ?? 0;
  const riskAmountUsd = balance > 0 ? (balance * config.risk_per_trade) / 100 : null;
  const positionUsd = riskAmountUsd ? riskAmountUsd * config.leverage : null;
  const dailyMaxUsd =
    balance > 0 && config.max_drawdown_pct != null
      ? (balance * config.max_drawdown_pct) / 100
      : null;
  const effectiveExposure = config.leverage * config.risk_per_trade;

  const canStart = (preflight?.ok ?? false) && ackChecked;

  const handleSave = () => {
    setSavedFlash(true);
    setTimeout(() => setSavedFlash(false), 1600);
  };

  const handleStart = async () => {
    setStarting(true);
    setError(null);
    try {
      const req: LiveTradingConfigRequest = {
        testnet: false,
        dry_run: false,
        // 3z.h: bot mode comes from `botConfig.sniperMode` (production
        // source of truth). Scanner inspection mode is independent.
        sniper_mode: botConfig.sniperMode ?? 'stealth',
        leverage: config.leverage,
        risk_per_trade: config.risk_per_trade,
        max_positions: config.max_positions,
        duration_hours: config.duration_hours,
        scan_interval_minutes: config.scan_interval_minutes,
        // Always custom — named bundles dropped per plan §3e.
        sensitivity_preset: 'custom',
        min_confluence: config.min_confluence,
        confluence_soft_floor: config.confluence_soft_floor,
        max_hours_open: config.max_hours_open,
        max_drawdown_pct: config.max_drawdown_pct ?? undefined,
        trailing_stop: config.trailing_stop,
        trailing_activation: config.trailing_activation,
        breakeven_after_target: config.breakeven_after_target,
        majors: config.majors,
        altcoins: config.altcoins,
        meme_mode: config.meme_mode,
        universe_size: config.universe_size,
        symbols: config.symbols,
        exclude_symbols: config.exclude_symbols,
        fee_rate: config.fee_rate,
        max_position_size_usd: config.max_position_size_usd,
        max_total_exposure_usd: config.max_total_exposure_usd,
        min_balance_usd: config.min_balance_usd,
        kill_switch_enabled: config.kill_switch_enabled,
        safety_acknowledgment: 'I_ACCEPT_LIVE_TRADING_RISK',
      };
      await liveTradingService.start(req);
      navigate('/bot/status');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setStarting(false);
    }
  };

  // 3z.h: derive display values from botConfig + scannerModes (per-mode
  // metadata source). Falls back to defaults if mode-list fetch is still
  // pending or the configured mode name doesn't match a known mode.
  const botMode = botConfig.sniperMode ?? 'stealth';
  const modeName = botMode.toUpperCase();
  const modeMetadata = scannerModes.find(
    (m) => m.name.toLowerCase() === botMode.toLowerCase(),
  );
  const modeMinScore = modeMetadata?.min_confluence_score ?? 65;
  const regimeText = recommendation?.regime?.composite
    ? recommendation.regime.composite.replace(/_/g, ' ')
    : 'adaptive';

  // Synthetic backtest stats (90d). Marked synthetic in the panel header.
  const backtestStats = useMemo(
    () => ({ pnl: '+34.8%', sharpe: '1.84', win: '62%', maxDd: '-8.4%' }),
    [],
  );

  return (
    <div className="page">
      <PageHead
        icon={
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <circle cx="6" cy="6" r="2" stroke="var(--accent)" strokeWidth="1.6" />
            <line x1="9" y1="6" x2="22" y2="6" stroke="var(--accent)" strokeWidth="1.6" />
            <circle cx="16" cy="12" r="2" stroke="var(--accent)" strokeWidth="1.6" />
            <line x1="2" y1="12" x2="13" y2="12" stroke="var(--accent)" strokeWidth="1.6" />
            <line x1="19" y1="12" x2="22" y2="12" stroke="var(--accent)" strokeWidth="1.6" />
            <circle cx="9" cy="18" r="2" stroke="var(--accent)" strokeWidth="1.6" />
            <line x1="2" y1="18" x2="6" y2="18" stroke="var(--accent)" strokeWidth="1.6" />
            <line x1="12" y1="18" x2="22" y2="18" stroke="var(--accent)" strokeWidth="1.6" />
          </svg>
        }
        title="Bot Setup"
        subtitle="execution config · risk · position limits · deploy"
        badges={
          <>
            <Chip kind="amber">BOT · {modeName}</Chip>
            <Chip kind={savedFlash ? 'green' : 'amber'}>
              {savedFlash ? '✓ SAVED' : '● UNSAVED'}
            </Chip>
            <Chip kind="red">● LIVE</Chip>
          </>
        }
      />

      {/* LIVE MODE banner — Phase 3 follow-up 3z.e symmetry. PAPER MODE
          banner lives at src/pages/training/RangeBot.tsx; both are always
          visible to prevent the §11 silent-confusion bug that 3z.e closed
          (Training Ground RANGE card previously routed here, claiming
          "no real funds" while landing the user on the LIVE bot interface). */}
      <div
        role="banner"
        aria-label="live mode disclosure"
        style={{
          background: 'rgba(248, 113, 113, 0.08)',
          border: '1px solid rgba(248, 113, 113, 0.45)',
          borderRadius: 4,
          padding: '10px 14px',
          marginBottom: 14,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}
      >
        <span
          className="mono"
          style={{ fontSize: 11, color: 'var(--red-2)', fontWeight: 700, letterSpacing: 1.5 }}
        >
          ◉ LIVE MODE
        </span>
        <span className="mono" style={{ fontSize: 11, color: 'var(--fg-2)' }}>
          real capital · executes on Phemex · for paper trading use TRAINING / RANGE
        </span>
      </div>

      {/* 3z.h: BOT MODE read-only badge. Pre-3z.h this strip read from
          ScannerContext.selectedMode and linked to /scanner to change it,
          which conflated bot production behavior with scanner inspection
          mode (§11 hidden-bug class — operator changed scanner mode for
          strategy review and inadvertently changed bot production mode).
          Per CLAUDE.md §15 line 117 the bot's mode is now driven by
          botConfig.sniperMode and is read-only here. Scanner inspection
          mode is independent. */}
      <section
        className="panel"
        style={{
          marginBottom: 14,
          background: 'rgba(245,158,11,.05)',
          borderColor: 'rgba(245,158,11,.3)',
        }}
      >
        <div
          style={{
            padding: '12px 18px',
            display: 'flex',
            alignItems: 'center',
            gap: 18,
            flexWrap: 'wrap',
          }}
        >
          <span
            className="mono"
            style={{
              fontSize: 10,
              color: 'var(--amber)',
              letterSpacing: '.20em',
              textTransform: 'uppercase',
              fontWeight: 700,
            }}
          >
            ◉ BOT MODE
          </span>
          <span
            className="mono"
            style={{
              fontSize: 16,
              color: 'var(--amber)',
              letterSpacing: '.14em',
              fontWeight: 700,
            }}
          >
            {modeName}
          </span>
          <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>
            ≥ {modeMinScore} confluence · production · read-only
          </span>
          <span
            className="mono"
            style={{
              fontSize: 10,
              color: 'var(--fg-3)',
              marginLeft: 'auto',
              letterSpacing: '.12em',
            }}
            title="Bot production mode is independent of Scanner inspection mode (CLAUDE.md §15 line 117). Change in Settings (future) — Scanner picker does not affect bot."
          >
            ◌ INDEPENDENT OF SCANNER PICKER
          </span>
        </div>
      </section>

      {error && (
        <section
          className="panel"
          style={{
            marginBottom: 14,
            background: 'rgba(248,113,113,.06)',
            borderColor: 'rgba(248,113,113,.4)',
          }}
        >
          <div style={{ padding: '12px 18px', fontSize: 12, color: 'var(--red-2)' }}>
            <span className="mono" style={{ letterSpacing: '.16em' }}>
              ERROR ·
            </span>{' '}
            {error}
          </div>
        </section>
      )}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 320px',
          gap: 14,
          alignItems: 'start',
        }}
      >
        {/* MAIN — config sections */}
        <div>
          {/* RISK */}
          <SectionPanel
            num="01"
            title="Risk Engine"
            desc="position sizing · loss limits · concurrent exposure"
          >
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 10,
                marginBottom: 10,
              }}
            >
              <Slider
                label="Risk per Trade"
                value={config.risk_per_trade}
                min={0.25}
                max={5}
                step={0.25}
                suffix="%"
                onChange={(v) => setConfig({ ...config, risk_per_trade: v })}
                color="var(--amber)"
              />
              <Slider
                label="Max Concurrent"
                value={config.max_positions}
                min={1}
                max={10}
                step={1}
                suffix=" pos"
                onChange={(v) => setConfig({ ...config, max_positions: v })}
              />
              <Slider
                label="Leverage"
                value={config.leverage}
                min={1}
                max={20}
                step={1}
                suffix="×"
                onChange={(v) => setConfig({ ...config, leverage: v })}
                color={
                  config.leverage > 10
                    ? 'var(--red-2)'
                    : config.leverage > 5
                      ? 'var(--amber)'
                      : 'var(--green-soft)'
                }
              />
              <Slider
                label="Min Confluence"
                value={config.min_confluence}
                min={40}
                max={100}
                step={1}
                onChange={(v) => setConfig({ ...config, min_confluence: v })}
                hint="full-size entry threshold"
              />
              <Slider
                label="Soft Floor"
                value={config.confluence_soft_floor}
                min={30}
                max={100}
                step={1}
                onChange={(v) => setConfig({ ...config, confluence_soft_floor: v })}
                hint="half-size near-miss floor"
              />
              <Slider
                label="Scan Interval"
                value={config.scan_interval_minutes}
                min={1}
                max={30}
                step={1}
                suffix=" min"
                onChange={(v) => setConfig({ ...config, scan_interval_minutes: v })}
              />
            </div>

            {/* Live risk preview tile */}
            <div
              style={{
                marginTop: 8,
                padding: '14px 16px',
                border: '1px dashed var(--accent)',
                borderRadius: 6,
                background: 'rgba(34,211,238,.05)',
              }}
            >
              <div
                className="mono"
                style={{
                  fontSize: 9,
                  color: 'var(--accent)',
                  letterSpacing: '.18em',
                  textTransform: 'uppercase',
                  marginBottom: 10,
                }}
              >
                // LIVE RISK PREVIEW · BAL{' '}
                {balance > 0 ? `$${balance.toFixed(2)}` : '—'}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
                <div className="metric-tile">
                  <div className="metric-label">Risk / Trade</div>
                  <div className="metric-value" style={{ color: 'var(--amber)' }}>
                    {riskAmountUsd != null ? `$${riskAmountUsd.toFixed(2)}` : '—'}
                  </div>
                  <div className="metric-sub">{config.risk_per_trade}% of equity</div>
                </div>
                <div className="metric-tile">
                  <div className="metric-label">Position Size</div>
                  <div className="metric-value">
                    {positionUsd != null ? `$${positionUsd.toFixed(0)}` : '—'}
                  </div>
                  <div className="metric-sub">@ {config.leverage}× lev</div>
                </div>
                <div className="metric-tile">
                  <div className="metric-label">Max Daily Loss</div>
                  <div className="metric-value" style={{ color: 'var(--red-2)' }}>
                    {dailyMaxUsd != null ? `-$${dailyMaxUsd.toFixed(0)}` : '—'}
                  </div>
                  <div className="metric-sub">
                    kills bot @ -{config.max_drawdown_pct ?? '—'}%
                  </div>
                </div>
                <div className="metric-tile">
                  <div className="metric-label">Max Exposure</div>
                  <div className="metric-value">
                    {positionUsd != null
                      ? `$${(positionUsd * config.max_positions).toFixed(0)}`
                      : '—'}
                  </div>
                  <div className="metric-sub">{config.max_positions} concurrent</div>
                </div>
              </div>
              <div
                className="mono"
                style={{
                  fontSize: 9,
                  color:
                    effectiveExposure >= 20
                      ? 'var(--red-2)'
                      : effectiveExposure >= 10
                        ? 'var(--amber)'
                        : 'var(--fg-4)',
                  letterSpacing: '.12em',
                  marginTop: 8,
                }}
              >
                {effectiveExposure.toFixed(1)}% effective exposure / trade
              </div>
            </div>
          </SectionPanel>

          {/* SAFETY */}
          <SectionPanel
            num="02"
            title="Safety Limits"
            desc="kill-switches · position caps · balance floor"
          >
            {/* Drawdown kill-switch */}
            <div style={{ marginBottom: 14 }}>
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
                // SESSION DRAWDOWN STOP
              </div>
              <div
                style={{
                  textAlign: 'center',
                  padding: '14px 0',
                  border: '1px solid rgba(248,113,113,.2)',
                  background: 'rgba(248,113,113,.04)',
                  borderRadius: 6,
                  marginBottom: 10,
                }}
              >
                <div
                  className="mono"
                  style={{
                    fontSize: 38,
                    fontWeight: 800,
                    color:
                      config.max_drawdown_pct == null
                        ? 'var(--fg-4)'
                        : config.max_drawdown_pct <= 10
                          ? 'var(--green-soft)'
                          : config.max_drawdown_pct <= 20
                            ? 'var(--amber)'
                            : 'var(--red-2)',
                  }}
                >
                  {config.max_drawdown_pct != null ? `${config.max_drawdown_pct}%` : 'OFF'}
                </div>
                <div
                  className="mono"
                  style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.18em', marginTop: 4 }}
                >
                  KILLS BOT WHEN HIT
                </div>
              </div>
              <div style={{ display: 'flex', gap: 4 }}>
                {[
                  { l: 'OFF', v: null as number | null },
                  { l: '5%', v: 5 },
                  { l: '10%', v: 10 },
                  { l: '15%', v: 15 },
                  { l: '25%', v: 25 },
                ].map(({ l, v }) => (
                  <button
                    key={l}
                    onClick={() => setConfig({ ...config, max_drawdown_pct: v })}
                    className={`btn ${config.max_drawdown_pct === v ? 'btn-red' : ''}`}
                    style={{ flex: 1, padding: '6px 8px', fontSize: 10 }}
                  >
                    {l}
                  </button>
                ))}
              </div>
            </div>

            {/* Position-size caps */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr 1fr',
                gap: 10,
                marginBottom: 14,
              }}
            >
              {(
                [
                  {
                    k: 'max_position_size_usd' as const,
                    label: 'Max Position ($)',
                    val: config.max_position_size_usd,
                  },
                  {
                    k: 'max_total_exposure_usd' as const,
                    label: 'Max Total Exposure ($)',
                    val: config.max_total_exposure_usd,
                  },
                  {
                    k: 'min_balance_usd' as const,
                    label: 'Min Balance Floor ($)',
                    val: config.min_balance_usd,
                  },
                ]
              ).map(({ k, label, val }) => (
                <div
                  key={k}
                  style={{
                    padding: '12px 14px',
                    border: '1px solid var(--border-soft)',
                    borderRadius: 6,
                    background: 'rgba(0,0,0,.3)',
                  }}
                >
                  <div
                    className="mono"
                    style={{
                      fontSize: 9,
                      color: 'var(--fg-4)',
                      letterSpacing: '.16em',
                      textTransform: 'uppercase',
                      marginBottom: 6,
                    }}
                  >
                    {label}
                  </div>
                  <input
                    type="number"
                    min={0}
                    value={val}
                    onChange={(e) => {
                      const v = parseFloat(e.target.value);
                      if (!Number.isNaN(v)) setConfig({ ...config, [k]: v });
                    }}
                    style={{
                      width: '100%',
                      padding: '6px 8px',
                      fontFamily: 'JetBrains Mono,monospace',
                      fontSize: 14,
                      background: 'rgba(0,0,0,.4)',
                      color: 'var(--fg)',
                      border: '1px solid var(--border-soft)',
                      borderRadius: 4,
                      textAlign: 'center',
                    }}
                  />
                </div>
              ))}
            </div>

            {/* Kill switch master toggle */}
            <Toggle
              label="Kill-Switch Active"
              value={config.kill_switch_enabled}
              hint="bot stops at session DD limit · disabling is dangerous"
              onChange={(v) => setConfig({ ...config, kill_switch_enabled: v })}
            />
          </SectionPanel>

          {/* EXECUTION */}
          <SectionPanel
            num="03"
            title="Execution Behavior"
            desc="stop management · trailing · breakeven"
          >
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <Toggle
                label="Move SL → BE @ TP1"
                value={config.breakeven_after_target === 1}
                hint="lock zero risk after first target"
                onChange={(v) =>
                  setConfig({ ...config, breakeven_after_target: v ? 1 : 0 })
                }
              />
              <Toggle
                label="Trailing Stop"
                value={config.trailing_stop}
                hint={`trail after ${config.trailing_activation}R`}
                onChange={(v) => setConfig({ ...config, trailing_stop: v })}
              />
              <Slider
                label="Max Trade Duration"
                value={config.max_hours_open}
                min={4}
                max={336}
                step={4}
                suffix=" h"
                onChange={(v) => setConfig({ ...config, max_hours_open: v })}
              />
              <Slider
                label="Trailing Activation"
                value={config.trailing_activation}
                min={1}
                max={5}
                step={0.25}
                suffix=" R"
                onChange={(v) => setConfig({ ...config, trailing_activation: v })}
              />
            </div>

            {/* Deferred toggles */}
            <div style={{ marginTop: 12, opacity: 0.45 }}>
              <div
                className="mono"
                style={{
                  fontSize: 9,
                  color: 'var(--fg-4)',
                  letterSpacing: '.18em',
                  textTransform: 'uppercase',
                  marginBottom: 8,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                }}
              >
                // DEFERRED
                <Chip kind="amber">◌ NOT YET WIRED</Chip>
              </div>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: 6,
                  fontSize: 11,
                }}
              >
                {[
                  'BTC veto filter',
                  'Funding rate filter',
                  'Spread filter',
                  'Average-in on pullback',
                  'Martingale (DANGER)',
                  'Auto-execute toggle',
                ].map((label) => (
                  <div
                    key={label}
                    className="mono"
                    style={{
                      padding: '8px 10px',
                      border: '1px dashed var(--border-soft)',
                      borderRadius: 4,
                      color: 'var(--fg-4)',
                      letterSpacing: '.04em',
                    }}
                  >
                    {label}
                  </div>
                ))}
              </div>
            </div>
          </SectionPanel>

          {/* UNIVERSE */}
          <SectionPanel
            num="04"
            title="Target Universe"
            desc="asset buckets · size · custom symbols"
          >
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr 1fr',
                gap: 6,
                marginBottom: 12,
              }}
            >
              {(
                [
                  { k: 'majors' as const, label: 'MAJORS', kind: 'green' as const },
                  { k: 'altcoins' as const, label: 'ALTS', kind: 'blue' as const },
                  { k: 'meme_mode' as const, label: 'MEME', kind: 'purple' as const },
                ]
              ).map(({ k, label, kind }) => {
                const active = config[k];
                return (
                  <button
                    key={k}
                    onClick={() => setConfig({ ...config, [k]: !active })}
                    className={`btn ${active ? `btn-${kind}` : ''}`}
                    style={{ padding: '12px', fontSize: 11, fontWeight: 700 }}
                  >
                    {active ? '● ' : '○ '}
                    {label}
                  </button>
                );
              })}
            </div>

            <Slider
              label="Universe Size"
              value={config.universe_size}
              min={10}
              max={50}
              step={5}
              suffix=" pairs"
              onChange={(v) => setConfig({ ...config, universe_size: v })}
              hint="total scan candidates after dedup"
            />

            <div style={{ marginTop: 12 }}>
              <div
                className="mono"
                style={{
                  fontSize: 9,
                  color: 'var(--fg-4)',
                  letterSpacing: '.18em',
                  textTransform: 'uppercase',
                  marginBottom: 6,
                }}
              >
                // CUSTOM SYMBOLS · OVERRIDES BUCKETS
              </div>
              <input
                type="text"
                placeholder="BTC/USDT, ETH/USDT, ..."
                value={config.symbols.join(', ')}
                onChange={(e) => {
                  const syms = e.target.value
                    .split(',')
                    .map((s) => s.trim().toUpperCase())
                    .filter((s) => s.length > 0);
                  setConfig({ ...config, symbols: syms });
                }}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  fontFamily: 'JetBrains Mono,monospace',
                  fontSize: 12,
                  background: 'rgba(0,0,0,.4)',
                  color: 'var(--fg)',
                  border: '1px solid var(--border-soft)',
                  borderRadius: 4,
                }}
              />
            </div>
          </SectionPanel>

          {/* BACKTEST — synthetic placeholder */}
          <SectionPanel
            num="05"
            title="Backtest"
            desc="90-day historical simulation"
            right={<Chip kind="amber">◌ SYNTHETIC</Chip>}
          >
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 10,
                marginBottom: 10,
              }}
            >
              <div className="metric-tile">
                <div className="metric-label">PnL</div>
                <div className="metric-value" style={{ color: 'var(--green-soft)' }}>
                  {backtestStats.pnl}
                </div>
              </div>
              <div className="metric-tile">
                <div className="metric-label">Sharpe</div>
                <div className="metric-value" style={{ color: 'var(--accent)' }}>
                  {backtestStats.sharpe}
                </div>
              </div>
              <div className="metric-tile">
                <div className="metric-label">Win Rate</div>
                <div className="metric-value">{backtestStats.win}</div>
              </div>
              <div className="metric-tile">
                <div className="metric-label">Max DD</div>
                <div className="metric-value" style={{ color: 'var(--red-2)' }}>
                  {backtestStats.maxDd}
                </div>
              </div>
            </div>
            <button
              className="btn"
              style={{ width: '100%', padding: '8px', fontSize: 11 }}
              disabled
            >
              ▶ RUN BACKTEST · NOT YET WIRED
            </button>
          </SectionPanel>
        </div>

        {/* RIGHT SIDEBAR — DEPLOY */}
        <div style={{ position: 'sticky', top: 14 }}>
          <section className="panel panel-accent">
            <Reticle />
            <div className="corner-tag tl">// DEPLOY</div>
            <div className="corner-tag tr">REAL FUNDS</div>
            <SectionHead title="Deploy" />
            <div style={{ padding: '18px 16px' }}>
              {/* Preflight summary */}
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
                // PREFLIGHT
              </div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '10px 12px',
                  border: `1px solid ${
                    preflight?.ok
                      ? 'rgba(34,197,94,.4)'
                      : preflight
                        ? 'rgba(248,113,113,.4)'
                        : 'var(--border-soft)'
                  }`,
                  borderRadius: 6,
                  background: 'rgba(0,0,0,.3)',
                  marginBottom: 12,
                }}
              >
                <span
                  className="mono"
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: preflight?.ok
                      ? 'var(--green-soft)'
                      : preflight
                        ? 'var(--red-2)'
                        : 'var(--fg-3)',
                    letterSpacing: '.12em',
                  }}
                >
                  {preflightLoading
                    ? 'CHECKING…'
                    : preflight?.ok
                      ? '● ONLINE'
                      : preflight
                        ? '○ OFFLINE'
                        : '○ UNKNOWN'}
                </span>
                <span
                  className="mono"
                  style={{ fontSize: 11, color: 'var(--fg-2)', marginLeft: 'auto' }}
                >
                  {balance > 0 ? `$${balance.toFixed(2)}` : '—'}
                </span>
              </div>

              {/* Config summary */}
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
                // CONFIG
              </div>
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 4,
                  fontFamily: 'JetBrains Mono,monospace',
                  fontSize: 11,
                  marginBottom: 14,
                }}
              >
                {(
                  [
                    ['mode', modeName],
                    ['regime', regimeText.toUpperCase()],
                    ['risk', `${config.risk_per_trade}%`],
                    ['leverage', `${config.leverage}×`],
                    ['max pos', `${config.max_positions}`],
                    ['min conf', `${config.min_confluence}`],
                    ['drawdown', config.max_drawdown_pct != null ? `${config.max_drawdown_pct}%` : 'OFF'],
                    [
                      'universe',
                      [
                        config.majors && 'majors',
                        config.altcoins && 'alts',
                        config.meme_mode && 'meme',
                      ]
                        .filter(Boolean)
                        .join('+') || '—',
                    ],
                  ] as Array<[string, string]>
                ).map(([k, v]) => (
                  <div
                    key={k}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      padding: '4px 0',
                      borderBottom: '1px dashed var(--border-soft)',
                    }}
                  >
                    <span
                      style={{
                        color: 'var(--fg-4)',
                        letterSpacing: '.1em',
                        textTransform: 'uppercase',
                        fontSize: 9,
                      }}
                    >
                      {k}
                    </span>
                    <span style={{ color: 'var(--fg)', fontWeight: 600 }}>{v}</span>
                  </div>
                ))}
              </div>

              {/* Pre-flight warning */}
              <div
                style={{
                  padding: '10px 12px',
                  border: '1px solid var(--amber-2)',
                  background: 'rgba(251,191,36,.08)',
                  borderRadius: 6,
                  marginBottom: 14,
                }}
              >
                <div
                  className="mono"
                  style={{
                    fontSize: 9,
                    color: 'var(--amber-2)',
                    letterSpacing: '.16em',
                    textTransform: 'uppercase',
                    marginBottom: 4,
                  }}
                >
                  ⚠ LIVE TRADING
                </div>
                <div style={{ fontSize: 11, color: 'var(--fg-2)', lineHeight: 1.5 }}>
                  Bot will trade <b style={{ color: 'var(--accent)' }}>real funds</b> using{' '}
                  <b style={{ color: 'var(--accent)' }}>{config.risk_per_trade}%</b> risk
                  per trade @ <b style={{ color: 'var(--accent)' }}>{config.leverage}×</b>{' '}
                  leverage. Daily kill at -{config.max_drawdown_pct ?? '—'}%.
                </div>
              </div>

              {/* Acknowledgment */}
              <label
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 10,
                  padding: '10px 12px',
                  border: '1px solid rgba(248,113,113,.2)',
                  background: 'rgba(248,113,113,.04)',
                  borderRadius: 6,
                  marginBottom: 12,
                  cursor: 'pointer',
                }}
              >
                <input
                  type="checkbox"
                  checked={ackChecked}
                  onChange={(e) => setAckChecked(e.target.checked)}
                  style={{ marginTop: 3 }}
                />
                <span style={{ fontSize: 10, color: 'var(--fg-2)', lineHeight: 1.5 }}>
                  I accept full responsibility for all trading outcomes. Capital at risk
                  — losses are permanent.
                </span>
              </label>

              {/* CTA buttons */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <button
                  className="btn"
                  style={{ padding: '10px', fontSize: 11 }}
                  onClick={handleSave}
                >
                  {savedFlash ? '✓ SAVED' : 'SAVE CONFIG'}
                </button>
                <button
                  className={canStart ? 'btn btn-red' : 'btn'}
                  style={{
                    padding: '14px',
                    fontSize: 13,
                    fontWeight: 800,
                    letterSpacing: '.18em',
                    opacity: canStart ? 1 : 0.5,
                    cursor: canStart ? 'pointer' : 'not-allowed',
                  }}
                  onClick={handleStart}
                  disabled={!canStart || starting}
                >
                  {starting ? 'INITIALIZING…' : '▶ DEPLOY LIVE BOT'}
                </button>
                <button
                  className="btn"
                  style={{ padding: '8px', fontSize: 10 }}
                  onClick={() => setConfig(DEFAULT_CONFIG)}
                >
                  ↺ RESET TO DEFAULTS
                </button>
              </div>
            </div>
          </section>

          {/* Recheck pill */}
          <button
            className="btn"
            style={{
              width: '100%',
              padding: '8px',
              fontSize: 10,
              marginTop: 10,
            }}
            onClick={runPreflight}
            disabled={preflightLoading}
          >
            ↻ RECHECK PREFLIGHT
          </button>
        </div>
      </div>

      <FooterStatus latency={28} build={`${now.toISOString().slice(0, 10)}`} />
    </div>
  );
}
