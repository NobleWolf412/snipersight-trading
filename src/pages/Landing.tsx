import { Link } from 'react-router-dom';
import { HeroSection } from '@/components/landing/HeroSection';
import { ModuleCard } from '@/components/landing/ModuleCard';
import { MetricsGrid } from '@/components/landing/MetricsGrid';
import { SystemStatus } from '@/components/landing/SystemStatus';
import { modules } from '@/config/landingConfig';
import { useTelemetry } from '@/hooks/useTelemetry';
import { SectionDivider } from '@/components/layout/SectionDivider';
import { SidebarNav } from '@/components/layout/SidebarNav';
import { Button } from '@/components/ui/button';
import { TopBar } from '@/components/TopBar/TopBar';

export function Landing() {
  const { metrics, system } = useTelemetry();
  const scannerModule = modules.find(m => m.key === 'scanner');
  const botModule = modules.find(m => m.key === 'bot');
  const contextModules = modules.filter(m => !['scanner', 'bot'].includes(m.key));

  return (
    <div className="relative min-h-screen overflow-hidden bg-gradient-to-b from-background via-background/95 to-background">
      <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <TopBar />
      </header>

      <main>
        <div className="absolute inset-0 tactical-grid opacity-25" aria-hidden />

        <section
          className="relative max-w-7xl mx-auto px-6 lg:px-16 py-12 lg:py-20"
          aria-labelledby="hero-overview"
          id="hero-overview"
        >
          <div className="space-y-10">
            <div className="space-y-4">
              <h2 id="hero-overview" className="text-sm uppercase tracking-[0.2em] text-muted-foreground">
                Situational Overview
              </h2>
              <HeroSection />
            </div>
            <div className="rounded-2xl border border-border/70 bg-card/40 p-6 shadow-inner">
              <h2 className="text-lg font-semibold text-foreground mb-3">Operational Telemetry</h2>
              <p className="text-sm text-muted-foreground mb-6">
                Live counters to confirm data uplinks, signal health, and exchange readiness before deploying any scans or automated plays.
              </p>
              <MetricsGrid metrics={metrics} />
            </div>
          </div>
        </section>

        <SectionDivider />

        <div className="relative max-w-7xl mx-auto px-6 lg:px-16 pb-12 xl:flex xl:items-start xl:gap-12">
          <SidebarNav />
          <div className="flex-1 space-y-16">
            <section aria-labelledby="scanner-section" id="scanner" className="space-y-6">
              <div className="flex flex-col gap-3">
                <p className="text-sm uppercase tracking-[0.2em] text-muted-foreground">Scanner</p>
                <h2 id="scanner-section" className="text-2xl font-bold text-foreground">Recon Scanner</h2>
                <p className="text-muted-foreground leading-relaxed">
                  Deploy the multi-timeframe scanner to sweep for actionable targets, validate liquidity, and surface the highest-probability entries with tactical context baked in.
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  <Button asChild size="lg">
                    <Link to="/scanner/setup">Configure Scanner</Link>
                  </Button>
                  <Button asChild variant="ghost" size="lg">
                    <Link to="/scanner/results">View Scan Results</Link>
                  </Button>
                </div>
              </div>
              {scannerModule && (
                <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-6 lg:gap-8">
                  <ModuleCard key={scannerModule.key} module={scannerModule} />
                </div>
              )}
            </section>

            <SectionDivider />

            <section aria-labelledby="bot-section" id="bot" className="space-y-6">
              <div className="flex flex-col gap-3">
                <p className="text-sm uppercase tracking-[0.2em] text-muted-foreground">Execution Bot</p>
                <h2 id="bot-section" className="text-2xl font-bold text-foreground">SniperBot Automation</h2>
                <p className="text-muted-foreground leading-relaxed">
                  Hand off qualified plays to automated execution with position sizing, failsafes, and telemetry so every move is disciplined and repeatable.
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  <Button asChild size="lg" variant="secondary">
                    <Link to="/bot/setup">Deploy Bot Loadout</Link>
                  </Button>
                  <Button asChild variant="ghost" size="lg">
                    <Link to="/bot/status">Monitor Live Bot</Link>
                  </Button>
                </div>
              </div>
              {botModule && (
                <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-6 lg:gap-8">
                  <ModuleCard key={botModule.key} module={botModule} />
                </div>
              )}
            </section>

            <SectionDivider />

            <section aria-labelledby="context-utilities" id="context-utilities" className="space-y-6">
              <div className="flex flex-col gap-3">
                <p className="text-sm uppercase tracking-[0.2em] text-muted-foreground">Context Utilities</p>
                <h2 id="context-utilities" className="text-2xl font-bold text-foreground">Intel & Market Context</h2>
                <p className="text-muted-foreground leading-relaxed">
                  Keep every decision anchored to live market intel, volatility regimes, and saved playbooks so the scanner and bot act within the right operating picture.
                </p>
              </div>
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 lg:gap-6">
                {contextModules.map(m => <ModuleCard key={m.key} module={m} />)}
              </div>
            </section>

            <SectionDivider />

            <footer aria-label="System Status" id="status" className="pt-2">
              <div className="mb-4 flex items-center justify-between flex-wrap gap-3">
                <div>
                  <p className="text-sm uppercase tracking-[0.2em] text-muted-foreground">Status &amp; Safeguards</p>
                  <h2 className="text-lg font-semibold text-foreground">Operational Readiness</h2>
                  <p className="text-sm text-muted-foreground">Connection health, data streams, and risk interlocks before deploying automation.</p>
                </div>
              </div>
              <SystemStatus data={system} />
            </footer>
          </div>
        </div>
      </main>
    </div>
  );
}
