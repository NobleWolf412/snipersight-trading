import { LightweightChart } from './LightweightChart';
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
        const modeEntry = activeMode.entry_timeframes || defaultEntry;

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

    // Combine Order Blocks
    const structureOBs = finalStructure.flatMap(tf =>
        (orderBlocksByTimeframe[tf] || []).map(ob => ({ ...ob, timeframe: tf }))
    );
    const zoneOBs = finalZone.flatMap(tf =>
        (orderBlocksByTimeframe[tf] || []).map(ob => ({ ...ob, timeframe: tf }))
    );
    const entryOBs = finalEntry.flatMap(tf =>
        (orderBlocksByTimeframe[tf] || []).map(ob => ({ ...ob, timeframe: tf }))
    );

    const structurePrimaryTF = finalStructure[0] || '1d';
    const zonePrimaryTF = finalZone[0] || '4h';
    // Fix: Select smallest timeframe (last in array) for Entry execution
    const entryPrimaryTF = finalEntry[finalEntry.length - 1] || '15m';

    return (
        <div className={cn('grid grid-cols-2 gap-4', className)}>
            {/* Top row: Structure chart (full width) */}
            {finalStructure.length > 0 && (
                <div className="col-span-2 h-[350px] relative group border border-white/5 rounded-xl bg-black/20">
                    <div className="absolute top-2 right-2 z-10 px-2 py-0.5 bg-blue-500/20 border border-blue-500/30 rounded text-[10px] font-bold text-blue-400 tracking-wider">
                        🛡️ STRUCTURE
                    </div>
                    <LightweightChart
                        symbol={symbol}
                        timeframe={structurePrimaryTF}
                        orderBlocks={structureOBs}
                        entryPrice={entryPrice}
                        stopLoss={stopLoss}
                        takeProfit={takeProfit}
                        title={`BIAS (${structurePrimaryTF.toUpperCase()})`}
                        showLegend={true}
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
