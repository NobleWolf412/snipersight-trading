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

    // Phase enhancements
    plan_type: (signal.plan_type as PlanType) || 'SMC',
    conviction_class: (signal.conviction_class as ConvictionClass) || derivedConviction,
    missing_critical_timeframes: signal.missing_critical_timeframes || signal.analysis?.missing_critical_timeframes || [],
    regime,
  };
}
