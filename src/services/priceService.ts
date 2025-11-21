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

  constructor() {
    this.connect();
  }

  private connect() {
    if (this.isConnecting || this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    this.isConnecting = true;

    try {
      this.ws = new WebSocket('wss://stream.binance.com:9443/ws/!ticker@arr');

      this.ws.onopen = () => {
        console.log('✅ Price service connected');
        this.reconnectAttempts = 0;
        this.isConnecting = false;
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (Array.isArray(data)) {
            data.forEach((ticker) => this.processTicker(ticker));
          } else {
            this.processTicker(data);
          }
        } catch (error) {
          console.error('Error parsing price data:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('Price service error:', error);
      };

      this.ws.onclose = () => {
        console.log('Price service disconnected');
        this.isConnecting = false;
        this.ws = null;
        this.scheduleReconnect();
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.isConnecting = false;
      this.scheduleReconnect();
    }
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

    return () => {
      const subscribers = this.subscribers.get(normalizedSymbol);
      if (subscribers) {
        subscribers.delete(callback);
        if (subscribers.size === 0) {
          this.subscribers.delete(normalizedSymbol);
          this.subscribedSymbols.delete(normalizedSymbol);
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

    return () => {
      const subscribers = this.tickSubscribers.get(normalizedSymbol);
      if (subscribers) {
        subscribers.delete(callback);
        if (subscribers.size === 0) {
          this.tickSubscribers.delete(normalizedSymbol);
          this.subscribedSymbols.delete(normalizedSymbol);
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

    const binanceSymbol = symbol.replace('/', '');
    const response = await fetch(`https://api.binance.com/api/v3/ticker/24hr?symbol=${binanceSymbol}`);
    
    if (!response.ok) {
      throw new Error(`Failed to fetch price for ${symbol}`);
    }

    const data = await response.json();
    
    const priceData: PriceData = {
      symbol,
      price: parseFloat(data.lastPrice),
      change24h: parseFloat(data.priceChange),
      changePercent24h: parseFloat(data.priceChangePercent),
      high24h: parseFloat(data.highPrice),
      low24h: parseFloat(data.lowPrice),
      volume24h: parseFloat(data.volume),
      timestamp: data.closeTime || Date.now(),
      exchange: 'Binance',
    };

    this.priceCache.set(symbol, priceData);
    return priceData;
  }

  async fetchMultiplePrices(symbols: string[]): Promise<Map<string, PriceData>> {
    const results = new Map<string, PriceData>();
    
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
  }
}

export const priceService = new PriceService();
