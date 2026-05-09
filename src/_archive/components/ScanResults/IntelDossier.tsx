import { ScanResult } from '@/utils/mockData';
import { LightweightChart } from '@/components/charts/LightweightChart';
import { ShieldWarning, TrendUp, TrendDown, X, Calculator, Wallet, WarningCircle, ChartPieSlice, Lightning, Target, Skull } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { useState, useMemo } from 'react';

interface IntelDossierProps {
    result: ScanResult;
    onClose: () => void;
}

export function IntelDossier({ result, onClose }: IntelDossierProps) {
    const isLong = result.trendBias === 'BULLISH';
    const mode = result.sniper_mode?.toLowerCase() || 'tactical';

    let chartTimeframe = '4h';
    if (mode.includes('surgical')) chartTimeframe = '15m';
    if (mode.includes('strike')) chartTimeframe = '1h';
    if (mode.includes('stealth')) chartTimeframe = '4h';
    if (mode.includes('overwatch')) chartTimeframe = '4h';

    const formatPrice = (p: number) => p.toLocaleString(undefined, {
        minimumFractionDigits: result.pair.includes('JPY') ? 2 : 4,
        maximumFractionDigits: result.pair.includes('JPY') ? 2 : 4,
    });

    // ── CALCULATOR STATE ──
    const [accountBalance, setAccountBalance] = useState(10000);
    const [riskAmount, setRiskAmount] = useState(200);
    const [usePercentage, setUsePercentage] = useState(false);
    const [customLeverage, setCustomLeverage] = useState<number | null>(null);

    const metaLeverage = (result as any).metadata?.leverage || 1;
    const leverage = customLeverage ?? metaLeverage;

    const entryPrice = result.entryZone.high;
    const stopPrice = result.stopLoss;
    const priceGap = Math.abs(entryPrice - stopPrice);

    const calc = useMemo(() => {
        const finalRisk = usePercentage ? accountBalance * (riskAmount / 100) : riskAmount;
        if (priceGap === 0 || finalRisk === 0 || accountBalance === 0) return null;

        const positionSizeCoins = finalRisk / priceGap;
        const notionalValue = positionSizeCoins * entryPrice;
        const marginRequired = notionalValue / leverage;
        const stopDistancePct = (priceGap / entryPrice) * 100;
        const riskPct = (finalRisk / accountBalance) * 100;
        const effectiveLeverage = notionalValue / accountBalance;

        // Liquidation (isolated margin, ~0.4% MMR — Bybit standard)
        const mmr = 0.004;
        const liqPrice = isLong
            ? entryPrice * (1 + mmr - (1 / leverage))
            : entryPrice * (1 - mmr + (1 / leverage));

        const distToLiq = Math.abs((entryPrice - liqPrice) / entryPrice) * 100;
        const stopToLiqDist = Math.abs((stopPrice - liqPrice) / stopPrice) * 100;
        const isLiqBeforeStop = isLong ? liqPrice >= stopPrice : liqPrice <= stopPrice;

        const profits = result.takeProfits.map(tp =>
            Math.abs(tp - entryPrice) * positionSizeCoins
        );

        return {
            finalRisk,
            positionSizeCoins,
            notionalValue,
            marginRequired,
            stopDistancePct,
            riskPct,
            effectiveLeverage,
            liqPrice,
            distToLiq,
            stopToLiqDist,
            isLiqBeforeStop,
            profits,
        };
    }, [accountBalance, riskAmount, usePercentage, leverage, entryPrice, stopPrice, priceGap, isLong, result.takeProfits]);

    const liqDanger = calc && (calc.isLiqBeforeStop || calc.distToLiq < 3);
    const liqWarning = calc && !liqDanger && calc.distToLiq < 8;
    const overRisk = calc && calc.riskPct > 3;

    return (
        <div className="w-full mt-8 animate-in slide-in-from-top-4 duration-500 fade-in">

            {/* ── DIVIDER ── */}
            <div className="flex items-center gap-4 mb-8">
                <div className="h-px flex-1 bg-gradient-to-r from-transparent via-[#00ff88]/50 to-transparent" />
                <div className="px-4 py-1.5 rounded-full border border-[#00ff88]/30 bg-[#00ff88]/5 text-[#00ff88] text-xs font-mono font-black tracking-[0.25em] shadow-[0_0_20px_rgba(0,255,136,0.15)]">
                    ◈ MISSION INTEL ◈
                </div>
                <div className="h-px flex-1 bg-gradient-to-r from-transparent via-[#00ff88]/50 to-transparent" />
            </div>

            <div className="relative w-full bg-[#040404] border border-zinc-800 rounded-2xl overflow-hidden shadow-[0_0_60px_rgba(0,0,0,0.8)]">

                {/* Subtle scanline texture */}
                <div className="absolute inset-0 pointer-events-none opacity-[0.015] bg-[repeating-linear-gradient(0deg,transparent,transparent_2px,rgba(255,255,255,1)_2px,rgba(255,255,255,1)_3px)] z-0" />

                {/* Close */}
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 z-20 p-2 rounded-lg bg-black/50 text-zinc-500 hover:text-white hover:bg-zinc-800 transition-all border border-transparent hover:border-zinc-700 hover:shadow-[0_0_10px_rgba(255,255,255,0.05)]"
                >
                    <X size={20} />
                </button>

                {/* ══════════════════════════════════════════
                    MISSION HEADER
                ══════════════════════════════════════════ */}
                <div className="relative p-8 border-b border-zinc-800/60 bg-gradient-to-br from-zinc-900/40 to-black/20 overflow-hidden">
                    {/* Glow blob behind score */}
                    <div className={cn(
                        "absolute right-0 top-0 w-96 h-full opacity-10 blur-3xl pointer-events-none",
                        isLong ? "bg-green-400" : "bg-red-500"
                    )} />

                    <div className="relative flex flex-col md:flex-row md:items-center justify-between gap-6">
                        <div className="flex items-center gap-6">
                            <div className={cn(
                                "relative flex items-center justify-center w-20 h-20 rounded-2xl border-2",
                                isLong
                                    ? "bg-green-500/10 border-green-500/30 text-green-400 shadow-[0_0_30px_rgba(34,197,94,0.2)]"
                                    : "bg-red-500/10 border-red-500/30 text-red-400 shadow-[0_0_30px_rgba(239,68,68,0.2)]"
                            )}>
                                {isLong ? <TrendUp size={40} weight="fill" /> : <TrendDown size={40} weight="fill" />}
                            </div>
                            <div className="flex flex-col">
                                <h2 className="text-6xl md:text-8xl font-black italic tracking-tighter text-white mb-2 drop-shadow-[0_0_30px_rgba(255,255,255,0.15)] hover:text-[#00ff88] transition-all cursor-default select-none">
                                    {result.pair}
                                </h2>
                                <div className="flex items-center gap-3 flex-wrap">
                                    <span className={cn(
                                        "px-3 py-1 text-sm font-black font-mono uppercase tracking-wider rounded-lg border",
                                        isLong
                                            ? "text-green-400 border-green-500/40 bg-green-500/10 shadow-[0_0_12px_rgba(34,197,94,0.15)]"
                                            : "text-red-400 border-red-500/40 bg-red-500/10 shadow-[0_0_12px_rgba(239,68,68,0.15)]"
                                    )}>
                                        {isLong ? '▲' : '▼'} {result.trendBias}
                                    </span>
                                    <span className="w-1.5 h-1.5 rounded-full bg-zinc-700" />
                                    <span className="text-zinc-400 font-mono text-sm tracking-widest uppercase font-bold">
                                        {result.classification} PROTOCOL
                                    </span>
                                    {result.sniper_mode && (
                                        <>
                                            <span className="w-1.5 h-1.5 rounded-full bg-zinc-700" />
                                            <span className="text-amber-500 font-mono text-xs tracking-[0.2em] font-black uppercase">
                                                {result.sniper_mode} ENGINE
                                            </span>
                                        </>
                                    )}
                                </div>
                            </div>
                        </div>

                        <div className="flex flex-col items-end gap-1">
                            <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-black">Confidence Score</div>
                            <div className={cn(
                                "text-6xl font-mono font-black tracking-tighter",
                                result.confidenceScore >= 85 ? "text-[#00ff88] drop-shadow-[0_0_20px_rgba(0,255,136,0.4)]"
                                    : result.confidenceScore >= 70 ? "text-yellow-400 drop-shadow-[0_0_20px_rgba(250,204,21,0.3)]"
                                        : "text-orange-400 drop-shadow-[0_0_20px_rgba(251,146,60,0.3)]"
                            )}>
                                {result.confidenceScore.toFixed(1)}%
                            </div>
                            <div className="text-[10px] font-mono text-zinc-600 tracking-wider">
                                EV: {result.riskReward ? (result.riskReward * (result.confidenceScore / 100)).toFixed(2) : '—'}R EXPECTED
                            </div>
                        </div>
                    </div>
                </div>

                <div className="flex flex-col">

                    {/* SECTOR 1 & 2 */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-zinc-800/60 border-b border-zinc-800/60">

                        {/* SECTOR 1: ANALYSIS */}
                        <div className="p-8 space-y-5">
                            <SectorHeader label="SECTOR 1" title="ANALYSIS" color="green" />

                            {/* Confluence chips */}
                            {result.confluence_breakdown?.factors && result.confluence_breakdown.factors.length > 0 && (
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <span className="text-[10px] font-black uppercase tracking-widest text-zinc-500">Confluence Drivers</span>
                                        <span className="text-[10px] font-mono text-zinc-600 bg-zinc-900 px-2 py-0.5 rounded border border-zinc-800">
                                            {result.confluence_breakdown.factors.length} factors
                                        </span>
                                    </div>
                                    <div className="grid grid-cols-2 gap-1.5">
                                        {result.confluence_breakdown.factors
                                            .sort((a, b) => (b.score * b.weight) - (a.score * a.weight))
                                            .slice(0, 6)
                                            .map((factor, idx) => (
                                                <div key={idx} className="flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg bg-zinc-900/80 border border-zinc-800/60 group/chip hover:border-[#00ff88]/20 hover:bg-zinc-900 transition-all">
                                                    <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide truncate group-hover/chip:text-zinc-200 transition-colors">
                                                        {factor.name.replace(/_/g, ' ')}
                                                    </span>
                                                    <div className="flex items-center gap-2 flex-shrink-0">
                                                        <div className="w-10 h-1 bg-zinc-800 rounded-full overflow-hidden">
                                                            <div
                                                                className={cn("h-full rounded-full transition-all", factor.score >= 80 ? "bg-[#00ff88]/70" : factor.score >= 50 ? "bg-yellow-400/70" : "bg-zinc-600")}
                                                                style={{ width: `${factor.score}%` }}
                                                            />
                                                        </div>
                                                        <span className={cn("text-[10px] font-mono font-black w-7 text-right", factor.score >= 80 ? "text-[#00ff88]" : factor.score >= 50 ? "text-yellow-400" : "text-zinc-500")}>
                                                            {factor.score.toFixed(0)}%
                                                        </span>
                                                    </div>
                                                </div>
                                            ))}
                                    </div>
                                    {result.confluence_breakdown.factors.length > 6 && (
                                        <div className="text-[10px] text-zinc-600 font-mono text-center">
                                            +{result.confluence_breakdown.factors.length - 6} more factors · expand row for full breakdown
                                        </div>
                                    )}
                                </div>
                            )}

                            <div className="h-px bg-gradient-to-r from-transparent via-zinc-800 to-transparent" />

                            {/* Rationale */}
                            <div className="space-y-3">
                                {result.rationale
                                    ? result.rationale.split('\n\n').map((line, i) => {
                                        const colonIdx = line.indexOf(':');
                                        if (colonIdx === -1) return <p key={i} className="text-zinc-400 text-sm pl-3">{line}</p>;
                                        const label = line.substring(0, colonIdx).trim();
                                        const rest = line.substring(colonIdx + 1).trim();
                                        const pipeIdx = rest.indexOf(' | ');
                                        const desc = pipeIdx !== -1 ? rest.substring(0, pipeIdx).trim() : rest;
                                        const stats = pipeIdx !== -1 ? rest.substring(pipeIdx + 3).trim() : null;
                                        return (
                                            <div key={i} className="flex flex-col gap-1 pl-3 border-l-2 border-zinc-800 hover:border-[#00ff88]/40 transition-colors group/bullet">
                                                <span className="text-[10px] font-black uppercase tracking-widest text-[#00ff88]/60 group-hover/bullet:text-[#00ff88] transition-colors">{label}</span>
                                                <span className="text-sm text-zinc-300 leading-relaxed">{desc}</span>
                                                {stats && <span className="inline-block mt-0.5 px-2 py-0.5 rounded bg-zinc-800/80 border border-zinc-700/60 text-[10px] font-mono text-zinc-400 w-fit">{stats}</span>}
                                            </div>
                                        );
                                    })
                                    : <p className="text-zinc-400 text-sm pl-3 border-l-2 border-zinc-800">{`Price action shows a strong ${isLong ? 'demand' : 'supply'} imbalance on the ${chartTimeframe.toUpperCase()} timeframe.`}</p>
                                }
                            </div>
                        </div>

                        {/* SECTOR 2: EXECUTION PLAN */}
                        <div className="p-8 space-y-6 bg-zinc-900/10">
                            <SectorHeader label="SECTOR 2" title="EXECUTION PLAN" color="amber" />

                            <div className="grid grid-cols-2 gap-6">
                                <div>
                                    <div className="text-[10px] uppercase text-cyan-400 font-black mb-1 font-mono tracking-widest">Entry Zone</div>
                                    <div className="text-2xl font-mono font-bold text-cyan-300 tracking-tight">
                                        {formatPrice(result.entryZone.low)}
                                    </div>
                                    <div className="text-sm font-mono text-cyan-400/50">to {formatPrice(result.entryZone.high)}</div>
                                </div>

                                <div className="text-right">
                                    <div className="text-[10px] uppercase text-red-400 font-black mb-1 font-mono tracking-widest">Stop Loss</div>
                                    <div className="text-2xl font-mono font-bold text-red-400 tracking-tight">
                                        {formatPrice(result.stopLoss)}
                                    </div>
                                    {result.stopLossRationale && (
                                        <div className="text-[10px] text-zinc-500 font-mono mt-1 leading-tight ml-auto max-w-[160px]">
                                            {result.stopLossRationale}
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* TP Targets */}
                            <div className="rounded-xl bg-zinc-900/60 border border-zinc-800 shadow-inner overflow-hidden">
                                {result.takeProfits.map((tp, idx) => (
                                    <div key={idx} className={cn(
                                        "flex justify-between items-center px-4 py-3 border-b border-zinc-800/50 last:border-0 group/tp hover:bg-[#00ff88]/5 transition-colors",
                                        idx > 0 && "opacity-60 hover:opacity-100"
                                    )}>
                                        <div className="flex items-center gap-3">
                                            <div className={cn("w-1.5 h-1.5 rounded-full", idx === 0 ? "bg-[#00ff88] shadow-[0_0_6px_rgba(0,255,136,0.6)]" : "bg-[#00ff88]/40")} />
                                            <span className="text-[10px] font-black font-mono tracking-widest text-zinc-500 group-hover/tp:text-zinc-300 transition-colors uppercase">Target {idx + 1}</span>
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <span className="text-[10px] font-mono text-zinc-600">
                                                1:{((tp - result.entryZone.high) / (result.entryZone.high - result.stopLoss)).toFixed(1)}R
                                            </span>
                                            <span className={cn("font-mono text-lg font-bold", idx === 0 ? "text-[#00ff88]" : "text-[#00ff88]/70")}>
                                                {formatPrice(tp)}
                                            </span>
                                        </div>
                                    </div>
                                ))}
                            </div>

                            <div className="flex items-center justify-between py-2 border-t border-zinc-800/40">
                                <div className="text-xs uppercase font-black text-zinc-500 font-mono tracking-widest">Risk : Reward</div>
                                <div className="text-3xl font-mono font-black text-zinc-100">
                                    1 : <span className="text-[#00ff88] drop-shadow-[0_0_8px_rgba(0,255,136,0.4)]">{(result.riskReward || 2.5).toFixed(1)}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* SECTOR 4: CALCULATOR */}
                    <div className="border-b border-zinc-800/60 bg-black/60">
                        <div className="p-6 border-b border-zinc-800/40">
                            <SectorHeader label="SECTOR 4" title="PRECISION CALCULATOR" color="cyan" icon={<Calculator size={18} weight="duotone" />} />
                        </div>

                        <div className="grid grid-cols-1 lg:grid-cols-12 divide-y lg:divide-y-0 lg:divide-x divide-zinc-800/60">

                            <div className="lg:col-span-4 p-6 space-y-5">
                                <div className="grid grid-cols-1 gap-4">
                                    <CalcInput
                                        icon={<Wallet size={12} />}
                                        label="Account Balance"
                                        suffix="USD"
                                        value={accountBalance}
                                        onChange={setAccountBalance}
                                        placeholder="10000"
                                    />

                                    <div className="space-y-1.5">
                                        <div className="flex items-center justify-between px-1">
                                            <label className="flex items-center gap-1.5 text-[10px] font-black text-zinc-500 uppercase tracking-widest">
                                                <ChartPieSlice size={12} /> Risk Per Trade
                                            </label>
                                            <button
                                                onClick={() => setUsePercentage(!usePercentage)}
                                                className="text-[9px] font-black uppercase tracking-widest text-[#00ff88]/40 hover:text-[#00ff88] transition-colors border border-zinc-800 hover:border-[#00ff88]/30 px-2 py-0.5 rounded"
                                            >
                                                {usePercentage ? '→ USD' : '→ %'}
                                            </button>
                                        </div>
                                        <div className="relative">
                                            <input
                                                type="number"
                                                value={riskAmount}
                                                onChange={e => setRiskAmount(Number(e.target.value))}
                                                className="w-full bg-zinc-900/80 border border-zinc-800 focus:border-[#00ff88]/40 rounded-lg px-4 py-3 font-mono text-white text-sm focus:outline-none transition-colors shadow-inner pr-12"
                                            />
                                            <span className="absolute right-4 top-1/2 -translate-y-1/2 font-mono text-xs text-zinc-600">{usePercentage ? '%' : 'USD'}</span>
                                        </div>
                                    </div>

                                    <div className="space-y-1.5">
                                        <div className="flex items-center justify-between px-1">
                                            <label className="flex items-center gap-1.5 text-[10px] font-black text-zinc-500 uppercase tracking-widest">
                                                <Lightning size={12} /> Leverage
                                            </label>
                                        </div>
                                        <div className="relative">
                                            <input
                                                type="number"
                                                value={leverage}
                                                onChange={e => setCustomLeverage(Number(e.target.value))}
                                                min={1} max={125}
                                                className="w-full bg-zinc-900/80 border border-zinc-800 focus:border-amber-400/40 rounded-lg px-4 py-3 font-mono text-amber-300 text-sm font-bold focus:outline-none transition-colors shadow-inner pr-10"
                                            />
                                            <span className="absolute right-4 top-1/2 -translate-y-1/2 font-mono text-xs text-zinc-600">x</span>
                                        </div>
                                    </div>
                                </div>

                                {calc && (
                                    <div className="p-5 rounded-xl border border-zinc-800/60 bg-zinc-900/30 space-y-4">
                                        <div className="grid grid-cols-2 gap-x-4 gap-y-4">
                                            <Stat label="Max Drawdown" value={`$${calc.finalRisk.toLocaleString()}`} color="red" />
                                            <Stat label="Margin Required" value={`$${calc.marginRequired.toLocaleString(undefined, { maximumFractionDigits: 0 })}`} color="cyan" />
                                            <Stat label="Stop Distance" value={`${calc.stopDistancePct.toFixed(2)}%`} color="zinc" />
                                            <Stat label="Risk of Account" value={`${calc.riskPct.toFixed(2)}%`} color={calc.riskPct > 3 ? "red" : calc.riskPct > 1.5 ? "yellow" : "green"} />
                                        </div>
                                    </div>
                                )}
                            </div>

                            <div className="lg:col-span-8 p-6 flex flex-col gap-6">
                                {calc ? (
                                    <>
                                        <div className="flex flex-col md:flex-row gap-6">
                                            <div className="flex-1 bg-zinc-900/20 p-5 rounded-2xl border border-white/5 shadow-inner">
                                                <div className="flex items-center gap-2 mb-4">
                                                    <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                                                    <span className="text-[10px] font-black tracking-[0.2em] text-zinc-500 uppercase">Mission Payload</span>
                                                </div>
                                                <div className="text-5xl font-mono font-black text-white tracking-tighter mb-2">
                                                    {calc.positionSizeCoins.toLocaleString(undefined, { maximumFractionDigits: 3 })}
                                                    <span className="text-xl text-zinc-500 ml-2 font-bold">{result.pair.split('/')[0]}</span>
                                                </div>
                                                <div className="text-sm font-mono text-zinc-500">
                                                    Notional: <span className="text-zinc-300 font-bold">${calc.notionalValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                                                    <span className="mx-3 text-zinc-700">|</span>
                                                    Eff. Leverage: <span className="text-amber-400 font-bold">{calc.effectiveLeverage.toFixed(2)}x</span>
                                                </div>
                                            </div>

                                            <div className={cn(
                                                "flex-1 rounded-2xl border p-5 flex flex-col gap-3",
                                                liqDanger
                                                    ? "border-red-500/50 bg-red-500/8 shadow-[0_0_20px_rgba(239,68,68,0.1)]"
                                                    : "border-orange-500/25 bg-orange-500/5"
                                            )}>
                                                <div className="flex items-center gap-2">
                                                    <WarningCircle size={16} weight="fill" className={liqDanger ? "text-red-400" : "text-orange-400"} />
                                                    <span className={cn(
                                                        "text-[10px] font-black uppercase tracking-widest",
                                                        liqDanger ? "text-red-400" : "text-orange-400"
                                                    )}>
                                                        {liqDanger ? "LIQUIDATION DANGER" : "Liquidation Price"}
                                                    </span>
                                                </div>
                                                <div className={cn(
                                                    "text-3xl font-mono font-black tracking-tight",
                                                    liqDanger ? "text-red-400" : "text-orange-400"
                                                )}>
                                                    ${formatPrice(calc.liqPrice)}
                                                </div>
                                                <div className="grid grid-cols-2 gap-4 mt-1">
                                                    <div>
                                                        <div className="text-[9px] text-zinc-600 font-black uppercase mb-1">Distance</div>
                                                        <div className="text-sm font-mono font-bold text-zinc-300">{calc.distToLiq.toFixed(2)}%</div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        <div>
                                            <div className="flex items-center gap-2 mb-3">
                                                <Target size={14} className="text-[#00ff88]/60" />
                                                <span className="text-[10px] font-black tracking-[0.2em] text-zinc-500 uppercase">Objective Yields</span>
                                            </div>
                                            <div className="grid grid-cols-3 gap-3">
                                                {calc.profits.map((p, i) => (
                                                    <div key={i} className={cn(
                                                        "flex flex-col p-4 rounded-xl border group/yield hover:scale-[1.02] transition-all cursor-default",
                                                        i === 0
                                                            ? "border-[#00ff88]/30 bg-[#00ff88]/5 shadow-[0_0_15px_rgba(0,255,136,0.05)] hover:shadow-[0_0_20px_rgba(0,255,136,0.1)]"
                                                            : "border-zinc-800 bg-zinc-900/30 hover:border-zinc-700"
                                                    )}>
                                                        <span className="text-[9px] font-black text-zinc-600 uppercase tracking-widest mb-1.5">Target {i + 1}</span>
                                                        <span className={cn(
                                                            "text-xl font-mono font-black",
                                                            i === 0 ? "text-[#00ff88] drop-shadow-[0_0_8px_rgba(0,255,136,0.3)]" : "text-[#00ff88]/60"
                                                        )}>
                                                            +${p.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                                                        </span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </>
                                ) : (
                                    <div className="flex flex-col items-center justify-center h-full gap-3 text-center py-12">
                                        <Calculator size={32} className="text-zinc-700" />
                                        <p className="text-zinc-600 text-sm font-mono">Enter balance & risk to arm</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* SECTOR 3: SURVEILLANCE (Chart) */}
                    <div className="w-full h-[500px] border-t border-zinc-800 bg-black relative flex flex-col">
                        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10">
                            <SectorHeader label="SECTOR 3" title={`SURVEILLANCE (${chartTimeframe.toUpperCase()})`} color="blue" />
                        </div>
                        <div className="flex-1 w-full h-full relative">
                            <LightweightChart
                                symbol={result.pair}
                                timeframe={chartTimeframe}
                                orderBlocks={[]}
                                entryPrice={result.entryZone.high}
                                stopLoss={result.stopLoss}
                                takeProfit={result.takeProfits[0]}
                                className="h-full w-full border-none"
                                showLegend={false}
                                uniformOBColor={true}
                            />
                        </div>
                    </div>

                </div>
            </div>
        </div>
    );
}

// ◈ SECTOR HEADER Component
function SectorHeader({ label, title, color, icon }: { label: string; title: string; color: 'green' | 'amber' | 'cyan' | 'blue'; icon?: React.ReactNode }) {
    const colors = {
        green: 'text-[#00ff88] drop-shadow-[0_0_6px_rgba(0,255,136,0.4)]',
        amber: 'text-amber-400 drop-shadow-[0_0_6px_rgba(251,191,36,0.4)]',
        cyan: 'text-cyan-400 drop-shadow-[0_0_6px_rgba(34,211,238,0.4)]',
        blue: 'text-blue-400 drop-shadow-[0_0_6px_rgba(96,165,250,0.4)]',
    };
    return (
        <div className="flex items-center gap-3">
            <div className={cn("w-1.5 h-1.5 rounded-full",
                color === 'green' ? "bg-[#00ff88] shadow-[0_0_10px_#00ff88]" :
                    color === 'amber' ? "bg-amber-400 shadow-[0_0_10px_rgba(251,191,36,0.5)]" :
                        color === 'cyan' ? "bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.5)]" :
                            "bg-blue-400 shadow-[0_0_10px_rgba(96,165,250,0.5)]"
            )} />
            {icon && <span className={colors[color]}>{icon}</span>}
            <h3 className={cn("text-xs font-black tracking-[0.25em] uppercase", colors[color])}>
                ◈ {label}: <span className="font-black underline decoration-2 underline-offset-4">{title}</span>
            </h3>
        </div>
    );
}

function CalcInput({ icon, label, suffix, value, onChange, placeholder }: {
    icon: React.ReactNode; label: string; suffix: string;
    value: number; onChange: (v: number) => void; placeholder: string;
}) {
    return (
        <div className="space-y-2">
            <label className="flex items-center gap-1.5 text-[10px] font-black text-zinc-500 uppercase tracking-widest px-1">
                {icon} {label}
            </label>
            <div className="relative group/input">
                <input
                    type="number"
                    value={value}
                    onChange={e => onChange(Number(e.target.value))}
                    placeholder={placeholder}
                    className="w-full bg-zinc-900/80 border border-zinc-800 focus:border-[#00ff88]/40 rounded-lg pl-7 pr-16 py-4 font-mono text-white text-base focus:outline-none transition-all shadow-inner group-hover/input:bg-zinc-900/100 leading-none"
                />
                <span className="absolute right-5 top-1/2 -translate-y-1/2 font-mono text-xs text-zinc-600 group-focus-within/input:text-[#00ff88]/60 transition-colors uppercase font-bold tracking-widest">{suffix}</span>
            </div>
        </div>
    );
}

function Stat({ label, value, color }: { label: string; value: string; color: 'red' | 'green' | 'cyan' | 'yellow' | 'zinc' }) {
    const colorMap = {
        red: 'text-red-400',
        green: 'text-[#00ff88]',
        cyan: 'text-cyan-400',
        yellow: 'text-yellow-400',
        zinc: 'text-zinc-300',
    };
    return (
        <div className="group/stat pl-2 border-l border-zinc-800/50 hover:border-[#00ff88]/20 transition-colors">
            <div className="text-[9px] text-zinc-600 font-black uppercase tracking-[0.15em] mb-1.5 group-hover/stat:text-zinc-500 transition-colors">{label}</div>
            <div className={cn("text-base font-mono font-black", colorMap[color])}>{value}</div>
        </div>
    );
}
