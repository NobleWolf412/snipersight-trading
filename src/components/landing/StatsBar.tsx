import { motion } from 'framer-motion';

interface Stat {
    value: string;
    label: string;
    color?: string;
}

const stats: Stat[] = [
    { value: "50+", label: "Trading Pairs", color: "text-accent" },
    { value: "5", label: "Scan Modes", color: "text-primary" },
    { value: "24/7", label: "Monitoring", color: "text-blue-400" },
    { value: "<12s", label: "Scan Speed", color: "text-warning" },
];

export function StatsBar() {
    return (
        <section className="relative py-12">
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6 }}
                className="max-w-6xl mx-auto px-4"
            >
                <div className="glass-card glow-border-green p-8">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
                        {stats.map((stat, index) => (
                            <motion.div
                                key={stat.label}
                                initial={{ opacity: 0, y: 10 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 0.4, delay: index * 0.1 }}
                                className="text-center"
                            >
                                <div className={`stat-number ${stat.color || 'text-foreground'}`}>
                                    {stat.value}
                                </div>
                                <div className="text-sm text-muted-foreground tracking-widest uppercase mt-2">
                                    {stat.label}
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </motion.div>
        </section>
    );
}
