import { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
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

// Default config
const DEFAULT_CONFIG: PaperTradingConfigRequest = {
  exchange: 'phemex',
  sniper_mode: 'stealth',
  initial_balance: 10000,
  risk_per_trade: 2,
  max_positions: 3,
  leverage: 1,
  duration_hours: 24,
  scan_interval_minutes: 5,
  trailing_stop: true,
  trailing_activation: 1.5,
  breakeven_after_target: 1,
  min_confluence: null,
  symbols: [],
  exclude_symbols: [],
  slippage_bps: 5,
  fee_rate: 0.001,
};

export function TrainingGround() {
  const [activeTab, setActiveTab] = useState<'config' | 'dashboard'>('config');
  const [config, setConfig] = useState<PaperTradingConfigRequest>(DEFAULT_CONFIG);
  const [status, setStatus] = useState<PaperTradingStatusResponse | null>(null);
  const [trades, setTrades] = useState<CompletedPaperTrade[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pollRef = useRef<number | null>(null);

  // Fetch status
  const fetchStatus = useCallback(async () => {
    try {
      const response = await api.getPaperTradingStatus();
      if (response.data) {
        setStatus(response.data);
        // Auto-switch to dashboard when running
        if (response.data.status === 'running' && activeTab === 'config') {
          setActiveTab('dashboard');
        }
      }
    } catch (err) {
      console.error('Failed to fetch status:', err);
    }
  }, [activeTab]);

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
        setActiveTab('dashboard');
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
        setActiveTab('config');
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
              <h1 className="text-3xl font-bold text-foreground flex items-center gap-3 heading-hud">
                <Target size={32} weight="bold" className="text-accent" />
                TRAINING GROUND
              </h1>
              <p className="text-muted-foreground text-lg">
                Paper trading with real market data
              </p>
            </div>
          </div>

          {/* Status Badge */}
          {status && (
            <Badge
              variant={isRunning ? 'default' : isStopped ? 'secondary' : 'outline'}
              className={`text-sm px-3 py-1 ${isRunning ? 'bg-green-500/20 text-green-400 border-green-500/30' : ''}`}
            >
              {isRunning && <Pulse size={14} className="mr-1 animate-pulse" />}
              {status.status.toUpperCase()}
            </Badge>
          )}
        </div>

        {/* Info Alert */}
        <Alert className="border-accent/50 bg-accent/10 py-4">
          <BookOpen size={20} className="text-accent" />
          <AlertTitle className="text-accent heading-hud">Safe Environment</AlertTitle>
          <AlertDescription className="mt-2">
            Paper trading uses real market data but simulated execution. Perfect for testing strategies without risking real capital.
          </AlertDescription>
        </Alert>

        {/* Error Alert */}
        {error && (
          <Alert variant="destructive">
            <Warning size={20} />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'config' | 'dashboard')}>
          <TabsList className="grid grid-cols-2 w-full max-w-md">
            <TabsTrigger value="config" className="flex items-center gap-2">
              <Gear size={18} />
              Configuration
            </TabsTrigger>
            <TabsTrigger value="dashboard" className="flex items-center gap-2">
              <ChartLine size={18} />
              Dashboard
            </TabsTrigger>
          </TabsList>

          {/* Config Tab */}
          <TabsContent value="config" className="space-y-6 mt-6">
            <PaperTradingConfig
              config={config}
              onChange={setConfig}
              disabled={isRunning}
            />

            {/* Start Button */}
            <div className="flex gap-4">
              <Button
                onClick={handleStart}
                disabled={isLoading || isRunning}
                className="flex-1 bg-accent hover:bg-accent/90 text-accent-foreground"
                size="lg"
              >
                {isLoading ? (
                  <ArrowsClockwise size={20} className="animate-spin mr-2" />
                ) : (
                  <PlayCircle size={20} weight="fill" className="mr-2" />
                )}
                {isLoading ? 'STARTING...' : 'START PAPER TRADING'}
              </Button>

              {isStopped && (
                <Button
                  onClick={handleReset}
                  disabled={isLoading}
                  variant="outline"
                  size="lg"
                >
                  <ArrowsClockwise size={20} className="mr-2" />
                  RESET
                </Button>
              )}
            </div>
          </TabsContent>

          {/* Dashboard Tab */}
          <TabsContent value="dashboard" className="space-y-6 mt-6">
            {/* Control Bar */}
            <TacticalPanel>
              <div className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-6">
                  {/* Session Info */}
                  <div>
                    <div className="text-xs text-muted-foreground">SESSION</div>
                    <div className="font-mono text-sm">{status?.session_id || '—'}</div>
                  </div>

                  {/* Uptime */}
                  <div>
                    <div className="text-xs text-muted-foreground">UPTIME</div>
                    <div className="font-mono text-sm flex items-center gap-1">
                      <Clock size={14} />
                      {formatDuration(status?.uptime_seconds || 0)}
                    </div>
                  </div>

                  {/* Next Scan */}
                  {isRunning && status?.next_scan_in_seconds !== null && (
                    <div>
                      <div className="text-xs text-muted-foreground">NEXT SCAN</div>
                      <div className="font-mono text-sm flex items-center gap-1 text-accent">
                        <Target size={14} className="animate-pulse" />
                        {formatDuration(Math.round(status.next_scan_in_seconds))}
                      </div>
                    </div>
                  )}

                  {/* Cache Hit Rate */}
                  {status?.cache_stats && (
                    <div>
                      <div className="text-xs text-muted-foreground">CACHE</div>
                      <div className={`font-mono text-sm ${status.cache_stats.hit_rate_pct > 50 ? 'text-green-400' : 'text-yellow-400'}`}>
                        {status.cache_stats.hit_rate_pct.toFixed(0)}% hit
                      </div>
                    </div>
                  )}

                  {/* Mode */}
                  <div>
                    <div className="text-xs text-muted-foreground">MODE</div>
                    <Badge variant="outline" className="font-mono text-xs">
                      {status?.config?.sniper_mode?.toUpperCase() || 'STEALTH'}
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
            </TacticalPanel>

            {/* Balance & Stats Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Balance Card */}
              <Card className="border-accent/30">
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs text-muted-foreground">EQUITY</div>
                      <div className="text-2xl font-bold font-mono">
                        {formatCurrency(status?.balance?.equity || config.initial_balance || 10000)}
                      </div>
                    </div>
                    <Wallet size={32} className="text-accent" />
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <Badge
                      variant={status?.balance?.pnl && status.balance.pnl >= 0 ? 'default' : 'destructive'}
                      className={status?.balance?.pnl && status.balance.pnl >= 0 ? 'bg-green-500/20 text-green-400' : ''}
                    >
                      {formatPct(status?.balance?.pnl_pct || 0)}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      from {formatCurrency(status?.balance?.initial || config.initial_balance || 10000)}
                    </span>
                  </div>
                </CardContent>
              </Card>

              {/* Win Rate Card */}
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs text-muted-foreground">WIN RATE</div>
                      <div className="text-2xl font-bold font-mono">
                        {(status?.statistics?.win_rate || 0).toFixed(1)}%
                      </div>
                    </div>
                    <Trophy size={32} className="text-yellow-500" />
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    {status?.statistics?.winning_trades || 0}W / {status?.statistics?.losing_trades || 0}L
                    <span className="mx-1">•</span>
                    {status?.statistics?.total_trades || 0} total
                  </div>
                </CardContent>
              </Card>

              {/* Avg R:R Card */}
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs text-muted-foreground">AVG R:R</div>
                      <div className="text-2xl font-bold font-mono">
                        {(status?.statistics?.avg_rr || 0).toFixed(2)}
                      </div>
                    </div>
                    <Crosshair size={32} className="text-primary" />
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    Avg Win: {formatCurrency(status?.statistics?.avg_win || 0)}
                    <span className="mx-1">•</span>
                    Avg Loss: {formatCurrency(status?.statistics?.avg_loss || 0)}
                  </div>
                </CardContent>
              </Card>

              {/* Scans Card */}
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs text-muted-foreground">SCANS</div>
                      <div className="text-2xl font-bold font-mono">
                        {status?.statistics?.scans_completed || 0}
                      </div>
                    </div>
                    <Target size={32} className="text-muted-foreground" />
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    {status?.statistics?.signals_generated || 0} signals
                    <span className="mx-1">→</span>
                    {status?.statistics?.signals_taken || 0} taken
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Positions & Activity Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Active Positions */}
              <TacticalPanel>
                <div className="p-4">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="heading-hud text-lg text-foreground flex items-center gap-2">
                      <ChartLine size={20} className="text-accent" />
                      ACTIVE POSITIONS
                    </h3>
                    <Badge variant="outline">{status?.positions?.length || 0}</Badge>
                  </div>

                  {status?.positions && status.positions.length > 0 ? (
                    <div className="space-y-3">
                      {status.positions.map((pos) => (
                        <PositionCard key={pos.position_id} position={pos} />
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <Crosshair size={40} className="mx-auto mb-2 opacity-30" />
                      <p>No active positions</p>
                    </div>
                  )}
                </div>
              </TacticalPanel>

              {/* Activity Feed */}
              <TacticalPanel>
                <div className="p-4">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="heading-hud text-lg text-foreground flex items-center gap-2">
                      <Pulse size={20} className="text-primary" />
                      ACTIVITY FEED
                    </h3>
                  </div>

                  {status?.recent_activity && status.recent_activity.length > 0 ? (
                    <div className="space-y-2 max-h-80 overflow-y-auto">
                      {status.recent_activity.slice(-15).reverse().map((event, i) => (
                        <ActivityItem key={i} event={event} />
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <ListBullets size={40} className="mx-auto mb-2 opacity-30" />
                      <p>No activity yet</p>
                    </div>
                  )}
                </div>
              </TacticalPanel>
            </div>

            {/* Trade History */}
            <TacticalPanel>
              <div className="p-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="heading-hud text-lg text-foreground flex items-center gap-2">
                    <ListBullets size={20} className="text-warning" />
                    TRADE HISTORY
                  </h3>
                  <Badge variant="outline">{trades.length} trades</Badge>
                </div>

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
                  <div className="text-center py-8 text-muted-foreground">
                    <TrendUp size={40} className="mx-auto mb-2 opacity-30" />
                    <p>No completed trades yet</p>
                  </div>
                )}
              </div>
            </TacticalPanel>
          </TabsContent>
        </Tabs>

        {/* Learning Resources (always visible at bottom) */}
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
    </PageContainer>
  );
}

// Position Card Component
function PositionCard({ position }: { position: PaperTradingPosition }) {
  const isLong = position.direction === 'LONG';
  const isProfitable = position.unrealized_pnl >= 0;

  return (
    <div className="p-3 bg-background rounded-lg border border-border hover:border-accent/30 transition-colors">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Badge
            variant={isLong ? 'default' : 'destructive'}
            className={isLong ? 'bg-green-500/20 text-green-400' : ''}
          >
            {isLong ? <ArrowUp size={12} className="mr-1" /> : <ArrowDown size={12} className="mr-1" />}
            {position.direction}
          </Badge>
          <span className="font-bold">{position.symbol}</span>
        </div>
        <div className={`font-mono text-sm ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
          {formatPct(position.unrealized_pnl_pct)}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs">
        <div>
          <div className="text-muted-foreground">Entry</div>
          <div className="font-mono">${position.entry_price.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-muted-foreground">Current</div>
          <div className="font-mono">${position.current_price.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-muted-foreground">Stop</div>
          <div className="font-mono text-red-400">${position.stop_loss.toFixed(2)}</div>
        </div>
      </div>

      <div className="mt-2 flex items-center gap-2 text-xs">
        {position.breakeven_active && (
          <Badge variant="secondary" className="text-xs">BE Active</Badge>
        )}
        {position.trailing_active && (
          <Badge variant="secondary" className="text-xs">Trailing</Badge>
        )}
        <span className="text-muted-foreground ml-auto">
          {position.targets_hit}/{position.targets_hit + position.targets_remaining} targets
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

export default TrainingGround;
