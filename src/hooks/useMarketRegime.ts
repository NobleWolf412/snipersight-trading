import { useEffect, useState, useMemo } from 'react';
import { api } from '@/utils/api';
import type { MarketRegimeLensProps } from '@/components/market/MarketRegimeLens';

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

    return {
      regimeLabel: mapped.label as MarketRegimeLensProps['regimeLabel'],
      visibility,
      color: mapped.color,
      btcDominance: data.dimensions?.dominance_btc ?? undefined,
      usdtDominance: data.dimensions?.dominance_usdt ?? undefined,
      altDominance: data.dimensions?.dominance_alt ?? undefined,
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
