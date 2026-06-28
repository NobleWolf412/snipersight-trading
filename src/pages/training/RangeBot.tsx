/**
 * RangeBot — full paper-trading equivalent of the live bot
 *
 * Operator intent: "a page just like bot but for paper trading — this is
 * a simulated version of the bot. Including bot setup, but like for paper trading."
 *
 * Tabbed shell: #setup / #status — mirrors the live bot's /bot/setup + /bot/status
 * split, but in one page under /training/range.
 *
 * Setup tab:
 *   - Paper-specific config: initial_balance slider (not real money)
 *   - Same execution sliders as BotSetup: risk%, leverage, max positions,
 *     duration, scan interval, confluence threshold
 *   - Execution toggles: trailing stop, breakeven
 *   - Universe scope: majors/altcoins + size
 *   - Paper-specific: slippage_bps, fee_rate (simulated fill realism)
 *   - ARM button — starts paper bot + switches to #status tab
 *   - No preflight check, no kill-switch acknowledgment (simulated capital)
 *
 * Status tab:
 *   - PAPER MODE banner (always visible)
 *   - CycleHeartbeat strip
 *   - Command Center (glowing dot, uptime, STOP/RESET buttons, metric grid, config pills)
 *   - Equity Curve + Statistics (2-column)
 *   - Open Positions (6-column, direction-symmetric)
 *   - Activity Log (recent_activity — paper bot logs signals, fills, exits)
 *   - Exit Reasons + By-Trade-Type breakdown (2-column)
 *
 * §15 boundary:
 *   - ALL API calls go through paperTradingService (hits /api/paper-trading/*).
 *   - No shared code with liveTradingService; structurally incapable of
 *     dispatching live orders.
 *   - sniper_mode sourced from botConfig.sniperMode (read-only consumer).
 *
 * Direction-agnostic: LONG/SHORT positions rendered by identical code paths.
 * Chip color differs; logic is fully symmetric per CLAUDE.md §10 #3.
 *
 * StrictMode-safe: cancelled flag + setTimeout recursion.
 * Snapshot-ready: body[data-snapshot-ready="true"] after first poll.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Chip,
  CycleHeartbeat,
  FooterStatus,
  PageHead,
  PositionDetailModal,
  Reticle,
  SectionHead,
  type DetailSelection,
} from '@/components/hud';
import { useScanner } from '@/context/ScannerContext';
import {
  paperTradingService,
  type CompletedPaperTrade,
  type PaperPosition,
  type PaperTradingConfigRequest,
  type PaperTradingStatus,
} from '@/services/paperTradingService';
import { tradeJournalService, type JournalAggregate } from '@/services/tradeJournalService';

// ─── Constants ─────────────────────────────────────────────────────────
const FAST_POLL_MS = 2_000;
const SLOW_POLL_MS = 10_000;

// ─── Formatters ────────────────────────────────────────────────────────
function fmtDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}m ${s}s`;
  }
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function fmtCurrency(v: number | null | undefined, decimals = 2): string {
  if (v == null || !Number.isFinite(v)) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(v);
}

function fmtPct(v: number | null | undefined, sign = false): string {
  if (v == null || !Number.isFinite(v)) return '—';
  const prefix = sign && v > 0 ? '+' : '';
  return `${prefix}${v.toFixed(2)}%`;
}

// ─── PAPER MODE Banner ─────────────────────────────────────────────────
function PaperModeBanner() {
  return (
    <div
      role="banner"
      aria-label="paper mode disclosure"
      style={{
        background: 'var(--amber-bg)',
        border: '1px solid var(--amber-border)',
        borderRadius: 10,
        padding: '12px 16px',
        marginBottom: 14,
        display: 'flex',
        alignItems: 'center',
        gap: 14,
      }}
    >
      <span className="mono" style={{ fontSize: 13, color: 'var(--amber)', fontWeight: 800, letterSpacing: 2 }}>
        ◉ PAPER MODE
      </span>
      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-2)' }}>
        simulated capital · no real funds · same scanner + engine as live bot
      </span>
    </div>
  );
}

// ─── Shared setup primitives ───────────────────────────────────────────
function Slider({
  label,
  value,
  min,
  max,
  step,
  onChange,
  suffix,
  color,
  hint,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  suffix?: string;
  color?: string;
  hint?: string;
}) {
  return (
    <div
      style={{
        padding: '12px 14px',
        border: '1px solid var(--border-soft)',
        borderRadius: 6,
        background: 'rgba(0,0,0,.3)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span className="mono" style={{ fontSize: 10, color: 'var(--fg-3)', letterSpacing: '.16em', textTransform: 'uppercase' }}>
          {label}
        </span>
        <span className="mono" style={{ fontSize: 14, fontWeight: 800, color: color || 'var(--accent)' }}>
          {value}{suffix || ''}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(+e.target.value)}
        style={{ width: '100%' }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
        <span className="mono" style={{ fontSize: 8, color: 'var(--fg-4)' }}>{min}{suffix || ''}</span>
        <span className="mono" style={{ fontSize: 8, color: 'var(--fg-4)' }}>{max}{suffix || ''}</span>
      </div>
      {hint && (
        <div className="mono" style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.1em', marginTop: 6 }}>
          {hint}
        </div>
      )}
    </div>
  );
}

function Toggle({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
  hint?: string;
}) {
  return (
    <div
      onClick={() => onChange(!value)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 12px',
        border: value ? '1px solid rgba(34,211,238,.5)' : '1px solid var(--border-soft)',
        borderRadius: 6,
        background: value ? 'rgba(34,211,238,.06)' : 'rgba(0,0,0,.3)',
        cursor: 'pointer',
        transition: 'border-color .15s, background .15s',
      }}
    >
      <div
        style={{
          width: 36,
          height: 18,
          borderRadius: 9,
          background: value ? 'var(--accent)' : 'rgba(0,0,0,.6)',
          position: 'relative',
          flexShrink: 0,
          border: '1px solid var(--border-soft)',
          boxShadow: value ? '0 0 8px var(--accent)' : 'none',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: 1,
            left: value ? 19 : 1,
            width: 14,
            height: 14,
            borderRadius: '50%',
            background: value ? '#0a0c0e' : 'var(--fg-3)',
          }}
        />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: 'Share Tech Mono,monospace', fontSize: 12, letterSpacing: '.05em', color: 'var(--fg)' }}>
          {label}
        </div>
        {hint && (
          <div className="mono" style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.1em', marginTop: 2 }}>
            {hint}
          </div>
        )}
      </div>
      <span className="mono" style={{ fontSize: 9, color: value ? 'var(--green-soft)' : 'var(--fg-4)', letterSpacing: '.18em' }}>
        {value ? 'ENGAGED' : 'OFF'}
      </span>
    </div>
  );
}

function SectionPanel({
  num,
  title,
  desc,
  children,
}: {
  num: string;
  title: string;
  desc?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="panel" style={{ marginBottom: 14 }}>
      <div
        style={{
          padding: '14px 18px',
          borderBottom: '1px solid var(--border-soft)',
          background: 'rgba(0,0,0,.4)',
          display: 'flex',
          alignItems: 'center',
          gap: 14,
        }}
      >
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 32,
            height: 32,
            border: '1px solid var(--accent)',
            color: 'var(--accent)',
            fontFamily: 'JetBrains Mono,monospace',
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: '.08em',
            borderRadius: 3,
            boxShadow: '0 0 8px rgba(34,211,238,.2)',
          }}
        >
          {num}
        </span>
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: 'Share Tech Mono,monospace', fontSize: 15, letterSpacing: '.08em', color: 'var(--fg)', textTransform: 'uppercase' }}>
            {title}
          </div>
          {desc && (
            <div className="mono" style={{ fontSize: 10, color: 'var(--fg-4)', letterSpacing: '.1em', marginTop: 2 }}>
              {desc}
            </div>
          )}
        </div>
      </div>
      <div style={{ padding: '14px 18px' }}>{children}</div>
    </section>
  );
}

// ─── Metric Tile ───────────────────────────────────────────────────────
function MetricTile({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: 'green' | 'red' | 'amber' | 'blue' | 'cyan';
}) {
  const valueColor =
    accent === 'green' ? 'var(--green)'
      : accent === 'red' ? 'var(--red)'
        : accent === 'amber' ? 'var(--amber)'
          : accent === 'blue' ? 'var(--blue)'
            : accent === 'cyan' ? '#22d3ee'
              : 'var(--fg-1)';
  return (
    <div style={{ padding: '12px 14px', border: '1px solid var(--border-soft)', borderRadius: 10, background: 'rgba(0,0,0,.35)' }}>
      <div className="mono" style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.18em', textTransform: 'uppercase', marginBottom: 8 }}>
        {label}
      </div>
      <div className="mono" style={{ fontSize: 22, fontWeight: 800, color: valueColor, letterSpacing: '-0.01em', lineHeight: 1, marginBottom: sub ? 4 : 0 }}>
        {value}
      </div>
      {sub && <div className="mono" style={{ fontSize: 10, color: 'var(--fg-4)' }}>{sub}</div>}
    </div>
  );
}

// ─── Equity Sparkline ──────────────────────────────────────────────────
function EquitySparkline({ trades, initialBalance }: { trades: CompletedPaperTrade[]; initialBalance: number }) {
  const points = useMemo(() => {
    if (!trades || trades.length === 0) return [];
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
    return (
      <div className="mono" style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color: 'var(--fg-4)', letterSpacing: '.18em', textTransform: 'uppercase' }}>
        — awaiting trades —
      </div>
    );
  }

  const minY = Math.min(...points.map((p) => p.y));
  const maxY = Math.max(...points.map((p) => p.y));
  const rangeY = maxY - minY || 1;
  const w = 280; const h = 56; const pad = 2;

  const pathD = points.map((p, i) => {
    const x = pad + (p.x / (points.length - 1)) * (w - 2 * pad);
    const y = h - pad - ((p.y - minY) / rangeY) * (h - 2 * pad);
    return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(' ');

  const lastPt = points[points.length - 1];
  const isUp = lastPt.y >= initialBalance;
  const strokeColor = isUp ? '#34d399' : '#f87171';
  const fillGradId = 'rb-eq-grad';
  const lastPtX = pad + (lastPt.x / (points.length - 1)) * (w - 2 * pad);
  const lastPtY = h - pad - ((lastPt.y - minY) / rangeY) * (h - 2 * pad);
  const areaD = `${pathD} L ${lastPtX.toFixed(1)} ${h} L ${pad.toFixed(1)} ${h} Z`;

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 64 }}>
      <defs>
        <linearGradient id={fillGradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={strokeColor} stopOpacity="0.18" />
          <stop offset="100%" stopColor={strokeColor} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaD} fill={`url(#${fillGradId})`} />
      <path d={pathD} fill="none" stroke={strokeColor} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lastPtX} cy={lastPtY} r="3" fill={strokeColor} />
    </svg>
  );
}

// ─── Position Row (direction-symmetric) ───────────────────────────────
// Direction-agnostic: LONG/SHORT handled by identical code path.
// Chip kind (green vs red) and PnL color differ by direction, but the
// underlying render logic is fully symmetric — no `if LONG` branches.
// No __long/__short snapshot pair is needed; both directions are exercised
// in the `range_bot_running` fixture which contains one LONG + one SHORT
// position. This mirrors the UniversePanel exception pattern documented
// in tests/visual/states.ts L262-266 — direction-agnostic per CLAUDE.md §10 #3.
function PositionRow({ pos, onClick }: { pos: PaperPosition; onClick?: () => void }) {
  const isLong = pos.direction === 'LONG';
  const isProfit = pos.unrealized_pnl >= 0;
  return (
    <div
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
      aria-label={onClick ? `Open detail for ${pos.symbol}` : undefined}
      style={{
        display: 'grid',
        gridTemplateColumns: '90px 70px 1fr 1fr 1fr 1fr',
        gap: 10,
        padding: '10px 12px',
        borderTop: '1px solid var(--border-soft)',
        alignItems: 'center',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'background-color .12s ease',
      }}
      onMouseEnter={
        onClick
          ? (e) => {
              (e.currentTarget as HTMLDivElement).style.backgroundColor = 'rgba(255,255,255,.03)';
            }
          : undefined
      }
      onMouseLeave={
        onClick
          ? (e) => {
              (e.currentTarget as HTMLDivElement).style.backgroundColor = '';
            }
          : undefined
      }
    >
      <span className="mono" style={{ fontWeight: 700 }}>{pos.symbol}</span>
      <Chip kind={isLong ? 'green' : 'red'}>{isLong ? 'LONG' : 'SHORT'}</Chip>
      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-2)' }}>
        entry {pos.entry_price < 1 ? pos.entry_price.toFixed(4) : pos.entry_price.toFixed(2)}
      </span>
      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-2)' }}>
        mark {pos.current_price < 1 ? pos.current_price.toFixed(4) : pos.current_price.toFixed(2)}
      </span>
      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-2)' }}>
        sl {pos.stop_loss < 1 ? pos.stop_loss.toFixed(4) : pos.stop_loss.toFixed(2)}
      </span>
      <span className="mono" style={{ fontWeight: 700, color: isProfit ? 'var(--green)' : 'var(--red)', textAlign: 'right' }}>
        {fmtCurrency(pos.unrealized_pnl)} ({fmtPct(pos.unrealized_pnl_pct, true)})
      </span>
    </div>
  );
}

// ─── Exit Badge ─────────────────────────────────────────────────────────
const EXIT_BADGE_MAP: Record<string, { label: string; kind: 'green' | 'red' | 'cyan' | 'amber' }> = {
  // Real backend strings (position_manager.py / paper_trading_service.py)
  target:         { label: 'TARGET HIT', kind: 'green' },
  stop_loss:      { label: 'HARD SL',    kind: 'red'   },
  stagnation:     { label: 'STAGNATION', kind: 'amber' },
  max_hours_open: { label: 'TIMEOUT',    kind: 'amber' },
  manual:         { label: 'MANUAL',     kind: 'cyan'  },
  emergency:      { label: 'EMERGENCY',  kind: 'red'   },
  // Fixture aliases for snapshot tests
  target_hit:     { label: 'TARGET HIT', kind: 'green' },
  trailing_stop:  { label: 'TRAILING',   kind: 'cyan'  },
  timeout:        { label: 'TIMEOUT',    kind: 'amber' },
};
function ExitBadge({ reason }: { reason: string }) {
  const m = EXIT_BADGE_MAP[reason];
  return m
    ? <Chip kind={m.kind}>{m.label}</Chip>
    : <Chip>{reason.replace(/_/g, ' ').toUpperCase()}</Chip>;
}

// ─── MAE / MFE Meters ────────────────────────────────────────────────────
// max_favorable = MFE (positive % — how far price moved in your favour)
// max_adverse   = MAE (negative % — how far it moved against you)
// Scale: 10 % = full bar; values beyond pin at 100 %.
function MaeMfeBar({ mfe, mae }: { mfe: number; mae: number }) {
  const scale = 10;
  const mfePct = Math.min(100, (Math.abs(mfe) / scale) * 100);
  const maePct = Math.min(100, (Math.abs(mae) / scale) * 100);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className="mono" style={{ fontSize: 9, color: 'var(--fg-4)', width: 30, textAlign: 'right', letterSpacing: '.08em' }}>MFE</span>
        <div style={{ flex: 1, height: 4, background: 'rgba(0,0,0,.35)', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{ width: `${mfePct}%`, height: '100%', background: 'var(--green)', borderRadius: 2 }} />
        </div>
        <span className="mono" style={{ fontSize: 9, color: 'var(--green)', width: 44, textAlign: 'right' }}>+{mfe.toFixed(2)}%</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className="mono" style={{ fontSize: 9, color: 'var(--fg-4)', width: 30, textAlign: 'right', letterSpacing: '.08em' }}>MAE</span>
        <div style={{ flex: 1, height: 4, background: 'rgba(0,0,0,.35)', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{ width: `${maePct}%`, height: '100%', background: 'var(--red)', borderRadius: 2 }} />
        </div>
        <span className="mono" style={{ fontSize: 9, color: 'var(--red)', width: 44, textAlign: 'right' }}>{mae.toFixed(2)}%</span>
      </div>
    </div>
  );
}

// ─── Trade History Row (expandable autopsy) ──────────────────────────────
function TradeHistoryRow({ trade }: { trade: CompletedPaperTrade }) {
  const [open, setOpen] = useState(false);
  const isLong = trade.direction === 'LONG';
  const isWin  = trade.pnl >= 0;
  const durMin = trade.entry_time && trade.exit_time
    ? Math.round((new Date(trade.exit_time).getTime() - new Date(trade.entry_time).getTime()) / 60000)
    : null;
  const fmtP = (p: number) => p < 1 ? p.toFixed(4) : p.toFixed(2);
  return (
    <div style={{ borderBottom: '1px solid var(--border-soft)', background: open ? 'rgba(0,0,0,.15)' : 'transparent', transition: 'background .15s' }}>
      {/* Collapsed summary row */}
      <div
        onClick={() => setOpen((s) => !s)}
        style={{ display: 'grid', gridTemplateColumns: '90px 64px 1fr 1fr auto', gap: 10, padding: '10px 12px', cursor: 'pointer', alignItems: 'center' }}
        title="Click to expand autopsy"
      >
        <span className="mono" style={{ fontWeight: 700 }}>{trade.symbol}</span>
        <Chip kind={isLong ? 'green' : 'red'}>{isLong ? 'LONG' : 'SHORT'}</Chip>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span className="mono" style={{ fontSize: 10, color: 'var(--fg-3)' }}>
            {fmtP(trade.entry_price)}<span style={{ color: 'var(--fg-4)' }}> → </span>{fmtP(trade.exit_price)}
          </span>
          {trade.trade_type && (
            <span className="mono" style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.1em' }}>{trade.trade_type.toUpperCase()}</span>
          )}
        </div>
        <span className="mono" style={{ fontWeight: 700, color: isWin ? 'var(--green)' : 'var(--red)' }}>
          {isWin ? '+' : ''}{fmtCurrency(trade.pnl)} ({fmtPct(trade.pnl_pct, true)})
        </span>
        <ExitBadge reason={trade.exit_reason} />
      </div>

      {/* Expanded autopsy panel */}
      {open && (
        <div style={{ padding: '12px 14px 14px', borderTop: '1px solid var(--border-soft)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }}>
          <div>
            <div className="mono" style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.14em', marginBottom: 8, textTransform: 'uppercase' }}>
              excursion analysis
            </div>
            <MaeMfeBar mfe={trade.max_favorable} mae={trade.max_adverse} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            {[
              { label: 'CONFIDENCE', val: trade.confidence_score != null ? `${trade.confidence_score.toFixed(1)}` : '—' },
              { label: 'DURATION',   val: durMin != null ? `${durMin}m` : '—' },
              { label: 'TARGETS',    val: trade.targets_hit?.length > 0 ? trade.targets_hit.map((t) => `T${t}`).join(', ') : 'none' },
              { label: 'ENTERED',    val: trade.entry_time ? new Date(trade.entry_time).toUTCString().slice(17, 22) + 'Z' : '—' },
            ].map(({ label, val }) => (
              <div key={label}>
                <div className="mono" style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.14em', marginBottom: 3 }}>{label}</div>
                <div className="mono" style={{ fontSize: 12, color: 'var(--fg-1)' }}>{val}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Activity row ──────────────────────────────────────────────────────
type ActivityEntry = { timestamp: string; event_type: string; data: any };

function ActivityRow({ entry, idx }: { entry: ActivityEntry; idx: number }) {
  const isExec = entry.event_type === 'trade_opened' || entry.event_type === 'signal_executed';
  const isExit = entry.event_type === 'trade_closed' || entry.event_type === 'position_closed';
  const isErr = entry.event_type === 'error';
  const color = isExec ? 'var(--green)' : isExit ? 'var(--amber)' : isErr ? 'var(--red)' : 'var(--fg-4)';
  const symbol = entry.data?.symbol ?? entry.data?.pair ?? '';
  const detail = entry.data?.reason ?? entry.data?.setup_type ?? entry.data?.exit_reason ?? entry.data?.message ?? entry.event_type.replace(/_/g, ' ');
  return (
    <div key={`act-${idx}`} className="mono" style={{ display: 'grid', gridTemplateColumns: '90px 1fr 100px', gap: 8, padding: '6px 8px', fontSize: 11, borderBottom: '1px solid var(--border-soft)' }}>
      <span style={{ fontWeight: 700 }}>{symbol || '—'}</span>
      <span style={{ color: 'var(--fg-3)' }}>{detail}</span>
      <span style={{ textAlign: 'right', color }}>{entry.event_type.replace(/_/g, ' ')}</span>
    </div>
  );
}

// ─── Setup Tab ─────────────────────────────────────────────────────────
interface PaperConfig {
  initial_balance: number;
  risk_per_trade: number;
  max_positions: number;
  leverage: number;
  duration_hours: number;
  scan_interval_minutes: number;
  min_confluence: number;
  trailing_stop: boolean;
  trailing_activation: number;
  breakeven_after_target: number;
  majors: boolean;
  altcoins: boolean;
  meme_mode: boolean;
  universe_size: number;
  slippage_bps: number;
  fee_rate: number;
  execution_mode: 'snap_taker' | 'rest_maker';
  macro_overlay_enabled: boolean;
}

const DEFAULT_SETUP: PaperConfig = {
  initial_balance: 10000,
  risk_per_trade: 2.0,
  max_positions: 3,
  leverage: 1,
  duration_hours: 24,
  scan_interval_minutes: 2,
  // 68 chosen to match the STRIKE mode min_confluence_score (scanner_modes.py
  // line ~45). STEALTH (live bot production mode) is 70; paper mode defaults
  // slightly lower so training sessions see more signals and provide richer
  // feedback data. This is a paper-only tuning choice — not a live gate change.
  min_confluence: 68,
  trailing_stop: true,
  trailing_activation: 1.5,
  breakeven_after_target: 1,
  majors: true,
  altcoins: false,
  meme_mode: false,
  universe_size: 20,
  slippage_bps: 5,
  fee_rate: 0.1,
  execution_mode: 'snap_taker',
  macro_overlay_enabled: true,
};

function SetupTab({
  sniperMode,
  onArm,
  working,
  armErr,
  decisionMode,
}: {
  sniperMode: string;
  onArm: (cfg: PaperConfig) => void;
  working: boolean;
  armErr: string | null;
  decisionMode?: string;
}) {
  // Heart-change: in thesis mode the structure thesis decides direction and the confluence score
  // is DEMOTED (no longer a go/no-go gate). Reflect that so the setup controls don't mislead.
  const thesis = decisionMode === 'thesis';
  const [cfg, setCfg] = useState<PaperConfig>(DEFAULT_SETUP);
  const set = useCallback(<K extends keyof PaperConfig>(key: K, val: PaperConfig[K]) => {
    setCfg((prev) => ({ ...prev, [key]: val }));
  }, []);

  return (
    <div>
      {/* Header strip: detection mode + paper-mode reminder */}
      <div
        style={{
          background: 'rgba(0,0,0,.4)',
          border: '1px solid rgba(34,211,238,.2)',
          borderRadius: 8,
          padding: '10px 14px',
          marginBottom: 14,
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          flexWrap: 'wrap',
        }}
      >
        <span className="mono" style={{ fontSize: 10, color: 'var(--fg-3)', letterSpacing: '.14em' }}>
          ◉ BOT MODE · <span style={{ color: '#22d3ee' }}>{sniperMode.toUpperCase()}</span> · detection set in Scanner · this page configures paper execution only
        </span>
        {thesis && <Chip kind="green">DECISION · THESIS (structure-led)</Chip>}
        <Chip kind="cyan">PAPER ONLY — NO REAL FUNDS</Chip>
      </div>

      {armErr && (
        <div style={{ margin: '0 0 14px', padding: '10px 14px', border: '1px solid var(--red)', borderRadius: 8, background: 'rgba(239,68,68,.08)', color: 'var(--red)', fontSize: 12 }}>
          ⚠ {armErr}
        </div>
      )}

      {/* § 1 — Capital */}
      <SectionPanel num="01" title="Simulated Capital" desc="initial balance for the paper session — not real money">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
          <Slider label="Initial Balance" value={cfg.initial_balance} min={1000} max={100000} step={1000} onChange={(v) => set('initial_balance', v)} suffix=" USD" color="#22d3ee" hint="starting equity for the paper session" />
          <Slider label="Risk per Trade" value={cfg.risk_per_trade} min={0.5} max={10} step={0.5} onChange={(v) => set('risk_per_trade', v)} suffix="%" hint="% of current balance risked per position" />
        </div>
      </SectionPanel>

      {/* § 2 — Execution */}
      <SectionPanel num="02" title="Execution" desc="position sizing, duration, leverage">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
          <Slider label="Max Concurrent Positions" value={cfg.max_positions} min={1} max={10} step={1} onChange={(v) => set('max_positions', v)} hint="positions open simultaneously" />
          <Slider label="Leverage" value={cfg.leverage} min={1} max={20} step={1} onChange={(v) => set('leverage', v)} suffix="×" hint="applied to each simulated position" />
          <Slider label="Session Duration" value={cfg.duration_hours} min={1} max={168} step={1} onChange={(v) => set('duration_hours', v)} suffix="h" hint="auto-stop the paper bot after this duration" />
          <Slider label="Scan Interval" value={cfg.scan_interval_minutes} min={1} max={30} step={1} onChange={(v) => set('scan_interval_minutes', v)} suffix="m" hint="minutes between scanner sweeps" />
        </div>
      </SectionPanel>

      {/* § 3 — Confluence */}
      <SectionPanel
        num="03"
        title="Confluence Gate"
        desc={thesis ? 'DEMOTED in thesis mode — the structure thesis decides direction; this score no longer rejects signals' : 'minimum score for a signal to be taken'}
      >
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(1, 1fr)', gap: 12, opacity: thesis ? 0.4 : 1 }}>
          <Slider
            label="Min Confluence Score"
            value={cfg.min_confluence}
            min={50}
            max={95}
            step={1}
            onChange={(v) => set('min_confluence', v)}
            hint={thesis ? 'context only — NOT a gate in thesis mode (at most nudges size tier)' : 'signals below this score are rejected'}
          />
        </div>
        {thesis && (
          <div className="mono" style={{ fontSize: 9, color: '#f5a623', letterSpacing: '.1em', marginTop: 8 }}>
            ⚠ thesis mode active — direction comes from confirmed market structure, not this score. This slider does not gate trades.
          </div>
        )}
      </SectionPanel>

      {/* § 4 — Position management toggles */}
      <SectionPanel num="04" title="Position Management" desc="trailing stop + breakeven — applied to all simulated trades">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, marginBottom: 12 }}>
          <Toggle label="Trailing Stop" value={cfg.trailing_stop} onChange={(v) => set('trailing_stop', v)} hint="trail stop once price moves in favour" />
          <Toggle label="Breakeven on TP1" value={cfg.breakeven_after_target >= 1} onChange={(v) => set('breakeven_after_target', v ? 1 : 0)} hint="move stop to entry after first target hit" />
        </div>
        {cfg.trailing_stop && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
            <Slider label="Trailing Activation" value={cfg.trailing_activation} min={0.5} max={5} step={0.5} onChange={(v) => set('trailing_activation', v)} suffix="%" hint="profit % before trailing activates" />
          </div>
        )}
      </SectionPanel>

      {/* § 5 — Universe */}
      <SectionPanel num="05" title="Universe Scope" desc="which pairs the paper bot is allowed to trade">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, marginBottom: 12 }}>
          <Toggle label="Majors (BTC/ETH/SOL…)" value={cfg.majors} onChange={(v) => set('majors', v)} hint="high-liquidity large-caps" />
          <Toggle label="Altcoins" value={cfg.altcoins} onChange={(v) => set('altcoins', v)} hint="mid-cap altcoins — wider spreads" />
          <Toggle label="Meme Mode" value={cfg.meme_mode} onChange={(v) => set('meme_mode', v)} hint="high-volatility meme coins — highest risk" />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(1, 1fr)', gap: 12 }}>
          <Slider label="Universe Size" value={cfg.universe_size} min={5} max={100} step={5} onChange={(v) => set('universe_size', v)} hint="max symbols the scanner evaluates per sweep" />
        </div>
      </SectionPanel>

      {/* § 6 — Simulated fill realism */}
      <SectionPanel num="06" title="Simulated Fill Realism" desc="slippage + fee model applied to all paper trades">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
          <Slider label="Slippage" value={cfg.slippage_bps} min={0} max={50} step={1} onChange={(v) => set('slippage_bps', v)} suffix=" bps" hint="basis points per fill — models market impact" />
          <Slider label="Taker Fee" value={cfg.fee_rate} min={0} max={0.5} step={0.05} onChange={(v) => set('fee_rate', v)} suffix="%" hint="% fee on each simulated fill" />
        </div>
      </SectionPanel>

      {/* § 7 — Signal & execution mode */}
      <SectionPanel num="07" title="Signal & Execution Mode" desc="how orders fill + whether the macro/dominance overlay biases direction">
        <div className="mono" style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.14em', marginBottom: 6 }}>
          ORDER EXECUTION
        </div>
        <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
          {([['snap_taker', 'SNAP / TAKER'], ['rest_maker', 'REST / MAKER']] as const).map(([m, lbl]) => (
            <button
              key={m}
              type="button"
              className={`btn ${cfg.execution_mode === m ? 'btn-cyan' : ''}`}
              onClick={() => set('execution_mode', m)}
              style={{ flex: 1, fontSize: 11, letterSpacing: '.12em', padding: '10px 0' }}
            >
              {lbl}
            </button>
          ))}
        </div>
        <div className="mono" style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.1em', marginBottom: thesis && cfg.execution_mode === 'rest_maker' ? 6 : 14 }}>
          snap/taker = fill at market now · rest/maker = rest the limit at the OB, fill on pullback (paper-only — ignored under testnet)
        </div>
        {thesis && cfg.execution_mode === 'rest_maker' && (
          <div className="mono" style={{ fontSize: 9, color: '#f5a623', letterSpacing: '.1em', marginBottom: 14 }}>
            ⚠ REST/MAKER rests the limit and fills only on a pullback — low fill rate in choppy ranges. Use SNAP/TAKER to generate trades; switch back to MAKER for fee-sensitive runs.
          </div>
        )}
        <Toggle
          label="Macro / Dominance Overlay"
          value={cfg.macro_overlay_enabled}
          onChange={(v) => set('macro_overlay_enabled', v)}
          hint="BTC.D / stable.D / alt.D bias on direction · OFF = pure technicals"
        />
      </SectionPanel>

      {/* ARM button */}
      <div style={{ paddingBottom: 20 }}>
        <button
          type="button"
          className="btn btn-cyan"
          onClick={() => onArm(cfg)}
          disabled={working}
          style={{ width: '100%', fontSize: 13, letterSpacing: '.2em', padding: '14px 0', fontWeight: 700 }}
        >
          {working ? '↻ ARMING PAPER BOT…' : '▶ ARM PAPER BOT'}
        </button>
        <div className="mono" style={{ fontSize: 9, color: 'var(--fg-4)', textAlign: 'center', marginTop: 8, letterSpacing: '.14em' }}>
          PAPER MODE — SIMULATED CAPITAL ONLY — NO REAL ORDERS SENT
        </div>
      </div>
    </div>
  );
}

// ─── Status Tab ────────────────────────────────────────────────────────
function StatusTab({
  status,
  trades,
  tradesErr,
  connErr,
  actionErr,
  loading,
  working,
  onStop,
  onReset,
  lifetime,
  lifetimeErr,
}: {
  status: PaperTradingStatus | null;
  trades: CompletedPaperTrade[];
  tradesErr: string | null;
  connErr: string | null;
  actionErr: string | null;
  loading: boolean;
  working: boolean;
  lifetime: JournalAggregate | null;
  lifetimeErr: string | null;
  onStop: () => void;
  onReset: () => void;
}) {
  const isRunning = status?.status === 'running';
  const cfg = status?.config;
  const balance = status?.balance;
  const initialBalance = balance?.initial ?? DEFAULT_SETUP.initial_balance;
  const positions = status?.positions ?? [];
  const stats = status?.statistics;
  const activity = status?.recent_activity ?? [];
  const [detailSelection, setDetailSelection] = useState<DetailSelection | null>(null);

  return (
    <div>
      {connErr && (
        <div style={{ margin: '0 0 14px', padding: '12px 14px', border: '1px solid var(--amber)', borderRadius: 10, background: 'rgba(234,179,8,.08)', color: 'var(--amber)', fontSize: 12 }}>
          ⚠ {connErr}
        </div>
      )}
      {actionErr && (
        <div style={{ margin: '0 0 14px', padding: '12px 14px', border: '1px solid var(--red)', borderRadius: 10, background: 'rgba(239,68,68,.08)', color: 'var(--red)', fontSize: 12 }}>
          ⚠ {actionErr}
        </div>
      )}

      {loading && !status && (
        <div className="panel" style={{ margin: '0 0 14px', padding: 32, textAlign: 'center', color: 'var(--fg-3)' }}>
          <span className="mono" style={{ letterSpacing: '.2em' }}>ESTABLISHING UPLINK…</span>
        </div>
      )}

      <div style={{ display: 'grid', gap: 14 }}>
        {/* Command Center */}
        <section className="panel panel-accent" style={{ padding: 18, borderColor: isRunning ? 'var(--amber-border)' : 'rgba(251,191,36,.15)' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
              <div style={{ width: 12, height: 12, borderRadius: '50%', background: isRunning ? 'var(--amber)' : 'var(--fg-3)', boxShadow: isRunning ? '0 0 14px rgba(255,194,102,.8)' : 'none', flexShrink: 0 }} />
              <div>
                <div className="mono" style={{ fontSize: 16, fontWeight: 800, letterSpacing: '.04em', textTransform: 'uppercase', color: 'var(--fg-1)' }}>
                  Ghost Range Engine
                </div>
                <div className="mono" style={{ fontSize: 10, color: 'var(--fg-4)', letterSpacing: '.16em', marginTop: 4, textTransform: 'uppercase' }}>
                  uptime {fmtDuration(status?.uptime_seconds ?? 0)}
                  {status?.session_id && <> · session {status.session_id.slice(0, 8)}</>}
                </div>
                {/* Cumulative P/L — cross-session, sourced from the
                    journal aggregate. Matches the strip on /bot/status so
                    the bot and training surfaces show the same lifetime
                    number. Distinct from balance.pnl (this session,
                    realized + unrealized) and stats.total_pnl (this
                    session, realized only). */}
                <div
                  className="mono"
                  title="Realized cumulative profit/loss across every closed trade in the journal — survives bot restarts and pre-dates this session."
                  style={{
                    fontSize: 10,
                    color: 'var(--fg-4)',
                    letterSpacing: '.16em',
                    marginTop: 4,
                    textTransform: 'uppercase',
                  }}
                >
                  Cumulative P/L (all sessions){' '}
                  <strong
                    style={{
                      color: lifetime
                        ? lifetime.total_pnl > 0
                          ? 'var(--green)'
                          : lifetime.total_pnl < 0
                            ? 'var(--red)'
                            : 'var(--fg-2)'
                        : 'var(--fg-3)',
                      fontWeight: 800,
                    }}
                  >
                    {lifetime
                      ? fmtCurrency(lifetime.total_pnl)
                      : lifetimeErr
                        ? '—'
                        : '…'}
                  </strong>
                  {lifetime && (
                    <>
                      {' · '}
                      <span style={{ color: 'var(--fg-3)' }}>
                        {lifetime.total_trades} trades · WR{' '}
                        {lifetime.win_rate.toFixed(0)}%
                      </span>
                    </>
                  )}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {isRunning ? (
                <button type="button" className="btn btn-red" onClick={onStop} disabled={working} style={{ fontSize: 11 }}>
                  {working ? '↻ STOPPING' : '■ STOP'}
                </button>
              ) : (
                <span className="mono" style={{ fontSize: 11, color: 'var(--fg-4)', alignSelf: 'center', letterSpacing: '.1em' }}>
                  {status?.status?.toUpperCase() ?? 'IDLE'}
                </span>
              )}
              <button type="button" className="btn" onClick={onReset} disabled={working || isRunning} title={isRunning ? 'stop the bot before resetting' : 'clear history + reset balance'} style={{ fontSize: 11, opacity: isRunning ? 0.4 : 1 }}>
                ↺ RESET
              </button>
            </div>
          </div>

          {/* Metric grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10, marginTop: 14 }}>
            <MetricTile label="Uptime" value={fmtDuration(status?.uptime_seconds ?? 0)} sub="session running" />
            <MetricTile label="Next Scan" value={isRunning && status?.next_scan_in_seconds != null ? fmtDuration(Math.round(status.next_scan_in_seconds)) : '—'} sub="until next sweep" accent={isRunning ? 'amber' : undefined} />
            <MetricTile label="Min Score" value={cfg?.min_confluence != null ? `≥${cfg.min_confluence}` : 'AUTO'} sub="confluence threshold" />
            <MetricTile label="Scans Done" value={String(stats?.scans_completed ?? 0)} sub={`${stats?.signals_generated ?? 0} signals`} accent="cyan" />
          </div>

          {/* Config pills */}
          {cfg && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--border-soft)' }}>
              {cfg.sniper_mode && <Chip>{cfg.sniper_mode.toUpperCase()}</Chip>}
              {cfg.duration_hours != null && <Chip>{cfg.duration_hours}H</Chip>}
              {cfg.max_positions != null && <Chip>{cfg.max_positions} SLOTS</Chip>}
              {cfg.risk_per_trade != null && <Chip>{cfg.risk_per_trade}% RISK</Chip>}
              {cfg.leverage != null && cfg.leverage !== 1 && <Chip>{cfg.leverage}× LEVERAGE</Chip>}
              {cfg.initial_balance != null && <Chip>${cfg.initial_balance.toLocaleString()} SIM</Chip>}
            </div>
          )}
        </section>

        {/* Equity Curve + Statistics */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <section className="panel" style={{ padding: 14 }}>
            <SectionHead title="Equity Curve" right={<span className="mono" style={{ fontSize: 10, color: 'var(--fg-4)' }}>{trades.length} trades</span>} />
            {tradesErr && <div style={{ color: 'var(--amber)', fontSize: 10, marginBottom: 6 }}>⚠ {tradesErr}</div>}
            <EquitySparkline trades={trades} initialBalance={initialBalance} />
            <div className="mono" style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--fg-4)', marginTop: 8, textTransform: 'uppercase', letterSpacing: '.14em' }}>
              <span>start {fmtCurrency(initialBalance)}</span>
              <span>now {fmtCurrency(balance?.equity ?? initialBalance)}</span>
              <span style={{ color: (balance?.pnl ?? 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                {fmtCurrency(balance?.pnl ?? 0)} ({fmtPct(balance?.pnl_pct ?? 0, true)})
              </span>
            </div>
          </section>

          <section className="panel" style={{ padding: 14 }}>
            <SectionHead title="Statistics" />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
              <MetricTile
                label="Total PnL"
                value={fmtCurrency(stats?.total_pnl ?? 0)}
                sub={stats?.total_pnl_pct != null ? `${fmtPct(stats.total_pnl_pct, true)} realised` : 'realised'}
                accent={(stats?.total_pnl ?? 0) > 0 ? 'green' : (stats?.total_pnl ?? 0) < 0 ? 'red' : undefined}
              />
              <MetricTile label="Trades" value={String(stats?.total_trades ?? 0)} sub={`${stats?.winning_trades ?? 0}W / ${stats?.losing_trades ?? 0}L`} />
              <MetricTile label="Win Rate" value={stats?.win_rate != null ? `${stats.win_rate.toFixed(0)}%` : '—'} sub="of closed" accent={stats && stats.win_rate >= 50 ? 'green' : undefined} />
              <MetricTile label="Avg R:R" value={stats?.avg_rr != null ? `${stats.avg_rr.toFixed(2)}R` : '—'} sub="realised" />
              <MetricTile label="Best" value={fmtCurrency(stats?.best_trade ?? 0)} accent="green" />
              <MetricTile label="Worst" value={fmtCurrency(stats?.worst_trade ?? 0)} accent="red" />
              <MetricTile label="Max DD" value={stats?.max_drawdown != null ? fmtPct(stats.max_drawdown) : '—'} accent="amber" />
            </div>
          </section>
        </div>

        {/* Open Positions */}
        <section className="panel" style={{ padding: 14 }}>
          <SectionHead title="Open Positions" right={<span className="mono" style={{ fontSize: 10, color: 'var(--fg-4)' }}>{positions.length} active</span>} />
          {positions.length === 0 ? (
            <div className="mono" style={{ padding: 18, textAlign: 'center', fontSize: 11, color: 'var(--fg-4)', letterSpacing: '.16em', textTransform: 'uppercase' }}>
              — no open positions —
            </div>
          ) : (
            <div>
              <div className="mono" style={{ display: 'grid', gridTemplateColumns: '90px 70px 1fr 1fr 1fr 1fr', gap: 10, padding: '8px 12px', fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.18em', textTransform: 'uppercase' }}>
                <span>Symbol</span><span>Side</span><span>Entry</span><span>Mark</span><span>Stop</span><span style={{ textAlign: 'right' }}>uPnL</span>
              </div>
              {positions.map((p) => (
                <PositionRow
                  key={p.position_id}
                  pos={p}
                  onClick={() => setDetailSelection({ kind: 'position', data: p })}
                />
              ))}
            </div>
          )}
        </section>

        {/* Activity Log */}
        <section className="panel" style={{ padding: 14 }}>
          <SectionHead title="Activity Log" right={<span className="mono" style={{ fontSize: 10, color: 'var(--fg-4)' }}>{activity.length} entries</span>} />
          {activity.length === 0 ? (
            <div className="mono" style={{ padding: 18, textAlign: 'center', fontSize: 11, color: 'var(--fg-4)', letterSpacing: '.16em', textTransform: 'uppercase' }}>
              — activity log empty — arm the paper bot to start —
            </div>
          ) : (
            <div style={{ display: 'grid', gap: 0 }}>
              {activity.slice(0, 15).map((entry, i) => <ActivityRow key={`act-${i}`} entry={entry} idx={i} />)}
            </div>
          )}
        </section>

        {/* Exit Reasons + By-Trade-Type */}
        {stats && stats.total_trades > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <section className="panel" style={{ padding: 14 }}>
              <SectionHead title="Exit Reasons" />
              {stats.exit_reasons && Object.keys(stats.exit_reasons).length > 0 ? (
                <div style={{ display: 'grid', gap: 6, paddingTop: 8 }}>
                  {Object.entries(stats.exit_reasons).sort((a, b) => b[1] - a[1]).map(([reason, count]) => (
                    <div key={reason} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0', borderBottom: '1px solid var(--border-soft)' }}>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-2)' }}>{reason.replace(/_/g, ' ')}</span>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-4)' }}>{count}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mono" style={{ fontSize: 11, color: 'var(--fg-4)', padding: '12px 0' }}>— no exits yet —</div>
              )}
            </section>

            <section className="panel" style={{ padding: 14 }}>
              <SectionHead title="By Trade Type" />
              {stats.by_trade_type && Object.keys(stats.by_trade_type).length > 0 ? (
                <div style={{ display: 'grid', gap: 8, paddingTop: 8 }}>
                  {Object.entries(stats.by_trade_type).map(([type, data]) => (
                    <div key={type} style={{ padding: '8px 10px', border: '1px solid var(--border-soft)', borderRadius: 8, background: 'rgba(0,0,0,.2)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <span className="mono" style={{ fontSize: 11, fontWeight: 700 }}>{type.toUpperCase()}</span>
                        <span className="mono" style={{ fontSize: 10, color: 'var(--fg-4)' }}>{data.trades} trades</span>
                      </div>
                      <div className="mono" style={{ fontSize: 10, color: 'var(--fg-3)', display: 'flex', gap: 10 }}>
                        <span>WR {data.win_rate.toFixed(0)}%</span>
                        <span style={{ color: data.total_pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>{fmtCurrency(data.total_pnl)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mono" style={{ fontSize: 11, color: 'var(--fg-4)', padding: '12px 0' }}>— no type breakdown yet —</div>
              )}
            </section>
          </div>
        )}

        {/* Trade History — per-trade rows with exit badge + expandable autopsy */}
        {trades.length > 0 && (
          <section className="panel" style={{ padding: 14 }}>
            <SectionHead
              title="Trade History"
              right={<span className="mono" style={{ fontSize: 10, color: 'var(--fg-4)' }}>{trades.length} closed</span>}
            />
            <div className="mono" style={{ display: 'grid', gridTemplateColumns: '90px 64px 1fr 1fr auto', gap: 10, padding: '6px 12px 8px', fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.18em', textTransform: 'uppercase', borderBottom: '1px solid var(--border-soft)' }}>
              <span>Symbol</span><span>Side</span><span>Entry → Exit</span><span>PnL</span><span>Exit</span>
            </div>
            {trades.map((t) => <TradeHistoryRow key={t.trade_id} trade={t} />)}
          </section>
        )}
      </div>

      <PositionDetailModal
        selection={detailSelection}
        onClose={() => setDetailSelection(null)}
        currentRegime={null}
      />
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────
export function RangeBot() {
  const { botConfig } = useScanner();
  const location = useLocation();
  const navigate = useNavigate();

  // Tab state — #setup or #status; default: setup when idle, status when running
  const [status, setStatus] = useState<PaperTradingStatus | null>(null);
  const [trades, setTrades] = useState<CompletedPaperTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [armErr, setArmErr] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [connErr, setConnErr] = useState<string | null>(null);
  const [tradesErr, setTradesErr] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  // Cross-session lifetime aggregate (matches /bot/status). Sourced from
  // the journal so it survives bot restarts and reflects every closed
  // trade — distinct from balance.pnl (current-session equity − initial)
  // and stats.total_pnl (current-session realized only).
  const [lifetime, setLifetime] = useState<JournalAggregate | null>(null);
  const [lifetimeErr, setLifetimeErr] = useState<string | null>(null);

  const cancelledRef = useRef(false);
  const fastPollRef = useRef(false);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const connErrRef = useRef<string | null>(null);
  connErrRef.current = connErr;

  // Compute active tab from hash; default to setup when idle, status when running
  const isRunning = status?.status === 'running';
  const hashTab = location.hash === '#status' ? 'status' : location.hash === '#setup' ? 'setup' : null;
  const activeTab = hashTab ?? (isRunning ? 'status' : 'setup');

  // Snapshot-ready handshake
  useEffect(() => {
    if (ready) {
      document.body.setAttribute('data-snapshot-ready', 'true');
      return () => { document.body.removeAttribute('data-snapshot-ready'); };
    }
  }, [ready]);

  const loadStatus = useCallback(async () => {
    try {
      const data = await paperTradingService.getStatus();
      setStatus(data);
      fastPollRef.current = data.status === 'running' || (data.positions?.length ?? 0) > 0;
      if (connErrRef.current) setConnErr(null);
    } catch (e) {
      setConnErr(`Backend unreachable: ${e instanceof Error ? e.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
      if (!ready) setReady(true);
    }
  }, [ready]);

  const loadTrades = useCallback(async () => {
    try {
      const data = await paperTradingService.getHistory(50);
      if (data && Array.isArray(data.trades)) {
        setTrades(data.trades);
        setTradesErr(null);
      } else {
        setTradesErr('Trade history response missing trades array');
      }
    } catch (e) {
      setTradesErr(e instanceof Error ? e.message : 'Could not load trade history');
    }
  }, []);

  const loadLifetime = useCallback(async () => {
    try {
      // limit=1 keeps the trades payload tiny — the aggregate envelope is
      // always computed over the full journal regardless of limit.
      const data = await tradeJournalService.getJournal({ limit: 1 });
      if (data && data.aggregate) {
        setLifetime(data.aggregate);
        setLifetimeErr(null);
      } else {
        setLifetimeErr('Journal aggregate missing');
      }
    } catch (e) {
      setLifetimeErr(e instanceof Error ? e.message : 'Could not load lifetime totals');
    }
  }, []);

  useEffect(() => {
    cancelledRef.current = false;
    loadStatus();
    loadTrades();
    loadLifetime();
    const schedule = () => {
      if (cancelledRef.current) return;
      const delay = fastPollRef.current ? FAST_POLL_MS : SLOW_POLL_MS;
      pollTimerRef.current = setTimeout(async () => {
        if (cancelledRef.current) return;
        await Promise.all([loadStatus(), loadTrades(), loadLifetime()]);
        schedule();
      }, delay);
    };
    schedule();
    return () => {
      cancelledRef.current = true;
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleArm = useCallback(async (cfg: PaperConfig) => {
    setWorking(true);
    setArmErr(null);
    try {
      const req: PaperTradingConfigRequest = {
        exchange: 'phemex',
        sniper_mode: botConfig.sniperMode ?? 'stealth',
        initial_balance: cfg.initial_balance,
        risk_per_trade: cfg.risk_per_trade,
        max_positions: cfg.max_positions,
        leverage: cfg.leverage,
        duration_hours: cfg.duration_hours,
        scan_interval_minutes: cfg.scan_interval_minutes,
        min_confluence: cfg.min_confluence,
        trailing_stop: cfg.trailing_stop,
        trailing_activation: cfg.trailing_activation,
        breakeven_after_target: cfg.breakeven_after_target,
        majors: cfg.majors,
        altcoins: cfg.altcoins,
        meme_mode: cfg.meme_mode,
        universe_size: cfg.universe_size,
        slippage_bps: cfg.slippage_bps,
        fee_rate: cfg.fee_rate / 100, // slider is in %, service expects decimal
        use_testnet: false,
        sensitivity_preset: 'custom',
        execution_mode: cfg.execution_mode,
        macro_overlay_enabled: cfg.macro_overlay_enabled,
      };
      await paperTradingService.start(req);
      await Promise.all([loadStatus(), loadTrades()]);
      navigate('/training/range#status', { replace: true });
    } catch (e) {
      console.warn('[RangeBot] arm error:', e);
      setArmErr(String((e as Error)?.message ?? e));
    } finally {
      setWorking(false);
    }
  }, [botConfig.sniperMode, loadStatus, loadTrades, navigate]);

  const handleStop = useCallback(async () => {
    setWorking(true);
    setActionErr(null);
    try {
      await paperTradingService.stop();
      await Promise.all([loadStatus(), loadTrades()]);
    } catch (e) {
      console.warn('[RangeBot] stop error:', e);
      setActionErr(String((e as Error)?.message ?? e));
    } finally {
      setWorking(false);
    }
  }, [loadStatus, loadTrades]);

  const handleReset = useCallback(async () => {
    setWorking(true);
    setActionErr(null);
    try {
      await paperTradingService.reset();
      await Promise.all([loadStatus(), loadTrades()]);
      navigate('/training/range#setup', { replace: true });
    } catch (e) {
      console.warn('[RangeBot] reset error:', e);
      setActionErr(String((e as Error)?.message ?? e));
    } finally {
      setWorking(false);
    }
  }, [loadStatus, loadTrades, navigate]);

  return (
    <div className="page-shell" id="main-content">
      <Reticle />

      <PageHead
        icon="◉"
        title="Ghost Range"
        subtitle="TRAINING / RANGE · real signals · simulated capital"
        accent="amber"
        badges={
          <>
            <Chip kind="amber">◉ PAPER MODE</Chip>
            <Chip kind={isRunning ? 'green' : undefined}>
              {isRunning ? '● RUNNING' : '○ IDLE'}
            </Chip>
          </>
        }
      />

      <PaperModeBanner />

      {/* Tab switcher */}
      <div
        style={{
          display: 'flex',
          gap: 4,
          marginBottom: 14,
          borderBottom: '1px solid var(--border-soft)',
          paddingBottom: 0,
        }}
      >
        {(['setup', 'status'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => navigate(`/training/range#${tab}`, { replace: true })}
            style={{
              padding: '8px 18px',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === tab ? '2px solid var(--amber)' : '2px solid transparent',
              color: activeTab === tab ? 'var(--amber)' : 'var(--fg-3)',
              fontFamily: 'Share Tech Mono,monospace',
              fontSize: 12,
              letterSpacing: '.16em',
              textTransform: 'uppercase',
              cursor: 'pointer',
              transition: 'color .15s',
              marginBottom: -1,
            }}
          >
            {tab === 'setup' ? '// SETUP' : '// STATUS'}
          </button>
        ))}
      </div>

      {/* Cycle heartbeat — both tabs */}
      <CycleHeartbeat />

      {/* Tab content */}
      {activeTab === 'setup' ? (
        <SetupTab
          sniperMode={botConfig.sniperMode ?? 'stealth'}
          onArm={handleArm}
          working={working}
          armErr={armErr}
          decisionMode={status?.decision_mode}
        />
      ) : (
        <StatusTab
          status={status}
          trades={trades}
          tradesErr={tradesErr}
          connErr={connErr}
          actionErr={actionErr}
          loading={loading}
          working={working}
          lifetime={lifetime}
          lifetimeErr={lifetimeErr}
          onStop={handleStop}
          onReset={handleReset}
        />
      )}

      <FooterStatus />
    </div>
  );
}
