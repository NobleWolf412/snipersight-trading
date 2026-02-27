import { useEffect, useState } from 'react';
import { Cpu, HardDrive, WifiHigh, Lightning, Activity } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

interface SystemVitalsProps {
    isScanning: boolean;
    apiLatency?: number; // ms
    targetsFound?: number;
    targetsTotal?: number;
    className?: string;
}

interface VitalGaugeProps {
    label: string;
    value: number;
    maxValue?: number;
    unit?: string;
    icon: React.ReactNode;
    color?: 'green' | 'amber' | 'red';
    animated?: boolean;
}

function VitalGauge({ label, value, maxValue = 100, unit = '%', icon, color = 'green', animated = false }: VitalGaugeProps) {
    const percentage = Math.min((value / maxValue) * 100, 100);

    const colorClasses = {
        green: {
            bar: 'bg-[#00ff88]',
            glow: 'shadow-[0_0_8px_rgba(0,255,136,0.5)]',
            text: 'text-[#00ff88]',
        },
        amber: {
            bar: 'bg-amber-500',
            glow: 'shadow-[0_0_8px_rgba(245,158,11,0.5)]',
            text: 'text-amber-400',
        },
        red: {
            bar: 'bg-red-500',
            glow: 'shadow-[0_0_8px_rgba(239,68,68,0.5)]',
            text: 'text-red-400',
        },
    };

    const colors = colorClasses[color];

    return (
        <div className="space-y-1.5">
            {/* Label row */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                    <span className={cn('opacity-60', colors.text)}>{icon}</span>
                    <span className="text-[10px] font-mono text-[#00ff88]/70 tracking-wider uppercase">{label}</span>
                </div>
                <span className={cn('text-xs font-mono font-bold tabular-nums', colors.text)}>
                    {Math.round(value)}{unit}
                </span>
            </div>

            {/* Bar */}
            <div className="h-1.5 bg-black/60 rounded-full overflow-hidden border border-[#00ff88]/20">
                <div
                    className={cn(
                        'h-full rounded-full transition-all duration-300',
                        colors.bar,
                        animated && colors.glow,
                        animated && 'animate-pulse'
                    )}
                    style={{ width: `${percentage}%` }}
                />
            </div>
        </div>
    );
}

export function SystemVitals({ isScanning, apiLatency = 50, targetsFound = 0, targetsTotal = 0, className = '' }: SystemVitalsProps) {
    const [metrics, setMetrics] = useState({
        cpu: 15,
        mem: 42,
        net: 28,
        api: apiLatency,
    });

    // Simulate fluctuating metrics when scanning
    useEffect(() => {
        if (!isScanning) {
            setMetrics({ cpu: 15, mem: 42, net: 28, api: apiLatency });
            return;
        }

        const interval = setInterval(() => {
            setMetrics(prev => ({
                cpu: Math.min(95, Math.max(20, prev.cpu + (Math.random() * 20 - 10))),
                mem: Math.min(85, Math.max(35, prev.mem + (Math.random() * 8 - 4))),
                net: Math.min(100, Math.max(15, prev.net + (Math.random() * 30 - 15))),
                api: Math.min(200, Math.max(20, prev.api + (Math.random() * 40 - 20))),
            }));
        }, 500);

        return () => clearInterval(interval);
    }, [isScanning, apiLatency]);

    const getCpuColor = () => metrics.cpu > 80 ? 'red' : metrics.cpu > 60 ? 'amber' : 'green';
    const getMemColor = () => metrics.mem > 80 ? 'red' : metrics.mem > 65 ? 'amber' : 'green';
    const getApiColor = () => metrics.api > 150 ? 'red' : metrics.api > 100 ? 'amber' : 'green';

    return (
        <div className={cn('space-y-4', className)}>

            {/* Vitals Grid */}
            <div className="space-y-3">
                <VitalGauge
                    label="CPU LOAD"
                    value={metrics.cpu}
                    icon={<Cpu size={12} />}
                    color={getCpuColor()}
                    animated={isScanning}
                />
                <VitalGauge
                    label="MEMORY"
                    value={metrics.mem}
                    icon={<HardDrive size={12} />}
                    color={getMemColor()}
                    animated={isScanning}
                />
                <VitalGauge
                    label="NET I/O"
                    value={metrics.net}
                    icon={<WifiHigh size={12} />}
                    color="green"
                    animated={isScanning}
                />
                <VitalGauge
                    label="LATENCY"
                    value={metrics.api}
                    maxValue={200}
                    unit="ms"
                    icon={<Lightning size={12} />}
                    color={getApiColor()}
                    animated={isScanning}
                />
            </div>

            {/* Target counter */}
            {targetsTotal > 0 && (
                <div className="pt-3 mt-1 border-t border-[#00ff88]/20">
                    <div className="flex items-center justify-between mb-1.5">
                        <span className="text-[10px] font-mono text-[#00ff88]/60 tracking-wider">TARGET ACQUISITION</span>
                        <span className="text-xs font-mono text-[#00ff88] font-bold">
                            {targetsFound} <span className="opacity-40">/ {targetsTotal}</span>
                        </span>
                    </div>
                    <div className="h-1 bg-black/40 rounded-full overflow-hidden border border-[#00ff88]/20">
                        <div
                            className="h-full bg-[#00ff88] rounded-full transition-all duration-500 shadow-[0_0_10px_rgba(0,255,136,0.5)]"
                            style={{ width: `${targetsTotal > 0 ? (targetsFound / targetsTotal) * 100 : 0}%` }}
                        />
                    </div>
                </div>
            )}
        </div>
    );
}
