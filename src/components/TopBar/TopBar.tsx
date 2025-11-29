import { Link } from 'react-router-dom';
import { Crosshair } from '@phosphor-icons/react';
import { SessionIndicator } from '@/components/SessionIndicator/SessionIndicator';
import { WalletConnect } from '@/components/WalletConnect';
import { NotificationStatus } from '@/components/NotificationStatus';

export function TopBar() {
  return (
    <nav className="border-b border-border bg-card/40 backdrop-blur-sm sticky top-0 z-50" role="navigation" aria-label="Main">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex items-center justify-between h-16 gap-6">
          <Link to="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
            <div className="w-10 h-10 bg-accent rounded flex items-center justify-center flex-shrink-0">
              <Crosshair size={22} weight="bold" className="text-accent-foreground" />
            </div>
            <span className="text-lg font-bold text-foreground tracking-tight hidden sm:inline">SNIPERSIGHT</span>
          </Link>

          <div className="hidden lg:flex flex-1 justify-center max-w-3xl mx-auto">
            <SessionIndicator />
          </div>

          <div className="flex items-center gap-3 sm:gap-4">
            <NotificationStatus />
            <WalletConnect />
          </div>
        </div>
      </div>
    </nav>
  );
}
