import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  chartMarketSymbol, chartTimeframe, closedPlay, formatPrice, parsePlayCandles, pendingPlay, playMetrics, positionPlay,
  selectBotPlay, setupPlay, snapToCandle, type PlayLevel,
} from './playInspector';
import type { LivePosition, PendingEntryOrder } from './liveTradingService';
import type { JournalTrade } from './tradeJournalService';
import { convertSignalToScanResult } from '@/utils/mockData';
import { api } from '@/utils/api';

afterEach(() => vi.unstubAllGlobals());
describe('scanner setup play evidence', () => {
  it.each(['LONG', 'SHORT'])('preserves exact %s boundaries and all targets through conversion and saved history', direction => {
    const near = direction === 'LONG' ? 3.55 : 3.4, far = direction === 'LONG' ? 3.4 : 3.55;
    const targets = direction === 'LONG' ? [3.7, 3.8, 3.9] : [3.2, 3.1, 3.0];
    const raw = { symbol: 'LITUSDT', original_symbol: 'LIT/USDT:USDT', direction, timeframe: '1h',
      entry_near: near, entry_far: far, stop_loss: direction === 'LONG' ? 3.3 : 3.6,
      targets: targets.map(level => ({ level })), timestamp: '2026-10-09T17:00:00Z' };
    const saved = JSON.parse(JSON.stringify(convertSignalToScanResult(raw)));
    const receipt = { exchange: 'phemex', marketType: 'swap', timestamp: '2026-10-09T17:01:00Z' };
    const plan = setupPlay(saved, receipt);
    expect(plan).toMatchObject({ symbol: 'LIT/USDT:USDT', direction, timeframe: '1h', timeframeRecorded: true, exchange: 'phemex', marketType: 'swap', recordedAt: raw.timestamp, warnings: [] });
    expect(plan.levels.map(level => [level.label, level.price])).toEqual([
      ['Entry near', near], ['Entry far', far], ['Stop', raw.stop_loss], ...targets.map((value, index) => [`TP${index + 1}`, value]),
    ]);
    expect(setupPlay(raw, receipt).levels).toEqual(plan.levels);
  });

  it('does not invent absent prices, provenance, or timeframe for older history', () => {
    const plan = setupPlay({ pair: 'BTC/USDT', entry_near: 1, entry_far: 1, stop_loss: 0,
      targets: [{ level: NaN }, { level: 2 }], timeframe: '1M' }, {});
    expect(plan.levels).toEqual([{ label: 'Entry', price: 1, kind: 'entry' }, { label: 'TP2', price: 2, kind: 'target' }]);
    expect(plan.exchange).toBeUndefined(); expect(plan.marketType).toBeUndefined();
    expect(plan.timeframeRecorded).toBe(false); expect(plan.warnings).toHaveLength(2);
    expect(plan.score).toBeUndefined(); expect(plan.threshold).toBeUndefined();
    expect(chartTimeframe('1D')).toBe('1d'); expect(chartTimeframe('1M')).toBeUndefined();
  });

  it.each([
    ['BTCUSDT', 'swap', 'BTC/USDT:USDT'], ['BTC/USDT', 'swap', 'BTC/USDT:USDT'],
    ['1000PEPE/USDT:USDT', 'swap', '1000PEPE/USDT:USDT'], ['ETHUSDC', 'swap', 'ETH/USDC:USDC'],
    ['BTC/USD:BTC', 'swap', 'BTC/USD:BTC'], ['BTC/USDT:USDT', 'spot', 'BTC/USDT'],
  ])('resolves %s for %s without changing contract units', (symbol, market, expected) => {
    expect(chartMarketSymbol(symbol, market)).toBe(expected);
  });

  it('rejects missing settlement instead of guessing an inverse contract', () => {
    expect(() => chartMarketSymbol('BTC/USD', 'swap')).toThrow('settlement');
    expect(() => chartMarketSymbol('unknown', 'swap')).toThrow('unavailable');
  });

  it('keeps tiny and precise saved levels round-trippable', () => {
    for (const value of [0.000000018412, 0.12345678912345678, 82525.34567891234])
      expect(Number(formatPrice(value))).toBe(value);
  });

  it('sorts, deduplicates and reads both naive and aware candle times as UTC; rejects corrupt OHLC', () => {
    const row = { open: 10, high: 12, low: 9, close: 11 };
    const candles = parsePlayCandles({ candles: [
      { ...row, timestamp: '2026-10-09T11:00:00' }, { ...row, timestamp: '2026-10-09T10:00:00Z' },
      { ...row, close: 12, timestamp: '2026-10-09T11:00:00Z' },
      { ...row, timestamp: 'invalid' }, { ...row, timestamp: '2026-10-09T12:00:00Z', high: 8 },
      { ...row, timestamp: '2026-10-09T13:00:00Z', low: 0 },
      { ...row, timestamp: '2026-10-09T14:00:00Z', close: Infinity },
    ] });
    expect(candles.map(candle => candle.time)).toEqual([Date.parse('2026-10-09T10:00:00Z') / 1000, Date.parse('2026-10-09T11:00:00Z') / 1000]);
    expect(candles[1].close).toBe(12);
    expect(() => parsePlayCandles({ candles: [] })).toThrow('No valid candles');
  });

  it('sends the selected venue, qualified contract and timeframe without falling back after errors', async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({ detail: 'Requested market is not configured' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetcher);
    const response = await api.getCandles(chartMarketSymbol('LIT/USDT', 'swap'), '4h', 160, { exchange: 'bybit', marketType: 'swap' });
    expect(fetcher).toHaveBeenCalledOnce();
    expect(fetcher.mock.calls[0][0]).toBe(`${api.baseURL}/market/candles/LIT%2FUSDT%3AUSDT?timeframe=4h&limit=160&exchange=bybit&market_type=swap`);
    expect(response.error).toBe('Requested market is not configured');
  });
});

const levels = (direction: 'LONG' | 'SHORT'): PlayLevel[] => direction === 'LONG'
  ? [{ label: 'Entry', price: 100, kind: 'entry' }, { label: 'Stop', price: 95, kind: 'stop' },
     { label: 'TP1', price: 110, kind: 'target' }, { label: 'TP2', price: 115, kind: 'target' }]
  : [{ label: 'Entry', price: 100, kind: 'entry' }, { label: 'Stop', price: 105, kind: 'stop' },
     { label: 'TP1', price: 90, kind: 'target' }, { label: 'TP2', price: 85, kind: 'target' }];

describe('play metrics', () => {
  it.each(['LONG', 'SHORT'] as const)('derives identical %s risk, R:R and reward for mirrored plans', direction => {
    const metrics = playMetrics(direction, levels(direction), 2, direction === 'LONG' ? 97 : 103);
    expect(metrics).toMatchObject({ entry: 100, riskPerUnit: 5, riskPct: 5, riskAmount: 10, bestRR: 3 });
    expect(metrics.targets.map(target => [target.rr, target.reward])).toEqual([[2, 20], [3, 30]]);
    expect(metrics.stopDistancePct).toBeCloseTo(2 / 97 * 100 * (direction === 'LONG' ? 1 : 97 / 103));
  });

  it.each(['LONG', 'SHORT'] as const)('refuses %s risk and R:R when the stop or target is on the wrong side', direction => {
    const flipped = levels(direction).map(level => level.kind === 'stop' ? { ...level, price: direction === 'LONG' ? 105 : 95 } : level);
    const metrics = playMetrics(direction, flipped, 2);
    expect(metrics.riskPerUnit).toBeUndefined(); expect(metrics.riskAmount).toBeUndefined(); expect(metrics.bestRR).toBeUndefined();
    const wrongTarget = playMetrics(direction, [...levels(direction).slice(0, 2), { label: 'TP1', price: direction === 'LONG' ? 90 : 110, kind: 'target' }], 2);
    expect(wrongTarget.targets[0]).toMatchObject({ rr: undefined, reward: undefined });
  });

  it('derives no directional metrics or side when direction is unrecognized', () => {
    const unknown = playMetrics('UNKNOWN', levels('LONG'), 2);
    expect([unknown.riskPerUnit, unknown.bestRR, unknown.riskAmount, unknown.targets[0].rr]).toEqual([undefined, undefined, undefined, undefined]);
    expect(setupPlay({ direction: 'NEUTRAL', entry: 1 }, {}).direction).toBe('UNKNOWN');
    expect(pendingPlay(pending({ direction: 'sideways' })).direction).toBe('UNKNOWN');
  });

  it('leaves size-dependent values unknown without a quantity', () => {
    expect(playMetrics('LONG', levels('LONG'))).toMatchObject({ riskAmount: undefined, bestRR: 3, stopDistancePct: undefined });
  });
});

const position = (overrides: Partial<LivePosition> = {}): LivePosition => ({
  position_id: 'p1', symbol: 'BTC/USDT:USDT', direction: 'SHORT', entry_price: 100, current_price: 98, quantity: 2,
  stop_loss: 105, unrealized_pnl: 4, unrealized_pnl_pct: 2, breakeven_active: false, trailing_active: false,
  opened_at: '2026-10-10T10:00:00Z', trade_type: 'swing', tp1: 90, tp2: 85, tp_final: 85, risk_pnl: -10,
  strategy: { mode: 'strike', strategy_gate: 65 }, ...overrides,
});
const pending = (overrides: Partial<PendingEntryOrder> = {}): PendingEntryOrder => ({
  order_id: 'o1', symbol: 'ETH/USDT:USDT', direction: 'LONG', limit_price: 100, quantity: 3, status: 'OPEN', ...overrides,
});

describe('bot plays', () => {
  it('projects an open position with deduplicated targets, mark, reported risk and provenance', () => {
    const play = positionPlay(position(), 'LIVE', 'trending_down');
    expect(play.levels.map(level => level.label)).toEqual(['Entry', 'Stop', 'TP1', 'TP2', 'Mark']);
    expect(play).toMatchObject({ account: 'LIVE', mode: 'STRIKE', threshold: 65, riskAmount: 10, timeframe: '4h', timeframeRecorded: false,
      pnl: { label: 'Unrealized', value: 4, pct: 2 } });
    expect(play.facts.find(fact => fact.label === 'Regime (current)')?.value).toBe('TRENDING DOWN');
    expect(positionPlay(position({ tp1: null, tp2: null, tp_final: null })).warnings[0]).toMatch(/No valid take-profit/);
  });

  it('distinguishes an unreported pending plan from one reported without a stop', () => {
    expect(pendingPlay(pending()).warnings[0]).toMatch(/did not report the pending plan/);
    expect(pendingPlay(pending({ stop_loss: null, targets: [] })).warnings[0]).toMatch(/no valid stop/);
    const play = pendingPlay(pending({ stop_loss: 95, targets: [110], timeframe: '15m', confluence: 71.5,
      strategy: { mode: 'surgical', strategy_gate: 70 }, current_price: null }), 'PAPER');
    expect(play).toMatchObject({ timeframe: '15m', timeframeRecorded: true, score: 71.5, threshold: 70, mode: 'SURGICAL', currentPrice: undefined, warnings: [] });
    expect(play.levels.map(level => level.kind)).toEqual(['entry', 'stop', 'target']);
  });

  it('resolves a selection against the latest poll and drops it once the play is gone', () => {
    const selection = { kind: 'position' as const, id: 'p1' };
    expect(selectBotPlay(selection, [position({ current_price: 97 })], [])?.currentPrice).toBe(97);
    expect(selectBotPlay(selection, [], [])).toBeUndefined();
    expect(selectBotPlay({ kind: 'pending', id: 'o1' }, [], [pending()])?.status).toBe('PENDING');
    expect(selectBotPlay(null, [position()], [])).toBeUndefined();
  });

  it('marks closed trades by entry/exit time and never invents the original plan', () => {
    const trade: JournalTrade = { trade_id: 't', session_id: 's', symbol: 'SOL/USDT', direction: 'LONG', trade_type: 'scalp',
      entry_price: 10, exit_price: 9.5, quantity: 1, entry_time: '2026-10-10T10:00:00Z', exit_time: '2026-10-10T11:00:00Z',
      pnl: -0.5, pnl_pct: -5, exit_reason: 'stop_loss', targets_hit: [], max_favorable: 0.2, max_adverse: -0.5 };
    const play = closedPlay(trade);
    expect(play.levels.map(level => level.kind)).toEqual(['entry', 'exit']);
    expect(play.markers.map(marker => marker.kind)).toEqual(['entry', 'exit']);
    expect(play.facts[0]).toMatchObject({ value: 'STOP', tone: 'red' });
    expect(play.timeframe).toBe('15m');
  });

  it('snaps markers to the nearest bar and rejects times outside the loaded window', () => {
    const times = [3600, 7200, 10800];
    expect(snapToCandle('1970-01-01T02:10:00Z', times, 3600)).toBe(7200);
    expect(snapToCandle('1970-01-02T00:00:00Z', times, 3600)).toBeUndefined();
    expect(snapToCandle('invalid', times, 3600)).toBeUndefined();
  });
});
