import { ScannerInputs } from '@/components/hud/ScannerInputs';
/** Manual scanner: application-owned runs, recorded history and explicit evidence.
 * Chart review overlays saved plan levels on source-specific candles; radar is decorative.
 * The selected history receipt owns result counts, timestamps and setup summaries.
 */
import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import {
  Chip,
  CooldownsTile,
  FooterStatus,
  MacroScoreTile,
  PageHead,
  RejectionPanel,
  Reticle,
  ScanController,
  ScannerModePicker,
  SectionHead,
  fmtPrice,
} from '@/components/hud';
import { readScore, readDirection, validScore, passesAdmission, admissionLabel, formatScore } from '@/utils/scoreEvidence';
import { useScanner } from '@/context/ScannerContext';
import { scanHistoryService, type ScanHistoryEntry } from '@/services/scanHistoryService';
import { buildSetupChartPlan, formatSetupPrice, type SetupChartPlan } from '@/services/scannerSetup';
import './Scanner.css';

const ScannerSetupModal = lazy(() => import('@/components/ScannerSetupModal').then(module => ({ default: module.ScannerSetupModal })));

// Categories contain only producer evidence; unavailable is selectable.
const SETUPS = ['OB+FVG', 'BOS', 'CHoCH', 'LIQ-SWEEP', 'OB-RETEST', 'FVG-FILL', 'BREAKER', 'SMC', 'UNKNOWN'] as const;
const TFS = ['1m', '5m', '15m', '1h', '4h', '1D', '1W', 'UNKNOWN'] as const;
const REGIMES = ['TREND', 'RANGE', 'CHOP', 'UNKNOWN'] as const;

type Setup = (typeof SETUPS)[number];
type Tf = (typeof TFS)[number];
type Regime = (typeof REGIMES)[number];
type Direction = 'LONG' | 'SHORT';

type TradeType = 'SWING' | 'INTRADAY' | 'SCALP';

interface CardSignal {
  id: string;
  sym: string;
  dir: Direction;
  setup: Setup;
  score: number | undefined;
  scoreGate: number | undefined;
  scoreGatePassed?: boolean;
  evidenceEligible?: boolean;
  admissionPassed?: boolean;
  evidenceMissing?: string[];
  scoreModelVersion?: string;
  scorePolicyVersion?: string;
  tf: Tf;
  regime: Regime;
  mark: number;
  entry: number;
  sl: number;
  tp1: number;
  tp2: number;
  rr: number;
  age: number;
  rationale?: string;
  raw?: unknown;
  chartPlan: SetupChartPlan;
  // tradeType: backend-emitted scale classification (SWING/INTRADAY/SCALP).
  // Sourced from the scan-history result's `classification` (already produced
  // by convertSignalToScanResult), with `trade_type` and `setup_type` accepted
  // as backend-format fallbacks. Undefined when history predates the field
  // or the upstream pipeline didn't emit one.
  tradeType?: TradeType;
  // Convergence/conflict (plan §3d P1) — green sliver = synergy_bonus,
  // red sliver = conflict_penalty. Both pulled directly from the
  // scan-history `confluence_breakdown` (already passed through by
  // convertSignalToScanResult). Numbers, not percentages — the renderer
  // scales to a fixed visual range so a typical score's bonus/penalty
  // surface without burying lower-impact factors.
  synergyBonus?: number;
  conflictPenalty?: number;
}

// Normalize any of the backend-format trade-type aliases to the upper-case
// frontend enum. Returns undefined when the input is missing/unrecognized so
// the card can render a placeholder rather than a misleading chip.
function normalizeTradeType(raw: unknown): TradeType | undefined {
  if (typeof raw !== 'string') return undefined;
  const v = raw.trim().toUpperCase();
  if (v === 'SWING' || v === 'INTRADAY' || v === 'SCALP') return v;
  return undefined;
}

// ─── Convergence/Conflict Mini-Bar (plan §3d P1) ─────────────────────────
// Two-segment horizontal bar surfacing the additive components of the
// confluence score: green = synergy_bonus (factor convergence), red =
// conflict_penalty (factor opposition). Width is proportional with a
// fixed visual scale (each unit = 1.4px, capped at 28px per side) so a
// typical 0–20 range reads well without one side dwarfing the other.
// Renders nothing when both values are absent — preserves card height.

const CC_BAR_PX_PER_UNIT = 1.4;
const CC_BAR_MAX_PX = 28;

function ConvergenceConflictBar({
  synergy,
  conflict,
}: {
  synergy?: number;
  conflict?: number;
}) {
  const hasSyn = typeof synergy === 'number' && synergy > 0;
  const hasCon = typeof conflict === 'number' && conflict > 0;
  if (!hasSyn && !hasCon) return null;
  const synW = hasSyn
    ? Math.min(CC_BAR_MAX_PX, Math.max(2, synergy! * CC_BAR_PX_PER_UNIT))
    : 0;
  const conW = hasCon
    ? Math.min(CC_BAR_MAX_PX, Math.max(2, conflict! * CC_BAR_PX_PER_UNIT))
    : 0;
  return (
    <div
      title={`synergy +${(synergy ?? 0).toFixed(1)} · conflict -${(conflict ?? 0).toFixed(1)}`}
      style={{
        display: 'inline-flex',
        gap: 2,
        marginTop: 4,
        height: 4,
        justifyContent: 'flex-end',
      }}
    >
      {hasSyn && (
        <span
          style={{
            width: synW,
            height: '100%',
            background: 'var(--green-soft, #4ade80)',
            borderRadius: 1,
            opacity: 0.85,
          }}
        />
      )}
      {hasCon && (
        <span
          style={{
            width: conW,
            height: '100%',
            background: 'var(--red-2, #f87171)',
            borderRadius: 1,
            opacity: 0.85,
          }}
        />
      )}
    </div>
  );
}

// ─── Signal Card ─────────────────────────────────────────────────────────

export function SignalCard({ sig }: { sig: CardSignal }) {
  const [chartOpen, setChartOpen] = useState(false);
  const isLong = sig.dir === 'LONG';
  const confCol = 'var(--fg-2)';
  const setupKind: 'blue' | 'purple' | 'amber' | undefined = sig.setup.includes('FVG')
    ? 'blue'
    : sig.setup.includes('BOS') || sig.setup.includes('CHoCH')
      ? 'purple'
      : sig.setup.includes('LIQ')
        ? 'amber'
        : undefined;
  return (
    <div className="pos brackets scanner-signal-card">
      <div className="scanner-signal-meta">
        {sig.tf} · {Number.isFinite(sig.age) ? `${sig.age}m ago at page load` : 'time unavailable'}
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
          marginBottom: 10,
          marginTop: 4,
          flexWrap: 'wrap',
        }}
      >
        <div className="scanner-signal-title">
          <Chip kind={isLong ? 'green' : 'red'}>
            {isLong ? '▲' : '▼'} {sig.dir}
          </Chip>
          <span
            style={{
              fontFamily: 'Share Tech Mono,monospace',
              fontSize: 16,
              letterSpacing: '.06em',
            }}
          >
            {sig.sym}
          </span>
          <Chip kind={setupKind} style={{ fontSize: 9 }}>
            {sig.setup}
          </Chip>
        </div>
        <div style={{ textAlign: 'right' }} title={[
          sig.scoreModelVersion && `Score model: ${sig.scoreModelVersion}`,
          sig.scorePolicyVersion && `Score policy: ${sig.scorePolicyVersion}`,
        ].filter(Boolean).join(' · ')}>
          <div
            className="mono"
            style={{ fontSize: 18, fontWeight: 800, color: confCol, lineHeight: 1 }}
          >
            {formatScore(sig.score)}
          </div>
          <div className="mono" style={{ fontSize: 8, color: confCol, letterSpacing: '.18em' }}>
            {sig.score === undefined ? 'SCORE UNAVAILABLE' : 'SCORE /100'}
          </div>
          {(sig.evidenceEligible !== undefined || sig.admissionPassed !== undefined) && (
            <div className="mono" title={sig.evidenceMissing?.join(' · ')}
              style={{ fontSize: 8, marginTop: 4, color: passesAdmission(sig) ? 'var(--green-soft)' : 'var(--amber-2)' }}>
              {admissionLabel(sig)}
            </div>
          )}
          <ConvergenceConflictBar
            synergy={sig.synergyBonus}
            conflict={sig.conflictPenalty}
          />
        </div>
      </div>
      <div className="scanner-signal-metrics">
        <div className="metric-tile">
          <div className="metric-label">Entry</div>
          <div className="metric-value" style={{ fontSize: 12 }}>
            {Number.isFinite(sig.entry) ? formatSetupPrice(sig.entry) : '—'}
          </div>
        </div>
        <div className="metric-tile">
          <div className="metric-label">Stop</div>
          <div className="metric-value" style={{ fontSize: 12, color: 'var(--red-2)' }}>
            {Number.isFinite(sig.sl) ? formatSetupPrice(sig.sl) : '—'}
          </div>
        </div>
        <div className="metric-tile">
          <div className="metric-label">TP1</div>
          <div className="metric-value" style={{ fontSize: 12, color: 'var(--green-soft)' }}>
            {Number.isFinite(sig.tp1) ? formatSetupPrice(sig.tp1) : '—'}
          </div>
        </div>
        <div className="metric-tile">
          <div className="metric-label">R:R</div>
          <div className="metric-value" style={{ fontSize: 12, color: 'var(--accent)' }}>
            {Number.isFinite(sig.rr) ? `${sig.rr.toFixed(1)}:1` : '—'}
          </div>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
        <Chip
          kind={sig.regime === 'TREND' ? 'green' : sig.regime === 'RANGE' ? 'amber' : 'red'}
          style={{ fontSize: 9 }}
        >
          {sig.regime}
        </Chip>
        {/* Trade-type chip — sourced from scan-history `classification`
            (or `trade_type`/`setup_type` fallback). Color maps to scale:
            SWING=blue (multi-day), INTRADAY=cyan (mid-tempo), SCALP=amber
            (fast). Falls back to amber `◌ —` placeholder when the upstream
            entry predates the field — preserves the prior visual width. */}
        {sig.tradeType ? (
          <Chip
            kind={
              sig.tradeType === 'SWING'
                ? 'blue'
                : sig.tradeType === 'INTRADAY'
                  ? 'cyan'
                  : 'amber'
            }
            style={{ fontSize: 9 }}
          >
            {sig.tradeType}
          </Chip>
        ) : (
          <Chip kind="amber" style={{ fontSize: 9 }}>
            ◌ —
          </Chip>
        )}
        <span style={{ flex: 1 }} />
        <button className="btn btn-green scanner-review-button" aria-haspopup="dialog" onClick={() => setChartOpen(true)}>
          REVIEW SETUP · CHART
        </button>
      </div>
      {chartOpen && <Suspense fallback={<p role="status">Opening setup chart…</p>}>
        <ScannerSetupModal plan={sig.chartPlan} symbol={sig.sym} direction={sig.dir}
          rationale={sig.rationale} onClose={() => setChartOpen(false)} />
      </Suspense>}
    </div>
  );
}

// ─── Filter Rail ─────────────────────────────────────────────────────────

interface Filters {
  minScore: number;
  dir: 'ALL' | Direction;
  tfs: Tf[];
  setups: Setup[];
  regimes: Regime[];
}

function FilterRail({
  filters,
  setFilters,
  counts,
  modeTfs,
}: {
  filters: Filters;
  setFilters: (f: Filters) => void;
  counts: { passing: number; total: number };
  // 3a''-A: TF set the active scanner mode actually scans. Chips for TFs
  // not in this set render dimmed + show a tooltip explaining that
  // selecting them does nothing because no signals at that TF will ever
  // be emitted. Empty array means "no mode loaded yet" — chips render
  // enabled but neutral.
  modeTfs: readonly string[];
}) {
  const upd = <K extends keyof Filters>(k: K, v: Filters[K]) => setFilters({ ...filters, [k]: v });
  const toggle = <K extends 'tfs' | 'setups' | 'regimes'>(k: K, v: Filters[K][number]) => {
    const arr = filters[k] as readonly string[];
    const next = arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v];
    setFilters({ ...filters, [k]: next as Filters[K] });
  };
  // Normalize mode TFs to the casing the FilterRail buttons use (1M / 5M /
  // 15M / 1H / 4H / 1D). Backend mode definitions emit lowercase ("1m",
  // "5m", "15m", "1h", "4h", "1d") — we uppercase here so the includes
  // check matches the TFS array's chip labels.
  const modeTfSet = useMemo(
    () => new Set(modeTfs.map((t) => t.toUpperCase())),
    [modeTfs],
  );
  return (
    <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* 3a''-C: filter scope label. Single line above the rail killing
          the implicit assumption that filtering = additional scanning.
          Sits at the top so it sets context before any control. */}
      <div
        className="mono"
        style={{
          fontSize: 9,
          color: 'var(--fg-3)',
          letterSpacing: '.16em',
          textTransform: 'uppercase',
          lineHeight: 1.5,
          padding: '6px 8px',
          background: 'rgba(0,0,0,.35)',
          border: '1px solid var(--border-soft)',
          borderRadius: 3,
        }}
        title="Filters narrow what's already been scanned. Scanning itself is controlled by the mode picker + ▶ run scan above."
      >
        // narrow displayed signals · scanning is controlled by mode above
      </div>
      <div>
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
          {/* 3a''-B: score scale is 0–100 to match the backend
              min_confluence_score (mode badge reads ≥ 70 etc). Pre-3a''
              this read 0–10 and silently never gated anything because
              backend scores arrive on a 0–100 scale. */}
          // MIN SCORE · {Math.round(filters.minScore)}
        </div>
        <input
          type="range"
          min="0"
          max="100"
          step="1"
          value={filters.minScore}
          onChange={(e) => upd('minScore', +e.target.value)}
          style={{ width: '100%' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
          <span className="mono" style={{ fontSize: 9, color: 'var(--fg-4)' }}>
            0
          </span>
          <span className="mono" style={{ fontSize: 9, color: 'var(--accent)' }}>
            ≥ {Math.round(filters.minScore)}
          </span>
          <span className="mono" style={{ fontSize: 9, color: 'var(--fg-4)' }}>
            100
          </span>
        </div>
      </div>
      <div>
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
          // DIRECTION
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {(['ALL', 'LONG', 'SHORT'] as const).map((d) => {
            const active = filters.dir === d;
            const cls = active ? (d === 'LONG' ? 'btn-green' : d === 'SHORT' ? 'btn-red' : 'btn-cyan') : '';
            return (
              <button
                key={d}
                className={`btn ${cls}`}
                style={{ padding: '6px 10px', fontSize: 10, flex: 1 }}
                onClick={() => upd('dir', d)}
              >
                {d}
              </button>
            );
          })}
        </div>
      </div>
      <div>
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
          {/* 3a''-A: TF chips dim when the active scanner mode doesn't
              scan them — the backend never emits signals at those TFs
              so selecting them in the filter does nothing. modeTfSet is
              built from selectedMode.timeframes at render time; empty
              set (no mode loaded) leaves everything enabled (neutral). */}
          // TIMEFRAME
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 6 }}>
          {TFS.map((tf) => {
            const active = filters.tfs.includes(tf);
            const inMode = tf === 'UNKNOWN' || modeTfSet.size === 0 || modeTfSet.has(tf.toUpperCase());
            return (
              <button
                key={tf}
                className={`btn ${active ? 'btn-cyan' : ''}`}
                style={{
                  padding: '6px 10px',
                  fontSize: 10,
                  opacity: inMode ? 1 : 0.4,
                  cursor: inMode ? 'pointer' : 'help',
                }}
                title={
                  inMode
                    ? undefined
                    : `not scanned by current mode — no signals will ever appear at ${tf}`
                }
                onClick={() => toggle('tfs', tf)}
              >
                {tf}
              </button>
            );
          })}
        </div>
      </div>
      <div>
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
          // SETUP <span style={{ color: 'var(--amber)' }}>◌</span>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {SETUPS.map((s) => {
            const active = filters.setups.includes(s);
            return (
              <button
                key={s}
                className={`btn ${active ? 'btn-cyan' : ''}`}
                style={{ padding: '5px 9px', fontSize: 9 }}
                onClick={() => toggle('setups', s)}
              >
                {s}
              </button>
            );
          })}
        </div>
      </div>
      <div>
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
          // REGIME
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {REGIMES.map((r) => {
            const active = filters.regimes.includes(r);
            const kind = r === 'TREND' ? 'btn-green' : r === 'RANGE' ? 'btn-cyan' : 'btn-red';
            return (
              <button
                key={r}
                className={`btn ${active ? kind : ''}`}
                style={{ padding: '6px 10px', fontSize: 10, flex: 1 }}
                onClick={() => toggle('regimes', r)}
              >
                {r}
              </button>
            );
          })}
        </div>
      </div>
      <div
        style={{
          paddingTop: 12,
          borderTop: '1px solid var(--border-soft)',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span
            className="mono"
            style={{
              fontSize: 10,
              color: 'var(--fg-4)',
              letterSpacing: '.18em',
              textTransform: 'uppercase',
            }}
          >
            passing
          </span>
          <span
            className="mono"
            style={{ fontSize: 11, color: 'var(--accent)', fontWeight: 700 }}
          >
            {counts.passing} / {counts.total}
          </span>
        </div>
        <button
          className="btn"
          style={{ padding: '8px', fontSize: 10 }}
          onClick={() =>
            setFilters({
              minScore: 0,
              dir: 'ALL',
              tfs: [...TFS],
              setups: [...SETUPS],
              regimes: [...REGIMES],
            })
          }
        >
          RESET FILTERS
        </button>
      </div>
    </div>
  );
}

// ─── Radar (synthetic — placement derived from card index) ───────────────

function ScannerRadar({ signals }: { signals: CardSignal[] }) {
  return (
    <div className="radar-wrap" style={{ aspectRatio: '1 / 1', position: 'relative' }}>
      <svg viewBox="-100 -100 200 200" style={{ width: '100%', height: '100%' }}>
        <defs>
          <linearGradient id="sweep2" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity=".5" />
          </linearGradient>
        </defs>
        {[30, 55, 80].map((r) => (
          <circle
            key={r}
            r={r}
            fill="none"
            stroke="var(--accent)"
            strokeOpacity=".18"
            strokeWidth=".4"
          />
        ))}
        <line
          x1="-90"
          y1="0"
          x2="90"
          y2="0"
          stroke="var(--accent)"
          strokeOpacity=".15"
          strokeWidth=".4"
        />
        <line
          x1="0"
          y1="-90"
          x2="0"
          y2="90"
          stroke="var(--accent)"
          strokeOpacity=".15"
          strokeWidth=".4"
        />
        {/* Static sweep wedge — no animation. */}
        <path d="M 0 0 L 88 0 A 88 88 0 0 0 67 -57 Z" fill="url(#sweep2)" />
        <line
          x1="0"
          y1="0"
          x2="88"
          y2="0"
          stroke="var(--accent)"
          strokeOpacity=".55"
          strokeWidth=".6"
        />
        {signals.slice(0, 12).map((s, i) => {
          const angle = (i / 12) * Math.PI * 2 - Math.PI / 2;
          const dist = 30 + (100 - (s.score ?? 0)) * 0.5;
          const x = Math.cos(angle) * dist,
            y = Math.sin(angle) * dist;
          const armed = passesAdmission(s);
          const color = s.dir === 'LONG' ? 'var(--green)' : 'var(--red-2)';
          return (
            <g key={s.id}>
              <circle cx={x} cy={y} r={armed ? 2.6 : 1.6} fill={color} />
              {armed && (
                <circle
                  cx={x}
                  cy={y}
                  r="6"
                  fill="none"
                  stroke={color}
                  strokeOpacity=".4"
                />
              )}
              <text
                x={x + 5}
                y={y - 3}
                fontFamily="JetBrains Mono,monospace"
                fontSize="6"
                fill={color}
                fontWeight="700"
              >
                {s.sym.split('/')[0]}
              </text>
            </g>
          );
        })}
        <circle r="3" fill="var(--accent)" />
      </svg>
    </div>
  );
}

// ─── Helpers: build CardSignals from scan history ────────────────────────

export function buildCardSignals(history: ScanHistoryEntry[]): CardSignal[] {
  const latest = history[0];
  if (!latest || !Array.isArray(latest.results) || latest.results.length === 0) return [];
  return latest.results.map((r: any, i: number): CardSignal | null => {
    const sym: string = r.pair ?? r.symbol ?? r.sym ?? 'UNKNOWN/USDT';
    const dir = readDirection(r);
    if (!dir) return null; // No directional evidence: do not invent a LONG.
    const category = <T extends string>(value: unknown, choices: readonly T[]): T =>
      choices.find(choice => choice.toUpperCase() === String(value ?? '').toUpperCase()) ?? ('UNKNOWN' as T);
    const price = (value: unknown) => typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : NaN;
    const entry: number = price(r.entryZone?.high ?? r.entry_near ?? r.entry ?? r.entry_price);
    const sl: number = price(r.stopLoss ?? r.stop_loss?.level ?? r.stop_loss ?? r.sl);
    const tp1: number = price(r.takeProfits?.[0] ?? r.targets?.[0]?.level ?? r.tp1);
    const tp2: number = price(r.takeProfits?.[1] ?? r.targets?.[1]?.level ?? r.tp2);
    const score = readScore(r);
    const scoreMetadata = r.confluence_breakdown?.metadata ?? r.metadata ?? {};
    const scoreGate = validScore(scoreMetadata.score_gate ?? latest.effectiveMinScore);
    const scoreGatePassed = scoreMetadata.score_gate_passed;
    const rr: number = price(r.riskReward ?? r.rr ?? r.risk_reward);
    const mark: number = Number(r.mark ?? r.mark_price ?? entry);
    const id: string = String(r.id ?? `card_${i}`);
    // Trade-type: prefer the convertSignalToScanResult-emitted `classification`
    // (already SWING/INTRADAY/SCALP). Fall back to raw backend fields for
    // history entries written by paths that bypass the converter.
    const tradeType = normalizeTradeType(r.classification ?? r.trade_type ?? r.setup_type);
    // Convergence/conflict — the breakdown object lives in two locations
    // depending on producer: top-level on raw backend signals, nested under
    // `confluence_breakdown` after convertSignalToScanResult. Read either.
    const cb = r.confluence_breakdown ?? r;
    const synergyBonus = typeof cb?.synergy_bonus === 'number' ? cb.synergy_bonus : undefined;
    const conflictPenalty = typeof cb?.conflict_penalty === 'number' ? cb.conflict_penalty : undefined;
    return {
      id,
      sym,
      dir,
      setup: category(r.setup_pattern ?? r.plan_type, SETUPS),
      score,
      scoreGate,
      scoreGatePassed: typeof scoreGatePassed === 'boolean' ? scoreGatePassed : undefined,
      evidenceEligible: typeof scoreMetadata.evidence_eligible === 'boolean' ? scoreMetadata.evidence_eligible : undefined,
      admissionPassed: typeof scoreMetadata.admission_passed === 'boolean' ? scoreMetadata.admission_passed : undefined,
      evidenceMissing: Array.isArray(scoreMetadata.evidence_missing)
        ? scoreMetadata.evidence_missing.filter((reason: unknown): reason is string => typeof reason === 'string') : undefined,
      scoreModelVersion: typeof scoreMetadata.score_model_version === 'string' ? scoreMetadata.score_model_version : undefined,
      scorePolicyVersion: typeof scoreMetadata.score_policy_version === 'string' ? scoreMetadata.score_policy_version : undefined,
      tf: category(r.timeframe, TFS),
      regime: category(r.regime?.symbol_regime?.trend === 'up' || r.regime?.symbol_regime?.trend === 'down' ? 'TREND' : r.regime?.symbol_regime?.trend === 'sideways' ? 'RANGE' : r.regime_label, REGIMES),
      mark,
      entry,
      sl,
      tp1,
      tp2,
      rr,
      age: Math.max(0, Math.floor((Date.now() - Date.parse(r.timestamp || latest.timestamp)) / 60000)),
      rationale: r.rationale, raw: r,
      chartPlan: buildSetupChartPlan(r, latest),
      tradeType,
      synergyBonus,
      conflictPenalty,
    };
  }).filter((signal): signal is CardSignal => signal !== null);
}

// ─── Main ────────────────────────────────────────────────────────────────

export function Scanner() {
  const { scannerModes, selectedMode } = useScanner();
  // Static now — no setInterval. Topbar drives UTC clock; this page does not.
  const [now] = useState(() => new Date());

  // Snapshot-ready handshake: StrictMode-safe pattern from Intel.tsx —
  // each mount sets, each cleanup unsets, final post-double-mount state
  // is set, which is what Playwright waits on.
  useEffect(() => {
    document.body.setAttribute('data-snapshot-ready', 'true');
    return () => {
      document.body.removeAttribute('data-snapshot-ready');
    };
  }, []);

  // Real signal source — scan history. Lifted to useState (was useMemo
  // pre-ScanController) so the controller can call `refreshCardSignals`
  // each time a fresh scan completes. Initial read still happens
  // synchronously to keep the snapshot capture deterministic.
  const [history, setHistory] = useState(() => scanHistoryService.getAllScans());
  const [cardSignals, setCardSignals] = useState<CardSignal[]>(() => {
    try {
      return buildCardSignals(scanHistoryService.getAllScans());
    } catch {
      return [];
    }
  });
  // 3a': latest history entry — feeds RejectionPanel. We track it as a
  // separate state from cardSignals so the panel can render the full
  // per-run rejection bundle (which buildCardSignals discards) without
  // forcing a service-layer refactor.
  const [latestHistoryEntry, setLatestHistoryEntry] = useState(() => {
    try {
      const all = scanHistoryService.getAllScans();
      return all.length > 0 ? all[0] : null;
    } catch {
      return null;
    }
  });
  const refreshCardSignals = useCallback(() => {
    try {
      const all = scanHistoryService.getAllScans();
      setHistory(all);
      setCardSignals(buildCardSignals(all));
      setLatestHistoryEntry(all.length > 0 ? all[0] : null);
    } catch (e) {
      // Re-read failure should not crash the page — log and keep the
      // current cards on screen.
      console.warn('[Scanner] refreshCardSignals failed:', e);
    }
  }, []);

  const [filters, setFilters] = useState<Filters>(() => ({
    minScore: 0,
    dir: 'ALL',
    tfs: [...TFS],
    setups: [...SETUPS],
    regimes: [...REGIMES],
  }));

  const filtered = useMemo(
    () =>
      cardSignals.filter((s) => {
        if (filters.minScore > 0 && (s.score === undefined || s.score < filters.minScore)) return false;
        if (filters.dir !== 'ALL' && s.dir !== filters.dir) return false;
        if (!filters.tfs.includes(s.tf)) return false;
        if (!filters.setups.includes(s.setup)) return false;
        if (!filters.regimes.includes(s.regime)) return false;
        return true;
      }),
    [cardSignals, filters],
  );

  const armedCount = filtered.filter(passesAdmission).length;
  const minScore = selectedMode?.min_confluence_score ?? 0;
  const modeName = (selectedMode?.name ?? '—').toUpperCase();
  const tfRoster = (selectedMode?.timeframes ?? []).join(' · ') || '—';

  return (
    <div className="page">
      <PageHead
        icon={
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="9" stroke="var(--amber-2)" strokeWidth="1.7" />
            <path
              d="M12 12 L20 6"
              stroke="var(--amber-2)"
              strokeWidth="1.7"
              strokeLinecap="round"
            />
            <circle cx="12" cy="12" r="3" stroke="var(--amber-2)" strokeWidth="1.2" />
            <path
              d="M12 4 L12 6 M12 18 L12 20 M4 12 L6 12 M18 12 L20 12"
              stroke="var(--amber-2)"
              strokeWidth="1.2"
            />
          </svg>
        }
        title="Scanner"
        subtitle={`real-time signal detection · ${scannerModes.length} modes · ${selectedMode?.timeframes.length ?? 0} timeframes`}
        badges={
          <>
            <Chip kind="blue">MODE · {modeName}</Chip>
            <Chip kind="green">{armedCount} ARMED</Chip>
            <Chip>≥ {minScore} SCORE</Chip>
          </>
        }
      />

      {/* Mode picker — drives ScannerContext.setSelectedMode ─────── */}
      {/* Scanner progress and diagnostics belong to the selected scan job. */}
      <ScannerModePicker />
      <ScannerInputs />
      <label style={{ display: 'block', margin: '16px 0' }}>Scan history{' '}
        <select value={latestHistoryEntry?.id ?? ''} onChange={e => {
          const entry = history.find(item => item.id === e.target.value);
          if (entry) { setLatestHistoryEntry(entry); setCardSignals(buildCardSignals([entry])); }
        }}>
          {!history.length && <option value="">No completed scans</option>}
          {history.map(entry => <option key={entry.id} value={entry.id}>{new Date(entry.timestamp).toLocaleString()} · {entry.mode} · {entry.signalsGenerated} setups</option>)}
        </select>
      </label>

      {/* Top SCAN-CONTROL strip ───────────────────────────────────── */}
      <section className="panel panel-accent" style={{ marginBottom: 18 }}>
        <Reticle />
        <div className="corner-tag tl">// SCAN-CONTROL</div>
        <div className="corner-tag tr">PHANTOM ENGINE</div>
        <div style={{ padding: '18px 22px' }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '2fr 1fr 1fr 1fr',
              gap: 14,
              alignItems: 'center',
            }}
          >
            <div>
              <div
                className="mono"
                style={{
                  fontSize: 10,
                  color: 'var(--fg-4)',
                  letterSpacing: '.18em',
                  textTransform: 'uppercase',
                  marginBottom: 4,
                }}
              >
                // ACTIVE MODE
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span
                  style={{
                    fontFamily: 'Share Tech Mono,monospace',
                    fontSize: 22,
                    letterSpacing: '.06em',
                    color: 'var(--accent)',
                  }}
                >
                  {modeName}
                </span>
                <span style={{ color: 'var(--fg-4)', fontSize: 10 }}>{tfRoster}</span>
              </div>
            </div>
            <div className="metric-tile">
              <div className="metric-label">SIGNALS</div>
              <div className="metric-value hud-glow-amber">{filtered.length}</div>
              <div className="metric-sub">{armedCount} actionable</div>
            </div>
            <div className="metric-tile">
              <div className="metric-label">PROFILE</div>
              <div className="metric-value" style={{ fontSize: 14 }}>
                {selectedMode?.profile ?? '—'}
              </div>
              <div className="metric-sub">scan profile</div>
            </div>
            <div className="metric-tile">
              <div className="metric-label">MIN SCORE</div>
              <div className="metric-value">≥ {minScore}</div>
              <div className="metric-sub">strict gate</div>
            </div>
            <MacroScoreTile />
            <CooldownsTile />
          </div>

          {/* Scan run controls — RUN / STOP / AUTO-SCAN with progress.
              Lifted into the SCAN-CONTROL panel so it lives adjacent to
              the mode + min-score + macro tiles that drive its config. */}
          <div style={{ marginTop: 14 }}>
            <ScanController onComplete={refreshCardSignals} />
          </div>
        </div>
      </section>

      {/* 3a': RejectionPanel — §11 observability surface. 6 category
          chips (UNIVERSE / DATA / CRITICAL_TF / FEATURES / CONFLUENCE /
          PLANNER) with click-expand sample failure rows. Sourced from
          the latest scan-history entry's rejectionSummary +
          universeSnapshot (both persisted in 3a'). Placed BELOW the
          SCAN-CONTROL panel so the cause-and-effect chain reads top-
          down: mode + ▶ → progress → outcome / rejections. */}
      <div style={{ marginBottom: 18 }}>
        <RejectionPanel entry={latestHistoryEntry} />
      </div>

      {/* Main 3-col ─────────────────────────────────────────────── */}
      <div className="layout-grid scanner-layout">
        {/* Left rail */}
        <section className="panel scanner-filter-panel">
          <SectionHead title="Filters" />
          <FilterRail
            filters={filters}
            setFilters={setFilters}
            counts={{ passing: filtered.length, total: cardSignals.length }}
            modeTfs={latestHistoryEntry?.timeframes ?? selectedMode?.timeframes ?? []}
          />
        </section>

        {/* Center grid */}
        <section className="panel">
          <SectionHead
            title={`Scan results · ${filtered.length}`}
            right={
              <>
                <Chip kind="green">SORT · SCORE ↓</Chip>
                <button className="btn" disabled={!latestHistoryEntry} onClick={() => {
                  const url = URL.createObjectURL(new Blob([JSON.stringify(latestHistoryEntry, null, 2)], { type: 'application/json' }));
                  const link = document.createElement('a'); link.href = url; link.download = `scan-${latestHistoryEntry?.id}.json`; link.click(); URL.revokeObjectURL(url);
                }}>EXPORT</button>
              </>
            }
          />
          <div className="scanner-results-grid">
            {filtered.length === 0 && (
              <div
                style={{
                  gridColumn: '1 / -1',
                  textAlign: 'center',
                  padding: '40px 0',
                  color: 'var(--fg-4)',
                  fontFamily: 'JetBrains Mono,monospace',
                  fontSize: 12,
                  letterSpacing: '.18em',
                  textTransform: 'uppercase',
                }}
              >
                {cardSignals.length === 0
                  ? latestHistoryEntry ? '// this scan produced no setups — review rejections above' : '// no scans yet — press ▶ run scan above'
                  : '// no signals match filters'}
              </div>
            )}
            {[...filtered].sort((a, b) => (b.score ?? -1) - (a.score ?? -1)).map((s) => (
              <SignalCard key={s.id} sig={s} />
            ))}
          </div>
        </section>

        {/* Right rail */}
        <div className="col">
          <section className="panel">
            <SectionHead
              title="Radar"
              right={
                <Chip kind="amber">{armedCount} HOT ◌</Chip>
              }
            />
            <div style={{ padding: '14px 18px' }}>
              <ScannerRadar signals={filtered} />
            </div>
          </section>

          <section className="panel">
            <SectionHead
              title="Result summary"
              right={
                <Chip>RECORDED</Chip>
              }
            />
            <div
              style={{
                padding: '12px 14px',
                background: 'rgba(0,0,0,.45)',
                maxHeight: 340,
                overflowY: 'auto',
              }}
            >
              <div
                className="term"
                style={{ fontSize: 11, color: 'var(--accent)', marginBottom: 8, opacity: 0.85 }}
              >
                Selected scan receipt
              </div>
              {cardSignals.length === 0 ? (
                <div
                  className="mono"
                  style={{ fontSize: 10, color: 'var(--fg-4)', padding: '8px 4px' }}
                >
                  // no recorded setups in this scan
                </div>
              ) : (
                cardSignals.slice(0, 8).map((c, i) => (
                  <div
                    className="log-row"
                    key={c.id}
                    style={{ gridTemplateColumns: '46px 36px 1fr 32px' }}
                  >
                    <span className="t">
                      {latestHistoryEntry ? new Date(latestHistoryEntry.timestamp).toLocaleTimeString() : '—'}
                    </span>
                    <span className={passesAdmission(c) ? 'pass' : 'rej'}>
                      {c.score === undefined ? 'N/A' : 'SCORE'}
                    </span>
                    <span>
                      <span className="sym">{c.sym}</span>
                      <br />
                      <span style={{ color: 'var(--fg-3)', fontSize: 10 }}>
                        {`${c.dir} · ${admissionLabel(c).toLowerCase()}`}
                      </span>
                    </span>
                    <span
                      className="mono"
                      style={{
                        fontSize: 10,
                        color: passesAdmission(c) ? 'var(--green-soft)' : 'var(--fg-4)',
                        textAlign: 'right',
                      }}
                    >
                      {formatScore(c.score)}
                    </span>
                  </div>
                ))
              )}
            </div>
          </section>

          <section className="panel">
            <SectionHead
              title="Recorded setup counts"
              right={
                <Chip kind="amber">◌</Chip>
              }
            />
            <div
              style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 8 }}
            >
              {!cardSignals.length && <p>No recorded setups.</p>}
              {Object.entries(cardSignals.reduce<Record<string, number>>((counts, signal) => { counts[signal.setup] = (counts[signal.setup] ?? 0) + 1; return counts; }, {})).map(([k, v]) => ({ k, v, c: 'var(--cyan)' })).map((x) => (
                <div key={x.k} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--fg-3)', width: 80 }}>
                    {x.k}
                  </span>
                  <div
                    style={{
                      flex: 1,
                      height: 6,
                      background: 'rgba(0,0,0,.4)',
                      borderRadius: 3,
                      border: '1px solid var(--border-soft)',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: (cardSignals.length ? x.v / cardSignals.length * 100 : 0) + '%',
                        background: x.c,
                        boxShadow: `0 0 6px ${x.c}`,
                      }}
                    />
                  </div>
                  <span
                    className="mono"
                    style={{
                      fontSize: 10,
                      color: 'var(--fg)',
                      fontWeight: 700,
                      width: 32,
                      textAlign: 'right',
                    }}
                  >
                    {x.v}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>

      <FooterStatus />

      <style>{`
        .layout-grid{display:grid;gap:18px}
        @media (max-width:1100px){.layout-grid{grid-template-columns:1fr !important}}
        .col{display:flex;flex-direction:column;gap:18px}
        .pos{padding:14px 16px;border:1px solid var(--border-soft);border-radius:8px;background:rgba(0,0,0,.35);position:relative}
        .brackets{position:relative}
        .corner-tag{position:absolute;font-family:'JetBrains Mono',monospace;font-size:8px;color:var(--fg-4);letter-spacing:.18em;text-transform:uppercase;padding:2px 6px}
        .corner-tag.tl{top:6px;left:8px}
        .corner-tag.tr{top:6px;right:8px}
        .metric-tile{padding:8px 10px;border:1px solid var(--border-soft);border-radius:6px;background:rgba(0,0,0,.35)}
        .metric-label{font-family:'JetBrains Mono',monospace;font-size:8px;color:var(--fg-4);letter-spacing:.18em;text-transform:uppercase;margin-bottom:4px}
        .metric-value{font-family:'Share Tech Mono',monospace;font-size:18px;font-weight:700;color:var(--fg);letter-spacing:.04em}
        .metric-sub{font-family:'JetBrains Mono',monospace;font-size:8px;color:var(--fg-4);letter-spacing:.12em;margin-top:3px}
        .log-row{display:grid;gap:6px;align-items:start;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.04);font-family:'JetBrains Mono',monospace;font-size:10px}
        .log-row .t{color:var(--fg-4)}
        .log-row .pass{color:var(--green-soft);font-weight:700}
        .log-row .rej{color:var(--red-2);font-weight:700}
        .log-row .sym{color:var(--fg);font-weight:700}
      `}</style>
    </div>
  );
}

export default Scanner;
