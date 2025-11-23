import { useState, useEffect } from 'react';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { api } from '@/utils/api';
import type { ScannerMode } from '@/utils/api';
import { Loader } from '@phosphor-icons/react';

interface SniperModeSelectorProps {
  selectedMode: string;
  onModeSelect: (modeName: string, mode: ScannerMode) => void;
}

export function SniperModeSelector({
  selectedMode,
  onModeSelect,
}: SniperModeSelectorProps) {
  const [modes, setModes] = useState<ScannerMode[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchModes = async () => {
      const response = await api.getScannerModes();
      if (response.data) {
        setModes(response.data.modes);
      }
      setLoading(false);
    };
    fetchModes();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader size={32} className="animate-spin text-accent" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <Label className="text-base">Sniper Mode</Label>
      <div className="grid grid-cols-1 gap-3">
        {modes.map((mode) => {
          const isSelected = selectedMode === mode.name;
          const modeIcon = getModeIcon(mode.name);

          return (
            <Card
              key={mode.name}
              className={`p-4 cursor-pointer transition-all ${
                isSelected
                  ? 'bg-accent/10 border-accent shadow-md'
                  : 'bg-background hover:bg-muted/30 border-border'
              }`}
              onClick={() => onModeSelect(mode.name, mode)}
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div className="space-y-1 flex-1">
                    <div className="font-bold text-base flex items-center gap-2">
                      <span className="text-xl">{modeIcon}</span>
                      {mode.name.toUpperCase()}
                    </div>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {mode.description}
                    </p>
                  </div>
                  {isSelected && (
                    <Badge className="bg-accent text-accent-foreground ml-2">
                      ARMED
                    </Badge>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-4 pt-2 border-t border-border/50 text-xs">
                  <div>
                    <div className="text-muted-foreground mb-1">Timeframes</div>
                    <div className="font-mono font-semibold">
                      {mode.timeframes.join(' · ')}
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground mb-1">Min Confluence</div>
                    <div className="font-mono font-semibold text-accent">
                      {mode.min_confluence_score}%
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground mb-1">Profile</div>
                    <div className="font-mono font-semibold capitalize">
                      {mode.profile.replace(/_/g, ' ')}
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground mb-1">Scope</div>
                    <div className="font-mono font-semibold">
                      {mode.timeframes.length} TF
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function getModeIcon(modeName: string): string {
  const icons: Record<string, string> = {
    overwatch: '🔭',
    recon: '🎯',
    strike: '⚡',
    surgical: '🔬',
    ghost: '👻',
  };
  return icons[modeName.toLowerCase()] || '🎯';
}
