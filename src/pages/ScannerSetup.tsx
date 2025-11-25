import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useScanner } from '@/context/ScannerContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Crosshair, Lightning } from '@phosphor-icons/react';
import type { ScanResult } from '@/utils/mockData';
import { generateMockScanResults, convertSignalToScanResult } from '@/utils/mockData';
import { MarketRegimeLens } from '@/components/market/MarketRegimeLens';
import { useMockMarketRegime } from '@/hooks/use-mock-market-regime';
import { SniperModeSelector } from '@/components/SniperModeSelector';
import { api } from '@/utils/api';
import { useToast } from '@/hooks/use-toast';
import { MetalSection, MetalCard } from '@/components/MetalCard';
import { HomeButton } from '@/components/layout/HomeButton';

export function ScannerSetup() {
  const navigate = useNavigate();
  const { scanConfig, setScanConfig, selectedMode } = useScanner();
  const [isScanning, setIsScanning] = useState(false);
  const { toast } = useToast();

  const marketRegimeProps = useMockMarketRegime('scanner');

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

    try {
      // Add timeout to prevent indefinite waiting (2 minutes for heavy computation)
      const timeoutPromise = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Request timeout')), 120000)
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
        console.error('[ScannerSetup] API error, falling back to mock data:', response.error);
        toast({
          title: 'Using Mock Data',
          description: 'Backend unavailable, displaying simulated results',
        });
        // Fallback to mock data
        const results = generateMockScanResults(8);
        localStorage.setItem('scan-results', JSON.stringify(results));
        localStorage.removeItem('scan-metadata');
      } else if (response.data) {
        console.log('[ScannerSetup] Received signals:', response.data.signals.length);
        console.log('[ScannerSetup] Scan metadata:', {
          mode: response.data.mode,
          scanned: response.data.scanned,
          total: response.data.total
        });
        
        // Convert backend signals to frontend ScanResult format
        const results = response.data.signals.map(convertSignalToScanResult);
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
      toast({
        title: 'Scanner Error',
        description: 'Failed to fetch signals, using mock data',
        variant: 'destructive',
      });
      // Fallback to mock data
      const results = generateMockScanResults(8);
      localStorage.setItem('scan-results', JSON.stringify(results));
      localStorage.removeItem('scan-metadata');
      setIsScanning(false);
      navigate('/results');
    }
  };

  return (
    <div className="min-h-screen w-full p-4 md:p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <div className="flex items-center justify-between mb-8">
          <HomeButton />
          <Button variant="outline" onClick={() => navigate('/scanner/status')} className="hover:border-accent/50 transition-all">
            View Status
          </Button>
        </div>

        <MetalSection title="MARKET CONTEXT" glowColor="accent" titleColor="text-accent">
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground uppercase tracking-wide">Real-time regime analysis and conditions</p>
            <MarketRegimeLens {...marketRegimeProps} />
          </div>
        </MetalSection>

        <MetalSection title="BASIC CONFIGURATION" glowColor="primary" titleColor="text-primary">
          <div className="space-y-6">
            <p className="text-sm text-muted-foreground uppercase tracking-wide">Exchange, pairs, and leverage settings</p>
            
            <div className="grid md:grid-cols-2 gap-6">
              <div className="space-y-3">
                <Label htmlFor="exchange" className="text-sm font-semibold uppercase tracking-wide">
                  Exchange
                </Label>
                <Select
                  value={scanConfig.exchange}
                  onValueChange={(value) =>
                    setScanConfig({ ...scanConfig, exchange: value })
                  }
                >
                  <SelectTrigger id="exchange" className="bg-background/60 h-12 border-border hover:border-primary/50 transition-colors">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Binance">Binance</SelectItem>
                    <SelectItem value="Coinbase">Coinbase</SelectItem>
                    <SelectItem value="Kraken">Kraken</SelectItem>
                    <SelectItem value="Bybit">Bybit</SelectItem>
                    <SelectItem value="Phemex">Phemex</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-3">
                <Label htmlFor="top-pairs" className="text-sm font-semibold uppercase tracking-wide flex items-center gap-2">
                  Top Pairs by Volume
                  <Badge variant="outline" className="text-xs font-normal">10</Badge>
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
                  className="bg-background/60 h-12 border-border hover:border-primary/50 focus:border-primary transition-colors"
                />
              </div>
            </div>

            <div className="space-y-3">
              <Label htmlFor="leverage" className="text-sm font-semibold uppercase tracking-wide flex items-center gap-2">
                Leverage
                <Badge variant="outline" className="text-xs font-normal text-warning">Risk Multiple</Badge>
              </Label>
              <Select
                value={(scanConfig.leverage ?? 1).toString()}
                onValueChange={(value) =>
                  setScanConfig({ ...scanConfig, leverage: parseInt(value) })
                }
              >
                <SelectTrigger id="leverage" className="bg-background/60 h-12 border-border hover:border-primary/50 transition-colors">
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
        </MetalSection>

        <MetalSection title="ASSET CATEGORIES" glowColor="success" titleColor="text-success">
          <div className="space-y-6">
            <p className="text-sm text-muted-foreground uppercase tracking-wide">Select market segments to scan</p>
            
            <div className="space-y-4">
              <div 
                className="flex items-center justify-between p-4 bg-background/40 rounded-lg border border-border hover:border-accent/50 transition-all cursor-pointer"
                onClick={() => setScanConfig({
                  ...scanConfig,
                  categories: { ...scanConfig.categories, majors: !scanConfig.categories.majors },
                })}
              >
                <div className="flex items-center gap-3">
                  <div className="flex flex-col">
                    <Label className="cursor-pointer text-sm font-semibold uppercase tracking-wide">Majors</Label>
                    <div className="flex items-center gap-1.5 mt-1">
                      <Badge variant="outline" className="text-xs px-1.5 py-0">ETH</Badge>
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
                className="flex items-center justify-between p-4 bg-background/40 rounded-lg border border-border hover:border-primary/50 transition-all cursor-pointer"
                onClick={() => setScanConfig({
                  ...scanConfig,
                  categories: { ...scanConfig.categories, altcoins: !scanConfig.categories.altcoins },
                })}
              >
                <div className="flex items-center gap-3">
                  <div className="flex flex-col">
                    <Label className="cursor-pointer text-sm font-semibold uppercase tracking-wide">Altcoins</Label>
                    <div className="flex items-center gap-1.5 mt-1">
                      <Badge variant="outline" className="text-xs px-1.5 py-0">SOL</Badge>
                      <Badge variant="outline" className="text-xs px-1.5 py-0">MATIC</Badge>
                      <Badge variant="outline" className="text-xs px-1.5 py-0">LINK</Badge>
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
                className="flex items-center justify-between p-4 bg-background/40 rounded-lg border border-destructive/40 hover:border-destructive/70 transition-all cursor-pointer"
                onClick={() => setScanConfig({
                  ...scanConfig,
                  categories: { ...scanConfig.categories, memeMode: !scanConfig.categories.memeMode },
                })}
              >
                <div className="flex items-center gap-3">
                  <div className="flex flex-col">
                    <Label className="cursor-pointer text-sm font-semibold uppercase tracking-wide">Memes</Label>
                    <div className="flex items-center gap-1.5 mt-1">
                      <Badge variant="outline" className="text-xs bg-destructive/20 text-destructive border-destructive/50">▼ HIGH VOLATILITY</Badge>
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
        </MetalSection>

        <MetalSection title="SNIPER MODE" glowColor="primary" titleColor="text-primary">
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground uppercase tracking-wide">Select precision level and confidence thresholds</p>
            <SniperModeSelector />
          </div>
        </MetalSection>

        <div className="relative group pt-4">
          <div className="absolute inset-0 bg-gradient-to-r from-accent/30 via-primary/30 to-accent/30 rounded-xl blur-xl group-hover:blur-2xl transition-all duration-300" />
          <Button
            onClick={handleArmScanner}
            disabled={isScanning || scanConfig.timeframes.length === 0}
            className="relative w-full h-16 text-lg font-bold disabled:opacity-50 btn-tactical-scanner"
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
  );
}
