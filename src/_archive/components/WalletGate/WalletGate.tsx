import { ReactNode } from 'react';
import { useWallet } from '@/context/WalletContext';
import { Card } from '@/components/ui/card';
import { WalletConnect } from '@/components/WalletConnect';
import { LockKey } from '@phosphor-icons/react';

interface WalletGateProps {
  children: ReactNode;
  message?: string;
  showFallback?: boolean;
}

export function WalletGate({ 
  children, 
  message = "Connect your wallet to access this feature",
  showFallback = true 
}: WalletGateProps) {
  const { isConnected } = useWallet();

  if (isConnected) {
    return <>{children}</>;
  }

  if (!showFallback) {
    return null;
  }

  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <Card className="max-w-md w-full p-8 text-center space-y-6 border-primary/20">
        <div className="flex justify-center">
          <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
            <LockKey size={32} className="text-primary" weight="duotone" />
          </div>
        </div>
        <div className="space-y-2">
          <h3 className="text-xl font-bold">Wallet Required</h3>
          <p className="text-sm text-muted-foreground">{message}</p>
        </div>
        <div className="flex justify-center">
          <WalletConnect />
        </div>
        <div className="pt-4 border-t border-border">
          <p className="text-xs text-muted-foreground">
            🔒 Your wallet is used for secure authentication only. 
            No transactions will be made without your explicit approval.
          </p>
        </div>
      </Card>
    </div>
  );
}
