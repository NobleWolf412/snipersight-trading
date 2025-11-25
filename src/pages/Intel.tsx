import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ChartLine, TrendUp, TrendDown, Activity } from '@phosphor-icons/react';
import { PageShell } from '@/components/layout/PageShell';
import { HomeButton } from '@/components/layout/HomeButton';
import { TacticalPanel } from '@/components/TacticalPanel';

export function Intel() {
  return (
    <PageShell>
      <div className="space-y-10 md:space-y-12">
        <div className="flex justify-start">
          <HomeButton />
        </div>
        <div className="space-y-3">
          <h1 className="text-4xl font-bold text-foreground flex items-center gap-4 heading-hud">
            <ChartLine size={40} weight="bold" className="text-accent" />
            MARKET INTEL
          </h1>
          <p className="text-lg text-muted-foreground">Real-time market insights and analysis</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <TacticalPanel>
            <div className="p-4 md:p-6">
              <div className="text-sm heading-hud mb-4 text-muted-foreground">BTC TREND</div>
              <div className="flex items-center gap-4">
                <TrendUp size={36} className="text-success" weight="bold" />
                <div>
                  <div className="text-3xl font-bold text-success">BULLISH</div>
                  <div className="text-sm text-muted-foreground mt-1">Higher timeframes aligned</div>
                </div>
              </div>
            </div>
          </TacticalPanel>

          <TacticalPanel>
            <div className="p-4 md:p-6">
              <div className="text-sm heading-hud mb-4 text-muted-foreground">MARKET VOLATILITY</div>
              <div className="flex items-center gap-4">
                <Activity size={36} className="text-warning" weight="bold" />
                <div>
                  <div className="text-3xl font-bold text-warning">MODERATE</div>
                  <div className="text-sm text-muted-foreground mt-1">Average daily range</div>
                </div>
              </div>
            </div>
          </TacticalPanel>

          <TacticalPanel>
            <div className="p-4 md:p-6">
              <div className="text-sm heading-hud mb-4 text-muted-foreground">ETH TREND</div>
              <div className="flex items-center gap-4">
                <TrendDown size={36} className="text-destructive" weight="bold" />
                <div>
                  <div className="text-3xl font-bold text-destructive">BEARISH</div>
                  <div className="text-sm text-muted-foreground mt-1">Correction phase</div>
                </div>
              </div>
            </div>
          </TacticalPanel>
        </div>

        <TacticalPanel>
          <div className="p-4 md:p-6">
            <h3 className="text-xl heading-hud text-foreground mb-6">Market Heatmap</h3>
            <div className="bg-muted/30 rounded-lg p-16 border border-border flex items-center justify-center min-h-[350px]">
              <div className="text-center space-y-3">
                <p className="text-lg text-muted-foreground">Market Heatmap Placeholder</p>
                <p className="text-sm text-muted-foreground">
                  Integrate with market data provider for live visualization
                </p>
              </div>
            </div>
          </div>
        </TacticalPanel>

        <TacticalPanel>
          <div className="p-4 md:p-6">
            <h3 className="heading-hud text-xl text-foreground mb-6">Active Alerts</h3>
            <div className="space-y-4">
              <div className="p-4 bg-success/10 border border-success/50 rounded">
                <div className="flex items-center justify-between mb-2">
                  <Badge className="bg-success/20 text-success border-success/50">OPPORTUNITY</Badge>
                  <span className="text-xs text-muted-foreground">2m ago</span>
                </div>
                <div className="text-sm">BTC approaching key support zone at $41,500</div>
              </div>

              <div className="p-4 bg-warning/10 border border-warning/50 rounded">
                <div className="flex items-center justify-between mb-2">
                  <Badge className="bg-warning/20 text-warning border-warning/50">CAUTION</Badge>
                  <span className="text-xs text-muted-foreground">15m ago</span>
                </div>
                <div className="text-sm">Increased volatility detected in altcoin sector</div>
              </div>

              <div className="p-4 bg-accent/10 border border-accent/50 rounded">
                <div className="flex items-center justify-between mb-2">
                  <Badge className="bg-accent/20 text-accent border-accent/50">INFO</Badge>
                  <span className="text-xs text-muted-foreground">1h ago</span>
                </div>
                <div className="text-sm">London session opening - increased liquidity expected</div>
              </div>
            </div>
          </div>
        </TacticalPanel>
      </div>
    </PageShell>
  );
}

export default Intel;
