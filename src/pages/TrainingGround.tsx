import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Target, PlayCircle, BookOpen } from '@phosphor-icons/react';
import { useState } from 'react';
import { generateMockScanResults } from '@/utils/mockData';
import { Badge } from '@/components/ui/badge';

export function TrainingGround() {
  const [isTraining, setIsTraining] = useState(false);
  const [results, setResults] = useState<any[]>([]);

  const handleStartTraining = () => {
    setIsTraining(true);
    setTimeout(() => {
      setResults(generateMockScanResults(3));
      setIsTraining(false);
    }, 2000);
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <Target size={32} weight="bold" className="text-accent" />
            TRAINING GROUND
          </h1>
          <p className="text-muted-foreground">Practice with simulated market data</p>
        </div>

        <Alert className="border-accent/50 bg-accent/10">
          <BookOpen size={20} className="text-accent" />
          <AlertTitle className="text-accent">Safe Environment</AlertTitle>
          <AlertDescription>
            All operations in training mode use simulated data. Perfect for learning the system without risk.
          </AlertDescription>
        </Alert>

        <Card className="bg-card/50 border-accent/30">
          <CardHeader>
            <CardTitle>Training Simulation</CardTitle>
            <CardDescription>Run scanner with mock market data</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-background rounded border border-border">
                <div className="text-sm text-muted-foreground mb-1">Mode</div>
                <Badge variant="outline" className="bg-accent/20 text-accent">TRAINING</Badge>
              </div>
              <div className="p-4 bg-background rounded border border-border">
                <div className="text-sm text-muted-foreground mb-1">Data Source</div>
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
          <Card className="bg-card/50 border-accent/30">
            <CardHeader>
              <CardTitle>Training Results</CardTitle>
              <CardDescription>{results.length} simulated targets identified</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {results.map((result, i) => (
                  <div key={i} className="p-3 bg-background rounded border border-border">
                    <div className="flex items-center justify-between">
                      <div className="font-bold">{result.pair}</div>
                      <div className="flex items-center gap-2">
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

        <Card className="bg-card/50 border-muted">
          <CardHeader>
            <CardTitle>Training Resources</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              <div className="p-3 bg-background rounded border border-border">
                <div className="font-bold mb-1">Smart Money Concepts</div>
                <div className="text-muted-foreground">Learn order blocks, fair value gaps, and institutional analysis</div>
              </div>
              <div className="p-3 bg-background rounded border border-border">
                <div className="font-bold mb-1">Multi-Timeframe Analysis</div>
                <div className="text-muted-foreground">Understand confluence across different timeframes</div>
              </div>
              <div className="p-3 bg-background rounded border border-border">
                <div className="font-bold mb-1">Risk Management</div>
                <div className="text-muted-foreground">Position sizing, stop placement, and reward-to-risk ratios</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
