import { useEffect, useState } from 'react';
import { usePrice } from '@/hooks/usePriceData';
import { priceService } from '@/services/priceService';
import { ArrowUp, ArrowDown } from '@phosphor-icons/react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatPrice } from '@/utils/formatters';

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
  const { priceData, isLoading, error } = usePrice(symbol);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

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

  // Check if we're in backoff state (price fetch failed and waiting to retry)
  const backoff = priceService.getBackoff(symbol);
  
  if (!priceData) {
    // Show backoff indicator if fetch failed, otherwise generic "No data"
    if (backoff) {
      const eta = Math.max(0, Math.ceil((backoff.next - now) / 1000));
      return (
        <div className={cn('flex items-center gap-2', className)}>
          <span className={cn('text-muted-foreground', sizeClasses[size])}>--</span>
          <span className="text-[10px] px-2 py-1 rounded bg-warning/20 border border-warning/40 text-warning font-mono">
            RETRY {eta}s
          </span>
        </div>
      );
    }
    return (
      <div className={cn('text-muted-foreground', sizeClasses[size], className)}>
        {error ? 'Fetch error' : 'No data'}
      </div>
    );
  }

  const isPositive = priceData.changePercent24h >= 0;
  const changeColor = isPositive ? 'text-success' : 'text-destructive';

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
      {/* Stale/backoff badges */}
      {(() => {
        const backoff = priceService.getBackoff(symbol);
        const ageMs = now - priceData.timestamp;
        const stale = ageMs > 10000; // >10s old
        if (backoff) {
          const eta = Math.max(0, Math.ceil((backoff.next - now) / 1000));
          return (
            <span className="text-[10px] px-2 py-1 rounded bg-warning/20 border border-warning/40 text-warning font-mono">
              RETRY {eta}s
            </span>
          );
        }
        if (stale) {
          return (
            <span className="text-[10px] px-2 py-1 rounded bg-destructive/15 border border-destructive/40 text-destructive font-mono">
              STALE {Math.floor(ageMs/1000)}s
            </span>
          );
        }
        return null;
      })()}
    </div>
  );
}
