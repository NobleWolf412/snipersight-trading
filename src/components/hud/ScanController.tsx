/**
 * ScanController — run/stop/auto-scan button cluster for the Scanner page.
 *
 * Wraps three responsibilities the HUD Scanner page was missing after the
 * archived ScannerSetup.tsx went away in Phase 6:
 *   1. Triggering a scan (POST /api/scanner/runs)
 *   2. Polling progress (GET /api/scanner/runs/{run_id}) until done
 *   3. Optionally auto-restarting on completion (AUTO-SCAN toggle)
 *
 * On each successful scan completion the controller:
 *   - Transforms backend signals via convertSignalToScanResult (same path
 *     the archived setup used, ensuring scan-history entries stay schema-
 *     compatible with downstream consumers).
 *   - Calls scanHistoryService.saveScan(...) so the existing Scanner page
 *     card grid (which reads from scanHistory) lights up.
 *   - Fires onComplete() so the page can refresh its local view.
 *
 * StrictMode-safe: all timers + the in-flight run are tracked via refs
 * and torn down on unmount. The dev-mode double-mount produces two probe
 * cycles; the cleanup ref-set ensures the second mount cleanly aborts the
 * first's poll loop.
 *
 * Auto-scan semantics:
 *   - When AUTO-SCAN is on AND the previous run completes/cancels/fails,
 *     a fresh run starts after AUTO_RESTART_MS (defaults to 5s, giving
 *     the operator a breath to read results before the grid changes).
 *   - When AUTO-SCAN is off, the run goes idle on completion. The button
 *     reverts to "RUN SCAN" and the controller waits for the next click.
 *
 * Failure handling:
 *   - HTTP errors during start surface as inline red copy under the
 *     button, keep the controller in 'idle' state, and never silently
 *     swallow the exception (logged at warn per §15).
 *   - Per-cycle poll failures retry; if 5 consecutive polls fail the
 *     run is marked failed and surfaced.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '@/utils/api';
import { scanHistoryService } from '@/services/scanHistoryService';
import { convertSignalToScanResult } from '@/utils/mockData';
import { useScanner } from '@/context/ScannerContext';
import { Chip } from './Chip';

const POLL_MS = 2_000; // 2s while a scan is in flight
const AUTO_RESTART_MS = 5_000; // breath between auto-scans
const MAX_CONSECUTIVE_POLL_FAILURES = 5;
const LS_AUTO_SCAN = 'sniper.scanner.autoScan.v1';

type RunStatus = 'idle' | 'starting' | 'running' | 'completed' | 'failed' | 'cancelled';

// Rejection summary kept compact — counts only, plus a small sampling of
// symbol names per reason for the "EXAMPLES" preview. Full details are
// available via the job endpoint if anyone needs to render them in a
// dedicated drawer later, but the inline breakdown intentionally trades
// completeness for a one-glance read.
interface RejectionSnapshot {
  total: number;
  byReason: Array<{ reason: string; count: number; examples: string[] }>;
}

interface ProgressState {
  status: RunStatus;
  progress: number;
  total: number;
  currentSymbol: string | null;
  error: string | null;
  signalsFound: number;
  rejections: RejectionSnapshot | null;
  // The run we last touched (used by the UI to render badges + cancel).
  runId: string | null;
  // Timestamps for rendering — null means "no completed run yet".
  startedAt: string | null;
  completedAt: string | null;
}

const INITIAL: ProgressState = {
  status: 'idle',
  progress: 0,
  total: 0,
  currentSymbol: null,
  error: null,
  signalsFound: 0,
  rejections: null,
  runId: null,
  startedAt: null,
  completedAt: null,
};

// Friendly labels for the most common rejection reason codes. Anything
// not in this map renders the raw key (lowercased, spaces preserved) so
// new backend codes surface without a code change here.
const REASON_LABELS: Record<string, string> = {
  low_confluence: 'LOW CONFLUENCE',
  no_data: 'NO DATA',
  risk_validation: 'RISK VALIDATION',
  no_trade_plan: 'NO TRADE PLAN',
  errors: 'PIPELINE ERROR',
  missing_critical_tf: 'MISSING CRITICAL TF',
  cooldown: 'COOLDOWN',
  regime_block: 'REGIME BLOCKED',
};

function summarizeRejections(raw: any): RejectionSnapshot | null {
  if (!raw || typeof raw !== 'object') return null;
  const byReasonObj = (raw.by_reason ?? {}) as Record<string, number>;
  const detailsObj = (raw.details ?? {}) as Record<string, Array<{ symbol?: string }>>;
  const reasons = Object.entries(byReasonObj)
    .filter(([, count]) => typeof count === 'number' && count > 0)
    .map(([reason, count]) => {
      const list = Array.isArray(detailsObj[reason]) ? detailsObj[reason] : [];
      const examples = list
        .slice(0, 3)
        .map((d) => d?.symbol)
        .filter((s): s is string => typeof s === 'string' && s.length > 0);
      return { reason, count: count as number, examples };
    })
    .sort((a, b) => b.count - a.count);
  const total = typeof raw.total_rejected === 'number'
    ? raw.total_rejected
    : reasons.reduce((s, r) => s + r.count, 0);
  if (total === 0 && reasons.length === 0) return null;
  return { total, byReason: reasons };
}

interface ScanControllerProps {
  /** Called after every successful scan completion so the page can
   *  re-pull from scanHistoryService and refresh its card grid. */
  onComplete?: () => void;
}

export function ScanController({ onComplete }: ScanControllerProps) {
  const { selectedMode, setIsScanning } = useScanner();
  const [state, setState] = useState<ProgressState>(INITIAL);

  // 3z.f: mirror local `state.status` into the global `isScanning`
  // flag on ScannerContext. The flag drives ActiveScanBeacon's
  // RECONNAISSANCE indicator. Pre-3z.f the global flag was a
  // useLocalStorage zombie with zero setters; this effect is the
  // single non-archive write path.
  useEffect(() => {
    setIsScanning(state.status === 'starting' || state.status === 'running');
  }, [state.status, setIsScanning]);

  // 3z.f: on unmount, force-clear isScanning. Prevents a stranded
  // ScanController (e.g., user navigated away mid-run) from leaving
  // the beacon stuck on RECONNAISSANCE.
  useEffect(() => () => setIsScanning(false), [setIsScanning]);

  const [autoScan, setAutoScan] = useState<boolean>(() => {
    try {
      return localStorage.getItem(LS_AUTO_SCAN) === '1';
    } catch {
      return false;
    }
  });

  // Refs for cleanup. `cancelled` is the StrictMode unmount marker; any
  // timer/interval is collected in `timers` so unmount kills all pending
  // setTimeouts cleanly.
  const cancelledRef = useRef(false);
  const timersRef = useRef<Set<ReturnType<typeof setTimeout>>>(new Set());
  // The most recently issued runId. Poll callbacks compare this so a
  // late response from a stale run never overwrites a newer run's state.
  const activeRunIdRef = useRef<string | null>(null);

  const clearAllTimers = useCallback(() => {
    for (const t of timersRef.current) clearTimeout(t);
    timersRef.current.clear();
  }, []);

  const scheduleTimer = useCallback(
    (fn: () => void, ms: number) => {
      const t = setTimeout(() => {
        timersRef.current.delete(t);
        if (cancelledRef.current) return;
        fn();
      }, ms);
      timersRef.current.add(t);
      return t;
    },
    [],
  );

  useEffect(() => {
    try {
      localStorage.setItem(LS_AUTO_SCAN, autoScan ? '1' : '0');
    } catch {
      /* localStorage quota — non-fatal */
    }
  }, [autoScan]);

  // Persist completed signals to scan history and notify caller.
  // Single helper so both the normal completion path and the failure
  // path (which may have partial metadata) share the same write.
  //
  // 3a' (Phase 3 follow-up): the persisted entry now retains the full
  // `rejectionSummary` (raw by_reason + details + features_breakdown)
  // and a parallel `universeSnapshot` captured at completion time. The
  // RejectionPanel consumes these to render per-run chips + click-expand
  // without re-polling the live /api/scanner/diagnostics endpoint.
  // Universe is fetched fire-and-forget; persistence still proceeds if
  // the snapshot fetch fails so a network blip on a sibling endpoint
  // can't strand the primary scan history write.
  const persistCompleted = useCallback(
    async (job: Awaited<ReturnType<typeof api.getScanRun>>['data']) => {
      if (!job) return;
      let universeSnapshot: import('@/services/scanHistoryService').UniverseSnapshot | undefined;
      try {
        const uRes = await api.getUniverse();
        if (uRes.data) {
          const u = uRes.data as any;
          const counts: Record<string, number> = {};
          const samples: Record<string, string[]> = {};
          for (const drop of u.dropped ?? []) {
            const reason: string = drop.reason ?? 'unknown';
            counts[reason] = (counts[reason] ?? 0) + 1;
            samples[reason] = samples[reason] ?? [];
            if (samples[reason].length < 10) samples[reason].push(drop.symbol);
          }
          universeSnapshot = {
            total_candidates: u.counts?.total_candidates ?? 0,
            drops_by_reason: counts,
            drops_by_reason_samples: samples,
            last_refresh_ts: u.last_refresh_ts ?? null,
          };
        }
      } catch (e) {
        // Universe fetch failure is non-fatal — log at warn per §15.
        // Scan-history persistence proceeds without the snapshot, and the
        // RejectionPanel handles a missing universeSnapshot gracefully.
        console.warn('[ScanController] universe snapshot fetch failed:', e);
      }
      try {
        const signals = (job.signals ?? []).map(convertSignalToScanResult);
        scanHistoryService.saveScan({
          mode: selectedMode?.name ?? 'unknown',
          profile: selectedMode?.profile ?? 'unknown',
          timeframes: selectedMode?.timeframes ?? [],
          symbolsScanned: job.total ?? 0,
          signalsGenerated: signals.length,
          signalsRejected: (job.rejections as any)?.total_rejected ?? 0,
          effectiveMinScore: selectedMode?.min_confluence_score ?? 0,
          rejectionBreakdown: (job.rejections as any)?.by_reason ?? {},
          rejectionSummary: (job.rejections as any) ?? undefined,
          universeSnapshot,
          results: signals,
        });
        onComplete?.();
      } catch (e) {
        // Persist failure should not crash the loop. Log loudly.
        console.warn('[ScanController] saveScan failed:', e);
      }
    },
    [selectedMode, onComplete],
  );

  // Poll loop. Recursive setTimeout pattern (not setInterval) so a slow
  // backend response can't pile up overlapping requests.
  const pollRun = useCallback(
    async (runId: string, consecutiveFailures = 0) => {
      if (cancelledRef.current) return;
      if (activeRunIdRef.current !== runId) return; // superseded

      try {
        const res = await api.getScanRun(runId, { silent: true });
        if (cancelledRef.current) return;
        if (activeRunIdRef.current !== runId) return;

        if (res.error || !res.data) {
          throw new Error(res.error || 'empty response');
        }
        const job = res.data;

        // Update UI state from the job snapshot. Always reflect what the
        // server says — never optimistically write progress numbers.
        setState((prev) => ({
          ...prev,
          status: job.status as RunStatus,
          progress: job.progress ?? 0,
          total: job.total ?? 0,
          currentSymbol: job.current_symbol ?? null,
          signalsFound: job.signals?.length ?? prev.signalsFound,
          // Only refresh rejections once a final state is reached; mid-
          // scan they're partial and would flicker. summarizeRejections
          // returns null when there's nothing to show.
          rejections:
            job.status === 'completed' || job.status === 'failed'
              ? summarizeRejections(job.rejections)
              : prev.rejections,
          runId,
          startedAt: job.started_at ?? prev.startedAt,
          completedAt: job.completed_at ?? prev.completedAt,
          error: job.error ?? null,
        }));

        if (job.status === 'completed') {
          // persistCompleted is async (fetches universe snapshot
          // alongside saveScan). Fire-and-forget — we don't gate the
          // auto-restart scheduler on its completion; the snapshot
          // arrives asynchronously and the next scan's render handles
          // the case where it lands after.
          void persistCompleted(job);
          activeRunIdRef.current = null;
          if (autoScan && !cancelledRef.current) {
            scheduleTimer(() => void startRun(), AUTO_RESTART_MS);
          }
          return;
        }
        if (job.status === 'failed' || job.status === 'cancelled') {
          activeRunIdRef.current = null;
          if (autoScan && job.status !== 'cancelled' && !cancelledRef.current) {
            scheduleTimer(() => void startRun(), AUTO_RESTART_MS);
          }
          return;
        }

        // Still queued/running — schedule next poll.
        scheduleTimer(() => void pollRun(runId, 0), POLL_MS);
      } catch (e) {
        const nextFail = consecutiveFailures + 1;
        console.warn(
          `[ScanController] poll failure ${nextFail}/${MAX_CONSECUTIVE_POLL_FAILURES}:`,
          e,
        );
        if (nextFail >= MAX_CONSECUTIVE_POLL_FAILURES) {
          if (cancelledRef.current) return;
          setState((prev) => ({
            ...prev,
            status: 'failed',
            error: `poll lost: ${String(e)}`,
          }));
          activeRunIdRef.current = null;
          return;
        }
        scheduleTimer(() => void pollRun(runId, nextFail), POLL_MS);
      }
    },
    // pollRun depends on persistCompleted, autoScan, scheduleTimer, and
    // a forward reference to startRun. We define startRun below; React's
    // closure semantics give us the right reference at call-time since
    // both are useCallback-wrapped and recreated together when deps shift.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [persistCompleted, autoScan, scheduleTimer],
  );

  const startRun = useCallback(async () => {
    if (cancelledRef.current) return;
    if (!selectedMode) {
      setState((prev) => ({ ...prev, status: 'failed', error: 'no scanner mode selected' }));
      return;
    }
    setState((prev) => ({
      ...prev,
      status: 'starting',
      error: null,
      progress: 0,
      total: 0,
      currentSymbol: null,
      signalsFound: 0,
    }));
    try {
      const res = await api.createScanRun({
        sniper_mode: selectedMode.name.toLowerCase(),
        // Defaults below mirror the archived ScannerSetup flow so the
        // job behaves identically to what users saw pre-rewrite. They
        // are NOT pulled from the mode definition because mode controls
        // strictness (min_confluence_score, timeframes), not universe
        // selection.
        majors: true,
        altcoins: true,
        meme_mode: false,
        exchange: 'phemex',
        leverage: 1,
        limit: 25,
      });
      if (cancelledRef.current) return;
      if (res.error || !res.data) {
        throw new Error(res.error || 'createScanRun returned no data');
      }
      const runId = res.data.run_id;
      activeRunIdRef.current = runId;
      setState((prev) => ({
        ...prev,
        status: 'running',
        runId,
        startedAt: res.data!.created_at,
      }));
      void pollRun(runId, 0);
    } catch (e) {
      console.warn('[ScanController] startRun failed:', e);
      if (cancelledRef.current) return;
      setState((prev) => ({
        ...prev,
        status: 'failed',
        error: String(e),
      }));
      activeRunIdRef.current = null;
    }
  }, [selectedMode, pollRun]);

  const cancelRun = useCallback(async () => {
    const runId = activeRunIdRef.current;
    if (!runId) return;
    try {
      await api.cancelScanRun(runId);
    } catch (e) {
      console.warn('[ScanController] cancelScanRun failed:', e);
    }
    activeRunIdRef.current = null;
    setState((prev) => ({ ...prev, status: 'cancelled' }));
    // Auto-scan honors a manual cancel — we deliberately do NOT
    // schedule a restart here even if autoScan is on. A cancel is a
    // human stop signal; auto only restarts after natural completion.
  }, []);

  // Cleanup on unmount: kill timers + flag cancellation. The
  // activeRunIdRef stays alive in case a later mount reconnects, but
  // any in-flight poll will see cancelledRef = true and bail.
  useEffect(() => {
    cancelledRef.current = false;
    return () => {
      cancelledRef.current = true;
      clearAllTimers();
    };
  }, [clearAllTimers]);

  const busy = state.status === 'starting' || state.status === 'running';
  const progressPct = state.total > 0 ? Math.min(100, (state.progress / state.total) * 100) : 0;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        padding: '10px 14px',
        border: '1px solid var(--border-soft)',
        borderRadius: 6,
        background: 'rgba(0,0,0,.35)',
      }}
    >
      {/* Button row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        {!busy && (
          <button
            className="btn btn-cyan"
            onClick={() => void startRun()}
            disabled={!selectedMode}
            style={{
              padding: '10px 20px',
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: '.18em',
              opacity: selectedMode ? 1 : 0.45,
              cursor: selectedMode ? 'pointer' : 'not-allowed',
            }}
          >
            ▶ RUN SCAN
          </button>
        )}
        {busy && (
          <button
            className="btn btn-red"
            onClick={() => void cancelRun()}
            style={{
              padding: '10px 20px',
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: '.18em',
            }}
          >
            ■ STOP
          </button>
        )}

        {/* Auto-scan toggle */}
        <label
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            cursor: 'pointer',
            userSelect: 'none',
          }}
          onClick={() => setAutoScan((v) => !v)}
        >
          <div
            style={{
              width: 32,
              height: 16,
              borderRadius: 8,
              background: autoScan ? 'var(--accent)' : 'rgba(0,0,0,.6)',
              border: '1px solid var(--border-soft)',
              position: 'relative',
              transition: 'background .15s',
              boxShadow: autoScan ? '0 0 6px var(--accent)' : 'none',
            }}
          >
            <div
              style={{
                position: 'absolute',
                top: 1,
                left: autoScan ? 17 : 1,
                width: 12,
                height: 12,
                borderRadius: '50%',
                background: autoScan ? '#0a0c0e' : 'var(--fg-3)',
                transition: 'left .15s',
              }}
            />
          </div>
          <span
            className="mono"
            style={{
              fontSize: 10,
              color: autoScan ? 'var(--accent)' : 'var(--fg-3)',
              letterSpacing: '.18em',
              textTransform: 'uppercase',
            }}
          >
            auto-scan {autoScan ? 'on' : 'off'}
          </span>
        </label>

        {/* Status chip — always one visible so the operator can always
            tell what the controller is doing at a glance. */}
        {state.status === 'idle' && <Chip>◌ IDLE</Chip>}
        {state.status === 'starting' && <Chip kind="amber">◌ STARTING…</Chip>}
        {state.status === 'running' && <Chip kind="cyan">● SCANNING</Chip>}
        {state.status === 'completed' && (
          <Chip kind={state.signalsFound > 0 ? 'green' : 'amber'}>
            {state.signalsFound > 0 ? '✓' : '◌'} {state.signalsFound} SIGNALS
          </Chip>
        )}
        {state.status === 'cancelled' && <Chip kind="amber">◌ CANCELLED</Chip>}
        {state.status === 'failed' && <Chip kind="red">✕ FAILED</Chip>}
      </div>

      {/* Progress row — only visible while busy or for the last result */}
      {(busy || state.total > 0) && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div
            className="mono"
            style={{
              fontSize: 10,
              color: 'var(--fg-3)',
              letterSpacing: '.16em',
              textTransform: 'uppercase',
              display: 'flex',
              justifyContent: 'space-between',
            }}
          >
            <span>
              progress · {state.progress} / {state.total || '—'}
            </span>
            <span style={{ color: 'var(--fg-4)' }}>
              {state.currentSymbol ? `// ${state.currentSymbol}` : ''}
            </span>
          </div>
          <div
            style={{
              width: '100%',
              height: 4,
              background: 'rgba(0,0,0,.6)',
              border: '1px solid var(--border-soft)',
              borderRadius: 2,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: '100%',
                height: '100%',
                transform: `scaleX(${progressPct / 100})`,
                transformOrigin: 'left center',
                background: 'var(--accent)',
                boxShadow: busy ? '0 0 6px var(--accent)' : 'none',
                transition: 'transform .35s ease-out',
              }}
            />
          </div>
        </div>
      )}

      {/* Error row */}
      {state.error && (
        <div
          className="mono"
          style={{
            fontSize: 10,
            color: 'var(--red-2)',
            letterSpacing: '.14em',
            textTransform: 'uppercase',
          }}
        >
          ✕ {state.error}
        </div>
      )}

      {/* Rejection breakdown — visible after any completed scan that
          recorded rejections. Bars are proportional within the strip
          (max-reason normalized to full width) so the operator sees
          relative dominance at a glance regardless of absolute scale. */}
      {state.rejections && state.rejections.byReason.length > 0 && (
        <RejectionBreakdownStrip
          rejections={state.rejections}
          signalsFound={state.signalsFound}
        />
      )}
    </div>
  );
}

// ─── RejectionBreakdownStrip ─────────────────────────────────────────────
// Stand-alone sub-component so the main controller render block stays
// scannable. Renders a stacked-by-count bar list with reason label,
// percentage of total, and up to three example symbols. The widest bar
// drives the visual scale — every other bar is relative width to it.

interface RejectionBreakdownStripProps {
  rejections: RejectionSnapshot;
  signalsFound: number;
}

function RejectionBreakdownStrip({ rejections, signalsFound }: RejectionBreakdownStripProps) {
  const maxCount = rejections.byReason[0]?.count ?? 1;
  return (
    <div
      style={{
        marginTop: 4,
        paddingTop: 8,
        borderTop: '1px dashed var(--border-soft)',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
      }}
    >
      <div
        className="mono"
        style={{
          fontSize: 10,
          color: 'var(--fg-3)',
          letterSpacing: '.18em',
          textTransform: 'uppercase',
          display: 'flex',
          justifyContent: 'space-between',
        }}
      >
        <span>// rejection breakdown</span>
        <span style={{ color: 'var(--fg-4)' }}>
          {rejections.total} rejected · {signalsFound} kept
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {rejections.byReason.map(({ reason, count, examples }) => {
          const label = REASON_LABELS[reason] ?? reason.replace(/_/g, ' ').toUpperCase();
          const pct = rejections.total > 0
            ? Math.round((count / rejections.total) * 100)
            : 0;
          const widthPct = (count / maxCount) * 100;
          return (
            <div key={reason} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <div
                className="mono"
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: 10,
                  color: 'var(--fg-2, var(--fg))',
                  letterSpacing: '.1em',
                }}
              >
                <span>
                  {label}
                  {examples.length > 0 && (
                    <span style={{ color: 'var(--fg-4)', marginLeft: 8, fontSize: 9 }}>
                      ({examples.join(', ')}
                      {count > examples.length ? '…' : ''})
                    </span>
                  )}
                </span>
                <span style={{ color: 'var(--fg-3)' }}>
                  {count} · {pct}%
                </span>
              </div>
              <div
                style={{
                  width: '100%',
                  height: 3,
                  background: 'rgba(0,0,0,.5)',
                  border: '1px solid var(--border-soft)',
                  borderRadius: 1,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    width: '100%',
                    height: '100%',
                    transform: `scaleX(${widthPct / 100})`,
                    transformOrigin: 'left center',
                    background: 'var(--amber, #fbbf24)',
                    opacity: 0.75,
                    transition: 'transform .35s ease-out',
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
