import { Chip } from '@/components/hud';
import { formatAccountMoney } from '@/services/accounting';
import type { ActiveMode } from '@/services/activeSession';
import type { CompletedLiveTrade, LivePosition, LiveTradingStatus } from '@/services/liveTradingService';
import { useMemo } from 'react';
// ─── Formatters ─────────────────────────────────────────────────────────
export function fmtDuration(seconds: number): string {
    if (!Number.isFinite(seconds) || seconds < 0)
        return '—';
    if (seconds < 60)
        return `${Math.round(seconds)}s`;
    if (seconds < 3600) {
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m}m ${s}s`;
    }
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
}
export function fmtCurrency(v: number | null | undefined, decimals = 2): string {
    return formatAccountMoney(v, decimals);
}
export function fmtPct(v: number | null | undefined, decimals = 2): string {
    if (v == null || !Number.isFinite(v))
        return '—';
    return `${v >= 0 ? '+' : ''}${v.toFixed(decimals)}%`;
}
// R-multiple = current PnL / planned risk. SMC traders think in R, not %.
export function fmtR(pnl: number, riskPnl: number | undefined): string {
    if (!Number.isFinite(pnl) || !riskPnl || !Number.isFinite(riskPnl))
        return '—';
    const r = pnl / Math.abs(riskPnl);
    if (!Number.isFinite(r))
        return '—';
    return `${r >= 0 ? '+' : ''}${r.toFixed(2)}R`;
}
// Shared column template — used by both header + PositionRow so widths stay locked.
export const OPEN_POS_COLS = '90px 70px 1fr 1fr 1fr 1fr 1.2fr 64px';
export const PENDING_ORDER_COLS = '90px 70px 1fr 1fr 90px';
// ─── Equity Sparkline ──────────────────────────────────────────────────
export function EquitySparkline({ trades, initialBalance, }: {
    trades: CompletedLiveTrade[];
    initialBalance: number;
}) {
    const points = useMemo(() => {
        if (!trades || trades.length === 0)
            return [];
        const sorted = [...trades].reverse();
        let equity = initialBalance;
        const pts = [{ x: 0, y: equity }];
        sorted.forEach((t, i) => {
            equity += t.pnl;
            pts.push({ x: i + 1, y: equity });
        });
        return pts;
    }, [trades, initialBalance]);
    if (points.length < 2) {
        return (<div className="mono" style={{
                height: 64,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 10,
                color: 'var(--fg-4)',
                letterSpacing: '.18em',
                textTransform: 'uppercase',
            }}>
        — awaiting trades —
      </div>);
    }
    const minY = Math.min(...points.map((p) => p.y));
    const maxY = Math.max(...points.map((p) => p.y));
    const rangeY = maxY - minY || 1;
    const w = 280;
    const h = 56;
    const pad = 2;
    const pathD = points
        .map((p, i) => {
        const x = pad + (p.x / (points.length - 1)) * (w - 2 * pad);
        const y = h - pad - ((p.y - minY) / rangeY) * (h - 2 * pad);
        return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
        .join(' ');
    const lastPt = points[points.length - 1];
    const isUp = lastPt.y >= initialBalance;
    const strokeColor = isUp ? '#34d399' : '#f87171';
    const fillGradId = 'lv-eq-grad';
    const lastPtX = pad + (lastPt.x / (points.length - 1)) * (w - 2 * pad);
    const lastPtY = h - pad - ((lastPt.y - minY) / rangeY) * (h - 2 * pad);
    const areaD = `${pathD} L ${lastPtX.toFixed(1)} ${h} L ${pad.toFixed(1)} ${h} Z`;
    return (<svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 64 }}>
      <defs>
        <linearGradient id={fillGradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={strokeColor} stopOpacity="0.18"/>
          <stop offset="100%" stopColor={strokeColor} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <path d={areaD} fill={`url(#${fillGradId})`}/>
      <path d={pathD} fill="none" stroke={strokeColor} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx={lastPtX} cy={lastPtY} r="3" fill={strokeColor}/>
    </svg>);
}
// ─── Metric Tile ───────────────────────────────────────────────────────
export function MetricTile({ label, value, sub, accent, }: {
    label: string;
    value: string;
    sub?: string;
    accent?: 'green' | 'red' | 'amber' | 'blue';
}) {
    const valueColor = accent === 'green'
        ? 'var(--green)'
        : accent === 'red'
            ? 'var(--red)'
            : accent === 'amber'
                ? 'var(--amber)'
                : accent === 'blue'
                    ? 'var(--blue)'
                    : 'var(--fg)';
    return (<div style={{
            padding: '12px 14px',
            border: '1px solid var(--border-soft)',
            borderRadius: 10,
            background: 'rgba(0,0,0,.35)',
        }}>
      <div className="mono" style={{
            fontSize: 9,
            color: 'var(--fg-4)',
            letterSpacing: '.18em',
            textTransform: 'uppercase',
            marginBottom: 8,
        }}>
        {label}
      </div>
      <div className="mono" style={{
            fontSize: 22,
            fontWeight: 800,
            color: valueColor,
            letterSpacing: '-0.01em',
            lineHeight: 1,
            marginBottom: 4,
        }}>
        {value}
      </div>
      {sub && (<div className="mono" style={{
                fontSize: 10,
                color: 'var(--fg-4)',
            }}>
          {sub}
        </div>)}
    </div>);
}
// ─── Position Row ──────────────────────────────────────────────────────
export function PositionRow({ position, onClick, }: {
    position: LivePosition;
    onClick?: () => void;
}) {
    const isLong = position.direction === 'LONG';
    const isProfit = position.unrealized_pnl >= 0;
    // TP display: prefer tp_final (close-everything level), fall back to tp1, then '—'.
    const tp = position.tp_final ?? position.tp1 ?? null;
    return (<div role={onClick ? 'button' : undefined} tabIndex={onClick ? 0 : undefined} onClick={onClick} onKeyDown={onClick
            ? (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onClick();
                }
            }
            : undefined} aria-label={onClick ? `Open detail for ${position.symbol}` : undefined} style={{
            display: 'grid',
            gridTemplateColumns: OPEN_POS_COLS,
            gap: 10,
            padding: '10px 12px',
            borderTop: '1px solid var(--border-soft)',
            alignItems: 'center',
            cursor: onClick ? 'pointer' : 'default',
            transition: 'background-color .12s ease',
        }} onMouseEnter={onClick
            ? (e) => {
                (e.currentTarget as HTMLDivElement).style.backgroundColor =
                    'rgba(255,255,255,.03)';
            }
            : undefined} onMouseLeave={onClick
            ? (e) => {
                (e.currentTarget as HTMLDivElement).style.backgroundColor = '';
            }
            : undefined}>
      <span className="mono" style={{ fontWeight: 700 }}>
        {position.symbol}
      </span>
      <Chip kind={isLong ? 'green' : 'red'}>{isLong ? 'LONG' : 'SHORT'}</Chip>
      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-2)' }}>
        {position.entry_price}
      </span>
      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-2)' }}>
        {position.current_price}
      </span>
      <span className="mono" style={{ fontSize: 11, color: 'var(--red-2)' }}>
        {position.stop_loss}
      </span>
      <span className="mono" style={{ fontSize: 11, color: 'var(--green-soft)' }}>
        {tp != null ? tp : '—'}
      </span>
      <span className="mono" style={{
            fontWeight: 700,
            color: isProfit ? 'var(--green)' : 'var(--red)',
            textAlign: 'right',
        }}>
        {fmtCurrency(position.unrealized_pnl)}
      </span>
      <span className="mono" style={{
            fontWeight: 700,
            color: isProfit ? 'var(--green)' : 'var(--red)',
            textAlign: 'right',
            fontSize: 11,
        }}>
        {fmtR(position.unrealized_pnl, position.risk_pnl)}
      </span>
    </div>);
}
// ─── Pending Order Row ─────────────────────────────────────────────────
// Renders a single unfilled limit order from status.pending_orders.
// Shape: { order_id, symbol, direction, limit_price, quantity, status }.
// No timestamp on the backend payload yet, so no age column.
export function PendingOrderRow({ order, onClick, }: {
    order: NonNullable<LiveTradingStatus['pending_orders']>[number];
    onClick?: () => void;
}) {
    const isLong = order.direction === 'LONG';
    const isPartial = order.status === 'PARTIALLY_FILLED';
    return (<div role={onClick ? 'button' : undefined} tabIndex={onClick ? 0 : undefined} onClick={onClick} onKeyDown={onClick
            ? (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onClick();
                }
            }
            : undefined} aria-label={onClick ? `Open detail for pending ${order.symbol} order` : undefined} style={{
            display: 'grid',
            gridTemplateColumns: PENDING_ORDER_COLS,
            gap: 10,
            padding: '10px 12px',
            borderTop: '1px solid var(--border-soft)',
            alignItems: 'center',
            cursor: onClick ? 'pointer' : 'default',
            transition: 'background-color .12s ease',
        }} onMouseEnter={onClick
            ? (e) => {
                (e.currentTarget as HTMLDivElement).style.backgroundColor =
                    'rgba(255,255,255,.03)';
            }
            : undefined} onMouseLeave={onClick
            ? (e) => {
                (e.currentTarget as HTMLDivElement).style.backgroundColor = '';
            }
            : undefined}>
      <span className="mono" style={{ fontWeight: 700 }}>
        {order.symbol}
      </span>
      <Chip kind={isLong ? 'green' : 'red'}>{isLong ? 'LONG' : 'SHORT'}</Chip>
      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-2)' }}>
        {order.limit_price}
      </span>
      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-2)' }}>
        {order.quantity}
      </span>
      <span style={{ textAlign: 'right' }}>
        <Chip kind={isPartial ? 'amber' : 'blue'}>{isPartial ? '◐ PARTIAL' : '○ OPEN'}</Chip>
      </span>
    </div>);
}
// ─── Mode Pill ─────────────────────────────────────────────────────────
// Accepts the unified ActiveMode union from activeSession.ts. Paper is a
// distinct mode from testnet/dry_run even though all three are non-real-
// money — paper is the operator's primary practice surface, testnet is
// for exchange-flow validation, dry_run is for offline replay.
export function ModePill({ mode }: {
    mode: ActiveMode;
}) {
    if (mode === 'live')
        return <Chip kind="red">● LIVE · REAL MONEY</Chip>;
    if (mode === 'paper')
        return <Chip kind="amber">● PAPER</Chip>;
    if (mode === 'testnet')
        return <Chip kind="amber">● TESTNET</Chip>;
    if (mode === 'dry_run')
        return <Chip kind="blue">● DRY RUN</Chip>;
    return <Chip>● IDLE</Chip>;
}
// ─── Status Pill ───────────────────────────────────────────────────────
// Status union covers both services' state machines:
//   live: idle / running / stopped / error / kill_switched
//   paper: idle / running / stopped / error / paused
export type SessionStatusValue = 'idle' | 'running' | 'stopped' | 'error' | 'kill_switched' | 'starting' | 'stopping' | 'recovering' | 'paused';
export function StatusPill({ status }: {
    status: SessionStatusValue;
}) {
    if (status === 'starting')
        return <Chip kind="amber">● VERIFYING ACCOUNT</Chip>;
    if (status === 'stopping')
        return <Chip kind="amber">● STOPPING</Chip>;
    if (status === 'recovering')
        return <Chip kind="red">● RECOVERY REQUIRED</Chip>;
    if (status === 'running')
        return <Chip kind="green">● RUNNING</Chip>;
    if (status === 'kill_switched')
        return <Chip kind="red">● KILL-SWITCHED</Chip>;
    if (status === 'error')
        return <Chip kind="red">● ERROR</Chip>;
    if (status === 'stopped')
        return <Chip kind="amber">● STOPPED</Chip>;
    if (status === 'paused')
        return <Chip kind="amber">● PAUSED</Chip>;
    return <Chip>● IDLE</Chip>;
}
// ─── Main Component ────────────────────────────────────────────────────
