import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Robot, StopCircle, Target, CheckCircle, XCircle, TrendUp } from '@phosphor-icons/react';
import { useState, useEffect } from 'react';
import { PriceDisplay } from '@/components/PriceDisplay';
import { LiveTicker } from '@/components/LiveTicker';
import { ActivityFeed } from '@/components/telemetry/ActivityFeed';
import { telemetryService, type TelemetryAnalytics } from '@/services/telemetryService';

export function BotStatus() {
  const navigate = useNavigate();
  const [isActive, setIsActive] = useState(true);
  const [analytics, setAnalytics] = useState<TelemetryAnalytics | null>(null);

  // Load analytics on mount
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
    
    // Refresh analytics every 30 seconds
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
    <div className="w-full px-4 sm:px-6 md:px-8 lg:px-10 py-12">
      <div className="space-y-8">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <h1 className="text-4xl font-bold text-foreground flex items-center gap-4">
              <Robot size={40} weight="bold" className="text-warning" />
              SNIPER IN THE FIELD
            </h1>
            <p className="text-lg text-muted-foreground">Autonomous bot operational status</p>
          </div>
          <div className="flex gap-3">
            <Button
              onClick={() => navigate('/')}
              variant="outline"
              className="h-12"
              size="lg"
            >
              Home
            </Button>
            <Button
              onClick={handleAbortMission}
              className="bg-destructive hover:bg-destructive/90 text-destructive-foreground h-12"
              size="lg"
            >
              <StopCircle size={22} weight="fill" />
              ABORT MISSION
            </Button>
          </div>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          <Card className="bg-card/50 border-accent/30">
            <CardHeader className="pb-5">
              <CardTitle className="text-sm">MISSION STATUS</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4">
                <div className="w-3 h-3 bg-success rounded-full scan-pulse" />
                <div>
                  <div className="text-3xl font-bold text-success">ACTIVE</div>
                  <div className="text-sm text-muted-foreground mt-1">Monitoring markets</div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card/50 border-accent/30">
            <CardHeader className="pb-5">
              <CardTitle className="text-sm">ACTIVE TRADES</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">2/3</div>
              <div className="text-xs text-muted-foreground">Max capacity</div>
            </CardContent>
          </Card>

          <Card className="bg-card/50 border-accent/30">
            <CardHeader>
              <CardTitle className="text-sm">RUNTIME</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">04:23:15</div>
              <div className="text-xs text-muted-foreground">Elapsed time</div>
            </CardContent>
          </Card>
        </div>

        <LiveTicker symbols={['BTC/USDT', 'ETH/USDT', 'SOL/USDT']} />

        {/* Analytics Dashboard */}
        <div className="grid md:grid-cols-4 gap-4">
          <Card className="bg-card/50 border-accent/30">
            <CardHeader>
              <CardTitle className="text-sm flex items-center gap-2">
                <Target size={16} />
                TOTAL SCANS
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">
                {analytics?.metrics.total_scans || 0}
              </div>
              <div className="text-xs text-muted-foreground">Completed</div>
            </CardContent>
          </Card>

          <Card className="bg-card/50 border-accent/30">
            <CardHeader>
              <CardTitle className="text-sm flex items-center gap-2">
                <CheckCircle size={16} />
                SIGNALS GENERATED
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-success">
                {analytics?.metrics.total_signals_generated || 0}
              </div>
              <div className="text-xs text-muted-foreground">High conviction</div>
            </CardContent>
          </Card>

          <Card className="bg-card/50 border-accent/30">
            <CardHeader>
              <CardTitle className="text-sm flex items-center gap-2">
                <XCircle size={16} />
                SIGNALS REJECTED
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-orange-400">
                {analytics?.metrics.total_signals_rejected || 0}
              </div>
              <div className="text-xs text-muted-foreground">Failed gates</div>
            </CardContent>
          </Card>

          <Card className="bg-card/50 border-accent/30">
            <CardHeader>
              <CardTitle className="text-sm flex items-center gap-2">
                <TrendUp size={16} />
                SUCCESS RATE
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-accent">
                {analytics?.metrics.signal_success_rate?.toFixed(1) || 0}%
              </div>
              <div className="text-xs text-muted-foreground">Signal quality</div>
            </CardContent>
          </Card>
        </div>

        {/* Real-time Activity Feed */}
        <ActivityFeed limit={100} autoScroll={true} showFilters={true} pollInterval={3000} />
      </div>
    </div>
  );
}
