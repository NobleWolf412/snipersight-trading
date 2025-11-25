import { cn } from '@/lib/utils';
import { ReactNode } from 'react';

interface MetalCardProps {
  children: ReactNode;
  className?: string;
}

export function MetalCard({ 
  children,
  className
}: MetalCardProps) {
  return (
    <div className={cn(
      'relative bg-card border border-border rounded-xl p-6 backdrop-blur-sm shadow-lg',
      className
    )}>
      {children}
    </div>
  );
}

interface MetalSectionProps {
  children: ReactNode;
  title?: string;
  className?: string;
  titleColor?: string;
  glowColor?: 'primary' | 'accent' | 'success' | 'warning' | 'destructive';
}

export function MetalSection({
  children,
  title, 
  className,
  titleColor = 'text-primary',
  glowColor = 'primary'
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
