import { CircleNotch, Binoculars, Lightning, Crosshair, Ghost, Star, Target, ShieldCheck, TrendUp, Clock } from '@phosphor-icons/react';
import { Badge } from '@/components/ui/badge';
import { useScanner } from '@/context/ScannerContext';
import { api } from '@/utils/api';
import { useEffect, useState } from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import { motion, AnimatePresence } from 'framer-motion';
import { ModeVisuals } from './ModeVisuals';

// Mode display configurations
const MODE_CONFIG = {
    overwatch: {
        icon: Binoculars,
        color: 'text-cyan-400',
        bgClass: 'bg-cyan-600/10',
        borderClass: 'border-cyan-500/20',
        glowClass: 'shadow-[0_0_20px_rgba(0,255,200,0.15)]',
        tagline: 'STRATEGIC MACRO POSITIONING',
        range: '1W · 1D → 4H',
        description: 'Deep-spectrum scanner designed to identify high-value swing setups aligned with weekly and daily market structure. Filters specifically for institutional accumulation zones and A+ macro opportunities.',
        bullets: [
            'Requires Weekly & Daily structure alignment',
            'Enforces institutional-grade 2:1+ R:R ratio',
            'Filters for high-timeframe order blocks',
            'Ideal for: Patient Swing Traders'
        ],
    },
    strike: {
        icon: Lightning,
        color: 'text-amber-400',
        bgClass: 'bg-amber-600/10',
        borderClass: 'border-amber-500/20',
        glowClass: 'shadow-[0_0_20px_rgba(255,170,0,0.15)]',
        tagline: 'HIGH-FREQUENCY MOMENTUM',
        range: '4H · 1H → 5m',
        description: 'Aggressive volatile-market scanner that hunts for rapid intraday expansions. Prioritizes signal frequency and execution speed over perfect structure, capturing reduced-timeframe breakouts.',
        bullets: [
            'Scans 4H/1H down to 5m structure',
            'Captures rapid momentum expansions',
            'Minimum 1.2:1 R:R for quick scalps',
            'Ideal for: Active Momentum Traders'
        ],
    },
    surgical: {
        icon: Crosshair,
        color: 'text-purple-400',
        bgClass: 'bg-purple-600/10',
        borderClass: 'border-purple-500/20',
        glowClass: 'shadow-[0_0_20px_rgba(170,100,255,0.15)]',
        tagline: 'PRECISION STRIKE OPERATIONS',
        range: '15m · 5m → 1m',
        description: 'Sniper-class scanner focused on entries with minimal drawdown. Enforces tight invalidation levels and clean market structure to maximize capital efficiency on lower timeframes.',
        bullets: [
            'Pinpoint entries on 15m/5m execution',
            'Tight invalidation levels (Stop-Loss)',
            'Requires 1.5:1+ R:R verification',
            'Ideal for: Precision Scalpers'
        ],
    },
    stealth: {
        icon: Ghost,
        color: 'text-violet-400',
        bgClass: 'bg-violet-600/10',
        borderClass: 'border-violet-500/20',
        glowClass: 'shadow-[0_0_20px_rgba(140,100,255,0.15)]',
        tagline: 'ADAPTIVE HYBRID RECON',
        range: 'Daily · 4H → 15m',
        description: 'A balanced tactical scanner blending swing mechanics with intraday precision. Versatile algorithm that adapts to diverse market conditions, filtering for high-probability pivot zones.',
        bullets: [
            'Multi-timeframe analysis (Daily to 5m)',
            'Balanced risk parameters (1.8:1 R:R)',
            'Filters for highest probability zones',
            'Ideal for: Hybrid Day/Swing Traders'
        ],
    },
};

// Mode recommendation logic based on market regime
function getModeRecommendation(modeName: string, regime: string | null): { recommended: boolean; reason: string } {
    if (!regime) return { recommended: false, reason: '' };

    const regimeLower = regime.toLowerCase();

    if (regimeLower.includes('trend') || regimeLower.includes('expansion')) {
        if (modeName === 'overwatch') return { recommended: true, reason: 'Trending market' };
        if (modeName === 'stealth') return { recommended: true, reason: 'Good for trends' };
    }

    if (regimeLower.includes('range') || regimeLower.includes('coil') || regimeLower.includes('sideways')) {
        if (modeName === 'strike') return { recommended: true, reason: 'Intraday plays' };
        if (modeName === 'surgical') return { recommended: true, reason: 'Precision scalps' };
    }

    if (regimeLower.includes('volatile') || regimeLower.includes('explosive')) {
        if (modeName === 'strike') return { recommended: true, reason: 'High volatility' };
    }

    return { recommended: false, reason: '' };
}

interface ScannerModeTabsProps {
    recommendation?: {
        mode: string;
        reason: string;
        warning: string | null;
        confidence: string;
        dominance?: {
            btc: number;
            alt: number;
            stable: number;
        };
    };
}

export function ScannerModeTabs({ recommendation: propRecommendation }: ScannerModeTabsProps) {
    const { scannerModes, selectedMode, setSelectedMode, scanConfig, setScanConfig } = useScanner();
    const [marketRegime, setMarketRegime] = useState<string | null>(null);
    const [activeSegment, setActiveSegment] = useState<'btc' | 'alt' | 'stable'>('btc');

    // Fetch market regime on mount
    useEffect(() => {
        api.getMarketRegime().then((res) => {
            if (res.data?.composite) {
                setMarketRegime(res.data.composite);
            }
        }).catch(() => { });
    }, []);

    if (scannerModes.length === 0) {
        return (
            <div className="flex items-center justify-center p-12">
                <CircleNotch size={40} className="animate-spin text-accent" />
            </div>
        );
    }

    const currentModeName = selectedMode?.name || 'overwatch';
    const currentConfig = MODE_CONFIG[currentModeName as keyof typeof MODE_CONFIG] || MODE_CONFIG.overwatch;

    const handleModeChange = (modeName: string) => {
        const mode = scannerModes.find(m => m.name === modeName);
        if (mode) {
            console.log(`[ScannerModeTabs] Mode selected: ${modeName}`);
            setSelectedMode(mode);
            setScanConfig({
                ...scanConfig,
                sniperMode: mode.name as any,
                timeframes: mode.timeframes,
            });
        }
    };

    // Helper to format regime label
    const formatRegimeLabel = (label: string) => {
        const map: Record<string, string> = {
            'choppy_risk_off': 'CHOPPY (RISK OFF)',
            'bullish_risk_on': 'BULLISH (RISK ON)',
            'bearish_risk_off': 'BEARISH (RISK OFF)',
            'chaotic_volatile': 'CHAOTIC VOLATILITY',
            'range_coiling': 'RANGE COILING',
        };
        if (map[label]) return map[label];
        return label.replace(/_/g, ' ').toUpperCase();
    };

    const getRegimeColor = (label: string) => {
        if (label.includes('strong_up') || label.includes('bullish') || label.includes('risk_on')) return 'text-[#00ff88] border-[#00ff88]/30 bg-[#00ff88]/10';
        if (label.includes('strong_down') || label.includes('bearish') || label.includes('risk_off') || label.includes('chaotic')) return 'text-red-400 border-red-500/30 bg-red-500/10';
        return 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10';
    };

    return (
        <Tabs.Root value={currentModeName} onValueChange={handleModeChange} className="w-full">
            {/* Market regime indicator */}
            {marketRegime && (
                <div className="mb-6 flex flex-col items-center gap-2">
                    <span className="text-xs font-mono text-muted-foreground uppercase tracking-widest pl-1">Global Market Context</span>
                    <div className={`inline-flex items-center gap-3 px-4 py-2 rounded-lg border backdrop-blur-sm ${getRegimeColor(marketRegime)}`}>
                        <div className="w-2 h-2 rounded-full bg-current animate-pulse" />
                        <span className="text-lg lg:text-xl font-black italic tracking-tighter">
                            {formatRegimeLabel(marketRegime)}
                        </span>
                    </div>

                    {propRecommendation?.dominance && (
                        <div className="w-full mt-6 bg-black/20 rounded-2xl p-6 border border-white/5 shadow-2xl relative overflow-hidden group">
                            {/* Ambient Background Glow */}
                            <div className="absolute inset-x-0 -top-20 h-40 bg-gradient-to-b from-white/5 to-transparent opacity-50 pointer-events-none" />

                            <div className="relative z-10 flex flex-col items-center">
                                {/* Combined Title & Season Indicator */}
                                <div className="flex items-center gap-3 mb-8">
                                    <div className="h-px w-8 bg-gradient-to-r from-transparent to-white/10" />
                                    <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-[0.3em] opacity-80">Capital Flow</span>
                                    <span className="text-muted-foreground/30">—</span>
                                    {propRecommendation.dominance.btc > 55 ?
                                        <span className="text-xs text-orange-400 font-extrabold tracking-[0.2em] animate-pulse">BTC SEASON</span> :
                                        propRecommendation.dominance.alt > 35 ?
                                            <span className="text-xs text-purple-400 font-extrabold tracking-[0.2em] animate-pulse">ALT SEASON</span> :
                                            <span className="text-xs text-emerald-400 font-extrabold tracking-[0.2em]">RISK NEUTRAL</span>
                                    }
                                    <div className="h-px w-8 bg-gradient-to-l from-transparent to-white/10" />
                                </div>

                                {/* Advanced Doughnut Chart */}
                                <div className="relative w-48 h-48 flex items-center justify-center">
                                    <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90 overflow-visible">
                                        {/* Background Track */}
                                        <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="10" />

                                        {/* Segments calculation: circumference ~264 (r=42) */}
                                        {/* BTC Segment */}
                                        <motion.circle
                                            cx="50" cy="50" r="42"
                                            fill="none"
                                            stroke="url(#btcGradient)"
                                            strokeWidth={activeSegment === 'btc' ? 14 : 10}
                                            strokeLinecap="round"
                                            initial={{ strokeDasharray: "0 264" }}
                                            animate={{ strokeDasharray: `${(propRecommendation.dominance.btc / 100) * 264} 264` }}
                                            transition={{ duration: 1.5, ease: "circOut" }}
                                            className={`cursor-pointer transition-all duration-300 ${activeSegment === 'btc' ? 'drop-shadow-[0_0_12px_rgba(249,115,22,0.6)]' : 'opacity-60 hover:opacity-100 hover:stroke-[12px]'}`}
                                            onClick={() => setActiveSegment('btc')}
                                        />

                                        {/* ALT Segment - offset by BTC */}
                                        <motion.circle
                                            cx="50" cy="50" r="42"
                                            fill="none"
                                            stroke="url(#altGradient)"
                                            strokeWidth={activeSegment === 'alt' ? 14 : 10}
                                            strokeLinecap="round"
                                            initial={{ strokeDasharray: "0 264", strokeDashoffset: 0 }}
                                            animate={{
                                                strokeDasharray: `${(propRecommendation.dominance.alt / 100) * 264} 264`,
                                                strokeDashoffset: -((propRecommendation.dominance.btc / 100) * 264)
                                            }}
                                            transition={{ duration: 1.5, delay: 0.2, ease: "circOut" }}
                                            className={`cursor-pointer transition-all duration-300 ${activeSegment === 'alt' ? 'drop-shadow-[0_0_12px_rgba(168,85,247,0.6)]' : 'opacity-60 hover:opacity-100 hover:stroke-[12px]'}`}
                                            onClick={() => setActiveSegment('alt')}
                                        />

                                        {/* STABLE Segment - offset by BTC + ALT */}
                                        <motion.circle
                                            cx="50" cy="50" r="42"
                                            fill="none"
                                            stroke="url(#stableGradient)"
                                            strokeWidth={activeSegment === 'stable' ? 14 : 10}
                                            strokeLinecap="round"
                                            initial={{ strokeDasharray: "0 264", strokeDashoffset: 0 }}
                                            animate={{
                                                strokeDasharray: `${(propRecommendation.dominance.stable / 100) * 264} 264`,
                                                strokeDashoffset: -(((propRecommendation.dominance.btc + propRecommendation.dominance.alt) / 100) * 264)
                                            }}
                                            transition={{ duration: 1.5, delay: 0.4, ease: "circOut" }}
                                            className={`cursor-pointer transition-all duration-300 ${activeSegment === 'stable' ? 'drop-shadow-[0_0_12px_rgba(16,185,129,0.6)]' : 'opacity-60 hover:opacity-100 hover:stroke-[12px]'}`}
                                            onClick={() => setActiveSegment('stable')}
                                        />

                                        <defs>
                                            <linearGradient id="btcGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                                                <stop offset="0%" stopColor="#ea580c" />
                                                <stop offset="100%" stopColor="#f97316" />
                                            </linearGradient>
                                            <linearGradient id="altGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                                                <stop offset="0%" stopColor="#9333ea" />
                                                <stop offset="100%" stopColor="#a855f7" />
                                            </linearGradient>
                                            <linearGradient id="stableGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                                                <stop offset="0%" stopColor="#059669" />
                                                <stop offset="100%" stopColor="#10b981" />
                                            </linearGradient>
                                        </defs>
                                    </svg>

                                    {/* Center Percentage Display */}
                                    <AnimatePresence mode="wait">
                                        <motion.div
                                            key={activeSegment}
                                            initial={{ opacity: 0, scale: 0.8, filter: 'blur(8px)' }}
                                            animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }}
                                            exit={{ opacity: 0, scale: 1.1, filter: 'blur(8px)' }}
                                            transition={{ duration: 0.3, ease: 'easeOut' }}
                                            className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none"
                                        >
                                            <div className={`text-3xl lg:text-4xl font-black tracking-tighter drop-shadow-lg ${activeSegment === 'btc' ? 'text-orange-400' :
                                                activeSegment === 'alt' ? 'text-purple-400' :
                                                    'text-emerald-400'
                                                }`}>
                                                {Math.round(propRecommendation.dominance[activeSegment])}%
                                            </div>
                                            <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest mt-1">
                                                {activeSegment === 'btc' ? 'BTC Dom' : activeSegment === 'alt' ? 'Alt Dom' : 'Stable Dom'}
                                            </div>
                                        </motion.div>
                                    </AnimatePresence>
                                </div>

                                {/* Minimal Color Indicator Dots (Interaction Hint) */}
                                <div className="flex gap-4 mt-8 opacity-50">
                                    <div className={`w-1.5 h-1.5 rounded-full ${activeSegment === 'btc' ? 'bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.8)]' : 'bg-white/10'}`} />
                                    <div className={`w-1.5 h-1.5 rounded-full ${activeSegment === 'alt' ? 'bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.8)]' : 'bg-white/10'}`} />
                                    <div className={`w-1.5 h-1.5 rounded-full ${activeSegment === 'stable' ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]' : 'bg-white/10'}`} />
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Tab Triggers - Horizontal on desktop, scrollable on mobile */}
            <Tabs.List className="flex flex-wrap lg:flex-nowrap gap-2 lg:gap-3 mb-6 lg:mb-8 overflow-x-auto pb-2 px-1">
                {scannerModes.map((mode) => {
                    const config = MODE_CONFIG[mode.name as keyof typeof MODE_CONFIG];
                    const ModeIcon = config?.icon || Binoculars;
                    const isActive = currentModeName === mode.name;
                    const recommendation = getModeRecommendation(mode.name, marketRegime);

                    return (
                        <Tabs.Trigger
                            key={mode.name}
                            value={mode.name}
                            className={`
                                relative flex-1 min-w-[140px] lg:min-w-0
                                flex items-center justify-center gap-2 lg:gap-3
                                px-4 lg:px-6 py-3 lg:py-4
                                font-mono text-sm lg:text-base font-bold
                                uppercase tracking-wider
                                rounded-lg border transition-all duration-300
                                ${isActive
                                    ? `${config?.bgClass} ${config?.borderClass} ${config?.glowClass} ${config?.color}`
                                    : 'bg-background/40 border-border/40 text-muted-foreground hover:text-foreground hover:border-border'
                                }
                            `}
                        >
                            <ModeIcon size={isActive ? 22 : 18} weight={isActive ? 'fill' : 'regular'} />
                            <span className="hidden sm:inline">{mode.name}</span>

                            {/* Recommendation badge */}
                            {recommendation.recommended && !isActive && (
                                <Star size={14} weight="fill" className="text-accent absolute -top-1 -right-1" />
                            )}
                        </Tabs.Trigger>
                    );
                })}
            </Tabs.List>

            {/* Tab Content */}
            <AnimatePresence mode="wait">
                {scannerModes.map((mode) => {
                    if (mode.name !== currentModeName) return null;
                    const config = MODE_CONFIG[mode.name as keyof typeof MODE_CONFIG] || MODE_CONFIG.overwatch;
                    const ModeIcon = config.icon;
                    const recommendation = getModeRecommendation(mode.name, marketRegime);

                    return (
                        <Tabs.Content key={mode.name} value={mode.name} asChild forceMount>
                            <motion.div
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -10 }}
                                transition={{ duration: 0.3 }}
                                className={`glass-card ${config.borderClass} p-0 rounded-xl overflow-hidden`}
                            >
                                {/* Two-column layout on desktop, stacked on mobile */}
                                <div className="grid grid-cols-1 lg:grid-cols-12 gap-0">

                                    {/* Left: 3D Visualization */}
                                    <div className="relative h-[300px] lg:h-auto lg:col-span-5 bg-black/60 border-r border-white/5 overflow-hidden group">
                                        {/* Gradient overlay for depth */}
                                        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent z-10 pointer-events-none" />
                                        <ModeVisuals activeMode={mode.name} />
                                    </div>

                                    {/* Right: Mode Details */}
                                    <div className="lg:col-span-7 p-6 lg:p-8 space-y-8 flex flex-col justify-center">

                                        {/* Header Section */}
                                        <div className="space-y-4">
                                            <div className="flex items-center justify-between">
                                                <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-md ${config.bgClass} border ${config.borderClass}`}>
                                                    <div className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" style={{ color: 'currentColor' }} />
                                                    <span className={`text-xs font-mono font-bold uppercase tracking-widest ${config.color}`}>
                                                        {mode.name} ARMED
                                                    </span>
                                                </div>

                                                {recommendation.recommended && (
                                                    <Badge className="bg-accent/10 text-accent border-accent/20 px-3 py-1">
                                                        <Star size={12} weight="fill" className="mr-1.5" />
                                                        RECOMMENDED
                                                    </Badge>
                                                )}
                                            </div>

                                            <div>
                                                <h3 className={`text-2xl lg:text-3xl font-bold uppercase tracking-wide mb-2 ${config.color}`}>
                                                    {config.tagline}
                                                </h3>
                                                <p className="text-base lg:text-lg text-muted-foreground leading-relaxed">
                                                    {config.description}
                                                </p>
                                            </div>
                                        </div>

                                        {/* Capabilities List */}
                                        <div className="space-y-3 p-4 rounded-xl bg-white/5 border border-white/5">
                                            {config.bullets.map((bullet, i) => (
                                                <div key={i} className="flex items-start gap-3">
                                                    <ShieldCheck size={18} className={`mt-0.5 shrink-0 ${config.color}`} weight="duotone" />
                                                    <span className="text-sm lg:text-base text-foreground/90">{bullet}</span>
                                                </div>
                                            ))}
                                        </div>

                                        {/* Technical Stats Grid */}
                                        <div className="grid grid-cols-3 gap-4 lg:gap-6 pt-2">
                                            <div>
                                                <div className="flex items-center gap-1.5 text-xs text-muted-foreground uppercase tracking-wider mb-2">
                                                    <Clock size={14} /> Timeframes
                                                </div>
                                                <div className={`font-mono text-sm lg:text-base font-medium ${config.color}`}>
                                                    {config.range}
                                                </div>
                                            </div>

                                            <div>
                                                <div className="flex items-center gap-1.5 text-xs text-muted-foreground uppercase tracking-wider mb-2">
                                                    <Target size={14} /> Min Score
                                                </div>
                                                <div className={`font-mono text-xl lg:text-2xl font-bold ${config.color}`}>
                                                    {mode.min_confluence_score}%
                                                </div>
                                            </div>

                                            <div>
                                                <div className="flex items-center gap-1.5 text-xs text-muted-foreground uppercase tracking-wider mb-2">
                                                    <TrendUp size={14} /> Profile
                                                </div>
                                                <div className="font-mono text-sm lg:text-base font-medium capitalize truncate">
                                                    {mode.profile.replace(/_/g, ' ')}
                                                </div>
                                            </div>
                                        </div>

                                    </div>
                                </div>
                            </motion.div>
                        </Tabs.Content>
                    );
                })}
            </AnimatePresence>
        </Tabs.Root>
    );
}
