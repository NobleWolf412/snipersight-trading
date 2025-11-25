// Simple verification script for scanHistoryService without test framework.
import { scanHistoryService } from './scanHistoryService.js';

class LocalStorageMock {
  constructor(){ this.store = {}; }
  getItem(k){ return Object.prototype.hasOwnProperty.call(this.store,k) ? this.store[k] : null; }
  setItem(k,v){ this.store[k]=v; }
  removeItem(k){ delete this.store[k]; }
  clear(){ this.store={}; }
}

globalThis.localStorage = new LocalStorageMock();

function addDummy(mode, score, generated, rejected){
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

function assert(condition, message){
  if(!condition){
    console.error('FAIL:', message);
    process.exitCode = 1;
  } else {
    console.log('PASS:', message);
  }
}

// Test save & retrieval
addDummy('recon',65,4,6);
addDummy('strike',60,2,3);
const all = scanHistoryService.getAllScans();
assert(all.length === 2, 'Two scans saved');
assert(all[0].mode === 'strike', 'Latest scan first');

// Test statistics
addDummy('surgical',70,5,5);
const stats = scanHistoryService.getStatistics();
assert(stats.totalScans === 3, 'Stats totalScans=3');
assert(stats.totalSignals === 11, 'Stats totalSignals=11');
assert(stats.totalRejections === 14, 'Stats totalRejections=14');

// Test clear recent (simulate older timestamp)
const history = scanHistoryService.getAllScans();
// Make second item old (2h ago)
history[1].timestamp = new Date(Date.now() - 2*60*60*1000).toISOString();
localStorage.setItem('scan-history', JSON.stringify(history));
const deleted = scanHistoryService.clearRecentScans(1); // should remove only recent entries within last hour
assert(deleted >= 1, 'Deleted recent scans');
const remaining = scanHistoryService.getAllScans();
assert(remaining.some(s => s.mode === 'strike') || remaining.some(s => s.mode === 'recon'), 'Older scan remains');

console.log('\nVerification complete.');
