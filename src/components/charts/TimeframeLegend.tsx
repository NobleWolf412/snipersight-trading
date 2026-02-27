import { cn } from '@/lib/utils';

interface TimeframeLegendProps {
    timeframes: Array<{
        tf: string;
        color: string;
        label?: string;
    }>;
    className?: string;
}

const TIMEFRAME_COLORS: Record<string, { color: string; label: string }> = {
    '1w': { color: '#a855f7', label: 'Weekly' },
    '1d': { color: '#3b82f6', label: 'Daily' },
    '4h': { color: '#06b6d4', label: '4 Hour' },
    '1h': { color: '#14b8a6', label: '1 Hour' },
    '15m': { color: '#ff8a00', label: '15 Min' },
    '5m': { color: '#fbbf24', label: '5 Min' },
    '1m': { color: '#ef4444', label: '1 Min' },
};

export function TimeframeLegend({ timeframes, className }: TimeframeLegendProps) {
    return (
        <div className={cn('flex flex-wrap items-center gap-3', className)}>
            <span className="text-xs font-mono text-white/40 uppercase tracking-wider">Timeframes:</span>
            {timeframes.map(({ tf, color, label }) => {
                const displayLabel = label || TIMEFRAME_COLORS[tf]?.label || tf.toUpperCase();
                const displayColor = color || TIMEFRAME_COLORS[tf]?.color || '#888';

                return (
                    <div key={tf} className="flex items-center gap-1.5">
                        <div
                            className="w-3 h-3 rounded-sm border border-white/20"
                            style={{ backgroundColor: displayColor }}
                        />
                        <span className="text-xs font-mono text-white/70">{displayLabel}</span>
                    </div>
                );
            })}
        </div>
    );
}

export { TIMEFRAME_COLORS };
