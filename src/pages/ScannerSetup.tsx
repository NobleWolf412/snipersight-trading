import { useState } from 'react';
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
          <h1 className="hud-headline hud-text-green text-base md:text-xl lg:text-2xl tracking-[0.2em] px-4 leading-relaxed py-2">SCANNER COMMAND CENTER</h1>
          <p className="text-base md:text-lg text-slate-400 max-w-2xl mx-auto px-4">Configure your sniper profile, exchange, and filters, then arm the scanner to search for high-confluence setups.</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:gap-8">
          <div className="lg:col-span-2 space-y-6 lg:space-y-8 bg-red-600">
            <HudPanel 
              title="Scan Mode & Profile" 
              subtitle="Select your tactical mode and operational parameters"
              className="tactical-grid holo-border"
              titleClassName="hud-text-green"
            >
              <div className="space-y-4">
                <div className="space-y-2 border-red-600 bg-slate-900">
                  <Label className="text-base md:text-lg font-bold uppercase tracking-widest text-muted-foreground">SNIPER MODE</Label>
                  <SniperModeSelector />
                </div>
              </div>
            </HudPanel>

            <HudPanel 
              title="Operational Parameters" 
              subtitle="Configure exchange, leverage, and scanning scope"
              className="tactical-grid holo-border"
              titleClassName="hud-text-amber"
            >
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="exchange" className="text-base md:text-lg font-bold uppercase tracking-widest text-muted-foreground">
                    Exchange
                  </Label>
                  <Select
                    value={scanConfig.exchange}
                    onValueChange={(value) =>
                      setScanConfig({ ...scanConfig, exchange: value })
                    }
                  >
                    <SelectTrigger id="exchange" className="bg-background/60 border-border/60 hover:border-primary/50 transition-colors h-12 text-base font-sans">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="font-sans">
                      <SelectItem value="phemex" className="text-base font-sans">⚡ Phemex (Fast, No Geo-Block)</SelectItem>
                      <SelectItem value="bybit" className="text-base font-sans">🔥 Bybit (May Be Geo-Blocked)</SelectItem>
                      <SelectItem value="okx" className="text-base font-sans">🏛️ OKX (May Be Geo-Blocked)</SelectItem>
                      <SelectItem value="bitget" className="text-base font-sans">🤖 Bitget</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="h-px bg-border/50" />

                <div className="space-y-2">
                  <Label htmlFor="leverage" className="text-base md:text-lg font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-2">
                    Leverage
                    <Badge variant="outline" className="text-xs font-normal text-warning border-warning/40 px-2 py-0.5 font-sans">Risk Multiple</Badge>
                  </Label>
                  <Select
                    value={(scanConfig.leverage ?? 1).toString()}
                    onValueChange={(value) =>
                      setScanConfig({ ...scanConfig, leverage: parseInt(value) })
                    }
                  >
                    <SelectTrigger id="leverage" className="bg-background/60 border-border/60 hover:border-primary/50 transition-colors h-12 text-base font-sans">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="font-sans">
                      <SelectItem value="1" className="text-base font-sans">1x (No Leverage)</SelectItem>
                      <SelectItem value="2" className="text-base font-sans">2x</SelectItem>
                      <SelectItem value="3" className="text-base font-sans">3x</SelectItem>
                      <SelectItem value="5" className="text-base font-sans">5x</SelectItem>
                      <SelectItem value="10" className="text-base font-sans">10x</SelectItem>
                      <SelectItem value="20" className="text-base font-sans">20x</SelectItem>
                      <SelectItem value="50" className="text-base font-sans">50x</SelectItem>
                      <SelectItem value="100" className="text-base font-sans">100x</SelectItem>
                      <SelectItem value="125" className="text-base font-sans">125x</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="h-px bg-border/50" />

                <div className="space-y-2">
                  <Label htmlFor="top-pairs" className="text-base md:text-lg font-bold uppercase tracking-widest text-muted-foreground">Top Pairs to Scan</Label>
                  <Input
                    id="top-pairs"
                    type="number"
                    min="1"
                    max="100"
                    value={scanConfig.topPairs ?? 20}
                    onChange={(e) =>
                      setScanConfig({ ...scanConfig, topPairs: parseInt(e.target.value) || 20 })
                    }
                    className="bg-background/60 border-border/60 hover:border-primary/50 focus:border-primary transition-colors h-12 font-mono text-lg"
                  />
                  <p className="text-sm text-muted-foreground">
                    Higher values scan more symbols but take longer
                  </p>
                </div>
              </div>
            </HudPanel>

            <HudPanel 
              title="Filters & Asset Categories" 
              subtitle="Enable or disable asset classes for scanning"
              className="tactical-grid holo-border"
              titleClassName="hud-text-amber"
            >
              <div className="space-y-3">
                <Label className="text-base md:text-lg font-bold uppercase tracking-widest text-muted-foreground">Category Filters</Label>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div 
                    className="flex items-center justify-between p-4 bg-background/40 rounded-lg border border-border/60 hover:border-accent/50 hover:bg-background/60 transition-all cursor-pointer"
                    onClick={() => setScanConfig({
                      ...scanConfig,
                      categories: { ...scanConfig.categories, majors: !scanConfig.categories.majors },
                    })}
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex flex-col gap-1.5">
                        <span className="text-base md:text-lg font-bold text-foreground uppercase tracking-wide font-sans">Majors</span>
                        <div className="flex items-center gap-1.5">
                          <Badge variant="outline" className="text-xs px-2 py-0.5 bg-accent/10 text-accent border-accent/40 font-sans">ETH</Badge>
                        </div>
                      </div>
                    </div>
                    <Switch
                      id="majors"
                      checked={scanConfig.categories.majors}
                      onCheckedChange={(checked) =>
                        setScanConfig({
                          ...scanConfig,
                          categories: { ...scanConfig.categories, majors: checked },
                        })
                      }
                      onClick={(e) => e.stopPropagation()}
                      className="data-[state=checked]:bg-accent"
                    />
                  </div>

                  <div 
                    className="flex items-center justify-between p-4 bg-background/40 rounded-lg border border-border/60 hover:border-primary/50 hover:bg-background/60 transition-all cursor-pointer"
                    onClick={() => setScanConfig({
                      ...scanConfig,
                      categories: { ...scanConfig.categories, altcoins: !scanConfig.categories.altcoins },
                    })}
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex flex-col gap-1.5">
                        <span className="text-base md:text-lg font-bold text-foreground uppercase tracking-wide font-sans">Altcoins</span>
                        <div className="flex items-center gap-1.5">
                          <Badge variant="outline" className="text-xs px-2 py-0.5 bg-primary/10 text-primary border-primary/40 font-sans">SOL</Badge>
                          <Badge variant="outline" className="text-xs px-2 py-0.5 bg-primary/10 text-primary border-primary/40 font-sans">MATIC</Badge>
                          <Badge variant="outline" className="text-xs px-2 py-0.5 bg-primary/10 text-primary border-primary/40 font-sans">LINK</Badge>
                        </div>
                      </div>
                    </div>
                    <Switch
                      id="altcoins"
                      checked={scanConfig.categories.altcoins}
                      onCheckedChange={(checked) =>
                        setScanConfig({
                          ...scanConfig,
                          categories: { ...scanConfig.categories, altcoins: checked },
                        })
                      }
                      onClick={(e) => e.stopPropagation()}
                      className="data-[state=checked]:bg-primary"
                    />
                  </div>

                  <div 
                    className="flex items-center justify-between p-4 bg-background/40 rounded-lg border border-destructive/40 hover:border-destructive/70 hover:bg-background/60 transition-all cursor-pointer"
                    onClick={() => setScanConfig({
                      ...scanConfig,
                      categories: { ...scanConfig.categories, memeMode: !scanConfig.categories.memeMode },
                    })}
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex flex-col gap-1.5">
                        <span className="text-base md:text-lg font-bold text-foreground uppercase tracking-wide font-sans">Meme Mode</span>
                        <div className="flex items-center gap-1.5">
                          <Badge variant="outline" className="text-xs bg-destructive/20 text-destructive border-destructive/50 px-2 py-0.5 font-sans">▼ HIGH VOLATILITY</Badge>
                        </div>
                      </div>
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
                      onClick={(e) => e.stopPropagation()}
                      className="data-[state=checked]:bg-destructive"
                    />
                  </div>
                </div>
              </div>
            </HudPanel>
          </div>

          <div className="lg:col-span-1">
            <HudPanel 
              title="Scanner Console" 
              subtitle="Real-time scan progress and system status"
              className="tactical-grid holo-border h-full"
              titleClassName="hud-text-green"
            >
              <div className="hud-console hud-terminal text-xs">
                <ScannerConsole isScanning={isScanning} />
              </div>
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
