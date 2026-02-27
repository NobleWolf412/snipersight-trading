import type { SystemStatusData } from '@/types/landing';

export function SystemStatus({ data }: { data: SystemStatusData }) {
  const statusColor = {
    connected: 'text-success',
    degraded: 'text-warning',
    offline: 'text-destructive'
  }[data.exchangeStatus];

  const statusBgColor = {
    connected: 'bg-success',
    degraded: 'bg-warning',
    offline: 'bg-destructive'
  }[data.exchangeStatus];

  return (
    <div className="rounded-lg border border-border/60 bg-card/40 p-6">
      <div className="flex flex-wrap items-center justify-between gap-6">
        <div className="flex flex-wrap items-center gap-6">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${statusBgColor} animate-pulse`} />
            <span className="text-sm text-muted-foreground">Exchange:</span>
            <span className={`text-sm font-semibold ${statusColor} capitalize`}>
              {data.exchangeStatus}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Latency:</span>
            <span className="text-sm font-semibold tabular-nums">
              {data.latencyMs}ms
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Active Targets:</span>
            <span className="text-sm font-semibold tabular-nums">
              {data.activeTargets}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Rejected:</span>
            <span className="text-sm font-semibold tabular-nums">
              {data.signalsRejected}
            </span>
          </div>
        </div>
        <div className="text-xs text-muted-foreground font-mono">
          v{data.version}
        </div>
      </div>
    </div>
  );
}
