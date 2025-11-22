import { MagnifyingGlass, Robot, Target, Crosshair, ListBullets } from '@phosphor-icons/react';
import React from 'react';
import type { ModuleDef, Metric, Badge } from '@/types/landing';

// Lightweight stub icons (using createElement to avoid JSX in .ts file)
function ActivityStub({ size = 16 }: { size?: number }) {
  return React.createElement('span', { style: { fontSize: size } }, '📡');
}
function ShieldStub({ size = 16 }: { size?: number }) {
  return React.createElement('span', { style: { fontSize: size } }, '🛡️');
}

export const badges: Badge[] = [
  { key: 'telemetry', title: 'Telemetry', value: 'Live', icon: ActivityStub, accent: 'success' },
  { key: 'regime', title: 'Market Regime', value: 'Neutral', icon: Target, accent: 'accent' },
  { key: 'risk', title: 'Risk Engine', value: 'Armed', icon: ShieldStub, accent: 'warning' },
];

export const modules: ModuleDef[] = [
  {
    key: 'scanner',
    title: 'Recon Scanner',
    description: 'Sweep multi-timeframe price action for high-precision targets.',
    icon: MagnifyingGlass,
    destination: '/scan',
    tier: 'primary',
    accent: 'accent'
  },
  {
    key: 'bot',
    title: 'SniperBot',
    description: 'Automated execution with disciplined risk constraints.',
    icon: Robot,
    destination: '/bot',
    tier: 'primary',
    accent: 'warning'
  },
  {
    key: 'intel',
    title: 'Intel Desk',
    description: 'Review target plans, rationale and tactical breakdown.',
    icon: Target,
    destination: '/intel',
    tier: 'primary',
    accent: 'success'
  },
  {
    key: 'market',
    title: 'Market View',
    description: 'Charts, regime and volatility context.',
    icon: Crosshair,
    destination: '/market',
    tier: 'secondary'
  },
  {
    key: 'profiles',
    title: 'Profiles',
    description: 'Saved tactical loadouts & preference presets.',
    icon: ListBullets,
    destination: '/profiles',
    tier: 'secondary'
  }
];

export const initialMetrics: Metric[] = [
  { key: 'activeTargets', title: 'Active Targets', value: 0, hint: 'Currently tracked', accent: 'accent' },
  { key: 'signalsRejected', title: 'Rejected', value: 0, hint: 'Failed gates', accent: 'warning' },
  { key: 'exchangeStatus', title: 'Exchange', value: 'Connected', hint: 'Data source', accent: 'success' },
  { key: 'latencyMs', title: 'Latency (ms)', value: 0, hint: 'Round trip', accent: 'muted' }
];
