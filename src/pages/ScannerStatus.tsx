import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ActivityFeed } from '@/components/telemetry/ActivityFeed';
import { useScanner } from '@/context/ScannerContext';
import { useEffect, useState } from 'react';
import { Crosshair, Target, TrendUp, XCircle, CheckCircle } from '@phosphor-icons/react';
import { telemetryService, type TelemetryAnalytics } from '@/services/telemetryService';
import { useNavigate } from 'react-router-dom';
import { PageShell } from '@/components/layout/PageShell';

export function ScannerStatus() {
  const { scanConfig } = useScanner();
  const [analytics, setAnalytics] = useState<TelemetryAnalytics | null>(null);
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
        <div className="flex items-center justify-between flex-wrap gap-6">
          <div className="space-y-3">
            <h1 className="text-4xl font-bold flex items-center gap-4 heading-hud">
              <Crosshair size={44} weight="bold" className="text-accent" />
              SCANNER OPERATIONAL
            </h1>
            <p className="text-lg text-muted-foreground">Reconnaissance scanner real-time status</p>
          </div>
          <Button variant="outline" onClick={handleReconfigure} size="lg">Configure</Button>
        </div>

        {/* Configuration Summary */}
        <Card className="command-panel">
          <CardHeader className="pb-4">
            <CardTitle className="text-sm tracking-wider heading-hud">CONFIGURATION SNAPSHOT</CardTitle>
          </CardHeader>
          <CardContent className="grid md:grid-cols-4 gap-6 text-sm">
            <div>
              <div className="text-xs text-muted-foreground mb-1">Exchange</div>
              <div className="font-medium">{scanConfig.exchange}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">Timeframes</div>
              <div className="flex flex-wrap gap-2">
                {scanConfig.timeframes.map(tf => (
                  <Badge key={tf} variant="outline" className="text-xs">{tf}</Badge>
                ))}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">Sniper Mode</div>
              <div className="font-medium uppercase">{scanConfig.sniperMode}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">Categories</div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(scanConfig.categories).filter(([_, v]) => v).map(([k]) => (
                  <Badge key={k} variant="outline" className="text-xs">{k}</Badge>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Analytics */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          <StatCard title="TOTAL SCANS" icon={<Target size={16} />} value={analytics?.metrics.total_scans || 0} subtitle="Completed" />
          <StatCard title="SIGNALS GENERATED" icon={<CheckCircle size={16} />} value={analytics?.metrics.total_signals_generated || 0} subtitle="High conviction" accent="text-success" />
          <StatCard title="SIGNALS REJECTED" icon={<XCircle size={16} />} value={analytics?.metrics.total_signals_rejected || 0} subtitle="Failed gates" accent="text-orange-400" />
          <StatCard title="SUCCESS RATE" icon={<TrendUp size={16} />} value={((analytics?.metrics.signal_success_rate || 0).toFixed(1) + '%')} subtitle="Quality" accent="text-accent" />
        </div>

        {/* Activity Feed */}
        <ActivityFeed limit={75} showFilters pollInterval={4000} />
      </div>
    </PageShell>
  );
}

function StatCard({ title, icon, value, subtitle, accent }: { title: string; icon: any; value: any; subtitle: string; accent?: string }) {
  return (
    <Card className="card-3d">
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2 heading-hud">{icon}{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className={`text-2xl font-bold ${accent || 'text-foreground'}`}>{value}</div>
        <div className="text-xs text-muted-foreground">{subtitle}</div>
      </CardContent>
    </Card>
  );
}