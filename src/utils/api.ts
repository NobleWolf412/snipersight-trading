/**
 * API Client for SniperSight Backend
 * 
 * Provides typed methods for interacting with the FastAPI backend.
 */

const API_BASE = '/api';

interface ApiResponse<T> {
  data?: T;
  error?: string;
}

// Scanner types
export interface ScannerConfig {
  exchange: string;
  symbols: string[];
  timeframes: string[];
  min_score: number;
  indicators: Record<string, boolean>;
}

export interface Signal {
  symbol: string;
  direction: string;
  score: number;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  timeframe: string;
  timestamp: string;
  analysis: Record<string, any>;
}

// Bot types
export interface BotConfig {
  exchange: string;
  leverage: number;
  risk_per_trade: number;
  max_positions: number;
  stop_loss_pct: number;
  take_profit_pct: number;
}

export interface Position {
  symbol: string;
  direction: string;
  entry_price: number;
  current_price: number;
  quantity: number;
  pnl: number;
  pnl_pct: number;
  opened_at: string;
}

export interface BotStatus {
  active: boolean;
  balance: number;
  equity: number;
  positions: number;
  total_trades: number;
  win_rate: number;
  pnl: number;
  statistics: Record<string, any>;
}

export interface OrderRequest {
  symbol: string;
  side: string;
  order_type: string;
  quantity: number;
  price?: number;
  leverage?: number;
}

class ApiClient {
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      if (!response.ok) {
        const error = await response.json();
        return { error: error.detail || 'Request failed' };
      }

      const data = await response.json();
      return { data };
    } catch (error) {
      return { error: error instanceof Error ? error.message : 'Unknown error' };
    }
  }

  // Health check
  async healthCheck() {
    return this.request('/health');
  }

  // Scanner endpoints
  async createScannerConfig(config: ScannerConfig) {
    return this.request('/scanner/config', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  async getScannerConfig(configId: string) {
    return this.request<ScannerConfig>(`/scanner/config/${configId}`);
  }

  async startScanner(configId: string) {
    return this.request(`/scanner/${configId}/start`, { method: 'POST' });
  }

  async stopScanner(configId: string) {
    return this.request(`/scanner/${configId}/stop`, { method: 'POST' });
  }

  async getSignals(params?: { limit?: number; min_score?: number }) {
    const query = new URLSearchParams(
      params as Record<string, string>
    ).toString();
    return this.request<{ signals: Signal[]; total: number }>(
      `/scanner/signals${query ? `?${query}` : ''}`
    );
  }

  // Bot endpoints
  async createBotConfig(config: BotConfig) {
    return this.request('/bot/config', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  async getBotConfig(configId: string) {
    return this.request<BotConfig>(`/bot/config/${configId}`);
  }

  async startBot(configId: string) {
    return this.request(`/bot/${configId}/start`, { method: 'POST' });
  }

  async stopBot(configId: string) {
    return this.request(`/bot/${configId}/stop`, { method: 'POST' });
  }

  async getBotStatus() {
    return this.request<BotStatus>('/bot/status');
  }

  async getPositions() {
    return this.request<{ positions: Position[]; total: number }>('/bot/positions');
  }

  async placeOrder(order: OrderRequest) {
    return this.request('/bot/order', {
      method: 'POST',
      body: JSON.stringify(order),
    });
  }

  async getTradeHistory(limit = 50) {
    return this.request(`/bot/trades?limit=${limit}`);
  }

  // Risk management
  async getRiskSummary() {
    return this.request('/risk/summary');
  }

  // Market data
  async getPrice(symbol: string) {
    return this.request<{ symbol: string; price: number; timestamp: string }>(
      `/market/price/${symbol}`
    );
  }

  async getCandles(symbol: string, timeframe = '1h', limit = 100) {
    return this.request(
      `/market/candles/${symbol}?timeframe=${timeframe}&limit=${limit}`
    );
  }
}

export const api = new ApiClient();
