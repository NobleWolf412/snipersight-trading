import { createContext, useContext, ReactNode } from 'react';
import { useKV } from '@github/spark/hooks';

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
}

export interface BotConfig {
  exchange: string;
  pair: string;
  modes: {
    swing: boolean;
    scalp: boolean;
  };
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
};

const defaultBotConfig: BotConfig = {
  exchange: 'Binance',
  pair: 'BTC/USDT',
  modes: {
    swing: true,
    scalp: false,
  },
  maxTrades: 3,
  duration: 24,
};

const ScannerContext = createContext<ScannerContextType | undefined>(undefined);

export function ScannerProvider({ children }: { children: ReactNode }) {
  const [scanConfig, setScanConfig] = useKV<ScanConfig>('scan-config', defaultScanConfig);
  const [botConfig, setBotConfig] = useKV<BotConfig>('bot-config', defaultBotConfig);
  const [isScanning, setIsScanning] = useKV<boolean>('is-scanning', false);
  const [isBotActive, setIsBotActive] = useKV<boolean>('is-bot-active', false);

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
