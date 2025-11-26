import { useState, useEffect } from 'react';
import { api } from '@/utils/api';
import type { MarketRegimeLensProps, RegimeLabel, Visibility, RegimeColor } from '@/components/market/MarketRegimeLens';

/**
 * Hook to fetch live market regime data from backend.
 * Polls /api/market/regime endpoint and maps to MarketRegimeLens props.
 */
export function useMarketRegime(mode: 'scanner' | 'bot' = 'scanner'): MarketRegimeLensProps {
  const [regimeData, setRegimeData] = useState<MarketRegimeLensProps>({
    regimeLabel: 'CHOPPY',
    visibility: 'MEDIUM',
    color: 'yellow',
    btcDominance: 50,
    usdtDominance: 5,
    altDominance: 45,
    guidanceLines: ['Loading market regime...'],
    mode,
  });

  useEffect(() => {
    const fetchRegime = async () => {
      try {
        const response = await api.getMarketRegime();
        
        if (response.error || !response.data) {
          console.warn('Market regime fetch failed, using fallback:', response.error);
          return;
        }

        const data = response.data;
        
        // Map backend composite regime to frontend RegimeLabel
        const regimeLabel = mapCompositeToLabel(data.composite);
        const visibility = mapScoreToVisibility(data.score);
        const color = mapLabelToColor(regimeLabel);
        
        // Generate guidance based on regime
        const guidanceLines = generateGuidance(regimeLabel, data.dimensions.trend, mode);
        
        // Mock dominance values (backend doesn't provide these yet)
        // TODO: Backend should expose BTC.D, USDT.D, ALT.D when available
        const btcDominance = data.dimensions.risk_appetite === 'risk_off' ? 55 : 48;
        const usdtDominance = data.dimensions.liquidity === 'thin' ? 8 : 5;
        const altDominance = 100 - btcDominance - usdtDominance;
        
        setRegimeData({
          regimeLabel,
          visibility,
          color,
          btcDominance,
          usdtDominance,
          altDominance,
          guidanceLines,
          mode,
        });
        
      } catch (error) {
        console.error('Market regime fetch error:', error);
      }
    };

    fetchRegime();
    const interval = setInterval(fetchRegime, 60000); // Refresh every minute
    
    return () => clearInterval(interval);
  }, [mode]);

  return regimeData;
}

/**
 * Map backend composite regime to frontend RegimeLabel
 */
function mapCompositeToLabel(composite: string): RegimeLabel {
  const lower = composite.toLowerCase();
  
  if (lower.includes('bullish') && lower.includes('risk_on')) return 'ALTSEASON';
  if (lower.includes('bullish') || lower.includes('uptrend')) return 'BTC_DRIVE';
  if (lower.includes('defensive') || lower.includes('risk_off')) return 'DEFENSIVE';
  if (lower.includes('bearish') && lower.includes('high_vol')) return 'PANIC';
  
  return 'CHOPPY';
}

/**
 * Map regime score to visibility level
 */
function mapScoreToVisibility(score: number): Visibility {
  if (score >= 80) return 'HIGH';
  if (score >= 65) return 'MEDIUM';
  if (score >= 45) return 'LOW';
  return 'VERY_LOW';
}

/**
 * Map regime label to color
 */
function mapLabelToColor(label: RegimeLabel): RegimeColor {
  const colorMap: Record<RegimeLabel, RegimeColor> = {
    ALTSEASON: 'green',
    BTC_DRIVE: 'blue',
    DEFENSIVE: 'orange',
    PANIC: 'red',
    CHOPPY: 'yellow',
  };
  return colorMap[label];
}

/**
 * Generate context-specific guidance lines
 */
function generateGuidance(label: RegimeLabel, trend: string, mode: 'scanner' | 'bot'): string[] {
  const scannerGuidance: Record<RegimeLabel, string[]> = {
    ALTSEASON: [
      'Strong altcoin momentum',
      'Favor high-quality alt setups',
      'BTC correlation weakening',
      'Look for breakout patterns',
    ],
    BTC_DRIVE: [
      'BTC leading the market',
      'Focus on BTC/ETH majors',
      'Alts may lag or consolidate',
      'High-cap plays preferred',
    ],
    DEFENSIVE: [
      'Money rotating to safety',
      'Favor BTC/ETH setups only',
      'Reduce size on alt trades',
      'Tighten stop-losses',
    ],
    PANIC: [
      'High volatility environment',
      'Avoid new long entries',
      'Short setups may be viable',
      'Cash is a position',
    ],
    CHOPPY: [
      'No clear directional bias',
      'Range-bound conditions',
      'Wait for structure clarity',
      'Lower conviction signals',
    ],
  };

  const botGuidance: Record<RegimeLabel, string[]> = {
    ALTSEASON: [
      'Bot Risk Multiplier: 1.5x (Aggressive)',
      'Full altcoin exposure allowed',
      'Wider profit targets engaged',
      'Riding trends longer',
    ],
    BTC_DRIVE: [
      'Bot Risk Multiplier: 1.0x (Normal)',
      'BTC/ETH preferred, alts secondary',
      'Standard position sizing',
      'Normal stop-loss distances',
    ],
    DEFENSIVE: [
      'Bot Risk Multiplier: 0.5x (Defensive)',
      'No new altcoin positions',
      'BTC/ETH only, reduced size',
      'Tighter stop-losses engaged',
    ],
    PANIC: [
      'Bot Risk Multiplier: 0.25x (Minimal)',
      'Position opening paused',
      'Closing partial positions',
      'Capital preservation mode',
    ],
    CHOPPY: [
      'Bot Risk Multiplier: 0.75x (Conservative)',
      'Reduced trade frequency',
      'Higher confluence required',
      'Quick profit-taking active',
    ],
  };

  return mode === 'bot' ? botGuidance[label] : scannerGuidance[label];
}
