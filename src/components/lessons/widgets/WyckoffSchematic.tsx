import { useMemo, useState } from 'react';

export interface WyckoffSchematicProps {
  phase?: 'accumulation' | 'distribution';
  compact?: boolean;
  height?: number;
  className?: string;
}

const VIEW_W = 720;
const PAD_X = 32;
const PAD_Y = 30;

const COLOR_ACTIVE = '#22d3ee';
const COLOR_DIM = 'var(--fg-4)';
const COLOR_RANGE = '#a78bfa';
const COLOR_SPRING = '#fbbf24';
const COLOR_TREND = '#34d399';
const COLOR_BEAR = '#f87171';

interface SchemaEvent {
  id: string;
  pct: number;
  label: string;
  full: string;
  price: number;
  intent: string;
}

const ACCUMULATION_EVENTS: SchemaEvent[] = [
  { id: 'ps',     pct: 0.06, label: 'PS',     full: 'Preliminary Support',         price: 40, intent: 'first taste of buying interest — composite operator probes the market' },
  { id: 'sc',     pct: 0.13, label: 'SC',     full: 'Selling Climax',              price: 20, intent: 'panicked retail dumps into bids — operator absorbs the supply' },
  { id: 'ar',     pct: 0.22, label: 'AR',     full: 'Automatic Rally',             price: 55, intent: 'shorts cover, weak hands chase — defines top of range' },
  { id: 'st',     pct: 0.32, label: 'ST',     full: 'Secondary Test',              price: 30, intent: 'price retests SC area on lower volume — confirms support holds' },
  { id: 'phaseb', pct: 0.46, label: 'PHASE B', full: 'Phase B — Cause Building',   price: 40, intent: 'long chop — operator accumulates inventory while drying out volume' },
  { id: 'spring', pct: 0.60, label: 'SPRING', full: 'Spring',                      price: 14, intent: 'tag below SC low — scoops stop-clusters parked there' },
  { id: 'test',   pct: 0.68, label: 'TEST',   full: 'Test of Spring',              price: 22, intent: 'low-volume retest — confirms supply is exhausted' },
  { id: 'sos',    pct: 0.78, label: 'SOS',    full: 'Sign of Strength',            price: 62, intent: 'wide-spread bar through the Creek — markup begins' },
  { id: 'lps',    pct: 0.86, label: 'LPS',    full: 'Last Point of Support',       price: 48, intent: 'pullback to creek edge — last low-risk entry' },
  { id: 'jac',    pct: 0.95, label: 'JAC',    full: 'Jump Across the Creek',       price: 82, intent: 'Phase E markup — trend established' },
];

const DISTRIBUTION_EVENTS: SchemaEvent[] = [
  { id: 'psy',    pct: 0.06, label: 'PSY',    full: 'Preliminary Supply',          price: 60, intent: 'first taste of selling — operator begins distributing' },
  { id: 'bc',     pct: 0.13, label: 'BC',     full: 'Buying Climax',               price: 80, intent: 'euphoric retail buys tops — operator unloads into demand' },
  { id: 'ar',     pct: 0.22, label: 'AR',     full: 'Automatic Reaction',          price: 45, intent: 'longs puke, defines bottom of range' },
  { id: 'st',     pct: 0.32, label: 'ST',     full: 'Secondary Test',              price: 70, intent: 'retest BC area on lower volume' },
  { id: 'phaseb', pct: 0.46, label: 'PHASE B', full: 'Phase B — Cause Building',   price: 60, intent: 'chop while operator distributes inventory' },
  { id: 'utad',   pct: 0.60, label: 'UTAD',   full: 'Upthrust After Distribution', price: 86, intent: 'tag above BC high — sweeps stop-clusters' },
  { id: 'st2',    pct: 0.68, label: 'ST',     full: 'ST after UTAD',               price: 78, intent: 'retest fails to break above range' },
  { id: 'sow',    pct: 0.78, label: 'SOW',    full: 'Sign of Weakness',            price: 38, intent: 'wide-spread down-bar through the Ice — markdown begins' },
  { id: 'lpsy',   pct: 0.86, label: 'LPSY',   full: 'Last Point of Supply',        price: 52, intent: 'weak rally back to ice — last low-risk short' },
  { id: 'mark',   pct: 0.95, label: 'MD',     full: 'Markdown',                    price: 18, intent: 'Phase E markdown — trend established' },
];

export function WyckoffSchematic({
  phase = 'accumulation',
  compact = false,
  height,
  className,
}: WyckoffSchematicProps) {
  const [playhead, setPlayhead] = useState(0);
  const events = phase === 'accumulation' ? ACCUMULATION_EVENTS : DISTRIBUTION_EVENTS;

  const viewH = height ?? (compact ? 280 : 360);
  const innerW = VIEW_W - 2 * PAD_X;
  const innerH = viewH - 2 * PAD_Y;

  const pctToX = (pct: number) => PAD_X + pct * innerW;
  const priceToY = (p: number) => PAD_Y + ((100 - p) / 100) * innerH;

  // Snake-line path connecting events in order
  const pathD = useMemo(() => {
    return events
      .map((e, i) => `${i === 0 ? 'M' : 'L'} ${pctToX(e.pct).toFixed(1)} ${priceToY(e.price).toFixed(1)}`)
      .join(' ');
  }, [events]);

  // Find the active event (closest to playhead position)
  const activeEvent = useMemo(() => {
    const target = playhead / 100;
    let best: SchemaEvent | null = null;
    let bestDist = Infinity;
    for (const e of events) {
      const d = Math.abs(e.pct - target);
      if (d < bestDist) {
        best = e;
        bestDist = d;
      }
    }
    return best;
  }, [playhead, events]);

  const trendColor = phase === 'accumulation' ? COLOR_TREND : COLOR_BEAR;

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
              color: COLOR_RANGE,
              letterSpacing: '.22em',
              textTransform: 'uppercase',
            }}
          >
            // WYCKOFF · {phase.toUpperCase()}
          </div>
          <div
            className="mono"
            style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.14em', marginTop: 3 }}
          >
            drag the playhead — composite operator narrates intent
          </div>
        </div>
        <div className="mono" style={{ fontSize: 9, color: COLOR_ACTIVE, letterSpacing: '.16em' }}>
          {playhead}% · {activeEvent?.label ?? '—'}
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
        {/* Range boundaries (creek / ice) */}
        <line
          x1={PAD_X}
          x2={VIEW_W - PAD_X}
          y1={priceToY(58)}
          y2={priceToY(58)}
          stroke={COLOR_RANGE}
          strokeWidth={1}
          strokeDasharray="6 4"
          opacity={0.6}
        />
        <line
          x1={PAD_X}
          x2={VIEW_W - PAD_X}
          y1={priceToY(22)}
          y2={priceToY(22)}
          stroke={COLOR_RANGE}
          strokeWidth={1}
          strokeDasharray="6 4"
          opacity={0.6}
        />
        <text
          x={PAD_X + 4}
          y={priceToY(58) - 4}
          fontSize={9}
          fontFamily="Share Tech Mono,monospace"
          fill={COLOR_RANGE}
          opacity={0.7}
        >
          {phase === 'accumulation' ? 'CREEK' : 'ICE'} · range high
        </text>
        <text
          x={PAD_X + 4}
          y={priceToY(22) - 4}
          fontSize={9}
          fontFamily="Share Tech Mono,monospace"
          fill={COLOR_RANGE}
          opacity={0.7}
        >
          range low
        </text>

        {/* Snake line through events */}
        <path d={pathD} fill="none" stroke={trendColor} strokeWidth={1.5} opacity={0.7} />

        {/* Event markers */}
        {events.map((e) => {
          const isActive = activeEvent?.id === e.id;
          const x = pctToX(e.pct);
          const y = priceToY(e.price);
          return (
            <g key={e.id}>
              <circle
                cx={x}
                cy={y}
                r={isActive ? 6 : 3.5}
                fill={isActive ? COLOR_ACTIVE : trendColor}
                stroke={isActive ? '#ffffff' : 'none'}
                strokeWidth={isActive ? 1 : 0}
              />
              {isActive && (
                <circle cx={x} cy={y} r={10} fill="none" stroke={COLOR_ACTIVE} strokeWidth={1}>
                  <animate attributeName="r" from={6} to={14} dur="1.4s" repeatCount="indefinite" />
                  <animate attributeName="opacity" from={0.9} to={0} dur="1.4s" repeatCount="indefinite" />
                </circle>
              )}
              <text
                x={x}
                y={y - 12}
                fontSize={isActive ? 11 : 9}
                fontFamily="Share Tech Mono,monospace"
                fill={isActive ? COLOR_ACTIVE : COLOR_DIM}
                textAnchor="middle"
                fontWeight={isActive ? 700 : 400}
              >
                {e.label}
              </text>
            </g>
          );
        })}

        {/* Playhead */}
        <line
          x1={pctToX(playhead / 100)}
          x2={pctToX(playhead / 100)}
          y1={PAD_Y - 6}
          y2={viewH - PAD_Y + 6}
          stroke={COLOR_SPRING}
          strokeWidth={1.5}
        />
        <polygon
          points={`${pctToX(playhead / 100) - 5},${PAD_Y - 10} ${pctToX(playhead / 100) + 5},${PAD_Y - 10} ${pctToX(playhead / 100)},${PAD_Y - 4}`}
          fill={COLOR_SPRING}
        />
      </svg>

      {/* Scrubber */}
      <div style={{ marginTop: 8 }}>
        <input
          type="range"
          min={0}
          max={100}
          step={1}
          value={playhead}
          onChange={(e) => setPlayhead(Number(e.target.value))}
          aria-label="schematic playhead"
          style={{ width: '100%', accentColor: COLOR_SPRING }}
        />
      </div>

      {/* Composite operator narration */}
      {activeEvent && (
        <div
          style={{
            marginTop: 8,
            padding: '10px 14px',
            border: `1px solid ${COLOR_ACTIVE}55`,
            borderRadius: 6,
            background: `${COLOR_ACTIVE}10`,
          }}
        >
          <div
            className="mono"
            style={{
              fontSize: 9,
              color: COLOR_ACTIVE,
              letterSpacing: '.18em',
              textTransform: 'uppercase',
              marginBottom: 4,
            }}
          >
            // {activeEvent.full}
          </div>
          <div
            style={{
              fontFamily: 'JetBrains Mono,monospace',
              fontSize: 12,
              color: 'var(--fg-1)',
              lineHeight: 1.55,
              fontStyle: 'italic',
            }}
          >
            "{activeEvent.intent}"
          </div>
        </div>
      )}
    </div>
  );
}
