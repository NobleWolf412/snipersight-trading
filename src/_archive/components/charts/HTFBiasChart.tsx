/**
 * HTF Bias Chart - ECharts-based visualization with layered heatmap overlays
 * 
 * Layers (bottom to top):
 * 1. Candlesticks (base)
 * 2. Volume Profile (right-side heatmap strip)
 * 3. OB Heat Zones (gradient opacity)
 * 4. Liquidity Zones (EQH/EQL bands)
 * 5. Annotations (Entry/SL/TP lines)
 */

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import { api } from '@/utils/api';
import { cn } from '@/lib/utils';
import { ChartLineUp, Fire, Drop, Stack } from '@phosphor-icons/react';

interface OrderBlock {
    price_high: number;
    price_low: number;
    timestamp: number;
    type: 'bullish' | 'bearish';
    mitigated?: boolean;
    timeframe?: string;
    freshness_score?: number;       // 0-1
    displacement_strength?: number;  // 0-1
    mitigation_level?: number;       // 0-1
}

interface LiquidityZone {
    type: 'EQH' | 'EQL';
    priceLevel: number;
    strength: number; // 0-1
}

interface VolumeAtPrice {
    priceLevel: number;
    volume: number;
    normalized: number; // 0-1 for color intensity
}

interface HTFBiasChartProps {
    symbol: string;
    timeframe?: string;
    orderBlocks?: OrderBlock[];
    liquidityZones?: LiquidityZone[];
    entryPrice?: number;
    stopLoss?: number;
    takeProfit?: number;
    className?: string;
    title?: string;
}

// Calculate volume profile from OHLCV data
function calculateVolumeProfile(candles: any[], buckets: number = 30): VolumeAtPrice[] {
    if (!candles || candles.length === 0) return [];

    // Find price range
    const highs = candles.map(c => c.high);
    const lows = candles.map(c => c.low);
    const maxPrice = Math.max(...highs);
    const minPrice = Math.min(...lows);
    const range = maxPrice - minPrice;
    const bucketSize = range / buckets;

    // Initialize buckets
    const volumeMap: Map<number, number> = new Map();
    for (let i = 0; i < buckets; i++) {
        const price = minPrice + (i + 0.5) * bucketSize;
        volumeMap.set(price, 0);
    }

    // Distribute volume across price levels
    candles.forEach(candle => {
        const candleRange = candle.high - candle.low || 0.0001;
        const volumePerPrice = candle.volume / Math.max(1, Math.ceil(candleRange / bucketSize));

        for (let price = candle.low; price <= candle.high; price += bucketSize) {
            const bucketPrice = minPrice + Math.floor((price - minPrice) / bucketSize) * bucketSize + bucketSize / 2;
            const existing = volumeMap.get(bucketPrice) || 0;
            volumeMap.set(bucketPrice, existing + volumePerPrice);
        }
    });

    // Normalize volumes
    const volumes = Array.from(volumeMap.values());
    const maxVol = Math.max(...volumes, 1);

    return Array.from(volumeMap.entries()).map(([priceLevel, volume]) => ({
        priceLevel,
        volume,
        normalized: volume / maxVol
    }));
}

// Color utilities
const COLORS = {
    // Candlesticks (subdued to not compete with overlays)
    candleUp: '#22c55e',
    candleDown: '#ef4444',
    // OB zones
    obBullish: 'rgba(34, 197, 94, 0.35)',
    obBullishMitigated: 'rgba(34, 197, 94, 0.08)',
    obBearish: 'rgba(239, 68, 68, 0.35)',
    obBearishMitigated: 'rgba(239, 68, 68, 0.08)',
    // Volume profile
    volumeHigh: '#f59e0b',
    volumeLow: '#1f2937',
    // Liquidity
    eqhZone: 'rgba(168, 85, 247, 0.25)',
    eqlZone: 'rgba(168, 85, 247, 0.25)',
    // Lines
    entry: '#00ff88',
    stopLoss: '#ff4444',
    takeProfit: '#00ff88',
    // Background
    background: '#0a0f0a',
    grid: 'rgba(0, 255, 136, 0.08)'
};

export function HTFBiasChart({
    symbol,
    timeframe = '1d',
    orderBlocks = [],
    liquidityZones = [],
    entryPrice,
    stopLoss,
    takeProfit,
    className = '',
    title
}: HTFBiasChartProps) {
    const [candles, setCandles] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Layer visibility toggles
    // NOTE: Volume profile disabled by default due to React Strict Mode + multi-grid ECharts issues
    const [showVolume, setShowVolume] = useState(false);
    const [showOBZones, setShowOBZones] = useState(true);
    const [showLiquidity, setShowLiquidity] = useState(true);

    // Fetch candle data
    const fetchData = useCallback(async () => {
        try {
            setCandles([]);
            setIsLoading(true);
            setError(null);

            const limit = timeframe === '1w' || timeframe === '1d' ? 200 : 500;
            const response = await api.getCandles(symbol, timeframe, limit);

            const candleData = Array.isArray(response)
                ? response
                : ((response as any)?.candles || (response as any)?.data?.candles || []);

            if (!candleData || candleData.length === 0) {
                throw new Error('No candle data available');
            }

            // Sort and dedupe
            const sortedData = candleData
                .map((c: any) => ({
                    ...c,
                    time: new Date(c.timestamp).getTime()
                }))
                .sort((a: any, b: any) => a.time - b.time)
                .filter((c: any, i: number, arr: any[]) => i === 0 || c.time > arr[i - 1].time);

            setCandles(sortedData);
        } catch (err: any) {
            setError(err.message || 'Failed to load chart');
        } finally {
            setIsLoading(false);
        }
    }, [symbol, timeframe]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    // Calculate volume profile
    const volumeProfile = useMemo(() => {
        if (!showVolume || candles.length === 0) return [];
        return calculateVolumeProfile(candles, 40);
    }, [candles, showVolume]);

    // Build ECharts option
    const chartOption = useMemo((): EChartsOption => {
        // Return a minimal valid option when no candles
        if (candles.length === 0) {
            return {
                backgroundColor: COLORS.background,
                xAxis: { type: 'category' as const, data: [] },
                yAxis: { type: 'value' as const },
                series: []
            };
        }

        // Prepare candlestick data: [open, close, low, high]
        const candleValues = candles.map(c => [c.open, c.close, c.low, c.high]);
        const categoryData = candles.map(c => {
            const d = new Date(c.time);
            return `${d.getMonth() + 1}/${d.getDate()}`;
        });

        // Price range for markArea
        const allPrices = candles.flatMap(c => [c.high, c.low]);
        const minPrice = Math.min(...allPrices);
        const maxPrice = Math.max(...allPrices);

        // Build OB zone markAreas
        const obMarkAreas: any[] = [];
        console.log('[HTFBiasChart] OB Data:', {
            showOBZones,
            orderBlocksCount: orderBlocks.length,
            orderBlocks: orderBlocks.slice(0, 3), // Log first 3
            priceRange: { minPrice, maxPrice }
        });
        if (showOBZones && orderBlocks && orderBlocks.length > 0) {
            orderBlocks.forEach(ob => {
                // Skip malformed OB entries
                if (!ob || typeof ob.price_low !== 'number' || typeof ob.price_high !== 'number') {
                    return;
                }

                const isBullish = ob.type === 'bullish';
                const freshness = ob.freshness_score ?? 0.8;
                const displacement = ob.displacement_strength ?? 0.5;
                const mitigation = ob.mitigation_level ?? 0;

                // Calculate opacity based on freshness and displacement (mitigated = faded)
                const baseOpacity = 0.25 * freshness * (1 + displacement * 0.3);
                const finalOpacity = baseOpacity * (1 - mitigation * 0.7);

                const color = isBullish
                    ? `rgba(34, 197, 94, ${finalOpacity.toFixed(2)})`
                    : `rgba(239, 68, 68, ${finalOpacity.toFixed(2)})`;

                obMarkAreas.push([
                    {
                        yAxis: ob.price_low,
                        itemStyle: { color }
                    },
                    {
                        yAxis: ob.price_high
                    }
                ]);
            });
        }

        // Build liquidity zone markAreas
        const liqMarkAreas: any[] = [];
        if (showLiquidity && liquidityZones && liquidityZones.length > 0) {
            liquidityZones.forEach(lz => {
                // Skip malformed entries
                if (!lz || typeof lz.priceLevel !== 'number') {
                    return;
                }
                const bandSize = (maxPrice - minPrice) * 0.005; // 0.5% band
                liqMarkAreas.push([
                    {
                        yAxis: lz.priceLevel - bandSize,
                        itemStyle: { color: lz.type === 'EQH' ? COLORS.eqhZone : COLORS.eqlZone }
                    },
                    {
                        yAxis: lz.priceLevel + bandSize
                    }
                ]);
            });
        }

        // Combine markAreas
        const allMarkAreas = [...obMarkAreas, ...liqMarkAreas];

        // Entry/SL/TP markLines
        const markLines: any[] = [];
        if (entryPrice) {
            markLines.push({
                yAxis: entryPrice,
                lineStyle: { color: COLORS.entry, width: 2, type: 'solid' },
                label: { formatter: 'ENTRY', position: 'end', color: COLORS.entry, fontSize: 10 }
            });
        }
        if (stopLoss) {
            markLines.push({
                yAxis: stopLoss,
                lineStyle: { color: COLORS.stopLoss, width: 2, type: 'dashed' },
                label: { formatter: 'SL', position: 'end', color: COLORS.stopLoss, fontSize: 10 }
            });
        }
        if (takeProfit) {
            markLines.push({
                yAxis: takeProfit,
                lineStyle: { color: COLORS.takeProfit, width: 2, type: 'dashed' },
                label: { formatter: 'TP', position: 'end', color: COLORS.takeProfit, fontSize: 10 }
            });
        }

        // Build volume profile as a separate heatmap-style bar series on secondary xAxis
        const volumeSeries: any[] = [];
        if (showVolume && volumeProfile.length > 0) {
            volumeSeries.push({
                type: 'bar',
                name: 'Volume Profile',
                xAxisIndex: 1,
                yAxisIndex: 1,  // Must match grid index (grid 1)
                data: volumeProfile.map(v => ({
                    value: v.normalized * 100,
                    itemStyle: {
                        color: {
                            type: 'linear',
                            x: 0, y: 0, x2: 1, y2: 0,
                            colorStops: [
                                { offset: 0, color: COLORS.volumeLow },
                                { offset: v.normalized, color: COLORS.volumeHigh },
                                { offset: 1, color: COLORS.volumeHigh }
                            ]
                        }
                    }
                })),
                barWidth: '80%',
                silent: true,
                z: 1
            });
        }

        return {
            backgroundColor: COLORS.background,
            animation: false,
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross' },
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                borderColor: 'rgba(0, 255, 136, 0.3)',
                textStyle: { color: '#fff', fontFamily: 'monospace' }
            },
            grid: [
                // Main chart grid
                { left: '5%', right: showVolume ? '15%' : '5%', top: '10%', bottom: '15%' },
                // Volume profile grid (right side)
                ...(showVolume ? [{ left: '86%', right: '2%', top: '10%', bottom: '15%' }] : [])
            ],
            xAxis: [
                // Main candlestick xAxis
                {
                    type: 'category' as const,
                    data: categoryData,
                    gridIndex: 0,
                    axisLine: { lineStyle: { color: 'rgba(0, 255, 136, 0.3)' } },
                    axisTick: { show: false },
                    axisLabel: { color: '#888', fontSize: 9 },
                    splitLine: { show: false }
                },
                // Volume profile xAxis (dummy, bars extend left)
                ...(showVolume ? [{
                    type: 'value' as const,
                    gridIndex: 1,
                    max: 100,
                    axisLine: { show: false },
                    axisTick: { show: false },
                    axisLabel: { show: false },
                    splitLine: { show: false },
                    inverse: true
                }] : [])
            ],
            yAxis: [
                // Main price yAxis
                {
                    type: 'value' as const,
                    gridIndex: 0,
                    position: 'right' as const,
                    scale: true,
                    axisLine: { lineStyle: { color: 'rgba(0, 255, 136, 0.3)' } },
                    axisLabel: { color: '#888', fontSize: 9, formatter: (v: number) => v.toFixed(2) },
                    splitLine: { lineStyle: { color: COLORS.grid } }
                },
                // Volume profile yAxis (shared with main)
                ...(showVolume ? [{
                    type: 'category' as const,
                    gridIndex: 1,
                    data: volumeProfile.map(v => v.priceLevel.toFixed(2)),
                    axisLine: { show: false },
                    axisTick: { show: false },
                    axisLabel: { show: false }
                }] : [])
            ],
            series: [
                // Candlestick series
                {
                    type: 'candlestick',
                    name: symbol,
                    xAxisIndex: 0,
                    yAxisIndex: 0,
                    data: candleValues,
                    itemStyle: {
                        color: COLORS.candleUp,
                        color0: COLORS.candleDown,
                        borderColor: COLORS.candleUp,
                        borderColor0: COLORS.candleDown
                    },
                    markArea: allMarkAreas.length > 0 ? { data: allMarkAreas, silent: true } : undefined,
                    markLine: markLines.length > 0 ? {
                        symbol: 'none',
                        data: markLines,
                        silent: true
                    } : undefined,
                    z: 2
                },
                ...volumeSeries
            ],
            dataZoom: [
                {
                    type: 'inside',
                    xAxisIndex: [0],
                    start: 70,
                    end: 100
                }
            ]
        };
    }, [candles, orderBlocks, liquidityZones, volumeProfile, showVolume, showOBZones, showLiquidity, entryPrice, stopLoss, takeProfit, symbol]);

    return (
        <div className={cn('relative w-full h-full bg-[#0a0f0a] rounded-lg overflow-hidden', className)}>
            {/* Loading State */}
            {isLoading && (
                <div className="absolute inset-0 flex items-center justify-center bg-[#0a0f0a]/90 z-20">
                    <div className="flex flex-col items-center gap-3">
                        <div className="w-8 h-8 border-2 border-[#00ff88] border-t-transparent rounded-full animate-spin" />
                        <span className="text-sm text-[#00ff88]/70 font-mono">Loading HTF chart...</span>
                    </div>
                </div>
            )}

            {/* Error State */}
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

            {/* Layer Toggle Controls - Moved to bottom left */}
            <div className="absolute bottom-4 left-2 flex flex-row items-center gap-2 z-50">
                <button
                    onClick={() => setShowVolume(!showVolume)}
                    className={cn(
                        "p-2 rounded-lg backdrop-blur-md border-2 transition-all shadow-lg hover:scale-105 active:scale-95",
                        showVolume
                            ? "bg-amber-500/30 border-amber-400 text-amber-300"
                            : "bg-black/70 border-zinc-600 text-zinc-400 hover:border-zinc-400"
                    )}
                    title="Toggle Volume Profile"
                >
                    <ChartLineUp size={20} weight="bold" />
                </button>
                <button
                    onClick={() => setShowOBZones(!showOBZones)}
                    className={cn(
                        "p-2 rounded-lg backdrop-blur-md border-2 transition-all shadow-lg hover:scale-105 active:scale-95",
                        showOBZones
                            ? "bg-emerald-500/30 border-emerald-400 text-emerald-300"
                            : "bg-black/70 border-zinc-600 text-zinc-400 hover:border-zinc-400"
                    )}
                    title="Toggle Order Block Zones"
                >
                    <Fire size={20} weight="bold" />
                </button>
                <button
                    onClick={() => setShowLiquidity(!showLiquidity)}
                    className={cn(
                        "p-2 rounded-lg backdrop-blur-md border-2 transition-all shadow-lg hover:scale-105 active:scale-95",
                        showLiquidity
                            ? "bg-purple-500/30 border-purple-400 text-purple-300"
                            : "bg-black/70 border-zinc-600 text-zinc-400 hover:border-zinc-400"
                    )}
                    title="Toggle Liquidity Zones (EQH/EQL)"
                >
                    <Drop size={20} weight="bold" />
                </button>
            </div>

            {/* Title Badge */}
            {title && (
                <div className="absolute top-2 left-1/2 -translate-x-1/2 z-30">
                    <div className="px-4 py-1.5 rounded bg-black/70 backdrop-blur-sm border border-blue-500/30">
                        <span className="text-sm font-mono font-bold text-blue-400">{title}</span>
                    </div>
                </div>
            )}

            {/* Symbol + TF badges */}
            <div className="absolute top-2 right-2 flex items-center gap-2 z-30">
                <div className="px-3 py-1.5 rounded bg-black/70 backdrop-blur-sm border border-[#00ff88]/40">
                    <span className="text-sm font-mono font-bold text-[#00ff88]">{symbol}</span>
                </div>
                <div className="px-3 py-1.5 rounded bg-[#00ff88]/10 backdrop-blur-sm border border-[#00ff88]/30">
                    <span className="text-sm font-mono font-bold text-[#00ff88]">{timeframe.toUpperCase()}</span>
                </div>
            </div>

            {/* ECharts Canvas */}
            {candles.length > 0 && Object.keys(chartOption).length > 0 && (
                <ReactECharts
                    key={`${symbol}-${timeframe}`}
                    option={chartOption}
                    style={{ height: '100%', width: '100%' }}
                    opts={{ renderer: 'canvas' }}
                    notMerge={true}
                    lazyUpdate={true}
                />
            )}
        </div>
    );
}

export default HTFBiasChart;
