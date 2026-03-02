import { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
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
  Crosshair,
  ArrowUp,
  ArrowDown,
  ListBullets,
  Gear,
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
  CompletedPaperTrade,
  PaperTradingActivity,
  SignalLogEntry,
} from '@/utils/api';

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

// Default Phantom Spec Config
const DEFAULT_CONFIG: PaperTradingConfigRequest = {
  exchange: 'phemex',
  sniper_mode: 'stealth', // Underlying detection mode
  initial_balance: 10000,
  risk_per_trade: 2, // Total 2% per thesis
  max_positions: 3, // 3 limits (L1, L2, L3)
  leverage: 1, // Default 1x
  duration_hours: 24,
  scan_interval_minutes: 5,
  trailing_stop: true,
  trailing_activation: 2.0, // WAS 1.0 - changed to 2.0 to give trade room to breathe
  breakeven_after_target: 1, // Move to BE after TP1 is hit
  min_confluence: 82,
  symbols: [],
  exclude_symbols: [],
  majors: true,
  altcoins: false,
  meme_mode: false,
  slippage_bps: 5,
  fee_rate: 0.001,
};

export function TrainingGround() {
  const [config, setConfig] = useState<PaperTradingConfigRequest>(DEFAULT_CONFIG);
  const [status, setStatus] = useState<PaperTradingStatusResponse | null>(null);
  const [trades, setTrades] = useState<CompletedPaperTrade[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  // Poll status when running
  useEffect(() => {
    fetchStatus();
    fetchTrades();

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

    try {
      const response = await api.stopPaperTrading();
      if (response.error) {
        setError(response.error);
      } else {
        await fetchStatus();
        await fetchTrades();
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
  const isIdle = !status || status.status === 'idle';

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

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 w-full">
                  <div className="p-4 rounded-lg bg-background border border-border">
                    <div className="text-[10px] text-muted-foreground uppercase tracking-widest mb-1.5">Leverage</div>
                    <div className="text-xl font-mono font-bold text-accent">{config.leverage}x</div>
                    <div className="text-[10px] text-muted-foreground mt-1">Adjustable Below</div>
                  </div>
                  <div className="p-4 rounded-lg bg-background border border-border">
                    <div className="text-[10px] text-muted-foreground uppercase tracking-widest mb-1.5">Risk Profile</div>
                    <div className="text-xl font-mono font-bold text-foreground">2% Max</div>
                    <div className="text-[10px] text-muted-foreground mt-1">Split across 3 limits</div>
                  </div>
                  <div className="p-4 rounded-lg bg-background border border-border">
                    <div className="text-[10px] text-muted-foreground uppercase tracking-widest mb-1.5">Regime State</div>
                    <div className="text-xl font-mono font-bold text-primary">Adaptive</div>
                  </div>
                  <div className="p-4 rounded-lg bg-background border border-border">
                    <div className="text-[10px] text-muted-foreground uppercase tracking-widest mb-1.5">Confluence Gate</div>
                    <div className="text-xl font-mono font-bold text-yellow-400">≥ {config.min_confluence}%</div>
                  </div>
                </div>

                <div className="w-full max-w-2xl pt-4 space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="space-y-2 text-left">
                      <label className="text-[10px] text-muted-foreground uppercase tracking-widest pl-1">Starting Balance</label>
                      <input
                        type="number"
                        value={config.initial_balance}
                        onChange={e => setConfig({ ...config, initial_balance: Number(e.target.value) })}
                        className="w-full h-12 bg-background border border-border rounded-lg px-4 font-mono text-center text-lg focus:outline-none focus:border-accent/40 text-foreground"
                      />
                    </div>
                    <div className="space-y-2 text-left">
                      <label className="text-[10px] text-muted-foreground uppercase tracking-widest pl-1">Leverage (x)</label>
                      <input
                        type="number"
                        min="1"
                        max="100"
                        value={config.leverage}
                        onChange={e => setConfig({ ...config, leverage: Number(e.target.value) })}
                        className="w-full h-12 bg-background border border-border rounded-lg px-4 font-mono text-center text-lg focus:outline-none focus:border-accent/40 text-foreground"
                      />
                    </div>
                    <div className="space-y-2 text-left">
                      <label className="text-[10px] text-muted-foreground uppercase tracking-widest pl-1">Min Confluence %</label>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={config.min_confluence ?? 0}
                        onChange={e => setConfig({ ...config, min_confluence: Number(e.target.value) })}
                        className="w-full h-12 bg-background border border-border rounded-lg px-4 font-mono text-center text-lg focus:outline-none focus:border-accent/40 text-foreground"
                      />
                    </div>
                  </div>

                  {/* Symbol Selection UI */}
                  <div className="bg-background/40 border border-border/50 rounded-xl p-4 space-y-4">
                    <div className="flex items-center justify-between">
                      <label className="text-[10px] text-accent font-bold uppercase tracking-widest pl-1">Target Asset Buckets</label>
                      <span className="text-[9px] text-muted-foreground font-mono italic">Hunting logic utilizes top-volume adapters</span>
                    </div>

                    <div className="flex flex-wrap gap-3">
                      <div
                        onClick={() => setConfig({ ...config, majors: !config.majors })}
                        className={cn(
                          "flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-all",
                          config.majors ? "bg-accent/10 border-accent text-accent shadow-[0_0_10px_rgba(0,255,170,0.1)]" : "bg-black/20 border-border text-muted-foreground opacity-60 grayscale"
                        )}
                      >
                        <Trophy size={16} weight={config.majors ? "fill" : "regular"} />
                        <span className="text-xs font-mono font-bold tracking-tighter">MAJORS</span>
                      </div>

                      <div
                        onClick={() => setConfig({ ...config, altcoins: !config.altcoins })}
                        className={cn(
                          "flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-all",
                          config.altcoins ? "bg-primary/10 border-primary text-primary shadow-[0_0_10px_rgba(59,130,246,0.1)]" : "bg-black/20 border-border text-muted-foreground opacity-60 grayscale"
                        )}
                      >
                        <ChartLine size={16} weight={config.altcoins ? "fill" : "regular"} />
                        <span className="text-xs font-mono font-bold tracking-tighter">TOP VOL ALTS</span>
                      </div>

                      <div
                        onClick={() => setConfig({ ...config, meme_mode: !config.meme_mode })}
                        className={cn(
                          "flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-all",
                          config.meme_mode ? "bg-purple-500/10 border-purple-500 text-purple-400 shadow-[0_0_10px_rgba(168,85,247,0.1)]" : "bg-black/20 border-border text-muted-foreground opacity-60 grayscale"
                        )}
                      >
                        <Crosshair size={16} weight={config.meme_mode ? "fill" : "regular"} />
                        <span className="text-xs font-mono font-bold tracking-tighter">MEME HUNTER</span>
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
                <div className="flex items-center gap-6">
                  {/* Session Info */}
                  <div>
                    <div className="text-xs text-[#00ff88] uppercase tracking-widest font-mono font-bold">SESSION</div>
                    <div className="mt-1 font-mono text-sm tracking-widest glow-border-green px-2 py-0.5 rounded bg-black/40">{status?.session_id || '—'}</div>
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
                    <div className="text-xs text-muted-foreground uppercase tracking-widest font-mono">REGIME</div>
                    <Badge variant="outline" className="font-mono text-xs border-accent text-accent bg-accent/10 tracking-widest mt-1">
                      ADAPTIVE
                    </Badge>
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
                    <div className="mt-3 pt-3 border-t border-border/50 flex gap-2 overflow-hidden">
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

            {/* Balance & Stats Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Balance Card */}
              <div className="glass-card p-5 rounded-2xl border-accent/30 relative overflow-hidden group">
                <div className="absolute top-0 right-0 w-32 h-32 bg-[radial-gradient(circle,_var(--tw-gradient-stops))] from-accent/5 to-transparent rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none -mr-16 -mt-16" />
                <div className="relative z-10 pt-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs text-muted-foreground font-mono font-bold tracking-widest uppercase">EQUITY</div>
                      <div className="text-2xl font-bold font-mono tracking-tight mt-1">
                        {formatCurrency(status?.balance?.equity || config.initial_balance || 10000)}
                      </div>
                    </div>
                    <Wallet size={32} className="text-accent" />
                  </div>
                  <div className="mt-2 flex items-center gap-2">
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
                    <span className="text-xs text-muted-foreground opacity-60">
                      from {formatCurrency(status?.balance?.initial || config.initial_balance || 10000)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Win Rate Card */}
              <div className="glass-card p-5 rounded-2xl border-border/50 relative overflow-hidden group">
                <div className="relative z-10 pt-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs text-muted-foreground font-mono font-bold tracking-widest uppercase">WIN RATE</div>
                      <div className="text-2xl font-bold font-mono tracking-tight mt-1">
                        {(status?.statistics?.win_rate || 0).toFixed(1)}%
                      </div>
                    </div>
                    <Trophy size={32} className="text-accent/20 transition-colors group-hover:text-accent/50" />
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground font-mono opacity-80 flex items-center gap-2">
                    <span className="text-green-400">{status?.statistics?.winning_trades || 0}W</span>
                    <span className="text-white/20">/</span>
                    <span className="text-red-400">{status?.statistics?.losing_trades || 0}L</span>
                    <span className="mx-1 opacity-20">•</span>
                    {status?.statistics?.total_trades || 0} total
                  </div>
                </div>
              </div>

              {/* Avg R:R Card */}
              <div className="glass-card p-5 rounded-2xl border-border/50 relative overflow-hidden group">
                <div className="relative z-10 pt-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs text-muted-foreground font-mono font-bold tracking-widest uppercase">AVG R:R</div>
                      <div className="text-2xl font-bold font-mono tracking-tight mt-1">
                        {(status?.statistics?.avg_rr || 0).toFixed(2)}
                      </div>
                    </div>
                    <Crosshair size={32} className="text-accent/20 transition-colors group-hover:text-amber-400/50" />
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground font-mono opacity-80 flex items-center flex-wrap gap-x-2">
                    <span className="text-green-400/80">AvgW: {formatCurrency(status?.statistics?.avg_win || 0)}</span>
                    <span className="opacity-20">•</span>
                    <span className="text-red-400/80">AvgL: {formatCurrency(status?.statistics?.avg_loss || 0)}</span>
                  </div>
                </div>
              </div>

              {/* Scans Card */}
              <div className="glass-card p-5 rounded-2xl border-border/50 relative overflow-hidden group">
                <div className="relative z-10 pt-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs text-muted-foreground font-mono font-bold tracking-widest uppercase">SCANS</div>
                      <div className="text-2xl font-bold font-mono tracking-tight mt-1">
                        {status?.statistics?.scans_completed || 0}
                      </div>
                    </div>
                    <Target size={32} className="text-accent/20 transition-colors group-hover:text-blue-400/50" />
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground font-mono opacity-80">
                    <span className="text-blue-400/80">{status?.statistics?.signals_generated || 0} sigs</span>
                    <span className="mx-2 opacity-20">→</span>
                    <span className="text-green-400/80">{status?.statistics?.signals_taken || 0} tk</span>
                  </div>
                </div>
              </div>
            </div>

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

                <div className="relative z-10">
                  {status?.positions && status.positions.length > 0 ? (
                    <div className="space-y-3">
                      {status.positions.map((pos) => (
                        <PositionCard key={pos.position_id} position={pos} />
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-12 border border-border border-dashed rounded-lg bg-background/50">
                      <Crosshair size={32} className="mx-auto mb-3 opacity-20 text-accent" />
                      <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground/50">No active positions</p>
                    </div>
                  )}
                </div>
              </section>

              {/* Activity Feed */}
              <section className="glass-card glow-border-blue p-5 rounded-2xl h-full flex flex-col relative overflow-hidden group">
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />

                <div className="flex items-center justify-between mb-6 relative z-10">
                  <h2 className="text-xl lg:text-2xl font-semibold hud-headline font-bold text-blue-400 tracking-wide flex items-center gap-3 drop-shadow-[0_0_8px_rgba(96,165,250,0.5)]">
                    <Pulse size={24} className="text-primary" />
                    ACTIVITY FEED
                  </h2>
                </div>

                <div className="relative z-10">
                  {status?.recent_activity && status.recent_activity.length > 0 ? (
                    <div className="space-y-2 max-h-80 overflow-y-auto">
                      {status.recent_activity.slice(-15).reverse().map((event, i) => (
                        <ActivityItem key={i} event={event} />
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-12 border border-border border-dashed rounded-lg bg-background/50">
                      <ListBullets size={32} className="mx-auto mb-3 opacity-20 text-primary" />
                      <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground/50">No activity yet</p>
                    </div>
                  )}
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
              <SignalIntelligencePanel signals={status.signal_log} />
            )}
          </div>
        )}

        {/* Learning Resources (always visible at bottom) */}
        <div className="mt-8">
          <TacticalPanel>
            <div className="p-4 md:p-6">
              <div className="mb-6">
                <h3 className="heading-hud text-xl text-foreground mb-2">Learning Resources</h3>
                <p className="text-sm text-muted-foreground">Essential concepts for successful trading</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-5 bg-background rounded-lg border border-border hover:border-accent/30 transition-colors">
                  <div className="font-bold mb-2 text-base heading-hud">Smart Money Concepts</div>
                  <div className="text-muted-foreground text-sm">Learn order blocks, fair value gaps, and institutional analysis</div>
                </div>
                <div className="p-5 bg-background rounded-lg border border-border hover:border-accent/30 transition-colors">
                  <div className="font-bold mb-2 text-base heading-hud">Multi-Timeframe Analysis</div>
                  <div className="text-muted-foreground text-sm">Understand confluence across different timeframes</div>
                </div>
                <div className="p-5 bg-background rounded-lg border border-border hover:border-accent/30 transition-colors">
                  <div className="font-bold mb-2 text-base heading-hud">Risk Management</div>
                  <div className="text-muted-foreground text-sm">Position sizing, stop placement, and reward-to-risk ratios</div>
                </div>
              </div>
            </div>
          </TacticalPanel>
        </div>
      </div>
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

  // Progress Calculation
  // We want to show where we are relative to SL and TP1
  const sl = position.stop_loss;
  const entry = position.entry_price;
  const tp1 = position.tp1 || (isLong ? entry * 1.01 : entry * 0.99); // Fallback
  const current = position.current_price;

  let progressPct = 0;
  if (isLong) {
    // SL < Current < TP1
    const range = tp1 - sl;
    progressPct = range !== 0 ? ((current - sl) / range) * 100 : 50;
  } else {
    // TP1 < Current < SL
    const range = sl - tp1;
    progressPct = range !== 0 ? ((sl - current) / range) * 100 : 50;
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
        </div>
        <div className={cn(
          "font-mono text-sm font-bold px-2 py-0.5 rounded transition-colors",
          isProfitable ? 'text-green-400' : 'text-red-400'
        )}>
          {formatPct(position.unrealized_pnl_pct)}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-2 text-[10px] sm:text-xs mb-4">
        <div>
          <div className="text-muted-foreground uppercase tracking-widest text-[9px]">Value</div>
          <div className="font-mono text-accent font-bold">{formatCurrency(position.quantity * position.entry_price)}</div>
        </div>
        <div>
          <div className="text-muted-foreground uppercase tracking-widest text-[9px]">Entry</div>
          <div className="font-mono">${position.entry_price.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-muted-foreground uppercase tracking-widest text-[9px]">Current</div>
          <div className="font-mono font-bold">${position.current_price.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-muted-foreground uppercase tracking-widest text-[9px]">Stop</div>
          <div className="font-mono text-red-400/80">${position.stop_loss.toFixed(2)}</div>
        </div>
      </div>

      {/* Progress tracking */}
      <div className="space-y-1.5 mb-4">
        <div className="flex justify-between text-[9px] font-mono text-muted-foreground uppercase tracking-tighter">
          <span>{isLong ? 'STOP' : 'TARGET'}</span>
          <span>ENTRY</span>
          <span>{isLong ? 'TARGET' : 'STOP'}</span>
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
      case 'trade_opened':
        return `Opened ${d.direction} ${d.symbol} @ ${d.entry_price?.toFixed(2)}`;
      case 'trade_closed':
        return `Closed ${d.symbol}: ${d.pnl >= 0 ? '+' : ''}${d.pnl?.toFixed(2)} (${d.exit_reason})`;
      case 'scan_error':
        return `⚠️ Scan error: ${d.error || 'Unknown error'}`;
      case 'trade_error':
        return `⚠️ Trade error: ${d.error || 'Unknown error'}`;
      default:
        return event.event_type.replace(/_/g, ' ');
    }
  };

  return (
    <div className="flex items-center gap-2 text-sm py-1 px-2 rounded hover:bg-muted/30">
      {getIcon()}
      <span className="flex-1 truncate">{getMessage()}</span>
      <span className="text-xs text-muted-foreground">
        {new Date(event.timestamp).toLocaleTimeString()}
      </span>
    </div>
  );
}

// Trade History Item Component
function TradeHistoryItem({ trade }: { trade: CompletedPaperTrade }) {
  const isLong = trade.direction === 'LONG';
  const isProfitable = trade.pnl >= 0;

  return (
    <div className="flex items-center justify-between p-3 bg-background rounded-lg border border-border">
      <div className="flex items-center gap-3">
        <Badge
          variant={isLong ? 'default' : 'destructive'}
          className={`text-xs ${isLong ? 'bg-green-500/20 text-green-400' : ''}`}
        >
          {trade.direction}
        </Badge>
        <div>
          <div className="font-bold">{trade.symbol}</div>
          <div className="text-xs text-muted-foreground">
            ${trade.entry_price.toFixed(2)} → ${trade.exit_price.toFixed(2)}
          </div>
        </div>
      </div>
      <div className="text-right">
        <div className={`font-mono font-bold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
          {formatCurrency(trade.pnl)}
        </div>
        <div className={`text-xs ${isProfitable ? 'text-green-400/70' : 'text-red-400/70'}`}>
          {formatPct(trade.pnl_pct)}
        </div>
      </div>
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
          <div className="max-h-96 overflow-y-auto space-y-1">
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

  return (
    <div
      className="p-2 rounded-lg bg-background/60 border border-border/50 hover:border-purple-500/30 transition-colors cursor-pointer"
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center gap-2 text-xs font-mono">
        {/* Result badge */}
        <Badge variant="outline" className={cn("text-[9px] tracking-widest uppercase border px-1.5 py-0 min-w-[38px] text-center", resultColor)}>
          {resultLabel}
        </Badge>

        {/* Direction */}
        <span className={cn("font-bold w-10", isLong ? 'text-green-400' : 'text-red-400')}>
          {isLong ? <ArrowUp size={12} className="inline mr-0.5" /> : <ArrowDown size={12} className="inline mr-0.5" />}
          {signal.direction.slice(0, 1)}
        </span>

        {/* Symbol */}
        <span className="font-bold text-foreground w-24 truncate">{signal.symbol.replace('/USDT', '')}</span>

        {/* Confluence */}
        <span className={cn("w-12 text-right", signal.confluence >= 82 ? 'text-green-400' : 'text-yellow-400')}>
          {signal.confluence.toFixed(0)}%
        </span>

        {/* Entry / Stop / R:R */}
        <span className="text-muted-foreground w-20 text-right">${signal.entry_zone.toFixed(2)}</span>
        <span className="text-red-400/60 w-20 text-right">${signal.stop_loss.toFixed(2)}</span>
        {signal.rr && <span className="text-muted-foreground w-10 text-right">{signal.rr.toFixed(1)}R</span>}

        {/* Reason (truncated) */}
        <span className="flex-1 truncate text-muted-foreground/80 pl-2">{signal.reason}</span>

        {/* Time */}
        <span className="text-muted-foreground/50 w-16 text-right">
          {new Date(signal.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </span>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="mt-2 pt-2 border-t border-border/30 text-xs font-mono text-muted-foreground grid grid-cols-2 md:grid-cols-4 gap-2">
          <div>
            <span className="text-muted-foreground/50">Setup: </span>
            <span>{signal.setup_type}</span>
          </div>
          <div>
            <span className="text-muted-foreground/50">Scan #: </span>
            <span>{signal.scan_number}</span>
          </div>
          {signal.fill_price && (
            <div>
              <span className="text-muted-foreground/50">Fill: </span>
              <span className="text-green-400">${signal.fill_price.toFixed(2)}</span>
            </div>
          )}
          {signal.fill_qty && (
            <div>
              <span className="text-muted-foreground/50">Qty: </span>
              <span>{signal.fill_qty.toFixed(6)}</span>
            </div>
          )}
          {signal.balance !== undefined && (
            <div>
              <span className="text-muted-foreground/50">Balance: </span>
              <span>${signal.balance.toFixed(2)}</span>
            </div>
          )}
          <div className="col-span-full">
            <span className="text-muted-foreground/50">Reason: </span>
            <span className="text-yellow-300/80">{signal.reason}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default TrainingGround;
