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
      
      <div className="relative rounded-xl overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-border/40 via-border/20 to-border/40" />
        
        <div className="relative m-[2px] rounded-xl bg-gradient-to-br from-card/95 to-background/95 backdrop-blur-sm">
          <div className="absolute top-3 left-3 w-3 h-3 rounded-full bg-border/60 shadow-inner" />
          <div className="absolute top-3 right-3 w-3 h-3 rounded-full bg-border/60 shadow-inner" />
          <div className="absolute bottom-3 left-3 w-3 h-3 rounded-full bg-border/60 shadow-inner" />
          <div className="absolute bottom-3 right-3 w-3 h-3 rounded-full bg-border/60 shadow-inner" />
          
          <div className="relative p-6 md:p-8">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}

interface MetalSectionProps {
  title: string;
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
      <h2 className={cn(
        'text-xl md:text-2xl font-bold tracking-wider uppercase',
        titleColor
      )}>
        {title}
      </h2>
      <MetalCard glowColor={glowColor}>
        {children}
      </MetalCard>
    </div>
  );
}
