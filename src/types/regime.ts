/**
 * Market Regime Types
 * 
 * Multi-dimensional regime tracking for adaptive signal generation
 */

export type TrendRegime = 'strong_up' | 'up' | 'sideways' | 'down' | 'strong_down';
export type VolatilityRegime = 'compressed' | 'normal' | 'elevated' | 'chaotic';
export type LiquidityRegime = 'thin' | 'healthy' | 'heavy';
export type RiskAppetite = 'risk_on' | 'risk_off' | 'rotation';
export type DerivativesRegime = 'short_crowded' | 'long_crowded' | 'balanced';

export interface RegimeDimensions {
  trend: TrendRegime;
  volatility: VolatilityRegime;
  liquidity: LiquidityRegime;
  risk_appetite: RiskAppetite;
  derivatives: DerivativesRegime;
}

export interface MarketRegime {
  dimensions: RegimeDimensions;
  composite: string;
  score: number; // 0-100, higher = more trade-friendly
  timestamp: string;
  
  // Per-dimension scores
  trend_score: number;
  volatility_score: number;
  liquidity_score: number;
  risk_score: number;
  derivatives_score: number;
  
  // Optional dominance data
  btc_dominance?: number;
  usdt_dominance?: number;
  alt_dominance?: number;
}

export interface SymbolRegime {
  symbol: string;
  trend: TrendRegime;
  volatility: VolatilityRegime;
  score: number; // 0-100
}

export interface RegimeMetadata {
  global_regime?: {
    composite: string;
    score: number;
    trend: TrendRegime;
    volatility: VolatilityRegime;
    liquidity: LiquidityRegime;
  };
  symbol_regime?: {
    trend: TrendRegime;
    volatility: VolatilityRegime;
    score: number;
  };
}

// Plan type and conviction
export type PlanType = 'SMC' | 'ATR_FALLBACK' | 'HYBRID';
export type ConvictionClass = 'A' | 'B' | 'C';

// Enhanced scan result with regime + conviction
export interface EnhancedScanResult {
  symbol: string;
  direction: 'LONG' | 'SHORT';
  setup_type: string;
  confidence_score: number;
  risk_reward: number;
  plan_type: PlanType;
  conviction_class: ConvictionClass;
  missing_critical_timeframes: string[];
  regime?: RegimeMetadata;
  
  // Entry/Stop/Targets
  entry_zone: {
    near_entry: number;
    far_entry: number;
    rationale: string;
  };
  stop_loss: {
    level: number;
    distance_atr: number;
    rationale: string;
  };
  targets: Array<{
    level: number;
    percentage: number;
    rationale: string;
  }>;
  
  rationale: string;
  timestamp: string;
}
