import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ChartLine, TrendUp, TrendDown, Activity } from '@phosphor-icons/react';

export function Intel() {
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <ChartLine size={32} weight="bold" className="text-accent" />
            MARKET INTEL
          </h1>
          <p className="text-muted-foreground">Real-time market insights and analysis</p>
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          <Card className="bg-card/50 border-accent/30">
            <CardHeader>
              <CardTitle className="text-sm">BTC TREND</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-3">
                <TrendUp size={32} className="text-success" weight="bold" />
                <div>
                  <div className="text-2xl font-bold text-success">BULLISH</div>
                  <div className="text-xs text-muted-foreground">Higher timeframes aligned</div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card/50 border-accent/30">
            <CardHeader>
              <CardTitle className="text-sm">MARKET VOLATILITY</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-3">
                <Activity size={32} className="text-warning" weight="bold" />
                <div>
                  <div className="text-2xl font-bold text-warning">MODERATE</div>
                  <div className="text-xs text-muted-foreground">Average daily range</div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card/50 border-accent/30">
            <CardHeader>
              <CardTitle className="text-sm">ETH TREND</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-3">
                <TrendDown size={32} className="text-destructive" weight="bold" />
                <div>
                  <div className="text-2xl font-bold text-destructive">BEARISH</div>
                  <div className="text-xs text-muted-foreground">Correction phase</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="bg-card/50 border-accent/30">
          <CardHeader>
            <CardTitle>Market Heatmap</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="bg-muted/30 rounded-lg p-12 border border-border flex items-center justify-center min-h-[300px]">
              <div className="text-center space-y-2">
                <p className="text-muted-foreground">Market Heatmap Placeholder</p>
                <p className="text-xs text-muted-foreground">
                  Integrate with market data provider for live visualization
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card/50 border-accent/30">
          <CardHeader>
            <CardTitle>Active Alerts</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
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
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
