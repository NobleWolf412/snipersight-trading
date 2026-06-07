import { useCallback, useEffect, useState } from 'react';

export interface FvgBuilderProps {
  direction?: 'bullish' | 'bearish';
  autoPlay?: boolean;
  loopDelayMs?: number;
  compact?: boolean;
  height?: number;
  className?: string;
}

const VIEW_W = 520;
const PAD_X = 36;
const PAD_Y = 22;

const COLOR_BULL = '#34d399';
const COLOR_BEAR = '#f87171';
const COLOR_FVG = '#fbbf24';
const COLOR_FILL = '#22d3ee';

type Step = 0 | 1 | 2 | 3 | 4 | 5;

const STEP_DESCRIPTIONS: Record<Step, { caption: string; sub: string }> = {
  0: { caption: 'EMPTY CHART', sub: 'press ▶ to build a fair value gap' },
  1: { caption: 'CANDLE 0', sub: 'baseline candle prints' },
  2: {
    caption: 'CANDLE 1 — DISPLACEMENT',
    sub: 'large body, range entirely above candle 0',
  },
  3: { caption: 'CANDLE 2', sub: 'opens above candle 0 high — gap left open' },
  4: { caption: 'FVG IDENTIFIED', sub: 'shaded region = unfilled imbalance' },
  5: { caption: 'PRICE RETURNS', sub: 'retrace into the gap (mitigation)' },
};

export function FvgBuilder({
  direction = 'bullish',
  autoPlay = false,
  loopDelayMs = 1100,
  compact = false,
  height,
  className,
}: FvgBuilderProps) {
  const [step, setStep] = useState<Step>(0);
  const [playing, setPlaying] = useState(autoPlay);

  useEffect(() => {
    if (!playing) return;
    const timer = setTimeout(() => {
      setStep((prev) => (prev >= 5 ? 0 : ((prev + 1) as Step)));
    }, loopDelayMs);
    return () => clearTimeout(timer);
  }, [playing, step, loopDelayMs]);

  const reset = useCallback(() => {
    setPlaying(false);
    setStep(0);
  }, []);

  const togglePlay = useCallback(() => setPlaying((p) => !p), []);
  const stepForward = useCallback(
    () => setStep((p) => (p >= 5 ? 5 : ((p + 1) as Step))),
    [],
  );

  const viewH = height ?? (compact ? 240 : 340);
  const innerW = VIEW_W - 2 * PAD_X;
  const innerH = viewH - 2 * PAD_Y;

  // Bar coordinates for the 3-candle sequence (bullish baseline)
  // Bullish FVG: candle 1's high = 100, candle 2 (displacement) body spans
  // 102-106, candle 3 low = 104. Gap from 100 to 104.
  const priceMin = 90;
  const priceMax = 120;
  const range = priceMax - priceMin;

  const priceToY = (p: number) =>
    PAD_Y + ((priceMax - (direction === 'bullish' ? p : 210 - p)) / range) * innerH;

  const barW = innerW / 7;
  const barCx = (idx: number) => PAD_X + (idx + 0.5) * barW;

  const isBull = direction === 'bullish';
  const bodyColor = isBull ? COLOR_BULL : COLOR_BEAR;

  // 3-bar definition: c0 = baseline; c1 = displacement; c2 = opens above c0 high
  const c0 = { o: 96, h: 100, l: 92, c: 99 };
  const c1 = { o: 99, h: 107, l: 99, c: 106 };
  const c2 = { o: 105, h: 109, l: 104, c: 108 };
  const fvgTop = c2.l;
  const fvgBottom = c0.h;

  const retraceBars = [
    { o: 108, h: 109, l: 105, c: 105 },
    { o: 105, h: 105, l: 102, c: 103 },
  ];

  const showCandle = (idx: number) => step >= ((idx + 1) as Step);
  const showFvg = step >= 4;
  const showRetrace = step === 5;

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
              color: COLOR_FVG,
              letterSpacing: '.22em',
              textTransform: 'uppercase',
            }}
          >
            // FVG BUILDER · {direction.toUpperCase()}
          </div>
          <div
            className="mono"
            style={{
              fontSize: 9,
              color: 'var(--fg-4)',
              letterSpacing: '.14em',
              marginTop: 3,
            }}
          >
            step {step}/5 · {STEP_DESCRIPTIONS[step].caption}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            type="button"
            onClick={togglePlay}
            className="btn"
            style={{ fontSize: 11, padding: '6px 14px', letterSpacing: '.16em' }}
          >
            {playing ? '■ PAUSE' : '▶ PLAY'}
          </button>
          <button
            type="button"
            onClick={stepForward}
            className="btn"
            disabled={step >= 5}
            style={{ fontSize: 11, padding: '6px 12px', letterSpacing: '.16em', opacity: step >= 5 ? 0.4 : 1 }}
          >
            STEP →
          </button>
          <button
            type="button"
            onClick={reset}
            className="btn"
            style={{ fontSize: 11, padding: '6px 12px', letterSpacing: '.16em' }}
          >
            ↺
          </button>
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
        {/* Price gridlines */}
        {[priceMin, (priceMin + priceMax) / 2, priceMax].map((p, i) => (
          <g key={`grid-${i}`}>
            <line
              x1={PAD_X}
              x2={VIEW_W - PAD_X}
              y1={priceToY(p)}
              y2={priceToY(p)}
              stroke="var(--border-soft)"
              strokeWidth={0.5}
              strokeDasharray="2 4"
            />
          </g>
        ))}

        {/* Candle 0 marker line (high) */}
        {showCandle(0) && (
          <line
            x1={PAD_X}
            x2={VIEW_W - PAD_X}
            y1={priceToY(c0.h)}
            y2={priceToY(c0.h)}
            stroke="var(--fg-4)"
            strokeWidth={0.75}
            strokeDasharray="3 3"
            opacity={0.5}
          />
        )}

        {/* Candle 2 marker line (low) */}
        {showCandle(2) && (
          <line
            x1={PAD_X}
            x2={VIEW_W - PAD_X}
            y1={priceToY(c2.l)}
            y2={priceToY(c2.l)}
            stroke="var(--fg-4)"
            strokeWidth={0.75}
            strokeDasharray="3 3"
            opacity={0.5}
          />
        )}

        {/* FVG shaded zone */}
        {showFvg && (
          <g style={{ transition: 'opacity 400ms', opacity: showFvg ? 1 : 0 }}>
            <rect
              x={PAD_X}
              y={priceToY(fvgTop)}
              width={VIEW_W - 2 * PAD_X}
              height={priceToY(fvgBottom) - priceToY(fvgTop)}
              fill={`${COLOR_FVG}22`}
              stroke={COLOR_FVG}
              strokeWidth={1}
              strokeDasharray="3 3"
            >
              <animate
                attributeName="opacity"
                values="0;1"
                dur="500ms"
                repeatCount="1"
                fill="freeze"
              />
            </rect>
            <text
              x={PAD_X + 6}
              y={priceToY(fvgTop) - 4}
              fontSize={10}
              fontFamily="Share Tech Mono,monospace"
              fill={COLOR_FVG}
            >
              FVG · {(fvgTop - fvgBottom).toFixed(0)} pts
            </text>
          </g>
        )}

        {/* Three core candles */}
        {[c0, c1, c2].map((bar, idx) => {
          if (!showCandle(idx)) return null;
          const cx = barCx(idx + 1);
          const yH = priceToY(bar.h);
          const yL = priceToY(bar.l);
          const yO = priceToY(bar.o);
          const yC = priceToY(bar.c);
          const isDisplacement = idx === 1;
          return (
            <g key={`c-${idx}`} style={{ animation: 'fvgFadeIn 350ms ease-out' }}>
              <line x1={cx} x2={cx} y1={yH} y2={yL} stroke={bodyColor} strokeWidth={1} />
              <rect
                x={cx - barW * 0.32}
                y={Math.min(yO, yC)}
                width={barW * 0.64}
                height={Math.max(Math.abs(yO - yC), 1)}
                fill={bodyColor}
                stroke={bodyColor}
                strokeWidth={isDisplacement ? 1.5 : 0.5}
              />
              <text
                x={cx}
                y={viewH - PAD_Y + 14}
                fontSize={9}
                fontFamily="JetBrains Mono,monospace"
                fill="var(--fg-4)"
                textAnchor="middle"
              >
                C{idx}
              </text>
            </g>
          );
        })}

        {/* Retrace bars */}
        {showRetrace &&
          retraceBars.map((bar, idx) => {
            const cx = barCx(idx + 4);
            const yH = priceToY(bar.h);
            const yL = priceToY(bar.l);
            const yO = priceToY(bar.o);
            const yC = priceToY(bar.c);
            const isBearRetrace = bar.c < bar.o;
            const c = isBearRetrace ? COLOR_BEAR : COLOR_BULL;
            return (
              <g key={`r-${idx}`} opacity={0.85}>
                <line x1={cx} x2={cx} y1={yH} y2={yL} stroke={c} strokeWidth={0.8} />
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

        {/* Mitigation arrow */}
        {showRetrace && (
          <g>
            <path
              d={`M ${barCx(3) + 6} ${priceToY(c2.h)} Q ${barCx(4)} ${priceToY((fvgTop + fvgBottom) / 2)}, ${barCx(5) - 4} ${priceToY((fvgTop + fvgBottom) / 2)}`}
              fill="none"
              stroke={COLOR_FILL}
              strokeWidth={1.5}
              strokeDasharray="4 3"
            />
            <text
              x={barCx(5) + 4}
              y={priceToY((fvgTop + fvgBottom) / 2) - 4}
              fontSize={9}
              fontFamily="Share Tech Mono,monospace"
              fill={COLOR_FILL}
            >
              MITIGATION TAP
            </text>
          </g>
        )}

        <style>
          {`@keyframes fvgFadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }`}
        </style>
      </svg>

      <div
        className="mono"
        style={{
          marginTop: 8,
          padding: '8px 12px',
          background: `${COLOR_FVG}10`,
          border: `1px solid ${COLOR_FVG}33`,
          borderRadius: 4,
          fontSize: 11,
          color: 'var(--fg-2)',
          lineHeight: 1.5,
        }}
      >
        <span style={{ color: COLOR_FVG, letterSpacing: '.16em', fontSize: 9 }}>
          {STEP_DESCRIPTIONS[step].caption} //
        </span>{' '}
        {STEP_DESCRIPTIONS[step].sub}
      </div>
    </div>
  );
}
