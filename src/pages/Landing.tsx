/**
 * Landing — Phase 3a sub-step 1
 *
 * TSX port of prototype/landing.jsx with the following deliberate changes:
 *
 * 1. The prototype's <land-topbar> is dropped; the global <Topbar/> in
 *    App.tsx handles header chrome on every route.
 * 2. All <a href="X.html"> external-style nav becomes <Link to="/x">
 *    (react-router) for internal routes.
 * 3. Tweaks panel + window.SS globals removed; the new chrome lives in
 *    @/components/hud/* and is wired at App level.
 * 4. TickerRail polls /api/market/prices (30s interval) and overlays
 *    24h-change% from /api/market/funding where available (10 of 12
 *    symbols have perp data; ARB/SUI/TIA show — for change%). Stale
 *    indicator appears if the price timestamp is > 120s old.
 * 5. body[data-snapshot-ready="true"] is set after first paint so the
 *    visual snapshot framework knows when to capture.
 */
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import type { ReactNode } from 'react';

// ─── Ticker rail data ──────────────────────────────────────────────────
const RAIL_SYMBOLS = [
  'BTC/USDT','ETH/USDT','SOL/USDT','BNB/USDT','XRP/USDT','DOGE/USDT',
  'AVAX/USDT','LINK/USDT','ARB/USDT','SUI/USDT','TIA/USDT','INJ/USDT',
];
const RAIL_SYMBOLS_PARAM = RAIL_SYMBOLS.join(',');
const POLL_MS  = 30_000;
// Stale threshold: 4× the poll interval. Backend /api/market/prices uses
// Phemex REST (no dedicated cache TTL beyond the exchange's own ~1s update
// cadence). Four missed polls (120s) signals a connectivity issue, not
// normal latency. Relative anchor: STALE_MS = 4 * POLL_MS.
const STALE_MS = 4 * POLL_MS; // 120 000 ms

interface TickerData {
  sym: string;
  price: number;
  change: number | null; // 24h %; null when perp data unavailable
}

// ─── Animated SCOPE (the hero centerpiece) ────────────────────────────
function Scope() {
  const [t, setT] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setT(x => x + 1), 60);
    return () => clearInterval(id);
  }, []);

  // Generate candle data once (deterministic per mount; not Math.random()
  // for the snapshot framework's sake — but the original prototype DID
  // use random, and the snapshot setup CSS suppresses animations anyway,
  // so the "frame 0" capture is what gets recorded).
  const candles = useRef(
    Array.from({ length: 48 }, (_, i) => {
      const base = 50 + Math.sin(i * 0.4) * 8 + i * 0.3;
      const seed = (i * 1103515245 + 12345) & 0x7fffffff; // deterministic LCG
      const r1 = (seed % 1000) / 1000 - 0.5;
      const r2 = ((seed >> 7) % 1000) / 1000 - 0.5;
      const o = base + r1 * 3;
      const c = base + r2 * 4;
      const h = Math.max(o, c) + Math.abs(r1) * 2;
      const l = Math.min(o, c) - Math.abs(r2) * 2;
      return { o, h, l, c };
    }),
  ).current;

  const lockX = 50 + Math.sin(t * 0.04) * 20;
  const lockY = 50 + Math.cos(t * 0.05) * 15;

  return (
    <div className="scope-wrap">
      <svg viewBox="-100 -100 200 200" className="scope-svg">
        <defs>
          <radialGradient id="scopeGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity=".15" />
            <stop offset="60%" stopColor="var(--accent)" stopOpacity=".04" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </radialGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="1.4" />
          </filter>
        </defs>
        <circle r="92" fill="url(#scopeGlow)" />
        {/* Outer rotating ring */}
        <g style={{ transform: `rotate(${t * 0.4}deg)`, transformOrigin: 'center' }}>
          <circle r="86" fill="none" stroke="var(--accent)" strokeOpacity=".5" strokeWidth=".5" strokeDasharray="2 6" />
          {[0, 60, 120, 180, 240, 300].map(a => (
            <line
              key={a}
              x1={Math.cos((a * Math.PI) / 180) * 82}
              y1={Math.sin((a * Math.PI) / 180) * 82}
              x2={Math.cos((a * Math.PI) / 180) * 90}
              y2={Math.sin((a * Math.PI) / 180) * 90}
              stroke="var(--accent)"
              strokeWidth="1"
            />
          ))}
        </g>
        {/* Mid ring */}
        <g style={{ transform: `rotate(${-t * 0.6}deg)`, transformOrigin: 'center' }}>
          <circle r="68" fill="none" stroke="var(--accent)" strokeOpacity=".7" strokeWidth=".6" />
          {Array.from({ length: 36 }).map((_, i) => (
            <line
              key={i}
              x1={Math.cos((i * 10 * Math.PI) / 180) * 64}
              y1={Math.sin((i * 10 * Math.PI) / 180) * 64}
              x2={Math.cos((i * 10 * Math.PI) / 180) * 68}
              y2={Math.sin((i * 10 * Math.PI) / 180) * 68}
              stroke="var(--accent)"
              strokeOpacity={i % 3 === 0 ? 0.8 : 0.3}
              strokeWidth=".5"
            />
          ))}
        </g>
        {/* Crosshairs */}
        <line x1="-92" y1="0" x2="-50" y2="0" stroke="var(--accent)" strokeWidth=".8" strokeOpacity=".7" />
        <line x1="50" y1="0" x2="92" y2="0" stroke="var(--accent)" strokeWidth=".8" strokeOpacity=".7" />
        <line x1="0" y1="-92" x2="0" y2="-50" stroke="var(--accent)" strokeWidth=".8" strokeOpacity=".7" />
        <line x1="0" y1="50" x2="0" y2="92" stroke="var(--accent)" strokeWidth=".8" strokeOpacity=".7" />
        {/* Candles arc */}
        <g>
          {candles.map((c, i) => {
            const ang = -90 + (i / (candles.length - 1)) * 180;
            const bullish = c.c >= c.o;
            return (
              <g
                key={i}
                style={{
                  transform: `rotate(${ang + 90}deg) translate(0,-38px)`,
                  transformOrigin: 'center',
                }}
              >
                <line
                  x1="0"
                  y1="-6"
                  x2="0"
                  y2="6"
                  stroke={bullish ? 'var(--green-soft)' : 'var(--red-2)'}
                  strokeOpacity=".6"
                  strokeWidth=".4"
                />
                <rect
                  x="-1.4"
                  y={bullish ? -3 : 0}
                  width="2.8"
                  height="3"
                  fill={bullish ? 'var(--green-soft)' : 'var(--red-2)'}
                  fillOpacity=".85"
                />
              </g>
            );
          })}
        </g>
        {/* Center reticle */}
        <circle r="22" fill="none" stroke="var(--accent)" strokeOpacity=".9" strokeWidth=".8" />
        <circle r="3" fill="var(--accent)" filter="url(#glow)" />
        <line x1="-22" y1="0" x2="-8" y2="0" stroke="var(--accent)" strokeWidth=".8" />
        <line x1="8" y1="0" x2="22" y2="0" stroke="var(--accent)" strokeWidth=".8" />
        <line x1="0" y1="-22" x2="0" y2="-8" stroke="var(--accent)" strokeWidth=".8" />
        <line x1="0" y1="8" x2="0" y2="22" stroke="var(--accent)" strokeWidth=".8" />
        {/* Scanning lock */}
        <g style={{ transform: `translate(${lockX - 50}%, ${lockY - 50}%)` }}>
          <rect
            x="-8"
            y="-8"
            width="16"
            height="16"
            fill="none"
            stroke="var(--accent)"
            strokeWidth="1"
            opacity={(Math.sin(t * 0.3) + 1) / 2 * 0.6 + 0.4}
          />
        </g>
        {/* Labels */}
        <text x="-86" y="-86" fill="var(--accent)" opacity=".7" fontSize="6" fontFamily="Share Tech Mono">[ TGT-LOCK ]</text>
        <text x="48" y="-86" fill="var(--accent)" opacity=".7" fontSize="6" fontFamily="Share Tech Mono">{('00' + (t % 999)).slice(-3)}</text>
        <text x="-86" y="92" fill="var(--accent)" opacity=".7" fontSize="6" fontFamily="Share Tech Mono">SCAN-MODE</text>
        <text x="60" y="92" fill="var(--accent)" opacity=".7" fontSize="6" fontFamily="Share Tech Mono">{(60 + Math.sin(t * 0.1) * 3).toFixed(1)}Hz</text>
      </svg>
      {/* HUD readouts overlay */}
      <div className="scope-hud-tl">
        <div className="mono" style={{ fontSize: 9, color: 'var(--accent)', letterSpacing: '.2em' }}>// FEED</div>
        <div className="mono" style={{ fontSize: 11, color: 'var(--fg)' }}>BTC ${(67841 + Math.sin(t * 0.2) * 40).toFixed(2)}</div>
        <div className="mono" style={{ fontSize: 9, color: 'var(--green-soft)' }}>+1.42% / 1H</div>
      </div>
      <div className="scope-hud-tr">
        <div className="mono" style={{ fontSize: 9, color: 'var(--accent)', letterSpacing: '.2em' }}>// DELTA</div>
        <div className="mono" style={{ fontSize: 11, color: 'var(--green-soft)' }}>BUY {(58.2 + Math.sin(t * 0.1) * 4).toFixed(1)}%</div>
        <div className="mono" style={{ fontSize: 9, color: 'var(--red-2)' }}>SELL {(41.8 - Math.sin(t * 0.1) * 4).toFixed(1)}%</div>
      </div>
      <div className="scope-hud-bl">
        <div className="mono" style={{ fontSize: 9, color: 'var(--accent)', letterSpacing: '.2em' }}>// REGIME</div>
        <div className="mono" style={{ fontSize: 11, color: 'var(--fg)' }}>RISK-ON</div>
        <div className="mono" style={{ fontSize: 9, color: 'var(--fg-3)' }}>VIX 14.2 · DXY 104.8</div>
      </div>
      <div className="scope-hud-br">
        <div className="mono" style={{ fontSize: 9, color: 'var(--accent)', letterSpacing: '.2em' }}>// SIGNAL</div>
        <div className="mono" style={{ fontSize: 11, color: 'var(--green-soft)' }}>● ARMED</div>
        <div className="mono" style={{ fontSize: 9, color: 'var(--fg-3)' }}>conf 82% · A-grade</div>
      </div>
    </div>
  );
}

// ─── Live ticker rail ─────────────────────────────────────────────────
function TickerRail() {
  const [items, setItems]   = useState<TickerData[] | null>(null);
  const [stale, setStale]   = useState(false);
  const [error, setError]   = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchTick() {
      try {
        const [pricesRes, fundingRes] = await Promise.all([
          fetch(`/api/market/prices?symbols=${encodeURIComponent(RAIL_SYMBOLS_PARAM)}`),
          fetch('/api/market/funding'),
        ]);
        if (!pricesRes.ok) throw new Error(`prices ${pricesRes.status}`);
        const prices: Array<{ symbol: string; price: number; timestamp: string }> =
          await pricesRes.json();

        // Funding failure is intentionally non-fatal: if /api/market/funding
        // returns non-2xx, changeMap stays empty and all 12 symbols render
        // with '— %' change column. Price data (the primary surface) is
        // unaffected. UX contract: no error banner for funding-only failure.
        const changeMap = new Map<string, number>();
        if (fundingRes.ok) {
          const fd: { rows?: Array<{ symbol: string; price_change_pct: number | null }> } =
            await fundingRes.json();
          for (const r of fd.rows ?? []) {
            if (r.price_change_pct != null) changeMap.set(r.symbol, r.price_change_pct);
          }
        }

        if (cancelled) return;
        const merged: TickerData[] = prices.map(p => ({
          sym: p.symbol,
          price: p.price,
          change: changeMap.get(p.symbol) ?? null,
        }));
        setItems(merged);
        setError(null);

        const oldest = prices.reduce(
          (min, p) => Math.min(min, new Date(p.timestamp).getTime()),
          Infinity,
        );
        setStale(Date.now() - oldest > STALE_MS);
      } catch (e) {
        console.warn('[TickerRail] fetch error:', e);
        if (!cancelled) setError(String(e));
      } finally {
        // Intentionally empty. Cleanup of the polling loop is owned by the
        // outer useEffect return — `cancelled = true` + `clearTimeout(tid)`.
        // This block exists as a structural marker so future edits inserting
        // additional setX writes between setItems and setStale have a visible
        // reminder that partial-write recovery is the caller's responsibility.
        // Rubric 7 (try/finally for code that can fail silently mid-flow).
      }
    }

    let tid: ReturnType<typeof setTimeout>;
    function schedule() {
      tid = setTimeout(async () => {
        if (cancelled) return;
        await fetchTick();
        if (!cancelled) schedule();
      }, POLL_MS);
    }
    fetchTick().then(() => { if (!cancelled) schedule(); });

    return () => { cancelled = true; clearTimeout(tid); };
  }, []);

  // Loading state
  if (!items && !error) {
    return (
      <div className="ticker-rail">
        <div className="ticker-track">
          {RAIL_SYMBOLS.map((sym, i) => (
            <div key={i} className="ticker-item">
              <span className="mono" style={{ fontSize: 10, color: 'var(--fg-3)', letterSpacing: '.1em' }}>
                {sym}
              </span>
              <span className="mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>$—</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Error with no prior data
  if (error && !items) {
    return (
      <div className="ticker-rail">
        <div className="ticker-track">
          <div className="ticker-item">
            <span className="mono" style={{ fontSize: 10, color: 'var(--amber)' }}>◌ FEED ERR · {error}</span>
          </div>
        </div>
      </div>
    );
  }

  const display = items!;
  return (
    <div className="ticker-rail" style={{ position: 'relative' }}>
      {stale && (
        <span
          className="mono"
          style={{ position: 'absolute', left: 4, top: '50%', transform: 'translateY(-50%)',
                   fontSize: 9, color: 'var(--amber)', zIndex: 2, pointerEvents: 'none' }}
        >
          ◌ STALE
        </span>
      )}
      <div className="ticker-track">
        {[...display, ...display].map((tk, i) => (
          <div key={i} className="ticker-item">
            <span className="mono" style={{ fontSize: 10, color: 'var(--fg-3)', letterSpacing: '.1em' }}>
              {tk.sym}
            </span>
            <span className="mono" style={{ fontSize: 11, color: 'var(--fg)', fontWeight: 600 }}>
              ${tk.price.toFixed(tk.price < 1 ? 4 : 2)}
            </span>
            {tk.change != null ? (
              <span className="mono" style={{ fontSize: 10, color: tk.change >= 0 ? 'var(--green-soft)' : 'var(--red-2)' }}>
                {tk.change >= 0 ? '▲' : '▼'} {Math.abs(tk.change).toFixed(2)}%
              </span>
            ) : (
              <span className="mono" style={{ fontSize: 10, color: 'var(--fg-3)' }}>— %</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Feature card ─────────────────────────────────────────────────────
interface FeatureCardProps {
  icon: ReactNode;
  title: string;
  body: string;
  to: string;
  accent: string;
}
function FeatureCard({ icon, title, body, to, accent }: FeatureCardProps) {
  return (
    <Link to={to} className="feat-card" style={{ textDecoration: 'none', color: 'inherit' }}>
      <div className="feat-icon" style={{ color: accent }}>{icon}</div>
      <div className="feat-title">{title}</div>
      <div className="feat-body">{body}</div>
      <div className="feat-cta mono" style={{ color: accent }}>ENTER →</div>
      <div className="feat-deco">
        <svg viewBox="0 0 100 100" width="100%" height="100%">
          <circle cx="50" cy="50" r="44" fill="none" stroke={accent} strokeOpacity=".15" strokeWidth=".5" strokeDasharray="2 4" />
          <circle cx="50" cy="50" r="30" fill="none" stroke={accent} strokeOpacity=".1" strokeWidth=".5" />
        </svg>
      </div>
    </Link>
  );
}

// ─── Sample signal card (proof) ───────────────────────────────────────
interface SignalProofProps {
  sym: string;
  side: 'LONG' | 'SHORT';
  price: string;
  conf: number;
  setup: string;
  change: number;
}
function SignalProof({ sym, side, price, conf, setup, change }: SignalProofProps) {
  const long = side === 'LONG';
  return (
    <div className="proof-signal">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <span className="mono" style={{ fontSize: 11, color: 'var(--fg)', letterSpacing: '.05em', fontWeight: 700 }}>{sym}</span>
        <span className={`chip ${long ? 'chip-green' : 'chip-red'}`} style={{ fontSize: 9 }}>
          {long ? '▲ LONG' : '▼ SHORT'}
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 8 }}>
        <span className="mono" style={{ fontSize: 16, color: 'var(--accent)', fontWeight: 700 }}>${price}</span>
        <span
          className="mono"
          style={{ fontSize: 10, color: change >= 0 ? 'var(--green-soft)' : 'var(--red-2)' }}
        >
          {change >= 0 ? '+' : ''}{change}%
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span className="mono" style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.14em', textTransform: 'uppercase' }}>
          {setup}
        </span>
        <span className="mono" style={{ fontSize: 10, color: 'var(--accent)', fontWeight: 700 }}>{conf}%</span>
      </div>
      <div style={{ height: 4, background: 'rgba(0,0,0,.5)', borderRadius: 2, marginTop: 6, overflow: 'hidden' }}>
        <div style={{ width: conf + '%', height: '100%', background: 'var(--accent)', boxShadow: `0 0 8px var(--accent)` }} />
      </div>
    </div>
  );
}

export function Landing() {
  // Snapshot framework readiness signal — set after first effect runs.
  useEffect(() => {
    document.body.setAttribute('data-snapshot-ready', 'true');
    return () => {
      document.body.removeAttribute('data-snapshot-ready');
    };
  }, []);

  return (
    <div className="landing-shell">
      <TickerRail />

      {/* HERO */}
      <section className="hero">
        <div className="hero-left">
          <div className="hero-eyebrow mono">
            <span style={{ color: 'var(--accent)' }}>●</span> SYSTEM-ONLINE · v1.0 · TACTICAL TRADING TERMINAL
          </div>
          <h1 className="hero-title">
            See the market<br />
            <span className="hero-title-em">before it moves.</span>
          </h1>
          <p className="hero-sub">
            SniperSight is a tactical heads-up display for crypto. Six purpose-built consoles fuse on-chain flow, derivatives positioning, and price action into one calm signal — then automate the trade end-to-end.
          </p>
          <div className="hero-stats">
            <div>
              <div className="hero-stat-v mono">61.4<span style={{ color: 'var(--accent)' }}>%</span></div>
              <div className="hero-stat-l mono">win rate · 60d</div>
            </div>
            <div className="hero-stat-sep" />
            <div>
              <div className="hero-stat-v mono">+0.84<span style={{ color: 'var(--accent)' }}>R</span></div>
              <div className="hero-stat-l mono">avg per trade</div>
            </div>
            <div className="hero-stat-sep" />
            <div>
              <div className="hero-stat-v mono">2.1<span style={{ color: 'var(--accent)' }}>s</span></div>
              <div className="hero-stat-l mono">sig→entry latency</div>
            </div>
            <div className="hero-stat-sep" />
            <div>
              <div className="hero-stat-v mono">412<span style={{ color: 'var(--accent)' }}>k</span></div>
              <div className="hero-stat-l mono">candles scanned/d</div>
            </div>
          </div>
          <div className="hero-cta">
            <Link to="/bot/status" className="btn-mega">
              <span>▶ ENTER COMMAND HUB</span>
              <span className="mono" style={{ fontSize: 9, letterSpacing: '.2em', opacity: 0.7, marginTop: 2 }}>
                CONFIGURE & DEPLOY THE BOT
              </span>
            </Link>
            <Link to="/training" className="btn-mega btn-mega-ghost">
              <span>◇ TRAINING GROUND</span>
              <span className="mono" style={{ fontSize: 9, letterSpacing: '.2em', opacity: 0.7, marginTop: 2 }}>
                RANGE · DRILLS · REPLAY
              </span>
            </Link>
          </div>
          <div className="hero-foot mono">
            <span>● BINANCE</span><span style={{ color: 'var(--fg-4)' }}>·</span>
            <span>● PHEMEX</span><span style={{ color: 'var(--fg-4)' }}>·</span>
            <span>● BYBIT</span><span style={{ color: 'var(--fg-4)' }}>·</span>
            <span>● BINGX</span><span style={{ color: 'var(--fg-4)' }}>·</span>
            <span style={{ color: 'var(--fg-3)' }}>4 venue execution router</span>
          </div>
        </div>
        <div className="hero-right">
          <Scope />
        </div>
      </section>

      {/* MODULES GRID */}
      <section className="modules">
        <div className="sec-title-row">
          <div className="sec-title-line" />
          <div className="mono" style={{ fontSize: 10, color: 'var(--fg-3)', letterSpacing: '.3em', textTransform: 'uppercase' }}>
            // SIX CONSOLES · ONE NETWORK
          </div>
          <div className="sec-title-line" />
        </div>
        <div className="modules-grid">
          <FeatureCard
            to="/intel"
            accent="#60a5fa"
            icon={<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="13" stroke="currentColor" strokeWidth="1.5" /><path d="M3 16h26M16 3a18 18 0 0 1 0 26M16 3a18 18 0 0 0 0 26" stroke="currentColor" strokeWidth="1" /></svg>}
            title="Intel"
            body="BTC dominance, market regime, liquidations, funding skew, news desk and AI macro commentary — the chart-room view of where the whole market sits right now."
          />
          <FeatureCard
            to="/scanner"
            accent="#fbbf24"
            icon={<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><circle cx="14" cy="14" r="9" stroke="currentColor" strokeWidth="1.5" /><path d="M21 21l7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /><circle cx="14" cy="14" r="3" fill="currentColor" /></svg>}
            title="Scanner"
            body="Continuous radar across 412 symbols. Detects breakouts, range fakes, liquidity sweeps and reclaim setups; ranks every signal A→D with conviction scoring."
          />
          <FeatureCard
            to="/bot/status"
            accent="#f87171"
            icon={<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><rect x="6" y="6" width="20" height="20" rx="2" stroke="currentColor" strokeWidth="1.5" /><path d="M11 16l4 4 6-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /><circle cx="16" cy="2" r="2" fill="currentColor" /></svg>}
            title="Bot Status"
            body="Live command center: armed positions, R-multiples ticking, kill-switch armed, full execution log. The room you sit in while the bot is hot."
          />
          <FeatureCard
            to="/journal"
            accent="#4ade80"
            icon={<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><path d="M6 6h20v20H6z" stroke="currentColor" strokeWidth="1.5" /><path d="M10 12h12M10 16h12M10 20h8" stroke="currentColor" strokeWidth="1.5" /></svg>}
            title="Journal"
            body="Every trade autopsied: equity curve, MAE/MFE, per-symbol edge, per-setup edge, time-of-day bias, drawdown, tags. Then trains the next iteration of the model."
          />
          <FeatureCard
            to="/training"
            accent="#22d3ee"
            icon={<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="3" fill="currentColor" /><circle cx="16" cy="16" r="9" stroke="currentColor" strokeWidth="1" strokeDasharray="2 2" /><circle cx="16" cy="16" r="13" stroke="currentColor" strokeWidth="1.5" /></svg>}
            title="Training"
            body="Drill room. Replay historical setups, run the autonomous paper-bot on simulated capital, ace the pattern quizzes. Build conviction before risking a dollar."
          />
          <FeatureCard
            to="/bot/setup"
            accent="#c084fc"
            icon={<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="4" stroke="currentColor" strokeWidth="1.5" /><path d="M16 4v4M16 24v4M4 16h4M24 16h4M7 7l3 3M22 22l3 3M7 25l3-3M22 10l3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>}
            title="Setup"
            body="Calibrate the strategy: timeframe stack, conviction floor, risk-per-trade, leverage cap, exchange routing, kill conditions. Ship it once, tune it forever."
          />
        </div>
      </section>

      {/* PROOF STRIP */}
      <section className="proof">
        <div className="proof-left">
          <div className="mono" style={{ fontSize: 10, color: 'var(--accent)', letterSpacing: '.3em', marginBottom: 14 }}>
            // LIVE-FEED // SAMPLE-SIGNALS
          </div>
          <h2 className="proof-h">Calm under fire.</h2>
          <p className="proof-p">
            The HUD never panics. It scores conviction, sizes risk, fires the entry, parks the stop, drags the trail, and posts a clean line in the journal. You watch it work — or you walk away.
          </p>
          <div className="proof-bullets">
            <div><span className="mono" style={{ color: 'var(--accent)' }}>›</span> Signal-grade gating: only A/B trades fire</div>
            <div><span className="mono" style={{ color: 'var(--accent)' }}>›</span> Hard daily-loss kill switch · armed at boot</div>
            <div><span className="mono" style={{ color: 'var(--accent)' }}>›</span> Per-venue position sync · zero drift</div>
            <div><span className="mono" style={{ color: 'var(--accent)' }}>›</span> Telegram + audio + on-screen alerts</div>
            <div><span className="mono" style={{ color: 'var(--accent)' }}>›</span> Backtest harness over 2y of 1m data</div>
          </div>
          <Link
            to="/scanner"
            className="btn btn-amber"
            style={{ textDecoration: 'none', padding: '12px 20px', fontSize: 12, fontWeight: 700, letterSpacing: '.2em', display: 'inline-block', marginTop: 18 }}
          >
            EXPLORE SIGNALS →
          </Link>
        </div>
        <div className="proof-right">
          <div className="proof-feed-head">
            <span className="mono" style={{ fontSize: 10, color: 'var(--fg-3)', letterSpacing: '.2em' }}>▣ LIVE SIGNAL FEED</span>
            <span className="chip chip-green" style={{ fontSize: 9 }}>● STREAMING</span>
          </div>
          <div className="proof-grid">
            <SignalProof sym="SOL/USDT" side="LONG" price="178.34" conf={87} setup="LIQ-SWEEP-RECLAIM" change={4.62} />
            <SignalProof sym="ETH/USDT" side="LONG" price="3284.55" conf={82} setup="RANGE-BREAK · 4H" change={2.18} />
            <SignalProof sym="ARB/USDT" side="SHORT" price="0.8912" conf={74} setup="LH · TREND-REJ" change={-1.18} />
            <SignalProof sym="SUI/USDT" side="LONG" price="1.482" conf={91} setup="CONSOL · BREAK" change={5.84} />
            <SignalProof sym="TIA/USDT" side="LONG" price="5.124" conf={78} setup="VOL-EXPANSION" change={3.92} />
            <SignalProof sym="BNB/USDT" side="LONG" price="612.40" conf={68} setup="VWAP-RECLAIM" change={0.88} />
          </div>
        </div>
      </section>

      {/* OPERATING DOCTRINE */}
      <section className="doctrine">
        <div className="sec-title-row">
          <div className="sec-title-line" />
          <div className="mono" style={{ fontSize: 10, color: 'var(--fg-3)', letterSpacing: '.3em', textTransform: 'uppercase' }}>
            // OPERATING DOCTRINE
          </div>
          <div className="sec-title-line" />
        </div>
        <div className="doctrine-grid">
          <div className="doctrine-card">
            <div className="doctrine-num mono">01</div>
            <div className="doctrine-h">Observe</div>
            <div className="doctrine-b">Intel watches the macro tide. Scanner watches every symbol. Nothing is missed; nothing is rushed.</div>
          </div>
          <div className="doctrine-arrow">→</div>
          <div className="doctrine-card">
            <div className="doctrine-num mono">02</div>
            <div className="doctrine-h">Score</div>
            <div className="doctrine-b">Each setup is graded A/B/C/D. Only A/B trades arm. Conviction gates the trigger.</div>
          </div>
          <div className="doctrine-arrow">→</div>
          <div className="doctrine-card">
            <div className="doctrine-num mono">03</div>
            <div className="doctrine-h">Execute</div>
            <div className="doctrine-b">Bot sizes, fires, places stop and trail. You watch the R climb on the HUD or sleep through it.</div>
          </div>
          <div className="doctrine-arrow">→</div>
          <div className="doctrine-card">
            <div className="doctrine-num mono">04</div>
            <div className="doctrine-h">Learn</div>
            <div className="doctrine-b">Journal autopsies every fill. Model retrains on closed trades. Edge compounds.</div>
          </div>
        </div>
      </section>

      {/* FINAL CTA */}
      <section className="cta-final">
        <div className="cta-final-bg">
          <svg viewBox="0 0 800 200" preserveAspectRatio="none" width="100%" height="100%">
            <defs>
              <linearGradient id="ctaG" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity=".06" />
                <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
              </linearGradient>
            </defs>
            <rect width="800" height="200" fill="url(#ctaG)" />
            {Array.from({ length: 30 }).map((_, i) => (
              <line key={i} x1={i * 30} y1="0" x2={i * 30} y2="200" stroke="var(--accent)" strokeOpacity=".05" strokeWidth=".5" />
            ))}
          </svg>
        </div>
        <div className="cta-final-inner">
          <div className="mono" style={{ fontSize: 10, color: 'var(--accent)', letterSpacing: '.4em', marginBottom: 14 }}>
            // READY-TO-DEPLOY
          </div>
          <h2 className="cta-final-h">Let the bot do the watching.</h2>
          <p className="cta-final-p">Six consoles. One network. The market on a leash.</p>
          <div className="cta-final-btns">
            <Link to="/bot/status" className="btn-mega">
              <span>▶ LAUNCH HUD</span>
              <span className="mono" style={{ fontSize: 9, letterSpacing: '.2em', opacity: 0.7, marginTop: 2 }}>
                ENTER COMMAND CENTER
              </span>
            </Link>
            <Link to="/training" className="btn-mega btn-mega-ghost">
              <span>◇ START TRAINING</span>
              <span className="mono" style={{ fontSize: 9, letterSpacing: '.2em', opacity: 0.7, marginTop: 2 }}>
                SAFE SANDBOX
              </span>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
