import { Link, useLocation } from 'react-router-dom';
import { Crosshair, MagnifyingGlass, Robot, Target, ChartLine, ChartLineUp } from '@phosphor-icons/react';
import { SessionIndicator } from '@/components/SessionIndicator/SessionIndicator';
import { WalletConnect } from '@/components/WalletConnect';
import { NotificationStatus } from '@/components/NotificationStatus';

export function Navigation() {
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'Command Center', icon: Crosshair },
    { path: '/scan', label: 'Scan', icon: MagnifyingGlass },
    { path: '/bot', label: 'Bot', icon: Robot },
    { path: '/market', label: 'Market', icon: ChartLineUp },
    { path: '/training', label: 'Training Ground', icon: Target },
    { path: '/intel', label: 'Intel', icon: ChartLine },
  ];

  return (
    <nav className="border-b border-border bg-card/30 backdrop-blur-sm sticky top-0 z-50">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-8">
            <Link to="/" className="flex items-center gap-2">
              <div className="w-8 h-8 bg-accent rounded flex items-center justify-center">
                <Crosshair size={20} weight="bold" className="text-accent-foreground" />
              </div>
              <span className="text-lg font-bold text-foreground tracking-tight">SNIPERSIGHT</span>
            </Link>

            <div className="flex gap-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path || 
                  (item.path !== '/' && location.pathname.startsWith(item.path));
                
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`flex items-center gap-2 px-3 py-2 rounded text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-accent/20 text-accent border border-accent/50'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                    }`}
                  >
                    <Icon size={16} weight={isActive ? 'fill' : 'regular'} />
                    <span className="hidden md:inline">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>

          <div className="flex items-center gap-4">
            <NotificationStatus />
            <WalletConnect />
            <SessionIndicator />
          </div>
        </div>
      </div>
    </nav>
  );
}
