import { Crosshair } from '@phosphor-icons/react';
import { useMousePosition } from '@/hooks/useMousePosition';

export function SniperReticle() {
  const mousePosition = useMousePosition();

  return (
    <div
      className="fixed pointer-events-none z-[100] scope-reticle"
      style={{
        left: `${mousePosition.x}px`,
        top: `${mousePosition.y}px`,
        transform: 'translate(-50%, -50%)',
        transition: 'left 0.05s ease-out, top 0.05s ease-out',
      }}
    >
      <div className="relative">
        <Crosshair 
          size={48} 
          weight="thin" 
          className="text-destructive hud-glow-red drop-shadow-[0_0_10px_rgba(255,0,0,0.8)]" 
        />
        
        <div className="absolute inset-0 flex items-center justify-center scope-marker">
          <div className="w-12 h-12 border border-destructive/40 rounded-full animate-ping" />
        </div>
        
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-16 h-16 border border-dashed border-destructive/30 rounded-full animate-[spin_3s_linear_infinite]" />
        </div>
        
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
          <div className="w-1 h-1 bg-destructive rounded-full shadow-[0_0_8px_rgba(255,0,0,1)] animate-pulse" />
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

        <div className="absolute top-full left-1/2 -translate-x-1/2 mt-8 text-[10px] font-mono text-destructive/80 whitespace-nowrap tracking-wider drop-shadow-[0_0_4px_rgba(255,0,0,0.6)]">
          X:{Math.round(mousePosition.x)} Y:{Math.round(mousePosition.y)}
        </div>
      </div>
    </div>
  );
}
