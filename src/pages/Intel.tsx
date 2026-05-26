/**
 * Intel — Phase 3e sub-step 1
 *
 * REWRITE of the prior @ts-nocheck synthetic-only Intel page (662 lines).
 * The new shape is the prototype's macro/regime command center per
 * `prototype/intel.jsx`.
 *
 * Data wiring:
 *   - BTC.D / USDT.D / Alt.D from `useMarketRegime` (calls /api/market/regime).
 *     Falls through to placeholder values when the hook returns the
 *     awaiting-backend default. No fake numbers presented as real.
 *   - Regime label + visibility chip from `useMarketRegime`.
 *   - Static "now" captured at mount — no setInterval re-render. The Topbar
 *     already runs its own UTC clock; this page does not need to drive
 *     time. Static timestamp stabilises snapshots and avoids ticking
 *     SVG indicators that defeat the visual-diff floor.
 *
 * What's intentionally DEFERRED — labelled inline so the operator can never
 * mistake a placeholder for a live signal:
 *   - **Funding & OI** — backend has no perp-funding endpoint yet. Panel
 *     renders SYNTHETIC seed data, panel header tagged
 *     "// SYNTHETIC — pending funding/OI feed".
 *   - **Liquidation Heatmap** — no liquidation feed integration yet;
 *     panel rendered with synthetic clustering, tagged accordingly.
 *   - **Catalyst Wire (news)** — no news ingestion service in scope;
 *     synthetic items labelled.
 *   - **AI Analyst** — Haiku-powered commentary endpoint is not wired;
 *     panel renders sample lines tagged "(synthetic — pending Haiku
 *     wiring)".
 *   - **Fear & Greed** — alternative.me feed not integrated; we surface
 *     a placeholder dial with a `(placeholder)` caption.
 *
 * body[data-snapshot-ready="true"] is set after the regime hook returns
 * its first value (success or fallback). Snapshot framework freezes
 * animations + intercepts /api/market/regime; the catch-all returns {}
 * so the hook produces its CHOPPY/MEDIUM default and the page renders
 * deterministically.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Chip,
  FooterStatus,
  KillZoneStrip,
  MacroScoreTile,
  PageHead,
  Reticle,
  SectionHead,
  fmtNum,
  fmtPct,
  fmtPrice,
} from '@/components/hud';
import { useMarketRegime } from '@/hooks/useMarketRegime';
import {
  api,
  type FundingRow,
  type FearGreedResponse,
  type ScannerMode,
  type BTCCycleContextData,
} from '@/utils/api';

// ─── Synthetic seed data — labelled in the UI as such ────────────────────
//
// These constants stand in for endpoints the backend does not yet expose
// (liquidations, news). Every panel that consumes them sets
// a "// SYNTHETIC" header so the operator never mistakes the rendering
// for a live signal. Replace the seed arrays with real fetches when the
// corresponding endpoints land — no UI restructure required.

interface FundingRowSeed {
  sym: string;
  oi: number;
  oiDelta: number;
  fund: number;
  mark: number;
  change24: number;
}

const FUNDING_SEED: FundingRowSeed[] = [
  { sym: 'BTC', oi: 23.4e9, oiDelta: 2.1, fund: 0.0118, mark: 65120, change24: 1.42 },
  { sym: 'ETH', oi: 11.8e9, oiDelta: -0.6, fund: 0.0094, mark: 3198, change24: -0.32 },
  { sym: 'SOL', oi: 3.62e9, oiDelta: 4.7, fund: 0.024, mark: 141.05, change24: 0.81 },
  { sym: 'BNB', oi: 1.94e9, oiDelta: 0.4, fund: 0.0061, mark: 572.4, change24: 0.22 },
  { sym: 'XRP', oi: 1.41e9, oiDelta: -1.8, fund: 0.0042, mark: 0.524, change24: -0.91 },
  { sym: 'TON', oi: 0.82e9, oiDelta: 6.1, fund: 0.018, mark: 6.84, change24: 2.1 },
  { sym: 'AVAX', oi: 0.51e9, oiDelta: -0.9, fund: 0.0072, mark: 34.18, change24: 1.1 },
  { sym: 'LINK', oi: 0.46e9, oiDelta: 1.1, fund: 0.0085, mark: 14.86, change24: 0.5 },
  { sym: 'INJ', oi: 0.31e9, oiDelta: 3.2, fund: 0.0301, mark: 24.18, change24: 3.4 },
  { sym: 'DOGE', oi: 0.62e9, oiDelta: -2.4, fund: 0.0035, mark: 0.134, change24: -0.97 },
];

interface LiqSeed {
  sym: string;
  longs: number;
  shorts: number;
  ts: number;
}

const LIQ_SEED: LiqSeed[] = [
  { sym: 'BTC', longs: 4.2e6, shorts: 12.8e6, ts: 14 * 60 + 12 },
  { sym: 'ETH', longs: 1.8e6, shorts: 6.4e6, ts: 13 * 60 + 58 },
  { sym: 'SOL', longs: 0.9e6, shorts: 3.1e6, ts: 13 * 60 + 44 },
  { sym: 'BTC', longs: 2.1e6, shorts: 0.8e6, ts: 13 * 60 + 22 },
  { sym: 'TON', longs: 0.4e6, shorts: 1.9e6, ts: 13 * 60 + 10 },
  { sym: 'INJ', longs: 0.2e6, shorts: 0.7e6, ts: 12 * 60 + 58 },
];

interface NewsSeed {
  id: string;
  tag: 'MACRO' | 'CHAIN' | 'REG' | 'WHALE' | 'EXCH';
  pri: 'HIGH' | 'MED' | 'LOW';
  t: string;
  src: string;
  headline: string;
  impact: 'bullish' | 'bearish' | 'neutral';
}

const NEWS_SEED: NewsSeed[] = [
  {
    id: 'n1',
    tag: 'MACRO',
    pri: 'HIGH',
    t: '14:32',
    src: 'Bloomberg',
    headline: 'Fed minutes signal patience on rate cuts; market prices in 2 cuts by Q4',
    impact: 'bullish',
  },
  {
    id: 'n2',
    tag: 'CHAIN',
    pri: 'MED',
    t: '14:11',
    src: 'Coindesk',
    headline: 'BTC ETF inflows hit $312M in single session, breaking 6-day outflow streak',
    impact: 'bullish',
  },
  {
    id: 'n3',
    tag: 'REG',
    pri: 'HIGH',
    t: '13:58',
    src: 'Reuters',
    headline: 'SEC delays decision on ETH staking ETF amendment to mid-Q3',
    impact: 'neutral',
  },
  {
    id: 'n4',
    tag: 'WHALE',
    pri: 'LOW',
    t: '13:42',
    src: 'WhaleAlert',
    headline: '2,400 BTC moved from cold wallet (origin: 2017) to Coinbase deposit',
    impact: 'bearish',
  },
  {
    id: 'n5',
    tag: 'CHAIN',
    pri: 'MED',
    t: '13:21',
    src: 'Coindesk',
    headline:
      'Solana validator count crosses 1,950; Jito MEV revenue up 24% week-over-week',
    impact: 'bullish',
  },
  {
    id: 'n6',
    tag: 'MACRO',
    pri: 'MED',
    t: '12:55',
    src: 'WSJ',
    headline: 'DXY softens to 103.4 as 10Y yields drop 6bp on weaker ISM print',
    impact: 'bullish',
  },
];

interface SessionSeed {
  name: string;
  open: number;
  close: number;
  color: string;
}

const SESSIONS: SessionSeed[] = [
  { name: 'TOKYO', open: 0, close: 9, color: '#60a5fa' },
  { name: 'LONDON', open: 8, close: 17, color: '#fbbf24' },
  { name: 'NEW YORK', open: 13, close: 22, color: '#22c55e' },
];

// ─── DominanceDial ────────────────────────────────────────────────────────
//
// Pure-SVG semicircular dial. Used for BTC.D (real), USDT.D (real),
// Fear&Greed (placeholder).

interface DominanceDialProps {
  value: number;
  label: string;
  range: [number, number];
  color: string;
  sub: string;
}

function DominanceDial({ value, label, range, color, sub }: DominanceDialProps) {
  const pct = (value - range[0]) / (range[1] - range[0]);
  const angle = -135 + Math.max(0, Math.min(1, pct)) * 270;
  const r = 90;
  const arc = (start: number, end: number) => {
    const s = (start * Math.PI) / 180;
    const e = (end * Math.PI) / 180;
    const x1 = r * Math.cos(s);
    const y1 = r * Math.sin(s);
    const x2 = r * Math.cos(e);
    const y2 = r * Math.sin(e);
    const large = end - start > 180 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
  };
  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        aspectRatio: '1.6 / 1',
        maxWidth: 340,
        margin: '0 auto',
      }}
    >
      <svg viewBox="-110 -110 220 130" style={{ width: '100%', height: '100%' }}>
        <path
          d={arc(-180 + 45, 45)}
          stroke="rgba(255,255,255,.06)"
          strokeWidth="6"
          fill="none"
          strokeLinecap="round"
        />
        {Array.from({ length: 11 }).map((_, i) => {
          const a = ((-135 + i * 27) * Math.PI) / 180;
          return (
            <line
              key={i}
              x1={Math.cos(a) * 82}
              y1={Math.sin(a) * 82}
              x2={Math.cos(a) * 98}
              y2={Math.sin(a) * 98}
              stroke="rgba(255,255,255,.12)"
              strokeWidth=".7"
            />
          );
        })}
        <path
          d={arc(-135, angle)}
          stroke={color}
          strokeWidth="6"
          fill="none"
          strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 6px ${color})` }}
        />
        <g transform={`rotate(${angle})`}>
          <line
            x1="0"
            y1="0"
            x2={r - 8}
            y2="0"
            stroke={color}
            strokeWidth="2.4"
            strokeLinecap="round"
          />
          <circle
            cx={r - 8}
            cy={0}
            r="3"
            fill={color}
            style={{ filter: `drop-shadow(0 0 4px ${color})` }}
          />
        </g>
        <circle r="6" fill="rgba(0,0,0,.6)" stroke={color} strokeWidth="1.5" />
        <text x="-94" y="14" fill="var(--fg-4)" fontSize="7" fontFamily="JetBrains Mono,monospace">
          {range[0]}%
        </text>
        <text x="78" y="14" fill="var(--fg-4)" fontSize="7" fontFamily="JetBrains Mono,monospace">
          {range[1]}%
        </text>
      </svg>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'flex-end',
          pointerEvents: 'none',
          paddingBottom: '8%',
        }}
      >
        <div
          className="mono"
          style={{
            fontSize: 9,
            letterSpacing: '.2em',
            color: 'var(--fg-4)',
            textTransform: 'uppercase',
            marginBottom: 2,
          }}
        >
          {label}
        </div>
        <div
          style={{
            fontFamily: 'Share Tech Mono,monospace',
            fontSize: 32,
            letterSpacing: '.04em',
            color,
            fontWeight: 700,
            lineHeight: 1,
          }}
        >
          {value.toFixed(2)}%
        </div>
        <div className="mono" style={{ fontSize: 10, color: 'var(--fg-3)', marginTop: 4 }}>
          {sub}
        </div>
      </div>
    </div>
  );
}

// ─── RegimeTape ──────────────────────────────────────────────────────────

interface TapeRange {
  label: string;
  min: number;
  max: number;
  color: string;
}

interface RegimeTapeProps {
  score: number;
  label: string;
  ranges: TapeRange[];
  color: string;
}

function RegimeTape({ score, label, ranges, color }: RegimeTapeProps) {
  const min = ranges[0].min;
  const max = ranges[ranges.length - 1].max;
  const span = max - min;
  const pct = Math.max(0, Math.min(100, ((score - min) / span) * 100));
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span
          className="mono"
          style={{
            fontSize: 10,
            color: 'var(--fg-4)',
            letterSpacing: '.18em',
            textTransform: 'uppercase',
          }}
        >
          {label}
        </span>
        <span className="mono" style={{ fontSize: 11, fontWeight: 700, color }}>
          {score.toFixed(0)}
        </span>
      </div>
      <div
        style={{
          position: 'relative',
          height: 14,
          borderRadius: 3,
          overflow: 'hidden',
          border: '1px solid var(--border-soft)',
          background: 'rgba(0,0,0,.4)',
          display: 'flex',
        }}
      >
        {ranges.map((r, i) => {
          const w = ((r.max - r.min) / span) * 100;
          return <div key={i} style={{ width: `${w}%`, background: r.color, opacity: 0.25 }} />;
        })}
        <div
          style={{
            position: 'absolute',
            top: -2,
            bottom: -2,
            left: `calc(${pct}% - 2px)`,
            width: 4,
            background: color,
            boxShadow: `0 0 8px ${color}`,
            borderRadius: 1,
          }}
        />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
        {ranges.map((r, i) => (
          <span
            key={i}
            className="mono"
            style={{
              fontSize: 8,
              color: 'var(--fg-4)',
              letterSpacing: '.16em',
              textTransform: 'uppercase',
            }}
          >
            {r.label}
          </span>
        ))}
      </div>
    </div>
  );
}

// ─── FundingRow ──────────────────────────────────────────────────────────

function FundingRowItem({ row }: { row: FundingRow }) {
  const fund = row.funding_rate ?? 0;
  const fundColor =
    fund > 0.0002
      ? 'var(--red-2)'
      : fund > 0.0001
        ? 'var(--amber)'
        : fund > 0
          ? 'var(--green-soft)'
          : 'var(--blue)';
  const fundPct = Math.max(0, Math.min(100, (Math.abs(fund) / 0.0004) * 100));
  const sym = row.symbol.includes('/') ? row.symbol.split('/')[0] : row.symbol;
  const pct = row.price_change_pct;
  const oiUsd = row.open_interest_usd;
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '70px 100px 1fr 90px',
        gap: 8,
        padding: '10px 4px',
        borderBottom: '1px solid var(--border-soft)',
        alignItems: 'center',
        opacity: row.error && !row.mark_price ? 0.45 : 1,
      }}
    >
      <span
        style={{
          fontFamily: 'Share Tech Mono,monospace',
          fontSize: 13,
          letterSpacing: '.06em',
        }}
      >
        {sym}
      </span>
      <div className="mono">
        <span style={{ fontSize: 12, color: 'var(--fg)' }}>
          {row.mark_price != null ? fmtPrice(row.mark_price) : '—'}
        </span>
        {pct != null && (
          <span
            style={{
              fontSize: 10,
              color: pct >= 0 ? 'var(--green-soft)' : 'var(--red-2)',
              marginLeft: 6,
            }}
          >
            {fmtPct(pct, 1)}
          </span>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div
          style={{
            flex: 1,
            position: 'relative',
            height: 5,
            borderRadius: 2,
            background: 'rgba(255,255,255,.05)',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              position: 'absolute',
              inset: 0,
              right: 'auto',
              width: `${fundPct}%`,
              background: fundColor,
              boxShadow: `0 0 6px ${fundColor}`,
            }}
          />
        </div>
        <span
          className="mono"
          style={{
            fontSize: 11,
            color: row.funding_rate != null ? fundColor : 'var(--fg-4)',
            fontWeight: 700,
            minWidth: 62,
            textAlign: 'right',
          }}
        >
          {row.funding_rate != null ? `${(row.funding_rate * 100).toFixed(4)}%` : '—'}
        </span>
      </div>
      <div style={{ textAlign: 'right' }} className="mono">
        <div style={{ fontSize: 11, color: 'var(--fg-2)' }}>
          {oiUsd != null ? `$${fmtNum(oiUsd).replace(/\$/, '')}` : '—'}
        </div>
      </div>
    </div>
  );
}

// ─── LiqHeatmap (synthetic, BTC only) ────────────────────────────────────

function LiqHeatmap() {
  const data = useMemo(() => {
    const center = 65120;
    const buckets = 14;
    const step = 0.005;
    return Array.from({ length: buckets })
      .map((_, i) => {
        const offset = (i - buckets / 2) * step;
        const price = center * (1 + offset);
        // Deterministic synthetic clustering — no Math.random so the snapshot
        // is reproducible. Shorts cluster above price, longs below.
        const shortHeat =
          offset > 0
            ? Math.abs(Math.sin(offset * 100) * 0.7 + Math.cos(i * 0.4) * 0.2)
            : Math.abs(Math.sin(i) * 0.15);
        const longHeat =
          offset < 0
            ? Math.abs(Math.cos(offset * 120) * 0.7 + Math.sin(i * 0.3) * 0.2)
            : Math.abs(Math.cos(i) * 0.12);
        return { offset, price, shortHeat, longHeat };
      })
      .reverse();
  }, []);
  const maxHeat = Math.max(...data.flatMap((d) => [d.shortHeat, d.longHeat]));
  return (
    <div style={{ padding: '12px 2px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <span
          className="mono"
          style={{
            fontSize: 9,
            color: 'var(--red-2)',
            letterSpacing: '.18em',
            textTransform: 'uppercase',
          }}
        >
          ◀ SHORT LIQUIDATIONS
        </span>
        <span
          className="mono"
          style={{
            fontSize: 9,
            color: 'var(--fg-4)',
            letterSpacing: '.18em',
            textTransform: 'uppercase',
          }}
        >
          BTC · price ladder
        </span>
        <span
          className="mono"
          style={{
            fontSize: 9,
            color: 'var(--green-soft)',
            letterSpacing: '.18em',
            textTransform: 'uppercase',
          }}
        >
          LONG LIQUIDATIONS ▶
        </span>
      </div>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
          fontFamily: 'JetBrains Mono,monospace',
          fontSize: 10,
        }}
      >
        {data.map((d, i) => {
          const sw = (d.shortHeat / maxHeat) * 100;
          const lw = (d.longHeat / maxHeat) * 100;
          const isCurrent = Math.abs(d.offset) < 0.003;
          return (
            <div
              key={i}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 90px 1fr',
                alignItems: 'center',
                gap: 8,
                padding: isCurrent ? '2px 0' : '0',
                background: isCurrent ? 'rgba(251,191,36,.08)' : 'transparent',
                borderRadius: isCurrent ? 4 : 0,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'flex-end',
                  height: 14,
                  position: 'relative',
                }}
              >
                <div
                  style={{
                    width: `${sw}%`,
                    background: `linear-gradient(90deg, transparent, rgba(248,113,113, ${
                      0.25 + 0.55 * (d.shortHeat / maxHeat)
                    }))`,
                    border: `1px solid rgba(248,113,113,${0.4 + 0.4 * (d.shortHeat / maxHeat)})`,
                    borderRight: 'none',
                    height: 14,
                    borderRadius: '2px 0 0 2px',
                  }}
                />
              </div>
              <div
                className="mono"
                style={{
                  textAlign: 'center',
                  fontSize: 10,
                  fontWeight: isCurrent ? 800 : 500,
                  color: isCurrent ? 'var(--amber)' : 'var(--fg-3)',
                }}
              >
                {isCurrent && <span style={{ marginRight: 4 }}>◉</span>}${d.price.toFixed(0)}
              </div>
              <div style={{ display: 'flex', height: 14, position: 'relative' }}>
                <div
                  style={{
                    width: `${lw}%`,
                    background: `linear-gradient(90deg, rgba(34,197,94, ${
                      0.25 + 0.55 * (d.longHeat / maxHeat)
                    }), transparent)`,
                    border: `1px solid rgba(34,197,94,${0.4 + 0.4 * (d.longHeat / maxHeat)})`,
                    borderLeft: 'none',
                    height: 14,
                    borderRadius: '0 2px 2px 0',
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── NewsItem ────────────────────────────────────────────────────────────

const TAG_KIND_MAP: Record<NewsSeed['tag'], 'blue' | 'red' | 'green' | 'amber' | 'purple'> = {
  MACRO: 'blue',
  REG: 'red',
  CHAIN: 'green',
  WHALE: 'amber',
  EXCH: 'purple',
};

function NewsItem({ item }: { item: NewsSeed }) {
  const priColor =
    item.pri === 'HIGH'
      ? 'var(--red-2)'
      : item.pri === 'MED'
        ? 'var(--amber)'
        : 'var(--fg-3)';
  const impactColor =
    item.impact === 'bullish'
      ? 'var(--green-soft)'
      : item.impact === 'bearish'
        ? 'var(--red-2)'
        : 'var(--blue)';
  return (
    <div
      style={{
        padding: '10px 10px',
        border: '1px solid var(--border-soft)',
        borderRadius: 6,
        background: 'rgba(0,0,0,.3)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span
          className="mono"
          style={{
            fontSize: 10,
            color: 'var(--fg-4)',
            letterSpacing: '.14em',
            width: 42,
            flexShrink: 0,
          }}
        >
          {item.t}
        </span>
        <Chip kind={TAG_KIND_MAP[item.tag]} style={{ flexShrink: 0, fontSize: 9 }}>
          {item.tag}
        </Chip>
        <span
          style={{
            flexShrink: 0,
            fontSize: 9,
            color: priColor,
            fontWeight: 700,
            letterSpacing: '.16em',
          }}
          className="mono"
        >
          ▲ {item.pri}
        </span>
        <span
          style={{
            flex: 1,
            fontSize: 12,
            color: 'var(--fg-2)',
            lineHeight: 1.4,
            minWidth: 0,
          }}
        >
          {item.headline}
        </span>
        <span
          className="mono"
          style={{
            fontSize: 10,
            color: impactColor,
            fontWeight: 700,
            flexShrink: 0,
            letterSpacing: '.16em',
            textTransform: 'uppercase',
          }}
        >
          {item.impact}
        </span>
      </div>
    </div>
  );
}

// ─── SessionStrip ────────────────────────────────────────────────────────
//
// `now` is captured once at mount (parent freezes it for the snapshot).
// No setInterval — Topbar already runs the page-wide UTC clock.

function SessionStrip({ now }: { now: Date }) {
  const utcHour = now.getUTCHours() + now.getUTCMinutes() / 60;
  const cellW = 100 / 24;
  return (
    <div>
      <div
        style={{
          position: 'relative',
          height: 60,
          border: '1px solid var(--border-soft)',
          borderRadius: 6,
          background: 'rgba(0,0,0,.4)',
          overflow: 'hidden',
        }}
      >
        {Array.from({ length: 24 }).map((_, i) => (
          <div
            key={i}
            style={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              left: `${i * cellW}%`,
              width: '1px',
              background: 'rgba(255,255,255,.04)',
            }}
          />
        ))}
        {SESSIONS.map((s, i) => {
          const left = (s.open / 24) * 100;
          const width = ((s.close - s.open) / 24) * 100;
          const active = utcHour >= s.open && utcHour < s.close;
          return (
            <div
              key={s.name}
              style={{
                position: 'absolute',
                top: 6 + i * 16,
                height: 14,
                left: `${left}%`,
                width: `${width}%`,
                background: active
                  ? `linear-gradient(90deg, ${s.color}33, ${s.color}88)`
                  : `${s.color}22`,
                border: `1px solid ${s.color}${active ? 'cc' : '55'}`,
                borderRadius: 3,
                display: 'flex',
                alignItems: 'center',
                padding: '0 6px',
                boxShadow: active ? `0 0 8px ${s.color}66` : 'none',
              }}
            >
              <span
                className="mono"
                style={{
                  fontSize: 9,
                  letterSpacing: '.18em',
                  color: active ? s.color : 'var(--fg-3)',
                  fontWeight: 700,
                }}
              >
                {s.name}
              </span>
            </div>
          );
        })}
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            left: `${(utcHour / 24) * 100}%`,
            width: 2,
            background: 'var(--accent)',
            boxShadow: '0 0 8px var(--accent)',
            zIndex: 2,
          }}
        >
          <div
            style={{
              position: 'absolute',
              top: -6,
              left: -5,
              width: 12,
              height: 12,
              borderRadius: 6,
              background: 'var(--accent)',
              boxShadow: '0 0 8px var(--accent)',
            }}
          />
        </div>
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: 6,
          fontFamily: 'JetBrains Mono,monospace',
          fontSize: 9,
          color: 'var(--fg-4)',
          letterSpacing: '.14em',
        }}
      >
        <span>00 UTC</span>
        <span>06</span>
        <span>
          12 ◉ {utcHour.toFixed(0).padStart(2, '0')}:
          {String(now.getUTCMinutes()).padStart(2, '0')}
        </span>
        <span>18</span>
        <span>24</span>
      </div>
    </div>
  );
}

// ─── AICommentary (synthetic) ────────────────────────────────────────────

const AI_LINES = [
  {
    t: 'PRIMARY',
    text: 'BTC reclaiming 64.5K with rising spot CVD; ETF inflow flip is structural.',
    conf: 78,
  },
  {
    t: 'CAVEAT',
    text: 'Mt. Gox tranche flagged — distribution overhang next 7-14 sessions.',
    conf: 62,
  },
  {
    t: 'OPP',
    text: 'Alts (TON, INJ, SOL) showing OI expansion w/ funding under 0.025% — clean longs.',
    conf: 71,
  },
  {
    t: 'HEDGE',
    text: '10Y yield pivot < 4.20% would unlock risk-on; >4.40% reverses thesis.',
    conf: 68,
  },
  {
    t: 'TIMING',
    text: 'NY session momentum window 14:30-16:00 UTC has +1.4σ historical edge.',
    conf: 74,
  },
];

function AICommentary() {
  return (
    <div
      style={{
        padding: '14px 18px',
        background: 'rgba(0,0,0,.45)',
        borderTop: '1px solid var(--border-soft)',
        fontFamily: 'JetBrains Mono,monospace',
      }}
    >
      <div style={{ fontSize: 11, color: 'var(--accent)', marginBottom: 10, opacity: 0.85 }}>
        {`> ai-analyst.exec --regime --window=24h`}
        <span>_</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {AI_LINES.map((l, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              gap: 10,
              alignItems: 'flex-start',
              fontSize: 12,
              lineHeight: 1.45,
              color: 'var(--fg-2)',
            }}
          >
            <span
              className="mono"
              style={{
                fontSize: 9,
                color: 'var(--accent)',
                letterSpacing: '.18em',
                fontWeight: 800,
                paddingTop: 3,
                minWidth: 62,
              }}
            >
              {l.t}
            </span>
            <span style={{ flex: 1, color: 'var(--fg)' }}>{l.text}</span>
            <span
              className="mono"
              style={{
                fontSize: 10,
                color:
                  l.conf >= 70
                    ? 'var(--green-soft)'
                    : l.conf >= 60
                      ? 'var(--amber)'
                      : 'var(--fg-3)',
                fontWeight: 700,
                minWidth: 38,
                textAlign: 'right',
              }}
            >
              {l.conf}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── MacroTicker ─────────────────────────────────────────────────────────

interface TickerCell {
  label: string;
  value: string;
  delta: number | null;
  color?: string;
  synthetic?: boolean;
}

function MacroTicker({ values }: { values: TickerCell[] }) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(6, minmax(0,1fr))',
        gap: 0,
        border: '1px solid var(--border-soft)',
        borderRadius: 8,
        overflow: 'hidden',
        background: 'rgba(0,0,0,.35)',
      }}
    >
      {values.map((v, i) => (
        <div
          key={i}
          style={{
            padding: '10px 14px',
            borderRight: i < values.length - 1 ? '1px solid var(--border-soft)' : 'none',
          }}
        >
          <div
            className="mono"
            style={{
              fontSize: 9,
              color: 'var(--fg-4)',
              letterSpacing: '.18em',
              textTransform: 'uppercase',
              marginBottom: 3,
              display: 'flex',
              gap: 4,
            }}
          >
            <span>{v.label}</span>
            {v.synthetic && (
              <span style={{ color: 'var(--amber)', fontSize: 8 }}>◌</span>
            )}
          </div>
          <div
            className="mono"
            style={{ fontSize: 13, fontWeight: 700, color: v.color ?? 'var(--fg)' }}
          >
            {v.value}
          </div>
          {v.delta != null && (
            <div
              className="mono"
              style={{
                fontSize: 9,
                color: v.delta >= 0 ? 'var(--green-soft)' : 'var(--red-2)',
                fontWeight: 600,
              }}
            >
              {fmtPct(v.delta, 2)}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────

export function Intel() {
  const regime = useMarketRegime('scanner');
  const [now] = useState(() => new Date()); // captured once, no interval

  // Snapshot-ready handshake: flip on every mount (StrictMode in dev double-
  // invokes effects; gating on a ref leaves the attribute removed after the
  // synthetic-unmount cleanup fires). Each mount sets, the matching cleanup
  // unsets — final post-double-mount state is set, which is what the
  // capture framework waits on.
  useEffect(() => {
    document.body.setAttribute('data-snapshot-ready', 'true');
    return () => {
      document.body.removeAttribute('data-snapshot-ready');
    };
  }, []);

  // Real dominance values when present, placeholders otherwise. We keep
  // the dial geometry intact in either branch — only the numeric value
  // and sub-caption change. `(awaiting feed)` makes the placeholder
  // unmissable.
  // ── Real data: funding rates + OI (Phemex, 60s cache) ──────────────────
  const [fundingRows, setFundingRows] = useState<FundingRow[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    api.getFundingRates().then((res) => {
      if (!cancelled && res.data) setFundingRows(res.data.rows);
    });
    return () => { cancelled = true; };
  }, []);

  // ── Real data: Fear & Greed (alternative.me, 15 min cache) ───────────────
  const [fearGreedData, setFearGreedData] = useState<FearGreedResponse | null>(null);
  useEffect(() => {
    let cancelled = false;
    api.getFearGreed().then((res) => {
      if (!cancelled && res.data) setFearGreedData(res.data);
    });
    return () => { cancelled = true; };
  }, []);

  // ── Real data: scanner modes → confluence floor for STEALTH (production) ─
  // CLAUDE.md §15 hard boundary: this is display-only. Never write back.
  const [stealthMode, setStealthMode] = useState<ScannerMode | null>(null);
  useEffect(() => {
    let cancelled = false;
    api.getScannerModes().then((res) => {
      if (!cancelled && res.data) {
        const stealth = res.data.modes.find((m) => m.name?.toLowerCase() === 'stealth');
        if (stealth) setStealthMode(stealth);
      }
    });
    return () => { cancelled = true; };
  }, []);

  // ── Real data: BTC cycle context → macro veto state ─────────────────────
  const [btcCycle, setBtcCycle] = useState<BTCCycleContextData | null>(null);
  useEffect(() => {
    let cancelled = false;
    api.getBTCCycleContext().then((res) => {
      if (!cancelled && res.data?.data) setBtcCycle(res.data.data);
    });
    return () => { cancelled = true; };
  }, []);

  const btcDom = regime.btcDominance ?? 54.32;
  const usdtDom = regime.usdtDominance ?? 4.12;
  const btcDomReal = regime.btcDominance != null;
  const usdtDomReal = regime.usdtDominance != null;
  const fearGreed = fearGreedData?.value ?? 64;
  const fearGreedReal = fearGreedData != null;

  // Funding table: real rows when loaded, fall back to FUNDING_SEED
  const activeFundingRows = fundingRows ?? FUNDING_SEED.map((s) => ({
    symbol: s.sym + '/USDT',
    mark_price: s.mark,
    price_change_pct: s.change24,
    funding_rate: s.fund,
    next_funding_ts: null,
    open_interest: null,
    open_interest_usd: s.oi,
    error: null,
  }));
  const fundingReal = fundingRows != null;
  const overheated = activeFundingRows.filter((r) => (r.funding_rate ?? 0) > 0.0002).length;

  const totalLongLiq = LIQ_SEED.reduce((a, l) => a + l.longs, 0);
  const totalShortLiq = LIQ_SEED.reduce((a, l) => a + l.shorts, 0);
  const highNews = NEWS_SEED.filter((n) => n.pri === 'HIGH').length;

  // BTC + ETH live prices from funding rows
  const btcRow = fundingRows?.find((r) => r.symbol === 'BTC/USDT');
  const ethRow = fundingRows?.find((r) => r.symbol === 'ETH/USDT');

  const visibilityChipKind: 'green' | 'amber' | 'red' =
    regime.visibility === 'HIGH' ? 'green' : regime.visibility === 'MEDIUM' ? 'amber' : 'red';

  return (
    <div className="page">
      <PageHead
        icon={
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="9" stroke="var(--blue)" strokeWidth="1.5" />
            <path
              d="M12 3 v18 M3 12 h18"
              stroke="var(--blue)"
              strokeWidth="1.1"
              strokeOpacity=".5"
            />
            <ellipse
              cx="12"
              cy="12"
              rx="9"
              ry="4"
              stroke="var(--blue)"
              strokeWidth="1.1"
              strokeOpacity=".7"
            />
            <circle cx="12" cy="12" r="2" fill="var(--blue)" />
          </svg>
        }
        title="Intel"
        subtitle="macro regime · funding · liquidations · catalysts"
        badges={
          <>
            <Chip kind="cyan">REGIME · {regime.regimeLabel}</Chip>
            <Chip kind={visibilityChipKind}>VIS · {regime.visibility}</Chip>
            <Chip>
              UPDATED{' '}
              {now.toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
              })}
            </Chip>
          </>
        }
      />

      {/* Macro ticker strip — BTC/ETH real via /api/market/funding;
          DXY/10Y/GOLD/VIX stay synthetic (no free TradFi source). */}
      <div style={{ marginBottom: 18 }}>
        <MacroTicker
          values={[
            {
              label: 'BTC',
              value: btcRow?.mark_price != null ? `$${fmtPrice(btcRow.mark_price)}` : '$—',
              delta: btcRow?.price_change_pct ?? null,
              color: 'var(--fg)',
              synthetic: !fundingReal,
            },
            {
              label: 'ETH',
              value: ethRow?.mark_price != null ? `$${fmtPrice(ethRow.mark_price)}` : '$—',
              delta: ethRow?.price_change_pct ?? null,
              color: 'var(--fg)',
              synthetic: !fundingReal,
            },
            {
              label: 'DXY',
              value: '103.41',
              delta: -0.18,
              color: 'var(--blue)',
              synthetic: true,
            },
            {
              label: '10Y',
              value: '4.184%',
              delta: -0.06,
              color: 'var(--blue)',
              synthetic: true,
            },
            {
              label: 'GOLD',
              value: '$2,408',
              delta: 0.22,
              color: 'var(--amber)',
              synthetic: true,
            },
            {
              label: 'VIX',
              value: '14.32',
              delta: -0.81,
              color: 'var(--green-soft)',
              synthetic: true,
            },
          ]}
        />
        {!fundingReal && (
          <div
            className="mono"
            style={{
              marginTop: 6,
              fontSize: 9,
              color: 'var(--amber)',
              letterSpacing: '.18em',
              textTransform: 'uppercase',
            }}
          >
            ◌ btc/eth loading · dxy/10y/gold/vix synthetic pending tradfi feed
          </div>
        )}
        {fundingReal && (
          <div
            className="mono"
            style={{
              marginTop: 6,
              fontSize: 9,
              color: 'var(--fg-4)',
              letterSpacing: '.18em',
              textTransform: 'uppercase',
            }}
          >
            ● btc/eth live · ◌ dxy/10y/gold/vix synthetic pending tradfi feed
          </div>
        )}
      </div>

      {/* Regime command center */}
      <section className="panel panel-accent" style={{ marginBottom: 18 }}>
        <Reticle />
        <div className="corner-tag tl">// MACRO-COMMAND</div>
        <div className="corner-tag tr">REGIME ENGINE</div>
        <div style={{ padding: '22px 22px 18px' }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1.2fr 1fr',
              gap: 24,
            }}
          >
            <div>
              <div
                className="mono"
                style={{
                  fontSize: 10,
                  color: 'var(--fg-4)',
                  letterSpacing: '.20em',
                  textTransform: 'uppercase',
                  marginBottom: 10,
                }}
              >
                // DOMINANCE & SENTIMENT
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 14 }}>
                <DominanceDial
                  value={btcDom}
                  label="BTC.D"
                  color="var(--amber-2)"
                  range={[40, 70]}
                  sub={
                    btcDomReal
                      ? btcDom > 54
                        ? 'consolidating'
                        : 'rotating'
                      : '(awaiting feed)'
                  }
                />
                <DominanceDial
                  value={usdtDom}
                  label="USDT.D"
                  color="var(--green-soft)"
                  range={[3, 8]}
                  sub={
                    usdtDomReal
                      ? usdtDom > 5
                        ? 'risk-off'
                        : 'risk-on'
                      : '(awaiting feed)'
                  }
                />
                <DominanceDial
                  value={fearGreed}
                  label="FEAR · GREED"
                  color={
                    fearGreed > 70
                      ? '#22c55e'
                      : fearGreed > 55
                        ? '#fbbf24'
                        : fearGreed > 30
                          ? '#f59e0b'
                          : '#f87171'
                  }
                  range={[0, 100]}
                  sub={
                    fearGreedReal
                      ? (fearGreedData?.classification ?? '—').toLowerCase()
                      : '(loading)'
                  }
                />
              </div>
            </div>
            <div>
              <div
                className="mono"
                style={{
                  fontSize: 10,
                  color: 'var(--fg-4)',
                  letterSpacing: '.20em',
                  textTransform: 'uppercase',
                  marginBottom: 10,
                }}
              >
                // REGIME CLASSIFIER
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <RegimeTape
                  score={regime.trendScore ?? 50}
                  label="Trend Strength"
                  color={
                    (regime.trendScore ?? 0) >= 55
                      ? 'var(--green-soft)'
                      : (regime.trendScore ?? 0) >= 30
                        ? 'var(--amber)'
                        : 'var(--red-2)'
                  }
                  ranges={[
                    { label: 'CHOP', min: 0, max: 30, color: '#f87171' },
                    { label: 'WEAK', min: 30, max: 55, color: '#fbbf24' },
                    { label: 'TREND', min: 55, max: 80, color: '#22c55e' },
                    { label: 'STRONG', min: 80, max: 100, color: '#00ffaa' },
                  ]}
                />
                <RegimeTape
                  score={regime.volatilityScore ?? 50}
                  label="Volatility (ATR%)"
                  color={
                    (regime.volatilityScore ?? 0) >= 85
                      ? 'var(--red-2)'
                      : (regime.volatilityScore ?? 0) >= 60
                        ? 'var(--amber)'
                        : (regime.volatilityScore ?? 0) >= 30
                          ? 'var(--green-soft)'
                          : 'var(--blue)'
                  }
                  ranges={[
                    { label: 'LOW', min: 0, max: 30, color: '#60a5fa' },
                    { label: 'NORM', min: 30, max: 60, color: '#22c55e' },
                    { label: 'HIGH', min: 60, max: 85, color: '#fbbf24' },
                    { label: 'EXT', min: 85, max: 100, color: '#f87171' },
                  ]}
                />
                <RegimeTape
                  score={regime.riskScore ?? 50}
                  label="Risk Appetite"
                  color={
                    (regime.riskScore ?? 0) >= 55
                      ? 'var(--green-soft)'
                      : (regime.riskScore ?? 0) >= 35
                        ? 'var(--amber)'
                        : 'var(--red-2)'
                  }
                  ranges={[
                    { label: 'OFF', min: 0, max: 35, color: '#f87171' },
                    { label: 'NEUT', min: 35, max: 55, color: '#fbbf24' },
                    { label: 'ON', min: 55, max: 80, color: '#22c55e' },
                    { label: 'EUPH', min: 80, max: 100, color: '#00ffaa' },
                  ]}
                />
                <RegimeTape
                  score={regime.derivativesScore ?? 50}
                  label="Derivatives"
                  color={
                    (regime.derivativesScore ?? 0) >= 85
                      ? 'var(--amber)'
                      : (regime.derivativesScore ?? 0) >= 65
                        ? 'var(--green-soft)'
                        : (regime.derivativesScore ?? 0) >= 35
                          ? 'var(--blue)'
                          : 'var(--red-2)'
                  }
                  ranges={[
                    { label: 'BEAR', min: 0, max: 35, color: '#f87171' },
                    { label: 'BAL', min: 35, max: 65, color: '#60a5fa' },
                    { label: 'BULL', min: 65, max: 85, color: '#22c55e' },
                    { label: 'EUPH', min: 85, max: 100, color: '#fbbf24' },
                  ]}
                />
              </div>
              {regime.trendScore == null && (
                <div
                  className="mono"
                  style={{
                    marginTop: 10,
                    fontSize: 9,
                    color: 'var(--amber)',
                    letterSpacing: '.18em',
                    textTransform: 'uppercase',
                  }}
                >
                  ◌ regime tape awaiting backend feed
                </div>
              )}
            </div>
          </div>

          <div
            style={{
              marginTop: 18,
              paddingTop: 14,
              borderTop: '1px solid var(--border-soft)',
            }}
          >
            <div
              className="mono"
              style={{
                fontSize: 10,
                color: 'var(--fg-4)',
                letterSpacing: '.20em',
                textTransform: 'uppercase',
                marginBottom: 10,
              }}
            >
              // SESSION CLOCK · LIVE
            </div>
            <SessionStrip now={now} />
            <KillZoneStrip />
          </div>
        </div>
      </section>

      {/* Main two-column grid */}
      <div className="intel-grid">
        <div className="intel-col">
          <section className="panel">
            <SectionHead
              title="Funding & Open Interest"
              right={
                <>
                  {overheated > 0 && <Chip kind="amber">⚠ {overheated} OVERHEATED</Chip>}
                  <Chip>{activeFundingRows.length} PERPS</Chip>
                  {!fundingReal && <Chip kind="amber">◌ SYNTHETIC</Chip>}
                </>
              }
            />
            <div style={{ padding: '10px 18px 14px' }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '70px 100px 1fr 90px',
                  gap: 8,
                  padding: '4px 4px 8px',
                  borderBottom: '1px solid var(--border-soft)',
                  marginBottom: 6,
                }}
              >
                <span
                  className="mono"
                  style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.18em' }}
                >
                  SYM
                </span>
                <span
                  className="mono"
                  style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.18em' }}
                >
                  MARK · 24H
                </span>
                <span
                  className="mono"
                  style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.18em' }}
                >
                  FUNDING (8H)
                </span>
                <span
                  className="mono"
                  style={{
                    fontSize: 9,
                    color: 'var(--fg-4)',
                    letterSpacing: '.18em',
                    textAlign: 'right',
                  }}
                >
                  OI (USD)
                </span>
              </div>
              {activeFundingRows.map((r) => (
                <FundingRowItem key={r.symbol} row={r} />
              ))}
            </div>
          </section>

          <section className="panel">
            <SectionHead
              title="Liquidation Heatmap"
              right={
                <>
                  <Chip kind="red">L · {(totalLongLiq / 1e6).toFixed(1)}M</Chip>
                  <Chip kind="green">S · {(totalShortLiq / 1e6).toFixed(1)}M</Chip>
                  <Chip>4H WINDOW</Chip>
                  <Chip kind="amber">◌ SYNTHETIC</Chip>
                </>
              }
            />
            <div style={{ padding: '4px 18px 14px' }}>
              <LiqHeatmap />
            </div>
          </section>
        </div>

        <div className="intel-col">
          <section className="panel">
            <Reticle />
            <SectionHead
              title="Catalyst Wire"
              right={
                <>
                  <Chip kind="red">{highNews} HIGH</Chip>
                  <Chip kind="amber">◌ SYNTHETIC</Chip>
                </>
              }
            />
            <div
              style={{
                padding: '12px 18px',
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
                maxHeight: 420,
                overflowY: 'auto',
              }}
            >
              {NEWS_SEED.map((n) => (
                <NewsItem key={n.id} item={n} />
              ))}
            </div>
          </section>

          <section className="panel">
            <SectionHead
              title="AI Analyst · Regime Read"
              right={
                <>
                  <Chip kind="cyan">CONF · 71</Chip>
                  <Chip kind="amber">◌ SYNTHETIC</Chip>
                </>
              }
            />
            <AICommentary />
          </section>

          <section className="panel">
            <SectionHead
              title="Position · Bias Map"
              right={<Chip kind="cyan">5 SLOTS</Chip>}
            />
            <div
              style={{
                padding: '14px 18px',
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 10,
              }}
            >
              <MacroScoreTile />
              <div className="metric-tile">
                <div className="metric-label">Confluence Floor</div>
                <div className="metric-value">
                  {stealthMode != null
                    ? `≥ ${stealthMode.min_confluence_score.toFixed(1)}`
                    : '—'}
                </div>
                <div className="metric-sub">
                  {stealthMode != null ? 'STEALTH · production mode' : '(awaiting feed)'}
                </div>
              </div>
              <div className="metric-tile">
                <div className="metric-label">Active Setups</div>
                <div className="metric-value">OB · FVG · BOS · SWEEP</div>
                <div className="metric-sub">SMC primitives · all modes</div>
              </div>
              <div className="metric-tile">
                <div className="metric-label">BTC Veto</div>
                {btcCycle != null ? (
                  (() => {
                    const bias = btcCycle.overall?.macro_bias;
                    if (bias === 'BULLISH') {
                      return (
                        <>
                          <div
                            className="metric-value"
                            style={{ color: 'var(--green-soft)' }}
                          >
                            CLEAR
                          </div>
                          <div className="metric-sub">macro tailwind · longs unblocked</div>
                        </>
                      );
                    }
                    if (bias === 'BEARISH') {
                      return (
                        <>
                          <div className="metric-value" style={{ color: 'var(--red-2)' }}>
                            ACTIVE
                          </div>
                          <div className="metric-sub">macro headwind · longs vetoed</div>
                        </>
                      );
                    }
                    return (
                      <>
                        <div className="metric-value" style={{ color: 'var(--amber)' }}>
                          WATCH
                        </div>
                        <div className="metric-sub">macro mixed · standard rules</div>
                      </>
                    );
                  })()
                ) : (
                  <>
                    <div className="metric-value" style={{ color: 'var(--fg-3)' }}>
                      —
                    </div>
                    <div className="metric-sub">(awaiting feed)</div>
                  </>
                )}
              </div>
            </div>
          </section>
        </div>
      </div>

      <FooterStatus latency={38} />

      <style>{`
        .intel-grid{display:grid;grid-template-columns:1.1fr 1fr;gap:18px;align-items:flex-start}
        .intel-col{display:flex;flex-direction:column;gap:18px}
        @media (max-width:1100px){.intel-grid{grid-template-columns:1fr}}
        .metric-tile{padding:14px;border:1px solid var(--border-soft);border-radius:8px;background:rgba(0,0,0,.3)}
        .metric-label{font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--fg-4);letter-spacing:.18em;text-transform:uppercase;margin-bottom:6px}
        .metric-value{font-family:'Share Tech Mono',monospace;font-size:18px;font-weight:700;color:var(--fg);letter-spacing:.04em}
        .metric-sub{font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--fg-4);letter-spacing:.12em;margin-top:4px}
      `}</style>
    </div>
  );
}

export default Intel;
