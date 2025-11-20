import { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { CaretDown, CaretUp, TrendUp, TrendDown, ArrowRight, Info } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

export type RegimeLabel = 'ALTSEASON' | 'BTC_DRIVE' | 'DEFENSIVE' | 'PANIC' | 'CHOPPY';
export type Visibility = 'HIGH' | 'MEDIUM' | 'LOW' | 'VERY_LOW';
export type RegimeColor = 'green' | 'blue' | 'yellow' | 'orange' | 'red';

export interface MarketRegimeLensProps {
  regimeLabel: RegimeLabel;
  visibility: Visibility;
  color?: RegimeColor;
  btcDominance?: number;
  usdtDominance?: number;
  altDominance?: number;
  guidanceLines?: string[];
  mode?: 'scanner' | 'bot';
  previousBtcDominance?: number;
  previousUsdtDominance?: number;
  previousAltDominance?: number;
}

const REGIME_DISPLAY_NAMES: Record<RegimeLabel, string> = {
  ALTSEASON: 'ALTSEASON',
  BTC_DRIVE: 'BTC DRIVE',
  DEFENSIVE: 'DEFENSIVE (BTC Only)',
  PANIC: 'PANIC MODE',
  CHOPPY: 'CHOPPY SEAS',
};

const REGIME_COLORS: Record<RegimeLabel, RegimeColor> = {
  ALTSEASON: 'green',
  BTC_DRIVE: 'blue',
  DEFENSIVE: 'orange',
  PANIC: 'red',
  CHOPPY: 'yellow',
};

const COLOR_CLASSES = {
  green: {
    lens: 'border-success shadow-success/30',
    reticle: 'bg-success/20 border-success',
    innerReticle: 'border-success/60',
    glow: 'shadow-[0_0_30px_rgba(134,239,172,0.3)]',
    text: 'text-success',
    bg: 'bg-success/10',
  },
  blue: {
    lens: 'border-blue-500 shadow-blue-500/30',
    reticle: 'bg-blue-500/20 border-blue-500',
    innerReticle: 'border-blue-500/60',
    glow: 'shadow-[0_0_30px_rgba(59,130,246,0.3)]',
    text: 'text-blue-500',
    bg: 'bg-blue-500/10',
  },
  yellow: {
    lens: 'border-warning shadow-warning/30',
    reticle: 'bg-warning/20 border-warning',
    innerReticle: 'border-warning/60',
    glow: 'shadow-[0_0_30px_rgba(234,179,8,0.3)]',
    text: 'text-warning',
    bg: 'bg-warning/10',
  },
  orange: {
    lens: 'border-orange-500 shadow-orange-500/30',
    reticle: 'bg-orange-500/20 border-orange-500',
    innerReticle: 'border-orange-500/60',
    glow: 'shadow-[0_0_30px_rgba(249,115,22,0.3)]',
    text: 'text-orange-500',
    bg: 'bg-orange-500/10',
  },
  red: {
    lens: 'border-destructive shadow-destructive/30',
    reticle: 'bg-destructive/20 border-destructive',
    innerReticle: 'border-destructive/60',
    glow: 'shadow-[0_0_30px_rgba(239,68,68,0.3)]',
    text: 'text-destructive',
    bg: 'bg-destructive/10',
  },
};

function DominanceTrend({ current, previous }: { current?: number; previous?: number }) {
  if (current === undefined || previous === undefined) return null;
  
  const diff = current - previous;
  const Icon = diff > 0.1 ? TrendUp : diff < -0.1 ? TrendDown : ArrowRight;
  const colorClass = diff > 0.1 ? 'text-success' : diff < -0.1 ? 'text-destructive' : 'text-muted-foreground';
  
  return <Icon size={16} className={cn('ml-1', colorClass)} weight="bold" />;
}

export function MarketRegimeLens({
  regimeLabel,
  visibility,
  color,
  btcDominance,
  usdtDominance,
  altDominance,
  guidanceLines = [],
  mode = 'scanner',
  previousBtcDominance,
  previousUsdtDominance,
  previousAltDominance,
}: MarketRegimeLensProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const regimeColor = color || REGIME_COLORS[regimeLabel];
  const colorClasses = COLOR_CLASSES[regimeColor];
  const regimeDisplayName = REGIME_DISPLAY_NAMES[regimeLabel];

  const visibilityPercent = {
    HIGH: 90,
    MEDIUM: 60,
    LOW: 35,
    VERY_LOW: 15,
  }[visibility];

  const visibilityDescription = {
    HIGH: 'Ideal conditions with clear trend signals and low noise',
    MEDIUM: 'Good conditions with moderate trend signals',
    LOW: 'Challenging conditions with weak or mixed signals',
    VERY_LOW: 'Very difficult conditions with high noise and uncertainty',
  }[visibility];

  return (
    <Card className={cn('bg-card/80 border-2', colorClasses.lens, colorClasses.glow)}>
      <CardContent className="p-4 md:p-6">
        <div className="flex flex-col md:flex-row gap-4 md:gap-6 items-start md:items-center">
          <TooltipProvider>
            <Tooltip delayDuration={100}>
              <TooltipTrigger asChild>
                <div className="flex-shrink-0 cursor-help">
                  <div className={cn(
                    'relative w-28 h-28 md:w-32 md:h-32 rounded-full border-4 flex items-center justify-center',
                    colorClasses.reticle,
                    'transition-all duration-300'
                  )}>
                    <div className={cn(
                      'absolute inset-4 rounded-full border-2',
                      colorClasses.innerReticle
                    )}>
                      <div className={cn(
                        'absolute inset-3 rounded-full border',
                        colorClasses.innerReticle,
                        'opacity-50'
                      )} />
                    </div>
                    
                    <div className={cn('absolute w-full h-0.5', colorClasses.reticle.split(' ')[1])} />
                    <div className={cn('absolute h-full w-0.5', colorClasses.reticle.split(' ')[1])} />
                    
                    <div className="text-center z-10">
                      <div className={cn('text-xs font-bold tracking-wider', colorClasses.text)}>
                        CLARITY
                      </div>
                      <div className={cn('text-2xl font-bold tabular-nums', colorClasses.text)}>
                        {visibilityPercent}%
                      </div>
                    </div>
                  </div>
                </div>
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                <p className="font-bold mb-1">Market Clarity Score</p>
                <p className="text-sm">{visibilityDescription}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          <div className="flex-1 space-y-3 min-w-0">
            <div className="space-y-1">
              <div className="text-xs font-bold text-muted-foreground tracking-wider">
                MARKET REGIME
              </div>
              <div className={cn('text-xl md:text-2xl font-bold tracking-tight', colorClasses.text)}>
                {regimeDisplayName}
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <TooltipProvider>
                  <Tooltip delayDuration={100}>
                    <TooltipTrigger asChild>
                      <div className="flex items-center gap-1 cursor-help">
                        <Badge variant="outline" className={cn('font-mono text-xs', colorClasses.text, 'border-current')}>
                          Signal Quality: {visibility}
                        </Badge>
                        <Info size={14} className={cn('opacity-60', colorClasses.text)} />
                      </div>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs">
                      <p className="font-bold mb-1">Signal Quality</p>
                      <p className="text-sm mb-2">How clear and reliable trading signals are in current conditions.</p>
                      <div className="text-xs space-y-1">
                        <p><span className="font-bold">HIGH (90%):</span> Clear trends, low noise</p>
                        <p><span className="font-bold">MEDIUM (60%):</span> Moderate trends</p>
                        <p><span className="font-bold">LOW (35%):</span> Weak signals, choppy</p>
                        <p><span className="font-bold">VERY LOW (15%):</span> High uncertainty</p>
                      </div>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                {mode === 'bot' && (
                  <TooltipProvider>
                    <Tooltip delayDuration={100}>
                      <TooltipTrigger asChild>
                        <div className="flex items-center gap-1 cursor-help">
                          <Badge variant="outline" className={cn('font-mono text-xs', colorClasses.text, 'border-current')}>
                            Risk Multiplier: {visibility === 'HIGH' ? '1.5x' : visibility === 'MEDIUM' ? '1.0x' : visibility === 'LOW' ? '0.5x' : '0.25x'}
                          </Badge>
                          <Info size={14} className={cn('opacity-60', colorClasses.text)} />
                        </div>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs">
                        <p className="font-bold mb-1">Risk Multiplier</p>
                        <p className="text-sm">Adjusts position sizing based on signal quality. Higher quality = larger positions, lower quality = smaller positions for protection.</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                )}
              </div>
            </div>

            {(btcDominance !== undefined || usdtDominance !== undefined || altDominance !== undefined) && (
              <div className="flex gap-3 md:gap-4 text-xs flex-wrap">
                {btcDominance !== undefined && (
                  <div className="flex items-center gap-1">
                    <span className="text-muted-foreground">BTC.D:</span>
                    <span className="font-mono font-bold">{btcDominance.toFixed(1)}%</span>
                    <DominanceTrend current={btcDominance} previous={previousBtcDominance} />
                  </div>
                )}
                {usdtDominance !== undefined && (
                  <div className="flex items-center gap-1">
                    <span className="text-muted-foreground">USDT.D:</span>
                    <span className="font-mono font-bold">{usdtDominance.toFixed(1)}%</span>
                    <DominanceTrend current={usdtDominance} previous={previousUsdtDominance} />
                  </div>
                )}
                {altDominance !== undefined && (
                  <div className="flex items-center gap-1">
                    <span className="text-muted-foreground">ALT.D:</span>
                    <span className="font-mono font-bold">{altDominance.toFixed(1)}%</span>
                    <DominanceTrend current={altDominance} previous={previousAltDominance} />
                  </div>
                )}
              </div>
            )}

            {guidanceLines.length > 0 && (
              <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
                <div className="space-y-2">
                  <div className={cn('text-sm space-y-1.5 p-3 rounded-md', colorClasses.bg)}>
                    {guidanceLines.slice(0, 2).map((line, index) => (
                      <div key={index} className="flex items-start gap-2">
                        <span className={cn('text-xs mt-0.5', colorClasses.text)}>▸</span>
                        <span className="text-foreground">{line}</span>
                      </div>
                    ))}
                  </div>
                  
                  <CollapsibleContent>
                    <div className={cn('text-sm space-y-1.5 p-3 rounded-md', colorClasses.bg)}>
                      {guidanceLines.slice(2).map((line, index) => (
                        <div key={index + 2} className="flex items-start gap-2">
                          <span className={cn('text-xs mt-0.5', colorClasses.text)}>▸</span>
                          <span className="text-foreground">{line}</span>
                        </div>
                      ))}
                    </div>
                  </CollapsibleContent>
                  
                  {guidanceLines.length > 2 && (
                    <CollapsibleTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className={cn('h-7 text-xs', colorClasses.text, 'hover:bg-current/10')}
                      >
                        {isExpanded ? (
                          <>
                            <CaretUp size={14} />
                            Show Less
                          </>
                        ) : (
                          <>
                            <CaretDown size={14} />
                            Show {guidanceLines.length - 2} More
                          </>
                        )}
                      </Button>
                    </CollapsibleTrigger>
                  )}
                </div>
              </Collapsible>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
