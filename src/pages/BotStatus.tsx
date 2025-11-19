import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Robot, StopCircle, CheckCircle, Warning, Info } from '@phosphor-icons/react';
import { generateMockBotActivity } from '@/utils/mockData';
import { useState, useEffect } from 'react';
import type { BotActivity } from '@/utils/mockData';

export function BotStatus() {
  const navigate = useNavigate();
  const [activities, setActivities] = useState<BotActivity[]>([]);
  const [isActive, setIsActive] = useState(true);

  useEffect(() => {
    setActivities(generateMockBotActivity());

    const interval = setInterval(() => {
      if (isActive) {
        const newActivity: BotActivity = {
          id: `activity-${Date.now()}`,
          timestamp: new Date().toISOString(),
          action: [
            'Monitoring price action',
            'Confluence check passed',
            'Entry zone proximity detected',
            'Risk parameters validated',
          ][Math.floor(Math.random() * 4)],
          pair: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'][Math.floor(Math.random() * 3)],
          status: ['success', 'info'][Math.floor(Math.random() * 2)] as BotActivity['status'],
        };
        setActivities((prev) => [newActivity, ...prev].slice(0, 20));
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [isActive]);

  const handleAbortMission = () => {
    setIsActive(false);
    setTimeout(() => {
      navigate('/bot');
    }, 1000);
  };

  const getStatusIcon = (status: BotActivity['status']) => {
    if (status === 'success') return <CheckCircle size={16} weight="fill" className="text-success" />;
    if (status === 'warning') return <Warning size={16} weight="fill" className="text-warning" />;
    return <Info size={16} weight="fill" className="text-accent" />;
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
              <Robot size={32} weight="bold" className="text-warning" />
              SNIPER IN THE FIELD
            </h1>
            <p className="text-muted-foreground">Autonomous bot operational status</p>
          </div>
          <Button
            onClick={handleAbortMission}
            className="bg-destructive hover:bg-destructive/90 text-destructive-foreground"
            size="lg"
          >
            <StopCircle size={20} weight="fill" />
            ABORT MISSION
          </Button>
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          <Card className="bg-card/50 border-accent/30">
            <CardHeader>
              <CardTitle className="text-sm">MISSION STATUS</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 bg-success rounded-full scan-pulse" />
                <div>
                  <div className="text-2xl font-bold text-success">ACTIVE</div>
                  <div className="text-xs text-muted-foreground">Monitoring markets</div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card/50 border-accent/30">
            <CardHeader>
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

        <Card className="bg-card/50 border-accent/30">
          <CardHeader>
            <CardTitle>Current Targets</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="p-4 bg-background rounded border border-accent/50">
                <div className="flex items-center justify-between mb-2">
                  <div className="font-bold">BTC/USDT</div>
                  <Badge className="bg-success/20 text-success border-success/50">MONITORING</Badge>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <div className="text-muted-foreground">Entry</div>
                    <div className="font-mono">$42,150</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Stop</div>
                    <div className="font-mono text-destructive">$41,200</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Target</div>
                    <div className="font-mono text-success">$43,800</div>
                  </div>
                </div>
              </div>

              <div className="p-4 bg-background rounded border border-accent/50">
                <div className="flex items-center justify-between mb-2">
                  <div className="font-bold">ETH/USDT</div>
                  <Badge className="bg-warning/20 text-warning border-warning/50">ENTRY PENDING</Badge>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <div className="text-muted-foreground">Entry</div>
                    <div className="font-mono">$2,245</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Stop</div>
                    <div className="font-mono text-destructive">$2,190</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Target</div>
                    <div className="font-mono text-success">$2,320</div>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card/50 border-accent/30">
          <CardHeader>
            <CardTitle>Mission Feed</CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[400px] pr-4">
              <div className="space-y-2">
                {activities.map((activity) => (
                  <div key={activity.id}>
                    <div className="flex items-start gap-3 p-3 bg-background rounded">
                      <div className="mt-0.5">{getStatusIcon(activity.status)}</div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-medium">{activity.action}</span>
                          <Badge variant="outline" className="text-xs">{activity.pair}</Badge>
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {new Date(activity.timestamp).toLocaleTimeString()}
                        </div>
                      </div>
                    </div>
                    <Separator className="my-2" />
                  </div>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
