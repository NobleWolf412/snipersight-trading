
// War Room Layout - Force Rebuild
import { useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { api } from '@/utils/api';
import { ScanResult } from '@/utils/mockData';
import { Button } from '@/components/ui/button';
import { TrendUp } from '@phosphor-icons/react';
import { RegimeMetadata } from '@/types/regime';
import { cn } from '@/lib/utils';
import { TargetList } from '@/components/ScanResults/TargetList';
import { IntelDossier } from '@/components/ScanResults/IntelDossier';
import { MissionStatsHero } from '@/components/ScanResults/MissionStatsHero';
import { HomeButton } from '@/components/layout/HomeButton';
import { TacticalBackground } from '@/components/ui/TacticalBackground';

export function ScanResults() {
  const navigate = useNavigate();
  const [scanResults, setScanResults] = useState<ScanResult[]>([]);
  const [scanMetadata, setScanMetadata] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [globalRegime, setGlobalRegime] = useState<RegimeMetadata | undefined>(undefined);
  const [symbolRegimes, setSymbolRegimes] = useState<Record<string, RegimeMetadata | undefined>>({});

  // 1. Load Data
  useEffect(() => {
    try {
      const resultsStr = localStorage.getItem('scan-results');
      const metadataStr = localStorage.getItem('scan-metadata');
      if (resultsStr) setScanResults(JSON.parse(resultsStr));
      if (metadataStr) setScanMetadata(JSON.parse(metadataStr));
    } catch (e) {
      console.error('Failed to parse scan data', e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 2. Fetch Regimes (Optional: Keep existing logic for deeper data)
  useEffect(() => {
    const topSymbols = (scanResults || []).slice(0, 6).map(r => r.pair);
    if (!topSymbols.length) return;
    let cancelled = false;
    (async () => {
      const updates: Record<string, RegimeMetadata | undefined> = {};
      await Promise.all(topSymbols.map(async (pair) => {
        const symbol = pair;
        const { data } = await api.getSymbolRegime(symbol);
        if (!data) return;
        updates[pair] = {
          symbol_regime: {
            // @ts-ignore
            trend: data?.trend,
            // @ts-ignore
            volatility: data?.volatility,
            score: data?.score ?? 0,
          }
        };
      }));
      if (!cancelled) setSymbolRegimes(prev => ({ ...prev, ...updates }));
    })();
    return () => { cancelled = true; };
  }, [scanResults]);

  const selectedResult = scanResults.find(r => r.id === selectedId);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#0a0f0a] flex items-center justify-center">
        <div className="animate-pulse text-[#00ff88] font-mono tracking-widest">INITIALIZING WAR ROOM...</div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen overflow-hidden bg-[#0a0f0a] text-foreground flex flex-col">
      <TacticalBackground />

      {/* Top Navigation Bar (Compact) */}
      <header className="h-14 border-b border-[#00ff88]/20 bg-black/40 backdrop-blur-md flex items-center justify-between px-4 z-50 shrink-0">
        <div className="flex items-center gap-4">
          <HomeButton />
          <div className="h-6 w-px bg-white/10" />
          <h1 className="text-lg font-bold hud-headline tracking-widest text-white hidden md:block">
            TACTICAL COMMAND
          </h1>
        </div>

        <div className="flex items-center gap-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/scan')}
            className="border-[#00ff88]/30 hover:bg-[#00ff88]/10 text-[#00ff88] font-mono text-xs"
          >
            <TrendUp weight="bold" className="mr-2" /> NEW SCAN
          </Button>
        </div>
      </header>

      {/* Main Content Area - Split Pane */}
      <div className="flex-1 flex overflow-hidden relative z-10">

        {/* LEFT PANEL: Target Feed - FLOATING GLASS DESIGN */}
        <div className={cn(
          "w-full md:w-[350px] lg:w-[400px] flex-shrink-0 h-full transition-transform duration-300 absolute md:relative z-20 bg-[#0a0f0a] md:bg-transparent",
          selectedId ? "-translate-x-full md:translate-x-0" : "translate-x-0"
        )}>
          <div className="h-full w-full md:p-4 md:pr-2">
            {/* Outer Glow Container */}
            <div className="h-full w-full relative group/panel">
              {/* Floating Glow Effect - Bottom (intensifies on hover) */}
              <div className="absolute -bottom-3 left-6 right-6 h-20 bg-[#00ff88]/15 blur-3xl rounded-full transition-all duration-500 group-hover/panel:bg-[#00ff88]/30 group-hover/panel:h-24" />

              {/* Main Card - Dark Glass */}
              <div className="h-full w-full overflow-hidden md:rounded-2xl relative
                md:border md:border-white/10
                md:bg-gradient-to-b md:from-[#151515] md:via-[#0d0d0d] md:to-[#0a0a0a]
                md:shadow-[0_25px_50px_-12px_rgba(0,0,0,0.9),0_0_0_1px_rgba(255,255,255,0.05)]
                md:backdrop-blur-xl
                transition-all duration-300
                group-hover/panel:border-[#00ff88]/30
                group-hover/panel:shadow-[0_25px_60px_-12px_rgba(0,255,136,0.15),0_0_0_1px_rgba(0,255,136,0.2)]
              ">
                {/* Animated Shimmer Effect (on hover) */}
                <div className="absolute inset-0 overflow-hidden rounded-2xl pointer-events-none">
                  <div className="absolute inset-0 -translate-x-full group-hover/panel:translate-x-full transition-transform duration-1000 ease-in-out bg-gradient-to-r from-transparent via-white/5 to-transparent" />
                </div>

                {/* Top Edge Highlight */}
                <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent group-hover/panel:via-[#00ff88]/40 transition-colors duration-300" />

                {/* Scanline Effect */}
                <div className="absolute inset-0 pointer-events-none opacity-[0.02]"
                  style={{
                    backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.03) 2px, rgba(255,255,255,0.03) 4px)',
                  }}
                />

                {/* Corner Brackets - Tactical HUD */}
                <div className="absolute top-3 left-3 w-4 h-4 border-t-2 border-l-2 border-white/20 group-hover/panel:border-[#00ff88]/60 transition-colors duration-300" />
                <div className="absolute top-3 right-3 w-4 h-4 border-t-2 border-r-2 border-white/20 group-hover/panel:border-[#00ff88]/60 transition-colors duration-300" />
                <div className="absolute bottom-3 left-3 w-4 h-4 border-b-2 border-l-2 border-white/20 group-hover/panel:border-[#00ff88]/60 transition-colors duration-300" />
                <div className="absolute bottom-3 right-3 w-4 h-4 border-b-2 border-r-2 border-white/20 group-hover/panel:border-[#00ff88]/60 transition-colors duration-300" />

                {/* Status Indicator Light */}
                <div className="absolute top-4 right-10 flex items-center gap-2 z-10">
                  <div className="w-2 h-2 rounded-full bg-[#00ff88] animate-pulse shadow-[0_0_8px_rgba(0,255,136,0.8)]" />
                  <span className="text-[9px] font-mono text-[#00ff88]/60 tracking-wider">LIVE</span>
                </div>

                <TargetList
                  results={scanResults}
                  selectedId={selectedId}
                  onSelect={(r) => setSelectedId(r.id)}
                  className="md:bg-transparent md:border-none"
                />
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT PANEL: Intel Dossier (Main) */}
        <div className="flex-1 h-full relative bg-black/40 backdrop-blur-sm overflow-hidden">
          {selectedResult ? (
            <IntelDossier
              result={selectedResult}
              metadata={scanMetadata}
              regime={symbolRegimes[selectedResult.pair] || globalRegime}
              onClose={() => setSelectedId(null)}
            />
          ) : (
            <MissionStatsHero
              results={scanResults}
              metadata={scanMetadata}
            />
          )}
        </div>
      </div>
    </div>
  );
}
