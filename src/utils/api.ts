/**
 * API Client for SniperSight Backend
 * 
 * Provides typed methods for interacting with the FastAPI backend.
 */

// Resolve API base: prefer Vite env, fallback to same-origin '/api' or localhost:8001
const API_BASE = (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_BASE)
  ? (import.meta as any).env.VITE_API_BASE
  : (typeof window !== 'undefined' && window.location && window.location.port === '5000'
      ? 'http://localhost:8001/api'
      : '/api');

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

export interface ScannerMode {
  name: string;
  description: string;
  timeframes: string[];
  min_confluence_score: number;
  profile: string;
}

export interface Signal {
  symbol: string;
  direction: 'LONG' | 'SHORT';
  score: number;
  entry_near: number;
  entry_far: number;
  stop_loss: number;
  targets: Array<{ level: number; percentage: number }>;
  primary_timeframe?: string;
  timeframe?: string;
  current_price?: number;
  analysis: {
    order_blocks?: number;
    fvgs?: number;
    structural_breaks?: number;
    liquidity_sweeps?: number;
    trend?: string;
    risk_reward?: number;
    confluence_score?: number;
    expected_value?: number;
  };
  smc_geometry?: {
    order_blocks?: any[];
    fvgs?: any[];
    bos_choch?: any[];
    liquidity_sweeps?: any[];
  };
  rationale: string;
  setup_type: string;
}

export interface SignalsResponse {
  signals: Signal[];
  total: number;
  scanned: number;
  mode: string;
  applied_timeframes: string[];
  effective_min_score: number;
  baseline_min_score: number;
  profile: string;
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
  public readonly baseURL = API_BASE;

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
        // Try JSON error first; fall back to text or generic message.
        try {
          const errJson = await response.json();
          return { error: (errJson && (errJson.detail || errJson.error)) || `${response.status} ${response.statusText}` };
        } catch {
          try {
            const errText = await response.text();
            return { error: errText || `${response.status} ${response.statusText}` };
          } catch {
            return { error: `${response.status} ${response.statusText}` };
          }
        }
      }

      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        return { data: undefined };
      }

      try {
        const data = await response.json();
        return { data };
      } catch {
        return { data: undefined };
      }
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

  async getScannerModes() {
    return this.request<{ modes: ScannerMode[]; total: number }>('/scanner/modes');
  }

  async getSignals(params?: { 
    limit?: number; 
    min_score?: number; 
    sniper_mode?: string;
    majors?: boolean;
    altcoins?: boolean;
    meme_mode?: boolean;
    exchange?: string;
    leverage?: number;
    macro_overlay?: boolean;
  }) {
    const queryParams: Record<string, string> = {};
    if (params) {
      if (params.limit !== undefined) queryParams.limit = params.limit.toString();
      if (params.min_score !== undefined) queryParams.min_score = params.min_score.toString();
      if (params.sniper_mode) queryParams.sniper_mode = params.sniper_mode;
      if (params.majors !== undefined) queryParams.majors = params.majors.toString();
      if (params.altcoins !== undefined) queryParams.altcoins = params.altcoins.toString();
      if (params.meme_mode !== undefined) queryParams.meme_mode = params.meme_mode.toString();
      if (params.exchange) queryParams.exchange = params.exchange;
      if (params.leverage !== undefined) queryParams.leverage = params.leverage.toString();
      if (params.macro_overlay !== undefined) queryParams.macro_overlay = params.macro_overlay.toString();
    }
    const query = new URLSearchParams(queryParams).toString();
    return this.request<SignalsResponse>(
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
  async getPrice(symbol: string, exchange?: string) {
    const qp = exchange ? `?exchange=${encodeURIComponent(exchange)}` : '';
    return this.request<{ symbol: string; price: number; timestamp: string }>(
      `/market/price/${encodeURIComponent(symbol)}${qp}`
    );
  }

  async getPrices(symbols: string[], exchange?: string) {
    const symbolsParam = symbols.join(',');
    const qp = new URLSearchParams();
    qp.set('symbols', symbolsParam);
    if (exchange) qp.set('exchange', exchange);
    
    return this.request<{
      prices: Array<{ symbol: string; price: number; timestamp: string }>;
      total: number;
      errors?: Array<{ symbol: string; error: string }>;
      exchange: string;
    }>(`/market/prices?${qp.toString()}`);
  }

  async getCandles(symbol: string, timeframe = '1h', limit = 100) {
    return this.request(
      `/market/candles/${symbol}?timeframe=${timeframe}&limit=${limit}`
    );
  }

  // Regime data
  async getMarketRegime() {
    return this.request<{
      composite: string;
      score: number;
      dimensions: {
        trend: string;
        volatility: string;
        liquidity: string;
        risk_appetite: string;
        derivatives: string;
      };
      trend_score: number;
      volatility_score: number;
      liquidity_score: number;
      risk_score: number;
      derivatives_score: number;
      timestamp: string;
    }>('/market/regime');
  }

  // HTF tactical opportunities
  async getHTFOpportunities(params?: { min_confidence?: number; proximity_threshold?: number }) {
    const qp = new URLSearchParams();
    if (params?.min_confidence !== undefined) qp.set('min_confidence', params.min_confidence.toString());
    if (params?.proximity_threshold !== undefined) qp.set('proximity_threshold', params.proximity_threshold.toString());
    return this.request<{ opportunities: Array<{
      symbol: string;
      level: { price: number; level_type: string; timeframe: string; strength: number; touches: number; proximity_pct: number };
      current_price: number;
      recommended_mode: string;
      rationale: string;
      confluence_factors: string[];
      expected_move_pct: number;
      confidence: number;
    }>; total: number; timestamp: string }>(`/htf/opportunities${qp.toString() ? `?${qp.toString()}` : ''}`);
  }

  // Optional: symbol-specific regime (if backend supports symbol query)
  async getSymbolRegime(symbol: string) {
    return this.request<{
      symbol: string;
      trend: string;
      volatility: string;
      score: number;
      timestamp: string;
    }>(`/market/regime?symbol=${encodeURIComponent(symbol)}`);
  }

  // Background scan jobs
  async createScanRun(params: {
    limit?: number;
    min_score?: number;
    sniper_mode?: string;
    majors?: boolean;
    altcoins?: boolean;
    meme_mode?: boolean;
    exchange?: string;
    leverage?: number;
  }) {
    const queryParams: Record<string, string> = {};
    if (params.limit !== undefined) queryParams.limit = params.limit.toString();
    if (params.min_score !== undefined) queryParams.min_score = params.min_score.toString();
    if (params.sniper_mode) queryParams.sniper_mode = params.sniper_mode;
    if (params.majors !== undefined) queryParams.majors = params.majors.toString();
    if (params.altcoins !== undefined) queryParams.altcoins = params.altcoins.toString();
    if (params.meme_mode !== undefined) queryParams.meme_mode = params.meme_mode.toString();
    if (params.exchange) queryParams.exchange = params.exchange;
    if (params.leverage !== undefined) queryParams.leverage = params.leverage.toString();

    const query = new URLSearchParams(queryParams).toString();
    return this.request<{
      run_id: string;
      status: string;
      created_at: string;
    }>(`/scanner/runs${query ? `?${query}` : ''}`, { method: 'POST' });
  }

  async getScanRun(runId: string) {
    return this.request<{
      run_id: string;
      status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
      progress: number;
      total: number;
      current_symbol?: string;
      created_at: string;
      started_at?: string;
      completed_at?: string;
      signals?: Signal[];
      metadata?: Record<string, any>;
      rejections?: Record<string, any>;
      error?: string;
    }>(`/scanner/runs/${runId}`);
  }

  async cancelScanRun(runId: string) {
    return this.request(`/scanner/runs/${runId}`, { method: 'DELETE' });
  }
}

export const api = new ApiClient();
