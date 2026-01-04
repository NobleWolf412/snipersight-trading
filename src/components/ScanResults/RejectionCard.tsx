import { XCircle, WarningCircle, Prohibit, Bug } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

export interface RejectionInfo {
    symbol: string;
    reason_type: 'low_confluence' | 'no_data' | 'missing_critical_tf' | 'risk_validation' | 'no_trade_plan' | 'cooldown_active' | 'errors';
    reason: string;
    trace_id?: string;
    [key: string]: any;
}

interface RejectionCardProps {
    rejection: RejectionInfo;
}

const REASON_CONFIG = {
    low_confluence: { icon: WarningCircle, color: 'text-amber-400', border: 'border-amber-500/20', bg: 'bg-amber-500/10', glow: 'hover:shadow-[0_0_15px_rgba(251,191,36,0.15)] hover:border-amber-500/40' },
    no_data: { icon: Prohibit, color: 'text-zinc-400', border: 'border-zinc-500/20', bg: 'bg-zinc-500/10', glow: 'hover:shadow-[0_0_15px_rgba(113,113,122,0.15)] hover:border-zinc-500/40' },
    missing_critical_tf: { icon: Prohibit, color: 'text-orange-400', border: 'border-orange-500/20', bg: 'bg-orange-500/10', glow: 'hover:shadow-[0_0_15px_rgba(251,146,60,0.15)] hover:border-orange-500/40' },
    risk_validation: { icon: XCircle, color: 'text-red-400', border: 'border-red-500/20', bg: 'bg-red-500/10', glow: 'hover:shadow-[0_0_15px_rgba(248,113,113,0.15)] hover:border-red-500/40' },
    no_trade_plan: { icon: XCircle, color: 'text-zinc-400', border: 'border-zinc-500/20', bg: 'bg-zinc-500/10', glow: 'hover:shadow-[0_0_15px_rgba(161,161,170,0.15)] hover:border-zinc-500/40' },
    cooldown_active: { icon: Prohibit, color: 'text-blue-400', border: 'border-blue-500/20', bg: 'bg-blue-500/10', glow: 'hover:shadow-[0_0_15px_rgba(96,165,250,0.15)] hover:border-blue-500/40' },
    errors: { icon: Bug, color: 'text-pink-400', border: 'border-pink-500/20', bg: 'bg-pink-500/10', glow: 'hover:shadow-[0_0_15px_rgba(244,114,182,0.15)] hover:border-pink-500/40' },
};

export function RejectionCard({ rejection }: RejectionCardProps) {
    const config = REASON_CONFIG[rejection.reason_type] || REASON_CONFIG.errors;
    const Icon = config.icon;

    return (
        <div className={cn(
            "w-full p-6 mb-4 bg-[#0a0f0a] border border-zinc-800/60 rounded-xl flex items-start gap-6 transition-all duration-300",
            config.glow
        )}>
            <div className={cn("flex items-center justify-center w-12 h-12 rounded-xl border flex-shrink-0", config.bg, config.border, config.color)}>
                <Icon size={28} weight="bold" />
            </div>

            <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-xl font-bold tracking-tight text-zinc-200">{rejection.symbol}</span>
                    <span className={cn("text-xs font-mono uppercase px-2 py-1 rounded border", config.bg, config.border, config.color)}>
                        {rejection.reason_type.replace(/_/g, ' ')}
                    </span>
                </div>

                <p className="text-zinc-400 text-lg leading-relaxed font-mono">
                    {rejection.reason}
                </p>

                {rejection.trace_id && (
                    <div className="mt-3 text-xs text-zinc-600 font-mono">
                        Trace ID: {rejection.trace_id}
                    </div>
                )}
            </div>
        </div>
    );
}
