import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  MagnifyingGlass,
  Robot,
  Target,
  ListBullets,
  Crosshair,
  Shield,
  Activity,
  ChartLine,
} from '@phosphor-icons/react';
import { LiveTicker } from '@/components/LiveTicker';

export function Landing() {
  const navigate = useNavigate();

  return (
    <div className="relative min-h-[calc(100vh-4rem)] overflow-hidden bg-gradient-to-b from-background via-background/90 to-background">
      <div className="absolute inset-0 tactical-grid opacity-30" aria-hidden />
      <div className="absolute -top-24 -right-10 w-80 h-80 hud-glow-cyan rounded-full blur-[120px] opacity-40" aria-hidden />
      <div className="absolute -bottom-16 -left-24 w-[28rem] h-[28rem] hud-glow-green rounded-full blur-[140px] opacity-30" aria-hidden />
      <div className="absolute inset-0 pointer-events-none radial-radar" aria-hidden />

      <div className="relative max-w-6xl mx-auto px-4 md:px-6 py-12 lg:py-16 space-y-10">
        <div className="grid lg:grid-cols-[1.25fr_1fr] gap-10 items-center">
          <div className="space-y-6">
            <div className="flex flex-wrap items-center gap-3 text-xs uppercase tracking-[0.2em] text-accent">
              <div className="w-2 h-2 bg-accent rounded-full scan-pulse" />
              <span>Systems Online</span>
              <span className="px-3 py-1 rounded-full border border-accent/40 bg-accent/10 text-[11px]">Night Ops Ready</span>
              <span className="px-3 py-1 rounded-full border border-success/40 bg-success/10 text-[11px] text-success">Low Latency Link</span>
            </div>

            <div className="space-y-3">
              <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight leading-tight">
                SniperSight Tactical Command
              </h1>
              <p className="text-lg text-muted-foreground max-w-2xl">
                HUD-inspired command deck with breathable spacing for analysts and operators. Precision crypto reconnaissance with
                automated execution when targets confirm.
              </p>
            </div>

            <div className="grid sm:grid-cols-3 gap-3">
              <div className="flex items-center gap-3 rounded-lg border border-accent/40 bg-card/40 p-3 backdrop-blur">
                <div className="w-9 h-9 rounded bg-accent/20 border border-accent/50 flex items-center justify-center">
                  <Shield size={18} className="text-accent" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Mission Grade</p>
                  <p className="text-sm font-semibold text-foreground">Institutional SMC</p>
                </div>
              </div>
              <div className="flex items-center gap-3 rounded-lg border border-success/40 bg-card/40 p-3 backdrop-blur">
                <div className="w-9 h-9 rounded bg-success/20 border border-success/50 flex items-center justify-center">
                  <Activity size={18} className="text-success" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Live Telemetry</p>
                  <p className="text-sm font-semibold text-foreground">Streaming Signals</p>
                </div>
              </div>
              <div className="flex items-center gap-3 rounded-lg border border-warning/40 bg-card/40 p-3 backdrop-blur">
                <div className="w-9 h-9 rounded bg-warning/20 border border-warning/50 flex items-center justify-center">
                  <ChartLine size={18} className="text-warning" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Mobile Ready</p>
                  <p className="text-sm font-semibold text-foreground">Adaptive Grid</p>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button
                size="lg"
                className="bg-accent hover:bg-accent/90 text-accent-foreground hud-glow"
                onClick={() => navigate('/scan')}
              >
                Launch Scanner
              </Button>
              <Button
                variant="outline"
                size="lg"
                className="border-border/70 bg-card/50 hover:border-accent/60 hover:text-foreground"
                onClick={() => navigate('/bot')}
              >
                Deploy Automation
              </Button>
            </div>
          </div>

          <Card className="relative p-6 bg-card/60 border border-border/70 backdrop-blur-xl hud-glow-cyan">
            <div className="absolute -top-8 -right-8 w-20 h-20 rounded-full bg-accent/10 border border-accent/40 flex items-center justify-center">
              <Crosshair size={36} weight="bold" className="text-accent" />
            </div>

            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-[0.2em]">Mission Status</p>
                  <p className="text-2xl font-semibold text-foreground">Active Recon</p>
                </div>
                <div className="flex items-center gap-2 text-xs text-accent">
                  <div className="w-2 h-2 bg-accent rounded-full scan-pulse" />
                  <span>Live Feed</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-accent/30 bg-background/60 p-3">
                  <p className="text-xs text-muted-foreground">Opportunities</p>
                  <p className="text-xl font-semibold text-accent">High Probability</p>
                  <p className="text-[11px] text-muted-foreground">SNR optimized</p>
                </div>
                <div className="rounded-lg border border-success/30 bg-background/60 p-3">
                  <p className="text-xs text-muted-foreground">Execution</p>
                  <p className="text-xl font-semibold text-success">Auto/Manual</p>
                  <p className="text-[11px] text-muted-foreground">Switchable control</p>
                </div>
                <div className="rounded-lg border border-warning/30 bg-background/60 p-3">
                  <p className="text-xs text-muted-foreground">Latency</p>
                  <p className="text-xl font-semibold text-warning">Sub-second</p>
                  <p className="text-[11px] text-muted-foreground">Web + mobile tuned</p>
                </div>
                <div className="rounded-lg border border-border/50 bg-background/60 p-3">
                  <p className="text-xs text-muted-foreground">Comms</p>
                  <p className="text-xl font-semibold text-foreground">Telegram</p>
                  <p className="text-[11px] text-muted-foreground">Actionable payloads</p>
                </div>
              </div>

              <div className="rounded-lg border border-border/60 bg-background/70 p-4 flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">Readiness</p>
                  <p className="text-lg font-semibold text-foreground">SniperSight v1.0.0</p>
                </div>
                <Button size="sm" className="bg-accent hover:bg-accent/90 text-accent-foreground" onClick={() => navigate('/market')}>
                  Market View
                </Button>
              </div>
            </div>
          </Card>
        </div>

        <LiveTicker />

        <div className="grid lg:grid-cols-3 gap-4">
          <Card
            className="p-5 bg-card/50 border-accent/30 hover:border-accent/60 transition-all cursor-pointer hud-glow group"
            onClick={() => navigate('/scan')}
          >
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 bg-accent/20 rounded-lg flex items-center justify-center border border-accent/50">
                  <MagnifyingGlass size={24} weight="bold" className="text-accent" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-foreground">Recon Scanner</h2>
                  <p className="text-xs text-muted-foreground">Manual sweep</p>
                </div>
              </div>
              <p className="text-sm text-foreground/80 leading-relaxed">
                Multi-timeframe hunts with Smart Money Concepts overlays. Built for quick reads on desktops and compact insight on
                mobile.
              </p>
              <Button variant="outline" size="sm" className="border-accent/60 text-accent hover:bg-accent/10">
                Acquire targets
              </Button>
            </div>
          </Card>

          <Card
            className="p-5 bg-card/50 border-warning/30 hover:border-warning/60 transition-all cursor-pointer group"
            onClick={() => navigate('/bot')}
          >
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 bg-warning/20 rounded-lg flex items-center justify-center border border-warning/50">
                  <Robot size={24} weight="bold" className="text-warning" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-foreground">Autonomous Bot</h2>
                  <p className="text-xs text-muted-foreground">Persistent watch</p>
                </div>
              </div>
              <p className="text-sm text-foreground/80 leading-relaxed">
                Deploy sniper logic with risk rails and time windows. Notifications carry actionable payloads—no empty fields, no
                guesswork.
              </p>
              <Button variant="outline" size="sm" className="border-warning/60 text-warning hover:bg-warning/10">
                Deploy automation
              </Button>
            </div>
          </Card>

          <Card
            className="p-5 bg-card/50 border-success/30 hover:border-success/60 transition-all cursor-pointer group"
            onClick={() => navigate('/intel')}
          >
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 bg-success/20 rounded-lg flex items-center justify-center border border-success/50">
                  <Target size={24} weight="bold" className="text-success" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-foreground">Intel Desk</h2>
                  <p className="text-xs text-muted-foreground">Signals & plans</p>
                </div>
              </div>
              <p className="text-sm text-foreground/80 leading-relaxed">
                Curated targets, playbooks, and training briefs. Designed with breathing room so teams can parse data at a glance.
              </p>
              <Button variant="outline" size="sm" className="border-success/60 text-success hover:bg-success/10">
                Review intel
              </Button>
            </div>
          </Card>
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          <Card
            className="p-4 bg-card/40 border-border/60 hover:border-accent/40 transition-all cursor-pointer backdrop-blur"
            onClick={() => navigate('/training')}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-muted/60 rounded-lg flex items-center justify-center border border-border/70">
                <Target size={20} className="text-foreground" />
              </div>
              <div>
                <h3 className="font-bold text-foreground">Training Ground</h3>
                <p className="text-xs text-muted-foreground">Simulated drills</p>
              </div>
            </div>
          </Card>

          <Card
            className="p-4 bg-card/40 border-border/60 hover:border-accent/40 transition-all cursor-pointer backdrop-blur"
            onClick={() => navigate('/profiles')}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-muted/60 rounded-lg flex items-center justify-center border border-border/70">
                <ListBullets size={20} className="text-foreground" />
              </div>
              <div>
                <h3 className="font-bold text-foreground">Sniper Profiles</h3>
                <p className="text-xs text-muted-foreground">Preset loadouts</p>
              </div>
            </div>
          </Card>

          <Card
            className="p-4 bg-card/40 border-border/60 hover:border-accent/40 transition-all cursor-pointer backdrop-blur"
            onClick={() => navigate('/market')}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-muted/60 rounded-lg flex items-center justify-center border border-border/70">
                <Crosshair size={20} className="text-foreground" />
              </div>
              <div>
                <h3 className="font-bold text-foreground">Market Overview</h3>
                <p className="text-xs text-muted-foreground">Situational awareness</p>
              </div>
            </div>
          </Card>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/70 bg-card/50 p-4 backdrop-blur">
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <div className="w-2 h-2 bg-success rounded-full scan-pulse" />
            <span>Telemetry</span>
            <span className="text-foreground font-semibold">Telegram dispatch online</span>
          </div>
          <div className="text-xs text-muted-foreground">Version 1.0.0 · Optimized for desktop & mobile HUD</div>
        </div>
      </div>
    </div>
  );
}
