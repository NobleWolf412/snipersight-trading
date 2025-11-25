import { cn } from '@/lib/utils';
import { ReactNode } from 'react';

interface MetalCardProps {
  children: ReactNode;
  className?: string;
  title?: string;
  glowColor?: string;
}

export function MetalCard({ 
  children,
  className,
  title,
  glowColor = 'primary'
}: MetalCardProps) {
  return (
    <div className={cn('metal-frame command-panel p-6', className)}>
      {title && (
        <div className="mb-4 text-lg font-semibold text-foreground">
          {title}
        </div>
      )}
      <div className="relative z-10">
        {children}
      </div>
    </div>
  );
}

interface MetalSectionProps {
  children: ReactNode;
  className?: string;
  title?: string;
  glowColor?: string;
  titleColor?: string;
}

export function MetalSection({ 
  children,
  className,
  title,
  glowColor = 'primary',
  titleColor = 'text-primary'
}: MetalSectionProps) {
  return (
    <div className={cn('command-panel p-6', className)}>
      {title && (
        <div className={cn('mb-6 text-xl font-bold uppercase tracking-wider', titleColor)}>
          {title}
        </div>
      )}
      <div className="relative z-10">
        {children}
      </div>
    </div>
  );
}
