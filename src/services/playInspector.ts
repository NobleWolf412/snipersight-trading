/**
 * Play Inspector projection: one display shape for scanner setups, open
 * positions, pending entries and closed trades. Display-only: saved plan
 * levels are never recomputed; missing values stay undefined (unknown).
 */
import type { JournalTrade } from './tradeJournalService';
import type { LivePosition, PendingEntryOrder } from './liveTradingService';
import type { PaperPosition } from './paperTradingService';
import { readDirection } from '@/utils/scoreEvidence';

export type PlaySource = 'setup' | 'position' | 'pending' | 'closed';
export type PlayDirection = 'LONG' | 'SHORT' | 'UNKNOWN';
export type PlayAccount = 'PAPER' | 'TESTNET' | 'LIVE';
export type LevelKind = 'entry' | 'stop' | 'target' | 'mark' | 'exit';
export interface PlayLevel { label: string; price: number; kind: LevelKind }
export interface PlayFact { label: string; value: string; tone?: 'green' | 'red' | 'amber' | 'cyan' }
export interface Play {
  source: PlaySource;
  symbol: string;
  direction: PlayDirection;
  account?: PlayAccount;
  mode?: string;
  tradeType?: string;
  status: string;
  /** Chart timeframe and whether the producer recorded it (vs inferred). */
  timeframe: string;
  timeframeRecorded: boolean;
  /** Known only for scanner receipts; bot plays use the session's default feed. */
  exchange?: string;
  marketType?: string;
  recordedAt?: string;
  levels: PlayLevel[];
  quantity?: number;
  currentPrice?: number;
  pnl?: { label: 'Unrealized' | 'Realized'; value: number; pct?: number };
  /** Planned loss at stop in account currency, when the producer reported it. */
  riskAmount?: number;
  score?: number;
  threshold?: number;
  rationale?: string;
  facts: PlayFact[];
  warnings: string[];
  markers: { kind: 'entry' | 'exit'; time: string }[];
}

export const CHART_TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d', '1w'] as const;
export const CHART_EXCHANGES = ['phemex', 'bybit', 'okx', 'bitget'] as const;

const finitePrice = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value) && value > 0;
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const text = (value: unknown) => typeof value === 'string' && value.trim() ? value.trim() : undefined;
/** Unrecognized direction stays UNKNOWN; never default a side. */
const side = (value: unknown): PlayDirection => readDirection({ direction: value }) ?? 'UNKNOWN';
const upper = (value: unknown) => text(value)?.toUpperCase();

export function chartTimeframe(value: unknown): string | undefined {
  const tf = text(value);
  if (!tf || tf === '1M') return undefined; // monthly normalization is unresolved
  return CHART_TIMEFRAMES.find(candidate => candidate === tf.toLowerCase());
}

/** Cascade tier → chart timeframe; used only when the plan timeframe is absent. */
export function tierTimeframe(tier: unknown): string {
  const value = String(tier ?? '').toLowerCase();
  return value === 'scalp' ? '15m' : value === 'swing' ? '4h' : '1h';
}

function planLevels(entryNear: unknown, entryFar: unknown, stop: unknown, targets: unknown[]): PlayLevel[] {
  const levels: PlayLevel[] = [];
  const zone = finitePrice(entryFar) && finitePrice(entryNear) && entryFar !== entryNear;
  if (finitePrice(entryNear)) levels.push({ label: zone ? 'Entry near' : 'Entry', price: entryNear, kind: 'entry' });
  else if (finitePrice(entryFar)) levels.push({ label: 'Entry', price: entryFar, kind: 'entry' });
  if (zone) levels.push({ label: 'Entry far', price: entryFar as number, kind: 'entry' });
  if (finitePrice(stop)) levels.push({ label: 'Stop', price: stop, kind: 'stop' });
  targets.forEach((target, index) => {
    if (finitePrice(target)) levels.push({ label: `TP${index + 1}`, price: target, kind: 'target' });
  });
  return levels;
}

export interface PlayMetrics {
  entry?: number;
  stop?: number;
  /** Per-unit distance from entry to stop; undefined when the stop is missing or on the wrong side. */
  riskPerUnit?: number;
  riskPct?: number;
  riskAmount?: number;
  targets: { label: string; price: number; rr?: number; reward?: number }[];
  bestRR?: number;
  stopDistancePct?: number;
}

/**
 * Direction-aware plan arithmetic. This is the single place R:R, risk and
 * reward are derived from levels, so edited levels can reuse it unchanged.
 */
export function playMetrics(direction: PlayDirection, levels: PlayLevel[], quantity?: number, currentPrice?: number): PlayMetrics {
  const entry = levels.find(level => level.kind === 'entry')?.price;
  const stop = levels.find(level => level.kind === 'stop')?.price;
  if (direction === 'UNKNOWN') return { entry, stop, targets: levels.filter(level => level.kind === 'target').map(level => ({ label: level.label, price: level.price })) };
  const sign = direction === 'LONG' ? 1 : -1;
  const riskPerUnit = entry !== undefined && stop !== undefined && (entry - stop) * sign > 0 ? Math.abs(entry - stop) : undefined;
  const qty = finitePrice(quantity) ? quantity : undefined;
  const targets = levels.filter(level => level.kind === 'target').map(level => {
    const move = entry !== undefined ? (level.price - entry) * sign : undefined;
    const valid = move !== undefined && move > 0;
    return {
      label: level.label, price: level.price,
      rr: valid && riskPerUnit ? move / riskPerUnit : undefined,
      reward: valid && qty ? move * qty : undefined,
    };
  });
  const ratios = targets.map(target => target.rr).filter(finite);
  return {
    entry, stop, riskPerUnit, targets,
    riskPct: riskPerUnit && entry ? riskPerUnit / entry * 100 : undefined,
    riskAmount: riskPerUnit && qty ? riskPerUnit * qty : undefined,
    bestRR: ratios.length ? Math.max(...ratios) : undefined,
    stopDistancePct: stop !== undefined && finitePrice(currentPrice) ? (currentPrice - stop) * sign / currentPrice * 100 : undefined,
  };
}

export function setupPlay(result: any, receipt: { exchange?: string; marketType?: string; timestamp?: string },
  evidence: { score?: number; threshold?: number; tradeType?: string } = {}): Play {
  // Historical entryZone.high/low are semantic near/far, including SHORT plans.
  const near = result.entryZone?.high ?? result.entry_near ?? result.entry ?? result.entry_price;
  const far = result.entryZone?.low ?? result.entry_far;
  const targets = Array.isArray(result.takeProfits) ? result.takeProfits
    : Array.isArray(result.targets) ? result.targets.map((target: any) => target?.level)
    : [result.tp1, result.tp2, result.tp_final];
  const timeframe = chartTimeframe(result.timeframe);
  const exchange = text(receipt.exchange ?? result.metadata?.exchange)?.toLowerCase();
  const marketType = text(receipt.marketType ?? result.metadata?.market_type)?.toLowerCase();
  const warnings: string[] = [];
  if (!exchange || !marketType) warnings.push('This older result did not save its market source. Confirm the chart source matches the setup.');
  if (!timeframe) warnings.push('Setup timeframe was not recorded. Viewing 1h candles.');
  return {
    source: 'setup', status: 'SETUP',
    symbol: text(result.original_symbol) ?? text(result.pair) ?? text(result.symbol) ?? '',
    direction: readDirection(result) ?? 'UNKNOWN',
    tradeType: upper(evidence.tradeType), mode: upper(result.metadata?.strategy?.mode),
    timeframe: timeframe ?? '1h', timeframeRecorded: !!timeframe,
    exchange, marketType,
    recordedAt: text(result.timestamp) ?? receipt.timestamp,
    levels: planLevels(near, far, result.stopLoss ?? result.stop_loss?.level ?? result.stop_loss ?? result.sl, targets),
    score: finite(evidence.score) ? evidence.score : undefined,
    threshold: finite(evidence.threshold) ? evidence.threshold : undefined,
    rationale: text(result.rationale),
    facts: [], warnings, markers: [],
  };
}

export function positionPlay(position: LivePosition | PaperPosition, account?: PlayAccount, regime?: string | null): Play {
  const targets = [position.tp1, position.tp2, position.tp_final].filter((value, index, all) => finitePrice(value) && all.indexOf(value) === index);
  const levels = planLevels(position.entry_price, undefined, position.stop_loss, targets);
  if (finitePrice(position.current_price)) levels.push({ label: 'Mark', price: position.current_price, kind: 'mark' });
  const facts: PlayFact[] = [
    { label: 'Opened', value: position.opened_at ? new Date(position.opened_at).toLocaleString() : 'Unavailable' },
    { label: 'Breakeven', value: position.breakeven_active ? 'TRIGGERED' : 'NOT YET', tone: position.breakeven_active ? 'green' : undefined },
    { label: 'Trailing', value: position.trailing_active ? 'TRAILING' : 'NOT YET', tone: position.trailing_active ? 'green' : undefined },
  ];
  if (finite(position.targets_hit)) facts.push({ label: 'Targets hit', value: String(position.targets_hit) });
  if (finitePrice(position.initial_stop_loss) && position.initial_stop_loss !== position.stop_loss)
    facts.push({ label: 'Initial stop', value: formatPrice(position.initial_stop_loss) });
  if (regime) facts.push({ label: 'Regime (current)', value: regime.replace(/_/g, ' ').toUpperCase(), tone: 'cyan' });
  const warnings: string[] = [];
  if (!targets.length || position.final_targets_remaining === 0 || (position.targets_stripped_count ?? 0) > 0)
    warnings.push('No valid take-profit remains. This position can exit only by stop, stagnation or max-hours timeout.');
  warnings.push(`Plan timeframe is not reported for open positions; chart defaults to ${tierTimeframe(position.trade_type)} from the ${position.trade_type || 'unknown'} tier.`);
  return {
    source: 'position', status: 'OPEN', account,
    symbol: position.symbol, direction: side(position.direction),
    mode: upper(position.strategy?.mode), tradeType: upper(position.trade_type),
    timeframe: tierTimeframe(position.trade_type), timeframeRecorded: false,
    levels, quantity: position.quantity, currentPrice: finitePrice(position.current_price) ? position.current_price : undefined,
    pnl: finite(position.unrealized_pnl) ? { label: 'Unrealized', value: position.unrealized_pnl, pct: finite(position.unrealized_pnl_pct) ? position.unrealized_pnl_pct : undefined } : undefined,
    riskAmount: finite(position.risk_pnl) && position.risk_pnl !== 0 ? Math.abs(position.risk_pnl) : undefined,
    threshold: finite(position.strategy?.strategy_gate) ? position.strategy?.strategy_gate : undefined,
    facts, warnings, markers: position.opened_at ? [{ kind: 'entry', time: position.opened_at }] : [],
  };
}

export function pendingPlay(order: PendingEntryOrder, account?: PlayAccount): Play {
  const levels = planLevels(order.limit_price, undefined, order.stop_loss, order.targets ?? []);
  const planNear = finitePrice(order.entry_near) ? order.entry_near : undefined;
  if (finitePrice(order.current_price)) levels.push({ label: 'Mark', price: order.current_price, kind: 'mark' });
  const timeframe = chartTimeframe(order.timeframe);
  const facts: PlayFact[] = [
    { label: 'Order', value: (order.status || 'OPEN').toUpperCase(), tone: 'cyan' },
    { label: 'Filled', value: finite(order.filled_qty) ? `${order.filled_qty} / ${order.quantity}` : 'Unavailable' },
  ];
  if (planNear !== undefined && planNear !== order.limit_price) facts.push({ label: 'Plan entry near', value: formatPrice(planNear) });
  const warnings: string[] = [];
  if (order.stop_loss === undefined) warnings.push('This session did not report the pending plan. Stop and targets are unknown until it does.');
  else if (order.stop_loss === null) warnings.push('The pending plan has no valid stop recorded.');
  if (order.awaiting_adoption) warnings.push('Entry fill observed; the position is awaiting adoption.');
  return {
    source: 'pending', status: 'PENDING', account,
    symbol: order.symbol, direction: side(order.direction),
    mode: upper(order.strategy?.mode), tradeType: upper(order.trade_type),
    timeframe: timeframe ?? tierTimeframe(order.trade_type), timeframeRecorded: !!timeframe,
    levels, quantity: order.quantity, currentPrice: finitePrice(order.current_price) ? order.current_price : undefined,
    score: finite(order.confluence) ? order.confluence : undefined,
    threshold: finite(order.strategy?.strategy_gate) ? order.strategy?.strategy_gate : undefined,
    rationale: text(order.rationale), facts, warnings, markers: [],
  };
}

export const EXIT_REASON_LABELS: Record<string, string> = {
  target: 'TARGET', stop_loss: 'STOP', stagnation: 'STALE', manual: 'MANUAL', max_hours: 'TIMEOUT',
  orphan_price_feed_failure: 'ORPHAN', trailing_stop: 'TRAIL',
};

export function closedPlay(trade: JournalTrade): Play {
  const levels = planLevels(trade.entry_price, undefined, undefined, []);
  if (finitePrice(trade.exit_price)) levels.push({ label: 'Exit', price: trade.exit_price, kind: 'exit' });
  const reason = EXIT_REASON_LABELS[trade.exit_reason] ?? (upper(trade.exit_reason) || 'UNKNOWN');
  const facts: PlayFact[] = [
    { label: 'Exit reason', value: reason, tone: reason === 'STOP' ? 'red' : reason === 'TARGET' || reason === 'TRAIL' ? 'green' : 'amber' },
    { label: 'Entered', value: new Date(trade.entry_time).toLocaleString() },
    { label: 'Exited', value: trade.exit_time ? new Date(trade.exit_time).toLocaleString() : 'Unavailable' },
    { label: 'Targets hit', value: trade.targets_hit?.length ? trade.targets_hit.join(', ') : 'None' },
  ];
  if (finite(trade.max_favorable)) facts.push({ label: 'MFE', value: formatPrice(trade.max_favorable), tone: 'green' });
  if (finite(trade.max_adverse)) facts.push({ label: 'MAE', value: formatPrice(trade.max_adverse), tone: 'red' });
  return {
    source: 'closed', status: 'CLOSED',
    symbol: trade.symbol, direction: side(trade.direction), tradeType: upper(trade.trade_type),
    timeframe: tierTimeframe(trade.trade_type), timeframeRecorded: false,
    levels, quantity: trade.quantity,
    pnl: finite(trade.pnl) ? { label: 'Realized', value: trade.pnl, pct: finite(trade.pnl_pct) ? trade.pnl_pct : undefined } : undefined,
    facts,
    warnings: ['The journal record does not carry the original stop and targets.'],
    markers: [{ kind: 'entry' as const, time: trade.entry_time }, ...(trade.exit_time ? [{ kind: 'exit' as const, time: trade.exit_time }] : [])],
  };
}

export type BotPlaySelection = { kind: 'position' | 'pending'; id: string };

/** Resolve a selection against the latest status so the inspector stays live. */
export function selectBotPlay(selection: BotPlaySelection | null, positions: (LivePosition | PaperPosition)[],
  pending: PendingEntryOrder[], account?: PlayAccount, regime?: string | null): Play | undefined {
  if (!selection) return undefined;
  if (selection.kind === 'position') {
    const position = positions.find(candidate => candidate.position_id === selection.id);
    return position && positionPlay(position, account, regime);
  }
  const order = pending.find(candidate => candidate.order_id === selection.id);
  return order && pendingPlay(order, account);
}

export interface PlayCandle { time: number; open: number; high: number; low: number; close: number }

export function chartMarketSymbol(symbol: string, marketType: string): string {
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

export function parsePlayCandles(body: unknown): PlayCandle[] {
  const list = Array.isArray(body) ? body : body && typeof body === 'object' && 'candles' in body ? body.candles : null;
  if (!Array.isArray(list)) throw new Error('No candles returned for this market.');
  const candles = new Map<number, PlayCandle>();
  for (const row of list) {
    if (!row || typeof row !== 'object') continue;
    const time = utcSeconds(row.timestamp ?? row.time);
    const { open, high, low, close } = row;
    if (time === undefined || ![open, high, low, close].every(finitePrice)
      || high < Math.max(open, low, close) || low > Math.min(open, high, close)) continue;
    candles.set(time, { time, open, high, low, close });
  }
  if (!candles.size) throw new Error('No valid candles returned for this market.');
  return [...candles.values()].sort((a, b) => a.time - b.time);
}

/** Backend timestamps denote UTC; naive ISO strings get the same interpretation. */
export function utcSeconds(stamp: unknown): number | undefined {
  const iso = typeof stamp === 'string' && /^\d{4}-\d\d-\d\dT/.test(stamp)
    ? (/(?:Z|[+-]\d\d:\d\d)$/i.test(stamp) ? stamp : `${stamp}Z`) : stamp;
  const time = typeof stamp === 'number' ? Math.floor(stamp > 1e12 ? stamp / 1000 : stamp)
    : typeof iso === 'string' ? Math.floor(Date.parse(iso) / 1000) : NaN;
  return Number.isFinite(time) && time > 0 ? time : undefined;
}

/** Snap a marker to the nearest bar, or undefined when it falls outside the loaded window. */
export function snapToCandle(stamp: string, times: number[], barSeconds: number): number | undefined {
  const target = utcSeconds(stamp);
  if (target === undefined || !times.length || target < times[0] - barSeconds || target > times[times.length - 1] + barSeconds) return undefined;
  return times.reduce((best, time) => Math.abs(time - target) < Math.abs(best - target) ? time : best, times[0]);
}

export const TIMEFRAME_SECONDS: Record<string, number> = { '1m': 60, '5m': 300, '15m': 900, '1h': 3600, '4h': 14400, '1d': 86400, '1w': 604800 };

/** Full precision: saved levels must round-trip exactly. */
export const formatPrice = (value: number) => String(value);
export const formatMoney = (value: number) => `${value >= 0 ? '+' : '-'}$${Math.abs(value).toFixed(2)}`;
export const formatPct = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
