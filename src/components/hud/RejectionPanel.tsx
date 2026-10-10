/**
 * RejectionPanel — Scanner page §11 observability surface (3a').
 *
 * Renders six per-category chips (UNIVERSE / DATA / CRITICAL_TF / FEATURES /
 * CONFLUENCE / PLANNER) sourced from the most recent ScanHistoryEntry, plus
 * the parallel `universeSnapshot` captured at scan completion. Click any
 * chip to expand its sample failure rows.
 *
 * Data sources per chip:
 *   UNIVERSE      — universeSnapshot.drops_by_reason (4 sub-reasons:
 *                   stable_base / non_perp / bucket_excluded / limit_exhausted).
 *                   Backed by /api/scanner/universe; latest-snapshot
 *                   semantics (NOT per-run) — see docstring note below.
 *   DATA          — missing candle/market context counts + details
 *   CRITICAL_TF   — rejectionSummary.by_reason.missing_critical_tf + details
 *   FEATURES      — rejectionSummary.features_breakdown (indicator_failures +
 *                   smc_rejections counts + samples) — backend extension A
 *   CONFLUENCE    — numeric cutoff and evidence-requirement failures + details
 *   PLANNER       — rejectionSummary.by_reason.no_trade_plan +
 *                   .risk_validation, merged + details
 *
 * §12 output ordering:
 *   1. Summary chips (per-category count + emphasis tone)
 *   2. Click-expand structured detail (sample rows per reason)
 *   3. Raw data — when nothing's available, render zero-state copy that
 *      points the operator at where to look next.
 *
 * Semantic gap acknowledged (per brief):
 *   The universe snapshot is *latest-snapshot* in the backend cache, not
 *   strictly per-run. 95% case alignment matches; CycleAuditStrip surfaces
 *   the cycle timing so a stale snapshot is observable. Documented here
 *   so future readers don't assume per-run isolation.
 *
 * Zero-candidates state (briefing item 5):
 *   When universeSnapshot.total_candidates === 0 OR the most recent run
 *   has symbolsScanned === 0, render an explicit copy line directing the
 *   operator to /api/scanner/universe drop reasons rather than a silent
 *   empty panel. §11 boundary.
 *
 * Direction-agnostic — the rejection pipeline is direction-agnostic at
 * stage level (each stage rejects independent of bull/bear). Per-symbol
 * details may carry direction-specific reasons but the chip aggregates
 * are intentionally unscoped.
 */
import { Modal } from './Modal';
import { useState, type ReactNode } from 'react';
import type {
  ScanHistoryEntry,
  ScanRejectionSummary,
  RejectionSampleRecord,
} from '@/services/scanHistoryService';
import { Chip, type ChipKind } from './Chip';

// ─── Category model ───────────────────────────────────────────────────────

type CategoryKey =
  | 'UNIVERSE'
  | 'DATA'
  | 'CRITICAL_TF'
  | 'FEATURES'
  | 'CONFLUENCE'
  | 'PLANNER'
  | 'OTHER';

interface CategorySubBucket {
  reason: string;
  count: number;
  samples: RejectionSampleRecord[];
}

interface Category {
  key: CategoryKey;
  label: string;
  description: string;
  totalCount: number;
  subBuckets: CategorySubBucket[]; // empty for categories with no sub-detail
}

// ─── Category builders ────────────────────────────────────────────────────
// Each builder pulls from rejectionSummary / universeSnapshot and emits a
// stable Category record (totalCount=0 + empty subBuckets when the source
// data has nothing). Stable shape per §11 — never a missing chip just
// because a category is empty.

function buildUniverse(entry: ScanHistoryEntry): Category {
  const snap = entry.universeSnapshot;
  if (!snap) {
    return {
      key: 'UNIVERSE',
      label: 'UNIVERSE',
      description: 'pair_selection drops · latest snapshot',
      totalCount: 0,
      subBuckets: [],
    };
  }
  const reasons = Object.entries(snap.drops_by_reason ?? {});
  const totalCount = reasons.reduce((s, [, c]) => s + c, 0);
  const subBuckets = reasons
    .filter(([, c]) => c > 0)
    .map(([reason, count]) => ({
      reason,
      count,
      // Universe samples are bare symbol strings, not record objects.
      // Wrap them into the RejectionSampleRecord shape used by the panel.
      samples: (snap.drops_by_reason_samples?.[reason] ?? []).map(
        (s): RejectionSampleRecord => ({ symbol: s, reason }),
      ),
    }))
    .sort((a, b) => b.count - a.count);
  return {
    key: 'UNIVERSE',
    label: 'UNIVERSE',
    description: 'pair_selection drops · latest snapshot',
    totalCount,
    subBuckets,
  };
}

function pickSingleReason(
  summary: ScanRejectionSummary | undefined,
  reasonKey: string,
): CategorySubBucket {
  const count = summary?.by_reason?.[reasonKey] ?? 0;
  const samples = (summary?.details?.[reasonKey] ?? []).slice(0, 5);
  return { reason: reasonKey, count, samples };
}

function buildData(entry: ScanHistoryEntry): Category {
  const subBuckets = ['no_data', 'market_context_unavailable', 'historical_context_unavailable']
    .map((reason) => pickSingleReason(entry.rejectionSummary, reason))
    .filter((bucket) => bucket.count > 0);
  return {
    key: 'DATA',
    label: 'DATA',
    description: 'required candle and market-context inputs',
    totalCount: subBuckets.reduce((total, bucket) => total + bucket.count, 0),
    subBuckets,
  };
}

function buildCriticalTf(entry: ScanHistoryEntry): Category {
  const sub = pickSingleReason(entry.rejectionSummary, 'missing_critical_tf');
  return {
    key: 'CRITICAL_TF',
    label: 'CRITICAL_TF',
    description: 'required-TF window missing for mode',
    totalCount: sub.count,
    subBuckets: sub.count > 0 ? [sub] : [],
  };
}

function buildFeatures(entry: ScanHistoryEntry): Category {
  // 3a' backend A: features_breakdown is the parallel field carrying
  // clean indicator + smc per-subcategory counts and samples. Falls back
  // to zero-shape when older history entries lack it.
  const fb = entry.rejectionSummary?.features_breakdown;
  const ind = fb?.indicator_failures ?? { count: 0, samples: [] };
  const smc = fb?.smc_rejections ?? { count: 0, samples: [] };
  const subBuckets: CategorySubBucket[] = [];
  if (ind.count > 0) {
    subBuckets.push({
      reason: 'indicator_failures',
      count: ind.count,
      samples: ind.samples ?? [],
    });
  }
  if (smc.count > 0) {
    subBuckets.push({
      reason: 'smc_rejections',
      count: smc.count,
      samples: smc.samples ?? [],
    });
  }
  return {
    key: 'FEATURES',
    label: 'FEATURES',
    description: 'indicator + SMC diagnostics; may overlap run rejections',
    totalCount: ind.count + smc.count,
    subBuckets,
  };
}

function buildConfluence(entry: ScanHistoryEntry): Category {
  const subBuckets = ['low_confluence', 'evidence_requirements']
    .map(reason => pickSingleReason(entry.rejectionSummary, reason))
    .filter(bucket => bucket.count > 0);
  return {
    key: 'CONFLUENCE',
    label: 'CONFLUENCE',
    description: 'numeric cutoff and required setup evidence',
    totalCount: subBuckets.reduce((total, bucket) => total + bucket.count, 0),
    subBuckets,
  };
}

function buildPlanner(entry: ScanHistoryEntry): Category {
  // PLANNER aggregates two near-adjacent reasons in the pipeline:
  //   no_trade_plan    — orchestrator couldn't construct a plan
  //   risk_validation  — plan rejected by risk manager / late price check
  const plannerSub = pickSingleReason(entry.rejectionSummary, 'no_trade_plan');
  const riskSub = pickSingleReason(entry.rejectionSummary, 'risk_validation');
  const revalidationSub = pickSingleReason(entry.rejectionSummary, 'post_plan_revalidation');
  const subBuckets: CategorySubBucket[] = [];
  if (plannerSub.count > 0) subBuckets.push(plannerSub);
  if (riskSub.count > 0) subBuckets.push(riskSub);
  if (revalidationSub.count > 0) subBuckets.push(revalidationSub);
  return {
    key: 'PLANNER',
    label: 'PLANNER',
    description: 'trade-plan construction · risk gate',
    totalCount: plannerSub.count + riskSub.count + revalidationSub.count,
    subBuckets,
  };
}

export function failureSampleText(sample: RejectionSampleRecord): string {
  const reason = typeof sample.reason === 'string' ? sample.reason
    : typeof sample.error === 'string' ? sample.error : '';
  const timeframe = typeof sample.timeframe === 'string' ? sample.timeframe : '';
  const stage = typeof sample.stage === 'string' ? sample.stage : '';
  return [timeframe || stage, reason].filter(Boolean).join(' · ');
}

export function buildCategories(entry: ScanHistoryEntry): Category[] {
  const summary = entry.rejectionSummary ?? {
    total_rejected: entry.signalsRejected, by_reason: entry.rejectionBreakdown ?? {},
  };
  const source = { ...entry, rejectionSummary: summary };
  const categories = [
    buildUniverse(source), buildData(source), buildCriticalTf(source),
    buildFeatures(source), buildConfluence(source), buildPlanner(source),
  ];
  const mapped = new Set(categories.filter(c => c.key !== 'UNIVERSE' && c.key !== 'FEATURES')
    .flatMap(c => c.subBuckets.map(bucket => bucket.reason)));
  const other = Object.entries(summary.by_reason ?? {})
    .filter(([reason, count]) => count > 0 && reason !== 'features' && !mapped.has(reason))
    .map(([reason]) => pickSingleReason(summary, reason));
  categories.push({ key: 'OTHER', label: 'OTHER GATES / ERRORS',
    description: 'Other recorded run rejection reasons',
    totalCount: other.reduce((sum, bucket) => sum + bucket.count, 0), subBuckets: other });
  return categories;
}

// ─── Chip tone selection ──────────────────────────────────────────────────
// Tone is count-based but capped — we never paint the entire panel red just
// because some category fired. amber for "non-zero", red only when the
// category dominates the total (>=50% of all rejections).

function chipTone(count: number, total: number): ChipKind | undefined {
  if (count === 0) return undefined; // base grey
  if (total > 0 && count / total >= 0.5) return 'red';
  return 'amber';
}

// ─── Friendly reason labels (per RejectionPanel-internal mapping) ─────────

const REASON_PRETTY: Record<string, string> = {
  // Universe stage
  stable_base: 'STABLE BASE',
  non_perp: 'NON-PERP MARKET',
  bucket_excluded: 'BUCKET EXCLUDED',
  limit_exhausted: 'SELECTION CAP HIT',
  // Pipeline stages
  no_data: 'DATA FETCH FAILED',
  market_context_unavailable: 'CURRENT MARKET CONTEXT UNAVAILABLE',
  historical_context_unavailable: 'HISTORICAL CONTEXT UNAVAILABLE',
  missing_critical_tf: 'CRITICAL TF MISSING',
  indicator_failures: 'INDICATOR COMPUTE FAIL',
  smc_rejections: 'SMC PATTERN MISSED',
  low_confluence: 'BELOW MIN SCORE',
  evidence_requirements: 'REQUIRED EVIDENCE NOT MET',
  no_trade_plan: 'PLAN UNAVAILABLE',
  risk_validation: 'RISK GATE',
};

function prettyReason(key: string): string {
  return REASON_PRETTY[key] ?? key.replace(/_/g, ' ').toUpperCase();
}

// ─── Panel ────────────────────────────────────────────────────────────────

interface RejectionPanelProps {
  entry: ScanHistoryEntry | null;
}

export function RejectionPanel({ entry }: RejectionPanelProps) {
  const [expandedKey, setExpandedKey] = useState<CategoryKey | null>(null);

  // No scan yet — render a stable placeholder so the panel slot has
  // consistent height in the layout grid. Direct operator to the run
  // button rather than rendering a silent blank.
  if (!entry) {
    return (
      <section className="panel" style={{ padding: 0 }}>
        <SectionHeader>// REJECTION BREAKDOWN</SectionHeader>
        <div
          className="mono"
          style={{
            padding: '24px 22px',
            color: 'var(--fg-4)',
            fontSize: 11,
            letterSpacing: '.18em',
            textTransform: 'uppercase',
          }}
        >
          // awaiting first scan — press ▶ run scan to populate
        </div>
      </section>
    );
  }

  // Zero-candidates state: universe filtered the entire input set OR the
  // run itself scanned 0 symbols. Either way, panel rejects rendering
  // pipeline-stage chips and instead points the operator at the universe
  // snapshot. §11 — don't render silent empty.
  const universeTotalCandidates = entry.universeSnapshot?.total_candidates ?? null;
  const isZeroCandidates =
    entry.symbolsScanned === 0 ||
    (universeTotalCandidates !== null &&
      universeTotalCandidates > 0 &&
      (entry.universeSnapshot?.drops_by_reason
        ? Object.values(entry.universeSnapshot.drops_by_reason).reduce(
            (s, c) => s + c,
            0,
          ) >= universeTotalCandidates
        : false));

  const categories = buildCategories(entry);
  const grandTotal = entry.rejectionSummary?.total_rejected ?? entry.signalsRejected ?? 0;

  return (
    <section className="panel" style={{ padding: 0 }}>
      <SectionHeader right={`${grandTotal} run rejections`}>
        // REJECTION BREAKDOWN
      </SectionHeader>
      <div style={{ padding: '14px 18px 18px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* §12 ordering: summary chips first */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {categories.map((cat) => {
            const separate = cat.key === 'UNIVERSE' || cat.key === 'FEATURES';
            const tone = separate ? (cat.totalCount > 0 ? 'amber' : undefined) : chipTone(cat.totalCount, grandTotal);
            const isOpen = expandedKey === cat.key;
            const disabled = cat.totalCount === 0 && cat.subBuckets.length === 0;
            return (
              <button
                key={cat.key}
                onClick={() => setExpandedKey(isOpen ? null : cat.key)}
                disabled={disabled}
                type="button"
                aria-haspopup="dialog"
                aria-label={cat.label + ' rejection details'}
                title={cat.description}
                style={{
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  cursor: disabled ? 'default' : 'pointer',
                  opacity: disabled ? 0.45 : 1,
                  boxShadow: isOpen ? '0 0 0 1px var(--accent)' : undefined,
                  borderRadius: 4,
                }}
              >
                <Chip kind={tone}>
                  {cat.label} · {cat.totalCount}
                </Chip>
              </button>
            );
          })}
        </div>

        <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
          Universe and feature counts are separate diagnostics and may overlap run rejections.
        </div>

        {/* Zero-candidates negative state */}
        {isZeroCandidates && (
          <div
            className="mono"
            style={{
              padding: '10px 12px',
              border: '1px solid var(--amber-border, rgba(251,191,36,.35))',
              borderRadius: 4,
              background: 'rgba(0,0,0,.4)',
              color: 'var(--amber)',
              fontSize: 11,
              letterSpacing: '.14em',
              textTransform: 'uppercase',
            }}
          >
            ◌ no symbols scanned, or the latest universe snapshot excludes all candidates.
            Review the universe details and scan status.
          </div>
        )}

        <div className="rejection-reasons" aria-label="Recorded rejection reasons">
          {categories.flatMap(cat => cat.subBuckets.filter(sub => sub.count > 0).map(sub =>
            <div key={cat.key + ':' + sub.reason}><span>{prettyReason(sub.reason)}</span><strong className="mono">{sub.count}</strong></div>
          ))}
        </div>
        {/* Sample evidence opens separately; the reasons remain visible above. */}
        {expandedKey && <Modal label={expandedKey + ' rejection details'} onClose={() => setExpandedKey(null)} maxWidth={850}>
          <div className="dialog-panel-content">{(() => {
            const cat = categories.find((c) => c.key === expandedKey);
            if (!cat) return null;
            if (cat.subBuckets.length === 0) {
              return (
                <DetailWrapper title={`${cat.label} · 0 rejections`}>
                  <div
                    className="mono"
                    style={{
                      padding: '10px 12px',
                      color: 'var(--fg-4)',
                      fontSize: 10,
                      letterSpacing: '.14em',
                      textTransform: 'uppercase',
                    }}
                  >
                    // no rejections in this category for the last run
                  </div>
                </DetailWrapper>
              );
            }
            return (
              <DetailWrapper title={`${cat.label} · ${cat.totalCount} rejections`}>
                {cat.subBuckets.map((sub) => (
                  <div
                    key={sub.reason}
                    style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '10px 12px', borderTop: '1px dashed var(--border-soft)' }}
                  >
                    <div
                      className="mono"
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        fontSize: 10,
                        color: 'var(--fg-2, var(--fg))',
                        letterSpacing: '.12em',
                      }}
                    >
                      <span>{prettyReason(sub.reason)}</span>
                      <span style={{ color: 'var(--fg-3)' }}>{sub.count}</span>
                    </div>
                    {sub.samples.length === 0 ? (
                      <div
                        className="mono"
                        style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.14em' }}
                      >
                        // samples not retained for this reason
                      </div>
                    ) : (
                      <ul
                        className="mono"
                        style={{
                          listStyle: 'none',
                          padding: 0,
                          margin: 0,
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 2,
                          fontSize: 10,
                          color: 'var(--fg-3)',
                          letterSpacing: '.06em',
                        }}
                      >
                        {sub.samples.slice(0, 5).map((s, i) => (
                          <li key={i}>
                            {(s.symbol ?? '—') as ReactNode}
                            {s.score != null && (
                              <span style={{ color: 'var(--fg-4)', marginLeft: 8 }}>
                                score {s.score}
                              </span>
                            )}
                            {s.threshold != null && (
                              <span style={{ color: 'var(--fg-4)', marginLeft: 4 }}>
                                / ≥ {s.threshold}
                              </span>
                            )}
                            {failureSampleText(s) && failureSampleText(s) !== sub.reason && (
                              <span style={{ color: 'var(--fg-4)', marginLeft: 6 }}>
                                · {failureSampleText(s)}
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </DetailWrapper>
            );
          })()}</div></Modal>}

        {/* §12 ordering: raw data row — link to the operator's hand-curl
             path for forensic dives. Always present, low-emphasis. */}
        <div
          className="mono"
          style={{
            fontSize: 9,
            color: 'var(--fg-4)',
            letterSpacing: '.16em',
            textTransform: 'uppercase',
          }}
        >
          // raw: /api/scanner/runs/{'{'}run_id{'}'} · /api/scanner/diagnostics · /api/scanner/universe
        </div>
      </div>
    </section>
  );
}

// ─── Tiny local atoms ─────────────────────────────────────────────────────

function SectionHeader({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div
      className="sec-head"
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '10px 18px',
        borderBottom: '1px dashed var(--border-soft)',
      }}
    >
      <span
        className="mono sec-title"
        style={{ fontSize: 10, color: 'var(--accent)', letterSpacing: '.2em', textTransform: 'uppercase' }}
      >
        {children}
      </span>
      {right && (
        <span
          className="mono"
          style={{ fontSize: 10, color: 'var(--fg-4)', letterSpacing: '.18em', textTransform: 'uppercase' }}
        >
          {right}
        </span>
      )}
    </div>
  );
}

function DetailWrapper({ title, children }: { title: ReactNode; children: ReactNode }) {
  return (
    <div
      style={{
        border: '1px solid var(--border-soft)',
        borderRadius: 4,
        background: 'rgba(0,0,0,.35)',
      }}
    >
      <div
        className="mono"
        style={{
          padding: '8px 12px',
          fontSize: 10,
          color: 'var(--accent)',
          letterSpacing: '.18em',
          textTransform: 'uppercase',
          borderBottom: '1px solid var(--border-soft)',
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}
