import type { Metric } from '@/types/landing';

export function MetricsGrid({ metrics }: { metrics: Metric[] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {metrics.map(m => (
        <div key={m.key} className="rounded-lg border border-border/60 bg-card/40 p-4">
          <p className="text-xs text-muted-foreground tracking-wide">{m.title}</p>
          <p className="text-xl font-semibold mt-1 tabular-nums">{m.value}{m.unit ? m.unit : ''}</p>
          {m.hint && <p className="text-[11px] text-muted-foreground mt-1">{m.hint}</p>}
        </div>
      ))}
    </div>
  );
}
