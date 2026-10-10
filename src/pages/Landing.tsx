import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import type { ReactNode } from 'react';
import snipersightLogo from '../assets/images/1000016768.png';
import './Landing.css';

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

interface SignalProofProps {
  sym: string;
  side: 'LONG' | 'SHORT';
  price: string;
  score: number;
  setup: string;
  change: number;
}

function SignalProof({ sym, side, price, score, setup, change }: SignalProofProps) {
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
        <span className="mono" style={{ fontSize: 10, color: 'var(--accent)', fontWeight: 700 }}>{score} / 100</span>
      </div>
      <div style={{ height: 4, background: 'rgba(0,0,0,.5)', borderRadius: 2, marginTop: 6, overflow: 'hidden' }}>
        <div style={{ width: score + '%', height: '100%', background: 'var(--accent)', boxShadow: `0 0 8px var(--accent)` }} />
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

      {/* HERO */}
      <section className="hero-stack">
        <img src={snipersightLogo} alt="SniperSight" className="hero-stack-logo" />
        <div className="hero-stack-tagline">SMART MONEY CONCEPTS · TRADING INTELLIGENCE</div>
        <h1 className="hero-stack-title">
          See the setup<br />
          <span className="hero-stack-title-em">with the evidence.</span>
        </h1>
        <p className="hero-stack-sub">
          Multi-timeframe analysis, explicit rejection reasons and inspectable trade plans. Configure execution separately; paper, testnet and live remain distinct.
        </p>
        <div className="hero-stack-stats">
          <div><div className="hero-stat-v mono">04</div><div className="hero-stat-l mono">Scanner modes</div></div>
          <div className="hero-stack-stat-sep" />
          <div><div className="hero-stat-v mono">SMC</div><div className="hero-stat-l mono">Multi-timeframe evidence</div></div>
          <div className="hero-stack-stat-sep" />
          <div><div className="hero-stat-v mono">PAPER / LIVE</div><div className="hero-stat-l mono">Explicit execution state</div></div>
        </div>
        <div className="hero-cta"><Link className="btn-mega" to="/scanner">OPEN SCANNER →</Link><Link className="btn-mega btn-mega-ghost" to="/training/range">PAPER SESSION →</Link></div>
        <p className="hero-stack-foot">Scores rank evidence. They are not win probabilities.</p>
      </section>

      {/* MODULES GRID */}
      <section className="modules">
        <div className="sec-title-row">
          <div className="sec-title-line" />
          <div className="mono" style={{ fontSize: 10, color: 'var(--fg-3)', letterSpacing: '.3em', textTransform: 'uppercase' }}>
            // SIX CONSOLES · ONE WORKSPACE
          </div>
          <div className="sec-title-line" />
        </div>
        <div className="modules-grid">
          <FeatureCard
            to="/intel"
            accent="#60a5fa"
            icon={<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="13" stroke="currentColor" strokeWidth="1.5" /><path d="M3 16h26M16 3a18 18 0 0 1 0 26M16 3a18 18 0 0 0 0 26" stroke="currentColor" strokeWidth="1" /></svg>}
            title="Intel"
            body="Market regime, mode advice, sessions and funding. Source times and unavailable fields remain visible."
          />
          <FeatureCard
            to="/scanner"
            accent="#fbbf24"
            icon={<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><circle cx="14" cy="14" r="9" stroke="currentColor" strokeWidth="1.5" /><path d="M21 21l7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /><circle cx="14" cy="14" r="3" fill="currentColor" /></svg>}
            title="Scanner"
            body="Four scanner modes on one pipeline. Inspect setup evidence, entry, stop and targets; review every rejection."
          />
          <FeatureCard
            to="/bot"
            accent="#f87171"
            icon={<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><rect x="6" y="6" width="20" height="20" rx="2" stroke="currentColor" strokeWidth="1.5" /><path d="M11 16l4 4 6-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /><circle cx="16" cy="2" r="2" fill="currentColor" /></svg>}
            title="Bot Status"
            body="Monitor the current session, open positions and pending orders. Attention causes and recovery controls stay visible."
          />
          <FeatureCard
            to="/journal"
            accent="#4ade80"
            icon={<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><path d="M6 6h20v20H6z" stroke="currentColor" strokeWidth="1.5" /><path d="M10 12h12M10 16h12M10 20h8" stroke="currentColor" strokeWidth="1.5" /></svg>}
            title="Journal"
            body="Review completed execution records, P&L and trade evidence. Filter and export the journal. Unknown amounts stay unknown."
          />
          <FeatureCard
            to="/training"
            accent="#22d3ee"
            icon={<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="3" fill="currentColor" /><circle cx="16" cy="16" r="9" stroke="currentColor" strokeWidth="1" strokeDasharray="2 2" /><circle cx="16" cy="16" r="13" stroke="currentColor" strokeWidth="1.5" /></svg>}
            title="Training"
            body="Nine authored lessons, causal historical replay and paper sessions. Model tools are labeled experimental research."
          />
          <FeatureCard
            to="/bot/setup"
            accent="#c084fc"
            icon={<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="4" stroke="currentColor" strokeWidth="1.5" /><path d="M16 4v4M16 24v4M4 16h4M24 16h4M7 7l3 3M22 22l3 3M7 25l3-3M22 10l3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>}
            title="Setup"
            body="Review risk, leverage and safety limits before starting live execution. The preflight makes capital at risk explicit."
          />
        </div>
      </section>

      {/* PROOF STRIP */}
      <section className="proof">
        <div className="proof-left">
          <div className="mono" style={{ fontSize: 10, color: 'var(--accent)', letterSpacing: '.3em', marginBottom: 14 }}>
            // EXAMPLE SETUPS · STATIC VALUES
          </div>
          <h2 className="proof-h">Evidence in view.</h2>
          <p className="proof-p">
            The scanner shows the evidence and planned trade. A separately configured session validates risk and executes, or rejects with reasons. These cards are illustrative, not current signals.
          </p>
          <div className="proof-bullets">
            <div><span className="mono" style={{ color: 'var(--accent)' }}>›</span> Fixed evidence-family budgets and explicit gates</div>
            <div><span className="mono" style={{ color: 'var(--accent)' }}>›</span> Session risk limits and visible safety state</div>
            <div><span className="mono" style={{ color: 'var(--accent)' }}>›</span> Separate paper, testnet and live paths</div>
            <div><span className="mono" style={{ color: 'var(--accent)' }}>›</span> Inspect rejection reasons and diagnostic output</div>
            <div><span className="mono" style={{ color: 'var(--accent)' }}>›</span> Causal historical replay with available source data</div>
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
            <span className="mono" style={{ fontSize: 10, color: 'var(--fg-3)', letterSpacing: '.2em' }}>▣ EXAMPLE SIGNALS</span>
            <span className="chip chip-green" style={{ fontSize: 9 }}>STATIC EXAMPLES</span>
          </div>
          <div className="proof-grid">
            <SignalProof sym="SOL/USDT" side="LONG" price="178.34" score={87} setup="LIQ-SWEEP-RECLAIM" change={4.62} />
            <SignalProof sym="ETH/USDT" side="LONG" price="3284.55" score={82} setup="RANGE-BREAK · 4H" change={2.18} />
            <SignalProof sym="ARB/USDT" side="SHORT" price="0.8912" score={74} setup="LH · TREND-REJ" change={-1.18} />
            <SignalProof sym="SUI/USDT" side="LONG" price="1.482" score={91} setup="CONSOL · BREAK" change={5.84} />
            <SignalProof sym="TIA/USDT" side="LONG" price="5.124" score={78} setup="VOL-EXPANSION" change={3.92} />
            <SignalProof sym="BNB/USDT" side="LONG" price="612.40" score={68} setup="VWAP-RECLAIM" change={0.88} />
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
            <div className="doctrine-b">Read market context and choose the scanner mode manually. Unavailable data stays explicit.</div>
          </div>
          <div className="doctrine-arrow">→</div>
          <div className="doctrine-card">
            <div className="doctrine-num mono">02</div>
            <div className="doctrine-h">Score</div>
            <div className="doctrine-b">Inspect fixed evidence-family budgets and effective thresholds. Scores are not win probabilities.</div>
          </div>
          <div className="doctrine-arrow">→</div>
          <div className="doctrine-card">
            <div className="doctrine-num mono">03</div>
            <div className="doctrine-h">Execute</div>
            <div className="doctrine-b">Review the plan and risk. Execution follows the selected session and its configured safety limits.</div>
          </div>
          <div className="doctrine-arrow">→</div>
          <div className="doctrine-card">
            <div className="doctrine-num mono">04</div>
            <div className="doctrine-h">Learn</div>
            <div className="doctrine-b">Review execution records and causal evidence. Research tools are separate from trading decisions.</div>
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
            // REVIEW BEFORE EXECUTION
          </div>
          <h2 className="cta-final-h">Plan. Inspect. Execute.</h2>
          <p className="cta-final-p">Every signal has evidence. Every rejection has a reason.</p>
        </div>
      </section>
    </div>
  );
}
