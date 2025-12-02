import { Link, useLocation } from 'react-router-dom';
import { Crosshair, Compass, Target, ChartLine, Lightning } from '@phosphor-icons/react';
import { SessionIndicator } from '@/components/SessionIndicator/SessionIndicator';
import { WalletConnect } from '@/components/WalletConnect';
import { NotificationStatus } from '@/components/NotificationStatus';
import { HTFAlertBeacon } from '@/components/htf/HTFAlertBeacon';
import { BackendStatusPill } from '@/components/BackendStatusPill';
import { debugLogger, LogLevel } from '@/utils/debugLogger';
import { useLocalStorage } from '@/hooks/useLocalStorage';

export function TopBar() {
  const location = useLocation();
  const [verbosity, setVerbosity] = useLocalStorage<'silent' | 'essential' | 'verbose'>(
    'log-verbosity',
    (import.meta.env.MODE === 'production') ? 'essential' : 'verbose'
  );

  // Apply verbosity to debugLogger
  const appliedLevel = verbosity === 'silent' ? LogLevel.SILENT : verbosity === 'essential' ? LogLevel.WARN : LogLevel.INFO;
  debugLogger.setLogLevel(appliedLevel);
  const links = [
    { to: '/scanner/setup', label: 'Scanner', icon: <Crosshair size={16} /> },
    { to: '/bot/setup', label: 'Bot', icon: <Lightning size={16} /> },
    { to: '/intel', label: 'Intel', icon: <Compass size={16} /> },
    { to: '/results', label: 'Results', icon: <ChartLine size={16} /> },
    { to: '/training', label: 'Training', icon: <Target size={16} /> },
  ];
  return (
    <header
      className="sticky top-0 z-50 border-b border-border/60 bg-gradient-to-r from-background/80 via-background/70 to-background/80 backdrop-blur-xl shadow-[0_0_0_1px_rgba(255,255,255,0.04),0_4px_24px_-4px_rgba(0,0,0,0.4)]"
      role="banner"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex items-center h-18 md:h-20 gap-4">
          {/* Brand */}
          <Link
            to="/"
            className="group flex items-center gap-3 pr-4 border-r border-border/40"
            aria-label="SniperSight Home"
          >
            <div className="relative w-11 h-11 rounded-lg bg-accent/15 flex items-center justify-center ring-1 ring-accent/40 shadow-[0_0_12px_-2px_rgba(0,255,170,0.5)] group-hover:shadow-[0_0_14px_0_rgba(0,255,170,0.65)] transition-shadow">
              <Crosshair size={26} weight="bold" className="text-accent" />
            </div>
            <div className="flex flex-col">
              <span className="text-base md:text-lg font-bold tracking-tight leading-none">SNIPERSIGHT</span>
              <span className="text-[10px] tracking-widest text-muted-foreground/80">PRECISION SYSTEM</span>
            </div>
          </Link>
          {/* Primary Nav */}
          <nav className="hidden md:flex flex-1 items-center gap-1" aria-label="Primary">
            {links.map(l => {
              const active = location.pathname.startsWith(l.to);
              return (
                <Link
                  key={l.to}
                  to={l.to}
                  className={
                    'inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ' +
                    (active
                      ? 'bg-accent/15 text-accent ring-1 ring-accent/40 shadow-[0_0_0_1px_rgba(0,255,170,0.3)]'
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
          {/* Session indicator center on large screens */}
          <div className="hidden xl:flex flex-1 justify-center">
            <SessionIndicator />
          </div>
          {/* Right utilities */}
          <div className="flex items-center gap-2 sm:gap-3 ml-auto">
            <HTFAlertBeacon />
            <BackendStatusPill />
            <NotificationStatus />
            <WalletConnect />
            {/* Log verbosity selector */}
            <label className="hidden md:flex items-center gap-2 px-2 py-1 rounded-md text-xs text-muted-foreground bg-card/50 border border-border/50">
              <span>Logs</span>
              <select
                aria-label="Log verbosity"
                className="bg-transparent outline-none text-foreground"
                value={verbosity}
                onChange={(e) => setVerbosity(e.target.value as any)}
              >
                <option value="silent">Silent</option>
                <option value="essential">Essential</option>
                <option value="verbose">Verbose</option>
              </select>
            </label>
          </div>
        </div>
      </div>
      {/* Mobile nav */}
      <div className="md:hidden border-t border-border/50 bg-background/90 backdrop-blur-sm">
        <nav className="flex items-stretch justify-around" aria-label="Mobile">
          {links.map(l => {
            const active = location.pathname.startsWith(l.to);
            return (
              <Link
                key={l.to}
                to={l.to}
                className={
                  'flex flex-col items-center justify-center gap-1 flex-1 py-3 text-[11px] font-medium tracking-wide ' +
                  (active ? 'text-accent bg-accent/10' : 'text-muted-foreground hover:text-foreground')
                }
                aria-current={active ? 'page' : undefined}
              >
                {l.icon}
                {l.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
