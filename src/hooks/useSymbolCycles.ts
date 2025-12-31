/**
 * useSymbolCycles - Hook for fetching cycle intelligence
 * 
 * Fetches DCL/WCL cycle data for symbols and caches results.
 * Also fetches BTC macro context once for 4YC data.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { api, SymbolCyclesData, BTCCycleContextData } from '@/utils/api';

interface UseSymbolCyclesOptions {
  symbols: string[];
  exchange?: string;
  autoFetch?: boolean;
  fetchBTCContext?: boolean;
}

interface UseSymbolCyclesResult {
  cycles: Record<string, SymbolCyclesData>;
  btcContext: BTCCycleContextData | null;
  loading: boolean;
  error: string | null;
  fetchCycle: (symbol: string) => Promise<SymbolCyclesData | null>;
  refetch: () => void;
}

// Cache to avoid refetching on re-renders
const cycleCache = new Map<string, { data: SymbolCyclesData; timestamp: number }>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

export function useSymbolCycles({
  symbols,
  exchange = 'phemex',
  autoFetch = true,
  fetchBTCContext = true
}: UseSymbolCyclesOptions): UseSymbolCyclesResult {
  const [cycles, setCycles] = useState<Record<string, SymbolCyclesData>>({});
  const [btcContext, setBtcContext] = useState<BTCCycleContextData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchedRef = useRef(new Set<string>());
  const btcFetchedRef = useRef(false);

  // Fetch single symbol cycle
  const fetchCycle = useCallback(async (symbol: string): Promise<SymbolCyclesData | null> => {
    // Check cache first
    const cacheKey = `${symbol}-${exchange}`;
    const cached = cycleCache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      setCycles(prev => ({ ...prev, [symbol]: cached.data }));
      return cached.data;
    }

    try {
      const response = await api.getSymbolCycles(symbol, exchange);
      if (response.data?.status === 'success' && response.data.data) {
        const data = response.data.data;

        // Cache it
        cycleCache.set(cacheKey, { data, timestamp: Date.now() });

        // Update state
        setCycles(prev => ({ ...prev, [symbol]: data }));
        return data;
      }
    } catch (e) {
      console.error(`Failed to fetch cycles for ${symbol}:`, e);
    }

    return null;
  }, [exchange]);

  // Fetch BTC context
  const fetchBTC = useCallback(async () => {
    if (btcFetchedRef.current) return;
    btcFetchedRef.current = true;

    try {
      const response = await api.getBTCCycleContext();
      if (response.data?.status === 'success' && response.data.data) {
        setBtcContext(response.data.data);
      }
    } catch (e) {
      console.error('Failed to fetch BTC context:', e);
    }
  }, []);

  // Batch fetch for multiple symbols
  const fetchAll = useCallback(async () => {
    if (!symbols.length) return;

    setLoading(true);
    setError(null);

    try {
      // Fetch BTC context first (if enabled)
      if (fetchBTCContext) {
        await fetchBTC();
      }

      // Fetch cycles for each symbol (limit concurrency)
      const BATCH_SIZE = 3;
      for (let i = 0; i < symbols.length; i += BATCH_SIZE) {
        const batch = symbols.slice(i, i + BATCH_SIZE);
        await Promise.all(
          batch
            .filter(s => !fetchedRef.current.has(s))
            .map(async (symbol) => {
              fetchedRef.current.add(symbol);
              await fetchCycle(symbol);
            })
        );
      }
    } catch (e) {
      setError('Failed to fetch cycle data');
    } finally {
      setLoading(false);
    }
  }, [symbols, fetchBTCContext, fetchBTC, fetchCycle]);

  // Auto-fetch on mount if enabled
  useEffect(() => {
    if (autoFetch && symbols.length > 0) {
      fetchAll();
    }
  }, [autoFetch, symbols.join(','), fetchAll]);

  // Refetch function
  const refetch = useCallback(() => {
    fetchedRef.current.clear();
    btcFetchedRef.current = false;
    cycleCache.clear();
    fetchAll();
  }, [fetchAll]);

  return {
    cycles,
    btcContext,
    loading,
    error,
    fetchCycle,
    refetch
  };
}

/**
 * Get cycle alignment status for a signal
 */
export function getCycleAlignment(
  symbolCycles: SymbolCyclesData | undefined,
  btcMacroBias: string | undefined,
  direction: 'LONG' | 'SHORT' | 'BULLISH' | 'BEARISH'
): {
  aligned: boolean;
  partial: boolean;
  conflicts: string[];
} {
  const normalizedDirection = direction === 'BULLISH' ? 'LONG' : direction === 'BEARISH' ? 'SHORT' : direction;

  if (!symbolCycles) {
    return { aligned: true, partial: false, conflicts: [] };
  }

  const conflicts: string[] = [];

  // Check DCL
  const dclOk = normalizedDirection === 'LONG'
    ? symbolCycles.dcl.bias !== 'SHORT'
    : symbolCycles.dcl.bias !== 'LONG';

  if (!dclOk) {
    conflicts.push(`DCL ${symbolCycles.dcl.translation === 'left_translated' ? 'LTR' : 'RTR'}`);
  }

  // Check WCL  
  const wclOk = normalizedDirection === 'LONG'
    ? symbolCycles.wcl.bias !== 'SHORT'
    : symbolCycles.wcl.bias !== 'LONG';

  if (!wclOk) {
    conflicts.push(`WCL ${symbolCycles.wcl.translation === 'left_translated' ? 'LTR' : 'RTR'}`);
  }

  // Check 4YC (BTC macro)
  let macroOk = true;
  if (btcMacroBias) {
    if (normalizedDirection === 'LONG' && btcMacroBias === 'BEARISH') {
      macroOk = false;
      conflicts.push('4YC BEARISH');
    } else if (normalizedDirection === 'SHORT' && btcMacroBias === 'BULLISH') {
      macroOk = false;
      conflicts.push('4YC BULLISH');
    }
  }

  const allOk = dclOk && wclOk && macroOk;
  const someOk = dclOk || wclOk || macroOk;

  return {
    aligned: allOk,
    partial: !allOk && someOk,
    conflicts
  };
}

export default useSymbolCycles;
