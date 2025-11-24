import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ArrowUp, ArrowDown, Minus, TrendUp, Eye, FileText } from '@phosphor-icons/react';
import type { ScanResult } from '@/utils/mockData';
import { useState, useEffect } from 'react';
import { ChartModal } from '@/components/ChartModal/ChartModal';
import { DetailsModal } from '@/components/DetailsModal/DetailsModal';
import { LiveTicker } from '@/components/LiveTicker';
import { PriceDisplay } from '@/components/PriceDisplay';
import { PageLayout, PageHeader, PageSection } from '@/components/layout/PageLayout';

export function ScanResults() {
  const navigate = useNavigate();
  const [scanResults, setScanResults] = useState<ScanResult[]>([]);
  const [scanMetadata, setScanMetadata] = useState<any>(null);
  const [selectedResult, setSelectedResult] = useState<ScanResult | null>(null);
  const [isChartModalOpen, setIsChartModalOpen] = useState(false);
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);

  // Load from localStorage on mount
  useEffect(() => {
    const resultsStr = localStorage.getItem('scan-results');
    const metadataStr = localStorage.getItem('scan-metadata');
    if (resultsStr) {
      try {
        setScanResults(JSON.parse(resultsStr));
      } catch (e) {
        console.error('Failed to parse scan results:', e);
      }
    }
    if (metadataStr) {
      try {
        setScanMetadata(JSON.parse(metadataStr));
      } catch (e) {
        console.error('Failed to parse scan metadata:', e);
      }
    }
  }, []);

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
      <PageLayout maxWidth="2xl">
        <div className="text-center space-y-6 py-12">
          <TrendUp size={80} className="mx-auto text-muted-foreground" />
          <h2 className="text-3xl font-bold text-foreground">No Targets Acquired</h2>
          <p className="text-lg text-muted-foreground">Run a scan to identify trading opportunities</p>
          <Button onClick={() => navigate('/scan')} className="bg-accent hover:bg-accent/90 text-accent-foreground h-12 text-base" size="lg">
            Arm Scanner
          </Button>
        </div>
      </PageLayout>
    );
  }

  return (
    <PageLayout maxWidth="2xl">
      <div className="space-y-10">
        <PageHeader
          title="Targets Locked"
          description={`${results.length} trading setup${results.length !== 1 ? 's' : ''} identified`}
          icon={<TrendUp size={40} weight="bold" className="text-accent" />}
          actions={
            <Button onClick={() => navigate('/scan')} variant="outline" className="h-12" size="lg">
              New Scan
            </Button>
          }
        />

        <PageSection>
          <LiveTicker symbols={results.slice(0, 6).map(r => r.pair)} />
        </PageSection>

        {scanMetadata && (
          <Card className="bg-accent/5 border-accent/30">
            <CardHeader>
              <CardTitle className="text-base">Scan Configuration</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
                <div>
                  <div className="text-muted-foreground mb-1">Mode</div>
                  <Badge className="bg-accent text-accent-foreground uppercase font-mono">
                    {scanMetadata.mode}
                  </Badge>
                </div>
                <div>
                  <div className="text-muted-foreground mb-1">Timeframes</div>
                  <div className="font-mono font-semibold">
                    {scanMetadata.appliedTimeframes?.join(' · ')}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground mb-1">Min Score</div>
                  <div className="font-mono font-semibold text-accent">
                    {scanMetadata.effectiveMinScore}%
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground mb-1">Profile</div>
                  <div className="font-mono font-semibold capitalize">
                    {scanMetadata.profile?.replace(/_/g, ' ')}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground mb-1">Scanned</div>
                  <div className="font-mono font-semibold">
                    {scanMetadata.scanned} symbols
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

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
    </PageLayout>
  );
}
