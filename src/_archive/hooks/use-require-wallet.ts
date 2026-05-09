import { useWallet } from '@/context/WalletContext';
import { useEffect } from 'react';
import { toast } from 'sonner';

export function useRequireWallet(message?: string) {
  const { isConnected } = useWallet();

  useEffect(() => {
    if (!isConnected && message) {
      toast.warning(message);
    }
  }, [isConnected, message]);

  return isConnected;
}
