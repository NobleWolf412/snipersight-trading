import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendUp, ChartLine } from '@phosphor-icons/react';
import { PriceCard } from '@/components/PriceCard';
import { LiveTicker } from '@/components/LiveTicker';
import { PageHeader, PageSection } from '@/components/layout/PageLayout';
import { PageContainer } from '@/components/layout/PageContainer';
import { HomeButton } from '@/components/layout/HomeButton';
import { useBackendHealth } from '@/hooks/useBackendHealth';
import { api } from '@/utils/api';
import { cn } from '@/lib/utils';

const MAJOR_PAIRS = [
  'BTC/USDT',
  'ETH/USDT',
  'SOL/USDT',
  'AVAX/USDT',
  'BNB/USDT',
  'LINK/USDT',
];

interface RegimeSummary {
  composite: string;
  score: number;
  dominance?: { btc_d: number; alt_d: number; stable_d: number };
  dimensions?: { trend: string; volatility: string };
}

export function MarketOverview() {
  const { online, lastChecked } = useBackendHealth(10_000);
  const [regime, setRegime] = useState<RegimeSummary | null>(null);

  useEffect(() => {
    api.getMarketRegime().then((res) => {
      if (res.data) setRegime(res.data as RegimeSummary);
    });
    const id = setInterval(() => {
      api.getMarketRegime().then((res) => {
        if (res.data) setRegime(res.data as RegimeSummary);
      });
    }, 60_000);
    return () => clearInterval(id);
  }, []);

  const lastCheckedLabel = lastChecked
    ? new Date(lastChecked).toLocaleTimeString()
    : '—';

  return (
    <PageContainer id="main-content" className="space-y-10">
      <div className="flex justify-start">
        <HomeButton />
      </div>
      <PageHeader
        title="Market Overview"
        description="Real-time price monitoring across major trading pairs"
        icon={<ChartLine size={40} weight="bold" className="text-accent" />}
      />

      <PageSection>
        <LiveTicker symbols={MAJOR_PAIRS} />
      </PageSection>

      <PageSection>
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
      </PageSection>

      <PageSection>
        <div className="grid md:grid-cols-2 gap-8">
          {/* Market Insights — sourced from regime endpoint */}
          <Card className="bg-card/50 border-border/50">
            <CardHeader className="pb-6">
              <CardTitle className="text-base text-muted-foreground">Market Insights</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between p-4 bg-background rounded-lg">
                <span className="text-base">Regime</span>
                <span className={cn('font-bold text-lg uppercase tracking-wide',
                  !regime && 'text-muted-foreground animate-pulse')}>
                  {regime?.composite?.replace(/_/g, ' ') ?? '—'}
                </span>
              </div>
              <div className="flex items-center justify-between p-4 bg-background rounded-lg">
                <span className="text-base">Regime Score</span>
                <span className={cn('font-bold text-lg',
                  regime
                    ? regime.score >= 70 ? 'text-success'
                      : regime.score >= 45 ? 'text-warning'
                      : 'text-destructive'
                    : 'text-muted-foreground animate-pulse')}>
                  {regime ? `${regime.score} / 100` : '—'}
                </span>
              </div>
              <div className="flex items-center justify-between p-4 bg-background rounded-lg">
                <span className="text-base">BTC Dominance</span>
                <span className={cn('font-bold text-lg', !regime?.dominance && 'text-muted-foreground animate-pulse')}>
                  {regime?.dominance?.btc_d != null
                    ? `${regime.dominance.btc_d.toFixed(1)}%`
                    : '—'}
                </span>
              </div>
              <div className="flex items-center justify-between p-4 bg-background rounded-lg">
                <span className="text-base">Active Pairs</span>
                <span className="font-bold text-lg">{MAJOR_PAIRS.length}</span>
              </div>
            </CardContent>
          </Card>

          {/* Connection Status — live from useBackendHealth */}
          <Card className="bg-card/50 border-border/50">
            <CardHeader className="pb-6">
              <CardTitle className="text-base text-muted-foreground">Connection Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className={cn(
                'flex items-center justify-between p-4 rounded-lg border',
                online
                  ? 'bg-success/10 border-success/30'
                  : 'bg-destructive/10 border-destructive/30',
              )}>
                <span className="text-base">Backend Status</span>
                <div className="flex items-center gap-2.5">
                  <div className={cn('w-2 h-2 rounded-full',
                    online ? 'bg-success scan-pulse' : 'bg-destructive')} />
                  <span className={cn('font-bold', online ? 'text-success' : 'text-destructive')}>
                    {online ? 'ONLINE' : 'OFFLINE'}
                  </span>
                </div>
              </div>
              <div className="flex items-center justify-between p-3 bg-background rounded">
                <span className="text-sm">Exchange</span>
                <span className="font-bold">Phemex</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-background rounded">
                <span className="text-sm">Price Update Freq</span>
                <span className="font-bold">3s polling</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-background rounded">
                <span className="text-sm">Last Health Check</span>
                <span className="font-bold tabular-nums">{lastCheckedLabel}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </PageSection>
    </PageContainer>
  );
}

export default MarketOverview;
