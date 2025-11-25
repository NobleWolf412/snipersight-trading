import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Robot, StopCircle, Target, CheckCircle, XCircle, TrendUp, CaretDown, CaretUp, Clock } from '@phosphor-icons/react';
import { useState, useEffect } from 'react';
import { PriceDisplay } from '@/components/PriceDisplay';
import { LiveTicker } from '@/components/LiveTicker';
import { ActivityFeed } from '@/components/telemetry/ActivityFeed';
import { telemetryService, type TelemetryAnalytics } from '@/services/telemetryService';
import { PageShell } from '@/components/layout/PageShell';
import { HomeButton } from '@/components/layout/HomeButton';

export function BotStatus() {
  const navigate = useNavigate();
  const [isActive, setIsActive] = useState(true);
  const [analytics, setAnalytics] = useState<TelemetryAnalytics | null>(null);
  const [showStatus, setShowStatus] = useState(true);
  const [showAnalytics, setShowAnalytics] = useState(true);

  useEffect(() => {
    const loadAnalytics = async () => {
      try {
        const data = await telemetryService.getAnalytics();
        setAnalytics(data);
      } catch (error) {
        console.error('Failed to load analytics:', error);
      }
    };

    loadAnalytics();
    
    const interval = setInterval(loadAnalytics, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleAbortMission = () => {
    setIsActive(false);
    setTimeout(() => {
      navigate('/bot/setup');
    }, 1000);
  };

  return (
    <PageShell>
      <div className="space-y-10 md:space-y-12">
        <div className="flex justify-start">
          <HomeButton />
        </div>
        <div className="flex items-center justify-between flex-wrap gap-6">
          <div className="space-y-3">
            <div className="flex items-center gap-4">
              <div className="relative">
                <Robot size={52} weight="bold" className="text-warning" />
                <div className="absolute inset-0 animate-ping">
                  <Robot size={52} weight="bold" className="text-warning opacity-20" />
                </div>
              </div>
              <div>
                <h1 className="text-4xl font-bold heading-hud">SNIPER IN THE FIELD</h1>
                <div className="flex items-center gap-2 mt-2">
                  <div className="w-2 h-2 bg-success rounded-full animate-pulse" />
                  <span className="text-sm text-success font-mono">AUTONOMOUS MODE</span>
                </div>
              </div>
            </div>
            <p className="text-lg text-muted-foreground">Autonomous bot operational status and metrics</p>
          </div>
          <div className="flex gap-4">
            <Button
              onClick={() => navigate('/')}
              variant="outline"
              size="lg"
              className="h-12 hover:border-accent/50 transition-all"
            >
              Home
            </Button>
            <Button
              onClick={handleAbortMission}
              className="bg-destructive hover:bg-destructive/90 text-destructive-foreground h-12 px-6 shadow-3d"
              size="lg"
            >
              <StopCircle size={22} weight="fill" />
              ABORT MISSION
            </Button>
          </div>
        </div>

        <Card className="command-panel card-3d overflow-hidden border-warning/30">
          <CardHeader 
            className="pb-5 cursor-pointer select-none hover:bg-warning/5 transition-colors"
            onClick={() => setShowStatus(!showStatus)}
          >
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm heading-hud flex items-center gap-3">
                <div className="w-2 h-2 bg-warning rounded-full scan-pulse" />
                MISSION STATUS
              </CardTitle>
              {showStatus ? 
                <CaretUp size={20} weight="bold" className="text-warning" /> : 
                <CaretDown size={20} weight="bold" className="text-muted-foreground" />
              }
            </div>
          </CardHeader>
          {showStatus && (
            <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-6 animate-in fade-in slide-in-from-top-2 duration-300">
              <div className="p-6 bg-background/40 rounded-xl border border-success/40 card-3d hud-glow-green">
                <div className="flex items-center gap-4 mb-3">
                  <div className="w-3 h-3 bg-success rounded-full scan-pulse" />
                  <div className="text-xs text-muted-foreground uppercase tracking-wider">Status</div>
                </div>
                <div className="text-3xl font-bold text-success mb-1">ACTIVE</div>
                <div className="text-sm text-muted-foreground">Monitoring markets</div>
              </div>

              <div className="p-6 bg-background/40 rounded-xl border border-accent/40 card-3d hud-glow-cyan">
                <div className="flex items-center gap-4 mb-3">
                  <Target size={16} weight="bold" className="text-accent" />
                  <div className="text-xs text-muted-foreground uppercase tracking-wider">Active Trades</div>
                </div>
                <div className="text-3xl font-bold text-accent mb-1">2/3</div>
                <div className="text-sm text-muted-foreground">Max capacity</div>
              </div>

              <div className="p-6 bg-background/40 rounded-xl border border-primary/40 card-3d hud-glow">
                <div className="flex items-center gap-4 mb-3">
                  <Clock size={16} weight="bold" className="text-primary" />
                  <div className="text-xs text-muted-foreground uppercase tracking-wider">Runtime</div>
                </div>
                <div className="text-3xl font-bold text-primary mb-1 font-mono">04:23:15</div>
                <div className="text-sm text-muted-foreground">Elapsed time</div>
              </div>
            </CardContent>
          )}
        </Card>

        <div className="space-y-4">
          <h2 className="text-2xl font-bold heading-hud flex items-center gap-3">
            <div className="w-2 h-2 bg-accent rounded-full animate-pulse" />
            LIVE PRICE TICKER
          </h2>
          <div className="card-3d rounded-xl overflow-hidden border border-accent/30">
            <LiveTicker symbols={['BTC/USDT', 'ETH/USDT', 'SOL/USDT']} />
          </div>
        </div>

        <div className="space-y-4">
          <div 
            className="flex items-center justify-between cursor-pointer select-none p-4 rounded-lg hover:bg-accent/5 transition-colors"
            onClick={() => setShowAnalytics(!showAnalytics)}
          >
            <h2 className="text-2xl font-bold heading-hud flex items-center gap-3">
              <TrendUp size={28} weight="bold" className="text-accent" />
              PERFORMANCE ANALYTICS
            </h2>
            {showAnalytics ? 
              <CaretUp size={24} weight="bold" className="text-accent" /> : 
              <CaretDown size={24} weight="bold" className="text-muted-foreground" />
            }
          </div>

          {showAnalytics && (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 animate-in fade-in slide-in-from-top-2 duration-300">
              <Card className="card-3d hud-glow hover:scale-105 transition-transform duration-300">
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2 heading-hud text-muted-foreground">
                    <Target size={20} weight="bold" />
                    TOTAL SCANS
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-foreground mb-1">
                    {analytics?.metrics.total_scans || 0}
                  </div>
                  <div className="text-xs text-muted-foreground uppercase tracking-wider">Completed</div>
                </CardContent>
              </Card>

              <Card className="card-3d hud-glow-green hover:scale-105 transition-transform duration-300">
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2 heading-hud text-muted-foreground">
                    <CheckCircle size={20} weight="bold" />
                    SIGNALS GENERATED
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-success mb-1">
                    {analytics?.metrics.total_signals_generated || 0}
                  </div>
                  <div className="text-xs text-muted-foreground uppercase tracking-wider">High conviction</div>
                </CardContent>
              </Card>

              <Card className="card-3d hud-glow-amber hover:scale-105 transition-transform duration-300">
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2 heading-hud text-muted-foreground">
                    <XCircle size={20} weight="bold" />
                    SIGNALS REJECTED
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-warning mb-1">
                    {analytics?.metrics.total_signals_rejected || 0}
                  </div>
                  <div className="text-xs text-muted-foreground uppercase tracking-wider">Failed gates</div>
                </CardContent>
              </Card>

              <Card className="card-3d hud-glow-cyan hover:scale-105 transition-transform duration-300">
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2 heading-hud text-muted-foreground">
                    <TrendUp size={20} weight="bold" />
                    SUCCESS RATE
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-accent mb-1">
                    {analytics?.metrics.signal_success_rate?.toFixed(1) || 0}%
                  </div>
                  <div className="text-xs text-muted-foreground uppercase tracking-wider">Signal quality</div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <h2 className="text-2xl font-bold heading-hud flex items-center gap-3">
            <div className="w-2 h-2 bg-accent rounded-full animate-pulse" />
            LIVE ACTIVITY FEED
          </h2>
          <ActivityFeed limit={100} autoScroll={true} showFilters={true} pollInterval={3000} />
        </div>
      </div>
    </PageShell>
  );
}
