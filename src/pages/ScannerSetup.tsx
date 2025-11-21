import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useScanner } from '@/context/ScannerContext';
import type { ScanConfig } from '@/context/ScannerContext';
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
import { generateMockScanResults } from '@/utils/mockData';
import { MarketRegimeLens } from '@/components/market/MarketRegimeLens';
import { useMockMarketRegime } from '@/hooks/use-mock-market-regime';
import { SniperModeSelector } from '@/components/SniperModeSelector';
import { SNIPER_MODES } from '@/types/sniperMode';
import type { SniperMode } from '@/types/sniperMode';

export function ScannerSetup() {
  const navigate = useNavigate();
  const { scanConfig, setScanConfig } = useScanner();
  const [, setScanResults] = useKV<ScanResult[]>('scan-results', []);
  const [isScanning, setIsScanning] = useState(false);

  const marketRegimeProps = useMockMarketRegime('scanner');

  const handleModeSelect = (mode: SniperMode) => {
    setScanConfig({
      ...scanConfig,
      sniperMode: mode,
    });
  };

  const handleCustomTimeframesChange = (timeframes: string[]) => {
    setScanConfig({
      ...scanConfig,
      customTimeframes: timeframes,
    });
  };

  const handleArmScanner = async () => {
    setIsScanning(true);

    setTimeout(() => {
      const results = generateMockScanResults(8);
      setScanResults(results);
      setIsScanning(false);
      navigate('/results');
    }, 2500);
  };

  const getEffectiveTimeframes = () => {
    if (scanConfig.sniperMode === 'custom') {
      return scanConfig.customTimeframes;
    }
    return SNIPER_MODES[scanConfig.sniperMode].timeframes;
  };

  const isValidConfig = () => {
    const effectiveTimeframes = getEffectiveTimeframes();
    return effectiveTimeframes.length > 0;
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <Crosshair size={32} weight="bold" className="text-accent" />
            ACQUIRE TARGETS
          </h1>
          <p className="text-muted-foreground">Configure scanner parameters for market reconnaissance</p>
        </div>

        <div className="space-y-4">
          <div className="space-y-1">
            <h2 className="text-sm font-bold text-muted-foreground tracking-wider">MARKET CONTEXT</h2>
          </div>
          <MarketRegimeLens {...marketRegimeProps} />
        </div>

        <Card className="bg-card/50 border-accent/30">
          <CardHeader>
            <CardTitle>Scanner Configuration</CardTitle>
            <CardDescription>Define search parameters and analysis scope</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="exchange">Exchange</Label>
              <Select
                value={scanConfig.exchange}
                onValueChange={(value) =>
                  setScanConfig({ ...scanConfig, exchange: value })
                }
              >
                <SelectTrigger id="exchange" className="bg-background">
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

            <div className="space-y-2">
              <Label htmlFor="top-pairs">Top Pairs by Volume</Label>
              <Input
                id="top-pairs"
                type="number"
                min="1"
                max="100"
                value={scanConfig.topPairs ?? 20}
                onChange={(e) =>
                  setScanConfig({ ...scanConfig, topPairs: parseInt(e.target.value) || 20 })
                }
                className="bg-background"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="leverage">Leverage</Label>
              <Select
                value={(scanConfig.leverage ?? 1).toString()}
                onValueChange={(value) =>
                  setScanConfig({ ...scanConfig, leverage: parseInt(value) })
                }
              >
                <SelectTrigger id="leverage" className="bg-background">
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

            <div className="space-y-3">
              <Label>Asset Categories</Label>
              <div className="space-y-2">
                <div className="flex items-center justify-between p-3 bg-background rounded border border-border">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="majors" className="cursor-pointer">Majors</Label>
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

                <div className="flex items-center justify-between p-3 bg-background rounded border border-border">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="altcoins" className="cursor-pointer">Altcoins</Label>
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

                <div className="flex items-center justify-between p-3 bg-background rounded border border-border">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="meme" className="cursor-pointer">Meme Mode</Label>
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

            <div className="space-y-3">
              <SniperModeSelector
                selectedMode={scanConfig.sniperMode}
                onModeSelect={handleModeSelect}
                customTimeframes={scanConfig.customTimeframes}
                onCustomTimeframesChange={handleCustomTimeframesChange}
              />
            </div>
          </CardContent>
        </Card>

        <Button
          onClick={handleArmScanner}
          disabled={isScanning || !isValidConfig()}
          className="w-full bg-accent hover:bg-accent/90 text-accent-foreground h-14 text-lg font-bold"
          size="lg"
        >
          {isScanning ? (
            <>
              <Lightning size={24} className="animate-pulse" />
              ACQUIRING TARGETS...
            </>
          ) : (
            <>
              <Crosshair size={24} weight="bold" />
              ARM THE SCANNER
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
