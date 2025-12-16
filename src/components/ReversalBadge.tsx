import { Badge } from '@/components/ui/badge';
import { ArrowsClockwise, TrendUp, TrendDown } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import type { ReversalContext } from '@/types/cycle';

interface ReversalBadgeProps {
  reversalContext?: ReversalContext;
  size?: 'sm' | 'md' | 'lg';
  showDetails?: boolean;
  className?: string;
}

/**
 * ReversalBadge displays a prominent indicator when a setup is a trend reversal
 *
 * Features:
 * - Shows reversal direction (LONG/SHORT)
 * - Displays confidence score
 * - Indicates HTF bypass status
 * - Shows cycle alignment
 * - Provides detailed rationale on hover
 */
export function ReversalBadge({
  reversalContext,
  size = 'md',
  showDetails = false,
  className
}: ReversalBadgeProps) {
  // Don't render if no reversal context or not a reversal setup
  if (!reversalContext?.is_reversal_setup) {
    return null;
  }

  const isLong = reversalContext.direction === 'LONG';
  const confidence = reversalContext.confidence || 0;

  // Color based on direction
  const colorClasses = isLong
    ? 'bg-success/20 text-success border-success/50'
    : 'bg-destructive/20 text-destructive border-destructive/50';

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
    lg: 'px-3 py-1.5 text-base'
  };

  const iconSize = {
    sm: 12,
    md: 16,
    lg: 20
  };

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <Badge
        variant="outline"
        className={cn(
          'font-bold border-2 animate-pulse-slow',
          colorClasses,
          sizeClasses[size]
        )}
        title={reversalContext.rationale || 'Trend Reversal Setup Detected'}
      >
        <span className="flex items-center gap-1.5">
          <ArrowsClockwise size={iconSize[size]} weight="bold" className="animate-spin-slow" />
          {isLong ? (
            <TrendUp size={iconSize[size]} weight="bold" />
          ) : (
            <TrendDown size={iconSize[size]} weight="bold" />
          )}
          <span>REVERSAL</span>
          {confidence > 0 && (
            <span className="ml-1 opacity-80">
              {confidence.toFixed(0)}%
            </span>
          )}
        </span>
      </Badge>

      {showDetails && (
        <div className="flex flex-wrap gap-1.5 mt-1">
          {reversalContext.cycle_aligned && (
            <Badge
              variant="outline"
              className="text-xs bg-blue-500/10 text-blue-400 border-blue-500/30"
              title="At cycle extreme (DCL/WCL zone)"
            >
              Cycle Aligned
            </Badge>
          )}
          {reversalContext.htf_bypass_active && (
            <Badge
              variant="outline"
              className="text-xs bg-purple-500/10 text-purple-400 border-purple-500/30"
              title="Strong reversal - bypasses HTF alignment requirements"
            >
              HTF Bypass
            </Badge>
          )}
        </div>
      )}
    </div>
  );
}
