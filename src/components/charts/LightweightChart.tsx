import { useRef, useEffect, useCallback, useState } from 'react';
import { createChart, ColorType, CrosshairMode, CandlestickSeries } from 'lightweight-charts';
import type { IChartApi, ISeriesApi, CandlestickData, Time, SeriesMarker } from 'lightweight-charts';
import { api } from '@/utils/api';
import { cn } from '@/lib/utils';

interface OrderBlock {
    price_high: number;
    price_low: number;
    timestamp: number;
    type: 'bullish' | 'bearish';
    mitigated?: boolean;
}

interface LightweightChartProps {
    symbol: string;
    timeframe?: string;
    orderBlocks?: OrderBlock[];
    entryPrice?: number;
    stopLoss?: number;
    takeProfit?: number;
    className?: string;
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
}: LightweightChartProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
    const zoneSeriesRefs = useRef<ISeriesApi<'Baseline'>[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [data, setData] = useState<CandlestickData[]>([]);

    // Fetch candle data with comprehensive error handling
    const fetchData = useCallback(async () => {
        try {
            setIsLoading(true);
            setError(null);

            const apiResponse = await api.getCandles(symbol, timeframe, 200);

            // Enhanced error handling from API response
            if (apiResponse.error) {
                // Handle structured error responses from backend
                const errorDetail = apiResponse.error;
                let errorMessage = 'Failed to load chart data';

                if (typeof errorDetail === 'object' && errorDetail.message) {
                    errorMessage = errorDetail.message;

                    // Add helpful suggestions
                    if (errorDetail.suggestion) {
                        errorMessage += `\n\n${errorDetail.suggestion}`;
                    }

                    // Log detailed troubleshooting info for debugging
                    if (errorDetail.troubleshooting) {
                        console.warn('[Chart Debug Info]', errorDetail.troubleshooting);
                    }
                } else if (typeof errorDetail === 'string') {
                    errorMessage = errorDetail;
                }

                throw new Error(errorMessage);
            }

            // Handle both direct array and object with candles property
            const responseData = apiResponse.data || apiResponse;
            const candles = Array.isArray(responseData) ? responseData : (responseData?.candles || []);

            // Graceful handling of empty data
            if (!candles || candles.length === 0) {
                const suggestions = [
                    `Symbol: ${symbol} | Timeframe: ${timeframe}`,
                    '',
                    'Possible solutions:',
                    '• Run a scanner to populate the cache',
                    '• Check if this symbol is available on the exchange',
                    '• Try a different timeframe or symbol'
                ].join('\n');

                throw new Error(`No candle data available\n\n${suggestions}`);
            }

            // Convert candles to chart format
            const candleData: CandlestickData[] = candles.map((candle) => ({
                time: (new Date(candle.timestamp).getTime() / 1000) as Time,
                open: candle.open,
                high: candle.high,
                low: candle.low,
                close: candle.close,
            }));

            // Log success with data source info
            const source = responseData?.source || 'unknown';
            const marketType = responseData?.market_type;
            console.log(`✓ Loaded ${candleData.length} candles from ${source}${marketType ? ` (${marketType})` : ''}`);

            setData(candleData);
        } catch (err: any) {
            console.error('Failed to fetch candle data:', err);

            // Extract user-friendly error message
            let userMessage = 'Failed to load chart data';
            if (err.message) {
                userMessage = err.message;
            } else if (typeof err === 'string') {
                userMessage = err;
            }

            setError(userMessage);
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

        const candleSeries = chart.addCandlestickSeries({
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
            // Bullish: Cyan Blue, Bearish: Neon Orange
            const fillColor = isBullish ? 'rgba(6, 182, 212, 0.2)' : 'rgba(255, 138, 0, 0.2)';
            const lineColor = isBullish ? '#06b6d4' : '#ff8a00';

            // Create baseline series for shaded zone
            const zoneSeries = chart.addBaselineSeries({
                baseValue: { type: 'price', price: ob.price_low },
                topLineColor: 'transparent',
                topFillColor1: fillColor,
                topFillColor2: fillColor,
                bottomLineColor: 'transparent',
                bottomFillColor1: fillColor,
                bottomFillColor2: fillColor,
                lineWidth: 0,
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
            candleSeries.createPriceLine({
                price: ob.price_high,
                color: lineColor,
                lineWidth: 2,
                lineStyle: 0, // Solid
                axisLabelVisible: true,
                title: `${isBullish ? '🔵' : '🟠'} OB${index + 1} Top`,
            });

            candleSeries.createPriceLine({
                price: ob.price_low,
                color: lineColor,
                lineWidth: 1,
                lineStyle: 2, // Dashed
                axisLabelVisible: true,
                title: `${isBullish ? '🔵' : '🟠'} OB${index + 1} Bot`,
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
                    <div className="flex flex-col items-center gap-3 max-w-lg px-6 py-4">
                        <div className="text-3xl">📊</div>
                        <div className="text-sm text-red-400 text-left font-mono whitespace-pre-line max-h-64 overflow-y-auto border border-red-400/30 rounded p-3 bg-red-400/5 w-full">
                            {error}
                        </div>
                        <button
                            onClick={fetchData}
                            className="px-4 py-2 bg-[#00ff88]/10 hover:bg-[#00ff88]/20 border border-[#00ff88]/30 rounded text-sm text-[#00ff88] font-mono transition-colors"
                        >
                            Retry
                        </button>
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

            <div ref={containerRef} className="w-full h-full" />
        </div>
    );
}
