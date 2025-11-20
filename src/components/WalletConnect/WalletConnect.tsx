import { Wallet, SignOut } from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { useWallet } from '@/context/WalletContext';
import { useState } from 'react';
import { toast } from 'sonner';
import { Card } from '@/components/ui/card';

const CHAIN_NAMES: Record<number, string> = {
  1: 'Ethereum Mainnet',
  56: 'BNB Smart Chain',
  137: 'Polygon',
  42161: 'Arbitrum One',
  10: 'Optimism',
  8453: 'Base',
};

export function WalletConnect() {
  const { wallet, isConnected, isConnecting, connect, disconnect, switchChain } = useWallet();
  const [open, setOpen] = useState(false);

  const handleConnect = async (provider: 'metamask' | 'walletconnect' | 'coinbase') => {
    try {
      await connect(provider);
      toast.success('Wallet connected successfully');
      setOpen(false);
    } catch (error: any) {
      toast.error(error.message || 'Failed to connect wallet');
    }
  };

  const handleDisconnect = async () => {
    await disconnect();
    toast.success('Wallet disconnected');
  };

  const formatAddress = (address: string) => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  const handleChainSwitch = async (chainId: number) => {
    try {
      await switchChain(chainId);
      toast.success(`Switched to ${CHAIN_NAMES[chainId]}`);
    } catch (error: any) {
      toast.error(error.message || 'Failed to switch chain');
    }
  };

  if (isConnected && wallet) {
    return (
      <Dialog>
        <DialogTrigger asChild>
          <Button variant="outline" className="gap-2 border-primary/30 bg-primary/10 hover:bg-primary/20">
            <Wallet className="text-primary" weight="fill" />
            <span className="hidden sm:inline">{formatAddress(wallet.address)}</span>
            <span className="text-xs text-muted-foreground hidden md:inline">
              {CHAIN_NAMES[wallet.chainId] || `Chain ${wallet.chainId}`}
            </span>
          </Button>
        </DialogTrigger>
        <DialogContent className="border-primary/20">
          <DialogHeader>
            <DialogTitle className="text-primary">Wallet Connected</DialogTitle>
            <DialogDescription>Manage your wallet connection</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <p className="text-sm text-muted-foreground mb-1">Address</p>
              <p className="font-mono text-sm">{wallet.address}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground mb-2">Network</p>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(CHAIN_NAMES).map(([chainId, name]) => (
                  <Button
                    key={chainId}
                    variant={wallet.chainId === parseInt(chainId) ? "default" : "outline"}
                    size="sm"
                    onClick={() => handleChainSwitch(parseInt(chainId))}
                    className="text-xs"
                  >
                    {name}
                  </Button>
                ))}
              </div>
            </div>
            <Button
              variant="destructive"
              className="w-full gap-2"
              onClick={handleDisconnect}
            >
              <SignOut weight="bold" />
              Disconnect Wallet
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="default" className="gap-2">
          <Wallet weight="bold" />
          Connect Wallet
        </Button>
      </DialogTrigger>
      <DialogContent className="border-primary/20">
        <DialogHeader>
          <DialogTitle className="text-primary">Connect Your Wallet</DialogTitle>
          <DialogDescription>
            Choose a wallet provider to securely authenticate with SniperSight
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Card
            className="p-4 cursor-pointer hover:bg-primary/10 border-primary/20 transition-colors"
            onClick={() => handleConnect('metamask')}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-orange-500/20 flex items-center justify-center">
                <Wallet size={24} className="text-orange-500" weight="fill" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold">MetaMask</h3>
                <p className="text-xs text-muted-foreground">Connect using MetaMask wallet</p>
              </div>
            </div>
          </Card>

          <Card
            className="p-4 cursor-not-allowed opacity-50 border-primary/20"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
                <Wallet size={24} className="text-blue-500" weight="fill" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold">WalletConnect</h3>
                <p className="text-xs text-muted-foreground">Coming soon</p>
              </div>
            </div>
          </Card>

          <Card
            className="p-4 cursor-not-allowed opacity-50 border-primary/20"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-blue-600/20 flex items-center justify-center">
                <Wallet size={24} className="text-blue-600" weight="fill" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold">Coinbase Wallet</h3>
                <p className="text-xs text-muted-foreground">Coming soon</p>
              </div>
            </div>
          </Card>

          <div className="mt-4 p-3 rounded-lg bg-muted/50 border border-border">
            <p className="text-xs text-muted-foreground">
              🔒 <strong>Secure Connection:</strong> Your private keys never leave your wallet. 
              SniperSight only requests your public address for authentication.
            </p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
