import type { SystemStatusData } from '@/types/landing';

export function SystemStatus({ data }: { data: SystemStatusData }) {
  const statusColor = {
    connected: 'text-success',
    degraded: 'text-warning',
    offline: 'text-destructive'
  }[data.exchangeStatus];

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border/60 bg-card/40 p-3 text-xs">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1">
          <span className={`w-2 h-2 rounded-full ${data.exchangeStatus === 'connected' ? 'bg-success' : data.exchangeStatus === 'degraded' ? 'bg-warning' : 'bg-destructive'} animate-pulse`} />
          <span className={statusColor}>Exchange: {data.exchangeStatus}</span>
        </div>
        <span className="text-muted-foreground">Latency: {data.latencyMs}ms</span>
        <span className="text-muted-foreground">Active Targets: {data.activeTargets}</span>
        <span className="text-muted-foreground">Rejected: {data.signalsRejected}</span>
      </div>
      <div className="text-muted-foreground font-medium">v{data.version}</div>
    </div>
  );
}
