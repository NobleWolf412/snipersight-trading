import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import {
  Robot, StopCircle, Skull, Target, Clock, TrendUp, TrendDown,
  Wallet, ArrowsClockwise, Warning, ShieldCheck, ChartLine, ListBullets,
  ArrowUp, ArrowDown, Pulse, PlayCircle, CheckCircle, XCircle, Gear,
  Lightning, Fire,
} from '@phosphor-icons/react';
import { PageContainer } from '@/components/layout/PageContainer';
import { HomeButton } from '@/components/layout/HomeButton';
import { TacticalPanel } from '@/components/TacticalPanel';
import { GauntletBreakdown } from '@/components/bot/GauntletBreakdown';
import { WatchlistRadar } from '@/components/bot/WatchlistRadar';
import { PhemexStatusPill } from '@/components/bot/PhemexStatusPill';
import {
  liveTradingService,
  type LiveTradingStatus,
  type LivePosition,
  type CompletedLiveTrade,
} from '@/services/liveTradingService';

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function formatCurrency(v: number, decimals = 2): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD',
    minimumFractionDigits: decimals, maximumFractionDigits: decimals,
  }).format(v);
}

function formatPct(v: number, decimals = 2): string {
  return `${v >= 0 ? '+' : ''}${v.toFixed(decimals)}%`;
}

// ── Equity Sparkline ─────────────────────────────────────────────────────────
function EquitySparkline({ trades, initialBalance }: { trades: CompletedLiveTrade[]; initialBalance: number }) {
  const points = useMemo(() => {
    if (!trades || trades.length === 0) return [];
    const sorted = [...trades].reverse();
    let equity = initialBalance;
    const pts = [{ x: 0, y: equity }];
    sorted.forEach((t, i) => { equity += t.pnl; pts.push({ x: i + 1, y: equity }); });
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
  const w = 280; const h = 56; const pad = 2;

  const pathD = points.map((p, i) => {
    const x = pad + (p.x / (points.length - 1)) * (w - 2 * pad);
    const y = h - pad - ((p.y - minY) / rangeY) * (h - 2 * pad);
    return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(' ');

  const lastPt = points[points.length - 1];
  const isUp = lastPt.y >= initialBalance;
  const strokeColor = isUp ? '#00ff88' : '#ff4444';
  const fillGradId = 'lv-eq-grad';
  const lastPtX = pad + (lastPt.x / (points.length - 1)) * (w - 2 * pad);
  const lastPtY = h - pad - ((lastPt.y - minY) / rangeY) * (h - 2 * pad);
  const areaD = pathD + ` L ${lastPtX.toFixed(1)} ${h} L ${pad.toFixed(1)} ${h} Z`;

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
      <circle cx={lastPtX} cy={lastPtY} r="3" fill={strokeColor} className="animate-pulse" />
    </svg>
  );
}

// ── Chart Level Modal ─────────────────────────────────────────────────────────
interface ChartLevel { label: string; price: number; color: string; bgColor: string }

function PositionChartModal({ open, onClose, symbol, direction, levels, title }: {
  open: boolean; onClose: () => void; symbol: string; direction: string;
  levels: ChartLevel[]; title?: string;
}) {
  const isLong = direction === 'LONG';
  const sortedLevels = [...levels].sort((a, b) => b.price - a.price);
  const prices = levels.map(l => l.price).filter(p => p > 0);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const priceRange = maxPrice - minPrice || maxPrice * 0.01;

  return (
    <Dialog open={open} onOpenChange={v => !v && onClose()}>
      <DialogContent className="bg-background border-border/50 p-0 overflow-hidden max-w-sm">
        <div className="p-4 border-b border-border/30 bg-black/40">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className={cn('font-mono text-xs border', isLong ? 'bg-green-500/10 text-green-400 border-green-500/30' : 'bg-red-500/10 text-red-400 border-red-500/30')}>
                {direction}
              </Badge>
              <span className="font-bold text-lg">{symbol}</span>
            </div>
            {title && <span className="text-xs text-muted-foreground font-mono">{title}</span>}
          </div>
        </div>
        <div className="flex-1 relative px-3 py-4 overflow-hidden" style={{ minHeight: 200 }}>
          <div className="relative" style={{ height: 180 }}>
            {sortedLevels.map((level, i) => {
              const pct = priceRange > 0 ? ((level.price - minPrice) / priceRange) * 100 : 50;
              const topPct = 100 - pct;
              return (
                <div key={i} className="absolute left-0 right-0 flex items-center gap-1.5"
                  style={{ top: `${Math.min(Math.max(topPct, 2), 94)}%`, transform: 'translateY(-50%)' }}>
                  <div className={cn('w-full h-px opacity-40', level.bgColor.replace('/10', '/60').replace('bg-', 'bg-'))} />
                  <div className={cn('shrink-0 text-right w-full absolute right-0')}>
                    <div className="flex items-center justify-end gap-1">
                      <span className={cn('text-[8px] font-mono font-bold uppercase tracking-widest', level.color)}>{level.label}</span>
                    </div>
                    <div className={cn('text-[10px] font-mono font-bold', level.color)}>
                      ${level.price < 1 ? level.price.toFixed(5) : level.price < 100 ? level.price.toFixed(4) : level.price.toFixed(2)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        <div className="border-t border-border/30 p-3 space-y-1.5">
          {sortedLevels.map((level, i) => (
            <div key={i} className="flex items-center justify-between text-xs font-mono">
              <span className={cn('text-[10px] font-bold uppercase tracking-widest', level.color)}>{level.label}</span>
              <span className={cn('font-bold', level.color)}>
                ${level.price < 1 ? level.price.toFixed(5) : level.price < 100 ? level.price.toFixed(4) : level.price.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Position Card ─────────────────────────────────────────────────────────────
function PositionCard({ position, leverage }: { position: LivePosition; leverage?: number }) {
  const isLong = position.direction === 'LONG';
  const isProfitable = position.unrealized_pnl >= 0;
  const [chartOpen, setChartOpen] = useState(false);

  const prevPriceRef = useRef(position.current_price);
  const [flashClass, setFlashClass] = useState('');
  useEffect(() => {
    if (position.current_price > prevPriceRef.current) {
      setFlashClass('animate-flash-green');
      const t = setTimeout(() => setFlashClass(''), 1000);
      prevPriceRef.current = position.current_price;
      return () => clearTimeout(t);
    } else if (position.current_price < prevPriceRef.current) {
      setFlashClass('animate-flash-red');
      const t = setTimeout(() => setFlashClass(''), 1000);
      prevPriceRef.current = position.current_price;
      return () => clearTimeout(t);
    }
  }, [position.current_price]);

  const initialSL = position.initial_stop_loss ?? position.stop_loss;
  const initialRisk = Math.abs(position.entry_price - initialSL);
  const currentProfit = isLong
    ? position.current_price - position.entry_price
    : position.entry_price - position.current_price;
  const rMultiple = initialRisk > 0 ? currentProfit / initialRisk : 0;

  const sl = position.stop_loss;
  const entry = position.entry_price;
  const tp1 = position.tp1 ?? null;
  const current = position.current_price;
  const timeInTrade = useMemo(() => {
    if (!position.opened_at) return null;
    const ms = Date.now() - new Date(position.opened_at).getTime();
    return formatDuration(Math.floor(ms / 1000));
  }, [position.opened_at]);
  let progressPct = 50;
  if (isLong) {
    if (current >= entry && tp1 != null) {
      const range = tp1 - entry;
      progressPct = range > 0 ? 50 + ((current - entry) / range) * 50 : 50;
    } else if (current < entry) {
      const range = entry - sl;
      progressPct = range > 0 ? ((current - sl) / range) * 50 : 50;
    }
  } else {
    if (current <= entry && tp1 != null) {
      const range = entry - tp1;
      progressPct = range > 0 ? 50 + ((entry - current) / range) * 50 : 50;
    } else if (current > entry) {
      const range = sl - entry;
      progressPct = range > 0 ? ((sl - current) / range) * 50 : 50;
    }
  }
  progressPct = Math.max(0, Math.min(100, progressPct));

  const chartLevels: ChartLevel[] = [
    ...(position.tp_final && position.tp_final !== position.tp1 && position.tp_final !== position.tp2 ? [{ label: 'TP3', price: position.tp_final, color: 'text-emerald-300', bgColor: 'bg-emerald-400/10' }] : []),
    ...(position.tp2 && position.tp2 !== position.tp1 && position.tp2 !== position.tp_final ? [{ label: 'TP2', price: position.tp2, color: 'text-green-300', bgColor: 'bg-green-400/10' }] : []),
    ...(position.tp1 ? [{ label: 'TP1', price: position.tp1, color: 'text-green-400', bgColor: 'bg-green-500/10' }] : []),
    { label: 'Current', price: position.current_price, color: 'text-yellow-400', bgColor: 'bg-yellow-500/10' },
    { label: 'Entry', price: position.entry_price, color: 'text-blue-400', bgColor: 'bg-blue-500/10' },
    { label: 'SL', price: position.stop_loss, color: 'text-red-400', bgColor: 'bg-red-500/10' },
  ].filter(l => l.price > 0);

  const targetPnl = position.target_pnl ?? 0;
  const riskPnl = position.risk_pnl ?? 0;

  return (
    <>
      <PositionChartModal
        open={chartOpen}
        onClose={() => setChartOpen(false)}
        symbol={position.symbol}
        direction={position.direction}
        levels={chartLevels}
        title={`${position.trade_type ?? 'intraday'} · ${isProfitable ? '+' : ''}${position.unrealized_pnl_pct.toFixed(2)}%`}
      />
      <div
        onClick={() => setChartOpen(true)}
        className={cn('p-3 bg-background rounded-lg border border-border hover:border-accent/30 transition-all duration-300 relative overflow-hidden cursor-pointer group', flashClass)}
      >
        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-60 transition-opacity">
          <ChartLine size={14} className="text-accent" />
        </div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className={cn('font-mono text-[10px] tracking-widest uppercase border', isLong ? 'bg-green-500/10 text-green-400 border-green-500/30' : 'bg-red-500/10 text-red-400 border-red-500/30')}>
              {isLong ? <ArrowUp size={12} className="mr-1" /> : <ArrowDown size={12} className="mr-1" />}
              {position.direction}
            </Badge>
            <span className="font-bold text-lg tracking-tight italic text-foreground">{position.symbol}</span>
            {position.trade_type && (
              <span className={cn('text-[9px] font-mono uppercase tracking-widest px-1.5 py-0.5 rounded-full border',
                position.trade_type === 'scalp' ? 'text-yellow-400/70 border-yellow-400/20' :
                position.trade_type === 'swing' ? 'text-purple-400/70 border-purple-400/20' :
                'text-blue-400/70 border-blue-400/20')}>
                {position.trade_type}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className={cn('font-mono text-[10px] font-bold px-1.5 py-0.5 rounded border', rMultiple >= 0 ? 'text-green-400/80 border-green-400/20' : 'text-red-400/80 border-red-400/20')}>
              {rMultiple >= 0 ? '+' : ''}{rMultiple.toFixed(1)}R
            </span>
            <span className={cn('font-mono text-sm font-bold px-2 py-0.5 rounded transition-colors', isProfitable ? 'text-green-400' : 'text-red-400')}>
              {formatPct(position.unrealized_pnl_pct)}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-y-4 gap-x-2 text-[10px] sm:text-xs mb-4 leading-tight">
          <div>
            <div className="text-muted-foreground uppercase tracking-widest text-[9px] mb-0.5">Size</div>
            <div className="font-mono text-accent font-bold">{formatCurrency(position.quantity * position.entry_price)}</div>
          </div>
          <div>
            <div className="text-muted-foreground uppercase tracking-widest text-[9px] mb-0.5">Entry</div>
            <div className="font-mono">${entry < 1 ? entry.toFixed(5) : entry < 100 ? entry.toFixed(4) : entry.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-muted-foreground uppercase tracking-widest text-[9px] mb-0.5">Current</div>
            <div className="font-mono font-bold">${current < 1 ? current.toFixed(5) : current < 100 ? current.toFixed(4) : current.toFixed(2)}</div>
          </div>
          {targetPnl !== 0 && (
            <div>
              <div className="text-muted-foreground uppercase tracking-widest text-[9px] mb-0.5">Est. Profit</div>
              <div className="font-mono text-green-400 font-bold">{formatCurrency(targetPnl)}</div>
            </div>
          )}
          {riskPnl !== 0 && (
            <div>
              <div className="text-muted-foreground uppercase tracking-widest text-[9px] mb-0.5">Risk Profile</div>
              <div className="font-mono text-red-400 font-bold">{formatCurrency(riskPnl)}</div>
            </div>
          )}
          <div>
            <div className="text-muted-foreground uppercase tracking-widest text-[9px] mb-0.5">TP / SL</div>
            <div className="font-mono text-[10px] opacity-80">
              {tp1 != null && (
                <><span className="text-green-500/80">${tp1 < 1 ? tp1.toFixed(5) : tp1 < 100 ? tp1.toFixed(4) : tp1.toFixed(2)}</span>
                <span className="mx-1 opacity-30">/</span></>
              )}
              <span className="text-red-500/80">${sl < 1 ? sl.toFixed(5) : sl < 100 ? sl.toFixed(4) : sl.toFixed(2)}</span>
            </div>
          </div>
          {timeInTrade && (
            <div>
              <div className="text-muted-foreground uppercase tracking-widest text-[9px] mb-0.5">Open</div>
              <div className="font-mono text-[10px] text-amber-400/80">{timeInTrade}</div>
            </div>
          )}
          {leverage != null && leverage > 1 && (
            <div>
              <div className="text-muted-foreground uppercase tracking-widest text-[9px] mb-0.5">Leverage</div>
              <div className="font-mono text-[10px] font-bold">{leverage}×</div>
            </div>
          )}
        </div>

        {/* Progress bar */}
        <div className="space-y-2 mb-2">
          <div className="grid grid-cols-3 mt-1 text-[9px] font-mono text-muted-foreground uppercase tracking-tight">
            <span className="text-red-400/70 text-left truncate">STOP {riskPnl !== 0 ? `(${formatCurrency(riskPnl)})` : ''}</span>
            <span className="text-center opacity-50">ENTRY</span>
            <span className="text-green-400/70 text-right truncate">TARGET {targetPnl !== 0 ? `(${formatCurrency(targetPnl)})` : ''}</span>
          </div>
          <div className="hud-progress-bg">
            <div className="hud-progress-indicator transition-all duration-500 ease-out" style={{ left: `${progressPct}%` }} />
          </div>
        </div>

        {/* Target ladder */}
        {((position.targets_hit ?? 0) + (position.targets_remaining ?? 0)) > 0 && (
          <div className="mt-2 pt-3 border-t border-border/50">
            <div className="flex items-center justify-between text-[9px] uppercase font-bold text-muted-foreground mb-1.5 tracking-widest">
              <span className="flex items-center gap-1"><Target size={10} /> Targets</span>
              <span className="text-accent/80 font-mono">{position.targets_hit ?? 0}/{(position.targets_hit ?? 0) + (position.targets_remaining ?? 0)} hit</span>
            </div>
            <div className="flex gap-1.5">
              {Array.from({ length: (position.targets_hit ?? 0) + (position.targets_remaining ?? 0) }).map((_, i) => (
                <div key={i} className={cn('h-1.5 flex-1 rounded-sm relative overflow-hidden',
                  i < (position.targets_hit ?? 0)
                    ? (isLong ? 'bg-green-400/70' : 'bg-red-400/70')
                    : 'bg-muted/20 border border-border/30')}>
                  {i < (position.targets_hit ?? 0) && <div className="absolute inset-0 bg-white/10" />}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="mt-3 flex items-center gap-2 text-xs">
          {position.breakeven_active && (
            <Badge variant="secondary" className="text-[9px] uppercase font-bold bg-blue-500/10 text-blue-400 border-blue-500/30">BE Active</Badge>
          )}
          {position.trailing_active && (
            <Badge variant="secondary" className="text-[9px] uppercase font-bold border-accent/30 text-accent bg-accent/10">Trailing</Badge>
          )}
          {(position.targets_hit !== undefined || position.targets_remaining !== undefined) && (
            <span className="text-muted-foreground ml-auto text-[9px] uppercase font-bold tracking-widest opacity-60">
              Targets: {position.targets_hit ?? 0}/{(position.targets_hit ?? 0) + (position.targets_remaining ?? 0)}
            </span>
          )}
        </div>
      </div>
    </>
  );
}

// ── Trade History Item ────────────────────────────────────────────────────────
function TradeHistoryItem({ trade }: { trade: CompletedLiveTrade }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = trade.direction === 'LONG';
  const isProfitable = trade.pnl >= 0;

  const duration = useMemo(() => {
    if (!trade.entry_time || !trade.exit_time) return null;
    const ms = new Date(trade.exit_time).getTime() - new Date(trade.entry_time).getTime();
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
      className={cn('rounded-lg border transition-all cursor-pointer overflow-hidden',
        expanded ? 'bg-background/80 border-accent/40 shadow-[0_0_15px_rgba(0,255,170,0.05)]' : 'bg-background border-border hover:border-border/80')}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center justify-between p-3">
        <div className="flex items-center gap-3">
          <Badge variant={isLong ? 'default' : 'destructive'}
            className={cn('text-xs px-2 py-0.5 border-none', isLong ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400')}>
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
            <div className="text-xs text-muted-foreground flex items-center gap-1.5 font-mono">
              <span>${trade.entry_price.toFixed(4)}</span>
              <span className={cn('text-[10px] font-bold', isLong ? 'text-green-400/60' : 'text-red-400/60')}>{isLong ? '↑' : '↓'}</span>
              <span>${trade.exit_price.toFixed(4)}</span>
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className={cn('font-mono font-bold text-sm', isProfitable ? 'text-green-400' : 'text-red-400')}>{formatCurrency(trade.pnl)}</div>
          <div className={cn('text-[10px] font-mono', isProfitable ? 'text-green-400/70' : 'text-red-400/70')}>{formatPct(trade.pnl_pct)}</div>
        </div>
      </div>

      {expanded && (
        <div className="px-3 pb-4 pt-2 border-t border-border/30 bg-black/20">
          {(() => {
            const rawMove = isLong
              ? (trade.exit_price - trade.entry_price) / trade.entry_price * 100
              : (trade.entry_price - trade.exit_price) / trade.entry_price * 100;
            const movedRight = rawMove >= 0;
            const entryLabel = isLong ? 'Bought at' : 'Sold at';
            const exitLabel = isLong ? 'Sold at' : 'Bought back at';
            return (
              <div className="mt-2 mb-3 rounded-xl overflow-hidden" style={{ border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(0,0,0,0.4)' }}>
                <div className="grid grid-cols-3 divide-x divide-white/[0.06]">
                  <div className="p-3">
                    <div className="text-[9px] text-white/30 font-mono uppercase tracking-widest mb-1.5">{entryLabel}</div>
                    <div className="text-base font-black font-mono text-white/90" style={{ letterSpacing: '-0.02em' }}>${trade.entry_price.toFixed(4)}</div>
                    {trade.entry_time && (
                      <div className="text-[9px] text-white/25 font-mono mt-1">{new Date(trade.entry_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                    )}
                  </div>
                  <div className="p-3 flex flex-col items-center justify-center text-center gap-1">
                    <div className={cn('text-sm font-black font-mono', movedRight ? 'text-green-400' : 'text-red-400')}
                      style={{ textShadow: movedRight ? '0 0 16px rgba(74,222,128,0.5)' : '0 0 16px rgba(248,113,113,0.5)' }}>
                      {movedRight ? '+' : ''}{rawMove.toFixed(3)}%
                    </div>
                    <div className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full"
                      style={{ background: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.4)' }}>
                      {displayReason}
                    </div>
                  </div>
                  <div className="p-3 text-right">
                    <div className="text-[9px] text-white/30 font-mono uppercase tracking-widest mb-1.5">{exitLabel}</div>
                    <div className={cn('text-base font-black font-mono', isProfitable ? 'text-green-400' : 'text-red-400')}
                      style={{ letterSpacing: '-0.02em', textShadow: isProfitable ? '0 0 16px rgba(74,222,128,0.4)' : '0 0 16px rgba(248,113,113,0.4)' }}>
                      ${trade.exit_price.toFixed(4)}
                    </div>
                    {trade.exit_time && (
                      <div className="text-[9px] text-white/25 font-mono mt-1">{new Date(trade.exit_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                    )}
                  </div>
                </div>
              </div>
            );
          })()}

          <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="space-y-1">
              <div className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest">Timing</div>
              <div className="text-xs font-mono text-foreground/80 flex flex-col gap-0.5">
                <span className="flex justify-between"><span className="text-muted-foreground/50">In:</span>{new Date(trade.entry_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
                {trade.exit_time && <span className="flex justify-between"><span className="text-muted-foreground/50">Out:</span>{new Date(trade.exit_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>}
                {duration && <span className="flex justify-between text-accent/80 mt-0.5 pt-0.5 border-t border-border/30"><span className="text-muted-foreground/50">Dur:</span>{duration}</span>}
              </div>
            </div>
            <div className="space-y-1">
              <div className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest">Excursion</div>
              <div className="text-xs font-mono flex flex-col gap-0.5">
                <span className="flex justify-between"><span className="text-muted-foreground/50">Peak:</span><span className="text-green-400/80">{formatPct(trade.max_favorable)}</span></span>
                <span className="flex justify-between"><span className="text-muted-foreground/50">Dip:</span><span className="text-red-400/80">{formatPct(-Math.abs(trade.max_adverse))}</span></span>
                <span className="flex justify-between mt-0.5 pt-0.5 border-t border-border/30"><span className="text-muted-foreground/50">Qty:</span><span className="text-foreground/80">{trade.quantity.toFixed(4)}</span></span>
              </div>
            </div>
            <div className="space-y-1">
              <div className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest">Execution</div>
              <div className="text-xs font-mono flex flex-col gap-0.5">
                <span className="flex justify-between"><span className="text-muted-foreground/50">Targets Hit:</span><span className="text-amber-400/80">{trade.targets_hit?.length || 0}</span></span>
                <span className="flex justify-between"><span className="text-muted-foreground/50">Confidence:</span><span className="text-foreground/80">{trade.confidence_score?.toFixed(0) ?? '—'}</span></span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Mode Badge ────────────────────────────────────────────────────────────────
function ModeBadge({ mode }: { mode: string }) {
  if (mode === 'live') return <Badge className="bg-red-500/20 text-red-400 border-red-500/40 font-mono text-xs animate-pulse">LIVE — REAL MONEY</Badge>;
  if (mode === 'testnet') return <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/40 font-mono text-xs">TESTNET</Badge>;
  if (mode === 'dry_run') return <Badge className="bg-zinc-500/20 text-zinc-400 border-zinc-500/40 font-mono text-xs">DRY RUN</Badge>;
  return null;
}

// ── Main Component ────────────────────────────────────────────────────────────
export function BotStatus() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<LiveTradingStatus | null>(null);
  const [trades, setTrades] = useState<CompletedLiveTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [stopping, setStopping] = useState(false);
  const [killing, setKilling] = useState(false);
  const [showKillConfirm, setShowKillConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeOutput, setAnalyzeOutput] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const fetchFailCount = useRef(0);
  const fastPollRef = useRef(false);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const connectionErrorRef = useRef<string | null>(null);
  connectionErrorRef.current = connectionError;
  // Distinguish "fetch failed" from "no trades yet" so the UI doesn't display
  // a misleading empty state when the backend is actually erroring.
  const [tradesLoaded, setTradesLoaded] = useState(false);
  const [tradesError, setTradesError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const data = await liveTradingService.getStatus();
      setStatus(data);
      fastPollRef.current = (data.positions?.length ?? 0) > 0 || data.current_scan?.status === 'running';
      fetchFailCount.current = 0;
      if (connectionErrorRef.current) setConnectionError(null);
    } catch (e: any) {
      fetchFailCount.current += 1;
      // Surface the failure on the first miss with the underlying message,
      // not after two silent rounds with a generic banner. A stale UI that
      // claims everything is fine is worse than an obvious error.
      const detail = e?.message || 'Unknown error';
      setConnectionError(`Backend unreachable: ${detail}`);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTrades = useCallback(async () => {
    try {
      const data = await liveTradingService.getHistory(50);
      // The backend always returns {trades:[], total:0, source:"merged"} — treat
      // a missing trades key as a shape mismatch, not an empty list.
      if (data && Array.isArray(data.trades)) {
        setTrades(data.trades);
        setTradesError(null);
      } else {
        setTradesError('Trade history response missing trades array');
      }
    } catch (e: any) {
      // Don't blank the existing trades on a transient error — show the prior
      // list with a banner so the operator can tell the difference between
      // "no trades" and "we couldn't fetch."
      setTradesError(e?.message || 'Could not load trade history');
    } finally {
      setTradesLoaded(true);
    }
  }, []);

  useEffect(() => {
    loadStatus();
    loadTrades();
    const schedule = () => {
      const delay = fastPollRef.current ? 2000 : 10000;
      pollTimerRef.current = setTimeout(async () => {
        await Promise.all([loadStatus(), loadTrades()]);
        schedule();
      }, delay);
    };
    schedule();
    return () => { if (pollTimerRef.current) clearTimeout(pollTimerRef.current); };
  }, [loadStatus, loadTrades]);

  const handleStop = async () => {
    setStopping(true);
    try { await liveTradingService.stop(); await loadStatus(); await loadTrades(); }
    catch (e: any) { setError(e.message); }
    finally { setStopping(false); }
  };

  const handleKillSwitch = async () => {
    setKilling(true);
    setShowKillConfirm(false);
    try { await liveTradingService.killSwitch(); await loadStatus(); }
    catch (e: any) { setError(e.message); }
    finally { setKilling(false); }
  };

  const handleReset = async () => {
    try { await liveTradingService.reset(); navigate('/bot/setup'); }
    catch (e: any) { setError(e.message); }
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setAnalyzeOutput(null);
    setAnalyzeError(null);
    try {
      const result = await liveTradingService.analyzeSession();
      setAnalyzeOutput(result.output || '(no output)');
      if (result.error) setAnalyzeError(result.error);
    } catch (e: any) {
      setAnalyzeError(e.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const isRunning = status?.status === 'running';
  const isStopped = status?.status === 'stopped' || status?.status === 'idle' || status?.status === 'kill_switched';
  const tradingMode = status?.trading_mode ?? 'idle';
  const isLive = tradingMode === 'live';
  const stats = status?.statistics;
  const balance = status?.balance;
  const initialBalance = balance?.initial || 0;

  return (
    <div className="min-h-screen text-foreground" id="main-content">
      <main className="py-10 md:py-14">
        <PageContainer>
          <div className="space-y-8 max-w-6xl mx-auto">
            <div className="flex justify-start"><HomeButton /></div>

            {/* Header */}
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div className="flex items-start gap-4">
                <div className="space-y-2">
                  <h1 className="text-3xl lg:text-4xl font-bold flex items-center gap-3 hud-headline tracking-widest" style={{ color: isLive ? '#f87171' : '#facc15' }}>
                    <Robot size={32} weight="bold" style={{ color: isLive ? '#f87171' : '#facc15' }} />
                    LIVE DEPLOYMENT
                  </h1>
                  <p className="font-mono text-sm text-muted-foreground uppercase tracking-widest pl-11">
                    {isLive ? 'Real money — Phemex perpetuals' : tradingMode === 'testnet' ? 'Testnet — simulated fills' : 'Dry run — no orders sent'}
                  </p>
                </div>
              </div>
              {status && (
                <Badge variant="outline" className={cn('text-sm px-3 py-1 font-mono tracking-widest uppercase border',
                  isRunning ? 'bg-green-500/10 text-green-400 border-green-500/30' :
                  isStopped ? 'bg-red-500/10 text-red-400 border-red-500/30' :
                  'bg-muted/50 text-muted-foreground border-border')}>
                  {isRunning && <Pulse size={14} className="mr-2 animate-pulse" />}
                  {status.status.toUpperCase()}
                </Badge>
              )}
            </div>

            {connectionError && (
              <div className="p-4 rounded-lg border border-yellow-500/40 bg-yellow-500/10 text-yellow-300 text-sm flex items-center gap-2">
                <Warning size={16} className="text-yellow-400" /> {connectionError}
              </div>
            )}
            {error && (
              <div className="p-4 rounded-lg border border-destructive/40 bg-destructive/10 text-destructive text-sm flex items-center gap-2">
                <Warning size={16} /> {error}
              </div>
            )}

            {loading && !status && (
              <div className="flex h-[400px] items-center justify-center glass-card rounded-2xl">
                <div className="flex flex-col items-center gap-4 text-accent opacity-70">
                  <ArrowsClockwise size={40} className="animate-spin" />
                  <p className="font-mono text-sm tracking-widest uppercase animate-pulse">Establishing Uplink...</p>
                </div>
              </div>
            )}

            {status && (
              <div className="space-y-6">

                {/* ── Command Center ─────────────────────────────────────────── */}
                <section className="rounded-2xl relative overflow-hidden" style={{
                  background: 'linear-gradient(135deg, rgba(0,0,0,0.7) 0%, rgba(10,20,15,0.8) 100%)',
                  border: isRunning ? '1px solid rgba(74,222,128,0.2)' : `1px solid ${isLive ? 'rgba(239,68,68,0.2)' : 'rgba(234,179,8,0.2)'}`,
                  boxShadow: isRunning ? '0 0 0 1px rgba(74,222,128,0.05), 0 8px 40px rgba(0,0,0,0.4)' : '0 0 0 1px rgba(234,179,8,0.05), 0 8px 40px rgba(0,0,0,0.4)',
                }}>
                  <div className="absolute inset-0 pointer-events-none" style={{
                    background: isRunning
                      ? 'radial-gradient(ellipse 80% 50% at 50% 0%, rgba(74,222,128,0.06) 0%, transparent 70%)'
                      : `radial-gradient(ellipse 80% 50% at 50% 0%, ${isLive ? 'rgba(239,68,68,0.06)' : 'rgba(234,179,8,0.06)'} 0%, transparent 70%)`,
                  }} />
                  <div className="relative z-10 p-5 space-y-5">

                    {/* Row 1: Identity + controls */}
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-4 min-w-0">
                        {/* Pulsing orb */}
                        <div className="relative flex-shrink-0 w-10 h-10 flex items-center justify-center">
                          <div className={cn('absolute inset-0 rounded-full animate-ping opacity-20', isRunning ? 'bg-green-400' : isLive ? 'bg-red-400' : 'bg-yellow-400')} style={{ animationDuration: '2.5s' }} />
                          <div className={cn('absolute inset-1 rounded-full opacity-30', isRunning ? 'bg-green-400/30' : isLive ? 'bg-red-400/30' : 'bg-yellow-400/30')} style={{ filter: 'blur(4px)' }} />
                          <div className={cn('relative w-4 h-4 rounded-full', isRunning ? 'bg-green-400 shadow-[0_0_16px_rgba(74,222,128,0.9)]' : isLive ? 'bg-red-400 shadow-[0_0_16px_rgba(239,68,68,0.9)]' : 'bg-yellow-400 shadow-[0_0_16px_rgba(234,179,8,0.9)]')} />
                        </div>
                        {/* Title */}
                        <div className="min-w-0">
                          <div className="flex items-center gap-2.5 flex-wrap">
                            <span className="text-base sm:text-lg font-black font-mono tracking-tight text-white/90 uppercase">Phantom Engine</span>
                            <ModeBadge mode={tradingMode} />
                            <span className={cn('text-[10px] font-black font-mono tracking-[0.2em] px-2 py-0.5 rounded-full border',
                              isRunning ? 'text-green-400 border-green-500/40 bg-green-500/10' : 'text-yellow-400 border-yellow-500/40 bg-yellow-500/10')}>
                              {isRunning ? 'LIVE' : 'PAUSED'}
                            </span>
                            <PhemexStatusPill isRunning={isRunning} />

                          </div>
                          <div className="text-[11px] text-white/30 font-mono mt-1 flex items-center gap-2 flex-wrap">
                            <Clock size={10} className="opacity-50" />
                            <span>{formatDuration(status?.uptime_seconds || 0)}</span>
                            {status?.session_id && <><span className="opacity-20">·</span><span className="opacity-40 truncate max-w-[120px]">{status.session_id.slice(0, 8)}</span></>}
                          </div>
                        </div>
                      </div>
                      {/* Controls */}
                      <div className="flex-shrink-0 flex gap-2">
                        {isRunning ? (
                          <>
                            <button onClick={handleStop} disabled={stopping}
                              className="flex items-center gap-2 px-4 py-2 rounded-lg font-mono font-black text-xs tracking-widest text-red-400 border border-red-500/30 bg-red-500/10 hover:bg-red-500/20 transition-all duration-200 disabled:opacity-40">
                              {stopping ? <ArrowsClockwise size={15} className="animate-spin" /> : <StopCircle size={15} />} STOP
                            </button>
                            <button onClick={() => setShowKillConfirm(true)}
                              className="flex items-center gap-2 px-4 py-2 rounded-lg font-mono font-black text-xs tracking-widest text-orange-400 border border-orange-500/30 bg-orange-500/10 hover:bg-orange-500/20 transition-all duration-200">
                              <Skull size={15} /> KILL
                            </button>
                          </>
                        ) : (
                          <div className="flex gap-2">
                            <button onClick={() => navigate('/bot/setup')}
                              className="flex items-center gap-2 px-4 py-2 rounded-lg font-mono font-black text-xs tracking-widest text-green-400 border border-green-500/30 bg-green-500/10 hover:bg-green-500/20 transition-all duration-200">
                              <PlayCircle size={15} /> RECONFIGURE
                            </button>
                            <button onClick={handleReset}
                              className="flex items-center justify-center w-9 h-9 rounded-lg text-white/40 border border-border/30 bg-black/20 hover:bg-black/40 transition-all duration-200">
                              <ArrowsClockwise size={15} />
                            </button>
                          </div>
                        )}
                        {/* Analyze Session — 3D button, always visible when logs exist */}
                        <button
                          onClick={handleAnalyze}
                          disabled={analyzing}
                          className="flex items-center gap-2 px-4 py-2 rounded-lg font-mono font-black text-xs tracking-widest text-cyan-300 disabled:opacity-40 transition-all duration-100 active:translate-y-px"
                          style={{
                            background: 'linear-gradient(180deg, #164e63 0%, #0e3a4a 60%, #0a2d3a 100%)',
                            border: '1px solid rgba(34,211,238,0.4)',
                            boxShadow: '0 4px 0 0 #061e27, 0 0 12px rgba(34,211,238,0.15), inset 0 1px 0 rgba(255,255,255,0.07)',
                          }}
                        >
                          {analyzing ? <ArrowsClockwise size={15} className="animate-spin" /> : <ChartLine size={15} />}
                          ANALYZE
                        </button>
                      </div>
                    </div>

                    {/* Kill switch confirm inline */}
                    {showKillConfirm && (
                      <div className="p-4 rounded-xl border border-red-500/60 bg-red-500/10 space-y-3">
                        <p className="font-bold text-red-400 flex items-center gap-2 text-sm"><Skull size={16} weight="bold" /> Confirm Kill Switch</p>
                        <p className="text-xs text-zinc-300">Immediately cancel all orders and close all positions at market price.{isLive && ' This uses real money.'}</p>
                        <div className="flex gap-3">
                          <button onClick={() => setShowKillConfirm(false)} className="px-4 py-2 rounded-lg text-xs font-mono border border-zinc-600 hover:bg-zinc-800 transition-colors">Cancel</button>
                          <button onClick={handleKillSwitch} disabled={killing}
                            className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-mono font-black bg-red-600 hover:bg-red-500 text-white transition-colors disabled:opacity-40">
                            {killing ? <ArrowsClockwise size={14} className="animate-spin" /> : <Skull size={14} weight="bold" />} Confirm Kill Switch
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Row 2: Metrics grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                      <div className="rounded-xl p-3 sm:p-4" style={{ background: 'rgba(0,0,0,0.35)', border: '1px solid rgba(255,255,255,0.06)' }}>
                        <div className="text-[9px] text-white/25 font-mono uppercase tracking-[0.18em] mb-2.5">Running</div>
                        <div className="text-xl sm:text-2xl font-black font-mono text-white/80 leading-none mb-1.5" style={{ letterSpacing: '-0.02em' }}>
                          {formatDuration(status?.uptime_seconds || 0)}
                        </div>
                        <div className="text-[10px] font-mono text-white/30">session uptime</div>
                      </div>
                      <div className="rounded-xl p-3 sm:p-4" style={{ background: 'rgba(0,0,0,0.35)', border: '1px solid rgba(255,255,255,0.06)' }}>
                        <div className="text-[9px] text-white/25 font-mono uppercase tracking-[0.18em] mb-2.5">Regime</div>
                        {status?.regime && status.regime.composite !== 'unknown' ? (
                          <>
                            <div className="text-xl sm:text-2xl font-black font-mono text-blue-400 leading-none mb-1.5 capitalize" style={{ letterSpacing: '-0.02em' }}>
                              {status.regime.composite.replace(/_/g, ' ').split(' ')[0].toUpperCase()}
                            </div>
                            <div className="text-[10px] font-mono text-white/30 uppercase tracking-wide">{status.regime.composite.replace(/_/g, ' ')}</div>
                          </>
                        ) : <div className="text-2xl font-black font-mono text-white/15">—</div>}
                      </div>
                      <div className="rounded-xl p-3 sm:p-4" style={{ background: 'rgba(0,0,0,0.35)', border: '1px solid rgba(255,255,255,0.06)' }}>
                        <div className="text-[9px] text-white/25 font-mono uppercase tracking-[0.18em] mb-2.5">Next Scan</div>
                        {isRunning && status?.next_scan_in_seconds != null ? (
                          <>
                            <div className="text-xl sm:text-2xl font-black font-mono text-amber-400 leading-none mb-1.5" style={{ textShadow: '0 0 24px rgba(251,191,36,0.5)', letterSpacing: '-0.02em' }}>
                              {formatDuration(Math.round(status.next_scan_in_seconds))}
                            </div>
                            <div className="text-[10px] font-mono text-white/30">until next scan</div>
                          </>
                        ) : <div className="text-2xl font-black font-mono text-white/15">—</div>}
                      </div>
                      <div className="rounded-xl p-3 sm:p-4" style={{ background: 'rgba(0,0,0,0.35)', border: '1px solid rgba(255,255,255,0.06)' }}>
                        <div className="text-[9px] text-white/25 font-mono uppercase tracking-[0.18em] mb-2.5">Min Score</div>
                        <div className="text-xl sm:text-2xl font-black font-mono text-white/70 leading-none mb-1.5" style={{ letterSpacing: '-0.02em' }}>
                          {status?.config?.min_confluence != null ? `≥${status.config.min_confluence}` : 'AUTO'}
                        </div>
                        <div className="text-[10px] font-mono text-white/30">confluence</div>
                      </div>
                    </div>

                    {/* Row 3: Config pills */}
                    {status?.config && (() => {
                      const cfg = status.config;
                      const pills = [
                        cfg.sniper_mode ? { label: cfg.sniper_mode.toUpperCase() } : null,
                        cfg.sensitivity_preset ? { label: cfg.sensitivity_preset.toUpperCase() } : null,
                        cfg.duration_hours != null ? { label: `${cfg.duration_hours}H` } : null,
                        cfg.max_positions != null ? { label: `${cfg.max_positions} SLOTS` } : null,
                        cfg.risk_per_trade != null ? { label: `${cfg.risk_per_trade}% RISK` } : null,
                        cfg.leverage != null && cfg.leverage !== 1 ? { label: `${cfg.leverage}× LEVERAGE` } : null,
                      ].filter(Boolean) as { label: string }[];
                      return (
                        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar pb-0.5">
                          {pills.map((pill, i) => (
                            <span key={i} className="flex-shrink-0 text-[10px] font-mono font-semibold px-2.5 py-1 rounded-md border text-white/70 border-white/20 bg-white/[0.07]">
                              {pill.label}
                            </span>
                          ))}
                        </div>
                      );
                    })()}

                    {/* Row 4: Scan progress */}
                    {status?.current_scan && (() => {
                      const scan = status.current_scan;
                      const isScanning = scan.status === 'running';
                      return (
                        <div className="space-y-2.5 pt-1 border-t border-white/[0.05]">
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2 min-w-0">
                              <Target size={12} className={cn('flex-shrink-0', isScanning ? 'text-amber-400 animate-pulse' : 'text-green-400')} />
                              <span className="text-[10px] font-mono text-white/40 uppercase tracking-widest truncate">
                                {isScanning ? `Scanning ${scan.current_symbol || '…'}` : 'Scan complete'}
                              </span>
                            </div>
                            <div className="flex items-center gap-3 flex-shrink-0 text-[10px] font-mono">
                              <span className="text-green-400 font-bold">{scan.passed} passed</span>
                              <span className="text-white/25">{scan.rejected} filtered</span>
                              <span className="text-white/20">{scan.completed}/{scan.total}</span>
                            </div>
                          </div>
                          <div className="relative h-1 rounded-full overflow-hidden" style={{ background: 'rgba(0,0,0,0.5)' }}>
                            <div className="h-full rounded-full transition-all duration-700" style={{
                              width: `${scan.progress_pct}%`,
                              background: isScanning ? 'linear-gradient(90deg, rgba(251,191,36,0.8), rgba(251,191,36,1))' : 'linear-gradient(90deg, rgba(74,222,128,0.7), rgba(74,222,128,1))',
                              boxShadow: isScanning ? '0 0 12px rgba(251,191,36,0.5)' : '0 0 10px rgba(74,222,128,0.4)',
                            }} />
                          </div>
                          {scan.recent_symbols && scan.recent_symbols.length > 0 && (
                            <div className="flex gap-1.5 overflow-x-auto no-scrollbar">
                              {scan.recent_symbols.map((item, idx) => (
                                <span key={`${item.symbol}-${idx}`} className={cn('flex-shrink-0 text-[9px] font-mono px-1.5 py-0.5 rounded whitespace-nowrap',
                                  item.passed ? 'text-green-400/80 bg-green-500/10' : 'text-white/20 bg-white/[0.03]')}>
                                  {item.symbol}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                </section>

                {/* Kill switched banner */}
                {status?.status === 'kill_switched' && (
                  <TacticalPanel className="border-red-500/40 bg-red-500/5">
                    <div className="p-4 flex items-center gap-3">
                      <Skull size={20} weight="bold" className="text-red-400" />
                      <span className="text-red-400 font-mono text-sm">KILL SWITCH ACTIVATED — all positions closed</span>
                    </div>
                  </TacticalPanel>
                )}

                {/* ── Equity Curve + Stats Row ─────────────────────────────── */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  {/* Session P&L hero (2 cols) */}
                  <div className="lg:col-span-2 glass-card p-5 rounded-2xl border-accent/30 relative group overflow-hidden">
                    <div className={cn('absolute top-0 left-0 right-0 h-0.5', (balance?.pnl ?? 0) >= 0 ? 'bg-gradient-to-r from-transparent via-green-400/60 to-transparent' : 'bg-gradient-to-r from-transparent via-red-400/60 to-transparent')} />
                    <div className="relative z-10">
                      <div className="text-[9px] text-muted-foreground font-mono font-bold tracking-[0.2em] uppercase mb-2 opacity-60 flex items-center gap-2">
                        <Wallet size={10} /> SESSION P&L
                      </div>
                      {(() => {
                        const initial = initialBalance;
                        const pnl = balance?.pnl ?? trades.reduce((s, t) => s + t.pnl, 0);
                        const pnlPct = balance?.pnl_pct ?? (initial > 0 ? (pnl / initial) * 100 : 0);
                        const realizedPnl = trades.reduce((s, t) => s + t.pnl, 0);
                        const wins = stats?.winning_trades ?? 0;
                        const losses = stats?.losing_trades ?? 0;
                        const avgWin = stats?.avg_win ?? 0;
                        const avgLoss = stats?.avg_loss ?? 0;
                        const grossWins = avgWin * wins;
                        const grossLosses = Math.abs(avgLoss) * losses;
                        const isPos = pnl >= 0;
                        return (
                          <>
                            <div className="flex items-end gap-4 mb-3">
                              <div className={cn('text-5xl font-bold font-mono tracking-tight leading-none', isPos ? 'text-green-400' : 'text-red-400')}
                                style={isPos ? { textShadow: '0 0 30px rgba(74,222,128,0.35)' } : { textShadow: '0 0 30px rgba(248,113,113,0.35)' }}>
                                {isPos ? '+' : ''}{formatCurrency(pnl)}
                              </div>
                              <div className="flex flex-col gap-1 pb-1">
                                <Badge variant="outline" className={cn('font-mono text-xs border tracking-widest self-start',
                                  isPos ? 'bg-green-500/10 text-green-400 border-green-500/30' : 'bg-red-500/10 text-red-400 border-red-500/30')}>
                                  {isPos ? '+' : ''}{pnlPct.toFixed(2)}%
                                </Badge>
                                <div className="text-[10px] text-muted-foreground/50 font-mono">
                                  {realizedPnl !== pnl ? `realized ${formatCurrency(realizedPnl)} · ` : ''}started {formatCurrency(initial)}
                                </div>
                              </div>
                            </div>
                            {(wins > 0 || losses > 0) && (
                              <div className="grid grid-cols-2 gap-2 mb-3 p-2.5 rounded-lg bg-black/30 border border-border/20">
                                <div>
                                  <div className="text-[9px] text-green-400/60 font-mono uppercase tracking-widest mb-0.5">GROSS WINS</div>
                                  <div className="text-base font-bold font-mono text-green-400">+{formatCurrency(grossWins)}</div>
                                  <div className="text-[9px] text-muted-foreground/40 font-mono">{wins} win{wins !== 1 ? 's' : ''} · avg {formatCurrency(avgWin)}</div>
                                </div>
                                <div>
                                  <div className="text-[9px] text-red-400/60 font-mono uppercase tracking-widest mb-0.5">GROSS LOSSES</div>
                                  <div className="text-base font-bold font-mono text-red-400">-{formatCurrency(grossLosses)}</div>
                                  <div className="text-[9px] text-muted-foreground/40 font-mono">{losses} loss{losses !== 1 ? 'es' : ''} · avg {formatCurrency(Math.abs(avgLoss))}</div>
                                </div>
                              </div>
                            )}
                          </>
                        );
                      })()}
                      <div className="p-2 rounded-lg bg-black/30 border border-border/30">
                        <EquitySparkline trades={trades} initialBalance={initialBalance} />
                      </div>
                      <div className="mt-2 flex items-center gap-2 text-[10px] text-muted-foreground/50 font-mono">
                        <span>{trades.length} completed trade{trades.length !== 1 ? 's' : ''}</span>
                      </div>
                    </div>
                  </div>

                  {/* Performance card */}
                  <div className="glass-card p-4 rounded-2xl border-border/50 relative group flex-1 min-w-0">
                    <div className="relative z-10 min-w-0">
                      <div className="text-[10px] text-muted-foreground font-mono font-bold tracking-wider uppercase mb-3">PERFORMANCE</div>
                      <div className="flex items-baseline gap-1.5 mb-2">
                        <span className="text-green-400 font-mono font-bold text-lg">{stats?.winning_trades || 0}W</span>
                        <span className="text-white/20 text-sm">/</span>
                        <span className="text-yellow-400/80 font-mono font-bold text-lg">{stats?.scratch_trades || 0}S</span>
                        <span className="text-white/20 text-sm">/</span>
                        <span className="text-red-400 font-mono font-bold text-lg">{stats?.losing_trades || 0}L</span>
                        <span className="text-muted-foreground text-xs ml-1">({stats?.total_trades || 0} trades)</span>
                      </div>
                      <div className="text-xs text-muted-foreground font-mono mb-3">
                        Win Rate: <span className={cn('font-bold', (stats?.win_rate ?? 0) >= 50 ? 'text-green-400' : 'text-amber-400')}>{(stats?.win_rate ?? 0).toFixed(0)}%</span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 mb-2">
                        <div className="p-2 rounded-lg bg-black/20">
                          <div className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest mb-0.5">EV / TRADE</div>
                          <div className={cn('text-base font-bold font-mono', (stats?.expectancy ?? 0) >= 0 ? 'text-green-400' : 'text-red-400')}>
                            {(stats?.expectancy ?? 0) >= 0 ? '+' : ''}{formatCurrency(stats?.expectancy ?? 0)}
                          </div>
                        </div>
                        <div className="p-2 rounded-lg bg-black/20">
                          <div className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest mb-0.5">AVG R:R</div>
                          <div className="text-base font-bold font-mono">{(stats?.avg_rr || 0).toFixed(2)}</div>
                        </div>
                      </div>
                      <div className="flex gap-3 text-xs font-mono">
                        <span>Avg W: <span className="text-green-400 font-bold">{formatCurrency(stats?.avg_win || 0)}</span></span>
                        <span className="opacity-20">|</span>
                        <span>Avg L: <span className="text-red-400 font-bold">{formatCurrency(stats?.avg_loss || 0)}</span></span>
                      </div>

                      {/* Balance section */}
                      {balance && balance.initial > 0 && (
                        <div className="mt-4 pt-3 border-t border-border/30 space-y-1.5">
                          <div className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest mb-2 flex items-center gap-1"><Wallet size={10} /> BALANCE</div>
                          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                            <div><span className="text-muted-foreground/60">Start</span><br /><span className="font-bold">{formatCurrency(balance.initial)}</span></div>
                            <div><span className="text-muted-foreground/60">Current</span><br /><span className="font-bold">{formatCurrency(balance.current)}</span></div>
                            <div><span className="text-muted-foreground/60">Equity</span><br /><span className="font-bold">{formatCurrency(balance.equity)}</span></div>
                            <div><span className="text-muted-foreground/60">P&L</span><br /><span className={cn('font-bold', balance.pnl >= 0 ? 'text-green-400' : 'text-red-400')}>{formatCurrency(balance.pnl)}</span></div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* ── Secondary Stats ─────────────────────────────────────── */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="glass-card p-4 rounded-2xl border-border/50 relative group min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <div><div className="text-[10px] text-muted-foreground font-mono font-bold tracking-wider uppercase">MAX DRAWDOWN</div>
                        <div className={cn('text-xl font-bold font-mono tracking-tight mt-0.5', stats?.max_drawdown ? 'text-red-400' : 'text-muted-foreground')}>
                          {(stats?.max_drawdown || 0).toFixed(2)}%
                        </div>
                      </div>
                      <TrendDown size={24} className="text-red-400/20 group-hover:text-red-400/50 shrink-0 transition-colors" />
                    </div>
                    <div className="mt-1.5 text-[10px] text-muted-foreground/60 font-mono">Peak-to-trough</div>
                  </div>
                  <div className="glass-card p-4 rounded-2xl border-border/50 relative group min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <div><div className="text-[10px] text-muted-foreground font-mono font-bold tracking-wider uppercase">PROFIT FACTOR</div>
                        {(() => {
                          const gw = (stats?.avg_win || 0) * (stats?.winning_trades || 0);
                          const gl = Math.abs(stats?.avg_loss || 0) * (stats?.losing_trades || 0);
                          const pf = gl > 0 ? gw / gl : (gw > 0 ? 99 : 0);
                          return <div className={cn('text-xl font-bold font-mono tracking-tight mt-0.5', pf === 0 ? 'text-muted-foreground' : pf >= 1.5 ? 'text-green-400' : pf >= 1 ? 'text-amber-400' : 'text-red-400')}>
                            {pf === 0 ? 'N/A' : pf >= 99 ? '∞' : `${pf.toFixed(2)}x`}
                          </div>;
                        })()}
                      </div>
                      <TrendUp size={24} className="text-accent/20 group-hover:text-accent/50 shrink-0 transition-colors" />
                    </div>
                    <div className="mt-1.5 text-[10px] text-muted-foreground/60 font-mono">Gross wins / gross losses</div>
                  </div>
                  {(stats?.winning_trades ?? 0) > 0 && (
                    <div className="glass-card p-4 rounded-2xl border-border/50 relative group min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <div><div className="text-[10px] text-muted-foreground font-mono font-bold tracking-wider uppercase">BEST TRADE</div>
                          <div className="text-xl font-bold font-mono tracking-tight mt-0.5 text-green-400">+{formatCurrency(stats?.best_trade ?? 0)}</div>
                        </div>
                        <TrendUp size={24} className="text-green-400/20 group-hover:text-green-400/50 shrink-0 transition-colors" />
                      </div>
                      <div className="mt-1.5 text-[10px] text-muted-foreground/60 font-mono">Single trade max profit</div>
                    </div>
                  )}
                  {(stats?.losing_trades ?? 0) > 0 && (
                    <div className="glass-card p-4 rounded-2xl border-border/50 relative group min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <div><div className="text-[10px] text-muted-foreground font-mono font-bold tracking-wider uppercase">WORST TRADE</div>
                          <div className="text-xl font-bold font-mono tracking-tight mt-0.5 text-red-400">{formatCurrency(stats?.worst_trade ?? 0)}</div>
                        </div>
                        <TrendDown size={24} className="text-red-400/20 group-hover:text-red-400/50 shrink-0 transition-colors" />
                      </div>
                      <div className="mt-1.5 text-[10px] text-muted-foreground/60 font-mono">Single trade max loss</div>
                    </div>
                  )}
                </div>

                {/* ── By Trade Type + Exit Reasons ────────────────────────── */}
                {stats && (Object.keys(stats.by_trade_type || {}).length > 0 || Object.keys(stats.exit_reasons || {}).length > 0) && (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {Object.keys(stats.by_trade_type || {}).length > 0 && (
                      <div className="glass-card p-4 rounded-2xl border-border/50">
                        <div className="text-[10px] text-muted-foreground font-mono font-bold tracking-wider uppercase mb-3">BY TRADE TYPE</div>
                        <div className="grid grid-cols-[80px_1fr_48px_48px_64px] gap-2 text-[9px] text-muted-foreground/50 font-mono uppercase tracking-widest mb-2 pb-1 border-b border-border/20">
                          <span>Type</span><span>Win Rate</span><span className="text-right">Win%</span><span className="text-right">Trades</span><span className="text-right">Net P&L</span>
                        </div>
                        {(['scalp', 'intraday', 'swing'] as const).filter(tt => stats.by_trade_type?.[tt]).map(tt => {
                          const b = stats.by_trade_type![tt];
                          if (!b) return null;
                          const color = tt === 'scalp' ? 'text-purple-400' : tt === 'intraday' ? 'text-blue-400' : 'text-amber-400';
                          const pnlColor = b.total_pnl >= 0 ? 'text-green-400' : 'text-red-400';
                          return (
                            <div key={tt} className="grid grid-cols-[80px_1fr_48px_48px_64px] gap-2 items-center text-xs font-mono py-1">
                              <span className={cn('font-bold uppercase tracking-tight', color)}>{tt}</span>
                              <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                                <div className={cn('h-full rounded-full', b.win_rate >= 50 ? 'bg-green-400/60' : 'bg-red-400/60')} style={{ width: `${b.win_rate}%` }} />
                              </div>
                              <span className="text-right text-muted-foreground">{b.win_rate.toFixed(0)}%</span>
                              <span className="text-right text-muted-foreground/60">{b.trades}</span>
                              <span className={cn('text-right font-bold', pnlColor)}>{b.total_pnl >= 0 ? '+' : ''}{b.total_pnl.toFixed(1)}</span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                    {Object.keys(stats.exit_reasons || {}).length > 0 && (
                      <div className="glass-card p-4 rounded-2xl border-border/50">
                        <div className="text-[10px] text-muted-foreground font-mono font-bold tracking-wider uppercase mb-3">EXIT REASONS</div>
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(stats.exit_reasons || {}).sort(([, a], [, b]) => b - a).map(([reason, count]) => {
                            const label = reason === 'stop_loss' ? 'Stop' : reason === 'target' ? 'Target' : reason === 'stagnation' ? 'Stagnation' : reason === 'direction_flip' ? 'Flip' : reason === 'emergency' ? 'Emergency' : reason === 'session_stopped' ? 'Session End' : reason.replace(/_/g, ' ');
                            const chipColor = reason === 'target' ? 'bg-green-400/15 border-green-400/30 text-green-400' : reason === 'stop_loss' ? 'bg-red-400/15 border-red-400/30 text-red-400' : reason === 'stagnation' ? 'bg-amber-400/15 border-amber-400/30 text-amber-400' : 'bg-white/5 border-border/40 text-muted-foreground';
                            const reasonPnl = trades.filter(t => t.exit_reason === reason).reduce((s, t) => s + t.pnl, 0);
                            const pnlStr = reasonPnl >= 0 ? `+${formatCurrency(reasonPnl)}` : formatCurrency(reasonPnl);
                            return (
                              <div key={reason} className={cn('flex flex-col gap-0.5 px-3 py-2 rounded-xl border text-[11px] font-mono font-bold', chipColor)}>
                                <div className="flex items-center gap-1.5"><span>{label}</span><span className="opacity-50 font-normal">×{count}</span></div>
                                <div className={cn('text-[10px] font-normal', reasonPnl >= 0 ? 'text-green-400/70' : 'text-red-400/70')}>{pnlStr}</div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* ── Positions & Risk Row ─────────────────────────────────── */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Active Positions */}
                  <section className="glass-card glow-border-green p-5 rounded-2xl h-full flex flex-col relative overflow-hidden group">
                    <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-green-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />
                    <div className="flex items-center justify-between mb-6 relative z-10">
                      <h2 className="text-xl lg:text-2xl font-semibold hud-headline hud-text-green tracking-wide flex items-center gap-3">
                        <ChartLine size={24} className="text-accent" /> ACTIVE POSITIONS
                      </h2>
                      <Badge variant="outline" className="bg-black/60 font-mono tracking-widest px-3 border-accent/40 text-accent glow-border-green">
                        {status?.positions?.length || 0}
                      </Badge>
                    </div>
                    <div className="relative z-10 space-y-10 mt-4">
                      {(status?.positions && status.positions.length > 0) ? (
                        <div>
                          <div className="flex items-center gap-3 mb-4">
                            <div className="h-px flex-1 bg-gradient-to-r from-transparent via-green-500/20 to-transparent" />
                            <h3 className="text-[10px] font-black tracking-[0.3em] uppercase text-green-400 bg-green-500/5 px-4 py-1 rounded-full border border-green-500/20">
                              ACTIVE ({status.positions.length})
                            </h3>
                            <div className="h-px flex-1 bg-gradient-to-r from-transparent via-green-500/20 to-transparent" />
                          </div>
                          <div className="space-y-4">
                            {status.positions.map((pos) => <PositionCard key={pos.position_id} position={pos} leverage={status?.config?.leverage} />)}
                          </div>
                        </div>
                      ) : null}
                      {(status?.pending_orders && status.pending_orders.length > 0) ? (
                        <div>
                          <div className="flex items-center gap-3 mb-4 mt-6">
                            <div className="h-px flex-1 bg-gradient-to-r from-transparent via-amber-500/20 to-transparent" />
                            <h3 className="text-[10px] font-black tracking-[0.3em] uppercase text-amber-400 bg-amber-500/5 px-4 py-1 rounded-full border border-amber-500/20">
                              PENDING ({status.pending_orders.length})
                            </h3>
                            <div className="h-px flex-1 bg-gradient-to-r from-transparent via-amber-500/20 to-transparent" />
                          </div>
                          <div className="space-y-3">
                            {status.pending_orders.map(order => (
                              <div key={order.order_id} className="p-3 bg-background/40 rounded-lg border border-amber-500/20 border-dashed">
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-2">
                                    <Badge variant="outline" className={cn('font-mono text-[9px] px-1.5 py-0 border-none', order.direction === 'LONG' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400')}>{order.direction}</Badge>
                                    <span className="font-bold text-sm">{order.symbol}</span>
                                    <span className="text-[9px] font-mono opacity-40 uppercase bg-amber-500/10 px-1 py-0 rounded">Waiting Fill</span>
                                  </div>
                                  <div className="text-xs font-bold font-mono text-amber-400/80">Limit ${order.limit_price.toFixed(4)}</div>
                                </div>
                                <div className="text-[10px] font-mono text-muted-foreground/60 mt-1">Qty: {order.quantity.toFixed(4)}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {!(status?.positions?.length) && !(status?.pending_orders?.length) && (
                        <div className="text-center py-20 px-4">
                          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-muted/5 border border-dashed border-muted/20 mb-4">
                            <Target size={32} className="text-muted-foreground/30" />
                          </div>
                          <h3 className="text-lg font-medium text-muted-foreground/80">No market exposure yet</h3>
                          <p className="text-sm text-muted-foreground/40 mt-1 max-w-xs mx-auto">
                            Monitoring for {status?.config?.sniper_mode ?? 'stealth'} setups.
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
                        <ShieldCheck size={24} className="text-amber-400" /> RISK &amp; EXPOSURE
                      </h2>
                    </div>
                    <div className="relative z-10 space-y-4 flex-1">
                      {(() => {
                        const positions = status?.positions || [];
                        const equity = balance?.equity || 0;
                        const totalExposure = positions.reduce((sum, p) => sum + (p.entry_price * p.quantity), 0);
                        const exposurePct = equity > 0 ? (totalExposure / equity) * 100 : 0;
                        const maxPositions = status?.config?.max_positions ?? 3;
                        const unrealizedPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
                        const riskPerTrade = status?.config?.risk_per_trade ?? 2;
                        return (
                          <>
                            <div className="grid grid-cols-2 gap-3">
                              <div className="p-3 rounded-xl bg-background/40 border border-border/30">
                                <div className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest mb-1">POSITIONS</div>
                                <div className="text-2xl font-mono font-bold">{positions.length}<span className="text-sm text-muted-foreground font-normal">/{maxPositions}</span></div>
                              </div>
                              <div className="p-3 rounded-xl bg-background/40 border border-border/30">
                                <div className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest mb-1">RISK / TRADE</div>
                                <div className="text-2xl font-mono font-bold">{riskPerTrade}%</div>
                                {equity > 0 && <div className="text-[10px] text-muted-foreground font-mono mt-0.5">{formatCurrency(equity * riskPerTrade / 100)} max</div>}
                              </div>
                            </div>
                            <div className="p-3 rounded-xl bg-background/40 border border-border/30">
                              <div className="flex justify-between items-center mb-2">
                                <span className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest">NOTIONAL EXPOSURE</span>
                                <span className={cn('text-xs font-mono font-bold', exposurePct > 50 ? 'text-amber-400' : 'text-green-400')}>{exposurePct.toFixed(1)}%</span>
                              </div>
                              <div className="h-2 rounded-full bg-black/40 overflow-hidden">
                                <div className={cn('h-full rounded-full transition-all duration-500', exposurePct > 75 ? 'bg-red-500' : exposurePct > 50 ? 'bg-amber-500' : 'bg-green-500')}
                                  style={{ width: `${Math.min(exposurePct, 100)}%` }} />
                              </div>
                              <div className="text-[10px] text-muted-foreground font-mono mt-1.5">{formatCurrency(totalExposure)} notional vs equity</div>
                            </div>
                            <div className="p-3 rounded-xl bg-background/40 border border-border/30">
                              <div className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest mb-1">TOTAL UNREALIZED P&amp;L</div>
                              <div className={cn('text-xl font-mono font-bold', unrealizedPnl > 0 ? 'text-green-400' : unrealizedPnl < 0 ? 'text-red-400' : 'text-muted-foreground')}>
                                {unrealizedPnl >= 0 ? '+' : ''}{formatCurrency(unrealizedPnl)}
                              </div>
                              <div className="text-[10px] text-muted-foreground font-mono mt-0.5">Across {positions.length} open position{positions.length !== 1 ? 's' : ''}</div>
                            </div>
                            {positions.length > 0 && (
                              <div className="space-y-2 pt-1">
                                <div className="text-[9px] text-muted-foreground font-mono uppercase tracking-widest">OPEN P&L BREAKDOWN</div>
                                {positions.map((pos) => (
                                  <div key={pos.position_id} className="flex items-center gap-2 text-xs font-mono">
                                    <span className={pos.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}>{pos.direction === 'LONG' ? '↑' : '↓'}</span>
                                    <span className="text-foreground/80 w-24 truncate">{pos.symbol}</span>
                                    <div className="flex-1 h-1.5 rounded-full bg-black/40 overflow-hidden">
                                      <div className={cn('h-full rounded-full', (pos.unrealized_pnl || 0) >= 0 ? 'bg-green-500' : 'bg-red-500')}
                                        style={{ width: `${Math.min(Math.abs(pos.unrealized_pnl_pct || 0), 100)}%` }} />
                                    </div>
                                    <span className={cn('w-16 text-right', (pos.unrealized_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400')}>
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

                {/* ── Watchlist Radar ──────────────────────────────────────── */}
                {status.signal_log && status.signal_log.length > 0 && (
                  <WatchlistRadar status={status as any} />
                )}

                {/* ── Trade History ────────────────────────────────────────── */}
                <section className="glass-card glow-border-amber p-5 rounded-2xl relative overflow-hidden group">
                  <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-amber-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />
                  <div className="flex items-center justify-between mb-6 relative z-10">
                    <h2 className="text-xl lg:text-2xl font-semibold hud-headline hud-text-amber tracking-wide flex items-center gap-3">
                      <ListBullets size={24} className="text-warning" /> TRADE HISTORY
                    </h2>
                    <Badge variant="outline" className="bg-black/60 font-mono tracking-widest px-3 border-amber-500/40 text-amber-500 glow-border-amber">
                      {trades.length} trades
                    </Badge>
                  </div>
                  <div className="relative z-10">
                    {tradesError && (
                      <div className="mb-3 px-3 py-2 border border-red-500/40 bg-red-500/10 rounded text-red-400 font-mono text-xs">
                        TRADE HISTORY ERROR — {tradesError}
                      </div>
                    )}
                    {trades.length > 0 ? (
                      <div className="max-h-[480px] overflow-y-auto pr-1 space-y-2 scrollbar-thin scrollbar-thumb-border/50 scrollbar-track-transparent">
                        {trades.map((trade) => <TradeHistoryItem key={trade.trade_id} trade={trade} />)}
                      </div>
                    ) : !tradesLoaded ? (
                      <div className="text-center py-12 border border-border border-dashed rounded-lg bg-background/50">
                        <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground/50">Loading trade history…</p>
                      </div>
                    ) : tradesError ? (
                      <div className="text-center py-12 border border-red-500/30 border-dashed rounded-lg bg-background/50">
                        <p className="font-mono text-xs uppercase tracking-widest text-red-400/80">Could not load trade history</p>
                      </div>
                    ) : (
                      <div className="text-center py-12 border border-border border-dashed rounded-lg bg-background/50">
                        <TrendUp size={32} className="mx-auto mb-3 opacity-20 text-warning" />
                        <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground/50">No completed trades yet</p>
                      </div>
                    )}
                  </div>
                </section>

                {/* ── Gauntlet Signal Intelligence ─────────────────────────── */}
                {status?.signal_log && status.signal_log.length > 0 && (
                  <GauntletBreakdown
                    signals={status.signal_log}
                    minConfluence={status.config?.min_confluence ?? undefined}
                    currentScan={status.current_scan ?? undefined}
                  />
                )}

                {/* ── Recent Activity ──────────────────────────────────────── */}
                {status.recent_activity.length > 0 && (
                  <TacticalPanel>
                    <div className="p-5 space-y-3">
                      <p className="text-xs font-mono uppercase tracking-wider text-zinc-400 flex items-center gap-2"><Clock size={14} /> Recent Activity</p>
                      <div className="space-y-1.5 max-h-48 overflow-y-auto">
                        {[...status.recent_activity].reverse().slice(0, 20).map((item, i) => (
                          <div key={i} className="flex items-start gap-3 text-xs font-mono">
                            <span className="text-zinc-600 flex-shrink-0 w-20 truncate">{new Date(item.timestamp).toLocaleTimeString()}</span>
                            <span className={cn('flex-shrink-0 w-32 truncate',
                              item.event_type.includes('error') ? 'text-destructive' :
                              item.event_type.includes('kill') ? 'text-red-400' :
                              item.event_type.includes('opened') || item.event_type.includes('started') ? 'text-success' :
                              item.event_type.includes('closed') ? 'text-accent' : 'text-zinc-400')}>
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

                {/* ── Idle CTA ─────────────────────────────────────────────── */}
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
              </div>
            )}
          </div>
        </PageContainer>
      </main>

      {/* ── Analyze Session Modal ─────────────────────────────────────────── */}
      <Dialog open={analyzeOutput !== null || analyzeError !== null} onOpenChange={(open) => { if (!open) { setAnalyzeOutput(null); setAnalyzeError(null); } }}>
        <DialogContent className="max-w-4xl w-full max-h-[85vh] flex flex-col bg-zinc-950 border-cyan-500/30 p-0">
          <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
            <div className="flex items-center gap-3">
              <ChartLine size={18} className="text-cyan-400" />
              <span className="font-mono font-black text-sm tracking-widest text-cyan-300 uppercase">Session Analysis</span>
            </div>
            <button
              onClick={() => { navigator.clipboard.writeText(analyzeOutput || analyzeError || ''); }}
              className="flex items-center gap-2 px-3 py-1.5 rounded font-mono text-xs text-zinc-400 border border-zinc-700 hover:bg-zinc-800 hover:text-zinc-200 transition-colors"
            >
              <ListBullets size={13} /> COPY
            </button>
          </div>
          {analyzeError && (
            <div className="px-5 py-3 bg-red-950/40 border-b border-red-500/20">
              <p className="font-mono text-xs text-red-400">{analyzeError}</p>
            </div>
          )}
          <div className="flex-1 overflow-y-auto p-5">
            <pre className="font-mono text-xs text-zinc-300 whitespace-pre-wrap leading-relaxed">{analyzeOutput}</pre>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
