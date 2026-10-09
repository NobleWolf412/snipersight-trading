import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ScanRunService, scanIsBusy } from './scanRunService';
import { ScanHistoryService } from './scanHistoryService';
import { ReplaySessionController } from './replaySessionController';
import { FreshFeed, observationDeadline } from './freshFeed';
import { fetchActiveSession } from './activeSession';
import { liveTradingService } from './liveTradingService';
import { paperTradingService } from './paperTradingService';
import { api } from '@/utils/api';
import { convertSignalToScanResult } from '@/utils/mockData';
import { classifyPhemexHealth } from '@/components/hud/PhemexStatusPill';

const deferred = <T = any>() => {
  let resolve!: (value: T) => void, reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
const flush = async () => { for (let i = 0; i < 16; i++) await Promise.resolve(); };
const mode = { name: 'stealth', profile: 'stealth_balanced', timeframes: ['4h', '1h'], min_confluence_score: 70, description: 'test' };
const activeKey = 'sniper.scanner.active.v2';
let storage: Storage;
beforeEach(() => {
  vi.useFakeTimers(); vi.setSystemTime(new Date('2026-10-09T12:00:00Z'));
  const items = new Map<string, string>();
  storage = { getItem: (key: string) => items.get(key) ?? null, setItem: (k: string, v: string) => { items.set(k, v); }, removeItem: (k: string) => { items.delete(k); }, clear: () => items.clear() } as Storage;
  vi.stubGlobal('localStorage', storage);
});
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function scanner() {
  let id = '';
  const client = {
    createScanRun: vi.fn(async (params) => { id = params.request_id; return { data: { run_id: id, created_at: new Date().toISOString(), status: 'queued' } }; }),
    getScanRun: vi.fn(async () => ({ data: { run_id: id, created_at: new Date().toISOString(), status: 'running', progress: 1, total: 10 } } as any)),
    cancelScanRun: vi.fn(async () => ({ data: {} } as any)),
  };
  const history = new ScanHistoryService();
  return { client, history, owner: new ScanRunService(client as any, history, () => storage) };
}
describe('application-owned scan workflow', () => {
  it('saves chart source from the completed run and its request, preserving contract identity', async () => {
    const w = scanner();
    w.client.getScanRun.mockResolvedValue({ data: { run_id: 'r', status: 'completed', created_at: '2026-10-09T12:00:00Z', progress: 1, total: 1,
      metadata: { exchange: 'bybit' }, signals: [{ symbol: '1000PEPEUSDT', original_symbol: '1000PEPE/USDT:USDT', direction: 'LONG', targets: [] }] } });
    await w.owner.start(mode, { exchange: 'bybit', market_type: 'swap' }); await flush();
    const [receipt] = w.history.getAllScans();
    expect(receipt.exchange).toBe('bybit'); expect(receipt.marketType).toBe('swap');
    expect(receipt.results[0].original_symbol).toBe('1000PEPE/USDT:USDT');
  });
  it('does not carry a restored terminal run stop into a new run', async () => {
    const w = scanner();
    storage.setItem(activeKey, JSON.stringify({ runId: 'old', mode, acknowledged: true, cancelRequested: true }));
    w.client.getScanRun.mockResolvedValueOnce({ error: 'expired', httpStatus: 404 });
    w.owner.resume(); await flush(); await w.owner.start(mode); await flush();
    expect(w.owner.getSnapshot().status).toBe('running');
    expect(w.client.cancelScanRun).not.toHaveBeenCalled();
  });
  it.each([true, false])('restores stop intent while creation is acknowledged=%s', async acknowledged => {
    const w = scanner(); const id = '66b2f001-bfd4-41a5-8ec4-19f402a22b10';
    storage.setItem(activeKey, JSON.stringify({ runId: id, mode, params: { request_id: id }, acknowledged, cancelRequested: true }));
    if (!acknowledged) w.client.getScanRun.mockResolvedValueOnce({ error: 'not created yet', httpStatus: 404 });
    w.owner.resume(); await flush();
    expect(w.client.cancelScanRun).toHaveBeenCalledWith(id);
    expect(JSON.parse(storage.getItem(activeKey)!).cancelRequested).toBe(true);
    expect(w.owner.getSnapshot().status).toBe('cancelling');
  });
  it('reuses an unacknowledged identity when GET races a delayed creation', async () => {
    const w = scanner(); const id = '66b2f001-bfd4-41a5-8ec4-19f402a22b10';
    storage.setItem(activeKey, JSON.stringify({ runId: id, mode, params: { request_id: id }, acknowledged: false }));
    w.client.getScanRun.mockResolvedValueOnce({ error: 'not created yet', httpStatus: 404 });
    w.owner.resume(); await flush();
    expect(w.client.createScanRun).toHaveBeenCalledWith(expect.objectContaining({ request_id: id }));
    expect(w.owner.getSnapshot().runId).toBe(id); expect(scanIsBusy(w.owner.getSnapshot().status)).toBe(true);
    await w.owner.start(mode); expect(w.client.createScanRun).toHaveBeenCalledTimes(1);
  });
  it('keeps a rejected stop visible after successful running-status polls', async () => {
    const w = scanner(); await w.owner.start(mode); await flush();
    w.client.cancelScanRun.mockResolvedValueOnce({ error: 'request rejected' });
    await w.owner.cancel(); await flush(); await vi.advanceTimersByTimeAsync(2000);
    expect(w.owner.getSnapshot().error).toContain('Stop not confirmed');
    expect(scanIsBusy(w.owner.getSnapshot().status)).toBe(true);
    await w.owner.cancel(); await flush();
    expect(w.owner.getSnapshot().status).toBe('cancelling');
    expect(w.owner.getSnapshot().error).toBeNull();
  });
  it.each(['BTCUSDT', 'BTC/USDT', 'BTC/USDT:USDT'])('preserves pair and absent plan evidence for %s', symbol => {
    const result = convertSignalToScanResult({ symbol, stop_loss: null });
    expect(result.pair).toBe('BTC/USDT'); expect(result.classification).toBe('UNKNOWN');
    expect(result.stopLoss).toBeNull(); expect(result.confidenceScore).toBeUndefined();
  });
  it('does not display healthy or idle status after a failed health/status request', () => {
    expect(classifyPhemexHealth({}, true, 'offline').severity).toBe('amber');
    expect(classifyPhemexHealth(null, false, 'offline').severity).toBe('amber');
  });
  it('uses one API prefix for scanner cooldowns', async () => {
    const request = vi.fn(async (..._args: any[]) => new Response(JSON.stringify({ active: [], count: 0, next_expiry_seconds: null }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', request);
    expect((await api.getActiveCooldowns()).data?.count).toBe(0);
    expect(request.mock.calls[0][0]).toBe(`${api.baseURL}/cooldowns`);
    await api.getSignalTrace('BTC/USDT');
    await api.getConfluenceDistribution();
    await api.getKillZoneStatus();
    expect(request.mock.calls.slice(1).map(args => args[0])).toEqual([
      `${api.baseURL}/signals/BTC%2FUSDT/trace`,
      `${api.baseURL}/signals/confluence/distribution?n=200&direction=all`,
      `${api.baseURL}/sessions/kill-zone`,
    ]);
  });
  it('owns a delayed start after the page unsubscribes and blocks duplicate clicks', async () => {
    const w = scanner(), response = deferred(); w.client.createScanRun.mockReturnValueOnce(response.promise);
    const off = w.owner.subscribe(vi.fn()); const start = w.owner.start(mode); off();
    const id = JSON.parse(storage.getItem(activeKey)!).runId;
    await w.owner.start(mode); expect(w.client.createScanRun).toHaveBeenCalledTimes(1);
    response.resolve({ data: { run_id: id, created_at: new Date().toISOString(), status: 'queued' } });
    await start; await flush(); expect(scanIsBusy(w.owner.getSnapshot().status)).toBe(true);
    expect(w.client.getScanRun).toHaveBeenCalledWith(id, { silent: true });
  });
  it('reconciles a lost POST response using the persisted request identity', async () => {
    const w = scanner(); w.client.createScanRun.mockResolvedValueOnce({ error: 'response lost' } as any);
    await w.owner.start(mode); await flush();
    const id = JSON.parse(storage.getItem(activeKey)!).runId;
    expect(w.client.getScanRun).toHaveBeenCalledWith(id, { silent: true });
    expect(w.owner.getSnapshot().status).toBe('running');
    expect(JSON.parse(storage.getItem(activeKey)!).acknowledged).toBe(true);
    expect(w.client.createScanRun).toHaveBeenCalledTimes(1);
  });
  it('keeps temporary disconnection busy, then recovers without starting another job', async () => {
    const w = scanner(); w.client.getScanRun.mockResolvedValueOnce({ error: 'offline' });
    await w.owner.start(mode); await flush(); expect(w.owner.getSnapshot().status).toBe('disconnected');
    await w.owner.start(mode); expect(w.client.createScanRun).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(10000); expect(w.owner.getSnapshot().status).toBe('running');
  });
  it('releases a restored job only on confirmed404', async () => {
    const w = scanner(); storage.setItem(activeKey, JSON.stringify({ runId: 'old', mode }));
    w.client.getScanRun.mockResolvedValueOnce({ error: 'gone', httpStatus: 404 });
    w.owner.resume(); await flush();
    expect(scanIsBusy(w.owner.getSnapshot().status)).toBe(false); expect(storage.getItem(activeKey)).toBeNull();
    await w.owner.start(mode); expect(w.client.createScanRun).toHaveBeenCalledTimes(1);
  });
  it('preserves old result time and writes one receipt when reconnecting repeatedly', async () => {
    const w = scanner(); const old = '2026-10-08T10:00:00Z';
    storage.setItem(activeKey, JSON.stringify({ runId: 'completed', mode }));
    w.client.getScanRun.mockResolvedValue({ data: { run_id: 'completed', status: 'completed', progress: 1, total: 1, created_at: old, completed_at: old,
      signals: [{ symbol: 'BTCUSDT', direction: 'LONG', score: 80, targets: [], timeframe: '1h' }], metadata: { mode: 'strike', effective_min_score: 65 } } });
    w.owner.resume(); await flush(); w.owner.reconnect(); await flush();
    const [receipt] = w.history.getAllScans(); expect(w.history.getAllScans()).toHaveLength(1);
    expect(receipt.mode).toBe('strike'); expect(receipt.timestamp).toBe(old); expect(receipt.results[0].timestamp).toBe(old);
  });
  it('keeps completed results visible when storage fails', async () => {
    const w = scanner(); vi.spyOn(storage, 'setItem').mockImplementation(() => { throw new Error('quota'); });
    w.client.getScanRun.mockResolvedValue({ data: { run_id: 'r', status: 'completed', created_at: new Date().toISOString(), progress: 1, total: 1, signals: [] } });
    await w.owner.start(mode); await flush();
    expect(w.history.getAllScans()).toHaveLength(1); expect(w.owner.getSnapshot().error).toContain('could not be saved');
  });
  it('disabling auto cancels the pending restart', async () => {
    const w = scanner(); w.owner.setAutoScan(true);
    w.client.getScanRun.mockResolvedValue({ data: { run_id: 'r', status: 'completed', created_at: new Date().toISOString(), progress: 1, total: 1, signals: [] } });
    await w.owner.start(mode); await flush(); w.owner.setAutoScan(false);
    await vi.advanceTimersByTimeAsync(6000); expect(w.client.createScanRun).toHaveBeenCalledTimes(1);
  });
  it('does not claim cancellation when DELETE fails and fences late errors from prior jobs', async () => {
    const w = scanner(); await w.owner.start(mode); await flush();
    const deletion = deferred(); w.client.cancelScanRun.mockReturnValueOnce(deletion.promise);
    const cancelled = w.owner.cancel();
    w.client.getScanRun.mockResolvedValueOnce({ data: { status: 'completed', created_at: new Date().toISOString(), signals: [] } });
    w.owner.reconnect(); await flush(); await w.owner.start(mode); await flush();
    const next = w.owner.getSnapshot().runId;
    deletion.resolve({ error: 'late rejection' }); await cancelled; await flush();
    expect(w.owner.getSnapshot().runId).toBe(next); expect(w.owner.getSnapshot().status).toBe('running');
  });
});

function replay() {
  let index = -1, count = 0;
  const client = {
    createReplaySession: vi.fn(async () => ({ data: { session_id: `s${++count}`, total_bars: 5 } } as any)),
    getReplaySession: vi.fn(async () => ({ data: { current_index: index } })),
    stepReplay: vi.fn(async (_id: string, n: number) => { index = Math.max(0, Math.min(4, index + n)); return { data: { index } } as any; }),
    deleteReplaySession: vi.fn(async () => ({ data: { ok: true } })),
  };
  return { client, owner: new ReplaySessionController(client as any), setIndex: (value: number) => { index = value; } };
}
const replayParams = { symbol: 'BTC/USDT', mode: 'stealth', window_start: '2026-10-01', window_end: '2026-10-02' };
describe('replay lifecycle', () => {
  it('rewinds an ended replay and allows playback again', async () => {
    const w = replay(); await w.owner.load(replayParams); await w.owner.seek(4);
    expect(w.owner.getSnapshot().playState).toBe('ended'); await w.owner.reset();
    expect(w.owner.getSnapshot().step?.index).toBe(0); w.owner.togglePlay(); expect(w.owner.getSnapshot().playState).toBe('playing');
  });
  it('serializes rapid absolute seeks using the current server cursor', async () => {
    const w = replay(); await w.owner.load(replayParams);
    await Promise.all([w.owner.seek(4), w.owner.seek(1), w.owner.seek(3)]);
    expect(w.owner.getSnapshot().step?.index).toBe(3);
  });
  it('reconciles a server-committed step with a lost response before the next seek', async () => {
    const w = replay(); await w.owner.load(replayParams);
    w.client.stepReplay.mockImplementationOnce(async () => { w.setIndex(3); return { error: 'lost' }; });
    await w.owner.stepBy(3); expect(w.owner.getSnapshot().playState).toBe('paused');
    await w.owner.seek(1); expect(w.owner.getSnapshot().step?.index).toBe(1);
  });
  it('publishes intermediate candles and bounds forward work to one bar per request', async () => {
    const w = replay(); await w.owner.load(replayParams);
    const indices: number[] = [];
    w.owner.subscribe(() => { const i = w.owner.getSnapshot().step?.index; if (i != null) indices.push(i); });
    w.client.stepReplay.mockClear(); await w.owner.seek(4);
    expect(w.client.stepReplay.mock.calls.map(call => call[1])).toEqual([1, 1, 1, 1]);
    expect(indices).toEqual(expect.arrayContaining([1, 2, 3, 4]));
    w.client.stepReplay.mockClear(); await w.owner.seek(2);
    expect(w.client.stepReplay.mock.calls.map(call => call[1])).toEqual([-4, 1, 1]);
    expect(w.owner.getSnapshot().step?.index).toBe(2);
    expect(w.owner.getSnapshot().moveTarget).toBeNull();
  });
  it('stops a long move after its current request and reconciles on the next action', async () => {
    const w = replay(); await w.owner.load(replayParams);
    const pending = deferred(); w.client.stepReplay.mockReturnValueOnce(pending.promise);
    w.client.stepReplay.mockClear(); const moving = w.owner.seek(4); await flush();
    expect(w.owner.getSnapshot().moveTarget).toBe(4);
    w.owner.cancelMove(); w.setIndex(1); pending.resolve({ data: { index: 1 } }); await moving;
    expect(w.client.stepReplay).toHaveBeenCalledTimes(1);
    expect(w.owner.getSnapshot().step?.index).toBe(0);
    expect(w.owner.getSnapshot().moveTarget).toBeNull();
    await w.owner.seek(2); expect(w.owner.getSnapshot().step?.index).toBe(2);
  });
  it('does not resume playback when the ended replay rewind was cancelled', async () => {
    const w = replay(); await w.owner.load(replayParams); await w.owner.seek(4);
    const pending = deferred(); w.client.stepReplay.mockReturnValueOnce(pending.promise);
    w.owner.togglePlay(); await flush(); expect(w.owner.getSnapshot().moveTarget).toBe(0);
    w.owner.cancelMove(); w.setIndex(0); pending.resolve({ data: { index: 0 } }); await flush();
    expect(w.owner.getSnapshot().playState).toBe('paused');
    expect(w.owner.getSnapshot().moveTarget).toBeNull();
  });
  it('closes a late-created session after escape without restoring it', async () => {
    const w = replay(), response = deferred(); w.client.createReplaySession.mockReturnValueOnce(response.promise);
    const load = w.owner.load(replayParams); await flush(); await w.owner.close();
    response.resolve({ data: { session_id: 'late', total_bars: 5 } }); await load;
    expect(w.client.deleteReplaySession).toHaveBeenCalledWith('late'); expect(w.owner.getSnapshot().session).toBeNull();
  });
  it('cleans up the active session and does not display it after failed replacement', async () => {
    const w = replay(); await w.owner.load(replayParams);
    w.client.createReplaySession.mockResolvedValueOnce({ error: 'failed' }); await w.owner.load(replayParams);
    expect(w.client.deleteReplaySession).toHaveBeenCalledWith('s1'); expect(w.owner.getSnapshot().session).toBeNull();
    expect(w.owner.getSnapshot().errorMsg).toContain('failed');
  });
  it('surfaces first-frame failure and can recover by stepping', async () => {
    const w = replay(); w.client.stepReplay.mockResolvedValueOnce({ error: 'first failed' }); await w.owner.load(replayParams);
    expect(w.owner.getSnapshot().errorMsg).toContain('first failed'); await w.owner.stepBy(1);
    expect(w.owner.getSnapshot().step?.index).toBe(0);
  });
  it('does not automatically retry a failed replay mutation in the API wrapper', async () => {
    const request = vi.fn(async () => { throw new TypeError('lost response'); }); vi.stubGlobal('fetch', request);
    const response = await api.stepReplay('one', 1); expect(response.error).toBeTruthy(); expect(request).toHaveBeenCalledTimes(1);
  });
});

describe('market feed expiry and retry', () => {
  it('clears the previous snapshot immediately during a slow retry', async () => {
    const request = vi.fn(async () => ({ data: { expires: Date.now() + 1000 } }));
    const owner = new FreshFeed(request, data => data.expires); await owner.refresh();
    expect(owner.getSnapshot().data).not.toBeNull(); const pending = deferred(); request.mockReturnValueOnce(pending.promise);
    const retry = owner.refresh(); await vi.advanceTimersByTimeAsync(2000); expect(owner.getSnapshot().data).toBeNull();
    pending.resolve({ error: 'offline' }); await retry; expect(owner.getSnapshot().error).toContain('offline');
  });
  it('expires independent feeds independently and ignores responses after disposal', async () => {
    const a = new FreshFeed(async () => ({ data: { deadline: Date.now() + 100 } }), d => d.deadline);
    const b = new FreshFeed(async () => ({ data: { deadline: Date.now() + 10000 } }), d => d.deadline);
    await Promise.all([a.refresh(), b.refresh()]); await vi.advanceTimersByTimeAsync(101);
    expect(a.getSnapshot().data).toBeNull(); expect(b.getSnapshot().data).not.toBeNull();
    const pending = deferred(); const c = new FreshFeed(() => pending.promise, () => Date.now() + 5000);
    const request = c.refresh(); c.stop(); pending.resolve({ data: {} }); await request; expect(c.getSnapshot().data).toBeNull();
  });
  it.each([undefined, 'invalid', '2027-01-01T00:00:00Z'])('rejects missing/future observation %s', observed => {
    expect(Number.isNaN(observationDeadline(observed, 1000, Date.now()))).toBe(true);
  });
});

describe('paper session ownership', () => {
  it('keeps recovery and completed paper history on the paper service', async () => {
    vi.spyOn(liveTradingService, 'getStatus').mockResolvedValue({ status: 'idle', session_id: null } as any);
    const paper = vi.spyOn(paperTradingService, 'getStatus').mockResolvedValue({ status: 'error', session_id: 'p', recovery_required: true } as any);
    expect((await fetchActiveSession()).service).toBe(paperTradingService);
    paper.mockResolvedValue({ status: 'stopped', session_id: 'p' } as any);
    expect((await fetchActiveSession('paper')).service).toBe(paperTradingService);
    paper.mockRejectedValue(new Error('offline')); await expect(fetchActiveSession('paper')).rejects.toThrow('Paper session unavailable');
  });
});
