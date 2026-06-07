import { useMemo, useState } from 'react';

export interface WickVsCloseDemoProps {
  direction?: 'bullish' | 'bearish';
  compact?: boolean;
  height?: number;
  className?: string;
}

const VIEW_W = 540;
const PAD_X = 36;
const PAD_Y = 24;

const COLOR_SWEEP = '#fbbf24';
const COLOR_BOS = '#22d3ee';
const COLOR_LEVEL = '#a78bfa';
const COLOR_BULL = '#34d399';
const COLOR_BEAR = '#f87171';

type Lens = 'sweep' | 'bos' | 'both';

export function WickVsCloseDemo({
  direction = 'bullish',
  compact = false,
  height,
  className,
}: WickVsCloseDemoProps) {
  const [lens, setLens] = useState<Lens>('both');
  const [wickHeight, setWickHeight] = useState(8);

  const viewH = height ?? (compact ? 240 : 320);
  const innerH = viewH - 2 * PAD_Y;
  const innerW = VIEW_W - 2 * PAD_X;

  const priceMin = 90;
  const priceMax = 120;
  const range = priceMax - priceMin;
  const swingLevel = 105;
  const priceToY = (p: number) => PAD_Y + ((priceMax - p) / range) * innerH;

  // Build the prior context — 5 bars trending up toward the swing high
  // (for bullish setup). Then 2 test bars: the sweep candle (wick + close back)
  // and the BOS candle (close beyond).
  const isBull = direction === 'bullish';

  const priorBars = useMemo(() => {
    const start = isBull ? 96 : 114;
    const end = isBull ? 104 : 106;
    const slope = (end - start) / 4;
    return Array.from({ length: 5 }, (_, i) => {
      const o = start + slope * i;
      const c = start + slope * (i + 1);
      return {
        o,
        c,
        h: Math.max(o, c) + 0.6,
        l: Math.min(o, c) - 0.6,
      };
    });
  }, [isBull]);

  // The two test bars share the same wick magnitude (driven by slider) but
  // differ in close placement.
  const wickPoke = wickHeight;
  const sweepBar = isBull
    ? { o: 104, h: swingLevel + wickPoke, l: 103, c: 104.5 }
    : { o: 106, h: 107, l: swingLevel - wickPoke, c: 105.5 };
  const bosBar = isBull
    ? { o: 104, h: swingLevel + wickPoke, l: 103, c: swingLevel + wickPoke * 0.6 }
    : { o: 106, h: 107, l: swingLevel - wickPoke, c: swingLevel - wickPoke * 0.6 };

  const barW = innerW / 8;
  const barCx = (i: number) => PAD_X + (i + 0.5) * barW;

  const showSweep = lens === 'sweep' || lens === 'both';
  const showBos = lens === 'bos' || lens === 'both';

  return (
    <div className={className} style={{ width: '100%' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-end',
          marginBottom: 8,
          gap: 10,
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
            // WICK VS CLOSE · {direction.toUpperCase()} SWING
          </div>
          <div
            className="mono"
            style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.14em', marginTop: 3 }}
          >
            same wick magnitude — only body close decides sweep vs BOS
          </div>
        </div>
        <div role="tablist" aria-label="lens" style={{ display: 'flex', gap: 4 }}>
          {(['both', 'sweep', 'bos'] as Lens[]).map((opt) => (
            <button
              key={opt}
              type="button"
              role="tab"
              aria-selected={lens === opt}
              onClick={() => setLens(opt)}
              className="btn"
              style={{
                fontSize: 10,
                padding: '6px 10px',
                letterSpacing: '.16em',
                color: lens === opt ? (opt === 'sweep' ? COLOR_SWEEP : opt === 'bos' ? COLOR_BOS : 'var(--fg)') : 'var(--fg-3)',
                borderColor: lens === opt ? (opt === 'sweep' ? COLOR_SWEEP : opt === 'bos' ? COLOR_BOS : 'var(--accent)') : 'var(--border-soft)',
              }}
            >
              {opt.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

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
        {/* Swing high level */}
        <line
          x1={PAD_X}
          x2={VIEW_W - PAD_X}
          y1={priceToY(swingLevel)}
          y2={priceToY(swingLevel)}
          stroke={COLOR_LEVEL}
          strokeWidth={1.5}
          strokeDasharray="6 4"
        />
        <text
          x={PAD_X + 4}
          y={priceToY(swingLevel) - 4}
          fontSize={10}
          fontFamily="Share Tech Mono,monospace"
          fill={COLOR_LEVEL}
        >
          {isBull ? 'PRIOR SWING HIGH' : 'PRIOR SWING LOW'} · {swingLevel.toFixed(0)}
        </text>

        {/* Prior context bars */}
        {priorBars.map((b, i) => {
          const cx = barCx(i);
          const yH = priceToY(b.h);
          const yL = priceToY(b.l);
          const yO = priceToY(b.o);
          const yC = priceToY(b.c);
          const c = b.c >= b.o ? COLOR_BULL : COLOR_BEAR;
          return (
            <g key={`p-${i}`} opacity={0.75}>
              <line x1={cx} x2={cx} y1={yH} y2={yL} stroke={c} strokeWidth={0.75} />
              <rect
                x={cx - barW * 0.28}
                y={Math.min(yO, yC)}
                width={barW * 0.56}
                height={Math.max(Math.abs(yO - yC), 1)}
                fill={c}
              />
            </g>
          );
        })}

        {/* SWEEP test bar */}
        {showSweep && (() => {
          const cx = barCx(5);
          const c = sweepBar.c < sweepBar.o ? COLOR_BEAR : COLOR_BULL;
          return (
            <g>
              <line x1={cx} x2={cx} y1={priceToY(sweepBar.h)} y2={priceToY(sweepBar.l)} stroke={COLOR_SWEEP} strokeWidth={1.5} />
              <rect
                x={cx - barW * 0.32}
                y={Math.min(priceToY(sweepBar.o), priceToY(sweepBar.c))}
                width={barW * 0.64}
                height={Math.max(Math.abs(priceToY(sweepBar.o) - priceToY(sweepBar.c)), 2)}
                fill={c}
                stroke={COLOR_SWEEP}
                strokeWidth={1.5}
              />
              <text
                x={cx}
                y={priceToY(sweepBar.h) - 6}
                fontSize={10}
                fontFamily="Share Tech Mono,monospace"
                fill={COLOR_SWEEP}
                textAnchor="middle"
              >
                SWEEP
              </text>
              <text
                x={cx}
                y={viewH - PAD_Y + 14}
                fontSize={9}
                fontFamily="JetBrains Mono,monospace"
                fill={COLOR_SWEEP}
                textAnchor="middle"
              >
                wick yes · close no
              </text>
            </g>
          );
        })()}

        {/* BOS test bar */}
        {showBos && (() => {
          const cx = barCx(6);
          const c = bosBar.c >= bosBar.o ? COLOR_BULL : COLOR_BEAR;
          return (
            <g>
              <line x1={cx} x2={cx} y1={priceToY(bosBar.h)} y2={priceToY(bosBar.l)} stroke={COLOR_BOS} strokeWidth={1.5} />
              <rect
                x={cx - barW * 0.32}
                y={Math.min(priceToY(bosBar.o), priceToY(bosBar.c))}
                width={barW * 0.64}
                height={Math.max(Math.abs(priceToY(bosBar.o) - priceToY(bosBar.c)), 2)}
                fill={c}
                stroke={COLOR_BOS}
                strokeWidth={1.5}
              />
              <text
                x={cx}
                y={priceToY(bosBar.h) - 6}
                fontSize={10}
                fontFamily="Share Tech Mono,monospace"
                fill={COLOR_BOS}
                textAnchor="middle"
              >
                BOS
              </text>
              <text
                x={cx}
                y={viewH - PAD_Y + 14}
                fontSize={9}
                fontFamily="JetBrains Mono,monospace"
                fill={COLOR_BOS}
                textAnchor="middle"
              >
                wick yes · close yes
              </text>
            </g>
          );
        })()}
      </svg>

      {/* Wick slider */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '130px 1fr 60px',
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
          WICK MAGNITUDE
        </span>
        <input
          type="range"
          min={1}
          max={14}
          step={0.5}
          value={wickHeight}
          onChange={(e) => setWickHeight(Number(e.target.value))}
          aria-label="wick magnitude"
          style={{ accentColor: COLOR_LEVEL }}
        />
        <span
          className="mono"
          style={{ fontSize: 12, color: COLOR_LEVEL, fontWeight: 700, textAlign: 'right' }}
        >
          {wickHeight.toFixed(1)} pts
        </span>
      </div>

      <div
        className="mono"
        style={{
          marginTop: 8,
          padding: '8px 12px',
          background: 'rgba(167,139,250,.08)',
          border: `1px solid ${COLOR_LEVEL}33`,
          borderRadius: 4,
          fontSize: 11,
          color: 'var(--fg-2)',
          lineHeight: 1.5,
        }}
      >
        Drag the slider — both candles always wick {isBull ? 'above' : 'below'} the level. The only thing
        that flips a sweep into a BOS is whether the body closes <strong>through</strong> the level. Same
        wick, opposite implication.
      </div>
    </div>
  );
}
