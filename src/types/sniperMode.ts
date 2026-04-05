export type SniperMode = 
  | 'overwatch'
  | 'recon'
  | 'strike'
  | 'surgical'
  | 'ghost'   // legacy alias → stealth
  | 'stealth'
  | 'custom';

export interface SniperModeConfig {
  mode: SniperMode;
  name: string;
  description: string;
  timeframes: string[];
  minConfluence: number;
  holdingPeriod: string;
  riskReward: number;
  icon: string;
}

export const SNIPER_MODES: Record<SniperMode, SniperModeConfig> = {
  'overwatch': {
    mode: 'overwatch',
    name: '🔭 Overwatch',
    description: 'Patient positioning. Monitor from distance, strike when opportunity is perfect.',
    timeframes: ['1d', '4h', '1h'],
    minConfluence: 72,
    holdingPeriod: 'Days to weeks',
    riskReward: 3.5,
    icon: '🔭'
  },
  'recon': {
    mode: 'recon',
    name: '🎯 Recon',
    description: 'Intelligence gathering. Scout the market, identify high-value targets.',
    timeframes: ['4h', '1h', '15m'],
    minConfluence: 75,
    holdingPeriod: 'Hours to days',
    riskReward: 2.8,
    icon: '🎯'
  },
  'strike': {
    mode: 'strike',
    name: '⚡ Strike',
    description: 'Tactical execution. Fast deployment, precise timing, quick extraction.',
    timeframes: ['1h', '15m', '5m'],
    minConfluence: 62,
    holdingPeriod: 'Minutes to hours',
    riskReward: 2.5,
    icon: '⚡'
  },
  'surgical': {
    mode: 'surgical',
    name: '🎯 Surgical',
    description: 'Precision-focused lower timeframe analysis. For experienced traders seeking exact entries.',
    timeframes: ['1h', '15m', '5m'],
    minConfluence: 65,
    holdingPeriod: 'Minutes to hours',
    riskReward: 2.2,
    icon: '🎯'
  },
  'ghost': {
    mode: 'ghost',
    name: '👻 Ghost',
    description: 'Legacy alias for Stealth mode. Use stealth for new setups.',
    timeframes: ['1d', '4h', '1h', '15m', '5m'],
    minConfluence: 70,
    holdingPeriod: 'Hours to days',
    riskReward: 1.8,
    icon: '👻'
  },
  'stealth': {
    mode: 'stealth',
    name: '🥷 Stealth',
    description: 'Balanced swing trading with multi-TF confluence. Adaptable and mission-ready.',
    timeframes: ['1d', '4h', '1h', '15m', '5m'],
    minConfluence: 65,
    holdingPeriod: 'Hours to days',
    riskReward: 1.8,
    icon: '🥷'
  },
  'custom': {
    mode: 'custom',
    name: '⚙️ Custom Mission',
    description: 'Advanced operators only. Configure your own parameters.',
    timeframes: [],
    minConfluence: 70,
    holdingPeriod: 'Varies',
    riskReward: 2.5,
    icon: '⚙️'
  }
};
