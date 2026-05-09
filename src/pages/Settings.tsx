/**
 * Settings — Phase 3c sub-step 1
 *
 * HUD chrome port of prototype/settings.jsx. Six cards in a 2-column grid:
 *   1. Account
 *   2. Notifications
 *   3. Exchange API Keys (Binance / Phemex / Bybit / BingX)
 *   4. Bot Behavior
 *   5. Appearance
 *   6. Danger Zone
 *
 * Per the migration plan, this is a CREATE (no prior /settings route in
 * App.tsx). Backend wiring for these surfaces lands in later phases:
 *   - 2FA / plan / API key persistence: Phase 5+ (auth/billing).
 *   - Notification toggles: hook through NotificationSettings/useNotifications
 *     in a follow-up; this sub-step keeps all toggles as local state so the
 *     visual port lands cleanly without dragging the existing shadcn-based
 *     NotificationSettings component along (it gets restyled in Phase 4).
 *   - Bot Behavior runtime defaults: today these duplicate Bot Setup sliders
 *     (kill switch, leverage, mode); plan calls for them to read/write the
 *     orchestrator's persisted config, which lands with Phase 3g (Bot).
 *
 * State is persisted to localStorage so the page survives reloads. No
 * backend calls are made — that's intentional; visual snapshots stay
 * deterministic without any new fixture.
 *
 * body[data-snapshot-ready="true"] is set on mount because there is no
 * async load path. This keeps the visual capture framework green.
 */
import { useEffect, useState, type ReactNode } from 'react';
import { Chip, FooterStatus, PageHead, Reticle, SectionHead } from '@/components/hud';

// ─── localStorage helpers ─────────────────────────────────────────────────

const LS_KEY = 'sniper.settings.v1';

interface PersistedSettings {
  tg: boolean;
  discord: boolean;
  email: boolean;
  audio: boolean;
  haptic: boolean;
  autoStart: boolean;
  tradingMode: 'LIVE' | 'PAPER';
  defaultLeverage: number;
  killSwitchPct: number;
  tacticalBg: boolean;
  hudOverlays: boolean;
  density: 'sparse' | 'balanced' | 'dense';
  displayName: string;
  email_addr: string;
}

const DEFAULTS: PersistedSettings = {
  tg: true,
  discord: true,
  email: false,
  audio: true,
  haptic: true,
  autoStart: false,
  tradingMode: 'LIVE',
  defaultLeverage: 5,
  killSwitchPct: 10,
  tacticalBg: true,
  hudOverlays: true,
  density: 'balanced',
  displayName: 'commander_07',
  email_addr: 'commander@signal.ops',
};

function loadSettings(): PersistedSettings {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<PersistedSettings>;
    return { ...DEFAULTS, ...parsed };
  } catch {
    return DEFAULTS;
  }
}

function saveSettings(s: PersistedSettings) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(s));
  } catch {
    // localStorage quota / privacy mode — ignore.
  }
}

// ─── Reusable atoms (Card / Row / Toggle) ────────────────────────────────

function Card({
  title,
  hint,
  children,
}: {
  title: ReactNode;
  hint?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="panel" style={{ padding: 0 }}>
      <SectionHead title={title} />
      {hint && (
        <div
          className="mono"
          style={{
            padding: '0 20px',
            fontSize: 10,
            color: 'var(--fg-4)',
            letterSpacing: '.18em',
            textTransform: 'uppercase',
            marginBottom: 6,
          }}
        >
          {hint}
        </div>
      )}
      <div style={{ padding: '14px 20px 18px' }}>{children}</div>
    </section>
  );
}

function Row({
  label,
  hint,
  children,
}: {
  label: ReactNode;
  hint?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '200px 1fr',
        gap: 18,
        padding: '12px 0',
        borderBottom: '1px dashed var(--border-soft)',
        alignItems: 'center',
      }}
    >
      <div>
        <div
          className="mono"
          style={{ fontSize: 11, color: 'var(--fg)', fontWeight: 600, letterSpacing: '.06em' }}
        >
          {label}
        </div>
        {hint && (
          <div
            className="mono"
            style={{
              fontSize: 9,
              color: 'var(--fg-4)',
              letterSpacing: '.14em',
              textTransform: 'uppercase',
              marginTop: 3,
            }}
          >
            {hint}
          </div>
        )}
      </div>
      <div>{children}</div>
    </div>
  );
}

function Toggle({
  value,
  onChange,
  label,
}: {
  value: boolean;
  onChange: (v: boolean) => void;
  label?: string;
}) {
  return (
    <div
      onClick={() => onChange(!value)}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}
    >
      <div
        style={{
          width: 40,
          height: 20,
          borderRadius: 10,
          background: value ? 'var(--accent)' : 'rgba(0,0,0,.6)',
          position: 'relative',
          border: '1px solid var(--border-soft)',
          boxShadow: value ? '0 0 8px var(--accent)' : 'none',
          transition: 'all .15s',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: 1,
            left: value ? 21 : 1,
            width: 16,
            height: 16,
            borderRadius: '50%',
            background: value ? '#0a0c0e' : 'var(--fg-3)',
            transition: 'left .15s',
          }}
        />
      </div>
      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-3)', letterSpacing: '.14em' }}>
        {label ?? (value ? 'ENABLED' : 'OFF')}
      </span>
    </div>
  );
}

const inputBase: React.CSSProperties = {
  padding: '8px 10px',
  background: 'rgba(0,0,0,.5)',
  border: '1px solid var(--border-soft)',
  borderRadius: 6,
  color: 'var(--fg)',
  fontSize: 12,
};

// Mock keys — same shape as prototype, deterministic per exchange so
// snapshots are stable. (No real key storage in this sub-step.)
const MOCK_KEYS: Record<string, string> = {
  BINANCE: '••••••BINA_4f7c',
  PHEMEX: '••••••PHEM_a2d9',
  BYBIT: '••••••BYBI_3e10',
  BINGX: '••••••BING_b06f',
};

// ─── Page ─────────────────────────────────────────────────────────────────

export function Settings() {
  const [s, setS] = useState<PersistedSettings>(() => loadSettings());
  const [showKeys, setShowKeys] = useState(false);

  // Persist on every change.
  useEffect(() => {
    saveSettings(s);
  }, [s]);

  // Snapshot-ready flag — no async work.
  useEffect(() => {
    document.body.setAttribute('data-snapshot-ready', 'true');
    return () => {
      document.body.removeAttribute('data-snapshot-ready');
    };
  }, []);

  const set = <K extends keyof PersistedSettings>(k: K, v: PersistedSettings[K]) =>
    setS((prev) => ({ ...prev, [k]: v }));

  return (
    <div className="page">
      <Reticle />

      <PageHead
        icon={
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <circle
              cx="12"
              cy="12"
              r="3"
              stroke="currentColor"
              strokeWidth="1.5"
              style={{ color: 'var(--accent)' }}
            />
            <path
              d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              style={{ color: 'var(--accent)' }}
            />
          </svg>
        }
        title="Settings"
        subtitle="Account · API keys · notifications · appearance"
        badges={
          <>
            <Chip kind="green">● ACCOUNT VERIFIED</Chip>
            <Chip>2FA · ON</Chip>
          </>
        }
      />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        {/* ── Account ── */}
        <Card title="Account">
          <Row label="Display Name">
            <input
              value={s.displayName}
              onChange={(e) => set('displayName', e.target.value)}
              className="mono"
              style={{ ...inputBase, width: '100%' }}
            />
          </Row>
          <Row label="Email" hint="Account recovery">
            <input
              value={s.email_addr}
              onChange={(e) => set('email_addr', e.target.value)}
              className="mono"
              style={{ ...inputBase, width: '100%' }}
            />
          </Row>
          <Row label="2FA" hint="TOTP via authenticator">
            <Toggle value={true} onChange={() => {}} label="ENABLED · TOTP" />
          </Row>
          <Row label="Plan">
            <div>
              <span className="chip chip-cyan">PRO</span>
              <span
                className="mono"
                style={{ marginLeft: 8, fontSize: 10, color: 'var(--fg-4)' }}
              >
                renews 2026-06-01
              </span>
            </div>
          </Row>
        </Card>

        {/* ── Notifications ── */}
        <Card title="Notifications" hint="// where to ping you">
          <Row label="Telegram" hint="Trade alerts + summary">
            <Toggle value={s.tg} onChange={(v) => set('tg', v)} />
          </Row>
          <Row label="Discord" hint="#signals webhook">
            <Toggle value={s.discord} onChange={(v) => set('discord', v)} />
          </Row>
          <Row label="Email" hint="Daily digest">
            <Toggle value={s.email} onChange={(v) => set('email', v)} />
          </Row>
          <Row label="Audio Cue" hint="On signal arm + fill">
            <Toggle value={s.audio} onChange={(v) => set('audio', v)} />
          </Row>
          <Row label="Haptic" hint="Mobile-only buzz on fills">
            <Toggle value={s.haptic} onChange={(v) => set('haptic', v)} />
          </Row>
        </Card>

        {/* ── Exchange API Keys ── */}
        <Card title="Exchange API Keys" hint="// live trading credentials">
          {(['BINANCE', 'PHEMEX', 'BYBIT', 'BINGX'] as const).map((ex) => (
            <Row
              key={ex}
              label={ex}
              hint={ex === 'PHEMEX' ? 'Primary execution venue' : undefined}
            >
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <input
                  type={showKeys ? 'text' : 'password'}
                  defaultValue={MOCK_KEYS[ex]}
                  className="mono"
                  style={{ ...inputBase, flex: 1, fontSize: 11 }}
                />
                <span className="chip chip-green">● LINKED</span>
              </div>
            </Row>
          ))}
          <div style={{ padding: '12px 0 0', display: 'flex', gap: 8 }}>
            <button
              className="btn"
              onClick={() => setShowKeys((v) => !v)}
              style={{ padding: '6px 12px', fontSize: 10, letterSpacing: '.18em' }}
            >
              {showKeys ? '◉ HIDE' : '◯ SHOW'} KEYS
            </button>
            <button
              className="btn btn-cyan"
              style={{ padding: '6px 12px', fontSize: 10, letterSpacing: '.18em' }}
            >
              + ADD EXCHANGE
            </button>
          </div>
        </Card>

        {/* ── Bot Behavior ── */}
        <Card title="Bot Behavior" hint="// global runtime defaults">
          <Row label="Auto-start on boot" hint="Resume bot after server restart">
            <Toggle value={s.autoStart} onChange={(v) => set('autoStart', v)} />
          </Row>
          <Row label="Trading Mode">
            <div className="tab-switch" style={{ display: 'inline-flex' }}>
              <button
                className={s.tradingMode === 'LIVE' ? 'active' : ''}
                onClick={() => set('tradingMode', 'LIVE')}
              >
                LIVE
              </button>
              <button
                className={s.tradingMode === 'PAPER' ? 'active' : ''}
                onClick={() => set('tradingMode', 'PAPER')}
              >
                PAPER
              </button>
            </div>
          </Row>
          <Row label="Default Leverage" hint="Override per-strategy">
            <input
              type="number"
              value={s.defaultLeverage}
              onChange={(e) => set('defaultLeverage', Number(e.target.value) || 0)}
              className="mono"
              style={{ ...inputBase, width: 80 }}
            />
          </Row>
          <Row label="Daily Kill Switch" hint="% drawdown stops bot">
            <input
              type="number"
              value={s.killSwitchPct}
              onChange={(e) => set('killSwitchPct', Number(e.target.value) || 0)}
              className="mono"
              style={{
                ...inputBase,
                width: 80,
                border: '1px solid var(--red-border)',
                color: 'var(--red-2)',
                fontWeight: 700,
              }}
            />{' '}
            <span
              className="mono"
              style={{ color: 'var(--fg-4)', fontSize: 10, letterSpacing: '.18em' }}
            >
              %
            </span>
          </Row>
        </Card>

        {/* ── Appearance ── */}
        <Card title="Appearance" hint="// HUD chrome density + overlays">
          <Row label="Tactical Background">
            <Toggle value={s.tacticalBg} onChange={(v) => set('tacticalBg', v)} />
          </Row>
          <Row label="HUD Overlays">
            <Toggle value={s.hudOverlays} onChange={(v) => set('hudOverlays', v)} />
          </Row>
          <Row label="Density">
            <div className="tab-switch" style={{ display: 'inline-flex' }}>
              {(['sparse', 'balanced', 'dense'] as const).map((d) => (
                <button
                  key={d}
                  className={s.density === d ? 'active' : ''}
                  onClick={() => set('density', d)}
                >
                  {d.toUpperCase()}
                </button>
              ))}
            </div>
          </Row>
        </Card>

        {/* ── Danger Zone ── */}
        <Card title="Danger Zone" hint="// destructive actions">
          <Row label="Export all trade data" hint="CSV · JSON">
            <button className="btn" style={{ padding: '8px 14px', fontSize: 11 }}>
              ↓ EXPORT
            </button>
          </Row>
          <Row label="Reset ML model" hint="Sends to Drills · Training Ground">
            <a
              href="/training#drills"
              className="btn"
              style={{
                padding: '8px 14px',
                fontSize: 11,
                textDecoration: 'none',
                display: 'inline-block',
              }}
            >
              OPEN DRILLS →
            </a>
          </Row>
          <Row label="Delete account" hint="Irreversible · removes all data">
            <button
              className="btn btn-red"
              style={{ padding: '8px 14px', fontSize: 11, fontWeight: 700 }}
            >
              ⚠ DELETE ACCOUNT
            </button>
          </Row>
        </Card>
      </div>

      <FooterStatus latency={36} />
    </div>
  );
}

export default Settings;
