export type SniperMode = 
  | 'overwatch'
  | 'recon'
  | 'strike'
  | 'rapid-fire'
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
    minConfluence: 80,
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
    minConfluence: 70,
    holdingPeriod: 'Minutes to hours',
    riskReward: 2.5,
    icon: '⚡'
  },
  'rapid-fire': {
    mode: 'rapid-fire',
    name: '🔥 Rapid Fire',
    description: 'High-frequency engagement. Multiple quick strikes, maximum precision required.',
    timeframes: ['15m', '5m', '1m'],
    minConfluence: 65,
    holdingPeriod: 'Seconds to minutes',
    riskReward: 2.0,
    icon: '🔥'
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
