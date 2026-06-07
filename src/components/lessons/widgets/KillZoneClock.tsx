import { useEffect, useMemo, useState } from 'react';

export interface KillZoneClockProps {
  /** UTC time to render. Defaults to a ticking `new Date()`. */
  currentTimeUtc?: Date;
  /** 24 hourly volume samples, used to modulate arc brightness. */
  volumeByHour?: number[];
  compact?: boolean;
  size?: number;
  className?: string;
}

interface Zone {
  id: string;
  label: string;
  // UTC start/end hours (decimals allowed). NY ET kill zones converted to UTC
  // assuming EST (UTC-5). DST shifts these by 1h — operator-side concern.
  startUtc: number;
  endUtc: number;
  color: string;
  tier: 'primary' | 'secondary' | 'overnight';
}

const ZONES: Zone[] = [
  { id: 'asian',        label: 'ASIAN',        startUtc: 1,   endUtc: 5,   color: '#60a5fa', tier: 'overnight' },
  { id: 'london_open',  label: 'LONDON OPEN',  startUtc: 7,   endUtc: 10,  color: '#22d3ee', tier: 'primary'   },
  { id: 'ny_am',        label: 'NY AM',        startUtc: 13.5, endUtc: 16, color: '#fbbf24', tier: 'primary'   },
  { id: 'london_close', label: 'LONDON CLOSE', startUtc: 15,  endUtc: 17,  color: '#fbbf24', tier: 'secondary' },
  { id: 'ny_pm',        label: 'NY PM',        startUtc: 18.5, endUtc: 21, color: '#fbbf24', tier: 'secondary' },
];

const COLOR_NOW = '#ffffff';
const COLOR_DEAD = 'var(--fg-4)';

export function KillZoneClock({
  currentTimeUtc,
  volumeByHour,
  compact = false,
  size,
  className,
}: KillZoneClockProps) {
  const [tick, setTick] = useState(() => currentTimeUtc ?? new Date());

  useEffect(() => {
    if (currentTimeUtc) {
      setTick(currentTimeUtc);
      return;
    }
    const timer = setInterval(() => setTick(new Date()), 30_000);
    return () => clearInterval(timer);
  }, [currentTimeUtc]);

  const dim = size ?? (compact ? 260 : 360);
  const cx = dim / 2;
  const cy = dim / 2;
  const rOuter = dim * 0.45;
  const rInner = dim * 0.30;
  const rArc = (rOuter + rInner) / 2;

  const nowHours = useMemo(() => {
    const utcH = tick.getUTCHours();
    const utcM = tick.getUTCMinutes();
    return utcH + utcM / 60;
  }, [tick]);

  const activeZone = useMemo(() => {
    return ZONES.find((z) => isHourInside(nowHours, z.startUtc, z.endUtc)) ?? null;
  }, [nowHours]);

  // Arc brightness modulation by historical volume; default = 1
  const zoneBrightness = useMemo(() => {
    if (!volumeByHour || volumeByHour.length !== 24) {
      return Object.fromEntries(ZONES.map((z) => [z.id, 1]));
    }
    const maxV = Math.max(...volumeByHour, 1);
    return Object.fromEntries(
      ZONES.map((z) => {
        const span: number[] = [];
        for (let h = Math.floor(z.startUtc); h < Math.ceil(z.endUtc); h++) {
          span.push(volumeByHour[h % 24] ?? 0);
        }
        const avg = span.length > 0 ? span.reduce((s, v) => s + v, 0) / span.length : 0;
        return [z.id, 0.4 + 0.6 * (avg / maxV)];
      }),
    );
  }, [volumeByHour]);

  // Find next boundary (zone enter or exit) for countdown
  const countdown = useMemo(() => {
    const boundaries: { t: number; label: string; entering: Zone | null }[] = [];
    for (const z of ZONES) {
      boundaries.push({ t: z.startUtc, label: `${z.label} OPEN`, entering: z });
      boundaries.push({ t: z.endUtc, label: `${z.label} CLOSE`, entering: null });
    }
    boundaries.sort((a, b) => a.t - b.t);
    const next = boundaries.find((b) => b.t > nowHours) ?? boundaries[0];
    const deltaH = next.t > nowHours ? next.t - nowHours : 24 - nowHours + next.t;
    const hh = Math.floor(deltaH);
    const mm = Math.round((deltaH - hh) * 60);
    return { label: next.label, hh, mm };
  }, [nowHours]);

  return (
    <div className={className} style={{ width: '100%', textAlign: 'center' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-end',
          marginBottom: 8,
          gap: 8,
        }}
      >
        <div style={{ textAlign: 'left' }}>
          <div
            className="mono"
            style={{
              fontSize: 10,
              color: activeZone?.color ?? COLOR_DEAD,
              letterSpacing: '.22em',
              textTransform: 'uppercase',
            }}
          >
            // 24H KILL-ZONE CLOCK · UTC
          </div>
          <div
            className="mono"
            style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.14em', marginTop: 3 }}
          >
            now {formatHM(nowHours)} · {activeZone ? `inside ${activeZone.label}` : 'dead session'}
          </div>
        </div>
        <div
          className="mono"
          style={{
            fontSize: 10,
            color: 'var(--fg-3)',
            letterSpacing: '.14em',
            textAlign: 'right',
          }}
        >
          next: {countdown.label}
          <br />
          <span style={{ color: COLOR_NOW, fontSize: 12, fontWeight: 700 }}>
            in {countdown.hh}h {countdown.mm.toString().padStart(2, '0')}m
          </span>
        </div>
      </div>

      <svg viewBox={`0 0 ${dim} ${dim}`} style={{ width: '100%', maxWidth: dim, height: 'auto' }}>
        {/* Outer ring */}
        <circle cx={cx} cy={cy} r={rOuter} fill="rgba(0,0,0,.4)" stroke="var(--border-soft)" strokeWidth={1} />
        {/* Inner ring */}
        <circle cx={cx} cy={cy} r={rInner} fill="rgba(0,0,0,.65)" stroke="var(--border-soft)" strokeWidth={1} />

        {/* Hour ticks */}
        {Array.from({ length: 24 }, (_, h) => {
          const a = hourToAngle(h);
          const r1 = rOuter;
          const r2 = rOuter + 6;
          const x1 = cx + r1 * Math.cos(a);
          const y1 = cy + r1 * Math.sin(a);
          const x2 = cx + r2 * Math.cos(a);
          const y2 = cy + r2 * Math.sin(a);
          const isMajor = h % 6 === 0;
          return (
            <g key={`tick-${h}`}>
              <line
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke="var(--fg-4)"
                strokeWidth={isMajor ? 1.5 : 0.5}
              />
              {isMajor && (
                <text
                  x={cx + (rOuter + 16) * Math.cos(a)}
                  y={cy + (rOuter + 16) * Math.sin(a) + 3}
                  fontSize={9}
                  fontFamily="JetBrains Mono,monospace"
                  fill="var(--fg-3)"
                  textAnchor="middle"
                >
                  {h.toString().padStart(2, '0')}
                </text>
              )}
            </g>
          );
        })}

        {/* Zone arcs */}
        {ZONES.map((z) => {
          const a0 = hourToAngle(z.startUtc);
          const a1 = hourToAngle(z.endUtc);
          const x0 = cx + rArc * Math.cos(a0);
          const y0 = cy + rArc * Math.sin(a0);
          const x1 = cx + rArc * Math.cos(a1);
          const y1 = cy + rArc * Math.sin(a1);
          const sweep = z.endUtc - z.startUtc;
          const largeArc = sweep > 12 ? 1 : 0;
          const brightness = zoneBrightness[z.id] ?? 1;
          const strokeWidth = (rOuter - rInner) * 0.85;
          const opacity = z.id === activeZone?.id ? 1 : 0.45 + 0.3 * brightness;
          return (
            <g key={z.id}>
              <path
                d={`M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${rArc} ${rArc} 0 ${largeArc} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`}
                fill="none"
                stroke={z.color}
                strokeWidth={strokeWidth}
                strokeLinecap="butt"
                opacity={opacity}
              />
              <text
                x={cx + rArc * Math.cos((a0 + a1) / 2)}
                y={cy + rArc * Math.sin((a0 + a1) / 2) + 3}
                fontSize={8}
                fontFamily="Share Tech Mono,monospace"
                fill={z.color}
                textAnchor="middle"
                fontWeight={z.id === activeZone?.id ? 700 : 400}
                opacity={z.id === activeZone?.id ? 1 : 0.7}
                letterSpacing="0.1em"
              >
                {z.label}
              </text>
            </g>
          );
        })}

        {/* NOW hand */}
        <line
          x1={cx}
          y1={cy}
          x2={cx + rOuter * Math.cos(hourToAngle(nowHours))}
          y2={cy + rOuter * Math.sin(hourToAngle(nowHours))}
          stroke={COLOR_NOW}
          strokeWidth={1.5}
        />
        <circle cx={cx} cy={cy} r={4} fill={COLOR_NOW} />
        <circle
          cx={cx + rArc * Math.cos(hourToAngle(nowHours))}
          cy={cy + rArc * Math.sin(hourToAngle(nowHours))}
          r={5}
          fill={activeZone?.color ?? COLOR_NOW}
          stroke="#000"
          strokeWidth={1}
        />

        {/* Center label */}
        <text
          x={cx}
          y={cy - 8}
          fontSize={11}
          fontFamily="Share Tech Mono,monospace"
          fill="var(--fg-3)"
          textAnchor="middle"
          letterSpacing="0.18em"
        >
          UTC
        </text>
        <text
          x={cx}
          y={cy + 10}
          fontSize={18}
          fontFamily="JetBrains Mono,monospace"
          fill={activeZone?.color ?? COLOR_NOW}
          textAnchor="middle"
          fontWeight={700}
        >
          {formatHM(nowHours)}
        </text>
      </svg>
    </div>
  );
}

function hourToAngle(h: number): number {
  // 0h at top (-PI/2), clockwise, 24h full revolution
  return -Math.PI / 2 + (h / 24) * 2 * Math.PI;
}

function formatHM(decH: number): string {
  const h = Math.floor(decH);
  const m = Math.floor((decH - h) * 60);
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
}

function isHourInside(h: number, start: number, end: number): boolean {
  if (start <= end) return h >= start && h < end;
  // wraps midnight
  return h >= start || h < end;
}
