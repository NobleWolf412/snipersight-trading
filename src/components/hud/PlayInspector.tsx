/**
 * Play Inspector: the one chart modal for scanner setups, open positions,
 * pending entries and closed trades. Read-only; plan editing builds on
 * playMetrics so edited levels reuse the same arithmetic.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import {
  CandlestickSeries, ColorType, createChart, createSeriesMarkers,
  type IChartApi, type ISeriesApi, type ISeriesMarkersPluginApi, type SeriesMarker, type Time, type UTCTimestamp,
} from 'lightweight-charts';
import { api } from '@/utils/api';
import {
  CHART_EXCHANGES, CHART_TIMEFRAMES, TIMEFRAME_SECONDS, chartMarketSymbol, formatMoney, formatPct, formatPrice,
  parsePlayCandles, playMetrics, snapToCandle, type LevelKind, type Play, type PlayCandle,
} from '@/services/playInspector';
import { Chip, type ChipKind } from './Chip';
import { Modal } from './Modal';
import './PlayInspector.css';

const LINE: Record<LevelKind, { color: string; style: number; width: 1 | 2 }> = {
  entry: { color: '#22d3ee', style: 0, width: 2 },
  stop: { color: '#f87171', style: 2, width: 2 },
  target: { color: '#4ade80', style: 2, width: 2 },
  mark: { color: '#a8b5b0', style: 0, width: 1 },
  exit: { color: '#fbbf24', style: 0, width: 2 },
};
const STATUS_CHIP: Record<Play['source'], ChipKind> = { setup: 'cyan', position: 'green', pending: 'blue', closed: 'amber' };

function PlayChart({ play, candles, children }: { play: Play; candles: PlayCandle[]; children?: ReactNode }) {
  const host = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const pricesRef = useRef<number[]>([]);
  const [ready, setReady] = useState(0);
  const [drawError, setDrawError] = useState(false);
  const [missingMarkers, setMissingMarkers] = useState(false);
  pricesRef.current = play.levels.map(level => level.price);
  // Candles own the chart; live status polls only redraw levels, so zoom survives.
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const chart = createChart(element, {
      width: element.clientWidth, height: element.clientHeight,
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#c0cec6', fontSize: 11, fontFamily: '"JetBrains Mono", monospace' },
      grid: { vertLines: { color: '#ffffff08' }, horzLines: { color: '#ffffff0d' } },
      timeScale: { timeVisible: true, secondsVisible: false, rightOffset: 6, borderColor: '#ffffff14' },
      rightPriceScale: { scaleMargins: { top: 0.12, bottom: 0.12 }, borderColor: '#ffffff14' },
      handleScroll: { vertTouchDrag: false },
      crosshair: { mode: 1 },
    });
    const minimum = Math.min(...pricesRef.current, ...candles.map(candle => candle.low));
    const precision = Math.min(12, Math.max(2, 4 - Math.floor(Math.log10(minimum))));
    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#4ade80', downColor: '#f87171', borderVisible: false, wickUpColor: '#4ade80', wickDownColor: '#f87171',
      priceLineVisible: false, // MARK carries current price; an unlabeled last-close line reads as a plan level
      priceFormat: { type: 'price', precision, minMove: 10 ** -precision },
      autoscaleInfoProvider: original => {
        const range = original();
        const prices = pricesRef.current;
        if (!range?.priceRange || !prices.length) return range;
        return { ...range, priceRange: { minValue: Math.min(range.priceRange.minValue, ...prices), maxValue: Math.max(range.priceRange.maxValue, ...prices) } };
      },
    });
    chartRef.current = chart; seriesRef.current = series; markersRef.current = createSeriesMarkers(series, []);
    try {
      series.setData(candles.map(candle => ({ ...candle, time: candle.time as UTCTimestamp })));
      chart.timeScale().fitContent();
    } catch { setDrawError(true); }
    setReady(value => value + 1);
    const observer = new ResizeObserver(() => chart.applyOptions({ width: element.clientWidth, height: element.clientHeight }));
    observer.observe(element);
    return () => {
      observer.disconnect(); chart.remove();
      chartRef.current = null; seriesRef.current = null; markersRef.current = null;
    };
  }, [candles]);
  const levelsKey = JSON.stringify(play.levels);
  const markersKey = JSON.stringify(play.markers);
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    const lines = (JSON.parse(levelsKey) as Play['levels']).map(level => series.createPriceLine({
      price: level.price, color: LINE[level.kind].color, lineWidth: LINE[level.kind].width,
      lineStyle: LINE[level.kind].style, axisLabelVisible: true, title: level.label.toUpperCase(),
    }));
    const times = candles.map(candle => candle.time);
    const bar = TIMEFRAME_SECONDS[play.timeframe] ?? 3600;
    const long = play.direction === 'LONG';
    const markers: SeriesMarker<Time>[] = [];
    let missing = false;
    for (const marker of JSON.parse(markersKey) as Play['markers']) {
      const time = snapToCandle(marker.time, times, bar);
      if (time === undefined) { missing = true; continue; }
      const entry = marker.kind === 'entry';
      markers.push({
        time: time as UTCTimestamp, text: entry ? 'ENTRY' : 'EXIT',
        position: play.direction === 'UNKNOWN' ? 'inBar' : entry === long ? 'belowBar' : 'aboveBar',
        shape: play.direction === 'UNKNOWN' ? 'circle' : entry === long ? 'arrowUp' : 'arrowDown',
        color: entry ? LINE.entry.color : LINE.exit.color,
      });
    }
    markersRef.current?.setMarkers(markers.sort((a, b) => Number(a.time) - Number(b.time)));
    setMissingMarkers(missing);
    // The chart effect may already have disposed this series (unmount or new candles).
    return () => { if (seriesRef.current === series) lines.forEach(line => series.removePriceLine(line)); };
  }, [ready, levelsKey, markersKey, candles, play.timeframe, play.direction]);
  return <>
    <div ref={host} className="play-chart" role="img"
      aria-label={`${play.symbol} candlestick chart with ${play.levels.map(level => level.label).join(', ')}. Exact prices are listed below.`} />
    {drawError && <p className="play-notice" role="alert">Chart could not be drawn. Levels are listed below.</p>}
    {missingMarkers && <p className="play-notice">Entry or exit time is outside the loaded candles; its marker is not shown.</p>}
    <div className="play-chart-bar">
      {children}
      <button className="btn" onClick={() => {
        chartRef.current?.priceScale('right').applyOptions({ autoScale: true });
        chartRef.current?.timeScale().fitContent();
      }}>Fit</button>
    </div>
  </>;
}

/** Keyed by feed, so a late response can never populate another chart. */
function PlayCandles({ play, timeframe, exchange, marketType }: { play: Play; timeframe: string; exchange?: string; marketType?: string }) {
  const [reload, setReload] = useState(0);
  const [state, setState] = useState<{ candles?: PlayCandle[]; error?: string }>({});
  const limit = play.source === 'closed' ? 500 : 200;
  useEffect(() => {
    let current = true;
    setState({});
    void Promise.resolve().then(() => exchange && marketType
      ? api.getCandles(chartMarketSymbol(play.symbol, marketType), timeframe, limit, { exchange, marketType })
      : api.getCandles(play.symbol, timeframe, limit)).then(response => {
      if (!current) return;
      if (response.error) throw new Error(response.error);
      setState({ candles: parsePlayCandles(response.data) });
    }).catch(error => {
      if (current) setState({ error: error instanceof Error ? error.message : 'Candle request failed.' });
    });
    return () => { current = false; };
  }, [play.symbol, timeframe, exchange, marketType, limit, reload]);
  const feed = exchange && marketType ? `${exchange.toUpperCase()} ${marketType === 'swap' ? 'perpetual' : marketType}` : 'session feed';
  return <div className="play-candles">
    {!state.candles && !state.error && <div className="play-chart-message" role="status">Loading {timeframe} candles ({feed})…</div>}
    {state.error && <div className="play-chart-message" role="alert">
      <p>Candles unavailable ({feed}).</p><p>{state.error}</p>
      <button className="btn" onClick={() => setReload(value => value + 1)}>Retry</button>
    </div>}
    {state.candles && <PlayChart play={play} candles={state.candles}>
      <p className="play-caption">UTC candles · {feed} · latest bar {new Date(state.candles[state.candles.length - 1].time * 1000).toISOString().slice(0, 16).replace('T', ' ')}</p>
      <button className="btn" onClick={() => setReload(value => value + 1)}>Refresh</button>
    </PlayChart>}
  </div>;
}

function Tile({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: 'green' | 'red' | 'amber' | 'cyan' }) {
  return <div className="metric-tile play-tile">
    <span className="play-tile__label">{label}</span>
    <strong className={tone ? `play-tone-${tone}` : undefined}>{value}</strong>
    {sub && <span className="play-tile__sub">{sub}</span>}
  </div>;
}

export function PlayInspector({ play, onClose }: { play: Play; onClose: () => void }) {
  const [timeframe, setTimeframe] = useState(play.timeframe);
  const [exchange, setExchange] = useState(play.exchange ?? 'phemex');
  const [marketType, setMarketType] = useState(play.marketType ?? 'swap');
  const chooseSource = play.source === 'setup' && (!play.exchange || !play.marketType);
  const metrics = playMetrics(play.direction, play.levels, play.quantity, play.currentPrice);
  const riskAmount = play.riskAmount ?? metrics.riskAmount;
  const long = play.direction === 'LONG';
  const delta = play.score !== undefined && play.threshold !== undefined ? play.score - play.threshold : undefined;
  const header = <div className="play-head">
    <h2 className="play-head__symbol">{play.symbol || 'Unknown market'}</h2>
    <Chip kind={play.direction === 'UNKNOWN' ? 'amber' : long ? 'green' : 'red'}>{play.direction === 'UNKNOWN' ? 'SIDE UNKNOWN' : play.direction}</Chip>
    <Chip kind={STATUS_CHIP[play.source]}>{play.status}</Chip>
    {play.account && <Chip kind={play.account === 'LIVE' ? 'red' : 'amber'}>{play.account}</Chip>}
    {play.mode && <Chip kind="purple">{play.mode}</Chip>}
    {play.tradeType && <Chip>{play.tradeType}</Chip>}
  </div>;
  return <Modal label={`${play.symbol} ${play.direction} play`} onClose={onClose} maxWidth={1120} className="play-dialog" header={header}>
    <div className="play-body">
      <section className="play-chart-section" aria-label="Chart">
        <div className="play-controls">
          <label>Timeframe <select value={timeframe} onChange={event => setTimeframe(event.target.value)}>
            {CHART_TIMEFRAMES.map(tf => <option key={tf} value={tf}>{tf}{tf === play.timeframe && play.timeframeRecorded ? ' · plan' : ''}</option>)}
          </select></label>
          {chooseSource && <>
            <label>Exchange <select value={exchange} onChange={event => setExchange(event.target.value)}>
              {[...new Set([...CHART_EXCHANGES, exchange])].map(value => <option key={value}>{value}</option>)}
            </select></label>
            <label>Market <select value={marketType} onChange={event => setMarketType(event.target.value)}>
              <option value="swap">Perpetual</option><option value="spot">Spot</option>
            </select></label>
          </>}
        </div>
        {play.source === 'setup' && <p className="play-caption">Latest candles with the saved scan levels. Changing the timeframe does not recalculate the plan.</p>}
        <PlayCandles key={`${exchange}:${marketType}:${timeframe}`} play={play} timeframe={timeframe}
          exchange={play.source === 'setup' ? exchange : undefined} marketType={play.source === 'setup' ? marketType : undefined} />
      </section>

      <section className="play-tiles" aria-label="Play metrics">
        {play.pnl && <Tile label={`${play.pnl.label} P&L`} value={formatMoney(play.pnl.value)}
          sub={play.pnl.pct !== undefined ? formatPct(play.pnl.pct) : undefined} tone={play.pnl.value >= 0 ? 'green' : 'red'} />}
        <Tile label="Best R:R" value={metrics.bestRR !== undefined ? `1 : ${metrics.bestRR.toFixed(2)}` : 'Unknown'}
          sub={metrics.targets.length ? `${metrics.targets.length} target${metrics.targets.length > 1 ? 's' : ''}` : 'No targets'} />
        <Tile label="Risk at stop" value={riskAmount !== undefined ? `$${riskAmount.toFixed(2)}` : 'Unknown'}
          sub={metrics.riskPct !== undefined ? `${metrics.riskPct.toFixed(2)}% from entry` : undefined} tone={riskAmount !== undefined ? 'red' : undefined} />
        {metrics.stopDistancePct !== undefined && <Tile label="Mark to stop" value={`${metrics.stopDistancePct.toFixed(2)}%`}
          tone={metrics.stopDistancePct < 0 ? 'red' : undefined} />}
        {play.quantity !== undefined && <Tile label="Size" value={String(play.quantity)} />}
        <Tile label="Score" value={play.score !== undefined ? `${play.score.toFixed(1)} / 100` : 'Unknown'}
          sub={play.threshold !== undefined ? `Gate ${play.threshold}${delta !== undefined ? ` · ${delta >= 0 ? '+' : ''}${delta.toFixed(1)}` : ''}` : 'Gate unknown'}
          tone={delta === undefined ? undefined : delta >= 0 ? 'green' : 'red'} />
      </section>

      {!!play.warnings.length && <section className="play-warnings" aria-label="Notices">
        {play.warnings.map(warning => <p key={warning} className="play-notice">{warning}</p>)}
      </section>}

      <section className="play-section" aria-labelledby="play-levels-title">
        <h3 id="play-levels-title" className="sec-title">Levels</h3>
        {play.levels.length ? <div className="play-levels">
          {play.levels.map((level, index) => {
            const target = metrics.targets.find(candidate => candidate.label === level.label && candidate.price === level.price);
            const fromEntry = metrics.entry && level.kind !== 'entry' ? (level.price - metrics.entry) / metrics.entry * 100 : undefined;
            return <div key={`${level.label}:${index}`} className={`play-level play-level--${level.kind}`}>
              <span>{level.label}</span>
              <strong>{formatPrice(level.price)}</strong>
              <span className="play-level__meta">
                {fromEntry !== undefined ? formatPct(fromEntry) : ''}
                {target?.rr !== undefined ? ` · ${target.rr.toFixed(2)}R` : ''}
                {target?.reward !== undefined ? ` · ${formatMoney(target.reward)}` : ''}
              </span>
            </div>;
          })}
        </div> : <p className="play-caption">No plan prices were recorded.</p>}
      </section>

      {!!play.facts.length && <section className="play-section" aria-labelledby="play-facts-title">
        <h3 id="play-facts-title" className="sec-title">State</h3>
        <dl className="play-facts">
          {play.facts.map(fact => <div key={fact.label}><dt>{fact.label}</dt><dd className={fact.tone ? `play-tone-${fact.tone}` : undefined}>{fact.value}</dd></div>)}
        </dl>
      </section>}

      <section className="play-section" aria-labelledby="play-why-title">
        <h3 id="play-why-title" className="sec-title">Why</h3>
        <p className="play-rationale">{play.rationale || 'No rationale was recorded for this play.'}</p>
        {play.recordedAt && <p className="play-caption">Recorded {new Date(play.recordedAt).toLocaleString()}</p>}
      </section>
    </div>
  </Modal>;
}
