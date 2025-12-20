import { Crosshair, Robot, Compass, Target } from '@phosphor-icons/react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import * as Tabs from '@radix-ui/react-tabs';
import { useState } from 'react';

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
}

const features: Feature[] = [
    {
        id: "scanner",
        title: "Reconnaissance",
        subtitle: "Manual Operations",
        description: "Multi-timeframe Smart Money Concept detection with institutional-grade confluence scoring.",
        bullets: [
            "Order blocks & Fair Value Gaps detection",
            "Liquidity sweep identification",
            "Break of Structure analysis",
            "Real-time confluence scoring"
        ],
        ctaText: "Configure Scanner",
        ctaLink: "/scanner/setup",
        icon: Crosshair,
        glowClass: "glow-border-green",
        iconColor: "text-accent"
    },
    {
        id: "bot",
        title: "Autonomous Bot",
        subtitle: "Automated Execution",
        description: "Hands-free trading execution with multi-layered quality gates and risk controls.",
        bullets: [
            "Automated entry & exit execution",
            "Dynamic position sizing",
            "Multi-tier stop loss management",
            "Real-time position monitoring"
        ],
        ctaText: "Configure Bot",
        ctaLink: "/bot/setup",
        icon: Robot,
        glowClass: "glow-border-green",
        iconColor: "text-primary"
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
        iconColor: "text-blue-400"
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
        iconColor: "text-warning"
    }
];

export function FeatureTabs() {
    const [activeTab, setActiveTab] = useState("scanner");

    return (
        <section className="relative py-24">
            <div className="max-w-6xl mx-auto px-4">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6 }}
                >
                    {/* Section Header */}
                    <div className="text-center mb-12">
                        <h2 className="hud-headline text-2xl md:text-3xl text-foreground mb-4">
                            Complete Trading Arsenal
                        </h2>
                        <p className="text-muted-foreground max-w-2xl mx-auto">
                            Four integrated modules working together to give you an edge in the market
                        </p>
                    </div>

                    <Tabs.Root value={activeTab} onValueChange={setActiveTab}>
                        {/* Tab Triggers */}
                        <Tabs.List className="flex flex-wrap justify-center gap-2 mb-8">
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
                        <div className="glass-card glow-border-green p-8 md:p-12 min-h-[400px]">
                            <AnimatePresence mode="wait">
                                {features.filter(f => f.id === activeTab).map((feature) => (
                                    <motion.div
                                        key={feature.id}
                                        initial={{ opacity: 0, x: 20 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        exit={{ opacity: 0, x: -20 }}
                                        transition={{ duration: 0.3 }}
                                        className="grid md:grid-cols-2 gap-12 items-center"
                                    >
                                        {/* Left: Icon & Title */}
                                        <div className="space-y-6">
                                            <div className={`inline-flex items-center justify-center w-20 h-20 glass-card-subtle ${feature.glowClass}`}>
                                                <feature.icon size={40} weight="bold" className={feature.iconColor} />
                                            </div>

                                            <div>
                                                <h3 className="hud-headline text-3xl font-bold text-foreground mb-2">
                                                    {feature.title}
                                                </h3>
                                                <p className={`text-sm tracking-widest uppercase ${feature.iconColor}`}>
                                                    {feature.subtitle}
                                                </p>
                                            </div>

                                            <p className="text-lg text-muted-foreground leading-relaxed">
                                                {feature.description}
                                            </p>

                                            <Link
                                                to={feature.ctaLink}
                                                className={`inline-flex items-center gap-2 px-6 py-3 glass-card ${feature.glowClass} hover:bg-white/5 transition-all group`}
                                            >
                                                <span className="font-bold tracking-wider">{feature.ctaText}</span>
                                                <span className="group-hover:translate-x-1 transition-transform">→</span>
                                            </Link>
                                        </div>

                                        {/* Right: Bullet Points */}
                                        <div className="space-y-4">
                                            {feature.bullets.map((bullet, index) => (
                                                <motion.div
                                                    key={bullet}
                                                    initial={{ opacity: 0, x: 20 }}
                                                    animate={{ opacity: 1, x: 0 }}
                                                    transition={{ duration: 0.3, delay: index * 0.1 }}
                                                    className="flex items-center gap-4 p-4 glass-card-subtle"
                                                >
                                                    <div className={`w-2 h-2 rounded-full ${feature.iconColor} bg-current`} />
                                                    <span className="text-foreground">{bullet}</span>
                                                </motion.div>
                                            ))}
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
