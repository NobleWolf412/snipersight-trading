import { CircleNotch, Crosshair, Eye, Lightning, Skull, Binoculars, Star } from '@phosphor-icons/react';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { useScanner } from '@/context/ScannerContext';
import { TacticalCard } from '@/components/hud';
import { api } from '@/utils/api';
import { useEffect, useState } from 'react';

// Mode recommendation logic based on market regime
function getModeRecommendation(modeName: string, regime: string | null): { recommended: boolean; reason: string } {
  if (!regime) return { recommended: false, reason: '' };

  const regimeLower = regime.toLowerCase();

  // Trending markets favor Overwatch (swing) and Stealth (balanced)
  if (regimeLower.includes('trend') || regimeLower.includes('expansion')) {
    if (modeName === 'overwatch') return { recommended: true, reason: 'Trending market' };
    if (modeName === 'stealth') return { recommended: true, reason: 'Good for trends' };
  }

  // Range/coiling markets favor Strike (intraday) and Surgical (precision)
  if (regimeLower.includes('range') || regimeLower.includes('coil') || regimeLower.includes('sideways')) {
    if (modeName === 'strike') return { recommended: true, reason: 'Intraday plays' };
    if (modeName === 'surgical') return { recommended: true, reason: 'Precision scalps' };
  }

  // High volatility markets favor Strike
  if (regimeLower.includes('volatile') || regimeLower.includes('explosive')) {
    if (modeName === 'strike') return { recommended: true, reason: 'High volatility' };
  }

  return { recommended: false, reason: '' };
}

export function SniperModeSelector() {
  const { scannerModes, selectedMode, setSelectedMode, scanConfig, setScanConfig } = useScanner();
  const [marketRegime, setMarketRegime] = useState<string | null>(null);

  // Fetch market regime on mount
  useEffect(() => {
    api.getMarketRegime().then((res) => {
      if (res.data?.composite) {
        setMarketRegime(res.data.composite);
      }
    }).catch(() => { });
  }, []);

  if (scannerModes.length === 0) {
    return (
      <div className="flex items-center justify-center p-8">
        <CircleNotch size={32} className="animate-spin text-accent" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 w-full">
      {marketRegime && (
        <div className="text-xs text-muted-foreground mb-1 px-1">
          📊 Market: <span className="text-foreground font-medium">{marketRegime.replace(/_/g, ' ')}</span>
        </div>
      )}
      {scannerModes.map((mode) => {
        const isSelected = selectedMode?.name === mode.name;
        const { icon: ModeIcon, color, glowClass, borderClass, bgClass, textEffect } = getModeStyle(mode.name);
        const recommendation = getModeRecommendation(mode.name, marketRegime);

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
                <div className="flex-1">
                  {recommendation.recommended && !isSelected && (
                    <Badge className="bg-accent/20 text-accent border-accent/30 text-[10px] animate-pulse">
                      <Star size={10} weight="fill" className="mr-1" />
                      {recommendation.reason}
                    </Badge>
                  )}
                </div>
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
    strike: {
      icon: Lightning,
      color: 'text-amber-300',
      glowClass: 'bg-amber-500/30',
      borderClass: 'ring-amber-400/60',
      bgClass: 'bg-amber-600/40',
      textEffect: 'drop-shadow-[0_0_10px_rgba(251,191,36,0.6)]',
    },
    surgical: {
      icon: Crosshair,
      color: 'text-purple-300',
      glowClass: 'bg-purple-500/30',
      borderClass: 'ring-purple-400/60',
      bgClass: 'bg-purple-600/40',
      textEffect: 'drop-shadow-[0_0_8px_rgba(168,85,247,0.5)]',
    },
    stealth: {
      icon: Skull,
      color: 'text-violet-300',
      glowClass: 'bg-violet-500/30',
      borderClass: 'ring-violet-400/60',
      bgClass: 'bg-violet-700/35',
      textEffect: 'drop-shadow-[0_0_6px_rgba(139,92,246,0.4)]',
    },
  };

  return styles[modeName.toLowerCase()] || styles.overwatch;
}
