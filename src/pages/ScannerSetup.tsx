import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useScanner } from '@/context/ScannerContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Crosshair, Lightning, Target } from '@phosphor-icons/react';
import { convertSignalToScanResult } from '@/utils/mockData';
import { SniperModeSelector } from '@/components/SniperModeSelector';
import { api } from '@/utils/api';
import { useToast } from '@/hooks/use-toast';
import { PageShell } from '@/components/layout/PageShell';
import { scanHistoryService } from '@/services/scanHistoryService';
import { HudPanel, MissionBrief, TargetReticleOverlay } from '@/components/hud';
import { ScannerConsole } from '@/components/ScannerConsole';

export function ScannerSetup() {
  const navigate = useNavigate();
  const { scanConfig, setScanConfig, selectedMode } = useScanner();
  const [isScanning, setIsScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState<{ current: number; total: number; symbol?: string } | null>(null);
  const { toast } = useToast();
  // Local state for topPairs input to allow empty string
  const [topPairsInput, setTopPairsInput] = useState(scanConfig.topPairs.toString());

  // Keep local input in sync with context changes
  useEffect(() => {
    setTopPairsInput(scanConfig.topPairs.toString());
  }, [scanConfig.topPairs]);

  const handleArmScanner = async () => {
    console.log('[ScannerSetup] Starting background scan job...', {
      mode: scanConfig.sniperMode,
      exchange: scanConfig.exchange,
      leverage: scanConfig.leverage,
      topPairs: scanConfig.topPairs,
      minScore: selectedMode?.min_confluence_score,
      categories: scanConfig.categories
    });
    setIsScanning(true);
    setScanProgress({ current: 0, total: 0 });
    
    localStorage.removeItem('scan-results');
    localStorage.removeItem('scan-metadata');
    localStorage.removeItem('scan-rejections');

    try {
      // Start background scan job
      const createResponse = await api.createScanRun({
        limit: scanConfig.topPairs || 20,
        min_score: selectedMode?.min_confluence_score || 0,
        sniper_mode: scanConfig.sniperMode,
        majors: scanConfig.categories.majors,
        altcoins: scanConfig.categories.altcoins,
        meme_mode: scanConfig.categories.memeMode,
        exchange: scanConfig.exchange,
        leverage: scanConfig.leverage || 1,
      });

      if (createResponse.error || !createResponse.data) {
        throw new Error(createResponse.error || 'Failed to start scan');
      }

      const runId = createResponse.data.run_id;
      console.log('[ScannerSetup] Scan job started:', runId);

      // Poll for progress
      const pollInterval = setInterval(async () => {
        const statusResponse = await api.getScanRun(runId);
        
        if (statusResponse.error || !statusResponse.data) {
          clearInterval(pollInterval);
          throw new Error(statusResponse.error || 'Failed to get scan status');
        }

        const job = statusResponse.data;
        console.log('[ScannerSetup] Job status:', job.status, `${job.progress}/${job.total}`);
        
        setScanProgress({
          current: job.progress,
          total: job.total,
          symbol: job.current_symbol
        });

        if (job.status === 'completed') {
          clearInterval(pollInterval);
          
          const results = (job.signals || []).map(convertSignalToScanResult);
          
          localStorage.setItem('scan-results', JSON.stringify(results));
          
          const metadata = {
            mode: job.metadata?.mode || scanConfig.sniperMode,
            appliedTimeframes: job.metadata?.applied_timeframes || [],
            effectiveMinScore: job.metadata?.effective_min_score || 0,
            baselineMinScore: selectedMode?.min_confluence_score || 0,
            profile: job.metadata?.profile || 'default',
            scanned: job.metadata?.scanned || 0,
          };
          localStorage.setItem('scan-metadata', JSON.stringify(metadata));
          
          if (job.rejections) {
            localStorage.setItem('scan-rejections', JSON.stringify(job.rejections));
          }
          
          scanHistoryService.saveScan({
            mode: metadata.mode,
            profile: metadata.profile,
            timeframes: metadata.appliedTimeframes,
            symbolsScanned: metadata.scanned,
            signalsGenerated: results.length,
            signalsRejected: job.metadata?.rejected || 0,
            effectiveMinScore: metadata.effectiveMinScore,
            rejectionBreakdown: job.rejections?.by_reason,
            results: results,
          });
          
          console.log('[ScannerSetup] Scan completed:', results.length, 'signals');
          
          // Show appropriate message based on results
          if (results.length === 0) {
            toast({
              title: 'No Setups Found',
              description: `Scanned ${job.metadata?.scanned || 0} symbols - all rejected. Try adjusting mode or threshold.`,
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
        } else if (job.status === 'failed') {
          clearInterval(pollInterval);
          throw new Error(job.error || 'Scan failed');
        } else if (job.status === 'cancelled') {
          clearInterval(pollInterval);
          throw new Error('Scan cancelled');
        }
      }, 2000); // Poll every 2 seconds

      // Timeout after 10 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        if (isScanning) {
          throw new Error('Scan timeout - job exceeded 10 minutes');
        }
      }, 600000);

    } catch (error) {
      console.error('Scanner error:', error);
      toast({
        title: 'Scanner Error',
        description: error instanceof Error ? error.message : 'Failed to complete scan',
        variant: 'destructive',
      });
      
      localStorage.setItem('scan-rejections', JSON.stringify({
        total_rejected: 0,
        by_reason: {},
        details: {},
      }));
      localStorage.setItem('scan-results', JSON.stringify([]));
      localStorage.removeItem('scan-metadata');
      
      setIsScanning(false);
      setScanProgress(null);
      navigate('/results');
    }
  };

  return (
    <PageShell>
      <div className="mx-auto w-full max-w-screen-2xl px-4 py-6 lg:py-8 space-y-6 lg:space-y-8">
        <div className="text-center space-y-3 mb-8">
          <h1 className="hud-headline text-emerald-700 dark:text-emerald-300 text-2xl md:text-4xl lg:text-5xl tracking-[0.2em] px-4 leading-relaxed py-2 drop-shadow-sm">SCANNER COMMAND CENTER</h1>
          <p className="text-lg md:text-xl lg:text-2xl text-slate-600 dark:text-slate-300 max-w-2xl mx-auto px-4">Configure your sniper profile, exchange, and filters, then arm the scanner to search for high-confluence setups.</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:gap-8">
          <div className="lg:col-span-2 space-y-6 lg:space-y-8 px-6 overflow-visible">
            <HudPanel 
              title="Scan Mode & Profile" 
              subtitle="Select your tactical mode and operational parameters"
              className="tactical-grid holo-border overflow-visible"
              titleClassName="hud-text-green"
            >
              <SniperModeSelector />
            </HudPanel>

            <HudPanel 
              title="Operational Parameters" 
              subtitle="Configure exchange, leverage, scanning scope, and asset classes"
              className="relative bg-card"
              titleClassName="hud-text-amber"
            >
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <span id="exchange-label" className="w-32 text-right text-base font-mono text-muted-foreground">Exchange</span>
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
                  <span id="leverage-label" className="w-32 text-right text-base font-mono text-muted-foreground">Leverage</span>
                  <div className="flex-1 flex justify-end">
                    <Select
                      value={(scanConfig.leverage ?? 1).toString()}
                      onValueChange={(value) =>
                        setScanConfig({ ...scanConfig, leverage: parseInt(value) })
                      }
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
                  <label htmlFor="top-pairs" id="top-pairs-label" className="w-32 text-right text-base font-mono text-muted-foreground">Pairs to Scan</label>
                  <div className="flex-1 flex justify-end">
                    <div>
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
                        className="bg-background border-border hover:border-primary/50 focus:border-primary transition-colors h-12 font-mono text-lg w-20 max-w-24"
                      />
                      <p className="text-sm text-muted-foreground mt-2">
                        Higher values scan more symbols but take longer
                      </p>
                    </div>
                  </div>
                </div>

                <div className="h-px bg-border/50" />

                <div className="flex items-center gap-4">
                  <span id="majors-label" className="w-32 text-right text-base font-mono text-muted-foreground">Majors</span>
                  <div className="flex-1 flex justify-end">
                    <Switch
                      id="majors"
                      aria-labelledby="majors-label"
                      aria-label="Toggle Majors"
                      checked={scanConfig.categories.majors}
                      onCheckedChange={(checked) =>
                        setScanConfig({
                          ...scanConfig,
                          categories: { ...scanConfig.categories, majors: checked },
                        })
                      }
                      className="shrink-0"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <span id="altcoins-label" className="w-32 text-right text-base font-mono text-muted-foreground">Altcoins</span>
                  <div className="flex-1 flex justify-end">
                    <Switch
                      id="altcoins"
                      aria-labelledby="altcoins-label"
                      aria-label="Toggle Altcoins"
                      checked={scanConfig.categories.altcoins}
                      onCheckedChange={(checked) =>
                        setScanConfig({
                          ...scanConfig,
                          categories: { ...scanConfig.categories, altcoins: checked },
                        })
                      }
                      className="shrink-0"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <div className="w-32 text-right">
                    <span id="meme-label" className="text-base font-mono text-muted-foreground">Meme Mode</span>
                  </div>
                  <div className="flex-1 flex items-center justify-end gap-3">
                    <Switch
                      id="meme"
                      aria-labelledby="meme-label"
                      aria-label="Toggle Meme Mode"
                      checked={scanConfig.categories.memeMode}
                      onCheckedChange={(checked) =>
                        setScanConfig({
                          ...scanConfig,
                          categories: { ...scanConfig.categories, memeMode: checked },
                        })
                      }
                      className="shrink-0"
                    />
                    {scanConfig.categories.memeMode && (
                      <Badge variant="outline" className="text-xs bg-red-100 dark:bg-destructive/20 text-red-800 dark:text-destructive border-red-300 dark:border-destructive/50 px-2 py-0.5 font-sans">HIGH VOLATILITY</Badge>
                    )}
                  </div>
                </div>
              </div>
            </HudPanel>

            {/* Filters & Asset Categories panel removed; toggles moved above */}
          </div>

          <div className="lg:col-span-1 flex flex-col px-6">
            <HudPanel 
              title="Scanner Console" 
              subtitle="Real-time scan progress and system status"
              className="tactical-grid holo-border flex-1 flex flex-col"
              titleClassName="hud-text-green"
            >
              <ScannerConsole
                isScanning={isScanning}
                className="hud-console hud-terminal text-xs flex-1 min-h-[300px]"
              />
            </HudPanel>
          </div>
        </div>

        <MissionBrief title="Intel Brief" className="hud-glow-cyan">
          <p className="mb-2">Scanner will analyze top symbols across multiple timeframes using Smart Money Concepts detection.</p>
          <p className="text-muted-foreground text-xs">Higher timeframes provide better confluence but require more data processing time.</p>
        </MissionBrief>

        <TargetReticleOverlay className="relative pt-2">
          <Button
            onClick={handleArmScanner}
            disabled={isScanning || scanConfig.timeframes.length === 0}
            className="inline-flex items-center justify-center gap-3 px-8 py-4 rounded-lg font-bold btn-tactical-scanner w-full text-base md:text-lg disabled:opacity-50"
            size="lg"
          >
            {isScanning ? (
              <>
                <Lightning size={24} />
                <span className="mx-2">
                  {scanProgress && scanProgress.total > 0 
                    ? `Scanning ${scanProgress.current}/${scanProgress.total}${scanProgress.symbol ? ` • ${scanProgress.symbol}` : ''}`
                    : 'Initializing Scan...'
                  }
                </span>
                <Lightning size={24} />
              </>
            ) : (
              <>
                <Crosshair size={24} weight="bold" />
                <span className="mx-3">Arm Scanner</span>
                <Target size={24} weight="bold" />
              </>
            )}
          </Button>
          {scanProgress && scanProgress.total > 0 && (
            <div className="relative mt-3 h-2 bg-background/60 rounded-full overflow-hidden border border-primary/30">
              <div 
                className="absolute inset-y-0 left-0 bg-gradient-to-r from-primary to-accent transition-all duration-500 rounded-full"
                style={{ width: `${(scanProgress.current / scanProgress.total) * 100}%` }}
              />
            </div>
          )}
        </TargetReticleOverlay>
      </div>
    </PageShell>
  );
}
