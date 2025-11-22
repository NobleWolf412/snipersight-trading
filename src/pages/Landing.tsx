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
import { SessionIndicator } from '@/components/SessionIndicator/SessionIndicator';

export function Landing() {
  const navigate = useNavigate();

  const readinessBadges = [
    {
      title: 'Mission Grade',
      value: 'Institutional SMC',
      icon: Shield,
      colorClass: 'border-accent/40 bg-card/40',
      iconClass: 'bg-accent/20 border-accent/50 text-accent',
    },
    {
      title: 'Live Telemetry',
      value: 'Streaming Signals',
      icon: Activity,
      colorClass: 'border-success/40 bg-card/40',
      iconClass: 'bg-success/20 border-success/50 text-success',
    },
    {
      title: 'Mobile Ready',
      value: 'Adaptive Grid',
      icon: ChartLine,
      colorClass: 'border-warning/40 bg-card/40',
      iconClass: 'bg-warning/20 border-warning/50 text-warning',
    },
  ];

  const missionStats = [
    {
      title: 'Opportunities',
      value: 'High Probability',
      hint: 'SNR optimized',
      border: 'border-accent/30',
      accent: 'text-accent',
    },
    {
      title: 'Execution',
      value: 'Auto/Manual',
      hint: 'Switchable control',
      border: 'border-success/30',
      accent: 'text-success',
    },
    {
      title: 'Latency',
      value: 'Sub-second',
      hint: 'Web + mobile tuned',
      border: 'border-warning/30',
      accent: 'text-warning',
    },
    {
      title: 'Comms',
      value: 'Telegram',
      hint: 'Actionable payloads',
      border: 'border-border/50',
      accent: 'text-foreground',
    },
  ];

  const primaryModules = [
    {
      title: 'Recon Scanner',
      subtitle: 'Manual sweep',
      body:
        'Multi-timeframe hunts with Smart Money Concepts overlays. Built for quick reads on desktops and compact insight on mobile.',
      icon: MagnifyingGlass,
      borderClass: 'border-accent/30 hover:border-accent/60',
      iconClass: 'bg-accent/20 border-accent/50 text-accent',
      buttonClass: 'border-accent/60 text-accent hover:bg-accent/10',
      buttonLabel: 'Acquire targets',
      destination: '/scan',
    },
    {
      title: 'Autonomous Bot',
      subtitle: 'Persistent watch',
      body:
        'Deploy sniper logic with risk rails and time windows. Notifications carry actionable payloads—no empty fields, no guesswork.',
      icon: Robot,
      borderClass: 'border-warning/30 hover:border-warning/60',
      iconClass: 'bg-warning/20 border-warning/50 text-warning',
      buttonClass: 'border-warning/60 text-warning hover:bg-warning/10',
      buttonLabel: 'Deploy automation',
      destination: '/bot',
    },
    {
      title: 'Intel Desk',
      subtitle: 'Signals & plans',
      body:
        'Curated targets, playbooks, and training briefs. Designed with breathing room so teams can parse data at a glance.',
      icon: Target,
      borderClass: 'border-success/30 hover:border-success/60',
      iconClass: 'bg-success/20 border-success/50 text-success',
      buttonClass: 'border-success/60 text-success hover:bg-success/10',
      buttonLabel: 'Review intel',
      destination: '/intel',
    },
  ];

  const secondaryModules = [
    {
      title: 'Training Ground',
      subtitle: 'Simulated drills',
      icon: Target,
      destination: '/training',
    },
    {
      title: 'Sniper Profiles',
      subtitle: 'Preset loadouts',
      icon: ListBullets,
      destination: '/profiles',
    },
    {
      title: 'Market Overview',
      subtitle: 'Situational awareness',
      icon: Crosshair,
      destination: '/market',
    },
  ];

  return (
    <div className="relative min-h-[calc(100vh-4rem)] overflow-hidden bg-gradient-to-b from-background via-background/90 to-background">
      <div className="absolute inset-0 tactical-grid opacity-30" aria-hidden />
      <div className="absolute -top-24 -right-10 w-80 h-80 hud-glow-cyan rounded-full blur-[120px] opacity-40" aria-hidden />
      <div className="absolute -bottom-16 -left-24 w-[28rem] h-[28rem] hud-glow-green rounded-full blur-[140px] opacity-30" aria-hidden />
      <div className="absolute inset-0 pointer-events-none radial-radar" aria-hidden="true" />
      <div className="relative max-w-6xl mx-auto px-6 md:px-8 py-16 lg:py-20 space-y-14">
        <div className="grid lg:grid-cols-[1.25fr_1fr] gap-12 items-center">
          <div className="space-y-8">
            <div className="flex flex-wrap items-center gap-4 text-xs uppercase tracking-[0.2em] text-accent">
              <div className="w-2 h-2 bg-accent rounded-full scan-pulse" />
              <span>Systems Online</span>
              <span className="px-4 py-1.5 rounded-full border border-accent/40 bg-accent/10 text-[11px]">Night Ops Ready</span>
              <span className="px-4 py-1.5 rounded-full border border-success/40 bg-success/10 text-[11px] text-success">Low Latency Link</span>
            </div>

            <div className="space-y-4">
              <h1 className="text-5xl md:text-6xl font-bold text-foreground tracking-tight leading-tight">
                SniperSight Tactical Command
              </h1>
              <p className="text-xl text-muted-foreground max-w-2xl">HUD-inspired command deck with breathable spacing for analysts and operators. Precision crypto reconnaissance with automated execution when targets confirm.</p>
            </div>

            <div className="grid sm:grid-cols-3 gap-4">
              {readinessBadges.map(({ title, value, icon: Icon, colorClass, iconClass }) => (
                <div
                  key={title}
                  className={`flex items-center gap-4 rounded-lg border ${colorClass} p-4 backdrop-blur`}
                >
                  <div className={`w-11 h-11 rounded border flex items-center justify-center ${iconClass}`}>
                    <Icon size={20} />
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">{title}</p>
                    <p className="text-base font-semibold text-foreground">{value}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex flex-wrap gap-4">
              <Button
                size="lg"
                className="bg-accent hover:bg-accent/90 text-accent-foreground hud-glow h-12 text-base"
                onClick={() => navigate('/scan')}
              >Launch Scanner</Button>
              <Button
                variant="outline"
                size="lg"
                className="border-border/70 bg-card/50 hover:border-accent/60 hover:text-foreground h-12 text-base"
                onClick={() => navigate('/bot')}
              >
                Deploy Automation
              </Button>
            </div>
          </div>

          <Card className="relative p-8 bg-card/60 border border-border/70 backdrop-blur-xl hud-glow-cyan">
            <div className="absolute -top-10 -right-10 w-24 h-24 rounded-full bg-accent/10 border border-accent/40 flex items-center justify-center">
              <Crosshair size={40} weight="bold" className="text-accent" />
            </div>

            <div className="space-y-8">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-[0.2em]">Mission Status</p>
                  <p className="text-3xl font-semibold text-foreground">Active Recon</p>
                </div>
                <div className="flex items-center gap-2.5 text-xs text-accent">
                  <div className="w-2 h-2 bg-accent rounded-full scan-pulse" />
                  <span>Live Feed</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                {missionStats.map(({ title, value, hint, border, accent }) => (
                  <div key={title} className={`rounded-lg border ${border} bg-background/60 p-4`}>
                    <p className="text-xs text-muted-foreground">{title}</p>
                    <p className={`text-2xl font-semibold ${accent} mt-1`}>{value}</p>
                    <p className="text-xs text-muted-foreground mt-1">{hint}</p>
                  </div>
                ))}
              </div>

              <div className="rounded-lg border border-border/60 bg-background/70 p-5 flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">Readiness</p>
                  <p className="text-xl font-semibold text-foreground mt-1">SniperSight v1.0.0</p>
                </div>
                <Button size="sm" className="bg-accent hover:bg-accent/90 text-accent-foreground h-10" onClick={() => navigate('/market')}>
                  Market View
                </Button>
              </div>
            </div>
          </Card>
        </div>

        <section className="space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-6">
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">LIVE MARKET FEED</p>
              <h2 className="text-2xl font-semibold text-foreground">Persistent ticker stream · fully compatible with sessions</h2>
              <p className="text-base text-muted-foreground max-w-2xl">The scrolling tape remains online with dual-pass rendering for continuous motion. Session telemetry stays syn</p>
            </div>
            <div className="flex items-center gap-4 rounded-lg border border-border/60 bg-card/60 px-4 py-3 backdrop-blur">
              <SessionIndicator />
              <div className="text-sm text-muted-foreground leading-tight">
                <div className="text-foreground font-semibold">Session link stable</div>
                <div className="mt-0.5">Aligned with HUD status and notifications</div>
              </div>
            </div>
          </div>
          <LiveTicker className="rounded-xl border border-border/60" />
        </section>

        <div className="grid lg:grid-cols-3 gap-6">
          {primaryModules.map(
            ({
              title,
              subtitle,
              body,
              icon: Icon,
              borderClass,
              iconClass,
              buttonClass,
              buttonLabel,
              destination,
            }) => (
              <Card
                key={title}
                className={`p-6 bg-card/50 ${borderClass} transition-all cursor-pointer hud-glow group`}
                onClick={() => navigate(destination)}
              >
                <div className="space-y-4">
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-lg flex items-center justify-center border ${iconClass}`}>
                      <Icon size={26} weight="bold" />
                    </div>
                    <div>
                      <h2 className="text-xl font-bold text-foreground">{title}</h2>
                      <p className="text-sm text-muted-foreground mt-0.5">{subtitle}</p>
                    </div>
                  </div>
                  <p className="text-base text-foreground/80 leading-relaxed">{body}</p>
                  <Button variant="outline" size="sm" className={`${buttonClass} h-10`}>
                    {buttonLabel}
                  </Button>
                </div>
              </Card>
            ),
          )}
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          {secondaryModules.map(({ title, subtitle, icon: Icon, destination }) => (
            <Card
              key={title}
              className="p-4 bg-card/40 border-border/60 hover:border-accent/40 transition-all cursor-pointer backdrop-blur"
              onClick={() => navigate(destination)}
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-muted/60 rounded-lg flex items-center justify-center border border-border/70">
                  <Icon size={20} className="text-foreground" />
                </div>
                <div>
                  <h3 className="font-bold text-foreground">{title}</h3>
                  <p className="text-xs text-muted-foreground">{subtitle}</p>
                </div>
              </div>
            </Card>
          ))}
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
