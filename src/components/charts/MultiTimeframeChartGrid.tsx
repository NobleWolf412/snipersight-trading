import { LightweightChart } from './LightweightChart';
import { HTFBiasChart } from './HTFBiasChart';
import { cn } from '@/lib/utils';
import { useScanner } from '@/context/ScannerContext';

interface OrderBlock {
    price_high: number;
    price_low: number;
    timestamp: number;
    type: 'bullish' | 'bearish';
    mitigated?: boolean;
    timeframe?: string;
}


interface MultiTimeframeChartGridProps {
    symbol: string;
    mode: string;
    timeframes: string[];
    orderBlocksByTimeframe: Record<string, OrderBlock[]>;
    liquidityZones?: any[]; // Added for HTF Bias Chart
    entryPrice?: number;
    stopLoss?: number;
    takeProfit?: number;
    className?: string;
}

/**
 * Adaptive multi-timeframe chart grid that displays charts based on scanner mode.
 * 
 * - 4 or fewer TFs: 2×2 grid with individual charts
 * - 5-6 TFs: 3-panel composite layout (Structure / Zone / Entry)
 */
export function MultiTimeframeChartGrid({
    symbol,
    mode,
    timeframes,
    orderBlocksByTimeframe,
    liquidityZones = [], // Default to empty array
    entryPrice,
    stopLoss,
    takeProfit,
    className,
}: MultiTimeframeChartGridProps) {

    // Always use composite 3-panel layout with labels for consistency across all modes
    // Previously, modes with <= 4 TFs used a simple 2x2 grid without labels

    // Determine the active mode's configuration
    const { scannerModes } = useScanner();
    const activeMode = (scannerModes && scannerModes.length > 0)
        ? (scannerModes.find(m => m.name.toLowerCase() === mode.toLowerCase()) || scannerModes[0])
        : {
            name: 'Default',
            structure_timeframes: ['1w', '1d'],
            zone_timeframes: ['4h', '1h'],
            entry_timeframes: ['15m', '5m']
        }; // Safe fallback to prevent crash

    // Helper: Find which category a set of timeframes belongs to
    const categorizeTimeframes = () => {
        // Default fallbacks if mode config is missing
        const defaultStructure = ['1w', '1d'];
        const defaultZone = ['4h', '1h'];
        const defaultEntry = ['15m', '5m', '1m'];

        const modeStructure = activeMode.structure_timeframes || defaultStructure;
        const modeZone = activeMode.zone_timeframes || defaultZone;
        // Include both entry_timeframes AND entry_trigger_timeframes (backend uses different names)
        const entryTriggerTfs = (activeMode as any).entry_trigger_timeframes || [];
        const modeEntry = [
            ...(activeMode.entry_timeframes || []),
            ...entryTriggerTfs
        ].length > 0
            ? [...(activeMode.entry_timeframes || []), ...entryTriggerTfs]
            : defaultEntry;

        return {
            structureFiles: timeframes.filter(tf => modeStructure.includes(tf)),
            zoneFiles: timeframes.filter(tf => modeZone.includes(tf)),
            entryFiles: timeframes.filter(tf => modeEntry.includes(tf)),
            // Dedup if overlaps exist (priority: Structure > Zone > Entry)
        };
    };

    const { structureFiles, zoneFiles, entryFiles } = categorizeTimeframes();

    // Fallback logic: If strict filtering leaves empty arrays, revert to index-based split
    const finalStructure = structureFiles.length ? structureFiles : timeframes.slice(0, 2);
    const finalZone = zoneFiles.length ? zoneFiles : timeframes.slice(2, 4);
    const finalEntry = entryFiles.length ? entryFiles : timeframes.slice(4);

    // Helper: Case-insensitive timeframe lookup
    // Backend may use "4H" while mode config uses "4h"
    const getOBsForTimeframe = (tf: string) => {
        const tfLower = tf.toLowerCase();
        // Try exact match first, then case-insensitive
        if (orderBlocksByTimeframe[tf]) {
            return orderBlocksByTimeframe[tf];
        }
        // Try lowercase key
        if (orderBlocksByTimeframe[tfLower]) {
            return orderBlocksByTimeframe[tfLower];
        }
        // Try uppercase key
        const tfUpper = tf.toUpperCase();
        if (orderBlocksByTimeframe[tfUpper]) {
            return orderBlocksByTimeframe[tfUpper];
        }
        return [];
    };

    // Combine Order Blocks (case-insensitive lookup)
    const structureOBs = finalStructure.flatMap(tf =>
        getOBsForTimeframe(tf).map(ob => ({ ...ob, timeframe: tf.toLowerCase() }))
    );
    const zoneOBs = finalZone.flatMap(tf =>
        getOBsForTimeframe(tf).map(ob => ({ ...ob, timeframe: tf.toLowerCase() }))
    );
    const entryOBs = finalEntry.flatMap(tf =>
        getOBsForTimeframe(tf).map(ob => ({ ...ob, timeframe: tf.toLowerCase() }))
    );

    const structurePrimaryTF = finalStructure[0] || '1d';
    const zonePrimaryTF = finalZone[0] || '4h';
    // Fix: Select smallest timeframe (last in array) for Entry execution
    const entryPrimaryTF = finalEntry[finalEntry.length - 1] || '15m';

    // Debug: Log OB data flow with detailed lookups
    console.log('[MultiTimeframeChartGrid] OB Debug:', {
        mode,
        finalStructure,
        finalZone,
        finalEntry,
        structureOBsCount: structureOBs.length,
        zoneOBsCount: zoneOBs.length,
        entryOBsCount: entryOBs.length,
        structureOBsSample: structureOBs.slice(0, 2),
        allTimeframesInData: Object.keys(orderBlocksByTimeframe),
        obCountsByTF: Object.entries(orderBlocksByTimeframe).map(([tf, obs]) => ({ tf, count: obs.length }))
    });

    return (
        <div className={cn('grid grid-cols-2 gap-4', className)}>
            {/* Top row: Structure chart (full width) - HTF Bias with Heatmap */}
            {finalStructure.length > 0 && (
                <div className="col-span-2 h-[400px] relative group border border-blue-500/20 rounded-xl bg-black/20 overflow-hidden">
                    <HTFBiasChart
                        symbol={symbol}
                        timeframe={structurePrimaryTF}
                        orderBlocks={structureOBs.map(ob => ({
                            price_high: ob.price_high,
                            price_low: ob.price_low,
                            timestamp: ob.timestamp,
                            type: ob.type,
                            mitigated: ob.mitigated,
                            timeframe: ob.timeframe
                        }))}
                        entryPrice={entryPrice}
                        stopLoss={stopLoss}
                        takeProfit={takeProfit}
                        liquidityZones={liquidityZones}
                        title={`🛡️ STRUCTURE (${structurePrimaryTF.toUpperCase()})`}
                    />
                </div>
            )}

            {/* Bottom Left: Zone chart (The Setup) */}
            {finalZone.length > 0 && (
                <div className="h-[400px] relative group rounded-xl border border-amber-500/50 shadow-[0_0_30px_-10px_rgba(255,170,0,0.3)] overflow-hidden bg-black/20">
                    <div className="absolute top-2 right-2 z-10 px-2 py-0.5 bg-amber-500/20 border border-amber-500/50 rounded text-[10px] font-bold text-amber-400 tracking-wider animate-pulse">
                        🎯 ZONE
                    </div>
                    <LightweightChart
                        symbol={symbol}
                        timeframe={zonePrimaryTF}
                        orderBlocks={zoneOBs}
                        liquidityZones={liquidityZones}
                        entryPrice={entryPrice}
                        stopLoss={stopLoss}
                        takeProfit={takeProfit}
                        title={`SETUP (${zonePrimaryTF.toUpperCase()})`}
                        showLegend={true}
                    />
                </div>
            )}

            {/* Bottom Right: Entry chart (The Trigger) */}
            {finalEntry.length > 0 && (
                <div className="h-[400px] relative group border border-white/5 rounded-xl bg-black/20">
                    <div className="absolute top-2 right-2 z-10 px-2 py-0.5 bg-emerald-500/20 border border-emerald-500/30 rounded text-[10px] font-bold text-emerald-400 tracking-wider">
                        ⚡ TRIGGER
                    </div>
                    <LightweightChart
                        symbol={symbol}
                        timeframe={entryPrimaryTF}
                        orderBlocks={entryOBs}
                        liquidityZones={liquidityZones}
                        entryPrice={entryPrice}
                        stopLoss={stopLoss}
                        takeProfit={takeProfit}
                        title={`EXECUTION (${entryPrimaryTF.toUpperCase()})`}
                        showLegend={true}
                    />
                </div>
            )}
        </div>
    );
}
