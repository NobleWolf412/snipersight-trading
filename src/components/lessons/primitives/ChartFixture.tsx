import { useMemo } from 'react';
import fixtureJson from '@/content/lessons/_fixtures/master-btc.json';
import annotationsJson from '@/content/lessons/_fixtures/master-btc.annotations.json';
import type { FixtureAnnotations, FixtureData, FixtureLens } from './types';

const FIX = fixtureJson as unknown as FixtureData;
const ANN = annotationsJson as unknown as FixtureAnnotations;

const VIEW_W = 800;
const VIEW_H = 380;
const PAD_X = 28;
const PAD_Y = 24;
const INNER_W = VIEW_W - 2 * PAD_X;
const INNER_H = VIEW_H - 2 * PAD_Y;

const LENS_COLOR: Record<FixtureLens, string> = {
  ob:       '#22d3ee',
  fvg:      '#fbbf24',
  bos:      '#a78bfa',
  sweep:    '#f472b6',
  wyckoff:  '#4ade80',
  regime:   '#60a5fa',
  killzone: '#fbbf24',
};

const CANDLE_BULL = '#34d399';
const CANDLE_BEAR = '#f87171';

export interface ChartFixtureProps {
  lens: FixtureLens;
  compact?: boolean;
  showNarrative?: boolean;
  className?: string;
}

export function ChartFixture({
  lens,
  compact = false,
  showNarrative = true,
  className,
}: ChartFixtureProps) {
  const bars = FIX.bars;
  const { minP, maxP, priceY, barX, barW } = useMemo(() => {
    const lows = bars.map((b) => b.l);
    const highs = bars.map((b) => b.h);
    const minP = Math.min(...lows);
    const maxP = Math.max(...highs);
    const range = maxP - minP || 1;
    const N = bars.length;
    return {
      minP,
      maxP,
      priceY: (p: number) => PAD_Y + ((maxP - p) / range) * INNER_H,
      barX: (i: number) => PAD_X + (i / Math.max(N - 1, 1)) * INNER_W,
      barW: (INNER_W / N) * 0.62,
    };
  }, [bars]);

  const accent = LENS_COLOR[lens];
  const chapterNote = getChapterNote(lens);

  return (
    <div className={className} style={{ width: '100%' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-end',
          marginBottom: 8,
          gap: 12,
        }}
      >
        <div>
          <div
            className="mono"
            style={{
              fontSize: 10,
              color: accent,
              letterSpacing: '.22em',
              textTransform: 'uppercase',
            }}
          >
            // {lens} LENS · {FIX.symbol} {FIX.timeframe}
          </div>
          <div
            className="mono"
            style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.16em', marginTop: 3 }}
          >
            {bars.length} bars · ${minP.toFixed(0)}–${maxP.toFixed(0)}
          </div>
        </div>
        <div
          className="mono"
          style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.14em' }}
        >
          {ANN.window.start.slice(0, 16)} → {ANN.window.end.slice(11, 16)} UTC
        </div>
      </div>

      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        style={{
          width: '100%',
          height: compact ? 240 : 360,
          background: 'rgba(0,0,0,.40)',
          border: '1px solid var(--border-soft)',
          borderRadius: 6,
        }}
      >
        {/* Price grid (5 horizontal lines) */}
        {Array.from({ length: 5 }, (_, i) => {
          const y = PAD_Y + (i / 4) * INNER_H;
          const p = maxP - (i / 4) * (maxP - minP);
          return (
            <g key={`grid-${i}`}>
              <line
                x1={PAD_X}
                x2={VIEW_W - PAD_X}
                y1={y}
                y2={y}
                stroke="var(--border-soft)"
                strokeWidth={0.5}
                strokeDasharray="2 4"
              />
              <text
                x={4}
                y={y + 3}
                fontSize={9}
                fontFamily="JetBrains Mono,monospace"
                fill="var(--fg-4)"
              >
                {p.toFixed(0)}
              </text>
            </g>
          );
        })}

        {/* Candles */}
        {bars.map((b, i) => {
          const cx = barX(i);
          const yH = priceY(b.h);
          const yL = priceY(b.l);
          const yO = priceY(b.o);
          const yC = priceY(b.c);
          const isBull = b.c >= b.o;
          const color = isBull ? CANDLE_BULL : CANDLE_BEAR;
          const top = Math.min(yO, yC);
          const bodyH = Math.max(Math.abs(yO - yC), 1);
          return (
            <g key={`bar-${i}`} opacity={0.85}>
              <line x1={cx} x2={cx} y1={yH} y2={yL} stroke={color} strokeWidth={0.75} />
              <rect
                x={cx - barW / 2}
                y={top}
                width={barW}
                height={bodyH}
                fill={color}
                stroke={color}
                strokeWidth={0.5}
              />
            </g>
          );
        })}

        {/* Lens overlay */}
        <LensOverlay lens={lens} barX={barX} priceY={priceY} barW={barW} barCount={bars.length} />
      </svg>

      {showNarrative && chapterNote && (
        <div
          className="mono"
          style={{
            marginTop: 10,
            padding: '10px 14px',
            border: `1px solid ${accent}`,
            borderRadius: 6,
            background: `${accent}10`,
            fontSize: 11,
            color: 'var(--fg-2)',
            lineHeight: 1.55,
          }}
        >
          <strong style={{ color: accent, letterSpacing: '.16em', fontSize: 9 }}>
            // CHAPTER NOTE
          </strong>
          <br />
          {chapterNote}
        </div>
      )}
    </div>
  );
}

interface LensOverlayProps {
  lens: FixtureLens;
  barX: (i: number) => number;
  priceY: (p: number) => number;
  barW: number;
  barCount: number;
}

function LensOverlay({ lens, barX, priceY, barW, barCount }: LensOverlayProps) {
  if (lens === 'ob' && ANN.ob) {
    const { bar_idx, high, low, direction } = ANN.ob;
    const color = LENS_COLOR.ob;
    const xStart = barX(bar_idx) - barW;
    const xEnd = VIEW_W - PAD_X;
    return (
      <g>
        <rect
          x={xStart}
          y={priceY(high)}
          width={xEnd - xStart}
          height={priceY(low) - priceY(high)}
          fill={`${color}22`}
          stroke={color}
          strokeWidth={1}
          strokeDasharray="3 3"
        />
        <text
          x={xStart + 4}
          y={priceY(high) - 4}
          fontSize={10}
          fontFamily="Share Tech Mono,monospace"
          fill={color}
        >
          OB · {direction.toUpperCase()}
        </text>
      </g>
    );
  }

  if (lens === 'fvg' && ANN.fvg) {
    const { bar_idx, top, bottom, direction } = ANN.fvg;
    const color = LENS_COLOR.fvg;
    const xStart = barX(Math.max(bar_idx - 2, 0));
    const xEnd = VIEW_W - PAD_X;
    return (
      <g>
        <rect
          x={xStart}
          y={priceY(top)}
          width={xEnd - xStart}
          height={priceY(bottom) - priceY(top)}
          fill={`${color}22`}
          stroke={color}
          strokeWidth={1}
          strokeDasharray="3 3"
        />
        <text
          x={xStart + 4}
          y={priceY(top) - 4}
          fontSize={10}
          fontFamily="Share Tech Mono,monospace"
          fill={color}
        >
          FVG · {direction.toUpperCase()}
        </text>
      </g>
    );
  }

  if (lens === 'bos' && ANN.bos) {
    const { bar_idx, break_level, direction } = ANN.bos;
    const color = LENS_COLOR.bos;
    const cx = barX(bar_idx);
    const yLevel = priceY(break_level);
    const arrowDir = direction === 'bearish' ? 1 : -1;
    return (
      <g>
        <line
          x1={PAD_X}
          x2={VIEW_W - PAD_X}
          y1={yLevel}
          y2={yLevel}
          stroke={color}
          strokeWidth={1.5}
          strokeDasharray="6 4"
        />
        <text
          x={PAD_X + 4}
          y={yLevel - 4}
          fontSize={10}
          fontFamily="Share Tech Mono,monospace"
          fill={color}
        >
          BROKEN LEVEL · {break_level.toFixed(0)}
        </text>
        <g transform={`translate(${cx}, ${yLevel})`}>
          <circle r={5} fill={color} />
          <line x1={0} x2={0} y1={0} y2={arrowDir * 26} stroke={color} strokeWidth={2} />
          <polygon
            points={`-4,${arrowDir * 20} 4,${arrowDir * 20} 0,${arrowDir * 30}`}
            fill={color}
          />
        </g>
        <text
          x={cx + 10}
          y={yLevel + arrowDir * 32 + (arrowDir < 0 ? -2 : 12)}
          fontSize={10}
          fontFamily="Share Tech Mono,monospace"
          fill={color}
        >
          BOS · {direction.toUpperCase()}
        </text>
      </g>
    );
  }

  if (lens === 'sweep' && ANN.sweep) {
    const { bar_idx, level, sweep_type, confirmation_level } = ANN.sweep;
    const color = LENS_COLOR.sweep;
    const cx = barX(bar_idx);
    const yLevel = priceY(level);
    return (
      <g>
        <line
          x1={PAD_X}
          x2={VIEW_W - PAD_X}
          y1={yLevel}
          y2={yLevel}
          stroke={color}
          strokeWidth={1}
          strokeDasharray="2 3"
          opacity={0.7}
        />
        <text
          x={PAD_X + 4}
          y={yLevel - 4}
          fontSize={10}
          fontFamily="Share Tech Mono,monospace"
          fill={color}
        >
          LIQUIDITY · {level.toFixed(0)}
        </text>
        <circle cx={cx} cy={yLevel} r={8} fill="none" stroke={color} strokeWidth={2}>
          <animate
            attributeName="r"
            from={4}
            to={14}
            dur="1.6s"
            repeatCount="indefinite"
          />
          <animate
            attributeName="opacity"
            from={1}
            to={0}
            dur="1.6s"
            repeatCount="indefinite"
          />
        </circle>
        <circle cx={cx} cy={yLevel} r={4} fill={color} />
        <text
          x={cx + 14}
          y={yLevel + 14}
          fontSize={10}
          fontFamily="Share Tech Mono,monospace"
          fill={color}
        >
          SWEEP {sweep_type.toUpperCase()} · L{confirmation_level ?? '?'}
        </text>
      </g>
    );
  }

  if (lens === 'wyckoff' && ANN.wyckoff_phase) {
    const color = LENS_COLOR.wyckoff;
    return (
      <g>
        <rect
          x={PAD_X}
          y={VIEW_H - PAD_Y - 16}
          width={INNER_W}
          height={16}
          fill={`${color}18`}
          stroke={color}
          strokeWidth={1}
          opacity={0.7}
        />
        <text
          x={PAD_X + 8}
          y={VIEW_H - PAD_Y - 4}
          fontSize={10}
          fontFamily="Share Tech Mono,monospace"
          fill={color}
          letterSpacing="0.14em"
        >
          PHASE · {ANN.wyckoff_phase.label.toUpperCase()}
        </text>
      </g>
    );
  }

  if (lens === 'regime' && ANN.regime_hint) {
    const color = LENS_COLOR.regime;
    // Highlight the volatility-expansion zone (bars 55-61 per annotation note)
    const xStart = barX(55);
    const xEnd = barX(Math.min(61, barCount - 1));
    return (
      <g>
        <rect
          x={xStart}
          y={PAD_Y}
          width={xEnd - xStart}
          height={INNER_H}
          fill={`${color}15`}
          stroke={color}
          strokeWidth={1}
          strokeDasharray="4 4"
        />
        <text
          x={(xStart + xEnd) / 2}
          y={PAD_Y + 14}
          fontSize={10}
          fontFamily="Share Tech Mono,monospace"
          fill={color}
          textAnchor="middle"
        >
          VOLATILITY EXPANSION
        </text>
        <text
          x={PAD_X + 4}
          y={VIEW_H - PAD_Y - 6}
          fontSize={9}
          fontFamily="Share Tech Mono,monospace"
          fill={color}
          letterSpacing="0.16em"
        >
          REGIME · {ANN.regime_hint.label.toUpperCase()}
        </text>
      </g>
    );
  }

  if (lens === 'killzone' && ANN.kill_zone) {
    const color = LENS_COLOR.killzone;
    return (
      <g>
        <text
          x={VIEW_W / 2}
          y={VIEW_H / 2}
          fontSize={11}
          fontFamily="Share Tech Mono,monospace"
          fill={color}
          textAnchor="middle"
          opacity={0.7}
        >
          // KILL ZONE LENS NOT COVERED BY MASTER FIXTURE — see Chapter 9 dedicated widget
        </text>
      </g>
    );
  }

  return null;
}

function getChapterNote(lens: FixtureLens): string | null {
  switch (lens) {
    case 'ob':       return ANN.ob?.chapter_note ?? null;
    case 'fvg':      return ANN.fvg?.chapter_note ?? null;
    case 'bos':      return ANN.bos?.chapter_note ?? null;
    case 'sweep':    return ANN.sweep?.chapter_note ?? null;
    case 'wyckoff':  return ANN.wyckoff_phase?.chapter_note ?? null;
    case 'regime':   return ANN.regime_hint?.chapter_note ?? null;
    case 'killzone': return ANN.kill_zone?.chapter_note ?? null;
  }
}
