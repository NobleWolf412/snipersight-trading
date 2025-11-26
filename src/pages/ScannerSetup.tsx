import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useScanner } from '@/context/ScannerContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Crosshair, Lightning, Target, ChartBar, GearSix } from '@phosphor-icons/react';
import type { ScanResult } from '@/utils/mockData';
import { generateMockScanResults, convertSignalToScanResult } from '@/utils/mockData';
import { MarketRegimeLens } from '@/components/market/MarketRegimeLens';
import { useMarketRegime } from '@/hooks/use-market-regime';
import { SniperModeSelector } from '@/components/SniperModeSelector';
import { api } from '@/utils/api';
import { useToast } from '@/hooks/use-toast';
import { TacticalSection } from '@/components/layout/TacticalSection';
import { HomeButton } from '@/components/layout/HomeButton';
import { scanHistoryService } from '@/services/scanHistoryService';

export function ScannerSetup() {
  const navigate = useNavigate();
  const { scanConfig, setScanConfig, selectedMode } = useScanner();
  const [isScanning, setIsScanning] = useState(false);
  const { toast } = useToast();

  const marketRegimeProps = useMarketRegime('scanner');

  const handleArmScanner = async () => {
    console.log('[ScannerSetup] Starting scan...', {
      mode: scanConfig.sniperMode,
      exchange: scanConfig.exchange,
      leverage: scanConfig.leverage,
      topPairs: scanConfig.topPairs,
      minScore: selectedMode?.min_confluence_score,
      categories: scanConfig.categories
    });
    setIsScanning(true);
    
    // Clear any stale results immediately to prevent showing old mock data
    localStorage.removeItem('scan-results');
    localStorage.removeItem('scan-metadata');
    localStorage.removeItem('scan-rejections');

    try {
      // Add timeout to prevent indefinite waiting (5 minutes for heavy computation with real exchange data)
      const timeoutPromise = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Request timeout')), 300000)
      );
      
      const apiPromise = api.getSignals({
        limit: scanConfig.topPairs || 20,
        min_score: selectedMode?.min_confluence_score || 0,
        sniper_mode: scanConfig.sniperMode,
        majors: scanConfig.categories.majors,
        altcoins: scanConfig.categories.altcoins,
        meme_mode: scanConfig.categories.memeMode,
        exchange: scanConfig.exchange,
        leverage: scanConfig.leverage || 1,
      });

      const response = await Promise.race([apiPromise, timeoutPromise]) as any;

      if (response.error) {
        console.error('[ScannerSetup] API error:', response.error);
        toast({
          title: 'Scanner Failed',
          description: 'Backend unavailable - check if API server is running',
          variant: 'destructive',
        });
        // Preserve rejection summary if backend included one in partial payload
        const maybeRejections = response.data?.rejections || {
          total_rejected: 0,
          by_reason: {},
          details: {},
        };
        localStorage.setItem('scan-results', JSON.stringify([]));
        localStorage.removeItem('scan-metadata');
        localStorage.setItem('scan-rejections', JSON.stringify(maybeRejections));
      } else if (response.data) {
        console.log('[ScannerSetup] Received signals:', response.data.signals.length);
        console.log('[ScannerSetup] Scan metadata:', {
          mode: response.data.mode,
          scanned: response.data.scanned,
          total: response.data.total
        });
        
        // Convert backend signals to frontend ScanResult format
        const results = response.data.signals.map(convertSignalToScanResult);
        
        // CRITICAL: Always clear old results, even if new results are empty
        // This prevents showing stale mock data from previous sessions
        localStorage.setItem('scan-results', JSON.stringify(results));
        
        // Store scan metadata for display
        const metadata = {
          mode: response.data.mode,
          appliedTimeframes: response.data.applied_timeframes,
          effectiveMinScore: response.data.effective_min_score,
          baselineMinScore: response.data.baseline_min_score,
          profile: response.data.profile,
          scanned: response.data.scanned,
        };
        localStorage.setItem('scan-metadata', JSON.stringify(metadata));
        
        // Store rejection stats if available
        if (response.data.rejections) {
          localStorage.setItem('scan-rejections', JSON.stringify(response.data.rejections));
        } else {
          localStorage.removeItem('scan-rejections');
        }
        
        // Save to scan history database
        scanHistoryService.saveScan({
          mode: response.data.mode,
          profile: response.data.profile || 'default',
          timeframes: response.data.applied_timeframes || [],
          symbolsScanned: response.data.scanned || 0,
          signalsGenerated: response.data.signals.length,
          signalsRejected: response.data.rejections?.total_rejected || 0,
          effectiveMinScore: response.data.effective_min_score || 0,
          rejectionBreakdown: response.data.rejections?.by_reason,
          results: results,
        });
        
        console.log('[ScannerSetup] Navigating to results with', results.length, 'setups');
        toast({
          title: 'Targets Acquired',
          description: `${results.length} high-conviction setups identified`,
        });
      }

      setIsScanning(false);
      navigate('/results');
    } catch (error) {
      console.error('Scanner error:', error);
      const isTimeout = error instanceof Error && error.message === 'Request timeout';
      toast({
        title: isTimeout ? 'Scan Timeout' : 'Scanner Error',
        description: isTimeout 
          ? 'Scan exceeded 5 minutes - try reducing symbols or timeframes'
          : 'Failed to complete scan - check backend logs',
        variant: 'destructive',
      });
      // Preserve any existing rejection stats if they were set before failure
      if (!localStorage.getItem('scan-rejections')) {
        localStorage.setItem('scan-rejections', JSON.stringify({
          total_rejected: 0,
          by_reason: {},
          details: {},
        }));
      }
      localStorage.setItem('scan-results', JSON.stringify([]));
      localStorage.removeItem('scan-metadata');
      setIsScanning(false);
      navigate('/results');
    }
  };

  return (
    <div className="min-h-screen w-full p-3 md:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6 md:mb-8">
          <HomeButton />
          <Button 
            variant="outline" 
            onClick={() => navigate('/scanner/status')} 
            className="hover:border-accent/50 transition-all h-10 px-4"
          >
            <ChartBar size={18} className="mr-2" />
            View Status
          </Button>
        </div>

        <div className="space-y-6">
          <TacticalSection
            title="MARKET CONTEXT"
            subtitle="Real-time regime analysis and conditions"
            variant="accent"
            badge={<Badge variant="outline" className="bg-accent/10 text-accent border-accent/40 text-xs">LIVE</Badge>}
          >
            <MarketRegimeLens {...marketRegimeProps} />
          </TacticalSection>

          <div className="grid lg:grid-cols-2 gap-6">
            <TacticalSection
              title="BASIC CONFIGURATION"
              subtitle="Exchange, pairs, and leverage settings"
              variant="default"
              badge={<GearSix size={16} className="text-primary" />}
            >
              <div className="space-y-5">
                <div className="space-y-2.5">
                  <Label htmlFor="exchange" className="text-xs font-bold uppercase tracking-widest text-foreground/80 flex items-center gap-2">
                    Exchange
                  </Label>
                  <Select
                    value={scanConfig.exchange}
                    onValueChange={(value) =>
                      setScanConfig({ ...scanConfig, exchange: value })
                    }
                  >
                    <SelectTrigger id="exchange" className="bg-background/60 h-11 border-border/60 hover:border-primary/50 transition-colors">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="phemex">⚡ Phemex (Fast, No Geo-Block)</SelectItem>
                      <SelectItem value="bybit">🔥 Bybit (May Be Geo-Blocked)</SelectItem>
                      <SelectItem value="okx">🏛️ OKX (May Be Geo-Blocked)</SelectItem>
                      <SelectItem value="bitget">🤖 Bitget</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2.5">
                  <Label htmlFor="top-pairs" className="text-xs font-bold uppercase tracking-widest text-foreground/80 flex items-center gap-2">
                    Top Pairs by Volume
                    <Badge variant="outline" className="text-[10px] font-normal px-1.5 py-0">10</Badge>
                  </Label>
                  <Input
                    id="top-pairs"
                    type="number"
                    min="1"
                    max="100"
                    value={scanConfig.topPairs ?? 20}
                    onChange={(e) =>
                      setScanConfig({ ...scanConfig, topPairs: parseInt(e.target.value) || 20 })
                    }
                    className="bg-background/60 h-11 border-border/60 hover:border-primary/50 focus:border-primary transition-colors"
                  />
                </div>

                <div className="space-y-2.5">
                  <Label htmlFor="leverage" className="text-xs font-bold uppercase tracking-widest text-foreground/80 flex items-center gap-2">
                    Leverage
                    <Badge variant="outline" className="text-[10px] font-normal text-warning border-warning/40 px-1.5 py-0">Risk Multiple</Badge>
                  </Label>
                  <Select
                    value={(scanConfig.leverage ?? 1).toString()}
                    onValueChange={(value) =>
                      setScanConfig({ ...scanConfig, leverage: parseInt(value) })
                    }
                  >
                    <SelectTrigger id="leverage" className="bg-background/60 h-11 border-border/60 hover:border-primary/50 transition-colors">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">1x (No Leverage)</SelectItem>
                      <SelectItem value="2">2x</SelectItem>
                      <SelectItem value="3">3x</SelectItem>
                      <SelectItem value="5">5x</SelectItem>
                      <SelectItem value="10">10x</SelectItem>
                      <SelectItem value="20">20x</SelectItem>
                      <SelectItem value="50">50x</SelectItem>
                      <SelectItem value="100">100x</SelectItem>
                      <SelectItem value="125">125x</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </TacticalSection>

            <TacticalSection
              title="ASSET CATEGORIES"
              subtitle="Select market segments to scan"
              variant="default"
              badge={<Target size={16} className="text-success" />}
            >
              <div className="space-y-3">
                <div 
                  className="group relative flex items-center justify-between p-3.5 bg-background/40 rounded border border-border/60 hover:border-accent/50 hover:bg-background/60 transition-all cursor-pointer"
                  onClick={() => setScanConfig({
                    ...scanConfig,
                    categories: { ...scanConfig.categories, majors: !scanConfig.categories.majors },
                  })}
                >
                  <div className="flex items-center gap-3">
                    <div className="flex flex-col gap-1.5">
                      <Label className="cursor-pointer text-xs font-bold uppercase tracking-widest text-foreground/90">Majors</Label>
                      <div className="flex items-center gap-1.5">
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 bg-accent/10 text-accent border-accent/40">ETH</Badge>
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
                  className="group relative flex items-center justify-between p-3.5 bg-background/40 rounded border border-border/60 hover:border-primary/50 hover:bg-background/60 transition-all cursor-pointer"
                  onClick={() => setScanConfig({
                    ...scanConfig,
                    categories: { ...scanConfig.categories, altcoins: !scanConfig.categories.altcoins },
                  })}
                >
                  <div className="flex items-center gap-3">
                    <div className="flex flex-col gap-1.5">
                      <Label className="cursor-pointer text-xs font-bold uppercase tracking-widest text-foreground/90">Altcoins</Label>
                      <div className="flex items-center gap-1.5">
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 bg-primary/10 text-primary border-primary/40">SOL</Badge>
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 bg-primary/10 text-primary border-primary/40">MATIC</Badge>
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 bg-primary/10 text-primary border-primary/40">LINK</Badge>
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
                  className="group relative flex items-center justify-between p-3.5 bg-background/40 rounded border border-destructive/40 hover:border-destructive/70 hover:bg-background/60 transition-all cursor-pointer"
                  onClick={() => setScanConfig({
                    ...scanConfig,
                    categories: { ...scanConfig.categories, memeMode: !scanConfig.categories.memeMode },
                  })}
                >
                  <div className="flex items-center gap-3">
                    <div className="flex flex-col gap-1.5">
                      <Label className="cursor-pointer text-xs font-bold uppercase tracking-widest text-foreground/90">Memes</Label>
                      <div className="flex items-center gap-1.5">
                        <Badge variant="outline" className="text-[10px] bg-destructive/20 text-destructive border-destructive/50 px-1.5 py-0">▼ HIGH VOLATILITY</Badge>
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
            </TacticalSection>
          </div>

          <TacticalSection
            title="SNIPER MODE"
            subtitle="Select precision level and confidence thresholds"
            variant="default"
            badge={<Crosshair size={16} className="text-primary" />}
          >
            <SniperModeSelector />
          </TacticalSection>

          <div className="relative group pt-2">
            <div className="absolute inset-0 bg-gradient-to-r from-accent/20 via-primary/30 to-accent/20 rounded-xl blur-xl group-hover:blur-2xl transition-all duration-300 opacity-75" />
            <Button
              onClick={handleArmScanner}
              disabled={isScanning || scanConfig.timeframes.length === 0}
              className="relative w-full h-14 md:h-16 text-base md:text-lg font-bold disabled:opacity-50 bg-primary hover:bg-primary/90 text-primary-foreground shadow-lg hover:shadow-xl transition-all"
              size="lg"
            >
              {isScanning ? (
                <>
                  <Lightning size={24} className="animate-pulse" />
                  <span className="mx-2">SCANNING MARKETS...</span>
                  <Lightning size={24} className="animate-pulse" />
                </>
              ) : (
                <>
                  <Crosshair size={24} weight="bold" />
                  <span className="mx-3">ARM SCANNER</span>
                  <span className="text-2xl">→</span>
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
