/* @refresh skip */
import { createContext, useContext, ReactNode, useEffect, useState, useCallback } from 'react';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import type { SniperMode } from '@/types/sniperMode';
import { api } from '@/utils/api';
import type { ScannerMode } from '@/utils/api';

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
  isScanning: boolean;
  setIsScanning: (scanning: boolean) => void;
  isBotActive: boolean;
  setIsBotActive: (active: boolean) => void;
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
    description: 'High-altitude overwatch: macro recon and regime alignment; fewer shots, higher conviction.',
    timeframes: ['1w','1d','4h','1h','15m','5m'],
    min_confluence_score: 75,
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
    description: 'Strike ops: intraday assault on momentum with local liquidity reads; HTF structure with LTF entry precision.',
    timeframes: ['4h','1h','15m','5m'],
    min_confluence_score: 60,
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
    description: 'Surgical precision: tight, high-quality entries only; minimal exposure, maximum control.',
    timeframes: ['1h','15m','5m'],
    min_confluence_score: 70,
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
    description: 'Stealth mode: balanced swing trading with multi-TF confluence; adaptable and mission-ready.',
    timeframes: ['1d','4h','1h','15m','5m'],
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
  console.log('[ScannerContext] Initializing ScannerProvider...');
  
  const [scanConfig, setScanConfig] = useLocalStorage<ScanConfig>('scan-config', defaultScanConfig);
  const [botConfig, setBotConfig] = useLocalStorage<BotConfig>('bot-config', defaultBotConfig);
  const [isScanning, setIsScanning] = useLocalStorage<boolean>('is-scanning', false);
  const [isBotActive, setIsBotActive] = useLocalStorage<boolean>('is-bot-active', false);
  
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

  // Poll HTF tactical opportunities every 60s
  useEffect(() => {
    refreshHTFOpportunities();
    const id = setInterval(() => refreshHTFOpportunities(), 60000);
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

  console.log('[ScannerContext] Provider ready');

  return (
    <ScannerContext.Provider
      value={{
        scanConfig: scanConfig || defaultScanConfig,
        setScanConfig,
        botConfig: botConfig || defaultBotConfig,
        setBotConfig,
        isScanning: isScanning || false,
        setIsScanning,
        isBotActive: isBotActive || false,
        setIsBotActive,
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
