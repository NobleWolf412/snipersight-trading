import { LiveTicker } from '@/components/LiveTicker';
import { SystemStatus } from '@/components/landing/SystemStatus';
import { useTelemetry } from '@/hooks/useTelemetry';
import { TopBar } from '@/components/TopBar/TopBar';
import { Crosshair } from '@phosphor-icons/react';
import { Link } from 'react-router-dom';

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

        {/* Scanner & Bot Features */}
        <section className="relative py-20 md:py-32">
          <div className="max-w-6xl mx-auto px-6 md:px-8">
            <div className="grid md:grid-cols-2 gap-12 md:gap-16">
              
              {/* Scanner Feature */}
              <div className="relative group">
                <div className="absolute inset-0 bg-gradient-to-br from-accent/10 to-transparent rounded-2xl blur-2xl group-hover:blur-3xl transition-all duration-500" />
                <div className="relative p-8 md:p-10 border border-border/50 rounded-2xl bg-card/50 backdrop-blur-sm hover:border-accent/50 transition-all duration-300">
                  <div className="flex items-start gap-4 mb-6">
                    <div className="w-14 h-14 bg-accent/20 rounded-xl flex items-center justify-center flex-shrink-0">
                      <Crosshair size={28} weight="bold" className="text-accent" />
                    </div>
                    <div>
                      <h3 className="text-2xl md:text-3xl font-bold mb-2">Reconnaissance Scanner</h3>
                      <p className="text-sm text-accent font-mono tracking-wider">MANUAL OPERATIONS</p>
                    </div>
                  </div>
                  
                  <p className="text-muted-foreground leading-relaxed mb-6">
                    Multi-timeframe Smart Money Concept detection with institutional-grade confluence scoring. 
                    Identify high-probability setups across order blocks, FVGs, liquidity sweeps, and structural breaks.
                  </p>
                  
                  <div className="space-y-3 mb-8">
                    <div className="flex items-start gap-3 text-sm">
                      <div className="w-1.5 h-1.5 bg-accent rounded-full mt-2 flex-shrink-0" />
                      <span className="text-muted-foreground">Smart Money pattern detection (OB, FVG, BOS, CHoCH)</span>
                    </div>
                    <div className="flex items-start gap-3 text-sm">
                      <div className="w-1.5 h-1.5 bg-accent rounded-full mt-2 flex-shrink-0" />
                      <span className="text-muted-foreground">Multi-factor confluence with HTF alignment</span>
                    </div>
                    <div className="flex items-start gap-3 text-sm">
                      <div className="w-1.5 h-1.5 bg-accent rounded-full mt-2 flex-shrink-0" />
                      <span className="text-muted-foreground">Complete trade plans with risk management</span>
                    </div>
                    <div className="flex items-start gap-3 text-sm">
                      <div className="w-1.5 h-1.5 bg-accent rounded-full mt-2 flex-shrink-0" />
                      <span className="text-muted-foreground">Interactive chart visualization with AI analysis</span>
                    </div>
                  </div>
                  
                  <div className="flex gap-3 flex-wrap">
                    <Link
                      to="/scanner/setup"
                      className="inline-flex items-center gap-2 px-6 py-3 bg-accent/10 hover:bg-accent/20 border border-accent/30 rounded-lg text-accent font-medium transition-all duration-200 group/btn"
                    >
                      Configure Scanner
                      <span className="group-hover/btn:translate-x-1 transition-transform">→</span>
                    </Link>
                    <Link
                      to="/scanner/status"
                      className="inline-flex items-center gap-2 px-6 py-3 bg-accent/5 hover:bg-accent/10 border border-accent/20 rounded-lg text-accent/80 font-medium transition-all duration-200 group/btn"
                    >
                      View Status
                      <span className="group-hover/btn:translate-x-1 transition-transform">→</span>
                    </Link>
                  </div>
                </div>
              </div>

              {/* Bot Feature */}
              <div className="relative group">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-transparent rounded-2xl blur-2xl group-hover:blur-3xl transition-all duration-500" />
                <div className="relative p-8 md:p-10 border border-border/50 rounded-2xl bg-card/50 backdrop-blur-sm hover:border-primary/50 transition-all duration-300">
                  <div className="flex items-start gap-4 mb-6">
                    <div className="w-14 h-14 bg-primary/20 rounded-xl flex items-center justify-center flex-shrink-0">
                      <div className="w-7 h-7 border-2 border-primary rounded" />
                    </div>
                    <div>
                      <h3 className="text-2xl md:text-3xl font-bold mb-2">Autonomous Bot</h3>
                      <p className="text-sm text-primary font-mono tracking-wider">AUTOMATED EXECUTION</p>
                    </div>
                  </div>
                  
                  <p className="text-muted-foreground leading-relaxed mb-6">
                    Fully automated trading execution with multi-layered quality gates, risk controls, and real-time position management. 
                    Deploy capital with institutional discipline and precision.
                  </p>
                  
                  <div className="space-y-3 mb-8">
                    <div className="flex items-start gap-3 text-sm">
                      <div className="w-1.5 h-1.5 bg-primary rounded-full mt-2 flex-shrink-0" />
                      <span className="text-muted-foreground">Autonomous setup detection & validation</span>
                    </div>
                    <div className="flex items-start gap-3 text-sm">
                      <div className="w-1.5 h-1.5 bg-primary rounded-full mt-2 flex-shrink-0" />
                      <span className="text-muted-foreground">Portfolio-level risk & correlation controls</span>
                    </div>
                    <div className="flex items-start gap-3 text-sm">
                      <div className="w-1.5 h-1.5 bg-primary rounded-full mt-2 flex-shrink-0" />
                      <span className="text-muted-foreground">Real-time SL/TP monitoring & trailing stops</span>
                    </div>
                    <div className="flex items-start gap-3 text-sm">
                      <div className="w-1.5 h-1.5 bg-primary rounded-full mt-2 flex-shrink-0" />
                      <span className="text-muted-foreground">Complete audit trail & telemetry logging</span>
                    </div>
                  </div>
                  
                  <div className="flex gap-3 flex-wrap">
                    <Link
                      to="/bot/setup"
                      className="inline-flex items-center gap-2 px-6 py-3 bg-primary/10 hover:bg-primary/20 border border-primary/30 rounded-lg text-primary font-medium transition-all duration-200 group/btn"
                    >
                      Configure Bot
                      <span className="group-hover/btn:translate-x-1 transition-transform">→</span>
                    </Link>
                    <Link
                      to="/bot/status"
                      className="inline-flex items-center gap-2 px-6 py-3 bg-primary/5 hover:bg-primary/10 border border-primary/20 rounded-lg text-primary/80 font-medium transition-all duration-200 group/btn"
                    >
                      View Status
                      <span className="group-hover/btn:translate-x-1 transition-transform">→</span>
                    </Link>
                  </div>
                </div>
              </div>

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

export default Landing;
