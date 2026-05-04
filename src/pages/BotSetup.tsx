import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import {
  Target, PlayCircle, ArrowsClockwise, TrendUp, TrendDown,
  Wallet, ChartLine, Warning, CheckCircle, XCircle,
  Crosshair, Lightning, ShieldCheck, Fire, Cpu,
  Trophy, Robot, Skull, Key,
} from '@phosphor-icons/react';
import { PageContainer } from '@/components/layout/PageContainer';
import { HomeButton } from '@/components/layout/HomeButton';
import { liveTradingService, type LiveTradingConfigRequest, type PreflightResult } from '@/services/liveTradingService';
import { api } from '@/utils/api';


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
    // Redirect immediately if bot is already running
    liveTradingService.getStatus().then(s => {
      if (s.status === 'running') navigate('/bot/status');
    }).catch(() => {});
    runPreflight();
    api.getScannerRecommendation().then(r => { if (r.data) setRecommendation(r.data); }).catch(() => {});
  }, [runPreflight]);

  const balance = preflight?.balance ?? 0;
  const riskAmountUsd = balance > 0 ? (balance * config.risk_per_trade / 100) : null;
  const maxRiskAtOnce = riskAmountUsd ? riskAmountUsd * config.max_positions : null;
  const effectiveExposure = config.leverage * config.risk_per_trade;

  const canStart = (preflight?.ok ?? false) && ackChecked;

  const handleStart = async () => {
    setStarting(true);
    setError(null);
    try {
      const req: LiveTradingConfigRequest = {
        testnet: false,
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
        safety_acknowledgment: 'I_ACCEPT_LIVE_TRADING_RISK',
      };
      await liveTradingService.start(req);
      navigate('/bot/status');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setStarting(false);
    }
  };

  return (
    <PageContainer id="main-content">
      <div className="space-y-4 cockpit-scanlines">

        {/* Header */}
        <div className="flex items-center gap-4">
          <HomeButton />
          <div>
            <h1 className="text-2xl font-black tracking-widest font-mono text-emerald-400 flex items-center gap-2">
              <Robot size={22} weight="bold" /> AUTONOMOUS BOT
            </h1>
            <p className="text-[10px] font-mono text-white/30 uppercase tracking-[0.2em] mt-0.5">
              Deploy your trained AI strategy · Live orders on Phemex
            </p>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-start gap-2 px-4 py-3 border border-red-500/30 bg-red-500/5 text-red-400 text-xs font-mono">
            <Warning size={14} className="flex-shrink-0 mt-0.5" /> {error}
          </div>
        )}

        {/* System Bar */}
        <div className="flex items-center gap-4 px-4 py-2 bg-black/80 border border-white/[0.06] text-[9px] font-mono tracking-[0.18em] overflow-x-auto">
          <span className="text-white/20 whitespace-nowrap">[SYS-01 · AUTONOMOUS BOT]</span>
          <span className="text-white/10">│</span>
          <span className="text-white/30">CONN</span>
          <span className={cn("font-bold", preflight?.ok ? "text-emerald-400" : preflightLoading ? "text-amber-400" : "text-red-400")}>
            {preflightLoading ? "CHECKING" : preflight?.ok ? "ONLINE" : "OFFLINE"}
          </span>
          {balance > 0 && <>
            <span className="text-white/10">│</span>
            <span className="text-white/30">BALANCE</span>
            <span className="text-white/60 font-bold">${balance.toFixed(2)}</span>
          </>}
          {recommendation?.regime?.composite && <>
            <span className="text-white/10">│</span>
            <span className="text-white/30">REGIME</span>
            <span className="text-cyan-400 capitalize">{recommendation.regime.composite.replace(/_/g, ' ')}</span>
          </>}
          <span className="ml-auto flex items-center gap-1.5 text-red-400 whitespace-nowrap">
            <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
            ● LIVE MODE
          </span>
        </div>

        {/* Cockpit Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-[1px] bg-white/[0.06] border border-white/[0.06]">

          {/* ── LEFT: System Health ── */}
          <div className="lg:col-span-3 bg-[#050c08] border-t-2 border-emerald-500/50 p-5 space-y-5">
            <div className="text-[8px] font-mono tracking-[0.25em] text-emerald-500/40 uppercase">[SYS-01] SYSTEM</div>

            {/* Connection */}
            <div className="space-y-2">
              <div className="text-[9px] uppercase tracking-[0.2em] text-white/30 font-mono">Exchange Connection</div>
              {preflight ? (
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    {preflight.ok
                      ? <CheckCircle size={14} weight="bold" className="text-emerald-400" />
                      : <XCircle size={14} weight="bold" className="text-red-400" />}
                    <span className={cn("text-sm font-bold font-mono", preflight.ok ? "text-emerald-400" : "text-red-400")}>
                      {preflight.ok ? "ONLINE" : "OFFLINE"}
                    </span>
                  </div>
                  {preflight.issues.map((issue, i) => (
                    <p key={i} className="text-[9px] text-red-400/70 font-mono leading-tight">{issue}</p>
                  ))}
                  {preflight.issues.some(i => i.toLowerCase().includes('api')) && (
                    <p className="text-[9px] text-white/25 font-mono leading-tight">Set PHEMEX_API_KEY + PHEMEX_API_SECRET in .env</p>
                  )}
                  {preflight.open_positions.length > 0 && (
                    <p className="text-[9px] text-amber-400/70 font-mono flex items-center gap-1">
                      <Warning size={10} /> {preflight.open_positions.length} existing position(s) on exchange
                    </p>
                  )}
                </div>
              ) : (
                <div className="flex items-center gap-2 text-white/25 text-[9px] font-mono">
                  <ArrowsClockwise size={11} className="animate-spin" /> CHECKING...
                </div>
              )}
            </div>

            {/* Balance */}
            {balance > 0 && (
              <div className="space-y-2">
                <div className="text-[9px] uppercase tracking-[0.2em] text-white/30 font-mono">Wallet</div>
                <div className="flex items-baseline justify-between">
                  <span className="text-[9px] text-white/25 font-mono">Available</span>
                  <span className="text-base font-bold font-mono text-emerald-400">${balance.toFixed(2)}</span>
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-[9px] text-white/25 font-mono">Risk / Trade</span>
                  <span className="text-sm font-bold font-mono text-white/60">{riskAmountUsd != null ? `$${riskAmountUsd.toFixed(2)}` : '—'}</span>
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-[9px] text-white/25 font-mono">Max Exposure</span>
                  <span className="text-sm font-bold font-mono text-white/40">{maxRiskAtOnce != null ? `$${maxRiskAtOnce.toFixed(2)}` : '—'}</span>
                </div>
                <div className="h-px bg-white/[0.06] mt-1" />
                <div className="h-1 bg-white/5">
                  <div className={cn("h-full transition-all duration-500", effectiveExposure >= 20 ? 'bg-red-500/60' : effectiveExposure >= 10 ? 'bg-amber-500/60' : 'bg-emerald-500/60')}
                    style={{ width: `${Math.min(100, effectiveExposure * 5).toFixed(1)}%` }} />
                </div>
                <div className={cn("text-[8px] font-mono", effectiveExposure >= 20 ? 'text-red-400' : effectiveExposure >= 10 ? 'text-amber-400' : 'text-white/25')}>
                  {effectiveExposure.toFixed(1)}% effective exposure / trade
                </div>
              </div>
            )}

            {/* Regime */}
            <div className="space-y-1.5">
              <div className="text-[9px] uppercase tracking-[0.2em] text-white/30 font-mono">Market Regime</div>
              <div className="flex items-center gap-2">
                <div className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0", recommendation?.regime?.composite ? "bg-cyan-400 animate-pulse" : "bg-white/20")} />
                <span className="text-sm font-bold font-mono text-cyan-300 capitalize">
                  {recommendation?.regime?.composite ? recommendation.regime.composite.replace(/_/g, ' ') : 'Adaptive'}
                </span>
              </div>
              {recommendation?.reason && (
                <p className="text-[9px] text-white/25 font-mono leading-tight line-clamp-2">{recommendation.reason}</p>
              )}
            </div>

            {/* Engine Mode */}
            <div className="space-y-2">
              <div className="text-[9px] uppercase tracking-[0.2em] text-white/30 font-mono">Engine Mode</div>
              <div className="border border-purple-500/20 bg-purple-500/5 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Lightning size={13} weight="fill" className="text-purple-400" />
                    <span className="text-sm font-black tracking-widest text-purple-300 font-mono">STEALTH</span>
                  </div>
                  <span className="text-[8px] font-mono border border-purple-500/30 text-purple-400/60 px-1.5 py-0.5">LOCKED</span>
                </div>
                <div className="grid grid-cols-2 gap-1.5 text-[9px] font-mono">
                  {[['R:R Min', '1.8'], ['TF Range', 'D→5m'], ['Direction', 'L + S'], ['Types', 'S/I/W']].map(([k, v]) => (
                    <div key={k}>
                      <div className="text-white/20">{k}</div>
                      <div className="text-white/60 font-bold">{v}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Live mode tag */}
            <div className="border border-red-500/20 bg-red-500/5 p-3 flex items-center gap-2">
              <Skull size={12} weight="fill" className="text-red-400" />
              <div>
                <div className="text-[9px] font-mono font-black tracking-[0.2em] text-red-400">LIVE TRADING</div>
                <div className="text-[8px] text-white/25 font-mono">Real orders · Real funds · Irreversible</div>
              </div>
            </div>

            {/* Recheck */}
            <button onClick={runPreflight} disabled={preflightLoading}
              className="w-full flex items-center justify-center gap-2 py-2 border border-white/10 text-white/30 text-[9px] font-mono tracking-widest uppercase hover:border-emerald-500/40 hover:text-emerald-400 transition-all disabled:opacity-30"
            >
              <ArrowsClockwise size={10} className={preflightLoading ? 'animate-spin' : ''} />
              Recheck Connection
            </button>
          </div>

          {/* ── CENTER: Operational Config ── */}
          <div className="lg:col-span-6 bg-[#070707] p-5 space-y-5">
            <div className="text-[8px] font-mono tracking-[0.25em] text-white/20 uppercase">[OPS-01] CONFIGURATION</div>

            {/* Signal Quality Filter */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="text-[9px] uppercase tracking-[0.2em] text-white/30 font-mono">Signal Quality Filter</div>
                <span className="text-[8px] text-white/20 font-mono">entry gate / near-miss floor</span>
              </div>
              <div className="grid grid-cols-4 gap-[1px] bg-white/[0.06]">
                {([
                  { key: 'conservative', label: 'PRECISION',  gate: 72, floor: 62, hi: 'text-blue-400 bg-blue-500/10' },
                  { key: 'balanced',     label: 'BALANCED',   gate: 65, floor: 55, hi: 'text-emerald-400 bg-emerald-500/10' },
                  { key: 'aggressive',   label: 'ACTIVE',     gate: 58, floor: 48, hi: 'text-orange-400 bg-orange-500/10' },
                  { key: 'custom',       label: 'CUSTOM',     gate: null, floor: null, hi: 'text-purple-400 bg-purple-500/10' },
                ] as const).map(({ key, label, gate, floor, hi }) => (
                  <button key={key}
                    onClick={() => setConfig({ ...config, sensitivity_preset: key,
                      min_confluence: key === 'custom' ? (config.min_confluence ?? 65) : null,
                      confluence_soft_floor: key === 'custom' ? (config.confluence_soft_floor ?? 55) : null,
                    })}
                    className={cn("py-2.5 flex flex-col items-center gap-0.5 text-[9px] font-mono font-bold tracking-wider transition-all border-t-2",
                      config.sensitivity_preset === key ? `border-current ${hi}` : "border-transparent bg-black/60 text-white/20 hover:text-white/50")}
                  >
                    <span>{label}</span>
                    {gate !== null && <span className="opacity-50 text-[8px] font-normal">{gate}/{floor}</span>}
                  </button>
                ))}
              </div>
              {config.sensitivity_preset === 'custom' && (
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <div className="text-[8px] text-purple-400/60 font-mono mb-1 uppercase tracking-widest">Gate % (full size)</div>
                    <input type="number" min="40" max="100" value={config.min_confluence ?? 65}
                      onChange={e => setConfig({ ...config, min_confluence: Number(e.target.value) || 65 })}
                      className="w-full h-9 bg-black border border-white/10 rounded-none px-3 font-mono text-sm text-center text-white shadow-[inset_0_2px_8px_rgba(0,0,0,0.6)] focus:outline-none focus:border-purple-500/40"
                    />
                  </div>
                  <div>
                    <div className="text-[8px] text-purple-400/60 font-mono mb-1 uppercase tracking-widest">Floor % (half size)</div>
                    <input type="number" min="30" max="100" value={config.confluence_soft_floor ?? 55}
                      onChange={e => setConfig({ ...config, confluence_soft_floor: Number(e.target.value) || 55 })}
                      className="w-full h-9 bg-black border border-white/10 rounded-none px-3 font-mono text-sm text-center text-white shadow-[inset_0_2px_8px_rgba(0,0,0,0.6)] focus:outline-none focus:border-purple-500/40"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* 2-up: Leverage + Risk */}
            <div className="grid grid-cols-2 gap-[1px] bg-white/[0.06]">
              <div className="bg-[#070707] p-3 space-y-2">
                <div className="text-[9px] uppercase tracking-[0.2em] text-white/30 font-mono">Leverage</div>
                <input type="number" min="1" max="20" value={config.leverage}
                  onChange={e => { const v = parseInt(e.target.value); if (!isNaN(v)) setConfig({ ...config, leverage: v }); }}
                  className="w-full h-9 bg-black border border-white/10 rounded-none px-3 font-mono text-lg text-center text-white shadow-[inset_0_2px_8px_rgba(0,0,0,0.6)] focus:outline-none focus:border-emerald-500/40"
                />
                <div className="flex gap-[1px]">
                  {[1, 2, 5, 10].map(v => (
                    <button key={v} onClick={() => setConfig({ ...config, leverage: v })}
                      className={cn("flex-1 py-1 text-[9px] font-mono font-bold transition-all",
                        config.leverage === v ? "bg-emerald-500/20 text-emerald-400" : "bg-black/40 text-white/20 hover:text-white/50")}
                    >{v}x</button>
                  ))}
                </div>
                <div className={cn("text-[8px] font-mono", effectiveExposure >= 20 ? 'text-red-400' : effectiveExposure >= 10 ? 'text-amber-400' : 'text-white/25')}>
                  {effectiveExposure.toFixed(1)}% effective / trade
                </div>
              </div>
              <div className="bg-[#070707] p-3 space-y-2">
                <div className="text-[9px] uppercase tracking-[0.2em] text-white/30 font-mono">Risk / Trade</div>
                <input type="number" min="0.1" max="5" step="0.5" value={config.risk_per_trade}
                  onChange={e => { const v = parseFloat(e.target.value); if (!isNaN(v)) setConfig({ ...config, risk_per_trade: v }); }}
                  className="w-full h-9 bg-black border border-white/10 rounded-none px-3 font-mono text-lg text-center text-white shadow-[inset_0_2px_8px_rgba(0,0,0,0.6)] focus:outline-none focus:border-emerald-500/40"
                />
                <div className="flex gap-[1px]">
                  {[0.5, 1, 2, 3].map(v => (
                    <button key={v} onClick={() => setConfig({ ...config, risk_per_trade: v })}
                      className={cn("flex-1 py-1 text-[9px] font-mono font-bold transition-all",
                        config.risk_per_trade === v ? "bg-emerald-500/20 text-emerald-400" : "bg-black/40 text-white/20 hover:text-white/50")}
                    >{v}%</button>
                  ))}
                </div>
                <div className="text-[8px] font-mono text-white/25">
                  {riskAmountUsd != null ? `≈ $${riskAmountUsd.toFixed(2)} per entry` : 'of balance per entry'}
                </div>
              </div>
            </div>

            {/* 2-up: Session Duration + Scan Freq */}
            <div className="grid grid-cols-2 gap-[1px] bg-white/[0.06]">
              <div className="bg-[#070707] p-3 space-y-2">
                <div className="text-[9px] uppercase tracking-[0.2em] text-white/30 font-mono">Session Duration</div>
                <input type="number" min="1" max="720" value={config.duration_hours}
                  onChange={e => { const v = parseInt(e.target.value); if (!isNaN(v)) setConfig({ ...config, duration_hours: v }); }}
                  className="w-full h-9 bg-black border border-white/10 rounded-none px-3 font-mono text-lg text-center text-white shadow-[inset_0_2px_8px_rgba(0,0,0,0.6)] focus:outline-none focus:border-emerald-500/40"
                />
                <div className="flex gap-[1px]">
                  {[8, 24, 72, 168].map(v => (
                    <button key={v} onClick={() => setConfig({ ...config, duration_hours: v })}
                      className={cn("flex-1 py-1 text-[9px] font-mono font-bold transition-all",
                        config.duration_hours === v ? "bg-emerald-500/20 text-emerald-400" : "bg-black/40 text-white/20 hover:text-white/50")}
                    >{v >= 168 ? '1w' : v >= 72 ? '3d' : `${v}h`}</button>
                  ))}
                </div>
              </div>
              <div className="bg-[#070707] p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="text-[9px] uppercase tracking-[0.2em] text-white/30 font-mono">Scan Interval</div>
                  <span className="text-[8px] text-emerald-500/50 font-mono">rec: 2m</span>
                </div>
                <input type="number" min="1" max="60" value={config.scan_interval_minutes}
                  onChange={e => { const v = parseInt(e.target.value); if (!isNaN(v)) setConfig({ ...config, scan_interval_minutes: v }); }}
                  className="w-full h-9 bg-black border border-white/10 rounded-none px-3 font-mono text-lg text-center text-white shadow-[inset_0_2px_8px_rgba(0,0,0,0.6)] focus:outline-none focus:border-emerald-500/40"
                />
                <div className="flex gap-[1px]">
                  {[2, 5, 15, 30].map(v => (
                    <button key={v} onClick={() => setConfig({ ...config, scan_interval_minutes: v })}
                      className={cn("flex-1 py-1 text-[9px] font-mono font-bold transition-all",
                        config.scan_interval_minutes === v ? "bg-emerald-500/20 text-emerald-400" : "bg-black/40 text-white/20 hover:text-white/50")}
                    >{v}m</button>
                  ))}
                </div>
              </div>
            </div>

            {/* 2-up: Max Trade Duration + Max Concurrent */}
            <div className="grid grid-cols-2 gap-[1px] bg-white/[0.06]">
              <div className="bg-[#070707] p-3 space-y-2">
                <div className="text-[9px] uppercase tracking-[0.2em] text-white/30 font-mono">Max Trade Duration</div>
                <input type="number" min="1" max="720" value={config.max_hours_open}
                  onChange={e => { const v = parseInt(e.target.value); if (!isNaN(v)) setConfig({ ...config, max_hours_open: v }); }}
                  className="w-full h-9 bg-black border border-white/10 rounded-none px-3 font-mono text-lg text-center text-white shadow-[inset_0_2px_8px_rgba(0,0,0,0.6)] focus:outline-none focus:border-emerald-500/40"
                />
                <div className="flex gap-[1px]">
                  {[24, 48, 72, 168].map(v => (
                    <button key={v} onClick={() => setConfig({ ...config, max_hours_open: v })}
                      className={cn("flex-1 py-1 text-[9px] font-mono font-bold transition-all",
                        config.max_hours_open === v ? "bg-emerald-500/20 text-emerald-400" : "bg-black/40 text-white/20 hover:text-white/50")}
                    >{v}h</button>
                  ))}
                </div>
              </div>
              <div className="bg-[#070707] p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="text-[9px] uppercase tracking-[0.2em] text-white/30 font-mono">Max Concurrent</div>
                  <span className="text-[8px] text-emerald-500/50 font-mono">rec: 3</span>
                </div>
                <input type="number" min="1" max="10" value={config.max_positions}
                  onChange={e => { const v = parseInt(e.target.value); if (!isNaN(v)) setConfig({ ...config, max_positions: v }); }}
                  className="w-full h-9 bg-black border border-white/10 rounded-none px-3 font-mono text-lg text-center text-white shadow-[inset_0_2px_8px_rgba(0,0,0,0.6)] focus:outline-none focus:border-emerald-500/40"
                />
                <div className="flex gap-[1px]">
                  {[1, 3, 5, 10].map(v => (
                    <button key={v} onClick={() => setConfig({ ...config, max_positions: v })}
                      className={cn("flex-1 py-1 text-[9px] font-mono font-bold transition-all",
                        config.max_positions === v ? "bg-emerald-500/20 text-emerald-400" : "bg-black/40 text-white/20 hover:text-white/50")}
                    >{v}</button>
                  ))}
                </div>
              </div>
            </div>

            {/* Asset Buckets */}
            <div className="space-y-2">
              <div className="text-[9px] uppercase tracking-[0.2em] text-white/30 font-mono">Target Asset Universe</div>
              <div className="grid grid-cols-3 gap-[1px] bg-white/[0.06]">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div onClick={() => setConfig({ ...config, majors: !config.majors })}
                        className={cn("flex items-center justify-center gap-1.5 py-2.5 cursor-pointer transition-all text-[9px] font-mono font-bold tracking-wider",
                          config.majors ? "bg-emerald-500/15 text-emerald-400" : "bg-black/60 text-white/20 hover:text-white/40")}
                      >
                        <Trophy size={12} weight={config.majors ? "fill" : "regular"} /> MAJORS
                      </div>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="bg-black/90 border-white/10 text-[10px] p-2 max-w-[200px] font-mono">
                      BTC, ETH, SOL, BNB, XRP, ADA, DOGE, AVAX, DOT, LINK
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                <div onClick={() => setConfig({ ...config, altcoins: !config.altcoins })}
                  className={cn("flex items-center justify-center gap-1.5 py-2.5 cursor-pointer transition-all text-[9px] font-mono font-bold tracking-wider",
                    config.altcoins ? "bg-blue-500/15 text-blue-400" : "bg-black/60 text-white/20 hover:text-white/40")}
                >
                  <ChartLine size={12} weight={config.altcoins ? "fill" : "regular"} /> ALTS
                </div>
                <div onClick={() => setConfig({ ...config, meme_mode: !config.meme_mode })}
                  className={cn("flex items-center justify-center gap-1.5 py-2.5 cursor-pointer transition-all text-[9px] font-mono font-bold tracking-wider",
                    config.meme_mode ? "bg-purple-500/15 text-purple-400" : "bg-black/60 text-white/20 hover:text-white/40")}
                >
                  <Crosshair size={12} weight={config.meme_mode ? "fill" : "regular"} /> MEME
                </div>
              </div>

              {/* Universe size */}
              <div className="flex items-center justify-between pt-1">
                <span className="text-[9px] font-mono text-white/25">UNIVERSE SIZE</span>
                <span className="text-[9px] font-bold font-mono text-emerald-400">{config.universe_size} pairs</span>
              </div>
              <input type="range" min={10} max={50} step={5} value={config.universe_size}
                onChange={e => setConfig({ ...config, universe_size: Number(e.target.value) })}
                className="cockpit-range w-full cursor-pointer"
              />
              <div className="flex justify-between">
                <span className="text-[8px] text-white/15 font-mono">10</span>
                <span className="text-[8px] text-white/15 font-mono">50</span>
              </div>
            </div>

            {/* Custom Symbols */}
            <div className="space-y-1.5">
              <div className="text-[9px] uppercase tracking-[0.2em] text-white/30 font-mono">Custom Symbols (overrides buckets)</div>
              <input type="text" placeholder="BTC/USDT, ETH/USDT, ..."
                value={config.symbols.join(', ')}
                onChange={e => {
                  const syms = e.target.value.split(',').map(s => s.trim().toUpperCase()).filter(s => s.length > 0);
                  setConfig({ ...config, symbols: syms });
                }}
                className="w-full h-9 bg-black border border-white/10 rounded-none px-3 font-mono text-xs text-white shadow-[inset_0_2px_8px_rgba(0,0,0,0.6)] focus:outline-none focus:border-emerald-500/40 placeholder:text-white/15"
              />
            </div>
          </div>

          {/* ── RIGHT: Safety + Deploy ── */}
          <div className="lg:col-span-3 bg-[#0c0505] border-t-2 border-red-500/50 p-5 space-y-5 flex flex-col">
            <div className="text-[8px] font-mono tracking-[0.25em] text-red-500/40 uppercase">[SAF-01] SAFETY</div>

            {/* Max Drawdown — Big Display */}
            <div className="space-y-2">
              <div className="text-[9px] uppercase tracking-[0.2em] text-white/30 font-mono">Max Drawdown Kill Switch</div>
              <div className="text-center py-4 border border-red-500/10 bg-red-500/5">
                <div className={cn("text-5xl font-black font-mono tracking-tight",
                  config.max_drawdown_pct == null ? "text-white/15" : config.max_drawdown_pct <= 10 ? "text-emerald-400" : config.max_drawdown_pct <= 20 ? "text-amber-400" : "text-red-400"
                )}>
                  {config.max_drawdown_pct != null ? `${config.max_drawdown_pct}%` : 'OFF'}
                </div>
                <div className="text-[8px] text-white/20 font-mono mt-1">session drawdown limit</div>
              </div>
              <input type="number" min="1" max="100" value={config.max_drawdown_pct ?? ''} placeholder="NONE"
                onChange={e => setConfig({ ...config, max_drawdown_pct: e.target.value === '' ? null : Number(e.target.value) })}
                className="w-full h-9 bg-black border border-red-500/20 rounded-none px-3 font-mono text-sm text-center text-white shadow-[inset_0_2px_8px_rgba(0,0,0,0.6)] focus:outline-none focus:border-red-500/40 placeholder:text-white/20"
              />
              <div className="flex gap-[1px]">
                {[{ l: 'OFF', v: null }, { l: '10%', v: 10 }, { l: '15%', v: 15 }, { l: '25%', v: 25 }].map(({ l, v }) => (
                  <button key={l} onClick={() => setConfig({ ...config, max_drawdown_pct: v })}
                    className={cn("flex-1 py-1 text-[9px] font-mono font-bold transition-all",
                      config.max_drawdown_pct === v ? "bg-red-500/20 text-red-400" : "bg-black/40 text-white/20 hover:text-white/50")}
                  >{l}</button>
                ))}
              </div>
            </div>

            {/* Capital Limits */}
            <div className="space-y-3">
              <div className="flex items-center gap-1.5 text-[9px] uppercase tracking-[0.2em] text-red-400/50 font-mono">
                <Fire size={10} /> Position Limits
              </div>
              <div className="space-y-2">
                {[
                  { label: 'MAX POSITION SIZE ($)', val: config.max_position_size_usd, key: 'max_position_size_usd' as const },
                  { label: 'MAX TOTAL EXPOSURE ($)', val: config.max_total_exposure_usd, key: 'max_total_exposure_usd' as const },
                  { label: 'MIN BALANCE FLOOR ($)', val: config.min_balance_usd, key: 'min_balance_usd' as const },
                ].map(({ label, val, key }) => (
                  <div key={key}>
                    <div className="text-[8px] text-white/20 font-mono mb-1 uppercase tracking-widest">{label}</div>
                    <input type="number" min="0" value={val}
                      onChange={e => { const v = parseFloat(e.target.value); if (!isNaN(v)) setConfig({ ...config, [key]: v }); }}
                      className="w-full h-9 bg-black border border-red-500/10 rounded-none px-3 font-mono text-sm text-center text-white shadow-[inset_0_2px_8px_rgba(0,0,0,0.6)] focus:outline-none focus:border-red-500/30"
                    />
                  </div>
                ))}
              </div>
            </div>

            <div className="flex-1" />

            {/* Live Acknowledgment */}
            <div className="space-y-3 border border-red-500/20 bg-red-500/5 p-3">
              <div className="flex items-start gap-2">
                <Skull size={14} weight="bold" className="text-red-400 flex-shrink-0 mt-0.5" />
                <p className="text-[9px] text-red-300/60 font-mono leading-relaxed">
                  Deploys real orders on Phemex. Capital at risk — all losses are permanent. Verify position limits and drawdown settings before proceeding.
                </p>
              </div>
              <label className="flex items-start gap-2.5 cursor-pointer">
                <input type="checkbox" checked={ackChecked} onChange={e => setAckChecked(e.target.checked)} className="w-3.5 h-3.5 mt-0.5 accent-red-500 flex-shrink-0" />
                <span className="text-[9px] text-white/40 font-mono leading-relaxed">
                  I accept full responsibility for all trading outcomes
                </span>
              </label>
            </div>

            {/* Deploy Button */}
            <button onClick={handleStart} disabled={!canStart || starting}
              className={cn(
                "w-full py-4 font-black text-sm tracking-[0.25em] uppercase font-mono flex items-center justify-center gap-2 transition-all duration-300 relative overflow-hidden group/btn",
                canStart && !starting
                  ? "bg-red-600 hover:bg-red-500 text-white shadow-[0_0_30px_rgba(239,68,68,0.3)] hover:shadow-[0_0_50px_rgba(239,68,68,0.5)]"
                  : "bg-white/5 text-white/20 cursor-not-allowed border border-white/10",
              )}
            >
              {canStart && !starting && (
                <div className="absolute inset-0 bg-white/10 skew-x-12 -translate-x-full group-hover/btn:translate-x-full transition-transform duration-700" />
              )}
              {starting ? <><ArrowsClockwise size={16} className="animate-spin" /> INITIALIZING...</> : <><Skull size={16} weight="bold" /> DEPLOY LIVE BOT</>}
            </button>
          </div>
        </div>

        {/* System capabilities footer */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-[1px] bg-white/[0.06] border border-white/[0.06]">
          {[
            { icon: <Cpu size={13} className="text-emerald-400" />, title: 'MARKET ADAPTIVE', desc: 'Auto-detects trending, ranging, or compressed conditions — adjusts targets and sizing accordingly.' },
            { icon: <Target size={13} className="text-cyan-400" />, title: 'SMART MONEY ANALYSIS', desc: 'Identifies institutional order blocks, fair value gaps, and liquidity zones across 5 timeframes.' },
            { icon: <ShieldCheck size={13} className="text-amber-400" />, title: 'CAPITAL PROTECTION', desc: 'Exchange-native stops, breakeven lock, session kill switch, and per-trade drawdown limits.' },
          ].map(({ icon, title, desc }) => (
            <div key={title} className="bg-black/60 p-4 space-y-1.5">
              <div className="flex items-center gap-2">{icon}<span className="text-[9px] font-bold font-mono uppercase tracking-[0.2em] text-white/50">{title}</span></div>
              <p className="text-[9px] text-white/25 font-mono leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>

      </div>
    </PageContainer>
  );
}
