import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ArrowUp, ArrowDown, Minus, TrendUp, Eye, FileText, CaretDown, CaretUp } from '@phosphor-icons/react';
import type { ScanResult } from '@/utils/mockData';

import { useState, useEffect } from 'react';
import { ChartModal } from '@/components/ChartModal/ChartModal';
import { DetailsModal } from '@/components/DetailsModal/DetailsModal';
import { LiveTicker } from '@/components/LiveTicker';
import { PriceDisplay } from '@/components/PriceDisplay';
import { PageLayout, PageHeader, PageSection } from '@/components/layout/PageLayout';
import { HomeButton } from '@/components/layout/HomeButton';
import { RejectionSummary } from '@/components/RejectionSummary';
import { RegimeIndicator } from '@/components/RegimeIndicator';
import { ConvictionBadge } from '@/components/ConvictionBadge';
import { api } from '@/utils/api';
import type { RegimeMetadata } from '@/types/regime';

export function ScanResults() {
  const navigate = useNavigate();
  const [scanResults, setScanResults] = useState<ScanResult[]>([]);
  const [scanMetadata, setScanMetadata] = useState<any>(null);
  const [rejectionStats, setRejectionStats] = useState<any>(null);
  const [selectedResult, setSelectedResult] = useState<ScanResult | null>(null);
  const [isChartModalOpen, setIsChartModalOpen] = useState(false);
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);
  const [showMetadata, setShowMetadata] = useState(true);
  const [showResults, setShowResults] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [globalRegime, setGlobalRegime] = useState<RegimeMetadata | undefined>(undefined);
  const [symbolRegimes, setSymbolRegimes] = useState<Record<string, RegimeMetadata | undefined>>({});

  useEffect(() => {
    try {
      const resultsStr = localStorage.getItem('scan-results');
      const metadataStr = localStorage.getItem('scan-metadata');
      const rejectionsStr = localStorage.getItem('scan-rejections');
      
      if (resultsStr) {
        try {
          const parsed = JSON.parse(resultsStr);
          console.log('[ScanResults] Parsed results:', Array.isArray(parsed) ? `${parsed.length} items` : 'not an array');
          setScanResults(Array.isArray(parsed) ? parsed : []);
        } catch (e) {
          console.error('Failed to parse scan results:', e);
          setScanResults([]);
        }
      } else {
        // No results in localStorage - set empty array explicitly
        console.log('[ScanResults] No results in localStorage, setting empty array');
        setScanResults([]);
      }
      
      if (metadataStr) {
        try {
          setScanMetadata(JSON.parse(metadataStr));
        } catch (e) {
          console.error('Failed to parse scan metadata:', e);
          setScanMetadata(null);
        }
      }
      
      if (rejectionsStr) {
        try {
          const parsed = JSON.parse(rejectionsStr);
          console.log('[ScanResults] Rejection stats loaded:', parsed);
          setRejectionStats(parsed);
        } catch (e) {
          console.error('Failed to parse rejection stats:', e);
          setRejectionStats(null);
        }
      }
    } catch (error) {
      console.error('[ScanResults] Error loading data from localStorage:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch global market regime as a fallback when per-result regime is missing
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const { data } = await api.getMarketRegime();
      if (cancelled || !data) return;
      const meta: RegimeMetadata = {
        global_regime: {
          composite: data.composite,
          score: data.score,
          trend: data.dimensions.trend as RegimeMetadata['global_regime']['trend'],
          volatility: data.dimensions.volatility as RegimeMetadata['global_regime']['volatility'],
          liquidity: data.dimensions.liquidity as RegimeMetadata['global_regime']['liquidity'],
        }
      };
      setGlobalRegime(meta);
    })();
    return () => { cancelled = true; };
  }, []);

  // Hydrate top N results with per-symbol regime if available
  useEffect(() => {
    const topSymbols = (scanResults || []).slice(0, 6).map(r => r.pair);
    if (!topSymbols.length) return;
    let cancelled = false;
    (async () => {
      const updates: Record<string, RegimeMetadata | undefined> = {};
      await Promise.all(topSymbols.map(async (pair) => {
        const symbol = pair; // API expects same format as getPrice (e.g., 'BTC/USDT')
        const { data } = await api.getSymbolRegime(symbol);
        if (!data) return;
        updates[pair] = {
          symbol_regime: {
            trend: data.trend as RegimeMetadata['symbol_regime']['trend'],
            volatility: data.volatility as RegimeMetadata['symbol_regime']['volatility'],
            score: data.score,
          }
        };
      }));
      if (!cancelled) setSymbolRegimes(prev => ({ ...prev, ...updates }));
    })();
    return () => { cancelled = true; };
  }, [scanResults]);

  const results = scanResults || [];
  
  // Compute EV from metadata if available, else approximate from confidence and a nominal R:R
  const getEV = (r: ScanResult) => {
    const metaEV = (r as any)?.metadata?.ev?.expected_value;
    if (typeof metaEV === 'number') return metaEV;
    const rr = (r as any)?.riskReward ?? 1.5;
    const pRaw = (r.confidenceScore ?? 50) / 100;
    const p = Math.max(0.2, Math.min(0.85, pRaw));
    return p * rr - (1 - p) * 1.0;
  };
  
  const sortedResults = [...results].sort((a, b) => getEV(b) - getEV(a));

  if (isLoading) {
    return (
      <PageLayout maxWidth="2xl">
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-center space-y-4">
            <div className="animate-pulse text-accent">
              <TrendUp size={48} weight="bold" />
            </div>
            <p className="text-muted-foreground">Loading...</p>
          </div>
        </div>
      </PageLayout>
    );
  }

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
        <div className="space-y-6">
          <div className="flex justify-start">
            <HomeButton />
          </div>
          
          {/* Header - always show */}
          <div className="text-center space-y-4 py-8">
            <div className="relative inline-block">
              <TrendUp size={80} className="mx-auto text-muted-foreground" />
              <div className="absolute inset-0 animate-ping">
                <TrendUp size={80} className={rejectionStats ? "mx-auto text-warning opacity-20" : "mx-auto text-accent opacity-20"} />
              </div>
            </div>
            <h2 className="text-3xl font-bold text-foreground heading-hud">No Targets Acquired</h2>
            <p className="text-lg text-muted-foreground">
              {rejectionStats && rejectionStats.total_rejected > 0 
                ? `All ${rejectionStats.total_rejected} symbols filtered by quality gates`
                : 'Run a scan to identify trading opportunities'
              }
            </p>
          </div>

          {/* Rejection breakdown - show if available */}
          {rejectionStats && rejectionStats.total_rejected > 0 && (
            <RejectionSummary 
              rejections={rejectionStats} 
              totalScanned={scanMetadata?.scanned || rejectionStats.total_rejected} 
            />
          )}

          {/* Action buttons - always show */}
          <div className="flex flex-col sm:flex-row gap-3 justify-center items-center pt-4">
            <Button 
              onClick={() => navigate('/scan')} 
              className="bg-accent hover:bg-accent/90 text-accent-foreground h-14 text-lg px-8 btn-tactical-scanner" 
              size="lg"
            >
              <TrendUp size={24} weight="bold" />
              {rejectionStats ? 'ADJUST & RESCAN' : 'ARM SCANNER'}
            </Button>
          </div>

          {/* Helper text */}
          <p className="text-xs text-muted-foreground text-center mt-4">
            {rejectionStats 
              ? 'Review rejection reasons above, then adjust scanner settings to capture more signals'
              : 'Preview button shows Phase 6 enhancements: Conviction badges, Regime indicators, Enhanced details'
            }
          </p>
        </div>
      </PageLayout>
    );
  }

  return (
    <PageLayout maxWidth="2xl">
      <div className="space-y-10">
        <div className="flex justify-start">
          <HomeButton />
        </div>
        <PageHeader
          title="Targets Locked"
          description={`${results.length} high-probability setup${results.length !== 1 ? 's' : ''} identified`}
          icon={<TrendUp size={40} weight="bold" className="text-accent" />}
          actions={
            <Button 
              onClick={() => navigate('/scan')} 
              variant="outline" 
              className="h-12 hover:border-accent/50 transition-all" 
              size="lg"
            >
              <TrendUp size={20} weight="bold" />
              New Scan
            </Button>
          }
        />

        <div className="card-3d rounded-xl overflow-hidden border border-accent/30">
          <LiveTicker symbols={sortedResults.slice(0, 6).map(r => r.pair)} />
        </div>

        {scanMetadata && (
          <Card className="bg-accent/5 border-accent/30 card-3d overflow-hidden">
            <CardHeader 
              className="cursor-pointer select-none hover:bg-accent/10 transition-colors"
              onClick={() => setShowMetadata(!showMetadata)}
            >
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base heading-hud flex items-center gap-3">
                    <div className="w-2 h-2 bg-accent rounded-full animate-pulse" />
                    SCAN CONFIGURATION
                  </CardTitle>
                </div>
                {showMetadata ? 
                  <CaretUp size={20} weight="bold" className="text-accent" /> : 
                  <CaretDown size={20} weight="bold" className="text-muted-foreground" />
                }
              </div>
            </CardHeader>
            {showMetadata && (
              <CardContent className="animate-in fade-in slide-in-from-top-2 duration-300">
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
                  <div className="p-4 bg-background/40 rounded-lg border border-accent/20">
                    <div className="text-xs text-muted-foreground mb-2 uppercase tracking-wider">Mode</div>
                    <Badge className="bg-accent text-accent-foreground uppercase font-mono font-bold">
                      {scanMetadata.mode}
                    </Badge>
                  </div>
                  <div className="p-4 bg-background/40 rounded-lg border border-primary/20">
                    <div className="text-xs text-muted-foreground mb-2 uppercase tracking-wider">Timeframes</div>
                    <div className="font-mono font-semibold text-primary">
                      {scanMetadata.appliedTimeframes?.join(' · ')}
                    </div>
                  </div>
                  <div className="p-4 bg-background/40 rounded-lg border border-success/20">
                    <div className="text-xs text-muted-foreground mb-2 uppercase tracking-wider">Min Score</div>
                    <div className="font-mono font-bold text-lg text-success">
                      {scanMetadata.effectiveMinScore}%
                    </div>
                  </div>
                  <div className="p-4 bg-background/40 rounded-lg border border-accent/20">
                    <div className="text-xs text-muted-foreground mb-2 uppercase tracking-wider">Profile</div>
                    <div className="font-mono font-semibold capitalize text-accent">
                      {scanMetadata.profile?.replace(/_/g, ' ')}
                    </div>
                  </div>
                  <div className="p-4 bg-background/40 rounded-lg border border-warning/20">
                    <div className="text-xs text-muted-foreground mb-2 uppercase tracking-wider">Scanned</div>
                    <div className="font-mono font-bold text-lg text-warning">
                      {scanMetadata.scanned}
                    </div>
                  </div>
                </div>
              </CardContent>
            )}
          </Card>
        )}

        {rejectionStats && rejectionStats.total_rejected > 0 && (
          <RejectionSummary 
            rejections={rejectionStats} 
            totalScanned={scanMetadata?.scanned || rejectionStats.total_rejected} 
          />
        )}

        <Card className="bg-card/50 border-accent/30 card-3d overflow-hidden">
          <CardHeader 
            className="cursor-pointer select-none hover:bg-accent/5 transition-colors"
            onClick={() => setShowResults(!showResults)}
          >
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="heading-hud flex items-center gap-3">
                  <div className="w-2 h-2 bg-primary rounded-full scan-pulse-fast" />
                  SCAN RESULTS
                </CardTitle>
              </div>
              {showResults ? 
                <CaretUp size={24} weight="bold" className="text-primary" /> : 
                <CaretDown size={24} weight="bold" className="text-muted-foreground" />
              }
            </div>
          </CardHeader>
          {showResults && (
            <CardContent className="p-0 animate-in fade-in slide-in-from-top-2 duration-300">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="border-border/40 hover:bg-accent/5">
                      <TableHead className="heading-hud text-xs">PAIR</TableHead>
                      <TableHead className="heading-hud text-xs">LIVE PRICE</TableHead>
                      <TableHead className="heading-hud text-xs">EV</TableHead>
                      <TableHead className="heading-hud text-xs">TREND</TableHead>
                      <TableHead className="heading-hud text-xs">CONVICTION</TableHead>
                      <TableHead className="heading-hud text-xs">REGIME</TableHead>
                      <TableHead className="heading-hud text-xs">CONFIDENCE</TableHead>
                      <TableHead className="heading-hud text-xs">RISK</TableHead>
                      <TableHead className="heading-hud text-xs">TYPE</TableHead>
                      <TableHead className="heading-hud text-xs">ACTIONS</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sortedResults.map((result, index) => (
                      <TableRow 
                        key={result.id} 
                        className="border-border/40 hover:bg-accent/5 transition-colors"
                        style={{ animationDelay: `${index * 50}ms` }}
                      >
                        <TableCell className="font-bold text-accent">{result.pair}</TableCell>
                        <TableCell>
                          <PriceDisplay symbol={result.pair} size="sm" />
                        </TableCell>
                                                <TableCell>
                                                  {(() => {
                                                    const ev = getEV(result);
                                                    const positive = ev >= 0;
                                                    const cls = positive ? 'bg-success/20 text-success border-success/50' : 'bg-destructive/20 text-destructive border-destructive/50';
                                                    return (
                                                      <Badge
                                                        variant="outline"
                                                        className={`font-mono font-bold ${cls}`}
                                                        title={`EV = ${ev.toFixed(2)} (p*R - (1-p)*1); p≈clamped confidence, R=first target/stop`}
                                                      >
                                                        {ev.toFixed(2)}
                                                      </Badge>
                                                    );
                                                  })()}
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
                          {result.conviction_class && result.plan_type ? (
                            <ConvictionBadge 
                              conviction={result.conviction_class} 
                              planType={result.plan_type}
                              size="sm"
                            />
                          ) : (
                            <span className="text-xs text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <RegimeIndicator regime={symbolRegimes[result.pair] || result.regime || globalRegime} size="sm" />
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div className="w-24 bg-muted rounded-full h-2.5">
                              <div
                                className="bg-accent h-2.5 rounded-full transition-all duration-500 hud-glow-cyan"
                                style={{ width: `${result.confidenceScore}%` }}
                              />
                            </div>
                            <span className="text-sm font-bold font-mono text-accent">{result.confidenceScore.toFixed(0)}%</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="font-mono font-bold">{result.riskScore.toFixed(1)}/10</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge 
                            variant={result.classification === 'SWING' ? 'default' : 'secondary'}
                            className="font-bold"
                          >
                            {result.classification}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleViewChart(result)}
                              className="hover:bg-accent/20 hover:border-accent transition-all"
                            >
                              <Eye size={16} weight="bold" />
                              CHART
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleViewDetails(result)}
                              className="hover:bg-primary/20 hover:border-primary transition-all"
                            >
                              <FileText size={16} weight="bold" />
                              DETAILS
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          )}
        </Card>

        {/* EV Legend */}
        <div className="text-xs text-muted-foreground text-center">
          <p>
            EV ≈ p(win) × R − (1 − p(win)) × 1. p(win) bounded 0.20–0.85 from confidence; R uses first target vs stop.
          </p>
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
    </PageLayout>
  );
}
