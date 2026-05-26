import { useEffect, useState, useMemo } from 'react';
import { api } from '@/utils/api';

// Public shape of the regime hook's return value.
// Inlined here after the original MarketRegimeLens component was archived in
// Phase 6 sub-step 4.
export type RegimeLabel = 'ALTSEASON' | 'BTC_DRIVE' | 'DEFENSIVE' | 'PANIC' | 'CHOPPY';
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
    api.getMarketRegime().then((res) => {
      if (!mounted) return;
      if (res.data) setData(res.data);
    });
    return () => { mounted = false };
  }, []);

  return useMemo<MarketRegimeLensProps>(() => {
    if (!data) {
      return {
        regimeLabel: 'CHOPPY',
        visibility: 'MEDIUM',
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

    // Map composite label to UI label/color heuristically
    const labelMap: Record<string, { label: string; color: MarketRegimeLensProps['color'] }> = {
      ALTSEASON: { label: 'ALTSEASON', color: 'green' },
      BTC_DRIVE: { label: 'BTC_DRIVE', color: 'blue' },
      DEFENSIVE: { label: 'DEFENSIVE', color: 'orange' },
      PANIC: { label: 'PANIC', color: 'red' },
      CHOPPY: { label: 'CHOPPY', color: 'yellow' },
      NEUTRAL: { label: 'CHOPPY', color: 'yellow' },
    };

    const mapped = labelMap[composite] || labelMap.NEUTRAL;

    // Dominance lives under `dominance` on the regime response, not
    // `dimensions` (which is a labels object). Reading the wrong path
    // silently discards real data and falls through to UI placeholders.
    // See CLAUDE.md §10 standing fix #4 (real dominance data).
    // Backend emits stablecoin dominance as `stable_d` (USDT-anchored);
    // the hook field stays named `usdtDominance` for backward compat —
    // dial labels read "USDT.D" since USDT is ~85% of stable mcap.
    return {
      regimeLabel: mapped.label as MarketRegimeLensProps['regimeLabel'],
      visibility,
      color: mapped.color,
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
        typeof data.derivatives_score === 'number' ? data.derivatives_score : undefined,
      compositeScore: typeof data.score === 'number' ? data.score : undefined,
      previousBtcDominance: undefined,
      previousUsdtDominance: undefined,
      previousAltDominance: undefined,
      guidanceLines: [
        'Derived from backend market regime analysis',
      ],
      mode,
    };
  }, [data, mode]);
}
