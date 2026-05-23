/**
 * PositionDetailModal — click-through detail surface for active positions
 * and pending limit orders.
 *
 * Activated from /bot/status when the operator clicks any row in the
 * Active Positions panel. Shows:
 *   - A candlestick chart (lightweight-charts, already in deps) with
 *     horizontal lines for entry / SL / TP1 / TP2 / tp_final / mark on
 *     filled positions, or limit-price on pending orders.
 *   - A metadata strip with trade_type, opened-at, breakeven/trailing
 *     state flags, current R-multiple, planned R:R, and current regime.
 *
 * Phase 2 deferrals (acknowledged in shape brief, flagged here):
 *   - regime-at-entry: requires backend extension to snapshot regime at
 *     signal time; we show CURRENT regime only.
 *   - exact entry timeframe: position carries only cascade tier
 *     (SCALP/INTRADAY/SWING) via trade_type; we map that to a chart TF
 *     but the real per-signal TF lives in signal_log metadata.
 *   - SL/TP for pending orders: backend pending_orders payload omits
 *     them (live on _pending_plans server-side). Pending modal shows
 *     limit-price only with an inline note.
 */
import { useEffect, useRef, useState } from 'react';
import {
  createChart,
  CandlestickSeries,
  ColorType,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from 'lightweight-charts';
import { Chip } from './Chip';
import { Modal } from './Modal';
import { api } from '@/utils/api';
import type { LivePosition } from '@/services/liveTradingService';
import type { PaperPosition } from '@/services/paperTradingService';

/** Pending order shape — mirrors backend payload, kept local so the modal
 * works whether called with LiveTradingStatus or PaperTradingStatus. */
export interface PendingOrderShape {
  order_id: string;
  symbol: string;
  direction: string;
  limit_price: number;
  quantity: number;
  status: string;
}

/** Selection passed from BotStatus / RangeBot row onClick.
 * LivePosition and PaperPosition are structurally identical (same 17 fields,
 * same domain concept). Accepting both lets the same modal serve the live bot
 * page (/bot) and the paper-trader page (/training/range) without a cast. */
export type DetailSelection =
  | { kind: 'position'; data: LivePosition | PaperPosition }
  | { kind: 'pending'; data: PendingOrderShape };

interface Props {
  selection: DetailSelection | null;
  onClose: () => void;
  /** Optional current-regime composite ("ranging" / "trending_up" / etc.)
   * Read from status.regime on BotStatus. Pass null on paper sessions. */
  currentRegime?: string | null;
}

// ─── Formatters / helpers ──────────────────────────────────────────────

function fmtPrice(v: number): string {
  if (!Number.isFinite(v)) return '—';
  // Adaptive precision: tiny prices get more decimals.
  if (v < 1) return v.toFixed(6);
  if (v < 100) return v.toFixed(4);
  return v.toFixed(2);
}

function fmtAgeFromIso(iso: string | undefined | null): string {
  if (!iso) return '—';
  const ms = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return '—';
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
  return `${Math.floor(s / 86400)}d ${Math.floor((s % 86400) / 3600)}h`;
}

/** Map cascade tier from position.trade_type to a chart timeframe. */
function tradeTypeToTimeframe(tt: string | undefined | null): string {
  const t = (tt || '').toLowerCase();
  if (t === 'scalp') return '15m';
  if (t === 'intraday') return '1h';
  if (t === 'swing') return '4h';
  return '1h';
}

/** R:R = planned reward / planned risk. Direction-aware. Returns null when
 * the plan is malformed (SL at-or-past entry, or reward ≤ 0 because TP is on
 * the wrong side of entry — usually a TP field serialized as 0 instead of
 * null). Without this guard, a `tp_final: 0` payload yields a nonsensical
 * 1:-N display. */
function calcRR(
  direction: string,
  entry: number,
  sl: number,
  tp: number | null | undefined,
): number | null {
  if (
    tp == null ||
    !Number.isFinite(tp) ||
    !Number.isFinite(sl) ||
    !Number.isFinite(entry) ||
    tp <= 0
  ) {
    return null;
  }
  if (direction === 'LONG') {
    const reward = tp - entry;
    const risk = entry - sl;
    if (risk <= 0 || reward <= 0) return null;
    return reward / risk;
  }
  const reward = entry - tp;
  const risk = sl - entry;
  if (risk <= 0 || reward <= 0) return null;
  return reward / risk;
}

/** Pick the most meaningful TP for the R:R display. `tp_final ?? tp1` is
 * insufficient because `??` only falls through on null/undefined — a
 * serialized `0` wins over a valid `tp1`, which produced the 1:-86 display
 * regression. Treat 0 / negative / non-finite as "unset" and fall through. */
function selectPlanTp(
  tp_final: number | null | undefined,
  tp1: number | null | undefined,
): number | null {
  if (tp_final != null && Number.isFinite(tp_final) && tp_final > 0) return tp_final;
  if (tp1 != null && Number.isFinite(tp1) && tp1 > 0) return tp1;
  return null;
}

/** Current R-multiple = unrealized PnL / planned risk dollars. */
function calcCurrentR(pnl: number, riskPnl: number | undefined): number | null {
  if (
    !Number.isFinite(pnl) ||
    riskPnl == null ||
    !Number.isFinite(riskPnl) ||
    Math.abs(riskPnl) < 1e-9
  ) {
    return null;
  }
  return pnl / Math.abs(riskPnl);
}

// ─── Component ─────────────────────────────────────────────────────────

export function PositionDetailModal({ selection, onClose, currentRegime }: Props) {
  const chartHostRef = useRef<HTMLDivElement>(null);
  const chartApiRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const [candlesError, setCandlesError] = useState<string | null>(null);
  const [candlesLoading, setCandlesLoading] = useState(false);

  // Escape-to-close. Window-scoped listener; cleaned up on unmount or
  // when the close handler reference changes.
  useEffect(() => {
    if (!selection) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [selection, onClose]);

  // Build chart on selection change. Tear down on unmount.
  useEffect(() => {
    if (!selection || !chartHostRef.current) return;
    const host = chartHostRef.current;

    const chart = createChart(host, {
      width: host.clientWidth,
      height: 280,
      layout: {
        background: { type: ColorType.Solid, color: 'rgba(0,0,0,0)' },
        // sRGB approximations of DESIGN.md OKLCH tokens so the lib (which
        // doesn't read CSS vars) blends with the panel chrome.
        textColor: '#8a9a93', // fg-3 equivalent
        fontFamily: '"JetBrains Mono", monospace',
        fontSize: 10,
      },
      grid: {
        vertLines: { color: 'rgba(255,255,255,.04)' },
        horzLines: { color: 'rgba(255,255,255,.04)' },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: 'rgba(255,255,255,.08)',
      },
      rightPriceScale: {
        borderColor: 'rgba(255,255,255,.08)',
      },
      crosshair: { mode: 1 },
    });

    // lightweight-charts v5 series API: chart.addSeries(SeriesDef, options)
    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#00ffaa',
      downColor: '#f87171',
      borderVisible: false,
      wickUpColor: '#00ffaa',
      wickDownColor: '#f87171',
    });

    chartApiRef.current = chart;
    seriesRef.current = series;

    const symbol = selection.data.symbol;
    const tf =
      selection.kind === 'position'
        ? tradeTypeToTimeframe(selection.data.trade_type)
        : '1h';

    setCandlesLoading(true);
    setCandlesError(null);

    api
      .getCandles(symbol, tf, 100)
      .then((res: unknown) => {
        // api.request returns an envelope { data?, error? }; surface the
        // real error so the modal doesn't mask backend cache misses or
        // fresh-fetch failures as a generic empty-candles message.
        if (res && typeof res === 'object' && 'error' in res && (res as { error?: unknown }).error) {
          setCandlesError(String((res as { error: unknown }).error));
          return;
        }
        const body =
          res && typeof res === 'object' && 'data' in res
            ? (res as { data: unknown }).data
            : res;
        // Backend candle response shape is unknown to TS here; coerce
        // defensively. Accept either { candles: [...] } or a bare array.
        const list =
          Array.isArray(body)
            ? body
            : body && typeof body === 'object' && 'candles' in body
              ? (body as { candles: unknown[] }).candles
              : [];

        const candles = (list as Array<Record<string, unknown>>)
          .map((c) => {
            const t = c.time ?? c.timestamp;
            const time =
              typeof t === 'number'
                ? (t > 1e12 ? Math.floor(t / 1000) : t) // ms vs seconds
                : typeof t === 'string'
                  ? Math.floor(new Date(t).getTime() / 1000)
                  : null;
            if (time == null) return null;
            const open = Number(c.open);
            const high = Number(c.high);
            const low = Number(c.low);
            const close = Number(c.close);
            if (
              !Number.isFinite(open) ||
              !Number.isFinite(high) ||
              !Number.isFinite(low) ||
              !Number.isFinite(close)
            ) {
              return null;
            }
            return { time: time as Time, open, high, low, close };
          })
          .filter((c): c is NonNullable<typeof c> => c != null);

        if (candles.length === 0) {
          setCandlesError('No candle data returned');
          return;
        }

        series.setData(candles);
        chart.timeScale().fitContent();

        // Plot horizontal price lines.
        if (selection.kind === 'position') {
          const p = selection.data;
          series.createPriceLine({
            price: p.entry_price,
            color: '#00ffaa',
            lineWidth: 2,
            lineStyle: 0, // solid
            axisLabelVisible: true,
            title: 'ENTRY',
          });
          series.createPriceLine({
            price: p.stop_loss,
            color: '#f87171',
            lineWidth: 1,
            lineStyle: 2, // dashed
            axisLabelVisible: true,
            title: 'SL',
          });
          if (p.tp1 != null) {
            series.createPriceLine({
              price: p.tp1,
              color: '#4ade80',
              lineWidth: 1,
              lineStyle: 1, // dotted
              axisLabelVisible: true,
              title: 'TP1',
            });
          }
          if (p.tp2 != null) {
            series.createPriceLine({
              price: p.tp2,
              color: '#4ade80',
              lineWidth: 1,
              lineStyle: 1,
              axisLabelVisible: true,
              title: 'TP2',
            });
          }
          if (p.tp_final != null) {
            series.createPriceLine({
              price: p.tp_final,
              color: '#4ade80',
              lineWidth: 2,
              lineStyle: 0,
              axisLabelVisible: true,
              title: 'TP',
            });
          }
          series.createPriceLine({
            price: p.current_price,
            color: '#a8b5b0',
            lineWidth: 1,
            lineStyle: 0,
            axisLabelVisible: true,
            title: 'MARK',
          });
        } else {
          // Pending order: limit-price only.
          series.createPriceLine({
            price: selection.data.limit_price,
            color: '#22d3ee',
            lineWidth: 2,
            lineStyle: 0,
            axisLabelVisible: true,
            title: 'LIMIT',
          });
        }
      })
      .catch((e) => {
        setCandlesError(e instanceof Error ? e.message : 'Candle fetch failed');
      })
      .finally(() => setCandlesLoading(false));

    // Resize handling — keep chart width synced to its host.
    const ro = new ResizeObserver(() => {
      if (chartApiRef.current && host) {
        chartApiRef.current.applyOptions({ width: host.clientWidth });
      }
    });
    ro.observe(host);

    return () => {
      ro.disconnect();
      chart.remove();
      chartApiRef.current = null;
      seriesRef.current = null;
    };
  }, [selection]);

  if (!selection) return null;

  const isPosition = selection.kind === 'position';
  const symbol = selection.data.symbol;
  const direction = selection.data.direction.toUpperCase();
  const isLong = direction === 'LONG';

  // Position-only derived values for the metadata strip.
  const pos = isPosition ? (selection.data as LivePosition) : null;
  const usableTp = pos != null ? selectPlanTp(pos.tp_final, pos.tp1) : null;
  const plannedRR =
    pos != null
      ? calcRR(direction, pos.entry_price, pos.stop_loss, usableTp)
      : null;
  const currentR = pos != null ? calcCurrentR(pos.unrealized_pnl, pos.risk_pnl) : null;
  // True when the position has no usable take-profit. Either the planner
  // shipped a plan with no targets, or position_manager's structural-validity
  // guard stripped every target as geometrically invalid. Either way, the
  // position can only exit via SL / stagnation / max_hours_open — never via
  // TP — so the operator should know before treating R:R "—" as a render bug.
  const noUsableTp = pos != null && usableTp == null;

  return (
    <Modal onClose={onClose} maxWidth={820}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '14px 18px',
          borderBottom: '1px solid var(--border-soft)',
          flexWrap: 'wrap',
        }}
      >
        <span
          className="mono"
          style={{
            fontSize: 16,
            fontWeight: 800,
            letterSpacing: '.06em',
            color: 'var(--fg)',
          }}
        >
          {symbol}
        </span>
        <Chip kind={isLong ? 'green' : 'red'}>{isLong ? 'LONG' : 'SHORT'}</Chip>
        {isPosition && pos?.trade_type && (
          <Chip kind="cyan">{pos.trade_type.toUpperCase()}</Chip>
        )}
        {noUsableTp && (
          <span
            title="This position has no valid take-profit. Either the planner shipped no targets or the executor's geometry guard stripped them as wrong-side-of-fill. The position can only close via stop loss, stagnation, or max-hours timeout."
          >
            <Chip kind="amber">NO TP — SL/STAGNATION ONLY</Chip>
          </span>
        )}
        {!isPosition && (
          <Chip kind="blue">
            {(selection.data.status || 'OPEN').toUpperCase()}
          </Chip>
        )}
        <span
          className="mono"
          style={{
            marginLeft: 'auto',
            fontSize: 10,
            color: 'var(--fg-4)',
            letterSpacing: '.18em',
            textTransform: 'uppercase',
          }}
        >
          {isPosition ? `${tradeTypeToTimeframe(pos?.trade_type ?? '')} chart` : '1h chart'}
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close detail"
          autoFocus
          style={{
            background: 'transparent',
            border: '1px solid var(--border-soft)',
            color: 'var(--fg-2)',
            borderRadius: 8,
            width: 28,
            height: 28,
            cursor: 'pointer',
            fontSize: 14,
            lineHeight: 1,
          }}
        >
          ×
        </button>
      </div>

      {/* Chart */}
      <div style={{ position: 'relative', padding: '12px 14px' }}>
        <div
          ref={chartHostRef}
          style={{
            width: '100%',
            height: 280,
            background: 'rgba(0,0,0,.25)',
            border: '1px solid var(--border-soft)',
            borderRadius: 8,
            overflow: 'hidden',
          }}
        />
        {candlesLoading && (
          <div
            className="mono"
            style={{
              position: 'absolute',
              inset: '12px 14px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 10,
              color: 'var(--fg-4)',
              letterSpacing: '.2em',
              textTransform: 'uppercase',
              pointerEvents: 'none',
            }}
          >
            Reading candles…
          </div>
        )}
        {candlesError && !candlesLoading && (
          <div
            className="mono"
            style={{
              position: 'absolute',
              inset: '12px 14px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 10,
              color: 'var(--amber)',
              letterSpacing: '.18em',
              textTransform: 'uppercase',
              pointerEvents: 'none',
            }}
          >
            ⚠ {candlesError}
          </div>
        )}
      </div>

      {/* Metadata strip */}
      <div
        className="mono"
        style={{
          padding: '12px 18px 14px',
          borderTop: '1px solid var(--border-soft)',
          display: 'flex',
          flexWrap: 'wrap',
          gap: 14,
          fontSize: 10,
          letterSpacing: '.18em',
          textTransform: 'uppercase',
          color: 'var(--fg-4)',
        }}
      >
        {isPosition && pos && (
          <>
            <span>
              Type{' '}
              <strong style={{ color: 'var(--fg)', fontWeight: 800 }}>
                {pos.trade_type || '—'}
              </strong>
            </span>
            <span style={{ opacity: 0.3 }}>·</span>
            <span>
              Opened{' '}
              <strong style={{ color: 'var(--fg)', fontWeight: 800 }}>
                {fmtAgeFromIso(pos.opened_at)} ago
              </strong>
            </span>
            <span style={{ opacity: 0.3 }}>·</span>
            <span>
              R:R{' '}
              <strong style={{ color: 'var(--fg)', fontWeight: 800 }}>
                {plannedRR != null ? `1 : ${plannedRR.toFixed(2)}` : '—'}
              </strong>
            </span>
            <span style={{ opacity: 0.3 }}>·</span>
            <span>
              Current{' '}
              <strong
                style={{
                  color:
                    currentR != null && currentR >= 0
                      ? 'var(--green)'
                      : currentR != null
                        ? 'var(--red)'
                        : 'var(--fg-3)',
                  fontWeight: 800,
                }}
              >
                {currentR != null
                  ? `${currentR >= 0 ? '+' : ''}${currentR.toFixed(2)}R`
                  : '—'}
              </strong>
            </span>
            <span style={{ opacity: 0.3 }}>·</span>
            <span title="ARMED = configured & monitoring; TRIGGERED = SL has been moved to breakeven (typically after TP1 prints)">
              Breakeven{' '}
              <strong
                style={{
                  color: pos.breakeven_active ? 'var(--green)' : 'var(--fg-3)',
                  fontWeight: 800,
                }}
              >
                {pos.breakeven_active ? 'TRIGGERED' : 'ARMED'}
              </strong>
            </span>
            <span style={{ opacity: 0.3 }}>·</span>
            <span title="ARMED = configured & monitoring; TRAILING = stop is actively trailing price">
              Trailing{' '}
              <strong
                style={{
                  color: pos.trailing_active ? 'var(--green)' : 'var(--fg-3)',
                  fontWeight: 800,
                }}
              >
                {pos.trailing_active ? 'TRAILING' : 'ARMED'}
              </strong>
            </span>
            {currentRegime && (
              <>
                <span style={{ opacity: 0.3 }}>·</span>
                <span>
                  Regime{' '}
                  <strong style={{ color: 'var(--blue)', fontWeight: 800 }}>
                    {currentRegime.replace(/_/g, ' ').toUpperCase()}
                  </strong>{' '}
                  <span style={{ opacity: 0.5 }}>(current)</span>
                </span>
              </>
            )}
          </>
        )}
        {!isPosition && (
          <>
            <span>
              Limit{' '}
              <strong style={{ color: 'var(--cyan)', fontWeight: 800 }}>
                {fmtPrice(selection.data.limit_price)}
              </strong>
            </span>
            <span style={{ opacity: 0.3 }}>·</span>
            <span>
              Qty{' '}
              <strong style={{ color: 'var(--fg)', fontWeight: 800 }}>
                {selection.data.quantity}
              </strong>
            </span>
            <span style={{ opacity: 0.3 }}>·</span>
            <span>
              Status{' '}
              <strong style={{ color: 'var(--blue)', fontWeight: 800 }}>
                {selection.data.status}
              </strong>
            </span>
            <span style={{ opacity: 0.3 }}>·</span>
            <span style={{ opacity: 0.6 }}>SL / TP land after fill</span>
          </>
        )}
      </div>
    </Modal>
  );
}
