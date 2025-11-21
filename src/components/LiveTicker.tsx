import { useMultiplePrices } from '@/hooks/usePriceData';
import { Card, CardContent } from '@/components/ui/card';
import { ArrowUp, ArrowDown } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

interface LiveTickerProps {
  symbols?: string[];
  className?: string;
}

const DEFAULT_SYMBOLS = [
  'BTC/USDT',
  'ETH/USDT',
  'SOL/USDT',
  'MATIC/USDT',
  'AVAX/USDT',
  'LINK/USDT',
];

export function LiveTicker({ symbols = DEFAULT_SYMBOLS, className }: LiveTickerProps) {
  const { prices, isLoading } = useMultiplePrices(symbols);

  const formatPrice = (price: number) => {
    if (price >= 1000) return price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (price >= 1) return price.toFixed(4);
    return price.toFixed(6);
  };

  if (isLoading) {
    return (
      <Card className={cn('bg-card/50 border-border/50', className)}>
        <CardContent className="p-4">
          <div className="flex items-center gap-6 overflow-x-auto">
            {symbols.map((symbol) => (
              <div key={symbol} className="flex items-center gap-2 min-w-[160px]">
                <div className="text-sm font-bold text-muted-foreground">{symbol.split('/')[0]}</div>
                <div className="h-4 w-20 bg-muted animate-pulse rounded" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn('bg-card/50 border-border/50', className)}>
      <CardContent className="p-4">
        <div className="flex items-center gap-6 overflow-x-auto scrollbar-hide">
          {symbols.map((symbol) => {
            const priceData = prices.get(symbol);
            if (!priceData) return null;

            const isPositive = priceData.changePercent24h >= 0;
            const changeColor = isPositive ? 'text-success' : 'text-destructive';

            return (
              <div key={symbol} className="flex items-center gap-3 min-w-[200px]">
                <div className="text-sm font-bold text-foreground">
                  {symbol.split('/')[0]}
                </div>
                <div className="text-sm font-bold tabular-nums">
                  ${formatPrice(priceData.price)}
                </div>
                <div className={cn('flex items-center gap-1 text-xs font-medium tabular-nums', changeColor)}>
                  {isPositive ? (
                    <ArrowUp size={12} weight="bold" />
                  ) : (
                    <ArrowDown size={12} weight="bold" />
                  )}
                  {Math.abs(priceData.changePercent24h).toFixed(2)}%
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
