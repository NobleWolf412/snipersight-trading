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
import { PageHeader } from '@/components/layout/PageLayout';
import { PageContainer } from '@/components/layout/PageContainer';
import { HomeButton } from '@/components/layout/HomeButton';
import { RejectionSummary } from '@/components/RejectionSummary';
import { RegimeIndicator } from '@/components/RegimeIndicator';
import { ConvictionBadge } from '@/components/ConvictionBadge';
import { ReversalBadge } from '@/components/ReversalBadge';
import { ExecutiveSummary } from '@/components/ExecutiveSummary';
import { TierBadge } from '@/components/TierBadge';
import { WhySignalsPassed } from '@/components/WhySignalsPassed';
import { WarningsContext } from '@/components/WarningsContext';
import { Recommendations } from '@/components/Recommendations';
import { TableControls, RiskAlertBadge, ViewMode } from '@/components/TableControls';
import { HeatmapGrid } from '@/components/HeatmapGrid';
import { ComparisonModal } from '@/components/ComparisonModal';
import { Checkbox } from '@/components/ui/checkbox';
import { api } from '@/utils/api';
import type { RegimeMetadata, TrendRegime, VolatilityRegime, LiquidityRegime } from '@/types/regime';

export function ScanResults() {
  const navigate = useNavigate();
  const [scanResults, setScanResults] = useState<ScanResult[]>([]);
  const [scanMetadata, setScanMetadata] = useState<any>(null);
  const [rejectionStats, setRejectionStats] = useState<any>(null);
  const [selectedResult, setSelectedResult] = useState<ScanResult | null>(null);
  const [isChartModalOpen, setIsChartModalOpen] = useState(false);
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);
  const [showMetadata, setShowMetadata] = useState(false);
  const [showResults, setShowResults] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [globalRegime, setGlobalRegime] = useState<RegimeMetadata | undefined>(undefined);
  const [symbolRegimes, setSymbolRegimes] = useState<Record<string, RegimeMetadata | undefined>>({});
  const [displayedResults, setDisplayedResults] = useState<ScanResult[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [selectedForCompare, setSelectedForCompare] = useState<string[]>([]);
  const [isCompareModalOpen, setIsCompareModalOpen] = useState(false);

  const toggleSelection = (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setSelectedForCompare(prev =>
      prev.includes(id)
        ? prev.filter(item => item !== id)
        : [...prev, id].slice(0, 3) // Max 3 items
    );
  };

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
          trend: data.dimensions?.trend as TrendRegime,
          volatility: data.dimensions?.volatility as VolatilityRegime,
          liquidity: data.dimensions?.liquidity as LiquidityRegime,
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
            trend: data?.trend as TrendRegime,
            volatility: data?.volatility as VolatilityRegime,
            score: data?.score ?? 0,
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
      <PageContainer id="main-content">
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-center space-y-4">
            <div className="animate-pulse text-accent">
              <TrendUp size={48} weight="bold" />
            </div>
            <p className="text-muted-foreground">Loading...</p>
          </div>
        </div>
      </PageContainer>
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

  const handleOpenCompare = () => {
    if (selectedForCompare.length < 2) return;
    setIsCompareModalOpen(true);
  };



  if (results.length === 0) {
    return (
      <PageContainer id="main-content">
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
      </PageContainer>
    );
  }

  return (
    <PageContainer id="main-content">
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

        {/* Executive Summary - NEW */}
        <ExecutiveSummary
          results={results}
          rejections={rejectionStats}
          metadata={scanMetadata}
        />

        {/* Why These Signals Passed */}
        <WhySignalsPassed
          results={results}
          metadata={scanMetadata}
        />

        {/* Warnings & Context */}
        <WarningsContext
          results={results}
          metadata={scanMetadata}
        />

        {/* Recommendations */}
        <Recommendations
          results={results}
          rejections={rejectionStats}
          metadata={scanMetadata}
        />

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
            <CardContent className="animate-in fade-in slide-in-from-top-2 duration-300">
              {/* Table Controls */}
              <div className="px-4 pb-4">
                <TableControls
                  results={sortedResults}
                  onFilteredResults={setDisplayedResults}
                  onSortChange={() => { }}
                  viewMode={viewMode}
                  onViewModeChange={setViewMode}
                />
              </div>

              {viewMode === 'grid' ? (
                <div className="px-4 pb-4 max-h-[600px] overflow-y-auto">
                  <HeatmapGrid
                    results={displayedResults.length > 0 ? displayedResults : sortedResults}
                    onViewChart={handleViewChart}
                    regimes={symbolRegimes}
                    globalRegime={globalRegime}
                    selectedIds={selectedForCompare}
                    onToggleSelection={toggleSelection}
                  />
                </div>
              ) : (
                <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
                  <Table>
                    <TableHeader className="sticky top-0 bg-card z-10 shadow-sm">
                      <TableRow className="border-border/40 bg-card/95 backdrop-blur-sm">
                        <TableHead className="heading-hud text-xs font-semibold w-10"></TableHead>
                        <TableHead className="heading-hud text-xs font-semibold">PAIR</TableHead>
                        <TableHead className="heading-hud text-xs font-semibold">BIAS</TableHead>
                        <TableHead className="heading-hud text-xs font-semibold w-40">CONFLUENCE</TableHead>
                        <TableHead className="heading-hud text-xs font-semibold" title="Expected Value in R-multiples">EV</TableHead>
                        <TableHead className="heading-hud text-xs font-semibold">R:R</TableHead>
                        <TableHead className="heading-hud text-xs font-semibold">ENTRY</TableHead>
                        <TableHead className="heading-hud text-xs font-semibold">REGIME</TableHead>
                        <TableHead className="heading-hud text-xs font-semibold w-24">ACTIONS</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(displayedResults.length > 0 ? displayedResults : sortedResults).map((result, index) => (
                        <TableRow
                          key={result.id}
                          className={`border-border/40 hover:bg-accent/10 transition-colors cursor-pointer group ${selectedForCompare.includes(result.id) ? 'bg-accent/5' : ''}`}
                          style={{ animationDelay: `${index * 50}ms` }}
                          onClick={() => handleViewChart(result)}
                        >
                          {/* Cell for Selection */}
                          <TableCell onClick={(e) => e.stopPropagation()}>
                            <Checkbox
                              checked={selectedForCompare.includes(result.id)}
                              onCheckedChange={() => toggleSelection(result.id)}
                            />
                          </TableCell>

                          {/* PAIR - with tier indicator */}
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <TierBadge confidenceScore={result.confidenceScore} size="sm" showLabel={false} />
                              <span className="font-bold text-accent">{result.pair}</span>
                            </div>
                          </TableCell>

                          {/* BIAS */}
                          <TableCell>
                            <div className="flex flex-col gap-1">
                              <Badge variant="outline" className={getTrendColor(result.trendBias)}>
                                <span className="flex items-center gap-1">
                                  {getTrendIcon(result.trendBias)}
                                  {result.trendBias === 'BULLISH' ? 'LONG' : 'SHORT'}
                                </span>
                              </Badge>
                              <ReversalBadge reversalContext={result.reversal_context} size="sm" />
                            </div>
                          </TableCell>

                          {/* CONFLUENCE - Color gradient bar */}
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <div className="w-28 bg-muted/30 rounded-full h-3 overflow-hidden">
                                <div
                                  className={`h-full rounded-full transition-all duration-500 ${result.confidenceScore >= 80 ? 'bg-success shadow-[0_0_8px_rgba(34,197,94,0.5)]' :
                                    result.confidenceScore >= 70 ? 'bg-accent shadow-[0_0_6px_rgba(0,255,255,0.4)]' :
                                      result.confidenceScore >= 65 ? 'bg-warning' :
                                        'bg-destructive'
                                    }`}
                                  style={{ width: `${result.confidenceScore}%` }}
                                />
                              </div>
                              <span className={`text-sm font-bold font-mono ${result.confidenceScore >= 80 ? 'text-success' :
                                result.confidenceScore >= 70 ? 'text-accent' :
                                  result.confidenceScore >= 65 ? 'text-warning' :
                                    'text-destructive'
                                }`}>
                                {result.confidenceScore.toFixed(0)}%
                              </span>
                            </div>
                          </TableCell>

                          {/* EV */}
                          <TableCell>
                            {(() => {
                              const ev = getEV(result);
                              const positive = ev >= 0;
                              const cls = positive ? 'bg-success/20 text-success border-success/50' : 'bg-destructive/20 text-destructive border-destructive/50';
                              return (
                                <Badge
                                  variant="outline"
                                  className={`font-mono font-bold ${cls}`}
                                  title={`EV = ${ev.toFixed(2)}`}
                                >
                                  {ev.toFixed(2)}R
                                </Badge>
                              );
                            })()}
                          </TableCell>

                          {/* R:R */}
                          <TableCell>
                            {(() => {
                              const rr = result.riskReward;
                              if (typeof rr === 'number' && rr > 0) {
                                const color = rr >= 3 ? 'text-success' : rr >= 2 ? 'text-accent' : rr >= 1.5 ? 'text-warning' : 'text-muted-foreground';
                                return (
                                  <Badge variant="outline" className={`font-mono font-bold ${color}`}>
                                    {rr.toFixed(1)}:1
                                  </Badge>
                                );
                              }
                              return <span className="text-muted-foreground">-</span>;
                            })()}
                          </TableCell>

                          {/* ENTRY TYPE */}
                          <TableCell>
                            {(() => {
                              const planType = result.plan_type;
                              if (!planType) return <span className="text-xs text-muted-foreground">-</span>;
                              const config = {
                                'SMC': { label: 'SMC', color: 'bg-success/20 text-success border-success/50' },
                                'HYBRID': { label: 'Hybrid', color: 'bg-primary/20 text-primary border-primary/50' },
                                'ATR_FALLBACK': { label: 'ATR', color: 'bg-muted text-muted-foreground border-border' },
                              }[planType] || { label: planType, color: 'bg-muted text-muted-foreground border-border' };
                              return (
                                <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-semibold border ${config.color}`}>
                                  {config.label}
                                </span>
                              );
                            })()}
                          </TableCell>

                          {/* REGIME */}
                          <TableCell>
                            <RegimeIndicator
                              regime={symbolRegimes[result.pair] || result.regime || globalRegime}
                              size="sm"
                              compact
                              timeframe={scanMetadata?.appliedTimeframes?.[0]}
                            />
                          </TableCell>

                          {/* ACTIONS */}
                          <TableCell onClick={(e) => e.stopPropagation()}>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleViewChart(result)}
                              className="hover:bg-accent/20 hover:border-accent transition-all opacity-70 group-hover:opacity-100"
                            >
                              <Eye size={16} weight="bold" />
                              <span className="hidden sm:inline ml-1">View</span>
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          )}
        </Card>

        {/* EV Legend */}
        <div className="text-xs text-muted-foreground text-center">
          <p>
            EV ≈ p(win) × R − (1 − p(win)) × 1. p(win) bounded 0.20–0.85 from confidence; R uses first target vs stop.
          </p>
        </div>

        {/* Rejection Analysis - Moved below table for better hierarchy */}
        {rejectionStats && rejectionStats.total_rejected > 0 && (
          <RejectionSummary
            rejections={rejectionStats}
            totalScanned={scanMetadata?.scanned || rejectionStats.total_rejected}
            defaultCollapsed={true}
          />
        )}

        {/* Floating Compare Action Bar - Only show when items selected */}
        {selectedForCompare.length > 0 && (
          <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-in slide-in-from-bottom-5 fade-in duration-300">
            <div className="bg-card border border-accent/40 shadow-[0_0_20px_rgba(0,0,0,0.5)] rounded-full px-6 py-3 flex items-center gap-4">
              <span className="text-sm font-bold text-accent">
                {selectedForCompare.length} Selected
              </span>
              <div className="h-4 w-px bg-border/50" />
              <Button
                size="sm"
                onClick={handleOpenCompare}
                className="rounded-full bg-accent text-accent-foreground hover:bg-accent/90"
                disabled={selectedForCompare.length < 2}
              >
                {selectedForCompare.length < 2 ? 'Select at least 2' : 'Compare Targets'}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setSelectedForCompare([])}
                className="rounded-full h-8 w-8 p-0"
              >
                <Minus size={16} />
              </Button>
            </div>
          </div>
        )}

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

        <ComparisonModal
          isOpen={isCompareModalOpen}
          onClose={() => setIsCompareModalOpen(false)}
          results={results.filter(r => selectedForCompare.includes(r.id))}
          regimes={symbolRegimes}
        />
      </div>
    </PageContainer>
  );
}
