import type { PlanType, ConvictionClass, RegimeMetadata } from '@/types/regime';

export interface ScanResult {
  id: string;
  pair: string;
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
  
  // Phase 1-5 enhancements
  plan_type?: PlanType;
  conviction_class?: ConvictionClass;
  missing_critical_timeframes?: string[];
  regime?: RegimeMetadata;
}

export interface BotActivity {
  id: string;
  timestamp: string;
  action: string;
  pair: string;
  status: 'success' | 'warning' | 'info';
}

export function generateMockScanResults(count: number = 5): ScanResult[] {
  const pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'MATIC/USDT', 'AVAX/USDT', 'LINK/USDT', 'DOT/USDT', 'ADA/USDT'];
  const results: ScanResult[] = [];
  
  const planTypes: PlanType[] = ['SMC', 'ATR_FALLBACK', 'HYBRID'];
  const convictions: ConvictionClass[] = ['A', 'B', 'C'];
  const trends = ['strong_up', 'up', 'sideways', 'down', 'strong_down'] as const;
  const volatilities = ['compressed', 'normal', 'elevated', 'chaotic'] as const;

  for (let i = 0; i < count; i++) {
    const pair = pairs[i % pairs.length];
    const basePrice = Math.random() * 50000 + 1000;
    const trendBias = ['BULLISH', 'BEARISH', 'NEUTRAL'][Math.floor(Math.random() * 3)] as ScanResult['trendBias'];
    const planType = planTypes[Math.floor(Math.random() * planTypes.length)];
    const conviction = convictions[Math.floor(Math.random() * convictions.length)];
    
    results.push({
      id: `scan-${Date.now()}-${i}`,
      pair,
      trendBias,
      confidenceScore: Math.random() * 40 + 60,
      riskScore: Math.random() * 5 + 1,
      classification: Math.random() > 0.5 ? 'SWING' : 'SCALP',
      entryZone: { low: basePrice * 0.98, high: basePrice * 1.02 },
      stopLoss: basePrice * (trendBias === 'BULLISH' ? 0.95 : 1.05),
      takeProfits: [
        basePrice * (trendBias === 'BULLISH' ? 1.03 : 0.97),
        basePrice * (trendBias === 'BULLISH' ? 1.06 : 0.94),
        basePrice * (trendBias === 'BULLISH' ? 1.09 : 0.91),
      ],
      orderBlocks: [
        { type: trendBias === 'BULLISH' ? 'bullish' : 'bearish', price: basePrice * 0.99, timeframe: '4H' },
        { type: trendBias === 'BULLISH' ? 'bullish' : 'bearish', price: basePrice * 0.97, timeframe: '1D' },
      ],
      fairValueGaps: [
        { low: basePrice * 0.96, high: basePrice * 0.98, type: 'bullish' },
      ],
      timestamp: new Date().toISOString(),
      
      // Phase 1-5 enhancements
      plan_type: planType,
      conviction_class: conviction,
      missing_critical_timeframes: Math.random() > 0.7 ? ['1w'] : [],
      regime: {
        global_regime: {
          composite: 'bullish_risk_on',
          score: 65 + Math.random() * 30,
          trend: trends[Math.floor(Math.random() * trends.length)],
          volatility: volatilities[Math.floor(Math.random() * volatilities.length)],
          liquidity: 'healthy' as const
        },
        symbol_regime: {
          trend: trends[Math.floor(Math.random() * trends.length)],
          volatility: volatilities[Math.floor(Math.random() * volatilities.length)],
          score: 50 + Math.random() * 50
        }
      }
    });
  }

  return results;
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

  return {
    id: `signal-${signal.symbol}-${Date.now()}`,
    pair: signal.symbol.replace('USDT', '/USDT'),
    trendBias,
    confidenceScore: signal.score,
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
  };
}
