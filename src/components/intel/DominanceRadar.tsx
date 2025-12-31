
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { useMarketRegime } from '@/hooks/useMarketRegime';
import { CaretUp, CaretDown, Info, Minus } from '@phosphor-icons/react';

interface Props {
    className?: string;
    compact?: boolean;
}

export function DominanceRadar({ className, compact = false }: Props) {
    const { btcDominance, usdtDominance, altDominance } = useMarketRegime('scanner');
    const [showInfo, setShowInfo] = useState(false);

    // Safety checks
    const btc = btcDominance || 52.5;
    const usdt = usdtDominance || 6.2;
    const alt = altDominance || 12.5;

    // Mock trends for visualization
    const trends = {
        btc: 0.5,
        usdt: -0.2,
        alts: -0.1
    };

    const renderTrend = (value: number) => {
        if (value > 0.05) return <CaretUp weight="bold" className="text-emerald-400" />;
        if (value < -0.05) return <CaretDown weight="bold" className="text-red-400" />;
        return <Minus weight="bold" className="text-muted-foreground" />;
    };

    return (
        <div className={cn(
            "rounded-xl border border-border/40 bg-card/20 backdrop-blur-sm p-4",
            className
        )}>
            <div className="flex items-center justify-between mb-4">
                <div className="text-xs font-bold text-muted-foreground tracking-widest uppercase">
                    CAPITAL ROTATION RADAR
                </div>
                <button
                    onClick={() => setShowInfo(!showInfo)}
                    className="text-muted-foreground hover:text-accent transition-colors"
                >
                    <Info size={16} weight={showInfo ? "fill" : "regular"} />
                </button>
            </div>

            {showInfo && (
                <div className="mb-4 p-3 bg-card/40 rounded-lg border border-border/30 text-xs text-muted-foreground animate-in slide-in-from-top-2">
                    <p className="mb-2"><strong className="text-foreground">Dominance Physics:</strong></p>
                    <ul className="list-disc pl-4 space-y-1">
                        <li><strong>BTC.D Rising:</strong> Bitcoin is sucking liquidity. Alts usually bleed. Risk-off within crypto.</li>
                        <li><strong>USDT.D Rising:</strong> Traders selling everything for stablecoins. True Risk-off / Correction.</li>
                        <li><strong>OTHERS.D Rising:</strong> "Altseason". Capital rotating from BTC to Alts. Risk-on.</li>
                    </ul>
                </div>
            )}

            <div className="space-y-4">
                {/* BTC Dominance */}
                <div className="space-y-1">
                    <div className="flex justify-between items-center text-sm">
                        <span className="font-bold text-orange-500">BTC.D</span>
                        <div className="flex items-center gap-2">
                            <span className="font-mono">{btc.toFixed(1)}%</span>
                            {renderTrend(trends.btc)}
                        </div>
                    </div>
                    <div className="h-2 bg-secondary/30 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-gradient-to-r from-orange-600 to-orange-400 transition-all duration-1000"
                            style={{ width: `${(btc / 80) * 100}%` }}
                        />
                    </div>
                </div>

                {/* USDT Dominance */}
                <div className="space-y-1">
                    <div className="flex justify-between items-center text-sm">
                        <span className="font-bold text-green-500">USDT.D</span>
                        <div className="flex items-center gap-2">
                            <span className="font-mono">{usdt.toFixed(1)}%</span>
                            {renderTrend(trends.usdt)}
                        </div>
                    </div>
                    <div className="h-2 bg-secondary/30 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-gradient-to-r from-green-600 to-green-400 transition-all duration-1000"
                            style={{ width: `${(usdt / 20) * 100}%` }}
                        />
                    </div>
                </div>

                {/* Others Dominance (Alts) */}
                {!compact && (
                    <div className="space-y-1">
                        <div className="flex justify-between items-center text-sm">
                            <span className="font-bold text-blue-500">OTHERS.D</span>
                            <div className="flex items-center gap-2">
                                <span className="font-mono">{alt.toFixed(1)}%</span>
                                {renderTrend(trends.alts)}
                            </div>
                        </div>
                        <div className="h-2 bg-secondary/30 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-gradient-to-r from-blue-600 to-blue-400 transition-all duration-1000"
                                style={{ width: `${(alt / 25) * 100}%` }}
                            />
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
