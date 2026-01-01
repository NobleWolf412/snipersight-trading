/**
 * 4-Year Cycle Gauge Component
 * 
 * Displays Bitcoin's position within the ~4-year halving cycle.
 * Based on Camel Finance methodology - provides macro context for all trades.
 * 
 * Usage:
 *   <FourYearCycleGauge data={cycleData} />
 *   <FourYearCycleGauge data={cycleData} compact />
 */

import { cn } from '@/lib/utils';
import { Target, Warning, TrendUp, Clock, CaretRight } from '@phosphor-icons/react';

export interface FourYearCycleData {
  days_since_low: number;
  days_until_expected_low: number;
  cycle_position_pct: number;
  phase: 'ACCUMULATION' | 'MARKUP' | 'DISTRIBUTION' | 'MARKDOWN' | 'UNKNOWN';
  phase_progress_pct: number;
  last_low: {
    date: string;
    price: number;
    event: string;
  };
  expected_next_low: string;
  macro_bias: 'BULLISH' | 'NEUTRAL' | 'BEARISH';
  confidence: number;
  zones: {
    is_danger_zone: boolean;
    is_opportunity_zone: boolean;
  };
}

interface Props {
  data: FourYearCycleData | null;
  compact?: boolean;
  className?: string;
}

const PHASE_CONFIG = {
  ACCUMULATION: {
    color: 'text-blue-400',
    bg: 'bg-blue-500/20',
    border: 'border-blue-500/40',
    glow: 'shadow-blue-500/20',
    label: 'ACCUMULATION',
    icon: '📦',
    description: 'Smart money loading - optimal entry zone',
    gradient: 'from-blue-600 to-blue-400'
  },
  MARKUP: {
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/20',
    border: 'border-emerald-500/40',
    glow: 'shadow-emerald-500/20',
    label: 'MARKUP',
    icon: '🚀',
    description: 'Bull market expansion - ride the trend',
    gradient: 'from-emerald-600 to-emerald-400'
  },
  DISTRIBUTION: {
    color: 'text-amber-400',
    bg: 'bg-amber-500/20',
    border: 'border-amber-500/40',
    glow: 'shadow-amber-500/20',
    label: 'DISTRIBUTION',
    icon: '⚠️',
    description: 'Smart money exiting - manage risk carefully',
    gradient: 'from-amber-600 to-amber-400'
  },
  MARKDOWN: {
    color: 'text-red-400',
    bg: 'bg-red-500/20',
    border: 'border-red-500/40',
    glow: 'shadow-red-500/20',
    label: 'MARKDOWN',
    icon: '📉',
    description: 'Bear market - preserve capital',
    gradient: 'from-red-600 to-red-400'
  },
  UNKNOWN: {
    color: 'text-gray-400',
    bg: 'bg-gray-500/20',
    border: 'border-gray-500/40',
    glow: 'shadow-gray-500/20',
    label: 'UNKNOWN',
    icon: '❓',
    description: 'Cycle position unclear',
    gradient: 'from-gray-600 to-gray-400'
  }
};

const BIAS_CONFIG = {
  BULLISH: {
    color: 'text-success',
    bg: 'bg-success/20',
    border: 'border-success/40',
    icon: '🟢'
  },
  NEUTRAL: {
    color: 'text-muted-foreground',
    bg: 'bg-muted/20',
    border: 'border-muted/40',
    icon: '🟡'
  },
  BEARISH: {
    color: 'text-destructive',
    bg: 'bg-destructive/20',
    border: 'border-destructive/40',
    icon: '🔴'
  }
};

/**
 * Compact badge version for headers/sidebars
 */
function CompactBadge({ data }: { data: FourYearCycleData }) {
  const config = PHASE_CONFIG[data.phase];
  const biasConfig = BIAS_CONFIG[data.macro_bias];

  return (
    <div className={cn(
      "px-3 py-2 rounded-lg border flex items-center gap-3 transition-all hover:shadow-lg",
      config.bg, config.border, config.glow
    )}>
      <div className="text-lg">{config.icon}</div>
      <div className="flex-1 min-w-0">
        <div className={cn("text-xs font-bold tracking-wide truncate", config.color)}>
          4YC: {config.label}
        </div>
        <div className="text-[10px] text-muted-foreground font-mono">
          Day {data.days_since_low.toLocaleString()} • {data.cycle_position_pct.toFixed(0)}%
        </div>
      </div>
      <div className={cn(
        "px-2 py-0.5 rounded text-[10px] font-bold shrink-0",
        biasConfig.bg, biasConfig.color
      )}>
        {biasConfig.icon} {data.macro_bias}
      </div>
    </div>
  );
}

/**
 * Arc visualization for cycle position
 */
function CycleArc({ position, phase }: { position: number; phase: string }) {
  const config = PHASE_CONFIG[phase as keyof typeof PHASE_CONFIG] || PHASE_CONFIG.UNKNOWN;

  // SVG arc path calculation
  // Arc goes from left (0%) to right (100%)
  const radius = 80;
  const centerX = 100;
  const centerY = 90;
  const startAngle = Math.PI; // 180 degrees (left)
  const endAngle = 0; // 0 degrees (right)

  // Calculate current position on arc
  const currentAngle = startAngle - (position / 100) * Math.PI;
  const markerX = centerX + radius * Math.cos(currentAngle);
  const markerY = centerY - radius * Math.sin(currentAngle);

  return (
    <svg viewBox="0 0 200 100" className="w-full max-w-xs">
      {/* Background track */}
      <path
        d="M 20 90 A 80 80 0 0 1 180 90"
        fill="none"
        stroke="currentColor"
        strokeWidth="12"
        strokeLinecap="round"
        className="text-muted/10"
      />

      {/* Phase segment: Accumulation (0-25%) */}
      <path
        d="M 20 90 A 80 80 0 0 1 60 30"
        fill="none"
        stroke="currentColor"
        strokeWidth="10"
        strokeLinecap="round"
        className="text-blue-500/30"
      />

      {/* Phase segment: Markup (25-50%) */}
      <path
        d="M 60 30 A 80 80 0 0 1 100 10"
        fill="none"
        stroke="currentColor"
        strokeWidth="10"
        className="text-emerald-500/30"
      />

      {/* Phase segment: Distribution (50-75%) */}
      <path
        d="M 100 10 A 80 80 0 0 1 140 30"
        fill="none"
        stroke="currentColor"
        strokeWidth="10"
        className="text-amber-500/30"
      />

      {/* Phase segment: Markdown (75-100%) */}
      <path
        d="M 140 30 A 80 80 0 0 1 180 90"
        fill="none"
        stroke="currentColor"
        strokeWidth="10"
        strokeLinecap="round"
        className="text-red-500/30"
      />

      {/* Progress arc (filled portion) */}
      <path
        d={`M 20 90 A 80 80 0 ${position > 50 ? 1 : 0} 1 ${markerX} ${markerY}`}
        fill="none"
        stroke="url(#progressGradient)"
        strokeWidth="10"
        strokeLinecap="round"
      />

      {/* Gradient definition */}
      <defs>
        <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#3b82f6" />
          <stop offset="33%" stopColor="#10b981" />
          <stop offset="66%" stopColor="#f59e0b" />
          <stop offset="100%" stopColor="#ef4444" />
        </linearGradient>
      </defs>

      {/* Current position marker */}
      <circle
        cx={markerX}
        cy={markerY}
        r="10"
        className={cn("fill-current", config.color)}
      />
      <circle
        cx={markerX}
        cy={markerY}
        r="6"
        className="fill-background"
      />
      <circle
        cx={markerX}
        cy={markerY}
        r="4"
        className={cn("fill-current", config.color)}
      />

      {/* Phase labels */}
      <text x="20" y="98" className="text-[8px] fill-blue-400 font-mono">ACC</text>
      <text x="60" y="20" className="text-[8px] fill-emerald-400 font-mono">MKP</text>
      <text x="125" y="20" className="text-[8px] fill-amber-400 font-mono">DST</text>
      <text x="165" y="98" className="text-[8px] fill-red-400 font-mono">MKD</text>
    </svg>
  );
}

/**
 * Full 4-Year Cycle Gauge Component
 */
export function FourYearCycleGauge({ data, compact = false, className }: Props) {
  // Handle no data state
  if (!data) {
    return (
      <div className={cn(
        "rounded-xl border border-border/40 bg-card/50 p-4 text-center",
        className
      )}>
        <div className="text-muted-foreground text-sm">
          4-Year cycle data unavailable
        </div>
      </div>
    );
  }

  // Normalize data with safe defaults for potentially missing API fields
  const safeData = {
    days_since_low: data.days_since_low ?? 0,
    days_until_expected_low: data.days_until_expected_low ?? 0,
    cycle_position_pct: data.cycle_position_pct ?? 0,
    phase: data.phase ?? 'UNKNOWN',
    phase_progress_pct: data.phase_progress_pct ?? 0,
    macro_bias: data.macro_bias ?? 'NEUTRAL',
    confidence: data.confidence ?? 0,
    last_low: {
      date: data.last_low?.date ?? '2022-11-21',
      price: data.last_low?.price ?? 0,
      event: data.last_low?.event ?? 'Unknown'
    },
    expected_next_low: data.expected_next_low ?? '2026-10-15',
    zones: {
      is_danger_zone: data.zones?.is_danger_zone ?? false,
      is_opportunity_zone: data.zones?.is_opportunity_zone ?? false
    }
  };

  const config = PHASE_CONFIG[safeData.phase as keyof typeof PHASE_CONFIG] || PHASE_CONFIG.UNKNOWN;
  const biasConfig = BIAS_CONFIG[safeData.macro_bias as keyof typeof BIAS_CONFIG] || BIAS_CONFIG.NEUTRAL;

  // Compact version
  if (compact) {
    return <CompactBadge data={safeData as FourYearCycleData} />;
  }

  // Full version
  return (
    <div className={cn(
      "rounded-xl border border-border/40 bg-card/50 backdrop-blur-sm overflow-hidden",
      className
    )}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-border/30 bg-muted/10 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Target size={16} className="text-accent" weight="bold" />
          <span className="text-xs font-bold tracking-[0.15em]">4-YEAR HALVING CYCLE</span>
          <span className="text-[10px] text-muted-foreground font-mono">BTC MACRO</span>
        </div>
        <div className="flex items-center gap-2">
          {safeData.zones.is_danger_zone && (
            <div className="flex items-center gap-1 px-2 py-0.5 rounded bg-destructive/20 text-destructive text-[10px] font-bold animate-pulse">
              <Warning size={12} weight="fill" />
              DANGER ZONE
            </div>
          )}
          {safeData.zones.is_opportunity_zone && (
            <div className="flex items-center gap-1 px-2 py-0.5 rounded bg-success/20 text-success text-[10px] font-bold">
              <TrendUp size={12} weight="bold" />
              OPPORTUNITY
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="p-6">
        {/* Arc Visualization */}
        <div className="relative flex flex-col items-center mb-6">
          <CycleArc position={safeData.cycle_position_pct} phase={safeData.phase} />

          {/* Center Stats Overlay */}
          <div className="absolute inset-0 flex flex-col items-center justify-center pt-4">
            <div className={cn("text-5xl font-bold", config.color)}>
              {safeData.cycle_position_pct.toFixed(0)}%
            </div>
            <div className="text-xs text-muted-foreground font-mono">
              Day {safeData.days_since_low.toLocaleString()}
            </div>
          </div>
        </div>

        {/* Phase Card */}
        <div className={cn(
          "p-4 rounded-lg text-center border transition-all",
          config.bg, config.border
        )}>
          <div className="text-3xl mb-2">{config.icon}</div>
          <div className={cn("text-xl font-bold mb-1 tracking-wide", config.color)}>
            {config.label}
          </div>
          <div className="text-sm text-muted-foreground mb-3">
            {config.description}
          </div>

          {/* Phase Progress Bar */}
          <div className="relative pt-1">
            <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
              <span>Phase Start</span>
              <span>{safeData.phase_progress_pct.toFixed(0)}% through</span>
              <span>Phase End</span>
            </div>
            <div className="h-2 bg-black/40 rounded-full overflow-hidden">
              <div
                className={cn("h-full rounded-full bg-gradient-to-r", config.gradient)}
                style={{ width: `${safeData.phase_progress_pct}%` }}
              />
            </div>
          </div>
        </div>

        {/* Macro Bias Badge */}
        <div className="flex justify-center mt-4">
          <div className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-lg border",
            biasConfig.bg, biasConfig.border
          )}>
            <span className="text-lg">{biasConfig.icon}</span>
            <div>
              <div className={cn("text-sm font-bold", biasConfig.color)}>
                MACRO BIAS: {safeData.macro_bias}
              </div>
              <div className="text-[10px] text-muted-foreground">
                {safeData.confidence.toFixed(0)}% confidence
              </div>
            </div>
          </div>
        </div>

        {/* Key Dates Grid */}
        <div className="grid grid-cols-2 gap-4 mt-6">
          <div className="p-3 rounded-lg bg-muted/10 border border-border/20">
            <div className="flex items-center gap-2 text-[10px] text-muted-foreground mb-1">
              <Clock size={12} />
              LAST 4YC LOW
            </div>
            <div className="text-sm font-bold">
              {new Date(safeData.last_low.date).toLocaleDateString('en-US', {
                month: 'short',
                year: 'numeric'
              })}
            </div>
            <div className="text-xs text-muted-foreground">
              ${safeData.last_low.price.toLocaleString()}
            </div>
            <div className="text-[10px] text-muted-foreground/70 mt-1 truncate" title={safeData.last_low.event}>
              {safeData.last_low.event}
            </div>
          </div>

          <div className="p-3 rounded-lg bg-muted/10 border border-border/20">
            <div className="flex items-center gap-2 text-[10px] text-muted-foreground mb-1">
              <Target size={12} />
              EXPECTED NEXT LOW
            </div>
            <div className="text-sm font-bold">
              {new Date(safeData.expected_next_low).toLocaleDateString('en-US', {
                month: 'short',
                year: 'numeric'
              })}
            </div>
            <div className="text-xs text-muted-foreground">
              ~{safeData.days_until_expected_low.toLocaleString()} days
            </div>
            <div className="text-[10px] text-muted-foreground/70 mt-1">
              Est. {new Date(safeData.expected_next_low).getFullYear()}
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-border/30 bg-muted/5 flex items-center justify-between">
        <span className="text-[10px] text-muted-foreground">
          Based on Nov 2022 bottom • Camel Finance methodology
        </span>
        <div className="flex items-center gap-1 text-[10px] text-accent">
          <span>View Details</span>
          <CaretRight size={10} />
        </div>
      </div>
    </div>
  );
}

export default FourYearCycleGauge;
