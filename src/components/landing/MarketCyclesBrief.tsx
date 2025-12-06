import { useState, useEffect, useCallback } from 'react';
import {
  Clock,
  TrendUp,
  TrendDown,
  Minus,
  Target,
  ArrowUp,
  ArrowDown,
  Lightning,
  ChartLine,
  Warning,
  CheckCircle,
  Timer,
  Gauge,
  ArrowsCounterClockwise,
  Info,
} from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { api } from '@/utils/api';

// Types matching the API response
interface CycleData {
  symbol: string;
  dcl: {
    days_since: number | null;
    price: number | null;
    timestamp: string | null;
    confirmation: string;
    in_zone: boolean;
    expected_window: { min_days: number; max_days: number };
    typical_range: { min: number; max: number };
  } | null;
  wcl: {
    days_since: number | null;
    price: number | null;
    timestamp: string | null;
    confirmation: string;
    in_zone: boolean;
    expected_window: { min_days: number; max_days: number };
    typical_range: { min: number; max: number };
  } | null;
  cycle_high: {
    price: number | null;
    timestamp: string | null;
    midpoint_price: number | null;
  };
  phase: 'ACCUMULATION' | 'MARKUP' | 'DISTRIBUTION' | 'MARKDOWN' | 'UNKNOWN';
  translation: 'LEFT_TRANSLATED' | 'MID_TRANSLATED' | 'RIGHT_TRANSLATED' | 'UNKNOWN';
  trade_bias: 'LONG' | 'SHORT' | 'NEUTRAL';
  confidence: number;
  stochastic_rsi: {
    k: number | null;
    d: number | null;
    zone: 'oversold' | 'overbought' | 'neutral';
  };
  interpretation: {
    messages: string[];
    severity: 'neutral' | 'bullish' | 'bearish' | 'caution';
    summary: string;
  };
  timestamp: string;
  error?: string;
}

// Phase display configuration
const PHASE_CONFIG: Record<string, { label: string; color: string; icon: typeof TrendUp; description: string }> = {
  'ACCUMULATION': {
    label: 'ACCUMULATION',
    color: 'text-success',
    icon: Target,
    description: 'Smart money accumulating at cycle low'
  },
  'MARKUP': {
    label: 'MARKUP',
    color: 'text-blue-400',
    icon: TrendUp,
    description: 'Price rising from cycle low'
  },
  'DISTRIBUTION': {
    label: 'DISTRIBUTION',
    color: 'text-warning',
    icon: ArrowsCounterClockwise,
    description: 'Smart money distributing at cycle high'
  },
  'MARKDOWN': {
    label: 'MARKDOWN',
    color: 'text-destructive',
    icon: TrendDown,
    description: 'Price falling toward next cycle low'
  },
  'UNKNOWN': {
    label: 'ANALYZING...',
    color: 'text-muted-foreground',
    icon: ChartLine,
    description: 'Insufficient data for phase determination'
  }
};

// Translation display configuration
const TRANSLATION_CONFIG: Record<string, { label: string; color: string; bias: string }> = {
  'LEFT_TRANSLATED': {
    label: 'LEFT TRANSLATED',
    color: 'text-destructive',
    bias: 'Bearish - cycle topped early'
  },
  'MID_TRANSLATED': {
    label: 'MID TRANSLATED',
    color: 'text-warning',
    bias: 'Neutral - balanced cycle'
  },
  'RIGHT_TRANSLATED': {
    label: 'RIGHT TRANSLATED',
    color: 'text-success',
    bias: 'Bullish - cycle topped late'
  },
  'UNKNOWN': {
    label: 'PENDING',
    color: 'text-muted-foreground',
    bias: 'Awaiting cycle high'
  }
};

// Stochastic zone configuration
const STOCH_ZONE_CONFIG: Record<string, { label: string; color: string; icon: typeof ArrowUp }> = {
  'oversold': { label: 'OVERSOLD ZONE', color: 'text-success', icon: ArrowDown },
  'overbought': { label: 'OVERBOUGHT ZONE', color: 'text-destructive', icon: ArrowUp },
  'neutral': { label: 'NEUTRAL ZONE', color: 'text-muted-foreground', icon: Minus }
};

// Progress bar component for cycle timing
function CycleProgressBar({ 
  daysSince, 
  typicalMin, 
  typicalMax, 
  inZone,
  label 
}: { 
  daysSince: number | null; 
  typicalMin: number; 
  typicalMax: number; 
  inZone: boolean;
  label: string;
}) {
  if (daysSince === null) return null;
  
  const progress = Math.min(100, (daysSince / typicalMax) * 100);
  const zoneStart = (typicalMin / typicalMax) * 100;
  
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium tracking-wider">{label}</span>
        <span className={cn(
          'font-mono tabular-nums',
          inZone ? 'text-success' : daysSince > typicalMax ? 'text-warning' : 'text-muted-foreground'
        )}>
          Day {daysSince} / {typicalMin}-{typicalMax}
        </span>
      </div>
      <div className="relative h-3 bg-muted/30 rounded-full overflow-hidden">
        {/* Zone indicator */}
        <div 
          className="absolute h-full bg-success/20 border-l-2 border-success/50"
          style={{ left: `${zoneStart}%`, width: `${100 - zoneStart}%` }}
        />
        {/* Progress */}
        <div 
          className={cn(
            'absolute h-full rounded-full transition-all duration-500',
            inZone ? 'bg-success' : progress > 100 ? 'bg-warning' : 'bg-accent'
          )}
          style={{ width: `${Math.min(progress, 100)}%` }}
        />
        {/* Current position marker */}
        <div 
          className={cn(
            'absolute top-0 h-full w-1 rounded-full',
            inZone ? 'bg-success' : 'bg-foreground'
          )}
          style={{ left: `${Math.min(progress, 100)}%` }}
        />
      </div>
      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
        <span>0</span>
        <span className="text-success/70">← DCL Zone →</span>
        <span>{typicalMax}</span>
      </div>
    </div>
  );
}

// Stochastic RSI visualization
function StochRSIGauge({ k, d, zone }: { k: number | null; d: number | null; zone: string }) {
  if (k === null || d === null) {
    return (
      <div className="text-center text-sm text-muted-foreground p-4">
        StochRSI data unavailable
      </div>
    );
  }
  
  const zoneConfig = STOCH_ZONE_CONFIG[zone] || STOCH_ZONE_CONFIG.neutral;
  const ZoneIcon = zoneConfig.icon;
  
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium tracking-wider">WEEKLY STOCH RSI</span>
        <div className={cn('flex items-center gap-1 text-xs font-bold', zoneConfig.color)}>
          <ZoneIcon size={12} weight="bold" />
          {zoneConfig.label}
        </div>
      </div>
      
      <div className="relative h-8 bg-muted/20 rounded-lg overflow-hidden">
        {/* Oversold zone */}
        <div className="absolute left-0 h-full w-[20%] bg-success/10 border-r border-success/30" />
        {/* Overbought zone */}
        <div className="absolute right-0 h-full w-[20%] bg-destructive/10 border-l border-destructive/30" />
        
        {/* K line marker */}
        <div 
          className="absolute top-1 h-3 w-1 bg-blue-400 rounded-full transition-all duration-500"
          style={{ left: `${k}%` }}
          title={`%K: ${k.toFixed(1)}`}
        />
        {/* D line marker */}
        <div 
          className="absolute bottom-1 h-3 w-1 bg-orange-400 rounded-full transition-all duration-500"
          style={{ left: `${d}%` }}
          title={`%D: ${d.toFixed(1)}`}
        />
        
        {/* Level markers */}
        <div className="absolute left-[20%] top-0 h-full border-l border-dashed border-success/40" />
        <div className="absolute left-[80%] top-0 h-full border-l border-dashed border-destructive/40" />
      </div>
      
      <div className="flex items-center justify-between text-[10px]">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 bg-blue-400 rounded-full" />
            <span className="text-muted-foreground">%K: <span className="font-mono">{k.toFixed(1)}</span></span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 bg-orange-400 rounded-full" />
            <span className="text-muted-foreground">%D: <span className="font-mono">{d.toFixed(1)}</span></span>
          </div>
        </div>
        <span className="text-success/70">20</span>
        <span className="text-destructive/70">80</span>
      </div>
      
      {/* Zone interpretation */}
      <div className={cn(
        'text-xs p-2 rounded-lg border',
        zone === 'oversold' && 'bg-success/10 border-success/30 text-success',
        zone === 'overbought' && 'bg-destructive/10 border-destructive/30 text-destructive',
        zone === 'neutral' && 'bg-muted/20 border-border/30 text-muted-foreground'
      )}>
        {zone === 'oversold' && '✅ Both K & D below 20 — bullish reversal zone'}
        {zone === 'overbought' && '⚠️ Both K & D above 80 — bearish reversal zone'}
        {zone === 'neutral' && 'Middle range — await extremes for cycle signals'}
      </div>
    </div>
  );
}

export function MarketCyclesBrief() {
  const [cycleData, setCycleData] = useState<CycleData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const fetchCycles = useCallback(async () => {
    try {
      const response = await api.getMarketCycles('BTC/USDT');
      if (response.data) {
        setCycleData(response.data);
        setError(null);
      } else if (response.error) {
        setError(response.error);
      }
    } catch (err) {
      setError('Failed to fetch cycle data');
    } finally {
      setLoading(false);
    }
  }, []);
  
  useEffect(() => {
    fetchCycles();
    // Refresh every 5 minutes
    const interval = setInterval(fetchCycles, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchCycles]);
  
  if (loading) {
    return (
      <div className="relative rounded-2xl border border-border/40 bg-card/50 backdrop-blur-sm p-6">
        <div className="flex items-center justify-center gap-3 text-muted-foreground">
          <div className="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin" />
          <span className="text-sm tracking-wider">ANALYZING MARKET CYCLES...</span>
        </div>
      </div>
    );
  }
  
  if (error || !cycleData) {
    return (
      <div className="relative rounded-2xl border border-destructive/30 bg-destructive/5 backdrop-blur-sm p-6">
        <div className="flex items-center gap-3 text-destructive">
          <Warning size={20} weight="bold" />
          <span className="text-sm">{error || 'Cycle data unavailable'}</span>
        </div>
      </div>
    );
  }
  
  const phaseConfig = PHASE_CONFIG[cycleData.phase] || PHASE_CONFIG.UNKNOWN;
  const translationConfig = TRANSLATION_CONFIG[cycleData.translation] || TRANSLATION_CONFIG.UNKNOWN;
  const PhaseIcon = phaseConfig.icon;
  
  // Determine overall severity for card styling
  const severityColors = {
    bullish: 'border-success/40 shadow-success/10',
    bearish: 'border-destructive/40 shadow-destructive/10',
    caution: 'border-warning/40 shadow-warning/10',
    neutral: 'border-border/40'
  };
  
  return (
    <div className={cn(
      'relative rounded-2xl border bg-card/50 backdrop-blur-sm shadow-lg overflow-hidden',
      severityColors[cycleData.interpretation.severity]
    )}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-border/30 bg-muted/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={cn('p-2 rounded-lg bg-muted/30', phaseConfig.color)}>
              <ChartLine size={20} weight="bold" />
            </div>
            <div>
              <h3 className="text-sm font-bold tracking-widest">MARKET CYCLES</h3>
              <p className="text-xs text-muted-foreground">{cycleData.symbol} Cycle Analysis</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className={cn(
              'px-3 py-1 rounded-full text-xs font-bold tracking-wider',
              cycleData.trade_bias === 'LONG' && 'bg-success/20 text-success',
              cycleData.trade_bias === 'SHORT' && 'bg-destructive/20 text-destructive',
              cycleData.trade_bias === 'NEUTRAL' && 'bg-muted/30 text-muted-foreground'
            )}>
              {cycleData.trade_bias === 'LONG' && <ArrowUp className="inline mr-1" size={12} />}
              {cycleData.trade_bias === 'SHORT' && <ArrowDown className="inline mr-1" size={12} />}
              {cycleData.trade_bias} BIAS
            </div>
            <div className="text-xs text-muted-foreground font-mono">
              {cycleData.confidence}%
            </div>
          </div>
        </div>
      </div>
      
      {/* Main content */}
      <div className="p-6 space-y-6">
        {/* Phase and Translation row */}
        <div className="grid grid-cols-2 gap-4">
          {/* Current Phase */}
          <div className="p-4 rounded-xl bg-muted/10 border border-border/30">
            <div className="flex items-center gap-2 mb-2">
              <PhaseIcon size={16} weight="bold" className={phaseConfig.color} />
              <span className="text-xs font-bold tracking-wider text-muted-foreground">CYCLE PHASE</span>
            </div>
            <div className={cn('text-lg font-bold tracking-wider', phaseConfig.color)}>
              {phaseConfig.label}
            </div>
            <p className="text-xs text-muted-foreground mt-1">{phaseConfig.description}</p>
          </div>
          
          {/* Translation */}
          <div className="p-4 rounded-xl bg-muted/10 border border-border/30">
            <div className="flex items-center gap-2 mb-2">
              <ArrowsCounterClockwise size={16} weight="bold" className={translationConfig.color} />
              <span className="text-xs font-bold tracking-wider text-muted-foreground">TRANSLATION</span>
            </div>
            <div className={cn('text-lg font-bold tracking-wider', translationConfig.color)}>
              {translationConfig.label}
            </div>
            <p className="text-xs text-muted-foreground mt-1">{translationConfig.bias}</p>
          </div>
        </div>
        
        {/* Cycle Timing */}
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Timer size={16} weight="bold" className="text-accent" />
            <span className="text-xs font-bold tracking-wider">CYCLE TIMING</span>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* DCL Progress */}
            {cycleData.dcl && (
              <div className={cn(
                'p-4 rounded-xl border',
                cycleData.dcl.in_zone ? 'bg-success/5 border-success/30' : 'bg-muted/10 border-border/30'
              )}>
                <CycleProgressBar
                  daysSince={cycleData.dcl.days_since}
                  typicalMin={cycleData.dcl.typical_range.min}
                  typicalMax={cycleData.dcl.typical_range.max}
                  inZone={cycleData.dcl.in_zone}
                  label="DAILY CYCLE LOW (DCL)"
                />
                {cycleData.dcl.in_zone && (
                  <div className="mt-3 flex items-center gap-2 text-xs text-success">
                    <CheckCircle size={14} weight="bold" />
                    <span>In DCL timing window — watch for reversal signals</span>
                  </div>
                )}
                {cycleData.dcl.confirmation === 'confirmed' && (
                  <div className="mt-2 flex items-center gap-2 text-xs text-success">
                    <Target size={14} weight="bold" />
                    <span>DCL confirmed at ${cycleData.dcl.price?.toLocaleString()}</span>
                  </div>
                )}
              </div>
            )}
            
            {/* WCL Progress */}
            {cycleData.wcl && (
              <div className={cn(
                'p-4 rounded-xl border',
                cycleData.wcl.in_zone ? 'bg-success/5 border-success/30' : 'bg-muted/10 border-border/30'
              )}>
                <CycleProgressBar
                  daysSince={cycleData.wcl.days_since}
                  typicalMin={cycleData.wcl.typical_range.min}
                  typicalMax={cycleData.wcl.typical_range.max}
                  inZone={cycleData.wcl.in_zone}
                  label="WEEKLY CYCLE LOW (WCL)"
                />
                {cycleData.wcl.in_zone && (
                  <div className="mt-3 flex items-center gap-2 text-xs text-success">
                    <CheckCircle size={14} weight="bold" />
                    <span>In WCL timing window — major reversal zone</span>
                  </div>
                )}
              </div>
            )}
          </div>
          
          {/* Expected windows */}
          <div className="flex items-center justify-center gap-8 text-xs text-muted-foreground">
            {cycleData.dcl && cycleData.dcl.expected_window.max_days > 0 && (
              <div className="flex items-center gap-2">
                <Clock size={14} />
                <span>Next DCL expected in {cycleData.dcl.expected_window.min_days}-{cycleData.dcl.expected_window.max_days} days</span>
              </div>
            )}
            {cycleData.wcl && cycleData.wcl.expected_window.max_days > 0 && (
              <div className="flex items-center gap-2">
                <Clock size={14} />
                <span>Next WCL expected in {cycleData.wcl.expected_window.min_days}-{cycleData.wcl.expected_window.max_days} days</span>
              </div>
            )}
          </div>
        </div>
        
        {/* Stochastic RSI */}
        <div className="p-4 rounded-xl bg-muted/10 border border-border/30">
          <StochRSIGauge 
            k={cycleData.stochastic_rsi.k} 
            d={cycleData.stochastic_rsi.d} 
            zone={cycleData.stochastic_rsi.zone} 
          />
        </div>
        
        {/* Interpretation messages */}
        <div className={cn(
          'p-4 rounded-xl border',
          cycleData.interpretation.severity === 'bullish' && 'bg-success/5 border-success/30',
          cycleData.interpretation.severity === 'bearish' && 'bg-destructive/5 border-destructive/30',
          cycleData.interpretation.severity === 'caution' && 'bg-warning/5 border-warning/30',
          cycleData.interpretation.severity === 'neutral' && 'bg-muted/10 border-border/30'
        )}>
          <div className="flex items-center gap-2 mb-3">
            <Info size={16} weight="bold" className="text-accent" />
            <span className="text-xs font-bold tracking-wider">CYCLE INTELLIGENCE</span>
          </div>
          <ul className="space-y-2">
            {cycleData.interpretation.messages.map((msg, idx) => (
              <li key={idx} className="text-sm text-foreground/90 flex items-start gap-2">
                <span className="text-muted-foreground">•</span>
                {msg}
              </li>
            ))}
          </ul>
        </div>
      </div>
      
      {/* Footer */}
      <div className="px-6 py-3 border-t border-border/30 bg-muted/10 flex items-center justify-between text-xs text-muted-foreground">
        <span>Based on Camel Finance methodology • DCL: 18-28 days • WCL: 35-50 days</span>
        <span className="font-mono">{new Date(cycleData.timestamp).toLocaleTimeString()}</span>
      </div>
    </div>
  );
}
