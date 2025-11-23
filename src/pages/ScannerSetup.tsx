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
import { Crosshair, Lightning } from '@phosphor-icons/react';
import { useKV } from '@github/spark/hooks';
import type { ScanResult } from '@/utils/mockData';
import { generateMockScanResults, convertSignalToScanResult } from '@/utils/mockData';
import { MarketRegimeLens } from '@/components/market/MarketRegimeLens';
import { useMockMarketRegime } from '@/hooks/use-mock-market-regime';
import { SniperModeSelector } from '@/components/SniperModeSelector';
import { api } from '@/utils/api';
// selectedMode now sourced from ScannerContext
import { useToast } from '@/hooks/use-toast';
import { PageLayout, PageHeader, PageSection } from '@/components/layout/PageLayout';

export function ScannerSetup() {
  const navigate = useNavigate();
  const { scanConfig, setScanConfig, selectedMode } = useScanner();
  const [, setScanResults] = useKV<ScanResult[]>('scan-results', []);
  const [, setScanMetadata] = useKV<any>('scan-metadata', null);
  const [isScanning, setIsScanning] = useState(false);
  const { toast } = useToast();

  const marketRegimeProps = useMockMarketRegime('scanner');

  const handleArmScanner = async () => {
    console.log('[ScannerSetup] Starting scan...', {
      mode: scanConfig.sniperMode,
      topPairs: scanConfig.topPairs,
      minScore: selectedMode?.min_confluence_score
    });
    setIsScanning(true);

    try {
      // Call the real backend API with selected mode
      const response = await api.getSignals({
        limit: scanConfig.topPairs || 20,
        min_score: selectedMode?.min_confluence_score || 0,
        sniper_mode: scanConfig.sniperMode,
      });

      if (response.error) {
        console.error('[ScannerSetup] API error, falling back to mock data:', response.error);
        toast({
          title: 'Using Mock Data',
          description: 'Backend unavailable, displaying simulated results',
        });
        // Fallback to mock data
        const results = generateMockScanResults(8);
        setScanResults(results);
        setScanMetadata(null);
      } else if (response.data) {
        console.log('[ScannerSetup] Received signals:', response.data.signals.length);
        console.log('[ScannerSetup] Scan metadata:', {
          mode: response.data.mode,
          scanned: response.data.scanned,
          total: response.data.total
        });
        
        // Convert backend signals to frontend ScanResult format
        const results = response.data.signals.map(convertSignalToScanResult);
        setScanResults(results);
        
        // Store scan metadata for display
        setScanMetadata({
          mode: response.data.mode,
          appliedTimeframes: response.data.applied_timeframes,
          effectiveMinScore: response.data.effective_min_score,
          baselineMinScore: response.data.baseline_min_score,
          profile: response.data.profile,
          scanned: response.data.scanned,
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
      toast({
        title: 'Scanner Error',
        description: 'Failed to fetch signals, using mock data',
        variant: 'destructive',
      });
      // Fallback to mock data
      const results = generateMockScanResults(8);
      setScanResults(results);
      setIsScanning(false);
      navigate('/results');
    }
  };

  return (
    <PageLayout maxWidth="lg">
      <div className="space-y-10">
        <PageHeader
          title="Acquire Targets"
          description="Configure scanner parameters for market opportunities"
          icon={<Crosshair size={40} weight="bold" className="text-accent" />}
          actions={
            <Button variant="outline" onClick={() => navigate('/scanner/status')} className="h-12">
              View Status
            </Button>
          }
        />

        <PageSection title="MARKET CONTEXT">
          <MarketRegimeLens {...marketRegimeProps} />
        </PageSection>

        <Card className="bg-card/50 border-accent/30">
          <CardHeader className="pb-6">
            <CardTitle className="text-xl">Scanner Configuration</CardTitle>
            <CardDescription className="text-base mt-2">Define search parameters and analysis scope</CardDescription>
          </CardHeader>
          <CardContent className="space-y-8">
            <div className="space-y-3">
              <Label htmlFor="exchange" className="text-base">Exchange</Label>
              <Select
                value={scanConfig.exchange}
                onValueChange={(value) =>
                  setScanConfig({ ...scanConfig, exchange: value })
                }
              >
                <SelectTrigger id="exchange" className="bg-background h-12">
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
              <Label htmlFor="top-pairs" className="text-base">Top Pairs by Volume</Label>
              <Input
                id="top-pairs"
                type="number"
                min="1"
                max="100"
                value={scanConfig.topPairs ?? 20}
                onChange={(e) =>
                  setScanConfig({ ...scanConfig, topPairs: parseInt(e.target.value) || 20 })
                }
                className="bg-background h-12"
              />
            </div>

            <div className="space-y-3">
              <Label htmlFor="leverage" className="text-base">Leverage</Label>
              <Select
                value={(scanConfig.leverage ?? 1).toString()}
                onValueChange={(value) =>
                  setScanConfig({ ...scanConfig, leverage: parseInt(value) })
                }
              >
                <SelectTrigger id="leverage" className="bg-background h-12">
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

            <div className="space-y-4">
              <Label className="text-base">Asset Categories</Label>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-4 bg-background rounded-lg border border-border">
                  <div className="flex items-center gap-3">
                    <Label htmlFor="majors" className="cursor-pointer text-base">Majors</Label>
                    <Badge variant="outline" className="text-xs">BTC, ETH, BNB</Badge>
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
                  />
                </div>

                <div className="flex items-center justify-between p-4 bg-background rounded-lg border border-border">
                  <div className="flex items-center gap-3">
                    <Label htmlFor="altcoins" className="cursor-pointer text-base">Altcoins</Label>
                    <Badge variant="outline" className="text-xs">SOL, MATIC, LINK</Badge>
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
                  />
                </div>

                <div className="flex items-center justify-between p-4 bg-background rounded-lg border border-border">
                  <div className="flex items-center gap-3">
                    <Label htmlFor="meme" className="cursor-pointer text-base">Meme Mode</Label>
                    <Badge variant="outline" className="text-xs bg-warning/20 text-warning">VOLATILE</Badge>
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
              </div>
            </div>

            <div className="space-y-4">
              <SniperModeSelector />
            </div>
          </CardContent>
        </Card>

        <Button
          onClick={handleArmScanner}
          disabled={isScanning || scanConfig.timeframes.length === 0}
          className="w-full bg-accent hover:bg-accent/90 text-accent-foreground h-12 text-base font-semibold disabled:opacity-50 mt-4"
          size="lg"
        >
          {isScanning ? (
            <>
              <Lightning size={20} className="animate-pulse" />
              Scanning...
            </>
          ) : (
            <>
              <Crosshair size={20} weight="bold" />
              Start Scan
            </>
          )}
        </Button>
      </div>
    </PageLayout>
  );
}

export default ScannerSetup;
