import { Link } from 'react-router-dom';
import { LiveTicker } from '@/components/LiveTicker';
import { MetricsGrid } from '@/components/landing/MetricsGrid';
import { SystemStatus } from '@/components/landing/SystemStatus';
import { modules } from '@/config/landingConfig';
import { useTelemetry } from '@/hooks/useTelemetry';
import { Button } from '@/components/ui/button';
import { TopBar } from '@/components/TopBar/TopBar';
import { Crosshair, MagnifyingGlass, Robot } from '@phosphor-icons/react';

export function Landing() {
  const { metrics, system } = useTelemetry();
  const contextModules = modules.filter(m => !['scanner', 'bot'].includes(m.key));

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
              <div className="space-y-6">
                <div className="flex items-center gap-4">
                  <Crosshair size={64} weight="thin" className="text-accent opacity-40" />
                  <h1 className="text-5xl md:text-7xl font-bold tracking-tight">SniperSight</h1>
                </div>
                <p className="text-xl md:text-2xl text-muted-foreground max-w-3xl leading-relaxed">Precision crypto market reconnaissance and disciplined execution. Identify high-quality targets, validate confluence, deploy with risk control.</p>
              </div>

              {/* Primary CTAs */}
              <div className="flex flex-wrap items-center gap-4 pt-4">
              </div>
            </div>
          </div>
        </section>

        {/* Market ticker strip */}
        <section className="relative border-y border-border/40">
          <LiveTicker />
        </section>

        {/* Recon scanner section */}
        <section className="relative py-16 md:py-20 bg-card/20">
          <div className="max-w-6xl mx-auto px-6 md:px-8">
            <div className="max-w-3xl mx-auto text-center">
              <div className="space-y-6">

                <p className="text-lg text-muted-foreground leading-relaxed">Deploy the multi-timeframe scanner to sweep for actionable targets, validate liquidity, and surface the highest-probability entries with tactical context baked in.</p>
                <div className="flex flex-col sm:flex-row gap-4 pt-4 justify-center">
                  <Button asChild size="lg" className="w-full sm:w-auto">
                    <Link to="/scanner/setup"></Link>
                  </Button>
                  <Button asChild variant="outline" size="lg" className="w-full sm:w-auto">
                    <Link to="/scanner/results"></Link>
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* SniperBot automation section */}
        <section className="relative py-16 md:py-20">
          <div className="max-w-6xl mx-auto px-6 md:px-8">
            <div className="grid md:grid-cols-2 gap-12 items-center">
              <div className="order-2 md:order-1 rounded-lg border border-border/60 bg-card/40 p-8 md:p-12">
                <div className="space-y-4 text-sm text-muted-foreground">
                  <div className="flex items-start gap-3">
                    <div className="w-1.5 h-1.5 rounded-full bg-warning mt-2" />
                    <p>Risk failsafes and circuit breakers</p>
                  </div>
                </div>
              </div>
              <div className="order-1 md:order-2 space-y-6">
                <div className="inline-flex items-center gap-3 px-4 py-2 rounded-full border border-warning/40 bg-warning/5">
                  <Robot size={20} weight="bold" className="text-warning" />
                  <span className="text-sm font-medium text-warning">Execution Bot</span>
                </div>
                <h2 className="text-3xl md:text-4xl font-bold">
                  SniperBot Automation
                </h2>
                <p className="text-lg text-muted-foreground leading-relaxed">
                  Hand off qualified plays to automated execution with position sizing, failsafes, and telemetry so every move is disciplined and repeatable.
                </p>
                <div className="flex flex-col sm:flex-row gap-4 pt-4">
                  <Button asChild size="lg" variant="secondary" className="w-full sm:w-auto">
                    <Link to="/bot/setup">Deploy Bot</Link>
                  </Button>
                  <Button asChild variant="outline" size="lg" className="w-full sm:w-auto">
                    <Link to="/bot/status">Monitor Status</Link>
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Intel & Market Context section */}
        <section className="relative py-16 md:py-20 bg-card/20">
          <div className="max-w-6xl mx-auto px-6 md:px-8 space-y-8">
            <div className="space-y-3">
              <p className="text-xs uppercase tracking-[0.25em] text-muted-foreground">CONTEXT UTILITIES</p>
              <h2 className="text-3xl md:text-4xl font-bold">
                Intel & Market Context
              </h2>
              <p className="text-lg text-muted-foreground max-w-2xl">
                Keep every decision anchored to live market intel, volatility regimes, and saved playbooks so the scanner and bot act within the right operating picture.
              </p>
            </div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {contextModules.map((module) => {
                const Icon = module.icon;
                return (
                  <Link
                    key={module.key}
                    to={module.destination}
                    className="group rounded-lg border border-border/60 bg-card/40 p-6 hover:bg-card/60 hover:border-border transition-all"
                  >
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 rounded-md flex items-center justify-center border border-border/60 bg-background/40 group-hover:scale-105 transition-transform">
                        <Icon size={24} weight="bold" />
                      </div>
                      <div className="space-y-2 flex-1">
                        <h3 className="text-lg font-semibold">{module.title}</h3>
                        <p className="text-sm text-muted-foreground leading-relaxed">
                          {module.description}
                        </p>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
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
