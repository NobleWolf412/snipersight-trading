import { fmtMoney } from '@/components/hud';
import type { JournalTrade } from '@/services/tradeJournalService';
import { useMemo, type ReactNode } from 'react';
export function fmt(n: number, decimals = 2) {
    return n.toFixed(decimals);
}
export function fmtDate(iso: string | null) {
    if (!iso)
        return '—';
    const d = new Date(iso);
    return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}
export const EXIT_REASON_LABELS: Record<string, string> = {
    target: 'TARGET',
    stop_loss: 'STOP',
    stagnation: 'STALE',
    manual: 'MANUAL',
    max_hours: 'TIMEOUT',
};
// ─── StatTile ─────────────────────────────────────────────────────────────
export function StatTile({ label, value, sub, color, big, }: {
    label: string;
    value: ReactNode;
    sub?: ReactNode;
    color?: string;
    big?: boolean;
}) {
    return (<div className="metric-tile">
      <div className="metric-label">{label}</div>
      <div className="metric-value" style={{ color: color || 'var(--fg)', fontSize: big ? 22 : 16 }}>
        {value}
      </div>
      {sub && (<div className="metric-sub" style={{ color: color || 'var(--fg-3)', opacity: 0.7 }}>
          {sub}
        </div>)}
    </div>);
}
// ─── EquityCurve (equity + drawdown SVG) ──────────────────────────────────
export function EquityCurve({ equityCurve, initial, }: {
    equityCurve: {
        time: string;
        value: number;
    }[];
    initial: number;
}) {
    const W = 800;
    const H = 180;
    const padL = 4;
    const padR = 10;
    const padT = 10;
    const padB = 20;
    const { eqPts } = useMemo(() => {
        let peak = initial;
        const eqPts = equityCurve.map((p, i) => {
            const y = initial + p.value;
            peak = Math.max(peak, y);
            return { x: i + 1, y, dd: y - peak };
        });
        eqPts.unshift({ x: 0, y: initial, dd: 0 });
        return { eqPts };
    }, [equityCurve, initial]);
    if (eqPts.length < 2)
        return null;
    const minY = Math.min(...eqPts.map(p => p.y));
    const maxY = Math.max(...eqPts.map(p => p.y));
    const yRng = maxY - minY || 1;
    const last = eqPts[eqPts.length - 1];
    const isUp = last.y >= initial;
    const stroke = isUp ? 'var(--green-soft)' : 'var(--red-2)';
    const xOf = (i: number) => padL + (i / (eqPts.length - 1)) * (W - padL - padR);
    const yOf = (y: number) => padT + (1 - (y - minY) / yRng) * (H - padT - padB);
    const line = eqPts
        .map((p, i) => (i ? 'L' : 'M') + xOf(p.x).toFixed(1) + ' ' + yOf(p.y).toFixed(1))
        .join(' ');
    const area = line + ` L ${xOf(eqPts.length - 1).toFixed(1)} ${H - padB} L ${padL} ${H - padB} Z`;
    const minDD = Math.min(...eqPts.map(p => p.dd));
    const ddH = 60;
    const ddYof = (dd: number) => H + 8 + (-dd / Math.abs(minDD || 1)) * ddH;
    const ddPath = eqPts
        .map((p, i) => (i ? 'L' : 'M') + xOf(p.x).toFixed(1) + ' ' + ddYof(p.dd).toFixed(1))
        .join(' ');
    const ddArea = ddPath + ` L ${xOf(eqPts.length - 1).toFixed(1)} ${H + 8} L ${padL} ${H + 8} Z`;
    return (<svg viewBox={`0 0 ${W} ${H + 8 + ddH + 12}`} style={{ width: '100%', height: 'auto' }}>
      <defs>
        <linearGradient id="eqg-journal" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity=".25"/>
          <stop offset="100%" stopColor={stroke} stopOpacity="0"/>
        </linearGradient>
        <linearGradient id="ddg-journal" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--red-2)" stopOpacity=".05"/>
          <stop offset="100%" stopColor="var(--red-2)" stopOpacity=".25"/>
        </linearGradient>
      </defs>
      {[0, 0.25, 0.5, 0.75, 1].map(g => (<line key={g} x1={padL} x2={W - padR} y1={padT + g * (H - padT - padB)} y2={padT + g * (H - padT - padB)} stroke="rgba(255,255,255,.05)" strokeDasharray="2 3"/>))}
      <path d={area} fill="url(#eqg-journal)"/>
      <path d={line} stroke={stroke} strokeWidth={1.6} fill="none"/>
      <text x={padL + 4} y={padT + 10} fill="var(--fg-4)" fontSize="9" fontFamily="JetBrains Mono,monospace" letterSpacing=".18em">
        EQUITY
      </text>
      <text x={W - padR} y={padT + 10} fill={stroke} fontSize="11" fontFamily="JetBrains Mono,monospace" textAnchor="end" fontWeight={700}>
        {fmtMoney(last.y)}
      </text>
      <path d={ddArea} fill="url(#ddg-journal)"/>
      <path d={ddPath} stroke="var(--red-2)" strokeWidth={1.2} fill="none" opacity={0.8}/>
      <text x={padL + 4} y={H + 18} fill="var(--fg-4)" fontSize="9" fontFamily="JetBrains Mono,monospace" letterSpacing=".18em">
        DRAWDOWN
      </text>
      <text x={W - padR} y={H + 18} fill="var(--red-2)" fontSize="11" fontFamily="JetBrains Mono,monospace" textAnchor="end" fontWeight={700}>
        {fmtMoney(minDD)}
      </text>
    </svg>);
}
// ─── PnLCalendar ──────────────────────────────────────────────────────────
export function PnLCalendar({ trades }: {
    trades: JournalTrade[];
}) {
    const byDay = useMemo(() => {
        const map: Record<string, number> = {};
        trades.forEach(t => {
            const day = (t.exit_time ?? t.entry_time).slice(0, 10);
            map[day] = (map[day] ?? 0) + t.pnl;
        });
        return map;
    }, [trades]);
    const entries = Object.entries(byDay).sort();
    if (entries.length === 0) {
        return (<div style={{ fontSize: 11, color: 'var(--fg-4)', fontFamily: 'JetBrains Mono,monospace' }}>
        // no closed-trade days in window
      </div>);
    }
    const max = Math.max(...entries.map(([, v]) => Math.abs(v))) || 1;
    return (<div className="journal-calendar-grid">
      {entries.map(([d, v]) => {
            const intensity = Math.abs(v) / max;
            const bg = v >= 0
                ? `rgba(34,197,94,${0.15 + 0.55 * intensity})`
                : `rgba(248,113,113,${0.15 + 0.55 * intensity})`;
            const bd = v >= 0 ? `rgba(34,197,94,.5)` : `rgba(248,113,113,.5)`;
            return (<div key={d} style={{
                    background: bg,
                    border: `1px solid ${bd}`,
                    borderRadius: 4,
                    padding: '8px 6px',
                    textAlign: 'center',
                }}>
            <div className="mono" style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.1em' }}>
              {d.slice(5)}
            </div>
            <div className="mono" style={{
                    fontSize: 12,
                    fontWeight: 800,
                    color: v >= 0 ? 'var(--green-soft)' : 'var(--red-2)',
                    marginTop: 2,
                }}>
              {v >= 0 ? '+' : ''}
              {v.toFixed(0)}
            </div>
          </div>);
        })}
    </div>);
}
// ─── GroupBreakdown (per-symbol / per-type bars) ──────────────────────────
export type GroupRow = {
    label: string;
    trades: number;
    wins: number;
    pnl: number;
    win_rate: number;
};
export function GroupBreakdown({ rows }: {
    rows: GroupRow[];
}) {
    if (rows.length === 0) {
        return (<div style={{ fontSize: 11, color: 'var(--fg-4)', fontFamily: 'JetBrains Mono,monospace' }}>
        // no data
      </div>);
    }
    const max = Math.max(...rows.map(r => Math.abs(r.pnl))) || 1;
    return (<div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {rows.map(g => {
            const profit = g.pnl >= 0;
            const w = (Math.abs(g.pnl) / max) * 100;
            return (<div key={g.label} style={{
                    padding: '10px 12px',
                    border: '1px solid var(--border-soft)',
                    borderRadius: 8,
                    background: 'rgba(0,0,0,.3)',
                    position: 'relative',
                    overflow: 'hidden',
                }}>
            <div style={{
                    position: 'absolute',
                    top: 0,
                    bottom: 0,
                    left: 0,
                    width: w + '%',
                    background: profit ? 'rgba(34,197,94,.05)' : 'rgba(248,113,113,.05)',
                    borderRight: `1px solid ${profit ? 'rgba(34,197,94,.3)' : 'rgba(248,113,113,.3)'}`,
                }}/>
            <div style={{
                    position: 'relative',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: 6,
                }}>
              <span style={{
                    fontFamily: 'Share Tech Mono,monospace',
                    fontSize: 13,
                    letterSpacing: '.06em',
                }}>
                {g.label}
              </span>
              <span className="mono" style={{
                    fontSize: 13,
                    fontWeight: 800,
                    color: profit ? 'var(--green-soft)' : 'var(--red-2)',
                }}>
                {(profit ? '+' : '') + fmtMoney(g.pnl)}
              </span>
            </div>
            <div style={{
                    position: 'relative',
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontSize: 10,
                    fontFamily: 'JetBrains Mono,monospace',
                    color: 'var(--fg-4)',
                    letterSpacing: '.14em',
                }}>
              <span>{g.trades} TRADES</span>
              <span style={{
                    color: g.win_rate >= 60
                        ? 'var(--green-soft)'
                        : g.win_rate >= 40
                            ? 'var(--amber)'
                            : 'var(--red-2)',
                }}>
                WR {g.win_rate.toFixed(0)}%
              </span>
              <span>
                {g.wins}W / {g.trades - g.wins}L
              </span>
            </div>
          </div>);
        })}
    </div>);
}
