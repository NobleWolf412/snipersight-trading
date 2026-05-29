import { useMemo } from 'react';

export type RegimeMetric = 'adx' | 'hurst';

export interface RegimePoint {
  trend: number;
  vol: number;
}

export interface RegimeQuadrantProps {
  symbol: string;
  trendStrength: number;
  volatility: number;
  trail?: RegimePoint[];
  comparison?: { symbol: string; trendStrength: number; volatility: number };
  metric?: RegimeMetric;
  volMax?: number;
  compact?: boolean;
  height?: number;
  className?: string;
  label?: string;
}

const VIEW_W = 520;
const PAD_L = 44;
const PAD_R = 16;
const PAD_T = 16;
const PAD_B = 36;

const COLOR_DOT = '#22d3ee';
const COLOR_DOT_GLOW = 'rgba(34,211,238,.45)';
const COLOR_GHOST = '#a78bfa';
const COLOR_GRID = 'var(--border-soft)';
const COLOR_TEXT = 'var(--fg-3)';

const QUADRANT_LABELS: { x0: number; x1: number; y0: number; y1: number; label: string; color: string }[] = [
  { x0: 0,   x1: 0.5, y0: 0,   y1: 0.5, label: 'COMPRESSION', color: '#60a5fa' },
  { x0: 0.5, x1: 1,   y0: 0,   y1: 0.5, label: 'QUIET TREND', color: '#34d399' },
  { x0: 0,   x1: 0.5, y0: 0.5, y1: 1,   label: 'CHOP',         color: '#f87171' },
  { x0: 0.5, x1: 1,   y0: 0.5, y1: 1,   label: 'VOLATILE TREND', color: '#fbbf24' },
];

function metricMax(metric: RegimeMetric): number {
  return metric === 'adx' ? 60 : 1;
}

function metricLabel(metric: RegimeMetric): string {
  return metric === 'adx' ? 'TREND STRENGTH (ADX)' : 'PERSISTENCE (HURST)';
}

export function RegimeQuadrant({
  symbol,
  trendStrength,
  volatility,
  trail = [],
  comparison,
  metric = 'adx',
  volMax = 5,
  compact = false,
  height,
  className,
  label,
}: RegimeQuadrantProps) {
  const viewH = height ?? (compact ? 240 : 360);
  const innerW = VIEW_W - PAD_L - PAD_R;
  const innerH = viewH - PAD_T - PAD_B;

  const xMax = metricMax(metric);
  const clampVol = (v: number) => Math.max(0, Math.min(volMax, v));
  const clampTrend = (t: number) => Math.max(0, Math.min(xMax, t));

  const trendToX = (t: number) => PAD_L + (clampTrend(t) / xMax) * innerW;
  const volToY = (v: number) => PAD_T + (clampVol(v) / volMax) * innerH;

  const dotX = trendToX(trendStrength);
  const dotY = volToY(volatility);

  const trailPath = useMemo(() => {
    if (trail.length < 2) return null;
    return trail
      .map((p, i) => `${i === 0 ? 'M' : 'L'} ${trendToX(p.trend).toFixed(1)} ${volToY(p.vol).toFixed(1)}`)
      .join(' ');
  }, [trail, trendToX, volToY]);

  const activeQuadrant = useMemo(() => {
    const tn = clampTrend(trendStrength) / xMax;
    const vn = clampVol(volatility) / volMax;
    return QUADRANT_LABELS.find(
      (q) => tn >= q.x0 && tn <= q.x1 && vn >= q.y0 && vn <= q.y1,
    );
  }, [trendStrength, volatility, xMax, volMax]);

  return (
    <div className={className} style={{ width: '100%' }}>
      {label && (
        <div
          className="mono"
          style={{
            fontSize: 10,
            color: activeQuadrant?.color ?? COLOR_DOT,
            letterSpacing: '.22em',
            textTransform: 'uppercase',
            marginBottom: 6,
          }}
        >
          {label}
        </div>
      )}

      <svg
        viewBox={`0 0 ${VIEW_W} ${viewH}`}
        style={{
          width: '100%',
          height: viewH,
          background: 'rgba(0,0,0,.40)',
          border: '1px solid var(--border-soft)',
          borderRadius: 6,
        }}
      >
        {/* Quadrant background tints */}
        {QUADRANT_LABELS.map((q) => (
          <rect
            key={q.label}
            x={PAD_L + q.x0 * innerW}
            y={PAD_T + q.y0 * innerH}
            width={(q.x1 - q.x0) * innerW}
            height={(q.y1 - q.y0) * innerH}
            fill={`${q.color}08`}
            stroke={activeQuadrant?.label === q.label ? q.color : 'transparent'}
            strokeWidth={activeQuadrant?.label === q.label ? 1.5 : 0}
            strokeDasharray={activeQuadrant?.label === q.label ? '4 3' : undefined}
          />
        ))}

        {/* Quadrant dividers */}
        <line
          x1={PAD_L + 0.5 * innerW}
          x2={PAD_L + 0.5 * innerW}
          y1={PAD_T}
          y2={viewH - PAD_B}
          stroke={COLOR_GRID}
          strokeWidth={1}
          strokeDasharray="3 4"
        />
        <line
          x1={PAD_L}
          x2={VIEW_W - PAD_R}
          y1={PAD_T + 0.5 * innerH}
          y2={PAD_T + 0.5 * innerH}
          stroke={COLOR_GRID}
          strokeWidth={1}
          strokeDasharray="3 4"
        />

        {/* Quadrant labels */}
        {QUADRANT_LABELS.map((q) => {
          const cx = PAD_L + (q.x0 + q.x1) / 2 * innerW;
          const cy = PAD_T + (q.y0 + q.y1) / 2 * innerH;
          const isActive = activeQuadrant?.label === q.label;
          return (
            <text
              key={`lbl-${q.label}`}
              x={cx}
              y={cy}
              fontSize={11}
              fontFamily="Share Tech Mono,monospace"
              fill={q.color}
              textAnchor="middle"
              opacity={isActive ? 1 : 0.4}
              letterSpacing="0.14em"
            >
              {q.label}
            </text>
          );
        })}

        {/* X axis ticks */}
        {[0, 0.25, 0.5, 0.75, 1].map((r) => (
          <g key={`xt-${r}`}>
            <text
              x={PAD_L + r * innerW}
              y={viewH - PAD_B + 14}
              fontSize={9}
              fontFamily="JetBrains Mono,monospace"
              fill={COLOR_TEXT}
              textAnchor="middle"
            >
              {(r * xMax).toFixed(metric === 'hurst' ? 2 : 0)}
            </text>
          </g>
        ))}
        <text
          x={PAD_L + innerW / 2}
          y={viewH - 6}
          fontSize={9}
          fontFamily="Share Tech Mono,monospace"
          fill={COLOR_TEXT}
          textAnchor="middle"
          letterSpacing="0.16em"
        >
          {metricLabel(metric)} →
        </text>

        {/* Y axis ticks */}
        {[0, 0.25, 0.5, 0.75, 1].map((r) => (
          <g key={`yt-${r}`}>
            <text
              x={PAD_L - 6}
              y={PAD_T + r * innerH + 3}
              fontSize={9}
              fontFamily="JetBrains Mono,monospace"
              fill={COLOR_TEXT}
              textAnchor="end"
            >
              {(r * volMax).toFixed(1)}
            </text>
          </g>
        ))}
        <text
          x={10}
          y={PAD_T - 4}
          fontSize={9}
          fontFamily="Share Tech Mono,monospace"
          fill={COLOR_TEXT}
          letterSpacing="0.16em"
        >
          VOLATILITY (ATR%) ↑
        </text>

        {/* Trail */}
        {trailPath && (
          <path d={trailPath} fill="none" stroke={COLOR_DOT} strokeWidth={1} opacity={0.4} />
        )}

        {/* Comparison ghost dot */}
        {comparison && (
          <g>
            <circle
              cx={trendToX(comparison.trendStrength)}
              cy={volToY(comparison.volatility)}
              r={5}
              fill="none"
              stroke={COLOR_GHOST}
              strokeWidth={1.5}
            />
            <text
              x={trendToX(comparison.trendStrength) + 8}
              y={volToY(comparison.volatility) + 3}
              fontSize={9}
              fontFamily="JetBrains Mono,monospace"
              fill={COLOR_GHOST}
            >
              {comparison.symbol}
            </text>
          </g>
        )}

        {/* Primary symbol dot with glow */}
        <circle cx={dotX} cy={dotY} r={12} fill={COLOR_DOT_GLOW} opacity={0.6}>
          <animate attributeName="r" from={8} to={16} dur="1.8s" repeatCount="indefinite" />
          <animate attributeName="opacity" from={0.6} to={0} dur="1.8s" repeatCount="indefinite" />
        </circle>
        <circle cx={dotX} cy={dotY} r={5} fill={COLOR_DOT} stroke="#ffffff" strokeWidth={1} />
        <text
          x={dotX + 10}
          y={dotY - 6}
          fontSize={11}
          fontFamily="Share Tech Mono,monospace"
          fill={COLOR_DOT}
          fontWeight="bold"
        >
          {symbol}
        </text>
      </svg>

      {/* Readout strip */}
      <div
        className="mono"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: 6,
          fontSize: 10,
          color: 'var(--fg-3)',
          letterSpacing: '.14em',
          textTransform: 'uppercase',
        }}
      >
        <span>
          {symbol} · {metric.toUpperCase()} {trendStrength.toFixed(metric === 'hurst' ? 2 : 0)} · ATR%{' '}
          {volatility.toFixed(2)}
        </span>
        <span style={{ color: activeQuadrant?.color ?? COLOR_DOT }}>
          ◉ {activeQuadrant?.label ?? '—'}
        </span>
      </div>
    </div>
  );
}
