import { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  TrendUp,
  TrendDown,
  Target,
  ArrowsCounterClockwise,
  ArrowLeft,
  ArrowRight,
  Minus,
} from '@phosphor-icons/react';

// ============================================
// CYCLE PHASE GRAPHIC
// A wave showing the 4 phases with animated marker
// ============================================

type CyclePhase = 'ACCUMULATION' | 'MARKUP' | 'DISTRIBUTION' | 'MARKDOWN' | 'UNKNOWN';

const PHASE_CONFIG: Record<CyclePhase, {
  position: number; // 0-100 along the wave
  color: string;
  glowColor: string;
  label: string;
  description: string;
}> = {
  'ACCUMULATION': {
    position: 12,
    color: 'text-success',
    glowColor: 'shadow-success/50',
    label: 'ACCUMULATION',
    description: 'Smart money accumulating'
  },
  'MARKUP': {
    position: 37,
    color: 'text-blue-400',
    glowColor: 'shadow-blue-400/50',
    label: 'MARKUP',
    description: 'Price rising from cycle low'
  },
  'DISTRIBUTION': {
    position: 62,
    color: 'text-warning',
    glowColor: 'shadow-warning/50',
    label: 'DISTRIBUTION',
    description: 'Smart money distributing'
  },
  'MARKDOWN': {
    position: 87,
    color: 'text-destructive',
    glowColor: 'shadow-destructive/50',
    label: 'MARKDOWN',
    description: 'Price falling to next low'
  },
  'UNKNOWN': {
    position: 50,
    color: 'text-muted-foreground',
    glowColor: 'shadow-muted/50',
    label: 'ANALYZING',
    description: 'Determining phase...'
  },
};

export function CyclePhaseGraphic({
  phase,
  onClick,
  compact = false,
  timeframeLabel
}: {
  phase: CyclePhase;
  onClick?: () => void;
  compact?: boolean;
  timeframeLabel?: string;
}) {
  const [hovered, setHovered] = useState(false);
  const config = PHASE_CONFIG[phase] || PHASE_CONFIG['UNKNOWN'];
  const labelText = timeframeLabel || 'DAILY CYCLE';

  // Wave path - starts low (accumulation), rises (markup), peaks (distribution), falls (markdown)
  const wavePath = "M 0,70 Q 25,70 25,70 T 50,30 T 75,30 T 100,70";
  const wavePathFilled = "M 0,70 Q 25,70 25,70 T 50,30 T 75,30 T 100,70 L 100,100 L 0,100 Z";

  // Calculate marker position on the wave
  const getMarkerY = (x: number): number => {
    // Approximate the wave curve
    if (x < 25) return 70;
    if (x < 50) return 70 - ((x - 25) / 25) * 40;
    if (x < 75) return 30;
    return 30 + ((x - 75) / 25) * 40;
  };

  const markerX = config.position;
  const markerY = getMarkerY(markerX);

  return (
    <div
      className={cn(
        'relative rounded-xl border border-border/30 bg-muted/10 overflow-hidden transition-all duration-300 cursor-pointer',
        'hover:border-accent/40 hover:bg-muted/20',
        compact ? 'p-3' : 'p-4',
        onClick && 'cursor-pointer'
      )}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* SVG Wave Graphic */}
      <div className={cn('relative', compact ? 'h-16' : 'h-20')}>
        <svg
          viewBox="0 0 100 100"
          className="w-full h-full"
          preserveAspectRatio="none"
        >
          {/* Background gradient fill */}
          <defs>
            <linearGradient id="waveGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="rgb(34, 197, 94)" stopOpacity="0.2" />
              <stop offset="25%" stopColor="rgb(96, 165, 250)" stopOpacity="0.2" />
              <stop offset="50%" stopColor="rgb(96, 165, 250)" stopOpacity="0.2" />
              <stop offset="75%" stopColor="rgb(234, 179, 8)" stopOpacity="0.2" />
              <stop offset="100%" stopColor="rgb(239, 68, 68)" stopOpacity="0.2" />
            </linearGradient>
            <linearGradient id="waveStroke" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="rgb(34, 197, 94)" />
              <stop offset="25%" stopColor="rgb(96, 165, 250)" />
              <stop offset="50%" stopColor="rgb(96, 165, 250)" />
              <stop offset="75%" stopColor="rgb(234, 179, 8)" />
              <stop offset="100%" stopColor="rgb(239, 68, 68)" />
            </linearGradient>
          </defs>

          {/* Filled area under wave */}
          <path
            d={wavePathFilled}
            fill="url(#waveGradient)"
            className="transition-opacity duration-300"
            opacity={hovered ? 0.8 : 0.5}
          />

          {/* Wave line */}
          <path
            d={wavePath}
            fill="none"
            stroke="url(#waveStroke)"
            strokeWidth="2"
            strokeLinecap="round"
            className="transition-all duration-300"
          />

          {/* Phase labels along bottom */}
          <text x="12" y="95" className="fill-muted-foreground text-[6px] font-mono">ACC</text>
          <text x="37" y="95" className="fill-muted-foreground text-[6px] font-mono">MKP</text>
          <text x="62" y="95" className="fill-muted-foreground text-[6px] font-mono">DST</text>
          <text x="87" y="95" className="fill-muted-foreground text-[6px] font-mono">MKD</text>

          {/* Animated marker */}
          <g className="transition-all duration-500" style={{ transform: `translate(${markerX}px, ${markerY}px)` }}>
            {/* Outer glow ring */}
            <circle
              cx="0"
              cy="0"
              r="8"
              className={cn('fill-current opacity-20 animate-ping', config.color)}
              style={{ animationDuration: '2s' }}
            />
            {/* Inner solid circle */}
            <circle
              cx="0"
              cy="0"
              r="5"
              className={cn('fill-current', config.color)}
            />
            {/* Center dot */}
            <circle cx="0" cy="0" r="2" className="fill-white" />
          </g>

          {/* Vertical line from marker */}
          <line
            x1={markerX}
            y1={markerY + 8}
            x2={markerX}
            y2="85"
            stroke="currentColor"
            strokeWidth="1"
            strokeDasharray="2,2"
            className={cn('transition-all duration-500 opacity-30', config.color)}
          />
        </svg>
      </div>

      {/* Label */}
      <div className={cn('text-center', compact ? 'mt-1' : 'mt-2')}>
        {!compact && (
          <div className="text-[9px] text-accent/70 font-mono tracking-wider mb-0.5">{labelText}</div>
        )}
        <div className={cn('font-bold tracking-wider', config.color, compact ? 'text-sm' : 'text-base')}>
          {config.label}
        </div>
        {!compact && (
          <div className="text-[10px] text-muted-foreground mt-0.5">
            {config.description}
          </div>
        )}
      </div>

      {/* Hover tooltip */}
      {hovered && compact && (
        <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 px-2 py-1 bg-popover border border-border rounded text-[10px] text-muted-foreground whitespace-nowrap z-10">
          {config.description}
        </div>
      )}
    </div>
  );
}

// ============================================
// TRANSLATION GRAPHIC
// A balance beam showing left/mid/right translation
// ============================================

type Translation = 'LEFT_TRANSLATED' | 'MID_TRANSLATED' | 'RIGHT_TRANSLATED' | 'UNKNOWN';

const TRANSLATION_CONFIG: Record<Translation, {
  position: number; // -1 (left), 0 (mid), 1 (right)
  color: string;
  bgColor: string;
  label: string;
  bias: string;
}> = {
  'LEFT_TRANSLATED': {
    position: -1,
    color: 'text-destructive',
    bgColor: 'bg-destructive',
    label: 'LEFT TRANSLATED',
    bias: 'Bearish - topped early'
  },
  'MID_TRANSLATED': {
    position: 0,
    color: 'text-warning',
    bgColor: 'bg-warning',
    label: 'MID TRANSLATED',
    bias: 'Neutral - balanced'
  },
  'RIGHT_TRANSLATED': {
    position: 1,
    color: 'text-success',
    bgColor: 'bg-success',
    label: 'RIGHT TRANSLATED',
    bias: 'Bullish - topped late'
  },
  'UNKNOWN': {
    position: 0,
    color: 'text-muted-foreground',
    bgColor: 'bg-muted',
    label: 'PENDING',
    bias: 'Awaiting cycle high'
  },
};

export function TranslationGraphic({
  translation,
  onClick,
  compact = false,
  timeframeLabel
}: {
  translation: Translation;
  onClick?: () => void;
  compact?: boolean;
  timeframeLabel?: string;
}) {
  const [hovered, setHovered] = useState(false);
  const config = TRANSLATION_CONFIG[translation] || TRANSLATION_CONFIG['UNKNOWN'];
  const labelText = timeframeLabel || 'DAILY CYCLE';

  // Map position (-1, 0, 1) to percentage (15%, 50%, 85%)
  const markerPosition = 50 + (config.position * 35);

  return (
    <div
      className={cn(
        'relative rounded-xl border border-border/30 bg-muted/10 overflow-hidden transition-all duration-300',
        'hover:border-accent/40 hover:bg-muted/20',
        compact ? 'p-3' : 'p-4',
        onClick && 'cursor-pointer'
      )}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Balance Beam Graphic */}
      <div className={cn('relative', compact ? 'h-16' : 'h-20')}>
        <svg viewBox="0 0 100 80" className="w-full h-full" preserveAspectRatio="xMidYMid meet">
          {/* Background zones */}
          <rect x="5" y="30" width="28" height="25" rx="3" className="fill-destructive/10" />
          <rect x="36" y="30" width="28" height="25" rx="3" className="fill-warning/10" />
          <rect x="67" y="30" width="28" height="25" rx="3" className="fill-success/10" />

          {/* Zone labels */}
          <text x="19" y="70" textAnchor="middle" className="fill-destructive/50 text-[7px] font-mono">LEFT</text>
          <text x="50" y="70" textAnchor="middle" className="fill-warning/50 text-[7px] font-mono">MID</text>
          <text x="81" y="70" textAnchor="middle" className="fill-success/50 text-[7px] font-mono">RIGHT</text>

          {/* Arrows */}
          <path d="M 10,42 L 5,42 L 10,38 M 5,42 L 10,46" stroke="currentColor" strokeWidth="1.5" fill="none" className="text-destructive/40" />
          <path d="M 90,42 L 95,42 L 90,38 M 95,42 L 90,46" stroke="currentColor" strokeWidth="1.5" fill="none" className="text-success/40" />

          {/* Center line */}
          <line x1="50" y1="25" x2="50" y2="58" stroke="currentColor" strokeWidth="1" strokeDasharray="2,2" className="text-muted-foreground/30" />

          {/* Balance beam */}
          <line x1="10" y1="42" x2="90" y2="42" stroke="currentColor" strokeWidth="3" strokeLinecap="round" className="text-muted/40" />

          {/* Tick marks */}
          <line x1="19" y1="38" x2="19" y2="46" stroke="currentColor" strokeWidth="1" className="text-muted-foreground/30" />
          <line x1="50" y1="38" x2="50" y2="46" stroke="currentColor" strokeWidth="1.5" className="text-muted-foreground/50" />
          <line x1="81" y1="38" x2="81" y2="46" stroke="currentColor" strokeWidth="1" className="text-muted-foreground/30" />

          {/* Animated marker */}
          <g
            className="transition-all duration-700 ease-out"
            style={{ transform: `translateX(${markerPosition - 50}px)` }}
          >
            {/* Glow */}
            <circle
              cx="50"
              cy="42"
              r="10"
              className={cn('fill-current opacity-20 animate-pulse', config.color)}
            />
            {/* Marker body */}
            <circle
              cx="50"
              cy="42"
              r="7"
              className={cn('fill-current', config.color)}
            />
            {/* Arrow indicator */}
            {config.position === -1 && (
              <path d="M 46,42 L 50,38 L 50,46 Z" className="fill-white/80" />
            )}
            {config.position === 1 && (
              <path d="M 54,42 L 50,38 L 50,46 Z" className="fill-white/80" />
            )}
            {config.position === 0 && (
              <circle cx="50" cy="42" r="2" className="fill-white/80" />
            )}
          </g>

          {/* Pivot point */}
          <path d="M 50,55 L 45,65 L 55,65 Z" className="fill-muted/30" />
        </svg>
      </div>

      {/* Label */}
      <div className={cn('text-center', compact ? 'mt-1' : 'mt-2')}>
        <div className="text-[9px] text-muted-foreground/60 font-mono tracking-widest mb-0.5">{labelText}</div>
        <div className={cn('font-bold tracking-wider', config.color, compact ? 'text-sm' : 'text-base')}>
          {config.label}
        </div>
        {!compact && (
          <div className="text-[10px] text-muted-foreground mt-0.5">
            {config.bias}
          </div>
        )}
      </div>

      {/* Hover tooltip */}
      {hovered && compact && (
        <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 px-2 py-1 bg-popover border border-border rounded text-[10px] text-muted-foreground whitespace-nowrap z-10">
          {config.bias}
        </div>
      )}
    </div>
  );
}

// ============================================
// STOCH RSI ZONE GRAPHIC
// A thermometer/tank gauge showing oversold/overbought
// ============================================

type StochZone = 'oversold' | 'overbought' | 'neutral';

const ZONE_CONFIG: Record<StochZone, {
  color: string;
  bgColor: string;
  label: string;
  description: string;
}> = {
  'oversold': {
    color: 'text-success',
    bgColor: 'bg-success',
    label: 'OVERSOLD',
    description: 'Bullish reversal zone'
  },
  'overbought': {
    color: 'text-destructive',
    bgColor: 'bg-destructive',
    label: 'OVERBOUGHT',
    description: 'Bearish reversal zone'
  },
  'neutral': {
    color: 'text-muted-foreground',
    bgColor: 'bg-muted',
    label: 'NEUTRAL',
    description: 'No extreme reading'
  },
};

export function StochRSIGraphic({
  k,
  d,
  zone,
  onClick,
  compact = false
}: {
  k: number | null;
  d: number | null;
  zone: StochZone;
  onClick?: () => void;
  compact?: boolean;
}) {
  const [hovered, setHovered] = useState(false);
  const config = ZONE_CONFIG[zone] || ZONE_CONFIG['neutral'];

  const kValue = k ?? 50;
  const dValue = d ?? 50;

  // Invert for visual (0 at bottom, 100 at top)
  const kPosition = 100 - kValue;
  const dPosition = 100 - dValue;

  // Determine fill color based on zone
  const getFillGradient = () => {
    if (zone === 'oversold') return 'url(#oversoldGradient)';
    if (zone === 'overbought') return 'url(#overboughtGradient)';
    return 'url(#neutralGradient)';
  };

  return (
    <div
      className={cn(
        'relative rounded-xl border border-border/30 bg-muted/10 overflow-hidden transition-all duration-300',
        'hover:border-accent/40 hover:bg-muted/20',
        compact ? 'p-3' : 'p-4',
        onClick && 'cursor-pointer'
      )}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Thermometer Graphic */}
      <div className={cn('relative flex items-center justify-center', compact ? 'h-16' : 'h-20')}>
        <svg viewBox="0 0 100 80" className="w-full h-full" preserveAspectRatio="xMidYMid meet">
          <defs>
            {/* Gradients for fill */}
            <linearGradient id="oversoldGradient" x1="0%" y1="100%" x2="0%" y2="0%">
              <stop offset="0%" stopColor="rgb(34, 197, 94)" stopOpacity="0.8" />
              <stop offset="100%" stopColor="rgb(34, 197, 94)" stopOpacity="0.2" />
            </linearGradient>
            <linearGradient id="overboughtGradient" x1="0%" y1="100%" x2="0%" y2="0%">
              <stop offset="0%" stopColor="rgb(239, 68, 68)" stopOpacity="0.2" />
              <stop offset="100%" stopColor="rgb(239, 68, 68)" stopOpacity="0.8" />
            </linearGradient>
            <linearGradient id="neutralGradient" x1="0%" y1="100%" x2="0%" y2="0%">
              <stop offset="0%" stopColor="rgb(148, 163, 184)" stopOpacity="0.3" />
              <stop offset="100%" stopColor="rgb(148, 163, 184)" stopOpacity="0.3" />
            </linearGradient>
            <linearGradient id="tankBg" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="rgb(239, 68, 68)" stopOpacity="0.1" />
              <stop offset="20%" stopColor="rgb(234, 179, 8)" stopOpacity="0.05" />
              <stop offset="80%" stopColor="rgb(234, 179, 8)" stopOpacity="0.05" />
              <stop offset="100%" stopColor="rgb(34, 197, 94)" stopOpacity="0.1" />
            </linearGradient>
          </defs>

          {/* Tank outline */}
          <rect x="35" y="5" width="30" height="65" rx="4" fill="url(#tankBg)" stroke="currentColor" strokeWidth="1" className="text-border/50" />

          {/* Zone markers */}
          <line x1="30" y1="18" x2="35" y2="18" stroke="currentColor" strokeWidth="1" className="text-destructive/50" />
          <text x="27" y="20" textAnchor="end" className="fill-destructive/50 text-[6px] font-mono">80</text>

          <line x1="30" y1="57" x2="35" y2="57" stroke="currentColor" strokeWidth="1" className="text-success/50" />
          <text x="27" y="59" textAnchor="end" className="fill-success/50 text-[6px] font-mono">20</text>

          {/* Overbought zone highlight */}
          <rect x="36" y="6" width="28" height="12" rx="2" className="fill-destructive/10" />
          <text x="73" y="14" className="fill-destructive/40 text-[5px] font-mono">OB</text>

          {/* Oversold zone highlight */}
          <rect x="36" y="52" width="28" height="17" rx="2" className="fill-success/10" />
          <text x="73" y="62" className="fill-success/40 text-[5px] font-mono">OS</text>

          {/* Fill level based on K value */}
          <rect
            x="38"
            y={8 + (kPosition * 0.58)}
            width="24"
            height={60 - (kPosition * 0.58)}
            rx="2"
            fill={getFillGradient()}
            className="transition-all duration-700"
          />

          {/* K line marker */}
          <g className="transition-all duration-700" style={{ transform: `translateY(${kPosition * 0.58}px)` }}>
            <line x1="36" y1="8" x2="64" y2="8" stroke="currentColor" strokeWidth="2" className={config.color} />
            <circle cx="64" cy="8" r="3" className={cn('fill-current', config.color)} />
            <text x="70" y="10" className={cn('text-[7px] font-bold', config.color)}>K</text>
          </g>

          {/* D line marker */}
          <g className="transition-all duration-700" style={{ transform: `translateY(${dPosition * 0.58}px)` }}>
            <line x1="40" y1="8" x2="60" y2="8" stroke="currentColor" strokeWidth="1.5" strokeDasharray="2,1" className="text-muted-foreground" />
            <text x="70" y="10" className="fill-muted-foreground text-[6px]">D</text>
          </g>

          {/* Zone indicator checkmark for oversold */}
          {zone === 'oversold' && (
            <g className="animate-pulse">
              <circle cx="85" cy="60" r="6" className="fill-success/20" />
              <path d="M 82,60 L 84,62 L 88,57" stroke="currentColor" strokeWidth="1.5" fill="none" className="text-success" />
            </g>
          )}

          {/* Zone indicator warning for overbought */}
          {zone === 'overbought' && (
            <g className="animate-pulse">
              <circle cx="85" cy="12" r="6" className="fill-destructive/20" />
              <text x="85" y="15" textAnchor="middle" className="fill-destructive text-[8px] font-bold">!</text>
            </g>
          )}
        </svg>
      </div>

      {/* Label and values */}
      <div className={cn('text-center', compact ? 'mt-1' : 'mt-2')}>
        <div className="text-[9px] text-muted-foreground/60 font-mono tracking-widest mb-0.5">WEEKLY</div>
        <div className={cn('font-bold tracking-wider', config.color, compact ? 'text-sm' : 'text-base')}>
          {config.label}
        </div>
        <div className="text-[10px] text-muted-foreground mt-0.5 font-mono">
          K:{kValue.toFixed(1)} D:{dValue.toFixed(1)}
        </div>
        {!compact && (
          <div className="text-[10px] text-muted-foreground mt-0.5">
            {config.description}
          </div>
        )}
      </div>

      {/* Hover tooltip */}
      {hovered && compact && (
        <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 px-2 py-1 bg-popover border border-border rounded text-[10px] text-muted-foreground whitespace-nowrap z-10">
          {config.description}
        </div>
      )}
    </div>
  );
}

// ============================================
// EXPORT ALL
// ============================================

export type { CyclePhase, Translation, StochZone };
