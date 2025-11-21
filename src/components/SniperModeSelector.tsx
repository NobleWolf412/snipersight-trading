import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { SNIPER_MODES } from '@/types/sniperMode';
import type { SniperMode } from '@/types/sniperMode';
import { X } from '@phosphor-icons/react';

interface SniperModeSelectorProps {
  selectedMode: SniperMode;
  onModeSelect: (mode: SniperMode) => void;
  customTimeframes?: string[];
  onCustomTimeframesChange?: (timeframes: string[]) => void;
}

const AVAILABLE_TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d', '1w'];

export function SniperModeSelector({
  selectedMode,
  onModeSelect,
  customTimeframes = [],
  onCustomTimeframesChange,
}: SniperModeSelectorProps) {
  const handleTimeframeToggle = (timeframe: string) => {
    if (!onCustomTimeframesChange) return;

    const newTimeframes = customTimeframes.includes(timeframe)
      ? customTimeframes.filter((tf) => tf !== timeframe)
      : [...customTimeframes, timeframe];

    onCustomTimeframesChange(newTimeframes);
  };

  return (
    <div className="space-y-3">
      <Label>Sniper Mode</Label>
      <div className="grid grid-cols-1 gap-2">
        {(Object.keys(SNIPER_MODES) as SniperMode[]).map((modeKey) => {
          const mode = SNIPER_MODES[modeKey];
          const isSelected = selectedMode === modeKey;

          return (
            <Card
              key={modeKey}
              className={`p-4 cursor-pointer transition-all ${
                isSelected
                  ? 'bg-warning/10 border-warning/50 shadow-md'
                  : 'bg-background hover:bg-muted/30 border-border'
              }`}
              onClick={() => onModeSelect(modeKey)}
            >
              <div className="space-y-2">
                <div className="flex items-start justify-between">
                  <div className="space-y-1 flex-1">
                    <div className="font-bold text-sm">{mode.name}</div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {mode.description}
                    </p>
                  </div>
                  {isSelected && (
                    <Badge className="bg-warning text-warning-foreground ml-2">
                      ACTIVE
                    </Badge>
                  )}
                </div>

                {modeKey !== 'custom' && (
                  <div className="grid grid-cols-2 gap-3 pt-2 border-t border-border/50 text-xs">
                    <div>
                      <div className="text-muted-foreground">Timeframes</div>
                      <div className="font-mono font-semibold">
                        {mode.timeframes.join(', ')}
                      </div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Min Confluence</div>
                      <div className="font-mono font-semibold">{mode.minConfluence}%</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Hold Period</div>
                      <div className="font-mono font-semibold">{mode.holdingPeriod}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Risk/Reward</div>
                      <div className="font-mono font-semibold">{mode.riskReward}:1</div>
                    </div>
                  </div>
                )}
              </div>
            </Card>
          );
        })}
      </div>

      {selectedMode === 'custom' && (
        <div className="space-y-3 p-4 bg-muted/20 rounded border border-border">
          <Label className="text-xs">Select Custom Timeframes</Label>
          <div className="flex flex-wrap gap-2">
            {AVAILABLE_TIMEFRAMES.map((tf) => {
              const isSelected = customTimeframes.includes(tf);
              return (
                <button
                  key={tf}
                  type="button"
                  onClick={() => handleTimeframeToggle(tf)}
                  className={`px-3 py-1.5 rounded font-mono text-sm font-semibold transition-all ${
                    isSelected
                      ? 'bg-warning text-warning-foreground'
                      : 'bg-background border border-border hover:border-warning/50'
                  }`}
                >
                  {isSelected && <X size={12} className="inline mr-1" weight="bold" />}
                  {tf}
                </button>
              );
            })}
          </div>
          {customTimeframes.length === 0 && (
            <p className="text-xs text-muted-foreground italic">
              Select at least one timeframe for custom mode
            </p>
          )}
        </div>
      )}
    </div>
  );
}
