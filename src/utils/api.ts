/**
 * API Client for SniperSight Backend
 * 
 * Provides typed methods for interacting with the FastAPI backend.
 * Includes retry logic with exponential backoff and request timeouts.
 */

import { debugLogger } from './debugLogger';

// Resolve API base: prefer Vite env, otherwise use same-origin '/api' (proxied through Vite)
// NOTE: Never hardcode localhost:8001 - breaks on Chromebook Crostini where localhost != container
const API_BASE = (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_BASE)
  ? (import.meta as any).env.VITE_API_BASE
  : '/api';

// Retry configuration
const DEFAULT_TIMEOUT_MS = 30000; // 30 seconds
const SCANNER_TIMEOUT_MS = 120000; // 2 minutes for scanner (fetches multi-TF data)
const DEFAULT_MAX_RETRIES = 3;
const RETRY_BASE_DELAY_MS = 1000;
const RETRYABLE_STATUS_CODES = [408, 429, 500, 502, 503, 504];

// Circuit breaker - prevents hammering a dead backend
let circuitBreakerOpen = false;
let circuitBreakerTrippedAt = 0;
let consecutiveFailures = 0;
const CIRCUIT_BREAKER_THRESHOLD = 5; // Open circuit after 5 consecutive failures
const CIRCUIT_BREAKER_RESET_MS = 30000; // Try again after 30 seconds

interface ApiResponse<T> {
  data?: T;
  error?: string;
}

interface RequestOptions extends RequestInit {
  timeout?: number;
  maxRetries?: number;
  skipRetry?: boolean;
  silent?: boolean; // Suppress debug logs for this request
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
  // Extended fields synced with backend scanner_modes.py
  critical_timeframes?: string[];
  primary_planning_timeframe?: string;
  entry_timeframes?: string[];
  structure_timeframes?: string[];
  zone_timeframes?: string[];
  target_timeframes?: string[];
  stop_timeframes?: string[];
  atr_multiplier?: number;
  min_rr_ratio?: number;
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
  rejected: number;
  mode: string;
  applied_timeframes: string[];
  critical_timeframes: string[];
  active_mode: {
    name: string;
    profile: string;
    timeframes: string[];
    critical_timeframes: string[];
    baseline_min_confluence: number;
  };
  effective_min_score: number;
  baseline_min_score: number;
  profile: string;
  exchange: string;
  leverage: number;
  categories: {
    majors: boolean;
    altcoins: boolean;
    meme_mode: boolean;
  };
  rejections: {
    total_rejected: number;
    by_reason: Record<string, number>;
    details: Record<string, any[]>;
    regime?: {
      composite: string;
      score: number;
      policy_min_score: number;
    };
  };
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

  /**
   * Sleep for specified milliseconds
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Check if error is retryable
   */
  private isRetryable(status: number): boolean {
    return RETRYABLE_STATUS_CODES.includes(status);
  }

  /**
   * Calculate exponential backoff delay with jitter
   */
  private getRetryDelay(attempt: number): number {
    const baseDelay = RETRY_BASE_DELAY_MS * Math.pow(2, attempt);
    const jitter = Math.random() * 0.3 * baseDelay; // 0-30% jitter
    return Math.min(baseDelay + jitter, 10000); // Cap at 10s
  }

  private async request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<ApiResponse<T>> {
    const {
      timeout = DEFAULT_TIMEOUT_MS,
      maxRetries = DEFAULT_MAX_RETRIES,
      skipRetry = false,
      silent = false,
      ...fetchOptions
    } = options;

    const method = fetchOptions.method || 'GET';
    const fullUrl = `${API_BASE}${endpoint}`;

    // Circuit breaker check - fail fast if backend is known to be down
    if (circuitBreakerOpen) {
      const elapsed = Date.now() - circuitBreakerTrippedAt;
      if (elapsed < CIRCUIT_BREAKER_RESET_MS) {
        const remaining = Math.round((CIRCUIT_BREAKER_RESET_MS - elapsed) / 1000);
        if (!silent) debugLogger.warning(`⚡ Circuit breaker OPEN - skipping request (retry in ${remaining}s)`, 'api');
        return { error: `Backend unavailable - retry in ${remaining}s` };
      }
      // Reset circuit breaker and try again
      circuitBreakerOpen = false;
      consecutiveFailures = 0;
      if (!silent) debugLogger.info(`⚡ Circuit breaker RESET - attempting connection`, 'api');
    }

    if (!silent) {
      debugLogger.api(`→ ${method} ${endpoint}`);
      debugLogger.info(`Connecting to: ${fullUrl}`, 'api');
      debugLogger.info(`Timeout: ${timeout / 1000}s | Retries: ${skipRetry ? 'disabled' : maxRetries}`, 'api');
    }

    let lastError: string = 'Unknown error';

    for (let attempt = 0; attempt <= (skipRetry ? 0 : maxRetries); attempt++) {
      // Add delay before retry (not on first attempt)
      if (attempt > 0) {
        const delay = this.getRetryDelay(attempt - 1);
        if (!silent) debugLogger.warning(`⟳ Retry ${attempt}/${maxRetries} (waiting ${Math.round(delay)}ms)`, 'api');
        // console.log(`[API] Retry attempt ${attempt}/${maxRetries} after ${Math.round(delay)}ms`);
        await this.sleep(delay);
      }

      // Create AbortController for timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);
      const startTime = Date.now();

      try {
        if (!silent) debugLogger.info(`Sending request... (attempt ${attempt + 1})`, 'api');

        const response = await fetch(`${API_BASE}${endpoint}`, {
          ...fetchOptions,
          signal: controller.signal,
          headers: {
            'Content-Type': 'application/json',
            ...fetchOptions.headers,
          },
        });

        clearTimeout(timeoutId);
        const elapsed = Date.now() - startTime;
        if (!silent) debugLogger.info(`Response: ${response.status} ${response.statusText} (${elapsed}ms)`, 'api');

        if (!response.ok) {
          // Check if retryable status
          if (!skipRetry && this.isRetryable(response.status) && attempt < maxRetries) {
            lastError = `${response.status} ${response.statusText}`;
            if (!silent) debugLogger.warning(`Retryable error: ${lastError}`, 'api');
            continue; // Retry
          }

          // Try JSON error first; fall back to text or generic message.
          try {
            const errJson = await response.json();
            const errMsg = (errJson && (errJson.detail || errJson.error)) || `${response.status} ${response.statusText}`;
            if (!silent) debugLogger.error(`API Error: ${errMsg}`, 'api');
            return { error: errMsg };
          } catch {
            try {
              const errText = await response.text();
              if (!silent) debugLogger.error(`API Error: ${errText || response.statusText}`, 'api');
              return { error: errText || `${response.status} ${response.statusText}` };
            } catch {
              if (!silent) debugLogger.error(`API Error: ${response.status} ${response.statusText}`, 'api');
              return { error: `${response.status} ${response.statusText}` };
            }
          }
        }

        const contentType = response.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
          if (!silent) debugLogger.success(`✓ Request completed (no JSON body)`, 'api');
          consecutiveFailures = 0; // Reset on success
          return { data: undefined };
        }

        try {
          const data = await response.json();
          if (!silent) debugLogger.success(`✓ Request successful`, 'api');
          consecutiveFailures = 0; // Reset on success
          return { data };
        } catch {
          if (!silent) debugLogger.warning('Response was not valid JSON', 'api');
          consecutiveFailures = 0; // Reset on success (even if JSON parse fails, backend responded)
          return { data: undefined };
        }
      } catch (error) {
        clearTimeout(timeoutId);
        const elapsed = Date.now() - startTime;

        if (error instanceof Error) {
          if (error.name === 'AbortError') {
            lastError = `Request timeout after ${timeout / 1000}s`;
            if (!silent) debugLogger.error(`⏱ Timeout after ${elapsed}ms (limit: ${timeout}ms)`, 'api');
          } else {
            lastError = error.message;
            if (!silent) debugLogger.error(`Network error: ${error.message}`, 'api');
          }

          // Network errors are retryable
          if (!skipRetry && attempt < maxRetries &&
            (error.name === 'AbortError' || error.message.includes('network') || error.message.includes('fetch'))) {
            if (!silent) debugLogger.info('Will retry...', 'api');
            continue; // Retry
          }
        }

        // Track consecutive failures for circuit breaker
        consecutiveFailures++;
        if (consecutiveFailures >= CIRCUIT_BREAKER_THRESHOLD) {
          circuitBreakerOpen = true;
          circuitBreakerTrippedAt = Date.now();
          if (!silent) debugLogger.error(`⚡ Circuit breaker TRIPPED after ${consecutiveFailures} failures - pausing requests for 30s`, 'api');
        }

        if (!silent) debugLogger.error(`✗ Request failed: ${lastError}`, 'api');
        return { error: lastError };
      }
    }

    // Track consecutive failures for circuit breaker
    consecutiveFailures++;
    if (consecutiveFailures >= CIRCUIT_BREAKER_THRESHOLD) {
      circuitBreakerOpen = true;
      circuitBreakerTrippedAt = Date.now();
      if (!silent) debugLogger.error(`⚡ Circuit breaker TRIPPED after ${consecutiveFailures} failures - pausing requests for 30s`, 'api');
    }

    if (!silent) debugLogger.error(`✗ All ${maxRetries} retries exhausted: ${lastError}`, 'api');
    return { error: `Failed after ${maxRetries} retries: ${lastError}` };
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

  async getScannerRecommendation() {
    return this.request<{
      mode: string;
      reason: string;
      warning: string | null;
      confidence: string;
      regime?: any;
    }>('/scanner/recommendation');
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
    market_type?: string;
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
      if (params.market_type) queryParams.market_type = params.market_type;
    }
    const query = new URLSearchParams(queryParams).toString();
    return this.request<SignalsResponse>(
      `/scanner/signals${query ? `?${query}` : ''}`,
      { timeout: SCANNER_TIMEOUT_MS, skipRetry: true } // Scanner needs more time, don't retry
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
      `/market/price/${encodeURIComponent(symbol)}${qp}`,
      { silent: import.meta.env.MODE === 'production' }
    );
  }

  async getPrices(symbols: string[], exchange?: string, options?: { silent?: boolean }) {
    const symbolsParam = symbols.join(',');
    const qp = new URLSearchParams();
    qp.set('symbols', symbolsParam);
    if (exchange) qp.set('exchange', exchange);

    // Merge environment-aware default with explicit options
    const silent = options?.silent ?? (import.meta.env.MODE === 'production');

    return this.request<{
      prices: Array<{ symbol: string; price: number; timestamp: string }>;
      total: number;
      errors?: Array<{ symbol: string; error: string }>;
      exchange: string;
    }>(`/market/prices?${qp.toString()}`,
      { silent }
    );
  }

  async getCandles(symbol: string, timeframe = '1h', limit = 100) {
    return this.request(
      `/market/candles/${encodeURIComponent(symbol)}?timeframe=${timeframe}&limit=${limit}`
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
      dominance?: {
        btc_d: number;
        alt_d: number;
        stable_d: number;
      };
      timestamp: string;
    }>('/market/regime', { silent: import.meta.env.MODE === 'production' });
  }

  // Market cycle context (DCL/WCL timing, translation, stochRSI zones)
  async getMarketCycles(symbol: string = 'BTC/USDT') {
    return this.request<{
      symbol: string;
      dcl: {
        days_since: number | null;
        price: number | null;
        timestamp: string | null;
        confirmation: string;
        in_zone: boolean;
        expected_window: { min_days: number; max_days: number };
        typical_range: { min: number; max: number };
      } | null;
      wcl: {
        days_since: number | null;
        price: number | null;
        timestamp: string | null;
        confirmation: string;
        in_zone: boolean;
        expected_window: { min_days: number; max_days: number };
        typical_range: { min: number; max: number };
      } | null;
      cycle_high: {
        price: number | null;
        timestamp: string | null;
        midpoint_price: number | null;
      };
      phase: 'ACCUMULATION' | 'MARKUP' | 'DISTRIBUTION' | 'MARKDOWN' | 'UNKNOWN';
      translation: 'LEFT_TRANSLATED' | 'MID_TRANSLATED' | 'RIGHT_TRANSLATED' | 'UNKNOWN';
      trade_bias: 'LONG' | 'SHORT' | 'NEUTRAL';
      confidence: number;
      stochastic_rsi: {
        k: number | null;
        d: number | null;
        zone: 'oversold' | 'overbought' | 'neutral';
      };
      interpretation: {
        messages: string[];
        severity: 'neutral' | 'bullish' | 'bearish' | 'caution';
        summary: string;
      };
      timestamp: string;
      error?: string;
    }>(`/market/cycles?symbol=${encodeURIComponent(symbol)}`, { silent: import.meta.env.MODE === 'production' });
  }

  // HTF tactical opportunities
  async getHTFOpportunities(params?: { min_confidence?: number; proximity_threshold?: number }) {
    const qp = new URLSearchParams();
    if (params?.min_confidence !== undefined) qp.set('min_confidence', params.min_confidence.toString());
    if (params?.proximity_threshold !== undefined) qp.set('proximity_threshold', params.proximity_threshold.toString());
    return this.request<{
      opportunities: Array<{
        symbol: string;
        level: { price: number; level_type: string; timeframe: string; strength: number; touches: number; proximity_pct: number };
        current_price: number;
        recommended_mode: string;
        rationale: string;
        confluence_factors: string[];
        expected_move_pct: number;
        confidence: number;
      }>; total: number; timestamp: string
    }>(`/htf/opportunities${qp.toString() ? `?${qp.toString()}` : ''}`, { timeout: 90000 }); // Increase timeout to 90s for heavy analysis
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
    macro_overlay?: boolean;
    market_type?: string;
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
    if (params.macro_overlay !== undefined) queryParams.macro_overlay = params.macro_overlay.toString();
    if (params.market_type) queryParams.market_type = params.market_type;

    const query = new URLSearchParams(queryParams).toString();
    return this.request<{
      run_id: string;
      status: string;
      created_at: string;
    }>(`/scanner/runs${query ? `?${query}` : ''}`, {
      method: 'POST',
      timeout: SCANNER_TIMEOUT_MS  // Allow deep scans to initialize (120s)
    });
  }

  async getScanRun(runId: string, options?: { silent?: boolean }) {
    return this.request<{
      run_id: string;
      status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
      progress: number;
      total: number;
      current_symbol?: string;
      created_at: string;
      started_at?: string;
      completed_at?: string;
      logs?: string[]; // Backend workflow logs from orchestrator
      signals?: Signal[];
      metadata?: Record<string, any>;
      rejections?: Record<string, any>;
      error?: string;
    }>(`/scanner/runs/${runId}`, { ...options });
  }

  async cancelScanRun(runId: string) {
    return this.request(`/scanner/runs/${runId}`, { method: 'DELETE' });
  }

  // ---------------------------------------------------------------------------
  // Paper Trading (Training Ground)
  // ---------------------------------------------------------------------------

  async startPaperTrading(config: PaperTradingConfigRequest) {
    return this.request<PaperTradingStartResponse>('/paper-trading/start', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  async stopPaperTrading() {
    return this.request<PaperTradingStatusResponse>('/paper-trading/stop', {
      method: 'POST',
    });
  }

  async getPaperTradingStatus() {
    return this.request<PaperTradingStatusResponse>('/paper-trading/status', {
      timeout: 60000,  // 60s timeout - paper trading can be slow during active scans
    });
  }

  async getPaperTradingPositions() {
    return this.request<{
      positions: PaperTradingPosition[];
      total: number;
    }>('/paper-trading/positions');
  }

  async getPaperTradingHistory(limit = 50) {
    return this.request<{
      trades: CompletedPaperTrade[];
      total: number;
    }>(`/paper-trading/history?limit=${limit}`, {
      timeout: 60000,  // 60s timeout - paper trading can be slow during active scans
    });
  }

  async getPaperTradingActivity(limit = 100) {
    return this.request<{
      activity: PaperTradingActivity[];
      total: number;
    }>(`/paper-trading/activity?limit=${limit}`);
  }

  async resetPaperTrading() {
    return this.request<{ status: string; message: string }>('/paper-trading/reset', {
      method: 'POST',
    });
  }
}

// ---------------------------------------------------------------------------
// Paper Trading Types
// ---------------------------------------------------------------------------

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
  symbols?: string[];
  exclude_symbols?: string[];
  slippage_bps?: number;
  fee_rate?: number;
}

export interface PaperTradingPosition {
  position_id: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  entry_price: number;
  current_price: number;
  quantity: number;
  remaining_quantity: number;
  stop_loss: number;
  targets_remaining: number;
  targets_hit: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  breakeven_active: boolean;
  trailing_active: boolean;
  opened_at: string;
}

export interface CompletedPaperTrade {
  trade_id: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  entry_price: number;
  exit_price: number;
  quantity: number;
  entry_time: string;
  exit_time: string | null;
  pnl: number;
  pnl_pct: number;
  exit_reason: 'target' | 'stop_loss' | 'emergency' | 'session_stopped' | string;
  targets_hit: number[];
  max_favorable: number;
  max_adverse: number;
}

export interface PaperTradingStats {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  total_pnl_pct: number;
  avg_win: number;
  avg_loss: number;
  avg_rr: number;
  best_trade: number;
  worst_trade: number;
  max_drawdown: number;
  current_streak: number;
  scans_completed: number;
  signals_generated: number;
  signals_taken: number;
}

export interface PaperTradingActivity {
  timestamp: string;
  event_type: 'session_started' | 'session_stopped' | 'scan_started' | 'scan_completed' |
  'scan_error' | 'trade_opened' | 'trade_closed' | 'trade_error' | string;
  data: Record<string, any>;
}

export interface PaperTradingBalance {
  initial: number;
  current: number;
  equity: number;
  pnl: number;
  pnl_pct: number;
}

export interface PaperTradingStatusResponse {
  status: 'idle' | 'running' | 'paused' | 'stopped' | 'error';
  session_id: string | null;
  started_at: string | null;
  stopped_at: string | null;
  uptime_seconds: number;
  config: PaperTradingConfigRequest | null;
  balance: PaperTradingBalance | null;
  positions: PaperTradingPosition[];
  statistics: PaperTradingStats;
  recent_activity: PaperTradingActivity[];
  last_scan_at: string | null;
  next_scan_in_seconds: number | null;
  cache_stats?: {
    hit_rate_pct: number;
    entries: number;
    candles_cached: number;
  } | null;
}

export interface PaperTradingStartResponse {
  session_id: string;
  status: string;
  started_at: string;
  config: PaperTradingConfigRequest;
}

export const api = new ApiClient();
