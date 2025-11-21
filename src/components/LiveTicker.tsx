import { useMultiplePrices } from '@/hooks/usePriceData';
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
  'BNB/USDT',
  'XRP/USDT',
  'ADA/USDT',
  'DOGE/USDT',
  'MATIC/USDT',
  'DOT/USDT',
  'AVAX/USDT',
  'LINK/USDT',
  'UNI/USDT',
  'ATOM/USDT',
  'LTC/USDT',
  'APT/USDT',
  'ARB/USDT',
  'OP/USDT',
  'NEAR/USDT',
  'IMX/USDT',
  'FIL/USDT',
];

export function LiveTicker({ symbols = DEFAULT_SYMBOLS, className }: LiveTickerProps) {
  const { prices, isLoading } = useMultiplePrices(symbols);

  const formatPrice = (price: number) => {
    if (price >= 1000) return price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (price >= 1) return price.toFixed(4);
    return price.toFixed(6);
  };

  const renderTickerItem = (symbol: string, index: number) => {
    const priceData = prices.get(symbol);
    if (!priceData) {
      return (
        <div key={`${symbol}-${index}`} className="flex items-center gap-3 px-6 min-w-[220px]">
          <div className="text-sm font-bold text-muted-foreground">{symbol.split('/')[0]}</div>
          <div className="h-4 w-20 bg-muted/30 animate-pulse rounded" />
        </div>
      );
    }

    const isPositive = priceData.changePercent24h >= 0;
    const changeColor = isPositive ? 'text-success' : 'text-destructive';

    return (
      <div key={`${symbol}-${index}`} className="flex items-center gap-3 px-6 min-w-[220px] border-r border-border/30">
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
  };

  return (
    <div className={cn('bg-card/50 border-y border-border/50 overflow-hidden relative', className)}>
      <div className="absolute left-0 top-0 bottom-0 w-20 bg-gradient-to-r from-card/50 to-transparent z-10 pointer-events-none" />
      <div className="absolute right-0 top-0 bottom-0 w-20 bg-gradient-to-l from-card/50 to-transparent z-10 pointer-events-none" />
      
      <div className="flex animate-scroll-left py-3">
        {symbols.map((symbol, idx) => renderTickerItem(symbol, idx))}
        {symbols.map((symbol, idx) => renderTickerItem(symbol, idx + symbols.length))}
      </div>
    </div>
  );
}
