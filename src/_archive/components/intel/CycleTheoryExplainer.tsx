
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Info, TrendUp, TrendDown } from '@phosphor-icons/react';

interface Props {
    className?: string;
}

export function CycleTheoryExplainer({ className }: Props) {
    const [activeTab, setActiveTab] = useState<'RTR' | 'LTR'>('RTR');

    return (
        <div className={cn(
            "rounded-2xl border border-border/40 bg-card/20 backdrop-blur-sm p-6 overflow-hidden relative",
            className
        )}>
            {/* Background Decor */}
            <div className="absolute top-0 right-0 p-32 bg-accent/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 pointer-events-none" />

            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h3 className="text-lg font-bold text-foreground">Cycle Theory 101</h3>
                    <p className="text-xs text-muted-foreground mt-1 max-w-[300px]">
                        Price structure dictates market health. Understanding "Translation" is key to identifying cycle tops.
                    </p>
                </div>
                <div className="flex bg-card/50 rounded-lg p-1 border border-border/30">
                    <button
                        onClick={() => setActiveTab('RTR')}
                        className={cn(
                            "px-3 py-1.5 rounded-md text-xs font-bold transition-all",
                            activeTab === 'RTR' ? "bg-green-500/20 text-green-400 shadow-sm" : "text-muted-foreground hover:text-foreground"
                        )}
                    >
                        Right Translation
                    </button>
                    <button
                        onClick={() => setActiveTab('LTR')}
                        className={cn(
                            "px-3 py-1.5 rounded-md text-xs font-bold transition-all",
                            activeTab === 'LTR' ? "bg-red-500/20 text-red-400 shadow-sm" : "text-muted-foreground hover:text-foreground"
                        )}
                    >
                        Left Translation
                    </button>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">

                {/* Visual Diagram */}
                <div className="h-48 relative border border-border/30 rounded-xl bg-card/30 flex items-center justify-center p-4">
                    {activeTab === 'RTR' ? (
                        <svg viewBox="0 0 100 50" className="w-full h-full drop-shadow-[0_0_15px_rgba(74,222,128,0.2)]">
                            {/* Grid Lines */}
                            <line x1="50" y1="0" x2="50" y2="50" className="stroke-border stroke-[0.5] stroke-dasharray-2" />
                            <text x="52" y="48" className="text-[3px] fill-muted-foreground font-mono">MIDPOINT</text>

                            {/* RTR Curve: Peak AFTER midpoint (Right Side) */}
                            <path
                                d="M 5,45 Q 25,45 35,35 T 75,5 T 95,45"
                                fill="none"
                                className="stroke-green-400 stroke-[1.5]"
                            />
                            {/* Peak Marker */}
                            <circle cx="75" cy="5" r="1.5" className="fill-green-400 animate-pulse" />
                            <text x="70" y="12" className="text-[3px] fill-green-400 font-bold">CYCLE PEAK</text>
                        </svg>
                    ) : (
                        <svg viewBox="0 0 100 50" className="w-full h-full drop-shadow-[0_0_15px_rgba(248,113,113,0.2)]">
                            {/* Grid Lines */}
                            <line x1="50" y1="0" x2="50" y2="50" className="stroke-border stroke-[0.5] stroke-dasharray-2" />
                            <text x="52" y="48" className="text-[3px] fill-muted-foreground font-mono">MIDPOINT</text>

                            {/* LTR Curve: Peak BEFORE midpoint (Left Side) */}
                            <path
                                d="M 5,45 Q 25,5 35,5 T 75,35 T 95,45"
                                fill="none"
                                className="stroke-red-400 stroke-[1.5]"
                            />
                            {/* Peak Marker */}
                            <circle cx="35" cy="5" r="1.5" className="fill-red-400 animate-pulse" />
                            <text x="30" y="12" className="text-[3px] fill-red-400 font-bold">CYCLE PEAK</text>
                        </svg>
                    )}
                </div>

                {/* Text Explanation */}
                <div className="space-y-4">
                    <div className="flex items-start gap-3">
                        <div className={cn(
                            "p-2 rounded-lg mt-1",
                            activeTab === 'RTR' ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"
                        )}>
                            {activeTab === 'RTR' ? <TrendUp size={20} weight="bold" /> : <TrendDown size={20} weight="bold" />}
                        </div>
                        <div>
                            <h4 className={cn(
                                "font-bold mb-1",
                                activeTab === 'RTR' ? "text-green-400" : "text-red-400"
                            )}>
                                {activeTab === 'RTR' ? "Right Translated (Bullish)" : "Left Translated (Bearish)"}
                            </h4>
                            <p className="text-sm text-muted-foreground leading-relaxed">
                                {activeTab === 'RTR'
                                    ? "A cycle that peaks AFTER the midpoint. This indicates strong buying pressure sustaining the trend longer than average. It is the hallmark of a healthy bull market."
                                    : "A cycle that peaks BEFORE the midpoint. This indicates weakness, where sellers overwhelm buyers early. Often leads to a long, painful correction (markdown phase)."}
                            </p>
                        </div>
                    </div>

                    <div className="bg-card/40 border border-border/30 rounded-lg p-3">
                        <div className="flex items-center gap-2 mb-2">
                            <Info size={14} className="text-accent" />
                            <span className="text-xs font-bold text-accent uppercase">Camel Finance Axiom</span>
                        </div>
                        <p className="text-xs text-muted-foreground italic">
                            "Price structure is truth. Narrative is noise. {activeTab === 'RTR' ? 'When price holds up late into a cycle, the narrative will turn bullish to justify it.' : 'When price fails early, the narrative often remains bullish while the market silently corrects.'}"
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}
