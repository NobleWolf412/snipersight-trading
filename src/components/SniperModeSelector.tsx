import { CircleNotch, Crosshair, Eye, Lightning, Skull, Binoculars } from '@phosphor-icons/react';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { useScanner } from '@/context/ScannerContext';
import { TacticalCard } from '@/components/hud';

export function SniperModeSelector() {
  const { scannerModes, selectedMode, setSelectedMode, scanConfig, setScanConfig } = useScanner();

  if (scannerModes.length === 0) {
    return (
      <div className="flex items-center justify-center p-8">
        <CircleNotch size={32} className="animate-spin text-accent" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4">
        {scannerModes.map((mode) => {
          const isSelected = selectedMode?.name === mode.name;
          const { icon: ModeIcon, color, glowClass, borderClass, bgClass, textEffect } = getModeStyle(mode.name);

          return (
            <div
              key={mode.name}
              className="relative group"
              onClick={() => {
                setSelectedMode(mode);
                setScanConfig({
                  ...scanConfig,
                  sniperMode: mode.name as any,
                  timeframes: mode.timeframes,
                });
              }}
            >
              {isSelected && (
                <div className={`absolute -inset-[2px] ${glowClass} rounded-xl blur-md transition-all duration-300`} />
              )}
              <TacticalCard
                title={mode.name.toUpperCase()}
                description={mode.description}
                selected={isSelected}
                icon={
                  <div className={`w-12 h-12 rounded-lg ${bgClass} flex items-center justify-center shadow-md ${isSelected ? 'scale-110' : 'group-hover:scale-105'} transition-transform`}>
                    <ModeIcon size={24} weight="bold" className={color} />
                  </div>
                }
                className={`cursor-pointer ${
                  isSelected
                    ? `bg-muted/40 ${borderClass} shadow-lg transform scale-[1.02] border-2`
                    : 'bg-card/60 hover:bg-muted/30 hover:border-border hover:scale-[1.01] border'
                } ${textEffect}`}
              >
                <div className="absolute inset-0 bg-gradient-to-br from-transparent via-transparent to-black/20 pointer-events-none" />
                
                <div className="flex items-end justify-between">
                  <div className="flex-1" />
                  {isSelected && (
                    <Badge className={`${bgClass} ${color} border-none shadow-md animate-in zoom-in duration-200`}>
                      <Crosshair size={12} weight="bold" className="mr-1" />
                      ARMED
                    </Badge>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-3 pt-3 border-t border-border/50">
                  <div className="space-y-1">
                    <div className="text-xs text-muted-foreground uppercase tracking-wide">Timeframes</div>
                    <div className="hud-terminal text-emerald-200 text-sm">
                      {mode.timeframes.join(' · ')}
                    </div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-muted-foreground uppercase tracking-wide">Min Confluence</div>
                    <div className={`hud-terminal text-sm ${color}`}>
                      {mode.min_confluence_score}%
                    </div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-muted-foreground uppercase tracking-wide">Profile</div>
                    <div className="hud-terminal text-emerald-200 text-sm capitalize">
                      {mode.profile.replace(/_/g, ' ')}
                    </div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-muted-foreground uppercase tracking-wide">Scope</div>
                    <div className="hud-terminal text-emerald-200 text-sm">
                      {mode.timeframes.length} TF
                    </div>
                  </div>
                </div>

                {isSelected && (
                  <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-current to-transparent opacity-50 animate-pulse" style={{ color }} />
                )}
              </TacticalCard>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function getModeStyle(modeName: string) {
  const styles: Record<string, {
    icon: any;
    color: string;
    glowClass: string;
    borderClass: string;
    bgClass: string;
    textEffect: string;
  }> = {
    overwatch: {
      icon: Binoculars,
      color: 'text-accent',
      glowClass: 'bg-accent/30',
      borderClass: 'border-accent/50',
      bgClass: 'bg-accent/10',
      textEffect: 'drop-shadow-[0_0_8px_rgba(101,186,195,0.5)]',
    },
    recon: {
      icon: Eye,
      color: 'text-primary',
      glowClass: 'bg-primary/30',
      borderClass: 'border-primary/50',
      bgClass: 'bg-primary/10',
      textEffect: 'drop-shadow-[0_0_8px_rgba(114,195,132,0.5)]',
    },
    strike: {
      icon: Lightning,
      color: 'text-warning',
      glowClass: 'bg-warning/30',
      borderClass: 'border-warning/50',
      bgClass: 'bg-warning/10',
      textEffect: 'drop-shadow-[0_0_10px_rgba(224,186,90,0.6)] animate-pulse',
    },
    surgical: {
      icon: Crosshair,
      color: 'text-success',
      glowClass: 'bg-success/30',
      borderClass: 'border-success/50',
      bgClass: 'bg-success/10',
      textEffect: 'drop-shadow-[0_0_8px_rgba(114,195,132,0.5)] tracking-widest',
    },
    ghost: {
      icon: Skull,
      color: 'text-muted-foreground',
      glowClass: 'bg-muted/30',
      borderClass: 'border-muted/50',
      bgClass: 'bg-muted/10',
      textEffect: 'drop-shadow-[0_0_6px_rgba(200,200,200,0.3)] opacity-80',
    },
  };
  
  return styles[modeName.toLowerCase()] || styles.recon;
}
