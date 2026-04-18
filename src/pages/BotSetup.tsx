import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  Robot, Key, Shield, Warning, CheckCircle, XCircle,
  PlayCircle, TestTube, Skull, ArrowsClockwise,
} from '@phosphor-icons/react';
import { PageContainer } from '@/components/layout/PageContainer';
import { HomeButton } from '@/components/layout/HomeButton';
import { TacticalPanel } from '@/components/TacticalPanel';
import { liveTradingService, type LiveTradingConfigRequest, type PreflightResult } from '@/services/liveTradingService';

type TradingMode = 'testnet' | 'live';

const PRESET_LABELS: Record<string, { gate: number; floor: number }> = {
  conservative: { gate: 72, floor: 62 },
  balanced:     { gate: 65, floor: 55 },
  aggressive:   { gate: 58, floor: 48 },
};

function PresetBtn({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'px-3 py-1.5 rounded text-xs font-mono uppercase tracking-wider border transition-all',
        active
          ? 'bg-accent/20 border-accent text-accent'
          : 'border-zinc-700 text-zinc-400 hover:border-zinc-500',
      )}
    >
      {label}
    </button>
  );
}

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <label className="text-xs font-mono uppercase tracking-wider text-zinc-400">{label}</label>
      {children}
    </div>
  );
}

export function BotSetup() {
  const navigate = useNavigate();

  const [mode, setMode] = useState<TradingMode>('testnet');
  const [preflight, setPreflight] = useState<PreflightResult | null>(null);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ackChecked, setAckChecked] = useState(false);

  // Config state
  const [riskPct, setRiskPct] = useState(1.0);
  const [maxPositions, setMaxPositions] = useState(3);
  const [durationHours, setDurationHours] = useState(24);
  const [scanInterval, setScanInterval] = useState(2);
  const [sensitivity, setSensitivity] = useState('balanced');
  const [maxDrawdown, setMaxDrawdown] = useState<number | null>(10);
  const [maxHoursOpen, setMaxHoursOpen] = useState(72);
  const [maxPosSizeUsd, setMaxPosSizeUsd] = useState(100);
  const [maxExposureUsd, setMaxExposureUsd] = useState(500);
  const [minBalanceUsd, setMinBalanceUsd] = useState(50);
  const [majors, setMajors] = useState(true);
  const [alts, setAlts] = useState(false);
  const [meme, setMeme] = useState(false);

  const runPreflight = async () => {
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
  };

  useEffect(() => { runPreflight(); }, []);

  const canStart = mode === 'testnet'
    ? (preflight?.ok ?? false)
    : (preflight?.ok ?? false) && ackChecked;

  const handleStart = async () => {
    setStarting(true);
    setError(null);
    try {
      const config: LiveTradingConfigRequest = {
        testnet: mode === 'testnet',
        dry_run: false,
        risk_per_trade: riskPct,
        max_positions: maxPositions,
        duration_hours: durationHours,
        scan_interval_minutes: scanInterval,
        sensitivity_preset: sensitivity,
        max_drawdown_pct: maxDrawdown ?? undefined,
        max_hours_open: maxHoursOpen,
        max_position_size_usd: maxPosSizeUsd,
        max_total_exposure_usd: maxExposureUsd,
        min_balance_usd: minBalanceUsd,
        kill_switch_enabled: true,
        trailing_stop: true,
        trailing_activation: 1.5,
        breakeven_after_target: 1,
        majors,
        altcoins: alts,
        meme_mode: meme,
        safety_acknowledgment: mode === 'live' ? 'I_ACCEPT_LIVE_TRADING_RISK' : '',
      };
      await liveTradingService.start(config);
      navigate('/bot/status');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setStarting(false);
    }
  };

  const modeColor = mode === 'live' ? 'text-red-400' : 'text-yellow-400';
  const modeBorder = mode === 'live' ? 'border-red-500/40' : 'border-yellow-500/40';
  const modeBg = mode === 'live' ? 'bg-red-500/10' : 'bg-yellow-500/10';

  return (
    <div className="min-h-screen text-foreground" id="main-content">
      <main className="py-10 md:py-14">
        <PageContainer>
          <div className="space-y-8 max-w-4xl mx-auto">
            <div className="flex justify-start">
              <HomeButton />
            </div>

            {/* Header */}
            <div className="flex items-center gap-4">
              <Robot size={44} weight="bold" className="text-primary" />
              <div>
                <h1 className="text-3xl font-bold tracking-tight heading-hud">AUTONOMOUS BOT</h1>
                <p className="text-sm text-muted-foreground mt-1">Configure and deploy live trading on Phemex</p>
              </div>
            </div>

            {/* Mode selector */}
            <TacticalPanel>
              <div className="p-5 space-y-4">
                <p className="text-xs font-mono uppercase tracking-wider text-zinc-400">Trading Mode</p>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={() => setMode('testnet')}
                    className={cn(
                      'p-4 rounded-xl border-2 text-left transition-all space-y-1',
                      mode === 'testnet' ? 'border-yellow-500/60 bg-yellow-500/10' : 'border-zinc-700 hover:border-zinc-600',
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <TestTube size={18} weight="bold" className="text-yellow-400" />
                      <span className="font-bold text-sm text-yellow-400">TESTNET</span>
                      {mode === 'testnet' && <Badge className="ml-auto bg-yellow-500/20 text-yellow-400 border-yellow-500/40 text-[10px]">SELECTED</Badge>}
                    </div>
                    <p className="text-xs text-zinc-400">Real orders on Phemex testnet. No real money at risk.</p>
                  </button>

                  <button
                    onClick={() => setMode('live')}
                    className={cn(
                      'p-4 rounded-xl border-2 text-left transition-all space-y-1',
                      mode === 'live' ? 'border-red-500/60 bg-red-500/10' : 'border-zinc-700 hover:border-zinc-600',
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <Skull size={18} weight="bold" className="text-red-400" />
                      <span className="font-bold text-sm text-red-400">LIVE — REAL MONEY</span>
                      {mode === 'live' && <Badge className="ml-auto bg-red-500/20 text-red-400 border-red-500/40 text-[10px]">SELECTED</Badge>}
                    </div>
                    <p className="text-xs text-zinc-400">Real orders with real funds. Requires confirmation.</p>
                  </button>
                </div>
              </div>
            </TacticalPanel>

            {/* API Key status */}
            <TacticalPanel>
              <div className="p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-mono uppercase tracking-wider text-zinc-400 flex items-center gap-2">
                    <Key size={14} /> Exchange Connection
                  </p>
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
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      {preflight.ok
                        ? <CheckCircle size={16} weight="bold" className="text-success" />
                        : <XCircle size={16} weight="bold" className="text-destructive" />}
                      <span className={cn('text-sm font-mono', preflight.ok ? 'text-success' : 'text-destructive')}>
                        {preflight.ok ? 'Connected' : 'Not connected'}
                      </span>
                      {preflight.ok && (
                        <span className="text-zinc-400 text-sm ml-auto font-mono">
                          Balance: <span className="text-foreground">${preflight.balance.toFixed(2)}</span>
                        </span>
                      )}
                    </div>
                    {preflight.issues.map((issue, i) => (
                      <p key={i} className="text-xs text-destructive flex items-start gap-1.5">
                        <Warning size={12} className="mt-0.5 flex-shrink-0" /> {issue}
                      </p>
                    ))}
                    {preflight.open_positions.length > 0 && (
                      <p className="text-xs text-warning flex items-center gap-1.5">
                        <Warning size={12} /> {preflight.open_positions.length} existing open position(s) on exchange
                      </p>
                    )}
                    {!preflight.ok && (
                      <p className="text-xs text-zinc-500 mt-1">
                        Add <code className="bg-zinc-800 px-1 rounded">PHEMEX_API_KEY</code> and{' '}
                        <code className="bg-zinc-800 px-1 rounded">PHEMEX_API_SECRET</code> to your <code className="bg-zinc-800 px-1 rounded">.env</code> file, then restart the backend.
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="text-sm text-zinc-500 font-mono">Checking connection...</div>
                )}
              </div>
            </TacticalPanel>

            {/* Session parameters */}
            <TacticalPanel>
              <div className="p-5 space-y-6">
                <p className="text-xs font-mono uppercase tracking-wider text-zinc-400">Session Parameters</p>

                <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
                  <FieldRow label="Risk Per Trade (%)">
                    <div className="flex gap-1.5 flex-wrap">
                      {[0.5, 1, 2, 3].map(v => (
                        <PresetBtn key={v} label={`${v}%`} active={riskPct === v} onClick={() => setRiskPct(v)} />
                      ))}
                    </div>
                    <input
                      type="number" step="0.1" min="0.1" max="5"
                      value={riskPct}
                      onChange={e => setRiskPct(parseFloat(e.target.value))}
                      className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-sm font-mono text-foreground focus:border-accent outline-none"
                    />
                  </FieldRow>

                  <FieldRow label="Max Positions">
                    <div className="flex gap-1.5">
                      {[1, 3, 5].map(v => (
                        <PresetBtn key={v} label={`${v}`} active={maxPositions === v} onClick={() => setMaxPositions(v)} />
                      ))}
                    </div>
                    <input
                      type="number" min="1" max="10"
                      value={maxPositions}
                      onChange={e => setMaxPositions(parseInt(e.target.value))}
                      className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-sm font-mono text-foreground focus:border-accent outline-none"
                    />
                  </FieldRow>

                  <FieldRow label="Duration (hours)">
                    <div className="flex gap-1.5 flex-wrap">
                      {[8, 24, 72].map(v => (
                        <PresetBtn key={v} label={`${v}h`} active={durationHours === v} onClick={() => setDurationHours(v)} />
                      ))}
                    </div>
                    <input
                      type="number" min="1" max="168"
                      value={durationHours}
                      onChange={e => setDurationHours(parseInt(e.target.value))}
                      className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-sm font-mono text-foreground focus:border-accent outline-none"
                    />
                  </FieldRow>

                  <FieldRow label="Scan Interval (min)">
                    <div className="flex gap-1.5 flex-wrap">
                      {[2, 5, 15].map(v => (
                        <PresetBtn key={v} label={`${v}m`} active={scanInterval === v} onClick={() => setScanInterval(v)} />
                      ))}
                    </div>
                    <input
                      type="number" min="1" max="60"
                      value={scanInterval}
                      onChange={e => setScanInterval(parseInt(e.target.value))}
                      className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-sm font-mono text-foreground focus:border-accent outline-none"
                    />
                  </FieldRow>

                  <FieldRow label="Max Drawdown (%)">
                    <div className="flex gap-1.5 flex-wrap">
                      {[null, 10, 15, 25].map(v => (
                        <PresetBtn
                          key={String(v)} label={v === null ? 'OFF' : `${v}%`}
                          active={maxDrawdown === v}
                          onClick={() => setMaxDrawdown(v)}
                        />
                      ))}
                    </div>
                    <input
                      type="number" min="1" max="100"
                      value={maxDrawdown ?? ''}
                      placeholder="OFF"
                      onChange={e => setMaxDrawdown(e.target.value ? parseFloat(e.target.value) : null)}
                      className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-sm font-mono text-foreground focus:border-accent outline-none"
                    />
                  </FieldRow>

                  <FieldRow label="Max Trade Open (hours)">
                    <div className="flex gap-1.5 flex-wrap">
                      {[24, 48, 72].map(v => (
                        <PresetBtn key={v} label={`${v}h`} active={maxHoursOpen === v} onClick={() => setMaxHoursOpen(v)} />
                      ))}
                    </div>
                    <input
                      type="number" min="1" max="720"
                      value={maxHoursOpen}
                      onChange={e => setMaxHoursOpen(parseInt(e.target.value))}
                      className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-sm font-mono text-foreground focus:border-accent outline-none"
                    />
                  </FieldRow>
                </div>

                {/* Signal sensitivity */}
                <FieldRow label="Signal Sensitivity">
                  <div className="flex gap-2 flex-wrap">
                    {(['conservative', 'balanced', 'aggressive'] as const).map(s => {
                      const p = PRESET_LABELS[s];
                      return (
                        <button
                          key={s}
                          onClick={() => setSensitivity(s)}
                          className={cn(
                            'px-4 py-2 rounded-lg border text-xs font-mono uppercase tracking-wider transition-all',
                            sensitivity === s
                              ? 'border-accent bg-accent/10 text-accent'
                              : 'border-zinc-700 text-zinc-400 hover:border-zinc-500',
                          )}
                        >
                          {s}
                          <span className="block text-[10px] text-zinc-500 normal-case mt-0.5">
                            gate {p.gate} / floor {p.floor}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </FieldRow>

                {/* Asset buckets */}
                <FieldRow label="Target Assets">
                  <div className="flex gap-2 flex-wrap">
                    {[
                      { label: 'MAJORS', val: majors, set: setMajors },
                      { label: 'ALTS', val: alts, set: setAlts },
                      { label: 'MEME', val: meme, set: setMeme },
                    ].map(({ label, val, set }) => (
                      <button
                        key={label}
                        onClick={() => set(!val)}
                        className={cn(
                          'px-4 py-2 rounded-lg border text-xs font-mono uppercase tracking-wider transition-all',
                          val ? 'border-accent bg-accent/10 text-accent' : 'border-zinc-700 text-zinc-500',
                        )}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </FieldRow>
              </div>
            </TacticalPanel>

            {/* Live-specific safety caps */}
            <TacticalPanel className={cn('border', modeBorder, modeBg)}>
              <div className="p-5 space-y-5">
                <p className={cn('text-xs font-mono uppercase tracking-wider flex items-center gap-2', modeColor)}>
                  <Shield size={14} />
                  Safety Limits — {mode === 'live' ? 'REAL MONEY' : 'Testnet'}
                </p>
                <div className="grid grid-cols-3 gap-4">
                  <FieldRow label="Max Position Size ($)">
                    <input
                      type="number" min="1"
                      value={maxPosSizeUsd}
                      onChange={e => setMaxPosSizeUsd(parseFloat(e.target.value))}
                      className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-sm font-mono text-foreground focus:border-accent outline-none"
                    />
                  </FieldRow>
                  <FieldRow label="Max Total Exposure ($)">
                    <input
                      type="number" min="1"
                      value={maxExposureUsd}
                      onChange={e => setMaxExposureUsd(parseFloat(e.target.value))}
                      className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-sm font-mono text-foreground focus:border-accent outline-none"
                    />
                  </FieldRow>
                  <FieldRow label="Min Balance Floor ($)">
                    <input
                      type="number" min="0"
                      value={minBalanceUsd}
                      onChange={e => setMinBalanceUsd(parseFloat(e.target.value))}
                      className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-sm font-mono text-foreground focus:border-accent outline-none"
                    />
                  </FieldRow>
                </div>
                <p className="text-xs text-zinc-500">
                  Bot automatically triggers kill switch if balance drops below the floor.
                </p>
              </div>
            </TacticalPanel>

            {/* Live acknowledgment */}
            {mode === 'live' && (
              <TacticalPanel className="border-red-500/40 bg-red-500/5">
                <div className="p-5 space-y-3">
                  <div className="flex items-start gap-3">
                    <Skull size={24} weight="bold" className="text-red-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-bold text-red-400 text-sm">Real Money Warning</p>
                      <p className="text-xs text-zinc-400 mt-1">
                        This bot will place real orders on Phemex using your API keys.
                        Losses are real and irreversible. Ensure your risk limits above are correct.
                      </p>
                    </div>
                  </div>
                  <label className="flex items-center gap-3 cursor-pointer mt-2">
                    <input
                      type="checkbox"
                      checked={ackChecked}
                      onChange={e => setAckChecked(e.target.checked)}
                      className="w-4 h-4 accent-red-500"
                    />
                    <span className="text-xs text-zinc-300">
                      I understand this trades real money and accept full responsibility
                    </span>
                  </label>
                </div>
              </TacticalPanel>
            )}

            {error && (
              <div className="p-4 rounded-lg border border-destructive/40 bg-destructive/10 text-destructive text-sm flex items-start gap-2">
                <Warning size={16} className="flex-shrink-0 mt-0.5" /> {error}
              </div>
            )}

            {/* Action buttons */}
            <div className="flex gap-3">
              <HomeButton className="flex-shrink-0" />
              <button
                onClick={handleStart}
                disabled={!canStart || starting}
                className={cn(
                  'flex-1 h-14 rounded-xl font-bold text-sm uppercase tracking-widest flex items-center justify-center gap-3 transition-all border-2',
                  canStart && !starting
                    ? mode === 'live'
                      ? 'bg-red-600 hover:bg-red-500 border-red-500 text-white shadow-lg shadow-red-900/30'
                      : 'bg-accent/20 hover:bg-accent/30 border-accent text-accent shadow-lg shadow-accent/10'
                    : 'bg-zinc-800 border-zinc-700 text-zinc-500 cursor-not-allowed',
                )}
              >
                {starting ? (
                  <><ArrowsClockwise size={18} className="animate-spin" /> Initializing...</>
                ) : mode === 'live' ? (
                  <><Skull size={18} weight="bold" /> Deploy Live Bot</>
                ) : (
                  <><PlayCircle size={18} weight="bold" /> Deploy on Testnet</>
                )}
              </button>
            </div>
          </div>
        </PageContainer>
      </main>
    </div>
  );
}
