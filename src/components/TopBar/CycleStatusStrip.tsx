/**
 * CycleStatusStrip - Compact cycle status badges for TopBar
 * Shows DCL/WCL translation status at a glance
 */

import { useSymbolCycles } from '@/hooks/useSymbolCycles';
import { cn } from '@/lib/utils';

interface CycleBadgeProps {
    label: string;
    day: number;
    range: string;
    translation: string;
    bias: string;
    isInWindow?: boolean;
}

function CycleBadge({ label, day, range, translation, bias, isInWindow }: CycleBadgeProps) {
    // Translation colors
    const translationColor =
        translation === 'RTR' ? 'text-emerald-400' :
            translation === 'LTR' ? 'text-red-400' : 'text-amber-400';

    const translationBg =
        translation === 'RTR' ? 'bg-emerald-500/20' :
            translation === 'LTR' ? 'bg-red-500/20' : 'bg-amber-500/20';

    return (
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-black/40 border border-white/10">
            {/* Label */}
            <span className="text-[10px] font-bold tracking-wider text-muted-foreground">
                {label}
            </span>

            {/* Day count */}
            <span className="text-xs font-mono text-foreground">
                D{day}
            </span>

            {/* Translation badge */}
            <span className={cn(
                "text-[9px] font-bold px-1.5 py-0.5 rounded",
                translationBg, translationColor
            )}>
                {translation}
            </span>

            {/* In-window indicator */}
            {isInWindow && (
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
            )}
        </div>
    );
}

export function CycleStatusStrip() {
    const { btcContext, isLoading } = useSymbolCycles({
        symbols: ['BTCUSDT'],
        exchange: 'phemex'
    });

    if (isLoading || !btcContext) {
        return (
            <div className="flex items-center gap-2 opacity-50">
                <div className="h-6 w-20 bg-white/5 rounded animate-pulse" />
                <div className="h-6 w-20 bg-white/5 rounded animate-pulse" />
            </div>
        );
    }

    const dcl = btcContext.dcl;
    const wcl = btcContext.wcl;

    // Format translation (strip "_translated" suffix if present)
    const formatTranslation = (t: string) => {
        if (t?.includes('right')) return 'RTR';
        if (t?.includes('left')) return 'LTR';
        if (t?.includes('mid')) return 'MTR';
        return t?.toUpperCase()?.slice(0, 3) || 'MTR';
    };

    return (
        <div className="flex items-center gap-2">
            {dcl && (
                <CycleBadge
                    label="DCL"
                    day={dcl.bars_since_low || 0}
                    range={`${dcl.expected_length?.min || 18}-${dcl.expected_length?.max || 28}`}
                    translation={formatTranslation(dcl.translation)}
                    bias={dcl.bias || 'NEUTRAL'}
                    isInWindow={dcl.is_in_window}
                />
            )}

            {wcl && (
                <CycleBadge
                    label="WCL"
                    day={wcl.bars_since_low || 0}
                    range={`${wcl.expected_length?.min || 35}-${wcl.expected_length?.max || 50}`}
                    translation={formatTranslation(wcl.translation)}
                    bias={wcl.bias || 'NEUTRAL'}
                    isInWindow={wcl.is_in_window}
                />
            )}
        </div>
    );
}
