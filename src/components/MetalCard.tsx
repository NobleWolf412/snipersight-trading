import { cn } from '@/lib/utils';
import { ReactNode } from 'react';

interface MetalCardProps {
  children: ReactNode;
  className?: string;
    accent: 'shadow-accent/20',
 

  return (
      <div className={c
        'bg-gradient-to-br from-p
    accent: 'shadow-accent/20',
        {children}
    </div>
}
inte

  return (
}
export function MetalSect
  children, 
  glowColor = 'primary',
}: MetalSectionProps) {
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













