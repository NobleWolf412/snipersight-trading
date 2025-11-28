import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useScanner } from '@/context/ScannerContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Crosshair, Lightning } from '@phosphor-icons/react';
import { convertSignalToScanResult } from '@/utils/mockData';
import { SniperModeSelector } from '@/components/SniperModeSelector';
import { api } from '@/utils/api';
import { useToast } from '@/hooks/use-toast';
import { scanHistoryService } from '@/services/scanHistoryService';
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
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold text-foreground">Scanner Setup</h1>
          <p className="text-muted-foreground">Configure your scanner parameters</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            {/* Scan Mode */}
            <div className="border border-border rounded-lg p-6 bg-card">
              <h2 className="text-xl font-semibold mb-4">Scan Mode & Profile</h2>
              <SniperModeSelector />
            </div>

            {/* Operational Parameters */}
            <div className="border border-border rounded-lg p-6 bg-card">
              <h2 className="text-xl font-semibold mb-4">Operational Parameters</h2>
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

              </div>
            </div>

            {/* Asset Categories */}
            <div className="border border-border rounded-lg p-6 bg-card">
              <h2 className="text-xl font-semibold mb-2">Asset Categories</h2>
              <p className="text-muted-foreground mb-4">Enable or disable asset classes for scanning</p>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-foreground">Majors</span>
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
                <div className="flex items-center justify-between">
                  <span className="text-foreground">Altcoins</span>
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
                <div className="flex items-center justify-between">
                  <span className="text-foreground">Meme Mode</span>
                  <div className="flex items-center gap-3">
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
                    {scanConfig.categories.memeMode && (
                      <Badge variant="outline" className="text-xs">HIGH VOLATILITY</Badge>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Console */}
          <div className="border border-border rounded-lg p-6 bg-card">
            <h2 className="text-xl font-semibold mb-4">Scanner Console</h2>
            <ScannerConsole
              isScanning={isScanning}
              className="min-h-[300px]"
            />
          </div>
        </div>

        {/* Info */}
        <div className="border border-border rounded-lg p-6 bg-card">
          <h3 className="font-semibold mb-2">Intel Brief</h3>
          <p className="text-sm text-muted-foreground mb-2">Scanner will analyze top symbols across multiple timeframes using Smart Money Concepts detection.</p>
          <p className="text-xs text-muted-foreground">Higher timeframes provide better confluence but require more data processing time.</p>
        </div>

        {/* Arm Button */}
        <Button
          onClick={handleArmScanner}
          disabled={isScanning || scanConfig.timeframes.length === 0}
          className="w-full h-14 text-lg"
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
    </div>
  );
}
