/**
 * paperTradingService — Phase 3 follow-up 3z.e
 *
 * Client wrapper for the existing /api/paper-trading/* backend surface
 * (backend/api_server.py:1138-1565). Mirrors the shape of liveTradingService
 * but is STRUCTURALLY DISTINCT — there is no shared base class or method
 * that could be flipped from paper to live by config alone. The two
 * services cannot be swapped at the call site; the §11 hidden-bug class
 * 3z.e closes (silent mode confusion) requires physical separation.
 *
 * Backend exposure verified by Explore subagent during 3z.e research
 * phase (FINDING 2): all 8 endpoints exist and are publicly mounted.
 * No backend extension required for this sub-step.
 *
 * §15 boundary: this service hits paper-trading endpoints only. It
 * cannot dispatch to /api/live-trading/* — there is no `mode` or
 * `dry_run` parameter in any method signature.
 */

const BASE = typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_BASE
  ? (import.meta as any).env.VITE_API_BASE
  : '/api';

export interface PaperTradingConfigRequest {
  exchange?: string;
  sniper_mode?: string;
  initial_balance?: number;
  risk_per_trade?: number;
  max_positions?: number;
  leverage?: number;
  duration_hours?: number;
  scan_interval_minutes?: number;
  trailing_stop?: boolean;
  trailing_activation?: number;
  breakeven_after_target?: number;
  min_confluence?: number | null;
  sensitivity_preset?: 'conservative' | 'balanced' | 'aggressive' | 'custom';
  confluence_soft_floor?: number | null;
  symbols?: string[];
  exclude_symbols?: string[];
  majors?: boolean;
  altcoins?: boolean;
  meme_mode?: boolean;
  slippage_bps?: number;
  fee_rate?: number;
  max_drawdown_pct?: number | null;
  max_hours_open?: number | null;
  use_testnet?: boolean;
  universe_size?: number;
  execution_mode?: 'snap_taker' | 'rest_maker';
  macro_overlay_enabled?: boolean;
  liquidity_mode?: 'fixed' | 'account_aware';
  participation_rate?: number;
  hard_min_volume_usdt?: number;
  depth_aware_admission?: boolean;
  min_order_risk_guard?: boolean;
  liquidation_safety_guard?: boolean;
}

export interface PaperPosition {
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
  // Tier 1.3: in-flight strip detection. When `final_targets_remaining === 0`
  // OR `targets_stripped_count > 0`, the executor's structural-validity guard
  // has stripped targets — position can exit only via SL/stagnation/timeout.
  // Drives the modal's NO-TP chip while the position is still open.
  final_targets_remaining?: number;
  targets_stripped_count?: number;
}

export interface CompletedPaperTrade {
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
}

export interface PaperTradingStatus {
  status: 'idle' | 'running' | 'stopped' | 'paused' | 'error';
  session_id: string | null;
  started_at: string | null;
  stopped_at: string | null;
  uptime_seconds: number;
  config: PaperTradingConfigRequest | null;
  last_scan_at: string | null;
  next_scan_in_seconds: number | null;
  // Heart-change decision-core flags (so the UI reflects the actual core): "thesis" = structure-led
  // direction + confluence score DEMOTED (not a gate); "legacy" = the classic score-gate path.
  decision_mode?: 'thesis' | 'legacy';
  fresh_entry_price?: boolean;
  positions: PaperPosition[];
  balance: {
    initial: number;
    current: number;
    equity: number;
    pnl: number;
    pnl_pct: number;
  };
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
  pending_orders: { order_id: string; symbol: string; direction: string; limit_price: number; quantity: number; status: string }[];
}

class PaperTradingService {
  /**
   * Start a paper-trading session. STRUCTURAL §15 BOUNDARY:
   * config has no `dry_run` or `mode` parameter — there is no way for
   * this method to dispatch a live order. The backend's
   * /api/paper-trading/start handler instantiates PaperExecutor (not
   * the live executor) regardless of any field value.
   */
  async start(config: PaperTradingConfigRequest): Promise<any> {
    const res = await fetch(`${BASE}/paper-trading/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Paper start failed: ${res.status}`);
    }
    return res.json();
  }

  async stop(): Promise<any> {
    const res = await fetch(`${BASE}/paper-trading/stop`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Paper stop failed: ${res.status}`);
    }
    return res.json();
  }

  async getStatus(): Promise<PaperTradingStatus> {
    const res = await fetch(`${BASE}/paper-trading/status`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Paper status failed: ${res.status}`);
    }
    return res.json();
  }

  async getPositions(): Promise<{ positions: PaperPosition[]; total: number }> {
    const res = await fetch(`${BASE}/paper-trading/positions`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Paper positions failed: ${res.status}`);
    }
    return res.json();
  }

  async getHistory(limit = 50): Promise<{ trades: CompletedPaperTrade[]; total: number }> {
    const res = await fetch(`${BASE}/paper-trading/history?limit=${limit}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Paper history failed: ${res.status}`);
    }
    return res.json();
  }

  async getActivity(limit = 100): Promise<{ activity: { timestamp: string; event_type: string; data: any }[]; total: number }> {
    const res = await fetch(`${BASE}/paper-trading/activity?limit=${limit}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Paper activity failed: ${res.status}`);
    }
    return res.json();
  }

  async reset(): Promise<any> {
    const res = await fetch(`${BASE}/paper-trading/reset`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Paper reset failed: ${res.status}`);
    }
    return res.json();
  }

  async cancelOrder(orderId: string): Promise<any> {
    const res = await fetch(`${BASE}/paper-trading/orders/${encodeURIComponent(orderId)}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Paper cancel failed: ${res.status}`);
    }
    return res.json();
  }
}

export const paperTradingService = new PaperTradingService();
