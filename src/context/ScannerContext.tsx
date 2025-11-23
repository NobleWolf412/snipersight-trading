import { createContext, useContext, ReactNode, useEffect, useState, useRef } from 'react';
import { useKV } from '@github/spark/hooks';
import type { SniperMode } from '@/types/sniperMode';
import type { ScannerMode } from '@/utils/api';
import { api } from '@/utils/api';

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

const ScannerContext = createContext<ScannerContextType | undefined>(undefined);

export function ScannerProvider({ children }: { children: ReactNode }) {
  const [scanConfig, setScanConfig] = useKV<ScanConfig>('scan-config', defaultScanConfig);
  const [botConfig, setBotConfig] = useKV<BotConfig>('bot-config', defaultBotConfig);
  const [isScanning, setIsScanning] = useKV<boolean>('is-scanning', false);
  const [isBotActive, setIsBotActive] = useKV<boolean>('is-bot-active', false);
  const [scannerModes, setScannerModes] = useState<ScannerMode[]>([]);
  const [selectedMode, setSelectedMode] = useState<ScannerMode | null>(null);
  const inFlightRef = useRef<Promise<void> | null>(null);

  const refreshModes = async (): Promise<void> => {
    if (inFlightRef.current) return inFlightRef.current;
    inFlightRef.current = (async () => {
      try {
        const response = await api.getScannerModes();
        if (response.data?.modes) {
          setScannerModes(response.data.modes);
          // Align selectedMode with existing scanConfig.sniperMode if present
          if (!selectedMode) {
            const match = response.data.modes.find(m => m.name === (scanConfig?.sniperMode || ''));
            if (match) setSelectedMode(match);
          }
        } else if (response.error) {
          console.error('[ScannerContext] Failed fetching scanner modes:', response.error);
        }
      } finally {
        inFlightRef.current = null;
      }
    })();
    return inFlightRef.current;
  };

  // Initial fetch (guarded to avoid duplicate under StrictMode)
  useEffect(() => {
    if (scannerModes.length === 0) {
      refreshModes();
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
