import { Link } from 'react-router-dom';
import { Crosshair } from '@phosphor-icons/react';
import { SessionIndicator } from '@/components/SessionIndicator/SessionIndicator';
import { WalletConnect } from '@/components/WalletConnect';
import { NotificationStatus } from '@/components/NotificationStatus';

export function TopBar() {
  return (
    <nav className="border-b border-border bg-card/30 backdrop-blur-sm sticky top-0 z-50">
      <div className="container mx-auto px-6">
        <div className="flex items-center justify-between h-20">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-10 h-10 bg-accent rounded flex items-center justify-center">
              <Crosshair size={24} weight="bold" className="text-accent-foreground" />
            </div>
            <span className="text-xl font-bold text-foreground tracking-tight">SNIPERSIGHT</span>
          </Link>

          <div className="flex items-center gap-8">
            <SessionIndicator />
            <div className="flex items-center gap-6">
              <NotificationStatus />
              <WalletConnect />
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
