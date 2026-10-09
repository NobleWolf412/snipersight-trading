import { useEffect, useState, useMemo } from 'react';
import { api } from '@/utils/api';

// Public shape of the regime hook's return value.
// Inlined here after the original MarketRegimeLens component was archived in
// Phase 6 sub-step 4.
export type RegimeLabel = string;
export type Visibility = 'HIGH' | 'MEDIUM' | 'LOW' | 'VERY_LOW';
export type RegimeColor = 'green' | 'blue' | 'yellow' | 'orange' | 'red';

export interface MarketRegimeLensProps {
  regimeLabel: RegimeLabel;
  visibility: Visibility;
  color?: RegimeColor;
  btcDominance?: number;
  usdtDominance?: number;
  altDominance?: number;
  // Per-dimension regime scores (0-100). Backend emits all five on
  // /api/market/regime; undefined in the loading/error fallback path.
  trendScore?: number;
  volatilityScore?: number;
  liquidityScore?: number;
  riskScore?: number;
  derivativesScore?: number;
  compositeScore?: number;
  guidanceLines?: string[];
  mode?: 'scanner' | 'bot';
  previousBtcDominance?: number;
  previousUsdtDominance?: number;
  previousAltDominance?: number;
}

export function useMarketRegime(mode: 'scanner' | 'bot' = 'scanner'): MarketRegimeLensProps {
  const [data, setData] = useState<any | null>(null);

  useEffect(() => {
    let mounted = true;
    let busy = false;
    let expiry: ReturnType<typeof setTimeout> | undefined;
    const refresh = async () => {
      if (busy) return;
      busy = true;
      try {
        const res = await api.getMarketRegime();
        if (!mounted) return;
        clearTimeout(expiry);
        const value = res.data as any;
        const expires = Date.parse(value?.expires_at ?? '');
        if (value?.dimensions && Date.now() < expires) {
          setData(value);
          expiry = setTimeout(() => setData(null), expires - Date.now());
        } else setData(null);
      } catch { if (mounted) setData(null); }
      finally { busy = false; }
    };
    void refresh();
    const interval = setInterval(() => { void refresh(); }, 60_000);
    return () => { mounted = false; clearInterval(interval); clearTimeout(expiry); };
  }, []);

  return useMemo<MarketRegimeLensProps>(() => {
    if (!data) {
      return {
        regimeLabel: 'UNAVAILABLE',
        visibility: 'VERY_LOW',
        color: 'yellow',
        btcDominance: undefined,
        usdtDominance: undefined,
        altDominance: undefined,
        trendScore: undefined,
        volatilityScore: undefined,
        liquidityScore: undefined,
        riskScore: undefined,
        derivativesScore: undefined,
        compositeScore: undefined,
        previousBtcDominance: undefined,
        previousUsdtDominance: undefined,
        previousAltDominance: undefined,
        guidanceLines: [
          'Awaiting regime signal from backend',
          'Favor conservative setups until visibility increases',
        ],
        mode,
      };
    }

    const composite = (data.composite || 'neutral').toUpperCase();
    const visibility = data.score >= 75 ? 'HIGH' : data.score >= 50 ? 'MEDIUM' : 'LOW';

    const trend = data.dimensions?.trend;
    const color: RegimeColor = data.dimensions?.volatility === 'chaotic' ? 'red'
      : trend === 'up' || trend === 'strong_up' ? 'green'
      : trend === 'down' || trend === 'strong_down' ? 'orange' : 'yellow';
    // Legacy property name retained for consumers; the measure includes all tracked stablecoins.
    return {
      regimeLabel: composite,
      visibility,
      color,
      btcDominance: data.dominance?.btc_d ?? undefined,
      usdtDominance: data.dominance?.stable_d ?? undefined,
      altDominance: data.dominance?.alt_d ?? undefined,
      trendScore: typeof data.trend_score === 'number' ? data.trend_score : undefined,
      volatilityScore:
        typeof data.volatility_score === 'number' ? data.volatility_score : undefined,
      liquidityScore:
        typeof data.liquidity_score === 'number' ? data.liquidity_score : undefined,
      riskScore: typeof data.risk_score === 'number' ? data.risk_score : undefined,
      derivativesScore:
        data.derivatives_available && typeof data.derivatives_score === 'number' ? data.derivatives_score : undefined,
      compositeScore: typeof data.score === 'number' ? data.score : undefined,
      previousBtcDominance: undefined,
      previousUsdtDominance: undefined,
      previousAltDominance: undefined,
      guidanceLines: [
        'Daily BTC context; scores are heuristic, not probabilities',
        data.dominance_source ?? 'Market basket dominance',
      ],
      mode,
    };
  }, [data, mode]);
}
