import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Crosshair, Compass, Target, ChartLine, Lightning, List, X } from '@phosphor-icons/react';
import { SessionIndicator } from '@/components/SessionIndicator/SessionIndicator';
import { WalletConnect } from '@/components/WalletConnect';
import { NotificationStatus } from '@/components/NotificationStatus';
import { HTFAlertBeacon } from '@/components/htf/HTFAlertBeacon';

// Streamlined static-height top bar with integrated mobile menu.
export function TopBarLite() {
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  const links = [
    { to: '/scanner/setup', label: 'Scanner', icon: <Crosshair size={16} /> },
    { to: '/bot/setup', label: 'Bot', icon: <Lightning size={16} /> },
    { to: '/intel', label: 'Intel', icon: <Compass size={16} /> },
    { to: '/results', label: 'Results', icon: <ChartLine size={16} /> },
    { to: '/training', label: 'Training', icon: <Target size={16} /> },
  ];

  const toggleMenu = () => setMenuOpen(o => !o);
  const closeMenu = () => setMenuOpen(false);

  return (
    <header
      className="sticky top-0 z-50 bg-background/80 backdrop-blur-md border-b border-border/70 supports-[backdrop-filter]:backdrop-blur-md"
      role="banner"
    >
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 px-3 py-2 rounded-md bg-accent/15 text-accent text-sm font-medium shadow-sm"
      >
        Skip to content
      </a>
      <div className="max-w-7xl mx-auto px-3 md:px-4">
        <div className="flex items-center h-16 md:h-16 gap-3 md:gap-4">
          {/* Brand */}
          <Link
            to="/"
            onClick={closeMenu}
            className="group flex items-center gap-3 pr-3 md:pr-4"
            aria-label="SniperSight Home"
          >
            <div className="relative w-10 h-10 md:w-11 md:h-11 rounded-lg bg-accent/12 flex items-center justify-center ring-1 ring-accent/35 shadow-[0_0_8px_-2px_rgba(0,255,170,0.35)] group-hover:shadow-[0_0_10px_-1px_rgba(0,255,170,0.55)] transition-shadow">
              <Crosshair size={24} weight="bold" className="text-accent" />
            </div>
            <div className="flex flex-col">
              <span className="text-sm md:text-base font-bold tracking-tight leading-none">SNIPERSIGHT</span>
              <span className="text-[9px] md:text-[10px] tracking-widest text-muted-foreground/80">PRECISION SYSTEM</span>
            </div>
          </Link>

          {/* Desktop Nav */}
          <nav className="hidden md:flex items-center gap-1 flex-1" aria-label="Primary">
            {links.map(l => {
              const active = location.pathname.startsWith(l.to);
              return (
                <Link
                  key={l.to}
                  to={l.to}
                  className={
                    'inline-flex items-center gap-2 px-3 py-2 rounded-md text-xs md:text-sm font-medium transition-colors ' +
                    (active
                      ? 'bg-accent/15 text-accent ring-1 ring-accent/40'
                      : 'text-muted-foreground hover:text-foreground hover:bg-card/40')
                  }
                  aria-current={active ? 'page' : undefined}
                >
                  {l.icon}
                  {l.label}
                </Link>
              );
            })}
          </nav>

          {/* Session indicator (>=lg) */}
          <div className="hidden lg:flex justify-center flex-1">
            <SessionIndicator />
          </div>

          {/* Right utilities */}
          <div className="flex items-center gap-2 md:gap-3 ml-auto">
            <HTFAlertBeacon />
            <NotificationStatus />
            <WalletConnect />
            <button
              type="button"
              onClick={toggleMenu}
              aria-expanded={menuOpen}
              aria-controls="mobile-menu"
              className="md:hidden inline-flex items-center justify-center w-10 h-10 rounded-md border border-border/60 bg-card/40 hover:bg-card/60 text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-accent/50"
            >
              {menuOpen ? <X size={22} /> : <List size={22} />}
              <span className="sr-only">{menuOpen ? 'Close menu' : 'Open menu'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Mobile panel */}
      <div
        id="mobile-menu"
        hidden={!menuOpen}
        className="md:hidden border-t border-border/60 bg-background/92 backdrop-blur-md"
      >
        <nav aria-label="Mobile" className="flex flex-col py-2">
          <div className="px-3 pb-2">
            <SessionIndicator />
          </div>
          <ul className="flex flex-col">
            {links.map(l => {
              const active = location.pathname.startsWith(l.to);
              return (
                <li key={l.to}>
                  <Link
                    to={l.to}
                    onClick={closeMenu}
                    className={
                      'flex items-center gap-2 px-4 py-3 text-sm font-medium ' +
                      (active
                        ? 'text-accent bg-accent/10'
                        : 'text-muted-foreground hover:text-foreground hover:bg-card/40')
                    }
                    aria-current={active ? 'page' : undefined}
                  >
                    {l.icon}
                    {l.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
    </header>
  );
}
