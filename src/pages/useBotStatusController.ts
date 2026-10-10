import { paperTradingService } from '@/services/paperTradingService';
/** Monitor one selected session owner. Commands remain owner-specific. */
import type { BotPlaySelection } from '@/services/playInspector';
import { liveTradingService, type CompletedLiveTrade } from '@/services/liveTradingService';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useScanner } from '@/context/ScannerContext';
import { fetchActiveSession, type ActiveSession } from '@/services/activeSession';
import { tradeJournalService, type JournalAggregate } from '@/services/tradeJournalService';
export function useBotStatusController() {
    const navigate = useNavigate();
    // Scanner-mode catalog drives the GauntletBreakdown mode-delta strip.
    // Selector is intentionally wide — useScanner is mounted at the App
    // root so this is always available; if it ever isn't (test harness),
    // GauntletBreakdown gracefully no-ops the strip when modes are empty.
    const { scannerModes, selectedMode } = useScanner();
    // Active session = whichever of {live, paper} owns the running bot, or the
    // live idle state when neither is running. See activeSession.ts. We keep
    // `status` as a derived shorthand for downstream JSX that referenced it.
    const [session, setSession] = useState<ActiveSession | null>(null);
    const status = session?.status ?? null;
    const [trades, setTrades] = useState<CompletedLiveTrade[]>([]);
    const [loading, setLoading] = useState(true);
    const [stopping, setStopping] = useState(false);
    const [resetting, setResetting] = useState(false);
    const [killing, setKilling] = useState(false);
    const [showKillConfirm, setShowKillConfirm] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [analyzing, setAnalyzing] = useState(false);
    const [analyzeOutput, setAnalyzeOutput] = useState<string | null>(null);
    const [analyzeError, setAnalyzeError] = useState<string | null>(null);
    const [connectionError, setConnectionError] = useState<string | null>(null);
    const [tradesError, setTradesError] = useState<string | null>(null);
    // Cross-session lifetime aggregate. Sourced from /api/trades/journal,
    // which sums realized PnL across every closed trade in the journal
    // file (all sessions, including pre-restart ones). Distinct from the
    // hero's balance.pnl (current-session equity − initial) and from
    // stats.total_pnl (current-session realized only). Re-fetched on the
    // slow poll plus whenever a trade closes in this session.
    const [lifetime, setLifetime] = useState<JournalAggregate | null>(null);
    const [lifetimeError, setLifetimeError] = useState<string | null>(null);
    // Phase 3g.ii.c — PipelineTracer drawer state. Non-null = drawer open.
    const [tracerSignalId, setTracerSignalId] = useState<string | null>(null);
    // Phase 3g.ii.f — DiagnoseWizard modal state.
    // `diagnoseOpenedAtMs` captures Date.now() at the instant the operator
    // clicks RUN DIAGNOSE so stale-cycle checks use a fresh reference time
    // every open (rather than the page-mount `now`). Snapshot tests freeze
    // the global Date constructor before goto so this still yields the
    // deterministic frozen ts during capture.
    const [diagnoseOpen, setDiagnoseOpen] = useState(false);
    const [diagnoseOpenedAtMs, setDiagnoseOpenedAtMs] = useState<number>(() => Date.now());
    // Position / pending-order detail modal. Click any row in Active
    // Positions to open. Modal carries the chart + metadata.
    const [detailSelection, setDetailSelection] = useState<BotPlaySelection | null>(null);
    const fetchFailCount = useRef(0);
    const fastPollRef = useRef(false);
    const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const connectionErrorRef = useRef<string | null>(null);
    connectionErrorRef.current = connectionError;
    // Ref-synced active service so action handlers + loadTrades don't need
    // `session` in their dep arrays (which would cascade into the polling
    // useEffect and create an infinite re-render loop). Updated whenever
    // session.service flips between live and paper.
    const activeServiceRef = useRef<typeof liveTradingService | typeof paperTradingService>(liveTradingService);
    useEffect(() => {
        if (session?.service)
            activeServiceRef.current = session.service;
    }, [session?.service]);
    // Kill-confirm focus management. When the destructive panel appears,
    // focus lands on CANCEL (safe default per WCAG / Apple HIG). User has
    // to deliberately tab to CONFIRM KILL SWITCH to fire.
    const cancelKillRef = useRef<HTMLButtonElement>(null);
    useEffect(() => {
        if (showKillConfirm)
            cancelKillRef.current?.focus();
    }, [showKillConfirm]);
    // Static now for snapshot determinism. Footer renders this once.
    const [now] = useState(() => new Date());
    // Snapshot-ready handshake — StrictMode-safe.
    useEffect(() => {
        document.body.setAttribute('data-snapshot-ready', 'true');
        return () => {
            document.body.removeAttribute('data-snapshot-ready');
        };
    }, []);
    const ownerRef = useRef<'live' | 'paper' | undefined>(undefined);
    const mountedRef = useRef(true);
    const statusGeneration = useRef(0);
    const historyGeneration = useRef(0);
    const lifetimeGeneration = useRef(0);
    const loadStatus = useCallback(async () => {
        const generation = ++statusGeneration.current;
        try {
            const next = await fetchActiveSession(ownerRef.current);
            if (!mountedRef.current || generation !== statusGeneration.current)
                return;
            if (activeServiceRef.current !== next.service) {
                historyGeneration.current++;
                setTrades([]);
                setTradesError(null);
            }
            ownerRef.current = next.isPaper ? 'paper' : 'live';
            activeServiceRef.current = next.service;
            setSession(next);
            // Fast-poll when there are open positions or a scan is in flight.
            // The `current_scan` field only exists on LiveTradingStatus; paper
            // doesn't expose it. Fall back to positions-only check for paper.
            const data = next.status;
            const hasCurrentScan = data && 'current_scan' in data && data.current_scan?.status === 'running';
            fastPollRef.current = (data?.positions?.length ?? 0) > 0 || !!hasCurrentScan
                || (!!data && 'lifecycle' in data && !!data.lifecycle?.recovery_required);
            fetchFailCount.current = 0;
            if (connectionErrorRef.current)
                setConnectionError(null);
        }
        catch (e) {
            if (!mountedRef.current || generation !== statusGeneration.current)
                return;
            fetchFailCount.current += 1;
            const detail = e instanceof Error ? e.message : 'Unknown error';
            setConnectionError(`Backend unreachable: ${detail}`);
        }
        finally {
            if (mountedRef.current && generation === statusGeneration.current)
                setLoading(false);
        }
    }, []);
    const loadTrades = useCallback(async () => {
        const generation = ++historyGeneration.current;
        // Dispatch against the active service via the ref (kept in sync below).
        // Reading session from useCallback deps would re-create loadTrades on
        // every poll, which would in turn re-schedule the polling useEffect and
        // create an infinite re-render loop. The ref pattern matches the
        // existing connectionErrorRef approach.
        const svc = activeServiceRef.current;
        try {
            const data = await svc.getHistory(50);
            if (!mountedRef.current || generation !== historyGeneration.current || activeServiceRef.current !== svc)
                return;
            if (data && Array.isArray(data.trades)) {
                setTrades(data.trades as CompletedLiveTrade[]);
                setTradesError(null);
            }
            else {
                setTradesError('Trade history response missing trades array');
            }
        }
        catch (e) {
            if (!mountedRef.current || generation !== historyGeneration.current || activeServiceRef.current !== svc)
                return;
            setTradesError(e instanceof Error ? e.message : 'Could not load trade history');
        }
    }, []);
    const loadLifetime = useCallback(async () => {
        const generation = ++lifetimeGeneration.current;
        try {
            // limit=1 keeps the trades payload tiny — the aggregate envelope is
            // always computed over the full journal regardless of limit.
            const data = await tradeJournalService.getJournal({ limit: 1 });
            if (!mountedRef.current || generation !== lifetimeGeneration.current)
                return;
            if (data && data.aggregate) {
                setLifetime(data.aggregate);
                setLifetimeError(null);
            }
            else {
                setLifetimeError('Journal aggregate missing');
            }
        }
        catch (e) {
            if (!mountedRef.current || generation !== lifetimeGeneration.current)
                return;
            setLifetimeError(e instanceof Error ? e.message : 'Could not load lifetime totals');
        }
    }, []);
    useEffect(() => {
        let disposed = false;
        mountedRef.current = true;
        const poll = async () => {
            await loadStatus();
            if (disposed)
                return;
            if (ownerRef.current)
                await Promise.all([loadTrades(), loadLifetime()]);
            if (!disposed)
                pollTimerRef.current = setTimeout(poll, fastPollRef.current ? 2000 : 10000);
        };
        void poll();
        return () => { disposed = true; mountedRef.current = false; statusGeneration.current++; historyGeneration.current++; lifetimeGeneration.current++; if (pollTimerRef.current)
            clearTimeout(pollTimerRef.current); };
    }, [loadStatus, loadTrades, loadLifetime]);
    const handleStop = async () => {
        setStopping(true);
        try {
            await activeServiceRef.current.stop();
            await loadStatus();
            await loadTrades();
        }
        catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setStopping(false);
        }
    };
    // KillSwitch is live-only. Button is hidden when !canKillSwitch but the
    // handler defends with an explicit type narrow in case it's wired
    // somewhere else later. Paper has no real positions to close at market.
    const handleKillSwitch = async () => {
        if (activeServiceRef.current !== liveTradingService)
            return;
        setKilling(true);
        setShowKillConfirm(false);
        try {
            await liveTradingService.killSwitch();
            await loadStatus();
        }
        catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setKilling(false);
        }
    };
    const handleReset = async () => {
        setResetting(true);
        try {
            const owner = activeServiceRef.current;
            await owner.reset();
            navigate(owner === paperTradingService ? '/training/range#setup' : '/bot/setup');
        }
        catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setResetting(false);
        }
    };
    // AnalyzeSession is live-only (no equivalent in paperTradingService).
    // Button is hidden when !canAnalyzeSession; handler guards in case.
    const handleAnalyze = async () => {
        if (activeServiceRef.current !== liveTradingService)
            return;
        setAnalyzing(true);
        setAnalyzeOutput(null);
        setAnalyzeError(null);
        try {
            const result = await liveTradingService.analyzeSession();
            setAnalyzeOutput(result.output || '(no output)');
            if (result.error)
                setAnalyzeError(result.error);
        }
        catch (e) {
            setAnalyzeError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setAnalyzing(false);
        }
    };
    return { navigate, scannerModes, selectedMode, session, status, trades, loading, stopping, resetting, killing, showKillConfirm, setShowKillConfirm, error, analyzing, analyzeOutput, analyzeError, connectionError, tradesError, lifetime, lifetimeError, tracerSignalId, setTracerSignalId, diagnoseOpen, setDiagnoseOpen, diagnoseOpenedAtMs, setDiagnoseOpenedAtMs, detailSelection, setDetailSelection, cancelKillRef, now, handleStop, handleKillSwitch, handleReset, handleAnalyze };
}
