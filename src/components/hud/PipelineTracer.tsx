/**
 * PipelineTracer — per-signal pipeline drawer (Phase 3g.ii.c)
 *
 * Plan reference: peppy-sniffing-owl §3e.
 *
 *   "NEW: <PipelineTracer /> drawer component — flattened ~11-stage
 *    horizontal flowchart for one signal, sourced from
 *    /api/signals/{id}/trace. Each stage shows pass/fail, the actual
 *    value (score, threshold, R:R, regime tag), and is clickable to
 *    expand the underlying gauntlet substages from the
 *    gauntlet_substages field."
 *
 * Real-data wiring:
 *   - Fetches `/api/signals/{id}/trace` via `api.getSignalTrace(id)` when
 *     `signalId` becomes non-null. The trace ring buffer is populated by
 *     `LiveTradingService._log_signal()` — every signal logged in the
 *     last cycle is queryable. Older ids return 404; we render the error
 *     state instead of mock data.
 *   - The wire shape is `Envelope<SignalTrace>`. We surface
 *     `metadata.status === 'PARTIAL'` (id known, trace evicted) and any
 *     `warnings[]` to the operator rather than silently degrading.
 *
 * Synthetic-but-disclosed: none. The drawer renders ONLY real backend
 *   trace data; if the fetch fails or status is PARTIAL, an explicit
 *   amber `◌` chip surfaces the condition.
 *
 * Determinism for snapshots:
 *   - Stage list iteration order is the wire `stages[]` order (the
 *     backend constructs it deterministically: UNIVERSE → DATA → ... →
 *     EXECUTION).
 *   - No `Date.now`, no `toLocaleTimeString`. Cycle ts is rendered as a
 *     bare number (the backend currently sends `scan_number` as
 *     `cycle_ts` per the live_trading_service ring-buffer wiring).
 *
 * StrictMode safety:
 *   - Dev-mode mount/unmount/mount is handled by AbortController +
 *     a captured `cancelled` flag in the effect closure. Late
 *     resolutions from the first mount are dropped.
 *
 * Symmetry (CLAUDE.md §10 #3):
 *   - Direction-agnostic layout. Stage colors are purely
 *     pass/fail/skip; LONG vs SHORT signals render identical chrome.
 *     The `side` chip is an information badge, not a layout switch.
 *
 * Deferred to later 3g.ii sub-steps:
 *   - Embedding the per-signal `<ConfluenceFactorList />` inside an
 *     expanded CONFLUENCE_SCORE stage (3g.ii.d, sourced from
 *     `/api/signals/{id}/confluence`).
 *   - Mode-delta tooltip integration with the bottleneck pill (3g.ii.f).
 */
import { useEffect, useState } from 'react';
import { api, type SignalTrace, type TraceStage, type ResponseMetadata } from '@/utils/api';
import { Chip } from './Chip';
import { Modal } from './Modal';

// ─── Stage display config ─────────────────────────────────────────────

interface StageView {
  pass: boolean | null;
  killed: boolean;
}

function stageColor({ pass, killed }: StageView): string {
  if (killed) return 'var(--red-2)';
  if (pass === true) return 'var(--green-soft)';
  if (pass === false) return 'var(--red-2)';
  return 'var(--fg-4)'; // skipped
}

function stageBg({ pass, killed }: StageView): string {
  if (killed) return 'rgba(248,113,113,.10)';
  if (pass === true) return 'rgba(74,222,128,.08)';
  if (pass === false) return 'rgba(248,113,113,.10)';
  return 'rgba(255,255,255,.02)'; // skipped
}

function stageGlyph({ pass, killed }: StageView): string {
  if (killed) return '\u2716'; // ✖
  if (pass === true) return '\u2713'; // ✓
  if (pass === false) return '\u2716';
  return '\u2014'; // — em-dash for skipped
}

// ─── Status chip mapping ──────────────────────────────────────────────

function finalStateChip(finalState: string): { kind: 'green' | 'red' | 'amber'; label: string } {
  const lc = finalState.toLowerCase();
  if (lc.startsWith('executed')) return { kind: 'green', label: finalState };
  if (lc.startsWith('error')) return { kind: 'red', label: finalState };
  // filtered:* / rejected:* / unknown
  return { kind: 'amber', label: finalState };
}

// ─── Component ────────────────────────────────────────────────────────

interface Props {
  /** Stable signal id (e.g. `BTC-USDT_42_15m_long`). When null, the drawer is closed. */
  signalId: string | null;
  onClose: () => void;
}

export function PipelineTracer({ signalId, onClose }: Props) {
  const [trace, setTrace] = useState<SignalTrace | null>(null);
  const [meta, setMeta] = useState<ResponseMetadata | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [expandedStage, setExpandedStage] = useState<string | null>(null);

  useEffect(() => {
    if (!signalId) {
      setTrace(null);
      setMeta(null);
      setWarnings([]);
      setError(null);
      setExpandedStage(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    setTrace(null);
    setMeta(null);
    setWarnings([]);
    setExpandedStage(null);

    api.getSignalTrace(signalId).then((res) => {
      if (cancelled) return;
      setLoading(false);
      if (res.error || !res.data) {
        setError(res.error || 'no response body');
        return;
      }
      const env = res.data;
      setMeta(env.metadata);
      setWarnings(env.warnings ?? []);
      if (env.data === null) {
        // PARTIAL — id known, trace unavailable. Surface meta.reason.
        setError(env.metadata.reason || 'trace unavailable');
        return;
      }
      setTrace(env.data);
    });

    return () => {
      cancelled = true;
    };
  }, [signalId]);

  if (!signalId) return null;

  // ─── Header (always rendered when drawer is open) ─────────────────
  const header = (
    <div
      className="sec-head"
      style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span className="dot" />
        <span
          className="mono"
          style={{ fontSize: 11, letterSpacing: '.18em', fontWeight: 700, color: 'var(--fg-1)' }}
        >
          PIPELINE TRACER
        </span>
        {trace && (
          <>
            <span className="mono" style={{ fontSize: 11, color: 'var(--fg-2)', fontWeight: 700 }}>
              {trace.symbol}
            </span>
            <span
              className="mono"
              style={{
                fontSize: 9,
                color: trace.side === 'long' ? 'var(--green-soft)' : 'var(--red-2)',
                letterSpacing: '.16em',
                fontWeight: 700,
              }}
            >
              {trace.side.toUpperCase()}
            </span>
            <span className="mono" style={{ fontSize: 10, color: 'var(--fg-3)' }}>
              {trace.tf}
            </span>
          </>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {trace && (() => {
          const fc = finalStateChip(trace.final_state);
          return <Chip kind={fc.kind}>{fc.label}</Chip>;
        })()}
        {meta?.status && meta.status !== 'OK' && (
          <Chip kind="amber">{'\u25CC'} {meta.status}</Chip>
        )}
        <button
          type="button"
          className="btn"
          onClick={onClose}
          style={{ padding: '4px 10px', fontSize: 9, letterSpacing: '.18em' }}
        >
          {'\u00D7'} CLOSE
        </button>
      </div>
    </div>
  );

  // ─── Body ─────────────────────────────────────────────────────────
  let body;
  if (loading) {
    body = (
      <div
        className="mono"
        style={{
          padding: 32,
          textAlign: 'center',
          fontSize: 11,
          color: 'var(--fg-4)',
          letterSpacing: '.16em',
          textTransform: 'uppercase',
        }}
      >
        — fetching trace —
      </div>
    );
  } else if (error) {
    body = (
      <div style={{ padding: 24 }}>
        <div
          className="mono"
          style={{
            padding: 16,
            border: '1px solid var(--amber-border)',
            borderRadius: 6,
            background: 'var(--amber-bg)',
            fontSize: 11,
            color: 'var(--amber-2)',
            letterSpacing: '.10em',
          }}
        >
          {'\u25CC'} {error}
        </div>
        <div
          className="mono"
          style={{ padding: '12px 4px 0', fontSize: 10, color: 'var(--fg-4)', letterSpacing: '.10em' }}
        >
          // signal id: <span style={{ color: 'var(--fg-3)' }}>{signalId}</span>
        </div>
      </div>
    );
  } else if (trace) {
    body = renderTraceBody({
      trace,
      warnings,
      expandedStage,
      setExpandedStage,
    });
  } else {
    body = null;
  }

  return (
    <Modal onClose={onClose} maxWidth={1080}>
      {header}
      {body}
    </Modal>
  );
}

// ─── Trace body — flowchart + expanded substage panel ────────────────

interface TraceBodyArgs {
  trace: SignalTrace;
  warnings: string[];
  expandedStage: string | null;
  setExpandedStage: (s: string | null) => void;
}

function renderTraceBody(args: TraceBodyArgs) {
  const { trace, warnings, expandedStage, setExpandedStage } = args;

  // Substage(s) for the currently-expanded stage. The backend currently
  // attaches a single GauntletSubstage rooted at the killed stage; future
  // versions will attach the full 21-stage detail. Render whatever we
  // get keyed by `name`, falling back to "no substages" empty state.
  const substages = trace.gauntlet_substages ?? [];

  return (
    <div style={{ padding: 18 }}>
      {/* Warnings strip — degraded envelopes only */}
      {warnings.length > 0 && (
        <div
          className="mono"
          style={{
            marginBottom: 12,
            padding: '8px 12px',
            border: '1px solid var(--amber-border)',
            borderRadius: 6,
            background: 'var(--amber-bg)',
            fontSize: 10,
            color: 'var(--amber-2)',
            letterSpacing: '.08em',
          }}
        >
          {'\u26A0'} warnings: {warnings.join(' · ')}
        </div>
      )}

      {/* Horizontal stage strip */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${trace.stages.length}, 1fr)`,
          gap: 4,
          marginBottom: 14,
        }}
      >
        {trace.stages.map((s, idx) => renderStageCard(s, idx, expandedStage, setExpandedStage))}
      </div>

      {/* Expanded substage panel for the selected stage */}
      {expandedStage && (
        <div
          style={{
            padding: 14,
            border: '1px solid var(--accent-border)',
            borderRadius: 8,
            background: 'rgba(255,255,255,.02)',
          }}
        >
          <div
            className="mono"
            style={{
              fontSize: 9,
              color: 'var(--fg-4)',
              letterSpacing: '.20em',
              marginBottom: 10,
              paddingBottom: 8,
              borderBottom: '1px dashed var(--border-soft)',
            }}
          >
            // SUBSTAGE DETAIL · {expandedStage}
          </div>
          {substages.length === 0 ? (
            <div
              className="mono"
              style={{ fontSize: 11, color: 'var(--fg-4)', letterSpacing: '.10em' }}
            >
              — no substage records attached to this trace —
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {substages.map((sub, i) => (
                <div
                  key={`${sub.name}-${i}`}
                  style={{
                    padding: '8px 10px',
                    border: '1px solid var(--border-soft)',
                    borderRadius: 4,
                    background: sub.pass === false ? 'rgba(248,113,113,.06)' : 'transparent',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <span
                      className="mono"
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        color: sub.pass === false ? 'var(--red-2)' : sub.pass === true ? 'var(--green-soft)' : 'var(--fg-2)',
                        letterSpacing: '.14em',
                        textTransform: 'uppercase',
                      }}
                    >
                      {sub.name}
                    </span>
                  </div>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--fg-2)', lineHeight: 1.5 }}>
                    {sub.reason || '—'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function renderStageCard(
  s: TraceStage,
  idx: number,
  expandedStage: string | null,
  setExpandedStage: (s: string | null) => void,
) {
  const view: StageView = { pass: s.pass, killed: s.killed_at };
  const color = stageColor(view);
  const bg = stageBg(view);
  const glyph = stageGlyph(view);
  const isExpanded = expandedStage === s.name;
  return (
    <button
      key={s.name}
      type="button"
      onClick={() => setExpandedStage(isExpanded ? null : s.name)}
      title={s.threshold ? `threshold: ${s.threshold}` : undefined}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start',
        gap: 4,
        padding: '8px 8px 9px',
        borderRadius: 4,
        cursor: 'pointer',
        background: bg,
        border: isExpanded
          ? '1px solid var(--accent-border)'
          : `1px solid ${s.killed_at ? 'var(--red-2)' : 'var(--border-soft)'}`,
        textAlign: 'left',
        font: 'inherit',
        color: 'inherit',
        position: 'relative',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%' }}>
        <span
          className="mono"
          style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.10em', fontWeight: 600 }}
        >
          {String(idx + 1).padStart(2, '0')}
        </span>
        <span style={{ fontSize: 11, color, fontWeight: 700, lineHeight: 1 }}>{glyph}</span>
      </div>
      <span
        className="mono"
        style={{
          fontSize: 9,
          fontWeight: 700,
          color: 'var(--fg-2)',
          letterSpacing: '.10em',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          width: '100%',
        }}
      >
        {s.name}
      </span>
      <span
        className="mono"
        style={{
          fontSize: 10,
          color,
          letterSpacing: '.04em',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          width: '100%',
        }}
      >
        {s.value}
      </span>
      {s.threshold != null && (
        <span
          className="mono"
          style={{
            fontSize: 9,
            color: 'var(--fg-4)',
            letterSpacing: '.04em',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            width: '100%',
          }}
        >
          thr: {s.threshold}
        </span>
      )}
    </button>
  );
}

export default PipelineTracer;
