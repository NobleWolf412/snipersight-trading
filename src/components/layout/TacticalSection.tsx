import { cn } from '@/lib/utils';
import { ReactNode } from 'react';

type TacticalSectionProps = {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  className?: string;
  variant?: 'default' | 'accent' | 'warning' | 'critical';
  badge?: ReactNode;
};

export function TacticalSection({
  children,
  title,
  subtitle,
  className,
  variant = 'default',
  badge
}: TacticalSectionProps) {
  const variantStyles = {
    default: 'border-primary/30 bg-card/40',
    accent: 'border-accent/40 bg-card/50',
    warning: 'border-warning/40 bg-card/40',
    critical: 'border-destructive/40 bg-card/40'
  };

  const headerAccent = {
    default: 'border-primary/50',
    accent: 'border-accent/60',
    warning: 'border-warning/60',
    critical: 'border-destructive/60'
  };

  const glowColors = {
    default: 'shadow-[0_0_20px_rgba(16,185,129,0.1)]',
    accent: 'shadow-[0_0_20px_rgba(6,182,212,0.15)]',
    warning: 'shadow-[0_0_20px_rgba(245,158,11,0.1)]',
    critical: 'shadow-[0_0_20px_rgba(239,68,68,0.1)]'
  };

  return (
    <div className={cn(
      "relative rounded-lg border backdrop-blur-sm overflow-hidden",
      "transition-all duration-300",
      variantStyles[variant],
      glowColors[variant],
      "hover:shadow-[0_0_30px_rgba(16,185,129,0.15)]",
      className
    )}>
      <div 
        className="absolute inset-0 opacity-[0.015] pointer-events-none"
        style={{
          backgroundImage: `linear-gradient(rgba(16,185,129,0.4) 1px, transparent 1px),
                           linear-gradient(90deg, rgba(16,185,129,0.4) 1px, transparent 1px)`,
          backgroundSize: '20px 20px'
        }}
      />
      
      <div className="absolute -left-px top-6 bottom-6 w-px bg-gradient-to-b from-transparent via-primary/50 to-transparent" />
      <div className="absolute -right-px top-6 bottom-6 w-px bg-gradient-to-b from-transparent via-primary/30 to-transparent" />
      
      {title && (
        <div className={cn(
          "relative border-b px-5 md:px-6 py-3.5 md:py-4 bg-background/20",
          headerAccent[variant]
        )}>
          <div className="flex items-center justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2.5 md:gap-3">
                <h3 className="text-xs md:text-sm font-bold uppercase tracking-widest text-foreground/90">
                  {title}
                </h3>
                {badge}
              </div>
              {subtitle && (
                <p className="text-[10px] md:text-xs text-muted-foreground mt-1 md:mt-1.5 uppercase tracking-wide">
                  {subtitle}
                </p>
              )}
            </div>
          </div>
          <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent" />
        </div>
      )}
      
      <div className="relative p-4 md:p-6">
        {children}
      </div>

      <div className="absolute top-0 left-0 w-3 h-3 border-l-2 border-t-2 border-primary/40" />
      <div className="absolute top-0 right-0 w-3 h-3 border-r-2 border-t-2 border-primary/40" />
      <div className="absolute bottom-0 left-0 w-3 h-3 border-l-2 border-b-2 border-primary/40" />
      <div className="absolute bottom-0 right-0 w-3 h-3 border-r-2 border-b-2 border-primary/40" />
      
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-16 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent" />
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-16 h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent" />
    </div>
  );
}
