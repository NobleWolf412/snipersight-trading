import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useScanner } from '@/context/ScannerContext';
import { useWallet } from '@/context/WalletContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Robot, Shield, Lightning, Wallet } from '@phosphor-icons/react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { WalletGate } from '@/components/WalletGate';
import { MarketRegimeLens } from '@/components/market/MarketRegimeLens';
import { useMockMarketRegime } from '@/hooks/use-mock-market-regime';
import { SniperModeSelector } from '@/components/SniperModeSelector';
import { SNIPER_MODES } from '@/types/sniperMode';
import type { SniperMode } from '@/types/sniperMode';
import { PageLayout, PageHeader, PageSection } from '@/components/layout/PageLayout';

export function BotSetup() {
  const navigate = useNavigate();
  const { botConfig, setBotConfig } = useScanner();
  const { wallet, isConnected: isWalletConnected } = useWallet();
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [isConnected, setIsConnected] = useState(false);

  const marketRegimeProps = useMockMarketRegime('bot');

  const handleModeSelect = (mode: SniperMode) => {
    setBotConfig({
      ...botConfig,
      sniperMode: mode,
    });
  };

  const handleCustomTimeframesChange = (timeframes: string[]) => {
    setBotConfig({
      ...botConfig,
      customTimeframes: timeframes,
    });
  };

  const handleConnectExchange = () => {
    setTimeout(() => {
      setIsConnected(true);
      setShowConnectModal(false);
    }, 1500);
  };

  const handleDeployBot = () => {
    navigate('/bot/status');
  };

  const getEffectiveTimeframes = () => {
    if (botConfig.sniperMode === 'custom') {
      return botConfig.customTimeframes || [];
    }
    const mode = SNIPER_MODES[botConfig.sniperMode];
    return mode?.timeframes || [];
  };

  const isValidConfig = () => {
    const effectiveTimeframes = getEffectiveTimeframes();
    return effectiveTimeframes.length > 0 && (botConfig.modes.swing || botConfig.modes.scalp);
  };

  return (
    <PageLayout maxWidth="lg">
      <div className="space-y-10">
        <PageHeader
          title="Deploy Trading Bot"
          description="Configure automated trading parameters and limits"
          icon={<Robot size={40} weight="bold" className="text-warning" />}
        />

        <PageSection title="MARKET CONTEXT">
          <MarketRegimeLens {...marketRegimeProps} />
        </PageSection>

        <WalletGate message="Connect your wallet to authenticate before deploying trading bots">
          <Alert className="border-accent/50 bg-accent/10 p-6">
            <Wallet size={24} className="text-accent" />
            <AlertTitle className="text-accent text-base mb-2">Wallet Authenticated</AlertTitle>
            <AlertDescription className="text-sm">
              Authenticated as {wallet?.address.slice(0, 6)}...{wallet?.address.slice(-4)} · 
              Your wallet signature confirms your identity for secure trading operations.
            </AlertDescription>
          </Alert>

          <Alert className="border-warning/50 bg-warning/10 p-6">
            <Shield size={24} className="text-warning" />
            <AlertTitle className="text-warning text-base mb-2">Security Notice</AlertTitle>
            <AlertDescription className="text-sm">
              API keys are stored securely on the backend. Your credentials are never exposed to the client.
            </AlertDescription>
          </Alert>

          <Card className="bg-card/50 border-warning/30">
            <CardHeader className="pb-6">
              <CardTitle className="text-xl">Exchange Connection</CardTitle>
              <CardDescription className="text-base mt-2">Secure API authentication</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-3">
                <Label htmlFor="exchange" className="text-base">Exchange</Label>
                <Select
                  value={botConfig.exchange}
                  onValueChange={(value) =>
                    setBotConfig({ ...botConfig, exchange: value })
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

              {!isConnected ? (
                <Button
                  onClick={() => setShowConnectModal(true)}
                  className="w-full bg-warning hover:bg-warning/90 text-warning-foreground h-12 text-base"
                  size="lg"
                >
                  <Shield size={20} />
                  Connect Exchange
                </Button>
              ) : (
                <div className="flex items-center justify-between p-5 bg-success/10 border border-success/50 rounded-lg">
                  <div className="flex items-center gap-4">
                    <div className="w-3 h-3 bg-success rounded-full scan-pulse" />
                    <div>
                      <div className="font-bold text-success text-base">CONNECTED</div>
                      <div className="text-sm text-muted-foreground mt-1">{botConfig.exchange} · Secure Backend Storage</div>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setIsConnected(false)}
                    className="border-destructive text-destructive hover:bg-destructive/10 h-10"
                  >
                    DISCONNECT
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {isConnected && (
            <Card className="bg-card/50 border-warning/30">
              <CardHeader className="pb-6">
                <CardTitle className="text-xl">Bot Configuration</CardTitle>
                <CardDescription className="text-base mt-2">Trading parameters and limits</CardDescription>
              </CardHeader>
              <CardContent className="space-y-8">
                <div className="space-y-3">
                  <Label htmlFor="pair" className="text-base">Trading Pair</Label>
                  <Select
                    value={botConfig.pair}
                    onValueChange={(value) =>
                      setBotConfig({ ...botConfig, pair: value })
                    }
                  >
                    <SelectTrigger id="pair" className="bg-background h-12">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="BTC/USDT">BTC/USDT</SelectItem>
                      <SelectItem value="ETH/USDT">ETH/USDT</SelectItem>
                      <SelectItem value="SOL/USDT">SOL/USDT</SelectItem>
                      <SelectItem value="MATIC/USDT">MATIC/USDT</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-4">
                  <Label className="text-base">Trading Modes</Label>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-4 bg-background rounded-lg border border-border">
                      <Label htmlFor="swing" className="cursor-pointer text-base">Swing Trading</Label>
                      <Switch
                        id="swing"
                        checked={botConfig.modes.swing}
                        onCheckedChange={(checked) =>
                          setBotConfig({
                            ...botConfig,
                            modes: { ...botConfig.modes, swing: checked },
                          })
                        }
                      />
                    </div>
                    <div className="flex items-center justify-between p-4 bg-background rounded-lg border border-border">
                      <Label htmlFor="scalp" className="cursor-pointer text-base">Scalp Trading</Label>
                      <Switch
                        id="scalp"
                        checked={botConfig.modes.scalp}
                        onCheckedChange={(checked) =>
                          setBotConfig({
                            ...botConfig,
                            modes: { ...botConfig.modes, scalp: checked },
                          })
                        }
                      />
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <SniperModeSelector
                    selectedMode={botConfig.sniperMode}
                    onModeSelect={handleModeSelect}
                    customTimeframes={botConfig.customTimeframes}
                    onCustomTimeframesChange={handleCustomTimeframesChange}
                  />
                </div>

                <div className="space-y-3">
                  <Label htmlFor="max-trades" className="text-base">Max Trades Per Run</Label>
                  <Input
                    id="max-trades"
                    type="number"
                    min="1"
                    max="10"
                    value={botConfig.maxTrades}
                    onChange={(e) =>
                      setBotConfig({
                        ...botConfig,
                        maxTrades: parseInt(e.target.value) || 1,
                      })
                    }
                    className="bg-background h-12"
                  />
                </div>

                <div className="space-y-3">
                  <Label htmlFor="duration" className="text-base">Mission Duration (Hours)</Label>
                  <Input
                    id="duration"
                    type="number"
                    min="1"
                    max="168"
                    value={botConfig.duration}
                    onChange={(e) =>
                      setBotConfig({
                        ...botConfig,
                        duration: parseInt(e.target.value) || 1,
                      })
                    }
                    className="bg-background h-12"
                  />
                </div>
              </CardContent>
            </Card>
          )}

          {isConnected && (
            <Button
              onClick={handleDeployBot}
              disabled={!isValidConfig()}
              className="w-full bg-warning hover:bg-warning/90 text-warning-foreground h-12 text-base font-semibold mt-4"
              size="lg"
            >
              <Lightning size={20} weight="bold" />
              Deploy Bot
            </Button>
          )}
        </WalletGate>
      </div>

      <Dialog open={showConnectModal} onOpenChange={setShowConnectModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Connect Exchange</DialogTitle>
            <DialogDescription>Secure backend authentication</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <Alert className="border-accent/50 bg-accent/10">
              <Shield size={20} className="text-accent" />
              <AlertTitle>Secure Storage</AlertTitle>
              <AlertDescription>
                Your API keys will be encrypted and stored on our secure backend. They are never transmitted to or stored in the browser.
              </AlertDescription>
            </Alert>

            <div className="p-4 bg-muted/30 rounded border border-border text-center space-y-2">
              <p className="text-sm text-muted-foreground">
                In production, this would initiate a secure OAuth flow or backend key management process.
              </p>
              <p className="text-xs text-muted-foreground">
                Simulating connection for demonstration...
              </p>
            </div>

            <Button
              onClick={handleConnectExchange}
              className="w-full bg-success hover:bg-success/90 text-success-foreground"
            >
              SIMULATE CONNECTION
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </PageLayout>
  );
}
