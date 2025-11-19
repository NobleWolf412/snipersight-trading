import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { MagnifyingGlass, Robot, Target, ListBullets, Crosshair } from '@phosphor-icons/react';

export function Landing() {
  const navigate = useNavigate();

  return (
    <div className="min-h-[calc(100vh-4rem)] tactical-grid flex items-center justify-center p-4">
      <div className="max-w-4xl w-full space-y-8">
        <div className="text-center space-y-4">
          <div className="flex justify-center">
            <div className="w-20 h-20 bg-accent/20 rounded-lg flex items-center justify-center border border-accent/50 hud-glow">
              <Crosshair size={48} weight="bold" className="text-accent" />
            </div>
          </div>
          <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight">
            SNIPERSIGHT COMMAND CENTER
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Precision Crypto Scanning · Institutional-Grade Analysis · Tactical Execution
          </p>
          <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
            <div className="w-2 h-2 bg-accent rounded-full scan-pulse" />
            <span>SYSTEMS ONLINE</span>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <Card
            className="p-6 bg-card/50 border-accent/30 hover:border-accent/60 transition-all cursor-pointer hud-glow group"
            onClick={() => navigate('/scan')}
          >
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-accent/20 rounded flex items-center justify-center border border-accent/50">
                  <MagnifyingGlass size={24} weight="bold" className="text-accent" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-foreground">SCAN MARKET</h2>
                  <p className="text-sm text-muted-foreground">Manual reconnaissance</p>
                </div>
              </div>
              <p className="text-sm text-foreground/80">
                Execute multi-timeframe analysis across crypto pairs. Identify high-conviction setups with Smart Money Concepts.
              </p>
              <Button className="w-full bg-accent hover:bg-accent/90 text-accent-foreground" size="lg">
                ACQUIRE TARGETS
              </Button>
            </div>
          </Card>

          <Card
            className="p-6 bg-card/50 border-warning/30 hover:border-warning/60 transition-all cursor-pointer group"
            onClick={() => navigate('/bot')}
          >
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-warning/20 rounded flex items-center justify-center border border-warning/50">
                  <Robot size={24} weight="bold" className="text-warning" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-foreground">DEPLOY BOT</h2>
                  <p className="text-sm text-muted-foreground">Autonomous execution</p>
                </div>
              </div>
              <p className="text-sm text-foreground/80">
                Activate automated sniper for continuous market surveillance and precision trade execution.
              </p>
              <Button className="w-full bg-warning hover:bg-warning/90 text-warning-foreground" size="lg">
                ACTIVATE AUTOMATION
              </Button>
            </div>
          </Card>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <Card
            className="p-4 bg-card/30 border-border hover:border-accent/30 transition-all cursor-pointer"
            onClick={() => navigate('/training')}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-muted rounded flex items-center justify-center">
                <Target size={20} className="text-foreground" />
              </div>
              <div>
                <h3 className="font-bold text-foreground">TRAINING GROUND</h3>
                <p className="text-xs text-muted-foreground">Practice with simulated data</p>
              </div>
            </div>
          </Card>

          <Card
            className="p-4 bg-card/30 border-border hover:border-accent/30 transition-all cursor-pointer"
            onClick={() => navigate('/profiles')}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-muted rounded flex items-center justify-center">
                <ListBullets size={20} className="text-foreground" />
              </div>
              <div>
                <h3 className="font-bold text-foreground">SNIPER PROFILES</h3>
                <p className="text-xs text-muted-foreground">Preset configurations</p>
              </div>
            </div>
          </Card>
        </div>

        <div className="text-center">
          <p className="text-xs text-muted-foreground">VERSION 1.0.0 · OPERATIONAL</p>
        </div>
      </div>
    </div>
  );
}
