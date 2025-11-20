import { useMemo } from 'react';
import type { MarketRegimeLensProps } from '@/components/market/MarketRegimeLens';

export function useMockMarketRegime(mode: 'scanner' | 'bot' = 'scanner'): MarketRegimeLensProps {
  return useMemo(() => {
    const scannerRegime: MarketRegimeLensProps = {
      regimeLabel: 'DEFENSIVE',
      visibility: 'LOW',
      color: 'orange',
      btcDominance: 53.4,
      usdtDominance: 7.9,
      altDominance: 38.7,
      previousBtcDominance: 51.2,
      previousUsdtDominance: 7.1,
      previousAltDominance: 41.7,
      guidanceLines: [
        'Money rotating into BTC & stables',
        'Favor BTC/ETH setups only',
        'Reduce size on alt trades',
        'Avoid new degen entries',
      ],
      mode,
    };

    const botRegime: MarketRegimeLensProps = {
      regimeLabel: 'DEFENSIVE',
      visibility: 'LOW',
      color: 'orange',
      btcDominance: 53.4,
      usdtDominance: 7.9,
      altDominance: 38.7,
      previousBtcDominance: 51.2,
      previousUsdtDominance: 7.1,
      previousAltDominance: 41.7,
      guidanceLines: [
        'Bot Risk Multiplier: 0.5x (Defensive Mode)',
        'Bot will not open new altcoin positions',
        'BTC/ETH allowed, reduced size',
        'Tighter stop-losses engaged',
      ],
      mode,
    };

    return mode === 'bot' ? botRegime : scannerRegime;
  }, [mode]);
}
