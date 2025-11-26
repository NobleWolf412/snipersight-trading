import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { 
  ChartLine, 
  TrendUp, 
  TrendDown, 
  Activity,
  Target,
  Crosshair,
  Eye,
  Knife,
  ArrowUp,
  ArrowDown,
  Minus
} from '@phosphor-icons/react';
import { PageShell } from '@/components/layout/PageShell';
import { HomeButton } from '@/components/layout/HomeButton';
import { TacticalPanel } from '@/components/TacticalPanel';
import { MarketRegimeLens } from '@/components/market/MarketRegimeLens';
import { useMockMarketRegime } from '@/hooks/use-mock-market-regime';
import { cn } from '@/lib/utils';

interface SymbolIntel {
  symbol: string;
  trendSummary: string;
  htfTrend: string;
  volatility: string;
  liquidity: string;
  momentum: string;
  recommendedModes: string[];
  riskNote: string;
  aiCommentary?: string;
}

interface AlertItem {
  title: string;
  severity: 'INFO' | 'WATCH' | 'ALERT';
  timeAgo: string;
  summary: string;
}

type ModeStatus = 'OPTIMAL' | 'FAVORABLE' | 'CAUTIOUS' | 'DISABLED';

interface ModeReadiness {
  mode: string;
  status: ModeStatus;
  icon: React.ComponentType<any>;
}

function getModeReadiness(regimeLabel: string, visibility: string): ModeReadiness[] {
  const isDefensive = regimeLabel === 'DEFENSIVE';
  const isPanic = regimeLabel === 'PANIC';
  const isChoppy = regimeLabel === 'CHOPPY';
  const isHighVis = visibility === 'HIGH';
  const isMediumVis = visibility === 'MEDIUM';

  return [
    {
      mode: 'Overwatch',
      icon: Eye,
      status: isPanic ? 'DISABLED' : isChoppy ? 'CAUTIOUS' : isDefensive ? 'CAUTIOUS' : isHighVis ? 'OPTIMAL' : isMediumVis ? 'FAVORABLE' : 'CAUTIOUS'
    },
    {
      mode: 'Recon',
      icon: Crosshair,
      status: isPanic ? 'CAUTIOUS' : isChoppy ? 'FAVORABLE' : isMediumVis ? 'OPTIMAL' : 'FAVORABLE'
    },
    {
      mode: 'Strike',
      icon: Target,
      status: isPanic ? 'DISABLED' : isDefensive ? 'CAUTIOUS' : isChoppy ? 'CAUTIOUS' : isHighVis ? 'OPTIMAL' : 'FAVORABLE'
    },
    {
      mode: 'Surgical',
      icon: Knife,
      status: isPanic ? 'FAVORABLE' : isDefensive ? 'OPTIMAL' : isChoppy ? 'OPTIMAL' : 'FAVORABLE'
    }
  ];
}

function ModeChip({ mode, status, icon: Icon }: ModeReadiness) {
  const statusColors = {
    OPTIMAL: 'bg-success/20 border-success text-success',
    FAVORABLE: 'bg-primary/20 border-primary text-primary',
    CAUTIOUS: 'bg-warning/20 border-warning text-warning',
    DISABLED: 'bg-muted border-border text-muted-foreground'
  };

  return (
    <div className={cn(
      'p-3 rounded-lg border-2 transition-all',
      statusColors[status]
    )}>
      <div className="flex items-center gap-2 mb-2">
        <Icon size={20} weight="bold" />
        <div className="font-bold text-sm">{mode}</div>
      </div>
      <Badge 
        variant="outline" 
        className={cn('text-xs font-mono border-current', statusColors[status])}
      >
        {status}
      </Badge>
    </div>
  );
}

export function Intel() {
  const regimeProps = useMockMarketRegime('scanner');
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [intel, setIntel] = useState<SymbolIntel | null>(null);

  const modeReadiness = getModeReadiness(regimeProps.regimeLabel, regimeProps.visibility);

  const btcDomChange = regimeProps.previousBtcDominance 
    ? regimeProps.btcDominance! - regimeProps.previousBtcDominance 
    : 0;
  const usdtDomChange = regimeProps.previousUsdtDominance 
    ? regimeProps.usdtDominance! - regimeProps.previousUsdtDominance 
    : 0;
  const altDomChange = regimeProps.previousAltDominance 
    ? regimeProps.altDominance! - regimeProps.previousAltDominance 
    : 0;

  const compositeScore = regimeProps.visibility === 'HIGH' ? 85 : 
                         regimeProps.visibility === 'MEDIUM' ? 60 :
                         regimeProps.visibility === 'LOW' ? 35 : 15;

  const alerts: AlertItem[] = [
    {
      title: 'BTC swept 4H lows in DEFENSIVE regime',
      severity: 'WATCH',
      timeAgo: '12m ago',
      summary: 'Watch for long setups only with strong confirmation and reduced size.'
    },
    {
      title: 'Altcoin basket showing elevated volatility',
      severity: 'ALERT',
      timeAgo: '28m ago',
      summary: 'Under PANIC conditions, avoid leveraged alt trades. BTC/ETH only.'
    },
    {
      title: 'Stablecoin dominance increasing',
      severity: 'INFO',
      timeAgo: '1h ago',
      summary: 'Money rotating to sidelines; expect defensive positioning to continue.'
    }
  ];

  const handleAnalyze = async () => {
    const cleanSymbol = symbol.trim().toUpperCase();
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/market-intel/symbol?symbol=${cleanSymbol}`);
      
      if (response.ok) {
        const data = await response.json();
        setIntel(data);
      } else {
        throw new Error('API not available');
      }
    } catch (err) {
      console.log('Falling back to mock data:', err);
      
      const mockIntel: SymbolIntel = {
        symbol: cleanSymbol,
        trendSummary: regimeProps.regimeLabel === 'DEFENSIVE' ? 'Defensive consolidation' : 'Strong uptrend',
        htfTrend: regimeProps.regimeLabel === 'PANIC' ? 'Bearish' : regimeProps.regimeLabel === 'DEFENSIVE' ? 'Neutral' : 'Bullish',
        volatility: regimeProps.visibility === 'HIGH' ? 'Low' : regimeProps.visibility === 'MEDIUM' ? 'Moderate' : 'High',
        liquidity: cleanSymbol.includes('BTC') || cleanSymbol.includes('ETH') ? 'High' : 'Moderate',
        momentum: regimeProps.regimeLabel === 'BTC_DRIVE' ? 'Strong bullish' : regimeProps.regimeLabel === 'PANIC' ? 'Weak bearish' : 'Neutral',
        recommendedModes: regimeProps.regimeLabel === 'DEFENSIVE' ? ['Surgical', 'Recon'] : ['Strike', 'Overwatch'],
        riskNote: regimeProps.regimeLabel === 'PANIC' ? 'High risk - reduce position sizes' : 'Standard risk protocols apply',
        aiCommentary: `${cleanSymbol} is trading in a ${regimeProps.regimeLabel} market regime with ${regimeProps.visibility} visibility. Consider ${regimeProps.regimeLabel === 'DEFENSIVE' ? 'conservative entries with tight stops' : 'standard setups with confirmation'}.`
      };
      
      setIntel(mockIntel);
    } finally {
      setIsLoading(false);
    }
  };

  const globalCommentary = regimeProps.regimeLabel === 'DEFENSIVE' 
    ? "Market is in a defensive, choppy regime with money rotating into BTC and stables. Favor conservative modes like Surgical and avoid aggressive trend continuation setups. Reduce position sizes and tighten stops."
    : regimeProps.regimeLabel === 'PANIC'
    ? "PANIC regime detected with very low signal visibility. Avoid new positions except for high-conviction BTC/ETH scalps. Wait for regime shift before deploying aggressive strategies."
    : regimeProps.regimeLabel === 'BTC_DRIVE'
    ? "BTC-driven uptrend with moderate volatility. Overwatch and Strike modes can be selectively deployed. Focus on BTC and major alts with strong confirmation."
    : regimeProps.regimeLabel === 'ALTSEASON'
    ? "ALTSEASON regime with high visibility. All sniper modes favorable. Focus on altcoins with strong momentum and proper liquidity."
    : "Choppy market conditions with mixed signals. Favor Surgical and Recon modes. Wait for clearer price action before deploying aggressive setups.";

  return (
    <PageShell>
      <div className="space-y-6 md:space-y-8">
        <div className="flex justify-start">
          <HomeButton />
        </div>

        <div className="space-y-2">
          <h1 className="text-3xl md:text-4xl font-bold text-foreground flex items-center gap-4 heading-hud">
            <ChartLine size={40} weight="bold" className="text-accent" />
            MARKET INTEL
          </h1>
          <p className="text-sm md:text-base text-muted-foreground max-w-3xl">
            Tactical overview of market regime, dominance flows, and AI-assisted trade readiness.
          </p>
        </div>

        <TacticalPanel className="mb-6">
          <div className="p-4 md:p-6">
            <div className="flex flex-col lg:flex-row gap-6 items-start lg:items-center justify-between">
              <div>
                <div className="text-xs heading-hud text-muted-foreground mb-1">
                  GLOBAL MARKET REGIME
                </div>
                <div className="text-xl md:text-2xl font-semibold text-foreground">
                  Tactical lens for scanner & bot deployment
                </div>
                <p className="text-sm text-muted-foreground mt-2 max-w-xl">
                  Uses BTC, stablecoin and altcoin flows plus internal volatility signals
                  to classify the current environment and guide which sniper modes are safe to deploy.
                </p>
              </div>
              <div className="w-full lg:w-auto">
                <MarketRegimeLens {...regimeProps} />
              </div>
            </div>
          </div>
        </TacticalPanel>

        <TacticalPanel className="mb-6">
          <div className="p-4 md:p-6">
            <div className="text-xs heading-hud text-muted-foreground mb-3">
              GLOBAL AI COMMENTARY
            </div>
            <div className="bg-muted/30 border border-border/50 rounded-lg p-4">
              <p className="text-sm text-foreground leading-relaxed">
                {globalCommentary}
              </p>
            </div>
          </div>
        </TacticalPanel>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          <TacticalPanel>
            <div className="p-4 md:p-6">
              <div className="text-xs heading-hud mb-4 text-muted-foreground">TREND & VISIBILITY</div>
              <div className="space-y-3">
                <div>
                  <div className="text-2xl font-bold text-foreground">{regimeProps.regimeLabel.replace('_', ' ')}</div>
                  <div className="text-sm text-muted-foreground mt-1">
                    Composite Score: <span className="font-mono font-bold">{compositeScore}%</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Activity size={20} className="text-accent" weight="bold" />
                  <span className="text-sm">
                    Signal clarity: <span className="font-bold">{regimeProps.visibility}</span>
                  </span>
                </div>
              </div>
            </div>
          </TacticalPanel>

          <TacticalPanel>
            <div className="p-4 md:p-6">
              <div className="text-xs heading-hud mb-4 text-muted-foreground">DOMINANCE FLOWS</div>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">BTC.D</span>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold">{regimeProps.btcDominance?.toFixed(1)}%</span>
                    {btcDomChange > 0.1 ? (
                      <ArrowUp size={16} className="text-success" weight="bold" />
                    ) : btcDomChange < -0.1 ? (
                      <ArrowDown size={16} className="text-destructive" weight="bold" />
                    ) : (
                      <Minus size={16} className="text-muted-foreground" weight="bold" />
                    )}
                  </div>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">USDT.D</span>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold">{regimeProps.usdtDominance?.toFixed(1)}%</span>
                    {usdtDomChange > 0.1 ? (
                      <ArrowUp size={16} className="text-success" weight="bold" />
                    ) : usdtDomChange < -0.1 ? (
                      <ArrowDown size={16} className="text-destructive" weight="bold" />
                    ) : (
                      <Minus size={16} className="text-muted-foreground" weight="bold" />
                    )}
                  </div>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">ALT.D</span>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold">{regimeProps.altDominance?.toFixed(1)}%</span>
                    {altDomChange > 0.1 ? (
                      <ArrowUp size={16} className="text-success" weight="bold" />
                    ) : altDomChange < -0.1 ? (
                      <ArrowDown size={16} className="text-destructive" weight="bold" />
                    ) : (
                      <Minus size={16} className="text-muted-foreground" weight="bold" />
                    )}
                  </div>
                </div>
              </div>
            </div>
          </TacticalPanel>

          <TacticalPanel>
            <div className="p-4 md:p-6">
              <div className="text-xs heading-hud mb-4 text-muted-foreground">SCANNER & BOT GUIDANCE</div>
              <div className="space-y-2">
                {regimeProps.guidanceLines?.slice(0, 3).map((line, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-sm">
                    <span className="text-accent mt-0.5">▸</span>
                    <span className="text-foreground leading-tight">{line}</span>
                  </div>
                ))}
              </div>
            </div>
          </TacticalPanel>
        </div>

        <TacticalPanel className="mb-6">
          <div className="p-4 md:p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="heading-hud text-xs text-muted-foreground">MODE READINESS</div>
              <div className="text-sm text-muted-foreground hidden md:block">
                Readiness derived from current regime and signal visibility
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {modeReadiness.map((mode) => (
                <ModeChip key={mode.mode} {...mode} />
              ))}
            </div>
          </div>
        </TacticalPanel>

        <TacticalPanel className="mb-6">
          <div className="p-4 md:p-6">
            <div className="mb-4">
              <div className="text-xs heading-hud text-muted-foreground mb-2">
                SYMBOL INTEL (AI-READY)
              </div>
              <p className="text-sm text-muted-foreground">
                Enter a symbol to generate a tactical intel brief. Backend AI wiring will be added later.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-3 mb-6">
              <Input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                placeholder="BTCUSDT"
                className="flex-1 font-mono"
                onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
              />
              <Button 
                onClick={handleAnalyze} 
                disabled={isLoading}
                className="min-w-[120px]"
              >
                {isLoading ? 'Analyzing...' : 'Analyze'}
              </Button>
            </div>

            {error && (
              <div className="p-4 bg-destructive/10 border border-destructive/50 rounded-lg mb-4">
                <p className="text-sm text-destructive">{error}</p>
              </div>
            )}

            {intel && (
              <div className="bg-card/50 border border-border rounded-lg p-4 space-y-4">
                <div className="border-b border-border pb-3">
                  <div className="flex items-center justify-between">
                    <div className="text-xl font-bold font-mono">{intel.symbol}</div>
                    <Badge variant="outline">{intel.trendSummary}</Badge>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">HTF Trend</div>
                    <div className="font-semibold">{intel.htfTrend}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Volatility</div>
                    <div className="font-semibold">{intel.volatility}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Liquidity</div>
                    <div className="font-semibold">{intel.liquidity}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Momentum</div>
                    <div className="font-semibold">{intel.momentum}</div>
                  </div>
                </div>

                <div>
                  <div className="text-xs text-muted-foreground mb-2">Recommended Modes</div>
                  <div className="flex gap-2 flex-wrap">
                    {intel.recommendedModes.map((mode) => (
                      <Badge key={mode} variant="secondary">{mode}</Badge>
                    ))}
                  </div>
                </div>

                <div className="bg-warning/10 border border-warning/30 rounded p-3">
                  <div className="text-xs font-bold text-warning mb-1">RISK NOTE</div>
                  <div className="text-sm text-foreground">{intel.riskNote}</div>
                </div>

                {intel.aiCommentary && (
                  <div className="bg-muted/30 border border-border/50 rounded p-3">
                    <div className="text-xs font-bold text-accent mb-2">AI COMMENTARY</div>
                    <p className="text-sm text-foreground leading-relaxed">{intel.aiCommentary}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </TacticalPanel>

        <TacticalPanel>
          <div className="p-4 md:p-6">
            <h3 className="heading-hud text-sm text-muted-foreground mb-6">ACTIVE ALERTS</h3>
            <div className="space-y-4">
              {alerts.map((alert, idx) => {
                const severityColors = {
                  INFO: 'bg-accent/10 border-accent/50',
                  WATCH: 'bg-warning/10 border-warning/50',
                  ALERT: 'bg-destructive/10 border-destructive/50'
                };
                const badgeColors = {
                  INFO: 'bg-accent/20 text-accent border-accent/50',
                  WATCH: 'bg-warning/20 text-warning border-warning/50',
                  ALERT: 'bg-destructive/20 text-destructive border-destructive/50'
                };

                return (
                  <div key={idx} className={cn('p-4 border rounded-lg', severityColors[alert.severity])}>
                    <div className="flex items-center justify-between mb-2">
                      <Badge className={badgeColors[alert.severity]}>{alert.severity}</Badge>
                      <span className="text-xs text-muted-foreground">{alert.timeAgo}</span>
                    </div>
                    <div className="font-semibold text-sm mb-1">{alert.title}</div>
                    <div className="text-sm text-muted-foreground">{alert.summary}</div>
                  </div>
                );
              })}
            </div>
          </div>
        </TacticalPanel>
      </div>
    </PageShell>
  );
}

export default Intel;
