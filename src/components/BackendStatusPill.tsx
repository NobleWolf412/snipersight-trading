import { useBackendHealth } from '@/hooks/useBackendHealth';
import { WifiHigh, WifiSlash } from '@phosphor-icons/react';

export function BackendStatusPill() {
  const { online, lastChecked } = useBackendHealth(3000);
  const ts = new Date(lastChecked).toLocaleTimeString();
  return (
    <div
      title={online ? `Backend online · ${ts}` : `Backend offline · ${ts}`}
      className={
        'flex items-center gap-2 px-2 py-1 rounded-md text-xs font-medium ' +
        (online ? 'text-emerald-400 bg-emerald-400/10 ring-1 ring-emerald-400/40' : 'text-red-400 bg-red-400/10 ring-1 ring-red-400/40')
      }
    >
      {online ? <WifiHigh size={14} /> : <WifiSlash size={14} />}
      <span>{online ? 'ONLINE' : 'OFFLINE'}</span>
    </div>
  );
}
