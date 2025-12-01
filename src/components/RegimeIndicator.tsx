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
  compact?: boolean; // If true, show only the regime label as a badge (for table cells)
}

export function RegimeIndicator({ regime, size = 'md', compact = false }: RegimeIndicatorProps) {
  if (!regime?.global_regime && !regime?.symbol_regime) {
    return null;
  }

  const global = regime.global_regime;
  const symbol = regime.symbol_regime;
  
  // UI-friendly regime labels per sniper_ui_theme.md: Trend/Range/Risk-On/Risk-Off
  const labelMap: Record<string, { label: string }> = {
    // Backend sends lowercase with underscores (e.g., 'sideways_elevated')
    altseason: { label: 'Risk On' },
    ALTSEASON: { label: 'Risk On' },
    btc_drive: { label: 'Trend' },
    BTC_DRIVE: { label: 'Trend' },
    defensive: { label: 'Risk Off' },
    DEFENSIVE: { label: 'Risk Off' },
    panic: { label: 'Risk Off' },
    PANIC: { label: 'Risk Off' },
    choppy: { label: 'Range' },
    CHOPPY: { label: 'Range' },
    neutral: { label: 'Range' },
    NEUTRAL: { label: 'Range' },
    sideways_elevated: { label: 'Range' },
    sideways_compressed: { label: 'Range' },
    trending_stable: { label: 'Trend' },
    trending_volatile: { label: 'Trend' },
  };
  const guidanceMap: Record<string, string> = {
    altseason: 'Risk-on; favor alt momentum entries',
    ALTSEASON: 'Risk-on; favor alt momentum entries',
    btc_drive: 'Favor BTC-led trends; be selective on alts',
    BTC_DRIVE: 'Favor BTC-led trends; be selective on alts',
    defensive: 'Size down; prefer high-quality setups',
    DEFENSIVE: 'Size down; prefer high-quality setups',
    panic: 'Avoid fresh entries; wait for stabilization',
    PANIC: 'Avoid fresh entries; wait for stabilization',
    choppy: 'Range-bound; avoid breakouts, trade extremes',
    CHOPPY: 'Range-bound; avoid breakouts, trade extremes',
    neutral: 'Range-bound; avoid breakouts, trade extremes',
    NEUTRAL: 'Range-bound; avoid breakouts, trade extremes',
    sideways_elevated: 'Range-bound with elevated volatility; caution on breakouts',
    sideways_compressed: 'Range-bound with low volatility; breakout watch',
    trending_stable: 'Healthy trend; favor pullback entries',
    trending_volatile: 'Strong trend but choppy; wider stops advised',
  };
  const globalComposite = (global?.composite || 'neutral');
  const friendlyGlobalLabel = labelMap[globalComposite]?.label || globalComposite.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  const guidance = guidanceMap[globalComposite] || '';

  // Compact mode: just show the regime label as a simple badge
  if (compact && global) {
    const colorClass = 
      friendlyGlobalLabel === 'Risk On' ? 'bg-success/20 text-success border-success/50' :
      friendlyGlobalLabel === 'Risk Off' ? 'bg-destructive/20 text-destructive border-destructive/50' :
      friendlyGlobalLabel === 'Trend' ? 'bg-primary/20 text-primary border-primary/50' :
      'bg-warning/20 text-warning border-warning/50'; // Range
    
    return (
      <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-semibold border ${colorClass}`}>
        {friendlyGlobalLabel}
      </span>
    );
  }

  return (
    <div className={`flex items-center gap-2 ${size === 'sm' ? 'text-xs' : size === 'lg' ? 'text-base' : 'text-sm'}`}>
      {global && (
        <div className="flex items-center gap-2 px-2 py-1 rounded bg-background/50 border border-border/50" title="Global market regime: affects scoring and risk controls">
          <span className="font-semibold text-foreground">{friendlyGlobalLabel}</span>
          <TrendIcon trend={global.trend} size={size} />
          <span className="font-medium text-muted-foreground">{formatTrend(global.trend)}</span>
          <VolatilityIcon volatility={global.volatility} size={size} />
          <RegimeScore score={global.score} size={size} />
          {guidance && (
            <span className="ml-2 text-muted-foreground/80">
              {guidance}
            </span>
          )}
        </div>
      )}
      
      {symbol && (
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-accent/10 border border-accent/30" title="Symbol-specific regime: local trend and volatility context">
          <TrendIcon trend={symbol.trend} size={size} />
          <span className="text-xs text-accent">Symbol</span>
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
