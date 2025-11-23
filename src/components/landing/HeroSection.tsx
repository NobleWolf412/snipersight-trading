import { LiveTicker } from '@/components/LiveTicker';
import { Crosshair } from '@phosphor-icons/react';

export function HeroSection() {
  return (
    <header className="relative space-y-8" id="hero">
      <div className="flex items-center gap-3 text-xs tracking-widest text-accent">
        <div className="w-2 h-2 bg-accent rounded-full animate-pulse" />
        <span>SYSTEM OPERATIONAL</span>
      </div>
      <div className="space-y-5 relative z-10">
        <h1 className="text-5xl md:text-6xl font-bold tracking-tight">SniperSight</h1>
        <p className="text-lg text-muted-foreground max-w-2xl leading-relaxed">
          Precision crypto market reconnaissance and disciplined execution.
          Identify high-quality targets, validate confluence, deploy with risk control.
        </p>
      </div>
      <LiveTicker className="rounded-md border border-border/60 relative z-10" />
      {/* Decorative reticle moved further out, thinner and subtler */}
      <div className="absolute -top-6 -right-24 w-56 h-56 rounded-full bg-accent/5 border border-accent/30 flex items-center justify-center pointer-events-none opacity-15">
        <Crosshair size={120} weight="thin" className="text-accent" />
      </div>
    </header>
  );
}
