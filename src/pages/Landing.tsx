import { SystemStatus } from '@/components/landing/SystemStatus';
import { HeroSection } from '@/components/landing/HeroSection';
import { FeatureTabs } from '@/components/landing/FeatureTabs';
import { TacticalDivider } from '@/components/landing/TacticalDivider';
import { useTelemetry } from '@/hooks/useTelemetry';
import { PageContainer } from '@/components/layout/PageContainer';
import { LandingProvider, useLandingData } from '@/context/LandingContext';
import { LandingLoader } from '@/components/landing/LandingLoader';

function LandingContent() {
  const { system } = useTelemetry();
  const { isLoading, error } = useLandingData();

  if (isLoading) {
    return <LandingLoader />;
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-destructive p-4 text-center">
        <div className="space-y-4">
          <div className="text-xl font-bold tracking-widest">SYSTEM OFFLINE</div>
          <div className="text-sm text-muted-foreground">{error}</div>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-destructive/10 hover:bg-destructive/20 rounded border border-destructive/30 text-destructive text-sm font-bold transition-colors"
          >
            RETRY CONNECTION
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen overflow-hidden" id="main-content">
      <main>
        {/* Hero Section - Full Height */}
        <HeroSection />

        {/* Animated Tactical Page Break */}
        {/* <TacticalDivider className="mt-24 mb-32 relative z-50" height="h-48" /> */}

        {/* Complete Trading Arsenal - The only remaining section */}
        <FeatureTabs />

        {/* Footer with system status */}
        <footer className="relative py-16 mt-12">
          <div className="section-divider max-w-4xl mx-auto mb-12" />
          <PageContainer>
            <div className="glass-card p-8">
              <SystemStatus data={system} />
            </div>
          </PageContainer>
        </footer>
      </main>
    </div>
  );
}

export function Landing() {
  return (
    <LandingProvider>
      <LandingContent />
    </LandingProvider>
  );
}
