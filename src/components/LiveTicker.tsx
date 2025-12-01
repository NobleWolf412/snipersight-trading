import { useMultiplePrices } from '@/hooks/usePriceData';
import { ArrowUp, ArrowDown } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { memo, useState, useEffect, useRef } from 'react';

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

import { formatPrice } from '@/utils/formatters';

const TickerItem = memo(({ symbol, price, changePercent24h }: { symbol: string; price?: number; changePercent24h?: number }) => {
  const [flash, setFlash] = useState<'up' | 'down' | null>(null);
  const prevPriceRef = useRef(price);

  useEffect(() => {
    if (price !== undefined && prevPriceRef.current !== undefined && price !== prevPriceRef.current) {
      setFlash(price > prevPriceRef.current ? 'up' : 'down');
      const timer = setTimeout(() => setFlash(null), 300);
      prevPriceRef.current = price;
      return () => clearTimeout(timer);
    }
    prevPriceRef.current = price;
  }, [price]);

  if (!price || !symbol) {
    return (
      <div className="flex items-center gap-3 px-6 min-w-[220px]">
        <div className="text-sm font-bold text-muted-foreground">{symbol?.split('/')[0] || 'Loading...'}</div>
        <div className="h-4 w-20 bg-muted/30 animate-pulse rounded" />
      </div>
    );
  }

  const isPositive = (changePercent24h ?? 0) >= 0;
  const changeColor = isPositive ? 'text-success' : 'text-destructive';

  return (
    <div className="flex items-center gap-3 px-6 min-w-[220px] border-r border-border/30">
      <div className="text-sm font-bold text-foreground">
        {symbol.split('/')[0]}
      </div>
      <div className={cn(
        'text-sm font-bold tabular-nums transition-colors duration-300',
        flash === 'up' && 'text-success',
        flash === 'down' && 'text-destructive'
      )}>
        ${formatPrice(price)}
      </div>
      <div className={cn('flex items-center gap-1 text-xs font-medium tabular-nums', changeColor)}>
        {isPositive ? (
          <ArrowUp size={12} weight="bold" />
        ) : (
          <ArrowDown size={12} weight="bold" />
        )}
        {Math.abs(changePercent24h ?? 0).toFixed(2)}%
      </div>
    </div>
  );
});

TickerItem.displayName = 'TickerItem';

export const LiveTicker = memo(({ symbols = DEFAULT_SYMBOLS, className }: LiveTickerProps) => {
  const { prices } = useMultiplePrices(symbols);

  return (
    <div className={cn('bg-card/50 border-y border-border/50 overflow-hidden relative', className)}>
      <div className="absolute left-0 top-0 bottom-0 w-20 bg-gradient-to-r from-card/50 to-transparent z-10 pointer-events-none" />
      <div className="absolute right-0 top-0 bottom-0 w-20 bg-gradient-to-l from-card/50 to-transparent z-10 pointer-events-none" />
      
      <div className="flex animate-scroll-left py-3 will-change-transform">
        {symbols.map((symbol) => {
          const priceData = prices.get(symbol);
          return (
            <TickerItem
              key={symbol}
              symbol={symbol}
              price={priceData?.price}
              changePercent24h={priceData?.changePercent24h}
            />
          );
        })}
        {symbols.map((symbol) => {
          const priceData = prices.get(symbol);
          return (
            <TickerItem
              key={`${symbol}-duplicate`}
              symbol={symbol}
              price={priceData?.price}
              changePercent24h={priceData?.changePercent24h}
            />
          );
        })}
      </div>
    </div>
  );
});

LiveTicker.displayName = 'LiveTicker';
