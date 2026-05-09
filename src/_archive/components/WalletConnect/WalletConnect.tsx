import { Wallet, SignOut, Circle } from '@phosphor-icons/react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useWallet } from '@/context/WalletContext';
import { useState } from 'react';
import { toast } from 'sonner';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

const CHAIN_NAMES: Record<number, string> = {
  1: 'Ethereum',
  56: 'BNB Chain',
  137: 'Polygon',
  42161: 'Arbitrum',
  10: 'Optimism',
  8453: 'Base',
};

const CHAIN_COLORS: Record<number, string> = {
  1: 'text-blue-400',
  56: 'text-yellow-400',
  137: 'text-purple-400',
  42161: 'text-blue-500',
  10: 'text-red-400',
  8453: 'text-blue-300',
};

export function WalletConnect() {
  const { wallet, isConnected, isConnecting, connect, disconnect, switchChain } = useWallet();
  const [open, setOpen] = useState(false);

  const handleConnect = async (provider: 'metamask' | 'walletconnect' | 'coinbase') => {
    try {
      await connect(provider);
      toast.success('Wallet connected');
      setOpen(false);
    } catch (error: any) {
      toast.error(error.message || 'Failed to connect');
    }
  };

  const handleDisconnect = async () => {
    await disconnect();
    toast.success('Disconnected');
  };

  const formatAddress = (address: string) => {
    return `${address.slice(0, 4)}…${address.slice(-3)}`;
  };

  const handleChainSwitch = async (chainId: number) => {
    try {
      await switchChain(chainId);
      toast.success(`Switched to ${CHAIN_NAMES[chainId]}`);
    } catch (error: any) {
      toast.error(error.message || 'Failed to switch');
    }
  };

  // Connected state - minimal pill design
  if (isConnected && wallet) {
    return (
      <Dialog>
        <DialogTrigger asChild>
          <button
            className="group flex items-center gap-3 px-6 py-2.5 rounded-full bg-gradient-to-r from-emerald-500/10 to-cyan-500/10 border border-emerald-500/30 hover:border-emerald-400/50 transition-all hover:shadow-[0_0_12px_rgba(16,185,129,0.3)]"
          >
            {/* Status dot */}
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
            </span>

            {/* Address */}
            <span className="text-sm font-mono text-emerald-300/90 group-hover:text-emerald-200 transition-colors">
              {formatAddress(wallet.address)}
            </span>

            {/* Chain indicator */}
            <Circle
              size={8}
              weight="fill"
              className={cn("opacity-80", CHAIN_COLORS[wallet.chainId] || 'text-zinc-400')}
            />
          </button>
        </DialogTrigger>

        <DialogContent className="border-emerald-500/20 bg-black/95 backdrop-blur-xl max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-emerald-400 flex items-center gap-2">
              <Wallet weight="fill" size={20} />
              Connected
            </DialogTitle>
            <DialogDescription className="font-mono text-xs break-all opacity-60">
              {wallet.address}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 mt-2">
            {/* Network selector */}
            <div>
              <p className="text-[10px] uppercase tracking-wider text-zinc-500 mb-2">Network</p>
              <div className="grid grid-cols-3 gap-1.5">
                {Object.entries(CHAIN_NAMES).map(([chainId, name]) => (
                  <button
                    key={chainId}
                    onClick={() => handleChainSwitch(parseInt(chainId))}
                    className={cn(
                      "px-2 py-1.5 rounded text-[10px] font-medium transition-all",
                      wallet.chainId === parseInt(chainId)
                        ? "bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/40"
                        : "bg-zinc-800/50 text-zinc-400 hover:bg-zinc-700/50 hover:text-zinc-300"
                    )}
                  >
                    {name}
                  </button>
                ))}
              </div>
            </div>

            {/* Disconnect */}
            <button
              onClick={handleDisconnect}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors text-sm font-medium"
            >
              <SignOut weight="bold" size={16} />
              Disconnect
            </button>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  // Disconnected state - sleek connect button
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          disabled={isConnecting}
          className={cn(
            "flex items-center gap-3 px-6 py-2.5 rounded-full border transition-all",
            isConnecting
              ? "bg-cyan-500/5 border-cyan-500/20 text-cyan-400/50 cursor-wait"
              : "bg-cyan-500/10 border-cyan-500/30 text-cyan-400 hover:border-cyan-400/50 hover:shadow-[0_0_12px_rgba(6,182,212,0.3)]"
          )}
        >
          <Wallet size={20} weight="bold" />
          <span className="text-base font-medium">
            {isConnecting ? 'Connecting...' : 'Connect'}
          </span>
        </button>
      </DialogTrigger>

      <DialogContent className="border-cyan-500/20 bg-black/95 backdrop-blur-xl max-w-sm">
        <DialogHeader>
          <DialogTitle className="text-cyan-400">Connect Wallet</DialogTitle>
          <DialogDescription className="text-xs">
            Authenticate with your Web3 wallet
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2 mt-2">
          {/* MetaMask */}
          <button
            onClick={() => handleConnect('metamask')}
            className="w-full flex items-center gap-3 p-3 rounded-lg bg-orange-500/5 border border-orange-500/20 hover:bg-orange-500/10 hover:border-orange-500/40 transition-all group"
          >
            <div className="w-8 h-8 rounded-lg bg-orange-500/20 flex items-center justify-center">
              <Wallet size={18} className="text-orange-400" weight="fill" />
            </div>
            <div className="flex-1 text-left">
              <p className="text-sm font-medium text-zinc-200 group-hover:text-orange-200 transition-colors">MetaMask</p>
              <p className="text-[10px] text-zinc-500">Browser extension</p>
            </div>
          </button>

          {/* WalletConnect - Coming Soon */}
          <div className="w-full flex items-center gap-3 p-3 rounded-lg bg-zinc-800/30 border border-zinc-700/30 opacity-50 cursor-not-allowed">
            <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
              <Wallet size={18} className="text-blue-400" weight="fill" />
            </div>
            <div className="flex-1 text-left">
              <p className="text-sm font-medium text-zinc-400">WalletConnect</p>
              <p className="text-[10px] text-zinc-600">Coming soon</p>
            </div>
          </div>

          {/* Coinbase - Coming Soon */}
          <div className="w-full flex items-center gap-3 p-3 rounded-lg bg-zinc-800/30 border border-zinc-700/30 opacity-50 cursor-not-allowed">
            <div className="w-8 h-8 rounded-lg bg-blue-600/10 flex items-center justify-center">
              <Wallet size={18} className="text-blue-500" weight="fill" />
            </div>
            <div className="flex-1 text-left">
              <p className="text-sm font-medium text-zinc-400">Coinbase Wallet</p>
              <p className="text-[10px] text-zinc-600">Coming soon</p>
            </div>
          </div>
        </div>

        <p className="text-[10px] text-zinc-600 text-center mt-3">
          🔒 Your keys stay in your wallet
        </p>
      </DialogContent>
    </Dialog>
  );
}
