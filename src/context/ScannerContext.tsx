/* @refresh skip */
import { createContext, useContext, ReactNode, useEffect, useState, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import type { SniperMode } from '@/types/sniperMode';
import { api } from '@/utils/api';
import type { ScannerMode } from '@/utils/api';
import { liveTradingService } from '@/services/liveTradingService';
import { paperTradingService } from '@/services/paperTradingService';

export interface ScanConfig {
  exchange: string;
  topPairs: number;
  customPairs: string[];
  categories: {
    majors: boolean;
    altcoins: boolean;
    memeMode: boolean;
  };
  timeframes: string[];
  leverage: number;
  sniperMode: SniperMode;
  customTimeframes?: string[];
  macroOverlay: boolean;
  marketType?: string;
  targetSymbol?: string;
}

export interface BotConfig {
  exchange: string;
  pair: string;
  modes: {
    swing: boolean;
    scalp: boolean;
  };
  sniperMode: SniperMode;
  customTimeframes?: string[];
  maxTrades: number;
  duration: number;
}

interface ScannerContextType {
  scanConfig: ScanConfig;
  setScanConfig: (config: ScanConfig) => void;
  botConfig: BotConfig;
  setBotConfig: (config: BotConfig) => void;
  // 3z.f: isScanning is imperative — written by ScanController on
  // scan start/complete. Backed by useState (not localStorage) so a
  // crash or reload cannot leave a stale `true` value behind.
  isScanning: boolean;
  setIsScanning: (scanning: boolean) => void;
  // 3z.f: isBotActive + isTrainingActive are DERIVED — no setters.
  // Source of truth is the live-bot / paper-bot service status poll
  // and route pathname (training case). Pre-3z.f they were
  // useLocalStorage-backed booleans with zero non-archive setters,
  // creating a §11 "background activity" beacon that locked into
  // whatever localStorage said and could not be cleared by the UI.
  isBotActive: boolean;
  isTrainingActive: boolean;
  scannerModes: ScannerMode[];
  selectedMode: ScannerMode | null;
  setSelectedMode: (mode: ScannerMode) => void;
  refreshModes: () => Promise<void>;
  consoleLogs: ConsoleLog[];
  addConsoleLog: (message: string, type?: ConsoleLog['type']) => void;
  clearConsoleLogs: () => void;
  htfOpportunities: Array<{
    symbol: string;
    recommended_mode: string;
    confidence: number;
    expected_move_pct: number;
    rationale: string;
    level: { timeframe: string; level_type: string; price: number; proximity_pct: number };
  }>;
  refreshHTFOpportunities: () => Promise<void>;
  hasHTFAlert: boolean;
}

export interface ConsoleLog {
  timestamp: number; // epoch ms for precise ordering
  message: string;
  type?: 'info' | 'success' | 'warning' | 'error' | 'config';
}

const defaultScanConfig: ScanConfig = {
  exchange: 'phemex',
  topPairs: 20,
  customPairs: [],
  categories: {
    majors: true,
    altcoins: true,
    memeMode: false,
  },
  timeframes: ['1D', '4H', '1H'],
  leverage: 1,
  sniperMode: 'stealth',
  customTimeframes: [],
  macroOverlay: false,
  marketType: 'swap',
  targetSymbol: '',
};

const defaultBotConfig: BotConfig = {
  exchange: 'phemex',
  pair: 'BTC/USDT',
  modes: {
    swing: true,
    scalp: false,
  },
  sniperMode: 'stealth',
  customTimeframes: [],
  maxTrades: 3,
  duration: 24,
};

// Static scanner modes (fallback if backend unavailable)
// Synced with backend/shared/config/scanner_modes.py MODES dict as of 2025-12-04
// NOTE: recon+ghost merged into stealth mode
const fallbackModes: ScannerMode[] = [
  {
    name: 'overwatch',
    description: 'SWING TRADES (Days-Weeks) • High-conviction setups only • Weekly/Daily structure alignment • Best for: Patient traders wanting A+ quality with 2:1+ R:R minimum',
    timeframes: ['1w', '1d', '4h', '1h', '15m', '5m'],
    min_confluence_score: 72,
    profile: 'macro_surveillance',
    critical_timeframes: ['1w', '1d'],
    primary_planning_timeframe: '4h',
    entry_timeframes: ['4h', '1h'],
    structure_timeframes: ['1w', '1d', '4h'],
    atr_multiplier: 4.0,
    min_rr_ratio: 2.0,
  },
  // NOTE: 'recon' removed - merged into 'stealth' mode
  {
    name: 'strike',
    description: 'INTRADAY TRADES (Hours) • Aggressive momentum plays • More signals, faster entries • Best for: Active traders comfortable with quick decision-making and 1.2:1+ R:R',
    timeframes: ['4h', '1h', '15m', '5m'],
    min_confluence_score: 62,
    profile: 'intraday_aggressive',
    critical_timeframes: ['15m'],
    primary_planning_timeframe: '15m',
    entry_timeframes: ['15m', '5m'],
    structure_timeframes: ['4h', '1h', '15m'],
    atr_multiplier: 2.5,
    min_rr_ratio: 1.2,  // Aggressive mode - looser R:R for more opportunities
  },
  {
    name: 'surgical',
    description: 'SCALP/INTRADAY (Minutes-Hours) • Precision entries with tight stops • Fewer but cleaner setups • Best for: Experienced traders wanting controlled risk with 1.5:1+ R:R',
    timeframes: ['1h', '15m', '5m'],
    min_confluence_score: 65,
    profile: 'precision',
    critical_timeframes: ['15m'],
    primary_planning_timeframe: '15m',
    entry_timeframes: ['15m', '5m'],
    structure_timeframes: ['1h', '15m'],
    atr_multiplier: 2.0,
    min_rr_ratio: 1.5,  // Precision mode - balanced R:R for quality setups
  },
  {
    name: 'stealth',
    description: 'BALANCED (Hours-Days) • Mix of swing and intraday setups • Good signal volume with solid quality • Best for: All-around trading with 1.8:1+ R:R minimum',
    timeframes: ['1d', '4h', '1h', '15m', '5m'],
    min_confluence_score: 65,
    profile: 'stealth_balanced',
    critical_timeframes: ['4h', '1h'],
    primary_planning_timeframe: '1h',
    entry_timeframes: ['1h', '15m', '5m'],
    structure_timeframes: ['1d', '4h', '1h'],
    atr_multiplier: 2.5,
    min_rr_ratio: 1.8,
  },
];

const ScannerContext = createContext<ScannerContextType | undefined>(undefined);

export function ScannerProvider({ children }: { children: ReactNode }) {
  // Only log in development and limit frequency
  if (import.meta.env.MODE === 'development' && Math.random() < 0.1) {
    console.debug('[ScannerContext] ScannerProvider mount');
  }

  const [scanConfig, setScanConfig] = useLocalStorage<ScanConfig>('scan-config', defaultScanConfig);
  const [botConfig, setBotConfig] = useLocalStorage<BotConfig>('bot-config', defaultBotConfig);

  // 3z.f: stale-localStorage migration shim. Pre-3z.f these three keys
  // held zombie booleans: useLocalStorage<boolean> was wired but zero
  // non-archive code paths called the setters. Whatever value
  // localStorage carried (from old _archive/pages/ScannerSetup.tsx
  // writes or test runs) persisted indefinitely. Clear on every mount
  // — removeItem is idempotent so StrictMode dev double-invoke is a
  // no-op on the second pass, and there is no failure mode for
  // "key already gone." Wrapped in try/catch because localStorage
  // can throw in private-window / quota scenarios per §15.
  useEffect(() => {
    try {
      localStorage.removeItem('is-scanning');
      localStorage.removeItem('is-bot-active');
      localStorage.removeItem('is-training-active');
    } catch (e) {
      console.warn('[ScannerContext] stale-flag migration: localStorage unavailable', e);
    }
  }, []);

  // 3z.f: isScanning is imperative (ScanController writes via the
  // exposed setter). Backed by useState so a stuck/cancelled scan
  // does not leave a `true` value persisted across reload.
  const [isScanning, setIsScanning] = useState<boolean>(false);

  // 3z.f: isBotActive + isTrainingActive are DERIVED from polling
  // liveTradingService.getStatus() + paperTradingService.getStatus()
  // every POLL_MS. isTrainingActive additionally fires when the
  // pathname is under /training (gives the beacon a deterministic
  // signal during navigation regardless of paper-bot run state).
  // Direction-agnostic per CLAUDE.md §10 #3: the beacon doesn't
  // distinguish long vs short — it's a presence indicator only.
  const [liveBotRunning, setLiveBotRunning] = useState<boolean>(false);
  const [paperBotRunning, setPaperBotRunning] = useState<boolean>(false);
  const location = useLocation();
  const isBotActive = liveBotRunning;
  const isTrainingActive = paperBotRunning || location.pathname.startsWith('/training');

  // 3z.f: live + paper status poll. 10-second cadence — beacon
  // visibility doesn't need 1s granularity, the page-level pollers
  // on /bot/status (2s/10s) and /training/range (3s/10s) still
  // own the detailed displays. StrictMode-safe: cancelled flag +
  // setTimeout recursion (standard pattern from CycleHeartbeat /
  // UniversePanel / RangeBot).
  useEffect(() => {
    let cancelled = false;
    let tid: number | undefined;

    async function pollStatus() {
      if (cancelled) return;
      try {
        const [liveRes, paperRes] = await Promise.allSettled([
          liveTradingService.getStatus(),
          paperTradingService.getStatus(),
        ]);
        if (cancelled) return;
        const liveRunning =
          liveRes.status === 'fulfilled' && liveRes.value?.status === 'running';
        const paperRunning =
          paperRes.status === 'fulfilled' && paperRes.value?.status === 'running';
        setLiveBotRunning(liveRunning);
        setPaperBotRunning(paperRunning);
      } catch (e) {
        // Promise.allSettled never throws; this branch is defensive.
        // Per §15: log at warn, do not swallow silently.
        if (!cancelled) {
          console.warn('[ScannerContext] beacon status poll error:', e);
        }
      } finally {
        if (!cancelled) {
          tid = window.setTimeout(pollStatus, 10_000);
        }
      }
    }

    void pollStatus();

    return () => {
      cancelled = true;
      if (tid !== undefined) window.clearTimeout(tid);
    };
  }, []);

  const [scannerModes, setScannerModes] = useState<ScannerMode[]>(fallbackModes);
  const [selectedMode, setSelectedMode] = useState<ScannerMode | null>(null);
  // Console logs should be ephemeral per session; do NOT persist in localStorage
  const [consoleLogs, setConsoleLogs] = useState<ConsoleLog[]>([]);
  const [htfOpportunities, setHtfOpportunities] = useState<ScannerContextType['htfOpportunities']>([]);
  const [hasHTFAlert, setHasHTFAlert] = useState(false);

  const addConsoleLog = useCallback((message: string, type: ConsoleLog['type'] = 'info') => {
    setConsoleLogs(prev => [...prev, { timestamp: Date.now(), message, type }]);
  }, []);

  const clearConsoleLogs = useCallback(() => {
    setConsoleLogs([]);
  }, []);

  const refreshHTFOpportunities = useCallback(async (): Promise<void> => {
    try {
      const res = await api.getHTFOpportunities({ min_confidence: 65 });
      if (res.data) {
        const mapped = res.data.opportunities.map(o => ({
          symbol: o.symbol,
          recommended_mode: o.recommended_mode,
          confidence: o.confidence,
          expected_move_pct: o.expected_move_pct,
          rationale: o.rationale,
          level: {
            timeframe: o.level.timeframe,
            level_type: o.level.level_type,
            price: o.level.price,
            proximity_pct: o.level.proximity_pct,
          }
        }));
        setHtfOpportunities(mapped);
        // Alert now triggers if ANY opportunities exist (user prefers persistent red beacon)
        setHasHTFAlert(mapped.length > 0);
      }
    } catch (e) {
      // Silent ignore
    }
  }, []);

  // Poll HTF tactical opportunities every 5 minutes (300s)
  useEffect(() => {
    refreshHTFOpportunities();
    const id = setInterval(() => refreshHTFOpportunities(), 300000);
    return () => clearInterval(id);
  }, [refreshHTFOpportunities]);

  const refreshModes = async (): Promise<void> => {
    console.log('[ScannerContext] Fetching modes from backend...');
    const { data, error } = await api.getScannerModes();
    if (error) {
      console.error('[ScannerContext] Failed to fetch modes:', error);
      console.warn('[ScannerContext] Using fallback modes');
      setScannerModes(fallbackModes);
      return;
    }
    console.log('[ScannerContext] Raw modes response:', data);
    const modes = (data?.modes || []).map(m => ({
      name: m.name,
      description: m.description,
      timeframes: m.timeframes,
      min_confluence_score: m.min_confluence_score,
      profile: m.profile,
      structure_timeframes: m.structure_timeframes,
      entry_timeframes: m.entry_timeframes,
      zone_timeframes: m.zone_timeframes,
      target_timeframes: m.target_timeframes,
      stop_timeframes: m.stop_timeframes,
    }));
    console.log('[ScannerContext] Processed modes:', modes);
    setScannerModes(modes.length ? modes : fallbackModes);
    // Ensure selectedMode aligned with scanConfig
    const desired = (scanConfig?.sniperMode as string) || 'stealth';
    const match = modes.find(m => m.name === desired) || modes.find(m => m.name === 'stealth') || modes[0] || fallbackModes[0];
    setSelectedMode(match);
    console.log('[ScannerContext] Modes loaded. Total:', modes.length, 'Active:', match?.name);
  };

  // On mount, fetch modes and set selectedMode from backend truth
  useEffect(() => {
    refreshModes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Provider ready - no need to log every render

  return (
    <ScannerContext.Provider
      value={{
        scanConfig: scanConfig || defaultScanConfig,
        setScanConfig,
        botConfig: botConfig || defaultBotConfig,
        setBotConfig,
        isScanning,
        setIsScanning,
        // 3z.f: derived — no setters exposed. Re-introducing a setter
        // would break the no-stale-state invariant the migration shim
        // restored.
        isBotActive,
        isTrainingActive,
        scannerModes,
        selectedMode,
        setSelectedMode,
        refreshModes,
        consoleLogs,
        addConsoleLog,
        clearConsoleLogs,
        htfOpportunities,
        refreshHTFOpportunities,
        hasHTFAlert,
      }}
    >
      {children}
    </ScannerContext.Provider>
  );
}

export function useScanner() {
  const context = useContext(ScannerContext);
  if (!context) {
    throw new Error('useScanner must be used within ScannerProvider');
  }
  return context;
}
