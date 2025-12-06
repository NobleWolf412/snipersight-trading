import { useState, useEffect, useCallback } from 'react';
import {
  Clock,
  ChartLine,
  Warning,
  Info,
  CaretDown,
  CaretRight,
  Target,
  ArrowUp,
  ArrowDown,
  CheckCircle,
  Timer,
} from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { api } from '@/utils/api';
import { Link } from 'react-router-dom';
import { 
  CyclePhaseGraphic, 
  TranslationGraphic, 
  StochRSIGraphic,
  type CyclePhase,
  type Translation,
  type StochZone,
} from './CycleGraphics';

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
  phase: CyclePhase;
  translation: Translation;
  trade_bias: 'LONG' | 'SHORT' | 'NEUTRAL';
  confidence: number;
  stochastic_rsi: {
    k: number | null;
    d: number | null;
    zone: StochZone;
  };
  interpretation: {
    messages: string[];
    severity: 'neutral' | 'bullish' | 'bearish' | 'caution';
    summary: string;
  };
  timestamp: string;
  error?: string;
}

// Compact progress bar for cycle timing
function MiniProgressBar({ 
  current, 
  min, 
  max, 
  inZone,
  label,
  confirmed,
  confirmedPrice,
}: { 
  current: number | null;
  min: number;
  max: number;
  inZone: boolean;
  label: string;
  confirmed?: boolean;
  confirmedPrice?: number | null;
}) {
  if (current === null) return null;
  
  const progress = Math.min(100, (current / max) * 100);
  const zoneStart = (min / max) * 100;
  
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-[10px]">
        <span className="font-bold tracking-wider text-muted-foreground">{label}</span>
        <span className={cn(
          'font-mono tabular-nums',
          inZone ? 'text-success font-bold' : current > max ? 'text-warning' : 'text-muted-foreground'
        )}>
          Day {current} / {min}-{max}
        </span>
      </div>
      <div className="relative h-2 bg-muted/30 rounded-full overflow-hidden">
        {/* Zone indicator */}
        <div 
          className="absolute h-full bg-success/20 border-l border-success/40"
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
      </div>
      {confirmed && confirmedPrice && (
        <div className="flex items-center gap-1 text-[10px] text-success">
          <Target size={10} weight="bold" />
          <span>Confirmed at ${confirmedPrice.toLocaleString()}</span>
        </div>
      )}
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
  icon: typeof Info;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  
  return (
    <div className="border border-border/30 rounded-xl overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-2.5 flex items-center justify-between bg-muted/10 hover:bg-muted/20 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon size={12} className="text-accent" />
          <span className="text-[10px] font-bold tracking-wider">{title}</span>
        </div>
        <CaretDown 
          size={12} 
          className={cn('text-muted-foreground transition-transform', isOpen && 'rotate-180')} 
        />
      </button>
      <div className={cn(
        'grid transition-all duration-300',
        isOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
      )}>
        <div className="overflow-hidden">
          <div className="p-4">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}

export function MarketCyclesBrief() {
  const [cycleData, setCycleData] = useState<CycleData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCycleData = useCallback(async () => {
    try {
      const response = await api.getMarketCycles('BTCUSDT');
      if (response.data) {
        setCycleData(response.data);
        setError(null);
      } else if (response.error) {
        setError(response.error);
      }
    } catch (err) {
      setError('Cycle data unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCycleData();
    const interval = setInterval(fetchCycleData, 60000);
    return () => clearInterval(interval);
  }, [fetchCycleData]);

  // Loading state
  if (loading) {
    return (
      <div className="relative p-6 rounded-xl border border-border/40 bg-card/50 backdrop-blur-sm">
        <div className="flex items-center justify-center gap-3 py-4">
          <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <span className="text-sm tracking-wider text-muted-foreground">Analyzing cycles...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !cycleData) {
    return (
      <div className="relative p-6 rounded-xl border border-destructive/30 bg-destructive/5 backdrop-blur-sm">
        <div className="flex items-center gap-3 text-destructive">
          <Warning size={18} weight="bold" />
          <span className="text-sm">{error || 'Cycle data unavailable'}</span>
        </div>
      </div>
    );
  }

  // Severity colors for border
  const severityBorder = {
    bullish: 'border-success/40',
    bearish: 'border-destructive/40',
    caution: 'border-warning/40',
    neutral: 'border-border/40'
  };

  return (
    <div className={cn(
      'relative rounded-xl border bg-card/50 backdrop-blur-sm overflow-hidden',
      severityBorder[cycleData.interpretation.severity]
    )}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-border/30 bg-muted/10 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ChartLine size={16} className="text-accent" weight="bold" />
          <span className="text-xs font-bold tracking-[0.15em]">MARKET CYCLES</span>
          <span className="text-[10px] text-muted-foreground font-mono">{cycleData.symbol}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className={cn(
            'flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-bold',
            cycleData.trade_bias === 'LONG' && 'bg-success/20 text-success',
            cycleData.trade_bias === 'SHORT' && 'bg-destructive/20 text-destructive',
            cycleData.trade_bias === 'NEUTRAL' && 'bg-muted/30 text-muted-foreground'
          )}>
            {cycleData.trade_bias === 'LONG' && <ArrowUp size={10} weight="bold" />}
            {cycleData.trade_bias === 'SHORT' && <ArrowDown size={10} weight="bold" />}
            {cycleData.trade_bias} BIAS
          </div>
          <span className="text-[10px] text-muted-foreground font-mono">{cycleData.confidence}%</span>
        </div>
      </div>

      {/* Main Content */}
      <div className="p-4 space-y-4">
        
        {/* Interactive Graphics Row */}
        <div className="grid grid-cols-3 gap-3">
          <CyclePhaseGraphic 
            phase={cycleData.phase} 
            compact={false}
          />
          <TranslationGraphic 
            translation={cycleData.translation} 
            compact={false}
          />
          <StochRSIGraphic 
            k={cycleData.stochastic_rsi.k}
            d={cycleData.stochastic_rsi.d}
            zone={cycleData.stochastic_rsi.zone}
            compact={false}
          />
        </div>

        {/* Cycle Intelligence - The actionable insights */}
        <div className={cn(
          'p-4 rounded-xl border',
          cycleData.interpretation.severity === 'bullish' && 'bg-success/5 border-success/30',
          cycleData.interpretation.severity === 'bearish' && 'bg-destructive/5 border-destructive/30',
          cycleData.interpretation.severity === 'caution' && 'bg-warning/5 border-warning/30',
          cycleData.interpretation.severity === 'neutral' && 'bg-muted/10 border-border/30'
        )}>
          <div className="flex items-center gap-2 mb-2">
            <Info size={14} className="text-accent" weight="bold" />
            <span className="text-[10px] font-bold tracking-wider">CYCLE INTELLIGENCE</span>
          </div>
          <ul className="space-y-1.5">
            {cycleData.interpretation.messages.map((msg, idx) => (
              <li key={idx} className="text-xs text-foreground/90 flex items-start gap-2">
                <CheckCircle size={12} className={cn(
                  'mt-0.5 flex-shrink-0',
                  cycleData.interpretation.severity === 'bullish' && 'text-success',
                  cycleData.interpretation.severity === 'bearish' && 'text-destructive',
                  cycleData.interpretation.severity === 'caution' && 'text-warning',
                  cycleData.interpretation.severity === 'neutral' && 'text-muted-foreground'
                )} />
                {msg}
              </li>
            ))}
          </ul>
        </div>

        {/* Collapsible: Timing Details */}
        <CollapsibleSection title="CYCLE TIMING DETAILS" icon={Timer} defaultOpen={false}>
          <div className="space-y-4">
            {/* DCL Progress */}
            {cycleData.dcl && (
              <MiniProgressBar
                current={cycleData.dcl.days_since}
                min={cycleData.dcl.typical_range.min}
                max={cycleData.dcl.typical_range.max}
                inZone={cycleData.dcl.in_zone}
                label="DAILY CYCLE LOW (DCL)"
                confirmed={cycleData.dcl.confirmation === 'confirmed'}
                confirmedPrice={cycleData.dcl.price}
              />
            )}
            
            {/* WCL Progress */}
            {cycleData.wcl && (
              <MiniProgressBar
                current={cycleData.wcl.days_since}
                min={cycleData.wcl.typical_range.min}
                max={cycleData.wcl.typical_range.max}
                inZone={cycleData.wcl.in_zone}
                label="WEEKLY CYCLE LOW (WCL)"
                confirmed={cycleData.wcl.confirmation === 'confirmed'}
                confirmedPrice={cycleData.wcl.price}
              />
            )}
            
            {/* Expected windows */}
            <div className="flex flex-wrap items-center justify-center gap-4 pt-2 text-[10px] text-muted-foreground">
              {cycleData.dcl && cycleData.dcl.expected_window.max_days > 0 && (
                <div className="flex items-center gap-1.5">
                  <Clock size={12} />
                  <span>Next DCL: {cycleData.dcl.expected_window.min_days}-{cycleData.dcl.expected_window.max_days} days</span>
                </div>
              )}
              {cycleData.wcl && cycleData.wcl.expected_window.max_days > 0 && (
                <div className="flex items-center gap-1.5">
                  <Clock size={12} />
                  <span>Next WCL: {cycleData.wcl.expected_window.min_days}-{cycleData.wcl.expected_window.max_days} days</span>
                </div>
              )}
            </div>
          </div>
        </CollapsibleSection>
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-border/30 bg-muted/5 flex items-center justify-between">
        <span className="text-[10px] text-muted-foreground">Based on Camel Finance methodology</span>
        <span className="text-[10px] text-muted-foreground font-mono">
          {new Date(cycleData.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </div>
  );
}
