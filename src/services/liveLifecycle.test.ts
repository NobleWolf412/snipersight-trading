import { afterEach, describe, expect, it, vi } from 'vitest';
import { liveSessionNeedsAttention, liveShutdownMessage, liveTradingService, type LiveLifecycle, type LiveTradingStatus } from './liveTradingService';
import { paperTradingService, type PaperTradingStatus } from './paperTradingService';
import { fetchActiveSession } from './activeSession';

const recovery = (changes: Partial<LiveLifecycle> = {}): LiveLifecycle => ({
  phase: 'recovering', entry_admission_enabled: false, recovery_required: true,
  account_state: 'unknown', scope: 'phemex:swap:USDT', observed_at: null,
  reset_allowed: false, unresolved_requests: [], unmanaged_symbols: [], account_open_orders: [], reason: null,
  ...changes,
});

afterEach(() => vi.restoreAllMocks());

describe('live execution lifecycle consumers', () => {
  it.each(['stopped', 'kill_switched', 'error'])('keeps unresolved %s visible to routes and beacon', (status) => {
    expect(liveSessionNeedsAttention({ status, lifecycle: recovery() })).toBe(true);
    expect(liveSessionNeedsAttention({ status, session_id: 'legacy-session' })).toBe(true);
  });

  it('keeps startup visible and releases a confirmed finished session', () => {
    expect(liveSessionNeedsAttention({ status: 'idle', lifecycle: recovery({ phase: 'starting' }) })).toBe(true);
    expect(liveSessionNeedsAttention({ status: 'stopped', lifecycle: recovery({ phase: 'stopped', recovery_required: false, account_state: 'flat_confirmed' }) })).toBe(false);
    expect(liveSessionNeedsAttention({ status: 'idle', session_id: null })).toBe(false);
  });

  it('does not claim closure from kill status or missing lifecycle data', () => {
    expect(liveShutdownMessage()).toContain('not been confirmed');
    expect(liveShutdownMessage(recovery())).toContain('unconfirmed');
    expect(liveShutdownMessage(recovery({ account_state: 'exposure_present' }))).toContain('remain');
    expect(liveShutdownMessage(recovery({ phase: 'stopped', account_state: 'flat_confirmed', recovery_required: false, observed_at: '2026-10-07T12:00:00Z' })))
      .toBe('USDT contracts observed flat at 2026-10-07T12:00:00Z.');
  });

  it('prioritizes unresolved live execution over running paper', async () => {
    vi.spyOn(liveTradingService, 'getStatus').mockResolvedValue({ status: 'stopped', trading_mode: 'live', lifecycle: recovery() } as LiveTradingStatus);
    vi.spyOn(paperTradingService, 'getStatus').mockResolvedValue({ status: 'running' } as PaperTradingStatus);
    const result = await fetchActiveSession();
    expect(result.service).toBe(liveTradingService);
    expect(result.isLive).toBe(true);
    expect(result.canKillSwitch).toBe(true);
  });

  it('allows running paper priority once live shutdown is settled', async () => {
    vi.spyOn(liveTradingService, 'getStatus').mockResolvedValue({ status: 'stopped', lifecycle: recovery({ phase: 'stopped', account_state: 'flat_confirmed', recovery_required: false }) } as LiveTradingStatus);
    vi.spyOn(paperTradingService, 'getStatus').mockResolvedValue({ status: 'running' } as PaperTradingStatus);
    expect((await fetchActiveSession()).service).toBe(paperTradingService);
  });

  it.each(['stop', 'killSwitch', 'reset'] as const)('surfaces backend %s conflict reasons', async (action) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 409, json: async () => ({ detail: 'Recovery still pending' }) }));
    try {
      await expect(liveTradingService[action]()).rejects.toThrow('Recovery still pending');
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
