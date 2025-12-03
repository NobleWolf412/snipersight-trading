/**
 * Cycle Theory Types
 * 
 * Based on Camel Finance methodology for crypto cycle detection.
 * - DCL (Daily Cycle Low): 18-28 trading days for crypto
 * - WCL (Weekly Cycle Low): 35-50 trading days  
 * - YCL (Yearly Cycle Low): 200-250 trading days
 * - Translation: LTR (bearish), MTR (neutral), RTR (bullish)
 */

// Cycle phase represents the current position within a market cycle
export type CyclePhase = 'ACCUMULATION' | 'MARKUP' | 'DISTRIBUTION' | 'MARKDOWN';

// Translation indicates whether the cycle topped early (bearish) or late (bullish)
export type CycleTranslation = 'LTR' | 'MTR' | 'RTR';

// Confirmation state for cycle lows
export type CycleConfirmation = 'CONFIRMED' | 'UNCONFIRMED' | 'CANCELLED' | 'UPDATED';

/**
 * Cycle context from backend analysis
 */
export interface CycleContext {
  // Current cycle phase
  phase: CyclePhase;
  
  // Daily cycle timing
  days_since_dcl?: number;          // Days since last Daily Cycle Low
  expected_dcl_window?: [number, number]; // Expected DCL range (e.g., [18, 28])
  dcl_due?: boolean;                // True if in DCL window
  
  // Weekly cycle timing
  days_since_wcl?: number;          // Days since last Weekly Cycle Low
  expected_wcl_window?: [number, number]; // Expected WCL range (e.g., [35, 50])
  wcl_due?: boolean;                // True if in WCL window
  
  // Cycle translation (determines trade bias)
  translation?: CycleTranslation;
  translation_confidence?: number;   // 0-100 confidence in translation call
  
  // Cycle low confirmation
  dcl_status?: CycleConfirmation;
  wcl_status?: CycleConfirmation;
  
  // Position in cycle
  cycle_position_pct?: number;       // 0-100, where in cycle we are
  near_cycle_low?: boolean;          // True if near DCL or WCL zone
  near_cycle_high?: boolean;         // True if near cycle high
  
  // Computed trade bias from cycle analysis
  cycle_bias?: 'LONG' | 'SHORT' | 'NEUTRAL';
}

/**
 * Reversal context combining cycle + SMC signals
 */
export interface ReversalContext {
  // Structure confirmation
  structure_broken: boolean;         // CHoCH detected
  volume_displacement: boolean;      // Strong volume spike on break
  
  // Cycle alignment  
  at_cycle_extreme: boolean;         // At DCL/WCL zone
  cycle_supports_direction: boolean; // Cycle translation supports reversal
  
  // Combined score
  reversal_score: number;            // 0-100 combined reversal confidence
  reversal_rationale?: string;       // Human-readable explanation
}

/**
 * Translation display configuration for UI
 */
export const TRANSLATION_DISPLAY: Record<CycleTranslation, {
  label: string;
  emoji: string;
  color: string;
  description: string;
}> = {
  LTR: {
    label: 'Left Translated',
    emoji: '🟥',
    color: 'text-destructive',
    description: 'Cycle topped early → Bearish bias → Favor SHORT setups'
  },
  MTR: {
    label: 'Mid Translated',
    emoji: '🟧',
    color: 'text-warning',
    description: 'Cycle topped mid-range → Neutral → Both directions valid'
  },
  RTR: {
    label: 'Right Translated',
    emoji: '🟩',
    color: 'text-success',
    description: 'Cycle topped late → Bullish bias → Favor LONG setups'
  }
};

/**
 * Phase display configuration for UI
 */
export const PHASE_DISPLAY: Record<CyclePhase, {
  label: string;
  color: string;
  icon: string;
  description: string;
}> = {
  ACCUMULATION: {
    label: 'Accumulation',
    color: 'text-blue-500',
    icon: '📦',
    description: 'Smart money building positions at lows'
  },
  MARKUP: {
    label: 'Markup',
    color: 'text-success',
    icon: '📈',
    description: 'Price advancing, trend underway'
  },
  DISTRIBUTION: {
    label: 'Distribution',
    color: 'text-orange-500',
    icon: '📤',
    description: 'Smart money selling to retail at highs'
  },
  MARKDOWN: {
    label: 'Markdown',
    color: 'text-destructive',
    icon: '📉',
    description: 'Price declining, downtrend underway'
  }
};
