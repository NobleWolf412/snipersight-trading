import type { PlanType, ConvictionClass, RegimeMetadata } from '@/types/regime';
import type { CycleContext, ReversalContext } from '@/types/cycle';
import type { ConfluenceBreakdown } from '@/types/confluence';

export interface ScanResult {
  id: string;
  pair: string;
  sniper_mode?: string; // added for mode-aware overlays
  trendBias: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  confidenceScore: number;
  riskScore: number;
  riskReward?: number; // Actual R:R ratio from trade plan
  classification: 'SWING' | 'SCALP';
  entryZone: { low: number; high: number };
  stopLoss: number;
  takeProfits: number[];
  orderBlocks: Array<{ type: 'bullish' | 'bearish'; price: number; timeframe: string }>;
  fairValueGaps: Array<{ low: number; high: number; type: 'bullish' | 'bearish' }>;
  timestamp: string;
  liqPrice?: number;
  liqCushionPct?: number;
  liqRiskBand?: 'high' | 'moderate' | 'comfortable';
  atrRegimeLabel?: string;
  atrPct?: number;
  recommendedStopBufferAtr?: number;
  usedStopBufferAtr?: number;
  altStopLevel?: number;
  altStopRationale?: string;

  // Phase 1-5 enhancements
  plan_type?: PlanType;
  conviction_class?: ConvictionClass;
  missing_critical_timeframes?: string[];
  regime?: RegimeMetadata;
  // Trade rationale and metadata from backend
  rationale?: string;
  confluence_breakdown?: ConfluenceBreakdown;
  metadata?: {
    exchange?: string;
    leverage?: number;
    mode?: string;
    scanned?: number;
    rejected?: number;
    appliedTimeframes?: string[];
    effectiveMinScore?: number;
    criticalTimeframes?: string[];
    [key: string]: unknown;
  };
  // Optional SMC geometry from backend for accurate overlays
  smc_geometry?: {
    order_blocks?: any[];
    fvgs?: any[];
    bos_choch?: any[];
    liquidity_sweeps?: any[];
  };

  // Cycle Theory context (Phase 7 - Camel Finance methodology)
  cycle_context?: CycleContext;
  reversal_context?: ReversalContext;
}

export interface BotActivity {
  id: string;
  timestamp: string;
  action: string;
  pair: string;
  status: 'success' | 'warning' | 'info';
}


export function generateMockBotActivity(): BotActivity[] {
  const activities = [
    'Target acquired: High-confidence setup detected',
    'Monitoring entry zone proximity',
    'Fair value gap alignment confirmed',
    'HTF structure validated',
    'Position sizing calculated',
    'Risk parameters verified',
  ];

  return activities.map((action, i) => ({
    id: `activity-${Date.now()}-${i}`,
    timestamp: new Date(Date.now() - i * 30000).toISOString(),
    action,
    pair: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'][Math.floor(Math.random() * 3)],
    status: ['success', 'warning', 'info'][Math.floor(Math.random() * 3)] as BotActivity['status'],
  }));
}

/**
 * Convert backend Signal to frontend ScanResult format
 */
export function convertSignalToScanResult(signal: any): ScanResult {
  const trendBias: ScanResult['trendBias'] =
    signal.direction === 'LONG' ? 'BULLISH' :
      signal.direction === 'SHORT' ? 'BEARISH' : 'NEUTRAL';

  // Determine classification based on setup_type (from backend)
  // setup_type values: 'scalp', 'intraday', 'swing'
  // Only fall back to timeframe heuristic if setup_type is missing
  let classification: ScanResult['classification'];
  if (signal.setup_type === 'swing') {
    classification = 'SWING';
  } else if (signal.setup_type === 'scalp' || signal.setup_type === 'intraday') {
    classification = 'SCALP';
  } else {
    // Fallback: infer from timeframe if no setup_type provided
    classification = ['5m', '15m', '30m'].includes(signal.timeframe) ? 'SCALP' : 'SWING';
  }



  // Calculate risk score from analysis (inverse of risk:reward, scaled 1-10)
  const riskScore = signal.analysis?.risk_reward
    ? Math.max(1, Math.min(10, 10 / signal.analysis.risk_reward))
    : 5;

  // Derive conviction class A/B/C from confidence score if not provided
  const confidence: number = typeof signal.score === 'number' ? signal.score : 0;
  const derivedConviction: ConvictionClass = confidence >= 80 ? 'A' : confidence >= 60 ? 'B' : 'C';

  // Prefer backend-provided regime metadata when available
  const regime: RegimeMetadata | undefined = signal.regime || signal.analysis?.regime || undefined;

  return {
    id: `signal-${signal.symbol}-${Date.now()}`,
    // Clean symbol: strip any :USDT suffix (exchange swap notation), then format as pair
    pair: signal.symbol.replace(':USDT', '').replace('USDT', '/USDT'),
    sniper_mode: signal.sniper_mode || signal.mode || undefined,
    trendBias,
    confidenceScore: confidence,
    riskScore,
    riskReward: signal.analysis?.risk_reward,
    classification,
    entryZone: { low: signal.entry_far, high: signal.entry_near },
    stopLoss: signal.stop_loss,
    takeProfits: signal.targets.map((t: any) => t.level),
    orderBlocks: signal.smc_geometry?.order_blocks
      ? signal.smc_geometry.order_blocks.map((ob: any) => ({
        type: ob.type as 'bullish' | 'bearish',
        price: ob.price || (ob.high + ob.low) / 2,
        high: ob.high,
        low: ob.low,
        timeframe: ob.timeframe,
      }))
      : [],
    fairValueGaps: signal.smc_geometry?.fvgs
      ? signal.smc_geometry.fvgs.map((fvg: any) => ({
        low: fvg.low,
        high: fvg.high,
        type: fvg.type as 'bullish' | 'bearish',
        timeframe: fvg.timeframe,
      }))
      : [],
    timestamp: new Date().toISOString(),

    liqPrice: signal.liquidation?.approx_liq_price,
    liqCushionPct: signal.liquidation?.cushion_pct,
    liqRiskBand: signal.liquidation?.risk_band,
    atrRegimeLabel: signal.atr_regime?.label,
    atrPct: signal.atr_regime?.atr_pct,
    recommendedStopBufferAtr: signal.atr_regime?.recommended_stop_buffer_atr,
    usedStopBufferAtr: signal.atr_regime?.used_stop_buffer_atr,
    altStopLevel: signal.alt_stop?.level,
    altStopRationale: signal.alt_stop?.rationale,
    confluence_breakdown: signal.confluence_breakdown,

    // Phase enhancements
    plan_type: (signal.plan_type as PlanType) || 'SMC',
    conviction_class: (signal.conviction_class as ConvictionClass) || derivedConviction,
    missing_critical_timeframes: signal.missing_critical_timeframes || signal.analysis?.missing_critical_timeframes || [],
    regime,
    // Pass through raw geometry if provided for future chart overlays
    smc_geometry: signal.smc_geometry,
  };
}

/**
 * Generate demo ScanResults for offline/dev fallback
 */
export function generateDemoScanResults(count = 5, mode: string = 'recon'): ScanResult[] {
  const symbols = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOT/USDT', 'LINK/USDT',
    'XRP/USDT', 'ADA/USDT', 'AVAX/USDT', 'MATIC/USDT', 'BNB/USDT',
  ];
  const basePrices: Record<string, number> = {
    'BTC/USDT': 43500,
    'ETH/USDT': 2280,
    'SOL/USDT': 98.5,
    'DOT/USDT': 7.45,
    'LINK/USDT': 15.2,
    'XRP/USDT': 0.62,
    'ADA/USDT': 0.58,
    'AVAX/USDT': 38.2,
    'MATIC/USDT': 0.89,
    'BNB/USDT': 315,
  };
  const now = Date.now();
  const out: ScanResult[] = [];
  for (let i = 0; i < Math.min(count, symbols.length); i++) {
    const pair = symbols[i];
    const base = basePrices[pair] ?? 100;
    const long = i % 2 === 0;
    const confidence = 60 + (i * 6) % 35; // 60..95
    const entryNear = long ? base * 0.995 : base * 1.005;
    const entryFar = long ? base * 0.99 : base * 1.01;
    const stop = long ? base * 0.97 : base * 1.03;
    const tp1 = long ? base * 1.02 : base * 0.98;
    const tp2 = long ? base * 1.04 : base * 0.96;
    const rr = Math.max(1.5, (Math.abs(((tp1 + tp2) / 2) - entryNear) / Math.abs(entryNear - stop)));

    out.push({
      id: `demo-${pair}-${now}-${i}`,
      pair,
      sniper_mode: mode,
      trendBias: long ? 'BULLISH' : 'BEARISH',
      confidenceScore: confidence,
      riskScore: Math.max(1, Math.min(10, 10 / rr)),
      classification: mode === 'surgical' || mode === 'strike' ? 'SCALP' : 'SWING',
      entryZone: { low: entryFar, high: entryNear },
      stopLoss: stop,
      takeProfits: [tp1, tp2],
      orderBlocks: [],
      fairValueGaps: [],
      timestamp: new Date(now - i * 60000).toISOString(),
      plan_type: 'SMC',
      conviction_class: confidence >= 80 ? 'A' : confidence >= 60 ? 'B' : 'C',
      missing_critical_timeframes: [],
      regime: {
        // Provide local regime metadata for better UI rendering
        symbol_regime: {
          trend: long ? 'up' : 'down',
          volatility: confidence >= 85 ? 'elevated' : confidence >= 70 ? 'normal' : 'compressed',
          score: Math.min(95, Math.max(35, Math.round(confidence)))
        }
      },
      smc_geometry: {
        order_blocks: [],
        fvgs: [],
        bos_choch: [],
        liquidity_sweeps: [],
      },
    });
  }
  return out;
}
