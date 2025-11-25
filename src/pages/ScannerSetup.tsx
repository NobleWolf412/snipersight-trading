import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useScanner } from '@/context/ScannerContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Crosshair, Lightning, CaretDown, CaretUp } from '@phosphor-icons/react';
import type { ScanResult } from '@/utils/mockData';
import { generateMockScanResults, convertSignalToScanResult } from '@/utils/mockData';
import { MarketRegimeLens } from '@/components/market/MarketRegimeLens';
import { useMockMarketRegime } from '@/hooks/use-mock-market-regime';
import { SniperModeSelector } from '@/components/SniperModeSelector';
import { api } from '@/utils/api';
import { useToast } from '@/hooks/use-toast';
import { PageLayout, PageHeader, PageSection } from '@/components/layout/PageLayout';
import { HomeButton } from '@/components/layout/HomeButton';

export function ScannerSetup() {
  const navigate = useNavigate();
  const { scanConfig, setScanConfig, selectedMode } = useScanner();
  const [isScanning, setIsScanning] = useState(false);
  const [showMarketContext, setShowMarketContext] = useState(true);
  const [showBasicConfig, setShowBasicConfig] = useState(true);
  const [showCategories, setShowCategories] = useState(true);
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
    <PageLayout maxWidth="lg">
      <div className="space-y-12">
        <div className="flex justify-start">
          <HomeButton />
        </div>
        <PageHeader
          title="Acquire Targets"
          description="Configure scanner parameters for market opportunities"
          icon={<Crosshair size={40} weight="bold" className="text-accent" />}
          actions={
            <Button variant="outline" onClick={() => navigate('/scanner/status')} className="h-12 hover:border-accent/50 transition-all">
              View Status
            </Button>
          }
        />

        <div className="flex flex-col space-y-8">
          <div className="rounded-xl border border-slate-700/60 bg-black/40 backdrop-blur-sm p-4 md:p-6">
            <Card className="bg-card/50 border-accent/30 card-3d overflow-hidden">
              <CardHeader 
                className="pb-6 cursor-pointer select-none hover:bg-accent/5 transition-colors"
                onClick={() => setShowMarketContext(!showMarketContext)}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-xl heading-hud flex items-center gap-3">
                      <div className="w-2 h-2 bg-accent rounded-full animate-pulse" />
                      MARKET CONTEXT
                    </CardTitle>
                    <CardDescription className="text-sm mt-2">Real-time regime analysis and conditions</CardDescription>
                  </div>
                  {showMarketContext ? 
                    <CaretUp size={24} weight="bold" className="text-accent" /> : 
                    <CaretDown size={24} weight="bold" className="text-muted-foreground" />
                  }
                </div>
              </CardHeader>
              {showMarketContext && (
                <CardContent className="pt-0 animate-in fade-in slide-in-from-top-2 duration-300">
                  <MarketRegimeLens {...marketRegimeProps} />
                </CardContent>
              )}
            </Card>
          </div>

          <div className="rounded-xl border border-slate-700/60 bg-black/40 backdrop-blur-sm p-4 md:p-6">
            <Card className="bg-card/50 border-accent/30 card-3d overflow-hidden">
              <CardHeader 
                className="pb-6 cursor-pointer select-none hover:bg-accent/5 transition-colors"
                onClick={() => setShowBasicConfig(!showBasicConfig)}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-xl heading-hud flex items-center gap-3">
                      <div className="w-2 h-2 bg-primary rounded-full scan-pulse" />
                      BASIC CONFIGURATION
                    </CardTitle>
                    <CardDescription className="text-sm mt-2">Exchange, pairs, and leverage settings</CardDescription>
                  </div>
                  {showBasicConfig ? 
                    <CaretUp size={24} weight="bold" className="text-primary" /> : 
                    <CaretDown size={24} weight="bold" className="text-muted-foreground" />
                  }
                </div>
              </CardHeader>
              {showBasicConfig && (
                <CardContent className="space-y-8 animate-in fade-in slide-in-from-top-2 duration-300">
                  <div className="grid md:grid-cols-2 gap-6">
                    <div className="space-y-3">
                      <Label htmlFor="exchange" className="text-base font-semibold flex items-center gap-2">
                        Exchange
                        <Badge variant="outline" className="text-xs font-normal">Required</Badge>
                      </Label>
                      <Select
                        value={scanConfig.exchange}
                        onValueChange={(value) =>
                          setScanConfig({ ...scanConfig, exchange: value })
                        }
                      >
                        <SelectTrigger id="exchange" className="bg-background h-12 border-border/60 hover:border-accent/50 transition-colors">
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
                      <Label htmlFor="top-pairs" className="text-base font-semibold flex items-center gap-2">
                        Top Pairs by Volume
                        <Badge variant="outline" className="text-xs font-normal">1-100</Badge>
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
                        className="bg-background h-12 border-border/60 hover:border-accent/50 focus:border-accent transition-colors w-24"
                      />
                    </div>
                  </div>

                  <div className="space-y-3">
                    <Label htmlFor="leverage" className="text-base font-semibold flex items-center gap-2">
                      Leverage
                      <Badge variant="outline" className="text-xs font-normal bg-warning/10 text-warning border-warning/40">Risk Multiplier</Badge>
                    </Label>
                    <Select
                      value={(scanConfig.leverage ?? 1).toString()}
                      onValueChange={(value) =>
                        setScanConfig({ ...scanConfig, leverage: parseInt(value) })
                      }
                    >
                      <SelectTrigger id="leverage" className="bg-background h-12 border-border/60 hover:border-accent/50 transition-colors">
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
                </CardContent>
              )}
            </Card>
          </div>

          <div className="rounded-xl border border-slate-700/60 bg-black/40 backdrop-blur-sm p-4 md:p-6">
            <Card className="bg-card/50 border-accent/30 card-3d overflow-hidden">
              <CardHeader 
                className="pb-6 cursor-pointer select-none hover:bg-accent/5 transition-colors"
                onClick={() => setShowCategories(!showCategories)}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-xl heading-hud flex items-center gap-3">
                      <div className="w-2 h-2 bg-success rounded-full scan-pulse-fast" />
                      ASSET CATEGORIES
                    </CardTitle>
                    <CardDescription className="text-sm mt-2">Select market segments to scan</CardDescription>
                  </div>
                  {showCategories ? 
                    <CaretUp size={24} weight="bold" className="text-success" /> : 
                    <CaretDown size={24} weight="bold" className="text-muted-foreground" />
                  }
                </div>
              </CardHeader>
              {showCategories && (
                <CardContent className="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
                  <div className="grid gap-6">
                    <div 
                      className="flex items-center justify-between p-4 bg-background/60 rounded-xl border-2 border-border/60 hover:border-accent/50 hover:bg-background/80 transition-all card-3d cursor-pointer text-base"
                      onClick={() => setScanConfig({
                        ...scanConfig,
                        categories: { ...scanConfig.categories, majors: !scanConfig.categories.majors },
                      })}
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center flex-shrink-0">
                          <div className="w-4 h-4 rounded border-2 border-accent" />
                        </div>
                        <div>
                          <Label className="cursor-pointer text-sm font-semibold block">Majors</Label>
                          <div className="flex items-center gap-1.5 mt-0.5">
                            <Badge variant="outline" className="text-xs px-1.5 py-0">BTC</Badge>
                            <Badge variant="outline" className="text-xs px-1.5 py-0">ETH</Badge>
                            <Badge variant="outline" className="text-xs px-1.5 py-0">BNB</Badge>
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
                        className="scale-110 data-[state=checked]:bg-accent"
                      />
                    </div>

                    <div 
                      className="flex items-center justify-between p-6 bg-background/60 rounded-xl border-2 border-border/60 hover:border-primary/50 hover:bg-background/80 transition-all card-3d cursor-pointer"
                      onClick={() => setScanConfig({
                        ...scanConfig,
                        categories: { ...scanConfig.categories, altcoins: !scanConfig.categories.altcoins },
                      })}
                    >
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                          <div className="w-5 h-5 rounded border-2 border-primary" />
                        </div>
                        <div>
                          <Label className="cursor-pointer text-base font-semibold block mb-1">Altcoins</Label>
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-xs">SOL</Badge>
                            <Badge variant="outline" className="text-xs">MATIC</Badge>
                            <Badge variant="outline" className="text-xs">LINK</Badge>
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
                        className="scale-125 data-[state=checked]:bg-primary"
                      />
                    </div>

                    <div 
                      className="relative flex items-center justify-between p-6 bg-background/60 rounded-xl border-2 border-destructive/30 hover:border-destructive/60 hover:bg-background/80 transition-all card-3d cursor-pointer overflow-hidden"
                      onClick={() => setScanConfig({
                        ...scanConfig,
                        categories: { ...scanConfig.categories, memeMode: !scanConfig.categories.memeMode },
                      })}
                    >
                      <div className="absolute -inset-1 bg-destructive/20 rounded-xl blur-md hud-glow-red" />
                      <div className="flex items-center gap-4 relative z-10">
                        <div className="w-10 h-10 rounded-lg bg-destructive/10 flex items-center justify-center flex-shrink-0 shadow-lg shadow-destructive/20">
                          <Lightning size={20} weight="bold" className="text-destructive animate-pulse" />
                        </div>
                        <div>
                          <Label className="cursor-pointer text-base font-semibold block mb-1">Memes</Label>
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-xs bg-destructive/20 text-destructive border-destructive/50">HIGH VOLATILITY</Badge>
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
                        className="scale-125 data-[state=checked]:bg-destructive relative z-10"
                      />
                    </div>
                  </div>
                </CardContent>
              )}
            </Card>
          </div>

          <div className="rounded-xl border border-slate-700/60 bg-black/40 backdrop-blur-sm p-4 md:p-6">
            <Card className="bg-card/50 border-primary/30 card-3d">
              <CardHeader className="pb-6">
                <CardTitle className="text-xl heading-hud flex items-center gap-3">
                  <Crosshair size={24} weight="bold" className="text-primary" />
                  SNIPER MODE
                </CardTitle>
                <CardDescription className="text-sm mt-2">Select precision level and confidence thresholds</CardDescription>
              </CardHeader>
              <CardContent>
                <SniperModeSelector />
              </CardContent>
            </Card>
          </div>
        </div>

        <div className="relative group">
          <div className="absolute inset-0 bg-gradient-to-r from-accent/20 via-primary/20 to-accent/20 rounded-xl blur-xl group-hover:blur-2xl transition-all duration-300" />
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
    </PageLayout>
  );
}
