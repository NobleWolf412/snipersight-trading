import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ActivityFeed } from '@/components/telemetry/ActivityFeed';
import { ScanHistory } from '@/components/ScanHistory';
import { useScanner } from '@/context/ScannerContext';
import { useEffect, useState } from 'react';
import { Crosshair, Target, TrendUp, XCircle, CheckCircle, CaretDown, CaretUp } from '@phosphor-icons/react';
import { telemetryService, type TelemetryAnalytics } from '@/services/telemetryService';
import { useNavigate } from 'react-router-dom';
import { PageShell } from '@/components/layout/PageShell';
import { HomeButton } from '@/components/layout/HomeButton';
import { scanHistoryService } from '@/services/scanHistoryService';
import { RiskSummary } from '@/components/risk/RiskSummary';

export function ScannerStatus() {
  const { scanConfig } = useScanner();
  const [analytics, setAnalytics] = useState<TelemetryAnalytics | null>(null);
  const [showConfig, setShowConfig] = useState(true);
  const [showAnalytics, setShowAnalytics] = useState(true);
  const [analyticsTf, setAnalyticsTf] = useState<'1h' | '24h' | '7d' | 'all'>('24h');
  const navigate = useNavigate();

  useEffect(() => {
    const load = async () => {
      try {
        const data = await telemetryService.getAnalytics();
        setAnalytics(data);
      } catch (e) {
        console.error('Failed loading telemetry analytics', e);
      }
    };
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, []);

  const handleReconfigure = () => navigate('/scanner/setup');

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
                <Crosshair size={48} weight="bold" className="text-accent" />
                <div className="absolute inset-0 animate-ping">
                  <Crosshair size={48} weight="bold" className="text-accent opacity-20" />
                </div>
              </div>
              <div>
                <h1 className="text-4xl font-bold heading-hud">SCANNER OPERATIONAL</h1>
                <div className="flex items-center gap-2 mt-2">
                  <div className="w-2 h-2 bg-success rounded-full animate-pulse" />
                  <span className="text-sm text-success font-mono">ACTIVE</span>
                </div>
              </div>
            </div>
            <p className="text-lg text-muted-foreground">Real-time reconnaissance status and analytics</p>
          </div>
          <Button 
            variant="outline" 
            onClick={handleReconfigure} 
            size="lg"
            className="h-12 hover:border-accent/50 hover:bg-accent/10 transition-all"
          >
            <Crosshair size={20} weight="bold" />
            Reconfigure
          </Button>
        </div>

        <Card className="command-panel card-3d overflow-hidden">
          <CardHeader 
            className="pb-4 cursor-pointer select-none hover:bg-primary/5 transition-colors"
            onClick={() => setShowConfig(!showConfig)}
          >
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm tracking-wider heading-hud flex items-center gap-3">
                <div className="w-2 h-2 bg-primary rounded-full scan-pulse" />
                CONFIGURATION SNAPSHOT
              </CardTitle>
              {showConfig ? 
                <CaretUp size={20} weight="bold" className="text-primary" /> : 
                <CaretDown size={20} weight="bold" className="text-muted-foreground" />
              }
            </div>
          </CardHeader>
          {showConfig && (
            <CardContent className="grid md:grid-cols-4 gap-6 text-sm animate-in fade-in slide-in-from-top-2 duration-300">
              <div className="p-4 bg-background/40 rounded-lg border border-border/40">
                <div className="text-xs text-muted-foreground mb-2 uppercase tracking-wider">Exchange</div>
                <div className="font-bold text-base text-accent">{scanConfig.exchange}</div>
              </div>
              <div className="p-4 bg-background/40 rounded-lg border border-border/40">
                <div className="text-xs text-muted-foreground mb-2 uppercase tracking-wider">Timeframes</div>
                <div className="flex flex-wrap gap-2">
                  {scanConfig.timeframes.map(tf => (
                    <Badge key={tf} variant="outline" className="text-xs bg-accent/10 text-accent border-accent/40">{tf}</Badge>
                  ))}
                </div>
              </div>
              <div className="p-4 bg-background/40 rounded-lg border border-border/40">
                <div className="text-xs text-muted-foreground mb-2 uppercase tracking-wider">Sniper Mode</div>
                <div className="font-bold text-base text-primary uppercase">{scanConfig.sniperMode}</div>
              </div>
              <div className="p-4 bg-background/40 rounded-lg border border-border/40">
                <div className="text-xs text-muted-foreground mb-2 uppercase tracking-wider">Categories</div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(scanConfig.categories).filter(([_, v]) => v).map(([k]) => (
                    <Badge key={k} variant="outline" className="text-xs bg-success/10 text-success border-success/40 capitalize">{k}</Badge>
                  ))}
                </div>
              </div>
            </CardContent>
          )}
        </Card>

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
            <div className="space-y-3">
              <div className="flex gap-2">
                {(['1h','24h','7d','all'] as const).map(tf => (
                  <Button
                    key={tf}
                    variant={analyticsTf === tf ? 'default' : 'outline'}
                    size="sm"
                    className={analyticsTf === tf ? 'bg-accent text-foreground' : ''}
                    onClick={() => setAnalyticsTf(tf)}
                  >
                    {tf.toUpperCase()}
                  </Button>
                ))}
              </div>
              <AnalyticsTiles analytics={analytics} timeframe={analyticsTf} />
            </div>
          )}
        </div>

        <ScanHistory maxEntries={10} />

        <RiskSummary />

        <div className="space-y-4">
          <h2 className="text-2xl font-bold heading-hud flex items-center gap-3">
            <div className="w-2 h-2 bg-accent rounded-full animate-pulse" />
            LIVE ACTIVITY FEED
          </h2>
          <ActivityFeed limit={75} showFilters pollInterval={4000} />
        </div>
      </div>
    </PageShell>
  );
}

function AnalyticsTiles({ analytics, timeframe }: { analytics: TelemetryAnalytics | null; timeframe: '1h' | '24h' | '7d' | 'all' }) {
  // Compute local stats fallback from scan history
  const hours = timeframe === '1h' ? 1 : timeframe === '24h' ? 24 : timeframe === '7d' ? 168 : undefined;
  const localStats = scanHistoryService.getStatistics(hours);

  const metrics = analytics?.metrics;
  const useLocal = !metrics || (
    (metrics.total_scans === 0 && metrics.total_signals_generated === 0 && metrics.total_signals_rejected === 0)
  );

  const totalScans = useLocal ? localStats.totalScans : (metrics?.total_scans || 0);
  const totalSignals = useLocal ? localStats.totalSignals : (metrics?.total_signals_generated || 0);
  const totalRejected = useLocal ? localStats.totalRejections : (metrics?.total_signals_rejected || 0);
  const successRate = useLocal ? localStats.avgSuccessRate : Number((metrics?.signal_success_rate || 0).toFixed(1));

  return (
    <div className="space-y-2">
      <div className="text-xs text-muted-foreground font-mono">Source: {useLocal ? 'Local History' : 'Backend Telemetry'}</div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 animate-in fade-in slide-in-from-top-2 duration-300">
        <StatCard 
        title="TOTAL SCANS" 
        icon={<Target size={20} weight="bold" />} 
        value={totalScans} 
        subtitle="Completed" 
        accent="text-foreground" 
        glowColor="primary"
        />
        <StatCard 
        title="SIGNALS GENERATED" 
        icon={<CheckCircle size={20} weight="bold" />} 
        value={totalSignals} 
        subtitle="High conviction" 
        accent="text-success" 
        glowColor="success"
        />
        <StatCard 
        title="SIGNALS REJECTED" 
        icon={<XCircle size={20} weight="bold" />} 
        value={totalRejected} 
        subtitle="Failed gates" 
        accent="text-warning" 
        glowColor="warning"
        />
        <StatCard 
        title="SUCCESS RATE" 
        icon={<TrendUp size={20} weight="bold" />} 
        value={`${successRate.toFixed ? successRate.toFixed(1) : Number(successRate).toFixed(1)}%`} 
        subtitle="Quality metric" 
        accent="text-accent" 
        glowColor="accent"
        />
      </div>
    </div>
  );
}

function StatCard({ title, icon, value, subtitle, accent, glowColor }: { 
  title: string; 
  icon: any; 
  value: any; 
  subtitle: string; 
  accent?: string; 
  glowColor?: string;
}) {
  const glowClass = glowColor === 'success' ? 'hud-glow-green' : 
                    glowColor === 'warning' ? 'hud-glow-amber' : 
                    glowColor === 'accent' ? 'hud-glow-cyan' : '';
  
  return (
    <Card className={`card-3d ${glowClass} hover:scale-105 transition-transform duration-300`}>
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2 heading-hud text-muted-foreground">{icon}{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className={`text-3xl font-bold mb-1 ${accent || 'text-foreground'}`}>{value}</div>
        <div className="text-xs text-muted-foreground uppercase tracking-wider">{subtitle}</div>
      </CardContent>
    </Card>
  );
}