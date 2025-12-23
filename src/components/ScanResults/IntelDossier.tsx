
import { ScanResult } from '@/utils/mockData';
import { cn } from '@/lib/utils';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Copy, Crosshair, ShieldWarning, ChartLineUp, CaretRight, CheckCircle, Warning } from '@phosphor-icons/react';
import { useToast } from '@/hooks/use-toast';
import { WarningsContext } from '@/components/WarningsContext';
import { RegimeIndicator } from '@/components/RegimeIndicator';
import { RegimeMetadata } from '@/types/regime';
import { LightweightChart } from '@/components/charts/LightweightChart';
import { MultiTimeframeChartGrid } from '@/components/charts/MultiTimeframeChartGrid';

interface IntelDossierProps {
    result: ScanResult;
    metadata?: any;
    regime?: RegimeMetadata;
    onClose?: () => void; // For mobile back nav
}

export function IntelDossier({ result, metadata, regime, onClose }: IntelDossierProps) {
    const { toast } = useToast();
    const [activeTab, setActiveTab] = useState('overview');

    // Helper to safely get numeric values from updated ScanResult type
    const entryPrice = result.entryZone ? (result.entryZone.high + result.entryZone.low) / 2 : 0;
    const stopPrice = result.stopLoss || 0;
    const targetPrice = result.takeProfits?.[0] || 0;
    // Use entry price as a proxy for current price if live data isn't merged yet
    const displayPrice = result.entryZone?.low || 0;

    const copySignal = () => {
        const text = `🎯 SIGNAL: ${result.pair} ${result.trendBias}\nEntry: ${entryPrice.toFixed(2)}\nStop: ${stopPrice.toFixed(2)}\nTarget: ${targetPrice.toFixed(2)}`;
        navigator.clipboard.writeText(text);
        toast({ title: 'Signal Copied', description: 'Trade parameters copied to clipboard' });
    };

    const isBullish = result.trendBias === 'BULLISH';

    // Extract factors from breakdown or provide generic fallback
    const factors = result.confluence_breakdown
        ? Object.keys(result.confluence_breakdown).filter(k => (result.confluence_breakdown as any)[k])
        : ['High Timeframe Alignment', 'Momentum Confirmation', 'Key Level Reaction'];

    // Extract order blocks by timeframe from metadata
    const orderBlocksByTimeframe: Record<string, any[]> = {};
    const scannedTimeframes: string[] = [];

    if (metadata?.applied_timeframes || metadata?.appliedTimeframes) {
        scannedTimeframes.push(...(metadata.applied_timeframes || metadata.appliedTimeframes));
    }

    // Extract OBs from metadata (structure varies by backend version)
    if (metadata?.order_blocks_by_timeframe) {
        Object.assign(orderBlocksByTimeframe, metadata.order_blocks_by_timeframe);
    } else if ((result.metadata as any)?.order_blocks) {
        // Fallback: group OBs by timeframe if they have tf property
        const allOBs = (result.metadata as any).order_blocks || [];
        allOBs.forEach((ob: any) => {
            const tf = ob.timeframe || result.timeframe || '1h';
            if (!orderBlocksByTimeframe[tf]) {
                orderBlocksByTimeframe[tf] = [];
            }
            orderBlocksByTimeframe[tf].push(ob);
        });
    }

    // Determine scanner mode from metadata
    const scannerMode = metadata?.mode || 'surgical';

    return (
        <div className="h-full flex flex-col bg-black/20 backdrop-blur-sm relative">
            {/* Mobile Close Button */}
            {onClose && (
                <button onClick={onClose} className="lg:hidden absolute top-4 left-4 z-50 p-2 bg-black/60 rounded-full border border-white/10 text-white">
                    <CaretRight size={20} className="rotate-180" />
                </button>
            )}

            {/* Hero Header */}
            <div className="p-6 border-b border-[#00ff88]/20 bg-gradient-to-r from-[#00ff88]/5 to-transparent">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                    <div>
                        <div className="flex items-center gap-3 mb-1">
                            <h1 className="text-3xl md:text-5xl font-bold tracking-tight text-white">{result.pair}</h1>
                            <Badge variant="outline" className={cn("text-xs px-2 py-0.5 border font-mono tracking-wider", isBullish ? "border-green-500/50 text-green-400 bg-green-500/10" : "border-red-500/50 text-red-400 bg-red-500/10")}>
                                {result.trendBias}
                            </Badge>
                        </div>
                        <div className="flex items-center gap-4 text-sm text-muted-foreground font-mono">
                            <span className="flex items-center gap-1">
                                Ref: <span className="text-white font-bold">${displayPrice.toFixed(displayPrice < 1 ? 5 : 2)}</span>
                            </span>
                            <span className="w-px h-3 bg-white/20" />
                            <RegimeIndicator regime={regime} size="xs" compact />
                        </div>
                    </div>

                    <div className="flex gap-3">
                        <Button variant="outline" onClick={copySignal} className="font-mono text-xs border-white/10 hover:bg-white/5 gap-2">
                            <Copy size={14} /> COPY
                        </Button>
                        <Button className="bg-[#00ff88] text-black hover:bg-[#00ff88]/90 font-bold font-mono tracking-wider gap-2">
                            <Crosshair size={18} weight="bold" /> EXECUTE PLAN
                        </Button>
                    </div>
                </div>
            </div>

            {/* Main Content Tabs */}
            <div className="flex-1 overflow-hidden flex flex-col">
                <Tabs defaultValue="overview" className="flex-1 flex flex-col" onValueChange={setActiveTab}>
                    <div className="px-6 pt-4 border-b border-[#00ff88]/10">
                        <TabsList className="bg-black/40 border border-[#00ff88]/20">
                            <TabsTrigger value="overview" className="gap-2 font-mono text-xs tracking-wider data-[state=active]:bg-[#00ff88]/20 data-[state=active]:text-[#00ff88]">
                                <ChartLineUp size={14} /> OVERVIEW
                            </TabsTrigger>
                            <TabsTrigger value="analysis" className="gap-2 font-mono text-xs tracking-wider data-[state=active]:bg-[#00ff88]/20 data-[state=active]:text-[#00ff88]">
                                <ShieldWarning size={14} /> INTEL & RISKS
                            </TabsTrigger>
                            <TabsTrigger value="plan" className="gap-2 font-mono text-xs tracking-wider data-[state=active]:bg-[#00ff88]/20 data-[state=active]:text-[#00ff88]">
                                <Crosshair size={14} /> TRADE PLAN
                            </TabsTrigger>
                        </TabsList>
                    </div>

                    <div className="flex-1 overflow-y-auto p-6 scrollbar-thin scrollbar-thumb-[#00ff88]/20 scrollbar-track-transparent">

                        {/* OVERVIEW TAB */}
                        <TabsContent value="overview" className="mt-0 space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                            {/* Key Metrics Grid */}
                            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                                <MetricCard label="Confluence" value={`${result.confidenceScore}%`} color={result.confidenceScore >= 80 ? 'green' : 'amber'} />
                                <MetricCard label="Expected Value" value={`${(result.metadata as any)?.ev?.expected_value || '0.0'}R`} color="cyan" />
                                <MetricCard label="Risk:Reward" value={`${result.riskReward || 0}:1`} color="white" />
                                <MetricCard label="Classification" value={result.classification || 'SWING'} color="purple" />
                            </div>

                            {/* Multi-Timeframe Charts with Order Blocks */}
                            <div className="w-full">
                                {scannedTimeframes.length > 0 ? (
                                    <MultiTimeframeChartGrid
                                        symbol={result.pair}
                                        mode={scannerMode}
                                        timeframes={scannedTimeframes}
                                        orderBlocksByTimeframe={orderBlocksByTimeframe}
                                        entryPrice={entryPrice}
                                        stopLoss={stopPrice}
                                        takeProfit={targetPrice}
                                    />
                                ) : (
                                    // Fallback to single chart if no timeframe data
                                    <div className="aspect-video w-full rounded-xl border border-[#00ff88]/20 bg-black/40 overflow-hidden">
                                        <LightweightChart
                                            symbol={result.pair}
                                            timeframe={result.timeframe || '1h'}
                                            orderBlocks={(result.metadata as any)?.order_blocks || []}
                                            entryPrice={entryPrice}
                                            stopLoss={stopPrice}
                                            takeProfit={targetPrice}
                                        />
                                    </div>
                                )}
                            </div>
                        </TabsContent>

                        {/* ANALYSIS TAB */}
                        <TabsContent value="analysis" className="mt-0 space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-300">
                            <section>
                                <h3 className="text-lg font-bold hud-headline mb-4 flex items-center gap-2">
                                    <CheckCircle className="text-[#00ff88]" /> CONFIRMED FACTORS
                                </h3>
                                {/* Reusing existing component but styled for panel */}
                                <div className="prose prose-invert max-w-none">
                                    <ul className="grid gap-2">
                                        {factors.map((factor, i) => (
                                            <li key={i} className="flex gap-2 p-3 bg-black/40 rounded border border-white/5 text-sm">
                                                <span className="text-[#00ff88] font-bold">✓</span> {formatFactor(factor)}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </section>

                            <section>
                                <h3 className="text-lg font-bold hud-headline mb-4 flex items-center gap-2 text-amber-400">
                                    <Warning weight="fill" /> RISK FACTORS
                                </h3>
                                <WarningsContext results={[result]} metadata={metadata} embedded />
                            </section>
                        </TabsContent>

                        {/* PLAN TAB */}
                        <TabsContent value="plan" className="mt-0 space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                            <div className="grid gap-4 md:grid-cols-3">
                                <PlanCard title="ENTRY ZONE" value={`$${entryPrice.toFixed(2)}`} type="entry" />
                                <PlanCard title="STOP LOSS" value={`$${stopPrice.toFixed(2)}`} type="stop" />
                                <PlanCard title="TAKE PROFIT" value={`$${targetPrice.toFixed(2)}`} type="target" />
                            </div>

                            <div className="p-4 rounded-xl border border-[#00ff88]/20 bg-[#00ff88]/5">
                                <h4 className="text-sm font-bold font-mono text-[#00ff88] mb-2 uppercase tracking-widest">Strategy Note</h4>
                                <p className="text-sm text-muted-foreground leading-relaxed">
                                    {(result as any).rationale || "No specific strategy notes generated for this setup."}
                                </p>
                            </div>
                        </TabsContent>

                    </div>
                </Tabs>
            </div>
        </div>
    );
}

function MetricCard({ label, value, color }: { label: string; value: string; color: string }) {
    const colors = {
        green: 'text-[#00ff88] border-[#00ff88]/30 bg-[#00ff88]/5',
        amber: 'text-amber-400 border-amber-500/30 bg-amber-500/5',
        red: 'text-red-400 border-red-500/30 bg-red-500/5',
        cyan: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/5',
        purple: 'text-purple-400 border-purple-500/30 bg-purple-500/5',
        white: 'text-white border-white/20 bg-white/5',
    };
    // @ts-ignore - dirty fast mapping
    const activeColor = colors[color] || colors.white;

    return (
        <div className={cn("p-4 rounded-lg border flex flex-col items-center justify-center text-center gap-1", activeColor)}>
            <div className="text-2xl font-bold font-mono tracking-tighter tabular-nums">{value}</div>
            <div className="text-[10px] uppercase tracking-widest opacity-60 font-semibold">{label}</div>
        </div>
    );
}

function PlanCard({ title, value, type }: { title: string; value: string; type: 'entry' | 'stop' | 'target' }) {
    const styles = {
        entry: { border: 'border-blue-500/30', text: 'text-blue-400', bg: 'bg-blue-500/5' },
        stop: { border: 'border-red-500/30', text: 'text-red-400', bg: 'bg-red-500/5' },
        target: { border: 'border-green-500/30', text: 'text-green-400', bg: 'bg-green-500/5' },
    }[type];

    return (
        <div className={cn("p-6 rounded-xl border flex flex-col items-center gap-2", styles.border, styles.bg)}>
            <span className="text-xs font-mono uppercase tracking-widest opacity-70">{title}</span>
            <span className={cn("text-3xl font-bold font-mono tabular-nums", styles.text)}>{value}</span>
        </div>
    );
}

function formatFactor(factor: string) {
    return factor.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
}
