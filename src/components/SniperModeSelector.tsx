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
    <div className="flex flex-col gap-5 w-full">
      {scannerModes.map((mode) => {
          const isSelected = selectedMode?.name === mode.name;
          const { icon: ModeIcon, color, glowClass, borderClass, bgClass, textEffect } = getModeStyle(mode.name);

          return (
            <div
              key={mode.name}
              role="button"
              tabIndex={0}
              aria-label={`Select ${mode.name} sniper mode`}
              aria-pressed={isSelected}
              className="relative group"
              onClick={() => {
                console.log(`[SniperModeSelector] Mode selected: ${mode.name}`);
                setSelectedMode(mode);
                setScanConfig({
                  ...scanConfig,
                  sniperMode: mode.name as any,
                  timeframes: mode.timeframes,
                });
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  console.log(`[SniperModeSelector] Mode selected (keyboard): ${mode.name}`);
                  setSelectedMode(mode);
                  setScanConfig({
                    ...scanConfig,
                    sniperMode: mode.name as any,
                    timeframes: mode.timeframes,
                  });
                }
              }}
            >
              {isSelected && (
                <div className={`absolute -inset-[1px] ${glowClass} rounded-xl blur-sm transition-all duration-300`} />
              )}
              <TacticalCard
                title={mode.name.toUpperCase()}
                description={mode.description}
                selected={isSelected}
                icon={
                  <div className={`w-12 h-12 rounded-lg ${bgClass} flex items-center justify-center shadow-lg ${isSelected ? 'scale-110 shadow-xl' : 'group-hover:scale-105'} transition-all duration-300`}>
                    <ModeIcon size={isSelected ? 26 : 24} weight="bold" className={color} />
                  </div>
                }
                className={[
                  'relative overflow-visible rounded-xl transition-all duration-300 cursor-pointer',
                  isSelected ? 'ring-2 ring-white/20 shadow-2xl' : 'ring-1 ring-white/10 hover:ring-white/15 shadow-lg',
                  bgClass,
                  borderClass,
                  textEffect,
                ].join(' ')}
              >
                <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-transparent via-black/0 to-black/10 rounded-xl" />
                
                <div className="flex items-end justify-between mb-3">
                  <div className="flex-1" />
                  {isSelected && (
                    <Badge className={`${bgClass} ${color} border-none shadow-md animate-in zoom-in duration-200`}>
                      <Crosshair size={12} weight="bold" className="mr-1" />
                      ARMED
                    </Badge>
                  )}
                </div>

                {/* Mode Brief: show only when selected */}
                {/* Mode Brief removed as redundant */}

                <div className="grid grid-cols-2 gap-3 pt-3 border-t border-border/50">
                  <div className="space-y-1">
                    <div className={`text-xs md:text-sm text-muted-foreground uppercase tracking-wide ${isSelected ? 'font-bold' : ''}`}>Timeframes</div>
                    <div className={`hud-terminal text-emerald-200 ${isSelected ? 'text-base md:text-lg font-bold' : 'text-sm md:text-base'} transition-all duration-300`}>
                      {mode.timeframes.join(' · ')}
                    </div>
                  </div>
                  <div className="space-y-1">
                    <div className={`text-xs md:text-sm text-muted-foreground uppercase tracking-wide ${isSelected ? 'font-bold' : ''}`}>Min Confluence</div>
                    <div className={`hud-terminal ${isSelected ? 'text-base md:text-lg font-bold' : 'text-sm md:text-base'} ${color} transition-all duration-300`}>
                      {mode.min_confluence_score}%
                    </div>
                  </div>
                  <div className="space-y-1">
                    <div className={`text-xs md:text-sm text-muted-foreground uppercase tracking-wide ${isSelected ? 'font-bold' : ''}`}>Profile</div>
                    <div className={`hud-terminal text-emerald-200 ${isSelected ? 'text-base md:text-lg font-bold' : 'text-sm md:text-base'} capitalize transition-all duration-300`}>
                      {mode.profile.replace(/_/g, ' ')}
                    </div>
                  </div>
                  <div className="space-y-1">
                    <div className={`text-xs md:text-sm text-muted-foreground uppercase tracking-wide ${isSelected ? 'font-bold' : ''}`}>Scope</div>
                    <div className={`hud-terminal text-emerald-200 ${isSelected ? 'text-base md:text-lg font-bold' : 'text-sm md:text-base'} transition-all duration-300`}>
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
      borderClass: 'ring-cyan-300/60',
      bgClass: 'bg-cyan-600/45',
      textEffect: 'drop-shadow-[0_0_8px_rgba(101,186,195,0.5)]',
    },
    recon: {
      icon: Eye,
      color: 'text-primary',
      glowClass: 'bg-primary/30',
      borderClass: 'ring-emerald-300/60',
      bgClass: 'bg-emerald-600/45',
      textEffect: 'drop-shadow-[0_0_8px_rgba(114,195,132,0.5)]',
    },
    strike: {
      icon: Lightning,
      color: 'text-warning',
      glowClass: 'bg-warning/30',
      borderClass: 'ring-amber-300/60',
      bgClass: 'bg-amber-600/50',
      textEffect: 'drop-shadow-[0_0_10px_rgba(224,186,90,0.6)]',
    },
    surgical: {
      icon: Crosshair,
      color: 'text-success',
      glowClass: 'bg-success/30',
      borderClass: 'ring-green-300/60',
      bgClass: 'bg-green-600/45',
      textEffect: 'drop-shadow-[0_0_8px_rgba(114,195,132,0.5)] tracking-widest',
    },
    ghost: {
      icon: Skull,
      color: 'text-muted-foreground',
      glowClass: 'bg-muted/30',
      borderClass: 'ring-cyan-400/60',
      bgClass: 'bg-cyan-700/35',
      textEffect: 'drop-shadow-[0_0_6px_rgba(200,200,200,0.3)] opacity-80',
    },
  };
  
  return styles[modeName.toLowerCase()] || styles.recon;
}
