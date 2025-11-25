import { cn } from '@/lib/utils';
import { ReactNode } from 'react';

type MetalCardProps = {
  children: ReactNode;
  title?: string;
  className?: string;
  glowColor?: string;
  titleColor?: string;
};

export function MetalCard({
  children,
  title,
  className,
  glowColor = 'emerald',
  titleColor = 'text-primary'
}: MetalCardProps) {
  const glowClasses = {
    emerald: 'shadow-[0_0_30px_rgba(16,185,129,0.3)] ring-emerald-400/25',
    red: 'shadow-[0_0_30px_rgba(239,68,68,0.3)] ring-red-500/25',
    amber: 'shadow-[0_0_30px_rgba(245,158,11,0.3)] ring-amber-500/25',
    cyan: 'shadow-[0_0_30px_rgba(6,182,212,0.3)] ring-cyan-400/25'
  };

  return (
    <div className={cn("relative metal-panel rounded-2xl overflow-hidden", className)}>
      <div className="pointer-events-none absolute inset-0">
        <span className="metal-rivet absolute left-4 top-4" />
        <span className="metal-rivet absolute right-4 top-4" />
        <span className="metal-rivet absolute left-4 bottom-4" />
        <span className="metal-rivet absolute right-4 bottom-4" />
      </div>

      <div className={cn(
        "pointer-events-none absolute inset-0 ring-1",
        glowClasses[glowColor as keyof typeof glowClasses] || glowClasses.emerald
      )} />

      <div className="relative p-4 md:p-6">
        {title && (
          <div className="mb-4">
            <h3 className={cn("text-lg font-semibold", titleColor)}>{title}</h3>
          </div>
        )}
        {children}
      </div>
    </div>
  );
}

export const MetalSection = MetalCard;
