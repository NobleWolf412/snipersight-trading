import { cn } from '@/lib/utils';


interface MetalCardProps {
  children: ReactNode;
  className?: string;
export function MetalCard({ 
 

    primary: 'shadow-primary
    success:
    destruct

    <div className={
      'shadow-lg',
      className
      {children}
  );

  title?: string;
  cl


  title, 
  className,
  titleColor = 'te
  const glowClasses = {
    accent: 'hu
    war
  };
  return (
    
 

          {title}
      )}
        {children}
    </div>
}









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
