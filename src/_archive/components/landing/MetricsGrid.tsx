import type { Metric } from '@/types/landing';

export function MetricsGrid({ metrics }: { metrics: Metric[] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
      {metrics.map(m => (
        <div 
          key={m.key} 
          className="rounded-lg border border-border/60 bg-card/40 p-6 hover:bg-card/60 transition-colors"
        >
          <p className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
            {m.title}
          </p>
          <p className="text-3xl font-bold tabular-nums">
            {m.value}{m.unit ? m.unit : ''}
          </p>
          {m.hint && (
            <p className="text-xs text-muted-foreground mt-2">
              {m.hint}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
