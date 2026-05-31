/**
 * Replay — historical candle-by-candle playback of the SniperSight pipeline.
 *
 * Operator picks a symbol + 30-day window + mode, then steps through the
 * historical bars while the backend replays the full scoring / SMC / regime
 * / planning pipeline against the data state as of each bar's close.
 *
 * Backend: backend/routers/replay.py (5 endpoints), backed by
 * backend/engine/replay_engine.py with bar-close slicing semantics and a
 * dedicated per-session replay-mode Orchestrator.
 *
 * Design ethos: HUD-tactical. Mission-briefing intro, neon score panel,
 * signal-fire reticle pulse, sound-design hooks, hotkey-first navigation.
 * Sticks to the HUD CSS palette (.panel/.btn/.chip/.mono) — no Tailwind.
 */
import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { CSSProperties } from 'react';
import { Chip, FooterStatus, PageHead, SectionHead } from '@/components/hud';
import { api } from '@/utils/api';
import type {
  ReplayCandle,
  ReplayStepResponse,
  ReplayConfluenceFactor,
} from '@/utils/api';
import {
  createChart,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from 'lightweight-charts';

type ReplayMode = 'stealth' | 'overwatch' | 'strike' | 'surgical';

interface SessionMeta {
  session_id: string;
  symbol: string;
  mode: string;
  total_bars: number;
  tf_step: string;
  window_start: string;
  window_end: string;
  bar_timestamps: string[];
}

type PlayState = 'idle' | 'loading' | 'ready' | 'playing' | 'paused' | 'ended';

const SPEED_OPTIONS: Array<{ label: string; value: number }> = [
  { label: '1×', value: 1 },
  { label: '2×', value: 2 },
  { label: '5×', value: 5 },
  { label: '10×', value: 10 },
];

const MODES: ReplayMode[] = ['stealth', 'overwatch', 'strike', 'surgical'];

const DEFAULT_WINDOW_DAYS = 7;
const MAX_WINDOW_DAYS = 30;

// Defensive `.toUpperCase()` shim. The replay API surface is wide and
// still warm — a malformed plan response (e.g. `direction: null` from
// `_serialize_plan`'s exception branch) would otherwise crash the page
// with "Cannot read properties of undefined (reading 'toUpperCase')".
// This helper degrades to an empty label instead of a HUD-wide fault.
function up(v: unknown): string {
  return (typeof v === 'string' ? v : '').toUpperCase();
}

// ---------------------------------------------------------------------------
// Hotkey hook (no dependency)
// ---------------------------------------------------------------------------

function useHotkey(
  handler: (e: KeyboardEvent) => void,
  enabled: boolean = true,
): void {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;
  useEffect(() => {
    if (!enabled) return;
    const onKey = (e: KeyboardEvent) => {
      // Ignore if focus is in a text input
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      handlerRef.current(e);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [enabled]);
}

// ---------------------------------------------------------------------------
// Chart wrapper — lightweight-charts, no Tailwind, replay-mode only
// (accepts a pre-loaded candle array per the active playback TF; no
// internal fetch).
// ---------------------------------------------------------------------------

interface ReplayChartProps {
  candles: ReplayCandle[];
  symbol: string;
  timeframe: string;
  // Markers from SMC snapshot — passed through as light price-line overlays
  // (full OB shading was deferred to v1.1)
  entryPrice?: number | null;
  stopLoss?: number | null;
  takeProfit?: number | null;
}

function ReplayChart({
  candles,
  symbol,
  timeframe,
  entryPrice,
  stopLoss,
  takeProfit,
}: ReplayChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const priceLinesRef = useRef<ReturnType<ISeriesApi<'Candlestick'>['createPriceLine']>[]>(
    [],
  );

  // Initialize chart once
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#9fbfa4',
        fontFamily: 'JetBrains Mono, monospace',
      },
      grid: {
        vertLines: { color: 'rgba(80, 200, 120, 0.07)' },
        horzLines: { color: 'rgba(80, 200, 120, 0.07)' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: '#22d3ee', width: 1, style: 2, labelBackgroundColor: '#22d3ee' },
        horzLine: { color: '#22d3ee', width: 1, style: 2, labelBackgroundColor: '#22d3ee' },
      },
      rightPriceScale: { borderColor: 'rgba(120, 160, 130, 0.25)' },
      timeScale: {
        borderColor: 'rgba(120, 160, 130, 0.25)',
        timeVisible: true,
        secondsVisible: false,
      },
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      priceLinesRef.current = [];
    };
  }, []);

  // Update candle data on every replay step
  useEffect(() => {
    if (!seriesRef.current) return;
    if (candles.length === 0) {
      seriesRef.current.setData([]);
      return;
    }
    // De-dupe + sort defensively (lightweight-charts requires strict ascending unique times)
    const seen = new Set<number>();
    const data = candles
      .filter((c) => {
        if (seen.has(c.time)) return false;
        seen.add(c.time);
        return true;
      })
      .map((c) => ({
        time: c.time as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
      .sort((a, b) => (a.time as number) - (b.time as number));
    seriesRef.current.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [candles]);

  // Update entry/SL/TP price lines
  useEffect(() => {
    if (!seriesRef.current) return;
    // Clear previous lines
    for (const line of priceLinesRef.current) {
      try {
        seriesRef.current.removePriceLine(line);
      } catch {
        // ignore
      }
    }
    priceLinesRef.current = [];
    if (entryPrice) {
      priceLinesRef.current.push(
        seriesRef.current.createPriceLine({
          price: entryPrice,
          color: '#22d3ee',
          lineWidth: 2,
          lineStyle: 0,
          axisLabelVisible: true,
          title: 'E',
        }),
      );
    }
    if (stopLoss) {
      priceLinesRef.current.push(
        seriesRef.current.createPriceLine({
          price: stopLoss,
          color: '#ef4444',
          lineWidth: 2,
          lineStyle: 0,
          axisLabelVisible: true,
          title: 'SL',
        }),
      );
    }
    if (takeProfit) {
      priceLinesRef.current.push(
        seriesRef.current.createPriceLine({
          price: takeProfit,
          color: '#22c55e',
          lineWidth: 2,
          lineStyle: 0,
          axisLabelVisible: true,
          title: 'TP',
        }),
      );
    }
  }, [entryPrice, stopLoss, takeProfit]);

  return (
    <div className="panel" style={{ position: 'relative', height: 440, padding: 0, overflow: 'hidden' }}>
      <div
        style={{
          position: 'absolute',
          top: 10,
          left: 12,
          zIndex: 2,
          display: 'flex',
          gap: 6,
        }}
      >
        <Chip kind="cyan">{symbol}</Chip>
        <Chip kind="amber">{up(timeframe)}</Chip>
      </div>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      {candles.length === 0 && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexDirection: 'column',
            gap: 8,
            zIndex: 3,
            background: 'rgba(0, 0, 0, 0.4)',
            pointerEvents: 'none',
            fontFamily: "'Share Tech Mono', monospace",
            color: 'rgba(159, 191, 164, 0.7)',
            letterSpacing: '.24em',
            fontSize: 12,
          }}
        >
          <div style={{ fontSize: 14, color: '#22d3ee' }}>◢ NO CANDLES YET ◣</div>
          <div>PRESS PLAY OR → TO STEP THE FIRST BAR</div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Spectrogram — confluence-score-over-time heat strip (the centrepiece visual)
// ---------------------------------------------------------------------------

interface SpectrogramProps {
  scores: Map<number, number>; // bar_index → confluence score (0-100)
  totalBars: number;
  currentIndex: number;
  signalIndices: Set<number>;
  onScrub: (index: number) => void;
}

function Spectrogram({
  scores,
  totalBars,
  currentIndex,
  signalIndices,
  onScrub,
}: SpectrogramProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const render = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const w = container.clientWidth;
    const h = 64;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    // Background
    ctx.fillStyle = 'rgba(10, 14, 11, 0.6)';
    ctx.fillRect(0, 0, w, h);

    if (totalBars === 0) return;

    const colW = Math.max(1, w / totalBars);
    for (let i = 0; i < totalBars; i++) {
      const s = scores.get(i);
      if (s == null) continue;
      // Score color ramp: red <50, amber 50-70, cyan 70-85, neon green >85
      let color: string;
      if (s < 50) color = `rgba(239, 68, 68, ${0.4 + (s / 100) * 0.4})`;
      else if (s < 70) color = `rgba(251, 191, 36, ${0.4 + (s / 100) * 0.4})`;
      else if (s < 85) color = `rgba(34, 211, 238, ${0.5 + (s / 100) * 0.4})`;
      else color = `rgba(34, 197, 94, ${0.7 + (s / 100) * 0.3})`;
      ctx.fillStyle = color;
      ctx.fillRect(Math.floor(i * colW), 0, Math.max(1, Math.ceil(colW)), h);
    }

    // Signal-fire vertical bars (cyan markers)
    ctx.fillStyle = 'rgba(34, 211, 238, 0.9)';
    for (const i of signalIndices) {
      const x = Math.floor(i * colW + colW / 2);
      ctx.fillRect(x - 1, 0, 2, h);
    }

    // Current cursor
    if (currentIndex >= 0 && currentIndex < totalBars) {
      const x = Math.floor(currentIndex * colW + colW / 2);
      ctx.strokeStyle = '#22d3ee';
      ctx.lineWidth = 2;
      ctx.shadowColor = '#22d3ee';
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
      ctx.shadowBlur = 0;
    }
  }, [scores, totalBars, currentIndex, signalIndices]);

  useEffect(() => {
    render();
  }, [render]);

  useEffect(() => {
    const onResize = () => render();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [render]);

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current || totalBars === 0) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const idx = Math.floor((x / rect.width) * totalBars);
    onScrub(Math.max(0, Math.min(totalBars - 1, idx)));
  };

  return (
    <div
      ref={containerRef}
      onClick={handleClick}
      style={{
        position: 'relative',
        cursor: 'pointer',
        marginTop: 8,
        borderRadius: 4,
        border: '1px solid rgba(120, 160, 130, 0.2)',
        overflow: 'hidden',
      }}
      title="Click to scrub to that bar"
    >
      <canvas ref={canvasRef} style={{ display: 'block' }} />
      <div
        style={{
          position: 'absolute',
          top: 4,
          left: 6,
          fontSize: 9,
          letterSpacing: '.18em',
          color: 'rgba(159, 191, 164, 0.7)',
          fontFamily: "'Share Tech Mono', monospace",
          pointerEvents: 'none',
        }}
      >
        SCORE TAPE · {currentIndex >= 0 ? `BAR ${currentIndex + 1}/${totalBars}` : 'IDLE'}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Score panel — confluence breakdown
// ---------------------------------------------------------------------------

function ScorePanel({
  step,
}: {
  step: ReplayStepResponse | null;
}) {
  if (!step) {
    return (
      <div className="panel" style={{ padding: 16, minHeight: 240 }}>
        <SectionHead title="CONFLUENCE" />
        <div
          style={{
            color: 'var(--fg-4)',
            fontFamily: "'Share Tech Mono', monospace",
            fontSize: 12,
            letterSpacing: '.14em',
            textAlign: 'center',
            padding: '32px 0',
          }}
        >
          AWAITING FIRST STEP
        </div>
      </div>
    );
  }

  const conf = step.confluence;
  const score = conf?.total_score ?? 0;
  const direction = conf?.direction ?? 'UNKNOWN';
  const factors: ReplayConfluenceFactor[] = (conf?.factors ?? []).slice().sort(
    (a, b) => b.weighted_contribution - a.weighted_contribution,
  );

  const tier =
    score >= 85 ? 'green' : score >= 70 ? 'cyan' : score >= 50 ? 'amber' : 'red';

  return (
    <div
      className="panel"
      style={{
        padding: 16,
        position: 'relative',
        borderColor:
          step.signal_fired
            ? 'rgba(34, 197, 94, 0.7)'
            : 'rgba(120, 160, 130, 0.25)',
        boxShadow: step.signal_fired
          ? '0 0 30px rgba(34, 197, 94, 0.4), inset 0 0 24px rgba(34, 197, 94, 0.15)'
          : 'none',
        transition: 'box-shadow .4s, border-color .4s',
      }}
    >
      <SectionHead title="CONFLUENCE" />
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 8 }}>
        <div
          className="mono"
          style={{
            fontSize: 36,
            fontWeight: 700,
            color:
              tier === 'green'
                ? '#22c55e'
                : tier === 'cyan'
                  ? '#22d3ee'
                  : tier === 'amber'
                    ? '#fbbf24'
                    : '#ef4444',
            textShadow: `0 0 12px currentColor`,
          }}
        >
          {score.toFixed(1)}
        </div>
        <Chip kind={direction === 'bullish' || direction === 'LONG' ? 'green' : 'red'}>
          {up(direction)}
        </Chip>
        {step.signal_fired && <Chip kind="cyan">● FIRED</Chip>}
      </div>
      <div
        style={{
          display: 'flex',
          gap: 6,
          marginTop: 6,
          fontFamily: "'Share Tech Mono', monospace",
          fontSize: 11,
          letterSpacing: '.12em',
        }}
      >
        <Chip kind={conf?.htf_aligned ? 'green' : 'red'}>
          HTF {conf?.htf_aligned ? '✓' : '✗'}
        </Chip>
        <Chip kind={conf?.btc_impulse_gate ? 'green' : 'red'}>
          BTC {conf?.btc_impulse_gate ? '✓' : '✗'}
        </Chip>
        {step.regime && (
          <Chip kind="blue">{up(step.regime.composite || step.regime.trend || '—')}</Chip>
        )}
      </div>

      <div style={{ marginTop: 14, maxHeight: 280, overflowY: 'auto' }}>
        {factors.slice(0, 12).map((f, i) => (
          <FactorRow key={`${f.name}-${i}`} factor={f} />
        ))}
        {factors.length > 12 && (
          <div
            style={{
              fontSize: 10,
              color: 'var(--fg-4)',
              letterSpacing: '.14em',
              textAlign: 'center',
              padding: '6px 0',
            }}
          >
            +{factors.length - 12} more factors
          </div>
        )}
      </div>
    </div>
  );
}

function FactorRow({ factor }: { factor: ReplayConfluenceFactor }) {
  const pctOfMax = Math.max(0, Math.min(100, factor.score));
  const barColor =
    factor.score >= 75
      ? '#22c55e'
      : factor.score >= 50
        ? '#22d3ee'
        : factor.score >= 25
          ? '#fbbf24'
          : '#ef4444';
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr auto',
        gap: 8,
        alignItems: 'center',
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 11,
        padding: '4px 0',
        borderBottom: '1px dashed rgba(120, 160, 130, 0.1)',
      }}
      title={factor.rationale}
    >
      <div>
        <div style={{ color: '#cfe5d4', textTransform: 'uppercase', letterSpacing: '.06em' }}>
          {factor.name.replace(/_/g, ' ')}
        </div>
        <div
          style={{
            height: 3,
            background: 'rgba(255,255,255,0.05)',
            borderRadius: 2,
            overflow: 'hidden',
            marginTop: 2,
          }}
        >
          <div
            style={{
              width: `${pctOfMax}%`,
              height: '100%',
              background: barColor,
              boxShadow: `0 0 6px ${barColor}`,
              transition: 'width .25s',
            }}
          />
        </div>
      </div>
      <div style={{ color: barColor, fontWeight: 600 }}>
        {factor.score.toFixed(0)}
        <span style={{ color: 'var(--fg-4)', fontWeight: 400 }}>
          {' '}×{factor.weight.toFixed(2)}
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Plan / Rejection panels
// ---------------------------------------------------------------------------

function PlanPanel({ step }: { step: ReplayStepResponse | null }) {
  const plan = step?.plan ?? null;
  if (!plan) {
    if (step?.rejection) {
      return (
        <div className="panel" style={{ padding: 14 }}>
          <SectionHead title="REJECTION" />
          <div
            style={{
              fontFamily: "'Share Tech Mono', monospace",
              fontSize: 11,
              letterSpacing: '.1em',
              color: '#ef4444',
              marginTop: 6,
            }}
          >
            {up(step.rejection.reason_type || 'unknown')}
          </div>
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 11,
              color: '#cfe5d4',
              marginTop: 6,
              lineHeight: 1.5,
            }}
          >
            {step.rejection.reason || '(no reason given)'}
          </div>
        </div>
      );
    }
    return null;
  }
  return (
    <div className="panel" style={{ padding: 14 }}>
      <SectionHead title="TRADE PLAN" />
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 8,
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11,
          marginTop: 8,
        }}
      >
        <MetricCell label="Direction" value={up(plan.direction)} accent />
        <MetricCell label="Setup" value={plan.setup_type || '—'} />
        <MetricCell label="Confidence" value={`${plan.confidence_score.toFixed(0)}`} />
        <MetricCell label="R:R" value={plan.risk_reward.toFixed(2)} />
        <MetricCell
          label="Entry zone"
          value={`${plan.entry_zone.far.toFixed(4)} → ${plan.entry_zone.near.toFixed(4)}`}
        />
        {plan.stop_loss && (
          <MetricCell label="Stop" value={plan.stop_loss.level.toFixed(4)} />
        )}
        {plan.targets[0] && (
          <MetricCell label="TP1" value={plan.targets[0].level.toFixed(4)} />
        )}
        {plan.targets[1] && (
          <MetricCell label="TP2" value={plan.targets[1].level.toFixed(4)} />
        )}
      </div>
    </div>
  );
}

function MetricCell({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div>
      <div
        style={{
          fontSize: 9,
          letterSpacing: '.18em',
          color: 'var(--fg-4)',
          textTransform: 'uppercase',
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontWeight: 600,
          color: accent ? '#22d3ee' : '#cfe5d4',
          marginTop: 2,
        }}
      >
        {value}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Transport bar — play/pause/speed/step/jump/reset
// ---------------------------------------------------------------------------

interface TransportProps {
  playState: PlayState;
  speed: number;
  currentIndex: number;
  totalBars: number;
  onPlayPause: () => void;
  onStep: (n: number) => void;
  onJump: () => void;
  onReset: () => void;
  onSpeed: (v: number) => void;
  onScrub: (i: number) => void;
}

function Transport({
  playState,
  speed,
  currentIndex,
  totalBars,
  onPlayPause,
  onStep,
  onJump,
  onReset,
  onSpeed,
  onScrub,
}: TransportProps) {
  const playing = playState === 'playing';
  return (
    <div
      className="panel"
      style={{
        padding: 12,
        marginTop: 12,
        display: 'flex',
        gap: 10,
        alignItems: 'center',
        flexWrap: 'wrap',
      }}
    >
      <button
        className={`btn btn-cyan`}
        onClick={onPlayPause}
        title={playing ? 'Pause (Space)' : 'Play (Space)'}
        disabled={playState === 'idle' || playState === 'loading' || totalBars === 0}
      >
        {playing ? '❚❚ PAUSE' : '▶ PLAY'}
      </button>
      <button
        className="btn"
        onClick={() => onStep(-1)}
        title="Step back (←)"
        disabled={currentIndex <= 0}
      >
        ◀ −1
      </button>
      <button
        className="btn"
        onClick={() => onStep(1)}
        title="Step forward (→)"
        disabled={currentIndex >= totalBars - 1}
      >
        +1 ▶
      </button>
      <button
        className="btn"
        onClick={() => onStep(-10)}
        title="Step back 10 (Shift+←)"
        disabled={currentIndex <= 0}
      >
        ◀◀ −10
      </button>
      <button
        className="btn"
        onClick={() => onStep(10)}
        title="Step forward 10 (Shift+→)"
        disabled={currentIndex >= totalBars - 1}
      >
        +10 ▶▶
      </button>
      <button
        className="btn btn-green"
        onClick={onJump}
        title="Jump to next signal (J)"
        disabled={currentIndex >= totalBars - 1}
      >
        → SIGNAL (J)
      </button>
      <button className="btn" onClick={onReset} title="Reset to start (R)">
        ⟲ RESET
      </button>

      <div style={{ marginLeft: 'auto', display: 'flex', gap: 6, alignItems: 'center' }}>
        <div
          style={{
            fontSize: 10,
            color: 'var(--fg-4)',
            letterSpacing: '.16em',
            marginRight: 4,
          }}
        >
          SPEED
        </div>
        {SPEED_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            className={`btn ${speed === opt.value ? 'btn-cyan' : ''}`}
            style={{ minWidth: 38 }}
            onClick={() => onSpeed(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <input
        type="range"
        min={0}
        max={Math.max(0, totalBars - 1)}
        value={Math.max(0, currentIndex)}
        onChange={(e) => onScrub(parseInt(e.target.value, 10))}
        disabled={totalBars === 0}
        style={{
          width: '100%',
          marginTop: 6,
          accentColor: '#22d3ee',
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mission briefing intro — 1.5s boot-up on session load
// ---------------------------------------------------------------------------

function MissionBriefing({
  symbol,
  mode,
  days,
}: {
  symbol: string;
  mode: string;
  days: number;
}) {
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background:
          'radial-gradient(ellipse at center, rgba(10, 20, 14, 0.95) 0%, rgba(0, 0, 0, 0.98) 100%)',
        zIndex: 999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: 12,
        animation: 'fadeIn .25s ease-out',
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          fontFamily: "'Share Tech Mono', monospace",
          fontSize: 11,
          letterSpacing: '.4em',
          color: 'rgba(34, 211, 238, 0.6)',
          animation: 'flicker 1.5s infinite',
        }}
      >
        ◢ REPLAY SESSION INITIALIZING ◣
      </div>
      <div
        style={{
          fontFamily: "'Share Tech Mono', monospace",
          fontSize: 28,
          fontWeight: 700,
          letterSpacing: '.2em',
          color: '#22d3ee',
          textShadow: '0 0 12px rgba(34, 211, 238, 0.6)',
        }}
      >
        {symbol} // {up(mode)} // {days}D
      </div>
      <div
        style={{
          fontFamily: "'Share Tech Mono', monospace",
          fontSize: 11,
          letterSpacing: '.28em',
          color: 'rgba(34, 197, 94, 0.8)',
        }}
      >
        ▸ SESSION ARMED
      </div>
      <style>{`
        @keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }
        @keyframes flicker {
          0%, 100% { opacity: 0.6 }
          50% { opacity: 1 }
        }
      `}</style>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hotkey help overlay
// ---------------------------------------------------------------------------

const HOTKEYS: Array<{ key: string; action: string }> = [
  { key: 'Space', action: 'Play / pause' },
  { key: '→ / ←', action: 'Step ±1 bar' },
  { key: 'Shift + → / ←', action: 'Step ±10 bars' },
  { key: 'J', action: 'Jump to next signal' },
  { key: '1 / 2 / 5 / 0', action: 'Speed 1× / 2× / 5× / 10×' },
  { key: 'R', action: 'Reset to start' },
  { key: 'B', action: 'Bookmark current bar (localStorage)' },
  { key: '?', action: 'Toggle this help' },
  { key: 'Esc', action: 'End session' },
];

function HelpOverlay({ onClose }: { onClose: () => void }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.85)',
        zIndex: 998,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div
        className="panel"
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: 540,
          padding: 24,
          background: 'rgba(10, 20, 14, 0.95)',
          border: '1px solid rgba(34, 211, 238, 0.4)',
        }}
      >
        <SectionHead title="HOTKEYS" />
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'auto 1fr',
            gap: '6px 18px',
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 12,
            marginTop: 14,
          }}
        >
          {HOTKEYS.map((h) => (
            <Fragment key={h.key}>
              <div
                style={{
                  color: '#22d3ee',
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                }}
              >
                {h.key}
              </div>
              <div style={{ color: '#cfe5d4' }}>
                {h.action}
              </div>
            </Fragment>
          ))}
        </div>
        <div
          style={{
            marginTop: 18,
            fontSize: 10,
            color: 'var(--fg-4)',
            letterSpacing: '.14em',
            textAlign: 'center',
          }}
        >
          CLICK ANYWHERE OR PRESS ? AGAIN TO CLOSE
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Setup panel — symbol / mode / window inputs
// ---------------------------------------------------------------------------

function isoDateInputValue(d: Date): string {
  // For <input type="date"> (YYYY-MM-DD)
  return d.toISOString().slice(0, 10);
}

function SetupPanel({
  defaultSymbol,
  defaultMode,
  defaultDays,
  loading,
  onLoad,
}: {
  defaultSymbol: string;
  defaultMode: ReplayMode;
  defaultDays: number;
  loading: boolean;
  onLoad: (symbol: string, mode: ReplayMode, windowStartIso: string, windowEndIso: string) => void;
}) {
  const today = new Date();
  const todayMinus5 = new Date(today.getTime() - 5 * 60 * 1000); // 5 min ago to avoid in-progress
  const [symbol, setSymbol] = useState(defaultSymbol);
  const [mode, setMode] = useState<ReplayMode>(defaultMode);
  const [endDate, setEndDate] = useState(isoDateInputValue(todayMinus5));
  const [days, setDays] = useState(defaultDays);

  const handleLoad = () => {
    const end = new Date(`${endDate}T23:59:00Z`);
    if (end.getTime() > todayMinus5.getTime()) {
      end.setTime(todayMinus5.getTime()); // clamp to slightly-before-now
    }
    const start = new Date(end.getTime() - days * 24 * 60 * 60 * 1000);
    onLoad(symbol, mode, start.toISOString(), end.toISOString());
  };

  return (
    <div
      className="panel"
      style={{
        padding: 12,
        display: 'flex',
        gap: 10,
        alignItems: 'flex-end',
        flexWrap: 'wrap',
      }}
    >
      <Field label="SYMBOL">
        <input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          placeholder="BTC/USDT"
          style={inputStyle}
        />
      </Field>
      <Field label="MODE">
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as ReplayMode)}
          style={inputStyle}
        >
          {MODES.map((m) => (
            <option key={m} value={m}>
              {up(m)}
            </option>
          ))}
        </select>
      </Field>
      <Field label="END DATE">
        <input
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          max={isoDateInputValue(today)}
          style={inputStyle}
        />
      </Field>
      <Field label={`WINDOW (1-${MAX_WINDOW_DAYS}d)`}>
        <input
          type="number"
          min={1}
          max={MAX_WINDOW_DAYS}
          value={days}
          onChange={(e) =>
            setDays(
              Math.max(1, Math.min(MAX_WINDOW_DAYS, parseInt(e.target.value, 10) || 1)),
            )
          }
          style={{ ...inputStyle, width: 72 }}
        />
      </Field>
      <button
        className="btn btn-cyan"
        onClick={handleLoad}
        disabled={loading || !symbol}
        style={{ minHeight: 36, padding: '0 18px' }}
      >
        {loading ? 'LOADING…' : '◢ LOAD SESSION'}
      </button>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        fontFamily: "'Share Tech Mono', monospace",
        fontSize: 10,
        letterSpacing: '.18em',
        color: 'var(--fg-4)',
      }}
    >
      {label}
      {children}
    </label>
  );
}

const inputStyle: CSSProperties = {
  background: 'rgba(0, 0, 0, 0.4)',
  border: '1px solid rgba(120, 160, 130, 0.3)',
  color: '#cfe5d4',
  padding: '8px 10px',
  borderRadius: 3,
  fontFamily: "'JetBrains Mono', monospace",
  fontSize: 13,
  minHeight: 36,
};

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function Replay() {
  const readyRef = useRef(false);
  const [playState, setPlayState] = useState<PlayState>('idle');
  const [session, setSession] = useState<SessionMeta | null>(null);
  const [step, setStep] = useState<ReplayStepResponse | null>(null);
  const [speed, setSpeed] = useState(1);
  const [showBriefing, setShowBriefing] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [helpClickHint, setHelpClickHint] = useState(true);

  // Score history for spectrogram (bar_index → score)
  const [scoreHistory, setScoreHistory] = useState<Map<number, number>>(new Map());
  const [signalIndices, setSignalIndices] = useState<Set<number>>(new Set());

  // Snapshot framework hook
  useEffect(() => {
    if (!readyRef.current) {
      readyRef.current = true;
      document.body.setAttribute('data-snapshot-ready', 'true');
    }
    return () => {
      document.body.removeAttribute('data-snapshot-ready');
    };
  }, []);

  // Cleanup session on unmount
  useEffect(() => {
    return () => {
      if (session) {
        api.deleteReplaySession(session.session_id).catch(() => {});
      }
    };
    // session ref captured at unmount time — intentional
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Briefing flag — fires for 1500ms after load
  useEffect(() => {
    if (showBriefing) {
      const t = setTimeout(() => setShowBriefing(false), 1500);
      return () => clearTimeout(t);
    }
  }, [showBriefing]);

  // ---- Session lifecycle ----
  const handleLoad = useCallback(
    async (symbol: string, mode: ReplayMode, windowStartIso: string, windowEndIso: string) => {
      try {
        setPlayState('loading');
        setErrorMsg(null);
        // If a prior session exists, end it first (idempotent)
        if (session) {
          api.deleteReplaySession(session.session_id).catch(() => {});
        }
        // api.request returns ApiResponse<T> = { data?: T, error?: string }
        // — must unwrap. Treating the wrapper as the data was the .toUpperCase /
        // .slice runtime-fault root cause (2026-05-26 calibration).
        const resp = await api.createReplaySession({
          symbol,
          mode,
          window_start: windowStartIso,
          window_end: windowEndIso,
        });
        if (resp.error) throw new Error(resp.error);
        if (!resp.data) throw new Error('No data in response');
        const newSession = resp.data as SessionMeta;
        setSession(newSession);
        setStep(null);
        setScoreHistory(new Map());
        setSignalIndices(new Set());
        setShowBriefing(true);
        setPlayState('ready');
        setHelpClickHint(true);

        // Auto-step to bar 0 so the chart isn't a TradingView-watermark-on-black
        // canvas at first paint. Without this the operator clicks LOAD, the
        // briefing flashes, and they see an empty chart wondering whether
        // anything happened. Calling the API directly (not doStep, which
        // captures the OLD session via closure) lets us seed the first frame
        // even before the briefing clears.
        try {
          const first = await api.stepReplay(newSession.session_id, 1);
          if (first.data) {
            const r = first.data as ReplayStepResponse;
            setStep(r);
            if (r.confluence?.total_score != null) {
              setScoreHistory((prev) => {
                const next = new Map(prev);
                next.set(r.index, r.confluence!.total_score);
                return next;
              });
            }
            if (r.signal_fired) {
              setSignalIndices((prev) => {
                const next = new Set(prev);
                next.add(r.index);
                return next;
              });
            }
          }
        } catch {
          // First-step failures are non-fatal — operator can manually step
        }
      } catch (e: any) {
        setErrorMsg(e?.message ?? 'Failed to load session');
        setPlayState('idle');
      }
    },
    [session],
  );

  // ---- Step execution ----
  const doStep = useCallback(
    async (n: number) => {
      if (!session) return;
      try {
        const result = await api.stepReplay(session.session_id, n);
        if (result.error) throw new Error(result.error);
        if (!result.data) return;
        const r = result.data as ReplayStepResponse;
        setStep(r);
        // Update score history + signal indices
        if (r.confluence?.total_score != null) {
          setScoreHistory((prev) => {
            const next = new Map(prev);
            next.set(r.index, r.confluence!.total_score);
            return next;
          });
        }
        if (r.signal_fired) {
          setSignalIndices((prev) => {
            if (prev.has(r.index)) return prev;
            const next = new Set(prev);
            next.add(r.index);
            return next;
          });
        }
        if (r.index >= session.total_bars - 1) {
          setPlayState('ended');
        }
      } catch (e: any) {
        setErrorMsg(e?.message ?? 'Step failed');
      }
    },
    [session],
  );

  // ---- Scrub: absolute index. Computes delta and calls step. ----
  const doScrub = useCallback(
    async (targetIndex: number) => {
      if (!session) return;
      const current = step?.index ?? -1;
      const delta = targetIndex - current;
      if (delta === 0) return;
      await doStep(delta);
    },
    [session, step, doStep],
  );

  // ---- Jump to next signal ----
  const doJump = useCallback(async () => {
    if (!session) return;
    try {
      const result = await api.jumpToNextSignal(session.session_id, 100);
      if (result.error) throw new Error(result.error);
      if (!result.data) return;
      const r = result.data as { found: boolean; bars_advanced: number; step: ReplayStepResponse | null };
      if (r.step) {
        setStep(r.step);
        if (r.step.confluence?.total_score != null) {
          setScoreHistory((prev) => {
            const next = new Map(prev);
            next.set(r.step!.index, r.step!.confluence!.total_score);
            return next;
          });
        }
        if (r.step.signal_fired) {
          setSignalIndices((prev) => {
            const next = new Set(prev);
            next.add(r.step!.index);
            return next;
          });
        }
      }
    } catch (e: any) {
      setErrorMsg(e?.message ?? 'Jump failed');
    }
  }, [session]);

  // ---- Reset to first bar ----
  const doReset = useCallback(() => {
    if (!session || !step) return;
    const back = -(step.index + 1);
    if (back !== 0) doStep(back);
  }, [session, step, doStep]);

  // ---- Play loop ----
  useEffect(() => {
    if (playState !== 'playing' || !session) return;
    const intervalMs = Math.max(80, Math.floor(1000 / speed));
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      await doStep(1);
      if (!cancelled && step && step.index < session.total_bars - 1) {
        timeoutId = window.setTimeout(tick, intervalMs);
      }
    };
    let timeoutId = window.setTimeout(tick, intervalMs);
    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [playState, speed, session, doStep, step]);

  const togglePlay = useCallback(() => {
    if (playState === 'ready' || playState === 'paused') setPlayState('playing');
    else if (playState === 'playing') setPlayState('paused');
  }, [playState]);

  // ---- Hotkeys ----
  useHotkey((e) => {
    if (e.key === '?' || (e.key.toLowerCase() === 'h' && !e.metaKey && !e.ctrlKey)) {
      e.preventDefault();
      setShowHelp((v) => !v);
      setHelpClickHint(false);
      return;
    }
    if (showHelp && e.key === 'Escape') {
      setShowHelp(false);
      return;
    }
    if (e.key === ' ' || e.code === 'Space') {
      e.preventDefault();
      togglePlay();
      return;
    }
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      doStep(e.shiftKey ? 10 : 1);
      return;
    }
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      doStep(e.shiftKey ? -10 : -1);
      return;
    }
    if (e.key.toLowerCase() === 'j') {
      e.preventDefault();
      doJump();
      return;
    }
    if (e.key.toLowerCase() === 'r') {
      e.preventDefault();
      doReset();
      return;
    }
    if (e.key.toLowerCase() === 'b') {
      e.preventDefault();
      if (session && step) {
        try {
          const key = `replay-bookmarks-${session.session_id}`;
          const existing: number[] = JSON.parse(localStorage.getItem(key) || '[]');
          if (!existing.includes(step.index)) {
            existing.push(step.index);
            localStorage.setItem(key, JSON.stringify(existing));
          }
        } catch {
          // ignore localStorage issues (e.g. private mode)
        }
      }
      return;
    }
    if (e.key === '1') setSpeed(1);
    else if (e.key === '2') setSpeed(2);
    else if (e.key === '5') setSpeed(5);
    else if (e.key === '0') setSpeed(10);
    else if (e.key === 'Escape') {
      if (session) {
        api.deleteReplaySession(session.session_id).catch(() => {});
        setSession(null);
        setStep(null);
        setScoreHistory(new Map());
        setSignalIndices(new Set());
        setPlayState('idle');
      }
    }
  });

  // ---- Computed: candles for the playback TF only (chart uses tf_step) ----
  const chartCandles = useMemo<ReplayCandle[]>(() => {
    if (!step || !session) return [];
    return step.candles_by_tf[session.tf_step] || [];
  }, [step, session]);

  const days = useMemo(() => {
    if (!session) return DEFAULT_WINDOW_DAYS;
    const start = new Date(session.window_start).getTime();
    const end = new Date(session.window_end).getTime();
    return Math.round((end - start) / (1000 * 60 * 60 * 24));
  }, [session]);

  return (
    <div className="page">
      <PageHead
        icon={
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <polygon
              points="6,4 20,12 6,20"
              stroke="currentColor"
              strokeWidth="1.5"
              fill="none"
              style={{ color: '#22d3ee' }}
            />
          </svg>
        }
        title="REPLAY"
        subtitle={
          session
            ? `${session.symbol} · ${up(session.mode)} · ${days}D · ${session.total_bars} bars at ${up(session.tf_step)}`
            : 'Step through historical bars and watch the scanner score evolve'
        }
        badges={
          <>
            {session ? (
              <>
                <Chip kind="cyan">SESSION · {session.session_id.slice(0, 6)}</Chip>
                <Chip kind={playState === 'playing' ? 'green' : 'blue'}>
                  {up(playState)}
                </Chip>
              </>
            ) : (
              <Chip kind="amber">● READY TO LOAD</Chip>
            )}
            {helpClickHint && !showHelp && (
              <Chip kind="blue">PRESS ? FOR HOTKEYS</Chip>
            )}
          </>
        }
      />

      <SetupPanel
        defaultSymbol="BTC/USDT"
        defaultMode="stealth"
        defaultDays={DEFAULT_WINDOW_DAYS}
        loading={playState === 'loading'}
        onLoad={handleLoad}
      />

      {errorMsg && (
        <div
          className="panel"
          style={{
            padding: 10,
            marginTop: 10,
            borderColor: 'rgba(239, 68, 68, 0.5)',
            color: '#ef4444',
            fontFamily: "'Share Tech Mono', monospace",
            fontSize: 12,
            letterSpacing: '.12em',
          }}
        >
          ⚠ {errorMsg}
        </div>
      )}

      {session && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1fr) 360px',
            gap: 14,
            marginTop: 14,
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <ReplayChart
              candles={chartCandles}
              symbol={session.symbol}
              timeframe={session.tf_step}
              entryPrice={step?.plan?.entry_zone.near ?? null}
              stopLoss={step?.plan?.stop_loss?.level ?? null}
              takeProfit={step?.plan?.targets?.[0]?.level ?? null}
            />
            <Spectrogram
              scores={scoreHistory}
              totalBars={session.total_bars}
              currentIndex={step?.index ?? -1}
              signalIndices={signalIndices}
              onScrub={doScrub}
            />
            <Transport
              playState={playState}
              speed={speed}
              currentIndex={step?.index ?? -1}
              totalBars={session.total_bars}
              onPlayPause={togglePlay}
              onStep={doStep}
              onJump={doJump}
              onReset={doReset}
              onSpeed={setSpeed}
              onScrub={doScrub}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <ScorePanel step={step} />
            <PlanPanel step={step} />
          </div>
        </div>
      )}

      {showBriefing && session && (
        <MissionBriefing symbol={session.symbol} mode={session.mode} days={days} />
      )}
      {showHelp && <HelpOverlay onClose={() => setShowHelp(false)} />}

      <FooterStatus latency={36} />
    </div>
  );
}

export default Replay;
