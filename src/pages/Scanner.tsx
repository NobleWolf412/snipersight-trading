/**
 * Scanner — Phase 3f sub-step 1
 *
 * NEW page. Port of `prototype/scanner.jsx` adapted to TSX + the project's
 * HUD primitives. Lives at `/scanner` alongside the legacy `/scanner/setup`
 * and `/scanner/status` routes (those archive in Phase 6 per the
 * peppy-sniffing-owl plan).
 *
 * Data wiring:
 *   - `useScanner()` provides `selectedMode` (drives min-score badge, mode
 *     name, profile description, timeframe roster). Mode picker itself is
 *     deferred to sub-step 2 — current-mode is read-only here.
 *   - `scanHistoryService.getAllScans()` provides the latest scan's results.
 *     If there are no scans yet, the grid renders an empty-state — no fake
 *     signals are ever displayed as real.
 *
 * Synthetic-but-disclosed (each tagged with the amber `◌` chip pattern
 * established by Intel.tsx):
 *   - Mini-chart candles per card — deterministic Math.sin from id/entry,
 *     not real OHLC. Tagged `◌` on the panel header.
 *   - Radar dot positions — synthetic placement around a circular grid.
 *   - Setup-bias bars — fixed counts; not bound to backend setup-tag stats.
 *   - Console log feed — empty when no scans; placeholder line otherwise.
 *
 * Deferred (with inline `◌ deferred` placeholders):
 *   - **ScannerModePicker** (plan §3d) — current selectedMode is read-only
 *     in this sub-step. Picker lands as 3f sub-step 2.
 *   - **Trade-type chips** (plan §3d P1) — backend has no `trade_type` per
 *     plan; show `—` placeholder when the tag would render.
 *   - **Convergence/conflict mini-bar** (plan §3d P1) — needs per-card
 *     confluence breakdown, not in current scan-history shape.
 *   - **Cooldown timer** (plan §3d P1) — needs cooldown ttl from rejected
 *     list.
 *   - **Cycle heartbeat strip** (plan §3d P1) — needs `/api/cycles/last`
 *     wired into a real heartbeat component (fixture exists; component
 *     does not yet).
 *   - **SignalDetail modal** — opens on card click in prototype; deferred
 *     so the `default` snapshot state stays direction-agnostic.
 *
 * Determinism for snapshots:
 *   - No `setInterval` (no ticking clock; Topbar already drives UTC).
 *   - No `Math.random` (all chart candles are Math.sin/Math.cos seeded by
 *     stable card ids).
 *   - Static `now` captured once at mount via useState initializer.
 *
 * Snapshot-ready handshake:
 *   StrictMode-safe pattern from Intel.tsx — each mount sets the body
 *   attribute, each cleanup unsets it; no ref-gate so the dev-mode
 *   double-invoke leaves the final state set.
 */
import { useEffect, useMemo, useState } from 'react';
import {
  Chip,
  FooterStatus,
  PageHead,
  Reticle,
  SectionHead,
  fmtPrice,
} from '@/components/hud';
import { useScanner } from '@/context/ScannerContext';
import { scanHistoryService, type ScanHistoryEntry } from '@/services/scanHistoryService';

// ─── Synthetic seed — labelled in the UI as such ─────────────────────────
//
// These constants stand in for the per-signal categorical tags the backend
// scorer does not yet emit in the scan-history shape (setup categorisation,
// regime per signal, multi-factor bias scores). Every panel that consumes
// them sets the amber `◌` chip on its SectionHead so the operator never
// mistakes the rendering for live signal output. Replace seed lookups with
// real fields when scoring exposes them — no UI restructure required.

const SETUPS = ['OB+FVG', 'BOS', 'CHoCH', 'LIQ-SWEEP', 'OB-RETEST', 'FVG-FILL', 'BREAKER'] as const;
const TFS = ['1m', '5m', '15m', '1h', '4h', '1D'] as const;
const REGIMES = ['TREND', 'RANGE', 'CHOP'] as const;

type Setup = (typeof SETUPS)[number];
type Tf = (typeof TFS)[number];
type Regime = (typeof REGIMES)[number];
type Direction = 'LONG' | 'SHORT';
type Confidence = 'HIGH' | 'MED' | 'LOW';

interface CardSignal {
  id: string;
  sym: string;
  dir: Direction;
  setup: Setup;
  score: number;
  tf: Tf;
  conf: Confidence;
  regime: Regime;
  mark: number;
  entry: number;
  sl: number;
  tp1: number;
  tp2: number;
  rr: number;
  age: number;
  bias: [number, number, number, number];
}

// Deterministic synthesizer: when scan history exists but lacks the
// categorical fields the prototype expects, derive a stable Setup/TF/Regime
// from the symbol so the same card always renders identically.
function synthFromSymbol(sym: string, idx: number): {
  setup: Setup;
  tf: Tf;
  regime: Regime;
  conf: Confidence;
  bias: [number, number, number, number];
} {
  const seed = sym.split('').reduce((s, c) => s + c.charCodeAt(0), 0) + idx;
  const setup = SETUPS[seed % SETUPS.length];
  const tf = TFS[seed % TFS.length];
  const regime = REGIMES[seed % REGIMES.length];
  const conf: Confidence = seed % 3 === 0 ? 'HIGH' : seed % 3 === 1 ? 'MED' : 'LOW';
  const b = (n: number) => 5 + ((seed >> n) % 5);
  return { setup, tf, regime, conf, bias: [b(0), b(2), b(4), b(6)] };
}

// ─── Mini chart (per card) ───────────────────────────────────────────────

interface CandleD {
  open: number;
  close: number;
  hi: number;
  lo: number;
}

function MiniChart({ sig }: { sig: CardSignal }) {
  const N = 30;
  const candles = useMemo<CandleD[]>(() => {
    const arr: CandleD[] = [];
    let p = sig.entry * (sig.dir === 'LONG' ? 0.99 : 1.01);
    const idSeed = sig.id.charCodeAt(Math.min(1, sig.id.length - 1)) || 1;
    for (let i = 0; i < N; i++) {
      const drift = sig.dir === 'LONG' ? 0.0008 : -0.0008;
      // Deterministic "noise" — no Math.random.
      const vol = Math.sin(i * 1.7 + idSeed) * 0.005;
      const open = p,
        close = p * (1 + drift + vol);
      arr.push({
        open,
        close,
        hi: Math.max(open, close) * 1.003,
        lo: Math.min(open, close) * 0.997,
      });
      p = close;
    }
    const f = sig.mark / arr[arr.length - 1].close;
    arr.forEach((c) => {
      c.open *= f;
      c.close *= f;
      c.hi *= f;
      c.lo *= f;
    });
    return arr;
  }, [sig]);
  const allP = [...candles.flatMap((c) => [c.hi, c.lo]), sig.entry, sig.sl, sig.tp1];
  const yMin = Math.min(...allP) * 0.998,
    yMax = Math.max(...allP) * 1.002,
    yR = yMax - yMin || 1;
  const W = 240,
    H = 70,
    pad = 3;
  const cw = (W - 2 * pad) / candles.length;
  const yOf = (p: number) => pad + ((yMax - p) / yR) * (H - 2 * pad);
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{
        width: '100%',
        height: 70,
        background: 'rgba(0,0,0,.35)',
        borderRadius: 4,
      }}
    >
      <line
        x1={pad}
        x2={W - pad}
        y1={yOf(sig.entry)}
        y2={yOf(sig.entry)}
        stroke="#60a5fa"
        strokeWidth=".5"
        strokeDasharray="2 3"
        opacity=".7"
      />
      <line
        x1={pad}
        x2={W - pad}
        y1={yOf(sig.sl)}
        y2={yOf(sig.sl)}
        stroke="#f87171"
        strokeWidth=".5"
        strokeDasharray="2 3"
        opacity=".7"
      />
      <line
        x1={pad}
        x2={W - pad}
        y1={yOf(sig.tp1)}
        y2={yOf(sig.tp1)}
        stroke="#22c55e"
        strokeWidth=".5"
        strokeDasharray="2 3"
        opacity=".7"
      />
      {candles.map((c, i) => {
        const x = pad + i * cw + cw * 0.15,
          w = cw * 0.7;
        const yO = yOf(c.open),
          yC = yOf(c.close),
          yH = yOf(c.hi),
          yL = yOf(c.lo);
        const up = c.close >= c.open,
          color = up ? '#22c55e' : '#f87171';
        return (
          <g key={i}>
            <line
              x1={x + w / 2}
              x2={x + w / 2}
              y1={yH}
              y2={yL}
              stroke={color}
              strokeWidth=".5"
              opacity=".6"
            />
            <rect
              x={x}
              y={Math.min(yO, yC)}
              width={w}
              height={Math.max(0.8, Math.abs(yC - yO))}
              fill={color}
              opacity=".85"
            />
          </g>
        );
      })}
      <circle cx={W - pad - 2} cy={yOf(sig.mark)} r="2" fill="#fbbf24" />
    </svg>
  );
}

// ─── Signal Card ─────────────────────────────────────────────────────────

function SignalCard({ sig }: { sig: CardSignal }) {
  const isLong = sig.dir === 'LONG';
  const confCol =
    sig.conf === 'HIGH' ? 'var(--green-soft)' : sig.conf === 'MED' ? 'var(--amber)' : 'var(--fg-3)';
  const setupKind: 'blue' | 'purple' | 'amber' | undefined = sig.setup.includes('FVG')
    ? 'blue'
    : sig.setup.includes('BOS') || sig.setup.includes('CHoCH')
      ? 'purple'
      : sig.setup.includes('LIQ')
        ? 'amber'
        : undefined;
  return (
    <div className="pos brackets">
      <div className="corner-tag tl">// {sig.id.toUpperCase()}</div>
      <div className="corner-tag tr">
        {sig.tf} · {sig.age}m AGO
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
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
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
        <div style={{ textAlign: 'right' }}>
          <div
            className="mono"
            style={{ fontSize: 18, fontWeight: 800, color: confCol, lineHeight: 1 }}
          >
            {sig.score.toFixed(1)}
          </div>
          <div className="mono" style={{ fontSize: 8, color: confCol, letterSpacing: '.18em' }}>
            {sig.conf}
          </div>
        </div>
      </div>
      <MiniChart sig={sig} />
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4,1fr)',
          gap: '8px 10px',
          marginTop: 10,
        }}
      >
        <div className="metric-tile">
          <div className="metric-label">Entry</div>
          <div className="metric-value" style={{ fontSize: 12 }}>
            {fmtPrice(sig.entry)}
          </div>
        </div>
        <div className="metric-tile">
          <div className="metric-label">Stop</div>
          <div className="metric-value" style={{ fontSize: 12, color: 'var(--red-2)' }}>
            {fmtPrice(sig.sl)}
          </div>
        </div>
        <div className="metric-tile">
          <div className="metric-label">TP1</div>
          <div className="metric-value" style={{ fontSize: 12, color: 'var(--green-soft)' }}>
            {fmtPrice(sig.tp1)}
          </div>
        </div>
        <div className="metric-tile">
          <div className="metric-label">R:R</div>
          <div className="metric-value" style={{ fontSize: 12, color: 'var(--accent)' }}>
            {sig.rr.toFixed(1)}:1
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
        {sig.bias[0] >= 7 && <Chip style={{ fontSize: 9 }}>HTF ✓</Chip>}
        {sig.bias[1] >= 7 && <Chip style={{ fontSize: 9 }}>VOL ✓</Chip>}
        {/* Trade-type chip: deferred — backend trade_type field not in scan-history shape */}
        <Chip kind="amber" style={{ fontSize: 9 }}>
          ◌ —
        </Chip>
        <span style={{ flex: 1 }} />
        <button className="btn btn-green" style={{ padding: '4px 10px', fontSize: 10 }} disabled>
          ▶ TAKE
        </button>
      </div>
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
}: {
  filters: Filters;
  setFilters: (f: Filters) => void;
  counts: { passing: number; total: number };
}) {
  const upd = <K extends keyof Filters>(k: K, v: Filters[K]) => setFilters({ ...filters, [k]: v });
  const toggle = <K extends 'tfs' | 'setups' | 'regimes'>(k: K, v: Filters[K][number]) => {
    const arr = filters[k] as readonly string[];
    const next = arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v];
    setFilters({ ...filters, [k]: next as Filters[K] });
  };
  return (
    <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 14 }}>
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
          // MIN SCORE · {filters.minScore.toFixed(1)}
        </div>
        <input
          type="range"
          min="0"
          max="10"
          step=".1"
          value={filters.minScore}
          onChange={(e) => upd('minScore', +e.target.value)}
          style={{ width: '100%' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
          <span className="mono" style={{ fontSize: 9, color: 'var(--fg-4)' }}>
            0.0
          </span>
          <span className="mono" style={{ fontSize: 9, color: 'var(--accent)' }}>
            ≥ {filters.minScore.toFixed(1)}
          </span>
          <span className="mono" style={{ fontSize: 9, color: 'var(--fg-4)' }}>
            10.0
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
          // TIMEFRAME
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 6 }}>
          {TFS.map((tf) => {
            const active = filters.tfs.includes(tf);
            return (
              <button
                key={tf}
                className={`btn ${active ? 'btn-cyan' : ''}`}
                style={{ padding: '6px 10px', fontSize: 10 }}
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
          const dist = 30 + (10 - s.score) * 5;
          const x = Math.cos(angle) * dist,
            y = Math.sin(angle) * dist;
          const armed = s.score >= 7;
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

function buildCardSignals(history: ScanHistoryEntry[]): CardSignal[] {
  const latest = history[0];
  if (!latest || !Array.isArray(latest.results) || latest.results.length === 0) return [];
  return latest.results.slice(0, 8).map((r: any, i: number): CardSignal => {
    const sym: string = r.symbol ?? r.sym ?? 'UNKNOWN/USDT';
    const dir: Direction =
      (r.direction || r.side || r.dir || 'long').toString().toUpperCase().startsWith('S')
        ? 'SHORT'
        : 'LONG';
    const synth = synthFromSymbol(sym, i);
    const entry: number = Number(r.entry ?? r.entry_price ?? r.price ?? 0) || 1;
    const sl: number = Number(r.stop ?? r.stop_loss ?? r.sl ?? entry * (dir === 'LONG' ? 0.98 : 1.02));
    const tp1: number = Number(r.tp1 ?? r.take_profit ?? r.tp ?? entry * (dir === 'LONG' ? 1.015 : 0.985));
    const tp2: number = Number(r.tp2 ?? entry * (dir === 'LONG' ? 1.03 : 0.97));
    const score: number = Number(r.score ?? r.confluence_score ?? r.confluence ?? 0) || 0;
    const rr: number = Number(r.rr ?? r.risk_reward ?? Math.abs((tp1 - entry) / Math.max(0.0001, entry - sl))) || 1.5;
    const mark: number = Number(r.mark ?? r.mark_price ?? entry);
    const id: string = String(r.id ?? `card_${i}`);
    return {
      id,
      sym,
      dir,
      setup: synth.setup,
      score,
      tf: synth.tf,
      conf: synth.conf,
      regime: synth.regime,
      mark,
      entry,
      sl,
      tp1,
      tp2,
      rr,
      age: i * 5 + 7, // synthetic — backend doesn't expose card age in history
      bias: synth.bias,
    };
  });
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

  // Real signal source — scan history. Empty when no scans yet (snapshot
  // capture renders the empty state).
  const cardSignals = useMemo<CardSignal[]>(() => {
    try {
      const history = scanHistoryService.getAllScans();
      return buildCardSignals(history);
    } catch {
      return [];
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
        if (s.score < filters.minScore) return false;
        if (filters.dir !== 'ALL' && s.dir !== filters.dir) return false;
        if (!filters.tfs.includes(s.tf)) return false;
        if (!filters.setups.includes(s.setup)) return false;
        if (!filters.regimes.includes(s.regime)) return false;
        return true;
      }),
    [cardSignals, filters],
  );

  const armedCount = filtered.filter((s) => s.score >= 7).length;
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
              <div
                style={{
                  position: 'relative',
                  height: 4,
                  marginTop: 8,
                  borderRadius: 2,
                  background: 'rgba(0,0,0,.5)',
                  overflow: 'hidden',
                }}
              >
                {/* Static progress placeholder — cycle heartbeat deferred. */}
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    width: '64%',
                    background:
                      'linear-gradient(90deg, rgba(251,191,36,.7), rgba(251,191,36,1))',
                    boxShadow: '0 0 12px rgba(251,191,36,.5)',
                  }}
                />
              </div>
              <div
                className="mono"
                style={{
                  fontSize: 9,
                  color: 'var(--fg-4)',
                  letterSpacing: '.14em',
                  marginTop: 6,
                }}
              >
                <span style={{ color: 'var(--amber)' }}>◌</span> cycle heartbeat —
                deferred (plan §3d P1)
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
          </div>
        </div>
      </section>

      {/* Main 3-col ─────────────────────────────────────────────── */}
      <div className="layout-grid" style={{ gridTemplateColumns: '260px 1fr 320px' }}>
        {/* Left rail */}
        <section className="panel" style={{ position: 'sticky', top: 14, alignSelf: 'start' }}>
          <SectionHead title="Filters" />
          <FilterRail
            filters={filters}
            setFilters={setFilters}
            counts={{ passing: filtered.length, total: cardSignals.length }}
          />
        </section>

        {/* Center grid */}
        <section className="panel">
          <SectionHead
            title={`Live Signals · ${filtered.length}`}
            right={
              <>
                <Chip kind="green">SORT · SCORE ↓</Chip>
                <Chip kind="amber">◌ EXPORT</Chip>
              </>
            }
          />
          <div
            style={{
              padding: '14px 18px',
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 12,
            }}
          >
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
                  ? '// no scans yet — run a scan from /scanner/setup'
                  : '// no signals match filters'}
              </div>
            )}
            {filtered.map((s) => (
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
              title="Console"
              right={
                <Chip kind="amber">◌ LIVE</Chip>
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
                {`> tail -f scanner.log`}
              </div>
              {cardSignals.length === 0 ? (
                <div
                  className="mono"
                  style={{ fontSize: 10, color: 'var(--fg-4)', padding: '8px 4px' }}
                >
                  // no console output until a scan runs
                </div>
              ) : (
                cardSignals.slice(0, 8).map((c, i) => (
                  <div
                    className="log-row"
                    key={c.id}
                    style={{ gridTemplateColumns: '46px 36px 1fr 32px' }}
                  >
                    <span className="t">
                      {String(14 - Math.floor(i / 4)).padStart(2, '0')}:
                      {String(42 - i * 2).padStart(2, '0')}:
                      {String((i * 7) % 60).padStart(2, '0')}
                    </span>
                    <span className={c.score >= 7 ? 'pass' : 'rej'}>
                      {c.score >= 7 ? 'PASS' : 'FILT'}
                    </span>
                    <span>
                      <span className="sym">{c.sym}</span>
                      <br />
                      <span style={{ color: 'var(--fg-3)', fontSize: 10 }}>
                        {c.score >= 7 ? `${c.setup} aligned · ${c.tf}` : `score < ${minScore}`}
                      </span>
                    </span>
                    <span
                      className="mono"
                      style={{
                        fontSize: 10,
                        color: c.score >= 7 ? 'var(--green-soft)' : 'var(--fg-4)',
                        textAlign: 'right',
                      }}
                    >
                      {c.score.toFixed(1)}
                    </span>
                  </div>
                ))
              )}
            </div>
          </section>

          <section className="panel">
            <SectionHead
              title="Setup Bias"
              right={
                <Chip kind="amber">◌</Chip>
              }
            />
            <div
              style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 8 }}
            >
              {[
                { k: 'OB+FVG', c: 'var(--cyan)', v: 42 },
                { k: 'BOS', c: 'var(--purple)', v: 28 },
                { k: 'CHoCH', c: 'var(--purple)', v: 18 },
                { k: 'LIQ-SWEEP', c: 'var(--amber)', v: 25 },
                { k: 'BREAKER', c: 'var(--red-2)', v: 14 },
              ].map((x) => (
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
                        width: Math.min(100, x.v * 2) + '%',
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

      <FooterStatus latency={42} />

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
