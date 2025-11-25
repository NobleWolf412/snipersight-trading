import { cn } from '@/lib/utils';
import { ReactNode } from 'react';

interface MetalCardProps {
  children: ReactNode;
  className?: string;
  glowColor?: 'primary' | 'accent' | 'success' | 'warning' | 'destructive';
}

export function MetalCard({ 
  children, 
  className,
  glowColor = 'primary'
}: MetalCardProps) {
  const glowClasses = {
    primary: 'shadow-primary/20',
    accent: 'shadow-accent/20',
    success: 'shadow-success/20',
    warning: 'shadow-warning/20',
    destructive: 'shadow-destructive/20',
  };

  return (
    <div className={cn(
      'bg-gradient-to-br from-card to-card/80 border border-border rounded-xl p-6 backdrop-blur-sm',
      'shadow-lg',
      glowClasses[glowColor],
      className
    )}>
      {children}
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
  const glowClasses = {
    primary: 'hud-glow-green',
    accent: 'hud-glow-cyan',
    success: 'hud-glow',
    warning: 'hud-glow-amber',
    destructive: 'hud-glow-red',
  };

  return (
    <div className={cn('space-y-4', className)}>
      {title && (
        <h2 className={cn(
          'text-xl font-bold tracking-tight',
          titleColor,
          glowClasses[glowColor]
        )}>
          {title}
        </h2>
      )}
      <div className="relative bg-card border border-border rounded-xl p-6 backdrop-blur-sm">
        {children}
      </div>
    </div>
  );
}
