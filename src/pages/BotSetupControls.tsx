import { DialogPanel } from '@/components/hud/DialogPanel';
import { Toggle } from '@/components/hud/Toggle';
export { Toggle } from '@/components/hud/Toggle';
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
export interface LiveConfig {
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
export const DEFAULT_CONFIG: LiveConfig = {
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
export interface SliderProps {
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
export function Slider({ label, value, min, max, step, onChange, suffix, color, hint }: SliderProps) {
    return (<div style={{
            padding: '12px 14px',
            border: '1px solid var(--border-soft)',
            borderRadius: 6,
            background: 'rgba(0,0,0,.3)',
        }}>
      <div className="setup-slider-heading">
        <span className="mono" style={{
            fontSize: 12,
            color: 'var(--fg-2)',
            letterSpacing: '.04em',
        }}>
          {label}
        </span>
        <span className="mono" style={{
            fontSize: 14,
            fontWeight: 800,
            color: color || 'var(--accent)',
        }}>
          {value}
          {suffix || ''}
        </span>
        {hint && <DialogPanel label={label + ' help'} icon maxWidth={520}><p>{hint.replace(/—/g, ':')}</p></DialogPanel>}
      </div>
      <input type="range" aria-label={label} min={min} max={max} step={step} value={value} onChange={(e) => onChange(+e.target.value)} style={{ width: '100%' }}/>
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

    </div>);
}
export interface ToggleProps {
    label: string;
    value: boolean;
    onChange?: (v: boolean) => void;
    hint?: string;
    disabled?: boolean;
}

export interface SectionPanelProps {
    num: string;
    title: string;
    desc?: string;
    right?: React.ReactNode;
    children: React.ReactNode;
}
export function SectionPanel({ num, title, desc, right, children }: SectionPanelProps) {
    return (<section className="panel" style={{ marginBottom: 14 }}>
      <div style={{
            padding: '14px 18px',
            borderBottom: '1px solid var(--border-soft)',
            background: 'rgba(0,0,0,.4)',
            display: 'flex',
            alignItems: 'center',
            gap: 14,
        }}>
        <span style={{
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
        }}>
          {num}
        </span>
        <div style={{ flex: 1 }}>
          <div style={{
            fontFamily: 'Share Tech Mono,monospace',
            fontSize: 15,
            letterSpacing: '.08em',
            color: 'var(--fg)',
            textTransform: 'uppercase',
        }}>
            {title}
          </div>
          {desc && (<div className="mono" style={{
                fontSize: 10,
                color: 'var(--fg-4)',
                letterSpacing: '.1em',
                marginTop: 2,
            }}>
              {desc}
            </div>)}
        </div>
        {right}
      </div>
      <div style={{ padding: '14px 18px' }}>{children}</div>
    </section>);
}
// ─── Main page ───────────────────────────────────────────────────────────
