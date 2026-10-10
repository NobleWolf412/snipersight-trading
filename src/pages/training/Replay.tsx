import { Modal } from '@/components/hud/Modal';
import { ReplaySessionController } from '@/services/replaySessionController';
/** Historical candle playback. ReplaySessionController serializes cursor mutations
 * and cleanup; historical inputs determine which evidence is available. */
import { Chip,FooterStatus,PageHead } from '@/components/hud';
import type {
ReplayCandle
} from '@/utils/api';
import {
useCallback,
useEffect,
useMemo,
useRef,
useState,
useSyncExternalStore
} from 'react';

import { DEFAULT_WINDOW_DAYS,HelpOverlay,MissionBriefing,PlanPanel,ReplayChart,ReplayMode,ScorePanel,SetupPanel,Spectrogram,Transport,up,useHotkey } from './ReplayViews';

export function Replay() {
  const readyRef = useRef(false);
  const [controller] = useState(() => new ReplaySessionController());
  const { playState, session, step, errorMsg, moveTarget, scoreHistory, signalIndices } = useSyncExternalStore(controller.subscribe, controller.getSnapshot);
  const setPlayState = controller.setPlayState;
  const [speed, setSpeed] = useState(1);
  const [showBriefing, setShowBriefing] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [showTapeSetup, setShowTapeSetup] = useState(false);

  const [helpClickHint, setHelpClickHint] = useState(true);

  // Score history for spectrogram (bar_index → score)


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

  useEffect(() => () => { void controller.close(); }, [controller]);

  // Briefing flag — fires for 1500ms after load
  useEffect(() => {
    if (showBriefing) {
      const t = setTimeout(() => setShowBriefing(false), 1500);
      return () => clearTimeout(t);
    }
  }, [showBriefing]);

  const handleLoad = useCallback(async (symbol: string, mode: ReplayMode, windowStartIso: string, windowEndIso: string) => {
    await controller.load({ symbol, mode, window_start: windowStartIso, window_end: windowEndIso });
    if (controller.getSnapshot().session && !controller.getSnapshot().errorMsg) { setShowTapeSetup(false); setShowBriefing(true); setHelpClickHint(true); }
  }, [controller]);
  const doStep = controller.stepBy;
  const doScrub = controller.seek;
  const doReset = controller.reset;
  // Signal replay is unavailable without historical macro/configuration inputs.
  const doJump = () => {};

  // ---- Play loop ----
  useEffect(() => {
    if (playState !== 'playing' || !session) return;
    const intervalMs = Math.max(80, Math.floor(1000 / speed));
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      await doStep(1, true);
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
    controller.togglePlay();
  }, [controller]);

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
    else if (e.key === 'Escape') { void controller.close(); }
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
            : 'Inspect closed candles and market structure across historical bars'
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

      <p role="status" style={{ color: '#cfe5d4', fontSize: 12, lineHeight: 1.5, margin: '12px 0' }}>
        Candle and structure inspection is available. Historical macro data and original strategy settings
        are missing, so trade-signal replay is unavailable.
      </p>

      {session && <button type="button" className="btn" aria-haspopup="dialog" onClick={() => setShowTapeSetup(true)}>Load another tape</button>}
      {!session && !showTapeSetup && <SetupPanel defaultSymbol="BTC/USDT" defaultMode="stealth"
        defaultDays={DEFAULT_WINDOW_DAYS} loading={playState === 'loading'} onLoad={handleLoad} />}
      {showTapeSetup && <Modal label="Load historical tape" onClose={() => setShowTapeSetup(false)} maxWidth={760}>
        <div className="dialog-panel-content"><h2>Load historical tape</h2>
          <SetupPanel defaultSymbol={session?.symbol ?? 'BTC/USDT'} defaultMode="stealth"
            defaultDays={DEFAULT_WINDOW_DAYS} loading={playState === 'loading'} onLoad={handleLoad} />
          {errorMsg && <p role="alert" style={{ color: 'var(--red)' }}>{errorMsg}</p>}
        </div>
      </Modal>}

      {moveTarget !== null && (
        <div className="panel" role="status" style={{ padding: 10, marginTop: 10 }}>
          Moving to bar {moveTarget + 1} of {session?.total_bars}. Each candle is checked in order.
          <button className="btn" style={{ marginLeft: 12 }} onClick={controller.cancelMove}>Stop moving</button>
        </div>
      )}

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
        <div className="replay-layout" style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 360px',
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

      <FooterStatus />
    </div>
  );
}

export default Replay;
