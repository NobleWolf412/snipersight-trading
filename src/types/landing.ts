import { ComponentType } from 'react';
import type { IconProps } from '@phosphor-icons/react';

export interface Badge {
  key: string;
  title: string;
  value: string | number;
  icon: ComponentType<{ size?: number }>;
  accent?: 'accent' | 'success' | 'warning' | 'foreground';
}

export interface Metric {
  key: string;
  title: string;
  value: number | string;
  hint?: string;
  unit?: string;
  accent?: 'accent' | 'success' | 'warning' | 'destructive' | 'muted';
}

export interface ModuleDef {
  key: string;
  title: string;
  description: string;
  icon: ComponentType<IconProps>;
  destination: string;
  tier: 'primary' | 'secondary';
  accent?: 'accent' | 'success' | 'warning' | 'foreground';
}

export interface SystemStatusData {
  exchangeStatus: 'connected' | 'degraded' | 'offline';
  latencyMs: number;
  activeTargets: number;
  signalsRejected: number;
  version: string;
}

export type ModuleClickHandler = (destination: string) => void;
