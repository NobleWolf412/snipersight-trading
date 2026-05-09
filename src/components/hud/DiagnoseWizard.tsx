/**
 * DiagnoseWizard — 9-step playbook modal (Phase 3g.ii.f)
 *
 * Plan reference: peppy-sniffing-owl §5a.
 *
 *   "Diagnose button on Bot Status. Modal walks the 9-step playbook
 *    from the spec:
 *      1. Phemex pill green?
 *      2. Universe size > 0?
 *      3. Scan cycles running?
 *      4. Symbols failing MISSING_TF?
 *      5. Most signals dying at CONFLUENCE?
 *      6. Dying at REGIME_ALIGNMENT/VETO?
 *      7. Dying at RISK_VALIDATION?
 *      8. Dying at MAX_POSITIONS/HAS_POSITION?
 *      9. Plans EXECUTED but no fills?
 *    Each step renders ✓ / ✗ inline; failed steps show a CTA to the
 *    right tuning surface. No new backend — orchestrates existing
 *    endpoints."
 *
 * Real-data wiring
 * ────────────────
 *   Step 1 → liveTradingService.getPhemexHealth() — same endpoint the
 *            persistent topbar pill consumes.
 *   Step 2 → api.getUniverse() — `data.counts.qualified > 0`.
 *   Step 3 → api.getLastCycle() — `failed === false` AND `ts_end` not
 *            stale (within 2× expected cycle interval ≈ 120s).
 *   Steps 4-9 → orchestrator-emitted `signals_per_stage` map plus
 *            position state from the bot status payload (passed in via
 *            props rather than re-fetched).
 *
 * Synthetic-but-disclosed: none. Wizard renders ONLY backend data;
 * an unreachable endpoint surfaces a `?` undetermined chip rather than
 * pretending the step is OK.
 *
 * Symmetry (CLAUDE.md §10 #3)
 * ───────────────────────────
 *   Direction-agnostic. The diagnostic playbook applies regardless of
 *   long/short flow. The `bottleneck_stage` from cycles/last and the
 *   `signals_per_stage` map both aggregate across direction by design.
 *
 * Determinism for snapshots
 * ─────────────────────────
 *   - Steps execute sequentially with their results memoized at modal
 *     mount; no Date.now / setInterval. Stale-cycle threshold uses a
 *     prop-injected `now` reference (defaults to a frozen ts in tests).
 *   - All step CTAs are static `<Link>`-style buttons with deterministic
 *     route hashes.
 */
import { useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { api, type CycleHeartbeat, type Universe } from '@/utils/api';
import { liveTradingService, type LiveTradingStatus } from '@/services/liveTradingService';

import { Chip } from './Chip';
import { Modal } from './Modal';
import { classifyPhemexHealth, type PhemexHealth } from './PhemexStatusPill';

// ─── Types ───────────────────────────────────────────────────────────

type StepResult = 'pass' | 'fail' | 'unknown';

interface StepRow {
  n: number;
  title: string;
  result: StepResult;
  detail: string;
  cta?: { label: string; href: string };
}

interface DiagnoseWizardProps {
  open: boolean;
  onClose: () => void;
  /** Live status payload — already polled by parent BotStatus page. */
  status: LiveTradingStatus | null;
  /**
   * Reference time (epoch seconds) for the stale-cycle check.
   * Production parent should capture `Date.now() / 1000` at the moment
   * the modal opens (not at parent mount); snapshot tests freeze the
   * global `Date` constructor via `page.addInitScript` so the same code
   * path produces a deterministic value during capture.
   */
  nowSec: number;
}

const STALE_CYCLE_SEC = 120;

export function DiagnoseWizard({ open, onClose, status, nowSec }: DiagnoseWizardProps) {
  const [phemex, setPhemex] = useState<PhemexHealth | null>(null);
  const [universe, setUniverse] = useState<Universe | null>(null);
  const [cycle, setCycle] = useState<CycleHeartbeat | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoaded(false);
    setErrors([]);

    (async () => {
      const errs: string[] = [];
      let p: PhemexHealth | null = null;
      let u: Universe | null = null;
      let c: CycleHeartbeat | null = null;
      try {
        // Step 1 — Phemex health.
        try {
          p = (await liveTradingService.getPhemexHealth()) as PhemexHealth;
        } catch (e) {
          errs.push(`phemex: ${e instanceof Error ? e.message : String(e)}`);
        }
        // Step 2 — Universe.
        try {
          const uRes = await api.getUniverse();
          u = uRes.data?.data ?? null;
          if (uRes.error) errs.push(`universe: ${uRes.error}`);
        } catch (e) {
          errs.push(`universe: ${e instanceof Error ? e.message : String(e)}`);
        }
        // Step 3 — Last cycle heartbeat.
        try {
          const cRes = await api.getLastCycle();
          c = cRes.data?.data ?? null;
          if (cRes.error) errs.push(`cycles: ${cRes.error}`);
        } catch (e) {
          errs.push(`cycles: ${e instanceof Error ? e.message : String(e)}`);
        }
      } finally {
        // §16 #7 — try/finally guarantees `loaded=true` always fires so
        // the modal never hangs on "— running playbook —" even if the
        // request<T> helper throws unexpectedly.
        if (!cancelled) {
          setPhemex(p);
          setUniverse(u);
          setCycle(c);
          setErrors(errs);
          setLoaded(true);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [open]);

  if (!open) return null;

  const steps = loaded ? buildSteps({ phemex, universe, cycle, status, nowSec }) : [];
  const passCount = steps.filter((s) => s.result === 'pass').length;
  const failCount = steps.filter((s) => s.result === 'fail').length;
  const unknownCount = steps.filter((s) => s.result === 'unknown').length;

  return (
    <Modal onClose={onClose} maxWidth={780}>
      <div style={{ padding: 18 }}>
        <div
          className="sec-head"
          style={{ marginBottom: 14, paddingBottom: 10, borderBottom: '1px solid var(--border-soft)' }}
        >
          <div className="sec-title">
            <span className="dot" /> Diagnose — 9-step Playbook
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <Chip kind="green">{passCount} PASS</Chip>
            {failCount > 0 && <Chip kind="red">{failCount} FAIL</Chip>}
            {unknownCount > 0 && <Chip kind="amber">{'\u25CC'} {unknownCount} UNKNOWN</Chip>}
            <button
              type="button"
              className="btn"
              onClick={onClose}
              style={{ marginLeft: 8, fontSize: 10, padding: '4px 10px' }}
            >
              CLOSE
            </button>
          </div>
        </div>

        {!loaded ? (
          <div className="mono" style={loadingStyle}>— running playbook —</div>
        ) : (
          <>
            {errors.length > 0 && (
              <div className="mono" style={errStripStyle}>
                {'\u26A0'} fetch errors: {errors.join(' · ')}
              </div>
            )}
            <ol style={{ margin: 0, padding: 0, listStyle: 'none' }}>
              {steps.map((s) => renderStep(s))}
            </ol>
          </>
        )}
      </div>
    </Modal>
  );
}

// ─── Step builder ────────────────────────────────────────────────────

interface BuildCtx {
  phemex: PhemexHealth | null;
  universe: Universe | null;
  cycle: CycleHeartbeat | null;
  status: LiveTradingStatus | null;
  nowSec: number;
}

function buildSteps(ctx: BuildCtx): StepRow[] {
  const rows: StepRow[] = [];

  const isRunning = ctx.status?.status === 'running';

  // Step 1 — Phemex pill green.
  rows.push(step1Phemex(ctx.phemex, isRunning));

  // Step 2 — Universe size > 0.
  rows.push(step2Universe(ctx.universe));

  // Step 3 — Scan cycles running.
  rows.push(step3Cycles(ctx.cycle, ctx.nowSec));

  // Steps 4-9 — derive from cycle.signals_per_stage when available.
  // §16 #3 mass-conservation sanity: backend invariant is
  //   plans_emitted + sum(signals_per_stage) === symbols_scanned
  // Surface a console.warn on violation so fixture/orchestrator regressions
  // are noticed at the consumption site (not just at producer).
  const sps = ctx.cycle?.signals_per_stage ?? {};
  const total = Object.values(sps).reduce((s, n) => s + n, 0);
  if (ctx.cycle && import.meta.env?.MODE !== 'production') {
    const expected = ctx.cycle.symbols_scanned;
    const got = (ctx.cycle.plans_emitted ?? 0) + total;
    if (expected != null && got !== expected) {
      // eslint-disable-next-line no-console
      console.warn(
        `[DiagnoseWizard] mass-conservation violated: plans+stages=${got} != symbols_scanned=${expected}`,
      );
    }
  }
  rows.push(step4MissingTF(sps, total));
  rows.push(step5Confluence(sps, total));
  rows.push(step6Regime(sps, total));
  rows.push(step7Risk(sps, total));
  rows.push(step8Positions(ctx.status));
  rows.push(step9Fills(ctx.phemex, ctx.cycle));

  return rows;
}

function step1Phemex(p: PhemexHealth | null, isRunning: boolean): StepRow {
  if (!p) {
    return {
      n: 1,
      title: 'Phemex pill green?',
      result: 'unknown',
      detail: 'healthz endpoint unreachable',
      cta: { label: 'INSPECT TOPBAR PILL', href: '/bot' },
    };
  }
  // Reuse canonical PhemexStatusPill severity logic (audit #2 — single
  // source of truth so step 1 cannot drift from the topbar pill).
  const { severity, reasons } = classifyPhemexHealth(p, isRunning);
  if (severity === 'green') {
    return { n: 1, title: 'Phemex pill green?', result: 'pass', detail: reasons.join(' · ') };
  }
  if (severity === 'idle') {
    return {
      n: 1,
      title: 'Phemex pill green?',
      result: 'unknown',
      detail: reasons.join(' · '),
    };
  }
  return {
    n: 1,
    title: 'Phemex pill green?',
    result: 'fail',
    detail: `${severity.toUpperCase()} · ${reasons.join(' · ')}`,
    cta: { label: 'OPEN HEALTHZ MODAL', href: '/bot' },
  };
}

function step2Universe(u: Universe | null): StepRow {
  if (!u) {
    return {
      n: 2,
      title: 'Universe size > 0?',
      result: 'unknown',
      detail: 'universe endpoint unreachable',
    };
  }
  if (u.counts.qualified > 0) {
    return {
      n: 2,
      title: 'Universe size > 0?',
      result: 'pass',
      detail: `${u.counts.qualified} qualified / ${u.counts.total_candidates} candidates`,
    };
  }
  return {
    n: 2,
    title: 'Universe size > 0?',
    result: 'fail',
    detail: `0 qualified · ${u.counts.dropped} dropped`,
    cta: { label: 'INSPECT UNIVERSE', href: '/bot' },
  };
}

function step3Cycles(c: CycleHeartbeat | null, nowSec: number): StepRow {
  if (!c) {
    return {
      n: 3,
      title: 'Scan cycles running?',
      result: 'unknown',
      detail: 'cycles/last endpoint unreachable',
    };
  }
  if (c.failed) {
    return {
      n: 3,
      title: 'Scan cycles running?',
      result: 'fail',
      detail: `last cycle failed${c.exception_class ? ` · ${c.exception_class}` : ''}`,
      cta: { label: 'OPEN BOT LOGS', href: '/bot' },
    };
  }
  const endTs = c.ts_end ?? c.ts_start;
  const ageSec = Math.max(0, nowSec - endTs);
  if (ageSec > STALE_CYCLE_SEC) {
    return {
      n: 3,
      title: 'Scan cycles running?',
      result: 'fail',
      detail: `last cycle ended ${Math.round(ageSec)}s ago · stale (>${STALE_CYCLE_SEC}s)`,
      cta: { label: 'CHECK ORCHESTRATOR', href: '/bot' },
    };
  }
  return {
    n: 3,
    title: 'Scan cycles running?',
    result: 'pass',
    detail: `last cycle ended ${Math.round(ageSec)}s ago · ${c.symbols_scanned} symbols`,
  };
}

function makeStageStep(
  n: number,
  title: string,
  stageKeys: string[],
  sps: Record<string, number>,
  total: number,
  cta: { label: string; href: string },
): StepRow {
  if (total === 0) {
    return {
      n,
      title,
      result: 'unknown',
      detail: 'no cycle data',
    };
  }
  // Case-insensitive lookup — orchestrator emits stage keys in different
  // cases depending on subsystem (uppercase trace stages vs lowercase
  // rejection-reason keys). Match defensively.
  const wanted = new Set(stageKeys.map((k) => k.toLowerCase()));
  let stageHits = 0;
  for (const [k, v] of Object.entries(sps)) {
    if (wanted.has(k.toLowerCase())) stageHits += v;
  }
  const pct = (stageHits / total) * 100;
  // "Most signals dying at X" threshold = 30% of all rejections in the stage(s).
  if (pct >= 30) {
    return {
      n,
      title,
      result: 'fail',
      detail: `${stageHits}/${total} (${pct.toFixed(0)}%) rejected at ${stageKeys.join('/')}`,
      cta,
    };
  }
  return {
    n,
    title,
    result: 'pass',
    detail: `${stageHits}/${total} (${pct.toFixed(0)}%) — within tolerance`,
  };
}

function step4MissingTF(sps: Record<string, number>, total: number): StepRow {
  return makeStageStep(
    4,
    'Symbols failing MISSING_TF?',
    ['MISSING_TF', 'DATA', 'CRITICAL_TF', 'no_data', 'missing_tf'],
    sps,
    total,
    { label: 'INSPECT DATA INGEST', href: '/bot' },
  );
}

function step5Confluence(sps: Record<string, number>, total: number): StepRow {
  return makeStageStep(
    5,
    'Most signals dying at CONFLUENCE?',
    ['CONFLUENCE_SCORE', 'CONFLUENCE', 'low_confluence'],
    sps,
    total,
    { label: 'TUNE SCANNER MODE', href: '/scanner' },
  );
}

function step6Regime(sps: Record<string, number>, total: number): StepRow {
  return makeStageStep(
    6,
    'Dying at REGIME_ALIGNMENT/VETO?',
    ['REGIME', 'REGIME_ALIGNMENT', 'BTC_VETO', 'MACRO_VETO', 'regime_alignment'],
    sps,
    total,
    { label: 'OPEN INTEL', href: '/intel' },
  );
}

function step7Risk(sps: Record<string, number>, total: number): StepRow {
  return makeStageStep(
    7,
    'Dying at RISK_VALIDATION?',
    ['RISK_VALIDATION', 'RISK', 'STOP_TOO_FAR', 'risk_validation'],
    sps,
    total,
    { label: 'TUNE RISK PANEL', href: '/bot' },
  );
}

function step8Positions(status: LiveTradingStatus | null): StepRow {
  // Audit #1 — derive from live position-cap pressure rather than
  // signals_per_stage. Backend (`orchestrator.py`) does not currently emit
  // a dedicated rejection reason for position caps, so the stage-map
  // approach would always report PASS. Compare concurrent open positions
  // against the configured cap instead.
  if (!status) {
    return {
      n: 8,
      title: 'Dying at MAX_POSITIONS/HAS_POSITION?',
      result: 'unknown',
      detail: 'bot status unreachable',
    };
  }
  const concurrent = status.positions?.length ?? 0;
  const cap = status.config?.max_positions ?? null;
  if (cap == null) {
    return {
      n: 8,
      title: 'Dying at MAX_POSITIONS/HAS_POSITION?',
      result: 'unknown',
      detail: `${concurrent} concurrent open · max_positions not configured`,
    };
  }
  if (concurrent >= cap) {
    return {
      n: 8,
      title: 'Dying at MAX_POSITIONS/HAS_POSITION?',
      result: 'fail',
      detail: `${concurrent}/${cap} concurrent — cap saturated`,
      cta: { label: 'TUNE POSITION CAPS', href: '/bot' },
    };
  }
  return {
    n: 8,
    title: 'Dying at MAX_POSITIONS/HAS_POSITION?',
    result: 'pass',
    detail: `${concurrent}/${cap} concurrent — headroom OK`,
  };
}

function step9Fills(p: PhemexHealth | null, c: CycleHeartbeat | null): StepRow {
  if (!c) {
    return {
      n: 9,
      title: 'Plans EXECUTED but no fills?',
      result: 'unknown',
      detail: 'cycles/last endpoint unreachable',
    };
  }
  const plans = c.plans_emitted ?? 0;
  if (plans === 0) {
    return {
      n: 9,
      title: 'Plans EXECUTED but no fills?',
      result: 'pass',
      detail: 'no plans emitted this cycle — N/A',
    };
  }
  // Look for fill counters on healthz (executor.fills_recorded_via_*).
  const exec = (p as { executor?: Record<string, number> } | null)?.executor ?? {};
  const fills = Object.entries(exec)
    .filter(([k]) => k.startsWith('fills_recorded_via_'))
    .reduce((s, [, v]) => s + (typeof v === 'number' ? v : 0), 0);
  if (fills === 0) {
    return {
      n: 9,
      title: 'Plans EXECUTED but no fills?',
      result: 'fail',
      detail: `${plans} plans emitted · 0 fills recorded`,
      cta: { label: 'OPEN EXECUTOR LOGS', href: '/bot' },
    };
  }
  return {
    n: 9,
    title: 'Plans EXECUTED but no fills?',
    result: 'pass',
    detail: `${plans} plans · ${fills} fills recorded`,
  };
}

// ─── Render helpers ──────────────────────────────────────────────────

function renderStep(s: StepRow): ReactNode {
  const glyph = s.result === 'pass' ? '\u2713' : s.result === 'fail' ? '\u2717' : '\u25CC';
  const color =
    s.result === 'pass' ? 'var(--green-soft)' : s.result === 'fail' ? 'var(--red-2)' : 'var(--amber-2)';
  const chipKind = s.result === 'pass' ? 'green' : s.result === 'fail' ? 'red' : 'amber';
  return (
    <li key={s.n} style={stepRowStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
        <span
          className="mono"
          style={{
            color,
            fontWeight: 700,
            fontSize: 16,
            lineHeight: 1,
            width: 18,
            textAlign: 'center',
          }}
        >
          {glyph}
        </span>
        <span
          className="mono"
          style={{
            color: 'var(--fg-4)',
            fontSize: 9,
            letterSpacing: '.18em',
            width: 28,
          }}
        >
          STEP {s.n}
        </span>
        <span
          className="mono"
          style={{
            color: 'var(--fg-2)',
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: '.06em',
            flex: 1,
          }}
        >
          {s.title}
        </span>
        <Chip kind={chipKind}>{s.result.toUpperCase()}</Chip>
      </div>
      <div
        className="mono"
        style={{
          marginLeft: 56,
          fontSize: 10,
          color: 'var(--fg-3)',
          letterSpacing: '.06em',
        }}
      >
        {s.detail}
        {s.cta && (
          <Link
            to={s.cta.href}
            className="btn"
            style={{
              marginLeft: 10,
              padding: '2px 8px',
              fontSize: 9,
              letterSpacing: '.14em',
              textDecoration: 'none',
            }}
          >
            {s.cta.label} →
          </Link>
        )}
      </div>
    </li>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────

const loadingStyle = {
  padding: 24,
  textAlign: 'center' as const,
  fontSize: 11,
  color: 'var(--fg-4)',
  letterSpacing: '.16em',
};

const errStripStyle = {
  marginBottom: 12,
  padding: '8px 12px',
  border: '1px solid var(--amber-border)',
  borderRadius: 4,
  background: 'var(--amber-bg)',
  fontSize: 9,
  color: 'var(--amber-2)',
  letterSpacing: '.08em',
};

const stepRowStyle = {
  padding: '10px 0',
  borderBottom: '1px dashed var(--border-soft)',
};

export default DiagnoseWizard;
