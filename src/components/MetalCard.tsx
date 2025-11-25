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
  glowColor?: string;
  titleColor?: string;
}

export function MetalSection({ 
  children,
  title,
  className,
  glowColor,
  titleColor
}: MetalSectionProps) {
  return (
    <div className={cn('space-y-4', className)}>
      {title && (
        <h2 className={cn(
          'text-lg font-semibold',
          titleColor || 'text-primary'
        )}>
          {title}
        </h2>
      )}
      {children}
    </div>
  );
}
