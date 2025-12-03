import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { CycleContext, CyclePhase, CycleTranslation } from '@/types/cycle';
import { PHASE_DISPLAY, TRANSLATION_DISPLAY } from '@/types/cycle';
import { ArrowFatLineRight, ArrowFatLineLeft, Minus, Recycle } from '@phosphor-icons/react';

interface CycleIndicatorProps {
  cycle?: CycleContext;
  size?: 'sm' | 'md' | 'lg';
  compact?: boolean;
  showTranslation?: boolean;
  showPhase?: boolean;
}

/**
 * Display cycle phase and translation indicator
 * - Phase: ACCUMULATION / MARKUP / DISTRIBUTION / MARKDOWN
 * - Translation: LTR (bearish) / MTR (neutral) / RTR (bullish)
 */
export function CycleIndicator({
  cycle,
  size = 'md',
  compact = false,
  showTranslation = true,
  showPhase = true,
}: CycleIndicatorProps) {
  if (!cycle) {
    return (
      <Badge variant="outline" className="text-muted-foreground border-muted">
        <Recycle size={12} className="mr-1" />
        No Cycle Data
      </Badge>
    );
  }

  const phase = cycle.phase;
  const translation = cycle.translation;
  const phaseDisplay = phase ? PHASE_DISPLAY[phase] : null;
  const translationDisplay = translation ? TRANSLATION_DISPLAY[translation] : null;

  const sizeClasses = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base',
  };

  // Translation arrow direction
  const TranslationIcon = translation === 'LTR' 
    ? ArrowFatLineLeft 
    : translation === 'RTR' 
      ? ArrowFatLineRight 
      : Minus;

  if (compact) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <div className={cn('flex items-center gap-1', sizeClasses[size])}>
              {showPhase && phaseDisplay && (
                <Badge 
                  variant="outline" 
                  className={cn('font-mono', phaseDisplay.color, 'border-current/30')}
                >
                  {phaseDisplay.icon}
                </Badge>
              )}
              {showTranslation && translationDisplay && (
                <Badge 
                  variant="outline" 
                  className={cn('font-mono', translationDisplay.color, 'border-current/30')}
                >
                  <TranslationIcon size={14} weight="bold" />
                </Badge>
              )}
            </div>
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-xs">
            <div className="space-y-1">
              {phaseDisplay && (
                <div className="text-sm">
                  <span className="font-semibold">{phaseDisplay.label}</span>
                  <span className="text-muted-foreground"> - {phaseDisplay.description}</span>
                </div>
              )}
              {translationDisplay && (
                <div className="text-sm">
                  <span className="font-semibold">{translationDisplay.emoji} {translationDisplay.label}</span>
                  <span className="text-muted-foreground"> - {translationDisplay.description}</span>
                </div>
              )}
              {cycle.days_since_dcl !== undefined && (
                <div className="text-xs text-muted-foreground">
                  Days since DCL: {cycle.days_since_dcl}
                  {cycle.dcl_due && <span className="text-warning ml-1">(DCL due)</span>}
                </div>
              )}
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return (
    <div className={cn('space-y-2', sizeClasses[size])}>
      {showPhase && phaseDisplay && (
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground text-xs uppercase tracking-wider">Phase:</span>
          <Badge 
            variant="outline" 
            className={cn('font-semibold', phaseDisplay.color, 'border-current/30')}
          >
            {phaseDisplay.icon} {phaseDisplay.label}
          </Badge>
        </div>
      )}
      
      {showTranslation && translationDisplay && (
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground text-xs uppercase tracking-wider">Translation:</span>
          <Badge 
            variant="outline" 
            className={cn('font-semibold', translationDisplay.color, 'border-current/30')}
          >
            <TranslationIcon size={14} weight="bold" className="mr-1" />
            {translationDisplay.label}
          </Badge>
          {cycle.translation_confidence !== undefined && (
            <span className="text-xs text-muted-foreground">
              ({cycle.translation_confidence}% conf)
            </span>
          )}
        </div>
      )}

      {/* Cycle timing info */}
      {(cycle.days_since_dcl !== undefined || cycle.days_since_wcl !== undefined) && (
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
          {cycle.days_since_dcl !== undefined && (
            <div className="flex items-center gap-1">
              <span>DCL:</span>
              <span className="font-mono">
                {cycle.days_since_dcl}d
                {cycle.expected_dcl_window && (
                  <span className="text-muted-foreground/60">
                    /{cycle.expected_dcl_window[0]}-{cycle.expected_dcl_window[1]}
                  </span>
                )}
              </span>
              {cycle.dcl_due && (
                <Badge variant="outline" className="text-warning border-warning/30 text-[10px]">
                  DUE
                </Badge>
              )}
            </div>
          )}
          {cycle.days_since_wcl !== undefined && (
            <div className="flex items-center gap-1">
              <span>WCL:</span>
              <span className="font-mono">
                {cycle.days_since_wcl}d
                {cycle.expected_wcl_window && (
                  <span className="text-muted-foreground/60">
                    /{cycle.expected_wcl_window[0]}-{cycle.expected_wcl_window[1]}
                  </span>
                )}
              </span>
              {cycle.wcl_due && (
                <Badge variant="outline" className="text-warning border-warning/30 text-[10px]">
                  DUE
                </Badge>
              )}
            </div>
          )}
        </div>
      )}

      {/* Cycle bias */}
      {cycle.cycle_bias && (
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground text-xs uppercase tracking-wider">Cycle Bias:</span>
          <Badge 
            variant="outline" 
            className={cn(
              'font-bold',
              cycle.cycle_bias === 'LONG' ? 'text-success border-success/30' :
              cycle.cycle_bias === 'SHORT' ? 'text-destructive border-destructive/30' :
              'text-muted-foreground border-muted'
            )}
          >
            {cycle.cycle_bias}
          </Badge>
        </div>
      )}
    </div>
  );
}

/**
 * Translation arrow for compact display in price cards
 */
export function TranslationArrow({ translation, size = 16 }: { translation?: CycleTranslation; size?: number }) {
  if (!translation) return null;
  
  const display = TRANSLATION_DISPLAY[translation];
  const Icon = translation === 'LTR' 
    ? ArrowFatLineLeft 
    : translation === 'RTR' 
      ? ArrowFatLineRight 
      : Minus;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className={cn('inline-flex items-center gap-1', display.color)}>
            {display.emoji}
            <Icon size={size} weight="bold" />
          </span>
        </TooltipTrigger>
        <TooltipContent side="top">
          <div className="text-sm">
            <div className="font-semibold">{display.label}</div>
            <div className="text-xs text-muted-foreground">{display.description}</div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
