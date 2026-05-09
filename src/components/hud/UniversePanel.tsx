/**
 * UniversePanel — qualified + dropped pair list (Phase 3g.ii.e)
 *
 * Plan reference: peppy-sniffing-owl §3e.
 *
 *   "NEW: Universe panel — small card '184 pairs · 12 dropped · last
 *    refresh 04:18' reading /api/scanner/universe. Click → modal with
 *    full list and drop reasons."
 *
 * Layout
 * ──────
 *   ┌── UNIVERSE ────────────────── ◇ 184 PAIRS · 12 DROPPED ──┐
 *   │  LAST REFRESH 04:18 · TOTAL 196                          │
 *   │  [ OPEN FULL LIST → ]                                    │
 *   └──────────────────────────────────────────────────────────┘
 *
 *   Modal (on click):
 *     - Two columns: QUALIFIED (left) and DROPPED (right).
 *     - Qualified row: symbol · sector chip · tags chips.
 *     - Dropped row: symbol · reason chip (stable_base, non_perp, etc.).
 *
 * Real-data wiring
 * ────────────────
 *   - Polls `/api/scanner/universe` once on mount + every 60s. The
 *     orchestrator refreshes once per scan cycle so 60s polling cannot
 *     miss a refresh by more than one cycle.
 *   - Empty universe (counts.total_candidates === 0) renders an amber
 *     `◌ awaiting` chip — same convention as ConfluenceBreakdown.
 *   - Surfaces `metadata.status !== 'OK'` and `warnings[]`.
 *
 * Synthetic-but-disclosed: none. Panel renders ONLY backend data.
 *
 * Symmetry (CLAUDE.md §10 #3)
 * ───────────────────────────
 *   - Direction-agnostic. The universe is symbol-level; bull/bear
 *     symmetry is enforced upstream in pair_selection. This panel
 *     just displays the resulting set.
 *
 * Determinism for snapshots
 * ─────────────────────────
 *   - Iteration order is the wire order (backend sorts qualified by
 *     bucket, dropped by reason).
 *   - `last_refresh_ts` is formatted as a 5-char `HH:MM` slice from
 *     UTC ISO string — deterministic for any given epoch.
 *
 * StrictMode safety
 * ─────────────────
 *   - Polling loop captures a `cancelled` flag; cleanup clears the
 *     pending timer.
 */
import { useEffect, useMemo, useState } from 'react';
import {
  api,
  type DroppedPair,
  type ResponseMetadata,
  type Universe,
  type UniversePair,
} from '@/utils/api';
import { Chip } from './Chip';
import { Modal } from './Modal';
import { SectionHead } from './SectionHead';

// Polling cadence — universe refreshes once per scan cycle (~30-60s);
// 60s is enough to surface stale refresh timestamps in operator view.
const POLL_MS = 60_000;

function formatRefresh(ts: number | null): string {
  if (ts == null) return '—';
  // ts is a unix epoch (seconds). Format as UTC HH:MM.
  const d = new Date(ts * 1000);
  if (Number.isNaN(d.getTime())) return '—';
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const mm = String(d.getUTCMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
}

export function UniversePanel() {
  const [universe, setUniverse] = useState<Universe | null>(null);
  const [meta, setMeta] = useState<ResponseMetadata | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      const res = await api.getUniverse();
      if (cancelled) return;
      setLoaded(true);
      if (res.error || !res.data) {
        setError(res.error || 'no response body');
        setUniverse(null);
      } else {
        setMeta(res.data.metadata);
        setWarnings(res.data.warnings ?? []);
        if (res.data.data) {
          setUniverse(res.data.data);
          setError(null);
        } else {
          setError(res.data.metadata.reason || 'universe unavailable');
          setUniverse(null);
        }
      }
      if (!cancelled) {
        timer = setTimeout(tick, POLL_MS);
      }
    };

    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  const counts = universe?.counts;
  const refreshLabel = useMemo(
    () => formatRefresh(universe?.last_refresh_ts ?? null),
    [universe?.last_refresh_ts],
  );

  // ─── Empty / loading / error states ──────────────────────────────
  if (!loaded) {
    return (
      <section className="panel" style={{ padding: 14 }}>
        <SectionHead title="Universe" right={<Chip kind="amber">{'\u25CC'} loading</Chip>} />
        <div className="mono" style={emptyMsgStyle}>— fetching universe —</div>
      </section>
    );
  }

  if (error || !universe) {
    return (
      <section className="panel" style={{ padding: 14 }}>
        <SectionHead
          title="Universe"
          right={<Chip kind="amber">{'\u25CC'} {meta?.status ?? 'error'}</Chip>}
        />
        <div className="mono" style={emptyMsgStyle}>
          — {error ?? 'no universe data'} —
        </div>
      </section>
    );
  }

  if (!counts || counts.total_candidates === 0) {
    return (
      <section className="panel" style={{ padding: 14 }}>
        <SectionHead title="Universe" right={<Chip kind="amber">{'\u25CC'} awaiting</Chip>} />
        <div className="mono" style={emptyMsgStyle}>
          — universe empty · pair selection has not run —
        </div>
      </section>
    );
  }

  // ─── Populated render ────────────────────────────────────────────
  return (
    <>
      <section className="panel" style={{ padding: 14 }}>
        <SectionHead
          title="Universe"
          right={
            <div style={{ display: 'flex', gap: 6 }}>
              <Chip>{counts.qualified} PAIRS</Chip>
              <Chip kind="red">{counts.dropped} DROPPED</Chip>
              {meta?.status && meta.status !== 'OK' && (
                <Chip kind="amber">{'\u25CC'} {meta.status}</Chip>
              )}
            </div>
          }
        />
        <div style={{ padding: '10px 4px 4px' }}>
          {warnings.length > 0 && (
            <div className="mono" style={warnStripStyle}>
              {'\u26A0'} warnings: {warnings.join(' · ')}
            </div>
          )}
          <div
            className="mono"
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 14,
              fontSize: 10,
              color: 'var(--fg-3)',
              letterSpacing: '.10em',
              marginBottom: 10,
            }}
          >
            <span>LAST REFRESH <span style={{ color: 'var(--fg-2)', fontWeight: 700 }}>{refreshLabel}</span></span>
            <span>TOTAL <span style={{ color: 'var(--fg-2)', fontWeight: 700 }}>{counts.total_candidates}</span></span>
            <span>QUALIFIED <span style={{ color: 'var(--green-soft)', fontWeight: 700 }}>{counts.qualified}</span></span>
            <span>DROPPED <span style={{ color: 'var(--red-2)', fontWeight: 700 }}>{counts.dropped}</span></span>
          </div>
          <button
            type="button"
            className="btn"
            onClick={() => setModalOpen(true)}
            style={{ width: '100%', fontSize: 10, letterSpacing: '.16em' }}
          >
            OPEN FULL LIST →
          </button>
        </div>
      </section>

      {modalOpen && (
        <Modal onClose={() => setModalOpen(false)} maxWidth={920}>
          {renderModalBody(universe, refreshLabel, () => setModalOpen(false))}
        </Modal>
      )}
    </>
  );
}

// ─── Modal body ──────────────────────────────────────────────────────

function renderModalBody(u: Universe, refreshLabel: string, onClose: () => void) {
  // Group dropped pairs by reason for a tidy summary at the top.
  const byReason = new Map<string, DroppedPair[]>();
  for (const d of u.dropped) {
    const arr = byReason.get(d.reason) ?? [];
    arr.push(d);
    byReason.set(d.reason, arr);
  }
  const reasonRows = Array.from(byReason.entries()).sort(
    (a, b) => b[1].length - a[1].length,
  );

  return (
    <div style={{ padding: 18 }}>
      <div
        className="sec-head"
        style={{ marginBottom: 14, paddingBottom: 10, borderBottom: '1px solid var(--border-soft)' }}
      >
        <div className="sec-title"><span className="dot" /> Universe — Full Pair List</div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <Chip>{u.counts.qualified} QUALIFIED</Chip>
          <Chip kind="red">{u.counts.dropped} DROPPED</Chip>
          <Chip kind="amber">REFRESH {refreshLabel}</Chip>
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

      {/* Drop-reason summary */}
      {reasonRows.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div className="mono" style={subTitleStyle}>// DROPPED — REASON SUMMARY</div>
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 6,
              marginTop: 6,
            }}
          >
            {reasonRows.map(([reason, pairs]) => (
              <Chip key={reason} kind="red">
                {reason} · {pairs.length}
              </Chip>
            ))}
          </div>
        </div>
      )}

      {/* Two-column qualified + dropped lists */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 14,
          maxHeight: 480,
        }}
      >
        <div style={listColStyle}>
          <div className="mono" style={subTitleStyle}>
            // QUALIFIED · {u.qualified.length}
          </div>
          {u.qualified.length === 0 ? (
            <div className="mono" style={emptyColStyle}>— none —</div>
          ) : (
            u.qualified.map((p) => renderQualifiedRow(p))
          )}
        </div>
        <div style={listColStyle}>
          <div className="mono" style={subTitleStyle}>
            // DROPPED · {u.dropped.length}
          </div>
          {u.dropped.length === 0 ? (
            <div className="mono" style={emptyColStyle}>— none —</div>
          ) : (
            u.dropped.map((d) => renderDroppedRow(d))
          )}
        </div>
      </div>
    </div>
  );
}

function renderQualifiedRow(p: UniversePair) {
  return (
    <div key={p.symbol} style={rowStyle}>
      <div
        className="mono"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontSize: 11,
          color: 'var(--fg-2)',
          fontWeight: 700,
          letterSpacing: '.08em',
        }}
      >
        <span style={{ color: 'var(--green-soft)' }}>{p.symbol}</span>
        {p.sector && (
          <span
            className="mono"
            style={{
              fontSize: 9,
              color: 'var(--fg-3)',
              letterSpacing: '.10em',
              fontWeight: 500,
            }}
          >
            · {p.sector.toUpperCase()}
          </span>
        )}
      </div>
      {p.tags.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
          {p.tags.map((t) => (
            <Chip key={t}>{t}</Chip>
          ))}
        </div>
      )}
    </div>
  );
}

function renderDroppedRow(d: DroppedPair) {
  return (
    <div key={`${d.symbol}-${d.reason}`} style={rowStyle}>
      <div
        className="mono"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontSize: 11,
          color: 'var(--fg-2)',
          fontWeight: 700,
          letterSpacing: '.08em',
        }}
      >
        <span style={{ color: 'var(--red-2)' }}>{d.symbol}</span>
        <Chip kind="red">{d.reason}</Chip>
      </div>
    </div>
  );
}

// ─── Shared styles ───────────────────────────────────────────────────

const emptyMsgStyle = {
  padding: 14,
  textAlign: 'center' as const,
  fontSize: 10,
  color: 'var(--fg-4)',
  letterSpacing: '.14em',
};

const warnStripStyle = {
  marginBottom: 10,
  padding: '6px 10px',
  border: '1px solid var(--amber-border)',
  borderRadius: 4,
  background: 'var(--amber-bg)',
  fontSize: 9,
  color: 'var(--amber-2)',
  letterSpacing: '.08em',
};

const subTitleStyle = {
  fontSize: 9,
  color: 'var(--fg-4)',
  letterSpacing: '.20em',
  marginBottom: 6,
};

const listColStyle = {
  border: '1px solid var(--border-soft)',
  borderRadius: 4,
  padding: 10,
  overflowY: 'auto' as const,
  maxHeight: 480,
  background: 'rgba(0,0,0,.20)',
};

const emptyColStyle = {
  padding: 14,
  textAlign: 'center' as const,
  fontSize: 10,
  color: 'var(--fg-4)',
  letterSpacing: '.14em',
};

const rowStyle = {
  padding: '6px 4px',
  borderBottom: '1px dashed var(--border-soft)',
};

export default UniversePanel;
