import { createContext, useContext, ReactNode, useEffect, useState } from 'react';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import type { SniperMode } from '@/types/sniperMode';
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
  exchange: 'Binance',
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
  exchange: 'Binance',
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

// Static scanner modes - these are UI configurations only
const SCANNER_MODES: ScannerMode[] = [
  {
    name: 'overwatch',
    description: 'Long-term trend surveillance across 6 timeframes (1W to 5m). Best for patient, high-conviction setups.',
    timeframes: ['1W', '1D', '4H', '1H', '15m', '5m'],
    min_confluence_score: 75,
    profile: 'conservative',
  },
  {
    name: 'recon',
    description: 'Balanced multi-timeframe analysis (5 TFs). Standard operating mode for most market conditions.',
    timeframes: ['1D', '4H', '1H', '15m', '5m'],
    min_confluence_score: 70,
    profile: 'balanced',
  },
  {
    name: 'strike',
    description: 'Fast-action scanner focused on intraday timeframes (4 TFs). Ideal for active trading sessions.',
    timeframes: ['4H', '1H', '15m', '5m'],
    min_confluence_score: 65,
    profile: 'aggressive',
  },
  {
    name: 'surgical',
    description: 'Precision-focused lower timeframe analysis (3 TFs). For experienced traders seeking exact entries.',
    timeframes: ['1H', '15m', '5m'],
    min_confluence_score: 60,
    profile: 'aggressive',
  },
];

const ScannerContext = createContext<ScannerContextType | undefined>(undefined);

export function ScannerProvider({ children }: { children: ReactNode }) {
  const [scanConfig, setScanConfig] = useLocalStorage<ScanConfig>('scan-config', defaultScanConfig);
  const [botConfig, setBotConfig] = useLocalStorage<BotConfig>('bot-config', defaultBotConfig);
  const [isScanning, setIsScanning] = useLocalStorage<boolean>('is-scanning', false);
  const [isBotActive, setIsBotActive] = useLocalStorage<boolean>('is-bot-active', false);
  
  // Scanner modes are now static, no API fetch needed
  const [scannerModes] = useState<ScannerMode[]>(SCANNER_MODES);
  const [selectedMode, setSelectedMode] = useState<ScannerMode | null>(() => {
    // Initialize with the mode matching scanConfig, or default to 'recon'
    const defaultMode = SCANNER_MODES.find(m => m.name === defaultScanConfig.sniperMode) || SCANNER_MODES[1];
    return defaultMode;
  });

  const refreshModes = async (): Promise<void> => {
    // No-op - modes are static now, but keeping function for API compatibility
    return Promise.resolve();
  };

  // Sync selectedMode with scanConfig.sniperMode on mount
  useEffect(() => {
    if (scanConfig?.sniperMode && !selectedMode) {
      const match = SCANNER_MODES.find(m => m.name === scanConfig.sniperMode);
      if (match) setSelectedMode(match);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
