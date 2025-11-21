import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { SNIPER_MODES, type SniperMode, type SniperModeConfig } from '@/types/sniperMode';
import { CheckCircle } from '@phosphor-icons/react';

interface SniperModeSelectorProps {
  selectedMode: SniperMode;
  onModeSelect: (mode: SniperMode) => void;
  customTimeframes?: string[];
  onCustomTimeframesChange?: (timeframes: string[]) => void;
}

export function SniperModeSelector({
  selectedMode,
  onModeSelect,
  customTimeframes = [],
  onCustomTimeframesChange,
}: SniperModeSelectorProps) {
  const availableTimeframes = ['1W', '1d', '4h', '1h', '15m', '5m', '1m'];

  const handleCustomTimeframeToggle = (tf: string) => {
    if (!onCustomTimeframesChange) return;
    
    const newTimeframes = customTimeframes.includes(tf)
      ? customTimeframes.filter((t) => t !== tf)
      : [...customTimeframes, tf];
    
    onCustomTimeframesChange(newTimeframes);
  };

  const renderModeCard = (config: SniperModeConfig) => {
    const isSelected = selectedMode === config.mode;
    
    return (
      <Card
        key={config.mode}
        className={`cursor-pointer transition-all duration-200 ${
          isSelected
            ? 'bg-accent/20 border-accent border-2 ring-2 ring-accent/30'
            : 'bg-card/50 border-border hover:border-accent/50 hover:bg-card/70'
        }`}
        onClick={() => onModeSelect(config.mode)}
      >
        <CardContent className="p-4">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-2xl">{config.icon}</span>
              <div>
                <h3 className="font-bold text-foreground">{config.name.replace(config.icon + ' ', '')}</h3>
              </div>
            </div>
            {isSelected && (
              <CheckCircle size={24} weight="fill" className="text-accent" />
            )}
          </div>
          
          <p className="text-sm text-muted-foreground mb-3">
            {config.description}
          </p>
          
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Timeframes:</span>
              <div className="flex gap-1">
                {config.mode !== 'custom' ? (
                  config.timeframes.map((tf) => (
                    <Badge key={tf} variant="outline" className="text-xs">
                      {tf}
                    </Badge>
                  ))
                ) : (
                  <span className="text-muted-foreground italic">Configure below</span>
                )}
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Holding Period:</span>
              <span className="font-medium">{config.holdingPeriod}</span>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Min Confluence:</span>
              <Badge variant="secondary">{config.minConfluence}%</Badge>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Risk/Reward:</span>
              <span className="font-bold text-accent">{config.riskReward}x</span>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label className="text-base">Mission Profile</Label>
        <p className="text-sm text-muted-foreground">
          Select your tactical approach based on timeframe and risk tolerance
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {(Object.keys(SNIPER_MODES) as SniperMode[])
          .filter(mode => mode !== 'custom')
          .map((mode) => renderModeCard(SNIPER_MODES[mode]))}
      </div>

      <div className="grid grid-cols-1 gap-3">
        {renderModeCard(SNIPER_MODES.custom)}
      </div>

      {selectedMode === 'custom' && (
        <div className="space-y-3 p-4 bg-muted/30 border border-border rounded-lg">
          <Label>Custom Timeframe Selection</Label>
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-7 gap-2">
            {availableTimeframes.map((tf) => (
              <Button
                key={tf}
                variant={customTimeframes.includes(tf) ? 'default' : 'outline'}
                size="sm"
                className={
                  customTimeframes.includes(tf)
                    ? 'bg-accent hover:bg-accent/90 text-accent-foreground'
                    : ''
                }
                onClick={() => handleCustomTimeframeToggle(tf)}
              >
                {tf}
              </Button>
            ))}
          </div>
          {customTimeframes.length === 0 && (
            <p className="text-xs text-destructive">
              ⚠️ Select at least one timeframe
            </p>
          )}
        </div>
      )}
    </div>
  );
}
