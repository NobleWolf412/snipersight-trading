import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  Robot, StopCircle, Skull, Target, Clock, TrendUp, TrendDown,
  Wallet, ArrowsClockwise, CheckCircle, Warning, ShieldCheck,
} from '@phosphor-icons/react';
import { PageContainer } from '@/components/layout/PageContainer';
import { HomeButton } from '@/components/layout/HomeButton';
import { TacticalPanel } from '@/components/TacticalPanel';
import { liveTradingService, type LiveTradingStatus, type LivePosition } from '@/services/liveTradingService';

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function formatCurrency(v: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 }).format(v);
}

function formatPct(v: number) {
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

function ModeBadge({ mode }: { mode: string }) {
  if (mode === 'live') return (
    <Badge className="bg-red-500/20 text-red-400 border-red-500/40 font-mono text-xs animate-pulse">
      LIVE — REAL MONEY
    </Badge>
  );
  if (mode === 'testnet') return (
    <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/40 font-mono text-xs">
      TESTNET
    </Badge>
  );
  if (mode === 'dry_run') return (
    <Badge className="bg-zinc-500/20 text-zinc-400 border-zinc-500/40 font-mono text-xs">
      DRY RUN
    </Badge>
  );
  return null;
}

function PositionCard({ pos }: { pos: LivePosition }) {
  const isLong = pos.direction === 'LONG';
  const pnlColor = pos.unrealized_pnl >= 0 ? 'text-success' : 'text-destructive';
  return (
    <div className="p-4 rounded-xl border border-zinc-700/40 bg-background/40 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isLong
            ? <TrendUp size={16} weight="bold" className="text-success" />
            : <TrendDown size={16} weight="bold" className="text-destructive" />}
          <span className="font-mono font-bold text-sm">{pos.symbol}</span>
          <Badge className={cn('text-[10px]', isLong ? 'bg-success/10 text-success border-success/30' : 'bg-destructive/10 text-destructive border-destructive/30')}>
            {pos.direction}
          </Badge>
        </div>
        <span className={cn('font-mono font-bold text-sm', pnlColor)}>
          {formatCurrency(pos.unrealized_pnl)} <span className="text-xs opacity-70">({formatPct(pos.unrealized_pnl_pct)})</span>
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs text-zinc-400 font-mono">
        <div>Entry <span className="text-foreground">{pos.entry_price.toFixed(4)}</span></div>
        <div>Now <span className="text-foreground">{pos.current_price.toFixed(4)}</span></div>
        <div>SL <span className="text-destructive">{pos.stop_loss.toFixed(4)}</span></div>
      </div>
      <div className="flex gap-2 flex-wrap">
        {pos.breakeven_active && <Badge className="bg-accent/10 text-accent border-accent/30 text-[10px]">BE active</Badge>}
        {pos.trailing_active && <Badge className="bg-primary/10 text-primary border-primary/30 text-[10px]">Trailing</Badge>}
        <Badge className="bg-zinc-800 text-zinc-400 border-zinc-700 text-[10px]">{pos.trade_type}</Badge>
      </div>
    </div>
  );
}

function StatCard({ label, value, color = 'text-foreground', sub }: { label: string; value: string; color?: string; sub?: string }) {
  return (
    <div className="p-4 rounded-xl border border-zinc-700/40 bg-background/40 space-y-1">
      <p className="text-xs text-zinc-500 font-mono uppercase tracking-wider">{label}</p>
      <p className={cn('text-2xl font-bold font-mono', color)}>{value}</p>
      {sub && <p className="text-xs text-zinc-500">{sub}</p>}
    </div>
  );
}

export function BotStatus() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<LiveTradingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [stopping, setStopping] = useState(false);
  const [killing, setKilling] = useState(false);
  const [showKillConfirm, setShowKillConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const data = await liveTradingService.getStatus();
      setStatus(data);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 5000);
    return () => clearInterval(interval);
  }, [loadStatus]);

  const handleStop = async () => {
    setStopping(true);
    try {
      await liveTradingService.stop();
      await loadStatus();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setStopping(false);
    }
  };

  const handleKillSwitch = async () => {
    setKilling(true);
    setShowKillConfirm(false);
    try {
      await liveTradingService.killSwitch();
      await loadStatus();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setKilling(false);
    }
  };

  const handleReset = async () => {
    try {
      await liveTradingService.reset();
      navigate('/bot/setup');
    } catch (e: any) {
      setError(e.message);
    }
  };

  const isRunning = status?.status === 'running';
  const isStopped = status?.status === 'stopped' || status?.status === 'idle' || status?.status === 'kill_switched';
  const tradingMode = status?.trading_mode ?? 'idle';
  const isLive = tradingMode === 'live';
  const stats = status?.statistics;
  const balance = status?.balance;

  return (
    <div className="min-h-screen text-foreground" id="main-content">
      <main className="py-10 md:py-14">
        <PageContainer>
          <div className="space-y-8 max-w-5xl mx-auto">
            <div className="flex justify-start">
              <HomeButton />
            </div>

            {/* Header */}
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div className="flex items-center gap-4">
                <div className="relative">
                  <Robot size={44} weight="bold" className={isRunning ? 'text-warning' : 'text-zinc-500'} />
                  {isRunning && (
                    <div className="absolute inset-0 animate-ping opacity-20">
                      <Robot size={44} weight="bold" className="text-warning" />
                    </div>
                  )}
                </div>
                <div>
                  <h1 className="text-3xl font-bold heading-hud">
                    {isRunning ? 'BOT ACTIVE' : 'BOT OFFLINE'}
                  </h1>
                  <div className="flex items-center gap-2 mt-1">
                    {isRunning && <div className="w-2 h-2 rounded-full bg-success animate-pulse" />}
                    <ModeBadge mode={tradingMode} />
                    {status?.session_id && (
                      <span className="text-xs text-zinc-500 font-mono">#{status.session_id}</span>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex gap-2">
                {isRunning && (
                  <>
                    <Button
                      onClick={handleStop}
                      disabled={stopping}
                      variant="outline"
                      className="border-zinc-600 hover:border-zinc-400 h-10"
                    >
                      {stopping ? <ArrowsClockwise size={16} className="animate-spin" /> : <StopCircle size={16} weight="bold" />}
                      Stop
                    </Button>
                    <Button
                      onClick={() => setShowKillConfirm(true)}
                      className="bg-destructive hover:bg-destructive/80 text-white h-10 px-4"
                    >
                      <Skull size={16} weight="bold" />
                      KILL SWITCH
                    </Button>
                  </>
                )}
                {isStopped && (
                  <>
                    <Button onClick={() => navigate('/bot/setup')} variant="outline" className="border-zinc-600 h-10">
                      Reconfigure
                    </Button>
                    <Button onClick={handleReset} variant="outline" className="border-zinc-600 h-10">
                      <ArrowsClockwise size={16} /> Reset
                    </Button>
                  </>
                )}
              </div>
            </div>

            {/* Kill switch confirm */}
            {showKillConfirm && (
              <TacticalPanel className="border-red-500/60 bg-red-500/10">
                <div className="p-5 space-y-3">
                  <p className="font-bold text-red-400 flex items-center gap-2">
                    <Skull size={18} weight="bold" /> Confirm Kill Switch
                  </p>
                  <p className="text-sm text-zinc-300">
                    This will immediately cancel all open orders and close all positions at market price.
                    {isLive && ' This will use real money.'}
                  </p>
                  <div className="flex gap-3">
                    <Button onClick={() => setShowKillConfirm(false)} variant="outline" className="border-zinc-600">
                      Cancel
                    </Button>
                    <Button onClick={handleKillSwitch} disabled={killing} className="bg-red-600 hover:bg-red-500 text-white">
                      {killing ? <ArrowsClockwise size={16} className="animate-spin" /> : <Skull size={16} weight="bold" />}
                      Confirm Kill Switch
                    </Button>
                  </div>
                </div>
              </TacticalPanel>
            )}

            {error && (
              <div className="p-4 rounded-lg border border-destructive/40 bg-destructive/10 text-destructive text-sm flex items-center gap-2">
                <Warning size={16} /> {error}
              </div>
            )}

            {status?.status === 'kill_switched' && (
              <TacticalPanel className="border-red-500/40 bg-red-500/5">
                <div className="p-4 flex items-center gap-3">
                  <Skull size={20} weight="bold" className="text-red-400" />
                  <span className="text-red-400 font-mono text-sm">KILL SWITCH ACTIVATED — all positions closed</span>
                </div>
              </TacticalPanel>
            )}

            {loading && !status && (
              <div className="text-center py-20 text-zinc-500 font-mono text-sm">Loading...</div>
            )}

            {status && (
              <>
                {/* Mission Status */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <StatCard
                    label="Status"
                    value={status.status.toUpperCase()}
                    color={isRunning ? 'text-success' : 'text-zinc-400'}
                  />
                  <StatCard
                    label="Uptime"
                    value={formatDuration(status.uptime_seconds)}
                    color="text-primary"
                  />
                  <StatCard
                    label="Positions"
                    value={`${status.positions.length}/${status.config?.max_positions ?? 3}`}
                    color="text-accent"
                    sub="open / max"
                  />
                  <StatCard
                    label="Next Scan"
                    value={status.next_scan_in_seconds != null ? `${Math.round(status.next_scan_in_seconds)}s` : '—'}
                    color="text-warning"
                  />
                </div>

                {/* Balance */}
                {balance && (
                  <TacticalPanel>
                    <div className="p-5 space-y-4">
                      <p className="text-xs font-mono uppercase tracking-wider text-zinc-400 flex items-center gap-2">
                        <Wallet size={14} /> Balance
                      </p>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div>
                          <p className="text-xs text-zinc-500">Starting</p>
                          <p className="font-mono font-bold text-lg">{formatCurrency(balance.initial)}</p>
                        </div>
                        <div>
                          <p className="text-xs text-zinc-500">Current</p>
                          <p className="font-mono font-bold text-lg">{formatCurrency(balance.current)}</p>
                        </div>
                        <div>
                          <p className="text-xs text-zinc-500">Equity</p>
                          <p className="font-mono font-bold text-lg">{formatCurrency(balance.equity)}</p>
                        </div>
                        <div>
                          <p className="text-xs text-zinc-500">P&L</p>
                          <p className={cn('font-mono font-bold text-lg', balance.pnl >= 0 ? 'text-success' : 'text-destructive')}>
                            {formatCurrency(balance.pnl)}
                            <span className="text-sm ml-1 opacity-70">({formatPct(balance.pnl_pct)})</span>
                          </p>
                        </div>
                      </div>
                    </div>
                  </TacticalPanel>
                )}

                {/* Active Positions */}
                {status.positions.length > 0 && (
                  <div className="space-y-3">
                    <p className="text-xs font-mono uppercase tracking-wider text-zinc-400 flex items-center gap-2">
                      <Target size={14} /> Active Positions ({status.positions.length})
                    </p>
                    <div className="grid md:grid-cols-2 gap-3">
                      {status.positions.map(pos => (
                        <PositionCard key={pos.position_id} pos={pos} />
                      ))}
                    </div>
                  </div>
                )}

                {/* Performance stats */}
                {stats && (
                  <TacticalPanel>
                    <div className="p-5 space-y-4">
                      <p className="text-xs font-mono uppercase tracking-wider text-zinc-400 flex items-center gap-2">
                        <TrendUp size={14} /> Performance
                      </p>
                      <div className="grid grid-cols-3 md:grid-cols-6 gap-4 text-center">
                        {[
                          { label: 'Trades', value: String(stats.total_trades) },
                          { label: 'Win Rate', value: `${stats.win_rate.toFixed(1)}%`, color: stats.win_rate >= 50 ? 'text-success' : 'text-destructive' },
                          { label: 'Total P&L', value: formatCurrency(stats.total_pnl), color: stats.total_pnl >= 0 ? 'text-success' : 'text-destructive' },
                          { label: 'Avg Win', value: formatCurrency(stats.avg_win), color: 'text-success' },
                          { label: 'Avg Loss', value: formatCurrency(stats.avg_loss), color: 'text-destructive' },
                          { label: 'Max DD', value: `${stats.max_drawdown.toFixed(1)}%`, color: stats.max_drawdown > 10 ? 'text-warning' : 'text-zinc-400' },
                        ].map(({ label, value, color }) => (
                          <div key={label}>
                            <p className="text-xs text-zinc-500 font-mono">{label}</p>
                            <p className={cn('font-bold font-mono text-sm mt-0.5', color ?? 'text-foreground')}>{value}</p>
                          </div>
                        ))}
                      </div>
                      <div className="flex gap-6 pt-2 border-t border-zinc-800 text-xs text-zinc-500 font-mono">
                        <span>Scans: <span className="text-foreground">{stats.scans_completed}</span></span>
                        <span>Signals: <span className="text-foreground">{stats.signals_generated}</span></span>
                        <span>Taken: <span className="text-foreground">{stats.signals_taken}</span></span>
                      </div>
                    </div>
                  </TacticalPanel>
                )}

                {/* Activity log */}
                {status.recent_activity.length > 0 && (
                  <TacticalPanel>
                    <div className="p-5 space-y-3">
                      <p className="text-xs font-mono uppercase tracking-wider text-zinc-400 flex items-center gap-2">
                        <Clock size={14} /> Recent Activity
                      </p>
                      <div className="space-y-1.5 max-h-48 overflow-y-auto">
                        {[...status.recent_activity].reverse().slice(0, 20).map((item, i) => (
                          <div key={i} className="flex items-start gap-3 text-xs font-mono">
                            <span className="text-zinc-600 flex-shrink-0 w-20 truncate">
                              {new Date(item.timestamp).toLocaleTimeString()}
                            </span>
                            <span className={cn(
                              'flex-shrink-0 w-28 truncate',
                              item.event_type.includes('error') ? 'text-destructive' :
                              item.event_type.includes('kill') ? 'text-red-400' :
                              item.event_type.includes('opened') ? 'text-success' :
                              item.event_type.includes('closed') ? 'text-accent' :
                              'text-zinc-400',
                            )}>
                              {item.event_type}
                            </span>
                            <span className="text-zinc-500 truncate">
                              {item.data?.symbol ?? item.data?.session_id ?? ''}
                              {item.data?.pnl != null ? ` ${formatCurrency(item.data.pnl)}` : ''}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </TacticalPanel>
                )}

                {/* Idle state CTA */}
                {isStopped && status.status !== 'kill_switched' && (
                  <TacticalPanel>
                    <div className="p-8 text-center space-y-4">
                      <ShieldCheck size={40} weight="bold" className="text-zinc-600 mx-auto" />
                      <p className="text-zinc-400 font-mono text-sm">Bot is offline. Configure and deploy to start trading.</p>
                      <Button onClick={() => navigate('/bot/setup')} className="bg-accent/20 border border-accent text-accent hover:bg-accent/30">
                        Configure Bot
                      </Button>
                    </div>
                  </TacticalPanel>
                )}
              </>
            )}
          </div>
        </PageContainer>
      </main>
    </div>
  );
}
