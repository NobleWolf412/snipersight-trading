import { usePrice } from '@/hooks/usePriceData';
import { ArrowUp, ArrowDown } from '@phosphor-icons/react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

interface PriceDisplayProps {
  symbol: string;
  showChange?: boolean;
  showVolume?: boolean;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

export function PriceDisplay({ 
  symbol, 
  showChange = true, 
  showVolume = false,
  className,
  size = 'md'
}: PriceDisplayProps) {
  const { priceData, isLoading } = usePrice(symbol);

  const sizeClasses = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-xl',
  };

  if (isLoading) {
    return (
      <div className={cn('flex items-center gap-2', className)}>
        <Skeleton className="h-6 w-24" />
        {showChange && <Skeleton className="h-5 w-16" />}
      </div>
    );
  }

  if (!priceData) {
    return (
      <div className={cn('text-muted-foreground', sizeClasses[size], className)}>
        No data
      </div>
    );
  }

  const isPositive = priceData.changePercent24h >= 0;
  const changeColor = isPositive ? 'text-success' : 'text-destructive';

  const formatPrice = (price: number) => {
    if (price >= 1000) return price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (price >= 1) return price.toFixed(4);
    return price.toFixed(6);
  };

  const formatVolume = (volume: number) => {
    if (volume >= 1e9) return `${(volume / 1e9).toFixed(2)}B`;
    if (volume >= 1e6) return `${(volume / 1e6).toFixed(2)}M`;
    if (volume >= 1e3) return `${(volume / 1e3).toFixed(2)}K`;
    return volume.toFixed(2);
  };

  return (
    <div className={cn('flex items-center gap-3', className)}>
      <div className={cn('font-bold tabular-nums', sizeClasses[size])}>
        ${formatPrice(priceData.price)}
      </div>
      
      {showChange && (
        <div className={cn('flex items-center gap-1 tabular-nums', changeColor)}>
          {isPositive ? (
            <ArrowUp size={16} weight="bold" />
          ) : (
            <ArrowDown size={16} weight="bold" />
          )}
          <span className="text-sm font-medium">
            {Math.abs(priceData.changePercent24h).toFixed(2)}%
          </span>
        </div>
      )}

      {showVolume && (
        <div className="text-sm text-muted-foreground tabular-nums">
          Vol: {formatVolume(priceData.volume24h)}
        </div>
      )}
    </div>
  );
}
