import { useEffect, useState, useRef, useCallback } from 'react';
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
  const updateTimerRef = useRef<number | null>(null);
  const pendingUpdatesRef = useRef<Map<string, PriceData>>(new Map());

  const flushUpdates = useCallback(() => {
    if (pendingUpdatesRef.current.size > 0) {
      setPrices((prev) => {
        const newMap = new Map(prev);
        pendingUpdatesRef.current.forEach((data, symbol) => {
          newMap.set(symbol, data);
        });
        return newMap;
      });
      pendingUpdatesRef.current.clear();
    }
  }, []);

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
        pendingUpdatesRef.current.set(symbol, data);
        
        if (updateTimerRef.current !== null) {
          return;
        }
        
        updateTimerRef.current = window.setTimeout(() => {
          flushUpdates();
          updateTimerRef.current = null;
        }, 100);
      })
    );

    return () => {
      if (updateTimerRef.current !== null) {
        clearTimeout(updateTimerRef.current);
        updateTimerRef.current = null;
      }
      unsubscribers.forEach((unsub) => unsub());
      pendingUpdatesRef.current.clear();
    };
  }, [symbols.join(','), flushUpdates]);

  return { prices, isLoading, error };
}
