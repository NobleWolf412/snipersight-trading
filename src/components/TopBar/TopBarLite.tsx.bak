import { Link } from 'react-router-dom';
import { Crosshair } from '@phosphor-icons/react';
import { SessionIndicator } from '@/components/SessionIndicator/SessionIndicator';
import { WalletConnect } from '@/components/WalletConnect';
import { NotificationStatus } from '@/components/NotificationStatus';
import { HTFAlertBeacon } from '@/components/htf/HTFAlertBeacon';

// Simplified top bar (brand + system utilities + beacon) with enhanced readability.
export function TopBarLite() {
  const closeMenu = () => {};

  return (
    <header
      className="sticky top-0 z-50 bg-black/90 backdrop-blur-md border-b border-border supports-[backdrop-filter]:backdrop-blur-md shadow-[0_2px_12px_-2px_rgba(0,0,0,0.6)]"
      role="banner"
    >
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 px-3 py-2 rounded-md bg-accent/15 text-accent text-sm font-medium shadow-sm"
      >
        Skip to content
      </a>
      <div className="max-w-7xl mx-auto px-4 md:px-6">
        <div className="flex items-center h-20 gap-4">
          {/* Brand */}
          <Link
            to="/"
            onClick={closeMenu}
            className="group flex items-center gap-4 pr-6"
            aria-label="SniperSight Home"
          >
            <div className="relative w-14 h-14 rounded-xl bg-accent/15 flex items-center justify-center ring-2 ring-accent/40 shadow-[0_0_14px_-2px_rgba(0,255,170,0.50)] group-hover:shadow-[0_0_16px_-1px_rgba(0,255,170,0.65)] transition-shadow">
              <Crosshair size={34} weight="bold" className="text-accent" />
            </div>
            <div className="flex flex-col leading-tight">
              <span className="text-xl font-extrabold tracking-tight bg-gradient-to-r from-accent via-emerald-300 to-teal-200 text-transparent bg-clip-text drop-shadow-[0_1px_2px_rgba(0,0,0,0.4)]">
                SNIPERSIGHT
              </span>
              <span className="text-[11px] tracking-[0.25em] font-medium text-muted-foreground/70">
                PRECISION SYSTEM
              </span>
            </div>
          </Link>
          {/* Session indicator (center) */}
          <div className="hidden lg:flex justify-center flex-1">
            <SessionIndicator />
          </div>

          {/* Right utilities */}
          <div className="flex items-center gap-3 ml-auto">
            <HTFAlertBeacon />
            <NotificationStatus />
            <WalletConnect />
          </div>
        </div>
      </div>
    </header>
  );
}
