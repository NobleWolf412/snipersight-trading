import { useNavigate } from 'react-router-dom';
import { useKV } from '@github/spark/hooks';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ArrowUp, ArrowDown, Minus, TrendUp, Eye, FileText } from '@phosphor-icons/react';
import type { ScanResult } from '@/utils/mockData';
import { useState } from 'react';
import { ChartModal } from '@/components/ChartModal/ChartModal';
import { DetailsModal } from '@/components/DetailsModal/DetailsModal';
import { LiveTicker } from '@/components/LiveTicker';
import { PriceDisplay } from '@/components/PriceDisplay';

export function ScanResults() {
  const navigate = useNavigate();
  const [scanResults] = useKV<ScanResult[]>('scan-results', []);
  const [selectedResult, setSelectedResult] = useState<ScanResult | null>(null);
  const [isChartModalOpen, setIsChartModalOpen] = useState(false);
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);

  const results = scanResults || [];

  const getTrendIcon = (bias: ScanResult['trendBias']) => {
    if (bias === 'BULLISH') return <ArrowUp size={16} weight="bold" className="text-success" />;
    if (bias === 'BEARISH') return <ArrowDown size={16} weight="bold" className="text-destructive" />;
    return <Minus size={16} weight="bold" className="text-muted-foreground" />;
  };

  const getTrendColor = (bias: ScanResult['trendBias']) => {
    if (bias === 'BULLISH') return 'bg-success/20 text-success border-success/50';
    if (bias === 'BEARISH') return 'bg-destructive/20 text-destructive border-destructive/50';
    return 'bg-muted text-muted-foreground border-border';
  };

  const handleViewChart = (result: ScanResult) => {
    setSelectedResult(result);
    setIsChartModalOpen(true);
  };

  const handleViewDetails = (result: ScanResult) => {
    setSelectedResult(result);
    setIsDetailsModalOpen(true);
  };

  if (results.length === 0) {
    return (
      <div className="container mx-auto px-6 py-12">
        <div className="max-w-6xl mx-auto space-y-8">
          <div className="text-center space-y-6">
            <TrendUp size={80} className="mx-auto text-muted-foreground" />
            <h2 className="text-3xl font-bold text-foreground">NO TARGETS ACQUIRED</h2>
            <p className="text-lg text-muted-foreground">Run a scan to identify trading opportunities</p>
            <Button onClick={() => navigate('/scan')} className="bg-accent hover:bg-accent/90 text-accent-foreground h-14 text-base" size="lg">
              ARM THE SCANNER
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-6 py-12">
      <div className="max-w-6xl mx-auto space-y-8">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <h1 className="text-4xl font-bold text-foreground flex items-center gap-4">
              <TrendUp size={40} weight="bold" className="text-accent" />
              TARGETS LOCKED
            </h1>
            <p className="text-lg text-muted-foreground">
              {results.length} high-conviction setup{results.length !== 1 ? 's' : ''} identified
            </p>
          </div>
          <Button onClick={() => navigate('/scan')} variant="outline" className="h-12" size="lg">
            NEW SCAN
          </Button>
        </div>

        <LiveTicker symbols={results.slice(0, 6).map(r => r.pair)} />

        <Card className="bg-card/50 border-accent/30">
          <CardHeader>
            <CardTitle>Scan Results</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>PAIR</TableHead>
                  <TableHead>LIVE PRICE</TableHead>
                  <TableHead>TREND</TableHead>
                  <TableHead>CONFIDENCE</TableHead>
                  <TableHead>RISK</TableHead>
                  <TableHead>TYPE</TableHead>
                  <TableHead>ACTIONS</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {results.map((result) => (
                  <TableRow key={result.id}>
                    <TableCell className="font-bold">{result.pair}</TableCell>
                    <TableCell>
                      <PriceDisplay symbol={result.pair} size="sm" />
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className={getTrendColor(result.trendBias)}>
                        <span className="flex items-center gap-1">
                          {getTrendIcon(result.trendBias)}
                          {result.trendBias}
                        </span>
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className="w-24 bg-muted rounded-full h-2">
                          <div
                            className="bg-accent h-2 rounded-full"
                            style={{ width: `${result.confidenceScore}%` }}
                          />
                        </div>
                        <span className="text-sm font-medium">{result.confidenceScore.toFixed(0)}%</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{result.riskScore.toFixed(1)}/10</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={result.classification === 'SWING' ? 'default' : 'secondary'}>
                        {result.classification}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleViewChart(result)}
                          className="hover:bg-accent/20 hover:border-accent"
                        >
                          <Eye size={16} />
                          CHART
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleViewDetails(result)}
                          className="hover:bg-accent/20 hover:border-accent"
                        >
                          <FileText size={16} />
                          DETAILS
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      {selectedResult && (
        <>
          <ChartModal
            isOpen={isChartModalOpen}
            onClose={() => setIsChartModalOpen(false)}
            result={selectedResult}
          />
          <DetailsModal
            isOpen={isDetailsModalOpen}
            onClose={() => setIsDetailsModalOpen(false)}
            result={selectedResult}
          />
        </>
      )}
    </div>
  );
}
