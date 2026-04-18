const BASE = typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_BASE
  ? (import.meta as any).env.VITE_API_BASE
  : '/api';

export interface LiveTradingConfigRequest {
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
  fee_rate?: number;
  max_drawdown_pct?: number | null;
  max_hours_open?: number;
  // live-specific
  testnet?: boolean;
  max_position_size_usd?: number;
  max_total_exposure_usd?: number;
  min_balance_usd?: number;
  kill_switch_enabled?: boolean;
  dry_run?: boolean;
  safety_acknowledgment?: string;
}

export interface LivePosition {
  position_id: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  entry_price: number;
  current_price: number;
  quantity: number;
  stop_loss: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  breakeven_active: boolean;
  trailing_active: boolean;
  opened_at: string;
  trade_type: string;
}

export interface LiveTradingStatus {
  status: 'idle' | 'running' | 'stopped' | 'error' | 'kill_switched';
  trading_mode: 'idle' | 'dry_run' | 'testnet' | 'live';
  session_id: string | null;
  started_at: string | null;
  stopped_at: string | null;
  uptime_seconds: number;
  config: LiveTradingConfigRequest | null;
  last_scan_at: string | null;
  next_scan_in_seconds: number | null;
  positions: LivePosition[];
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
    win_rate: number;
    total_pnl: number;
    avg_win: number;
    avg_loss: number;
    best_trade: number;
    worst_trade: number;
    max_drawdown: number;
    scans_completed: number;
    signals_generated: number;
    signals_taken: number;
  };
  recent_activity: { timestamp: string; event_type: string; data: any }[];
  pending_orders: { order_id: string; symbol: string; direction: string; limit_price: number; quantity: number; status: string }[];
}

export interface PreflightResult {
  ok: boolean;
  balance: number;
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
    if (!res.ok) throw new Error(`Stop failed: ${res.status}`);
    return res.json();
  }

  async killSwitch(): Promise<any> {
    const res = await fetch(`${BASE}/live-trading/kill-switch`, { method: 'POST' });
    if (!res.ok) throw new Error(`Kill switch failed: ${res.status}`);
    return res.json();
  }

  async getStatus(): Promise<LiveTradingStatus> {
    const res = await fetch(`${BASE}/live-trading/status`);
    if (!res.ok) throw new Error(`Status failed: ${res.status}`);
    return res.json();
  }

  async reset(): Promise<any> {
    const res = await fetch(`${BASE}/live-trading/reset`, { method: 'POST' });
    if (!res.ok) throw new Error(`Reset failed: ${res.status}`);
    return res.json();
  }

  async getHistory(limit = 50): Promise<{ trades: any[]; total: number }> {
    const res = await fetch(`${BASE}/live-trading/history?limit=${limit}`);
    if (!res.ok) throw new Error(`History failed: ${res.status}`);
    return res.json();
  }
}

export const liveTradingService = new LiveTradingService();
