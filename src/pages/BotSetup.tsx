import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import {
  Target, PlayCircle, ArrowsClockwise, TrendUp, TrendDown,
  Wallet, ChartLine, Warning, CheckCircle, XCircle,
  Crosshair, Lightning, ShieldCheck, Fire, Cpu, TestTube,
  Trophy, Robot, Skull, Key,
} from '@phosphor-icons/react';
import { PageContainer } from '@/components/layout/PageContainer';
import { HomeButton } from '@/components/layout/HomeButton';
import { liveTradingService, type LiveTradingConfigRequest, type PreflightResult } from '@/services/liveTradingService';
import { api } from '@/utils/api';

type TradingMode = 'testnet' | 'live';

interface LiveConfig {
  leverage: number;
  risk_per_trade: number;
  max_positions: number;
  duration_hours: number;
  scan_interval_minutes: number;
  sensitivity_preset: string;
  min_confluence: number | null;
  confluence_soft_floor: number | null;
  max_hours_open: number;
  max_drawdown_pct: number | null;
  trailing_stop: boolean;
  trailing_activation: number;
  breakeven_after_target: number;
  majors: boolean;
  altcoins: boolean;
  meme_mode: boolean;
  universe_size: number;
  symbols: string[];
  exclude_symbols: string[];
  fee_rate: number;
  max_position_size_usd: number;
  max_total_exposure_usd: number;
  min_balance_usd: number;
  kill_switch_enabled: boolean;
}

const DEFAULT_CONFIG: LiveConfig = {
  leverage: 1,
  risk_per_trade: 1,
  max_positions: 3,
  duration_hours: 24,
  scan_interval_minutes: 2,
  sensitivity_preset: 'balanced',
  min_confluence: null,
  confluence_soft_floor: null,
  max_hours_open: 72,
  max_drawdown_pct: 10,
  trailing_stop: true,
  trailing_activation: 2.0,
  breakeven_after_target: 1,
  majors: true,
  altcoins: false,
  meme_mode: false,
  universe_size: 20,
  symbols: [],
  exclude_symbols: [],
  fee_rate: 0.001,
  max_position_size_usd: 100,
  max_total_exposure_usd: 500,
  min_balance_usd: 50,
  kill_switch_enabled: true,
};

export function BotSetup() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<TradingMode>('live');
  const [config, setConfig] = useState<LiveConfig>(DEFAULT_CONFIG);
  const [preflight, setPreflight] = useState<PreflightResult | null>(null);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ackChecked, setAckChecked] = useState(false);
  const [recommendation, setRecommendation] = useState<{ mode: string; reason: string; regime?: any } | null>(null);

  const runPreflight = useCallback(async () => {
    setPreflightLoading(true);
    setError(null);
    try {
      const result = await liveTradingService.preflight();
      setPreflight(result);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setPreflightLoading(false);
    }
  }, []);

  useEffect(() => {
    runPreflight();
    api.getScannerRecommendation().then(r => { if (r.data) setRecommendation(r.data); }).catch(() => {});
  }, [runPreflight]);

  const balance = preflight?.balance ?? 0;
  const riskAmountUsd = balance > 0 ? (balance * config.risk_per_trade / 100) : null;
  const maxRiskAtOnce = riskAmountUsd ? riskAmountUsd * config.max_positions : null;
  const effectiveExposure = config.leverage * config.risk_per_trade;

  const canStart = mode === 'testnet'
    ? (preflight?.ok ?? false)
    : (preflight?.ok ?? false) && ackChecked;

  const handleStart = async () => {
    setStarting(true);
    setError(null);
    try {
      const req: LiveTradingConfigRequest = {
        testnet: mode === 'testnet',
        dry_run: false,
        sniper_mode: 'stealth',
        leverage: config.leverage,
        risk_per_trade: config.risk_per_trade,
        max_positions: config.max_positions,
        duration_hours: config.duration_hours,
        scan_interval_minutes: config.scan_interval_minutes,
        sensitivity_preset: config.sensitivity_preset,
        min_confluence: config.min_confluence ?? undefined,
        confluence_soft_floor: config.confluence_soft_floor ?? undefined,
        max_hours_open: config.max_hours_open,
        max_drawdown_pct: config.max_drawdown_pct ?? undefined,
        trailing_stop: config.trailing_stop,
        trailing_activation: config.trailing_activation,
        breakeven_after_target: config.breakeven_after_target,
        majors: config.majors,
        altcoins: config.altcoins,
        meme_mode: config.meme_mode,
        universe_size: config.universe_size,
        symbols: config.symbols,
        exclude_symbols: config.exclude_symbols,
        fee_rate: config.fee_rate,
        max_position_size_usd: config.max_position_size_usd,
        max_total_exposure_usd: config.max_total_exposure_usd,
        min_balance_usd: config.min_balance_usd,
        kill_switch_enabled: config.kill_switch_enabled,
        safety_acknowledgment: mode === 'live' ? 'I_ACCEPT_LIVE_TRADING_RISK' : '',
      };
      await liveTradingService.start(req);
      navigate('/bot/status');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setStarting(false);
    }
  };

  const isLive = mode === 'live';

  return (
    <PageContainer id="main-content">
      <div className="space-y-8">

        {/* Header */}
        <div className="flex justify-between items-start">
          <div className="flex items-start gap-4">
            <HomeButton />
            <div className="space-y-2">
              <h1 className="text-3xl lg:text-4xl font-bold flex items-center gap-3 hud-headline hud-text-green tracking-widest">
                <Robot size={32} weight="bold" className="text-accent" />
                AUTONOMOUS BOT
              </h1>
              <p className="font-mono text-sm text-muted-foreground uppercase tracking-widest pl-11">
                Live trading on Phemex — real market orders
              </p>
            </div>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="p-4 rounded-xl border border-destructive/40 bg-destructive/10 text-destructive text-sm flex items-start gap-2">
            <Warning size={16} className="flex-shrink-0 mt-0.5" /> {error}
          </div>
        )}

        {/* Hero initialization panel */}
        <section className="glass-card glow-border-green rounded-2xl p-6 md:p-8 flex flex-col items-center text-center space-y-6 relative overflow-hidden group transition-all duration-500 hover:shadow-[0_0_50px_rgba(0,255,170,0.15)]">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-green-500/10 via-transparent to-transparent opacity-40 pointer-events-none group-hover:opacity-60 transition-opacity duration-1000" />
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-[#00ff88]/50 to-transparent opacity-50" />

          <div className="relative z-10 w-full flex flex-col items-center text-center space-y-6">
            <Target size={64} className="text-accent opacity-50 mb-2" />
            <div className="max-w-xl mx-auto space-y-2">
              <h2 className="text-3xl lg:text-4xl font-black italic tracking-tighter text-transparent bg-clip-text bg-gradient-to-b from-white via-green-50 to-green-400/80 drop-shadow-[0_4px_4px_rgba(0,0,0,0.5)]">LIVE DEPLOYMENT</h2>
              <div className="h-1 w-24 mx-auto bg-gradient-to-r from-transparent via-green-500/50 to-transparent rounded-full mb-4" />
              <p className="text-base text-green-100/80 leading-relaxed font-light">
                Stealth engine — regime-adaptive, limit-only entries with a scaled ladder approach. Real orders on Phemex.
              </p>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 w-full">
              <div className="p-4 rounded-xl bg-background/60 border border-border hover:border-accent/30 transition-colors">
                <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">Leverage</div>
                <div className="text-2xl font-mono font-bold text-accent">{config.leverage}x</div>
                <div className="text-[9px] text-muted-foreground mt-1 opacity-60">Adjustable below</div>
              </div>
              <div className="p-4 rounded-xl bg-background/60 border border-border hover:border-border/60 transition-colors">
                <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">Risk / Trade</div>
                <div className="text-2xl font-mono font-bold text-foreground">{config.risk_per_trade}%</div>
                <div className="text-[9px] text-muted-foreground mt-1 opacity-60">
                  {riskAmountUsd != null ? `≈ $${riskAmountUsd.toFixed(2)}` : 'of balance'}
                </div>
              </div>
              <div className="p-4 rounded-xl bg-background/60 border border-border hover:border-primary/30 transition-colors relative overflow-hidden">
                {recommendation?.regime?.composite && (
                  <div className="absolute inset-0 bg-[radial-gradient(circle_at_bottom_right,_var(--tw-gradient-stops))] from-blue-500/10 to-transparent pointer-events-none" />
                )}
                <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">Regime</div>
                <div className="flex items-center gap-1.5">
                  <div className={cn("w-1.5 h-1.5 rounded-full shrink-0", recommendation?.regime?.composite ? "bg-primary animate-pulse" : "bg-muted-foreground/40")} />
                  <div className="text-lg font-mono font-bold text-primary capitalize truncate">
                    {recommendation?.regime?.composite ? recommendation.regime.composite.replace(/_/g, ' — ') : 'Adaptive'}
                  </div>
                </div>
                {recommendation?.reason && (
                  <div className="text-[9px] text-muted-foreground mt-1 leading-tight truncate opacity-70">{recommendation.reason}</div>
                )}
              </div>
              <div className="p-4 rounded-xl bg-background/60 border border-border hover:border-yellow-400/30 transition-colors">
                <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">Sensitivity</div>
                <div className="text-xl font-mono font-bold text-yellow-400 capitalize">{config.sensitivity_preset}</div>
                <div className="text-[9px] text-muted-foreground mt-1 opacity-60">
                  {config.sensitivity_preset === 'conservative' ? '72/62' : config.sensitivity_preset === 'aggressive' ? '58/48' : config.sensitivity_preset === 'custom' ? `${config.min_confluence ?? 65}/${config.confluence_soft_floor ?? 55}` : '65/55'}
                </div>
              </div>
            </div>

            {/* Engine info */}
            <div className="w-full max-w-2xl pt-4 space-y-6">
              <div className="space-y-3">
                <label className="text-[10px] text-accent font-bold uppercase tracking-widest pl-1">Engine Mode</label>
                <div className="bg-gradient-to-r from-purple-500/10 via-accent/5 to-blue-500/10 border border-purple-500/30 rounded-xl p-4 relative overflow-hidden">
                  <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-purple-400/50 to-transparent" />
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Lightning size={18} weight="fill" className="text-purple-400" />
                      <span className="text-sm font-black tracking-widest text-purple-400">STEALTH</span>
                      <span className="text-[8px] border border-purple-500/30 text-purple-300/80 bg-purple-500/10 px-1.5 py-0.5 rounded font-mono">LOCKED</span>
                    </div>
                    <ShieldCheck size={18} className="text-accent/40" />
                  </div>
                  <p className="text-[11px] text-muted-foreground/80 leading-relaxed mb-3">
                    Stealth covers the full timeframe range (D→5m) and adaptively selects between scalp, intraday, and swing setups based on market structure. Optimal for live execution.
                  </p>
                  <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
                    {[
                      { label: 'R:R Min', value: '1.8' },
                      { label: 'Range', value: 'D→5m' },
                      { label: 'Direction', value: 'L + S' },
                      { label: 'Types', value: 'S/I/Sw' },
                      { label: 'Scan Every', value: `${config.scan_interval_minutes}m` },
                    ].map(({ label, value }) => (
                      <div key={label} className="text-center p-2 rounded-lg bg-black/30 border border-border/30">
                        <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1">{label}</div>
                        <div className="text-sm font-mono font-bold text-accent">{value}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Mode toggle (testnet / live) */}
              <div className="glass-card glow-border-green p-6 lg:p-8 rounded-3xl relative overflow-hidden group transition-all duration-500 hover:shadow-[0_0_50px_rgba(0,255,170,0.15)]">
                <div className={cn(
                  'absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] opacity-40 pointer-events-none transition-opacity duration-1000 group-hover:opacity-60',
                  isLive ? 'from-red-500/10 via-transparent to-transparent' : 'from-yellow-500/10 via-transparent to-transparent',
                )} />
                <div className={cn(
                  'absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent to-transparent opacity-60',
                  isLive ? 'via-red-400/60' : 'via-yellow-400/60',
                )} />
                <div className="relative z-10 flex flex-col items-center gap-5 text-center">
                  <div className="flex items-center gap-1 bg-black/40 p-1.5 rounded-xl border border-white/5 backdrop-blur-md">
                    <button
                      onClick={() => setMode('live')}
                      className={cn(
                        'flex items-center gap-2 px-6 py-2.5 rounded-lg font-bold tracking-wider transition-all duration-300',
                        isLive ? 'bg-red-500/20 text-red-400 shadow-[0_0_15px_rgba(239,68,68,0.3)] border border-red-500/40' : 'text-muted-foreground hover:text-white hover:bg-white/5',
                      )}
                    >
                      <Skull size={18} weight={isLive ? 'fill' : 'bold'} />
                      LIVE
                    </button>
                    <button
                      onClick={() => { setMode('testnet'); setAckChecked(false); }}
                      className={cn(
                        'flex items-center gap-2 px-6 py-2.5 rounded-lg font-bold tracking-wider transition-all duration-300',
                        !isLive ? 'bg-yellow-500/20 text-yellow-300 shadow-[0_0_15px_rgba(234,179,8,0.3)] border border-yellow-500/40' : 'text-muted-foreground hover:text-white hover:bg-white/5',
                      )}
                    >
                      <TestTube size={18} weight={!isLive ? 'fill' : 'bold'} />
                      TESTNET
                    </button>
                  </div>
                  <h2 className={cn(
                    'text-5xl lg:text-7xl font-black italic tracking-tighter text-transparent bg-clip-text drop-shadow-[0_4px_4px_rgba(0,0,0,0.5)]',
                    isLive ? 'bg-gradient-to-b from-white via-red-50 to-red-400/80' : 'bg-gradient-to-b from-white via-yellow-50 to-yellow-400/80',
                  )}>
                    {isLive ? 'LIVE' : 'TESTNET'}
                  </h2>
                  <div className={cn('h-1 w-24 mx-auto bg-gradient-to-r from-transparent to-transparent rounded-full', isLive ? 'via-red-500/50' : 'via-yellow-500/50')} />
                  <p className="text-lg text-green-100/70 max-w-md mx-auto leading-relaxed font-light">
                    {isLive ? '"Real orders with real funds. Losses are real and irreversible."' : '"Real Phemex order book fills on the testnet. No real capital at risk."'}
                  </p>
                  <div className={cn(
                    'flex items-center gap-3 px-8 py-3 rounded-full border font-bold tracking-widest',
                    isLive ? 'text-red-400 bg-red-400/10 border-red-400/30 shadow-[0_0_20px_rgba(239,68,68,0.1)]' : 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30 shadow-[0_0_20px_rgba(234,179,8,0.1)]',
                  )}>
                    {isLive ? <Skull size={20} weight="fill" /> : <TestTube size={20} weight="fill" />}
                    <span>MODE ACTIVE</span>
                  </div>
                </div>
              </div>

              {/* Exchange connection + balance */}
              <div className="space-y-3 text-left">
                <div className="flex items-center justify-between">
                  <label className="text-[10px] text-accent font-bold uppercase tracking-widest pl-1 flex items-center gap-1.5">
                    <Key size={12} /> Exchange Connection
                  </label>
                  <button
                    onClick={runPreflight}
                    disabled={preflightLoading}
                    className="text-xs text-zinc-400 hover:text-accent flex items-center gap-1 transition-colors"
                  >
                    <ArrowsClockwise size={12} className={preflightLoading ? 'animate-spin' : ''} />
                    Recheck
                  </button>
                </div>

                {preflight ? (
                  <div className="rounded-xl border border-border/50 bg-background/40 p-4 space-y-3">
                    <div className="flex items-center gap-2">
                      {preflight.ok
                        ? <CheckCircle size={16} weight="bold" className="text-success" />
                        : <XCircle size={16} weight="bold" className="text-destructive" />}
                      <span className={cn('text-sm font-mono font-bold', preflight.ok ? 'text-success' : 'text-destructive')}>
                        {preflight.ok ? 'Connected' : 'Not connected'}
                      </span>
                    </div>

                    {/* Balance display — the main event */}
                    {balance > 0 && (
                      <div className="grid grid-cols-3 gap-3 pt-2 border-t border-border/30">
                        <div className="text-center p-3 rounded-lg bg-black/30 border border-border/30">
                          <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1 flex items-center justify-center gap-1">
                            <Wallet size={10} /> Available
                          </div>
                          <div className="text-lg font-mono font-bold text-accent">${balance.toFixed(2)}</div>
                          <div className="text-[9px] text-muted-foreground/60 mt-0.5">Futures wallet</div>
                        </div>
                        <div className="text-center p-3 rounded-lg bg-black/30 border border-border/30">
                          <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1 flex items-center justify-center gap-1">
                            <TrendDown size={10} /> Risk / Trade
                          </div>
                          <div className="text-lg font-mono font-bold text-foreground">
                            {riskAmountUsd != null ? `$${riskAmountUsd.toFixed(2)}` : '—'}
                          </div>
                          <div className="text-[9px] text-muted-foreground/60 mt-0.5">{config.risk_per_trade}% of balance</div>
                        </div>
                        <div className="text-center p-3 rounded-lg bg-black/30 border border-border/30">
                          <div className="text-[9px] text-muted-foreground uppercase tracking-widest mb-1 flex items-center justify-center gap-1">
                            <TrendUp size={10} /> Max Exposure
                          </div>
                          <div className="text-lg font-mono font-bold text-foreground">
                            {maxRiskAtOnce != null ? `$${maxRiskAtOnce.toFixed(2)}` : '—'}
                          </div>
                          <div className="text-[9px] text-muted-foreground/60 mt-0.5">{config.max_positions} positions × risk</div>
                        </div>
                      </div>
                    )}

                    {preflight.issues.map((issue, i) => (
                      <p key={i} className="text-xs text-destructive flex items-start gap-1.5">
                        <Warning size={12} className="mt-0.5 flex-shrink-0" /> {issue}
                      </p>
                    ))}
                    {preflight.open_positions.length > 0 && (
                      <p className="text-xs text-warning flex items-center gap-1.5">
                        <Warning size={12} /> {preflight.open_positions.length} existing position(s) on exchange — bot will manage alongside them
                      </p>
                    )}
                    {preflight.issues.some(i => i.toLowerCase().includes('api key') || i.toLowerCase().includes('api_key')) && (
                      <p className="text-xs text-zinc-500">
                        Add <code className="bg-zinc-800 px-1 rounded">PHEMEX_API_KEY</code> and{' '}
                        <code className="bg-zinc-800 px-1 rounded">PHEMEX_API_SECRET</code> to your <code className="bg-zinc-800 px-1 rounded">.env</code> file, then restart the backend.
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="rounded-xl border border-border/50 bg-background/40 p-4 text-sm text-zinc-500 font-mono flex items-center gap-2">
                    <ArrowsClockwise size={14} className="animate-spin" /> Checking exchange connection...
                  </div>
                )}
              </div>

              {/* ── Parameters Grid ── */}
              <div className="space-y-1.5 text-left">
                <div className="text-[10px] text-accent font-bold uppercase tracking-widest pl-1 mb-2">Session Parameters</div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

                  {/* Leverage */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between h-4 mb-0.5">
                      <label className="text-[10px] text-muted-foreground uppercase tracking-widest pl-1">Leverage (x)</label>
                    </div>
                    <input
                      type="number" min="1" max="20"
                      value={config.leverage}
                      onChange={e => { const v = parseInt(e.target.value); if (!isNaN(v)) setConfig({ ...config, leverage: v }); }}
                      className="w-full h-12 bg-background border border-border rounded-lg px-4 font-mono text-center text-lg focus:outline-none focus:border-accent/40 text-foreground"
                    />
                    <div className="flex gap-1.5">
                      {[1, 2, 5, 10].map(v => (
                        <button key={v} onClick={() => setConfig({ ...config, leverage: v })}
                          className={cn('flex-1 py-1 rounded text-[9px] font-mono font-bold tracking-tight border transition-all',
                            config.leverage === v ? 'bg-accent/15 border-accent/50 text-accent' : 'bg-black/30 border-border/40 text-muted-foreground/60 hover:border-border hover:text-muted-foreground')}
                        >{v}x</button>
                      ))}
                    </div>
                    <p className={cn('text-[9px] font-mono pl-1 leading-snug', effectiveExposure >= 20 ? 'text-red-400' : effectiveExposure >= 10 ? 'text-yellow-400' : 'text-muted-foreground/50')}>
                      Effective exposure / trade: {effectiveExposure.toFixed(1)}%
                    </p>
                  </div>

                  {/* Risk Per Trade */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between h-4 mb-0.5">
                      <label className="text-[10px] text-muted-foreground uppercase tracking-widest pl-1">Risk Per Trade (%)</label>
                    </div>
                    <input
                      type="number" min="0.1" max="5" step="0.5"
                      value={config.risk_per_trade}
                      onChange={e => { const v = parseFloat(e.target.value); if (!isNaN(v)) setConfig({ ...config, risk_per_trade: v }); }}
                      className="w-full h-12 bg-background border border-border rounded-lg px-4 font-mono text-center text-lg focus:outline-none focus:border-accent/40 text-foreground"
                    />
                    <div className="flex gap-1.5">
                      {[0.5, 1, 2, 3].map(v => (
                        <button key={v} onClick={() => setConfig({ ...config, risk_per_trade: v })}
                          className={cn('flex-1 py-1 rounded text-[9px] font-mono font-bold tracking-tight border transition-all',
                            config.risk_per_trade === v ? 'bg-accent/15 border-accent/50 text-accent' : 'bg-black/30 border-border/40 text-muted-foreground/60 hover:border-border hover:text-muted-foreground')}
                        >{v}%</button>
                      ))}
                    </div>
                    <p className="text-[9px] text-muted-foreground/40 font-mono pl-1 leading-snug">% of balance risked per entry — scales across 3 limit levels</p>
                  </div>

                  {/* Session Duration */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between h-4 mb-0.5">
                      <label className="text-[10px] text-muted-foreground uppercase tracking-widest pl-1">Session Duration (h)</label>
                    </div>
                    <input
                      type="number" min="1" max="720"
                      value={config.duration_hours}
                      onChange={e => { const v = parseInt(e.target.value); if (!isNaN(v)) setConfig({ ...config, duration_hours: v }); }}
                      className="w-full h-12 bg-background border border-border rounded-lg px-4 font-mono text-center text-lg focus:outline-none focus:border-accent/40 text-foreground"
                    />
                    <div className="flex gap-1.5">
                      {[8, 24, 72, 168].map(v => (
                        <button key={v} onClick={() => setConfig({ ...config, duration_hours: v })}
                          className={cn('flex-1 py-1 rounded text-[9px] font-mono font-bold tracking-tight border transition-all',
                            config.duration_hours === v ? 'bg-accent/15 border-accent/50 text-accent' : 'bg-black/30 border-border/40 text-muted-foreground/60 hover:border-border hover:text-muted-foreground')}
                        >{v >= 168 ? '1w' : v >= 72 ? '3d' : `${v}h`}</button>
                      ))}
                    </div>
                  </div>

                  {/* Signal Sensitivity */}
                  <div className="space-y-2 md:col-span-2">
                    <div className="flex justify-between items-center h-4 mb-0.5">
                      <label className="text-[10px] text-muted-foreground uppercase tracking-widest pl-1">Signal Sensitivity</label>
                      <span className="text-[8px] text-muted-foreground/50 font-mono italic">gate / floor</span>
                    </div>
                    <div className="flex gap-1.5">
                      {([
                        { key: 'conservative', label: 'Conservative', gate: 72, floor: 62, color: 'blue' },
                        { key: 'balanced',     label: 'Balanced',     gate: 65, floor: 55, color: 'emerald' },
                        { key: 'aggressive',   label: 'Aggressive',   gate: 58, floor: 48, color: 'orange' },
                        { key: 'custom',       label: 'Custom',       gate: null, floor: null, color: 'purple' },
                      ] as const).map(({ key, label, gate, floor, color }) => {
                        const isSelected = config.sensitivity_preset === key;
                        const selectedCls = {
                          blue:    'bg-blue-500/15 border-blue-500/60 text-blue-400',
                          emerald: 'bg-emerald-500/15 border-emerald-500/60 text-emerald-400',
                          orange:  'bg-orange-500/15 border-orange-500/60 text-orange-400',
                          purple:  'bg-purple-500/15 border-purple-500/60 text-purple-400',
                        }[color];
                        return (
                          <button key={key}
                            onClick={() => setConfig({
                              ...config, sensitivity_preset: key,
                              min_confluence: key === 'custom' ? (config.min_confluence ?? 65) : null,
                              confluence_soft_floor: key === 'custom' ? (config.confluence_soft_floor ?? 55) : null,
                            })}
                            className={cn('flex-1 py-1.5 rounded text-[9px] font-mono font-bold tracking-tight border transition-all flex flex-col items-center gap-0.5',
                              isSelected ? selectedCls : 'bg-black/30 border-border/40 text-muted-foreground/60 hover:border-border hover:text-muted-foreground')}
                          >
                            <span>{label}</span>
                            {gate !== null && <span className="opacity-60 text-[8px]">{gate}/{floor}</span>}
                          </button>
                        );
                      })}
                    </div>
                    {config.sensitivity_preset === 'custom' && (
                      <div className="flex gap-3 mt-1">
                        <div className="flex-1 space-y-1">
                          <label className="text-[9px] text-purple-400/70 uppercase tracking-widest pl-0.5">Gate % (full size)</label>
                          <input type="number" min="40" max="100"
                            value={config.min_confluence ?? 65}
                            onChange={e => setConfig({ ...config, min_confluence: Number(e.target.value) || 65 })}
                            className="w-full h-10 bg-background border border-purple-500/30 rounded-lg px-3 font-mono text-center text-base focus:outline-none focus:border-purple-400/60 text-foreground"
                          />
                        </div>
                        <div className="flex-1 space-y-1">
                          <label className="text-[9px] text-purple-400/70 uppercase tracking-widest pl-0.5">Floor % (half size)</label>
                          <input type="number" min="30" max="100"
                            value={config.confluence_soft_floor ?? 55}
                            onChange={e => setConfig({ ...config, confluence_soft_floor: Number(e.target.value) || 55 })}
                            className="w-full h-10 bg-background border border-purple-500/30 rounded-lg px-3 font-mono text-center text-base focus:outline-none focus:border-purple-400/60 text-foreground"
                          />
                        </div>
                      </div>
                    )}
                    <p className="text-[9px] text-muted-foreground/40 font-mono pl-1 leading-snug">
                      {config.sensitivity_preset === 'conservative' ? 'Highest-conviction only — 2–5 trades/week' :
                       config.sensitivity_preset === 'aggressive'   ? 'Wider net, more near-misses — 10–20+ trades/week' :
                       config.sensitivity_preset === 'custom'       ? 'Score ≥ gate → 100% size · floor ≤ score < gate → 50% size' :
                       'Good setups full size, near-misses half size — 5–12 trades/week'}
                    </p>
                  </div>

                  {/* Max Trade Duration */}
                  <div className="space-y-2">
                    <label className="text-[10px] text-muted-foreground uppercase tracking-widest pl-1">Max Trade Duration (h)</label>
                    <input type="number" min="1" max="720"
                      value={config.max_hours_open}
                      onChange={e => { const v = parseInt(e.target.value); if (!isNaN(v)) setConfig({ ...config, max_hours_open: v }); }}
                      className="w-full h-12 bg-background border border-border rounded-lg px-4 font-mono text-center text-lg focus:outline-none focus:border-accent/40 text-foreground"
                    />
                    <div className="flex gap-1.5">
                      {[24, 48, 72, 168].map(v => (
                        <button key={v} onClick={() => setConfig({ ...config, max_hours_open: v })}
                          className={cn('flex-1 py-1 rounded text-[9px] font-mono font-bold tracking-tight border transition-all',
                            config.max_hours_open === v ? 'bg-accent/15 border-accent/50 text-accent' : 'bg-black/30 border-border/40 text-muted-foreground/60 hover:border-border hover:text-muted-foreground')}
                        >{v}h</button>
                      ))}
                    </div>
                    <p className="text-[9px] text-muted-foreground/40 font-mono pl-1 leading-snug">Auto-closes any trade open longer than this</p>
                  </div>

                  {/* Max Drawdown */}
                  <div className="space-y-2">
                    <label className="text-[10px] text-red-400/80 uppercase tracking-widest pl-1">Max Drawdown Limit (%)</label>
                    <input type="number" min="1" max="100"
                      value={config.max_drawdown_pct ?? ''}
                      placeholder="NONE"
                      onChange={e => setConfig({ ...config, max_drawdown_pct: e.target.value === '' ? null : Number(e.target.value) })}
                      className="w-full h-12 bg-background border border-red-500/20 rounded-lg px-4 font-mono text-center text-lg focus:outline-none focus:border-red-400/40 text-foreground placeholder:text-muted-foreground/30"
                    />
                    <div className="flex gap-1.5">
                      {[{ l: 'OFF', v: null }, { l: '10%', v: 10 }, { l: '15%', v: 15 }, { l: '25%', v: 25 }].map(({ l, v }) => (
                        <button key={l} onClick={() => setConfig({ ...config, max_drawdown_pct: v })}
                          className={cn('flex-1 py-1 rounded text-[9px] font-mono font-bold tracking-tight border transition-all',
                            config.max_drawdown_pct === v ? 'bg-red-500/15 border-red-500/50 text-red-400' : 'bg-black/30 border-border/40 text-muted-foreground/60 hover:border-border hover:text-muted-foreground')}
                        >{l}</button>
                      ))}
                    </div>
                    <p className="text-[9px] text-muted-foreground/40 font-mono pl-1 leading-snug">Kill switch fires if balance drops this % from session start</p>
                  </div>

                  {/* Scan Interval */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between h-4 mb-0.5">
                      <label className="text-[10px] text-muted-foreground uppercase tracking-widest pl-1">Scan Every (m)</label>
                      <span className="text-[8px] text-accent/60 border border-accent/20 bg-accent/5 px-1.5 py-0 rounded">Suggested: 2m</span>
                    </div>
                    <input type="number" min="1" max="60"
                      value={config.scan_interval_minutes}
                      onChange={e => { const v = parseInt(e.target.value); if (!isNaN(v)) setConfig({ ...config, scan_interval_minutes: v }); }}
                      className="w-full h-12 bg-background border border-border rounded-lg px-4 font-mono text-center text-lg focus:outline-none focus:border-accent/40 text-foreground"
                    />
                    <div className="flex gap-1.5">
                      {[2, 5, 15, 30].map(v => (
                        <button key={v} onClick={() => setConfig({ ...config, scan_interval_minutes: v })}
                          className={cn('flex-1 py-1 rounded text-[9px] font-mono font-bold tracking-tight border transition-all',
                            config.scan_interval_minutes === v ? 'bg-accent/15 border-accent/50 text-accent' : 'bg-black/30 border-border/40 text-muted-foreground/60 hover:border-border hover:text-muted-foreground')}
                        >{v}m</button>
                      ))}
                    </div>
                    <p className="text-[9px] text-muted-foreground/40 font-mono pl-1 leading-snug">Fast scans (2m) catch scalp entries; slower scans reduce CPU load</p>
                  </div>

                  {/* Max Concurrent Assets */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between h-4 mb-0.5">
                      <label className="text-[10px] text-muted-foreground uppercase tracking-widest pl-1">Max Concurrent Assets</label>
                      <span className="text-[8px] text-accent/60 border border-accent/20 bg-accent/5 px-1.5 py-0 rounded">Suggested: 3</span>
                    </div>
                    <input type="number" min="1" max="10"
                      value={config.max_positions}
                      onChange={e => { const v = parseInt(e.target.value); if (!isNaN(v)) setConfig({ ...config, max_positions: v }); }}
                      className="w-full h-12 bg-background border border-border rounded-lg px-4 font-mono text-center text-lg focus:outline-none focus:border-accent/40 text-foreground"
                    />
                    <div className="flex gap-1.5">
                      {[1, 3, 5, 10].map(v => (
                        <button key={v} onClick={() => setConfig({ ...config, max_positions: v })}
                          className={cn('flex-1 py-1 rounded text-[9px] font-mono font-bold tracking-tight border transition-all',
                            config.max_positions === v ? 'bg-accent/15 border-accent/50 text-accent' : 'bg-black/30 border-border/40 text-muted-foreground/60 hover:border-border hover:text-muted-foreground')}
                        >{v}</button>
                      ))}
                    </div>
                    <p className="text-[9px] text-muted-foreground/40 font-mono pl-1 leading-snug">Limit of concurrent open + pending position slots</p>
                  </div>
                </div>
              </div>

              {/* Asset Buckets */}
              <div className="bg-background/40 border border-border/50 rounded-xl p-4 space-y-4 text-left">
                <div className="flex items-center justify-between">
                  <label className="text-[10px] text-accent font-bold uppercase tracking-widest pl-1">Target Asset Buckets</label>
                  <span className="text-[9px] text-muted-foreground font-mono italic">Volume adaptive</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div onClick={() => setConfig({ ...config, majors: !config.majors })}
                          className={cn('flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg border cursor-pointer transition-all',
                            config.majors ? 'bg-accent/10 border-accent text-accent shadow-[0_0_10px_rgba(0,255,170,0.1)]' : 'bg-black/20 border-border text-muted-foreground opacity-60 grayscale')}
                        >
                          <Trophy size={16} weight={config.majors ? 'fill' : 'regular'} />
                          <span className="text-xs font-mono font-bold tracking-tight">MAJORS</span>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="top" className="bg-black/90 border-border text-[10px] p-2 max-w-[200px]">
                        BTC, ETH, SOL, BNB, XRP, ADA, DOGE, AVAX, DOT, LINK
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                  <div onClick={() => setConfig({ ...config, altcoins: !config.altcoins })}
                    className={cn('flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg border cursor-pointer transition-all',
                      config.altcoins ? 'bg-primary/10 border-primary text-primary shadow-[0_0_10px_rgba(59,130,246,0.1)]' : 'bg-black/20 border-border text-muted-foreground opacity-60 grayscale')}
                  >
                    <ChartLine size={16} weight={config.altcoins ? 'fill' : 'regular'} />
                    <span className="text-xs font-mono font-bold tracking-tight">ALTS</span>
                  </div>
                  <div onClick={() => setConfig({ ...config, meme_mode: !config.meme_mode })}
                    className={cn('flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg border cursor-pointer transition-all',
                      config.meme_mode ? 'bg-purple-500/10 border-purple-500 text-purple-400 shadow-[0_0_10px_rgba(168,85,247,0.1)]' : 'bg-black/20 border-border text-muted-foreground opacity-60 grayscale')}
                  >
                    <Crosshair size={16} weight={config.meme_mode ? 'fill' : 'regular'} />
                    <span className="text-xs font-mono font-bold tracking-tight">MEME HUNTER</span>
                  </div>
                </div>

                <div className="pt-2 border-t border-border/30">
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-[10px] text-muted-foreground uppercase tracking-widest font-mono">Universe Size</label>
                    <span className="text-[10px] font-mono font-bold text-accent">{config.universe_size} pairs</span>
                  </div>
                  <input type="range" min={10} max={50} step={5}
                    value={config.universe_size}
                    onChange={e => setConfig({ ...config, universe_size: Number(e.target.value) })}
                    className="w-full h-1.5 accent-accent cursor-pointer"
                  />
                  <div className="flex justify-between mt-1">
                    <span className="text-[9px] text-muted-foreground/40 font-mono">10</span>
                    <span className="text-[9px] text-muted-foreground/40 font-mono">50</span>
                  </div>
                </div>

                <div className="pt-2 border-t border-border/30">
                  <label className="text-[10px] text-muted-foreground uppercase tracking-widest mb-2 block font-mono">Custom symbols (comma separated)</label>
                  <input type="text"
                    placeholder="e.g. BTC/USDT, ETH/USDT, LINK/USDT"
                    value={config.symbols.join(', ')}
                    onChange={e => {
                      const syms = e.target.value.split(',').map(s => s.trim().toUpperCase()).filter(s => s.length > 0);
                      setConfig({ ...config, symbols: syms });
                    }}
                    className="w-full h-10 bg-black/40 border border-border rounded-md px-3 font-mono text-xs focus:outline-none focus:border-accent/40 placeholder:text-muted-foreground/30 text-foreground"
                  />
                </div>
              </div>

              {/* Safety Limits */}
              <div className={cn('rounded-xl border p-4 space-y-4 text-left', isLive ? 'border-red-500/30 bg-red-500/5' : 'border-yellow-500/30 bg-yellow-500/5')}>
                <label className={cn('text-[10px] font-bold uppercase tracking-widest pl-1 flex items-center gap-1.5', isLive ? 'text-red-400' : 'text-yellow-400')}>
                  <Fire size={12} /> Safety Limits — {isLive ? 'REAL MONEY' : 'Testnet'}
                </label>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-[9px] text-muted-foreground uppercase tracking-widest font-mono">Max Position Size ($)</label>
                    <input type="number" min="1"
                      value={config.max_position_size_usd}
                      onChange={e => { const v = parseFloat(e.target.value); if (!isNaN(v)) setConfig({ ...config, max_position_size_usd: v }); }}
                      className="w-full h-10 bg-background border border-border rounded-lg px-3 font-mono text-center focus:outline-none focus:border-accent/40 text-foreground"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[9px] text-muted-foreground uppercase tracking-widest font-mono">Max Total Exposure ($)</label>
                    <input type="number" min="1"
                      value={config.max_total_exposure_usd}
                      onChange={e => { const v = parseFloat(e.target.value); if (!isNaN(v)) setConfig({ ...config, max_total_exposure_usd: v }); }}
                      className="w-full h-10 bg-background border border-border rounded-lg px-3 font-mono text-center focus:outline-none focus:border-accent/40 text-foreground"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[9px] text-muted-foreground uppercase tracking-widest font-mono">Min Balance Floor ($)</label>
                    <input type="number" min="0"
                      value={config.min_balance_usd}
                      onChange={e => { const v = parseFloat(e.target.value); if (!isNaN(v)) setConfig({ ...config, min_balance_usd: v }); }}
                      className="w-full h-10 bg-background border border-border rounded-lg px-3 font-mono text-center focus:outline-none focus:border-accent/40 text-foreground"
                    />
                  </div>
                </div>
                <p className="text-[9px] text-muted-foreground/50 font-mono pl-1">Kill switch fires automatically if balance drops below the floor</p>
              </div>

              {/* Live acknowledgment */}
              {isLive && (
                <div className="rounded-xl border border-red-500/40 bg-red-500/5 p-4 space-y-3 text-left">
                  <div className="flex items-start gap-3">
                    <Skull size={24} weight="bold" className="text-red-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-bold text-red-400 text-sm">Real Money Warning</p>
                      <p className="text-xs text-zinc-400 mt-1">
                        This bot will place real orders on Phemex using your API keys. Losses are real and irreversible. Verify all limits above before deploying.
                      </p>
                    </div>
                  </div>
                  <label className="flex items-center gap-3 cursor-pointer mt-2">
                    <input type="checkbox" checked={ackChecked} onChange={e => setAckChecked(e.target.checked)} className="w-4 h-4 accent-red-500" />
                    <span className="text-xs text-zinc-300">I understand this trades real money and accept full responsibility</span>
                  </label>
                </div>
              )}

              {/* Deploy button */}
              <button
                onClick={handleStart}
                disabled={!canStart || starting}
                className={cn(
                  'w-full h-14 rounded-xl font-bold text-sm uppercase tracking-widest flex items-center justify-center gap-3 transition-all duration-300 relative overflow-hidden group/btn border-2',
                  canStart && !starting
                    ? isLive
                      ? 'bg-red-600 hover:bg-red-500 border-red-500 text-white shadow-lg shadow-red-900/30 hover:shadow-red-500/30'
                      : 'bg-[#00ff88] hover:bg-[#00cc6a] border-white/20 text-black shadow-[0_0_30px_rgba(0,255,136,0.4)] hover:shadow-[0_0_50px_rgba(0,255,136,0.6)] hover:scale-105'
                    : 'bg-zinc-800 border-zinc-700 text-zinc-500 cursor-not-allowed',
                )}
              >
                {canStart && !starting && (
                  <div className="absolute inset-0 bg-white/10 skew-x-12 -translate-x-full group-hover/btn:translate-x-full transition-transform duration-700" />
                )}
                {starting ? (
                  <><ArrowsClockwise size={20} className="animate-spin" /> Initializing...</>
                ) : isLive ? (
                  <><Skull size={20} weight="bold" /> Deploy Live Bot</>
                ) : (
                  <><PlayCircle size={20} weight="fill" /> Deploy on Testnet</>
                )}
              </button>
            </div>
          </div>
        </section>

        {/* System capabilities */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { icon: <Cpu size={18} className="text-accent" />, title: 'Regime Adaptive', desc: 'Adjusts targets, position sizing, and entry thresholds based on live volatility regime detection.' },
            { icon: <Target size={18} className="text-primary" />, title: 'SMC Detection', desc: 'Order blocks, fair value gaps, liquidity sweeps, and multi-timeframe structure alignment.' },
            { icon: <ShieldCheck size={18} className="text-warning" />, title: 'Risk Control', desc: 'Native exchange stops, trailing breakeven, kill switch, and per-session drawdown limits.' },
          ].map(({ icon, title, desc }) => (
            <div key={title} className="p-4 rounded-xl bg-background/40 border border-border/30 space-y-2">
              <div className="flex items-center gap-2">{icon}<span className="text-xs font-bold font-mono uppercase tracking-wider">{title}</span></div>
              <p className="text-[10px] text-muted-foreground/70 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>

      </div>
    </PageContainer>
  );
}
