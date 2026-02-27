import { Crosshair } from '@phosphor-icons/react';
import { useMousePosition } from '@/hooks/useMousePosition';

export function SniperReticle() {
  const mousePosition = useMousePosition();

  return (
    <div
      className="fixed pointer-events-none z-[100] scope-reticle will-change-transform"
      style={{
        left: `${mousePosition.x}px`,
        top: `${mousePosition.y}px`,
        transform: 'translate(-50%, -50%)',
      }}
    >
      <div className="relative">
        <Crosshair
          size={40}
          weight="regular"
          className="text-destructive"
        />
        
        {/* simplified pulse to reduce layout thrash */}
        <div className="absolute inset-0 flex items-center justify-center scope-marker">
          <div className="w-10 h-10 border border-destructive/30 rounded-full" />
        </div>
        
        {/* remove continuous spin animation to avoid GPU churn */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-14 h-14 border border-dashed border-destructive/30 rounded-full" />
        </div>
        
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
          <div className="w-1 h-1 bg-destructive rounded-full" />
        </div>

        <div className="absolute left-1/2 top-0 -translate-x-1/2 -translate-y-8 scope-marker">
          <div className="h-6 w-px bg-destructive/60 shadow-[0_0_4px_rgba(255,0,0,0.5)]" />
        </div>
        
        <div className="absolute left-1/2 bottom-0 -translate-x-1/2 translate-y-8 scope-marker">
          <div className="h-6 w-px bg-destructive/60 shadow-[0_0_4px_rgba(255,0,0,0.5)]" />
        </div>
        
        <div className="absolute top-1/2 left-0 -translate-y-1/2 -translate-x-8 scope-marker">
          <div className="w-6 h-px bg-destructive/60 shadow-[0_0_4px_rgba(255,0,0,0.5)]" />
        </div>
        
        <div className="absolute top-1/2 right-0 -translate-y-1/2 translate-x-8 scope-marker">
          <div className="w-6 h-px bg-destructive/60 shadow-[0_0_4px_rgba(255,0,0,0.5)]" />
        </div>

        <div className="absolute top-full left-1/2 -translate-x-1/2 mt-6 text-[10px] font-mono text-destructive/80 whitespace-nowrap tracking-wider">
          X:{Math.round(mousePosition.x)} Y:{Math.round(mousePosition.y)}
        </div>
      </div>
    </div>
  );
}
