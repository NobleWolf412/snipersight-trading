import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { ModuleDef } from '@/types/landing';
import { useNavigate } from 'react-router-dom';

const accentClassMap: Record<string, string> = {
  accent: 'border-accent/40 hover:border-accent/60',
  success: 'border-success/40 hover:border-success/60',
  warning: 'border-warning/40 hover:border-warning/60',
  foreground: 'border-border/50 hover:border-accent/40'
};

export function ModuleCard({ module }: { module: ModuleDef }) {
  const navigate = useNavigate();
  const AccentIcon = module.icon;
  return (
    <Card
      onClick={() => navigate(module.destination)}
      className={cn(
        'group cursor-pointer p-5 bg-card/50 transition border rounded-lg hover:bg-card/60',
        accentClassMap[module.accent || 'foreground']
      )}
      aria-label={module.title}
    >
      <div className="flex items-start gap-4">
        <div className={cn('w-12 h-12 rounded-md flex items-center justify-center border text-foreground bg-background/40 group-hover:scale-105 transition',
          module.accent === 'accent' && 'border-accent/50',
          module.accent === 'success' && 'border-success/50',
          module.accent === 'warning' && 'border-warning/50'
        )}>
          <AccentIcon size={26} weight="bold" />
        </div>
        <div className="space-y-1">
          <h2 className="text-lg font-semibold tracking-tight">{module.title}</h2>
          <p className="text-sm text-muted-foreground leading-relaxed">{module.description}</p>
        </div>
      </div>
    </Card>
  );
}
