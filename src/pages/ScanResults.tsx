
// War Room Layout - Glass Cockpit Edition
import { useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { api } from '@/utils/api';
import { ScanResult } from '@/utils/mockData';
import { Button } from '@/components/ui/button';
import { TrendUp, Globe, Broadcast, WifiHigh } from '@phosphor-icons/react';
import { RegimeMetadata } from '@/types/regime';
import { cn } from '@/lib/utils';
import { TargetList } from '@/components/ScanResults/TargetList';
import { IntelDossier } from '@/components/ScanResults/IntelDossier';
import { MissionStatsHero } from '@/components/ScanResults/MissionStatsHero';
import { TacticalBackground } from '@/components/ui/TacticalBackground';
import { NavigationRail } from '@/components/Layout/NavigationRail';
import { LiveBadge, DataPill } from '@/components/ui/TacticalComponents';
import { SystemTerminal } from '@/components/ui/SystemTerminal';

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

  // Loading State
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#0a0f0a] flex flex-col items-center justify-center gap-4">
        <div className="relative w-24 h-24">
          <div className="absolute inset-0 rounded-full border-4 border-[#00ff88]/20 border-t-[#00ff88] animate-spin" />
          <div className="absolute inset-4 rounded-full border-4 border-[#00ff88]/20 border-b-[#00ff88] animate-spin-reverse" />
        </div>
        <div className="hud-headline text-[#00ff88] animate-pulse">ESTABLISHING UPLINK...</div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 overflow-hidden bg-[#050505] text-foreground font-sans selection:bg-[#00ff88]/30 selection:text-[#00ff88]">
      <TacticalBackground />
      <SystemTerminal />

      {/* GLOBAL APP SHELL GRID: [NAV | SIDEBAR | MAIN] */}
      <div className="grid h-full w-full grid-cols-[64px_1fr] relative z-10">

        {/* COL 1: NAVIGATION RAIL */}
        <NavigationRail />

        {/* CONTENT AREA (Dynamic Grid) */}
        <div className="flex flex-col h-full overflow-hidden relative">

          {/* HEADER: STATUS BAR */}
          <header className="h-[60px] border-b border-white/10 bg-black/60 backdrop-blur-md flex items-center justify-between px-6 z-50 shrink-0">

            {/* LEFT: SYSTEM & CONTEXT */}
            <div className="flex items-center gap-6">

              {/* System Status (Clean) */}
              <div className="flex items-center gap-2.5">
                <div className="relative flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-accent"></span>
                </div>
                <span className="text-[10px] font-bold tracking-[0.2em] text-accent uppercase font-mono">
                  SYSTEM ONLINE
                </span>
              </div>

              <div className="h-6 w-px bg-white/10 rotate-12" />

              {/* Breadcrumb Context */}
              <div className="flex items-baseline gap-2">
                <h1 className="text-sm font-bold tracking-widest text-white uppercase hud-headline">
                  {(scanMetadata?.mode || 'SCANNER')}
                </h1>
                <span className="text-[10px] text-zinc-500 font-mono tracking-wider uppercase">
                      // {scanMetadata?.profile || 'PRECISION'}
                </span>
              </div>
            </div>

            {/* RIGHT: STATS & ACTIONS */}
            <div className="flex items-center gap-6">

              {/* Stats Group (Text Only, No Boxes) */}
              <div className="hidden lg:flex items-center gap-6 text-[10px] font-mono tracking-wider text-zinc-500">
                <div className="flex items-center gap-2">
                  <span>TARGETS</span>
                  <span className="text-white font-bold text-sm">{scanResults.length}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span>LATENCY</span>
                  <span className="text-accent">1.2s</span>
                </div>
              </div>

              {/* Status Indicator - Shows DEMO MODE when offline */}
              {scanMetadata?.offline ? (
                <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-500/20 rounded border border-amber-500/40 animate-pulse">
                  <div className="w-2 h-2 rounded-full bg-amber-500" />
                  <span className="text-[10px] font-bold text-amber-500 tracking-widest">DEMO MODE</span>
                </div>
              ) : (
                <div className="flex items-center gap-2 px-2 py-1 bg-red-500/10 rounded border border-red-500/20">
                  <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                  <span className="text-[9px] font-bold text-red-500 tracking-widest">LIVE</span>
                </div>
              )}

              <div className="h-6 w-px bg-white/10" />

              {/* Actions */}
              <div className="flex items-center gap-2">
                {selectedId && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedId(null)}
                    className="h-8 text-[10px] font-mono text-zinc-400 hover:text-white hover:bg-white/5 tracking-wider"
                  >
                    <Globe className="mr-2 h-3 w-3" /> DEBRIEF
                  </Button>
                )}

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate('/scan')}
                  className="h-8 border-accent/20 bg-accent/5 hover:bg-accent/10 hover:border-accent/40 text-accent text-[10px] font-bold tracking-widest font-mono shadow-[0_0_10px_-4px_rgba(0,255,170,0.3)]"
                >
                  NEW SCAN
                </Button>
              </div>
            </div>
          </header>

          {/* SPLIT VIEW: SIDEBAR | MAIN */}
          <div className="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-[320px_1fr] lg:grid-cols-[380px_1fr] overflow-hidden relative">

            {/* LEFT PANEL: TARGET FEED */}
            <div className={cn(
              "h-full min-h-0 border-r border-white/5 bg-black/20 backdrop-blur-sm relative transition-transform duration-300 md:translate-x-0 z-20",
              selectedId ? "-translate-x-full md:translate-x-0 absolute md:relative w-full md:w-auto" : "translate-x-0 w-full"
            )}>
              <TargetList
                results={scanResults}
                selectedId={selectedId}
                onSelect={(r) => setSelectedId(r.id)}
                className="h-full bg-transparent border-none"
              />
            </div>

            {/* RIGHT PANEL: INTEL CENTER */}
            <div className="relative h-full overflow-auto bg-black/40">
              {/* Background Texture */}
              <div className="absolute inset-0 opacity-[0.03] pointer-events-none"
                style={{ backgroundImage: 'radial-gradient(circle at center, #00ff88 1px, transparent 1px)', backgroundSize: '40px 40px' }}
              />

              {/* Content Container */}
              <div className="min-h-full w-full relative z-10">
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
        </div>
      </div>
    </div>
  );
}
