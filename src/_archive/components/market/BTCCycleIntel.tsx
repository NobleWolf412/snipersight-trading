/**
 * BTCCycleIntel - Bitcoin Cycle Intelligence Panel
 * 
 * Shows complete BTC cycle context across all timeframes:
 * - DCL (Daily Cycle Low) - 18-28 days
 * - WCL (Weekly Cycle Low) - 35-50 days  
 * - 4YC (4-Year Macro Cycle) - Halving-based
 * 
 * BTC cycles serve as the market leader - use this for macro context
 * on any altcoin trade.
 * 
 * Usage:
 *   <BTCCycleIntel />
 */

import React, { useEffect, useState, useCallback } from 'react';
import { api, BTCCycleContextData } from '@/utils/api';

interface BTCCycleIntelProps {
  onLoad?: (data: BTCCycleContextData) => void;
  autoRefresh?: boolean;
  refreshInterval?: number; // in ms
  compact?: boolean;
  className?: string;
}

export const BTCCycleIntel: React.FC<BTCCycleIntelProps> = ({
  onLoad,
  autoRefresh = false,
  refreshInterval = 300000, // 5 minutes
  compact = false,
  className = ''
}) => {
  const [data, setData] = useState<BTCCycleContextData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const response = await api.getBTCCycleContext();
      if (response.data?.status === 'success' && response.data.data) {
        setData(response.data.data);
        setLastUpdated(new Date());
        setError(null);
        onLoad?.(response.data.data);
      } else {
        setError('Failed to load BTC cycle data');
      }
    } catch (e) {
      setError('Network error');
    } finally {
      setLoading(false);
    }
  }, [onLoad]);

  useEffect(() => {
    fetchData();

    if (autoRefresh) {
      const interval = setInterval(fetchData, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetchData, autoRefresh, refreshInterval]);

  if (loading) {
    return (
      <div className={`bg-slate-800/50 rounded-lg p-4 ${className}`}>
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-slate-700 rounded w-1/2"></div>
          <div className="grid grid-cols-3 gap-4">
            <div className="h-32 bg-slate-700 rounded"></div>
            <div className="h-32 bg-slate-700 rounded"></div>
            <div className="h-32 bg-slate-700 rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className={`bg-slate-800/50 rounded-lg p-4 ${className}`}>
        <div className="text-red-400">⚠️ {error || 'No data available'}</div>
        <button
          onClick={fetchData}
          className="mt-2 text-sm text-cyan-400 hover:text-cyan-300"
        >
          Retry
        </button>
      </div>
    );
  }

  // Compact mode
  if (compact) {
    return <BTCCycleIntelCompact data={data} className={className} />;
  }

  return (
    <div className={`bg-slate-800/50 rounded-lg overflow-hidden ${className}`}>
      {/* Header */}
      <div className="bg-gradient-to-r from-amber-600/20 to-slate-700/50 px-4 py-3 border-b border-slate-600/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">₿</span>
            <div>
              <h3 className="font-bold text-white">BTC Cycle Intelligence</h3>
              <p className="text-xs text-slate-400">Market leader context for all trades</p>
            </div>
          </div>
          <AlignmentBadge alignment={data.overall.alignment} />
        </div>
      </div>

      {/* Three Cycle Cards */}
      <div className="p-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* DCL Card */}
        <CycleCard
          title="Daily Cycle"
          shortName="DCL"
          day={data.dcl.bars_since_low}
          range={`${data.dcl.expected_length.min}-${data.dcl.expected_length.max}`}
          translation={getShortTranslation(data.dcl.translation)}
          status={data.dcl.status}
          bias={data.dcl.bias}
          isFailed={data.dcl.is_failed}
          isInWindow={data.dcl.is_in_window}
          progress={(data.dcl.bars_since_low / data.dcl.expected_length.max) * 100}
          peakDay={data.dcl.cycle_high.peak_bar || undefined}
          maxDay={data.dcl.expected_length.max}
        />

        {/* WCL Card */}
        <CycleCard
          title="Weekly Cycle"
          shortName="WCL"
          day={data.wcl.bars_since_low}
          range={`${data.wcl.expected_length.min}-${data.wcl.expected_length.max}`}
          translation={getShortTranslation(data.wcl.translation)}
          status={data.wcl.status}
          bias={data.wcl.bias}
          isFailed={data.wcl.is_failed}
          isInWindow={data.wcl.is_in_window}
          progress={(data.wcl.bars_since_low / data.wcl.expected_length.max) * 100}
          peakDay={data.wcl.cycle_high.peak_bar || undefined}
          maxDay={data.wcl.expected_length.max}
        />

        {/* 4YC Card */}
        <CycleCard
          title="4-Year Macro"
          shortName="4YC"
          day={data.four_year_cycle.days_since_low}
          range="1460"
          translation={data.four_year_cycle.translation}
          status={data.four_year_cycle.phase.toLowerCase()}
          bias={data.four_year_cycle.macro_bias === 'BULLISH' ? 'LONG' : data.four_year_cycle.macro_bias === 'BEARISH' ? 'SHORT' : 'NEUTRAL'}
          isFailed={false}
          isInWindow={data.four_year_cycle.is_opportunity_zone}
          progress={data.four_year_cycle.cycle_position_pct}
          phase={data.four_year_cycle.phase}
          phaseProgress={data.four_year_cycle.phase_progress_pct}
          isDangerZone={data.four_year_cycle.is_danger_zone}
          confidence={data.four_year_cycle.confidence}
        />
      </div>

      {/* Halving Info */}
      <div className="px-4 pb-4">
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-amber-400">⛏</span>
              <span className="text-amber-300 text-sm font-medium">Halving Status</span>
            </div>
            <div className="text-xs text-slate-400">
              Last: {new Date(data.halving.last_halving_date).toLocaleDateString()}
            </div>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-slate-400">Days since halving:</span>
              <span className="text-white ml-2 font-mono">{data.halving.days_since_halving}</span>
            </div>
            <div>
              <span className="text-slate-400">Next halving:</span>
              <span className="text-amber-400 ml-2 font-mono">~{data.halving.days_until_halving} days</span>
            </div>
          </div>
        </div>
      </div>

      {/* Warnings */}
      {data.overall.warnings && data.overall.warnings.length > 0 && (
        <div className="px-4 pb-4">
          <div className="space-y-1">
            {data.overall.warnings.map((warning, idx) => (
              <div key={idx} className="text-xs text-amber-400/80 flex items-start gap-2">
                <span className="mt-0.5">⚠️</span>
                <span>{warning}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="px-4 py-2 bg-slate-700/30 border-t border-slate-600/50 flex items-center justify-between text-xs text-slate-400">
        <span>
          Based on Camel Finance methodology
        </span>
        {lastUpdated && (
          <span>
            Updated: {lastUpdated.toLocaleTimeString()}
          </span>
        )}
      </div>
    </div>
  );
};

/**
 * Compact version for headers/sidebars
 */
const BTCCycleIntelCompact: React.FC<{ data: BTCCycleContextData; className?: string }> = ({
  data,
  className = ''
}) => {
  return (
    <div className={`bg-slate-800/50 rounded-lg p-3 ${className}`}>
      <div className="flex items-center gap-4">
        <span className="text-xl">₿</span>

        {/* DCL */}
        <div className="flex items-center gap-1">
          <span className="text-xs text-slate-400">DCL:</span>
          <TranslationIcon translation={getShortTranslation(data.dcl.translation)} isFailed={data.dcl.is_failed} />
        </div>

        {/* WCL */}
        <div className="flex items-center gap-1">
          <span className="text-xs text-slate-400">WCL:</span>
          <TranslationIcon translation={getShortTranslation(data.wcl.translation)} isFailed={data.wcl.is_failed} />
        </div>

        {/* 4YC */}
        <div className="flex items-center gap-1">
          <span className="text-xs text-slate-400">4YC:</span>
          <span className={`text-xs font-bold ${data.four_year_cycle.macro_bias === 'BULLISH' ? 'text-emerald-400' :
              data.four_year_cycle.macro_bias === 'BEARISH' ? 'text-red-400' :
                'text-amber-400'
            }`}>
            {data.four_year_cycle.phase}
          </span>
        </div>

        {/* Overall */}
        <div className="ml-auto">
          <AlignmentBadge alignment={data.overall.alignment} size="sm" />
        </div>
      </div>
    </div>
  );
};

/**
 * Translation icon component
 */
const TranslationIcon: React.FC<{ translation: string; isFailed?: boolean }> = ({
  translation,
  isFailed = false
}) => {
  if (isFailed) {
    return <span className="text-red-400 animate-pulse">🚨</span>;
  }

  if (translation === 'RTR') {
    return <span className="text-emerald-400">🟢</span>;
  }

  if (translation === 'LTR') {
    return <span className="text-red-400">🔴</span>;
  }

  return <span className="text-amber-400">🟡</span>;
};

/**
 * Alignment badge component
 */
const AlignmentBadge: React.FC<{
  alignment: string;
  size?: 'sm' | 'md'
}> = ({ alignment, size = 'md' }) => {
  const configs: Record<string, { color: string; label: string; icon: string }> = {
    'ALL_BULLISH': { color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50', label: 'All Bullish', icon: '🟢' },
    'MOSTLY_BULLISH': { color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50', label: 'Mostly Bullish', icon: '◐' },
    'ALL_BEARISH': { color: 'bg-red-500/20 text-red-400 border-red-500/50', label: 'All Bearish', icon: '🔴' },
    'MOSTLY_BEARISH': { color: 'bg-red-500/20 text-red-400 border-red-500/50', label: 'Mostly Bearish', icon: '◐' },
    'MIXED': { color: 'bg-amber-500/20 text-amber-400 border-amber-500/50', label: 'Mixed', icon: '⚠' }
  };

  const config = configs[alignment] || configs['MIXED'];

  if (size === 'sm') {
    return (
      <span className={`px-1.5 py-0.5 rounded text-xs font-medium border ${config.color}`}>
        {config.icon}
      </span>
    );
  }

  return (
    <span className={`px-2 py-1 rounded-md text-xs font-medium border ${config.color}`}>
      {config.icon} {config.label}
    </span>
  );
};

/**
 * Individual cycle card
 */
interface CycleCardProps {
  title: string;
  shortName: string;
  day: number;
  range: string;
  translation: string;
  status: string;
  bias: 'LONG' | 'SHORT' | 'NEUTRAL';
  isFailed: boolean;
  isInWindow: boolean;
  progress: number;
  peakDay?: number;
  maxDay?: number;
  phase?: string;
  phaseProgress?: number;
  isDangerZone?: boolean;
  confidence?: number;
}

const CycleCard: React.FC<CycleCardProps> = ({
  title,
  shortName,
  day,
  range,
  translation,
  status,
  bias,
  isFailed,
  isInWindow,
  progress,
  peakDay,
  maxDay,
  phase,
  phaseProgress,
  isDangerZone,
  confidence
}) => {
  const translationColors: Record<string, string> = {
    'RTR': 'text-emerald-400',
    'MTR': 'text-amber-400',
    'LTR': 'text-red-400'
  };

  const biasColors: Record<string, string> = {
    'LONG': 'bg-emerald-500/20 text-emerald-400',
    'SHORT': 'bg-red-500/20 text-red-400',
    'NEUTRAL': 'bg-slate-500/20 text-slate-400'
  };

  const progressColor =
    isFailed ? 'bg-red-500' :
      translation === 'RTR' ? 'bg-emerald-500' :
        translation === 'LTR' ? 'bg-red-500' :
          'bg-amber-500';

  return (
    <div className={`
      bg-slate-700/30 rounded-lg p-4 border
      ${isFailed
        ? 'border-red-500/50'
        : isDangerZone
          ? 'border-orange-500/50'
          : isInWindow
            ? 'border-cyan-500/50'
            : 'border-slate-600/50'
      }
    `}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-xs text-slate-400">{title}</div>
          <div className="font-bold text-white text-lg">{shortName}</div>
        </div>
        <div className={`px-2 py-1 rounded text-xs font-bold ${biasColors[bias]}`}>
          {bias}
        </div>
      </div>

      {/* Progress */}
      <div className="mb-3">
        <div className="flex justify-between text-xs text-slate-400 mb-1">
          <span>Day {day}</span>
          <span>/ {range}</span>
        </div>
        <div className="relative h-2 bg-slate-600/50 rounded-full overflow-hidden">
          {/* Midpoint marker for DCL/WCL */}
          {maxDay && (
            <div
              className="absolute top-0 bottom-0 w-px bg-white/30"
              style={{ left: '50%' }}
            />
          )}

          {/* Progress fill */}
          <div
            className={`absolute top-0 bottom-0 left-0 rounded-full transition-all duration-300 ${progressColor}`}
            style={{ width: `${Math.min(progress, 100)}%` }}
          />

          {/* Peak marker */}
          {peakDay && maxDay && (
            <div
              className="absolute top-0 bottom-0 w-1 bg-white"
              style={{ left: `${(peakDay / maxDay) * 100}%` }}
            />
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-slate-400">Translation</span>
          <span className={`font-bold ${translationColors[translation] || 'text-slate-400'}`}>
            {translation}
          </span>
        </div>

        {phase && (
          <div className="flex justify-between">
            <span className="text-slate-400">Phase</span>
            <span className="text-white">{phase} {phaseProgress ? `(${phaseProgress.toFixed(0)}%)` : ''}</span>
          </div>
        )}

        {confidence !== undefined && (
          <div className="flex justify-between">
            <span className="text-slate-400">Confidence</span>
            <span className="text-white">{confidence.toFixed(0)}%</span>
          </div>
        )}
      </div>

      {/* Status Badges */}
      <div className="mt-3 flex flex-wrap gap-1">
        {isFailed && (
          <span className="px-2 py-0.5 bg-red-500/20 text-red-400 rounded text-xs animate-pulse">
            🚨 FAILED
          </span>
        )}
        {isInWindow && !isFailed && (
          <span className="px-2 py-0.5 bg-cyan-500/20 text-cyan-400 rounded text-xs">
            ◉ IN WINDOW
          </span>
        )}
        {isDangerZone && (
          <span className="px-2 py-0.5 bg-orange-500/20 text-orange-400 rounded text-xs">
            ⚠️ DANGER ZONE
          </span>
        )}
      </div>
    </div>
  );
};

/**
 * Helper to normalize translation strings
 */
function getShortTranslation(translation: string): string {
  if (translation === 'right_translated' || translation === 'RTR') return 'RTR';
  if (translation === 'mid_translated' || translation === 'MTR') return 'MTR';
  if (translation === 'left_translated' || translation === 'LTR') return 'LTR';
  return 'MTR';
}

export default BTCCycleIntel;
