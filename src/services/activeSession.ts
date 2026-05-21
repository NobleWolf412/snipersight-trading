/**
 * activeSession — unified probe across the live + paper trading services.
 *
 * The bot is one logical entity from the operator's perspective: it's either
 * running in some mode or it isn't. But the backend exposes two separate
 * services (live_trading_service.py and paper_trading_service.py) with
 * parallel /api/live-trading/* and /api/paper-trading/* endpoints.
 *
 * Without this helper, BotStatus and BotIndex hardcode against the live
 * service, making paper sessions invisible to the HUD (pending orders,
 * positions, PnL all empty even when paper is actively trading).
 *
 * This helper:
 *   1. Probes both endpoints in parallel.
 *   2. Picks the running one. Both-running ties go to live (real-money
 *      priority — defensive since the bot should be one-at-a-time).
 *   3. If neither is running, prefers live's idle state for display
 *      continuity (live service is the historical primary).
 *   4. Returns the dispatch service so callers route stop/reset/history
 *      to the correct backend without branching.
 *
 * Method surface gates (paper service is a strict subset):
 *   - killSwitch / analyzeSession / preflight are LIVE-ONLY.
 *   - `canKillSwitch` and `canAnalyzeSession` reflect this; UI hides
 *     buttons when false.
 */
import {
  liveTradingService,
  type LiveTradingStatus,
} from './liveTradingService';
import {
  paperTradingService,
  type PaperTradingStatus,
} from './paperTradingService';

export type ActiveMode = 'live' | 'testnet' | 'dry_run' | 'paper' | 'idle';

export type ActiveStatus = LiveTradingStatus | PaperTradingStatus;

export type ActiveService =
  | typeof liveTradingService
  | typeof paperTradingService;

export interface ActiveSession {
  /** Resolved mode for display + ModePill + chrome color. */
  mode: ActiveMode;
  /** Raw status payload from whichever service won. May be null if both probes failed. */
  status: ActiveStatus | null;
  /** Service reference for downstream dispatch (stop, reset, getHistory). */
  service: ActiveService;
  /** Live mode = real-money. Drives red chrome priority. */
  isLive: boolean;
  /** Paper mode running. Drives amber chrome (paper-mode demarcation per memory). */
  isPaper: boolean;
  /** Whether killSwitch is available (live-only). */
  canKillSwitch: boolean;
  /** Whether analyzeSession is available (live-only). */
  canAnalyzeSession: boolean;
}

/**
 * Fetch the active session by probing both /api/live-trading/status and
 * /api/paper-trading/status in parallel.
 *
 * Throws only if BOTH services fail. If one succeeds and the other doesn't,
 * the successful one is used. This keeps the HUD operational when one
 * backend service is temporarily unreachable.
 */
export async function fetchActiveSession(): Promise<ActiveSession> {
  const [liveResult, paperResult] = await Promise.allSettled([
    liveTradingService.getStatus(),
    paperTradingService.getStatus(),
  ]);

  const live = liveResult.status === 'fulfilled' ? liveResult.value : null;
  const paper = paperResult.status === 'fulfilled' ? paperResult.value : null;

  // Total failure: rethrow whichever error fired first. The caller's catch
  // block decides how to surface this (connection banner, retry, etc).
  if (!live && !paper) {
    const err =
      liveResult.status === 'rejected'
        ? liveResult.reason
        : paperResult.status === 'rejected'
          ? paperResult.reason
          : 'Both trading services unreachable';
    throw err instanceof Error ? err : new Error(String(err));
  }

  const liveRunning = live?.status === 'running';
  const paperRunning = paper?.status === 'running';

  // Live wins on both-running. Real money is the loudest state — and a paper
  // session running alongside a live one shouldn't visually displace it.
  if (liveRunning) {
    const tradingMode = live!.trading_mode ?? 'live';
    return {
      mode: tradingMode as ActiveMode,
      status: live!,
      service: liveTradingService,
      isLive: tradingMode === 'live',
      isPaper: false,
      canKillSwitch: true,
      canAnalyzeSession: true,
    };
  }

  if (paperRunning) {
    return {
      mode: 'paper',
      status: paper!,
      service: paperTradingService,
      isLive: false,
      isPaper: true,
      canKillSwitch: false,
      canAnalyzeSession: false,
    };
  }

  // Neither running. Prefer live's idle state for display continuity; falls
  // back to paper if live probe failed entirely.
  if (live) {
    return {
      mode: (live.trading_mode ?? 'idle') as ActiveMode,
      status: live,
      service: liveTradingService,
      isLive: false,
      isPaper: false,
      canKillSwitch: true,
      canAnalyzeSession: true,
    };
  }

  return {
    mode: 'idle',
    status: paper,
    service: paperTradingService,
    isLive: false,
    isPaper: true,
    canKillSwitch: false,
    canAnalyzeSession: false,
  };
}
