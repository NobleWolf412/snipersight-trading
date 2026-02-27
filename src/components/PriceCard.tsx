import { usePrice } from '@/hooks/usePriceData';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ArrowUp, ArrowDown, TrendUp, TrendDown } from '@phosphor-icons/react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

interface PriceCardProps {
  symbol: string;
  className?: string;
}

import { formatPrice, formatVolume } from '@/utils/formatters';

export function PriceCard({ symbol, className }: PriceCardProps) {
  const { priceData, isLoading } = usePrice(symbol);

  if (isLoading) {
    return (
      <Card className={cn('bg-card/50 border-border/50', className)}>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-6 w-24" />
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-10 w-40" />
          <div className="grid grid-cols-2 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="space-y-1">
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-5 w-24" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!priceData) {
    return (
      <Card className={cn('bg-card/50 border-border/50', className)}>
        <CardContent className="p-6 text-center text-muted-foreground">
          No price data available
        </CardContent>
      </Card>
    );
  }

  const isPositive = priceData.changePercent24h >= 0;
  const changeColor = isPositive ? 'text-success' : 'text-destructive';
  const bgColor = isPositive ? 'bg-success/10' : 'bg-destructive/10';
  const borderColor = isPositive ? 'border-success/30' : 'border-destructive/30';

  return (
    <Card className={cn('bg-card/50 border-border/50', className)}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold">{symbol.split('/')[0]}</span>
            <span className="text-sm text-muted-foreground font-normal">
              /{symbol.split('/')[1]}
            </span>
          </div>
          <div className={cn('flex items-center gap-1 px-3 py-1 rounded-full', bgColor, borderColor, 'border')}>
            {isPositive ? (
              <TrendUp size={16} weight="bold" className={changeColor} />
            ) : (
              <TrendDown size={16} weight="bold" className={changeColor} />
            )}
            <span className={cn('text-sm font-bold tabular-nums', changeColor)}>
              {isPositive ? '+' : ''}{priceData.changePercent24h.toFixed(2)}%
            </span>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1">
          <div className="text-3xl font-bold tabular-nums">
            ${formatPrice(priceData.price)}
          </div>
          <div className={cn('flex items-center gap-1 text-sm font-medium tabular-nums', changeColor)}>
            {isPositive ? (
              <ArrowUp size={14} weight="bold" />
            ) : (
              <ArrowDown size={14} weight="bold" />
            )}
            ${Math.abs(priceData.change24h).toFixed(2)}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 pt-4 border-t border-border/50">
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground uppercase tracking-wide">
              24H High
            </div>
            <div className="text-sm font-bold tabular-nums">
              ${formatPrice(priceData.high24h)}
            </div>
          </div>
          
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground uppercase tracking-wide">
              24H Low
            </div>
            <div className="text-sm font-bold tabular-nums">
              ${formatPrice(priceData.low24h)}
            </div>
          </div>
          
          <div className="space-y-1 col-span-2">
            <div className="text-xs text-muted-foreground uppercase tracking-wide">
              24H Volume
            </div>
            <div className="text-sm font-bold tabular-nums">
              {formatVolume(priceData.volume24h)}
            </div>
          </div>

          <div className="space-y-1 col-span-2">
            <div className="text-xs text-muted-foreground uppercase tracking-wide">
              Exchange
            </div>
            <div className="text-sm font-medium">
              {priceData.exchange}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
