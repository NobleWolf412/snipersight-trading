export interface PriceData {
  symbol: string;
  price: number;
  change24h: number;
  changePercent24h: number;
  high24h: number;
  low24h: number;
  volume24h: number;
  timestamp: number;
  exchange: string;
}

export interface PriceTick {
  symbol: string;
  price: number;
  timestamp: number;
}

type PriceUpdateCallback = (data: PriceData) => void;
type TickUpdateCallback = (tick: PriceTick) => void;

import { api } from '@/utils/api';

class PriceService {
  private ws: WebSocket | null = null;
  private reconnectTimer: number | null = null;
  private priceCache: Map<string, PriceData> = new Map();
  private subscribers: Map<string, Set<PriceUpdateCallback>> = new Map();
  private tickSubscribers: Map<string, Set<TickUpdateCallback>> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private subscribedSymbols: Set<string> = new Set();
  private isConnecting = false;
  private pollers: Map<string, number> = new Map();
  private exchange: string = 'phemex';

  constructor() {
    // Disable direct Binance WebSocket in browser to avoid CORS/network blocks.
    // We will poll backend prices instead.
  }

  // Kept for potential future backend WS support; currently unused.
  private connect() {
    return;
  }

  private processTicker(ticker: any) {
    const symbol = this.normalizeSymbol(ticker.s);
    
    if (!this.subscribedSymbols.has(symbol)) {
      return;
    }
    
    const priceData: PriceData = {
      symbol,
      price: parseFloat(ticker.c),
      change24h: parseFloat(ticker.p),
      changePercent24h: parseFloat(ticker.P),
      high24h: parseFloat(ticker.h),
      low24h: parseFloat(ticker.l),
      volume24h: parseFloat(ticker.v),
      timestamp: ticker.E || Date.now(),
      exchange: 'Binance',
    };

    this.priceCache.set(symbol, priceData);

    const subscribers = this.subscribers.get(symbol);
    if (subscribers && subscribers.size > 0) {
      subscribers.forEach((callback) => callback(priceData));
    }

    const tickSubscribers = this.tickSubscribers.get(symbol);
    if (tickSubscribers && tickSubscribers.size > 0) {
      const tick: PriceTick = {
        symbol,
        price: priceData.price,
        timestamp: priceData.timestamp,
      };
      tickSubscribers.forEach((callback) => callback(tick));
    }
  }

  private normalizeSymbol(binanceSymbol: string): string {
    if (binanceSymbol.endsWith('USDT')) {
      const base = binanceSymbol.replace('USDT', '');
      return `${base}/USDT`;
    }
    return binanceSymbol;
  }

  private scheduleReconnect() {
    if (this.reconnectTimer !== null) {
      return;
    }

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnect attempts reached');
      return;
    }

    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts++;

    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      console.log(`Reconnecting (attempt ${this.reconnectAttempts})...`);
      this.connect();
    }, delay);
  }

  subscribe(symbol: string, callback: PriceUpdateCallback): () => void {
    const normalizedSymbol = symbol;
    
    if (!this.subscribers.has(normalizedSymbol)) {
      this.subscribers.set(normalizedSymbol, new Set());
    }
    
    this.subscribers.get(normalizedSymbol)!.add(callback);
    this.subscribedSymbols.add(normalizedSymbol);

    const cached = this.priceCache.get(normalizedSymbol);
    if (cached) {
      callback(cached);
    }

    this.ensurePolling(normalizedSymbol);

    return () => {
      const subscribers = this.subscribers.get(normalizedSymbol);
      if (subscribers) {
        subscribers.delete(callback);
        if (subscribers.size === 0) {
          this.subscribers.delete(normalizedSymbol);
          this.subscribedSymbols.delete(normalizedSymbol);
          this.maybeStopPolling(normalizedSymbol);
        }
      }
    };
  }

  subscribeTick(symbol: string, callback: TickUpdateCallback): () => void {
    const normalizedSymbol = symbol;
    
    if (!this.tickSubscribers.has(normalizedSymbol)) {
      this.tickSubscribers.set(normalizedSymbol, new Set());
    }
    
    this.tickSubscribers.get(normalizedSymbol)!.add(callback);
    this.subscribedSymbols.add(normalizedSymbol);

    const cached = this.priceCache.get(normalizedSymbol);
    if (cached) {
      callback({
        symbol: normalizedSymbol,
        price: cached.price,
        timestamp: cached.timestamp,
      });
    }

    this.ensurePolling(normalizedSymbol);

    return () => {
      const subscribers = this.tickSubscribers.get(normalizedSymbol);
      if (subscribers) {
        subscribers.delete(callback);
        if (subscribers.size === 0) {
          this.tickSubscribers.delete(normalizedSymbol);
          this.subscribedSymbols.delete(normalizedSymbol);
          this.maybeStopPolling(normalizedSymbol);
        }
      }
    };
  }

  getPrice(symbol: string): PriceData | undefined {
    return this.priceCache.get(symbol);
  }

  async fetchPrice(symbol: string): Promise<PriceData> {
    const cached = this.priceCache.get(symbol);
    if (cached && Date.now() - cached.timestamp < 5000) {
      return cached;
    }

    // Use bulk endpoint with single symbol
    const { data, error } = await api.getPrices([symbol], this.exchange);
    if (error || !data || data.prices.length === 0) {
      throw new Error(error || `Failed to fetch price for ${symbol}`);
    }

    const item = data.prices[0];
    const priceData: PriceData = {
      symbol: item.symbol,
      price: Number(item.price) || 0,
      change24h: 0,
      changePercent24h: 0,
      high24h: 0,
      low24h: 0,
      volume24h: 0,
      timestamp: new Date(item.timestamp).getTime() || Date.now(),
      exchange: data.exchange,
    };

    this.priceCache.set(symbol, priceData);
    return priceData;
  }

  async fetchMultiplePrices(symbols: string[]): Promise<Map<string, PriceData>> {
    const results = new Map<string, PriceData>();
    
    // Use bulk endpoint if more than 3 symbols
    if (symbols.length > 3) {
      try {
        const { data, error } = await api.getPrices(symbols, this.exchange);
        if (error || !data) {
          throw new Error(error || 'Failed to fetch bulk prices');
        }

        // Process successful prices
        for (const item of data.prices) {
          const priceData: PriceData = {
            symbol: item.symbol,
            price: Number(item.price) || 0,
            change24h: 0,
            changePercent24h: 0,
            high24h: 0,
            low24h: 0,
            volume24h: 0,
            timestamp: new Date(item.timestamp).getTime() || Date.now(),
            exchange: data.exchange,
          };
          results.set(item.symbol, priceData);
          this.priceCache.set(item.symbol, priceData);
        }

        // Log errors if any
        if (data.errors && data.errors.length > 0) {
          data.errors.forEach(err => {
            console.warn(`Failed to fetch ${err.symbol}: ${err.error}`);
          });
        }

        return results;
      } catch (error) {
        console.error('Bulk price fetch failed, falling back to individual requests:', error);
        // Fall through to individual fetches
      }
    }

    // Fallback: individual requests (or for small lists)
    await Promise.all(
      symbols.map(async (symbol) => {
        try {
          const price = await this.fetchPrice(symbol);
          results.set(symbol, price);
        } catch (error) {
          console.error(`Failed to fetch price for ${symbol}:`, error);
        }
      })
    );

    return results;
  }

  disconnect() {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.subscribers.clear();
    this.tickSubscribers.clear();
    this.subscribedSymbols.clear();

    // Stop all pollers
    this.pollers.forEach((id) => clearInterval(id));
    this.pollers.clear();
  }

  setExchange(exchange: string) {
    this.exchange = exchange || 'phemex';
  }

  private ensurePolling(symbol: string) {
    if (this.pollers.has(symbol)) return;

    // Poll backend every 3 seconds
    const id = window.setInterval(async () => {
      try {
        const data = await this.fetchPrice(symbol);
        const subs = this.subscribers.get(symbol);
        if (subs && subs.size > 0) subs.forEach((cb) => cb(data));

        const tickSubs = this.tickSubscribers.get(symbol);
        if (tickSubs && tickSubs.size > 0) {
          const tick: PriceTick = { symbol, price: data.price, timestamp: data.timestamp };
          tickSubs.forEach((cb) => cb(tick));
        }
      } catch (e) {
        // Already logged in fetchPrice via api client handling
      }
    }, 3000);

    this.pollers.set(symbol, id);
  }

  private maybeStopPolling(symbol: string) {
    const hasPriceSubs = this.subscribers.has(symbol) && (this.subscribers.get(symbol)?.size || 0) > 0;
    const hasTickSubs = this.tickSubscribers.has(symbol) && (this.tickSubscribers.get(symbol)?.size || 0) > 0;
    if (!hasPriceSubs && !hasTickSubs) {
      const id = this.pollers.get(symbol);
      if (id) {
        clearInterval(id);
        this.pollers.delete(symbol);
      }
    }
  }
}

export const priceService = new PriceService();
