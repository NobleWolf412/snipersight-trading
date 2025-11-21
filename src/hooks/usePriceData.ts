import { useEffect, useState } from 'react';
import { priceService, type PriceData, type PriceTick } from '@/services/priceService';

export function usePrice(symbol: string | null) {
  const [priceData, setPriceData] = useState<PriceData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol) {
      setPriceData(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    priceService
      .fetchPrice(symbol)
      .then((data) => {
        setPriceData(data);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setIsLoading(false);
      });

    const unsubscribe = priceService.subscribe(symbol, (data) => {
      setPriceData(data);
    });

    return () => {
      unsubscribe();
    };
  }, [symbol]);

  return { priceData, isLoading, error };
}

export function usePriceTick(symbol: string | null) {
  const [tick, setTick] = useState<PriceTick | null>(null);

  useEffect(() => {
    if (!symbol) {
      setTick(null);
      return;
    }

    const unsubscribe = priceService.subscribeTick(symbol, (tickData) => {
      setTick(tickData);
    });

    return () => {
      unsubscribe();
    };
  }, [symbol]);

  return tick;
}

export function useMultiplePrices(symbols: string[]) {
  const [prices, setPrices] = useState<Map<string, PriceData>>(new Map());
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (symbols.length === 0) {
      setPrices(new Map());
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    priceService
      .fetchMultiplePrices(symbols)
      .then((data) => {
        setPrices(data);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setIsLoading(false);
      });

    const unsubscribers = symbols.map((symbol) =>
      priceService.subscribe(symbol, (data) => {
        setPrices((prev) => new Map(prev).set(symbol, data));
      })
    );

    return () => {
      unsubscribers.forEach((unsub) => unsub());
    };
  }, [symbols.join(',')]);

  return { prices, isLoading, error };
}
