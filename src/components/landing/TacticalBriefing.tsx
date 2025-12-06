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
  CaretDown,
  CaretRight,
  Clock,
  Pulse,
  ArrowUp,
  ArrowDown,
  ChartLine,
  Compass,
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

// Threat level based on score
function getThreatLevel(score: number): { level: string; color: string; bgColor: string } {
  if (score >= 70) return { level: 'GREEN', color: 'text-success', bgColor: 'bg-success' };
  if (score >= 50) return { level: 'YELLOW', color: 'text-warning', bgColor: 'bg-warning' };
  if (score >= 30) return { level: 'ORANGE', color: 'text-orange-500', bgColor: 'bg-orange-500' };
  return { level: 'RED', color: 'text-destructive', bgColor: 'bg-destructive' };
}

// Get dominance signal
function getDominanceSignal(btcD: number, stableD: number): { signal: string; color: string } {
  if (stableD > 10) return { signal: 'DEFENSIVE', color: 'text-destructive' };
  if (btcD > 55) return { signal: 'BTC SEASON', color: 'text-blue-400' };
  return { signal: 'ALT SEASON', color: 'text-success' };
}

// Mini circular gauge component
function MiniGauge({ 
  value, 
  label, 
  color,
  size = 48 
}: { 
  value: number; 
  label: string; 
  color: string;
  size?: number;
}) {
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDasharray = `${(value / 100) * circumference} ${circumference}`;
  
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg className="w-full h-full -rotate-90" viewBox={`0 0 ${size} ${size}`}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth="4"
            className="text-muted/20"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray={strokeDasharray}
            className={cn('transition-all duration-700', color)}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={cn('text-sm font-bold tabular-nums', color)}>
            {Math.round(value)}
          </span>
        </div>
      </div>
      <span className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider">{label}</span>
    </div>
  );
}

// Static metric display (no link - footer has the intel link)
function MetricDisplay({ 
  icon: Icon, 
  label, 
  value, 
  subValue,
  color,
}: { 
  icon: typeof Activity;
  label: string;
  value: string | number;
  subValue?: string;
  color: string;
}) {
  return (
    <div 
      className={cn(
        'relative p-3 rounded-xl bg-muted/10 border border-border/30',
        'flex items-center gap-3'
      )}
    >
      <div className={cn('p-2 rounded-lg bg-muted/30', color)}>
        <Icon size={18} weight="bold" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[10px] font-bold tracking-wider text-muted-foreground">{label}</div>
        <div className={cn('text-sm font-bold', color)}>{value}</div>
        {subValue && <div className="text-[10px] text-muted-foreground">{subValue}</div>}
      </div>
    </div>
  );
}

// Interactive Dominance Bar
function DominanceBar({ btcD, altD, stableD }: { btcD: number; altD: number; stableD: number }) {
  const [hovered, setHovered] = useState<string | null>(null);
  
  const segments = [
    { key: 'btc', value: btcD, label: 'BTC', color: 'from-amber-500 to-orange-600', textColor: 'text-amber-400', icon: CurrencyBtc },
    { key: 'alt', value: altD, label: 'ALT', color: 'from-violet-500 to-purple-600', textColor: 'text-violet-400', icon: Coins },
    { key: 'stable', value: stableD, label: 'STABLE', color: 'from-emerald-400 to-teal-500', textColor: 'text-emerald-400', icon: Wallet },
  ];

  return (
    <div className="space-y-2">
      {/* Bar */}
      <div className="h-6 rounded-lg overflow-hidden flex bg-black/40 border border-white/5">
        {segments.map((seg) => (
          <div
            key={seg.key}
            className={cn(
              'relative bg-gradient-to-r transition-all duration-300 flex items-center justify-center cursor-pointer',
              seg.color,
              hovered === seg.key && 'brightness-125',
              hovered && hovered !== seg.key && 'opacity-50'
            )}
            style={{ width: `${seg.value}%` }}
            onMouseEnter={() => setHovered(seg.key)}
            onMouseLeave={() => setHovered(null)}
          >
            {seg.value > 5 && (
              <span className={cn(
                "text-[10px] font-bold drop-shadow-sm",
                seg.key === 'stable' ? 'text-black/90' : 'text-white'
              )}>{seg.label}</span>
            )}
          </div>
        ))}
      </div>
      
      {/* Stats */}
      <div className="grid grid-cols-3 gap-1">
        {segments.map((seg) => {
          const Icon = seg.icon;
          return (
            <div
              key={seg.key}
              className={cn(
                'flex items-center justify-center gap-1.5 py-1 rounded text-xs transition-all',
                hovered === seg.key && 'bg-white/5'
              )}
              onMouseEnter={() => setHovered(seg.key)}
              onMouseLeave={() => setHovered(null)}
            >
              <Icon size={12} className={seg.textColor} />
              <span className={cn('font-mono tabular-nums font-bold', seg.textColor)}>
                {seg.value.toFixed(1)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Collapsible section
function CollapsibleSection({ 
  title, 
  icon: Icon,
  defaultOpen = false,
  children 
}: { 
  title: string;
  icon: typeof Activity;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  
  return (
    <div className="border border-border/30 rounded-xl overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between bg-muted/10 hover:bg-muted/20 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon size={14} className="text-accent" />
          <span className="text-xs font-bold tracking-wider">{title}</span>
        </div>
        <CaretDown 
          size={14} 
          className={cn('text-muted-foreground transition-transform', isOpen && 'rotate-180')} 
        />
      </button>
      <div className={cn(
        'grid transition-all duration-300',
        isOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
      )}>
        <div className="overflow-hidden">
          <div className="p-4 space-y-3">
            {children}
          </div>
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
    const interval = setInterval(fetchRegime, 60000);
    return () => clearInterval(interval);
  }, [fetchRegime]);

  const threatLevel = getThreatLevel(regime?.score || 50);
  const btcD = regime?.dominance?.btc_d || 50;
  const altD = regime?.dominance?.alt_d || 35;
  const stableD = regime?.dominance?.stable_d || 15;
  const dominanceSignal = getDominanceSignal(btcD, stableD);

  // Loading state - simple and clean
  if (loading) {
    return (
      <div className="relative p-6 rounded-xl border border-accent/30 bg-card/80 backdrop-blur-sm">
        <div className="flex items-center justify-center gap-4 py-6">
          <div className="relative">
            <div className="w-12 h-12 rounded-full border-2 border-accent/30 flex items-center justify-center">
              <Gauge size={24} className="text-accent" />
            </div>
            <div className="absolute inset-0 rounded-full border-2 border-t-accent border-transparent animate-spin" />
          </div>
          <div>
            <div className="text-sm font-bold tracking-wider text-foreground">Analyzing Market</div>
            <div className="text-xs text-muted-foreground">Gathering regime data...</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn(
      'relative rounded-xl border-2 backdrop-blur-sm overflow-hidden',
      'bg-gradient-to-br from-card/90 to-card/60',
      threatLevel.level === 'GREEN' && 'border-success/40',
      threatLevel.level === 'YELLOW' && 'border-warning/40',
      threatLevel.level === 'ORANGE' && 'border-orange-500/40',
      threatLevel.level === 'RED' && 'border-destructive/40',
    )}>
      {/* Compact Header */}
      <div className="px-4 py-3 border-b border-border/40 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={cn('w-2 h-2 rounded-full animate-pulse', threatLevel.bgColor)} />
          <span className="text-xs font-bold tracking-[0.15em]">TACTICAL BRIEFING</span>
          <span className="text-[10px] text-muted-foreground font-mono">// LIVE</span>
        </div>
        <div className="flex items-center gap-3">
          <div className={cn(
            'flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-bold',
            threatLevel.level === 'GREEN' && 'bg-success/20 text-success',
            threatLevel.level === 'YELLOW' && 'bg-warning/20 text-warning',
            threatLevel.level === 'ORANGE' && 'bg-orange-500/20 text-orange-500',
            threatLevel.level === 'RED' && 'bg-destructive/20 text-destructive',
          )}>
            <Target size={10} weight="fill" />
            THREAT: {threatLevel.level}
          </div>
          <span className="text-[10px] text-muted-foreground font-mono">
            {lastUpdate?.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
        </div>
      </div>

      {/* Main Content - Compact Two-Row Layout */}
      <div className="p-4 space-y-4">
        
        {/* Row 1: Key Metrics Strip */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Market Score */}
          <div className="col-span-1 flex items-center gap-3 p-3 rounded-xl bg-muted/10 border border-border/30">
            <MiniGauge value={regime?.score || 0} label="CLARITY" color={threatLevel.color} />
            <div className="flex-1">
              <div className={cn('text-lg font-bold', threatLevel.color)}>
                {threatLevel.level}
              </div>
              <div className="text-[10px] text-muted-foreground">
                {threatLevel.level === 'GREEN' ? 'Optimal' : threatLevel.level === 'YELLOW' ? 'Selective' : 'Caution'}
              </div>
            </div>
          </div>

          {/* Bias Indicator */}
          <MetricDisplay
            icon={regime?.dimensions?.trend === 'bullish' ? TrendUp : regime?.dimensions?.trend === 'bearish' ? TrendDown : Minus}
            label="TREND BIAS"
            value={regime?.dimensions?.trend?.toUpperCase() || 'N/A'}
            color={regime?.trend_score && regime.trend_score >= 60 ? 'text-success' : regime?.trend_score && regime.trend_score >= 40 ? 'text-warning' : 'text-destructive'}
          />

          {/* Volatility */}
          <MetricDisplay
            icon={Lightning}
            label="VOLATILITY"
            value={regime?.dimensions?.volatility?.toUpperCase() || 'N/A'}
            color={regime?.volatility_score && regime.volatility_score >= 60 ? 'text-success' : regime?.volatility_score && regime.volatility_score >= 40 ? 'text-warning' : 'text-orange-500'}
          />

          {/* Risk Appetite */}
          <MetricDisplay
            icon={ShieldWarning}
            label="RISK APPETITE"
            value={regime?.dimensions?.risk_appetite?.toUpperCase() || 'N/A'}
            color={regime?.risk_score && regime.risk_score >= 60 ? 'text-success' : regime?.risk_score && regime.risk_score >= 40 ? 'text-warning' : 'text-destructive'}
          />
        </div>

        {/* Row 2: Dominance + Flow Signal (Interactive) */}
        <Link 
          to="/intel"
          className="block p-4 rounded-xl bg-black/20 border border-white/5 hover:border-accent/30 hover:bg-black/30 transition-all group"
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <ChartPie size={14} className="text-accent" weight="fill" />
              <span className="text-xs font-bold tracking-wider">DOMINANCE</span>
            </div>
            <div className="flex items-center gap-2">
              <div className={cn(
                'flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold',
                'bg-black/30 border',
                dominanceSignal.color === 'text-success' && 'border-success/30',
                dominanceSignal.color === 'text-destructive' && 'border-destructive/30',
                dominanceSignal.color === 'text-blue-400' && 'border-blue-400/30',
              )}>
                <div className={cn('w-1.5 h-1.5 rounded-full animate-pulse',
                  dominanceSignal.color === 'text-success' && 'bg-success',
                  dominanceSignal.color === 'text-destructive' && 'bg-destructive',
                  dominanceSignal.color === 'text-blue-400' && 'bg-blue-400',
                )} />
                <span className={dominanceSignal.color}>{dominanceSignal.signal}</span>
              </div>
              <CaretRight 
                size={12} 
                className="text-muted-foreground group-hover:text-accent group-hover:translate-x-0.5 transition-all" 
              />
            </div>
          </div>
          <DominanceBar btcD={btcD} altD={altD} stableD={stableD} />
        </Link>

        {/* Collapsible: Dimension Breakdown */}
        <CollapsibleSection title="DIMENSION ANALYSIS" icon={Activity} defaultOpen={false}>
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: 'Trend', value: regime?.dimensions?.trend, score: regime?.trend_score || 0, icon: TrendUp },
              { label: 'Volatility', value: regime?.dimensions?.volatility, score: regime?.volatility_score || 0, icon: Lightning },
              { label: 'Liquidity', value: regime?.dimensions?.liquidity, score: regime?.liquidity_score || 0, icon: Drop },
              { label: 'Risk', value: regime?.dimensions?.risk_appetite, score: regime?.risk_score || 0, icon: ShieldWarning },
            ].map((dim) => (
              <div key={dim.label} className="flex items-center gap-2 p-2 rounded-lg bg-muted/10">
                <dim.icon size={14} className={dim.score >= 60 ? 'text-success' : dim.score >= 40 ? 'text-warning' : 'text-destructive'} />
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-muted-foreground">{dim.label}</span>
                    <span className={cn('text-xs font-bold capitalize', dim.score >= 60 ? 'text-success' : dim.score >= 40 ? 'text-warning' : 'text-destructive')}>
                      {dim.value || 'N/A'}
                    </span>
                  </div>
                  <div className="h-1 bg-muted/30 rounded-full overflow-hidden mt-1">
                    <div 
                      className={cn('h-full rounded-full transition-all', dim.score >= 60 ? 'bg-success' : dim.score >= 40 ? 'bg-warning' : 'bg-destructive')}
                      style={{ width: `${dim.score}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      </div>

      {/* Footer with Market Intel Link */}
      <div className="px-4 py-2 border-t border-border/40 bg-muted/5 flex items-center justify-between">
        {error ? (
          <div className="flex items-center gap-2 text-[10px] text-warning">
            <Warning size={12} />
            <span>Cached data</span>
          </div>
        ) : (
          <Link 
            to="/intel" 
            className="flex items-center gap-2 text-[10px] text-accent hover:underline group"
          >
            <Compass size={12} />
            <span>Full analysis in Market Intel</span>
            <CaretRight size={10} className="group-hover:translate-x-0.5 transition-transform" />
          </Link>
        )}
        <span className="text-[10px] text-muted-foreground font-mono">Auto-refresh: 60s</span>
      </div>
    </div>
  );
}
