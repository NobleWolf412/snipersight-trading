import { afterEach, describe, expect, it, vi } from 'vitest';
import { buildSetupChartPlan, formatSetupPrice, parseSetupCandles, setupMarketSymbol } from './scannerSetup';
import { convertSignalToScanResult } from '@/utils/mockData';
import { api } from '@/utils/api';

afterEach(() => vi.unstubAllGlobals());
describe('scanner setup chart evidence', () => {
  it.each(['LONG', 'SHORT'])('preserves exact %s boundaries and all targets through conversion and saved history', direction => {
    const near = direction === 'LONG' ? 3.55 : 3.4, far = direction === 'LONG' ? 3.4 : 3.55;
    const targets = direction === 'LONG' ? [3.7, 3.8, 3.9] : [3.2, 3.1, 3.0];
    const raw = { symbol: 'LITUSDT', original_symbol: 'LIT/USDT:USDT', direction, timeframe: '1h',
      entry_near: near, entry_far: far, stop_loss: direction === 'LONG' ? 3.3 : 3.6,
      targets: targets.map(level => ({ level })), timestamp: '2026-10-09T17:00:00Z' };
    const saved = JSON.parse(JSON.stringify(convertSignalToScanResult(raw)));
    const receipt = { exchange: 'phemex', marketType: 'swap', timestamp: '2026-10-09T17:01:00Z' };
    const plan = buildSetupChartPlan(saved, receipt);
    expect(plan).toMatchObject({ symbol: 'LIT/USDT:USDT', timeframe: '1h', exchange: 'phemex', marketType: 'swap', recordedAt: raw.timestamp });
    expect(plan.levels.map(level => [level.label, level.price])).toEqual([
      ['Entry near', near], ['Entry far', far], ['Stop', raw.stop_loss], ...targets.map((value, index) => [`TP${index + 1}`, value]),
    ]);
    expect(buildSetupChartPlan(raw, receipt).levels).toEqual(plan.levels);
  });

  it('does not invent absent prices, provenance, or timeframe for older history', () => {
    const plan = buildSetupChartPlan({ pair: 'BTC/USDT', entry_near: 1, entry_far: 1, stop_loss: 0,
      targets: [{ level: NaN }, { level: 2 }], timeframe: '1M' }, {});
    expect(plan.levels).toEqual([{ label: 'Entry', price: 1, kind: 'entry' }, { label: 'TP2', price: 2, kind: 'target' }]);
    expect(plan.exchange).toBeUndefined(); expect(plan.marketType).toBeUndefined(); expect(plan.timeframe).toBeUndefined();
    expect(buildSetupChartPlan({ timeframe: '1D' }, {}).timeframe).toBe('1d');
  });

  it.each([
    ['BTCUSDT', 'swap', 'BTC/USDT:USDT'], ['BTC/USDT', 'swap', 'BTC/USDT:USDT'],
    ['1000PEPE/USDT:USDT', 'swap', '1000PEPE/USDT:USDT'], ['ETHUSDC', 'swap', 'ETH/USDC:USDC'],
    ['BTC/USD:BTC', 'swap', 'BTC/USD:BTC'], ['BTC/USDT:USDT', 'spot', 'BTC/USDT'],
  ])('resolves %s for %s without changing contract units', (symbol, market, expected) => {
    expect(setupMarketSymbol(symbol, market)).toBe(expected);
  });

  it('rejects missing settlement instead of guessing an inverse contract', () => {
    expect(() => setupMarketSymbol('BTC/USD', 'swap')).toThrow('settlement');
    expect(() => setupMarketSymbol('unknown', 'swap')).toThrow('unavailable');
  });

  it('keeps tiny and precise saved levels round-trippable', () => {
    for (const value of [0.000000018412, 0.12345678912345678, 82525.34567891234])
      expect(Number(formatSetupPrice(value))).toBe(value);
  });

  it('sorts, deduplicates and reads both naive and aware candle times as UTC; rejects corrupt OHLC', () => {
    const row = { open: 10, high: 12, low: 9, close: 11 };
    const candles = parseSetupCandles({ candles: [
      { ...row, timestamp: '2026-10-09T11:00:00' }, { ...row, timestamp: '2026-10-09T10:00:00Z' },
      { ...row, close: 12, timestamp: '2026-10-09T11:00:00Z' },
      { ...row, timestamp: 'invalid' }, { ...row, timestamp: '2026-10-09T12:00:00Z', high: 8 },
      { ...row, timestamp: '2026-10-09T13:00:00Z', low: 0 },
      { ...row, timestamp: '2026-10-09T14:00:00Z', close: Infinity },
    ] });
    expect(candles.map(candle => candle.time)).toEqual([Date.parse('2026-10-09T10:00:00Z') / 1000, Date.parse('2026-10-09T11:00:00Z') / 1000]);
    expect(candles[1].close).toBe(12);
    expect(() => parseSetupCandles({ candles: [] })).toThrow('No valid candles');
  });

  it('sends the selected venue, qualified contract and timeframe without falling back after errors', async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({ detail: 'Requested market is not configured' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetcher);
    const response = await api.getCandles(setupMarketSymbol('LIT/USDT', 'swap'), '4h', 160, { exchange: 'bybit', marketType: 'swap' });
    expect(fetcher).toHaveBeenCalledOnce();
    expect(fetcher.mock.calls[0][0]).toBe(`${api.baseURL}/market/candles/LIT%2FUSDT%3AUSDT?timeframe=4h&limit=160&exchange=bybit&market_type=swap`);
    expect(response.error).toBe('Requested market is not configured');
  });
});
