import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendUp, ChartLine } from '@phosphor-icons/react';
import { PriceCard } from '@/components/PriceCard';
import { LiveTicker } from '@/components/LiveTicker';

const MAJOR_PAIRS = [
  'BTC/USDT',
  'ETH/USDT',
  'SOL/USDT',
  'MATIC/USDT',
  'AVAX/USDT',
  'LINK/USDT',
];

export function MarketOverview() {
  return (
    <div className="container mx-auto px-6 py-12">
      <div className="max-w-7xl mx-auto space-y-8">
        <div className="space-y-3">
          <h1 className="text-4xl font-bold text-foreground flex items-center gap-4">
            <ChartLine size={40} weight="bold" className="text-accent" />
            MARKET OVERVIEW
          </h1>
          <p className="text-lg text-muted-foreground">Real-time price monitoring and market analysis</p>
        </div>

        <LiveTicker symbols={MAJOR_PAIRS} />

        <Card className="bg-card/50 border-accent/30">
          <CardHeader className="pb-6">
            <CardTitle className="flex items-center gap-3 text-xl">
              <TrendUp size={24} className="text-accent" />
              Major Pairs
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {MAJOR_PAIRS.map((symbol) => (
                <PriceCard key={symbol} symbol={symbol} />
              ))}
            </div>
          </CardContent>
        </Card>

        <div className="grid md:grid-cols-2 gap-8">
          <Card className="bg-card/50 border-border/50">
            <CardHeader className="pb-6">
              <CardTitle className="text-base text-muted-foreground">Market Insights</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-background rounded-lg">
                <span className="text-base">Total Market Cap</span>
                <span className="font-bold text-lg">$2.1T</span>
              </div>
              <div className="flex items-center justify-between p-4 bg-background rounded-lg">
                <span className="text-base">24h Volume</span>
                <span className="font-bold text-lg">$95.3B</span>
              </div>
              <div className="flex items-center justify-between p-4 bg-background rounded-lg">
                <span className="text-base">BTC Dominance</span>
                <span className="font-bold text-lg">48.2%</span>
              </div>
              <div className="flex items-center justify-between p-4 bg-background rounded-lg">
                <span className="text-base">Active Pairs</span>
                <span className="font-bold text-lg">{MAJOR_PAIRS.length}</span>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card/50 border-border/50">
            <CardHeader className="pb-6">
              <CardTitle className="text-base text-muted-foreground">Connection Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-success/10 rounded-lg border border-success/30">
                <span className="text-base">WebSocket Status</span>
                <div className="flex items-center gap-2.5">
                  <div className="w-2 h-2 bg-success rounded-full scan-pulse" />
                  <span className="font-bold text-success">CONNECTED</span>
                </div>
              </div>
              <div className="flex items-center justify-between p-3 bg-background rounded">
                <span className="text-sm">Exchange</span>
                <span className="font-bold">Binance</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-background rounded">
                <span className="text-sm">Update Frequency</span>
                <span className="font-bold">Real-time</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-background rounded">
                <span className="text-sm">Data Source</span>
                <span className="font-bold">Live Stream</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
