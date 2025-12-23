import { useRef, useEffect, useCallback, useState } from 'react';
import { createChart, ColorType, CrosshairMode, CandlestickSeries, BaselineSeries } from 'lightweight-charts';
import type { IChartApi, ISeriesApi, CandlestickData, Time, SeriesMarker } from 'lightweight-charts';
import { api } from '@/utils/api';
import { cn } from '@/lib/utils';
import { TimeframeLegend, TIMEFRAME_COLORS } from './TimeframeLegend';

interface OrderBlock {
    price_high: number;
    price_low: number;
    timestamp: number;
    type: 'bullish' | 'bearish';
    mitigated?: boolean;
    timeframe?: string; // Optional: for color-coding in overlay mode
}

interface LightweightChartProps {
    symbol: string;
    timeframe?: string;
    orderBlocks?: OrderBlock[];
    entryPrice?: number;
    stopLoss?: number;
    takeProfit?: number;
    className?: string;
    title?: string; // Optional chart title
    showLegend?: boolean; // Show timeframe legend if OBs have timeframe property
}

interface CandleResponse {
    symbol: string;
    timeframe: string;
    candles: Array<{
        timestamp: string;
        open: number;
        high: number;
        low: number;
        close: number;
        volume: number;
    }>;
}

export function LightweightChart({
    symbol,
    timeframe = '15m',
    orderBlocks = [],
    entryPrice,
    stopLoss,
    takeProfit,
    className = '',
    title,
    showLegend = false,
}: LightweightChartProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
    const zoneSeriesRefs = useRef<ISeriesApi<'Baseline'>[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [data, setData] = useState<CandlestickData[]>([]);

    // Helper to determine candle limit based on timeframe
    const getLimitForTimeframe = (tf: string): number => {
        switch (tf.toLowerCase()) {
            case '1w': return 150;
            case '1d': return 300;
            case '4h': return 500;
            case '1h': return 600;
            case '15m': return 700;
            case '5m': return 700;
            case '1m': return 300;
            default: return 300;
        }
    };

    // Fetch candle data
    const fetchData = useCallback(async () => {
        try {
            setIsLoading(true);
            setError(null);

            const limit = getLimitForTimeframe(timeframe);
            const response = await api.getCandles(symbol, timeframe, limit);

            // Handle direct array, object with candles, OR wrapped data object
            const candles = Array.isArray(response)
                ? response
                : ((response as any)?.candles || (response as any)?.data?.candles || []);

            if (!candles || candles.length === 0) {
                throw new Error('No candle data available');
            }

            const candleData: CandlestickData[] = candles.map((candle: any) => {
                try {
                    const timestamp = new Date(candle.timestamp).getTime() / 1000;
                    if (isNaN(timestamp)) {
                        return null;
                    }
                    return {
                        time: timestamp as Time,
                        open: candle.open,
                        high: candle.high,
                        low: candle.low,
                        close: candle.close,
                    };
                } catch (e) {
                    return null;
                }
            }).filter((c: any) => c !== null) as CandlestickData[];

            if (candleData.length === 0) {
                throw new Error('Failed to parse any valid candles');
            }

            if (candleData.length === 0) {
                throw new Error('Failed to parse any valid candles');
            }

            setData(candleData);
        } catch (err: any) {
            console.error('Failed to fetch candle data:', err);
            setError(err.message || 'Failed to load chart data');
        } finally {
            setIsLoading(false);
        }
    }, [symbol, timeframe]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    // Initialize chart
    useEffect(() => {
        if (!containerRef.current || data.length === 0) return;

        const chart = createChart(containerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: '#0a0f0a' },
                textColor: '#00ff88',
            },
            grid: {
                vertLines: { color: 'rgba(0, 255, 136, 0.1)' },
                horzLines: { color: 'rgba(0, 255, 136, 0.1)' },
            },
            crosshair: {
                mode: CrosshairMode.Normal,
                vertLine: {
                    color: '#00ff88',
                    width: 1,
                    style: 2,
                    labelBackgroundColor: '#00ff88',
                },
                horzLine: {
                    color: '#00ff88',
                    width: 1,
                    style: 2,
                    labelBackgroundColor: '#00ff88',
                },
            },
            rightPriceScale: {
                borderColor: 'rgba(0, 255, 136, 0.3)',
            },
            timeScale: {
                borderColor: 'rgba(0, 255, 136, 0.3)',
                timeVisible: true,
                secondsVisible: false,
            },
            width: containerRef.current.clientWidth,
            height: containerRef.current.clientHeight,
        });

        const candleSeries = chart.addSeries(CandlestickSeries, {
            upColor: '#00ff88',
            downColor: '#ff4444',
            borderUpColor: '#00ff88',
            borderDownColor: '#ff4444',
            wickUpColor: '#00ff88',
            wickDownColor: '#ff4444',
        });

        candleSeries.setData(data);
        chart.timeScale().fitContent();

        chartRef.current = chart;
        candleSeriesRef.current = candleSeries;

        // Handle resize
        const handleResize = () => {
            if (containerRef.current) {
                chart.applyOptions({
                    width: containerRef.current.clientWidth,
                    height: containerRef.current.clientHeight,
                });
            }
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
            chartRef.current = null;
            candleSeriesRef.current = null;
        };
    }, [data]);

    // Draw order blocks as SHADED ZONES and price levels
    useEffect(() => {
        if (!chartRef.current || !candleSeriesRef.current || data.length === 0) return;

        const chart = chartRef.current;
        const candleSeries = candleSeriesRef.current;

        // Clear previous zone series
        zoneSeriesRefs.current.forEach(series => chart.removeSeries(series));
        zoneSeriesRefs.current = [];

        // Create shaded zones for each order block
        orderBlocks.forEach((ob, index) => {
            const isBullish = ob.type === 'bullish';

            // Use timeframe-specific color if available, otherwise default bull/bear colors
            let fillColor: string;
            let lineColor: string;

            if (ob.timeframe && TIMEFRAME_COLORS[ob.timeframe]) {
                // Timeframe-specific color (for overlay mode)
                const tfColor = TIMEFRAME_COLORS[ob.timeframe].color;
                fillColor = tfColor.replace('rgb', 'rgba').replace(')', ', 0.2)');
                lineColor = tfColor;
            } else {
                // Default: Bullish = Cyan Blue, Bearish = Neon Orange
                fillColor = isBullish ? 'rgba(6, 182, 212, 0.2)' : 'rgba(255, 138, 0, 0.2)';
                lineColor = isBullish ? '#06b6d4' : '#ff8a00';
            }

            // Create baseline series for shaded zone
            const zoneSeries = chart.addSeries(BaselineSeries, {
                baseValue: { type: 'price', price: ob.price_low },
                topLineColor: 'transparent',
                topFillColor1: fillColor,
                topFillColor2: fillColor,
                bottomLineColor: 'transparent',
                bottomFillColor1: fillColor,
                bottomFillColor2: fillColor,
                lineWidth: 1,
                priceLineVisible: false,
                lastValueVisible: false,
            });

            // Fill the zone across the entire chart
            const zoneData = data.map(candle => ({
                time: candle.time,
                value: ob.price_high,
            }));

            zoneSeries.setData(zoneData);
            zoneSeriesRefs.current.push(zoneSeries);

            // Add boundary lines with labels
            const tfLabel = ob.timeframe ? ` (${ob.timeframe.toUpperCase()})` : '';
            const emoji = ob.timeframe ? '' : (isBullish ? '🔵' : '🟠');

            candleSeries.createPriceLine({
                price: ob.price_high,
                color: lineColor,
                lineWidth: 2,
                lineStyle: 0, // Solid
                axisLabelVisible: true,
                title: `${emoji} OB${index + 1}${tfLabel} Top`,
            });

            candleSeries.createPriceLine({
                price: ob.price_low,
                color: lineColor,
                lineWidth: 1,
                lineStyle: 2, // Dashed
                axisLabelVisible: true,
                title: `${emoji} OB${index + 1}${tfLabel} Bot`,
            });
        });

        // Always show entry/SL/TP lines (important trade levels)
        if (entryPrice) {
            candleSeries.createPriceLine({
                price: entryPrice,
                color: '#00ff88',
                lineWidth: 2,
                lineStyle: 0,
                axisLabelVisible: true,
                title: 'ENTRY',
            });
        }

        if (stopLoss) {
            candleSeries.createPriceLine({
                price: stopLoss,
                color: '#ff4444',
                lineWidth: 2,
                lineStyle: 0,
                axisLabelVisible: true,
                title: 'STOP',
            });
        }

        if (takeProfit) {
            candleSeries.createPriceLine({
                price: takeProfit,
                color: '#00ff88',
                lineWidth: 2,
                lineStyle: 0,
                axisLabelVisible: true,
                title: 'TP',
            });
        }
    }, [orderBlocks, entryPrice, stopLoss, takeProfit, data]);

    return (
        <div className={cn('relative w-full h-full bg-[#0a0f0a] rounded-lg overflow-hidden', className)}>
            {isLoading && (
                <div className="absolute inset-0 flex items-center justify-center bg-[#0a0f0a]/90 z-20">
                    <div className="flex flex-col items-center gap-3">
                        <div className="w-8 h-8 border-2 border-[#00ff88] border-t-transparent rounded-full animate-spin" />
                        <span className="text-sm text-[#00ff88]/70 font-mono">Loading chart...</span>
                    </div>
                </div>
            )}

            {error && (
                <div className="absolute inset-0 flex items-center justify-center bg-[#0a0f0a]/90 z-20">
                    <div className="flex flex-col items-center gap-3 max-w-md px-4">
                        <div className="text-2xl">📊</div>
                        <p className="text-sm text-red-400 text-center font-mono">{error}</p>
                        <button
                            onClick={fetchData}
                            className="px-4 py-2 bg-[#00ff88]/10 hover:bg-[#00ff88]/20 border border-[#00ff88]/30 rounded text-sm text-[#00ff88] font-mono transition-colors"
                        >
                            Retry
                        </button>
                    </div>
                </div>
            )}


            {/* Optional Chart Title */}
            {title && (
                <div className="absolute top-2 left-1/2 -translate-x-1/2 z-30">
                    <div className="px-4 py-1.5 rounded bg-black/70 backdrop-blur-sm border border-[#00ff88]/30">
                        <span className="text-sm font-mono font-bold text-[#00ff88]">{title}</span>
                    </div>
                </div>
            )}

            {/* Symbol and Timeframe badges */}
            <div className="absolute top-2 left-2 flex items-center gap-2 z-30">
                <div className="px-3 py-1.5 rounded bg-black/70 backdrop-blur-sm border border-[#00ff88]/40">
                    <span className="text-sm font-mono font-bold text-[#00ff88]">{symbol}</span>
                </div>
                <div className="px-3 py-1.5 rounded bg-[#00ff88]/10 backdrop-blur-sm border border-[#00ff88]/30">
                    <span className="text-sm font-mono font-bold text-[#00ff88]">{timeframe}</span>
                </div>
            </div>

            {/* Timeframe Legend (for overlay mode) */}
            {showLegend && orderBlocks.some(ob => ob.timeframe) && (
                <div className="absolute bottom-2 left-2 right-2 z-30">
                    <div className="px-3 py-2 rounded bg-black/70 backdrop-blur-sm border border-[#00ff88]/20">
                        <TimeframeLegend
                            timeframes={Array.from(new Set(orderBlocks.map(ob => ob.timeframe).filter(Boolean))).map(tf => ({
                                tf: tf!,
                                color: TIMEFRAME_COLORS[tf!]?.color || '#888',
                            }))}
                        />
                    </div>
                </div>
            )}

            <div ref={containerRef} className="w-full h-full" />
        </div>
    );
}
