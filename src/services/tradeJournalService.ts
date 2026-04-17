import { api } from './api';

const BASE = typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_BASE
  ? (import.meta as any).env.VITE_API_BASE
  : '/api';

export interface JournalTrade {
  trade_id: string;
  session_id: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  trade_type: 'scalp' | 'intraday' | 'swing';
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
}

export interface EquityPoint {
  time: string;
  value: number;
}

export interface SymbolBreakdown {
  trades: number;
  wins: number;
  pnl: number;
  win_rate: number;
}

export interface TypeBreakdown {
  trades: number;
  wins: number;
  pnl: number;
  win_rate: number;
}

export interface JournalAggregate {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  avg_win: number;
  avg_loss: number;
  avg_rr: number;
  best_trade: number;
  worst_trade: number;
  max_drawdown: number;
  equity_curve: EquityPoint[];
  by_symbol: Record<string, SymbolBreakdown>;
  by_type: Record<string, TypeBreakdown>;
}

export interface JournalFilters {
  symbol?: string;
  trade_type?: string;
  exit_reason?: string;
  session_id?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}

export interface JournalResponse {
  trades: JournalTrade[];
  total: number;
  aggregate: JournalAggregate;
}

class TradeJournalService {
  async getJournal(filters: JournalFilters = {}): Promise<JournalResponse> {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') params.append(k, String(v));
    });
    const res = await fetch(`${BASE}/trades/journal?${params}`);
    if (!res.ok) throw new Error(`Journal fetch failed: ${res.statusText}`);
    return res.json();
  }

  getExportUrl(filters: JournalFilters = {}): string {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') params.append(k, String(v));
    });
    return `${BASE}/trades/export?${params}`;
  }
}

export const tradeJournalService = new TradeJournalService();
