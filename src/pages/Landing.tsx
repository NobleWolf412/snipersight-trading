import { LiveTicker } from '@/components/LiveTicker';
import { SystemStatus } from '@/components/landing/SystemStatus';
import { useTelemetry } from '@/hooks/useTelemetry';
import { TopBar } from '@/components/TopBar/TopBar';
import { Crosshair, Target, ChartLine, Compass } from '@phosphor-icons/react';
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
          <div className="w-full px-4 sm:px-6 md:px-8 lg:px-10">
            <div className="relative space-y-8">
              {/* Status indicator */}
              <div className="flex items-center gap-3 text-xs tracking-widest text-accent">
                <div className="w-2 h-2 bg-accent rounded-full animate-pulse" />
                <span>SYSTEM OPERATIONAL</span>
              </div>

              {/* Hero title and subtitle */}
              <div className="space-y-6 text-center">
                <div className="flex items-center justify-center gap-4">
                  <h1 className="text-5xl md:text-7xl font-bold tracking-tight heading-hud hud-glow-green scan-pulse-slow glitch-text">SNIPERSIGHT</h1>
                </div>
                <p className="text-base md:text-lg text-slate-400 max-w-3xl leading-relaxed mx-auto px-4 font-sans">Precision crypto market reconnaissance and disciplined execution. Identify high-quality targets, validate confluence, deploy with risk control.</p>
              </div>
            </div>
          </div>
        </section>

        {/* Market ticker strip */}
        <section className="relative border-y border-border/40">
          <LiveTicker />
        </section>

        {/* Main Features Grid */}
        <section className="relative py-20 md:py-32">
          <div className="w-full px-4 sm:px-6 md:px-8 lg:px-10">
            <div className="grid md:grid-cols-2 gap-12 md:gap-16">
              
              {/* Scanner Feature */}
              <div className="relative group">
                <div className="absolute inset-0 bg-gradient-to-br from-accent/10 to-transparent rounded-2xl blur-2xl group-hover:blur-3xl transition-all duration-500" />
                <div className="relative p-8 md:p-10 rounded-2xl backdrop-blur-sm card-3d">
                  <div className="flex items-start gap-4 mb-6">
                    <div className="w-14 h-14 bg-accent/20 rounded-xl flex items-center justify-center flex-shrink-0">
                      <Crosshair size={28} weight="bold" className="text-accent" />
                    </div>
                    <div>
                      <h3 className="text-xl md:text-2xl lg:text-3xl font-bold mb-2 heading-hud">RECONNAISSANCE SCANNER</h3>
                      <p className="text-xs md:text-sm text-accent font-mono tracking-wider heading-hud uppercase">Manual Operations</p>
                    </div>
                  </div>
                  
                  <p className="text-base md:text-lg text-slate-400 leading-relaxed mb-10 font-sans">Multi-timeframe Smart Money Concept detection with institutional-grade confluence scoring. Identify high-probability setups across order blocks, FVGs, liquidity sweeps, and structural breaks.</p>
                  
                  <div className="flex justify-center">
                    <Link
                      to="/scanner/setup"
                      className="inline-flex items-center justify-center gap-3 px-8 py-4 rounded-lg font-bold btn-tactical-scanner w-full md:w-auto text-base"
                    >
                      <Crosshair size={20} weight="bold" />
                      Configure Scanner
                      <span className="text-xl">→</span>
                    </Link>
                  </div>
                </div>
              </div>

              {/* Bot Feature */}
              <div className="relative group">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-transparent rounded-2xl blur-2xl group-hover:blur-3xl transition-all duration-500" />
                <div className="relative p-8 md:p-10 rounded-2xl backdrop-blur-sm card-3d">
                  <div className="flex items-start gap-4 mb-6">
                    <div className="w-14 h-14 bg-primary/20 rounded-xl flex items-center justify-center flex-shrink-0">
                      <div className="w-7 h-7 border-2 border-primary rounded" />
                    </div>
                    <div>
                      <h3 className="text-xl md:text-2xl lg:text-3xl font-bold mb-2 heading-hud">AUTONOMOUS BOT</h3>
                      <p className="text-xs md:text-sm text-primary font-mono tracking-wider heading-hud uppercase">Automated Execution</p>
                    </div>
                  </div>
                  
                  <p className="text-base md:text-lg text-slate-400 leading-relaxed mb-10 font-sans">
                    Fully automated trading execution with multi-layered quality gates, risk controls, and real-time position management. 
                    Deploy capital with institutional discipline and precision.
                  </p>
                  
                  <div className="flex justify-center">
                    <Link
                      to="/bot/setup"
                      className="inline-flex items-center justify-center gap-3 px-8 py-4 rounded-lg font-bold btn-tactical-bot w-full md:w-auto text-base"
                    >
                      <div className="w-5 h-5 border-2 border-current rounded" />
                      Configure Bot
                      <span className="text-xl">→</span>
                    </Link>
                  </div>
                </div>
              </div>

              {/* Market Intel Feature */}
              <div className="relative group">
                <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 to-transparent rounded-2xl blur-2xl group-hover:blur-3xl transition-all duration-500" />
                <div className="relative p-8 md:p-10 rounded-2xl backdrop-blur-sm card-3d">
                  <div className="flex items-start gap-4 mb-6">
                    <div className="w-14 h-14 bg-blue-500/20 rounded-xl flex items-center justify-center flex-shrink-0">
                      <Compass size={28} weight="bold" className="text-blue-500" />
                    </div>
                    <div>
                      <h3 className="text-xl md:text-2xl lg:text-3xl font-bold mb-2 heading-hud">MARKET INTEL</h3>
                      <p className="text-xs md:text-sm text-blue-500 font-mono tracking-wider heading-hud uppercase">Regime & AI Analysis</p>
                    </div>
                  </div>
                  
                  <p className="text-base md:text-lg text-slate-400 leading-relaxed mb-10 font-sans">Real-time market regime classification, dominance flows, and AI-powered symbol analysis. Understand market conditions and deploy the right sniper modes at the right time.</p>
                  
                  <div className="flex justify-center">
                    <Link
                      to="/intel"
                      className="inline-flex items-center justify-center gap-3 px-8 py-4 rounded-lg font-bold btn-tactical-intel w-full md:w-auto text-base"
                    >
                      <Compass size={20} weight="bold" />
                      View Market Intel
                      <span className="text-xl">→</span>
                    </Link>
                  </div>
                </div>
              </div>

              {/* Training Ground Feature */}
              <div className="relative group">
                <div className="absolute inset-0 bg-gradient-to-br from-warning/10 to-transparent rounded-2xl blur-2xl group-hover:blur-3xl transition-all duration-500" />
                <div className="relative p-8 md:p-10 rounded-2xl backdrop-blur-sm card-3d">
                  <div className="flex items-start gap-4 mb-6">
                    <div className="w-14 h-14 bg-warning/20 rounded-xl flex items-center justify-center flex-shrink-0">
                      <Target size={28} weight="bold" className="text-warning" />
                    </div>
                    <div>
                      <h3 className="text-xl md:text-2xl lg:text-3xl font-bold mb-2 heading-hud">TRAINING GROUND</h3>
                      <p className="text-xs md:text-sm text-warning font-mono tracking-wider heading-hud uppercase">Simulation Mode</p>
                    </div>
                  </div>
                  
                  <p className="text-base md:text-lg text-slate-400 leading-relaxed mb-10 font-sans">Practice with simulated market data in a risk-free environment. Master the system's features, test strategies, and build confidence before deploying real capital.</p>
                  
                  <div className="flex justify-center">
                    <Link
                      to="/training"
                      className="inline-flex items-center justify-center gap-3 px-8 py-4 rounded-lg font-bold btn-tactical-training w-full md:w-auto text-base"
                    >
                      <Target size={20} weight="bold" />
                      Enter Training Ground
                      <span className="text-xl">→</span>
                    </Link>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </section>

        {/* Footer with system status */}
        <footer className="relative py-12 border-t border-border/40">
          <div className="w-full px-4 sm:px-6 md:px-8 lg:px-10">
            <SystemStatus data={system} />
          </div>
        </footer>
      </main>
    </div>
  );
}
