import { cn } from '@/lib/utils';
import { ReactNode } from 'react';

interface MetalCardProps {
  children: ReactNode;
  className?: string;
  glowColor?: 'primary' | 'accent' | 'success' | 'warning' | 'destructive';
}

export function MetalCard({ children, className, glowColor = 'primary' }: MetalCardProps) {
  const glowClasses = {
    primary: 'shadow-primary/20',
    accent: 'shadow-accent/20',
    success: 'shadow-success/20',
    warning: 'shadow-warning/20',
    destructive: 'shadow-destructive/20',
  };

  return (
    <div className={cn('relative metal-frame group', className)}>
      <div className={cn(
        'absolute -inset-[2px] rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500',
        'bg-gradient-to-br from-primary/30 via-accent/20 to-primary/30 blur-md',
        glowClasses[glowColor]
      )} />
      <div className="relative bg-card border border-border rounded-xl p-6 backdrop-blur-sm">
        {children}
      </div>
    </div>
  );
}

interface MetalSectionProps {
  title?: string;
  children: ReactNode;
  className?: string;
  glowColor?: 'primary' | 'accent' | 'success' | 'warning' | 'destructive';
  titleColor?: string;
}

export function MetalSection({ 
  title, 
  children, 
  className,
  glowColor = 'primary',
  titleColor = 'text-primary'
}: MetalSectionProps) {
  return (
    <div className={cn('space-y-4', className)}>
      {title && (
        <h2 className={cn(
          'text-xl md:text-2xl font-bold tracking-wider uppercase',
          titleColor
        )}>
          {title}
        </h2>
      )}
      {children}
    </div>
  );
}
