/* @refresh skip */
import { createContext, useContext, ReactNode, useEffect, useState } from 'react';
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
  sniperMode: 'recon',
  customTimeframes: [],
};

const defaultBotConfig: BotConfig = {
  exchange: 'phemex',
  pair: 'BTC/USDT',
  modes: {
    swing: true,
    scalp: false,
  },
  sniperMode: 'recon',
  customTimeframes: [],
  maxTrades: 3,
  duration: 24,
};

// Static scanner modes (fallback if backend unavailable)
// Should mirror backend/shared/config/scanner_modes.py MODES dict
const fallbackModes: ScannerMode[] = [
  {
    name: 'overwatch',
    description: 'High-altitude overwatch: macro recon and regime alignment; fewer shots, higher conviction.',
    timeframes: ['1W','1D','4H','1H','15m','5m'],
    min_confluence_score: 75,
    profile: 'macro_surveillance'
  },
  {
    name: 'recon',
    description: 'Balanced recon: multi-timeframe scouting for momentum pivots; adaptable and mission-ready.',
    timeframes: ['1D','4H','1H','15m','5m'],
    min_confluence_score: 65,
    profile: 'balanced'
  },
  {
    name: 'strike',
    description: 'Strike ops: intraday assault on momentum with local liquidity reads; fast entry, fast exfil.',
    timeframes: ['4H','1H','15m','5m'],
    min_confluence_score: 60,
    profile: 'intraday_aggressive'
  },
  {
    name: 'surgical',
    description: 'Surgical precision: tight, high-quality entries only; minimal exposure, maximum control.',
    timeframes: ['1H','15m','5m'],
    min_confluence_score: 70,
    profile: 'precision'
  },
  {
    name: 'ghost',
    description: 'Ghost mode: stealth surveillance across mixed horizons; nimble, low profile, reduced macro drag.',
    timeframes: ['1D','4H','1H','15m','5m'],
    min_confluence_score: 70,
    profile: 'stealth_balanced'
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
    const desired = (scanConfig?.sniperMode as string) || 'recon';
    const match = modes.find(m => m.name === desired) || modes.find(m => m.name === 'recon') || modes[0] || fallbackModes[0];
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
