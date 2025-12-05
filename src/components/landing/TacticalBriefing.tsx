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
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs font-bold tracking-wider text-muted-foreground">
        <ChartPie size={14} />
        <span>MARKET DOMINANCE</span>
      </div>
      
      {/* Stacked bar */}
      <div className="h-4 rounded-full overflow-hidden flex bg-muted/20">
        <div 
          className="bg-orange-500 transition-all duration-700 flex items-center justify-center"
          style={{ width: `${btcD}%` }}
        >
          {btcD > 15 && <span className="text-[10px] font-bold text-white/90">BTC</span>}
        </div>
        <div 
          className="bg-purple-500 transition-all duration-700 flex items-center justify-center"
          style={{ width: `${altD}%` }}
        >
          {altD > 15 && <span className="text-[10px] font-bold text-white/90">ALT</span>}
        </div>
        <div 
          className="bg-emerald-500 transition-all duration-700 flex items-center justify-center"
          style={{ width: `${stableD}%` }}
        >
          {stableD > 10 && <span className="text-[10px] font-bold text-white/90">STABLE</span>}
        </div>
      </div>
      
      {/* Legend */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1.5">
          <CurrencyBtc size={14} className="text-orange-500" />
          <span className="text-muted-foreground">BTC.D</span>
          <span className="font-bold font-mono text-orange-500">{btcD.toFixed(1)}%</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Coins size={14} className="text-purple-500" />
          <span className="text-muted-foreground">ALT.D</span>
          <span className="font-bold font-mono text-purple-500">{altD.toFixed(1)}%</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Wallet size={14} className="text-emerald-500" />
          <span className="text-muted-foreground">STABLE.D</span>
          <span className="font-bold font-mono text-emerald-500">{stableD.toFixed(1)}%</span>
        </div>
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
              <div className="flex-1 flex flex-col items-center justify-center text-center p-6 rounded-xl bg-muted/10 border border-border/30">
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
              <div className="flex-1 p-5 rounded-xl bg-muted/10 border border-border/30">
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
              <div className="p-5 rounded-xl bg-muted/10 border border-border/30">
                <DominanceBar btcD={btcD} altD={altD} stableD={stableD} />
                
                {/* Dominance signal */}
                <div className="mt-4 pt-4 border-t border-border/30">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">Capital Flow Signal:</span>
                    <span className={cn('text-sm font-bold', dominanceSignal.color)}>
                      {dominanceSignal.signal}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {dominanceSignal.description}
                  </div>
                </div>
              </div>
            </div>

            {/* Right: Dimension Analysis (4 cols) */}
            <div className="lg:col-span-4 flex flex-col">
              <div className="flex-1 p-5 rounded-xl bg-muted/10 border border-border/30">
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
    </div>
  );
}
