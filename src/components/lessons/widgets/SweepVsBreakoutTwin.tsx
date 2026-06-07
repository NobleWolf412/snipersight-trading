import { useMemo, useState } from 'react';

export interface SweepVsBreakoutTwinProps {
  direction?: 'bullish' | 'bearish';
  compact?: boolean;
  height?: number;
  className?: string;
}

const VIEW_W = 280;
const PAD_X = 22;
const PAD_Y = 22;

const COLOR_BULL = '#34d399';
const COLOR_BEAR = '#f87171';
const COLOR_SWEEP = '#fbbf24';
const COLOR_BREAKOUT = '#22d3ee';
const COLOR_LEVEL = '#a78bfa';

const POST_BARS = 10;

interface Bar {
  o: number;
  h: number;
  l: number;
  c: number;
}

function buildPriorBars(direction: 'bullish' | 'bearish'): Bar[] {
  const isBull = direction === 'bullish';
  const start = isBull ? 96 : 114;
  const end = isBull ? 104 : 106;
  const step = (end - start) / 4;
  return Array.from({ length: 5 }, (_, i) => {
    const o = start + step * i;
    const c = start + step * (i + 1);
    return { o, c, h: Math.max(o, c) + 0.5, l: Math.min(o, c) - 0.5 };
  });
}

function buildSweepPath(direction: 'bullish' | 'bearish', level: number): Bar[] {
  // Sweep: bar 6 wicks past, closes back inside. Bars 7-15 reverse.
  const isBull = direction === 'bullish';
  const dec = (s: number) => Array.from({ length: POST_BARS }, (_, i) => s - 1.3 * (i + 1));
  const incr = (s: number) => Array.from({ length: POST_BARS }, (_, i) => s + 1.3 * (i + 1));
  const sweepCloses = isBull ? dec(level - 0.5) : incr(level + 0.5);
  return sweepCloses.map((c, i) => {
    const prev = i === 0 ? (isBull ? level - 0.5 : level + 0.5) : sweepCloses[i - 1];
    const o = prev;
    return {
      o,
      c,
      h: Math.max(o, c) + 0.6,
      l: Math.min(o, c) - 0.6,
    };
  });
}

function buildBreakoutPath(direction: 'bullish' | 'bearish', level: number): Bar[] {
  // Breakout: bar 6 closes past, then continues.
  const isBull = direction === 'bullish';
  const incr = (s: number) => Array.from({ length: POST_BARS }, (_, i) => s + 1.2 * (i + 1));
  const dec = (s: number) => Array.from({ length: POST_BARS }, (_, i) => s - 1.2 * (i + 1));
  const breakoutCloses = isBull ? incr(level + 1) : dec(level - 1);
  return breakoutCloses.map((c, i) => {
    const prev = i === 0 ? (isBull ? level + 1 : level - 1) : breakoutCloses[i - 1];
    const o = prev;
    return {
      o,
      c,
      h: Math.max(o, c) + 0.6,
      l: Math.min(o, c) - 0.6,
    };
  });
}

function buildTriggerBar(
  direction: 'bullish' | 'bearish',
  level: number,
  kind: 'sweep' | 'breakout',
): Bar {
  const isBull = direction === 'bullish';
  const opening = isBull ? level - 1 : level + 1;
  if (kind === 'sweep') {
    return isBull
      ? { o: opening, h: level + 3, l: opening - 0.5, c: level - 0.5 }
      : { o: opening, h: opening + 0.5, l: level - 3, c: level + 0.5 };
  }
  return isBull
    ? { o: opening, h: level + 3, l: opening - 0.5, c: level + 1 }
    : { o: opening, h: opening + 0.5, l: level - 3, c: level - 1 };
}

export function SweepVsBreakoutTwin({
  direction = 'bullish',
  compact = false,
  height,
  className,
}: SweepVsBreakoutTwinProps) {
  const [scrub, setScrub] = useState(POST_BARS);

  const isBull = direction === 'bullish';
  const level = 105;

  const prior = useMemo(() => buildPriorBars(direction), [direction]);
  const sweepFollow = useMemo(() => buildSweepPath(direction, level), [direction]);
  const breakoutFollow = useMemo(() => buildBreakoutPath(direction, level), [direction]);

  const viewH = height ?? (compact ? 200 : 280);

  return (
    <div className={className} style={{ width: '100%' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-end',
          marginBottom: 8,
          gap: 8,
        }}
      >
        <div>
          <div
            className="mono"
            style={{
              fontSize: 10,
              color: COLOR_LEVEL,
              letterSpacing: '.22em',
              textTransform: 'uppercase',
            }}
          >
            // SWEEP VS BREAKOUT · {direction.toUpperCase()}
          </div>
          <div
            className="mono"
            style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.14em', marginTop: 3 }}
          >
            identical first 5 bars · scrub to watch divergence
          </div>
        </div>
        <div className="mono" style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.16em' }}>
          bar +{scrub} after trigger
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <TwinChart
          title="SWEEP"
          color={COLOR_SWEEP}
          direction={direction}
          level={level}
          prior={prior}
          triggerBar={buildTriggerBar(direction, level, 'sweep')}
          followBars={sweepFollow.slice(0, scrub)}
          isBull={isBull}
          viewH={viewH}
          caption={isBull ? 'wick above · close back below → reverses' : 'wick below · close back above → reverses'}
        />
        <TwinChart
          title="BREAKOUT"
          color={COLOR_BREAKOUT}
          direction={direction}
          level={level}
          prior={prior}
          triggerBar={buildTriggerBar(direction, level, 'breakout')}
          followBars={breakoutFollow.slice(0, scrub)}
          isBull={isBull}
          viewH={viewH}
          caption={isBull ? 'wick + close above → continues' : 'wick + close below → continues'}
        />
      </div>

      {/* Scrubber */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '100px 1fr 50px',
          gap: 12,
          alignItems: 'center',
          marginTop: 10,
          padding: '8px 12px',
          background: 'rgba(0,0,0,.30)',
          border: '1px solid var(--border-soft)',
          borderRadius: 4,
        }}
      >
        <span
          className="mono"
          style={{ fontSize: 10, color: 'var(--fg-3)', letterSpacing: '.18em' }}
        >
          SCRUB POST
        </span>
        <input
          type="range"
          min={0}
          max={POST_BARS}
          step={1}
          value={scrub}
          onChange={(e) => setScrub(Number(e.target.value))}
          aria-label="post-trigger bar scrub"
          style={{ accentColor: COLOR_LEVEL }}
        />
        <span
          className="mono"
          style={{ fontSize: 12, color: COLOR_LEVEL, fontWeight: 700, textAlign: 'right' }}
        >
          +{scrub}
        </span>
      </div>
    </div>
  );
}

interface TwinChartProps {
  title: string;
  color: string;
  direction: 'bullish' | 'bearish';
  level: number;
  prior: Bar[];
  triggerBar: Bar;
  followBars: Bar[];
  isBull: boolean;
  viewH: number;
  caption: string;
}

function TwinChart({
  title,
  color,
  level,
  prior,
  triggerBar,
  followBars,
  viewH,
  caption,
}: TwinChartProps) {
  const allBars = [...prior, triggerBar, ...followBars];
  const lows = allBars.map((b) => b.l);
  const highs = allBars.map((b) => b.h);
  const minP = Math.min(...lows);
  const maxP = Math.max(...highs);
  const range = maxP - minP || 1;
  const innerW = VIEW_W - 2 * PAD_X;
  const innerH = viewH - 2 * PAD_Y;
  const barW = innerW / (5 + 1 + POST_BARS);

  const priceToY = (p: number) => PAD_Y + ((maxP - p) / range) * innerH;
  const barX = (i: number) => PAD_X + (i + 0.5) * barW;

  return (
    <div>
      <div
        className="mono"
        style={{
          fontSize: 10,
          color,
          letterSpacing: '.22em',
          marginBottom: 4,
          textAlign: 'center',
        }}
      >
        {title}
      </div>
      <svg
        viewBox={`0 0 ${VIEW_W} ${viewH}`}
        style={{
          width: '100%',
          height: viewH,
          background: 'rgba(0,0,0,.40)',
          border: `1px solid ${color}33`,
          borderRadius: 6,
        }}
      >
        {/* Level */}
        <line
          x1={PAD_X}
          x2={VIEW_W - PAD_X}
          y1={priceToY(level)}
          y2={priceToY(level)}
          stroke={COLOR_LEVEL}
          strokeWidth={1}
          strokeDasharray="4 3"
        />

        {/* Bars */}
        {allBars.map((b, i) => {
          const cx = barX(i);
          const yH = priceToY(b.h);
          const yL = priceToY(b.l);
          const yO = priceToY(b.o);
          const yC = priceToY(b.c);
          const isTrigger = i === 5;
          const c = b.c >= b.o ? COLOR_BULL : COLOR_BEAR;
          return (
            <g key={`b-${i}`} opacity={i >= 5 ? 1 : 0.75}>
              <line x1={cx} x2={cx} y1={yH} y2={yL} stroke={isTrigger ? color : c} strokeWidth={0.75} />
              <rect
                x={cx - barW * 0.3}
                y={Math.min(yO, yC)}
                width={barW * 0.6}
                height={Math.max(Math.abs(yO - yC), 1)}
                fill={c}
                stroke={isTrigger ? color : c}
                strokeWidth={isTrigger ? 1.5 : 0.5}
              />
            </g>
          );
        })}
      </svg>
      <div
        className="mono"
        style={{
          fontSize: 9,
          color: 'var(--fg-4)',
          letterSpacing: '.14em',
          marginTop: 4,
          textAlign: 'center',
        }}
      >
        {caption}
      </div>
    </div>
  );
}
