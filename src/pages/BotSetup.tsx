import { TopBar } from '@/components/TopBar/TopBar';
import { Link } from 'react-router-dom';
import { PageShell } from '@/components/layout/PageShell';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Robot, Key, Shield, Activity, Gear, TrendUp } from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { HomeButton } from '@/components/layout/HomeButton';

export function BotSetup() {
  const configSections = [
    {
      icon: <Key size={24} weight="bold" className="text-accent" />,
      title: 'Exchange & Wallet Authentication',
      items: [
        'API key management & secure credential storage',
        'Exchange connection status monitoring',
        'Wallet address verification & balance tracking',
      ],
      color: 'accent',
    },
    {
      icon: <Shield size={24} weight="bold" className="text-warning" />,
      title: 'Global Risk Limits',
      items: [
        'Maximum portfolio exposure cap',
        'Per-asset position size limits',
        'Drawdown thresholds & circuit breakers',
      ],
      color: 'warning',
    },
    {
      icon: <TrendUp size={24} weight="bold" className="text-success" />,
      title: 'Position Management',
      items: [
        'Breakeven delay & trailing activation rules',
        'Stop-loss & take-profit automation',
        'Position scaling & partial exit strategies',
      ],
      color: 'success',
    },
    {
      icon: <Activity size={24} weight="bold" className="text-primary" />,
      title: 'Execution Preferences',
      items: [
        'Limit vs market order bias configuration',
        'Slippage tolerance & protection',
        'Order routing & exchange selection logic',
      ],
      color: 'primary',
    },
    {
      icon: <Gear size={24} weight="bold" className="text-accent" />,
      title: 'Correlation & Risk Controls',
      items: [
        'Correlation matrix thresholds',
        'Decay settings & temporal analysis',
        'Portfolio-level diversification rules',
      ],
      color: 'accent',
    },
    {
      icon: <Robot size={24} weight="bold" className="text-primary" />,
      title: 'Telemetry & Monitoring',
      items: [
        'Sampling rate & verbosity controls',
        'Real-time performance dashboards',
        'Alert configuration & notification settings',
      ],
      color: 'primary',
    },
  ];

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-50 border-b border-border/60 bg-background/95 backdrop-blur-sm">
        <TopBar />
      </header>
      <main>
        <PageShell>
          <div className="space-y-10 md:space-y-12">
            <div className="flex justify-start">
              <HomeButton />
            </div>
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="relative">
                  <Robot size={48} weight="bold" className="text-primary" />
                  <div className="absolute inset-0 animate-ping">
                    <Robot size={48} weight="bold" className="text-primary opacity-20" />
                  </div>
                </div>
                <div>
                  <h1 className="text-4xl font-bold tracking-tight heading-hud">AUTONOMOUS BOT CONFIGURATION</h1>
                  <div className="flex items-center gap-2 mt-2">
                    <Badge variant="outline" className="bg-warning/10 text-warning border-warning/40">DEVELOPMENT</Badge>
                    <span className="text-sm text-muted-foreground">Advanced execution framework</span>
                  </div>
                </div>
              </div>
              <p className="text-lg text-muted-foreground max-w-3xl">
                Configure execution parameters, risk constraints, position management rules, and environment credentials for autonomous trading operations.
              </p>
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              {configSections.map((section, index) => (
                <Card 
                  key={index}
                  className="card-3d hover:scale-[1.02] transition-all duration-300 border-border/40 hover:border-accent/40"
                  style={{ animationDelay: `${index * 75}ms` }}
                >
                  <CardHeader>
                    <div className="flex items-start gap-4">
                      <div className={`w-12 h-12 rounded-lg bg-${section.color}/10 flex items-center justify-center flex-shrink-0`}>
                        {section.icon}
                      </div>
                      <div className="flex-1">
                        <CardTitle className="text-lg heading-hud mb-2">{section.title}</CardTitle>
                        <Badge variant="outline" className="text-xs">COMING SOON</Badge>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2">
                      {section.items.map((item, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                          <div className="w-1.5 h-1.5 bg-accent rounded-full mt-2 flex-shrink-0" />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              ))}
            </div>

            <Card className="command-panel border-primary/30">
              <CardHeader>
                <CardTitle className="heading-hud flex items-center gap-3">
                  <div className="w-2 h-2 bg-primary rounded-full scan-pulse" />
                  DEPLOYMENT STATUS
                </CardTitle>
                <CardDescription className="text-base mt-2">
                  Bot deployment controls and activation settings
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="p-6 bg-background/40 rounded-xl border-2 border-warning/30">
                  <div className="flex items-start gap-4">
                    <Shield size={32} weight="bold" className="text-warning flex-shrink-0" />
                    <div>
                      <h3 className="text-lg font-bold text-warning mb-2">Configuration Required</h3>
                      <p className="text-sm text-muted-foreground mb-4">
                        Complete all configuration sections above before deploying the autonomous bot. 
                        This ensures proper risk management and execution parameters are in place.
                      </p>
                      <div className="flex flex-wrap gap-3">
                        <Badge variant="outline" className="bg-destructive/10 text-destructive border-destructive/40">
                          API Keys: Not Configured
                        </Badge>
                        <Badge variant="outline" className="bg-destructive/10 text-destructive border-destructive/40">
                          Risk Limits: Not Set
                        </Badge>
                        <Badge variant="outline" className="bg-destructive/10 text-destructive border-destructive/40">
                          Execution Rules: Missing
                        </Badge>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-4 pt-4">
                  <Link to="/" className="flex-1">
                    <Button 
                      variant="outline" 
                      size="lg" 
                      className="w-full h-12 hover:border-accent/50 transition-all"
                    >
                      ← Back to Landing
                    </Button>
                  </Link>
                  <Button 
                    disabled 
                    size="lg"
                    className="flex-1 h-12 cursor-not-allowed opacity-50 bg-primary/20 text-primary border border-primary/30"
                  >
                    <Robot size={20} weight="bold" />
                    Deploy Bot (Inactive)
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </PageShell>
      </main>
    </div>
  );
}
