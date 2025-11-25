import { LiveTicker } from '@/components/LiveTicker';
import { SystemStatus } from '@/components/landing/SystemStatus';
import { useTelemetry } from '@/hooks/useTelemetry';
import { TopBar } from '@/components/TopBar/TopBar';
import { Crosshair, Target, ChartLine, BookOpen, TrendUp } from '@phosphor-icons/react';
import { Link } from 'react-router-dom';
import { TacticalPanel } from '@/components/TacticalPanel';

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
                      <h3 className="text-2xl md:text-3xl font-bold mb-2 heading-hud">RECONNAISSANCE SCANNER</h3>
                      <p className="text-sm text-accent font-mono tracking-wider heading-hud">MANUAL OPERATIONS</p>
                    </div>
                  </div>
                  
                  <p className="text-muted-foreground leading-relaxed mb-10">Multi-timeframe Smart Money Concept detection with institutional-grade confluence scoring. Identify high-probability setups across order blocks, FVGs, liquidity sweeps, and structural breaks.</p>
                  
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
                      <h3 className="text-2xl md:text-3xl font-bold mb-2 heading-hud">AUTONOMOUS BOT</h3>
                      <p className="text-sm text-primary font-mono tracking-wider heading-hud">AUTOMATED EXECUTION</p>
                    </div>
                  </div>
                  
                  <p className="text-muted-foreground leading-relaxed mb-10">
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

            </div>
          </div>
        </section>

        {/* Training Ground Section */}
        <section className="relative py-20 md:py-32 border-t border-border/40">
          <div className="w-full px-4 sm:px-6 md:px-8 lg:px-10">
            <div className="space-y-10">
              <div className="text-center space-y-4">
                <div className="flex items-center justify-center gap-3 text-xs tracking-widest text-warning">
                  <div className="w-2 h-2 bg-warning rounded-full animate-pulse" />
                  <span>TRAINING MODE</span>
                </div>
                <h2 className="text-4xl md:text-5xl font-bold heading-hud hud-glow-amber">TRAINING GROUND</h2>
                <p className="text-lg text-muted-foreground max-w-2xl mx-auto">Practice with simulated market data in a safe environment. Perfect for learning the system without risk.</p>
              </div>

              <div className="grid md:grid-cols-2 gap-8">
                <TacticalPanel className="group hover:shadow-[0_0_40px_oklch(0.70_0.16_75/0.2)] transition-all duration-300">
                  <div className="relative p-6 md:p-8">
                    <div className="flex items-start gap-4 mb-6">
                      <div className="w-12 h-12 bg-warning/20 rounded-xl flex items-center justify-center flex-shrink-0 scan-pulse-slow">
                        <Target size={24} weight="bold" className="text-warning" />
                      </div>
                      <div>
                        <h3 className="text-xl md:text-2xl font-bold mb-2 heading-hud text-warning">SIMULATION MODE</h3>
                        <p className="text-sm text-muted-foreground">Risk-free environment</p>
                      </div>
                    </div>
                    
                    <div className="space-y-4 mb-6">
                      <div className="p-4 bg-background/80 rounded-lg border border-warning/20">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm text-muted-foreground">Mock Data Sets</span>
                          <span className="font-mono font-bold text-warning">5+</span>
                        </div>
                      </div>
                      <div className="p-4 bg-background/80 rounded-lg border border-warning/20">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm text-muted-foreground">Training Scenarios</span>
                          <span className="font-mono font-bold text-warning">10+</span>
                        </div>
                      </div>
                    </div>

                    <Link
                      to="/training"
                      className="inline-flex items-center justify-center gap-3 px-6 py-3 rounded-lg font-bold w-full text-sm
                        bg-warning/10 border-2 border-warning/40 text-warning
                        hover:bg-warning/20 hover:border-warning/60 hover:shadow-[0_0_20px_oklch(0.70_0.16_75/0.3)]
                        transition-all duration-200 hud-glow-amber"
                    >
                      <Target size={18} weight="bold" />
                      Enter Training Ground
                      <span className="text-lg">→</span>
                    </Link>
                  </div>
                </TacticalPanel>

                <TacticalPanel className="group hover:shadow-[0_0_40px_oklch(0.70_0.16_75/0.2)] transition-all duration-300">
                  <div className="relative p-6 md:p-8">
                    <div className="flex items-start gap-4 mb-6">
                      <div className="w-12 h-12 bg-warning/20 rounded-xl flex items-center justify-center flex-shrink-0 scan-pulse-slow">
                        <BookOpen size={24} weight="bold" className="text-warning" />
                      </div>
                      <div>
                        <h3 className="text-xl md:text-2xl font-bold mb-2 heading-hud text-warning">LEARNING CENTER</h3>
                        <p className="text-sm text-muted-foreground">Essential trading concepts</p>
                      </div>
                    </div>
                    
                    <div className="space-y-3 mb-6">
                      <div className="p-4 bg-background/80 rounded-lg border border-border/40 hover:border-warning/30 transition-colors">
                        <div className="font-bold text-sm heading-hud mb-1">Smart Money Concepts</div>
                        <div className="text-xs text-muted-foreground">Order blocks, FVGs, institutional analysis</div>
                      </div>
                      <div className="p-4 bg-background/80 rounded-lg border border-border/40 hover:border-warning/30 transition-colors">
                        <div className="font-bold text-sm heading-hud mb-1">Multi-Timeframe Analysis</div>
                        <div className="text-xs text-muted-foreground">Confluence across timeframes</div>
                      </div>
                      <div className="p-4 bg-background/80 rounded-lg border border-border/40 hover:border-warning/30 transition-colors">
                        <div className="font-bold text-sm heading-hud mb-1">Risk Management</div>
                        <div className="text-xs text-muted-foreground">Position sizing and stop placement</div>
                      </div>
                    </div>
                  </div>
                </TacticalPanel>
              </div>
            </div>
          </div>
        </section>

        {/* Market Overview Section */}
        <section className="relative py-20 md:py-32 border-t border-border/40">
          <div className="w-full px-4 sm:px-6 md:px-8 lg:px-10">
            <div className="space-y-10">
              <div className="text-center space-y-4">
                <div className="flex items-center justify-center gap-3 text-xs tracking-widest text-primary">
                  <div className="w-2 h-2 bg-primary rounded-full scan-pulse" />
                  <span>LIVE MARKET DATA</span>
                </div>
                <h2 className="text-4xl md:text-5xl font-bold heading-hud hud-glow-green">MARKET OVERVIEW</h2>
                <p className="text-lg text-muted-foreground max-w-2xl mx-auto">Real-time price monitoring and market intelligence across major trading pairs.</p>
              </div>

              <div className="grid lg:grid-cols-3 gap-8">
                <TacticalPanel className="lg:col-span-2 group hover:shadow-[0_0_40px_oklch(0.60_0.18_145/0.2)] transition-all duration-300">
                  <div className="relative p-6 md:p-8">
                    <div className="flex items-start gap-4 mb-6">
                      <div className="w-12 h-12 bg-primary/20 rounded-xl flex items-center justify-center flex-shrink-0 scan-pulse">
                        <ChartLine size={24} weight="bold" className="text-primary" />
                      </div>
                      <div>
                        <h3 className="text-xl md:text-2xl font-bold mb-2 heading-hud text-primary">LIVE MONITORING</h3>
                        <p className="text-sm text-muted-foreground">Real-time price feeds</p>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
                      {['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'AVAX/USDT', 'MATIC/USDT', 'LINK/USDT'].map((pair) => (
                        <div key={pair} className="p-4 bg-background/80 rounded-lg border border-border/40 hover:border-primary/30 transition-colors">
                          <div className="font-mono font-bold text-sm mb-1">{pair}</div>
                          <div className="flex items-center gap-2">
                            <TrendUp size={14} className="text-success" weight="bold" />
                            <span className="text-xs text-success">+2.4%</span>
                          </div>
                        </div>
                      ))}
                    </div>

                    <Link
                      to="/market"
                      className="inline-flex items-center justify-center gap-3 px-6 py-3 rounded-lg font-bold w-full text-sm
                        bg-primary/10 border-2 border-primary/40 text-primary
                        hover:bg-primary/20 hover:border-primary/60 hover:shadow-[0_0_20px_oklch(0.60_0.18_145/0.3)]
                        transition-all duration-200 hud-glow-green"
                    >
                      <ChartLine size={18} weight="bold" />
                      View Full Market Overview
                      <span className="text-lg">→</span>
                    </Link>
                  </div>
                </TacticalPanel>

                <TacticalPanel className="group hover:shadow-[0_0_40px_oklch(0.60_0.18_145/0.2)] transition-all duration-300">
                  <div className="relative p-6 md:p-8">
                    <div className="mb-6">
                      <h3 className="text-lg font-bold mb-4 heading-hud text-primary">MARKET INTEL</h3>
                    </div>
                    
                    <div className="space-y-4">
                      <div className="p-4 bg-background/80 rounded-lg border border-border/40">
                        <div className="text-xs text-muted-foreground mb-1">Total Market Cap</div>
                        <div className="font-mono font-bold text-lg">$2.1T</div>
                      </div>
                      <div className="p-4 bg-background/80 rounded-lg border border-border/40">
                        <div className="text-xs text-muted-foreground mb-1">24h Volume</div>
                        <div className="font-mono font-bold text-lg">$95.3B</div>
                      </div>
                      <div className="p-4 bg-background/80 rounded-lg border border-border/40">
                        <div className="text-xs text-muted-foreground mb-1">BTC Dominance</div>
                        <div className="font-mono font-bold text-lg">48.2%</div>
                      </div>
                      <div className="p-4 bg-success/10 rounded-lg border border-success/30">
                        <div className="text-xs text-muted-foreground mb-1">Feed Status</div>
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 bg-success rounded-full scan-pulse" />
                          <div className="font-bold text-sm text-success">LIVE</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </TacticalPanel>
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
