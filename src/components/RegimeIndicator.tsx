/**
 * RegimeIndicator Component
 * 
 * Displays market regime status with visual indicators
 */

import { TrendRegime, VolatilityRegime, RegimeMetadata } from '@/types/regime';
import { TrendingUp, TrendingDown, Minus, Activity, Droplets } from 'lucide-react';

interface RegimeIndicatorProps {
  regime?: RegimeMetadata;
  size?: 'sm' | 'md' | 'lg';
}

export function RegimeIndicator({ regime, size = 'md' }: RegimeIndicatorProps) {
  if (!regime?.global_regime && !regime?.symbol_regime) {
    return null;
  }

  const global = regime.global_regime;
  const symbol = regime.symbol_regime;

  return (
    <div className={`flex items-center gap-2 ${size === 'sm' ? 'text-xs' : size === 'lg' ? 'text-base' : 'text-sm'}`}>
      {global && (
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-background/50 border border-border/50">
          <TrendIcon trend={global.trend} size={size} />
          <span className="font-medium text-muted-foreground">
            {formatTrend(global.trend)}
          </span>
          <VolatilityIcon volatility={global.volatility} size={size} />
          <RegimeScore score={global.score} size={size} />
        </div>
      )}
      
      {symbol && (
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-accent/10 border border-accent/30">
          <TrendIcon trend={symbol.trend} size={size} />
          <span className="text-xs text-accent">Local</span>
          <RegimeScore score={symbol.score} size={size} accent />
        </div>
      )}
    </div>
  );
}

function TrendIcon({ trend, size }: { trend: TrendRegime; size: string }) {
  const iconSize = size === 'sm' ? 12 : size === 'lg' ? 18 : 14;
  
  if (trend === 'strong_up' || trend === 'up') {
    return <TrendingUp size={iconSize} className="text-green-500" />;
  }
  if (trend === 'strong_down' || trend === 'down') {
    return <TrendingDown size={iconSize} className="text-red-500" />;
  }
  return <Minus size={iconSize} className="text-muted-foreground" />;
}

function VolatilityIcon({ volatility, size }: { volatility: VolatilityRegime; size: string }) {
  const iconSize = size === 'sm' ? 12 : size === 'lg' ? 18 : 14;
  
  if (volatility === 'chaotic') {
    return <Activity size={iconSize} className="text-red-400 animate-pulse" />;
  }
  if (volatility === 'elevated') {
    return <Activity size={iconSize} className="text-orange-400" />;
  }
  if (volatility === 'compressed') {
    return <Droplets size={iconSize} className="text-blue-400" />;
  }
  return <Activity size={iconSize} className="text-muted-foreground" />;
}

function RegimeScore({ score, size, accent }: { score: number; size: string; accent?: boolean }) {
  const color = score >= 70 ? 'text-green-500' : score >= 50 ? 'text-yellow-500' : 'text-red-500';
  const accentColor = accent ? 'text-accent' : color;
  
  return (
    <span className={`font-mono font-semibold ${size === 'sm' ? 'text-xs' : 'text-sm'} ${accentColor}`}>
      {score.toFixed(0)}
    </span>
  );
}

function formatTrend(trend: TrendRegime): string {
  const map: Record<TrendRegime, string> = {
    'strong_up': '↑↑',
    'up': '↑',
    'sideways': '→',
    'down': '↓',
    'strong_down': '↓↓'
  };
  return map[trend];
}
