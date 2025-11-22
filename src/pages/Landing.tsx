import { HeroSection } from '@/components/landing/HeroSection';
import { ModuleCard } from '@/components/landing/ModuleCard';
import { MetricsGrid } from '@/components/landing/MetricsGrid';
import { SystemStatus } from '@/components/landing/SystemStatus';
import { modules } from '@/config/landingConfig';
import { useTelemetry } from '@/hooks/useTelemetry';

export function Landing() {
  const { metrics, system } = useTelemetry();
  const primary = modules.filter(m => m.tier === 'primary');
  const secondary = modules.filter(m => m.tier === 'secondary');

  return (
    <main className="relative min-h-[calc(100vh-4rem)] overflow-hidden bg-gradient-to-b from-background via-background/95 to-background">
      <div className="absolute inset-0 tactical-grid opacity-25" aria-hidden />
      <div className="relative max-w-6xl mx-auto px-6 md:px-8 py-16 space-y-14">
        <HeroSection />

        <section aria-label="Key Metrics" className="space-y-6">
          <MetricsGrid metrics={metrics} />
        </section>

        <section aria-label="Primary Modules" className="space-y-6">
          <div className="grid lg:grid-cols-3 gap-6">
            {primary.map(m => <ModuleCard key={m.key} module={m} />)}
          </div>
        </section>

        {secondary.length > 0 && (
          <section aria-label="Secondary Modules" className="space-y-4">
            <div className="grid md:grid-cols-3 gap-4">
              {secondary.map(m => <ModuleCard key={m.key} module={m} />)}
            </div>
          </section>
        )}

        <SystemStatus data={system} />
      </div>
    </main>
  );
}
