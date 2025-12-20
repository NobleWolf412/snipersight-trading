import { SystemStatus } from '@/components/landing/SystemStatus';
import { TacticalBriefing } from '@/components/landing/TacticalBriefing';
import { MarketCyclesBrief } from '@/components/landing/MarketCyclesBrief';
import { HTFOpportunities } from '@/components/landing/HTFOpportunities';
import { HeroSection } from '@/components/landing/HeroSection';
import { StatsBar } from '@/components/landing/StatsBar';
import { FeatureTabs } from '@/components/landing/FeatureTabs';
import { useTelemetry } from '@/hooks/useTelemetry';
import { PageContainer } from '@/components/layout/PageContainer';
import { LandingProvider, useLandingData } from '@/context/LandingContext';
import { LandingLoader } from '@/components/landing/LandingLoader';
import { motion } from 'framer-motion';

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

        {/* Stats Bar */}
        <StatsBar />

        {/* Section Divider */}
        <div className="section-divider max-w-4xl mx-auto" />

        {/* HTF Tactical Opportunities - Live High-Confidence Setups */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="py-16"
        >
          <PageContainer>
            <div className="text-center mb-8">
              <h2 className="hud-headline text-xl md:text-2xl text-foreground mb-2">
                Priority Targets
              </h2>
              <p className="text-sm text-muted-foreground tracking-wider">
                Live high-confidence setups detected by the scanner
              </p>
            </div>
            <div className="glass-card glow-border-red p-6">
              <HTFOpportunities />
            </div>
          </PageContainer>
        </motion.section>

        {/* Section Divider */}
        <div className="section-divider max-w-4xl mx-auto" />

        {/* Intelligence Grid - Tactical Briefing & Market Cycles */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="py-16"
        >
          <PageContainer>
            <div className="text-center mb-8">
              <h2 className="hud-headline text-xl md:text-2xl text-foreground mb-2">
                Market Intelligence
              </h2>
              <p className="text-sm text-muted-foreground tracking-wider">
                Macro context and cycle analysis at a glance
              </p>
            </div>
            <div className="grid md:grid-cols-2 gap-6">
              <div className="glass-card glow-border-green p-6">
                <TacticalBriefing />
              </div>
              <div className="glass-card glow-border-amber p-6">
                <MarketCyclesBrief />
              </div>
            </div>
          </PageContainer>
        </motion.section>

        {/* Section Divider */}
        <div className="section-divider max-w-4xl mx-auto" />

        {/* Feature Tabs */}
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

