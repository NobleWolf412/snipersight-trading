import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ArrowUp, ArrowDown, Minus, TrendUp, Eye, FileText, CaretDown, CaretUp } from '@phosphor-icons/react';
import type { ScanResult } from '@/utils/mockData';

import { useState, useEffect } from 'react';
import { ChartModal } from '@/components/ChartModal/ChartModal';
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
import { TacticalBackground } from '@/components/ui/TacticalBackground';
import { MissionStats } from '@/components/MissionStats';

export function ScanResults() {
  const navigate = useNavigate();
  const [scanResults, setScanResults] = useState<ScanResult[]>([]);
  const [scanMetadata, setScanMetadata] = useState<any>(null);
  const [rejectionStats, setRejectionStats] = useState<any>(null);
  const [selectedResult, setSelectedResult] = useState<ScanResult | null>(null);
  const [isChartModalOpen, setIsChartModalOpen] = useState(false);
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
    <>
      {/* Tactical Background - Fixed layers behind content */}
      <TacticalBackground />

      <PageContainer id="main-content" className="relative z-10">
        <div className="space-y-10">
          <div className="flex justify-start">
            <HomeButton />
          </div>

          {/* Tactical Header */}
          <div className="relative text-center py-8">
            {/* Background reticle effect */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="w-64 h-64 border border-[#00ff88]/10 rounded-full animate-[pulse_4s_ease-in-out_infinite]" />
              <div className="absolute w-48 h-48 border border-[#00ff88]/20 rounded-full animate-[pulse_3s_ease-in-out_infinite_0.5s]" />
              <div className="absolute w-32 h-32 border border-[#00ff88]/30 rounded-full animate-[pulse_2s_ease-in-out_infinite_1s]" />
            </div>

            <h1 className="display-headline hud-text-green text-4xl lg:text-5xl mb-3 relative z-10">
              TARGETS ACQUIRED
            </h1>
            <p className="text-lg text-muted-foreground font-mono tracking-wider relative z-10">
              {results.length} HIGH-PROBABILITY SETUP{results.length !== 1 ? 'S' : ''} LOCKED
            </p>

            {/* New Scan Button */}
            <Button
              onClick={() => navigate('/scan')}
              variant="outline"
              className="mt-6 h-12 px-8 glass-card glow-border-green hover:bg-[#00ff88]/10 transition-all font-mono tracking-wider"
              size="lg"
            >
              <TrendUp size={20} weight="bold" className="mr-2" />
              NEW SCAN
            </Button>
          </div>

          {/* Live Ticker - Enhanced */}
          <div className="glass-card glow-border-green rounded-xl overflow-hidden">
            <LiveTicker symbols={sortedResults.slice(0, 6).map(r => r.pair)} />
          </div>

          {/* Mission Stats - NEW hero section */}
          <MissionStats results={results} metadata={scanMetadata} />

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
            <section className="glass-card glow-border-amber rounded-2xl overflow-hidden">
              <button
                type="button"
                className="w-full p-5 cursor-pointer select-none hover:bg-white/5 transition-colors text-left"
                onClick={() => setShowMetadata(!showMetadata)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 bg-amber-400 rounded-full animate-pulse" />
                    <h3 className="text-lg font-bold hud-headline tracking-wide text-amber-400">
                      SCAN CONFIGURATION
                    </h3>
                  </div>
                  {showMetadata ?
                    <CaretUp size={20} weight="bold" className="text-amber-400" /> :
                    <CaretDown size={20} weight="bold" className="text-muted-foreground" />
                  }
                </div>
              </button>
              {showMetadata && (
                <div className="px-5 pb-5 animate-in fade-in slide-in-from-top-2 duration-300">
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
                    <div className="p-4 bg-black/40 rounded-lg border border-amber-500/20">
                      <div className="text-xs text-muted-foreground mb-2 uppercase tracking-widest font-mono">Mode</div>
                      <Badge className="bg-amber-500/20 text-amber-400 border border-amber-500/40 uppercase font-mono font-bold">
                        {scanMetadata.mode}
                      </Badge>
                    </div>
                    <div className="p-4 bg-black/40 rounded-lg border border-blue-500/20">
                      <div className="text-xs text-muted-foreground mb-2 uppercase tracking-widest font-mono">Timeframes</div>
                      <div className="font-mono font-semibold text-blue-400">
                        {scanMetadata.appliedTimeframes?.join(' · ')}
                      </div>
                    </div>
                    <div className="p-4 bg-black/40 rounded-lg border border-[#00ff88]/20">
                      <div className="text-xs text-muted-foreground mb-2 uppercase tracking-widest font-mono">Min Score</div>
                      <div className="font-mono font-bold text-lg text-[#00ff88]">
                        {scanMetadata.effectiveMinScore}%
                      </div>
                    </div>
                    <div className="p-4 bg-black/40 rounded-lg border border-cyan-500/20">
                      <div className="text-xs text-muted-foreground mb-2 uppercase tracking-widest font-mono">Profile</div>
                      <div className="font-mono font-semibold capitalize text-cyan-400">
                        {scanMetadata.profile?.replace(/_/g, ' ')}
                      </div>
                    </div>
                    <div className="p-4 bg-black/40 rounded-lg border border-amber-500/20">
                      <div className="text-xs text-muted-foreground mb-2 uppercase tracking-widest font-mono">Scanned</div>
                      <div className="font-mono font-bold text-lg text-amber-400">
                        {scanMetadata.scanned}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </section>
          )}


          <section className="glass-card glow-border-green rounded-2xl overflow-hidden">
            <button
              type="button"
              className="w-full p-5 cursor-pointer select-none hover:bg-white/5 transition-colors text-left"
              onClick={() => setShowResults(!showResults)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 bg-[#00ff88] rounded-full animate-pulse" />
                  <h3 className="text-xl font-bold hud-headline tracking-wide hud-text-green">
                    SCAN RESULTS
                  </h3>
                  <Badge className="bg-[#00ff88]/20 text-[#00ff88] border border-[#00ff88]/40 font-mono">
                    {results.length} TARGETS
                  </Badge>
                </div>
                {showResults ?
                  <CaretUp size={24} weight="bold" className="text-[#00ff88]" /> :
                  <CaretDown size={24} weight="bold" className="text-muted-foreground" />
                }
              </div>
            </button>
            {showResults && (
              <div className="px-5 pb-5 animate-in fade-in slide-in-from-top-2 duration-300">
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
              </div>
            )}
          </section>

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
              <div className="glass-card glow-border-green px-6 py-4 rounded-2xl flex items-center gap-6">
                {/* Selection count */}
                <div className="flex items-center gap-3">
                  <span className="text-3xl font-bold font-mono tabular-nums hud-text-green">
                    {selectedForCompare.length}
                  </span>
                  <span className="text-xs uppercase tracking-widest text-muted-foreground font-mono">
                    TARGETS<br />SELECTED
                  </span>
                </div>

                <div className="h-10 w-px bg-white/10" />

                {/* Compare button */}
                <Button
                  onClick={handleOpenCompare}
                  disabled={selectedForCompare.length < 2}
                  className="bg-[#00ff88] text-black font-bold uppercase tracking-wider hover:bg-[#00ff88]/90 disabled:opacity-50 disabled:cursor-not-allowed px-6 h-10"
                >
                  {selectedForCompare.length < 2 ? 'SELECT 2+' : 'EXECUTE COMPARE'}
                </Button>

                {/* Clear button */}
                <Button
                  variant="ghost"
                  onClick={() => setSelectedForCompare([])}
                  className="h-10 w-10 p-0 rounded-full hover:bg-red-500/20 hover:text-red-400 transition-colors"
                >
                  <Minus size={18} weight="bold" />
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
    </>
  );
}
