/**
 * BTCPricePill - Live BTC price display for TopBar
 * Fetches from Binance public API for reliable 24/7 data
 */

import { useState, useEffect } from 'react';
import { TrendUp, TrendDown } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

interface PriceData {
    price: number;
    change24h: number;
    timestamp: number;
}

export function BTCPricePill() {
    const [priceData, setPriceData] = useState<PriceData | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const fetchPrice = async () => {
            try {
                // Use local proxy to avoid CORS issues
                const response = await fetch('/api/market/btc-ticker');
                if (response.ok) {
                    const data = await response.json();
                    setPriceData({
                        price: parseFloat(data.lastPrice),
                        change24h: parseFloat(data.priceChangePercent),
                        timestamp: Date.now()
                    });
                }
            } catch (err) {
                console.error('Failed to fetch BTC price:', err);
            } finally {
                setIsLoading(false);
            }
        };

        fetchPrice();
        // Refresh every 30 seconds
        const interval = setInterval(fetchPrice, 30000);
        return () => clearInterval(interval);
    }, []);

    if (isLoading) {
        return (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-black/40 border border-white/10">
                <div className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                <span className="text-xs text-muted-foreground font-mono">...</span>
            </div>
        );
    }

    if (!priceData || priceData.price === 0) {
        return null;
    }

    const isPositive = priceData.change24h >= 0;
    const formattedPrice = new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(priceData.price);

    return (
        <div className={cn(
            "flex items-center gap-2 px-3 py-1.5 rounded-full border transition-all",
            isPositive
                ? "bg-emerald-500/10 border-emerald-500/30 shadow-[0_0_10px_rgba(16,185,129,0.15)]"
                : "bg-red-500/10 border-red-500/30 shadow-[0_0_10px_rgba(239,68,68,0.15)]"
        )}>
            {/* BTC icon */}
            <span className="text-xs font-bold text-amber-400">₿</span>

            {/* Price */}
            <span className="text-sm font-mono font-semibold text-foreground">
                {formattedPrice}
            </span>

            {/* Change indicator */}
            <div className={cn(
                "flex items-center gap-0.5 text-xs font-medium",
                isPositive ? "text-emerald-400" : "text-red-400"
            )}>
                {isPositive ? (
                    <TrendUp size={12} weight="bold" />
                ) : (
                    <TrendDown size={12} weight="bold" />
                )}
                <span>{isPositive ? '+' : ''}{priceData.change24h.toFixed(1)}%</span>
            </div>
        </div>
    );
}
