import type { ActiveMode, ActiveSession } from '@/services/activeSession';
import { liveSessionNeedsAttention, liveTradingService, type LiveTradingStatus } from '@/services/liveTradingService';
import { paperSessionNeedsAttention } from '@/services/paperTradingService';
export function buildBotStatusViewModel(session: ActiveSession | null) {
    const status = session?.status ?? null;
    const lifecycle = status && 'lifecycle' in status ? status.lifecycle : undefined;
    const isStarting = lifecycle?.phase === 'starting';
    const isRunning = status?.status === 'running' && !isStarting;
    const isKilled = status?.status === 'kill_switched';
    const liveServiceSelected = session?.service === liveTradingService;
    const needsRecovery = (liveServiceSelected ? liveSessionNeedsAttention(status) : paperSessionNeedsAttention(status as any)) && !isRunning && !isStarting;
    const tradingMode: ActiveMode = session?.mode ?? 'idle';
    const isLive = session?.isLive ?? false;
    const isPaper = session?.isPaper ?? false;
    const canKillSwitch = session?.canKillSwitch ?? false;
    const canAnalyzeSession = session?.canAnalyzeSession ?? false;
    const stats = status?.statistics;
    const balance = status?.balance;
    const initialBalance = balance?.initial;
    const positions = status?.positions ?? [];
    const pendingOrders = status?.pending_orders ?? [];
    // signal_log only exists on LiveTradingStatus; paper service doesn't
    // emit it. Returns empty array for paper sessions until backend parity.
    const signalLog = (status && 'signal_log' in status ? status.signal_log : null) ?? [];
    // regime is also LiveTradingStatus-only. Returns null for paper.
    const regime = status && 'regime' in status ? (status.regime as LiveTradingStatus['regime']) : null;
    // Live diagnostics are unavailable for paper; the modal and entry guard both enforce ownership.
    const liveStatus = !isPaper && status ? (status as LiveTradingStatus) : null;
    const cfg = status?.config;
    // Subtitle reflects the active mode. Commas (not em dashes) per DESIGN.md.
    const subtitleText = (() => {
        switch (tradingMode) {
            case 'live':
                return 'real money, phemex perpetuals';
            case 'paper':
                return 'paper trading, phemex price feed';
            case 'testnet':
                return 'testnet, simulated fills';
            case 'dry_run':
                return 'dry run, no orders sent';
            default:
                return 'idle, awaiting deployment';
        }
    })();
    // PageHead accent: live = red, everything else = amber (paper, testnet,
    // dry_run, idle all sandbox-or-quiet).
    const headAccent: 'red' | 'amber' = isLive ? 'red' : 'amber';
    return { lifecycle, isStarting, isRunning, isKilled, liveServiceSelected, needsRecovery, tradingMode, isLive, isPaper, canKillSwitch, canAnalyzeSession, stats, balance, initialBalance, positions, pendingOrders, signalLog, regime, liveStatus, cfg, subtitleText, headAccent };
}
