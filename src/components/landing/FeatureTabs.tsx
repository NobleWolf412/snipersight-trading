import { Crosshair, Robot, Compass, Target } from '@phosphor-icons/react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import * as Tabs from '@radix-ui/react-tabs';
import { useState } from 'react';
import { ArsenalVisuals } from './ArsenalVisuals';

interface Feature {
    id: string;
    title: string;
    subtitle: string;
    description: string;
    bullets: string[];
    ctaText: string;
    ctaLink: string;
    icon: typeof Crosshair;
    glowClass: string;
    iconColor: string;
    hexColor: string;
}

const features: Feature[] = [
    {
        id: "scanner",
        title: "Reconnaissance",
        subtitle: "Manual Operations",
        description: "Multi-timeframe Smart Money Concept detection with institutional-grade confluence scoring.",
        bullets: [
            "Order blocks & FVG detection",
            "Liquidity sweep identification",
            "Break of Structure analysis",
            "Real-time confluence scoring"
        ],
        ctaText: "Configure Scanner",
        ctaLink: "/scanner/setup",
        icon: Crosshair,
        glowClass: "glow-border-green",
        iconColor: "text-accent",
        hexColor: "#00ff88"
    },
    {
        id: "bot",
        title: "Autonomous Bot",
        subtitle: "Automated Execution",
        description: "Hands-free trading execution with multi-layered quality gates and risk controls.",
        bullets: [
            "Automated entry & exit",
            "Dynamic position sizing",
            "Multi-tier stop loss management",
            "Real-time position monitoring"
        ],
        ctaText: "Configure Bot",
        ctaLink: "/bot/setup",
        icon: Robot,
        glowClass: "glow-border-green",
        iconColor: "text-primary",
        hexColor: "#00ff88"
    },
    {
        id: "intel",
        title: "Market Intel",
        subtitle: "AI Analysis",
        description: "Real-time market regime classification and dominance flow analysis.",
        bullets: [
            "Market regime detection",
            "BTC dominance tracking",
            "Sector rotation signals",
            "AI-powered trend analysis"
        ],
        ctaText: "View Intel",
        ctaLink: "/intel",
        icon: Compass,
        glowClass: "glow-border-blue",
        iconColor: "text-blue-400",
        hexColor: "#60a5fa"
    },
    {
        id: "training",
        title: "Training Ground",
        subtitle: "Simulation Mode",
        description: "Practice with simulated market data in a risk-free environment.",
        bullets: [
            "Paper trading simulation",
            "Strategy backtesting",
            "Performance analytics",
            "Risk-free learning"
        ],
        ctaText: "Enter Simulation",
        ctaLink: "/training",
        icon: Target,
        glowClass: "glow-border-amber",
        iconColor: "text-warning",
        hexColor: "#f59e0b"
    }
];

export function FeatureTabs() {
    const [activeTab, setActiveTab] = useState("scanner");

    return (
        <section className="relative py-24">
            <div className="max-w-7xl mx-auto px-4">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6 }}
                >
                    {/* Section Header */}
                    <div className="text-center mb-16">
                        <h2 className="hud-headline text-2xl md:text-3xl text-foreground mb-4">
                            Complete Trading Arsenal
                        </h2>
                        <p className="text-muted-foreground max-w-2xl mx-auto">
                            Four integrated modules working together to give you an edge in the market
                        </p>
                    </div>

                    <Tabs.Root value={activeTab} onValueChange={setActiveTab}>
                        {/* Tab Triggers */}
                        <Tabs.List className="flex flex-wrap justify-center gap-2 mb-12">
                            {features.map((feature) => (
                                <Tabs.Trigger
                                    key={feature.id}
                                    value={feature.id}
                                    className="tab-trigger"
                                >
                                    {feature.title}
                                </Tabs.Trigger>
                            ))}
                        </Tabs.List>

                        {/* Tab Content */}
                        <div className="glass-card glow-border-green p-6 md:p-12 min-h-[700px] flex items-center">
                            <AnimatePresence mode="wait">
                                {features.filter(f => f.id === activeTab).map((feature) => (
                                    <motion.div
                                        key={feature.id}
                                        initial={{ opacity: 0, scale: 0.95 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        exit={{ opacity: 0, scale: 0.95 }}
                                        transition={{ duration: 0.4 }}
                                        className="grid lg:grid-cols-2 gap-20 items-stretch w-full"
                                    >
                                        {/* Left: Content Column - MAXIMIZED SPACING */}
                                        <div className="flex flex-col justify-between items-center text-center py-4 h-full min-h-[600px]">

                                            {/* 1. Header Block */}
                                            <div className="flex flex-col items-center gap-8">
                                                <div className={`inline-flex items-center justify-center w-24 h-24 rounded-full glass-card ${feature.glowClass} flex-shrink-0 shadow-[0_0_40px_rgba(0,0,0,0.4)] border border-white/10 animate-pulse-slow`}>
                                                    <feature.icon size={48} weight="fill" className={feature.iconColor} />
                                                </div>
                                                <div>
                                                    <h3 className="hud-headline text-4xl lg:text-6xl font-bold text-foreground mb-4 leading-none uppercase tracking-tight drop-shadow-xl">
                                                        {feature.title}
                                                    </h3>
                                                    <div className="flex items-center justify-center gap-4 opacity-90">
                                                        <div className={`w-1.5 h-1.5 rounded-full ${feature.iconColor}`} />
                                                        <p className={`text-sm md:text-base font-mono tracking-[0.3em] uppercase ${feature.iconColor}`}>
                                                            {feature.subtitle}
                                                        </p>
                                                        <div className={`w-1.5 h-1.5 rounded-full ${feature.iconColor}`} />
                                                    </div>
                                                </div>
                                            </div>

                                            {/* 2. Description Block */}
                                            <div className="max-w-lg">
                                                <p className="text-xl md:text-2xl text-muted-foreground leading-relaxed font-light">
                                                    {feature.description}
                                                </p>
                                            </div>

                                            {/* 3. Bullets Block */}
                                            <div className="flex flex-col gap-6 items-center w-full">
                                                {feature.bullets.map((bullet, index) => (
                                                    <div key={bullet} className="flex items-center justify-center gap-4">
                                                        <div className={`w-2 h-2 ${feature.iconColor} bg-current flex-shrink-0 shadow-[0_0_10px_currentColor] rotate-45`} />
                                                        <span className="text-lg md:text-xl text-gray-200 font-mono tracking-wide leading-snug whitespace-nowrap">
                                                            {bullet}
                                                        </span>
                                                    </div>
                                                ))}
                                            </div>

                                            {/* 4. Button Block */}
                                            <div className="w-full flex justify-center pt-4">
                                                <Link
                                                    to={feature.ctaLink}
                                                    className="relative inline-flex items-center justify-center px-12 py-6 overflow-hidden font-bold text-white transition-all duration-300 bg-red-600 rounded-lg group hover:bg-red-500 ring-4 ring-red-900/20 shadow-[0_0_50px_rgba(220,38,38,0.5)] hover:shadow-[0_0_80px_rgba(220,38,38,0.8)] hover:scale-105"
                                                >
                                                    <div className="absolute inset-0 w-full h-full bg-gradient-to-br from-white/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                                                    <span className="relative uppercase tracking-[0.2em] text-lg drop-shadow-md flex items-center gap-3">
                                                        <span>{feature.ctaText}</span>
                                                        <span className="opacity-0 group-hover:opacity-100 transition-all duration-300 -translate-x-2 group-hover:translate-x-0">
                                                            →
                                                        </span>
                                                    </span>
                                                </Link>
                                            </div>

                                        </div>

                                        {/* Right: 3D Visualization */}
                                        <div className="relative h-full min-h-[600px] w-full bg-black/80 rounded-2xl overflow-hidden border border-white/10 shadow-[0_0_50px_rgba(0,0,0,0.5)]">
                                            {/* Hex Grid Pattern */}
                                            <div
                                                className="absolute inset-0 opacity-20 pointer-events-none"
                                                style={{
                                                    backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(255,255,255,0.15) 1px, transparent 0)',
                                                    backgroundSize: '24px 24px'
                                                }}
                                            />

                                            <ArsenalVisuals activeTab={activeTab} />

                                            {/* HUD Overlay System */}
                                            <div className="absolute inset-0 pointer-events-none">
                                                <div className="absolute top-0 left-0 right-0 h-10 border-b border-white/10 bg-gradient-to-b from-white/5 to-transparent flex items-center justify-between px-6">
                                                    <span className="text-[10px] font-mono text-white/40 tracking-widest">SYS.VISUAL.01</span>
                                                    <div className="flex gap-1">
                                                        <div className="w-1 h-1 bg-white/20 rounded-full" />
                                                        <div className="w-1 h-1 bg-white/20 rounded-full" />
                                                        <div className="w-1 h-1 bg-white/20 rounded-full" />
                                                    </div>
                                                </div>

                                                <div className="absolute top-1/2 left-10 w-2 h-2 border-t border-l border-white/30" />
                                                <div className="absolute top-1/2 right-10 w-2 h-2 border-t border-r border-white/30" />
                                                <div className="absolute bottom-10 left-1/2 w-2 h-2 border-b border-l border-white/30" />

                                                <div className="absolute bottom-6 right-6 px-3 py-1 border border-white/10 rounded-full bg-black/60 backdrop-blur text-xs font-mono text-emerald-500 flex items-center gap-2">
                                                    <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                                                    SYSTEM_ACTIVE
                                                </div>
                                            </div>
                                        </div>
                                    </motion.div>
                                ))}
                            </AnimatePresence>
                        </div>
                    </Tabs.Root>
                </motion.div>
            </div>
        </section>
    );
}
