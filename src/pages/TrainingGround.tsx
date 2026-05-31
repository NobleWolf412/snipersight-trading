/**
 * TrainingGround — Phase 3d sub-step 1 (Drills extracted to /training/drills)
 *
 * Training-hub: 5 module cards (Range / Drills / Replay / Quizzes / Lessons).
 *
 * Data wiring:
 *   - Real ML state via mlService.getStatus on mount (drives DRILLS card stats
 *     + topbar MODEL chip).
 *   - Module cards link to existing flows — RANGE ⇒ /training/range,
 *     DRILLS ⇒ /training/drills, REPLAY ⇒ /training/replay, LESSONS ⇒
 *     /training/lessons (separate pages). QUIZZES ⇒ href="#" placeholder
 *     (no backend content yet; visually disabled).
 *
 * The inline DrillsPanel that previously lived at #drills now lives at
 * /training/drills (src/pages/training/Drills.tsx). Operator-driven: clicking
 * the DRILLS card should navigate to a dedicated page, not scroll-anchor.
 *
 * body[data-snapshot-ready="true"] is set after the initial mlService.getStatus
 * call settles (resolved or errored).
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Chip, FooterStatus, PageHead } from '@/components/hud';
import { mlService, type MLStatus } from '@/services/mlService';

// ─── Module catalog ───────────────────────────────────────────────────────

interface ModuleStat {
  k: string;
  v: string;
  vc?: string;
}

interface Module {
  id: string;
  label: string;
  tag: string;
  color: string;
  body: string;
  stat: ModuleStat[];
  cta: string;
  href: string;
  disabled?: boolean;
}

const MODULES: Module[] = [
  {
    id: 'range',
    label: 'RANGE',
    tag: 'Live-fire paper trader',
    color: '#22d3ee',
    body:
      "Ghost — autonomous bot armed on simulated capital. Same engine as the live bot, no real funds. Generates the trade data the ML model trains on.",
    stat: [
      { k: 'Status', v: '● ARMED', vc: '#4ade80' },
      { k: 'Sim Equity', v: '$5,842' },
      { k: 'Win', v: '61%' },
    ],
    cta: 'ENTER RANGE',
    href: '/training/range',
  },
  {
    id: 'drills',
    label: 'DRILLS',
    tag: 'ML model training',
    color: '#c084fc',
    body:
      "Train the bot on Ghost's closed paper trades. Promote new params to the live bot when the model beats baseline — or reset the model to factory defaults.",
    stat: [
      { k: 'Model', v: '—', vc: '#c084fc' },
      { k: 'vs Baseline', v: '—', vc: '#c084fc' },
      { k: 'Samples', v: '—' },
    ],
    cta: 'OPEN DRILLS',
    href: '/training/drills',
  },
  {
    id: 'replay',
    label: 'REPLAY',
    tag: 'Historical setup walkthrough',
    color: '#fbbf24',
    body:
      'Step through real past trades candle-by-candle. See the entry trigger, stop placement, and exit logic exactly as the bot saw it.',
    stat: [
      { k: 'Library', v: '—' },
      { k: 'Last', v: '—' },
      { k: 'Yours', v: '—' },
    ],
    cta: 'ENTER REPLAY',
    href: '/training/replay',
  },
  {
    id: 'quizzes',
    label: 'QUIZZES',
    tag: 'Pattern recognition tests',
    color: '#60a5fa',
    body:
      'Grade A/B/C/D drills on order blocks, liquidity sweeps, structure breaks. Build the eye before you trust the bot.',
    stat: [
      { k: 'Bank', v: '—' },
      { k: 'Streak', v: '—' },
      { k: 'Score', v: '—' },
    ],
    cta: 'COMING SOON',
    href: '#',
    disabled: true,
  },
  {
    id: 'lessons',
    label: 'LESSONS',
    tag: 'Strategy library',
    color: '#4ade80',
    body:
      'Read-up on every setup the bot trades. Order blocks, FVGs, liquidity sweeps, regime detection, position sizing.',
    stat: [
      { k: 'Chapters', v: '—' },
      { k: 'Done', v: '—' },
      { k: 'Next', v: '—' },
    ],
    cta: 'OPEN LESSONS',
    href: '/training/lessons',
  },
];

// ─── ModCard ──────────────────────────────────────────────────────────────

function ModCard({ m }: { m: Module }) {
  const onClick = (e: React.MouseEvent) => {
    if (m.disabled) e.preventDefault();
  };
  return (
    <a
      href={m.href}
      onClick={onClick}
      className="tg-card"
      style={{
        borderColor: `color-mix(in oklch, ${m.color} 30%, var(--border-soft))`,
        opacity: m.disabled ? 0.55 : 1,
        cursor: m.disabled ? 'not-allowed' : 'pointer',
      }}
    >
      <div className="tg-card-head">
        <div className="tg-card-title" style={{ color: m.color }}>
          <span
            className="mono"
            style={{
              fontSize: 11,
              letterSpacing: '.32em',
              opacity: 0.6,
              marginRight: 8,
            }}
          >
            {m.id.toUpperCase().padStart(2, '0').slice(0, 2)}
          </span>
          {m.label}
        </div>
        <div className="tg-card-tag mono">{m.tag}</div>
      </div>
      <div className="tg-card-body">{m.body}</div>
      <div className="tg-card-stats">
        {m.stat.map((s, i) => (
          <div key={i}>
            <div
              className="mono"
              style={{
                fontSize: 9,
                color: 'var(--fg-4)',
                letterSpacing: '.18em',
                textTransform: 'uppercase',
              }}
            >
              {s.k}
            </div>
            <div
              className="mono"
              style={{
                fontSize: 13,
                color: s.vc ?? 'var(--fg)',
                fontWeight: 700,
                marginTop: 2,
              }}
            >
              {s.v}
            </div>
          </div>
        ))}
      </div>
      <div className="tg-card-cta mono" style={{ color: m.color }}>
        {m.cta} →
      </div>
      <div className="tg-card-deco" style={{ color: m.color }}>
        <svg viewBox="-50 -50 100 100" width="100%" height="100%">
          <circle
            r="44"
            fill="none"
            stroke="currentColor"
            strokeOpacity=".2"
            strokeWidth=".5"
            strokeDasharray="2 4"
          />
          <circle
            r="30"
            fill="none"
            stroke="currentColor"
            strokeOpacity=".15"
            strokeWidth=".5"
          />
        </svg>
      </div>
    </a>
  );
}

// ─── Drills card baseline — live UI lives at /training/drills

const BASELINE_PCT = 55; // placeholder — see src/pages/training/Drills.tsx for the live panel.

// ─── Page ─────────────────────────────────────────────────────────────────

export function TrainingGround() {
  const [status, setStatus] = useState<MLStatus | null>(null);
  const readyRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await mlService.getStatus();
        if (!cancelled) setStatus(s);
      } catch {
        // status load failure leaves DRILLS card stats as placeholders;
        // the live drills page (/training/drills) handles its own retries.
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

  // Inject DRILLS module stat values once status loads.
  const modules = useMemo(() => {
    return MODULES.map((m) => {
      if (m.id !== 'drills' || !status) return m;
      const versus = (status.accuracy * 100 - BASELINE_PCT).toFixed(1);
      const above = status.accuracy * 100 > BASELINE_PCT;
      return {
        ...m,
        stat: [
          { k: 'Model', v: status.model_type, vc: '#c084fc' },
          {
            k: 'vs Baseline',
            v: `${above ? '+' : ''}${versus}%`,
            vc: above ? '#4ade80' : '#f87171',
          },
          { k: 'Samples', v: status.n_samples.toLocaleString() },
        ],
      };
    });
  }, [status]);

  const modelChip = status ? `MODEL · ${status.model_type}` : 'MODEL · —';

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
              style={{ color: 'var(--accent)' }}
            />
            <circle
              cx="12"
              cy="12"
              r="5"
              stroke="currentColor"
              strokeWidth="1"
              strokeDasharray="2 2"
              style={{ color: 'var(--accent)' }}
            />
            <circle
              cx="12"
              cy="12"
              r="1.5"
              fill="currentColor"
              style={{ color: 'var(--accent)' }}
            />
          </svg>
        }
        title="Training Ground"
        subtitle="Hub · Range · Drills · Replay · Quizzes · Lessons — practice the system, train the model"
        badges={
          <>
            <Chip kind="cyan">● 5 MODULES</Chip>
            <Chip kind="green">GHOST · ARMED</Chip>
            <Chip kind="purple">{modelChip}</Chip>
          </>
        }
      />

      <div
        className="mono"
        style={{
          fontSize: 10,
          color: 'var(--fg-3)',
          letterSpacing: '.24em',
          textTransform: 'uppercase',
          margin: '10px 4px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: 14,
        }}
      >
        <div
          style={{
            flex: 1,
            height: 1,
            background: 'linear-gradient(90deg,transparent,var(--border-soft),transparent)',
          }}
        />
        <span>// SELECT A TRAINING MODULE</span>
        <div
          style={{
            flex: 1,
            height: 1,
            background: 'linear-gradient(90deg,transparent,var(--border-soft),transparent)',
          }}
        />
      </div>

      <div className="tg-grid">
        {modules.map((m) => (
          <ModCard key={m.id} m={m} />
        ))}
      </div>

      <FooterStatus latency={36} />

      <style>{`
        .tg-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
        @media (max-width:1100px){.tg-grid{grid-template-columns:repeat(2,1fr)}}
        @media (max-width:700px){.tg-grid{grid-template-columns:1fr}}
        .tg-card{position:relative;display:flex;flex-direction:column;gap:10px;padding:18px 20px;border:1px solid var(--border-soft);border-radius:12px;background:linear-gradient(135deg,rgba(0,0,0,.55),oklch(0.22 0.010 125 / .55));text-decoration:none;color:inherit;overflow:hidden;transition:transform .2s,box-shadow .2s;min-height:230px}
        .tg-card:hover{transform:translateY(-2px);box-shadow:0 8px 32px rgba(0,0,0,.4)}
        .tg-card-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
        .tg-card-title{font-family:'Share Tech Mono',monospace;font-size:24px;letter-spacing:.16em;text-transform:uppercase}
        .tg-card-tag{font-size:10px;color:var(--fg-4);letter-spacing:.2em;text-transform:uppercase;text-align:right;max-width:140px;line-height:1.4}
        .tg-card-body{font-size:13px;color:var(--fg-2);line-height:1.5;flex:1}
        .tg-card-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:10px 0;border-top:1px dashed var(--border-soft);border-bottom:1px dashed var(--border-soft)}
        .tg-card-cta{font-size:11px;letter-spacing:.24em;font-weight:700;padding-top:4px}
        .tg-card-deco{position:absolute;right:-30px;bottom:-30px;width:130px;height:130px;opacity:.5;pointer-events:none}
      `}</style>
    </div>
  );
}

export default TrainingGround;
