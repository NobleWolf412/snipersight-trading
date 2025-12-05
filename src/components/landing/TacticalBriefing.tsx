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
  Skull,
  Smiley,
  Warning,
  ArrowsCounterClockwise
} from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { api } from '@/utils/api';

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
  timestamp: string;
}

// Map backend regime to display
const REGIME_DISPLAY: Record<string, { label: string; color: string; icon: typeof Crosshair; advice: string }> = {
  'TRENDING_UP': { label: 'BULLISH MOMENTUM', color: 'text-success', icon: TrendUp, advice: 'Long bias favored' },
  'TRENDING_DOWN': { label: 'BEARISH PRESSURE', color: 'text-destructive', icon: TrendDown, advice: 'Short bias or sidelines' },
  'RANGING': { label: 'CONSOLIDATION', color: 'text-warning', icon: Minus, advice: 'Range plays only' },
  'HIGH_VOLATILITY': { label: 'VOLATILE CONDITIONS', color: 'text-orange-500', icon: Lightning, advice: 'Reduce position size' },
  'LOW_VOLATILITY': { label: 'QUIET MARKET', color: 'text-blue-400', icon: Drop, advice: 'Wait for breakout' },
  'RISK_ON': { label: 'RISK ON', color: 'text-success', icon: Smiley, advice: 'Alts may outperform' },
  'RISK_OFF': { label: 'RISK OFF', color: 'text-destructive', icon: ShieldWarning, advice: 'BTC/stables safer' },
  'CHOPPY': { label: 'CHOPPY SEAS', color: 'text-warning', icon: ArrowsCounterClockwise, advice: 'High selectivity required' },
  'UNKNOWN': { label: 'SCANNING...', color: 'text-muted-foreground', icon: Eye, advice: 'Gathering intel' },
};

// Threat level based on score
function getThreatLevel(score: number): { level: string; color: string; bgColor: string } {
  if (score >= 70) return { level: 'GREEN', color: 'text-success', bgColor: 'bg-success' };
  if (score >= 50) return { level: 'YELLOW', color: 'text-warning', bgColor: 'bg-warning' };
  if (score >= 30) return { level: 'ORANGE', color: 'text-orange-500', bgColor: 'bg-orange-500' };
  return { level: 'RED', color: 'text-destructive', bgColor: 'bg-destructive' };
}

// Animated scan line effect
function ScanLine({ active }: { active: boolean }) {
  return (
    <div className={cn(
      'absolute inset-0 pointer-events-none overflow-hidden rounded-xl',
      active && 'opacity-100',
      !active && 'opacity-0'
    )}>
      <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-accent to-transparent animate-scan-line" />
    </div>
  );
}

// Dimension bar component
function DimensionBar({ 
  label, 
  value, 
  score,
  color = 'accent' 
}: { 
  label: string; 
  value: string;
  score: number;
  color?: string;
}) {
  const colorClass = color === 'success' ? 'bg-success' : 
                     color === 'warning' ? 'bg-warning' : 
                     color === 'destructive' ? 'bg-destructive' :
                     color === 'orange' ? 'bg-orange-500' :
                     'bg-accent';
  
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground font-mono tracking-wider">{label}</span>
        <span className={cn('font-bold', 
          score >= 60 ? 'text-success' : score >= 40 ? 'text-warning' : 'text-destructive'
        )}>{value}</span>
      </div>
      <div className="h-1.5 bg-muted/30 rounded-full overflow-hidden">
        <div 
          className={cn('h-full rounded-full transition-all duration-500', colorClass)}
          style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
        />
      </div>
    </div>
  );
}

export function TacticalBriefing() {
  const [regime, setRegime] = useState<RegimeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

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

  // If loading or error, show minimal skeleton
  if (loading) {
    return (
      <div className="relative p-6 rounded-xl border border-border/40 bg-card/50 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 bg-accent/50 rounded-full animate-pulse" />
          <span className="text-xs tracking-widest text-muted-foreground">ACQUIRING INTEL...</span>
        </div>
        <ScanLine active={true} />
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Main briefing container */}
      <div className={cn(
        'relative p-6 rounded-xl border-2 backdrop-blur-sm transition-all duration-300',
        'bg-gradient-to-br from-card/80 to-card/40',
        threatLevel.level === 'GREEN' && 'border-success/40 shadow-[0_0_30px_rgba(134,239,172,0.1)]',
        threatLevel.level === 'YELLOW' && 'border-warning/40 shadow-[0_0_30px_rgba(234,179,8,0.1)]',
        threatLevel.level === 'ORANGE' && 'border-orange-500/40 shadow-[0_0_30px_rgba(249,115,22,0.1)]',
        threatLevel.level === 'RED' && 'border-destructive/40 shadow-[0_0_30px_rgba(239,68,68,0.1)]',
      )}>
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className={cn('w-2 h-2 rounded-full animate-pulse', threatLevel.bgColor)} />
            <span className="text-xs font-bold tracking-[0.2em] text-muted-foreground">TACTICAL BRIEFING</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Eye size={14} />
            <span className="font-mono">
              {lastUpdate ? lastUpdate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '--:--'}
            </span>
          </div>
        </div>

        {/* Main content grid */}
        <div className="grid md:grid-cols-3 gap-6">
          
          {/* Left: Primary Regime Display */}
          <div className="md:col-span-1 flex flex-col items-center justify-center text-center space-y-3">
            {/* Reticle with regime icon */}
            <div className={cn(
              'relative w-24 h-24 rounded-full border-2 flex items-center justify-center',
              threatLevel.level === 'GREEN' && 'border-success/60 bg-success/10',
              threatLevel.level === 'YELLOW' && 'border-warning/60 bg-warning/10',
              threatLevel.level === 'ORANGE' && 'border-orange-500/60 bg-orange-500/10',
              threatLevel.level === 'RED' && 'border-destructive/60 bg-destructive/10',
            )}>
              {/* Crosshair lines */}
              <div className="absolute w-full h-[1px] bg-current opacity-30" />
              <div className="absolute h-full w-[1px] bg-current opacity-30" />
              {/* Corner ticks */}
              <div className="absolute top-2 left-1/2 -translate-x-1/2 w-[1px] h-2 bg-current opacity-50" />
              <div className="absolute bottom-2 left-1/2 -translate-x-1/2 w-[1px] h-2 bg-current opacity-50" />
              <div className="absolute left-2 top-1/2 -translate-y-1/2 h-[1px] w-2 bg-current opacity-50" />
              <div className="absolute right-2 top-1/2 -translate-y-1/2 h-[1px] w-2 bg-current opacity-50" />
              
              <Icon size={36} weight="bold" className={display.color} />
            </div>
            
            <div>
              <div className={cn('text-lg font-bold tracking-wider', display.color)}>
                {display.label}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {display.advice}
              </div>
            </div>
            
            {/* Threat level badge */}
            <div className={cn(
              'inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold tracking-wider',
              threatLevel.level === 'GREEN' && 'bg-success/20 text-success',
              threatLevel.level === 'YELLOW' && 'bg-warning/20 text-warning',
              threatLevel.level === 'ORANGE' && 'bg-orange-500/20 text-orange-500',
              threatLevel.level === 'RED' && 'bg-destructive/20 text-destructive',
            )}>
              <Target size={14} weight="fill" />
              THREAT: {threatLevel.level}
            </div>
          </div>

          {/* Center: Score gauge */}
          <div className="md:col-span-1 flex flex-col items-center justify-center">
            <div className="text-xs font-bold tracking-[0.2em] text-muted-foreground mb-3">
              MARKET CLARITY
            </div>
            
            {/* Circular score display */}
            <div className="relative w-32 h-32">
              {/* Background ring */}
              <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                <circle
                  cx="50"
                  cy="50"
                  r="42"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="6"
                  className="text-muted/20"
                />
                <circle
                  cx="50"
                  cy="50"
                  r="42"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="6"
                  strokeLinecap="round"
                  strokeDasharray={`${(regime?.score || 0) * 2.64} 264`}
                  className={cn(
                    'transition-all duration-1000',
                    threatLevel.color
                  )}
                />
              </svg>
              
              {/* Center text */}
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className={cn('text-3xl font-bold tabular-nums', threatLevel.color)}>
                  {regime?.score || '--'}
                </span>
                <span className="text-xs text-muted-foreground">/ 100</span>
              </div>
            </div>
            
            <div className="text-xs text-muted-foreground mt-2 text-center max-w-[200px]">
              Higher score = clearer conditions for precision entries
            </div>
          </div>

          {/* Right: Dimension breakdown */}
          <div className="md:col-span-1 space-y-3">
            <div className="text-xs font-bold tracking-[0.2em] text-muted-foreground mb-3">
              DIMENSION ANALYSIS
            </div>
            
            <DimensionBar 
              label="TREND" 
              value={regime?.dimensions?.trend || 'N/A'} 
              score={regime?.trend_score || 0}
            />
            <DimensionBar 
              label="VOLATILITY" 
              value={regime?.dimensions?.volatility || 'N/A'} 
              score={regime?.volatility_score || 0}
            />
            <DimensionBar 
              label="LIQUIDITY" 
              value={regime?.dimensions?.liquidity || 'N/A'} 
              score={regime?.liquidity_score || 0}
            />
            <DimensionBar 
              label="RISK APPETITE" 
              value={regime?.dimensions?.risk_appetite || 'N/A'} 
              score={regime?.risk_score || 0}
            />
          </div>
        </div>

        {/* Bottom: Quick action hint */}
        {error ? (
          <div className="mt-6 pt-4 border-t border-border/40 flex items-center justify-center gap-2 text-xs text-muted-foreground">
            <Warning size={14} className="text-warning" />
            <span>Backend intel feed unavailable - using cached data</span>
          </div>
        ) : (
          <div className="mt-6 pt-4 border-t border-border/40 flex items-center justify-between text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <Crosshair size={14} className="text-accent" />
              <span>Full analysis available in <span className="text-accent font-bold">Market Intel</span></span>
            </div>
            <div className="font-mono">
              Updated {lastUpdate ? `${Math.round((Date.now() - lastUpdate.getTime()) / 1000)}s ago` : 'never'}
            </div>
          </div>
        )}

        {/* Scan line effect */}
        <ScanLine active={loading} />
      </div>
    </div>
  );
}
