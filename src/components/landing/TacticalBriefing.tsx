import { useState, useEffect, useCallback } from 'react';
import { 
  Crosshair, 
  Eye, 
  ShieldWarning, 
  TrendUp, 
  TrendDown, 
  Minus,
  Lightning,
  Drop,
  Target,
  Smiley,
  Warning,
  ArrowsCounterClockwise,
  CurrencyBtc,
  Coins,
  Wallet,
  ChartPie,
  Activity,
  Gauge,
  Info,
  X,
  CaretRight,
  Clock,
  Pulse,
  ArrowUp,
  ArrowDown,
} from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { api } from '@/utils/api';
import { Link } from 'react-router-dom';

interface RegimeData {
  composite: string;
  score: number;
  dimensions: {
    trend: string;
    volatility: string;
    liquidity: string;
    risk_appetite: string;
    derivatives: string;
  };
  trend_score: number;
  volatility_score: number;
  liquidity_score: number;
  risk_score: number;
  derivatives_score: number;
  dominance?: {
    btc_d: number;
    alt_d: number;
    stable_d: number;
  };
  timestamp: string;
}

// Map backend regime to display
const REGIME_DISPLAY: Record<string, { 
  label: string; 
  color: string; 
  icon: typeof Crosshair; 
  advice: string;
  description: string;
  bgGradient: string;
}> = {
  'TRENDING_UP': { 
    label: 'BULLISH MOMENTUM', 
    color: 'text-success', 
    icon: TrendUp, 
    advice: 'Long bias favored',
    description: 'Market showing strong upward momentum with institutional buying pressure',
    bgGradient: 'from-success/5 to-transparent'
  },
  'TRENDING_DOWN': { 
    label: 'BEARISH PRESSURE', 
    color: 'text-destructive', 
    icon: TrendDown, 
    advice: 'Short bias or sidelines',
    description: 'Downward pressure dominant - consider defensive positioning',
    bgGradient: 'from-destructive/5 to-transparent'
  },
  'RANGING': { 
    label: 'CONSOLIDATION', 
    color: 'text-warning', 
    icon: Minus, 
    advice: 'Range plays only',
    description: 'Price action confined within range - await breakout confirmation',
    bgGradient: 'from-warning/5 to-transparent'
  },
  'HIGH_VOLATILITY': { 
    label: 'VOLATILE CONDITIONS', 
    color: 'text-orange-500', 
    icon: Lightning, 
    advice: 'Reduce position size',
    description: 'Elevated volatility detected - tighten risk parameters',
    bgGradient: 'from-orange-500/5 to-transparent'
  },
  'LOW_VOLATILITY': { 
    label: 'QUIET MARKET', 
    color: 'text-blue-400', 
    icon: Drop, 
    advice: 'Wait for breakout',
    description: 'Compressed volatility often precedes significant moves',
    bgGradient: 'from-blue-400/5 to-transparent'
  },
  'RISK_ON': { 
    label: 'RISK ON', 
    color: 'text-success', 
    icon: Smiley, 
    advice: 'Alts may outperform',
    description: 'Capital flowing into risk assets - altcoin opportunities emerging',
    bgGradient: 'from-success/5 to-transparent'
  },
  'RISK_OFF': { 
    label: 'RISK OFF', 
    color: 'text-destructive', 
    icon: ShieldWarning, 
    advice: 'BTC/stables safer',
    description: 'Flight to safety active - prioritize capital preservation',
    bgGradient: 'from-destructive/5 to-transparent'
  },
  'CHOPPY': { 
    label: 'CHOPPY SEAS', 
    color: 'text-warning', 
    icon: ArrowsCounterClockwise, 
    advice: 'High selectivity required',
    description: 'Inconsistent price action - only highest conviction setups',
    bgGradient: 'from-warning/5 to-transparent'
  },
  'CHOPPY_RISK_OFF': { 
    label: 'CHOPPY & DEFENSIVE', 
    color: 'text-orange-500', 
    icon: ShieldWarning, 
    advice: 'Maximum caution',
    description: 'Erratic conditions with risk-off sentiment - consider sidelines',
    bgGradient: 'from-orange-500/5 to-transparent'
  },
  'UNKNOWN': { 
    label: 'ACQUIRING TARGET...', 
    color: 'text-muted-foreground', 
    icon: Eye, 
    advice: 'Gathering intel',
    description: 'Analyzing market conditions - standby for regime classification',
    bgGradient: 'from-muted/5 to-transparent'
  },
};

// Threat level based on score
function getThreatLevel(score: number): { level: string; color: string; bgColor: string; description: string } {
  if (score >= 70) return { 
    level: 'GREEN', 
    color: 'text-success', 
    bgColor: 'bg-success',
    description: 'Optimal conditions for precision entries'
  };
  if (score >= 50) return { 
    level: 'YELLOW', 
    color: 'text-warning', 
    bgColor: 'bg-warning',
    description: 'Moderate clarity - selective engagement'
  };
  if (score >= 30) return { 
    level: 'ORANGE', 
    color: 'text-orange-500', 
    bgColor: 'bg-orange-500',
    description: 'Reduced visibility - elevated caution'
  };
  return { 
    level: 'RED', 
    color: 'text-destructive', 
    bgColor: 'bg-destructive',
    description: 'Poor conditions - consider sidelines'
  };
}

// Get dominance interpretation
function getDominanceSignal(btcD: number, altD: number, stableD: number): { signal: string; color: string; description: string } {
  if (stableD > 10) {
    return { 
      signal: 'DEFENSIVE', 
      color: 'text-destructive',
      description: 'High stablecoin dominance indicates risk-off sentiment'
    };
  }
  if (btcD > 55) {
    return { 
      signal: 'BTC SEASON', 
      color: 'text-blue-400',
      description: 'Bitcoin leading - altcoins may underperform'
    };
  }
  if (altD > 45) {
    return { 
      signal: 'ALT SEASON', 
      color: 'text-success',
      description: 'Capital rotating into altcoins - increased opportunities'
    };
  }
  return { 
    signal: 'ROTATION', 
    color: 'text-warning',
    description: 'Mixed flows - selective positioning recommended'
  };
}

// Animated scan line effect
function ScanLine({ active }: { active: boolean }) {
  if (!active) return null;
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden rounded-xl">
      <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-accent to-transparent animate-scan-line" />
    </div>
  );
}

// Expanded detail panel overlay
function DetailPanel({ 
  isOpen, 
  onClose, 
  title, 
  icon: Icon,
  accentColor,
  children 
}: { 
  isOpen: boolean; 
  onClose: () => void; 
  title: string;
  icon: typeof Activity;
  accentColor: string;
  children: React.ReactNode;
}) {
  if (!isOpen) return null;
  
  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div 
        className={cn(
          'relative w-full max-w-2xl max-h-[80vh] overflow-y-auto rounded-2xl border-2 bg-card/95 backdrop-blur-xl shadow-2xl',
          'animate-in zoom-in-95 slide-in-from-bottom-4 duration-300',
          accentColor === 'success' && 'border-success/50 shadow-success/20',
          accentColor === 'warning' && 'border-warning/50 shadow-warning/20',
          accentColor === 'destructive' && 'border-destructive/50 shadow-destructive/20',
          accentColor === 'orange' && 'border-orange-500/50 shadow-orange-500/20',
          accentColor === 'accent' && 'border-accent/50 shadow-accent/20',
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Panel header */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-4 border-b border-border/40 bg-card/95 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <div className={cn(
              'p-2 rounded-lg',
              accentColor === 'success' && 'bg-success/20 text-success',
              accentColor === 'warning' && 'bg-warning/20 text-warning',
              accentColor === 'destructive' && 'bg-destructive/20 text-destructive',
              accentColor === 'orange' && 'bg-orange-500/20 text-orange-500',
              accentColor === 'accent' && 'bg-accent/20 text-accent',
            )}>
              <Icon size={20} weight="bold" />
            </div>
            <span className="text-lg font-bold tracking-wider">{title}</span>
          </div>
          <button 
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-muted/50 transition-colors text-muted-foreground hover:text-foreground"
          >
            <X size={20} />
          </button>
        </div>
        
        {/* Panel content */}
        <div className="p-6">
          {children}
        </div>
        
        {/* Shimmer effect on border */}
        <div className="absolute inset-0 rounded-2xl pointer-events-none overflow-hidden">
          <div className={cn(
            'absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-current to-transparent animate-shimmer',
            accentColor === 'success' && 'text-success',
            accentColor === 'warning' && 'text-warning',
            accentColor === 'destructive' && 'text-destructive',
            accentColor === 'orange' && 'text-orange-500',
            accentColor === 'accent' && 'text-accent',
          )} />
        </div>
      </div>
    </div>
  );
}

// Dimension indicator with visual bar
function DimensionIndicator({ 
  label, 
  value, 
  score,
  icon: Icon,
}: { 
  label: string; 
  value: string;
  score: number;
  icon: typeof Activity;
}) {
  const getScoreColor = (s: number) => {
    if (s >= 60) return 'text-success';
    if (s >= 40) return 'text-warning';
    return 'text-destructive';
  };
  
  const getBarColor = (s: number) => {
    if (s >= 60) return 'bg-success';
    if (s >= 40) return 'bg-warning';
    return 'bg-destructive';
  };
  
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/20 hover:bg-muted/30 transition-colors">
      <div className={cn('p-2 rounded-lg bg-muted/40', getScoreColor(score))}>
        <Icon size={18} weight="bold" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-bold tracking-wider text-muted-foreground">{label}</span>
          <span className={cn('text-sm font-bold capitalize', getScoreColor(score))}>{value}</span>
        </div>
        <div className="h-1.5 bg-muted/30 rounded-full overflow-hidden">
          <div 
            className={cn('h-full rounded-full transition-all duration-700', getBarColor(score))}
            style={{ width: `${Math.min(100, Math.max(5, score))}%` }}
          />
        </div>
      </div>
    </div>
  );
}

// Dominance bar visualization
function DominanceBar({ btcD, altD, stableD }: { btcD: number; altD: number; stableD: number }) {
  const [hoveredSegment, setHoveredSegment] = useState<'btc' | 'alt' | 'stable' | null>(null);
  
  const segments = [
    { 
      key: 'btc' as const, 
      value: btcD, 
      label: 'BTC', 
      fullLabel: 'Bitcoin Dominance',
      color: 'from-amber-500 to-orange-600', 
      textColor: 'text-amber-400',
      glowColor: 'shadow-amber-500/50',
      icon: CurrencyBtc 
    },
    { 
      key: 'alt' as const, 
      value: altD, 
      label: 'ALT', 
      fullLabel: 'Altcoin Market Share',
      color: 'from-violet-500 to-purple-600', 
      textColor: 'text-violet-400',
      glowColor: 'shadow-violet-500/50',
      icon: Coins 
    },
    { 
      key: 'stable' as const, 
      value: stableD, 
      label: 'STABLE', 
      fullLabel: 'Stablecoin Reserves',
      color: 'from-emerald-400 to-teal-500', 
      textColor: 'text-emerald-400',
      glowColor: 'shadow-emerald-500/50',
      icon: Wallet 
    },
  ];

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ChartPie size={16} className="text-accent" weight="fill" />
          <span className="text-sm font-bold tracking-wide text-foreground">DOMINANCE</span>
        </div>
        {hoveredSegment && (
          <span className="text-xs text-muted-foreground animate-in fade-in duration-200">
            {segments.find(s => s.key === hoveredSegment)?.fullLabel}
          </span>
        )}
      </div>
      
      {/* Stacked bar with glow effect */}
      <div className="relative">
        <div className="h-8 rounded-lg overflow-hidden flex bg-black/40 border border-white/5">
          {segments.map((segment) => (
            <div
              key={segment.key}
              className={cn(
                'relative bg-gradient-to-r transition-all duration-500 flex items-center justify-center cursor-pointer',
                segment.color,
                hoveredSegment === segment.key && 'brightness-125 scale-y-110 z-10',
                hoveredSegment && hoveredSegment !== segment.key && 'opacity-60'
              )}
              style={{ width: `${segment.value}%` }}
              onMouseEnter={() => setHoveredSegment(segment.key)}
              onMouseLeave={() => setHoveredSegment(null)}
            >
              {segment.value > 12 && (
                <span className={cn(
                  'text-xs font-bold text-white drop-shadow-lg transition-transform duration-300',
                  hoveredSegment === segment.key && 'scale-110'
                )}>
                  {segment.label}
                </span>
              )}
              {/* Shimmer effect on hover */}
              {hoveredSegment === segment.key && (
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
              )}
            </div>
          ))}
        </div>
        {/* Glow under bar */}
        <div className="absolute -bottom-2 left-0 right-0 h-4 bg-gradient-to-t from-transparent to-white/5 blur-sm rounded-b-lg" />
      </div>
      
      {/* Stats row */}
      <div className="grid grid-cols-3 gap-2">
        {segments.map((segment) => {
          const Icon = segment.icon;
          const isHovered = hoveredSegment === segment.key;
          return (
            <div
              key={segment.key}
              className={cn(
                'flex flex-col items-center p-2 rounded-lg transition-all duration-300 cursor-pointer',
                'bg-white/[0.02] border border-white/5',
                isHovered && 'bg-white/[0.06] border-white/10 shadow-lg',
                isHovered && segment.glowColor
              )}
              onMouseEnter={() => setHoveredSegment(segment.key)}
              onMouseLeave={() => setHoveredSegment(null)}
            >
              <Icon 
                size={18} 
                weight={isHovered ? 'fill' : 'regular'}
                className={cn('transition-all duration-300', segment.textColor, isHovered && 'scale-110')} 
              />
              <span className={cn(
                'text-lg font-bold font-mono tabular-nums mt-1 transition-colors',
                segment.textColor
              )}>
                {segment.value.toFixed(1)}%
              </span>
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                {segment.label}.D
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function TacticalBriefing() {
  const [regime, setRegime] = useState<RegimeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  
  // Expanded panel states
  const [expandedPanel, setExpandedPanel] = useState<'regime' | 'clarity' | 'dimensions' | null>(null);

  const fetchRegime = useCallback(async () => {
    try {
      const response = await api.getMarketRegime();
      if (response.data) {
        setRegime(response.data);
        setLastUpdate(new Date());
        setError(null);
      } else if (response.error) {
        setError(response.error);
      }
    } catch (err) {
      setError('Intel unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRegime();
    // Refresh every 60 seconds
    const interval = setInterval(fetchRegime, 60000);
    return () => clearInterval(interval);
  }, [fetchRegime]);

  // Get display info
  const regimeKey = regime?.composite?.toUpperCase().replace(/ /g, '_') || 'UNKNOWN';
  const display = REGIME_DISPLAY[regimeKey] || REGIME_DISPLAY['UNKNOWN'];
  const Icon = display.icon;
  const threatLevel = getThreatLevel(regime?.score || 50);
  
  // Dominance data
  const btcD = regime?.dominance?.btc_d || 50;
  const altD = regime?.dominance?.alt_d || 35;
  const stableD = regime?.dominance?.stable_d || 15;
  const dominanceSignal = getDominanceSignal(btcD, altD, stableD);

  // Loading state
  if (loading) {
    return (
      <div className="relative p-8 rounded-xl border-2 border-accent/30 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-sm">
        <div className="flex flex-col items-center justify-center gap-4 py-8">
          <div className="relative w-20 h-20 rounded-full border-2 border-accent/50 flex items-center justify-center">
            <Eye size={32} className="text-accent animate-pulse" />
            <div className="absolute inset-0 rounded-full border-2 border-accent/30 animate-ping" />
          </div>
          <div className="text-center space-y-2">
            <div className="text-lg font-bold tracking-wider text-accent">ACQUIRING INTEL...</div>
            <div className="text-sm text-muted-foreground">Scanning market conditions</div>
          </div>
        </div>
        <ScanLine active={true} />
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Main briefing container */}
      <div className={cn(
        'relative rounded-xl border-2 backdrop-blur-sm transition-all duration-300 overflow-hidden',
        'bg-gradient-to-br from-card/90 to-card/60',
        threatLevel.level === 'GREEN' && 'border-success/50 shadow-[0_0_40px_rgba(134,239,172,0.15)]',
        threatLevel.level === 'YELLOW' && 'border-warning/50 shadow-[0_0_40px_rgba(234,179,8,0.15)]',
        threatLevel.level === 'ORANGE' && 'border-orange-500/50 shadow-[0_0_40px_rgba(249,115,22,0.15)]',
        threatLevel.level === 'RED' && 'border-destructive/50 shadow-[0_0_40px_rgba(239,68,68,0.15)]',
      )}>
        {/* Background gradient based on regime */}
        <div className={cn('absolute inset-0 bg-gradient-to-br pointer-events-none', display.bgGradient)} />
        
        {/* Header */}
        <div className="relative px-6 py-4 border-b border-border/40 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={cn('w-2.5 h-2.5 rounded-full animate-pulse', threatLevel.bgColor)} />
            <span className="text-sm font-bold tracking-[0.2em] text-foreground">TACTICAL BRIEFING</span>
            <span className="text-xs text-muted-foreground font-mono">// LIVE</span>
          </div>
          <div className="flex items-center gap-4">
            <div className={cn(
              'flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold',
              threatLevel.level === 'GREEN' && 'bg-success/20 text-success',
              threatLevel.level === 'YELLOW' && 'bg-warning/20 text-warning',
              threatLevel.level === 'ORANGE' && 'bg-orange-500/20 text-orange-500',
              threatLevel.level === 'RED' && 'bg-destructive/20 text-destructive',
            )}>
              <Target size={12} weight="fill" />
              THREAT: {threatLevel.level}
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Eye size={14} />
              <span className="font-mono">
                {lastUpdate ? lastUpdate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '--:--:--'}
              </span>
            </div>
          </div>
        </div>

        {/* Main content */}
        <div className="relative p-6">
          <div className="grid lg:grid-cols-12 gap-6">
            
            {/* Left: Primary Regime Display (4 cols) */}
            <div className="lg:col-span-4 flex flex-col">
              <div 
                className="flex-1 flex flex-col items-center justify-center text-center p-6 rounded-xl bg-muted/10 border border-border/30 cursor-pointer group hover:bg-muted/20 hover:border-accent/30 transition-all duration-300"
                onClick={() => setExpandedPanel('regime')}
              >
                {/* Click hint */}
                <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 text-xs text-accent">
                  <span>Details</span>
                  <CaretRight size={12} weight="bold" />
                </div>
                
                {/* Large reticle with regime icon */}
                <div className={cn(
                  'relative w-32 h-32 rounded-full border-4 flex items-center justify-center mb-4',
                  threatLevel.level === 'GREEN' && 'border-success/60 bg-success/10',
                  threatLevel.level === 'YELLOW' && 'border-warning/60 bg-warning/10',
                  threatLevel.level === 'ORANGE' && 'border-orange-500/60 bg-orange-500/10',
                  threatLevel.level === 'RED' && 'border-destructive/60 bg-destructive/10',
                )}>
                  {/* Outer ring animation */}
                  <div className={cn(
                    'absolute inset-0 rounded-full border-2 opacity-30 animate-ping',
                    threatLevel.level === 'GREEN' && 'border-success',
                    threatLevel.level === 'YELLOW' && 'border-warning',
                    threatLevel.level === 'ORANGE' && 'border-orange-500',
                    threatLevel.level === 'RED' && 'border-destructive',
                  )} style={{ animationDuration: '3s' }} />
                  
                  {/* Crosshair lines */}
                  <div className="absolute w-full h-[1px] bg-current opacity-20" />
                  <div className="absolute h-full w-[1px] bg-current opacity-20" />
                  
                  {/* Corner ticks */}
                  <div className="absolute top-3 left-1/2 -translate-x-1/2 w-[2px] h-3 bg-current opacity-40" />
                  <div className="absolute bottom-3 left-1/2 -translate-x-1/2 w-[2px] h-3 bg-current opacity-40" />
                  <div className="absolute left-3 top-1/2 -translate-y-1/2 h-[2px] w-3 bg-current opacity-40" />
                  <div className="absolute right-3 top-1/2 -translate-y-1/2 h-[2px] w-3 bg-current opacity-40" />
                  
                  <Icon size={48} weight="bold" className={display.color} />
                </div>
                
                <div className="space-y-2 mb-4">
                  <div className={cn('text-2xl font-bold tracking-wider', display.color)}>
                    {display.label}
                  </div>
                  <div className="text-sm text-muted-foreground max-w-[250px]">
                    {display.description}
                  </div>
                </div>
                
                {/* Tactical advice badge */}
                <div className={cn(
                  'inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold',
                  'bg-muted/30 border border-border/50'
                )}>
                  <Info size={16} className={display.color} />
                  <span className={display.color}>{display.advice}</span>
                </div>
              </div>
            </div>

            {/* Center: Score & Dominance (4 cols) */}
            <div className="lg:col-span-4 flex flex-col gap-4">
              {/* Market Clarity Score */}
              <div 
                className="flex-1 p-5 rounded-xl bg-muted/10 border border-border/30 cursor-pointer group hover:bg-muted/20 hover:border-accent/30 transition-all duration-300 relative"
                onClick={() => setExpandedPanel('clarity')}
              >
                {/* Click hint */}
                <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 text-xs text-accent">
                  <span>Details</span>
                  <CaretRight size={12} weight="bold" />
                </div>
                
                <div className="flex items-center gap-2 text-xs font-bold tracking-wider text-muted-foreground mb-4">
                  <Gauge size={14} />
                  <span>MARKET CLARITY INDEX</span>
                </div>
                
                <div className="flex items-center gap-6">
                  {/* Circular gauge */}
                  <div className="relative w-28 h-28 flex-shrink-0">
                    <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                      <circle
                        cx="50"
                        cy="50"
                        r="40"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="8"
                        className="text-muted/20"
                      />
                      <circle
                        cx="50"
                        cy="50"
                        r="40"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="8"
                        strokeLinecap="round"
                        strokeDasharray={`${(regime?.score || 0) * 2.51} 251`}
                        className={cn('transition-all duration-1000', threatLevel.color)}
                      />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className={cn('text-3xl font-bold tabular-nums', threatLevel.color)}>
                        {Math.round(regime?.score || 0)}
                      </span>
                      <span className="text-[10px] text-muted-foreground font-mono">/100</span>
                    </div>
                  </div>
                  
                  {/* Score interpretation */}
                  <div className="flex-1 space-y-2">
                    <div className={cn('text-sm font-bold', threatLevel.color)}>
                      {threatLevel.level} ZONE
                    </div>
                    <div className="text-xs text-muted-foreground leading-relaxed">
                      {threatLevel.description}
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Dominance visualization */}
              <div className="p-4 rounded-xl bg-black/20 border border-white/5 backdrop-blur-sm">
                <DominanceBar btcD={btcD} altD={altD} stableD={stableD} />
                
                {/* Dominance signal - more compact */}
                <div className="mt-3 pt-3 border-t border-white/5 flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Flow Signal</span>
                  <div className={cn(
                    'flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold',
                    'bg-black/30 border',
                    dominanceSignal.color === 'text-success' && 'border-success/30',
                    dominanceSignal.color === 'text-destructive' && 'border-destructive/30',
                    dominanceSignal.color === 'text-blue-400' && 'border-blue-400/30',
                    dominanceSignal.color === 'text-warning' && 'border-warning/30',
                  )}>
                    <div className={cn('w-1.5 h-1.5 rounded-full animate-pulse', 
                      dominanceSignal.color === 'text-success' && 'bg-success',
                      dominanceSignal.color === 'text-destructive' && 'bg-destructive',
                      dominanceSignal.color === 'text-blue-400' && 'bg-blue-400',
                      dominanceSignal.color === 'text-warning' && 'bg-warning',
                    )} />
                    <span className={dominanceSignal.color}>{dominanceSignal.signal}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right: Dimension Analysis (4 cols) */}
            <div className="lg:col-span-4 flex flex-col">
              <div 
                className="flex-1 p-5 rounded-xl bg-muted/10 border border-border/30 cursor-pointer group hover:bg-muted/20 hover:border-accent/30 transition-all duration-300 relative"
                onClick={() => setExpandedPanel('dimensions')}
              >
                {/* Click hint */}
                <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 text-xs text-accent">
                  <span>Details</span>
                  <CaretRight size={12} weight="bold" />
                </div>
                
                <div className="flex items-center gap-2 text-xs font-bold tracking-wider text-muted-foreground mb-4">
                  <Activity size={14} />
                  <span>DIMENSION ANALYSIS</span>
                </div>
                
                <div className="space-y-2">
                  <DimensionIndicator 
                    label="TREND" 
                    value={regime?.dimensions?.trend || 'N/A'} 
                    score={regime?.trend_score || 0}
                    icon={TrendUp}
                  />
                  <DimensionIndicator 
                    label="VOLATILITY" 
                    value={regime?.dimensions?.volatility || 'N/A'} 
                    score={regime?.volatility_score || 0}
                    icon={Lightning}
                  />
                  <DimensionIndicator 
                    label="LIQUIDITY" 
                    value={regime?.dimensions?.liquidity || 'N/A'} 
                    score={regime?.liquidity_score || 0}
                    icon={Drop}
                  />
                  <DimensionIndicator 
                    label="RISK APPETITE" 
                    value={regime?.dimensions?.risk_appetite || 'N/A'} 
                    score={regime?.risk_score || 0}
                    icon={ShieldWarning}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="relative px-6 py-3 border-t border-border/40 flex items-center justify-between bg-muted/5">
          {error ? (
            <div className="flex items-center gap-2 text-xs text-warning">
              <Warning size={14} />
              <span>Backend feed unavailable - displaying cached data</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Crosshair size={14} className="text-accent" />
              <span>Detailed analysis available in</span>
              <Link to="/intel" className="text-accent font-bold hover:underline">Market Intel →</Link>
            </div>
          )}
          <div className="text-xs text-muted-foreground font-mono">
            Auto-refresh: 60s
          </div>
        </div>

        {/* Scan line effect */}
        <ScanLine active={loading} />
      </div>
      
      {/* Expanded Panel Overlays */}
      
      {/* Regime Detail Panel */}
      <DetailPanel
        isOpen={expandedPanel === 'regime'}
        onClose={() => setExpandedPanel(null)}
        title="MARKET REGIME ANALYSIS"
        icon={Icon}
        accentColor={threatLevel.level === 'GREEN' ? 'success' : threatLevel.level === 'YELLOW' ? 'warning' : threatLevel.level === 'ORANGE' ? 'orange' : 'destructive'}
      >
        <div className="space-y-6">
          {/* Current Regime Summary */}
          <div className="flex items-center gap-4 p-4 rounded-xl bg-muted/20 border border-border/30">
            <div className={cn(
              'w-16 h-16 rounded-full border-2 flex items-center justify-center',
              threatLevel.level === 'GREEN' && 'border-success/60 bg-success/10',
              threatLevel.level === 'YELLOW' && 'border-warning/60 bg-warning/10',
              threatLevel.level === 'ORANGE' && 'border-orange-500/60 bg-orange-500/10',
              threatLevel.level === 'RED' && 'border-destructive/60 bg-destructive/10',
            )}>
              <Icon size={32} weight="bold" className={display.color} />
            </div>
            <div className="flex-1">
              <div className={cn('text-xl font-bold tracking-wider mb-1', display.color)}>
                {display.label}
              </div>
              <div className="text-sm text-muted-foreground">
                {display.description}
              </div>
            </div>
          </div>
          
          {/* What This Means */}
          <div className="space-y-3">
            <h4 className="text-sm font-bold tracking-wider text-foreground flex items-center gap-2">
              <Info size={16} className="text-accent" />
              WHAT THIS MEANS
            </h4>
            <div className="p-4 rounded-lg bg-muted/10 border border-border/30 text-sm text-muted-foreground leading-relaxed">
              {regimeKey === 'TRENDING_UP' && (
                <>
                  <p className="mb-3">The market is displaying <span className="text-success font-bold">bullish characteristics</span> with clear institutional buying pressure. This is typically the most favorable environment for long positions.</p>
                  <p><span className="text-foreground font-bold">Key characteristics:</span> Higher highs, higher lows, strong momentum, increasing volume on up moves.</p>
                </>
              )}
              {regimeKey === 'TRENDING_DOWN' && (
                <>
                  <p className="mb-3">The market is under <span className="text-destructive font-bold">sustained selling pressure</span>. This environment favors short positions or staying on the sidelines.</p>
                  <p><span className="text-foreground font-bold">Key characteristics:</span> Lower highs, lower lows, increasing volume on down moves, capitulation patterns.</p>
                </>
              )}
              {regimeKey === 'RANGING' && (
                <>
                  <p className="mb-3">Price action is <span className="text-warning font-bold">consolidating</span> within a defined range. This environment is best for mean-reversion strategies.</p>
                  <p><span className="text-foreground font-bold">Key characteristics:</span> Clear support and resistance, decreasing volatility, accumulation/distribution patterns.</p>
                </>
              )}
              {regimeKey === 'HIGH_VOLATILITY' && (
                <>
                  <p className="mb-3">Market is experiencing <span className="text-orange-500 font-bold">elevated volatility</span>. Position sizing should be reduced and stop losses widened to avoid premature exits.</p>
                  <p><span className="text-foreground font-bold">Key characteristics:</span> Large candle ranges, frequent reversals, increased risk of liquidation cascades.</p>
                </>
              )}
              {regimeKey === 'CHOPPY' && (
                <>
                  <p className="mb-3">Market is <span className="text-warning font-bold">inconsistent and unpredictable</span>. Only the highest conviction setups should be considered.</p>
                  <p><span className="text-foreground font-bold">Key characteristics:</span> Failed breakouts, whipsaws, low follow-through on moves.</p>
                </>
              )}
              {(regimeKey === 'RISK_ON' || regimeKey === 'RISK_OFF' || regimeKey === 'UNKNOWN' || regimeKey === 'LOW_VOLATILITY' || regimeKey === 'CHOPPY_RISK_OFF') && (
                <p>{display.description}</p>
              )}
            </div>
          </div>
          
          {/* Tactical Recommendations */}
          <div className="space-y-3">
            <h4 className="text-sm font-bold tracking-wider text-foreground flex items-center gap-2">
              <Target size={16} className="text-accent" />
              TACTICAL RECOMMENDATIONS
            </h4>
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-muted/10 border border-border/30">
                <div className="text-xs text-muted-foreground mb-1">Position Bias</div>
                <div className={cn('text-sm font-bold', display.color)}>{display.advice}</div>
              </div>
              <div className="p-3 rounded-lg bg-muted/10 border border-border/30">
                <div className="text-xs text-muted-foreground mb-1">Risk Level</div>
                <div className={cn('text-sm font-bold', threatLevel.color)}>{threatLevel.level}</div>
              </div>
              <div className="p-3 rounded-lg bg-muted/10 border border-border/30">
                <div className="text-xs text-muted-foreground mb-1">Suggested Mode</div>
                <div className="text-sm font-bold text-accent">
                  {threatLevel.level === 'GREEN' ? 'STRIKE' : threatLevel.level === 'YELLOW' ? 'STEALTH' : 'OVERWATCH'}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-muted/10 border border-border/30">
                <div className="text-xs text-muted-foreground mb-1">Position Size</div>
                <div className="text-sm font-bold text-foreground">
                  {threatLevel.level === 'GREEN' ? '100%' : threatLevel.level === 'YELLOW' ? '75%' : threatLevel.level === 'ORANGE' ? '50%' : '25%'}
                </div>
              </div>
            </div>
          </div>
          
          {/* Last Update */}
          <div className="flex items-center justify-between pt-4 border-t border-border/30 text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <Clock size={14} />
              <span>Last updated: {lastUpdate?.toLocaleString() || 'N/A'}</span>
            </div>
            <Link to="/intel" className="text-accent font-bold hover:underline flex items-center gap-1">
              Full Analysis <CaretRight size={12} />
            </Link>
          </div>
        </div>
      </DetailPanel>
      
      {/* Market Clarity Detail Panel */}
      <DetailPanel
        isOpen={expandedPanel === 'clarity'}
        onClose={() => setExpandedPanel(null)}
        title="MARKET CLARITY INDEX"
        icon={Gauge}
        accentColor={threatLevel.level === 'GREEN' ? 'success' : threatLevel.level === 'YELLOW' ? 'warning' : threatLevel.level === 'ORANGE' ? 'orange' : 'destructive'}
      >
        <div className="space-y-6">
          {/* Large Score Display */}
          <div className="flex items-center justify-center gap-8 p-6 rounded-xl bg-muted/20 border border-border/30">
            <div className="relative w-36 h-36">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="40" fill="none" stroke="currentColor" strokeWidth="8" className="text-muted/20" />
                <circle cx="50" cy="50" r="40" fill="none" stroke="currentColor" strokeWidth="8" strokeLinecap="round"
                  strokeDasharray={`${(regime?.score || 0) * 2.51} 251`}
                  className={cn('transition-all duration-1000', threatLevel.color)}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className={cn('text-4xl font-bold tabular-nums', threatLevel.color)}>
                  {Math.round(regime?.score || 0)}
                </span>
                <span className="text-xs text-muted-foreground font-mono">/100</span>
              </div>
            </div>
            <div className="space-y-2">
              <div className={cn('text-2xl font-bold', threatLevel.color)}>
                {threatLevel.level} ZONE
              </div>
              <div className="text-sm text-muted-foreground max-w-[200px]">
                {threatLevel.description}
              </div>
            </div>
          </div>
          
          {/* Score Breakdown */}
          <div className="space-y-3">
            <h4 className="text-sm font-bold tracking-wider text-foreground flex items-center gap-2">
              <Activity size={16} className="text-accent" />
              SCORE COMPONENTS
            </h4>
            <div className="space-y-2">
              {[
                { label: 'Trend Clarity', score: regime?.trend_score || 0, icon: TrendUp },
                { label: 'Volatility Health', score: regime?.volatility_score || 0, icon: Lightning },
                { label: 'Liquidity Depth', score: regime?.liquidity_score || 0, icon: Drop },
                { label: 'Risk Sentiment', score: regime?.risk_score || 0, icon: ShieldWarning },
              ].map((item) => (
                <div key={item.label} className="flex items-center gap-3 p-3 rounded-lg bg-muted/10 border border-border/30">
                  <item.icon size={18} className={item.score >= 60 ? 'text-success' : item.score >= 40 ? 'text-warning' : 'text-destructive'} />
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-bold">{item.label}</span>
                      <span className={cn('text-sm font-bold tabular-nums', item.score >= 60 ? 'text-success' : item.score >= 40 ? 'text-warning' : 'text-destructive')}>
                        {item.score}
                      </span>
                    </div>
                    <div className="h-1.5 bg-muted/30 rounded-full overflow-hidden">
                      <div 
                        className={cn('h-full rounded-full transition-all duration-700', item.score >= 60 ? 'bg-success' : item.score >= 40 ? 'bg-warning' : 'bg-destructive')}
                        style={{ width: `${item.score}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          {/* Zone Explanation */}
          <div className="space-y-3">
            <h4 className="text-sm font-bold tracking-wider text-foreground flex items-center gap-2">
              <Info size={16} className="text-accent" />
              ZONE GUIDE
            </h4>
            <div className="grid grid-cols-2 gap-2">
              {[
                { level: 'GREEN', range: '70-100', desc: 'Optimal conditions', color: 'text-success', bg: 'bg-success/10' },
                { level: 'YELLOW', range: '50-69', desc: 'Moderate clarity', color: 'text-warning', bg: 'bg-warning/10' },
                { level: 'ORANGE', range: '30-49', desc: 'Reduced visibility', color: 'text-orange-500', bg: 'bg-orange-500/10' },
                { level: 'RED', range: '0-29', desc: 'Poor conditions', color: 'text-destructive', bg: 'bg-destructive/10' },
              ].map((zone) => (
                <div key={zone.level} className={cn('p-3 rounded-lg border border-border/30', zone.bg, threatLevel.level === zone.level && 'ring-2 ring-current')}>
                  <div className={cn('text-sm font-bold', zone.color)}>{zone.level}</div>
                  <div className="text-xs text-muted-foreground">{zone.range} • {zone.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </DetailPanel>
      
      {/* Dimensions Detail Panel */}
      <DetailPanel
        isOpen={expandedPanel === 'dimensions'}
        onClose={() => setExpandedPanel(null)}
        title="DIMENSION ANALYSIS"
        icon={Activity}
        accentColor="accent"
      >
        <div className="space-y-6">
          {/* Dimension Cards */}
          {[
            { 
              label: 'TREND', 
              value: regime?.dimensions?.trend || 'N/A', 
              score: regime?.trend_score || 0,
              icon: TrendUp,
              description: 'Measures the direction and strength of price movement. Higher scores indicate clearer directional bias.',
              bullish: 'Strong upward momentum with institutional buying',
              bearish: 'Downward pressure with distribution patterns',
              neutral: 'No clear directional bias - sideways action'
            },
            { 
              label: 'VOLATILITY', 
              value: regime?.dimensions?.volatility || 'N/A', 
              score: regime?.volatility_score || 0,
              icon: Lightning,
              description: 'Measures price movement magnitude. Optimal trading occurs in moderate volatility environments.',
              bullish: 'Controlled volatility with good range opportunities',
              bearish: 'Excessive volatility may trigger stop hunts',
              neutral: 'Compressed volatility - breakout imminent'
            },
            { 
              label: 'LIQUIDITY', 
              value: regime?.dimensions?.liquidity || 'N/A', 
              score: regime?.liquidity_score || 0,
              icon: Drop,
              description: 'Measures market depth and trade execution quality. Higher liquidity = tighter spreads.',
              bullish: 'Deep order books with minimal slippage',
              bearish: 'Thin liquidity may cause price gaps',
              neutral: 'Average market depth - standard execution'
            },
            { 
              label: 'RISK APPETITE', 
              value: regime?.dimensions?.risk_appetite || 'N/A', 
              score: regime?.risk_score || 0,
              icon: ShieldWarning,
              description: 'Measures market sentiment toward risk assets. Risk-on favors altcoins, risk-off favors BTC/stables.',
              bullish: 'Capital flowing into risk assets',
              bearish: 'Flight to safety - defensive positioning',
              neutral: 'Mixed sentiment - selective opportunities'
            },
          ].map((dim) => (
            <div key={dim.label} className="p-4 rounded-xl bg-muted/10 border border-border/30">
              <div className="flex items-center gap-3 mb-4">
                <div className={cn('p-2 rounded-lg', dim.score >= 60 ? 'bg-success/20 text-success' : dim.score >= 40 ? 'bg-warning/20 text-warning' : 'bg-destructive/20 text-destructive')}>
                  <dim.icon size={20} weight="bold" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold tracking-wider">{dim.label}</span>
                    <div className="flex items-center gap-2">
                      <span className={cn('text-lg font-bold capitalize', dim.score >= 60 ? 'text-success' : dim.score >= 40 ? 'text-warning' : 'text-destructive')}>
                        {dim.value}
                      </span>
                      <span className={cn('text-sm font-mono tabular-nums', dim.score >= 60 ? 'text-success' : dim.score >= 40 ? 'text-warning' : 'text-destructive')}>
                        ({dim.score})
                      </span>
                    </div>
                  </div>
                  <div className="h-2 bg-muted/30 rounded-full overflow-hidden mt-2">
                    <div 
                      className={cn('h-full rounded-full transition-all duration-700', dim.score >= 60 ? 'bg-success' : dim.score >= 40 ? 'bg-warning' : 'bg-destructive')}
                      style={{ width: `${dim.score}%` }}
                    />
                  </div>
                </div>
              </div>
              <div className="text-sm text-muted-foreground mb-3">
                {dim.description}
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="p-2 rounded bg-success/10 border border-success/20">
                  <div className="flex items-center gap-1 text-success font-bold mb-1">
                    <ArrowUp size={12} /> Bullish
                  </div>
                  <div className="text-muted-foreground">{dim.bullish}</div>
                </div>
                <div className="p-2 rounded bg-warning/10 border border-warning/20">
                  <div className="flex items-center gap-1 text-warning font-bold mb-1">
                    <Minus size={12} /> Neutral
                  </div>
                  <div className="text-muted-foreground">{dim.neutral}</div>
                </div>
                <div className="p-2 rounded bg-destructive/10 border border-destructive/20">
                  <div className="flex items-center gap-1 text-destructive font-bold mb-1">
                    <ArrowDown size={12} /> Bearish
                  </div>
                  <div className="text-muted-foreground">{dim.bearish}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </DetailPanel>
    </div>
  );
}
