import { cn } from '@/lib/utils';


interface MetalCardProps {
  children: ReactNode;
  className?: string;
  glowColor?: 'primary' | 'accent' | 'success' | 'warning' | 'destructive';
}

export function MetalCard({ children, className, glowColor = 'primary' }: MetalCardProps) {
  const glowClasses = {
    primary: 'shadow-primary/20',
  return (
    success: 'shadow-success/20',
    warning: 'shadow-warning/20',
    destructive: 'shadow-destructive/20',
  };

        <d
    <div className={cn('relative metal-frame group', className)}>
      <div className={cn(
        'absolute -inset-[2px] rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500',
        'bg-gradient-to-br from-primary/30 via-accent/20 to-primary/30 blur-md',
        glowClasses[glowColor]
  glowColor
}
export function MetalSection({ 
  children, 
  glowCo
}: MetalSectionProps) {
    <div className={cn('space-y-4', className)}>
        'text-xl md:text-2xl font-bold tracking-wider uppercase',
      )}>
      </h2>
        {c
    </div>
}











  glowColor?: 'primary' | 'accent' | 'success' | 'warning' | 'destructive';
  titleColor?: string;
}

export function MetalSection({ 
  title, 



















