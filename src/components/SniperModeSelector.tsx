import { CircleNotch, Crosshair, Eye, Lightning, Skull, Binoculars } from '@phosphor-icons/react';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { useScanner } from '@/context/ScannerContext';

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
              <Card
                className={`relative cursor-pointer transition-all duration-300 overflow-hidden ${
                  isSelected
                    ? `${bgClass} ${borderClass} shadow-lg transform scale-[1.02]`
                    : 'bg-background/40 hover:bg-background/60 border-border hover:border-border/80 hover:scale-[1.01]'
                }`}
              >
                <div className="absolute inset-0 bg-gradient-to-br from-transparent via-transparent to-black/20 pointer-events-none" />
                
                <div className="relative p-5 space-y-4">
                  <div className="flex items-start justify-between">
                    <div className="space-y-2 flex-1">
                      <div className="flex items-center gap-3">
                        <div className={`w-12 h-12 rounded-lg ${bgClass} flex items-center justify-center flex-shrink-0 shadow-md ${isSelected ? 'scale-110' : 'group-hover:scale-105'} transition-transform`}>
                          <ModeIcon size={24} weight="bold" className={color} />
                        </div>
                        <div>
                          <div className={`font-bold text-lg tracking-wider ${textEffect} ${color}`}>
                            {mode.name.toUpperCase()}
                          </div>
                          <p className="text-sm text-muted-foreground leading-relaxed mt-0.5">
                            {mode.description}
                          </p>
                        </div>
                      </div>
                    </div>
                    {isSelected && (
                      <Badge className={`ml-2 ${bgClass} ${color} border-none shadow-md animate-in zoom-in duration-200`}>
                        <Crosshair size={12} weight="bold" className="mr-1" />
                        ARMED
                      </Badge>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-3 pt-3 border-t border-border/50">
                    <div className="space-y-1">
                      <div className="text-xs text-muted-foreground uppercase tracking-wide">Timeframes</div>
                      <div className="font-mono font-bold text-sm">
                        {mode.timeframes.join(' · ')}
                      </div>
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs text-muted-foreground uppercase tracking-wide">Min Confluence</div>
                      <div className={`font-mono font-bold text-sm ${color}`}>
                        {mode.min_confluence_score}%
                      </div>
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs text-muted-foreground uppercase tracking-wide">Profile</div>
                      <div className="font-mono font-bold text-sm capitalize">
                        {mode.profile.replace(/_/g, ' ')}
                      </div>
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs text-muted-foreground uppercase tracking-wide">Scope</div>
                      <div className="font-mono font-bold text-sm">
                        {mode.timeframes.length} TF
                      </div>
                    </div>
                  </div>
                </div>

                {isSelected && (
                  <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-current to-transparent opacity-50 animate-pulse" style={{ color }} />
                )}
              </Card>
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
