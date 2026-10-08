import { describe, expect, it, vi } from 'vitest';
import type { SignalLogEntry } from '@/utils/api';
import type { ScanHistoryEntry } from '@/services/scanHistoryService';

// These tests exercise classification and counts, without mounting the app.
vi.mock('@/components/hud', () => ({ Chip: () => null, SectionHead: () => null }));
import { classifyStage } from './GauntletBreakdown';
import { buildCategories } from './RejectionPanel';

describe('missing market inputs remain visible', () => {
  it.each(['market_context_unavailable', 'historical_context_unavailable'])('classifies %s before scoring', (reason_type) => {
    expect(classifyStage({ result: 'filtered', reason_type } as SignalLogEntry)).toBe('MARKET_CONTEXT');
  });

  it('includes missing context in DATA counts and preserves its explanation', () => {
    const entry = {
      rejectionSummary: {
        by_reason: { no_data: 1, market_context_unavailable: 3, historical_context_unavailable: 2 },
        details: { market_context_unavailable: [{ symbol: 'BTC/USDT', reason: 'Required current dominance is unavailable' }] },
      },
    } as unknown as ScanHistoryEntry;
    const data = buildCategories(entry).find((category) => category.key === 'DATA')!;
    expect(data.totalCount).toBe(6);
    expect(data.subBuckets.find((bucket) => bucket.reason === 'market_context_unavailable')?.samples[0].reason)
      .toBe('Required current dominance is unavailable');
  });

  it('preserves the zero-data shape for older history', () => {
    const data = buildCategories({} as ScanHistoryEntry).find((category) => category.key === 'DATA')!;
    expect(data.totalCount).toBe(0);
    expect(data.subBuckets).toEqual([]);
  });
});
