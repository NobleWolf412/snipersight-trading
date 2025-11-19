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

  for (let i = 0; i < count; i++) {
    const pair = pairs[i % pairs.length];
    const basePrice = Math.random() * 50000 + 1000;
    const trendBias = ['BULLISH', 'BEARISH', 'NEUTRAL'][Math.floor(Math.random() * 3)] as ScanResult['trendBias'];
    
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
