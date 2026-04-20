import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import {
  Target,
  PlayCircle,
  StopCircle,
  ArrowsClockwise,
  BookOpen,
  TrendUp,
  TrendDown,
  Wallet,
  ChartLine,
  Pulse,
  Clock,
  Trophy,
  Warning,
  CheckCircle,
  XCircle,
  X,
  Crosshair,
  ArrowUp,
  ArrowDown,
  ListBullets,
  Gear,
  Lightning,
  ShieldCheck,
  Fire,
  CaretDown,
  Cpu,
  TestTube,
} from '@phosphor-icons/react';
import { PageContainer } from '@/components/layout/PageContainer';
import { HomeButton } from '@/components/layout/HomeButton';
import { TacticalPanel } from '@/components/TacticalPanel';
import { PaperTradingConfig } from '@/components/PaperTradingConfig';
import {
  api,
  PaperTradingConfigRequest,
  PaperTradingStatusResponse,
  PaperTradingPosition,
  PaperTradingStats,
  PaperTradingBalance,
  CompletedPaperTrade,
  PaperTradingActivity,
  SignalLogEntry,
} from '@/utils/api';
import { GauntletBreakdown } from '@/components/bot/GauntletBreakdown';


// Format time duration
function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${mins}m`;
}

// Format currency
function formatCurrency(value: number, decimals = 2): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

// Format percentage
function formatPct(value: number, decimals = 2): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
}

// Mini Equity Sparkline Component
function EquitySparkline({ trades, initialBalance }: { trades: CompletedPaperTrade[]; initialBalance: number }) {
  const points = useMemo(() => {
    if (!trades || trades.length === 0) return [];
    // Build cumulative equity curve from trades (oldest first)
    const sorted = [...trades].reverse();
    let equity = initialBalance;
    const pts = [{ x: 0, y: equity }];
    sorted.forEach((t, i) => {
      equity += t.pnl;
      pts.push({ x: i + 1, y: equity });
    });
    return pts;
  }, [trades, initialBalance]);

  if (points.length < 2) {
    return (
      <div className="h-16 flex items-center justify-center text-[10px] text-muted-foreground/40 font-mono uppercase tracking-widest">
        Awaiting trades...
      </div>
    );
  }

  const minY = Math.min(...points.map(p => p.y));
  const maxY = Math.max(...points.map(p => p.y));
  const rangeY = maxY - minY || 1;
  const w = 280;
  const h = 56;
  const pad = 2;

  const pathD = points.map((p, i) => {
    const x = pad + (p.x / (points.length - 1)) * (w - 2 * pad);
    const y = h - pad - ((p.y - minY) / rangeY) * (h - 2 * pad);
    return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(' ');

  const lastPt = points[points.length - 1];
  const isUp = lastPt.y >= initialBalance;
  const strokeColor = isUp ? '#00ff88' : '#ff4444';
  const fillGradId = 'eq-grad';

  // Area fill: close from the actual last point's X down to the baseline and back to origin
  const lastPtX = pad + (lastPt.x / (points.length - 1)) * (w - 2 * pad);
  const lastPtY = h - pad - ((lastPt.y - minY) / rangeY) * (h - 2 * pad);
  const firstX = pad;
  const areaD = pathD + ` L ${lastPtX.toFixed(1)} ${h} L ${firstX.toFixed(1)} ${h} Z`;

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="w-full h-16">
      <defs>
        <linearGradient id={fillGradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={strokeColor} stopOpacity="0.15" />
          <stop offset="100%" stopColor={strokeColor} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaD} fill={`url(#${fillGradId})`} />
      <path d={pathD} fill="none" stroke={strokeColor} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      {/* Pulse dot at the actual last data point */}
      <circle
        cx={lastPtX}
        cy={lastPtY}
        r="3"
        fill={strokeColor}
        className="animate-pulse"
      />
    </svg>
  );
}

// Default Phantom Spec Config — mode is always stealth (hardcoded backend)
const DEFAULT_CONFIG: PaperTradingConfigRequest = {
  exchange: 'phemex',
  sniper_mode: 'stealth', // Fixed: optimal balance for paper trading (adaptive scalp/swing)
  initial_balance: 10000,
  risk_per_trade: 2, // Total 2% per thesis
  max_positions: 3, // 3 limits (L1, L2, L3)
  leverage: 1, // Default 1x
  max_drawdown_pct: 10, // 10% session drawdown kill-switch
  duration_hours: 24,
  scan_interval_minutes: 2,
  trailing_stop: true,
  trailing_activation: 2.0, // WAS 1.0 - changed to 2.0 to give trade room to breathe
  breakeven_after_target: 1, // Move to BE after TP1 is hit
  sensitivity_preset: 'balanced',
  min_confluence: null,          // null = use preset gate (resolved backend-side)
  confluence_soft_floor: null,   // null = use preset floor (resolved backend-side)
  symbols: [],
  exclude_symbols: [],
  majors: true,
  altcoins: false,
  meme_mode: false,
  slippage_bps: 15,
  fee_rate: 0.001,
  max_hours_open: 72,
  use_testnet: false,
};

export function TrainingGround() {
  const navigate = useNavigate();
  const [config, setConfig] = useState<PaperTradingConfigRequest>(DEFAULT_CONFIG);
  const [status, setStatus] = useState<PaperTradingStatusResponse | null>(null);
  const [trades, setTrades] = useState<CompletedPaperTrade[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recommendation, setRecommendation] = useState<{mode: string, reason: string, warning: string | null, confidence: string, recommended_confluence?: number, regime?: any} | null>(null);
  const [debrief, setDebrief] = useState<{ stats: PaperTradingStats; balance: PaperTradingBalance; config: PaperTradingConfigRequest; uptime: number; signalLog: SignalLogEntry[] } | null>(null);

  const pollRef = useRef<number | null>(null);

  // Fetch status
  const fetchStatus = useCallback(async () => {
    try {
      const response = await api.getPaperTradingStatus();
      if (response.data) {
        setStatus(response.data);
      }
    } catch (err) {
      console.error('Failed to fetch status:', err);
    } finally {
      setIsInitialLoad(false);
    }
  }, []);

  // Fetch trade history
  const fetchTrades = useCallback(async () => {
    try {
      const response = await api.getPaperTradingHistory(50);
      if (response.data?.trades) {
        setTrades(response.data.trades);
      }
    } catch (err) {
      console.error('Failed to fetch trades:', err);
    }
  }, []);

  // Fetch recommendation
  const fetchRecommendation = useCallback(async () => {
    try {
      const response = await api.getScannerRecommendation();
      if (response.data) {
        setRecommendation(response.data);
      }
    } catch (err) {
      console.error('Failed to fetch recommendation:', err);
    }
  }, []);

  // Poll status when running
  useEffect(() => {
    fetchStatus();
    fetchTrades();
    fetchRecommendation();

    // Set up polling - use longer interval (15s) to avoid overwhelming backend during heavy scans
    // Backend can take 10-20s to respond when scanner is actively processing
    if (status?.status === 'running') {
      pollRef.current = window.setInterval(() => {
        fetchStatus();
        fetchTrades();
      }, 15000);
    }

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [status?.status, fetchStatus, fetchTrades]);

  // Start paper trading
  const handleStart = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await api.startPaperTrading(config);
      if (response.error) {
        setError(response.error);
      } else {
        await fetchStatus();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start paper trading');
    } finally {
      setIsLoading(false);
    }
  };

  // Stop paper trading
  const handleStop = async () => {
    setIsLoading(true);
    setError(null);

    // Snapshot current session data for the debrief modal
    const preStopStatus = status;

    try {
      const response = await api.stopPaperTrading();
      if (response.error) {
        setError(response.error);
      } else {
        await fetchStatus();
        await fetchTrades();
        // Show debrief if there was meaningful activity
        if (preStopStatus?.statistics && preStopStatus.balance && preStopStatus.config) {
          setDebrief({
            stats: preStopStatus.statistics,
            balance: preStopStatus.balance,
            config: preStopStatus.config,
            uptime: preStopStatus.uptime_seconds,
            signalLog: preStopStatus.signal_log ?? [],
          });
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop paper trading');
    } finally {
      setIsLoading(false);
    }
  };

  // Reset paper trading
  const handleReset = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await api.resetPaperTrading();
      if (response.error) {
        setError(response.error);
      } else {
        setStatus(null);
        setTrades([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset paper trading');
    } finally {
      setIsLoading(false);
    }
  };

  const isRunning = status?.status === 'running';
  const isStopped = status?.status === 'stopped';
  const isIdle = !status || status.status === 'idle' || status.status === 'stopped';

  return (
    <PageContainer id="main-content">
      <div className="space-y-8">
        {/* Header */}
        <div className="flex justify-between items-start">
          <div className="flex items-start gap-4">
            <HomeButton />
            <div className="space-y-2">
              <h1 className="text-3xl lg:text-4xl font-bold flex items-center gap-3 hud-headline hud-text-green tracking-widest">
                <Target size={32} weight="bold" className="text-accent" />
                TRAINING GROUND
              </h1>
              <p className="font-mono text-sm text-muted-foreground uppercase tracking-widest pl-11">
                Paper trading with real market data
              </p>
            </div>
          </div>

          {/* Status Badge */}
          {status && (
            <Badge
              variant="outline"
              className={cn(
                "text-sm px-3 py-1 font-mono tracking-widest uppercase border",
                isRunning ? 'bg-green-500/10 text-green-400 border-green-500/30' :
                  isStopped ? 'bg-red-500/10 text-red-400 border-red-500/30' :
                    'bg-muted/50 text-muted-foreground border-border'
              )}
            >
              {isRunning && <Pulse size={14} className="mr-2 animate-pulse" />}
              {status.status.toUpperCase()}
            </Badge>
          )}
        </div>

        {/* Page tab nav */}
        <div className="flex gap-2 p-1 rounded-lg bg-black/40 border border-white/10 w-fit">
          <span className="px-4 py-2 rounded-md text-xs font-mono tracking-widest bg-accent/20 text-accent border border-accent/30 font-bold">
            TRAINING GROUND
          </span>
          <button
            onClick={() => navigate('/journal')}
            className="px-4 py-2 rounded-md text-xs font-mono tracking-widest text-white/70 hover:bg-white/10 hover:text-white transition-colors font-bold"
          >
            JOURNAL &amp; ML
          </button>
        </div>

        {/* Info Alert */}
        <div className="border border-accent/30 bg-accent/5 p-4 rounded-xl relative overflow-hidden glass-card glow-border-green">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-green-500/5 via-transparent to-transparent opacity-40" />
          <div className="flex items-start gap-4">
            <BookOpen size={20} className="text-accent mt-0.5" />
            <div>
              <h3 className="text-accent uppercase font-bold tracking-widest text-sm mb-1 font-mono">
                SAFE ENVIRONMENT
              </h3>
              <p className="text-muted-foreground text-sm font-mono leading-relaxed">
                Paper trading uses real market data but simulated execution. Perfect for testing strategies without risking real capital.
              </p>
            </div>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert variant="destructive">
            <Warning size={20} />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Main Content Area */}
        {isInitialLoad ? (
          <div className="flex h-[400px] items-center justify-center mt-6 glass-card glow-border-green rounded-2xl relative overflow-hidden">
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-green-500/5 via-transparent to-transparent opacity-40 pointer-events-none" />
            <div className="flex flex-col items-center gap-4 text-accent opacity-70 relative z-10">
              <ArrowsClockwise size={40} className="animate-spin" />
              <p className="font-mono text-sm tracking-widest uppercase animate-pulse">Establishing Uplink...</p>
            </div>
          </div>
        ) : isIdle ? (
          <div className="space-y-6 mt-6">
            <section className="glass-card glow-border-green rounded-2xl p-6 md:p-8 flex flex-col items-center text-center space-y-6 relative overflow-hidden group transition-all duration-500 hover:shadow-[0_0_50px_rgba(0,255,170,0.15)]">
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-green-500/10 via-transparent to-transparent opacity-40 pointer-events-none group-hover:opacity-60 transition-opacity duration-1000" />
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-[#00ff88]/50 to-transparent opacity-50" />
              <div className="relative z-10 w-full flex flex-col items-center text-center space-y-6">
                <Target size={64} className="text-accent opacity-50 mb-2" />
                <div className="max-w-xl mx-auto space-y-2">
                  <h2 className="text-3xl lg:text-4xl font-black italic tracking-tighter text-transparent bg-clip-text bg-gradient-to-b from-white via-green-50 to-green-400/80 drop-shadow-[0_4px_4px_rgba(0,0,0,0.5)]">PHANTOM INITIALIZATION</h2>
                  <div className="h-1 w-24 mx-auto bg-gradient-to-r from-transparent via-green-500/50 to-transparent rounded-full mb-4" />
                  <p className="text-base text-green-100/80 leading-relaxed font-light">
                    Phantom is an autonomous, regime-adaptive execution layer running strictly limit-only entries with a scaled ladder approach.
                  </p>
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 w-full">
                  {/* Leverage */}
                  <div className="p-4 rounded-xl bg-background/60 border border-border hover:border-accent/30 transition-colors">
                    <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">Leverage</div>
                    <div className="text-2xl font-mono font-bold text-accent">{config.leverage}x</div>
                    <div className="text-[9px] text-muted-foreground mt-1 opacity-60">Adjustable below</div>
                  </div>
                  {/* Risk */}
                  <div className="p-4 rounded-xl bg-background/60 border border-border hover:border-border/60 transition-colors">
                    <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">Risk Profile</div>
                    <div className="text-2xl font-mono font-bold text-foreground">{config.risk_per_trade ?? 2}%</div>
                    <div className="text-[9px] text-muted-foreground mt-1 opacity-60">3-part scale-in</div>
                  </div>
                  {/* Regime */}
                  <div className="p-4 rounded-xl bg-background/60 border border-border hover:border-primary/30 transition-colors relative overflow-hidden">
                    {recommendation?.regime?.composite && (
                      <div className="absolute inset-0 bg-[radial-gradient(circle_at_bottom_right,_var(--tw-gradient-stops))] from-blue-500/10 to-transparent pointer-events-none" />
                    )}
                    <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">Regime State</div>
                    <div className="flex items-center gap-1.5">
                      <div className={cn("w-1.5 h-1.5 rounded-full shrink-0", recommendation?.regime?.composite ? "bg-primary animate-pulse" : "bg-muted-foreground/40")} />
                      <div className="text-lg font-mono font-bold text-primary capitalize truncate">
                        {recommendation?.regime?.composite
                          ? recommendation.regime.composite.replace(/_/g, ' — ')
                          : 'Adaptive'}
                      </div>
                    </div>
                    {recommendation?.reason && (
                      <div className="text-[9px] text-muted-foreground mt-1 leading-tight truncate opacity-70">
                        {recommendation.reason}
                      </div>
                    )}
                  </div>
                  {/* Signal Sensitivity */}
                  <div className="p-4 rounded-xl bg-background/60 border border-border hover:border-yellow-400/30 transition-colors">
                    <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">Sensitivity</div>
                    <div className="text-xl font-mono font-bold text-yellow-400 capitalize">
                      {config.sensitivity_preset ?? 'balanced'}
                    </div>
                    <div className="text-[9px] text-muted-foreground mt-1 opacity-60">
                      {config.sensitivity_preset === 'conservative' ? '72/62 gate/floor' :
                       config.sensitivity_preset === 'aggressive' ? '58/48 gate/floor' :
                       config.sensitivity_preset === 'custom' ? `${config.min_confluence ?? 65}/${config.confluence_soft_floor ?? 55}` :
                       '65/55 gate/floor'}
                    </div>
                  </div>
                </div>

                <div className="w-full max-w-2xl pt-4 space-y-6">
                  {/* Engine Mode — Fixed to Stealth */}
                  <div className="space-y-3">
                    <label className="text-[10px] text-accent font-bold uppercase tracking-widest pl-1">Engine Mode</label>
                    <div className="bg-gradient-to-r from-purple-500/10 via-accent/5 to-blue-500/10 border border-purple-500/30 rounded-xl p-4 relative overflow-hidden">
                      <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-purple-400/50 to-transparent" />
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <Lightning size={18} weight="fill" className="text-purple-400" />
                          <span className="text-sm font-black tracking-widest text-purple-400">STEALTH</span>
                          {recommendation?.mode && recommendation.mode !== 'stealth' ? (
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Badge variant="outline" className="text-[8px] border-accent/40 text-accent bg-accent/10 px-1.5 py-0 capitalize cursor-help transition-all hover:bg-accent/20">
                                    ADAPTING TO {recommendation.mode} PROFILE
                                  </Badge>
                                </TooltipTrigger>
                                <TooltipContent side="top" className="max-w-[240px] border-accent/30 bg-black/90 p-3 shadow-[0_0_20px_rgba(0,255,170,0.1)]">
                                  <div className="space-y-1.5">
                                    <div className="flex items-center gap-1.5 text-accent font-bold text-[10px] uppercase tracking-wider">
                                      <Lightning size={12} weight="fill" />
                                      {recommendation.mode} Mode Active
                                    </div>
                                    <p className="text-[10px] text-muted-foreground leading-relaxed italic">
                                      "Market is currently high-risk. I'm being extra picky with trades—waiting for perfect signals and double-checking volume to ensure we don't get trapped by fake moves. Prioritizing safety over speed."
                                    </p>
                                  </div>
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          ) : (
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Badge variant="outline" className="text-[8px] border-purple-500/30 text-purple-300/80 bg-purple-500/10 px-1.5 py-0 cursor-help">
                                    LOCKED
                                  </Badge>
                                </TooltipTrigger>
                                <TooltipContent side="top" className="bg-black/90 border-purple-500/30 text-[10px] p-2">
                                  Stealth engine is in standard autonomous mode.
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          )}
                        </div>
                        <ShieldCheck size={18} className="text-accent/40" />
                      </div>
                      <p className="text-[11px] text-muted-foreground/80 leading-relaxed mb-3">
                        Stealth is the optimal paper trading engine — it covers the full timeframe range (D→5m) and adaptively selects between scalp, intraday, and swing setups based on what the market structure dictates.
                      </p>
                      <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
                        <div className="text-center p-2 rounded-lg bg-black/30 border border-border/30">
                          <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">R:R Min</div>
                          <div className="text-sm font-mono font-bold text-accent">1.8</div>
                        </div>
                        <div className="text-center p-2 rounded-lg bg-black/30 border border-border/30">
                          <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">Range</div>
                          <div className="text-sm font-mono font-bold text-foreground">D→5m</div>
                        </div>
                        <div className="text-center p-2 rounded-lg bg-black/30 border border-border/30">
                          <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">Direction</div>
                          <div className="text-sm font-mono font-bold text-foreground">L + S</div>
                        </div>
                        <div className="text-center p-2 rounded-lg bg-black/30 border border-border/30">
                          <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">Types</div>
                          <div className="text-sm font-mono font-bold text-foreground">Scalp / Intraday / Swing</div>
                        </div>
                        <div className="text-center p-2 rounded-lg bg-black/30 border border-border/30">
                          <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">Scan Every</div>
                          <div className="text-sm font-mono font-bold text-accent">{config.scan_interval_minutes ?? 2}m</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* ── Execution Mode Toggle ── */}
                  <div className="glass-card glow-border-green p-6 lg:p-10 rounded-3xl relative overflow-hidden group transition-all duration-500 hover:shadow-[0_0_50px_rgba(0,255,170,0.15)]">
                    {/* Cinematic background glow */}
                    <div className={cn(
                      'absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] opacity-40 pointer-events-none transition-opacity duration-1000 group-hover:opacity-60',
                      config.use_testnet ? 'from-yellow-500/10 via-transparent to-transparent' : 'from-green-500/10 via-transparent to-transparent',
                    )} />
                    <div className={cn(
                      'absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent to-transparent opacity-60 transition-all duration-500',
                      config.use_testnet ? 'via-yellow-400/60' : 'via-[#00ff88]/60',
                    )} />

                    <div className="relative z-10 flex flex-col items-center gap-6 text-center">
                      {/* Mode picker pills */}
                      <div className="flex items-center gap-1 bg-black/40 p-1.5 rounded-xl border border-white/5 backdrop-blur-md">
                        <button
                          onClick={() => setConfig({ ...config, use_testnet: false })}
                          className={cn(
                            'flex items-center gap-2 px-6 py-2.5 rounded-lg font-bold tracking-wider transition-all duration-300',
                            !config.use_testnet
                              ? 'bg-accent/20 text-accent shadow-[0_0_15px_rgba(0,255,136,0.3)] border border-accent/40'
                              : 'text-muted-foreground hover:text-white hover:bg-white/5',
                          )}
                        >
                          <Cpu size={18} weight={!config.use_testnet ? 'fill' : 'bold'} />
                          SIMULATION
                        </button>
                        <button
                          onClick={() => setConfig({ ...config, use_testnet: true })}
                          className={cn(
                            'flex items-center gap-2 px-6 py-2.5 rounded-lg font-bold tracking-wider transition-all duration-300',
                            config.use_testnet
                              ? 'bg-yellow-500/20 text-yellow-300 shadow-[0_0_15px_rgba(234,179,8,0.3)] border border-yellow-500/40'
                              : 'text-muted-foreground hover:text-white hover:bg-white/5',
                          )}
                        >
                          <TestTube size={18} weight={config.use_testnet ? 'fill' : 'bold'} />
                          TESTNET
                        </button>
                      </div>

                      {/* Big mode name */}
                      <div className="space-y-2">
                        <h2 className={cn(
                          'text-5xl lg:text-7xl font-black italic tracking-tighter text-transparent bg-clip-text drop-shadow-[0_4px_4px_rgba(0,0,0,0.5)]',
                          config.use_testnet
                            ? 'bg-gradient-to-b from-white via-yellow-50 to-yellow-400/80'
                            : 'bg-gradient-to-b from-white via-green-50 to-green-400/80',
                        )}>
                          {config.use_testnet ? 'TESTNET' : 'SIMULATED'}
                        </h2>
                        <div className={cn(
                          'h-1 w-24 mx-auto bg-gradient-to-r from-transparent to-transparent rounded-full',
                          config.use_testnet ? 'via-yellow-500/50' : 'via-green-500/50',
                        )} />
                      </div>

                      {/* Description */}
                      <p className="text-lg text-green-100/70 max-w-md mx-auto leading-relaxed font-light">
                        {config.use_testnet
                          ? '"Real Phemex order book fills, paper account. The most accurate way to validate a strategy."'
                          : '"Internal fill math with realistic fee & slippage simulation. No API keys needed — run anywhere."'}
                      </p>

                      {/* Warning / API hint for testnet */}
                      {config.use_testnet && (
                        <div className="flex items-center gap-2 text-yellow-400 bg-yellow-400/10 px-4 py-2 rounded-lg text-sm border border-yellow-400/20">
                          <TestTube size={16} />
                          Requires PHEMEX_API_KEY + PHEMEX_API_SECRET in .env
                        </div>
                      )}

                      {/* Active badge */}
                      <div className={cn(
                        'flex items-center gap-3 px-8 py-3 rounded-full border font-bold tracking-widest',
                        config.use_testnet
                          ? 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30 shadow-[0_0_20px_rgba(234,179,8,0.1)]'
                          : 'text-[#00ff88] bg-[#00ff88]/10 border-[#00ff88]/30 shadow-[0_0_20px_rgba(0,255,136,0.1)]',
                      )}>
                        {config.use_testnet ? <TestTube size={20} weight="fill" /> : <Cpu size={20} weight="fill" />}
                        <span>MODE ACTIVE</span>
                      </div>
                    </div>
                  </div>

                  {/* ── Parameters Grid ── */}
                  <div className="space-y-1.5 text-left">
                    <div className="text-[10px] text-accent font-bold uppercase tracking-widest pl-1 mb-2">Session Parameters</div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      
                      {/* Starting Balance */}
                      <div className="space-y-2">
                        <div className="flex items-center justify-between h-4 mb-0.5">
                          <label className="text-[10px] text-muted-foreground uppercase tracking-widest pl-1">Starting Balance ($)</label>
                        </div>
                        <input
                          type="number"
                          value={config.initial_balance}
                          onChange={e => setConfig({ ...config, initial_balance: Number(e.target.value) })}
                          className="w-full h-12 bg-background border border-border rounded-lg px-4 font-mono text-center text-lg focus:outline-none focus:border-accent/40 text-foreground"
                        />
                        <div className="flex gap-1.5">
                          {[1000, 5000, 10000, 50000].map(preset => (
                            <button
                              key={preset}
                              onClick={() => setConfig({ ...config, initial_balance: preset })}
                              className={cn(
                                "flex-1 py-1 rounded text-[9px] font-mono font-bold tracking-tight border transition-all",
                                config.initial_balance === preset
                                  ? "bg-accent/15 border-accent/50 text-accent"
                                  : "bg-black/30 border-border/40 text-muted-foreground/60 hover:border-border hover:text-muted-foreground"
                              )}
                            >
                              {preset >= 1000 ? `${preset / 1000}k` : preset}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Leverage */}
                      <div className="space-y-2">
                        <div className="flex items-center justify-between h-4 mb-0.5">
                          <label className="text-[10px] text-muted-foreground uppercase tracking-widest pl-1">Leverage (x)</label>
                        </div>
                        <input
                          type="number"
                          min="1"
                          max="100"
                          value={config.leverage}
                          onChange={e => setConfig({ ...config, leverage: Number(e.target.value) })}
                          className="w-full h-12 bg-background border border-border rounded-lg px-4 font-mono text-center text-lg focus:outline-none focus:border-accent/40 text-foreground"
                        />
                        <div className="flex gap-1.5">
                          {[1, 5, 10, 20].map(preset => (
                            <button
                              key={preset}
                              onClick={() => setConfig({ ...config, leverage: preset })}
                              className={cn(
                                "flex-1 py-1 rounded text-[9px] font-mono font-bold tracking-tight border transition-all",
                                config.leverage === preset
                                  ? "bg-accent/15 border-accent/50 text-accent"
                                  : "bg-black/30 border-border/40 text-muted-foreground/60 hover:border-border hover:text-muted-foreground"
                              )}
                            >
                              {preset}x
                            </button>
                          ))}
                        </div>
                        {(() => {
                          const exposure = (config.leverage ?? 1) * (config.risk_per_trade ?? 2);
                          const color = exposure >= 20 ? 'text-red-400' : exposure >= 10 ? 'text-yellow-400' : 'text-muted-foreground/50';
                          return (
                            <p className={`text-[9px] font-mono pl-1 leading-snug ${color}`}>
                              Effective exposure per trade: {exposure.toFixed(1)}%
                            </p>
                          );
                        })()}
                      </div>

                      {/* Risk Per Trade */}
                      <div className="space-y-2">
                        <div className="flex items-center justify-between h-4 mb-0.5">
                          <label className="text-[10px] text-muted-foreground uppercase tracking-widest pl-1">Risk Per Trade (%)</label>
                        </div>
                        <input
                          type="number"
                          min="0.1"
                          max="10"
                          step="0.5"
                          value={config.risk_per_trade ?? 2}
                          onChange={e => setConfig({ ...config, risk_per_trade: Number(e.target.value) })}
                          className="w-full h-12 bg-background border border-border rounded-lg px-4 font-mono text-center text-lg focus:outline-none focus:border-accent/40 text-foreground"
                        />
                        <div className="flex gap-1.5">
                          {[0.5, 1, 2, 3].map(preset => (
                            <button
                              key={preset}
                              onClick={() => setConfig({ ...config, risk_per_trade: preset })}
                              className={cn(
                                "flex-1 py-1 rounded text-[9px] font-mono font-bold tracking-tight border transition-all",
                                config.risk_per_trade === preset
                                  ? "bg-accent/15 border-accent/50 text-accent"
                                  : "bg-black/30 border-border/40 text-muted-foreground/60 hover:border-border hover:text-muted-foreground"
                              )}
                            >
                              {preset}%
                            </button>
                          ))}
                        </div>
                        <p className="text-[9px] text-muted-foreground/40 font-mono pl-1 leading-snug">% of balance risked per entry across 3 scale-in levels</p>
                      </div>

                      {/* Duration */}
                      <div className="space-y-2">
                        <div className="flex items-center justify-between h-4 mb-0.5">
                          <label className="text-[10px] text-muted-foreground uppercase tracking-widest pl-1">Session Duration (h)</label>
                        </div>
                        <input
                          type="number"
                          min="1"
                          max="720"
                          value={config.duration_hours}
                          onChange={e => setConfig({ ...config, duration_hours: Number(e.target.value) })}
                          className="w-full h-12 bg-background border border-border rounded-lg px-4 font-mono text-center text-lg focus:outline-none focus:border-accent/40 text-foreground"
                        />
                        <div className="flex gap-1.5">
                          {[8, 24, 72, 168].map(preset => (
                            <button
                              key={preset}
                              onClick={() => setConfig({ ...config, duration_hours: preset })}
                              className={cn(
                                "flex-1 py-1 rounded text-[9px] font-mono font-bold tracking-tight border transition-all",
                                config.duration_hours === preset
                                  ? "bg-accent/15 border-accent/50 text-accent"
                                  : "bg-black/30 border-border/40 text-muted-foreground/60 hover:border-border hover:text-muted-foreground"
                              )}
                            >
                              {preset >= 168 ? '1w' : preset >= 72 ? '3d' : `${preset}h`}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Signal Sensitivity */}
                      <div className="space-y-2 md:col-span-2">
                        <div className="flex justify-between items-center h-4 mb-0.5">
                          <label className="text-[10px] text-muted-foreground uppercase tracking-widest pl-1">Signal Sensitivity</label>
                          <span className="text-[8px] text-muted-foreground/50 font-mono italic">gate / floor / near-miss</span>
                        </div>
                        <div className="flex gap-1.5">
                          {([
                            { key: 'conservative', label: 'Conservative', gate: 72, floor: 62, color: 'blue' },
                            { key: 'balanced',     label: 'Balanced',     gate: 65, floor: 55, color: 'emerald' },
                            { key: 'aggressive',   label: 'Aggressive',   gate: 58, floor: 48, color: 'orange' },
                            { key: 'custom',       label: 'Custom',       gate: null, floor: null, color: 'purple' },
                          ] as const).map(({ key, label, gate, floor, color }) => {
                            const isSelected = (config.sensitivity_preset ?? 'balanced') === key;
                            const selectedCls = {
                              blue:    'bg-blue-500/15 border-blue-500/60 text-blue-400',
                              emerald: 'bg-emerald-500/15 border-emerald-500/60 text-emerald-400',
                              orange:  'bg-orange-500/15 border-orange-500/60 text-orange-400',
                              purple:  'bg-purple-500/15 border-purple-500/60 text-purple-400',
                            }[color];
                            return (
                              <button
                                key={key}
                                onClick={() => setConfig({
                                  ...config,
                                  sensitivity_preset: key,
                                  min_confluence: key === 'custom' ? (config.min_confluence ?? 65) : null,
                                  confluence_soft_floor: key === 'custom' ? (config.confluence_soft_floor ?? 55) : null,
                                })}
                                className={cn(
                                  "flex-1 py-1.5 rounded text-[9px] font-mono font-bold tracking-tight border transition-all flex flex-col items-center gap-0.5",
                                  isSelected ? selectedCls : "bg-black/30 border-border/40 text-muted-foreground/60 hover:border-border hover:text-muted-foreground"
                                )}
                              >
                                <span>{label}</span>
                                {gate !== null && <span className="opacity-60 text-[8px]">{gate}/{floor}</span>}
                              </button>
                            );
                          })}
                        </div>
                        {/* Custom gate/floor inputs */}
                        {(config.sensitivity_preset ?? 'balanced') === 'custom' && (
                          <div className="flex gap-3 mt-1">
                            <div className="flex-1 space-y-1">
                              <label className="text-[9px] text-purple-400/70 uppercase tracking-widest pl-0.5">Gate % (full size)</label>
                              <input
                                type="number" min="40" max="100"
                                value={config.min_confluence ?? 65}
                                onChange={e => setConfig({ ...config, min_confluence: Number(e.target.value) || 65 })}
                                className="w-full h-10 bg-background border border-purple-500/30 rounded-lg px-3 font-mono text-center text-base focus:outline-none focus:border-purple-400/60 text-foreground"
                              />
                            </div>
                            <div className="flex-1 space-y-1">
                              <label className="text-[9px] text-purple-400/70 uppercase tracking-widest pl-0.5">Floor % (half size)</label>
                              <input
                                type="number" min="30" max="100"
                                value={config.confluence_soft_floor ?? 55}
                                onChange={e => setConfig({ ...config, confluence_soft_floor: Number(e.target.value) || 55 })}
                                className="w-full h-10 bg-background border border-purple-500/30 rounded-lg px-3 font-mono text-center text-base focus:outline-none focus:border-purple-400/60 text-foreground"
                              />
                            </div>
                          </div>
                        )}
                        {/* Description line */}
                        <p className="text-[9px] text-muted-foreground/40 font-mono pl-1 leading-snug">
                          {config.sensitivity_preset === 'conservative' ? 'Highest-conviction only — 2–5 trades/week' :
                           config.sensitivity_preset === 'aggressive'   ? 'Wider net, more near-misses — 10–20+ trades/week' :
                           config.sensitivity_preset === 'custom'       ? 'Score ≥ gate → 100% size · floor ≤ score < gate → 50% size' :
                           'Good setups full size, near-misses half size — 5–12 trades/week'}
                        </p>
                      </div>

                      {/* Max Trade Duration */}
                      <div className="space-y-2">
                        <div className="flex items-center justify-between h-4 mb-0.5">
                          <label className="text-[10px] text-muted-foreground uppercase tracking-widest pl-1">Max Trade Duration (h)</label>
                        </div>
                        <input
                          type="number"
                          min="1"
                          max="720"
                          value={config.max_hours_open}
                          onChange={e => setConfig({ ...config, max_hours_open: Number(e.target.value) })}
                          className="w-full h-12 bg-background border border-border rounded-lg px-4 font-mono text-center text-lg focus:outline-none focus:border-accent/40 text-foreground"
                        />
                        <div className="flex gap-1.5">
                          {[24, 48, 72, 168].map(preset => (
                            <button
                              key={preset}
                              onClick={() => setConfig({ ...config, max_hours_open: preset })}
                              className={cn(
                                "flex-1 py-1 rounded text-[9px] font-mono font-bold tracking-tight border transition-all",
                                config.max_hours_open === preset
                                  ? "bg-accent/15 border-accent/50 text-accent"
                                  : "bg-black/30 border-border/40 text-muted-foreground/60 hover:border-border hover:text-muted-foreground"
                              )}
                            >
                              {preset}h
                            </button>
                          ))}
                        </div>
                        <p className="text-[9px] text-muted-foreground/40 font-mono pl-1 leading-snug tracking-tighter">Auto-closes any trade that hasn't exited after this period</p>
                      </div>

                      {/* Max Drawdown Kill Switch */}
                      <div className="space-y-2">
                        <div className="flex items-center justify-between h-4 mb-0.5">
                          <label className="text-[10px] text-red-400/80 uppercase tracking-widest pl-1">Max Drawdown Limit (%)</label>
                        </div>
                        <input
                          type="number"
                          min="1"
                          max="100"
                          value={config.max_drawdown_pct ?? ''}
                          placeholder="NONE"
                          onChange={e => setConfig({ ...config, max_drawdown_pct: e.target.value === '' ? null : Number(e.target.value) })}
                          className="w-full h-12 bg-background border border-red-500/20 rounded-lg px-4 font-mono text-center text-lg focus:outline-none focus:border-red-400/40 text-foreground placeholder:text-muted-foreground/30"
                        />
                        <div className="flex gap-1.5">
                          {[{ l: 'OFF', v: null }, { l: '10%', v: 10 }, { l: '15%', v: 15 }, { l: '25%', v: 25 }].map(({ l, v }) => (
                            <button
                              key={l}
                              onClick={() => setConfig({ ...config, max_drawdown_pct: v })}
                              className={cn(
                                "flex-1 py-1 rounded text-[9px] font-mono font-bold tracking-tight border transition-all",
                                config.max_drawdown_pct === v
                                  ? "bg-red-500/15 border-red-500/50 text-red-400"
                                  : "bg-black/30 border-border/40 text-muted-foreground/60 hover:border-border hover:text-muted-foreground"
                              )}
                            >
                              {l}
                            </button>
                          ))}
                        </div>
                        <p className="text-[9px] text-muted-foreground/40 font-mono pl-1 leading-snug tracking-tighter">Stop session if balance drops by this % from start</p>
                      </div>

                      {/* Scan Interval */}
                      <div className="space-y-2">
                        <div className="flex items-center justify-between h-4 mb-0.5">
                          <label className="text-[10px] text-muted-foreground uppercase tracking-widest pl-1">Scan Every (m)</label>
                          <div className="text-[8px] text-accent/60 border border-accent/20 bg-accent/5 px-1.5 py-0 rounded">
                            Suggested: 2m
                          </div>
                        </div>
                        <input
                          type="number"
                          min="1"
                          max="60"
                          value={config.scan_interval_minutes}
                          onChange={e => setConfig({ ...config, scan_interval_minutes: Number(e.target.value) })}
                          className="w-full h-12 bg-background border border-border rounded-lg px-4 font-mono text-center text-lg focus:outline-none focus:border-accent/40 text-foreground"
                        />
                        <div className="flex gap-1.5">
                          {[2, 5, 15, 30].map(m => (
                            <button
                              key={m}
                              onClick={() => setConfig({ ...config, scan_interval_minutes: m })}
                              className={cn(
                                "flex-1 py-1 rounded text-[9px] font-mono font-bold tracking-tight border transition-all",
                                config.scan_interval_minutes === m
                                  ? "bg-accent/15 border-accent/50 text-accent"
                                  : "bg-black/30 border-border/40 text-muted-foreground/60 hover:border-border hover:text-muted-foreground"
                              )}
                            >
                              {m}m
                            </button>
                          ))}
                        </div>
                        <p className="text-[9px] text-muted-foreground/40 font-mono pl-1 leading-snug tracking-tighter">Fast scans (2-5m) catch Scalp entries on lower timeframes</p>
                      </div>

                      {/* Max Assets */}
                      <div className="space-y-2">
                        <div className="flex items-center justify-between h-4 mb-0.5">
                          <label className="text-[10px] text-muted-foreground uppercase tracking-widest pl-1">Max Concurrent Assets</label>
                          <div className="text-[8px] text-accent/60 border border-accent/20 bg-accent/5 px-1.5 py-0 rounded">
                            Suggested: 3
                          </div>
                        </div>
                        <input
                          type="number"
                          min="1"
                          max="10"
                          value={config.max_positions}
                          onChange={e => setConfig({ ...config, max_positions: Number(e.target.value) })}
                          className="w-full h-12 bg-background border border-border rounded-lg px-4 font-mono text-center text-lg focus:outline-none focus:border-accent/40 text-foreground"
                        />
                        <div className="flex gap-1.5">
                          {[1, 3, 5, 10].map(v => (
                            <button
                              key={v}
                              onClick={() => setConfig({ ...config, max_positions: v })}
                              className={cn(
                                "flex-1 py-1 rounded text-[9px] font-mono font-bold tracking-tight border transition-all",
                                config.max_positions === v
                                  ? "bg-accent/15 border-accent/50 text-accent"
                                  : "bg-black/30 border-border/40 text-muted-foreground/60 hover:border-border hover:text-muted-foreground"
                              )}
                            >
                              {v}
                            </button>
                          ))}
                        </div>
                        <p className="text-[9px] text-muted-foreground/40 font-mono pl-1 leading-snug tracking-tighter">Limit of concurrent active symbol slots (Positions + Pending)</p>
                      </div>
                    </div>
                  </div>

                  {/* Symbol Selection UI */}
                  <div className="bg-background/40 border border-border/50 rounded-xl p-4 space-y-4">
                    <div className="flex items-center justify-between">
                      <label className="text-[10px] text-accent font-bold uppercase tracking-widest pl-1">Target Asset Buckets</label>
                      <span className="text-[9px] text-muted-foreground font-mono italic">Volume adaptive</span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <div
                              onClick={() => setConfig({ ...config, majors: !config.majors })}
                              className={cn(
                                "flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg border cursor-pointer transition-all",
                                config.majors ? "bg-accent/10 border-accent text-accent shadow-[0_0_10px_rgba(0,255,170,0.1)]" : "bg-black/20 border-border text-muted-foreground opacity-60 grayscale"
                              )}
                            >
                              <Trophy size={16} weight={config.majors ? "fill" : "regular"} />
                              <span className="text-xs font-mono font-bold tracking-tight">MAJORS</span>
                            </div>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="bg-black/90 border-border text-[10px] p-2 max-w-[200px]">
                            BTC, ETH, SOL, BNB, XRP, ADA, DOGE, AVAX, DOT, LINK
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>

                      <div
                        onClick={() => setConfig({ ...config, altcoins: !config.altcoins })}
                        className={cn(
                          "flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg border cursor-pointer transition-all",
                          config.altcoins ? "bg-primary/10 border-primary text-primary shadow-[0_0_10px_rgba(59,130,246,0.1)]" : "bg-black/20 border-border text-muted-foreground opacity-60 grayscale"
                        )}
                      >
                        <ChartLine size={16} weight={config.altcoins ? "fill" : "regular"} />
                        <span className="text-xs font-mono font-bold tracking-tight">ALTS</span>
                      </div>

                      <div
                        onClick={() => setConfig({ ...config, meme_mode: !config.meme_mode })}
                        className={cn(
                          "flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg border cursor-pointer transition-all",
                          config.meme_mode ? "bg-purple-500/10 border-purple-500 text-purple-400 shadow-[0_0_10px_rgba(168,85,247,0.1)]" : "bg-black/20 border-border text-muted-foreground opacity-60 grayscale"
                        )}
                      >
                        <Crosshair size={16} weight={config.meme_mode ? "fill" : "regular"} />
                        <span className="text-xs font-mono font-bold tracking-tight">MEME HUNTER</span>
                      </div>
                    </div>

                    <div className="pt-2 border-t border-border/30">
                      <label className="text-[10px] text-muted-foreground uppercase tracking-widest mb-2 block font-mono">Custom symbols (comma separated)</label>
                      <input
                        type="text"
                        placeholder="e.g. BTC/USDT, ETH/USDT, LINK/USDT"
                        value={config.symbols?.join(', ') || ''}
                        onChange={(e) => {
                          const syms = e.target.value.split(',').map(s => s.trim().toUpperCase()).filter(s => s.length > 0);
                          setConfig({ ...config, symbols: syms });
                        }}
                        className="w-full h-10 bg-black/40 border border-border rounded-md px-3 font-mono text-xs focus:outline-none focus:border-accent/40 placeholder:text-muted-foreground/30 text-foreground"
                      />
                    </div>
                  </div>
                  <p className="text-center text-[10px] text-muted-foreground/40 font-mono italic">
                    Simulated execution only — no real funds at risk
                  </p>
                  <Button
                    onClick={handleStart}
                    disabled={isLoading}
                    className="w-full h-14 bg-[#00ff88] hover:bg-[#00cc6a] text-black font-bold tracking-widest text-lg border-2 border-white/20 shadow-[0_0_30px_rgba(0,255,136,0.4)] hover:shadow-[0_0_50px_rgba(0,255,136,0.6)] hover:scale-105 transition-all duration-300 relative overflow-hidden group/btn"
                  >
                    <div className="absolute inset-0 bg-white/40 skew-x-12 -translate-x-full group-hover/btn:animate-shimmer" />
                    {isLoading ? <ArrowsClockwise size={20} className="animate-spin mr-2" /> : <PlayCircle size={24} weight="fill" className="mr-2" />}
                    {isLoading ? 'ARMING...' : 'ARM PHANTOM'}
                  </Button>
                </div>
              </div>
            </section>
          </div>
        ) : (
          <div className="space-y-6 mt-6">
            {/* Control Bar */}
            <section className="glass-card glow-border-green rounded-2xl relative overflow-hidden group">
              <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-green-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />
              <div className="p-4 flex items-center justify-between relative z-10">
                <div className="flex-1 flex items-center justify-between max-w-[80%] mr-12">
                  {/* Session Info */}
                  <div>
                    <div className="text-xs text-[#00ff88] uppercase tracking-widest font-mono font-bold">SESSION</div>
                    <div className="mt-1 font-mono text-sm tracking-widest glow-border-green px-2 py-0.5 rounded bg-black/40 flex items-center gap-2">
                      {status?.session_id || '—'}
                      <Badge variant="outline" className="text-[9px] h-4 border-purple-500/30 text-purple-400 font-black bg-purple-500/10">
                        STEALTH
                      </Badge>
                    </div>
                  </div>

                  {/* Uptime */}
                  <div>
                    <div className="text-xs text-muted-foreground uppercase tracking-widest font-mono">UPTIME</div>
                    <div className="mt-1 font-mono text-sm flex items-center gap-1 tracking-widest">
                      <Clock size={14} />
                      {formatDuration(status?.uptime_seconds || 0)}
                    </div>
                  </div>

                  {/* Next Scan */}
                  {isRunning && status?.next_scan_in_seconds !== null && (
                    <div>
                      <div className="text-xs text-yellow-400/80 uppercase tracking-widest font-mono font-bold">NEXT SCAN</div>
                      <div className="mt-1 font-mono text-sm flex items-center gap-1 text-yellow-500 tracking-widest">
                        <Target size={14} className="animate-pulse shadow-[0_0_8px_rgba(234,179,8,0.8)]" />
                        {formatDuration(Math.round(status.next_scan_in_seconds))}
                      </div>
                    </div>
                  )}

                  {/* Cache Hit Rate */}
                  {status?.cache_stats && (
                    <div>
                      <div className="text-xs text-muted-foreground uppercase tracking-widest font-mono">CACHE</div>
                      <div className={cn(
                        "mt-1 font-mono text-sm tracking-widest",
                        status.cache_stats.hit_rate_pct > 50 ? 'text-green-400' : 'text-yellow-400'
                      )}>
                        {status.cache_stats.hit_rate_pct.toFixed(0)}% <span className="text-xs opacity-50">hit</span>
                      </div>
                    </div>
                  )}

                  {/* Mode / Regime */}
                  <div>
                    <div className="text-xs text-muted-foreground uppercase tracking-widest font-mono">
                      {status?.config?.sniper_mode === 'stealth' ? 'ADAPTIVE MODE' : 'MODE'}
                    </div>
                    <div className="flex gap-1.5 mt-1">
                      <Badge variant="outline" className={cn(
                        "font-mono text-xs tracking-widest",
                        (status?.active_mode || status?.current_scan?.actual_mode) && (status?.active_mode || status?.current_scan?.actual_mode) !== (status?.config?.sniper_mode || 'stealth')
                          ? "border-purple-500 text-purple-400 bg-purple-500/10"
                          : "border-accent text-accent bg-accent/10"
                      )}>
                        {(status?.active_mode || status?.current_scan?.actual_mode || status?.config?.sniper_mode || 'ADAPTIVE').toUpperCase()}
                      </Badge>
                      {status?.active_profile && status.active_profile !== 'stealth' && (
                        <Badge variant="outline" className="font-mono text-xs tracking-widest border-yellow-500/50 text-yellow-400 bg-yellow-500/10">
                          {(status.active_profile || '').toUpperCase()}
                        </Badge>
                      )}
                    </div>
                  </div>

                  {/* Market Regime */}
                  {status?.regime && status.regime.composite !== 'unknown' && (
                    <div>
                      <div className="text-xs text-muted-foreground uppercase tracking-widest font-mono">
                        MARKET REGIME
                      </div>
                      <div className="mt-1 flex items-center gap-2">
                        <span className={cn(
                          "font-mono text-sm font-bold tracking-tight",
                          status.regime.trend.includes('up') ? 'text-green-400' : status.regime.trend.includes('down') ? 'text-red-400' : 'text-blue-400'
                        )}>
                          {status.regime.trend.toUpperCase()}
                        </span>
                        <span className="text-muted-foreground/30 font-mono text-xs">—</span>
                        <span className="text-xs font-mono text-muted-foreground/80 uppercase">
                          {status.regime.volatility}
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Confluence Gate */}
                  <div>
                    <div className="text-xs text-muted-foreground uppercase tracking-widest font-mono">
                      GATE
                    </div>
                    <div className="mt-1 font-mono text-sm tracking-widest text-yellow-400 font-bold">
                      {status?.config?.min_confluence != null ? `≥ ${status.config.min_confluence}%` : 'AUTO'}
                    </div>
                  </div>
                </div>

                {/* Control Buttons */}
                <div className="flex gap-3">
                  {isRunning ? (
                    <Button
                      onClick={handleStop}
                      disabled={isLoading}
                      variant="destructive"
                      size="sm"
                    >
                      <StopCircle size={18} className="mr-1" />
                      STOP
                    </Button>
                  ) : (
                    <>
                      <Button
                        onClick={handleStart}
                        disabled={isLoading || isRunning}
                        size="sm"
                        className="bg-accent hover:bg-accent/90"
                      >
                        <PlayCircle size={18} className="mr-1" />
                        START
                      </Button>
                      <Button
                        onClick={handleReset}
                        disabled={isLoading || isRunning}
                        variant="outline"
                        size="sm"
                      >
                        <ArrowsClockwise size={18} className="mr-1" />
                        RESET
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </section>

            {/* Active/Last Scan Progress */}
            {status?.current_scan && (
              <section className={cn("glass-card rounded-2xl relative overflow-hidden group p-4 border", status.current_scan.status === 'running' ? "glow-border-amber border-amber-500/30" : "glow-border-green border-green-500/30")}>
                <div className={cn("absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] via-transparent to-transparent opacity-40 pointer-events-none", status.current_scan.status === 'running' ? 'from-amber-500/10' : 'from-green-500/10')} />
                <div className={cn("absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent to-transparent opacity-50", status.current_scan.status === 'running' ? "via-amber-400/50" : "via-green-400/50")} />
                <div className="space-y-3 relative z-10">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Target size={18} className={cn("text-accent", status.current_scan.status === 'running' ? "animate-pulse" : "text-green-400")} />
                      <h3 className="heading-hud text-sm text-foreground uppercase tracking-widest">
                        {status.current_scan.status === 'running' ? 'Scan in Progress' : 'Last Scan'}
                      </h3>
                      <Badge variant="outline" className="ml-2 font-mono text-[10px] bg-background">
                        {status.current_scan.completed} / {status.current_scan.total}
                      </Badge>
                    </div>
                    <div className="text-xs font-mono text-muted-foreground uppercase tracking-widest">
                      {status.current_scan.progress_pct}%
                    </div>
                  </div>

                  <Progress value={status.current_scan.progress_pct} className="h-1.5" />

                  <div className="flex justify-between items-center text-xs font-mono">
                    <div className="text-muted-foreground">
                      <span className="text-foreground mr-1">Scanning:</span>
                      {status.current_scan.status === 'running'
                        ? (status.current_scan.current_symbol || 'Initializing...')
                        : 'Completed'}
                    </div>
                    <div className="flex gap-3">
                      <span className="text-green-400">{status.current_scan.passed} Passed</span>
                      <span className="text-red-400">{status.current_scan.rejected} Rejected</span>
                    </div>
                  </div>

                  {/* Recent symbols ticker */}
                  {status.current_scan.recent_symbols && status.current_scan.recent_symbols.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-border/50 flex gap-6 overflow-hidden overflow-x-auto no-scrollbar">
                      {status.current_scan.recent_symbols.map((item, idx) => (
                        <div
                          key={`${item.symbol}-${idx}`}
                          className={cn(
                            "text-[10px] font-mono px-2 py-1 rounded whitespace-nowrap",
                            item.passed ? "bg-green-500/10 text-green-400" : "bg-muted/40 text-muted-foreground"
                          )}
                          title={item.reason || 'Passed'}
                        >
                          {item.passed ? <CheckCircle size={10} className="inline mr-1" /> : <XCircle size={10} className="inline mr-1 opacity-50" />}
                          {item.symbol}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* Equity Curve + Stats Row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Equity Curve Card (spans 2 cols) */}
              <div className="lg:col-span-2 glass-card p-5 rounded-2xl border-accent/30 relative group">
                <div className="absolute top-0 right-0 w-32 h-32 bg-[radial-gradient(circle,_var(--tw-gradient-stops))] from-accent/5 to-transparent rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none -mr-16 -mt-16" />
                <div className="relative z-10">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex flex-col gap-1 items-start">
                      <div>
                        <div className="text-[9px] text-muted-foreground font-mono font-bold tracking-wider uppercase opacity-70">EQUITY</div>
                        <div className="text-xl font-bold font-mono tracking-tight glow-text-accent">
                          {formatCurrency(status?.balance?.equity || config.initial_balance || 10000)}
                        </div>
                      </div>
                      <div>
                        <div className="text-[9px] text-muted-foreground font-mono font-bold tracking-wider uppercase opacity-60">AVAILABLE CASH (W/ P&L)</div>
                        <div className="text-sm font-bold font-mono tracking-tight opacity-80">
                          {formatCurrency(status?.balance?.current || config.initial_balance || 10000)}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge
                        variant="outline"
                        className={cn(
                          "font-mono text-xs border tracking-widest",
                          status?.balance?.pnl && status.balance.pnl >= 0
                            ? 'bg-green-500/10 text-green-400 border-green-500/30 glow-border-green'
                            : 'bg-red-500/10 text-red-400 border-red-500/30'
                        )}
                      >
                        {formatPct(status?.balance?.pnl_pct || 0)}
                      </Badge>
                      <Wallet size={28} className="text-accent/40" />
                    </div>
                  </div>
                  {/* Equity Sparkline */}
                  <div className="mt-2 p-2 rounded-lg bg-black/30 border border-border/30">
                    <EquitySparkline
                      trades={trades}
                      initialBalance={status?.balance?.initial || config.initial_balance || 10000}
                    />
                  </div>
                  <div className="mt-2 flex items-center gap-2 text-[10px] text-muted-foreground/50 font-mono">
                    <span>from {formatCurrency(status?.balance?.initial || config.initial_balance || 10000)}</span>
                    <span className="opacity-30">•</span>
                    <span>{trades.length} trades</span>
                  </div>
                </div>
              </div>

              {/* Right column — stacked stats */}
              <div className="flex flex-col gap-4 min-w-0">
                {/* Win Rate Card */}
                <div className="glass-card p-4 rounded-2xl border-border/50 relative group flex-1 min-w-0">
                  <div className="relative z-10 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-[10px] text-muted-foreground font-mono font-bold tracking-wider uppercase">WIN RATE</div>
                        <div className="text-2xl font-bold font-mono tracking-tight mt-0.5">
                          {(status?.statistics?.win_rate || 0).toFixed(1)}%
                        </div>
                      </div>
                      <Trophy size={24} className="text-accent/20 transition-colors group-hover:text-accent/50 shrink-0" />
                    </div>
                    <div className="mt-1.5 text-xs text-muted-foreground opacity-80 flex items-center gap-1.5 flex-wrap">
                      <span className="text-green-400">{status?.statistics?.winning_trades || 0}W</span>
                      <span className="text-white/20">/</span>
                      <span className="text-red-400">{status?.statistics?.losing_trades || 0}L</span>
                      <span className="opacity-20">•</span>
                      <span>{status?.statistics?.total_trades || 0} total</span>
                    </div>
                  </div>
                </div>

                {/* Avg R:R Card */}
                <div className="glass-card p-4 rounded-2xl border-border/50 relative group flex-1 min-w-0">
                  <div className="relative z-10 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-[10px] text-muted-foreground font-mono font-bold tracking-wider uppercase">AVG R:R</div>
                        <div className="text-2xl font-bold font-mono tracking-tight mt-0.5">
                          {(status?.statistics?.avg_rr || 0).toFixed(2)}
                        </div>
                      </div>
                      <Crosshair size={24} className="text-accent/20 transition-colors group-hover:text-amber-400/50 shrink-0" />
                    </div>
                    <div className="mt-1.5 text-xs text-muted-foreground opacity-80 flex flex-col gap-0.5">
                      <span className="text-green-400/80">W: {formatCurrency(status?.statistics?.avg_win || 0)}</span>
                      <span className="text-red-400/80">L: {formatCurrency(status?.statistics?.avg_loss || 0)}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Secondary Stats Row — Max Drawdown, Profit Factor, Scans, Streak */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Max Drawdown */}
              <div className="glass-card p-4 rounded-2xl border-border/50 relative group min-w-0">
                <div className="relative z-10 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-[10px] text-muted-foreground font-mono font-bold tracking-wider uppercase">MAX DRAWDOWN</div>
                      <div className={cn(
                        "text-xl font-bold font-mono tracking-tight mt-0.5",
                        (status?.statistics as any)?.max_drawdown_pct ? 'text-red-400' : 'text-muted-foreground'
                      )}>
                        {((status?.statistics as any)?.max_drawdown_pct || 0).toFixed(2)}%
                      </div>
                    </div>
                    <TrendDown size={24} className="text-red-400/20 transition-colors group-hover:text-red-400/50 shrink-0" />
                  </div>
                  <div className="mt-1.5 text-[10px] text-muted-foreground/60 font-mono">
                    Peak-to-trough
                  </div>
                </div>
              </div>

              {/* Avg Trade P&L */}
              <div className="glass-card p-4 rounded-2xl border-border/50 relative group min-w-0">
                <div className="relative z-10 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-[10px] text-muted-foreground font-mono font-bold tracking-wider uppercase">AVG TRADE</div>
                      {(() => {
                        const totalTrades = status?.statistics?.total_trades || 0;
                        const totalPnl = status?.statistics?.total_pnl || 0;
                        const avg = totalTrades > 0 ? totalPnl / totalTrades : 0;
                        return (
                          <div className={cn(
                            "text-xl font-bold font-mono tracking-tight mt-0.5",
                            avg > 0 ? 'text-green-400' : avg < 0 ? 'text-red-400' : 'text-muted-foreground'
                          )}>
                            {avg >= 0 ? '+' : ''}{formatCurrency(avg)}
                          </div>
                        );
                      })()}
                    </div>
                    <Fire size={24} className="text-amber-400/20 transition-colors group-hover:text-amber-400/50 shrink-0" />
                  </div>
                  <div className="mt-1.5 text-[10px] text-muted-foreground/60 font-mono">
                    Expectancy per trade
                  </div>
                </div>
              </div>

              {/* Scans Card */}
              <div className="glass-card p-4 rounded-2xl border-border/50 relative group min-w-0">
                <div className="relative z-10 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-[10px] text-muted-foreground font-mono font-bold tracking-wider uppercase">SCANS</div>
                      <div className="text-xl font-bold font-mono tracking-tight mt-0.5">
                        {status?.statistics?.scans_completed || 0}
                      </div>
                    </div>
                    <Target size={24} className="text-accent/20 transition-colors group-hover:text-blue-400/50 shrink-0" />
                  </div>
                  <div className="mt-1.5 text-[10px] text-muted-foreground font-mono opacity-80">
                    <span className="text-blue-400/80">{status?.statistics?.signals_generated || 0} sigs</span>
                    <span className="mx-1.5 opacity-20">→</span>
                    <span className="text-green-400/80">{status?.statistics?.signals_taken || 0} tk</span>
                  </div>
                </div>
              </div>

              {/* Current Streak */}
              <div className="glass-card p-4 rounded-2xl border-border/50 relative group min-w-0">
                <div className="relative z-10 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-[10px] text-muted-foreground font-mono font-bold tracking-wider uppercase">STREAK</div>
                      {(() => {
                        // Calculate current streak from trade history
                        let streak = 0;
                        let streakType: 'win' | 'loss' | 'none' = 'none';
                        if (trades.length > 0) {
                          streakType = trades[0].pnl >= 0 ? 'win' : 'loss';
                          for (const t of trades) {
                            if ((t.pnl >= 0 && streakType === 'win') || (t.pnl < 0 && streakType === 'loss')) {
                              streak++;
                            } else break;
                          }
                        }
                        return (
                          <div className={cn(
                            "text-xl font-bold font-mono tracking-tight mt-0.5 flex items-center gap-1.5",
                            streakType === 'win' ? 'text-green-400' : streakType === 'loss' ? 'text-red-400' : 'text-muted-foreground'
                          )}>
                            {streak > 0 && streakType === 'win' && <TrendUp size={18} />}
                            {streak > 0 && streakType === 'loss' && <TrendDown size={18} />}
                            {streak === 0 ? '—' : `${streak}${streakType === 'win' ? 'W' : 'L'}`}
                          </div>
                        );
                      })()}
                    </div>
                    <Lightning size={24} className="text-purple-400/20 transition-colors group-hover:text-purple-400/50 shrink-0" />
                  </div>
                  <div className="mt-1.5 text-[10px] text-muted-foreground/60 font-mono">
                    Current streak
                  </div>
                </div>
              </div>
            </div>

            {/* Breakdown Row — By Trade Type + Exit Reasons */}
            {status?.statistics && (
              (Object.keys(status.statistics.by_trade_type || {}).length > 0 ||
               Object.keys(status.statistics.exit_reasons || {}).length > 0) && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

                {/* By Trade Type */}
                {Object.keys(status.statistics.by_trade_type || {}).length > 0 && (
                  <div className="glass-card p-4 rounded-2xl border-border/50">
                    <div className="text-[10px] text-muted-foreground font-mono font-bold tracking-wider uppercase mb-3">BY TRADE TYPE</div>
                    <div className="flex flex-col gap-2">
                      {((['scalp', 'intraday', 'swing'] as const).filter(tt => status.statistics.by_trade_type?.[tt]).concat(
                        Object.keys(status.statistics.by_trade_type || {}).filter(tt => !['scalp','intraday','swing'].includes(tt)) as any
                      ) as string[]).map(tt => {
                        const b = status.statistics.by_trade_type![tt];
                        if (!b) return null;
                        const color = tt === 'scalp' ? 'text-purple-400' : tt === 'intraday' ? 'text-blue-400' : 'text-amber-400';
                        const pnlColor = b.total_pnl >= 0 ? 'text-green-400' : 'text-red-400';
                        return (
                          <div key={tt} className="flex items-center gap-3 text-xs font-mono">
                            <span className={cn("w-16 font-bold uppercase tracking-tight shrink-0", color)}>{tt}</span>
                            <div className="flex-1 bg-white/5 rounded-full h-1.5 overflow-hidden">
                              <div
                                className={cn("h-full rounded-full", b.win_rate >= 50 ? 'bg-green-400/60' : 'bg-red-400/60')}
                                style={{ width: `${b.win_rate}%` }}
                              />
                            </div>
                            <span className="w-10 text-right text-muted-foreground">{b.win_rate.toFixed(0)}%</span>
                            <span className="w-12 text-right text-muted-foreground/60">{b.trades}T</span>
                            <span className={cn("w-16 text-right", pnlColor)}>{b.total_pnl >= 0 ? '+' : ''}{b.total_pnl.toFixed(1)}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Exit Reasons */}
                {Object.keys(status.statistics.exit_reasons || {}).length > 0 && (
                  <div className="glass-card p-4 rounded-2xl border-border/50">
                    <div className="text-[10px] text-muted-foreground font-mono font-bold tracking-wider uppercase mb-3">EXIT REASONS</div>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(status.statistics.exit_reasons || {})
                        .sort(([, a], [, b]) => b - a)
                        .map(([reason, count]) => {
                          const label = reason === 'stop_loss' ? 'Stop' : reason === 'target' ? 'Target' : reason === 'stagnation' ? 'Stagnation' : reason === 'direction_flip' ? 'Flip' : reason === 'emergency' ? 'Emergency' : reason;
                          const chipColor = reason === 'target' ? 'bg-green-400/15 border-green-400/30 text-green-400' : reason === 'stop_loss' ? 'bg-red-400/15 border-red-400/30 text-red-400' : reason === 'stagnation' ? 'bg-amber-400/15 border-amber-400/30 text-amber-400' : 'bg-white/5 border-border/40 text-muted-foreground';
                          return (
                            <div key={reason} className={cn("flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-mono font-bold", chipColor)}>
                              <span>{label}</span>
                              <span className="opacity-60">×{count}</span>
                            </div>
                          );
                        })}
                    </div>
                  </div>
                )}

              </div>
            ))}

            {/* Positions & Activity Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Active Positions */}
              <section className="glass-card glow-border-green p-5 rounded-2xl h-full flex flex-col relative overflow-hidden group">
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-green-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />

                <div className="flex items-center justify-between mb-6 relative z-10">
                  <h2 className="text-xl lg:text-2xl font-semibold hud-headline hud-text-green tracking-wide flex items-center gap-3">
                    <ChartLine size={24} className="text-accent" />
                    ACTIVE POSITIONS
                  </h2>
                  <Badge variant="outline" className="bg-black/60 font-mono tracking-widest px-3 border-accent/40 text-accent glow-border-green">
                    {status?.positions?.length || 0}
                  </Badge>
                </div>

                <div className="relative z-10 space-y-10 mt-4">
                  {/* Part 1: Active Positions */}
                  {(status?.positions && status.positions.length > 0) ? (
                    <div>
                      <div className="flex items-center gap-3 mb-4">
                        <div className="h-px flex-1 bg-gradient-to-r from-transparent via-green-500/20 to-transparent" />
                        <h3 className="text-[10px] font-black tracking-[0.3em] uppercase text-green-400 drop-shadow-[0_0_8px_rgba(74,222,128,0.3)] bg-green-500/5 px-4 py-1 rounded-full border border-green-500/20">
                          ACTIVE POSITIONS ({status.positions.length})
                        </h3>
                        <div className="h-px flex-1 bg-gradient-to-r from-transparent via-green-500/20 to-transparent" />
                      </div>
                      <div className="space-y-4">
                        {status.positions.map((pos) => (
                          <PositionCard key={pos.position_id} position={pos} />
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {/* Part 2: Pending Orders */}
                  {(status?.pending_orders && status.pending_orders.length > 0) ? (
                    <div>
                      <div className="flex items-center gap-3 mb-4 mt-6">
                        <div className="h-px flex-1 bg-gradient-to-r from-transparent via-amber-500/20 to-transparent" />
                        <h3 className="text-[10px] font-black tracking-[0.3em] uppercase text-amber-400 drop-shadow-[0_0_8px_rgba(251,191,36,0.3)] bg-amber-500/5 px-4 py-1 rounded-full border border-amber-500/20">
                          PENDING LIMIT ORDERS ({status.pending_orders.length})
                        </h3>
                        <div className="h-px flex-1 bg-gradient-to-r from-transparent via-amber-500/20 to-transparent" />
                      </div>
                      <div className="space-y-3">
                        {status.pending_orders.map((order) => (
                          <PendingOrderCard key={order.order_id} order={order} />
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {/* Combined Empty State */}
                  {!(status?.positions?.length) && !(status?.pending_orders?.length) && (
                    <div className="text-center py-20 px-4">
                      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-muted/5 border border-dashed border-muted/20 mb-4">
                        <Target size={32} className="text-muted-foreground/30" />
                      </div>
                      <h3 className="text-lg font-medium text-muted-foreground/80">No market exposure yet</h3>
                      <p className="text-sm text-muted-foreground/40 mt-1 max-w-xs mx-auto">
                        Your bot is currently monitoring {config.symbols?.length ?? 0} symbols for {config.sniper_mode} setups.
                      </p>
                      <p className="text-xs text-muted-foreground/25 mt-2 max-w-xs mx-auto font-mono">
                        In typical conditions, Stealth generates 1–4 entries per 24h session
                      </p>
                    </div>
                  )}
                </div>
              </section>

              {/* Risk & Exposure */}
              <section className="glass-card glow-border-amber p-5 rounded-2xl h-full flex flex-col relative overflow-hidden group">
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-amber-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />
                <div className="flex items-center justify-between mb-5 relative z-10">
                  <h2 className="text-xl lg:text-2xl font-semibold hud-headline hud-text-amber tracking-wide flex items-center gap-3">
                    <ShieldCheck size={24} className="text-amber-400" />
                    RISK &amp; EXPOSURE
                  </h2>
                </div>

                <div className="relative z-10 space-y-4 flex-1">
                  {/* Capital deployed */}
                  {(() => {
                    const positions = status?.positions || [];
                    const equity = status?.balance?.equity || config.initial_balance || 10000;
                    const totalExposure = positions.reduce((sum, p) => sum + (p.entry_price * p.quantity), 0);
                    const exposurePct = equity > 0 ? (totalExposure / equity) * 100 : 0;
                    const maxPositions = config.max_positions ?? 3;
                    const usedPositions = positions.length;
                    const unrealizedPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
                    const riskPerTrade = config.risk_per_trade ?? 2;

                    return (
                      <>
                        <div className="grid grid-cols-2 gap-3">
                          <div className="p-3 rounded-xl bg-background/40 border border-border/30">
                            <div className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest mb-1">POSITIONS</div>
                            <div className="text-2xl font-mono font-bold text-foreground">
                              {usedPositions}<span className="text-sm text-muted-foreground font-normal">/{maxPositions}</span>
                            </div>
                          </div>
                          <div className="p-3 rounded-xl bg-background/40 border border-border/30">
                            <div className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest mb-1">RISK / TRADE</div>
                            <div className="text-2xl font-mono font-bold text-foreground">
                              {riskPerTrade}%
                            </div>
                            <div className="text-[10px] text-muted-foreground font-mono mt-0.5">
                              {formatCurrency(equity * riskPerTrade / 100)} max
                            </div>
                          </div>
                        </div>

                        {/* Exposure bar */}
                        <div className="p-3 rounded-xl bg-background/40 border border-border/30">
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest">CAPITAL DEPLOYED</span>
                            <span className={cn("text-xs font-mono font-bold", exposurePct > 50 ? 'text-amber-400' : 'text-green-400')}>
                              {exposurePct.toFixed(1)}%
                            </span>
                          </div>
                          <div className="h-2 rounded-full bg-black/40 overflow-hidden">
                            <div
                              className={cn(
                                "h-full rounded-full transition-all duration-500",
                                exposurePct > 75 ? 'bg-red-500' : exposurePct > 50 ? 'bg-amber-500' : 'bg-green-500'
                              )}
                              style={{ width: `${Math.min(exposurePct, 100)}%` }}
                            />
                          </div>
                          <div className="text-[10px] text-muted-foreground font-mono mt-1.5">
                            {formatCurrency(totalExposure)} of {formatCurrency(equity)}
                          </div>
                        </div>

                        {/* Unrealized P&L */}
                        <div className="p-3 rounded-xl bg-background/40 border border-border/30">
                          <div className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest mb-1">UNREALIZED P&amp;L</div>
                          <div className={cn(
                            "text-xl font-mono font-bold",
                            unrealizedPnl > 0 ? 'text-green-400' : unrealizedPnl < 0 ? 'text-red-400' : 'text-muted-foreground'
                          )}>
                            {unrealizedPnl >= 0 ? '+' : ''}{formatCurrency(unrealizedPnl)}
                          </div>
                          <div className="text-[10px] text-muted-foreground font-mono mt-0.5">
                            Across {usedPositions} open position{usedPositions !== 1 ? 's' : ''}
                          </div>
                        </div>

                        {/* Per-position heat */}
                        {positions.length > 0 && (
                          <div className="space-y-2 pt-1">
                            <div className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest">POSITION HEAT</div>
                            {positions.map((pos) => (
                              <div key={pos.position_id} className="flex items-center gap-2 text-xs font-mono">
                                <span className={pos.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}>
                                  {pos.direction === 'LONG' ? '↑' : '↓'}
                                </span>
                                <span className="text-foreground/80 w-24 truncate">{pos.symbol}</span>
                                <div className="flex-1 h-1.5 rounded-full bg-black/40 overflow-hidden">
                                  <div
                                    className={cn(
                                      "h-full rounded-full",
                                      (pos.unrealized_pnl || 0) >= 0 ? 'bg-green-500' : 'bg-red-500'
                                    )}
                                    style={{ width: `${Math.min(Math.abs((pos.unrealized_pnl_pct || 0)), 100)}%` }}
                                  />
                                </div>
                                <span className={cn(
                                  "w-16 text-right",
                                  (pos.unrealized_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                                )}>
                                  {(pos.unrealized_pnl || 0) >= 0 ? '+' : ''}{formatCurrency(pos.unrealized_pnl || 0)}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </>
                    );
                  })()}
                </div>
              </section>
            </div>

            {/* Trade History */}
            <section className="glass-card glow-border-amber p-5 rounded-2xl relative overflow-hidden group">
              <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-amber-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />

              <div className="flex items-center justify-between mb-6 relative z-10">
                <h2 className="text-xl lg:text-2xl font-semibold hud-headline hud-text-amber tracking-wide flex items-center gap-3">
                  <ListBullets size={24} className="text-warning" />
                  TRADE HISTORY
                </h2>
                <Badge variant="outline" className="bg-black/60 font-mono tracking-widest px-3 border-amber-500/40 text-amber-500 glow-border-amber">
                  {trades.length} trades
                </Badge>
              </div>

              <div className="relative z-10">
                {trades.length > 0 ? (
                  <div className="space-y-2">
                    {trades.slice(0, 10).map((trade) => (
                      <TradeHistoryItem key={trade.trade_id} trade={trade} />
                    ))}
                    {trades.length > 10 && (
                      <div className="text-center text-sm text-muted-foreground py-2">
                        + {trades.length - 10} more trades
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-12 border border-border border-dashed rounded-lg bg-background/50">
                    <TrendUp size={32} className="mx-auto mb-3 opacity-20 text-warning" />
                    <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground/50">No completed trades yet</p>
                  </div>
                )}
              </div>
            </section>
            {/* Signal Intelligence Panel */}
            {status?.signal_log && status.signal_log.length > 0 && (
              <GauntletBreakdown
                signals={status.signal_log}
                minConfluence={status?.config?.min_confluence ?? undefined}
                currentScan={status?.current_scan ?? null}
              />
            )}
          </div>
        )}

        {/* System Capabilities Panel (always visible at bottom) */}
        <div className="mt-8">
          <TacticalPanel>
            <div className="p-4 md:p-6">
              <div className="mb-6 flex justify-between items-end">
                <div>
                  <h3 className="heading-hud text-xl text-foreground mb-1 uppercase tracking-tight">Phantom Engine Specs</h3>
                  <p className="text-sm text-muted-foreground">Internal logic and autonomous execution parameters</p>
                </div>
                {status?.status === 'running' && (
                  <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-green-500/5 border border-green-500/20 mb-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse shadow-[0_0_8px_rgba(74,222,128,0.5)]" />
                    <span className="text-[9px] font-black text-green-400/80 uppercase tracking-[0.2em] pl-1">Engine Active</span>
                  </div>
                )}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Regime Adaptive */}
                <div className="p-5 bg-background/40 hover:bg-background/60 rounded-xl border border-border/50 hover:border-purple-500/30 transition-all duration-300 group relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-24 h-24 bg-purple-500/5 blur-3xl rounded-full -mr-12 -mt-12 pointer-events-none" />
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                       <Lightning size={18} weight="fill" className={cn("text-purple-400", status?.status === 'running' && "animate-pulse")} />
                       <div className="font-bold text-sm tracking-widest uppercase text-purple-400/90">Regime Adaptive</div>
                    </div>
                    {status?.regime && status.regime.composite !== 'unknown' && (
                       <Badge variant="outline" className="text-[9px] border-purple-500/20 text-purple-400/80 bg-purple-500/5 font-mono tracking-tighter">
                          {status.regime.composite.toUpperCase()}
                       </Badge>
                    )}
                  </div>
                  <p className="text-muted-foreground text-xs leading-relaxed mb-4">
                    Position sizing automatically scales up in strong trends and reduces in choppy/risk-off conditions.
                  </p>
                  {status?.regime && status.regime.composite !== 'unknown' && (
                    <div className="pt-3 border-t border-purple-500/10 flex items-center justify-between">
                       <span className="text-[9px] text-muted-foreground/40 uppercase font-mono tracking-[0.2em]">Live Pulse</span>
                       <span className="text-[10px] font-mono font-bold text-purple-400/80">{status.regime.trend.toUpperCase()}</span>
                    </div>
                  )}
                </div>

                {/* SMC Detection */}
                <div className="p-5 bg-background/40 hover:bg-background/60 rounded-xl border border-border/50 hover:border-accent/30 transition-all duration-300 group relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-24 h-24 bg-blue-500/5 blur-3xl rounded-full -mr-12 -mt-12 pointer-events-none" />
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                       <Crosshair size={18} className={cn("text-accent", status?.status === 'running' && "animate-pulse")} />
                       <div className="font-bold text-sm tracking-widest uppercase text-accent/90">SMC Detection</div>
                    </div>
                    {status?.status === 'running' && (
                       <Badge variant="outline" className="text-[9px] border-accent/20 text-accent/80 bg-accent/5 font-mono animate-pulse">
                          SCANNING
                       </Badge>
                    )}
                  </div>
                  <p className="text-muted-foreground text-xs leading-relaxed mb-4">
                    MTF Smart Money analysis — hunting Order Blocks, FVGs, and structural breaks across D→5m.
                  </p>
                  {status?.status === 'running' && (
                    <div className="pt-3 border-t border-accent/10 flex items-center justify-between">
                       <span className="text-[9px] text-muted-foreground/40 uppercase font-mono tracking-[0.2em]">Target Depth</span>
                       <span className="text-[10px] font-mono font-bold text-accent/80">{(config.symbols?.length || 0) + (config.majors ? 5 : 0) + (config.altcoins ? 15 : 0)} Assets</span>
                    </div>
                  )}
                </div>

                {/* Risk Management */}
                <div className="p-5 bg-background/40 hover:bg-background/60 rounded-xl border border-border/50 hover:border-amber-500/30 transition-all duration-300 group relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/5 blur-3xl rounded-full -mr-12 -mt-12 pointer-events-none" />
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                       <ShieldCheck size={18} className={cn("text-amber-400", status?.status === 'running' && "animate-pulse")} />
                       <div className="font-bold text-sm tracking-widest uppercase text-amber-400/90">Risk Control</div>
                    </div>
                    {status?.statistics && (
                       <Badge variant="outline" className="text-[9px] border-amber-500/20 text-amber-400/80 bg-amber-500/5 font-mono">
                          {status.statistics.total_pnl < 0 ? Math.abs(status.statistics.total_pnl_pct).toFixed(1) : '0.0'}% DD
                       </Badge>
                    )}
                  </div>
                  <p className="text-muted-foreground text-xs leading-relaxed mb-4">
                    Scalable entry ladder (L1→L3), trailing stops, and proprietary stagnation kill-switches.
                  </p>
                  {status?.status === 'running' && (
                    <div className="pt-3 border-t border-amber-500/10">
                       <div className="flex items-center justify-between mb-2">
                          <span className="text-[9px] text-muted-foreground/40 uppercase font-mono tracking-[0.2em]">DD Threshold</span>
                          <span className="text-[10px] font-mono text-foreground/60">{config.max_drawdown_pct || 'OFF'}%</span>
                       </div>
                       <div className="h-1 w-full bg-black/40 rounded-full overflow-hidden border border-white/5">
                          <div 
                             className="h-full bg-gradient-to-r from-amber-500/50 to-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.5)] transition-all duration-700"
                             style={{ width: `${Math.min(100, ((status.statistics?.total_pnl < 0 ? Math.abs(status.statistics.total_pnl_pct) : 0) / (config.max_drawdown_pct || 100)) * 100)}%` }}
                          />
                       </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </TacticalPanel>
        </div>
      </div>

      {/* Session Debrief Modal */}
      {debrief && (
        <SessionDebriefModal
          stats={debrief.stats}
          balance={debrief.balance}
          config={debrief.config}
          uptime={debrief.uptime}
          signalLog={debrief.signalLog}
          onClose={() => setDebrief(null)}
        />
      )}
    </PageContainer>
  );
}

// Position Card Component
function PositionCard({ position }: { position: PaperTradingPosition }) {
  const isLong = position.direction === 'LONG';
  const isProfitable = position.unrealized_pnl >= 0;

  // Flash effect logic
  const prevPriceRef = useRef(position.current_price);
  const [flashClass, setFlashClass] = useState('');

  useEffect(() => {
    if (position.current_price > prevPriceRef.current) {
      setFlashClass('animate-flash-green');
      const timer = setTimeout(() => setFlashClass(''), 1000);
      prevPriceRef.current = position.current_price;
      return () => clearTimeout(timer);
    } else if (position.current_price < prevPriceRef.current) {
      setFlashClass('animate-flash-red');
      const timer = setTimeout(() => setFlashClass(''), 1000);
      prevPriceRef.current = position.current_price;
      return () => clearTimeout(timer);
    }
  }, [position.current_price]);

  // R-multiple: how many risk units of profit (or loss) the trade has
  const initialRisk = Math.abs(position.entry_price - (position.initial_stop_loss || position.stop_loss));
  const currentProfit = isLong
    ? position.current_price - position.entry_price
    : position.entry_price - position.current_price;
  const rMultiple = initialRisk > 0 ? currentProfit / initialRisk : 0;

  // Progress Calculation
  // We want to show where we are relative to SL and TP1
  const sl = position.stop_loss;
  const entry = position.entry_price;
  const tp1 = position.tp1 || (isLong ? entry * 1.01 : entry * 0.99); // Fallback
  const current = position.current_price;

  let progressPct = 50; // Default center
  if (isLong) {
    if (current >= entry) {
      // Profit side: Entry -> TP1 (50% to 100%)
      const range = tp1 - entry;
      progressPct = range > 0 ? 50 + ((current - entry) / range) * 50 : 50;
    } else {
      // Loss side: SL -> Entry (0% to 50%)
      const range = entry - sl;
      progressPct = range > 0 ? ((current - sl) / range) * 50 : 50;
    }
  } else { // SHORT
    if (current <= entry) {
      // Profit side: Entry -> TP1 (price dropping) (50% to 100%)
      const range = entry - tp1;
      progressPct = range > 0 ? 50 + ((entry - current) / range) * 50 : 50;
    } else {
      // Loss side: SL -> Entry (price rising) (0% to 50%)
      const range = sl - entry;
      progressPct = range > 0 ? ((sl - current) / range) * 50 : 50;
    }
  }
  progressPct = Math.max(0, Math.min(100, progressPct));

  return (
    <div className={cn("p-3 bg-background rounded-lg border border-border hover:border-accent/30 transition-all duration-300 relative overflow-hidden", flashClass)}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className={cn(
              "font-mono text-[10px] tracking-widest uppercase border",
              isLong ? 'bg-green-500/10 text-green-400 border-green-500/30' : 'bg-red-500/10 text-red-400 border-red-500/30'
            )}
          >
            {isLong ? <ArrowUp size={12} className="mr-1" /> : <ArrowDown size={12} className="mr-1" />}
            {position.direction}
          </Badge>
          <span className="font-bold text-lg tracking-tight italic text-foreground">{position.symbol}</span>
          {position.trade_type && (
            <span className={cn(
              "text-[9px] font-mono uppercase tracking-widest px-1.5 py-0.5 rounded-full border",
              position.trade_type === 'scalp' ? 'text-yellow-400/70 border-yellow-400/20' :
              position.trade_type === 'swing' ? 'text-purple-400/70 border-purple-400/20' :
              'text-blue-400/70 border-blue-400/20'
            )}>
              {position.trade_type}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className={cn(
            "font-mono text-[10px] font-bold px-1.5 py-0.5 rounded border",
            rMultiple >= 0 ? 'text-green-400/80 border-green-400/20' : 'text-red-400/80 border-red-400/20'
          )}>
            {rMultiple >= 0 ? '+' : ''}{rMultiple.toFixed(1)}R
          </span>
          <span className={cn(
            "font-mono text-sm font-bold px-2 py-0.5 rounded transition-colors",
            isProfitable ? 'text-green-400' : 'text-red-400'
          )}>
            {formatPct(position.unrealized_pnl_pct)}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-y-4 gap-x-2 text-[10px] sm:text-xs mb-4 leading-tight">
        <div>
          <div className="text-muted-foreground uppercase tracking-widest text-[9px] mb-0.5">Size</div>
          <div className="font-mono text-accent font-bold" title="Notional Position Value">{formatCurrency(position.quantity * position.entry_price)}</div>
        </div>
        <div>
          <div className="text-muted-foreground uppercase tracking-widest text-[9px] mb-0.5">Entry</div>
          <div className="font-mono">${position.entry_price.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-muted-foreground uppercase tracking-widest text-[9px] mb-0.5">Current</div>
          <div className="font-mono font-bold">${position.current_price.toFixed(2)}</div>
        </div>

        <div>
          <div className="text-muted-foreground uppercase tracking-widest text-[9px] mb-0.5">Est. Profit</div>
          <div className="font-mono text-green-400 font-bold" title="Total Realized + Potential PnL">{formatCurrency(position.target_pnl)}</div>
        </div>
        <div>
          <div className="text-muted-foreground uppercase tracking-widest text-[9px] mb-0.5">Risk Profile</div>
          <div className="font-mono text-red-400 font-bold" title="Total Realized + Stop Loss PnL">{formatCurrency(position.risk_pnl)}</div>
        </div>
        <div>
          <div className="text-muted-foreground uppercase tracking-widest text-[9px] mb-0.5">TP / SL</div>
          <div className="font-mono text-[10px] opacity-80" title="Target price and Stop Loss price">
            <span className="text-green-500/80">${tp1.toFixed(2)}</span><span className="mx-1 opacity-30">/</span><span className="text-red-500/80">${position.stop_loss.toFixed(2)}</span>
          </div>
        </div>
      </div>

      {/* Progress tracking */}
      <div className="space-y-2 mb-2">
        <div className="grid grid-cols-3 mt-1 text-[9px] font-mono text-muted-foreground uppercase tracking-tight">
          <span className="text-red-400/70 text-left truncate">STOP ({formatCurrency(position.risk_pnl)})</span>
          <span className="text-center opacity-50">ENTRY</span>
          <span className="text-green-400/70 text-right truncate">TARGET ({formatCurrency(position.target_pnl)})</span>
        </div>
        <div className="hud-progress-bg">
          <div
            className="hud-progress-indicator transition-all duration-500 ease-out"
            style={{ left: `${progressPct}%` }}
          />
        </div>
      </div>

      {/* Phantom Scale-In Ladder */}
      <div className="mt-2 pt-3 border-t border-border/50">
        <div className="flex items-center justify-between text-[9px] uppercase font-bold text-muted-foreground mb-1.5 tracking-widest">
          <span className="flex items-center gap-1"><Gear size={10} className="animate-spin-slow" /> Phantom Scale Ladder</span>
          <span className="text-accent/80 font-mono">Fill: 100% (L1)</span>
        </div>
        <div className="flex gap-1.5">
          <div className={cn("h-1.5 flex-1 rounded-sm relative overflow-hidden", isLong ? "bg-green-400/50" : "bg-red-400/50")} title="L1 (100%) Filled">
            <div className="absolute inset-0 bg-white/20 animate-pulse" />
          </div>
          <div className={cn("h-1.5 flex-1 rounded-sm bg-muted/20 border border-border/30")} title="L2 (Adaptive)" />
          <div className={cn("h-1.5 flex-1 rounded-sm bg-muted/20 border border-border/30")} title="L3 (Adaptive)" />
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2 text-xs">
        {position.breakeven_active && (
          <Badge variant="secondary" className="text-[9px] uppercase font-bold bg-blue-500/10 text-blue-400 border-blue-500/30">BE Active</Badge>
        )}
        {position.trailing_active && (
          <Badge variant="secondary" className="text-[9px] uppercase font-bold border-accent/30 text-accent bg-accent/10">Trailing</Badge>
        )}
        <span className="text-muted-foreground ml-auto text-[9px] uppercase font-bold tracking-widest opacity-60">
          Targets: {position.targets_hit}/{position.targets_hit + position.targets_remaining}
        </span>
      </div>
    </div>
  );
}

// Pending Order Card Component
function PendingOrderCard({ order, onCancel }: { order: any; onCancel?: (orderId: string) => void }) {
  const isLong = order.direction === 'LONG';
  const [cancelling, setCancelling] = useState(false);
  const [cancelled, setCancelled] = useState(false);

  const handleCancel = async () => {
    if (cancelling || cancelled) return;
    setCancelling(true);
    try {
      const res = await fetch(`/api/paper-trading/orders/${order.order_id}`, { method: 'DELETE' });
      if (res.ok) {
        setCancelled(true);
        onCancel?.(order.order_id);
      } else {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        console.error('Cancel failed:', err.detail);
      }
    } catch (e) {
      console.error('Cancel request failed:', e);
    } finally {
      setCancelling(false);
    }
  };

  if (cancelled) return null;

  return (
    <div className="p-3 bg-background/40 rounded-lg border border-amber-500/20 border-dashed hover:border-amber-500/40 transition-all duration-300 group">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className={cn(
              "font-mono text-[9px] px-1.5 py-0 border-none",
              isLong ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"
            )}
          >
            {order.direction}
          </Badge>
          <span className="font-bold text-sm tracking-tight">{order.symbol}</span>
          {order.trade_type && (
            <Badge variant="secondary" className="font-mono text-[9px] tracking-widest uppercase ml-1 opacity-80 bg-accent/10 text-accent border-accent/20">
              {order.trade_type}
            </Badge>
          )}
          <span className="text-[9px] font-mono opacity-40 uppercase tracking-widest bg-amber-500/10 px-1 py-0 rounded">Waiting Fill</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-xs font-bold font-mono text-amber-400/80">
            ${order.limit_price.toFixed(order.limit_price < 1 ? 5 : 2)}
          </div>
          <button
            onClick={handleCancel}
            disabled={cancelling}
            title="Cancel order"
            className={cn(
              "flex items-center justify-center w-5 h-5 rounded border transition-all duration-200",
              "opacity-0 group-hover:opacity-100",
              cancelling
                ? "border-muted/30 text-muted/30 cursor-not-allowed"
                : "border-red-500/30 text-red-400/60 hover:border-red-500/70 hover:text-red-400 hover:bg-red-500/10 cursor-pointer"
            )}
          >
            <X size={10} />
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between text-[10px]">
        <div className="flex items-center gap-3">
          <span className="text-muted-foreground opacity-60">Qty: {order.quantity.toFixed(4)}</span>
          <span className="text-muted-foreground opacity-60">Conf: {order.confluence.toFixed(0)}%</span>
        </div>
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-black/40 border border-border/30">
          <div className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse shadow-[0_0_8px_rgba(245,158,11,0.5)]" />
          <span className="text-[9px] font-mono tracking-tighter opacity-70 uppercase">Market Monitoring Active</span>
        </div>
      </div>
    </div>
  );
}

// Activity Item Component
function ActivityItem({ event }: { event: PaperTradingActivity }) {
  const getIcon = () => {
    switch (event.event_type) {
      case 'session_started':
        return <PlayCircle size={16} className="text-green-400" />;
      case 'session_stopped':
        return <StopCircle size={16} className="text-red-400" />;
      case 'scan_started':
        return <Target size={16} className="text-accent" />;
      case 'scan_completed':
        return <CheckCircle size={16} className="text-green-400" />;
      case 'trade_opened':
        return <TrendUp size={16} className="text-primary" />;
      case 'trade_closed':
        return <TrendDown size={16} className="text-warning" />;
      case 'signal_filtered':
        return <XCircle size={16} className="text-yellow-400" />;
      case 'pending_order_placed':
      case 'pending_order_replaced':
        return <Clock size={16} className="text-blue-400" />;
      case 'pending_order_expired':
        return <XCircle size={16} className="text-muted-foreground" />;
      case 'pending_order_ttl_extended':
        return <Clock size={16} className="text-yellow-400" />;
      case 'scan_error':
      case 'trade_error':
        return <XCircle size={16} className="text-red-400" />;
      default:
        return <Pulse size={16} className="text-muted-foreground" />;
    }
  };

  const getMessage = () => {
    const d = event.data;
    switch (event.event_type) {
      case 'session_started':
        return `Session ${d.session_id} started`;
      case 'session_stopped':
        return `Session stopped`;
      case 'scan_started':
        return `Scan started (${d.mode})`;
      case 'scan_completed':
        return `Scan: ${d.signals_found} signals from ${d.symbols_scanned} symbols`;
      case 'signal_filtered':
        return `${d.symbol} ${d.direction} (${d.confluence?.toFixed(0)}%) - ${d.reason}`;
      case 'trade_opened': {
        const typeLabel = d.trade_type ? ` [${d.trade_type}]` : '';
        return `Opened ${d.direction} ${d.symbol}${typeLabel} @ ${d.entry_price?.toFixed(2)}`;
      }
      case 'trade_closed': {
        const tradeTypeLabel = d.trade_type ? ` [${d.trade_type}]` : '';

        // Use smart stop loss labels
        let displayReason = d.exit_reason || 'unknown';
        if (d.exit_reason === 'stop_loss') {
          if (d.pnl > 0) displayReason = 'trailing_stop';
          else if (Math.abs(d.pnl) < 1) displayReason = 'breakeven_stop';
        }
        displayReason = displayReason.replace(/_/g, ' ');

        const regimeLabel = d.regime_at_close?.trend && d.exit_reason === 'stagnation'
          ? ` | regime: ${d.regime_at_close.trend}/${d.regime_at_close.volatility}`
          : '';
        return `Closed ${d.symbol}${tradeTypeLabel}: ${d.pnl >= 0 ? '+' : ''}${d.pnl?.toFixed(2)} (${displayReason}${regimeLabel})`;
      }
      case 'pending_order_placed':
        return `${d.symbol || ''} ${d.direction || ''} — limit placed @ ${d.limit_price != null ? d.limit_price.toFixed(4) : '?'} (${d.confluence != null ? d.confluence.toFixed(0) + '% conf' : ''})`.trim();
      case 'pending_order_replaced':
        return `${d.symbol || ''} ${d.direction || ''} — limit updated @ ${d.limit_price != null ? d.limit_price.toFixed(4) : '?'}`.trim();
      case 'pending_order_expired': {
        const limStr = d.limit_price != null ? ` @ ${d.limit_price.toFixed(4)}` : '';
        const ageStr = d.age_minutes != null ? ` after ${d.age_minutes.toFixed(0)}min` : '';
        const ttlStr = d.ttl_minutes != null ? `/${d.ttl_minutes.toFixed(0)}min TTL` : '';
        return `${d.symbol || ''} ${d.direction || ''} — limit${limStr} expired unfilled${ageStr}${ttlStr}`.trim();
      }
      case 'pending_order_ttl_extended':
        return `${d.symbol || ''} ${d.direction || ''} — TTL extended [${d.extension_count}/${d.max_extensions}] +${d.extension_minutes?.toFixed(0)}min (price approaching limit ${d.limit_price != null ? d.limit_price.toFixed(4) : ''})`.trim();
      case 'scan_error':
        return `⚠️ Scan error: ${d.error || 'Unknown error'}`;
      case 'trade_error':
        return `⚠️ Trade error: ${d.error || 'Unknown error'}`;
      default:
        return event.event_type.replace(/_/g, ' ');
    }
  };

  return (
    <div className="flex items-center gap-3 text-sm py-2 px-2 rounded hover:bg-muted/30 border-b border-border/10 last:border-0 border-dashed">
      <div className="shrink-0">{getIcon()}</div>
      <span className="flex-1 truncate leading-relaxed">{getMessage()}</span>
      <span className="text-[10px] font-mono text-muted-foreground/60 shrink-0">
        {new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
      </span>
    </div>
  );
}

// Trade History Item Component
function TradeHistoryItem({ trade }: { trade: CompletedPaperTrade }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = trade.direction === 'LONG';
  const isProfitable = trade.pnl >= 0;

  const duration = useMemo(() => {
    if (!trade.entry_time || !trade.exit_time) return null;
    const enter = new Date(trade.entry_time);
    const exit = new Date(trade.exit_time);
    const ms = exit.getTime() - enter.getTime();
    return formatDuration(Math.floor(ms / 1000));
  }, [trade.entry_time, trade.exit_time]);

  const displayReason = useMemo(() => {
    let reason = trade.exit_reason || 'unknown';
    if (trade.exit_reason === 'stop_loss') {
      if (trade.pnl > 0) reason = 'trailing_stop';
      else if (Math.abs(trade.pnl) < 1) reason = 'breakeven_stop';
    }
    return reason.replace(/_/g, ' ');
  }, [trade.exit_reason, trade.pnl]);

  return (
    <div
      className={cn(
        "rounded-lg border transition-all cursor-pointer overflow-hidden",
        expanded ? "bg-background/80 border-accent/40 shadow-[0_0_15px_rgba(0,255,170,0.05)]" : "bg-background border-border hover:border-border/80"
      )}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center justify-between p-3">
        <div className="flex items-center gap-3">
          <Badge
            variant={isLong ? 'default' : 'destructive'}
            className={cn(
              "text-xs px-2 py-0.5 border-none",
              isLong ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"
            )}
          >
            {trade.direction}
          </Badge>
          <div className="flex flex-col">
            <div className="font-bold flex items-center gap-2">
              {trade.symbol}
              <span className="text-[9px] font-mono opacity-50 uppercase tracking-widest px-1.5 py-0.5 rounded-full border border-border/50">
                {displayReason}
              </span>
              {trade.trade_type && (
                <span className="text-[9px] font-mono text-blue-400/60 uppercase tracking-widest px-1.5 py-0.5 rounded-full border border-blue-400/20">
                  {trade.trade_type}
                </span>
              )}
            </div>
            <div className="text-xs text-muted-foreground flex items-center gap-2">
              <span>${trade.entry_price.toFixed(4)} <span className="text-muted-foreground/30 mx-1">→</span> ${trade.exit_price.toFixed(4)}</span>
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className={cn("font-mono font-bold text-sm", isProfitable ? 'text-green-400' : 'text-red-400')}>
            {formatCurrency(trade.pnl)}
          </div>
          <div className={cn("text-[10px] font-mono", isProfitable ? 'text-green-400/70' : 'text-red-400/70')}>
            {formatPct(trade.pnl_pct)}
          </div>
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-border/30 bg-black/20">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-3">
            {/* Times */}
            <div className="space-y-1">
              <div className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest">Timing</div>
              <div className="text-xs font-mono text-foreground/80 flex flex-col gap-0.5">
                <span className="flex justify-between">
                  <span className="text-muted-foreground/50">In:</span>
                  {new Date(trade.entry_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
                {trade.exit_time && (
                  <span className="flex justify-between">
                    <span className="text-muted-foreground/50">Out:</span>
                    {new Date(trade.exit_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                )}
                {duration && (
                  <span className="flex justify-between text-accent/80 mt-0.5 pt-0.5 border-t border-border/30">
                    <span className="text-muted-foreground/50">Dur:</span>
                    {duration}
                  </span>
                )}
              </div>
            </div>

            {/* Excursion */}
            <div className="space-y-1">
              <div className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest">Excursion</div>
              <div className="text-xs font-mono flex flex-col gap-0.5">
                <span className="flex justify-between">
                  <span className="text-muted-foreground/50">MFE:</span>
                  <span className="text-green-400/80">+{formatPct(trade.max_favorable)}</span>
                </span>
                <span className="flex justify-between">
                  <span className="text-muted-foreground/50">MAE:</span>
                  <span className="text-red-400/80">{formatPct(trade.max_adverse)}</span>
                </span>
                <span className="flex justify-between mt-0.5 pt-0.5 border-t border-border/30">
                  <span className="text-muted-foreground/50">Qty:</span>
                  <span className="text-foreground/80">{trade.quantity.toFixed(4)}</span>
                </span>
              </div>
            </div>

            {/* Execution */}
            <div className="space-y-1">
              <div className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest">Execution</div>
              <div className="text-xs font-mono flex flex-col gap-0.5">
                <span className="flex justify-between">
                  <span className="text-muted-foreground/50">Targets Hit:</span>
                  <span className="text-amber-400/80">{trade.targets_hit?.length || 0}</span>
                </span>
                {trade.targets_hit && trade.targets_hit.length > 0 && (
                  <span className="text-[9px] text-muted-foreground/50 text-right truncate">
                    ({trade.targets_hit.map((_, i) => `TP${i + 1}`).join(', ')})
                  </span>
                )}
                <span className="flex justify-between mt-0.5 pt-0.5 border-t border-border/30">
                  <span className="text-muted-foreground/50">Type:</span>
                  <span className="text-foreground/80">{trade.trade_type || 'Unknown'}</span>
                </span>
              </div>
            </div>

            {/* Results breakdown */}
            <div className="space-y-1 flex flex-col items-end justify-center bg-background/40 p-2 rounded border border-border/50">
              <div className="text-[10px] text-muted-foreground font-mono uppercase tracking-widest mb-1">Final Result</div>
              <div className={cn("text-lg font-mono font-bold tracking-tight", isProfitable ? 'text-green-400' : 'text-red-400')}>
                {formatCurrency(trade.pnl)}
              </div>
              <div className={cn("text-xs font-mono", isProfitable ? 'text-green-400/70' : 'text-red-400/70')}>
                {formatPct(trade.pnl_pct)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Signal Intelligence Panel - shows every signal's processing result
function SignalIntelligencePanel({ signals }: { signals: SignalLogEntry[] }) {
  const [expanded, setExpanded] = useState(true);

  const executed = signals.filter(s => s.result === 'executed');
  const filtered = signals.filter(s => s.result === 'filtered');
  const errors = signals.filter(s => s.result === 'error');

  // Group filter reasons
  const reasonCounts: Record<string, number> = {};
  for (const s of filtered) {
    const key = s.reason.split(':')[0].split('(')[0].trim();
    reasonCounts[key] = (reasonCounts[key] || 0) + 1;
  }

  return (
    <section className="glass-card p-5 rounded-2xl relative overflow-hidden group border border-purple-500/20">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-purple-500/5 via-transparent to-transparent opacity-40 pointer-events-none" />
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-purple-400/50 to-transparent opacity-50" />

      <div
        className="flex items-center justify-between mb-4 relative z-10 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <h2 className="text-xl lg:text-2xl font-semibold hud-headline tracking-wide flex items-center gap-3 text-purple-400 drop-shadow-[0_0_8px_rgba(168,85,247,0.5)]">
          <Crosshair size={24} className="text-purple-400" />
          SIGNAL INTELLIGENCE
        </h2>
        <div className="flex items-center gap-3">
          <Badge variant="outline" className="font-mono text-[10px] bg-green-500/10 text-green-400 border-green-500/30">
            {executed.length} EXEC
          </Badge>
          <Badge variant="outline" className="font-mono text-[10px] bg-yellow-500/10 text-yellow-400 border-yellow-500/30">
            {filtered.length} FILT
          </Badge>
          {errors.length > 0 && (
            <Badge variant="outline" className="font-mono text-[10px] bg-red-500/10 text-red-400 border-red-500/30">
              {errors.length} ERR
            </Badge>
          )}
          <Badge variant="outline" className="font-mono text-xs bg-black/60 px-3 border-purple-500/40 text-purple-400">
            {signals.length} TOTAL
          </Badge>
        </div>
      </div>

      {expanded && (
        <div className="relative z-10 space-y-4">
          {/* Filter reason summary */}
          {Object.keys(reasonCounts).length > 0 && (
            <div className="p-3 rounded-lg bg-background/80 border border-yellow-500/20">
              <div className="text-[10px] uppercase tracking-widest text-yellow-400/80 font-bold mb-2">Filter Reason Breakdown</div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(reasonCounts).sort((a, b) => b[1] - a[1]).map(([reason, count]) => (
                  <span key={reason} className="text-xs font-mono px-2 py-1 rounded bg-yellow-500/10 text-yellow-300/80 border border-yellow-500/20">
                    {reason}: {count}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Signal table */}
          <div className="max-h-96 overflow-y-auto space-y-2 pr-2">
            {[...signals].reverse().map((sig, idx) => (
              <SignalLogRow key={idx} signal={sig} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

// Individual signal log row
function SignalLogRow({ signal }: { signal: SignalLogEntry }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = signal.direction === 'LONG';

  const resultColor = signal.result === 'executed'
    ? 'text-green-400 bg-green-500/10 border-green-500/30'
    : signal.result === 'error'
      ? 'text-red-400 bg-red-500/10 border-red-500/30'
      : 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30';

  const resultLabel = signal.result === 'executed' ? 'EXEC' : signal.result === 'error' ? 'ERR' : 'FILT';

  // Parse reason into layman summary + technical detail bullets
  const { layman, details } = (() => {
    const r = signal.reason || '';

    // Known layman mappings
    if (r.toLowerCase().includes('max positions')) return { layman: 'Slot full — max positions reached', details: [] };
    if (r.toLowerCase().includes('waiting for limit fill') || r.toLowerCase().includes('limit placed')) return { layman: 'Limit order placed, waiting for fill', details: [] };
    if (r.toLowerCase().includes('no directional edge')) return { layman: 'No clear bias — too close to call', details: [] };
    if (r.toLowerCase().includes('already in position')) return { layman: 'Already holding this symbol', details: [] };
    if (r.toLowerCase().includes('pending order already exists')) return { layman: 'Better pending order already queued', details: [] };
    if (r.toLowerCase().includes('invalid position size')) return { layman: 'Position size too small to open', details: [] };
    if (r.toLowerCase().includes('session stopped')) return { layman: 'Trade closed — session ended', details: [] };

    // Confluence gate pattern: "Score X% is Y points below Z gate. Weakest signals: a: b, c: d"
    const scoreMatch = r.match(/score\s+([\d.]+)%\s+is\s+([\d.]+)\s+points\s+below/i);
    const weakestIdx = r.indexOf('Weakest signals:');

    if (scoreMatch) {
      const gap = parseFloat(scoreMatch[2]).toFixed(0);
      const weakestRaw = weakestIdx >= 0 ? r.slice(weakestIdx + 'Weakest signals:'.length).trim() : '';
      // Split on ", " where followed by a capital letter (each factor starts with a name)
      const bulletItems = weakestRaw
        ? weakestRaw.split(/,\s*(?=[A-Z])/).map(s => s.trim()).filter(Boolean)
        : [];
      return {
        layman: `Scored ${parseFloat(scoreMatch[1]).toFixed(0)}% — ${gap}pts below the gate`,
        details: bulletItems,
      };
    }

    // Executed signal
    if (signal.result === 'executed') {
      return { layman: r.split('.')[0] || 'Order executed', details: [] };
    }

    // Fallback: first sentence is layman, rest is detail
    const dotIdx = r.indexOf('.');
    if (dotIdx > 0 && dotIdx < r.length - 1) {
      return { layman: r.slice(0, dotIdx).trim(), details: [r.slice(dotIdx + 1).trim()] };
    }
    return { layman: r, details: [] };
  })();

  return (
    <div className="rounded-lg bg-background/60 border border-border/50 hover:border-purple-500/30 transition-all duration-200 overflow-hidden">
      {/* Collapsed view body — wraps for mobile/narrow views */}
      <div 
        className="cursor-pointer select-none group/row"
        onClick={() => setExpanded(!expanded)}
      >
        {/* Row 1: Badges, Symbol, Conf, Time */}
        <div className="flex items-center gap-2 px-3 pt-2 pb-1 text-[10px] font-mono">
          <Badge variant="outline" className={cn("text-[8px] tracking-widest uppercase border px-1.5 py-0 shrink-0 font-bold", resultColor)}>
            {resultLabel}
          </Badge>

          <div className="flex items-center gap-1.5 min-w-0">
            <span className={cn("font-bold shrink-0", isLong ? 'text-green-400' : 'text-red-400')}>
              {isLong ? <ArrowUp size={8} className="inline" /> : <ArrowDown size={8} className="inline" />}
            </span>
            <span className="font-bold text-foreground text-xs truncate w-14">{signal.symbol.replace('/USDT', '')}</span>
          </div>

          <span className={cn(
            "text-[10px] font-mono font-bold px-1.5 py-0.5 rounded shrink-0",
            signal.confluence >= 80 ? 'text-green-400 bg-green-500/10' :
            signal.confluence >= 65 ? 'text-yellow-400 bg-yellow-500/10' :
            'text-red-400/80 bg-red-500/10'
          )}>
            {signal.confluence.toFixed(0)}%
          </span>

          {/* Time & Chevron pushed right */}
          <div className="ml-auto flex items-center gap-2">
            <span className="text-[9px] font-mono text-muted-foreground/35">
              {new Date(signal.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
            {(details.length > 0 || signal.fill_price) && (
              <span className={cn("text-purple-400/40 transition-transform duration-200", expanded ? 'rotate-180' : 'group-hover/row:text-purple-400')}>
                <CaretDown size={11} />
              </span>
            )}
          </div>
        </div>

        {/* Row 2: Layman Summary — full width with wrap, no truncate */}
        <div className="px-3 pb-2 pt-0.5 border-t border-transparent">
          <p className="text-[10px] text-muted-foreground/60 leading-relaxed italic break-words">
            {layman}
          </p>
        </div>
      </div>

      {/* Expanded — technical detail in purple, wrapped */}
      {expanded && (details.length > 0 || signal.fill_price || signal.fill_qty || signal.balance !== undefined) && (
        <div className="px-3 pb-3 pt-1 border-t border-purple-500/10 bg-purple-500/5 space-y-2">
          {/* Weakest signal breakdown — each as its own wrapped line */}
          {details.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-[9px] font-mono uppercase tracking-widest text-purple-400/50 font-bold mb-1">Why it was filtered:</div>
              {details.map((item, i) => {
                // Split on first ": " to get factor name vs explanation
                const colonIdx = item.indexOf(': ');
                const factor = colonIdx > 0 ? item.slice(0, colonIdx) : null;
                const explanation = colonIdx > 0 ? item.slice(colonIdx + 2) : item;
                return (
                  <div key={i} className="flex gap-2 text-[10px] font-mono leading-relaxed">
                    <span className="text-purple-400/40 shrink-0 mt-0.5">›</span>
                    <span>
                      {factor && <span className="text-purple-300/70 font-bold mr-1">{factor}:</span>}
                      <span className="text-muted-foreground/60">{explanation}</span>
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          {/* Execution metadata — always shown when expanded */}
          <div className="flex flex-wrap gap-3 text-[10px] font-mono pt-1 border-t border-border/20">
            {signal.timeframe && (
              <span><span className="text-muted-foreground/40">TF:</span> <span className="text-accent/70 font-bold">{signal.timeframe}</span></span>
            )}
            <span><span className="text-muted-foreground/40">Setup:</span> <span className="text-foreground/70">{signal.setup_type}</span></span>
            <span><span className="text-muted-foreground/40">Scan #:</span> <span className="text-foreground/70">{signal.scan_number}</span></span>
            {signal.fill_price && (
              <span><span className="text-muted-foreground/40">Fill:</span> <span className="text-green-400">${signal.fill_price.toFixed(4)}</span></span>
            )}
            {signal.fill_qty && (
              <span><span className="text-muted-foreground/40">Qty:</span> <span className="text-foreground/70">{signal.fill_qty.toFixed(6)}</span></span>
            )}
            {signal.balance !== undefined && (
              <span><span className="text-muted-foreground/40">Balance:</span> <span className="text-foreground/70">${signal.balance.toFixed(2)}</span></span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Session Debrief Modal
function SessionDebriefModal({
  stats,
  balance,
  config,
  uptime,
  signalLog,
  onClose,
}: {
  stats: PaperTradingStats;
  balance: PaperTradingBalance;
  config: PaperTradingConfigRequest;
  uptime: number;
  signalLog: SignalLogEntry[];
  onClose: () => void;
}) {
  const profitFactor = (() => {
    const wins = stats.winning_trades;
    const losses = stats.losing_trades;
    const gross_profit = (stats.avg_win || 0) * wins;
    const gross_loss = Math.abs(stats.avg_loss || 0) * losses;
    if (gross_loss === 0) return wins > 0 ? 99 : 0;
    return gross_profit / gross_loss;
  })();

  // Compute top filter from signal log
  const topFilter = (() => {
    const filtered = signalLog.filter(s => s.result === 'filtered');
    if (!filtered.length) return null;
    const counts: Record<string, number> = {};
    for (const s of filtered) {
      const key = s.reason || 'unknown';
      counts[key] = (counts[key] || 0) + 1;
    }
    const top = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
    return top ? { reason: top[0], count: top[1] } : null;
  })();

  // Readiness criteria
  const criteria = [
    { label: 'Trade count ≥ 5', met: stats.total_trades >= 5 },
    { label: 'Win rate ≥ 50%', met: stats.win_rate >= 50 },
    { label: 'Profit factor ≥ 1.2', met: profitFactor >= 1.2 },
    { label: 'Max drawdown ≤ 15%', met: stats.max_drawdown <= 15 },
  ];
  const metCount = criteria.filter(c => c.met).length;
  const verdict =
    metCount === 4 ? { label: 'READY FOR LIVE', color: 'text-accent border-accent/50 bg-accent/10' }
    : metCount >= 2 ? { label: 'KEEP TRAINING', color: 'text-yellow-400 border-yellow-500/50 bg-yellow-500/10' }
    : { label: 'NEEDS ADJUSTMENT', color: 'text-red-400 border-red-500/50 bg-red-500/10' };

  const hours = Math.floor(uptime / 3600);
  const minutes = Math.floor((uptime % 3600) / 60);
  const durationLabel = hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-lg bg-background border border-border rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Trophy size={20} className="text-accent" weight="fill" />
            <span className="font-mono font-bold text-sm uppercase tracking-widest text-foreground">Session Debrief</span>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors">
            <XCircle size={20} />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* Verdict */}
          <div className={cn("text-center py-3 rounded-xl border font-mono font-black text-lg tracking-widest", verdict.color)}>
            {verdict.label}
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-3 gap-3">
            <div className="text-center p-3 rounded-lg bg-black/40 border border-border/30">
              <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">P&L</div>
              <div className={cn("text-lg font-mono font-bold", balance.pnl >= 0 ? 'text-accent' : 'text-red-400')}>
                {balance.pnl >= 0 ? '+' : ''}{balance.pnl.toFixed(0)}
              </div>
              <div className="text-[9px] text-muted-foreground">{balance.pnl_pct >= 0 ? '+' : ''}{balance.pnl_pct.toFixed(2)}%</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-black/40 border border-border/30">
              <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">Win Rate</div>
              <div className={cn("text-lg font-mono font-bold", stats.win_rate >= 50 ? 'text-foreground' : 'text-red-400')}>
                {stats.win_rate.toFixed(1)}%
              </div>
              <div className="text-[9px] text-muted-foreground">{stats.winning_trades}W / {stats.losing_trades}L</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-black/40 border border-border/30">
              <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">Prof. Factor</div>
              <div className={cn("text-lg font-mono font-bold", profitFactor >= 1.2 ? 'text-foreground' : 'text-red-400')}>
                {profitFactor >= 99 ? '∞' : profitFactor.toFixed(2)}
              </div>
              <div className="text-[9px] text-muted-foreground">{stats.total_trades} trades</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-black/40 border border-border/30">
              <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">Max DD</div>
              <div className={cn("text-lg font-mono font-bold", stats.max_drawdown <= 15 ? 'text-foreground' : 'text-red-400')}>
                {stats.max_drawdown.toFixed(1)}%
              </div>
              <div className="text-[9px] text-muted-foreground">from peak</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-black/40 border border-border/30">
              <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">Avg R:R</div>
              <div className="text-lg font-mono font-bold text-foreground">{stats.avg_rr.toFixed(2)}</div>
              <div className="text-[9px] text-muted-foreground">{durationLabel} session</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-black/40 border border-border/30">
              <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">Acceptance</div>
              <div className="text-lg font-mono font-bold text-foreground">
                {stats.signals_generated > 0 ? ((stats.signals_taken / stats.signals_generated) * 100).toFixed(0) : 0}%
              </div>
              <div className="text-[9px] text-muted-foreground">{stats.signals_taken}/{stats.signals_generated} sigs</div>
            </div>
          </div>

          {/* Readiness checklist */}
          <div className="space-y-1.5">
            <div className="text-[9px] text-muted-foreground uppercase tracking-widest pl-1 mb-2">Readiness Criteria</div>
            {criteria.map(c => (
              <div key={c.label} className="flex items-center gap-2">
                {c.met
                  ? <CheckCircle size={14} className="text-accent shrink-0" weight="fill" />
                  : <XCircle size={14} className="text-muted-foreground/40 shrink-0" />}
                <span className={cn("text-xs font-mono", c.met ? 'text-foreground' : 'text-muted-foreground/50')}>{c.label}</span>
              </div>
            ))}
          </div>

          {/* Top filter killer */}
          {topFilter && (
            <div className="p-3 rounded-lg bg-yellow-500/5 border border-yellow-500/20 flex items-start gap-2">
              <Warning size={14} className="text-yellow-400 mt-0.5 shrink-0" />
              <p className="text-[10px] font-mono text-yellow-300/70 leading-snug">
                Top killer: <span className="text-yellow-300 font-bold">{topFilter.reason}</span> — blocked {topFilter.count} signal{topFilter.count !== 1 ? 's' : ''}
              </p>
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-border/50">
          <Button onClick={onClose} className="w-full font-mono text-xs tracking-widest" variant="outline">
            CLOSE
          </Button>
        </div>
      </div>
    </div>
  );
}

export default TrainingGround;
