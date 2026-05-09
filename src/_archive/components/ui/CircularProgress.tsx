import React from 'react';

interface CircularProgressProps {
    value: number; // 0-100
    size?: number;
    strokeWidth?: number;
    className?: string;
    showValue?: boolean;
    label?: string;
    colorScheme?: 'default' | 'success' | 'warning' | 'danger' | 'gradient';
}

/**
 * CircularProgress - A visual circular progress/gauge component
 */
export function CircularProgress({
    value,
    size = 80,
    strokeWidth = 8,
    className = '',
    showValue = true,
    label,
    colorScheme = 'gradient',
}: CircularProgressProps) {
    const radius = (size - strokeWidth) / 2;
    const circumference = radius * 2 * Math.PI;
    const clampedValue = Math.min(100, Math.max(0, value));
    const offset = circumference - (clampedValue / 100) * circumference;

    // Determine color based on scheme and value
    const getStrokeColor = () => {
        switch (colorScheme) {
            case 'success':
                return 'stroke-success';
            case 'warning':
                return 'stroke-warning';
            case 'danger':
                return 'stroke-destructive';
            case 'gradient':
                // Value-based coloring
                if (value >= 70) return 'stroke-success';
                if (value >= 50) return 'stroke-warning';
                return 'stroke-destructive';
            default:
                return 'stroke-accent';
        }
    };

    const getTextColor = () => {
        switch (colorScheme) {
            case 'success':
                return 'text-success';
            case 'warning':
                return 'text-warning';
            case 'danger':
                return 'text-destructive';
            case 'gradient':
                if (value >= 70) return 'text-success';
                if (value >= 50) return 'text-warning';
                return 'text-destructive';
            default:
                return 'text-accent';
        }
    };

    return (
        <div className={`relative inline-flex items-center justify-center ${className}`}>
            <svg width={size} height={size} className="-rotate-90">
                {/* Background circle */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    strokeWidth={strokeWidth}
                    className="stroke-muted/30"
                />
                {/* Progress circle */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    strokeWidth={strokeWidth}
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                    strokeLinecap="round"
                    className={`${getStrokeColor()} transition-all duration-700 ease-out`}
                    style={{
                        filter: 'drop-shadow(0 0 6px currentColor)',
                    }}
                />
            </svg>
            {showValue && (
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className={`text-lg font-bold font-mono ${getTextColor()}`}>
                        {Math.round(clampedValue)}%
                    </span>
                    {label && (
                        <span className="text-[10px] text-muted-foreground uppercase tracking-wide">
                            {label}
                        </span>
                    )}
                </div>
            )}
        </div>
    );
}

interface ConfidenceBarProps {
    value: number; // 0-100
    width?: number;
    height?: number;
    showValue?: boolean;
    className?: string;
}

/**
 * ConfidenceBar - Horizontal progress bar with gradient coloring
 */
export function ConfidenceBar({
    value,
    width = 100,
    height = 8,
    showValue = true,
    className = '',
}: ConfidenceBarProps) {
    const clampedValue = Math.min(100, Math.max(0, value));

    // Get color based on value
    const getBarColor = () => {
        if (value >= 80) return 'bg-success';
        if (value >= 70) return 'bg-accent';
        if (value >= 65) return 'bg-warning';
        return 'bg-destructive';
    };

    const getGlow = () => {
        if (value >= 80) return 'shadow-[0_0_8px_rgba(34,197,94,0.5)]';
        if (value >= 70) return 'shadow-[0_0_8px_rgba(0,255,255,0.4)]';
        return '';
    };

    return (
        <div className={`flex items-center gap-2 ${className}`}>
            <div
                className="bg-muted/30 rounded-full overflow-hidden"
                style={{ width: `${width}px`, height: `${height}px` }}
            >
                <div
                    className={`h-full rounded-full transition-all duration-500 ${getBarColor()} ${getGlow()}`}
                    style={{ width: `${clampedValue}%` }}
                />
            </div>
            {showValue && (
                <span className={`text-sm font-bold font-mono ${value >= 80 ? 'text-success' :
                        value >= 70 ? 'text-accent' :
                            value >= 65 ? 'text-warning' :
                                'text-destructive'
                    }`}>
                    {value.toFixed(0)}%
                </span>
            )}
        </div>
    );
}

interface MiniPieChartProps {
    segments: { value: number; color: string; label: string }[];
    size?: number;
    className?: string;
}

/**
 * MiniPieChart - Small pie chart for direction analytics
 */
export function MiniPieChart({ segments, size = 48, className = '' }: MiniPieChartProps) {
    const total = segments.reduce((sum, s) => sum + s.value, 0);
    if (total === 0) return null;

    let cumulativePercent = 0;
    const radius = size / 2;
    const center = size / 2;

    return (
        <svg width={size} height={size} className={className}>
            {segments.map((segment, i) => {
                const percent = (segment.value / total) * 100;
                const startAngle = cumulativePercent * 3.6 - 90;
                const endAngle = (cumulativePercent + percent) * 3.6 - 90;
                cumulativePercent += percent;

                // Convert to radians
                const startRad = (startAngle * Math.PI) / 180;
                const endRad = (endAngle * Math.PI) / 180;

                // Path coordinates
                const x1 = center + radius * Math.cos(startRad);
                const y1 = center + radius * Math.sin(startRad);
                const x2 = center + radius * Math.cos(endRad);
                const y2 = center + radius * Math.sin(endRad);

                const largeArcFlag = percent > 50 ? 1 : 0;

                const d = `M ${center} ${center} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArcFlag} 1 ${x2} ${y2} Z`;

                return (
                    <path
                        key={i}
                        d={d}
                        fill={segment.color}
                        className="transition-all duration-300"
                    >
                        <title>{segment.label}: {segment.value}</title>
                    </path>
                );
            })}
        </svg>
    );
}
