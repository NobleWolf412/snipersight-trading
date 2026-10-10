import type { AccountBalance,AccountingStatus,ExecutionHistoryStatus,ExecutionOutcomeSnapshot,ExecutionReportState } from './accounting';
import { API_BASE as BASE } from './apiBase';

export interface LiveTradingConfigRequest {
  selection_mode?: 'fixed';
  exchange?: string;
  sniper_mode?: string;
  risk_per_trade?: number;
  max_positions?: number;
  leverage?: number;
  duration_hours?: number;
  scan_interval_minutes?: number;
  trailing_stop?: boolean;
  trailing_activation?: number;
  breakeven_after_target?: number;
  min_confluence?: number | null;
  sensitivity_preset?: string;
  symbols?: string[];
  exclude_symbols?: string[];
  majors?: boolean;
  altcoins?: boolean;
  meme_mode?: boolean;
  universe_size?: number;
  fee_rate?: number;
  max_drawdown_pct?: number | null;
  max_hours_open?: number;
  confluence_soft_floor?: number | null;
  // live-specific
  testnet?: boolean;
  max_position_size_usd?: number;
  max_total_exposure_usd?: number;
  min_balance_usd?: number;
  kill_switch_enabled?: boolean;
  dry_run?: boolean;
  safety_acknowledgment?: string;
}

/** Strategy provenance recorded on a plan and inherited by its position. */
export interface PlayStrategy { mode?: string; version?: string; selection_mode?: string; strategy_gate?: number }

/** Unfilled entry from status.pending_orders. Plan fields come from the backend's pending_plan_view. */
export interface PendingEntryOrder {
  order_id: string;
  symbol: string;
  direction: string;
  limit_price: number;
  quantity: number;
  status: string;
  filled_qty?: number;
  average_fill_price?: number | null;
  awaiting_adoption?: boolean;
  current_price?: number | null;
  entry_near?: number | null;
  entry_far?: number | null;
  /** undefined: not reported by this backend; null: reported as missing. */
  stop_loss?: number | null;
  targets?: number[];
  timeframe?: string | null;
  trade_type?: string | null;
  confluence?: number | null;
  rationale?: string | null;
  strategy?: PlayStrategy;
}

export interface LivePosition {
  strategy?: PlayStrategy;
  position_id: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  entry_price: number;
  current_price: number;
  quantity: number;
  stop_loss: number;
  initial_stop_loss?: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  breakeven_active: boolean;
  trailing_active: boolean;
  opened_at: string;
  trade_type: string;
  tp1?: number | null;
  tp2?: number | null;
  tp_final?: number | null;
  target_pnl?: number;
  risk_pnl?: number;
  targets_hit?: number;
  targets_remaining?: number;
  // Tier 1.3: in-flight strip detection (see PaperPosition for full rationale).
  final_targets_remaining?: number;
  targets_stripped_count?: number;
}

export interface CompletedLiveTrade {
  trade_id: string;
  symbol: string;
  direction: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  entry_time: string;
  exit_time: string | null;
  pnl: number;
  pnl_pct: number;
  exit_reason: string;
  targets_hit: number[];
  max_favorable: number;
  max_adverse: number;
  trade_type: string;
  confidence_score: number;
  execution_accounting?: ExecutionOutcomeSnapshot;
  execution_report_prepared_at?: string;
  gross_pnl?: number;
  execution_fees?: Record<string, string>;
}

export interface LiveLifecycle {
  phase: 'idle' | 'starting' | 'running' | 'stopping' | 'recovering' | 'stopped';
  entry_admission_enabled: boolean;
  recovery_required: boolean;
  /** Last complete observation; Start/Reset always obtain a fresh one. */
  account_state: 'unknown' | 'exposure_present' | 'flat_confirmed';
  scope: string;
  observed_at: string | null;
  reset_allowed: boolean;
  unresolved_requests: { order_id: string; exchange_id?: string; symbol: string; purpose: string; status: string; filled_quantity: number | null; reason: string }[];
  unmanaged_symbols: string[];
  account_open_orders: { exchange_id: string; symbol: string }[];
  reason: string | null;
}

export function liveSessionNeedsAttention(status?: {
  status?: string; lifecycle?: LiveLifecycle; session_id?: string | null;
  positions?: unknown[]; pending_orders?: unknown[];
} | null): boolean {
  if (!status) return false;
  if (status.status === 'running') return true;
  const state = status.lifecycle;
  if (!state) return !!status.session_id || !!status.positions?.length || !!status.pending_orders?.length;
  return ['starting', 'stopping', 'recovering'].includes(state.phase) || state.recovery_required
    || state.unresolved_requests.length > 0 || state.account_state === 'exposure_present';
}

export function liveShutdownMessage(state?: LiveLifecycle): string {
  if (!state) return 'Shutdown requested. Account closure has not been confirmed.';
  const scope = state.scope === 'simulation' ? 'Simulated account' : 'USDT contracts';
  if (state.phase === 'stopped' && state.account_state === 'flat_confirmed' && !state.recovery_required) {
    return `${scope} observed flat${state.observed_at ? ` at ${state.observed_at}` : ''}.`;
  }
  if (state.account_state === 'flat_confirmed') return `${scope} observed flat. Session recovery is still finishing.${state.reason ? ` ${state.reason}` : ''}`;
  if (state.account_state === 'exposure_present') return 'Scanning stopped. Orders or positions remain; recovery is required.';
  return `Scanning stopped. Account closure is unconfirmed; recovery remains required.${state.reason ? ` ${state.reason}` : ''}`;
}

export interface LiveTradingStatus {
  status: 'idle' | 'running' | 'stopped' | 'error' | 'kill_switched';
  lifecycle?: LiveLifecycle;
  trading_mode: 'idle' | 'dry_run' | 'testnet' | 'live';
  session_id: string | null;
  started_at: string | null;
  stopped_at: string | null;
  uptime_seconds: number;
  config: LiveTradingConfigRequest | null;
  last_scan_at: string | null;
  next_scan_in_seconds: number | null;
  current_scan: {
    status: string;
    current_symbol?: string;
    passed: number;
    rejected: number;
    completed: number;
    total: number;
    progress_pct: number;
    recent_symbols?: { symbol: string; passed: boolean }[];
  } | null;
  regime: {
    composite: string;
    score: number;
    trend?: string;
    volatility?: string;
  } | null;
  positions: LivePosition[];
  balance: AccountBalance;
  accounting?: AccountingStatus;
  outcome_basis?: 'legacy_estimate' | 'executions_excluding_funding_and_transfers';
  execution_reporting?: Record<string, ExecutionReportState>;
  execution_history?: ExecutionHistoryStatus;
  statistics: {
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    scratch_trades: number;
    win_rate: number;
    expectancy: number;
    total_pnl: number;
    total_pnl_pct: number;
    avg_win: number;
    avg_loss: number;
    avg_rr: number;
    best_trade: number;
    worst_trade: number;
    max_drawdown: number;
    scans_completed: number;
    signals_generated: number;
    signals_taken: number;
    exit_reasons: Record<string, number>;
    by_trade_type: Record<string, {
      trades: number;
      win_rate: number;
      total_pnl: number;
      avg_win: number;
      avg_loss: number;
    }>;
  };
  recent_activity: { timestamp: string; event_type: string; data: any }[];
  pending_orders: PendingEntryOrder[];
  signal_log?: import('@/utils/api').SignalLogEntry[];
}

export interface PreflightResult {
  ok: boolean;
  balance: number | null;
  equity?: number | null;
  basis?: 'exchange_mark';
  open_positions: { symbol: string; size: number }[];
  issues: string[];
}

class LiveTradingService {
  async preflight(): Promise<PreflightResult> {
    const res = await fetch(`${BASE}/live-trading/preflight`);
    if (!res.ok) throw new Error(`Preflight failed: ${res.status}`);
    return res.json();
  }

  async start(config: LiveTradingConfigRequest): Promise<any> {
    const res = await fetch(`${BASE}/live-trading/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Start failed: ${res.status}`);
    }
    return res.json();
  }

  async stop(): Promise<any> {
    const res = await fetch(`${BASE}/live-trading/stop`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Stop failed: ${res.status}`);
    }
    return res.json();
  }

  async killSwitch(): Promise<any> {
    const res = await fetch(`${BASE}/live-trading/kill-switch`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Kill switch failed: ${res.status}`);
    }
    return res.json();
  }

  async getStatus(): Promise<LiveTradingStatus> {
    const res = await fetch(`${BASE}/live-trading/status`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Status failed: ${res.status}`);
    }
    return res.json();
  }

  async reset(): Promise<any> {
    const res = await fetch(`${BASE}/live-trading/reset`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Reset failed: ${res.status}`);
    }
    return res.json();
  }

  async getHistory(
    limit = 50,
    source: 'merged' | 'session' | 'journal' = 'merged',
  ): Promise<{ trades: CompletedLiveTrade[]; total: number; source: string }> {
    const res = await fetch(`${BASE}/live-trading/history?limit=${limit}&source=${source}`);
    if (!res.ok) {
      // Surface the backend's detail message instead of a bare status code so
      // the UI banner can show what actually went wrong.
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `History failed: ${res.status}`);
    }
    return res.json();
  }

  async getPhemexHealth(): Promise<Record<string, any>> {
    const res = await fetch(`${BASE}/integrations/phemex/healthz`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Phemex healthz failed: ${res.status}`);
    }
    return res.json();
  }

  async analyzeSession(sessionId?: string): Promise<{ session_dir: string; session_id: string; output: string; error: string; returncode: number }> {
    const url = sessionId ? `${BASE}/live-trading/analyze-session?session_id=${sessionId}` : `${BASE}/live-trading/analyze-session`;
    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Analyze failed: ${res.status}`);
    }
    return res.json();
  }
}

export const liveTradingService = new LiveTradingService();
