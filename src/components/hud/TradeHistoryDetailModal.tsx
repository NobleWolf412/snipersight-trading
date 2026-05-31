/**
 * TradeHistoryDetailModal — click-through chart for a CLOSED trade.
 *
 * Activated from /journal when the operator clicks a row in the Trade Log.
 * Renders a candlestick chart for the trade's symbol on a timeframe inferred
 * from `trade_type` (scalp→15m, intraday→1h, swing→4h) and overlays:
 *   - ENTRY and EXIT horizontal price lines
 *   - ENTRY and EXIT time markers on the candle series (arrow direction +
 *     color encodes long/short and win/loss)
 *   - Header strip with PnL / MFE / MAE / exit reason
 *
 * Companion to PositionDetailModal — same chart library, same chrome, but
 * the domain is "post-mortem of a finished trade" rather than "monitor an
 * open position", so:
 *   - no SL/TP lines (journal record does not carry the original plan)
 *   - no current-mark line (the trade is closed)
 *   - markers replace the live "MARK" line so the operator can see the
 *     entry and exit candles in price/time context
 *
 * Time-window caveat: api.getCandles returns the most recent N candles, no
 * `since` parameter. For very old trades the entry/exit may fall outside
 * the returned window. We detect that case and surface a warning chip so
 * "marker missing" never looks like a render bug.
 */
import { useEffect, useRef, useState } from 'react';
import {
  createChart,
  createSeriesMarkers,
  CandlestickSeries,
  ColorType,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
} from 'lightweight-charts';
import { Chip } from './Chip';
import { Modal } from './Modal';
import { api } from '@/utils/api';
import type { JournalTrade } from '@/services/tradeJournalService';

interface Props {
  trade: JournalTrade | null;
  onClose: () => void;
}

// ─── Helpers ───────────────────────────────────────────────────────────

function fmtPrice(v: number): string {
  if (!Number.isFinite(v)) return '—';
  if (v < 1) return v.toFixed(6);
  if (v < 100) return v.toFixed(4);
  return v.toFixed(2);
}

function fmtMoney(v: number): string {
  if (!Number.isFinite(v)) return '—';
  const sign = v >= 0 ? '+' : '';
  return `${sign}$${Math.abs(v).toFixed(2) === '0.00' ? '0.00' : v.toFixed(2)}`;
}

function fmtPct(v: number): string {
  if (!Number.isFinite(v)) return '—';
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(2)}%`;
}

function fmtDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
}

function tradeTypeToTimeframe(tt: string | undefined | null): string {
  const t = (tt || '').toLowerCase();
  if (t === 'scalp') return '15m';
  if (t === 'intraday') return '1h';
  if (t === 'swing') return '4h';
  return '1h';
}

const EXIT_REASON_LABELS: Record<string, string> = {
  target: 'TARGET',
  stop_loss: 'STOP',
  stagnation: 'STALE',
  manual: 'MANUAL',
  max_hours: 'TIMEOUT',
  orphan_price_feed_failure: 'ORPHAN',
  trailing_stop: 'TRAIL',
};

function exitReasonKind(reason: string, pnl: number): 'green' | 'red' | 'amber' {
  if (reason === 'target' || reason === 'trailing_stop') return 'green';
  if (reason === 'stop_loss') return 'red';
  return pnl >= 0 ? 'green' : 'amber';
}

/** Snap an ISO timestamp to the nearest candle bucket present in `times`.
 * Lightweight-charts markers must land on a real bar time or they're dropped
 * silently — this guards against off-by-a-bucket render gaps. */
function snapToNearestCandle(iso: string | null, times: number[]): number | null {
  if (!iso || times.length === 0) return null;
  const target = Math.floor(new Date(iso).getTime() / 1000);
  if (!Number.isFinite(target)) return null;
  // Out-of-range guards — if the trade fell before the first candle or
  // after the last, mark as missing so the caller can warn the operator
  // instead of silently snapping to a wildly wrong bar.
  if (target < times[0] - 86400 * 3 || target > times[times.length - 1] + 86400 * 3) {
    return null;
  }
  // Binary search for the closest bar.
  let lo = 0;
  let hi = times.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (times[mid] < target) lo = mid + 1;
    else hi = mid;
  }
  // Compare lo with lo-1 to pick the truly nearest.
  if (lo > 0 && Math.abs(times[lo - 1] - target) < Math.abs(times[lo] - target)) {
    return times[lo - 1];
  }
  return times[lo];
}

// ─── Component ─────────────────────────────────────────────────────────

export function TradeHistoryDetailModal({ trade, onClose }: Props) {
  const chartHostRef = useRef<HTMLDivElement>(null);
  const chartApiRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const [candlesError, setCandlesError] = useState<string | null>(null);
  const [candlesLoading, setCandlesLoading] = useState(false);
  // True when the trade's entry-time or exit-time fell outside the candle
  // window returned by the backend (older than the most recent N bars).
  // The chart still renders, but markers are missing — the warning chip in
  // the header tells the operator this isn't a render bug.
  const [outOfWindow, setOutOfWindow] = useState(false);

  // Escape-to-close.
  useEffect(() => {
    if (!trade) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [trade, onClose]);

  useEffect(() => {
    if (!trade || !chartHostRef.current) return;
    const host = chartHostRef.current;

    const chart = createChart(host, {
      width: host.clientWidth,
      height: 320,
      layout: {
        background: { type: ColorType.Solid, color: 'rgba(0,0,0,0)' },
        textColor: '#8a9a93',
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
      rightPriceScale: { borderColor: 'rgba(255,255,255,.08)' },
      crosshair: { mode: 1 },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#00ffaa',
      downColor: '#f87171',
      borderVisible: false,
      wickUpColor: '#00ffaa',
      wickDownColor: '#f87171',
    });

    chartApiRef.current = chart;
    seriesRef.current = series;
    setOutOfWindow(false);

    const tf = tradeTypeToTimeframe(trade.trade_type);
    // 500 bars: ~5d on 15m, ~21d on 1h, ~83d on 4h — covers the vast
    // majority of recent trades while keeping the payload small.
    setCandlesLoading(true);
    setCandlesError(null);

    api
      .getCandles(trade.symbol, tf, 500)
      .then((res: unknown) => {
        if (res && typeof res === 'object' && 'error' in res && (res as { error?: unknown }).error) {
          setCandlesError(String((res as { error: unknown }).error));
          return;
        }
        const body =
          res && typeof res === 'object' && 'data' in res
            ? (res as { data: unknown }).data
            : res;
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
                ? (t > 1e12 ? Math.floor(t / 1000) : t)
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

        // Horizontal price lines for entry + exit.
        const isLong = trade.direction === 'LONG';
        const isWin = trade.pnl >= 0;
        series.createPriceLine({
          price: trade.entry_price,
          color: '#22d3ee',
          lineWidth: 2,
          lineStyle: 0,
          axisLabelVisible: true,
          title: 'ENTRY',
        });
        series.createPriceLine({
          price: trade.exit_price,
          color: isWin ? '#4ade80' : '#f87171',
          lineWidth: 2,
          lineStyle: 2,
          axisLabelVisible: true,
          title: 'EXIT',
        });

        // Entry / exit candle markers. Snap to nearest bar so the marker
        // actually lands on a candle — lightweight-charts silently drops
        // markers whose time doesn't match a bar.
        const times = candles.map((c) => Number(c.time));
        const entrySnap = snapToNearestCandle(trade.entry_time, times);
        const exitSnap = snapToNearestCandle(trade.exit_time, times);
        const markers: SeriesMarker<Time>[] = [];
        if (entrySnap != null) {
          markers.push({
            time: entrySnap as Time,
            position: isLong ? 'belowBar' : 'aboveBar',
            shape: isLong ? 'arrowUp' : 'arrowDown',
            color: '#22d3ee',
            text: `ENTRY ${isLong ? 'LONG' : 'SHORT'}`,
          });
        }
        if (exitSnap != null) {
          markers.push({
            time: exitSnap as Time,
            position: isLong ? 'aboveBar' : 'belowBar',
            shape: isLong ? 'arrowDown' : 'arrowUp',
            color: isWin ? '#4ade80' : '#f87171',
            text: `EXIT ${EXIT_REASON_LABELS[trade.exit_reason] ?? trade.exit_reason.toUpperCase()}`,
          });
        }
        // Either side falling outside the candle window means the operator
        // is looking at a chart that doesn't visually contain the trade.
        // Surface that loudly instead of leaving the chart looking blank
        // of markers (Hidden Bug Surfacing, §11).
        if (entrySnap == null || exitSnap == null) {
          setOutOfWindow(true);
        }
        markersRef.current = createSeriesMarkers(series, markers);

        // Fit-to-content first, then if both markers landed inside the
        // window, zoom in to a window centered on the trade so the
        // operator sees price action *around* the trade — not the full
        // 500-bar range.
        chart.timeScale().fitContent();
        if (entrySnap != null && exitSnap != null) {
          const span = Math.max(exitSnap - entrySnap, 1);
          const pad = Math.max(span * 0.6, 1);
          const fromTime = (entrySnap - pad) as Time;
          const toTime = (exitSnap + pad) as Time;
          chart.timeScale().setVisibleRange({ from: fromTime, to: toTime });
        }
      })
      .catch((e) => {
        setCandlesError(e instanceof Error ? e.message : 'Candle fetch failed');
      })
      .finally(() => setCandlesLoading(false));

    const ro = new ResizeObserver(() => {
      if (chartApiRef.current && host) {
        chartApiRef.current.applyOptions({ width: host.clientWidth });
      }
    });
    ro.observe(host);

    return () => {
      ro.disconnect();
      try {
        markersRef.current?.detach();
      } catch {
        // If the chart is already gone, detach is a no-op.
      }
      markersRef.current = null;
      chart.remove();
      chartApiRef.current = null;
      seriesRef.current = null;
    };
  }, [trade]);

  if (!trade) return null;

  const isLong = trade.direction === 'LONG';
  const isWin = trade.pnl >= 0;
  const tf = tradeTypeToTimeframe(trade.trade_type);
  const durationSec =
    trade.entry_time && trade.exit_time
      ? (new Date(trade.exit_time).getTime() - new Date(trade.entry_time).getTime()) / 1000
      : NaN;
  const exitLabel = EXIT_REASON_LABELS[trade.exit_reason] ?? trade.exit_reason.toUpperCase();

  return (
    <Modal onClose={onClose} maxWidth={860}>
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
          {trade.symbol}
        </span>
        <Chip kind={isLong ? 'green' : 'red'}>{isLong ? 'LONG' : 'SHORT'}</Chip>
        {trade.trade_type && <Chip kind="cyan">{trade.trade_type.toUpperCase()}</Chip>}
        <Chip kind={exitReasonKind(trade.exit_reason, trade.pnl)}>{exitLabel}</Chip>
        {outOfWindow && (
          <span title="The trade's entry or exit time falls outside the most recent 500 bars returned by the candle endpoint. The chart shows current price action for this symbol; markers for entry/exit are not plotted because the historical bar isn't loaded.">
            <Chip kind="amber">CHART WINDOW BEFORE TRADE</Chip>
          </span>
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
          {tf} chart
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close trade detail"
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
            height: 320,
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
        <span>
          PnL{' '}
          <strong
            style={{
              color: isWin ? 'var(--green)' : 'var(--red)',
              fontWeight: 800,
            }}
          >
            {fmtMoney(trade.pnl)} ({fmtPct(trade.pnl_pct)})
          </strong>
        </span>
        <span style={{ opacity: 0.3 }}>·</span>
        <span>
          Entry{' '}
          <strong style={{ color: 'var(--fg)', fontWeight: 800 }}>
            {fmtPrice(trade.entry_price)}
          </strong>
        </span>
        <span style={{ opacity: 0.3 }}>·</span>
        <span>
          Exit{' '}
          <strong style={{ color: 'var(--fg)', fontWeight: 800 }}>
            {fmtPrice(trade.exit_price)}
          </strong>
        </span>
        <span style={{ opacity: 0.3 }}>·</span>
        <span title="Maximum Favorable Excursion — best unrealized PnL during the trade">
          MFE{' '}
          <strong style={{ color: 'var(--green-soft)', fontWeight: 800 }}>
            +{trade.max_favorable.toFixed(2)}
          </strong>
        </span>
        <span style={{ opacity: 0.3 }}>·</span>
        <span title="Maximum Adverse Excursion — worst unrealized PnL during the trade">
          MAE{' '}
          <strong style={{ color: 'var(--red-2)', fontWeight: 800 }}>
            -{trade.max_adverse.toFixed(2)}
          </strong>
        </span>
        <span style={{ opacity: 0.3 }}>·</span>
        <span>
          Held{' '}
          <strong style={{ color: 'var(--fg)', fontWeight: 800 }}>
            {fmtDuration(durationSec)}
          </strong>
        </span>
        {trade.targets_hit && trade.targets_hit.length > 0 && (
          <>
            <span style={{ opacity: 0.3 }}>·</span>
            <span>
              Targets{' '}
              <strong style={{ color: 'var(--green-soft)', fontWeight: 800 }}>
                {trade.targets_hit.join(', ')}
              </strong>
            </span>
          </>
        )}
      </div>
    </Modal>
  );
}
