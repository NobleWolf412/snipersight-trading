import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { 
  TrendUp, 
  TrendDown, 
  Target, 
  Warning,
  ChartBar,
  Crosshair
} from '@phosphor-icons/react';
import type { ScanResult } from '@/utils/mockData';

interface TradingStatsProps {
  result: ScanResult;
}

export function TradingStats({ result }: TradingStatsProps) {
  const entryPrice = result.entryZone.high;
  const tp1 = result.takeProfits[0];
  const tp2 = result.takeProfits[1];
  const tp3 = result.takeProfits[2];
  const stopLoss = result.stopLoss;

  const riskAmount = entryPrice - stopLoss;
  const reward1 = tp1 - entryPrice;
  const reward2 = tp2 - entryPrice;
  const reward3 = tp3 - entryPrice;

  const rr1 = reward1 / riskAmount;
  const rr2 = reward2 / riskAmount;
  const rr3 = reward3 / riskAmount;

  const riskPercent = (riskAmount / entryPrice) * 100;
  const reward1Percent = (reward1 / entryPrice) * 100;
  const reward2Percent = (reward2 / entryPrice) * 100;
  const reward3Percent = (reward3 / entryPrice) * 100;

  const winRate = Math.min(95, 55 + (result.confidenceScore / 100) * 30);
  const invalidationDistance = Math.abs((stopLoss - entryPrice) / entryPrice) * 100;

  return (
    <div className="grid md:grid-cols-2 gap-4">
      <Card className="bg-card/30 border-accent/20">
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <Target size={16} className="text-accent" />
            Risk/Reward Analysis
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Target 1</span>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="bg-success/20 text-success border-success/50 font-mono">
                  1:{rr1.toFixed(2)}
                </Badge>
                <span className="text-xs font-mono text-success">+{reward1Percent.toFixed(2)}%</span>
              </div>
            </div>
            <Progress value={(rr1 / 5) * 100} className="h-1.5" />
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Target 2</span>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="bg-success/20 text-success border-success/50 font-mono">
                  1:{rr2.toFixed(2)}
                </Badge>
                <span className="text-xs font-mono text-success">+{reward2Percent.toFixed(2)}%</span>
              </div>
            </div>
            <Progress value={(rr2 / 5) * 100} className="h-1.5" />
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Target 3</span>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="bg-success/20 text-success border-success/50 font-mono">
                  1:{rr3.toFixed(2)}
                </Badge>
                <span className="text-xs font-mono text-success">+{reward3Percent.toFixed(2)}%</span>
              </div>
            </div>
            <Progress value={(rr3 / 5) * 100} className="h-1.5" />
          </div>

          <div className="pt-3 border-t border-border space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">Max Risk:</span>
              <span className="font-mono text-destructive font-bold">-{riskPercent.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">Invalidation:</span>
              <span className="font-mono">${stopLoss.toFixed(2)}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card/30 border-accent/20">
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <ChartBar size={16} className="text-accent" />
            Setup Quality Metrics
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Confidence Score</span>
              <span className="text-xs font-mono font-bold text-accent">
                {result.confidenceScore.toFixed(0)}%
              </span>
            </div>
            <Progress value={result.confidenceScore} className="h-2" />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Estimated Win Rate</span>
              <span className="text-xs font-mono font-bold text-success">
                {winRate.toFixed(1)}%
              </span>
            </div>
            <Progress value={winRate} className="h-2" />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Risk Score</span>
              <span className="text-xs font-mono font-bold text-warning">
                {result.riskScore.toFixed(1)}/10
              </span>
            </div>
            <Progress value={result.riskScore * 10} className="h-2" />
          </div>

          <div className="pt-3 border-t border-border grid grid-cols-2 gap-3">
            <div className="bg-muted/30 rounded p-2">
              <div className="text-xs text-muted-foreground mb-1">Classification</div>
              <Badge variant={result.classification === 'SWING' ? 'default' : 'secondary'} className="text-xs">
                {result.classification}
              </Badge>
            </div>
            <div className="bg-muted/30 rounded p-2">
              <div className="text-xs text-muted-foreground mb-1">Trend Bias</div>
              <Badge 
                variant="outline" 
                className={
                  result.trendBias === 'BULLISH' 
                    ? 'bg-success/20 text-success border-success/50 text-xs'
                    : result.trendBias === 'BEARISH'
                    ? 'bg-destructive/20 text-destructive border-destructive/50 text-xs'
                    : 'text-xs'
                }
              >
                {result.trendBias}
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card/30 border-accent/20">
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <Crosshair size={16} className="text-accent" />
            Entry Strategy
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="bg-success/10 border border-success/50 rounded-lg p-3">
            <div className="text-xs font-bold text-success mb-2">PRIMARY ENTRY ZONE</div>
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Upper Bound:</span>
                <span className="font-mono">${result.entryZone.high.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Lower Bound:</span>
                <span className="font-mono">${result.entryZone.low.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-xs pt-2 border-t border-success/30">
                <span className="text-muted-foreground">Zone Width:</span>
                <span className="font-mono">{((result.entryZone.high - result.entryZone.low) / result.entryZone.high * 100).toFixed(2)}%</span>
              </div>
            </div>
          </div>

          <div className="bg-muted/30 rounded-lg p-3 space-y-2">
            <div className="text-xs font-bold text-foreground">RECOMMENDED APPROACH</div>
            <ul className="text-xs text-muted-foreground space-y-1 list-disc list-inside">
              <li>Split entry: 50% at upper, 50% at lower</li>
              <li>Wait for confirmation candle close</li>
              <li>Scale out at each TP level (33% each)</li>
              <li>Move SL to breakeven after TP1</li>
            </ul>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card/30 border-accent/20">
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <Warning size={16} className="text-warning" />
            Risk Considerations
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Invalidation Distance:</span>
              <span className="font-mono font-bold text-destructive">
                {invalidationDistance.toFixed(2)}%
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Order Blocks Identified:</span>
              <span className="font-mono">{result.orderBlocks.length}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Fair Value Gaps:</span>
              <span className="font-mono">{result.fairValueGaps.length}</span>
            </div>
          </div>

          <div className="bg-warning/10 border border-warning/50 rounded-lg p-3">
            <div className="text-xs font-bold text-warning mb-2">KEY RISKS</div>
            <ul className="text-xs text-muted-foreground space-y-1 list-disc list-inside">
              <li>Monitor BTC correlation during entry</li>
              <li>Beware of news events and volatility spikes</li>
              <li>Respect stop loss - no second guessing</li>
              <li>Volume confirmation required for entries</li>
            </ul>
          </div>

          <div className="bg-accent/10 border border-accent/50 rounded-lg p-2">
            <div className="text-xs text-center">
              <span className="text-muted-foreground">Suggested Position Size: </span>
              <span className="font-mono font-bold text-accent">
                {result.riskScore < 4 ? '2-3%' : result.riskScore < 7 ? '1-2%' : '0.5-1%'}
              </span>
              <span className="text-muted-foreground"> of capital</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
