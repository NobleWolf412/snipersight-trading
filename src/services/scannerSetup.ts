/** Display-only projection of saved plans. Never recompute entries or targets. */
export interface SetupLevel { label: string; price: number; kind: 'entry' | 'stop' | 'target' }
export interface SetupChartPlan {
  symbol: string;
  timeframe?: string;
  exchange?: string;
  marketType?: string;
  recordedAt?: string;
  levels: SetupLevel[];
}
export const CHART_TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d', '1w'] as const;
export const CHART_EXCHANGES = ['phemex', 'bybit', 'okx', 'bitget'] as const;
const price = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value) && value > 0;
const text = (value: unknown) => typeof value === 'string' && value.trim() ? value.trim() : undefined;

export function buildSetupChartPlan(result: any, receipt: {
  exchange?: string; marketType?: string; timestamp?: string;
}): SetupChartPlan {
  const levels: SetupLevel[] = [];
  const add = (label: string, value: unknown, kind: SetupLevel['kind']) => {
    if (price(value)) levels.push({ label, price: value, kind });
  };
  // Historical entryZone.high/low are semantic near/far, including SHORT plans.
  const near = result.entryZone?.high ?? result.entry_near ?? result.entry ?? result.entry_price;
  const far = result.entryZone?.low ?? result.entry_far;
  add(price(far) && far !== near ? 'Entry near' : 'Entry', near, 'entry');
  if (far !== near) add('Entry far', far, 'entry');
  add('Stop', result.stopLoss ?? result.stop_loss?.level ?? result.stop_loss ?? result.sl, 'stop');
  const targets = Array.isArray(result.takeProfits) ? result.takeProfits
    : Array.isArray(result.targets) ? result.targets.map((target: any) => target?.level)
    : [result.tp1, result.tp2, result.tp_final];
  targets.forEach((target: unknown, index: number) => add(`TP${index + 1}`, target, 'target'));
  const tf = text(result.timeframe);
  const timeframe = tf !== '1M' ? CHART_TIMEFRAMES.find(value => value === tf?.toLowerCase()) : undefined;
  return {
    symbol: text(result.original_symbol) ?? text(result.pair) ?? text(result.symbol) ?? '',
    timeframe,
    exchange: text(receipt.exchange ?? result.metadata?.exchange)?.toLowerCase(),
    marketType: text(receipt.marketType ?? result.metadata?.market_type)?.toLowerCase(),
    recordedAt: text(result.timestamp) ?? receipt.timestamp,
    levels,
  };
}

export interface SetupCandle { time: number; open: number; high: number; low: number; close: number }
export function setupMarketSymbol(symbol: string, marketType: string): string {
  const canonical = symbol.includes('/') ? symbol : symbol.replace(/(USDT|USDC|USD)(?=:|$)/, '/$1');
  if (!canonical.includes('/')) throw new Error('The saved market symbol is unavailable.');
  if (marketType === 'spot') return canonical.split(':')[0];
  if (marketType !== 'swap') throw new Error('This chart supports spot and perpetual markets.');
  if (canonical.includes(':')) return canonical;
  const quote = canonical.split('/')[1];
  if (!['USDT', 'USDC'].includes(quote)) throw new Error('Contract settlement was not recorded for this market.');
  // A plain BASE/USDT resolves to spot on some CCXT exchanges even with defaultType=swap.
  return `${canonical}:${quote}`;
}

export function parseSetupCandles(body: unknown): SetupCandle[] {
  const list = body && typeof body === 'object' && 'candles' in body ? body.candles : null;
  if (!Array.isArray(list)) throw new Error('No candles returned for this market.');
  const candles = new Map<number, SetupCandle>();
  for (const row of list) {
    if (!row || typeof row !== 'object') continue;
    const stamp = row.timestamp ?? row.time;
    // Backend candle timestamps denote UTC; old naive ISO rows need the same interpretation.
    const iso = typeof stamp === 'string' && /^\d{4}-\d\d-\d\dT/.test(stamp)
      ? (/(?:Z|[+-]\d\d:\d\d)$/i.test(stamp) ? stamp : `${stamp}Z`) : stamp;
    const time = typeof stamp === 'number' ? Math.floor(stamp > 1e12 ? stamp / 1000 : stamp)
      : typeof iso === 'string' ? Math.floor(Date.parse(iso) / 1000) : NaN;
    const { open, high, low, close } = row;
    if (!Number.isFinite(time) || time <= 0 || ![open, high, low, close].every(price)
      || high < Math.max(open, low, close) || low > Math.min(open, high, close)) continue;
    candles.set(time, { time, open, high, low, close });
  }
  if (!candles.size) throw new Error('No valid candles returned for this market.');
  return [...candles.values()].sort((a, b) => a.time - b.time);
}

export const formatSetupPrice = (value: number) => String(value);
