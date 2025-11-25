import { describe, it, expect, beforeEach } from 'vitest';
import { scanHistoryService } from './scanHistoryService';

// Minimal localStorage mock
class LocalStorageMock {
  store: Record<string,string> = {};
  getItem(key: string) { return Object.prototype.hasOwnProperty.call(this.store,key) ? this.store[key] : null; }
  setItem(key: string, value: string) { this.store[key] = value; }
  removeItem(key: string) { delete this.store[key]; }
  clear() { this.store = {}; }
}

globalThis.localStorage = new LocalStorageMock() as any;

describe('scanHistoryService', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  function addDummy(mode: string, score: number, generated: number, rejected: number) {
    return scanHistoryService.saveScan({
      mode,
      profile: 'test',
      timeframes: ['1h','4h'],
      symbolsScanned: generated + rejected + 5,
      signalsGenerated: generated,
      signalsRejected: rejected,
      effectiveMinScore: score,
      rejectionBreakdown: {
        low_confluence: rejected,
        no_data: 0,
        risk_validation: 0,
        no_trade_plan: 0,
        errors: 0
      },
      results: []
    });
  }

  it('saves scans and retrieves all', () => {
    addDummy('recon',65,4,6);
    addDummy('strike',60,2,3);
    const all = scanHistoryService.getAllScans();
    expect(all.length).toBe(2);
    expect(all[0].mode).toBe('strike'); // last saved is first (unshift)
    expect(all[1].mode).toBe('recon');
  });

  it('computes statistics correctly', () => {
    addDummy('recon',65,4,6); // success rate 40%
    addDummy('strike',60,2,3); // success rate 40%
    addDummy('surgical',70,5,5); // success rate 50%
    const stats = scanHistoryService.getStatistics();
    expect(stats.totalScans).toBe(3);
    expect(stats.totalSignals).toBe(11);
    expect(stats.totalRejections).toBe(14);
    expect(stats.avgSignalsPerScan).toBeCloseTo(11/3,1);
    // avg success rate = (40 + 40 + 50)/3 = 43.33
    expect(stats.avgSuccessRate).toBeCloseTo(43.3,1);
    expect(stats.topModes.length).toBeGreaterThan(0);
  });

  it('clears recent scans', () => {
    addDummy('recon',65,4,6);
    // simulate older scan by manipulating timestamp
    const old = addDummy('strike',60,2,3);
    const all = scanHistoryService.getAllScans();
    // modify second entry timestamp to 2 hours ago
    const twoHoursAgo = new Date(Date.now() - 2*60*60*1000).toISOString();
    all[1].timestamp = twoHoursAgo;
    localStorage.setItem('scan-history', JSON.stringify(all));

    // Clear last 1 hour (should remove recent first entry only)
    const deleted = scanHistoryService.clearRecentScans(1);
    expect(deleted).toBe(1);
    const remaining = scanHistoryService.getAllScans();
    expect(remaining.length).toBe(1);
    expect(remaining[0].id).toBe(old.id);
  });
});
