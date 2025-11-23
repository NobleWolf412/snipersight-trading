import { LiveTicker } from '@/components/LiveTicker';
import { SystemStatus } from '@/components/landing/SystemStatus';
import { useTelemetry } from '@/hooks/useTelemetry';
import { TopBar } from '@/components/TopBar/TopBar';
import { Crosshair } from '@phosphor-icons/react';

export function Landing() {
  const { system } = useTelemetry();

  return (
    <div className="relative min-h-screen overflow-hidden bg-background">
      {/* Header with TopBar */}
      <header className="sticky top-0 z-50 border-b border-border/60 bg-background/95 backdrop-blur-sm">
        <TopBar />
      </header>
      <main>
        {/* Tactical grid background */}
        <div className="fixed inset-0 tactical-grid opacity-20 pointer-events-none" aria-hidden="true" />

        {/* Hero section */}
        <section className="relative py-16 md:py-24">
          <div className="max-w-6xl mx-auto px-6 md:px-8">
            <div className="relative space-y-8">
              {/* Status indicator */}
              <div className="flex items-center gap-3 text-xs tracking-widest text-accent">
                <div className="w-2 h-2 bg-accent rounded-full animate-pulse" />
                <span>SYSTEM OPERATIONAL</span>
              </div>

              {/* Hero title and subtitle */}
              <div className="space-y-6 text-center">
                <div className="flex items-center justify-center gap-4">
                  <Crosshair size={64} weight="thin" className="text-accent opacity-40" />
                  <h1 className="text-5xl md:text-7xl font-bold tracking-tight">SniperSight</h1>
                </div>
                <p className="text-xl md:text-2xl text-muted-foreground max-w-3xl leading-relaxed mx-auto">Precision crypto market reconnaissance and disciplined execution. Identify high-quality targets, validate confluence, deploy with risk control.</p>
              </div>
            </div>
          </div>
        </section>

        {/* Market ticker strip */}
        <section className="relative border-y border-border/40">
          <LiveTicker />
        </section>



        {/* Footer with system status */}
        <footer className="relative py-12 border-t border-border/40">
          <div className="max-w-6xl mx-auto px-6 md:px-8">
            <SystemStatus data={system} />
          </div>
        </footer>
      </main>
    </div>
  );
}
