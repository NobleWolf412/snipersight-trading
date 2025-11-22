import { LiveTicker } from '@/components/LiveTicker';
import { Crosshair } from '@phosphor-icons/react';

export function HeroSection() {
  return (
    <header className="space-y-8">
      <div className="flex items-center gap-3 text-xs tracking-widest text-accent">
        <div className="w-2 h-2 bg-accent rounded-full animate-pulse" />
        <span>SYSTEM OPERATIONAL</span>
      </div>
      <div className="space-y-5">
        <h1 className="text-5xl md:text-6xl font-bold tracking-tight">SniperSight</h1>
        <p className="text-lg text-muted-foreground max-w-2xl leading-relaxed">
          Precision crypto market reconnaissance and disciplined execution.
          Identify high-quality targets, validate confluence, deploy with risk control.
        </p>
      </div>
      <LiveTicker className="rounded-md border border-border/60" />
      <div className="absolute -top-16 -right-12 w-32 h-32 rounded-full bg-accent/10 border border-accent/40 flex items-center justify-center pointer-events-none">
        <Crosshair size={42} weight="bold" className="text-accent" />
      </div>
    </header>
  );
}
