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
} from '@phosphor-icons/react';
import type { PaperTradingConfigRequest } from '@/utils/api';

interface PaperTradingConfigProps {
  config: PaperTradingConfigRequest;
  onChange: (config: PaperTradingConfigRequest) => void;
  disabled?: boolean;
}

const SNIPER_MODES = [
  { value: 'stealth', label: 'Stealth', description: 'Balanced swing trading' },
  { value: 'surgical', label: 'Surgical', description: 'Precision scalping' },
  { value: 'strike', label: 'Strike', description: 'Intraday aggressive' },
  { value: 'overwatch', label: 'Overwatch', description: 'Macro surveillance' },
];

const EXCHANGES = [
  { value: 'phemex', label: 'Phemex' },
  { value: 'bybit', label: 'Bybit' },
  { value: 'okx', label: 'OKX' },
  { value: 'bitget', label: 'Bitget' },
];

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

            {/* Sniper Mode */}
            <div className="space-y-2">
              <Label>Sniper Mode</Label>
              <Select
                value={config.sniper_mode ?? 'stealth'}
                onValueChange={(value) => updateConfig({ sniper_mode: value })}
                disabled={disabled}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SNIPER_MODES.map((mode) => (
                    <SelectItem key={mode.value} value={mode.value}>
                      <div className="flex flex-col">
                        <span className="font-medium">{mode.label}</span>
                        <span className="text-xs text-muted-foreground">{mode.description}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
                {/* Min Confluence */}
                <div className="space-y-2">
                  <Label htmlFor="min-confluence">Min Confluence Score</Label>
                  <div className="flex items-center gap-2">
                    <Input
                      id="min-confluence"
                      type="number"
                      min={0}
                      max={100}
                      value={config.min_confluence ?? ''}
                      placeholder="Auto (from mode)"
                      onChange={(e) => updateConfig({ 
                        min_confluence: e.target.value ? parseFloat(e.target.value) : null 
                      })}
                      disabled={disabled}
                      className="font-mono"
                    />
                    <span className="text-muted-foreground">%</span>
                  </div>
                  <p className="text-xs text-muted-foreground">Leave empty to use mode default</p>
                </div>

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
                    onChange={(e) => updateConfig({ fee_rate: (parseFloat(e.target.value) || 0.1) / 100 })}
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
