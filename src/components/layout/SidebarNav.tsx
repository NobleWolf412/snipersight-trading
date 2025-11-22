import { useTelemetry } from '@/hooks/useTelemetry';
import { Link } from 'react-router-dom';
import { Crosshair, Pulse, Target, ListBullets } from '@phosphor-icons/react';

export function SidebarNav() {
  const { metrics, system } = useTelemetry();
  const activeTargets = metrics.find(m => m.key === 'activeTargets')?.value ?? 0;
  const latency = metrics.find(m => m.key === 'latencyMs')?.value ?? 0;
  const rejected = metrics.find(m => m.key === 'signalsRejected')?.value ?? 0;

  const items = [
    { href: '#hero', label: 'Hero', icon: Crosshair },
    { href: '#metrics', label: 'Metrics', icon: Pulse },
    { href: '#primary-modules', label: 'Tools', icon: Target },
    { href: '#status', label: 'Status', icon: ListBullets }
  ];

  return (
    <aside className="hidden xl:block w-60 shrink-0 sticky top-24 self-start" aria-label="Section navigation">
      <div className="space-y-6">
        <nav className="rounded-lg border border-border/60 bg-card/40 p-4">
          <ul className="space-y-2 text-sm">
            {items.map(item => {
              const Icon = item.icon;
              return (
                <li key={item.href}>
                  <a href={item.href} className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-accent/10 transition-colors">
                    <Icon size={16} weight="bold" className="text-accent" />
                    <span>{item.label}</span>
                  </a>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="rounded-lg border border-border/60 bg-card/40 p-4 space-y-3 text-xs">
          <div className="flex justify-between"><span className="text-muted-foreground">Active</span><span className="font-semibold tabular-nums">{activeTargets}</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Latency</span><span className="font-semibold tabular-nums">{latency}ms</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Rejected</span><span className="font-semibold tabular-nums">{rejected}</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Exchange</span><span className="capitalize font-semibold">{system.exchangeStatus}</span></div>
        </div>
      </div>
    </aside>
  );
}

export default SidebarNav;