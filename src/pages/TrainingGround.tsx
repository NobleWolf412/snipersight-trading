import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Target, PlayCircle, BookOpen } from '@phosphor-icons/react';
import { PageShell } from '@/components/layout/PageShell';
import { HomeButton } from '@/components/layout/HomeButton';

interface MockScanResult {
  pair: string;
  trendBias: string;
  classification: string;
}

function generateMockScanResults(count: number): MockScanResult[] {
  const pairs = ['BTC/USD', 'ETH/USD', 'SOL/USD', 'AVAX/USD', 'MATIC/USD'];
  const trends = ['BULLISH', 'BEARISH', 'NEUTRAL'];
  const classifications = ['STRONG', 'MODERATE', 'WEAK'];
  
  return Array.from({ length: count }, (_, i) => ({
    pair: pairs[i % pairs.length],
    trendBias: trends[Math.floor(Math.random() * trends.length)],
    classification: classifications[Math.floor(Math.random() * classifications.length)],
  }));
}

export function TrainingGround() {
  const [isTraining, setIsTraining] = useState(false);
  const [results, setResults] = useState<MockScanResult[]>([]);

  const handleStartTraining = () => {
    setIsTraining(true);
    setTimeout(() => {
      setResults(generateMockScanResults(3));
      setIsTraining(false);
    }, 2000);
  };

  return (
    <PageShell>
      <div className="space-y-10 md:space-y-12">
        <div className="flex justify-start">
          <HomeButton />
        </div>
        <div className="space-y-3">
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3 heading-hud">
            <Target size={32} weight="bold" className="text-accent" />
            TRAINING GROUND
          </h1>
          <p className="text-muted-foreground text-lg">Practice with simulated market data</p>
        </div>

        <Alert className="border-accent/50 bg-accent/10 py-4">
          <BookOpen size={20} className="text-accent" />
          <AlertTitle className="text-accent heading-hud">Safe Environment</AlertTitle>
          <AlertDescription className="mt-2">
            All operations in training mode use simulated data. Perfect for learning the system without risk.
          </AlertDescription>
        </Alert>

        <Card className="command-panel">
          <CardHeader className="pb-6">
            <CardTitle className="heading-hud">Training Simulation</CardTitle>
            <CardDescription>Run scanner with mock market data</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="p-5 bg-background rounded-lg border border-border">
                <div className="text-sm text-muted-foreground mb-2">Mode</div>
                <Badge variant="outline" className="bg-accent/20 text-accent">TRAINING</Badge>
              </div>
              <div className="p-5 bg-background rounded-lg border border-border">
                <div className="text-sm text-muted-foreground mb-2">Data Source</div>
                <Badge variant="outline">SIMULATED</Badge>
              </div>
            </div>

            <Button
              onClick={handleStartTraining}
              disabled={isTraining}
              className="w-full bg-accent hover:bg-accent/90 text-accent-foreground"
              size="lg"
            >
              <PlayCircle size={20} weight={isTraining ? 'fill' : 'regular'} />
              {isTraining ? 'RUNNING SIMULATION...' : 'START TRAINING SCAN'}
            </Button>
          </CardContent>
        </Card>

        {results.length > 0 && (
          <Card className="card-3d">
            <CardHeader className="pb-6">
              <CardTitle className="heading-hud">Training Results</CardTitle>
              <CardDescription>{results.length} simulated targets identified</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {results.map((result, i) => (
                  <div key={i} className="p-4 bg-background rounded-lg border border-border hover:border-accent/30 transition-colors">
                    <div className="flex items-center justify-between">
                      <div className="font-bold text-lg">{result.pair}</div>
                      <div className="flex items-center gap-3">
                        <Badge variant="outline">{result.trendBias}</Badge>
                        <Badge variant="secondary">{result.classification}</Badge>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        <Card className="command-panel">
          <CardHeader className="pb-6">
            <CardTitle className="heading-hud">Learning Resources</CardTitle>
            <CardDescription>Essential concepts for successful trading</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="p-5 bg-background rounded-lg border border-border hover:border-accent/30 transition-colors">
                <div className="font-bold mb-2 text-base heading-hud">Smart Money Concepts</div>
                <div className="text-muted-foreground">Learn order blocks, fair value gaps, and institutional analysis</div>
              </div>
              <div className="p-5 bg-background rounded-lg border border-border hover:border-accent/30 transition-colors">
                <div className="font-bold mb-2 text-base heading-hud">Multi-Timeframe Analysis</div>
                <div className="text-muted-foreground">Understand confluence across different timeframes</div>
              </div>
              <div className="p-5 bg-background rounded-lg border border-border hover:border-accent/30 transition-colors">
                <div className="font-bold mb-2 text-base heading-hud">Risk Management</div>
                <div className="text-muted-foreground">Position sizing, stop placement, and reward-to-risk ratios</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </PageShell>
  );
}

export default TrainingGround;
