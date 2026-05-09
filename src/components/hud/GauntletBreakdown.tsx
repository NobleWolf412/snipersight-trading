/**
 * GauntletBreakdown — HUD port (Phase 3g.ii.b)
 *
 * Supersedes `src/components/bot/GauntletBreakdown.tsx`. Merges:
 *   - Real-data binding from the prior Tailwind component: every signal in
 *     `signal_log[]` is mapped to its exact gauntlet stage via
 *     `classifyStage()`, which prefers the machine-readable `reason_type`
 *     and falls back to substring matching on `reason`. The classification
 *     rules are unchanged from the prior component (see CHECKER block).
 *   - HUD chrome from `prototype/gauntlet.jsx`: 3-column funnel (PRE-SCORE
 *     / POST-SCORE / EXECUTION), per-stage filter click, bottleneck-insight
 *     pill with action-map CTAs, DETAIL toggle revealing the per-signal
 *     table.
 *
 * Real-data wiring:
 *   - Sole input is `signals: SignalLogEntry[]` from
 *     `liveTradingService.getStatus().signal_log`. No mock data path. When
 *     `signals.length === 0` the empty-state renders with a `◌ awaiting`
 *     chip — caller may also choose not to mount the panel at all.
 *
 * Synthetic-but-disclosed: none.
 *
 * Per-row drilldown:
 *   - Detail rows are clickable when an `onSignalClick` callback is
 *     supplied AND the row's `id` field is non-empty. The callback
 *     receives the stable signal id; the parent typically opens
 *     `<PipelineTracer />` with it. Older signal_log entries lacking the
 *     `id` field fall back to a non-interactive row.
 *
 * Mode-delta strip (Phase 3g.ii.g):
 *   - When the bottleneck is CONFLUENCE and the caller supplies
 *     `scannerModes` + `currentModeName`, a small strip under the pill
 *     reports for each *other* mode: "switching to STRIKE (≥62) would
 *     have unblocked 14 of 18". Computed client-side by comparing each
 *     CONFLUENCE-rejected signal's `confluence` score against each
 *     other mode's `min_confluence_score`. Direction-agnostic by design
 *     — confluence scoring is symmetric across long/short (see
 *     CLAUDE.md §10 #3).
 *
 * Deferred to later 3g.ii sub-steps:
 *   - ConfluenceFactorList embed inside expanded CONFLUENCE rows
 *     (3g.ii.d).
 *
 * Determinism for snapshots:
 *   - Times are formatted from the ISO `Z` slice directly (HH:MM:SS,
 *     UTC). No `toLocaleTimeString` (locale-dependent). No `Date.now`.
 *
 * Plan reference: peppy-sniffing-owl §3e (Bot · GauntletBreakdown).
 */
import { useMemo, useState } from 'react';
import type { ScannerMode, SignalLogEntry } from '@/utils/api';
import { Chip, SectionHead } from '@/components/hud';

// ─── Stage taxonomy (unchanged from prior component) ───────────────────

export type GauntletStage =
  // pre-scoring hard gates
  | 'NO_DATA'
  | 'MISSING_TF'
  | 'STRUCTURAL_ANCHOR'
  | 'REGIME_ALIGNMENT'
  | 'BTC_IMPULSE'
  | 'CONFLICT_DENSITY'
  | 'COOLDOWN'
  // post-scoring / planner
  | 'CONFLUENCE'
  | 'NO_TRADE_PLAN'
  | 'RISK_VALIDATION'
  | 'ML_GATE'
  // execution
  | 'REGIME_VETO'
  | 'MAX_POSITIONS'
  | 'HAS_POSITION'
  | 'PENDING_ORDER'
  | 'POSITION_SIZE'
  | 'PULLBACK_PROB'
  | 'PRICE_FETCH'
  | 'EXEC_ERROR'
  | 'PENDING_FILL'
  | 'EXECUTED'
  | 'UNKNOWN';

type StageGroup = 'PRE-SCORE' | 'POST-SCORE' | 'EXECUTION';

interface StageMeta {
  group: StageGroup;
  label: string;
  hint: string;
}

const STAGES: Record<GauntletStage, StageMeta> = {
  // PRE-SCORE
  NO_DATA:           { group: 'PRE-SCORE',  label: 'NO DATA',           hint: 'OHLCV missing for required TFs' },
  MISSING_TF:        { group: 'PRE-SCORE',  label: 'MISSING TF',        hint: 'Critical timeframe failed to load' },
  STRUCTURAL_ANCHOR: { group: 'PRE-SCORE',  label: 'STRUCTURAL ANCHOR', hint: 'No valid HTF anchor (BOS/CHoCH/OB)' },
  REGIME_ALIGNMENT:  { group: 'PRE-SCORE',  label: 'REGIME ALIGNMENT',  hint: 'Direction conflicts with macro regime' },
  BTC_IMPULSE:       { group: 'PRE-SCORE',  label: 'BTC IMPULSE',       hint: 'BTC moving against the trade' },
  CONFLICT_DENSITY:  { group: 'PRE-SCORE',  label: 'CONFLICT DENSITY',  hint: 'Too many opposing signals nearby' },
  COOLDOWN:          { group: 'PRE-SCORE',  label: 'COOLDOWN',          hint: 'Symbol just lost / recently rejected' },
  // POST-SCORE
  CONFLUENCE:        { group: 'POST-SCORE', label: 'CONFLUENCE',        hint: 'Score < mode min_confluence_score' },
  NO_TRADE_PLAN:     { group: 'POST-SCORE', label: 'NO TRADE PLAN',     hint: 'Planner couldn\u2019t build entry/stop/TP' },
  RISK_VALIDATION:   { group: 'POST-SCORE', label: 'RISK VALIDATION',   hint: 'R:R below min, or stops too wide/tight' },
  ML_GATE:           { group: 'POST-SCORE', label: 'ML GATE',           hint: 'Edge model said skip' },
  // EXECUTION
  REGIME_VETO:       { group: 'EXECUTION',  label: 'REGIME VETO',       hint: 'Late-stage regime check killed it' },
  MAX_POSITIONS:     { group: 'EXECUTION',  label: 'MAX POSITIONS',     hint: 'Already at concurrent-position cap' },
  HAS_POSITION:      { group: 'EXECUTION',  label: 'HAS POSITION',      hint: 'Already have a position on this symbol' },
  PENDING_ORDER:     { group: 'EXECUTION',  label: 'PENDING ORDER',     hint: 'Already have a pending order on this symbol' },
  POSITION_SIZE:     { group: 'EXECUTION',  label: 'POSITION SIZE',     hint: 'Sizing math returned zero / dust' },
  PULLBACK_PROB:     { group: 'EXECUTION',  label: 'PULLBACK PROB',     hint: 'Entry zone too far from price' },
  PRICE_FETCH:       { group: 'EXECUTION',  label: 'PRICE FETCH',       hint: 'Couldn\u2019t fetch current price' },
  EXEC_ERROR:        { group: 'EXECUTION',  label: 'EXEC ERROR',        hint: 'Exchange call failed' },
  PENDING_FILL:      { group: 'EXECUTION',  label: 'PENDING FILL',      hint: 'Order placed, waiting on fill' },
  EXECUTED:          { group: 'EXECUTION',  label: 'EXECUTED',          hint: 'Survived everything · position opened' },
  UNKNOWN:           { group: 'EXECUTION',  label: 'UNKNOWN',           hint: 'Reason string didn\u2019t match a known gate' },
};

const PRE_SCORE_STAGES: GauntletStage[] = [
  'NO_DATA', 'MISSING_TF', 'STRUCTURAL_ANCHOR', 'REGIME_ALIGNMENT',
  'BTC_IMPULSE', 'CONFLICT_DENSITY', 'COOLDOWN',
];
const POST_SCORE_STAGES: GauntletStage[] = [
  'CONFLUENCE', 'NO_TRADE_PLAN', 'RISK_VALIDATION', 'ML_GATE',
];
const EXECUTION_STAGES: GauntletStage[] = [
  'REGIME_VETO', 'MAX_POSITIONS', 'HAS_POSITION', 'PENDING_ORDER',
  'POSITION_SIZE', 'PULLBACK_PROB', 'PRICE_FETCH', 'EXEC_ERROR',
  'PENDING_FILL', 'EXECUTED',
];

// ─── Reason → stage classifier (lifted verbatim from prior component) ─

export function classifyStage(signal: SignalLogEntry): GauntletStage {
  if (signal.result === 'executed') return 'EXECUTED';
  if (signal.result === 'error') return 'EXEC_ERROR';

  const r = (signal.reason ?? '').toLowerCase();
  const rt = (signal.reason_type ?? '').toLowerCase();

  // PENDING_FILL — reason-based; the SignalLogEntry result enum doesn't
  // carry this terminal state directly.
  if (r.includes('waiting for limit fill') || (r.includes('pending') && r.includes('fill'))) {
    return 'PENDING_FILL';
  }

  // reason_type fast-path (preferred — machine-readable).
  if (rt === 'structural_anchor')   return 'STRUCTURAL_ANCHOR';
  if (rt === 'regime_alignment')    return 'REGIME_ALIGNMENT';
  if (rt === 'btc_impulse')         return 'BTC_IMPULSE';
  if (rt === 'conflict_density')    return 'CONFLICT_DENSITY';
  if (rt === 'cooldown_active')     return 'COOLDOWN';
  if (rt === 'missing_critical_tf') return 'MISSING_TF';
  if (rt === 'no_data')              return 'NO_DATA';
  if (rt === 'no_trade_plan')        return 'NO_TRADE_PLAN';
  if (rt === 'risk_validation')      return 'RISK_VALIDATION';
  if (rt === 'ml_gate')              return 'ML_GATE';
  if (rt === 'low_confluence')       return 'CONFLUENCE';
  if (rt === 'regime_veto')          return 'REGIME_VETO';
  if (rt === 'max_positions')        return 'MAX_POSITIONS';
  if (rt === 'has_position')         return 'HAS_POSITION';
  if (rt === 'pending_order')        return 'PENDING_ORDER';
  if (rt === 'position_size')        return 'POSITION_SIZE';
  if (rt === 'pullback_prob')        return 'PULLBACK_PROB';
  if (rt === 'price_fetch')          return 'PRICE_FETCH';
  if (rt === 'errors')               return 'EXEC_ERROR';

  // Fallback substring scan (older entries may lack reason_type).
  if (r.includes('structural anchor') || r.includes('quality structural')) return 'STRUCTURAL_ANCHOR';
  if (r.includes('regime is') || (r.includes('rejected') && r.includes('choch'))) return 'REGIME_ALIGNMENT';
  if (r.includes('btc in opposing') || r.includes('opposing strong impulse')) return 'BTC_IMPULSE';
  if (r.includes('simultaneous conflict') || r.includes('conflict conditions detected')) return 'CONFLICT_DENSITY';
  if (r.includes('stop-out') || r.includes('cooldown') || (r.includes('wait') && r.includes('h ago'))) return 'COOLDOWN';
  if (r.includes('missing critical timeframe') || r.includes('critical tf')) return 'MISSING_TF';
  if (r.includes('no market data') || r.includes('no data available')) return 'NO_DATA';
  if (r.includes('insufficient smc') || r.includes('no trade plan') || r.includes('no plan generated')) return 'NO_TRADE_PLAN';
  if (r.includes('revalidation failed') || r.includes('risk validation') || r.includes('post-plan')) return 'RISK_VALIDATION';
  if (r.includes('ml') && (r.includes('win prob') || r.includes('gate') || r.includes('model'))) return 'ML_GATE';
  if (r.includes('regime veto') || r.includes('extreme regime') || r.includes('chaotic')) return 'REGIME_VETO';
  if (r.includes('max position')) return 'MAX_POSITIONS';
  if (r.includes('already in position') || r.includes('position already')) return 'HAS_POSITION';
  if (r.includes('pending order') && (r.includes('equal') || r.includes('higher') || r.includes('exists'))) return 'PENDING_ORDER';
  if (r.includes('confluence') || r.includes('below min')) return 'CONFLUENCE';
  if (r.includes('invalid position size') || r.includes('position size')) return 'POSITION_SIZE';
  if (r.includes('pullback probability') || r.includes('low pullback')) return 'PULLBACK_PROB';
  if (r.includes('price fetch') || r.includes('no price') || r.includes('price is zero')) return 'PRICE_FETCH';

  return 'UNKNOWN';
}

// ─── Bottleneck derivation + action map ────────────────────────────────

type Action = { msg: string; cta: string; href: string };

const ACTION_MAP: Partial<Record<GauntletStage, Action>> = {
  CONFLUENCE: {
    msg: 'Confluence threshold may be too high for current conditions.',
    cta: 'Open Scanner modes',
    href: '/scanner',
  },
  REGIME_ALIGNMENT: {
    msg: 'Most signals fight the macro regime — direction bias is wrong.',
    cta: 'Review Intel',
    href: '/intel',
  },
  REGIME_VETO: {
    msg: 'Late-stage regime check is killing approved plans.',
    cta: 'Inspect regime',
    href: '/intel',
  },
  BTC_IMPULSE: {
    msg: 'BTC volatility is breaking signals before entry.',
    cta: 'Open Intel',
    href: '/intel',
  },
  RISK_VALIDATION: {
    msg: 'Plans don\u2019t meet R:R floor — stops or TPs need recalibrating.',
    cta: 'Tune risk params',
    href: '/bot/setup',
  },
  ML_GATE: {
    msg: 'Edge model is rejecting most signals — model may be stale.',
    cta: 'Retrain model',
    href: '/training',
  },
  MAX_POSITIONS: {
    msg: 'Concurrent-position cap is the bottleneck, not detection.',
    cta: 'Raise cap',
    href: '/bot/setup',
  },
  COOLDOWN: {
    msg: 'Cooldown filter eating most signals — recent loss streak.',
    cta: 'Review Journal',
    href: '/journal',
  },
  NO_TRADE_PLAN: {
    msg: 'Planner can\u2019t build valid plans — anchors may be too sparse.',
    cta: 'Tune planner',
    href: '/bot/setup',
  },
  STRUCTURAL_ANCHOR: {
    msg: 'No HTF anchors are forming — market is choppy.',
    cta: 'Wait for trend',
    href: '/intel',
  },
  EXEC_ERROR: {
    msg: 'Exchange is rejecting orders — check API keys / size precision.',
    cta: 'Open Settings',
    href: '/settings',
  },
};

function deriveBottleneck(counts: Record<GauntletStage, number>) {
  // Skip terminal / informational stages.
  const skip = new Set<GauntletStage>(['EXECUTED', 'PENDING_FILL', 'UNKNOWN']);
  let total = 0;
  let topId: GauntletStage | null = null;
  let topCount = 0;
  for (const id of Object.keys(counts) as GauntletStage[]) {
    if (skip.has(id)) continue;
    const c = counts[id] ?? 0;
    total += c;
    if (c > topCount) {
      topCount = c;
      topId = id;
    }
  }
  if (topId === null || topCount === 0 || total === 0) return null;
  const winner: GauntletStage = topId;
  const pct = Math.round((topCount / total) * 100);
  const action: Action = ACTION_MAP[winner] ?? {
    msg: 'Investigate this stage in DETAIL mode.',
    cta: 'View detail',
    href: '#',
  };
  return { id: winner, label: STAGES[winner].label, count: topCount, pct, ...action };
}

// ─── Time formatter — TZ-independent slice from ISO Z timestamp ─────────

function fmtTime(ts: string): string {
  // Inputs are ISO 8601 (e.g. "2026-05-09T09:42:00Z"). Slice positions
  // 11:19 yields HH:MM:SS in UTC without invoking the JS Date locale path,
  // which keeps snapshot output deterministic across runners.
  if (!ts || ts.length < 19) return '—';
  return ts.slice(11, 19);
}

// ─── Color helpers ────────────────────────────────────────────────────

function stageColor(id: GauntletStage, count: number): string {
  if (count === 0) return 'var(--fg-4)';
  if (id === 'EXECUTED') return 'var(--green-soft)';
  if (id === 'PENDING_FILL') return 'var(--amber-2)';
  return 'var(--red-2)';
}
function stageBg(id: GauntletStage, count: number): string {
  if (count === 0) return 'transparent';
  if (id === 'EXECUTED') return 'rgba(74,222,128,.12)';
  if (id === 'PENDING_FILL') return 'rgba(251,191,36,.10)';
  return 'rgba(248,113,113,.10)';
}

// ─── Component ────────────────────────────────────────────────────────

interface Props {
  signals: SignalLogEntry[];
  /**
   * Called when a detail row is clicked. Receives the stable signal id.
   * Wire to a PipelineTracer drawer to drill into the per-signal trace.
   * If omitted, rows are non-interactive (purely informational table).
   */
  onSignalClick?: (id: string) => void;
  /**
   * Scanner-mode catalog from `useScanner().scannerModes`. When supplied
   * AND the bottleneck stage is CONFLUENCE, the strip below the
   * bottleneck pill renders a per-mode delta showing how many of the
   * CONFLUENCE-rejected signals would have passed each *other* mode's
   * `min_confluence_score`. Omit to suppress the strip entirely.
   */
  scannerModes?: ScannerMode[];
  /** Active mode name (excluded from the delta strip — comparing X to X is noise). */
  currentModeName?: string | null;
}

interface ModeDelta {
  name: string;
  threshold: number;
  unblocked: number;
  total: number;
}

function computeModeDeltas(
  bottleneckSignals: SignalLogEntry[],
  scannerModes: ScannerMode[],
  currentModeName: string | null | undefined,
): ModeDelta[] {
  // §16 #3 mass conservation: every signal counted is part of `total`;
  // `unblocked <= total` per mode by construction. Negative tests
  // (signals.length === 0 or no scanner modes) return [] so the strip
  // does not render.
  if (bottleneckSignals.length === 0 || scannerModes.length === 0) return [];
  const total = bottleneckSignals.length;
  const cur = (currentModeName ?? '').toLowerCase();
  const out: ModeDelta[] = [];
  for (const m of scannerModes) {
    if (m.name.toLowerCase() === cur) continue;
    let unblocked = 0;
    for (const s of bottleneckSignals) {
      if (typeof s.confluence === 'number' && s.confluence >= m.min_confluence_score) {
        unblocked += 1;
      }
    }
    out.push({ name: m.name, threshold: m.min_confluence_score, unblocked, total });
  }
  // Sort descending by unblocked so the most-helpful alternative leads.
  // Tie-break by lower threshold (less restrictive ranks higher).
  out.sort((a, b) => b.unblocked - a.unblocked || a.threshold - b.threshold);
  return out;
}

export function GauntletBreakdown({ signals, onSignalClick, scannerModes, currentModeName }: Props) {
  const [detail, setDetail] = useState(false);
  const [filterStage, setFilterStage] = useState<GauntletStage | null>(null);

  const staged = useMemo(
    () => signals.map((s) => ({ ...s, stage: classifyStage(s) })),
    [signals],
  );

  const counts = useMemo(() => {
    const c = {} as Record<GauntletStage, number>;
    (Object.keys(STAGES) as GauntletStage[]).forEach((id) => { c[id] = 0; });
    staged.forEach((s) => { c[s.stage] = (c[s.stage] ?? 0) + 1; });
    return c;
  }, [staged]);

  const total = staged.length;
  const executed = counts.EXECUTED ?? 0;
  const conversion = total > 0 ? (executed / total) * 100 : 0;
  const bottleneck = useMemo(() => deriveBottleneck(counts), [counts]);
  const maxCount = Math.max(...Object.values(counts), 1);

  const filtered = filterStage ? staged.filter((s) => s.stage === filterStage) : staged;
  const visibleRows = detail || filterStage ? filtered : [];

  // Mode-delta strip: only meaningful when CONFLUENCE is the bottleneck.
  // Pass the actual rejected-at-CONFLUENCE signals (not all staged) so the
  // "would have unblocked N of M" math reflects the population the operator
  // would actually recover by switching mode.
  const modeDeltas = useMemo(() => {
    if (!bottleneck || bottleneck.id !== 'CONFLUENCE') return [];
    if (!scannerModes || scannerModes.length === 0) return [];
    const conflSignals = staged.filter((s) => s.stage === 'CONFLUENCE');
    return computeModeDeltas(conflSignals, scannerModes, currentModeName);
  }, [bottleneck, scannerModes, currentModeName, staged]);

  // ─── Empty state ──────────────────────────────────────────────────
  if (signals.length === 0) {
    return (
      <section className="panel" style={{ padding: 14 }}>
        <SectionHead title="Gauntlet Breakdown" right={<Chip kind="amber">{'\u25CC'} awaiting</Chip>} />
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
          — signal log empty · gauntlet has no candidates yet —
        </div>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="sec-head">
        <div className="sec-title"><span className="dot" /> Gauntlet Breakdown</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Chip>{`${total} CAND · ${executed} EXEC · ${conversion.toFixed(1)}%`}</Chip>
          <button
            type="button"
            className="btn"
            onClick={() => setDetail((d) => !d)}
            style={{ padding: '4px 10px', fontSize: 9, letterSpacing: '.18em' }}
          >
            {detail ? '\u25C9 DETAIL' : '\u25CB DETAIL'}
          </button>
        </div>
      </div>

      {/* Bottleneck insight pill ─────────────────────────────────── */}
      {bottleneck && (
        <div
          style={{
            margin: '14px 18px 0',
            padding: '10px 14px',
            border: '1px solid var(--amber-border)',
            borderRadius: 8,
            background: 'var(--amber-bg)',
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: 'var(--amber-2)', fontSize: 14 }}>{'\u26A0'}</span>
            <span
              className="mono"
              style={{ fontSize: 9, color: 'var(--amber-2)', letterSpacing: '.18em', fontWeight: 700 }}
            >
              BOTTLENECK
            </span>
            <span
              className="mono"
              style={{ fontSize: 11, color: 'var(--fg)', fontWeight: 700, letterSpacing: '.14em' }}
            >
              {bottleneck.label}
            </span>
            <span className="mono" style={{ fontSize: 10, color: 'var(--fg-3)' }}>
              · {bottleneck.count} signals · {bottleneck.pct}% of rejects
            </span>
          </div>
          <div style={{ flex: 1, minWidth: 200, fontSize: 11, color: 'var(--fg-2)', lineHeight: 1.4 }}>
            {bottleneck.msg}
          </div>
          <a
            href={`#${bottleneck.href}`}
            className="btn"
            style={{
              padding: '5px 12px',
              fontSize: 10,
              letterSpacing: '.16em',
              textDecoration: 'none',
              background: 'var(--amber-bg)',
              borderColor: 'var(--amber-border)',
              color: 'var(--amber-2)',
            }}
          >
            {bottleneck.cta} {'\u2192'}
          </a>
        </div>
      )}

      {/* Mode-delta strip — CONFLUENCE bottleneck only, requires scannerModes prop */}
      {modeDeltas.length > 0 && (
        <div
          style={{
            margin: '8px 18px 0',
            padding: '8px 14px',
            border: '1px dashed var(--amber-border)',
            borderRadius: 6,
            background: 'rgba(251,191,36,.04)',
          }}
        >
          <div
            className="mono"
            style={{
              fontSize: 9,
              color: 'var(--fg-4)',
              letterSpacing: '.18em',
              marginBottom: 6,
            }}
          >
            // MODE DELTA · would-pass count if you switched modes
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            {modeDeltas.map((d) => {
              const helpful = d.unblocked > 0;
              return (
                <div
                  key={d.name}
                  className="mono"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '3px 10px',
                    border: `1px solid ${helpful ? 'var(--amber-border)' : 'var(--border-soft)'}`,
                    borderRadius: 4,
                    background: helpful ? 'rgba(251,191,36,.08)' : 'transparent',
                    fontSize: 10,
                    letterSpacing: '.10em',
                  }}
                >
                  <span style={{ color: 'var(--fg-2)', fontWeight: 700 }}>
                    {d.name.toUpperCase()}
                  </span>
                  <span style={{ color: 'var(--fg-4)' }}>
                    ({'\u2265'}{d.threshold.toFixed(0)})
                  </span>
                  <span
                    style={{
                      color: helpful ? 'var(--amber-2)' : 'var(--fg-4)',
                      fontWeight: 700,
                    }}
                  >
                    {d.unblocked} / {d.total}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Funnel grid ────────────────────────────────────────────── */}
      <div
        style={{
          padding: '14px 18px',
          display: 'grid',
          gridTemplateColumns: detail ? '1fr' : '1fr 1fr 1fr',
          gap: 18,
        }}
      >
        {(['PRE-SCORE', 'POST-SCORE', 'EXECUTION'] as StageGroup[]).map((g) => {
          const ids =
            g === 'PRE-SCORE' ? PRE_SCORE_STAGES :
            g === 'POST-SCORE' ? POST_SCORE_STAGES : EXECUTION_STAGES;
          const groupHint =
            g === 'PRE-SCORE' ? 'cheap rejects' :
            g === 'POST-SCORE' ? 'after confluence math' : 'execution layer';
          return (
            <div key={g}>
              <div
                className="mono"
                style={{
                  fontSize: 9,
                  color: 'var(--fg-4)',
                  letterSpacing: '.20em',
                  marginBottom: 8,
                  paddingBottom: 6,
                  borderBottom: '1px dashed var(--border-soft)',
                }}
              >
                // {g} · {groupHint}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: detail ? 2 : 3 }}>
                {ids.map((id) => {
                  const c = counts[id] ?? 0;
                  const w = (c / maxCount) * 100;
                  const sel = filterStage === id;
                  return (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setFilterStage(sel ? null : id)}
                      title={STAGES[id].hint}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: detail ? '160px 1fr 50px' : '130px 1fr 32px',
                        gap: 8,
                        alignItems: 'center',
                        padding: '5px 8px',
                        borderRadius: 4,
                        cursor: 'pointer',
                        background: sel ? 'rgba(255,255,255,.04)' : 'transparent',
                        border: sel ? '1px solid var(--accent-border)' : '1px solid transparent',
                        textAlign: 'left',
                        font: 'inherit',
                        color: 'inherit',
                      }}
                    >
                      <span
                        className="mono"
                        style={{
                          fontSize: 9,
                          color: c === 0 ? 'var(--fg-4)' : 'var(--fg-2)',
                          letterSpacing: '.10em',
                          fontWeight: c > 0 ? 700 : 400,
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {STAGES[id].label}
                      </span>
                      <div
                        style={{
                          height: detail ? 16 : 12,
                          background: 'rgba(0,0,0,.35)',
                          borderRadius: 2,
                          position: 'relative',
                          overflow: 'hidden',
                          border: '1px solid var(--border-soft)',
                        }}
                      >
                        <div
                          style={{
                            position: 'absolute',
                            left: 0,
                            top: 0,
                            bottom: 0,
                            width: `${w}%`,
                            background: stageBg(id, c),
                            borderRight: c > 0 ? `2px solid ${stageColor(id, c)}` : 'none',
                          }}
                        />
                      </div>
                      <span
                        className="mono"
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          color: stageColor(id, c),
                          textAlign: 'right',
                          letterSpacing: '.06em',
                        }}
                      >
                        {c}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Detail rows — visible when DETAIL toggle on, OR when filtering ─ */}
      {(detail || filterStage) && (
        <div style={{ padding: '0 18px 18px' }}>
          <div style={{ paddingTop: 10, borderTop: '1px dashed var(--border-soft)' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 10,
              }}
            >
              <span
                className="mono"
                style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.20em' }}
              >
                // {filterStage ? `STAGE: ${filterStage}` : 'ALL SIGNALS'} · {visibleRows.length} ROWS
              </span>
              {filterStage && (
                <button
                  type="button"
                  className="btn"
                  onClick={() => setFilterStage(null)}
                  style={{ padding: '3px 10px', fontSize: 9, letterSpacing: '.16em' }}
                >
                  {'\u00D7'} CLEAR FILTER
                </button>
              )}
            </div>
            <table className="mono" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr
                  style={{
                    textAlign: 'left',
                    color: 'var(--fg-4)',
                    fontSize: 9,
                    letterSpacing: '.18em',
                    textTransform: 'uppercase',
                  }}
                >
                  <th style={{ padding: '4px 0' }}>Time</th>
                  <th>Symbol</th>
                  <th>TF</th>
                  <th>Side</th>
                  <th>Score</th>
                  <th>Stage</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {visibleRows.slice().reverse().map((s, i) => {
                  const c = stageColor(s.stage, 1);
                  const score = Number.isFinite(s.confluence) && s.confluence > 0 ? s.confluence : null;
                  const thr = s.threshold ?? null;
                  const clickable = Boolean(onSignalClick && s.id);
                  return (
                    <tr
                      key={`${s.symbol}-${s.timestamp}-${i}`}
                      onClick={clickable && s.id ? () => onSignalClick!(s.id!) : undefined}
                      style={{
                        borderTop: '1px dashed var(--border-soft)',
                        cursor: clickable ? 'pointer' : 'default',
                      }}
                      title={clickable ? 'Open pipeline tracer' : undefined}
                    >
                      <td style={{ padding: '6px 0', color: 'var(--fg-4)', fontSize: 10 }}>
                        {fmtTime(s.timestamp)}
                      </td>
                      <td style={{ fontWeight: 700 }}>{s.symbol}</td>
                      <td style={{ color: 'var(--fg-3)' }}>{s.timeframe ?? '—'}</td>
                      <td
                        style={{
                          color: s.direction === 'LONG' ? 'var(--green-soft)' : 'var(--red-2)',
                          fontWeight: 700,
                          fontSize: 10,
                          letterSpacing: '.12em',
                        }}
                      >
                        {s.direction}
                      </td>
                      <td
                        style={{
                          color:
                            score == null
                              ? 'var(--fg-4)'
                              : thr != null && score >= thr
                                ? 'var(--green-soft)'
                                : 'var(--red-2)',
                        }}
                      >
                        {score == null ? '—' : thr != null ? `${score.toFixed(1)} / ${thr.toFixed(1)}` : score.toFixed(1)}
                      </td>
                      <td>
                        <span
                          style={{
                            color: c,
                            fontWeight: 700,
                            fontSize: 9,
                            letterSpacing: '.14em',
                            padding: '2px 8px',
                            border: `1px solid ${c}`,
                            borderRadius: 3,
                            background: stageBg(s.stage, 1),
                          }}
                        >
                          {s.stage}
                        </span>
                      </td>
                      <td style={{ color: 'var(--fg-3)', fontSize: 10 }}>
                        {s.reason || s.setup_type || '—'}
                      </td>
                    </tr>
                  );
                })}
                {visibleRows.length === 0 && (
                  <tr>
                    <td
                      colSpan={7}
                      style={{
                        textAlign: 'center',
                        padding: '20px 0',
                        color: 'var(--fg-4)',
                        fontSize: 11,
                        letterSpacing: '.16em',
                      }}
                    >
                      // no signals at this stage
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

export default GauntletBreakdown;
