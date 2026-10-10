import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { CandlestickSeries, ColorType, createChart, type UTCTimestamp } from 'lightweight-charts';
import { api } from '@/utils/api';
import { CHART_EXCHANGES, CHART_TIMEFRAMES, formatSetupPrice, parseSetupCandles, setupMarketSymbol,
  type SetupCandle, type SetupChartPlan } from '@/services/scannerSetup';
import './ScannerSetupModal.css';

const colors = { entry: '#22d3ee', stop: '#fb7185', target: '#4ade80' };
const date = (value?: string) => value && Number.isFinite(Date.parse(value))
  ? new Date(value).toLocaleString() : 'Unavailable';

function CandleChart({ candles, plan }: { candles: SetupCandle[]; plan: SetupChartPlan }) {
  const host = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof createChart> | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    if (!host.current) return;
    const element = host.current;
    const chart = createChart(element, {
      width: element.clientWidth, height: element.clientHeight,
      layout: { background: { type: ColorType.Solid, color: '#101712' }, textColor: '#c0cec6', fontSize: 11 },
      grid: { vertLines: { color: '#ffffff08' }, horzLines: { color: '#ffffff0d' } },
      timeScale: { timeVisible: true, secondsVisible: false, rightOffset: 6 },
      rightPriceScale: { scaleMargins: { top: 0.12, bottom: 0.12 } },
      handleScroll: { vertTouchDrag: false },
    });
    chartRef.current = chart;
    const prices = plan.levels.map(level => level.price);
    const minimum = Math.min(...prices, ...candles.map(candle => candle.low));
    const precision = Math.min(12, Math.max(2, 4 - Math.floor(Math.log10(minimum))));
    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#4ade80', downColor: '#fb7185', borderVisible: false,
      wickUpColor: '#4ade80', wickDownColor: '#fb7185',
      priceFormat: { type: 'price', precision, minMove: 10 ** -precision },
      autoscaleInfoProvider: original => {
        const range = original();
        if (!range?.priceRange || !prices.length) return range;
        return { ...range, priceRange: {
          minValue: Math.min(range.priceRange.minValue, ...prices),
          maxValue: Math.max(range.priceRange.maxValue, ...prices),
        } };
      },
    });
    try {
      series.setData(candles.map(candle => ({ ...candle, time: candle.time as UTCTimestamp })));
      plan.levels.forEach(level => series.createPriceLine({
        price: level.price, color: colors[level.kind], lineWidth: 2,
        lineStyle: level.kind === 'entry' ? 0 : 2, axisLabelVisible: true,
        title: level.label.replace('Entry near', 'NEAR').replace('Entry far', 'FAR').toUpperCase(),
      }));
      chart.timeScale().fitContent();
    } catch { setError(true); }
    const observer = new ResizeObserver(() => chart.applyOptions({ width: element.clientWidth, height: element.clientHeight }));
    observer.observe(element);
    return () => { observer.disconnect(); chartRef.current = null; chart.remove(); };
  }, [candles, plan]);
  return <>
    <div ref={host} className="setup-chart" role="img"
      aria-label="Candlestick chart with saved entry, stop and target levels. Exact prices are listed below." />
    {error && <p role="alert">Chart could not be drawn. Saved levels are listed below.</p>}
    <button className="btn" onClick={() => {
      chartRef.current?.priceScale('right').applyOptions({ autoScale: true });
      chartRef.current?.timeScale().fitContent();
    }}>Fit candles and levels</button>
  </>;
}

/** Keyed by selected feed, so late responses can never populate another chart. */
function SetupCandles({ plan, timeframe, exchange, marketType }: {
  plan: SetupChartPlan; timeframe: string; exchange: string; marketType: string;
}) {
  const [reload, setReload] = useState(0);
  const [state, setState] = useState<{ candles?: SetupCandle[]; error?: string; receivedAt?: string }>({});
  useEffect(() => {
    let current = true;
    setState({});
    void Promise.resolve().then(() => api.getCandles(setupMarketSymbol(plan.symbol, marketType), timeframe, 160, { exchange, marketType })).then(response => {
      if (!current) return;
      if (response.error) throw new Error(response.error);
      const candles = parseSetupCandles(response.data);
      setState({ candles, receivedAt: new Date().toISOString() });
    }).catch(error => {
      if (current) setState({ error: error instanceof Error ? error.message : 'Candle request failed.' });
    });
    return () => { current = false; };
  }, [plan.symbol, timeframe, exchange, marketType, reload]);
  return <div className="setup-candles">
    {!state.candles && !state.error && <div className="setup-chart-message" role="status">Loading {exchange} {timeframe} candles…</div>}
    {state.error && <div className="setup-chart-message" role="alert">
      <p>Candles unavailable for {exchange} {marketType}.</p><p>{state.error}</p>
      <button className="btn" onClick={() => setReload(value => value + 1)}>Retry candles</button>
    </div>}
    {state.candles && <>
      <CandleChart candles={state.candles} plan={plan} />
      <p className="setup-chart-caption">Candle times are UTC. Latest bar: {new Date(state.candles[state.candles.length - 1].time * 1000).toISOString().replace('T', ' ').replace('.000Z', ' UTC')}.
        {' '}Loaded {date(state.receivedAt)}. <button className="btn" onClick={() => setReload(value => value + 1)}>Refresh candles</button></p>
    </>}
  </div>;
}

export function ScannerSetupModal({ plan, symbol, direction, rationale, onClose }: {
  plan: SetupChartPlan; symbol: string; direction: string; rationale?: string; onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [timeframe, setTimeframe] = useState(plan.timeframe ?? '1h');
  const [exchange, setExchange] = useState(plan.exchange ?? 'phemex');
  const [marketType, setMarketType] = useState(plan.marketType ?? 'swap');
  useEffect(() => {
    const element = dialog.current!;
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    element.showModal();
    document.body.style.overflow = 'hidden';
    return () => {
      element.close(); document.body.style.overflow = previousOverflow;
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, []);
  const sourceKnown = !!plan.exchange && !!plan.marketType;
  return createPortal(<dialog ref={dialog} className="scanner-setup-dialog" aria-labelledby="setup-chart-title"
    onCancel={event => { event.preventDefault(); onClose(); }}
    onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="scanner-setup-dialog__body">
      <header className="setup-chart-header">
        <div><h2 id="setup-chart-title">{symbol} <span style={{ color: direction === 'LONG' ? colors.target : colors.stop }}>{direction}</span></h2>
          <p>Saved setup · {date(plan.recordedAt)}</p></div>
        <button autoFocus className="btn" onClick={onClose} aria-label="Close setup chart">Close ×</button>
      </header>
      <div className="setup-chart-controls">
        <label>Chart timeframe <select value={timeframe} onChange={event => setTimeframe(event.target.value)}>
          {CHART_TIMEFRAMES.map(tf => <option key={tf} value={tf}>{tf}{tf === plan.timeframe ? ' · setup' : ''}</option>)}
        </select></label>
        {sourceKnown ? <span>{exchange.toUpperCase()} · {marketType === 'swap' ? 'Perpetual' : marketType}</span> : <>
          <label>Chart exchange <select value={exchange} onChange={event => setExchange(event.target.value)}>
            {[...new Set([...CHART_EXCHANGES, exchange])].map(value => <option key={value}>{value}</option>)}
          </select></label>
          <label>Chart market <select value={marketType} onChange={event => setMarketType(event.target.value)}>
            <option value="swap">Perpetual</option><option value="spot">Spot</option>
          </select></label>
        </>}
      </div>
      {!sourceKnown && <p className="setup-chart-notice">This older result did not save its full market source. The chart uses the source selected above; confirm it matches your setup.</p>}
      {!plan.timeframe && <p className="setup-chart-notice">Setup timeframe was not recorded. Viewing {timeframe} candles.</p>}
      <p className="setup-chart-caption">Latest available candles with the original scan’s levels. Changing the chart timeframe does not recalculate the setup.</p>
      <SetupCandles key={`${exchange}:${marketType}:${timeframe}`} plan={plan} timeframe={timeframe} exchange={exchange} marketType={marketType} />
      <section aria-label="Saved plan prices" className="setup-levels">
        {plan.levels.map((level, index) => <div key={`${level.label}:${index}`} style={{ borderColor: colors[level.kind] }}>
          <span>{level.label}</span><strong>{formatSetupPrice(level.price)}</strong>
        </div>)}
        {!plan.levels.length && <p>Plan prices were not recorded.</p>}
      </section>
      <section className="setup-rationale" aria-label="Setup rationale">
        <h3>Setup rationale</h3>
        <p>{rationale || 'No rationale was supplied with this result.'}</p>
      </section>
    </div>
  </dialog>, document.body);
}
