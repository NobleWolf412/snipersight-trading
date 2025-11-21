import { createContext, useContext, ReactNode, useEffect } from 'react';
import { useKV } from '@github/spark/hooks';

export interface WalletConnection {
  address: string;
  chainId: number;
  connectedAt: number;
  provider: 'metamask' | 'walletconnect' | 'coinbase' | null;
}

interface WalletContextType {
  wallet: WalletConnection | null;
  isConnected: boolean;
  isConnecting: boolean;
  connect: (provider: 'metamask' | 'walletconnect' | 'coinbase') => Promise<void>;
  disconnect: () => Promise<void>;
  switchChain: (chainId: number) => Promise<void>;
}

const WalletContext = createContext<WalletContextType | undefined>(undefined);

export function WalletProvider({ children }: { children: ReactNode }) {
  const [wallet, setWallet] = useKV<WalletConnection | null>('wallet-connection', null);
  const [isConnecting, setIsConnecting] = useKV<boolean>('wallet-connecting', false);

  const isConnected = !!(wallet && wallet.address);

  useEffect(() => {
    if (wallet && wallet.address && window.ethereum) {
      const handleAccountsChanged = (accounts: string[]) => {
        if (accounts.length === 0) {
          disconnect();
        } else if (accounts[0] !== wallet.address) {
          setWallet((current) => current ? { ...current, address: accounts[0] } : null);
        }
      };

      const handleChainChanged = (chainId: string) => {
        const newChainId = parseInt(chainId, 16);
        setWallet((current) => current ? { ...current, chainId: newChainId } : null);
      };

      const handleDisconnect = () => {
        disconnect();
      };

      const eth = window.ethereum;
      eth.on('accountsChanged', handleAccountsChanged);
      eth.on('chainChanged', handleChainChanged);
      eth.on('disconnect', handleDisconnect);

      return () => {
        eth.removeListener('accountsChanged', handleAccountsChanged);
        eth.removeListener('chainChanged', handleChainChanged);
        eth.removeListener('disconnect', handleDisconnect);
      };
    }
  }, [wallet?.address]);

  const connect = async (provider: 'metamask' | 'walletconnect' | 'coinbase') => {
    setIsConnecting(true);

    try {
      if (provider === 'metamask') {
        if (!window.ethereum) {
          throw new Error('MetaMask not installed');
        }

        const accounts = await window.ethereum.request({
          method: 'eth_requestAccounts',
        });

        const chainId = await window.ethereum.request({
          method: 'eth_chainId',
        });

        setWallet({
          address: accounts[0],
          chainId: parseInt(chainId, 16),
          connectedAt: Date.now(),
          provider: 'metamask',
        });
      } else if (provider === 'walletconnect') {
        throw new Error('WalletConnect integration coming soon');
      } else if (provider === 'coinbase') {
        throw new Error('Coinbase Wallet integration coming soon');
      }
    } catch (error) {
      console.error('Wallet connection failed:', error);
      throw error;
    } finally {
      setIsConnecting(false);
    }
  };

  const disconnect = async () => {
    setWallet(null);
  };

  const switchChain = async (chainId: number) => {
    if (!window.ethereum) {
      throw new Error('No wallet provider found');
    }

    try {
      await window.ethereum.request({
        method: 'wallet_switchEthereumChain',
        params: [{ chainId: `0x${chainId.toString(16)}` }],
      });

      setWallet((current) => current ? { ...current, chainId } : null);
    } catch (error: any) {
      if (error.code === 4902) {
        throw new Error('Chain not added to wallet');
      }
      throw error;
    }
  };

  return (
    <WalletContext.Provider
      value={{
        wallet: wallet || null,
        isConnected,
        isConnecting: isConnecting || false,
        connect,
        disconnect,
        switchChain,
      }}
    >
      {children}
    </WalletContext.Provider>
  );
}

export function useWallet() {
  const context = useContext(WalletContext);
  if (!context) {
    throw new Error('useWallet must be used within WalletProvider');
  }
  return context;
}
