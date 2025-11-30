import type { PlanType, ConvictionClass, RegimeMetadata } from '@/types/regime';

export interface ScanResult {
  id: string;
  pair: string;
  sniper_mode?: string; // added for mode-aware overlays
  trendBias: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  confidenceScore: number;
  riskScore: number;
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
  // Optional SMC geometry from backend for accurate overlays
  smc_geometry?: {
    order_blocks?: any[];
    fvgs?: any[];
    bos_choch?: any[];
    liquidity_sweeps?: any[];
  };
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

  // Determine classification based on setup_type or timeframe
  const classification: ScanResult['classification'] = 
    signal.setup_type === 'intraday' || ['5m', '15m', '30m'].includes(signal.timeframe) 
      ? 'SCALP' 
      : 'SWING';

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
    pair: signal.symbol.replace('USDT', '/USDT'),
    sniper_mode: signal.sniper_mode || signal.mode || undefined,
    trendBias,
    confidenceScore: confidence,
    riskScore,
    classification,
    entryZone: { low: signal.entry_far, high: signal.entry_near },
    stopLoss: signal.stop_loss,
    takeProfits: signal.targets.map((t: any) => t.level),
    orderBlocks: signal.analysis?.order_blocks 
      ? Array(signal.analysis.order_blocks).fill(null).map((_, i) => ({
          type: trendBias === 'BULLISH' ? 'bullish' as const : 'bearish' as const,
          price: signal.entry_near * (trendBias === 'BULLISH' ? 0.98 - i * 0.01 : 1.02 + i * 0.01),
          timeframe: signal.timeframe,
        }))
      : [],
    fairValueGaps: signal.analysis?.fvgs
      ? Array(signal.analysis.fvgs).fill(null).map((_, i) => ({
          low: signal.entry_near * (0.96 - i * 0.01),
          high: signal.entry_near * (0.98 - i * 0.01),
          type: 'bullish' as const,
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
