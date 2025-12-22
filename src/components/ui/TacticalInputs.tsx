import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { Check, Warning } from '@phosphor-icons/react';

// --- Tactical Selector Grid ---
// --- Tactical Selector Grid ---
interface TacticalSelectorProps {
    label?: string;
    subLabel?: string; // Additional instruction label below main label
    options: { value: string; label: string; subLabel?: string; icon?: React.ReactNode }[];
    value: string;
    onChange: (value: string) => void;
    className?: string;
    gridCols?: number;
}

export function TacticalSelector({ label, subLabel, options, value, onChange, className, gridCols = 2 }: TacticalSelectorProps) {
    return (
        <div className={className}>
            <div className="mb-4">
                {label && <label className="block text-base font-bold font-mono text-[#00ff88] tracking-widest uppercase mb-1">{label}</label>}
                {subLabel && <p className="text-sm text-muted-foreground">{subLabel}</p>}
            </div>
            <div
                className="grid gap-4"
                style={{ gridTemplateColumns: `repeat(${gridCols}, minmax(0, 1fr))` }}
            >
                {options.map((option) => {
                    const isSelected = value === option.value;
                    return (
                        <button
                            key={option.value}
                            type="button"
                            onClick={() => onChange(option.value)}
                            className={cn(
                                "relative flex flex-col items-center justify-center gap-1.5 p-5 rounded-xl border-2 transition-all duration-200 group overflow-hidden h-full",
                                isSelected
                                    ? "border-[#00ff88] bg-[#00ff88]/10 text-[#00ff88] shadow-[0_0_20px_rgba(0,255,136,0.15)]"
                                    : "border-white/5 bg-black/40 text-muted-foreground hover:border-white/20 hover:text-white hover:bg-white/5"
                            )}
                        >
                            {isSelected && (
                                <motion.div
                                    layoutId={`glow-${label}`}
                                    className="absolute inset-0 bg-[#00ff88]/5"
                                    transition={{ duration: 0.2 }}
                                />
                            )}

                            {/* Corner accents for selected state */}
                            {isSelected && (
                                <>
                                    <div className="absolute top-0 left-0 w-3 h-3 border-t-2 border-l-2 border-[#00ff88]" />
                                    <div className="absolute bottom-0 right-0 w-3 h-3 border-b-2 border-r-2 border-[#00ff88]" />
                                </>
                            )}

                            <span className="relative z-10 flex items-center gap-3 font-mono text-lg font-bold uppercase tracking-wide">
                                {option.icon && <span className={cn("transition-opacity", isSelected ? "opacity-100" : "opacity-70")}>{option.icon}</span>}
                                {option.label}
                            </span>

                            {option.subLabel && (
                                <span className={cn(
                                    "relative z-10 text-xs font-mono uppercase tracking-wider font-semibold",
                                    isSelected ? "text-[#00ff88]/80" : "text-muted-foreground/40"
                                )}>
                                    {option.subLabel}
                                </span>
                            )}
                        </button>
                    );
                })}
            </div>
        </div>
    );
}

// --- Tactical Slider ---
interface TacticalSliderProps {
    label: string;
    subLabel?: string;
    value: number;
    min: number;
    max: number;
    step?: number;
    onChange: (value: number) => void;
    formatValue?: (val: number) => string;
    zones?: { limit: number; color: string; label: string }[];
    className?: string;
}

export function TacticalSlider({
    label,
    subLabel,
    value,
    min,
    max,
    step = 1,
    onChange,
    formatValue = (v) => v.toString(),
    zones,
    className
}: TacticalSliderProps) {

    const percentage = ((value - min) / (max - min)) * 100;

    // Determine current zone color
    const activeZone = zones?.find(z => value <= z.limit) || zones?.[zones.length - 1];
    const color = activeZone?.color || '#00ff88';

    return (
        <div className={className}>
            <div className="flex items-end justify-between mb-4">
                <div>
                    <label className="block text-base font-bold font-mono text-[#00ff88] tracking-widest uppercase mb-1">{label}</label>
                    {subLabel && <p className="text-sm text-muted-foreground">{subLabel}</p>}
                </div>
                <div className="flex items-center gap-3 bg-black/40 border border-white/10 px-3 py-1.5 rounded-lg">
                    {activeZone && (
                        <span className="text-xs font-bold px-2 py-0.5 rounded-sm bg-black/60 border border-white/5 uppercase tracking-wider" style={{ color: color, borderColor: `${color}40` }}>
                            {activeZone.label}
                        </span>
                    )}
                    <span className="text-2xl font-bold font-mono tabular-nums leading-none" style={{ color }}>
                        {formatValue(value)}
                    </span>
                </div>
            </div>

            <div className="relative h-16 flex items-center select-none touch-none group">
                {/* Track Background */}
                <div className="absolute inset-x-0 h-6 bg-black/80 rounded-full border-2 border-white/10 overflow-hidden shadow-[inset_0_4px_6px_rgba(0,0,0,0.6)]">
                    {/* Zone Indicators (Background segments) */}
                    {zones && (
                        <div className="absolute inset-0 flex">
                            {zones.map((zone, i) => {
                                const prevLimit = i === 0 ? min : zones[i - 1].limit;
                                const width = ((Math.min(zone.limit, max) - Math.max(prevLimit, min)) / (max - min)) * 100;
                                return (
                                    <div
                                        key={i}
                                        className="h-full border-r border-black/50 opacity-20 hover:opacity-30 transition-opacity"
                                        style={{ width: `${width}%`, backgroundColor: zone.color }}
                                    />
                                );
                            })}
                        </div>
                    )}

                    {/* Fill Bar */}
                    <motion.div
                        className="absolute top-0 left-0 h-full shadow-[0_0_15px_rgba(0,0,0,0.5)]"
                        style={{ backgroundColor: color, width: `${percentage}%` }}
                        animate={{ width: `${percentage}%`, backgroundColor: color }}
                        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                    />

                    {/* Scanline texture overlay on track */}
                    <div className="absolute inset-0 bg-[url('/scanlines.png')] opacity-25 pointer-events-none mix-blend-overlay" />
                    <div className="absolute inset-0 bg-gradient-to-b from-white/5 to-black/20 pointer-events-none" />
                </div>

                {/* Input (invisible but interactive) */}
                <input
                    type="range"
                    min={min}
                    max={max}
                    step={step}
                    value={value}
                    onChange={(e) => onChange(Number(e.target.value))}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-30"
                />

                {/* Thumb (Visual only) */}
                <motion.div
                    className="absolute top-1/2 -translate-y-1/2 w-10 h-14 z-20 pointer-events-none flex items-center justify-center filter drop-shadow-[0_6px_10px_rgba(0,0,0,0.8)]"
                    style={{ left: `calc(${percentage}% - 20px)` }}
                    animate={{ left: `calc(${percentage}% - 20px)` }}
                    transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                >
                    <div
                        className="w-full h-full rounded-lg relative flex items-center justify-center transition-all duration-200 group-active:scale-95 transform"
                        style={{
                            background: `linear-gradient(180deg, #2a2a2a 0%, #151515 100%)`,
                            border: `3px solid ${color}`,
                            boxShadow: `0 0 20px ${color}60, inset 0 1px 0 rgba(255,255,255,0.1), 0 4px 8px rgba(0,0,0,0.5)`
                        }}
                    >
                        {/* Grip Lines */}
                        <div className="flex gap-2">
                            <div className="w-1 h-7 bg-white/50 block rounded-full" />
                            <div className="w-1 h-7 bg-white/50 block rounded-full" />
                        </div>

                        {/* Active Glow Center */}
                        <div className="absolute inset-0 bg-gradient-to-t from-transparent via-white/5 to-white/10 rounded-lg pointer-events-none" />
                    </div>
                </motion.div>

                {/* Ticks */}
                <div className="absolute -bottom-3 w-full flex justify-between px-2 pointer-events-none">
                    {Array.from({ length: 11 }).map((_, i) => (
                        <div key={i} className="w-0.5 h-2 bg-white/20" />
                    ))}
                </div>
            </div>
        </div>
    );
}

// --- Tactical Toggle Card ---
interface TacticalToggleProps {
    label: string;
    sublabel?: string;
    checked: boolean;
    onChange: (checked: boolean) => void;
    icon?: React.ReactNode;
    isHazard?: boolean; // Special styling for Meme mode etc.
    className?: string;
}

export function TacticalToggle({ label, sublabel, checked, onChange, icon, isHazard, className }: TacticalToggleProps) {
    return (
        <button
            type="button"
            onClick={() => onChange(!checked)}
            className={cn(
                "relative group flex flex-col items-start p-4 rounded-xl border-2 transition-all duration-200 w-full text-left overflow-hidden",
                checked
                    ? (isHazard
                        ? "border-amber-500 bg-amber-500/10 shadow-[0_0_20px_rgba(245,158,11,0.2)]"
                        : "border-[#00ff88] bg-[#00ff88]/10 shadow-[0_0_20px_rgba(0,255,136,0.15)]")
                    : "border-white/5 bg-black/40 hover:border-white/20 hover:bg-white/5",
                className
            )}
        >
            {/* Background Pulse for Hazard */}
            {checked && isHazard && (
                <div className="absolute inset-0 bg-amber-500/5 animate-pulse pointer-events-none" />
            )}

            {/* Active Indicator Dot */}
            <div className="absolute top-3 right-3">
                <div className={cn(
                    "w-3 h-3 rounded-full border transition-all duration-300",
                    checked
                        ? (isHazard ? "bg-amber-500 border-amber-400 shadow-[0_0_8px_rgba(245,158,11,0.8)]" : "bg-[#00ff88] border-[#00ff88] shadow-[0_0_8px_rgba(0,255,136,0.8)]")
                        : "bg-transparent border-white/20"
                )} />
            </div>

            {/* Content */}
            <div className="relative z-10">
                <div className={cn(
                    "mb-2 transition-colors duration-200",
                    checked
                        ? (isHazard ? "text-amber-400" : "text-[#00ff88]")
                        : "text-white/40 group-hover:text-white/60"
                )}>
                    {icon || <Check size={24} />}
                </div>

                <div className={cn(
                    "font-bold font-mono text-lg transition-colors",
                    checked ? "text-white" : "text-muted-foreground group-hover:text-white"
                )}>
                    {label}
                </div>

                {sublabel && (
                    <div className={cn(
                        "text-xs mt-1 font-mono transition-colors",
                        checked
                            ? (isHazard ? "text-amber-400/70" : "text-[#00ff88]/70")
                            : "text-muted-foreground/50"
                    )}>
                        {sublabel}
                    </div>
                )}
            </div>

            {/* Hazard Warning */}
            {isHazard && checked && (
                <div className="absolute -bottom-6 -right-6 text-amber-500/10 transform -rotate-12 pointer-events-none">
                    <Warning size={80} weight="fill" />
                </div>
            )}
        </button>
    );
}
