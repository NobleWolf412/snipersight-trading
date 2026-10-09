import { ScannerInputs } from '@/components/hud/ScannerInputs';
/** Manual scanner: application-owned runs, recorded history and explicit evidence.
 * Chart review overlays saved plan levels on source-specific candles.
 * The selected history receipt owns result counts, timestamps and setup summaries.
 */
import {
Chip,
FooterStatus,
PageHead,
RejectionPanel,
ScanController,
ScannerModePicker,
SectionHead
} from '@/components/hud';
import { useScanner } from '@/context/ScannerContext';
import { scanHistoryService } from '@/services/scanHistoryService';
import { formatSetupPrice } from '@/services/scannerSetup';
import { admissionLabel,formatScore,passesAdmission } from '@/utils/scoreEvidence';
import { Suspense,lazy,useCallback,useEffect,useMemo,useState } from 'react';
import './Scanner.css';

const ScannerSetupModal = lazy(() => import('@/components/ScannerSetupModal').then(module => ({ default: module.ScannerSetupModal })));

import { REGIMES,SETUPS,TFS,buildCardSignals,type CardSignal,type Direction,type Regime,type Setup,type Tf } from './scannerSignals';
export { buildCardSignals } from './scannerSignals';

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
          type="range" aria-label="Minimum displayed score"
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
                aria-pressed={active}
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
                aria-pressed={active}
                className={`btn ${active ? 'btn-cyan' : ''}`}
                style={{
                  padding: '6px 10px',
                  fontSize: 10,
                  cursor: 'pointer',
                }}
                title={
                  inMode
                    ? undefined
                    : `Not scanned by this mode. No matching signals appear at ${tf}.`
                }
                onClick={() => toggle('tfs', tf)}
              >
                {tf}{!inMode && <span style={{ fontSize: 9, letterSpacing: 0 }}>Outside mode</span>}
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
                aria-pressed={active}
                className={`btn ${active ? 'btn-cyan' : ''}`}
                style={{ padding: '5px 9px', fontSize: 9, minWidth: 44 }}
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
                aria-pressed={active}
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

// ─── Helpers: build CardSignals from scan history ────────────────────────

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

      <section className="panel scanner-run-panel" aria-label="Scan configuration and actions">
        <ScannerModePicker />
        <ScanController onComplete={refreshCardSignals} />
        <ScannerInputs />
      </section>
      <label className="scanner-history">Scan history
        <select value={latestHistoryEntry?.id ?? ''} onChange={e => {
          const entry = history.find(item => item.id === e.target.value);
          if (entry) { setLatestHistoryEntry(entry); setCardSignals(buildCardSignals([entry])); }
        }}>
          {!history.length && <option value="">No completed scans</option>}
          {history.map(entry => <option key={entry.id} value={entry.id}>{new Date(entry.timestamp).toLocaleString()} · {entry.mode} · {entry.signalsGenerated} setups</option>)}
        </select>
      </label>

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
          <details><summary>Filter displayed setups</summary>
          <FilterRail
            filters={filters}
            setFilters={setFilters}
            counts={{ passing: filtered.length, total: cardSignals.length }}
            modeTfs={latestHistoryEntry?.timeframes ?? selectedMode?.timeframes ?? []}
          />
          </details>
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
