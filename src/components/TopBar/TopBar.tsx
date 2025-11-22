import { Link } from 'react-router-dom';
import { Crosshair } from '@phosphor-icons/react';
import { SessionIndicator } from '@/components/SessionIndicator/SessionIndicator';
import { WalletConnect } from '@/components/WalletConnect';
import { NotificationStatus } from '@/components/NotificationStatus';

export function TopBar() {
  return (
    <nav className="border-b border-border bg-card/30 backdrop-blur-sm sticky top-0 z-50">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-accent rounded flex items-center justify-center">
              <Crosshair size={20} weight="bold" className="text-accent-foreground" />
            </div>
            <span className="text-lg font-bold text-foreground tracking-tight">SNIPERSIGHT</span>
          </Link>

          {/* Right side controls */}
          <div className="flex items-center gap-6">
            <SessionIndicator />
            <div className="flex items-center gap-4">
              <NotificationStatus />
              <WalletConnect />
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
