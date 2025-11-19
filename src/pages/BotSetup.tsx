import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Robot, Shield, Lightning } from '@phosphor-icons/react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

export function BotSetup() {
  const navigate = useNavigate();
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [pair, setPair] = useState('BTC/USDT');
  const [swingMode, setSwingMode] = useState(true);
  const [scalpMode, setScalpMode] = useState(false);
  const [maxTrades, setMaxTrades] = useState(3);
  const [duration, setDuration] = useState(24);

  const handleConnectExchange = () => {
    setTimeout(() => {
      setIsConnected(true);
      setShowConnectModal(false);
    }, 1500);
  };

  const handleDeployBot = () => {
    navigate('/bot/status');
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
                    <div className="text-xs text-muted-foreground">Binance · Secure Backend Storage</div>
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
          <Card className="bg-card/50 border-warning/30">
            <CardHeader>
              <CardTitle>Bot Configuration</CardTitle>
              <CardDescription>Trading parameters and limits</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="pair">Trading Pair</Label>
                <Select value={pair} onValueChange={setPair}>
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
                    <Switch id="swing" checked={swingMode} onCheckedChange={setSwingMode} />
                  </div>
                  <div className="flex items-center justify-between p-3 bg-background rounded border border-border">
                    <Label htmlFor="scalp" className="cursor-pointer">Scalp Trading</Label>
                    <Switch id="scalp" checked={scalpMode} onCheckedChange={setScalpMode} />
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="max-trades">Max Trades Per Run</Label>
                <Input
                  id="max-trades"
                  type="number"
                  min="1"
                  max="10"
                  value={maxTrades}
                  onChange={(e) => setMaxTrades(parseInt(e.target.value) || 1)}
                  className="bg-background"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="duration">Mission Duration (Hours)</Label>
                <Input
                  id="duration"
                  type="number"
                  min="1"
                  max="168"
                  value={duration}
                  onChange={(e) => setDuration(parseInt(e.target.value) || 1)}
                  className="bg-background"
                />
              </div>
            </CardContent>
          </Card>
        )}

        {isConnected && (
          <Button
            onClick={handleDeployBot}
            disabled={!swingMode && !scalpMode}
            className="w-full bg-warning hover:bg-warning/90 text-warning-foreground h-14 text-lg font-bold"
            size="lg"
          >
            <Lightning size={24} weight="bold" />
            DEPLOY BOT
          </Button>
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
