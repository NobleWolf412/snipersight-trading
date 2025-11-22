import { HeroSection } from '@/components/landing/HeroSection';
import { ModuleCard } from '@/components/landing/ModuleCard';
import { MetricsGrid } from '@/components/landing/MetricsGrid';
import { SystemStatus } from '@/components/landing/SystemStatus';
import { modules } from '@/config/landingConfig';
import { useTelemetry } from '@/hooks/useTelemetry';
import { SectionDivider } from '@/components/layout/SectionDivider';
import { SidebarNav } from '@/components/layout/SidebarNav';

export function Landing() {
  const { metrics, system } = useTelemetry();
  const primary = modules.filter(m => m.tier === 'primary');
  const secondary = modules.filter(m => m.tier === 'secondary');

  return (
    <main className="relative min-h-screen overflow-hidden bg-gradient-to-b from-background via-background/95 to-background">
      <div className="absolute inset-0 tactical-grid opacity-25" aria-hidden />

      {/* Hero */}
      <section className="relative max-w-7xl mx-auto px-6 lg:px-16 py-12 lg:py-20" aria-label="Hero" id="hero">
        <HeroSection />
      </section>
      <SectionDivider />

      {/* Content with sidebar */}
      <div className="relative max-w-7xl mx-auto px-6 lg:px-16 pb-12 xl:flex xl:items-start xl:gap-12">
        <SidebarNav />
        <div className="flex-1 space-y-16">
          <section aria-label="Key Metrics" id="metrics">
            <h2 className="sr-only">Key Operational Metrics</h2>
            <MetricsGrid metrics={metrics} />
          </section>
          <SectionDivider />
          <section aria-label="Primary Modules" id="primary-modules">
            <h2 className="sr-only">Core Trading Tools</h2>
            <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-6 lg:gap-8">
              {primary.map(m => <ModuleCard key={m.key} module={m} />)}
            </div>
          </section>
          {secondary.length > 0 && (
            <>
              <SectionDivider />
              <section aria-label="Secondary Modules" id="secondary-modules">
                <h2 className="sr-only">Additional Tools</h2>
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 lg:gap-6">
                  {secondary.map(m => <ModuleCard key={m.key} module={m} />)}
                </div>
              </section>
            </>
          )}
          <SectionDivider />
          <footer aria-label="System Status" id="status" className="pt-2">
            <SystemStatus data={system} />
          </footer>
        </div>
      </div>
    </main>
  );
}
