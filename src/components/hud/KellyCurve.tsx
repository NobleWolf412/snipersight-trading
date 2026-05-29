import { useMemo, useState } from 'react';

export interface KellyCurveProps {
  winRate: number;
  payoffRatio: number;
  bettingFraction?: number;
  showZones?: boolean;
  showFractionalMarkers?: boolean;
  compact?: boolean;
  height?: number;
  className?: string;
  label?: string;
}

const VIEW_W = 560;
const PAD_L = 44;
const PAD_R = 16;
const PAD_T = 18;
const PAD_B = 36;

const COLOR_UNDER = '#22d3ee';
const COLOR_OVER = '#fbbf24';
const COLOR_RUIN = '#f87171';
const COLOR_GRID = 'var(--border-soft)';
const COLOR_TEXT = 'var(--fg-3)';
const COLOR_MARKER = '#a78bfa';

const SAMPLES = 240;

export function KellyCurve({
  winRate,
  payoffRatio,
  bettingFraction,
  showZones = true,
  showFractionalMarkers = true,
  compact = false,
  height,
  className,
  label,
}: KellyCurveProps) {
  const [hover, setHover] = useState<{ f: number; g: number; x: number; y: number } | null>(null);

  const viewH = height ?? (compact ? 200 : 320);
  const innerW = VIEW_W - PAD_L - PAD_R;
  const innerH = viewH - PAD_T - PAD_B;

  const { fStar, twoFStar, xMax, points, yMin, yMax } = useMemo(() => {
    const b = payoffRatio;
    const p = Math.min(0.999, Math.max(0.001, winRate));
    const q = 1 - p;
    const star = Math.max(0, (b * p - q) / b);
    const twoStar = 2 * star;
    // x-axis ends slightly past 2·f* to show the ruin zone; clamp before log(1-f)=−∞
    const xMaxRaw = Math.min(0.95, Math.max(0.05, twoStar * 1.35));
    const pts: { f: number; g: number }[] = [];
    for (let i = 0; i <= SAMPLES; i++) {
      const f = (i / SAMPLES) * xMaxRaw;
      if (f >= 1) continue;
      const g = p * Math.log(1 + f * b) + q * Math.log(1 - f);
      pts.push({ f, g });
    }
    const ys = pts.map((pt) => pt.g);
    const ymax = Math.max(...ys, 0);
    const ymin = Math.min(...ys, 0);
    return { fStar: star, twoFStar: twoStar, xMax: xMaxRaw, points: pts, yMin: ymin, yMax: ymax };
  }, [winRate, payoffRatio]);

  const yRange = yMax - yMin || 1;
  const fToX = (f: number) => PAD_L + (f / xMax) * innerW;
  const gToY = (g: number) => PAD_T + ((yMax - g) / yRange) * innerH;

  const pathD = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${fToX(p.f).toFixed(2)} ${gToY(p.g).toFixed(2)}`)
    .join(' ');

  const zeroY = gToY(0);

  // Zone bands
  const xZeroLineY = gToY(0);
  const zones = showZones
    ? [
        { x0: 0, x1: fStar, fill: COLOR_UNDER, label: 'UNDER-KELLY' },
        { x0: fStar, x1: twoFStar, fill: COLOR_OVER, label: 'OVER-KELLY' },
        { x0: twoFStar, x1: xMax, fill: COLOR_RUIN, label: 'RUIN ZONE' },
      ]
    : [];

  const onMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const xPx = e.clientX - rect.left;
    const xRatio = xPx / rect.width;
    const xView = xRatio * VIEW_W;
    const f = ((xView - PAD_L) / innerW) * xMax;
    if (f < 0 || f >= xMax) {
      setHover(null);
      return;
    }
    const b = payoffRatio;
    const g = winRate * Math.log(1 + f * b) + (1 - winRate) * Math.log(1 - f);
    setHover({ f, g, x: fToX(f), y: gToY(g) });
  };

  return (
    <div className={className} style={{ width: '100%' }}>
      {label && (
        <div
          className="mono"
          style={{
            fontSize: 10,
            color: COLOR_MARKER,
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
        onMouseMove={onMouseMove}
        onMouseLeave={() => setHover(null)}
        style={{
          width: '100%',
          height: viewH,
          background: 'rgba(0,0,0,.40)',
          border: '1px solid var(--border-soft)',
          borderRadius: 6,
          cursor: 'crosshair',
        }}
      >
        {/* Zone bands (under curve) */}
        {zones.map((z, i) => (
          <rect
            key={`zone-${i}`}
            x={fToX(z.x0)}
            y={PAD_T}
            width={Math.max(0, fToX(z.x1) - fToX(z.x0))}
            height={innerH}
            fill={`${z.fill}10`}
          />
        ))}

        {/* Horizontal gridlines + y labels */}
        {[yMax, (yMax + yMin) / 2, yMin].map((y, i) => (
          <g key={`yg-${i}`}>
            <line
              x1={PAD_L}
              x2={VIEW_W - PAD_R}
              y1={gToY(y)}
              y2={gToY(y)}
              stroke={COLOR_GRID}
              strokeWidth={0.5}
              strokeDasharray="2 4"
            />
            <text
              x={PAD_L - 6}
              y={gToY(y) + 3}
              fontSize={9}
              fontFamily="JetBrains Mono,monospace"
              fill={COLOR_TEXT}
              textAnchor="end"
            >
              {y.toFixed(3)}
            </text>
          </g>
        ))}

        {/* Zero growth line */}
        <line
          x1={PAD_L}
          x2={VIEW_W - PAD_R}
          y1={zeroY}
          y2={zeroY}
          stroke={COLOR_GRID}
          strokeWidth={1}
        />

        {/* X axis labels */}
        {[0, fStar, twoFStar, xMax].map((f, i) => (
          <g key={`xg-${i}`}>
            <line
              x1={fToX(f)}
              x2={fToX(f)}
              y1={PAD_T}
              y2={viewH - PAD_B}
              stroke={COLOR_GRID}
              strokeWidth={0.5}
              strokeDasharray="2 4"
            />
            <text
              x={fToX(f)}
              y={viewH - PAD_B + 14}
              fontSize={9}
              fontFamily="JetBrains Mono,monospace"
              fill={COLOR_TEXT}
              textAnchor="middle"
            >
              {(f * 100).toFixed(1)}%
            </text>
          </g>
        ))}

        {/* The Kelly curve */}
        <path d={pathD} fill="none" stroke={COLOR_MARKER} strokeWidth={2} />

        {/* f* marker line */}
        <line
          x1={fToX(fStar)}
          x2={fToX(fStar)}
          y1={PAD_T}
          y2={viewH - PAD_B}
          stroke={COLOR_UNDER}
          strokeWidth={1.5}
          strokeDasharray="4 3"
        />
        <text
          x={fToX(fStar) + 4}
          y={PAD_T + 12}
          fontSize={10}
          fontFamily="Share Tech Mono,monospace"
          fill={COLOR_UNDER}
        >
          f* = {(fStar * 100).toFixed(1)}%
        </text>

        {/* 2f* marker line */}
        <line
          x1={fToX(twoFStar)}
          x2={fToX(twoFStar)}
          y1={PAD_T}
          y2={viewH - PAD_B}
          stroke={COLOR_OVER}
          strokeWidth={1.5}
          strokeDasharray="4 3"
        />
        <text
          x={fToX(twoFStar) + 4}
          y={PAD_T + 26}
          fontSize={10}
          fontFamily="Share Tech Mono,monospace"
          fill={COLOR_OVER}
        >
          2f* (g=0)
        </text>

        {/* Fractional Kelly markers */}
        {showFractionalMarkers && fStar > 0 && (
          <>
            {[0.5, 0.25].map((frac) => (
              <g key={`frac-${frac}`}>
                <line
                  x1={fToX(fStar * frac)}
                  x2={fToX(fStar * frac)}
                  y1={zeroY - 6}
                  y2={zeroY + 6}
                  stroke={COLOR_TEXT}
                  strokeWidth={1}
                />
                <text
                  x={fToX(fStar * frac)}
                  y={zeroY + 18}
                  fontSize={8}
                  fontFamily="JetBrains Mono,monospace"
                  fill={COLOR_TEXT}
                  textAnchor="middle"
                >
                  {frac === 0.5 ? '½K' : '¼K'}
                </text>
              </g>
            ))}
          </>
        )}

        {/* Operator's current bettingFraction */}
        {bettingFraction !== undefined && bettingFraction >= 0 && bettingFraction < xMax && (
          <g>
            <line
              x1={fToX(bettingFraction)}
              x2={fToX(bettingFraction)}
              y1={PAD_T}
              y2={viewH - PAD_B}
              stroke="#ffffff"
              strokeWidth={1.5}
            />
            <text
              x={fToX(bettingFraction)}
              y={viewH - PAD_B - 4}
              fontSize={9}
              fontFamily="Share Tech Mono,monospace"
              fill="#ffffff"
              textAnchor="middle"
            >
              YOUR f = {(bettingFraction * 100).toFixed(1)}%
            </text>
          </g>
        )}

        {/* Hover crosshair */}
        {hover && (
          <g>
            <line
              x1={hover.x}
              x2={hover.x}
              y1={PAD_T}
              y2={viewH - PAD_B}
              stroke={COLOR_MARKER}
              strokeWidth={1}
              strokeDasharray="3 3"
              opacity={0.6}
            />
            <circle cx={hover.x} cy={hover.y} r={4} fill={COLOR_MARKER} />
            <rect
              x={Math.min(hover.x + 8, VIEW_W - 110)}
              y={Math.max(hover.y - 26, PAD_T + 2)}
              width={100}
              height={22}
              fill="rgba(0,0,0,.85)"
              stroke={COLOR_MARKER}
              strokeWidth={0.5}
              rx={3}
            />
            <text
              x={Math.min(hover.x + 14, VIEW_W - 104)}
              y={Math.max(hover.y - 12, PAD_T + 16)}
              fontSize={9}
              fontFamily="JetBrains Mono,monospace"
              fill="#ffffff"
            >
              f={(hover.f * 100).toFixed(1)}% g={hover.g.toFixed(4)}
            </text>
          </g>
        )}
      </svg>

      <div
        className="mono"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: 6,
          fontSize: 9,
          color: 'var(--fg-4)',
          letterSpacing: '.16em',
          textTransform: 'uppercase',
        }}
      >
        <span>W {(winRate * 100).toFixed(1)}% · b {payoffRatio.toFixed(2)}</span>
        <span>
          <span style={{ color: COLOR_UNDER }}>under-kelly</span>
          {' / '}
          <span style={{ color: COLOR_OVER }}>over</span>
          {' / '}
          <span style={{ color: COLOR_RUIN }}>ruin</span>
        </span>
      </div>
    </div>
  );
}
