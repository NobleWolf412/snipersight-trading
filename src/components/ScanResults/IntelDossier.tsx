
import { ScanResult } from '@/utils/mockData';
import { cn } from '@/lib/utils';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import * as Tabs from '@radix-ui/react-tabs';
import {
    Copy, Crosshair, ShieldWarning, ChartLineUp, CaretRight,
    CheckCircle, Warning, Lightning, Lightbulb, Info, Clock,
    Target, TrendUp, TrendDown, Gauge, XCircle
} from '@phosphor-icons/react';
import { useToast } from '@/hooks/use-toast';
import { WarningsContext } from '@/components/WarningsContext';
import { RegimeIndicator } from '@/components/RegimeIndicator';
import { RegimeMetadata } from '@/types/regime';
import { LightweightChart } from '@/components/charts/LightweightChart';
import { MultiTimeframeChartGrid } from '@/components/charts/MultiTimeframeChartGrid';
import { TierBadge } from '@/components/TierBadge';
import { getSignalTier } from '@/utils/signalTiers';

interface IntelDossierProps {
    result: ScanResult;
    metadata?: any;
    regime?: RegimeMetadata;
    onClose?: () => void;
}

// ============================================================================
// SECTION WRAPPER - Consistent styling for all sections
// ============================================================================
function Section({ title, icon, children, className, variant = 'default' }: {
    title?: string;
    icon?: React.ReactNode;
    children: React.ReactNode;
    className?: string;
    variant?: 'default' | 'green' | 'amber' | 'red' | 'blue';
}) {
    const glowClasses = {
        default: '',
        green: 'glow-border-green',
        amber: 'glow-border-amber',
        red: 'glow-border-red',
        blue: 'glow-border-blue',
    };

    return (
        <div className={cn(
            "glass-card rounded-xl overflow-hidden",
            glowClasses[variant],
            className
        )}>
            {title && (
                <div className="px-4 py-3 border-b border-white/10 bg-black/20 flex items-center gap-3">
                    {icon}
                    <h3 className="text-sm font-bold hud-headline tracking-wider text-white/90">{title}</h3>
                    <div className="h-px flex-1 bg-gradient-to-r from-white/10 to-transparent" />
                </div>
            )}
            <div className="p-4">
                {children}
            </div>
        </div>
    );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================
export function IntelDossier({ result, metadata, regime, onClose }: IntelDossierProps) {
    const { toast } = useToast();
    const [activeTab, setActiveTab] = useState('overview');

    // Computed values
    const entryPrice = result.entryZone ? (result.entryZone.high + result.entryZone.low) / 2 : 0;
    const stopPrice = result.stopLoss || 0;
    const targetPrice = result.takeProfits?.[0] || 0;
    const displayPrice = result.entryZone?.low || 0;
    const isBullish = result.trendBias === 'BULLISH';
    const tier = getSignalTier(result.confidenceScore);

    // R:R calculation
    const riskAmount = Math.abs(entryPrice - stopPrice);
    const rewardAmount = Math.abs(targetPrice - entryPrice);
    const rrRatio = riskAmount > 0 ? (rewardAmount / riskAmount).toFixed(1) : '0';

    // Format price with appropriate decimals
    const formatPrice = (price: number) => `$${price.toFixed(price < 1 ? 5 : 2)}`;

    // Extract data
    const breakdown = result.confluence_breakdown;
    const factors = breakdown?.factors || [];
    const scannedTimeframes: string[] = metadata?.applied_timeframes || metadata?.appliedTimeframes || [];

    // Transform order_blocks (from smc_geometry) into grouped-by-timeframe format
    // Backend sends OB data per-signal in smc_geometry.order_blocks
    const orderBlocksList: any[] = (result as any).smc_geometry?.order_blocks || [];

    // DEBUG: Trace OB data sources
    console.log('[IntelDossier] OB Data Debug:', {
        hasSmcGeometry: !!(result as any).smc_geometry,
        orderBlocksCount: orderBlocksList.length,
        sampleOB: orderBlocksList[0],
        sampleOBTimeframe: orderBlocksList[0]?.timeframe,
        allOBTimeframes: orderBlocksList.map((ob: any) => ob.timeframe),
        // Also check for pre-transformed orderBlocks array
        preTransformedOBs: (result as any).orderBlocks?.length,
    });

    const orderBlocksByTimeframe: Record<string, any[]> = orderBlocksList.reduce((acc: Record<string, any[]>, ob: any) => {
        const tf = ob.timeframe?.toLowerCase() || 'unknown';
        if (!acc[tf]) acc[tf] = [];
        acc[tf].push({
            price_high: ob.high,
            price_low: ob.low,
            timestamp: ob.timestamp ? new Date(ob.timestamp).getTime() : Date.now(),
            type: ob.direction === 'bullish' ? 'bullish' : ob.type || 'bearish',
            mitigated: ob.mitigation_level > 0.5,
            timeframe: tf,
            freshness_score: ob.freshness_score,
            grade: ob.grade
        });
        return acc;
    }, {} as Record<string, any[]>);

    // DEBUG: Log the transformed OB structure
    console.log('[IntelDossier] OB Transform Result:', {
        timeframeKeys: Object.keys(orderBlocksByTimeframe),
        countsByTF: Object.entries(orderBlocksByTimeframe).map(([tf, obs]) => ({ tf, count: obs.length })),
        scannedTimeframes,
    });

    // Extract Liquidity Zones (EQH/EQL)
    const liquidityPools = (result as any).smc_geometry?.liquidity_pools || (result.metadata as any)?.liquidity_pools_list || [];
    // Also support checking flat equal_highs/lows if pools structure is different
    const equalHighs = (result as any).smc_geometry?.equal_highs || [];
    const equalLows = (result as any).smc_geometry?.equal_lows || [];

    const liquidityZones: any[] = [
        ...liquidityPools.map((p: any) => ({
            type: p.type === 'highs' ? 'EQH' : 'EQL',
            priceLevel: p.price ?? (p.level),
            strength: p.grade === 'A' ? 0.9 : p.grade === 'B' ? 0.7 : 0.5,
            ...p
        })),
        // Fallback for flat lists if pools empty
        ...(liquidityPools.length === 0 ? equalHighs.map((price: number) => ({
            type: 'EQH', priceLevel: price, strength: 0.6
        })) : []),
        ...(liquidityPools.length === 0 ? equalLows.map((price: number) => ({
            type: 'EQL', priceLevel: price, strength: 0.6
        })) : [])
    ];

    console.log('[IntelDossier] Liquidity Data:', {
        poolsCount: liquidityPools.length,
        eqhCount: equalHighs.length,
        eqlCount: equalLows.length,
        totalZones: liquidityZones.length
    });

    const scannerMode = metadata?.mode || 'surgical';

    const copySignal = () => {
        const text = `🎯 SIGNAL: ${result.pair} ${result.trendBias}\nEntry: ${formatPrice(entryPrice)}\nStop: ${formatPrice(stopPrice)}\nTarget: ${formatPrice(targetPrice)}`;
        navigator.clipboard.writeText(text);
        toast({ title: 'Signal Copied', description: 'Trade parameters copied to clipboard' });
    };

    return (
        <div className="min-h-full flex flex-col glass-card relative">
            {/* Close Button (All Screens) */}
            {onClose && (
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 z-50 p-2 bg-black/40 hover:bg-red-500/20 rounded-full border border-white/10 hover:border-red-500/50 text-white/60 hover:text-red-400 transition-all duration-300"
                    title="Close Dossier"
                >
                    <XCircle size={24} weight="light" />
                </button>
            )}

            {/* Hero Header - Tactical HUD Style */}
            <div className="p-4 md:p-6 border-b border-[var(--accent)]/20 bg-gradient-to-r from-[var(--accent)]/10 via-transparent to-transparent relative overflow-hidden">
                {/* Subtle animated scan line */}
                <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-30">
                    <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-[var(--accent)] to-transparent animate-scan-line" />
                </div>
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 relative z-10">
                    <div className="flex items-center gap-4">
                        <div>
                            <div className="flex items-center gap-3 mb-1">
                                <h1 className="text-2xl md:text-4xl font-bold hud-headline hud-text-green">{result.pair}</h1>
                                <Badge variant="outline" className={cn(
                                    "text-xs px-2 py-0.5 border font-mono tracking-wider",
                                    isBullish ? "border-green-500/50 text-green-400 bg-green-500/10" : "border-red-500/50 text-red-400 bg-red-500/10"
                                )}>
                                    {result.trendBias}
                                </Badge>
                                <TierBadge confidenceScore={result.confidenceScore} size="sm" />
                            </div>
                            <div className="flex items-center gap-4 text-sm text-muted-foreground font-mono">
                                <span>Ref: <span className="text-white font-bold">{formatPrice(displayPrice)}</span></span>
                                <span className="w-px h-3 bg-white/20" />
                                <RegimeIndicator regime={regime} size="xs" compact />
                            </div>
                        </div>
                    </div>

                    <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={copySignal} className="font-mono text-xs border-white/10 hover:bg-white/5 gap-2">
                            <Copy size={14} /> COPY
                        </Button>
                        <Button size="sm" className="bg-[var(--accent)] text-black hover:bg-[var(--accent)]/90 font-bold hud-headline tracking-wider gap-2 shadow-[0_0_15px_rgba(0,255,170,0.3)]">
                            <Crosshair size={16} weight="bold" /> EXECUTE
                        </Button>
                    </div>
                </div>
            </div>

            {/* Tabs Container */}
            <div className="flex-1 overflow-hidden flex flex-col">
                <Tabs.Root value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
                    {/* Tab Navigation */}
                    <div className="px-4 md:px-6 pt-4 pb-3 border-b border-[var(--accent)]/20 bg-black/40">
                        <Tabs.List className="flex flex-wrap gap-2">
                            <Tabs.Trigger value="overview" className="tab-trigger flex items-center gap-2">
                                <ChartLineUp size={18} weight="bold" /> OVERVIEW
                            </Tabs.Trigger>
                            <Tabs.Trigger value="intel" className="tab-trigger flex items-center gap-2">
                                <ShieldWarning size={18} weight="bold" /> INTEL
                            </Tabs.Trigger>
                            <Tabs.Trigger value="plan" className="tab-trigger flex items-center gap-2">
                                <Crosshair size={18} weight="bold" /> TRADE PLAN
                            </Tabs.Trigger>
                            <Tabs.Trigger value="context" className="tab-trigger flex items-center gap-2">
                                <Lightbulb size={18} weight="bold" /> CONTEXT
                            </Tabs.Trigger>
                        </Tabs.List>
                    </div>

                    {/* Tab Content - Scrollable */}
                    <div className="flex-1 overflow-y-auto p-4 md:p-6 scrollbar-thin scrollbar-thumb-[#00ff88]/20 scrollbar-track-transparent">

                        {/* ================================================================ */}
                        {/* TAB 1: OVERVIEW */}
                        {/* ================================================================ */}
                        <Tabs.Content value="overview" className="mt-0 space-y-6 animate-in fade-in duration-200">

                            {/* Metrics Row - 4 columns */}
                            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                                <MetricCard label="Confluence" value={`${result.confidenceScore}%`} color={result.confidenceScore >= 80 ? 'green' : 'amber'} />
                                <MetricCard label="Risk:Reward" value={`${rrRatio}:1`} color="white" />
                                <MetricCard label="Regime" value={breakdown?.regime?.toUpperCase() || 'UNKNOWN'} color="cyan" />
                                <MetricCard label="Trade Type" value={result.classification || 'SWING'} color="purple" />
                            </div>

                            {/* Status Badges Row */}
                            <div className="flex flex-wrap gap-2">
                                <StatusBadge label="HTF ALIGNED" active={breakdown?.htf_aligned ?? false} />
                                <StatusBadge label="BTC GATE" active={breakdown?.btc_impulse_gate ?? true} />
                                {breakdown?.synergy_bonus && breakdown.synergy_bonus > 0 && (
                                    <div className="px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
                                        +{breakdown.synergy_bonus.toFixed(1)} SYNERGY
                                    </div>
                                )}
                                {breakdown?.conflict_penalty && breakdown.conflict_penalty > 0 && (
                                    <div className="px-3 py-1.5 rounded-full bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-mono">
                                        -{breakdown.conflict_penalty.toFixed(1)} CONFLICT
                                    </div>
                                )}
                            </div>

                            {/* Market Context - 2 columns */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <Section title="Zone Position" icon={<Target size={16} className="text-cyan-400" />}>
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            {isBullish ? (
                                                <TrendUp size={24} className="text-green-400" weight="bold" />
                                            ) : (
                                                <TrendDown size={24} className="text-red-400" weight="bold" />
                                            )}
                                            <span className="text-lg font-bold text-white">
                                                {isBullish ? 'DISCOUNT' : 'PREMIUM'}
                                            </span>
                                        </div>
                                        <Badge variant="outline" className="text-xs font-mono">
                                            Entry Zone
                                        </Badge>
                                    </div>
                                </Section>

                                <Section title="Session Timing" icon={<Clock size={16} className="text-amber-400" />}>
                                    <div className="flex items-center justify-between">
                                        <span className="text-white font-mono">
                                            {getSessionInfo()}
                                        </span>
                                        <div className={cn(
                                            "w-2 h-2 rounded-full",
                                            isKillZoneActive() ? "bg-green-500 animate-pulse" : "bg-gray-500"
                                        )} />
                                    </div>
                                </Section>
                            </div>

                            {/* Chart Grid */}
                            <Section title="Multi-Timeframe Analysis" icon={<ChartLineUp size={16} className="text-[var(--accent)]" />} variant="green">
                                {scannedTimeframes.length > 0 ? (
                                    <MultiTimeframeChartGrid
                                        symbol={result.pair}
                                        mode={scannerMode}
                                        timeframes={scannedTimeframes}
                                        orderBlocksByTimeframe={orderBlocksByTimeframe}
                                        liquidityZones={liquidityZones}
                                        entryPrice={entryPrice}
                                        stopLoss={stopPrice}
                                        takeProfit={targetPrice}
                                    />
                                ) : (
                                    <div className="aspect-video w-full rounded-lg border border-white/10 overflow-hidden">
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
                            </Section>
                        </Tabs.Content>

                        {/* ================================================================ */}
                        {/* TAB 2: INTEL & RISKS */}
                        {/* ================================================================ */}
                        <Tabs.Content value="intel" className="mt-0 space-y-6 animate-in fade-in duration-200">

                            {/* Factor Breakdown + Scorecard - 2 columns */}
                            <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
                                {/* Factor Bars - 3/5 width */}
                                <Section title="Confluence Factors" icon={<Gauge size={16} className="text-[var(--accent)]" />} variant="green" className="lg:col-span-3">
                                    <div className="space-y-3">
                                        {factors.length > 0 ? (
                                            factors
                                                .sort((a, b) => b.weighted_score - a.weighted_score)
                                                .slice(0, 6)
                                                .map((factor, i) => (
                                                    <FactorBar key={i} factor={factor} />
                                                ))
                                        ) : (
                                            <div className="text-muted-foreground text-sm text-center py-4">
                                                No factor data available
                                            </div>
                                        )}
                                    </div>
                                </Section>

                                {/* Scorecard - 2/5 width */}
                                <Section title="Quality Scorecard" icon={<CheckCircle size={16} className="text-emerald-400" />} className="lg:col-span-2">
                                    <div className="space-y-3">
                                        <div className="text-center py-2">
                                            <div className="text-4xl font-bold text-white font-mono">
                                                {result.confidenceScore}
                                            </div>
                                            <div className="text-xs text-muted-foreground uppercase tracking-wider">Total Score</div>
                                        </div>
                                        <div className="space-y-2 text-sm">
                                            <ScoreRow label="Base Score" value={breakdown?.total_score ? (breakdown.total_score - (breakdown.synergy_bonus || 0) + (breakdown.conflict_penalty || 0)).toFixed(0) : '--'} />
                                            <ScoreRow label="Synergy Bonus" value={`+${breakdown?.synergy_bonus?.toFixed(1) || '0'}`} color="green" />
                                            <ScoreRow label="Conflict Penalty" value={`-${breakdown?.conflict_penalty?.toFixed(1) || '0'}`} color="red" />
                                            <div className="h-px bg-white/10 my-2" />
                                            <ScoreRow label="Comparative Rank" value="TOP 15%" color="green" />
                                        </div>
                                    </div>
                                </Section>
                            </div>

                            {/* Risk Warnings */}
                            <Section title="Risk Factors" icon={<Warning size={16} className="text-amber-400" />} variant="amber">
                                <WarningsContext results={[result]} metadata={metadata} embedded />
                            </Section>
                        </Tabs.Content>

                        {/* ================================================================ */}
                        {/* TAB 3: TRADE PLAN */}
                        {/* ================================================================ */}
                        <Tabs.Content value="plan" className="mt-0 space-y-6 animate-in fade-in duration-200">

                            {/* Entry/Stop/TP Cards - 3 columns */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <PlanCard title="ENTRY ZONE" value={formatPrice(entryPrice)} type="entry" subtitle={`Zone: ±${((result.entryZone?.high || 0) - (result.entryZone?.low || 0)).toFixed(2)}`} />
                                <PlanCard title="STOP LOSS" value={formatPrice(stopPrice)} type="stop" subtitle={`${((Math.abs(entryPrice - stopPrice) / entryPrice) * 100).toFixed(2)}% risk`} />
                                <PlanCard title="TAKE PROFIT" value={formatPrice(targetPrice)} type="target" subtitle={`${rrRatio}R reward`} />
                            </div>

                            {/* Target Ladder */}
                            {result.takeProfits && result.takeProfits.length > 0 && (
                                <Section title="Target Ladder" icon={<Target size={16} className="text-green-400" />} variant="green">
                                    <div className="space-y-2">
                                        {result.takeProfits.map((tp, i) => {
                                            const tpRR = riskAmount > 0 ? ((tp - entryPrice) / riskAmount).toFixed(1) : '0';
                                            const allocation = [50, 30, 20][i] || 10;
                                            const targetMeta = (result.metadata as any)?.targets?.[i];

                                            return (
                                                <div key={i} className="flex items-center gap-4 p-3 rounded-lg bg-black/40 border border-green-500/20">
                                                    <span className="text-xs font-mono text-green-400 bg-green-500/20 px-2 py-1 rounded font-bold">
                                                        TP{i + 1}
                                                    </span>
                                                    <span className="text-lg font-bold font-mono text-white flex-shrink-0">
                                                        {formatPrice(tp)}
                                                    </span>
                                                    {/* Allocation bar */}
                                                    <div className="flex-1 h-2 bg-black/60 rounded-full overflow-hidden">
                                                        <div
                                                            className="h-full bg-gradient-to-r from-green-600 to-green-400 rounded-full"
                                                            style={{ width: `${allocation}%` }}
                                                        />
                                                    </div>
                                                    <span className="text-xs text-muted-foreground font-mono w-12">{allocation}%</span>
                                                    <span className="text-xs text-green-400 font-mono w-12">{tpRR}R</span>
                                                    {targetMeta?.rationale && (
                                                        <span className="text-xs text-muted-foreground font-mono truncate max-w-[200px]">
                                                            {targetMeta.rationale}
                                                        </span>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                </Section>
                            )}

                            {/* Execution Details - 2 columns */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <Section title="Entry Details" icon={<Info size={16} className="text-blue-400" />} variant="blue">
                                    <div className="space-y-2 text-sm">
                                        {/* Show actual entry structure from OB/FVG metadata */}
                                        {(() => {
                                            const entryStructure = (result.metadata as any)?.entry_structure;
                                            const structureTf = entryStructure?.timeframe?.toUpperCase() || result.timeframe || '1H';
                                            const structureType = entryStructure?.type || 'Zone';
                                            const zoneHigh = entryStructure?.zone_high;
                                            const zoneLow = entryStructure?.zone_low;
                                            return (
                                                <>
                                                    <DetailRow label="Entry Structure" value={`${structureTf} ${structureType}`} />
                                                    {zoneHigh && zoneLow && (
                                                        <DetailRow
                                                            label="Entry Zone Range"
                                                            value={`${formatPrice(zoneLow)} - ${formatPrice(zoneHigh)}`}
                                                        />
                                                    )}
                                                </>
                                            );
                                        })()}
                                        <DetailRow label="Classification" value={result.classification || 'SWING'} />
                                        <DetailRow label="Conviction" value={result.conviction_class || 'B'} />
                                    </div>
                                </Section>

                                <Section title="Stop Details" icon={<ShieldWarning size={16} className="text-red-400" />} variant="red">
                                    <div className="space-y-2 text-sm">
                                        <DetailRow label="Stop Buffer" value={`${result.usedStopBufferAtr?.toFixed(2) || '0.5'} ATR`} />
                                        {result.altStopLevel && (
                                            <DetailRow label="Alt Stop" value={formatPrice(result.altStopLevel)} />
                                        )}
                                        <DetailRow label="Liq Risk" value={result.liqRiskBand?.toUpperCase() || 'MODERATE'} />
                                    </div>
                                </Section>
                            </div>

                            {/* Strategy Note */}
                            {result.rationale && (
                                <Section title="Strategy Note" icon={<Lightbulb size={16} className="text-yellow-400" />}>
                                    <p className="text-sm text-muted-foreground leading-relaxed">
                                        {result.rationale}
                                    </p>
                                </Section>
                            )}
                        </Tabs.Content>

                        {/* ================================================================ */}
                        {/* TAB 4: CONTEXT */}
                        {/* ================================================================ */}
                        <Tabs.Content value="context" className="mt-0 space-y-6 animate-in fade-in duration-200">

                            {/* Why This Signal Passed */}
                            <Section title="Why This Signal Passed" icon={<CheckCircle size={16} className="text-green-400" />} variant="green">
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                                    <CriteriaCard
                                        label="Confluence Score"
                                        passed={result.confidenceScore >= 65}
                                        detail={`${result.confidenceScore}% ≥ 65% threshold`}
                                    />
                                    <CriteriaCard
                                        label="Valid Trade Plan"
                                        passed={!!entryPrice && !!stopPrice}
                                        detail="Entry, stop, targets computed"
                                    />
                                    <CriteriaCard
                                        label="Risk:Reward"
                                        passed={parseFloat(rrRatio) >= 1.5}
                                        detail={`${rrRatio}:1 ≥ 1.5:1 minimum`}
                                    />
                                    <CriteriaCard
                                        label="Directional Clarity"
                                        passed={result.trendBias !== 'NEUTRAL'}
                                        detail={`${result.trendBias} bias confirmed`}
                                    />
                                    <CriteriaCard
                                        label="HTF Alignment"
                                        passed={breakdown?.htf_aligned ?? true}
                                        detail="Multi-timeframe confluence"
                                    />
                                    <CriteriaCard
                                        label="BTC Gate"
                                        passed={breakdown?.btc_impulse_gate ?? true}
                                        detail="BTC impulse check passed"
                                    />
                                </div>
                            </Section>

                            {/* Recommendations Grid */}
                            <Section title="Recommendations" icon={<Lightbulb size={16} className="text-blue-400" />} variant="blue">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    {tier.tier === 'TOP' && (
                                        <RecommendationCard
                                            type="action"
                                            title="High Priority Signal"
                                            description="TOP tier (80%+) - prioritize this setup"
                                        />
                                    )}
                                    {parseFloat(rrRatio) >= 3 && (
                                        <RecommendationCard
                                            type="action"
                                            title="Excellent R:R"
                                            description={`${rrRatio}:1 ratio - strong asymmetric opportunity`}
                                        />
                                    )}
                                    <RecommendationCard
                                        type="tip"
                                        title="Verify Before Entry"
                                        description="Confirm price action at entry zone"
                                    />
                                    <RecommendationCard
                                        type="consider"
                                        title="Position Sizing"
                                        description={tier.tier === 'SOLID' ? 'Consider half-size for SOLID tier' : 'Standard position size appropriate'}
                                    />
                                </div>
                            </Section>

                            {/* Scan Summary */}
                            <Section title="Scan Summary" icon={<Info size={16} className="text-muted-foreground" />}>
                                <div className="flex flex-wrap gap-4 text-sm text-muted-foreground font-mono">
                                    <span>Mode: <span className="text-white">{scannerMode.toUpperCase()}</span></span>
                                    <span className="text-white/20">|</span>
                                    <span>Timeframes: <span className="text-white">{scannedTimeframes.length || 'N/A'}</span></span>
                                    <span className="text-white/20">|</span>
                                    <span>Min Score: <span className="text-white">{metadata?.effectiveMinScore || 65}%</span></span>
                                </div>
                            </Section>
                        </Tabs.Content>

                    </div>
                </Tabs.Root>
            </div>
        </div>
    );
}

// ============================================================================
// HELPER COMPONENTS
// ============================================================================

function MetricCard({ label, value, color }: { label: string; value: string; color: string }) {
    const colorStyles: Record<string, { text: string; glow: string; border: string }> = {
        green: { text: 'hud-text-green', glow: 'shadow-[0_0_15px_rgba(0,255,136,0.2)]', border: 'border-[var(--accent)]/30' },
        amber: { text: 'hud-text-amber', glow: 'shadow-[0_0_15px_rgba(255,194,102,0.15)]', border: 'border-amber-500/30' },
        red: { text: 'hud-text-red', glow: 'shadow-[0_0_15px_rgba(255,102,102,0.15)]', border: 'border-red-500/30' },
        cyan: { text: 'text-cyan-400', glow: 'shadow-[0_0_15px_rgba(0,200,255,0.15)]', border: 'border-cyan-500/30' },
        purple: { text: 'text-purple-400', glow: 'shadow-[0_0_15px_rgba(168,85,247,0.15)]', border: 'border-purple-500/30' },
        white: { text: 'text-white', glow: '', border: 'border-white/20' },
    };

    const style = colorStyles[color] || colorStyles.white;

    return (
        <div className={cn(
            "glass-card-subtle p-4 rounded-xl border flex flex-col items-center justify-center text-center gap-1 transition-all duration-300 hover:scale-[1.02]",
            style.border, style.glow
        )}>
            <div className={cn("text-2xl font-bold hud-headline tracking-tighter tabular-nums", style.text)}>{value}</div>
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">{label}</div>
        </div>
    );
}

function StatusBadge({ label, active }: { label: string; active: boolean }) {
    return (
        <div className={cn(
            "px-3 py-1.5 rounded-full text-xs font-mono flex items-center gap-2 transition-all",
            active
                ? "bg-emerald-500/10 border border-emerald-500/30 text-emerald-400"
                : "bg-red-500/10 border border-red-500/30 text-red-400"
        )}>
            <div className={cn("w-2 h-2 rounded-full", active ? "bg-emerald-500 animate-pulse" : "bg-red-500")} />
            {label}
        </div>
    );
}

function FactorBar({ factor }: { factor: { name: string; score: number; weight: number; rationale: string; weighted_score: number } }) {
    const scorePercent = Math.min(100, Math.max(0, factor.score));
    const isStrong = factor.score >= 70;
    const isMedium = factor.score >= 40;

    const color = isStrong ? 'emerald' : isMedium ? 'amber' : 'red';
    const Icon = isStrong ? CheckCircle : isMedium ? Warning : XCircle;

    return (
        <div className="flex items-center gap-3 group">
            <div className={cn("p-1 rounded-full bg-black/40 border",
                isStrong ? "border-emerald-500/30 text-emerald-400" :
                    isMedium ? "border-amber-500/30 text-amber-400" :
                        "border-red-500/30 text-red-400"
            )}>
                <Icon size={12} weight="fill" />
            </div>

            <div className="flex-1 space-y-1">
                <div className="flex justify-between items-center">
                    <span className="text-[10px] font-mono text-white/90 w-32 truncate uppercase tracking-tight">
                        {factor.name.replace(/_/g, ' ')}
                    </span>
                    <span className={cn("text-[10px] font-bold font-mono", `text-${color}-400`)}>
                        {factor.score.toFixed(0)}/100
                    </span>
                </div>

                <div className="h-1.5 bg-black/60 rounded-full overflow-hidden border border-white/5">
                    <div
                        className={cn(
                            "h-full rounded-full transition-all duration-500 shadow-[0_0_8px_rgba(0,0,0,0.5)]",
                            isStrong ? "bg-gradient-to-r from-emerald-600 to-emerald-400" :
                                isMedium ? "bg-gradient-to-r from-amber-600 to-amber-400" :
                                    "bg-gradient-to-r from-red-600 to-red-400"
                        )}
                        style={{ width: `${scorePercent}%` }}
                    />
                </div>
            </div>
        </div>
    );
}

function PlanCard({ title, value, type, subtitle }: { title: string; value: string; type: 'entry' | 'stop' | 'target'; subtitle?: string }) {
    const styles = {
        entry: {
            border: 'border-blue-500/30',
            text: 'text-blue-400',
            glow: 'shadow-[0_0_20px_rgba(59,130,246,0.15)]',
            icon: '►'
        },
        stop: {
            border: 'border-red-500/30',
            text: 'hud-text-red',
            glow: 'shadow-[0_0_20px_rgba(239,68,68,0.15)]',
            icon: '■'
        },
        target: {
            border: 'border-green-500/30',
            text: 'hud-text-green',
            glow: 'shadow-[0_0_20px_rgba(0,255,136,0.15)]',
            icon: '★'
        },
    }[type];

    return (
        <div className={cn(
            "glass-card-subtle p-5 rounded-xl border flex flex-col items-center gap-2 transition-all duration-300 hover:scale-[1.02]",
            styles.border, styles.glow
        )}>
            <span className="text-xs hud-headline uppercase tracking-widest text-muted-foreground flex items-center gap-2">
                <span className={styles.text}>{styles.icon}</span> {title}
            </span>
            <span className={cn("text-2xl md:text-3xl font-bold hud-headline tabular-nums", styles.text)}>{value}</span>
            {subtitle && <span className="text-xs text-muted-foreground font-mono">{subtitle}</span>}
        </div>
    );
}

function ScoreRow({ label, value, color }: { label: string; value: string; color?: 'green' | 'red' }) {
    return (
        <div className="flex justify-between items-center">
            <span className="text-muted-foreground">{label}</span>
            <span className={cn("font-mono font-bold", color === 'green' ? 'text-emerald-400' : color === 'red' ? 'text-red-400' : 'text-white')}>
                {value}
            </span>
        </div>
    );
}

function DetailRow({ label, value }: { label: string; value: string }) {
    return (
        <div className="flex justify-between items-center">
            <span className="text-muted-foreground">{label}</span>
            <span className="font-mono text-white">{value}</span>
        </div>
    );
}

function CriteriaCard({ label, passed, detail }: { label: string; passed: boolean; detail: string }) {
    return (
        <div className={cn(
            "p-3 rounded-lg border flex items-start gap-3",
            passed ? "bg-green-500/5 border-green-500/20" : "bg-red-500/5 border-red-500/20"
        )}>
            {passed ? (
                <CheckCircle size={18} className="text-green-400 flex-shrink-0 mt-0.5" weight="fill" />
            ) : (
                <Warning size={18} className="text-red-400 flex-shrink-0 mt-0.5" weight="fill" />
            )}
            <div>
                <div className="text-sm font-medium text-white">{label}</div>
                <div className="text-xs text-muted-foreground">{detail}</div>
            </div>
        </div>
    );
}

function RecommendationCard({ type, title, description }: { type: 'action' | 'consider' | 'tip'; title: string; description: string }) {
    const styles = {
        action: { bg: 'bg-green-500/5', border: 'border-green-500/20', icon: <Target size={16} className="text-green-400" />, badge: 'text-green-400' },
        consider: { bg: 'bg-amber-500/5', border: 'border-amber-500/20', icon: <Lightning size={16} className="text-amber-400" />, badge: 'text-amber-400' },
        tip: { bg: 'bg-blue-500/5', border: 'border-blue-500/20', icon: <Lightbulb size={16} className="text-blue-400" />, badge: 'text-blue-400' },
    }[type];

    return (
        <div className={cn("p-3 rounded-lg border flex items-start gap-3", styles.bg, styles.border)}>
            {styles.icon}
            <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-white">{title}</span>
                    <span className={cn("text-[10px] uppercase font-mono", styles.badge)}>{type}</span>
                </div>
                <p className="text-xs text-muted-foreground">{description}</p>
            </div>
        </div>
    );
}

// Helper functions
function getSessionInfo(): string {
    const hour = new Date().getHours();
    if (hour >= 8 && hour < 12) return 'London Session';
    if (hour >= 12 && hour < 17) return 'NY/London Overlap';
    if (hour >= 17 && hour < 21) return 'NY Session';
    if (hour >= 21 || hour < 3) return 'Asian Session';
    return 'Off-Hours';
}

function isKillZoneActive(): boolean {
    const hour = new Date().getHours();
    return (hour >= 8 && hour < 11) || (hour >= 13 && hour < 16);
}
