import { PageContainer } from '@/components/layout/PageContainer';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useScanner } from '@/context/ScannerContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Crosshair, Lightning } from '@phosphor-icons/react';
import { convertSignalToScanResult, generateDemoScanResults } from '@/utils/mockData';
import { SniperModeSelector } from '@/components/SniperModeSelector';
import { api } from '@/utils/api';
import { useToast } from '@/hooks/use-toast';
import { scanHistoryService } from '@/services/scanHistoryService';
import { ScannerConsole } from '@/components/ScannerConsole';
import { debugLogger } from '@/utils/debugLogger';

export function ScannerSetup() {
  const navigate = useNavigate();
  const { scanConfig, setScanConfig, selectedMode, addConsoleLog, clearConsoleLogs } = useScanner();
  const [isScanning, setIsScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState<{ current: number; total: number; symbol?: string } | null>(null);
  const { toast } = useToast();
  // Local state for topPairs input to allow empty string
  const [topPairsInput, setTopPairsInput] = useState(scanConfig.topPairs.toString());

  // Keep local input in sync with context changes
  useEffect(() => {
    setTopPairsInput(scanConfig.topPairs.toString());
  }, [scanConfig.topPairs]);

  // Clear any stale console logs when arriving on setup screen if not actively scanning
  useEffect(() => {
    clearConsoleLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleArmScanner = async () => {
    setIsScanning(true);
    setScanProgress({ current: 0, total: 0 });
    
    // Clear previous results
    localStorage.removeItem('scan-results');
    localStorage.removeItem('scan-metadata');
    localStorage.removeItem('scan-rejections');

    // Log scan initialization
    debugLogger.info('━━━ SCAN INITIATED ━━━', 'scanner');
    debugLogger.info(`Mode: ${scanConfig.sniperMode.toUpperCase()}`, 'scanner');
    debugLogger.info(`Exchange: ${scanConfig.exchange} | Leverage: ${scanConfig.leverage}x`, 'scanner');
    debugLogger.info(`Categories: Majors=${scanConfig.categories.majors}, Alts=${scanConfig.categories.altcoins}, Meme=${scanConfig.categories.memeMode}`, 'scanner');
    debugLogger.info(`Target pairs: ${scanConfig.topPairs} | Min Score: ${selectedMode?.min_confluence_score || 0}`, 'scanner');
    debugLogger.info(`API Base URL: ${api.baseURL}`, 'scanner');

    try {
      debugLogger.info('Sending request to backend...', 'scanner');
      const signalsResponse = await api.getSignals({
        limit: scanConfig.topPairs || 20,
        min_score: selectedMode?.min_confluence_score || 0,
        sniper_mode: scanConfig.sniperMode,
        majors: scanConfig.categories.majors,
        altcoins: scanConfig.categories.altcoins,
        meme_mode: scanConfig.categories.memeMode,
        exchange: scanConfig.exchange,
        leverage: scanConfig.leverage || 1,
        macro_overlay: scanConfig.macroOverlay,
      });

      if (signalsResponse.error || !signalsResponse.data) {
        debugLogger.error(`Scan failed: ${signalsResponse.error || 'No data received'}`, 'scanner');
        throw new Error(signalsResponse.error || 'Failed to fetch signals');
      }

      const data = signalsResponse.data;
      debugLogger.success(`✓ Received response: ${data.signals?.length || 0} signals`, 'scanner');
      debugLogger.info(`Scanned: ${data.scanned} | Rejected: ${data.rejected}`, 'scanner');

      // Process results immediately (no polling needed)
      const results = (data.signals || []).map(convertSignalToScanResult);
      
      localStorage.setItem('scan-results', JSON.stringify(results));
      
      // Read from root level - backend returns flat structure, not nested metadata
      const metadata = {
        mode: data.mode || scanConfig.sniperMode,
        appliedTimeframes: data.applied_timeframes || [],
        effectiveMinScore: data.effective_min_score || 0,
        baselineMinScore: data.baseline_min_score || selectedMode?.min_confluence_score || 0,
        profile: data.profile || 'default',
        scanned: data.scanned || 0,
        rejected: data.rejected || 0,
        exchange: data.exchange,
        leverage: data.leverage,
        criticalTimeframes: data.critical_timeframes || [],
      };
      localStorage.setItem('scan-metadata', JSON.stringify(metadata));
      
      if (data.rejections) {
        localStorage.setItem('scan-rejections', JSON.stringify(data.rejections));
      }
      
      scanHistoryService.saveScan({
        mode: metadata.mode,
        profile: metadata.profile,
        timeframes: metadata.appliedTimeframes,
        symbolsScanned: metadata.scanned,
        signalsGenerated: results.length,
        signalsRejected: metadata.rejected,
        effectiveMinScore: metadata.effectiveMinScore,
        rejectionBreakdown: data.rejections?.by_reason,
        results: results,
      });
      
      debugLogger.success(`━━━ SCAN COMPLETE: ${results.length} signals ━━━`, 'scanner');
      
      // Show appropriate message based on results
      if (results.length === 0) {
        toast({
          title: 'No Setups Found',
          description: `Scanned ${metadata.scanned || 0} symbols - all rejected. Try adjusting mode or threshold.`,
          variant: 'destructive',
        });
      } else {
        toast({
          title: 'Targets Acquired',
          description: `${results.length} high-conviction setups identified`,
        });
      }
      
      setIsScanning(false);
      setScanProgress(null);
      navigate('/results');

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      debugLogger.error(`━━━ SCAN FAILED ━━━`, 'scanner');
      debugLogger.error(`Error: ${errorMessage}`, 'scanner');
      debugLogger.warning('Falling back to demo results...', 'scanner');
      
      console.error('Scanner error:', error);
      // Fallback to demo results to prevent empty UI when backend is unreachable (e.g., 504)
      const demo = generateDemoScanResults(Math.min(scanConfig.topPairs || 5, 5), scanConfig.sniperMode);
      localStorage.setItem('scan-results', JSON.stringify(demo));
      localStorage.setItem('scan-rejections', JSON.stringify({
        total_rejected: 0,
        by_reason: {},
        details: {},
      }));
      localStorage.setItem('scan-metadata', JSON.stringify({
        mode: scanConfig.sniperMode,
        appliedTimeframes: scanConfig.timeframes,
        effectiveMinScore: selectedMode?.min_confluence_score || 0,
        baselineMinScore: selectedMode?.min_confluence_score || 0,
        profile: selectedMode?.profile || 'default',
        scanned: demo.length,
        offline: true,
      }));

      toast({
        title: 'Operating Offline',
        description: `Backend unavailable (e.g., 504). Showing ${demo.length} demo setups.`,
      });

      setIsScanning(false);
      setScanProgress(null);
      navigate('/results');
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-background" id="main-content">
      <main className="py-10 md:py-14">
        <PageContainer>
        <div className="fixed inset-0 tactical-grid opacity-20 pointer-events-none" aria-hidden="true" />
        <div className="max-w-6xl mx-auto space-y-8">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold hud-headline hud-text-green">SCANNER SETUP</h1>
          <p className="hud-terminal text-primary/80">Configure your scanner parameters</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            {/* Scan Mode */}
            <div className="rounded-2xl p-6 md:p-8 backdrop-blur-sm card-3d">
              <h2 className="text-xl font-semibold mb-4 hud-headline hud-text-green">SCAN MODE & PROFILE</h2>
              <SniperModeSelector />
            </div>

            {/* Operational Parameters */}
            <div className="rounded-2xl p-6 md:p-8 backdrop-blur-sm card-3d">
              <h2 className="text-xl font-semibold mb-4 hud-headline hud-text-green">OPERATIONAL PARAMETERS</h2>
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <span id="exchange-label" className="w-32 text-right text-base hud-terminal text-primary/90 tracking-wide">EXCHANGE</span>
                  <div className="flex-1 flex justify-end">
                    <Select
                      value={scanConfig.exchange}
                      onValueChange={(value) =>
                        setScanConfig({ ...scanConfig, exchange: value })
                      }
                    >
                      <SelectTrigger id="exchange" aria-label="Select Exchange" aria-labelledby="exchange-label" className="bg-background border-border hover:border-primary/50 transition-colors h-12 text-base font-mono">
                        <SelectValue placeholder="Exchange" />
                      </SelectTrigger>
                      <SelectContent className="font-mono">
                        <SelectItem value="phemex" className="text-base font-mono">⚡ Phemex (Fast, No Geo-Block)</SelectItem>
                        <SelectItem value="bybit" className="text-base font-mono">🔥 Bybit (May Be Geo-Blocked)</SelectItem>
                        <SelectItem value="okx" className="text-base font-mono">🏛️ OKX (May Be Geo-Blocked)</SelectItem>
                        <SelectItem value="bitget" className="text-base font-mono">🤖 Bitget</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="h-px bg-border/50" />

                <div className="flex items-center gap-4">
                  <span id="leverage-label" className="w-32 text-right text-base hud-terminal text-primary/90 tracking-wide">LEVERAGE</span>
                  <div className="flex-1 flex justify-end">
                    <Select
                      value={(scanConfig.leverage ?? 1).toString()}
                      onValueChange={(value) => {
                        const lev = parseInt(value);
                        setScanConfig({ ...scanConfig, leverage: lev });
                        addConsoleLog(`CONFIG: Leverage set to ${lev}x`, 'config');
                      }}
                    >
                      <SelectTrigger id="leverage" aria-label="Select Leverage" aria-labelledby="leverage-label" className="bg-background border-border hover:border-primary/50 transition-colors h-12 text-base font-mono">
                        <SelectValue placeholder="Leverage" />
                      </SelectTrigger>
                      <SelectContent className="font-mono">
                        <SelectItem value="1" className="text-base font-mono">1x (No Leverage)</SelectItem>
                        <SelectItem value="2" className="text-base font-mono">2x</SelectItem>
                        <SelectItem value="3" className="text-base font-mono">3x</SelectItem>
                        <SelectItem value="5" className="text-base font-mono">5x</SelectItem>
                        <SelectItem value="10" className="text-base font-mono">10x</SelectItem>
                        <SelectItem value="20" className="text-base font-mono">20x</SelectItem>
                        <SelectItem value="50" className="text-base font-mono">50x</SelectItem>
                        <SelectItem value="100" className="text-base font-mono">100x</SelectItem>
                        <SelectItem value="125" className="text-base font-mono">125x</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="h-px bg-border/50" />

                <div className="flex items-center gap-4">
                  <label htmlFor="top-pairs" id="top-pairs-label" className="w-32 text-right text-base hud-terminal text-primary/90 tracking-wide">PAIRS TO SCAN</label>
                  <div className="flex-1 flex flex-col items-end">
                    <Input
                      id="top-pairs"
                      aria-labelledby="top-pairs-label"
                      type="number"
                      min="1"
                      max="100"
                      value={topPairsInput}
                      onChange={(e) => {
                        const val = e.target.value;
                        // Allow empty string for deletion
                        setTopPairsInput(val);
                        if (val === '') return;
                        const num = Number(val);
                        if (!isNaN(num) && num >= 1 && num <= 100) {
                          setScanConfig({ ...scanConfig, topPairs: num });
                        }
                      }}
                      className="h-12 text-lg w-20 max-w-24"
                    />
                    <p className="text-sm hud-terminal text-primary/60 mt-2 text-right">
                      Higher values scan more symbols but take longer
                    </p>
                  </div>
                </div>

              </div>
            </div>

            {/* Asset Categories */}
            <div className="rounded-2xl p-6 md:p-8 backdrop-blur-sm card-3d">
              <h2 className="text-xl font-semibold mb-2 hud-headline hud-text-green">ASSET CATEGORIES</h2>
              <p className="hud-terminal text-primary/80 mb-4">Enable or disable asset classes for scanning</p>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded border border-border/40 bg-background/40 hover:border-primary/30 transition-colors">
                  <span className="hud-terminal text-primary/90 tracking-wide">MAJORS</span>
                  <Switch
                    id="majors"
                    checked={scanConfig.categories.majors}
                    onCheckedChange={(checked) =>
                      setScanConfig({
                        ...scanConfig,
                        categories: { ...scanConfig.categories, majors: checked },
                      })
                    }
                  />
                </div>
                <div className="flex items-center justify-between p-3 rounded border border-border/40 bg-background/40 hover:border-primary/30 transition-colors">
                  <span className="hud-terminal text-primary/90 tracking-wide">ALTCOINS</span>
                  <Switch
                    id="altcoins"
                    checked={scanConfig.categories.altcoins}
                    onCheckedChange={(checked) =>
                      setScanConfig({
                        ...scanConfig,
                        categories: { ...scanConfig.categories, altcoins: checked },
                      })
                    }
                  />
                </div>
                <div className="flex items-center justify-between p-3 rounded border border-border/40 bg-background/40 hover:border-primary/30 transition-colors">
                  <div className="flex items-center gap-3">
                    <span className="hud-terminal text-primary/90 tracking-wide">MEME MODE</span>
                    {scanConfig.categories.memeMode && (
                      <Badge variant="outline" className="text-xs hud-text-amber border-warning/50">HIGH VOLATILITY</Badge>
                    )}
                  </div>
                  <Switch
                    id="meme"
                    checked={scanConfig.categories.memeMode}
                    onCheckedChange={(checked) =>
                      setScanConfig({
                        ...scanConfig,
                        categories: { ...scanConfig.categories, memeMode: checked },
                      })
                    }
                  />
                </div>

                <div className="h-px bg-border/50 my-4" />

                <div className="flex items-center justify-between p-3 rounded border border-border/40 bg-background/40 hover:border-primary/30 transition-colors">
                  <div className="flex items-center gap-3">
                    <span className="hud-terminal text-primary/90 tracking-wide">MACRO OVERLAY</span>
                    {scanConfig.macroOverlay && (
                      <Badge variant="outline" className="text-xs hud-text-green border-accent/50">DOMINANCE FLOW</Badge>
                    )}
                  </div>
                  <Switch
                    id="macro-overlay"
                    checked={scanConfig.macroOverlay}
                    onCheckedChange={(checked) => {
                      setScanConfig({
                        ...scanConfig,
                        macroOverlay: checked,
                      });
                      addConsoleLog(
                        `CONFIG: Macro overlay ${checked ? 'enabled' : 'disabled'} (BTC/ALT dominance flow)`,
                        'config'
                      );
                    }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Console */}
          <div className="rounded-2xl p-6 md:p-8 backdrop-blur-sm card-3d mb-6 relative z-0">
            <h2 className="text-xl font-semibold mb-4 hud-headline hud-text-green">SCANNER CONSOLE</h2>
            <ScannerConsole
              isScanning={isScanning}
              className=""
            />
          </div>
        </div>

        {/* Arm Button */}
        <Button
          onClick={handleArmScanner}
          disabled={isScanning || scanConfig.timeframes.length === 0}
          className="w-full h-14 text-lg relative z-10 btn-tactical-scanner"
          size="lg"
        >
          {isScanning ? (
            <>
              <Lightning size={24} className="mr-2" />
              {scanProgress && scanProgress.total > 0 
                ? `Scanning ${scanProgress.current}/${scanProgress.total}${scanProgress.symbol ? ` • ${scanProgress.symbol}` : ''}`
                : 'Initializing Scan...'
              }
            </>
          ) : (
            <>
              <Crosshair size={24} className="mr-2" />
              Arm Scanner
            </>
          )}
        </Button>
        
        {scanProgress && scanProgress.total > 0 && (
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div 
              className="h-full bg-primary transition-all duration-500"
              style={{ width: `${(scanProgress.current / scanProgress.total) * 100}%` }}
            />
          </div>
        )}
        </div>
        </PageContainer>
      </main>
    </div>
  );
}
