import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import type { ScanHistoryEntry } from '@/services/scanHistoryService';
import type { SignalLogEntry, ScannerMode } from '@/utils/api';

vi.mock('@/components/hud', () => ({ Chip: ({ children }: any) => children, SectionHead: () => null }));
import { GauntletBreakdown, classifyStage } from './GauntletBreakdown';
import { buildCategories, failureSampleText, RejectionPanel } from './RejectionPanel';
import { summarizeRejections } from './ScanController';
import { renderStackedBar } from './ConfluenceBreakdown';

describe('rejection evidence does not invent totals or counterfactuals', () => {
  it.each([
    { rejectionSummary: { by_reason: { future_gate: 2 } } },
    { rejectionBreakdown: { future_gate: 2 } },
  ])('exposes new and legacy rejection causes before opening sample evidence: %j', evidence => {
    const entry = { symbolsScanned: 3, signalsRejected: 2, ...evidence } as unknown as ScanHistoryEntry;
    const html = renderToStaticMarkup(createElement(RejectionPanel, { entry }));
    expect(html).toContain('aria-label="Recorded rejection reasons"');
    expect(html).toContain('FUTURE GATE');
    expect(html).not.toContain('<dialog');
  });

  it('keeps an accepted scan with feature failures out of rejection summaries', () => {
    const entry = { symbolsScanned: 1, signalsGenerated: 1, signalsRejected: 0,
      rejectionSummary: { total_rejected: 0, by_reason: { features: 1 },
        features_breakdown: { indicator_failures: { count: 1,
          samples: [{ symbol: 'BTC/USDT', timeframe: '5m', error: 'MACD failed' }] } } },
    } as unknown as ScanHistoryEntry;
    const categories = buildCategories(entry);
    expect(categories.find(c => c.key === 'FEATURES')?.totalCount).toBe(1);
    expect(categories.find(c => c.key === 'OTHER')?.totalCount).toBe(0);
    expect(summarizeRejections(entry.rejectionSummary)).toBeNull();
    expect(renderToStaticMarkup(createElement(RejectionPanel, { entry }))).toContain('0 run rejections');
  });

  it('excludes legacy feature occurrences while preserving real unknown gate counts', () => {
    expect(summarizeRejections({ by_reason: { features: 9, future_gate: 2 } }))
      .toEqual({ total: 2, byReason: [{ reason: 'future_gate', count: 2, examples: [] }] });
  });

  it('retains the timeframe and error in feature sample text without rendering objects', () => {
    expect(failureSampleText({ symbol: 'BTC/USDT', timeframe: '5m', error: 'MACD failed' }))
      .toBe('5m · MACD failed');
    expect(failureSampleText({ stage: 'service', error: 'SMC stopped' })).toBe('service · SMC stopped');
    expect(failureSampleText({ error: { arbitrary: true } })).toBe('');
  });

  it('classifies post-plan price rejection as planning in both views', () => {
    const entry = { rejectionSummary: { by_reason: { post_plan_revalidation: 1 } } } as unknown as ScanHistoryEntry;
    const categories = buildCategories(entry);
    expect(categories.find(c => c.key === 'PLANNER')?.totalCount).toBe(1);
    expect(categories.find(c => c.key === 'OTHER')?.totalCount).toBe(0);
    expect(classifyStage({ result: 'filtered', reason_type: 'post_plan_revalidation' } as SignalLogEntry))
      .toBe('NO_TRADE_PLAN');
  });

  it('keeps universe/feature observations outside the reported run rejection count', () => {
    const entry = {
      symbolsScanned: 20, signalsRejected: 7,
      rejectionSummary: { total_rejected: 7, by_reason: { no_data: 2, structural_anchor: 3, future_gate: 2 },
        features_breakdown: { smc_rejections: { count: 5, samples: [] } } },
      universeSnapshot: { total_candidates: 100, drops_by_reason: { non_perp: 30 } },
    } as unknown as ScanHistoryEntry;
    const html = renderToStaticMarkup(createElement(RejectionPanel, { entry }));
    expect(html).toContain('7 run rejections');
    const other = buildCategories(entry).find(c => c.key === 'OTHER')!;
    expect(other.totalCount).toBe(5);
    expect(other.subBuckets.map(b => b.reason)).toContain('future_gate');
  });

  it('keeps legacy stored rejection reasons visible without a newer summary', () => {
    const entry = { signalsRejected: 3, rejectionBreakdown: { risk_validation: 1, future_gate: 2 } } as unknown as ScanHistoryEntry;
    const categories = buildCategories(entry);
    expect(categories.find(c => c.key === 'PLANNER')?.totalCount).toBe(1);
    expect(categories.find(c => c.key === 'OTHER')?.totalCount).toBe(2);
  });

  it('counts unclassified log rejections in the bottleneck denominator', () => {
    const signals = [
      { id: '1', result: 'filtered', reason_type: 'low_confluence', confluence: 65 },
      { id: '2', result: 'filtered', reason_type: 'future_gate', confluence: 0 },
    ] as SignalLogEntry[];
    const html = renderToStaticMarkup(createElement(GauntletBreakdown, { signals }));
    expect(html).toContain('50% of logged rejects');
  });

  it('labels threshold arithmetic as a comparison, not a mode replay', () => {
    const signals = [{ id: '1', result: 'filtered', reason_type: 'low_confluence', confluence: 69 }] as SignalLogEntry[];
    const scannerModes = [{ name: 'strike', min_confluence_score: 68 }] as ScannerMode[];
    const html = renderToStaticMarkup(createElement(GauntletBreakdown, { signals, scannerModes, currentModeName: 'stealth' }));
    expect(html).toContain('THRESHOLD COMPARISON');
    expect(html).toContain('Modes also change scoring, gates and timeframes');
    expect(html).not.toContain('would-pass');
    expect(html).not.toContain('threshold may be too high');
  });

  it('keeps evidence requirements in confluence without suggesting a lower cutoff', () => {
    const entry = { rejectionSummary: { by_reason: { evidence_requirements: 2, low_confluence: 1 } } } as unknown as ScanHistoryEntry;
    const categories = buildCategories(entry);
    const confluence = categories.find(c => c.key === 'CONFLUENCE')!;
    expect(confluence.totalCount).toBe(3);
    expect(confluence.subBuckets.map(bucket => bucket.reason)).toEqual(['low_confluence', 'evidence_requirements']);
    expect(categories.find(c => c.key === 'OTHER')?.totalCount).toBe(0);
    const signals = [{ id: '1', result: 'filtered', reason_type: 'evidence_requirements', confluence: 85,
      reason: 'Evidence requirements: missing structural confirmation' }] as SignalLogEntry[];
    expect(classifyStage(signals[0])).toBe('EVIDENCE_REQUIREMENTS');
    const html = renderToStaticMarkup(createElement(GauntletBreakdown, { signals,
      scannerModes: [{ name: 'strike', min_confluence_score: 65 }] as ScannerMode[], currentModeName: 'overwatch' }));
    expect(html).toContain('EVIDENCE REQUIREMENTS');
    expect(html).not.toContain('THRESHOLD COMPARISON');
    expect(html).not.toContain('Logged scores did not meet');
  });

  it('shows weighted contributions without zero-weight raw diagnostics', () => {
    const html = renderToStaticMarkup(renderStackedBar([
      { name: 'Raw Order Block', avg_score: 100, avg_weight: 0, avg_weighted_score: 0, sample_count: 1 },
      { name: 'Entry anchor', avg_score: 90, avg_weight: .2, avg_weighted_score: 18, sample_count: 1 },
      { name: 'Participation', avg_score: 0, avg_weight: .1, avg_weighted_score: 0, sample_count: 1 },
    ], 'AGGREGATE'));
    expect(html).not.toContain('Raw Order Block');
    expect(html).toContain('Entry anchor');
    expect(html).toContain('Participation');
    expect(html).toContain('18.0');
    expect(html).toContain('WEIGHTED BASE · BEFORE ADJUSTMENTS');
  });
});
