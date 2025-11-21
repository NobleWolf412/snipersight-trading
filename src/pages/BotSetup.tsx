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
import { Robot, Shield, Lightning } from '@phosphor-icons/react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { MarketRegimeLens } from '@/components/market/MarketRegimeLens';
import { useMockMarketRegime } from '@/hooks/use-mock-market-regime';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { SniperModeSelector } from '@/components/SniperModeSelector';
import { SNIPER_MODES } from '@/types/sniperMode';
import type { SniperMode } from '@/types/sniperMode';

export function BotSetup() {
  const navigate = useNavigate();
  const { botConfig, setBotConfig } = useScanner();
  const { isConnected: isWalletConnected } = useWallet();
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
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <Robot size={32} weight="bold" className="text-warning" />
            DEPLOY AUTONOMOUS SNIPER
          </h1>
          <p className="text-muted-foreground">Configure automated trading parameters</p>
        </div>

        <div className="space-y-4">
          <div className="space-y-1">
            <h2 className="text-sm font-bold text-muted-foreground tracking-wider">MARKET CONTEXT</h2>
          </div>
          <MarketRegimeLens {...marketRegimeProps} />
        </div>

        <Alert className="border-warning/50 bg-warning/10">
          <Shield size={20} className="text-warning" />
          <AlertTitle className="text-warning">Security Notice</AlertTitle>
          <AlertDescription>
            API keys are stored securely on the backend. Your credentials are never exposed to the client.
          </AlertDescription>
        </Alert>

        <Card className="bg-card/50 border-warning/30">
          <CardHeader>
            <CardTitle>Exchange Connection</CardTitle>
            <CardDescription>Secure API authentication</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="exchange">Exchange</Label>
              <Select
                value={botConfig.exchange}
                onValueChange={(value) =>
                  setBotConfig({ ...botConfig, exchange: value })
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

            {!isConnected ? (
              <Button
                onClick={() => setShowConnectModal(true)}
                className="w-full bg-warning hover:bg-warning/90 text-warning-foreground"
                size="lg"
              >
                <Shield size={20} />
                CONNECT EXCHANGE
              </Button>
            ) : (
              <div className="flex items-center justify-between p-4 bg-success/10 border border-success/50 rounded">
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 bg-success rounded-full scan-pulse" />
                  <div>
                    <div className="font-bold text-success">CONNECTED</div>
                    <div className="text-xs text-muted-foreground">{botConfig.exchange} · Secure Backend Storage</div>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsConnected(false)}
                  className="border-destructive text-destructive hover:bg-destructive/10"
                >
                  DISCONNECT
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {isConnected && (
          <TooltipProvider>
            <Tooltip open={!isWalletConnected ? undefined : false}>
              <TooltipTrigger asChild>
                <div>
                  <Card className={`bg-card/50 border-warning/30 ${!isWalletConnected ? 'opacity-40 pointer-events-none' : ''}`}>
                    <CardHeader>
                      <CardTitle>Bot Configuration</CardTitle>
                      <CardDescription>Trading parameters and limits</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      <div className="space-y-2">
                        <Label htmlFor="pair">Trading Pair</Label>
                        <Select
                          value={botConfig.pair}
                          onValueChange={(value) =>
                            setBotConfig({ ...botConfig, pair: value })
                          }
                          disabled={!isWalletConnected}
                        >
                          <SelectTrigger id="pair" className="bg-background">
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

                      <div className="space-y-3">
                        <Label>Trading Modes</Label>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between p-3 bg-background rounded border border-border">
                            <Label htmlFor="swing" className="cursor-pointer">Swing Trading</Label>
                            <Switch
                              id="swing"
                              checked={botConfig.modes.swing}
                              onCheckedChange={(checked) =>
                                setBotConfig({
                                  ...botConfig,
                                  modes: { ...botConfig.modes, swing: checked },
                                })
                              }
                              disabled={!isWalletConnected}
                            />
                          </div>
                          <div className="flex items-center justify-between p-3 bg-background rounded border border-border">
                            <Label htmlFor="scalp" className="cursor-pointer">Scalp Trading</Label>
                            <Switch
                              id="scalp"
                              checked={botConfig.modes.scalp}
                              onCheckedChange={(checked) =>
                                setBotConfig({
                                  ...botConfig,
                                  modes: { ...botConfig.modes, scalp: checked },
                                })
                              }
                              disabled={!isWalletConnected}
                            />
                          </div>
                        </div>
                      </div>

                      <div className="space-y-3">
                        <SniperModeSelector
                          selectedMode={botConfig.sniperMode}
                          onModeSelect={handleModeSelect}
                          customTimeframes={botConfig.customTimeframes}
                          onCustomTimeframesChange={handleCustomTimeframesChange}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="max-trades">Max Trades Per Run</Label>
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
                          className="bg-background"
                          disabled={!isWalletConnected}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="duration">Mission Duration (Hours)</Label>
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
                          className="bg-background"
                          disabled={!isWalletConnected}
                        />
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </TooltipTrigger>
              {!isWalletConnected && (
                <TooltipContent side="top" className="max-w-xs">
                  <p className="font-semibold mb-1">Wallet Connection Required</p>
                  <p className="text-xs">Connect your wallet at the top of the page to configure and deploy the trading bot.</p>
                </TooltipContent>
              )}
            </Tooltip>
          </TooltipProvider>
        )}

        {isConnected && (
          <TooltipProvider>
            <Tooltip open={!isWalletConnected ? undefined : false}>
              <TooltipTrigger asChild>
                <div>
                  <Button
                    onClick={handleDeployBot}
                    disabled={!isWalletConnected || !isValidConfig()}
                    className="w-full bg-warning hover:bg-warning/90 text-warning-foreground h-14 text-lg font-bold disabled:opacity-50"
                    size="lg"
                  >
                    <Lightning size={24} weight="bold" />
                    DEPLOY BOT
                  </Button>
                </div>
              </TooltipTrigger>
              {!isWalletConnected && (
                <TooltipContent side="top" className="max-w-xs">
                  <p className="font-semibold mb-1">Wallet Connection Required</p>
                  <p className="text-xs">Connect your wallet at the top of the page to deploy the trading bot.</p>
                </TooltipContent>
              )}
            </Tooltip>
          </TooltipProvider>
        )}
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
    </div>
  );
}
