import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import type { ScanHistoryEntry } from '@/services/scanHistoryService';
import type { SignalLogEntry, ScannerMode } from '@/utils/api';

vi.mock('@/components/hud', () => ({ Chip: ({ children }: any) => children, SectionHead: () => null }));
import { GauntletBreakdown } from './GauntletBreakdown';
import { buildCategories, RejectionPanel } from './RejectionPanel';

describe('rejection evidence does not invent totals or counterfactuals', () => {
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
});
