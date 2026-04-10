import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  Gear,
  CaretDown,
  CaretUp,
  CurrencyDollar,
  Target,
  ShieldCheck,
  Timer,
  TrendUp,
  Funnel,
} from '@phosphor-icons/react';
import type { PaperTradingConfigRequest } from '@/utils/api';

interface PaperTradingConfigProps {
  config: PaperTradingConfigRequest;
  onChange: (config: PaperTradingConfigRequest) => void;
  disabled?: boolean;
}

const EXCHANGES = [
  { value: 'phemex', label: 'Phemex' },
  { value: 'bybit', label: 'Bybit' },
  { value: 'okx', label: 'OKX' },
  { value: 'bitget', label: 'Bitget' },
];

type SensitivityPreset = 'conservative' | 'balanced' | 'aggressive' | 'custom';

const SENSITIVITY_PRESETS: Record<SensitivityPreset, {
  label: string;
  gate: number;
  floor: number;
  description: string;
  tradeFreq: string;
  color: string;
}> = {
  conservative: {
    label: 'Conservative',
    gate: 72,
    floor: 62,
    description: 'Only takes the highest-conviction setups at full size. Near-misses still get entered at half position size.',
    tradeFreq: '2–5 trades/week in normal markets',
    color: 'text-blue-400 border-blue-500/40 bg-blue-500/10',
  },
  balanced: {
    label: 'Balanced',
    gate: 65,
    floor: 55,
    description: 'Good setups trade fully. Decent setups trade at half size. Noise is skipped. The default for most sessions.',
    tradeFreq: '5–12 trades/week in normal markets',
    color: 'text-emerald-400 border-emerald-500/40 bg-emerald-500/10',
  },
  aggressive: {
    label: 'Aggressive',
    gate: 58,
    floor: 48,
    description: 'Casts a wider net. Lower bar for full entries, captures weaker setups at half size. More signals, more noise.',
    tradeFreq: '10–20+ trades/week in normal markets',
    color: 'text-orange-400 border-orange-500/40 bg-orange-500/10',
  },
  custom: {
    label: 'Custom',
    gate: 65,
    floor: 55,
    description: 'Set your own gate and floor thresholds.',
    tradeFreq: 'Depends on your settings',
    color: 'text-purple-400 border-purple-500/40 bg-purple-500/10',
  },
};

export function PaperTradingConfig({ config, onChange, disabled }: PaperTradingConfigProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const updateConfig = (updates: Partial<PaperTradingConfigRequest>) => {
    onChange({ ...config, ...updates });
  };

  return (
    <div className="space-y-6">
      {/* Essential Settings */}
      <Card className="border-accent/30">
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center gap-2 text-lg heading-hud">
            <CurrencyDollar size={20} className="text-accent" />
            ACCOUNT SETTINGS
          </CardTitle>
          <CardDescription>Paper trading account configuration</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Initial Balance */}
            <div className="space-y-2">
              <Label htmlFor="initial-balance">Initial Balance (USDT)</Label>
              <Input
                id="initial-balance"
                type="number"
                min={100}
                max={1000000}
                step={100}
                value={config.initial_balance ?? 10000}
                onChange={(e) => updateConfig({ initial_balance: parseFloat(e.target.value) || 10000 })}
                disabled={disabled}
                className="font-mono"
              />
            </div>

            {/* Exchange */}
            <div className="space-y-2">
              <Label>Exchange (for pricing)</Label>
              <Select
                value={config.exchange ?? 'phemex'}
                onValueChange={(value) => updateConfig({ exchange: value })}
                disabled={disabled}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {EXCHANGES.map((ex) => (
                    <SelectItem key={ex.value} value={ex.value}>
                      {ex.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Leverage */}
            <div className="space-y-2">
              <Label htmlFor="leverage">Leverage</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="leverage"
                  type="number"
                  min={1}
                  max={100}
                  value={config.leverage ?? 1}
                  onChange={(e) => updateConfig({ leverage: parseInt(e.target.value) || 1 })}
                  disabled={disabled}
                  className="font-mono w-20"
                />
                <span className="text-muted-foreground">×</span>
                <Badge variant={config.leverage && config.leverage > 10 ? 'destructive' : 'secondary'}>
                  {config.leverage && config.leverage > 20 ? 'HIGH RISK' : config.leverage && config.leverage > 10 ? 'MODERATE' : 'CONSERVATIVE'}
                </Badge>
              </div>
            </div>

            {/* Engine Mode — Fixed to Stealth */}
            <div className="space-y-2">
              <Label>Engine Mode</Label>
              <div className="flex items-center gap-2 h-10 px-3 rounded-md border border-purple-500/30 bg-purple-500/5">
                <Target size={16} className="text-purple-400" />
                <span className="font-mono font-bold text-sm text-purple-400 tracking-wider">STEALTH</span>
                <Badge variant="outline" className="text-[8px] ml-auto border-purple-500/30 text-purple-300/70 bg-purple-500/10 px-1.5 py-0">OPTIMAL</Badge>
              </div>
              <p className="text-[10px] text-muted-foreground/60">Adaptive engine — auto-selects scalp/intraday/swing</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Risk Management */}
      <Card className="border-warning/30">
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center gap-2 text-lg heading-hud">
            <ShieldCheck size={20} className="text-warning" />
            RISK MANAGEMENT
          </CardTitle>
          <CardDescription>Position sizing and risk parameters</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Risk Per Trade */}
            <div className="space-y-2">
              <Label htmlFor="risk-per-trade">Risk Per Trade (%)</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="risk-per-trade"
                  type="number"
                  min={0.1}
                  max={10}
                  step={0.1}
                  value={config.risk_per_trade ?? 2}
                  onChange={(e) => updateConfig({ risk_per_trade: parseFloat(e.target.value) || 2 })}
                  disabled={disabled}
                  className="font-mono w-20"
                />
                <span className="text-muted-foreground">%</span>
                <span className="text-sm text-muted-foreground">
                  ≈ ${((config.initial_balance ?? 10000) * (config.risk_per_trade ?? 2) / 100).toFixed(0)} per trade
                </span>
              </div>
            </div>

            {/* Max Positions */}
            <div className="space-y-2">
              <Label htmlFor="max-positions">Max Open Positions</Label>
              <Input
                id="max-positions"
                type="number"
                min={1}
                max={10}
                value={config.max_positions ?? 3}
                onChange={(e) => updateConfig({ max_positions: parseInt(e.target.value) || 3 })}
                disabled={disabled}
                className="font-mono w-20"
              />
            </div>

            {/* Trailing Stop */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-background border border-border">
              <div>
                <Label htmlFor="trailing-stop">Trailing Stop</Label>
                <p className="text-xs text-muted-foreground">Move stop as price moves in your favor</p>
              </div>
              <Switch
                id="trailing-stop"
                checked={config.trailing_stop ?? true}
                onCheckedChange={(checked) => updateConfig({ trailing_stop: checked })}
                disabled={disabled}
              />
            </div>

            {/* Breakeven After Target */}
            <div className="space-y-2">
              <Label htmlFor="breakeven-target">Breakeven After Target</Label>
              <Select
                value={String(config.breakeven_after_target ?? 1)}
                onValueChange={(value) => updateConfig({ breakeven_after_target: parseInt(value) })}
                disabled={disabled}
              >
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">Target 1</SelectItem>
                  <SelectItem value="2">Target 2</SelectItem>
                  <SelectItem value="3">Target 3</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Signal Sensitivity */}
      <Card className="border-accent/20">
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center gap-2 text-lg heading-hud">
            <Funnel size={20} className="text-accent" />
            SIGNAL SENSITIVITY
          </CardTitle>
          <CardDescription>How aggressively the bot enters trades</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Preset Buttons */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {(Object.keys(SENSITIVITY_PRESETS) as SensitivityPreset[]).map((preset) => {
              const p = SENSITIVITY_PRESETS[preset];
              const isSelected = (config.sensitivity_preset ?? 'balanced') === preset;
              return (
                <button
                  key={preset}
                  type="button"
                  disabled={disabled}
                  onClick={() => {
                    if (preset !== 'custom') {
                      updateConfig({
                        sensitivity_preset: preset,
                        min_confluence: null,
                        confluence_soft_floor: null,
                      });
                    } else {
                      updateConfig({
                        sensitivity_preset: 'custom',
                        min_confluence: config.min_confluence ?? 65,
                        confluence_soft_floor: config.confluence_soft_floor ?? 55,
                      });
                    }
                  }}
                  className={`relative flex flex-col items-center justify-center gap-1 p-3 rounded-lg border text-sm font-semibold transition-all ${
                    isSelected
                      ? `${p.color} border-opacity-80`
                      : 'border-border text-muted-foreground hover:border-muted-foreground/50 hover:text-foreground'
                  } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                >
                  <span className="text-xs font-bold tracking-wide uppercase">{p.label}</span>
                  {preset !== 'custom' && (
                    <span className="text-[10px] opacity-70 font-mono">{p.gate}/{p.floor}</span>
                  )}
                  {isSelected && (
                    <span className="absolute top-1 right-1.5 text-[8px] font-bold opacity-60">✓</span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Custom Inputs */}
          {(config.sensitivity_preset ?? 'balanced') === 'custom' && (
            <div className="grid grid-cols-2 gap-4 p-3 rounded-lg border border-purple-500/20 bg-purple-500/5">
              <div className="space-y-1.5">
                <Label htmlFor="custom-gate" className="text-xs">Gate — Full Size (%)</Label>
                <div className="flex items-center gap-2">
                  <Input
                    id="custom-gate"
                    type="number"
                    min={40}
                    max={100}
                    step={1}
                    value={config.min_confluence ?? 65}
                    onChange={(e) => updateConfig({ min_confluence: parseFloat(e.target.value) || 65 })}
                    disabled={disabled}
                    className="font-mono w-20"
                  />
                  <span className="text-muted-foreground text-sm">%</span>
                </div>
                <p className="text-[10px] text-muted-foreground/70">Score ≥ gate → 100% size</p>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="custom-floor" className="text-xs">Floor — Half Size (%)</Label>
                <div className="flex items-center gap-2">
                  <Input
                    id="custom-floor"
                    type="number"
                    min={30}
                    max={100}
                    step={1}
                    value={config.confluence_soft_floor ?? 55}
                    onChange={(e) => updateConfig({ confluence_soft_floor: parseFloat(e.target.value) || 55 })}
                    disabled={disabled}
                    className="font-mono w-20"
                  />
                  <span className="text-muted-foreground text-sm">%</span>
                </div>
                <p className="text-[10px] text-muted-foreground/70">Floor ≤ score &lt; gate → 50% size</p>
              </div>
            </div>
          )}

          {/* Description Panel */}
          {(() => {
            const preset = (config.sensitivity_preset ?? 'balanced') as SensitivityPreset;
            const p = SENSITIVITY_PRESETS[preset];
            const gate  = preset === 'custom' ? (config.min_confluence ?? 65) : p.gate;
            const floor = preset === 'custom' ? (config.confluence_soft_floor ?? 55) : p.floor;
            return (
              <div className={`rounded-lg border p-3 space-y-2 ${p.color}`}>
                <p className="text-xs leading-relaxed opacity-90">{p.description}</p>
                <div className="grid grid-cols-3 gap-2 text-[10px] font-mono">
                  <div className="flex flex-col gap-0.5">
                    <span className="opacity-60 uppercase tracking-wider">Full size</span>
                    <span className="font-bold">≥ {gate}%</span>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <span className="opacity-60 uppercase tracking-wider">Half size</span>
                    <span className="font-bold">{floor}–{gate}%</span>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <span className="opacity-60 uppercase tracking-wider">Skip</span>
                    <span className="font-bold">&lt; {floor}%</span>
                  </div>
                </div>
                <p className="text-[10px] opacity-60 italic">{p.tradeFreq}</p>
              </div>
            );
          })()}
        </CardContent>
      </Card>

      {/* Automation Settings */}
      <Card className="border-primary/30">
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center gap-2 text-lg heading-hud">
            <Timer size={20} className="text-primary" />
            AUTOMATION
          </CardTitle>
          <CardDescription>Scan frequency and session duration</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Scan Interval */}
            <div className="space-y-2">
              <Label htmlFor="scan-interval">Scan Interval</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="scan-interval"
                  type="number"
                  min={1}
                  max={60}
                  value={config.scan_interval_minutes ?? 5}
                  onChange={(e) => updateConfig({ scan_interval_minutes: parseInt(e.target.value) || 5 })}
                  disabled={disabled}
                  className="font-mono w-20"
                />
                <span className="text-muted-foreground">minutes</span>
              </div>
            </div>

            {/* Duration */}
            <div className="space-y-2">
              <Label htmlFor="duration">Session Duration</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="duration"
                  type="number"
                  min={0}
                  max={168}
                  value={config.duration_hours ?? 24}
                  onChange={(e) => updateConfig({ duration_hours: parseInt(e.target.value) || 24 })}
                  disabled={disabled}
                  className="font-mono w-20"
                />
                <span className="text-muted-foreground">hours</span>
                <span className="text-xs text-muted-foreground">(0 = manual stop)</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Advanced Settings (Collapsible) */}
      <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
        <Card className="border-muted">
          <CollapsibleTrigger asChild>
            <CardHeader className="cursor-pointer hover:bg-muted/30 transition-colors pb-4">
              <CardTitle className="flex items-center justify-between text-lg heading-hud">
                <div className="flex items-center gap-2">
                  <Gear size={20} className="text-muted-foreground" />
                  ADVANCED SETTINGS
                </div>
                {showAdvanced ? <CaretUp size={20} /> : <CaretDown size={20} />}
              </CardTitle>
              <CardDescription>Fine-tune simulation parameters</CardDescription>
            </CardHeader>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <CardContent className="space-y-4 pt-0">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Trailing Activation */}
                <div className="space-y-2">
                  <Label htmlFor="trailing-activation">Trailing Activation (R)</Label>
                  <Input
                    id="trailing-activation"
                    type="number"
                    min={1}
                    max={5}
                    step={0.1}
                    value={config.trailing_activation ?? 1.5}
                    onChange={(e) => updateConfig({ trailing_activation: parseFloat(e.target.value) || 1.5 })}
                    disabled={disabled || !(config.trailing_stop ?? true)}
                    className="font-mono w-24"
                  />
                  <p className="text-xs text-muted-foreground">Profit multiple before trailing starts</p>
                </div>

                {/* Slippage */}
                <div className="space-y-2">
                  <Label htmlFor="slippage">Simulated Slippage (bps)</Label>
                  <Input
                    id="slippage"
                    type="number"
                    min={0}
                    max={50}
                    step={1}
                    value={config.slippage_bps ?? 5}
                    onChange={(e) => updateConfig({ slippage_bps: parseFloat(e.target.value) || 5 })}
                    disabled={disabled}
                    className="font-mono w-24"
                  />
                  <p className="text-xs text-muted-foreground">1 bps = 0.01%</p>
                </div>

                {/* Fee Rate */}
                <div className="space-y-2">
                  <Label htmlFor="fee-rate">Trading Fee (%)</Label>
                  <Input
                    id="fee-rate"
                    type="number"
                    min={0}
                    max={1}
                    step={0.01}
                    value={(config.fee_rate ?? 0.001) * 100}
                    onChange={(e) => { const v = parseFloat(e.target.value); updateConfig({ fee_rate: (isNaN(v) ? 0.1 : v) / 100 }); }}
                    disabled={disabled}
                    className="font-mono w-24"
                  />
                </div>
              </div>
            </CardContent>
          </CollapsibleContent>
        </Card>
      </Collapsible>
    </div>
  );
}

export default PaperTradingConfig;
