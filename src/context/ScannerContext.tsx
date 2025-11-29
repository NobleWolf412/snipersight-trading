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

// Dynamic scanner modes fetched from backend (source of truth)
const fallbackModes: ScannerMode[] = [
  { name: 'recon', description: 'Balanced multi-timeframe', timeframes: ['1D','4H','1H','15m','5m'], min_confluence_score: 65, profile: 'balanced' },
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
    const { data, error } = await api.getScannerModes();
    if (error) {
      console.warn('[ScannerContext] Failed to fetch modes, using fallback:', error);
      setScannerModes(fallbackModes);
      return;
    }
    const modes = (data?.modes || []).map(m => ({
      name: m.name,
      description: m.description,
      timeframes: m.timeframes,
      min_confluence_score: m.min_confluence_score,
      profile: m.profile,
    }));
    setScannerModes(modes.length ? modes : fallbackModes);
    // Ensure selectedMode aligned with scanConfig
    const desired = (scanConfig?.sniperMode as string) || 'recon';
    const match = modes.find(m => m.name === desired) || modes.find(m => m.name === 'recon') || modes[0] || fallbackModes[0];
    setSelectedMode(match);
    console.log('[ScannerContext] Modes loaded. Active:', match?.name);
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
