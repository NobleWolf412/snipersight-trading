import { useScanner } from '@/context/ScannerContext';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ArrowCircleRight, Crosshair, ArrowUpRight } from '@phosphor-icons/react';

interface Props {
  opp: {
    symbol: string;
    recommended_mode: string;
    confidence: number;
    expected_move_pct: number;
    rationale: string;
    level: {
      timeframe: string;
      level_type: string;
      price: number;
      proximity_pct: number;
      fib_ratio?: number;
      trend_direction?: string;
    };
  };
  onSwitchMode?: (mode: string) => void;
  onViewChart?: (symbol: string) => void;
}

// Fib level detection and display helpers
const FIB_LEVEL_TYPES = ['fib_236', 'fib_382', 'fib_500', 'fib_618', 'fib_786'] as const;
const GOLDEN_RATIOS = ['fib_382', 'fib_618'];

function isFibLevel(levelType: string): boolean {
  return levelType.startsWith('fib_');
}

function getFibDisplayName(levelType: string): string {
  const mapping: Record<string, string> = {
    'fib_236': '23.6%',
    'fib_382': '38.2%',
    'fib_500': '50.0%',
    'fib_618': '61.8%',
    'fib_786': '78.6%',
  };
  return mapping[levelType] || levelType.toUpperCase();
}

function isGoldenRatio(levelType: string): boolean {
  return GOLDEN_RATIOS.includes(levelType);
}

export function HTFOpportunityCard({ opp, onSwitchMode, onViewChart }: Props) {
  const isFib = isFibLevel(opp.level.level_type);
  const isGolden = isGoldenRatio(opp.level.level_type);

  const severityCls = opp.confidence >= 85
    ? 'border-red-500/60 bg-red-500/10'
    : opp.confidence >= 75
      ? 'border-orange-500/60 bg-orange-500/10'
      : 'border-yellow-500/50 bg-yellow-500/10';

  return (
    <div className={`rounded-lg border p-4 space-y-3 ${severityCls} backdrop-blur-sm`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="font-mono font-bold">
            {opp.symbol}
          </Badge>
          {isFib ? (
            <Badge
              variant={isGolden ? "default" : "secondary"}
              className={`text-xs font-mono ${isGolden ? 'bg-amber-500/80 hover:bg-amber-500 text-black' : 'bg-purple-500/30 text-purple-300'}`}
              title={isGolden ? 'Golden Ratio - High probability zone' : 'Fibonacci retracement level'}
            >
              {isGolden && '⭐ '}{opp.level.timeframe.toUpperCase()} FIB {getFibDisplayName(opp.level.level_type)}
            </Badge>
          ) : (
            <span className="text-xs text-muted-foreground">
              {opp.level.timeframe.toUpperCase()} {opp.level.level_type.toUpperCase()}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 text-xs font-mono">
            <span className="text-muted-foreground">CONF</span>
            <span className={opp.confidence >= 85 ? 'text-red-400' : opp.confidence >= 75 ? 'text-orange-400' : 'text-yellow-400'}>
              {opp.confidence.toFixed(0)}%
            </span>
          </div>
          <div className="flex items-center gap-1 text-xs font-mono">
            <span className="text-muted-foreground">MOVE</span>
            <span className="text-accent">{opp.expected_move_pct.toFixed(1)}%</span>
          </div>
        </div>
      </div>
      <div className="text-xs text-muted-foreground leading-relaxed">
        {opp.rationale}
      </div>
      <div className="flex flex-wrap gap-1">
        <Badge variant="secondary" className="text-[10px] font-mono" title="Proximity to level">
          Δ {opp.level.proximity_pct.toFixed(2)}%
        </Badge>
        <Badge variant="secondary" className="text-[10px] font-mono" title="Level price">
          @ ${opp.level.price.toFixed(5)}
        </Badge>
        {opp.level.trend_direction && (
          <Badge
            variant="outline"
            className={`text-[10px] font-mono ${opp.level.trend_direction === 'bullish' ? 'border-green-500/50 text-green-400' : 'border-red-500/50 text-red-400'}`}
            title="Trend direction for retracement"
          >
            {opp.level.trend_direction === 'bullish' ? '↑ BUY ZONE' : '↓ SELL ZONE'}
          </Badge>
        )}
        <Badge variant="outline" className="text-[10px]" title="Recommended mode">
          {opp.recommended_mode.toUpperCase()}
        </Badge>
      </div>
      <div className="flex items-center gap-2 pt-1">
        <Button size="sm" variant="default" onClick={() => onSwitchMode?.(opp.recommended_mode)} className="flex items-center gap-1">
          <Crosshair size={14} /> SWITCH MODE
        </Button>
        <Button size="sm" variant="outline" onClick={() => onViewChart?.(opp.symbol)} className="flex items-center gap-1">
          <ArrowUpRight size={14} /> CHART
        </Button>
      </div>
    </div>
  );
}
