import { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { TacticalBackground } from '@/components/ui/TacticalBackground';
import { TacticalReturnButton } from '@/components/ui/TacticalReturnButton';
import { ResultCard } from '@/components/ScanResults/ResultCard';
import { RejectionCard, RejectionInfo } from '@/components/ScanResults/RejectionCard';
import { IntelDossier } from '@/components/ScanResults/IntelDossier';
import { ScanResult } from '@/utils/mockData';
import { Target, WarningCircle, CaretLeft, CaretRight, ArrowCounterClockwise } from '@phosphor-icons/react';
import { cn } from '@/lib/utils'; // Assuming cn exists

export function ScanResults() {
  const navigate = useNavigate();
  const dossierRef = useRef<HTMLDivElement>(null);
  const [activeTab, setActiveTab] = useState<'targets' | 'rejected'>('targets');
  const [results, setResults] = useState<ScanResult[]>([]);
  const [rejections, setRejections] = useState<RejectionInfo[]>([]);
  const [scanMetadata, setScanMetadata] = useState<any>(null);
  const [selectedResult, setSelectedResult] = useState<ScanResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const handleResultClick = (id: string) => {
    const result = results.find(r => r.id === id);
    if (result) {
      setSelectedResult(result);
      // Small timeout to allow render then scroll
      setTimeout(() => {
        dossierRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    }
  };

  // Load Data
  useEffect(() => {
    try {
      const resultsStr = localStorage.getItem('scan-results');
      const metadataStr = localStorage.getItem('scan-metadata');

      if (resultsStr) {
        setResults(JSON.parse(resultsStr));
      }

      if (metadataStr) {
        const meta = JSON.parse(metadataStr);
        setScanMetadata(meta); // Set scan metadata
        // Parse Rejections
        // structure: meta.rejection_summary.details = { "low_confluence": [...], ... }
        console.log('[ScanResults] Metadata:', meta);
        console.log('[ScanResults] Rejection summary:', meta?.rejection_summary);
        if (meta?.rejection_summary?.details) {
          console.log('[ScanResults] Rejection details:', meta.rejection_summary.details);
          const flatRejections: RejectionInfo[] = [];
          Object.values(meta.rejection_summary.details).forEach((group: any) => {
            if (Array.isArray(group)) {
              flatRejections.push(...group);
            }
          });
          console.log('[ScanResults] Flat rejections:', flatRejections);
          setRejections(flatRejections);
        } else {
          console.log('[ScanResults] No rejection details found');
        }
      }
    } catch (e) {
      console.error("Failed to load scan results", e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const stats = useMemo(() => {
    return {
      total: results.length + rejections.length,
      success: results.length,
      rejected: rejections.length,
      successRate: (results.length + rejections.length) > 0
        ? Math.round((results.length / (results.length + rejections.length)) * 100)
        : 0
    };
  }, [results, rejections]);

  return (
    <div className="min-h-screen bg-[#030504] text-zinc-100 font-sans selection:bg-[#00ff88]/30 relative">
      <TacticalBackground />

      {/* Return Button */}
      <div className="absolute top-6 left-6 z-50">
        <TacticalReturnButton />
      </div>

      <main className="relative z-10 min-h-screen flex flex-col items-center">

        {/* HERO: Mode Header (Front & Center) */}
        <div className="w-full pt-12 pb-8 flex flex-col items-center justify-center relative space-y-4">
          {/* Scan Identifier Badge */}
          <div className="flex items-center gap-2 px-4 py-2 rounded-full glass-card glow-border-green">
            <div className="w-2 h-2 rounded-full bg-[#00ff88] animate-pulse shadow-[0_0_8px_#00ff88]" />
            <span className="text-sm font-bold tracking-[0.2em] uppercase hud-text-green">ACTIVE SCAN RESULTS</span>
          </div>

          {/* Stylized Mode Name */}
          <div className="space-y-1 text-center">
            <h1 className="text-6xl md:text-8xl font-black italic tracking-tighter text-transparent bg-clip-text bg-gradient-to-b from-white via-green-50 to-green-400/80 drop-shadow-[0_4px_4px_rgba(0,0,0,0.5)]">
              {(scanMetadata?.mode || 'TACTICAL').toUpperCase()}
            </h1>
            <div className="h-1 w-32 mx-auto bg-gradient-to-r from-transparent via-[#00ff88]/50 to-transparent rounded-full" />
          </div>

          {/* Context Metadata */}
          <div className="flex items-center gap-4 text-sm font-mono text-zinc-400 tracking-wider">
            <span className="text-zinc-300">{scanMetadata?.profile?.toUpperCase() || 'DEFAULT PROFILE'}</span>
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-700" />
            <span className="text-zinc-300">MIN SCORE: {scanMetadata?.effectiveMinScore || 0}%</span>
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-700" />
            <span className="text-[#00ff88]">{scanMetadata?.leverage || 1}x LEVERAGE</span>
          </div>

          {/* New Scan Action */}
          <button
            onClick={() => navigate('/scan')}
            className="group mt-8 flex items-center gap-3 px-8 py-3 bg-[#0a0a0a] border border-[#00ff88]/30 hover:bg-[#00ff88]/10 text-[#00ff88] rounded-xl font-bold font-mono tracking-widest uppercase transition-all shadow-[0_0_20px_rgba(0,255,136,0.05)] hover:shadow-[0_0_30px_rgba(0,255,136,0.15)] hover:border-[#00ff88]/60"
          >
            <ArrowCounterClockwise size={20} weight="bold" className="group-hover:-rotate-180 transition-transform duration-500" />
            New Scan
          </button>
        </div>



        <div className="w-full max-w-7xl px-8 pb-24">

          {/* Header & Stats */}
          <div className="mb-10">
            {/* Stats Bar */}
            <div className="grid grid-cols-4 gap-6 p-6 rounded-2xl bg-zinc-900/40 border border-zinc-800/60 backdrop-blur-sm mt-6 shadow-[0_0_30px_rgba(0,0,0,0.3)] hover:border-[#00ff88]/30 hover:shadow-[0_0_20px_rgba(0,255,136,0.05)] transition-all duration-500">
              <div>
                <div className="text-sm uppercase tracking-wider text-zinc-400 font-bold mb-1">Total Scanned</div>
                <div className="text-4xl font-mono text-white tracking-tighter">{stats.total}</div>
              </div>
              <div>
                <div className="text-sm uppercase tracking-wider text-zinc-400 font-bold mb-1">Targets Acquired</div>
                <div className="text-4xl font-mono text-[#00ff88] tracking-tighter">{stats.success}</div>
              </div>
              <div>
                <div className="text-sm uppercase tracking-wider text-zinc-400 font-bold mb-1">Rejected</div>
                <div className="text-4xl font-mono text-zinc-400 tracking-tighter">{stats.rejected}</div>
              </div>
              <div>
                <div className="text-sm uppercase tracking-wider text-zinc-400 font-bold mb-1">Hit Rate</div>
                <div className="text-4xl font-mono text-zinc-300 tracking-tighter">{stats.successRate}%</div>
              </div>
            </div>
          </div>

          {/* Toggle Controls */}
          <div className="flex items-center gap-8 mb-8 border-b border-zinc-800/60">
            <button
              onClick={() => setActiveTab('targets')}
              className={cn(
                "pb-4 text-xl font-bold tracking-wide uppercase transition-all relative",
                activeTab === 'targets' ? "text-[#00ff88]" : "text-zinc-500 hover:text-zinc-300"
              )}
            >
              Targets ({results.length})
              {activeTab === 'targets' && (
                <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-[#00ff88] shadow-[0_0_15px_rgba(0,255,136,0.6)]" />
              )}
            </button>

            <button
              onClick={() => setActiveTab('rejected')}
              className={cn(
                "pb-4 text-xl font-bold tracking-wide uppercase transition-all relative",
                activeTab === 'rejected' ? "text-amber-400" : "text-zinc-500 hover:text-zinc-300"
              )}
            >
              Rejected ({rejections.length})
              {activeTab === 'rejected' && (
                <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-amber-400 shadow-[0_0_15px_rgba(250,204,21,0.6)]" />
              )}
            </button>
          </div>

          {/* List Content */}
          <div className="space-y-1 min-h-[400px]">
            {isLoading ? (
              // Simple loading skeleton
              <div className="space-y-3 animate-pulse">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-20 w-full bg-zinc-900/50 rounded-lg border border-zinc-800/50" />
                ))}
              </div>
            ) : (
              <>
                {activeTab === 'targets' && (
                  results.length > 0 ? (
                    results.map(result => (
                      <div key={result.id} className={cn("transition-all duration-300", selectedResult?.id === result.id ? "opacity-100 scale-[1.01]" : "opacity-100")}>
                        <ResultCard
                          result={result}
                          onClick={(id) => handleResultClick(id)}
                        />
                      </div>
                    ))
                  ) : (
                    <div className="flex flex-col items-center justify-center py-20 text-zinc-500">
                      <Target size={32} className="mb-2 opacity-50" />
                      <p className="font-mono text-sm">No valid targets found.</p>
                    </div>
                  )
                )}

                {activeTab === 'rejected' && (
                  rejections.length > 0 ? (
                    rejections.map((rejection, idx) => (
                      <RejectionCard
                        key={`${rejection.symbol}-${idx}`}
                        rejection={rejection}
                      />
                    ))
                  ) : (
                    <div className="flex flex-col items-center justify-center py-20 text-zinc-500">
                      <WarningCircle size={32} className="mb-2 opacity-50" />
                      <p className="font-mono text-sm">No rejections recorded.</p>
                    </div>
                  )
                )}
              </>
            )}
          </div>

          {/* INTEL DOSSIER (Detail View) */}
          <div ref={dossierRef}>
            {selectedResult && (
              <IntelDossier
                result={selectedResult}
                onClose={() => {
                  setSelectedResult(null);
                  window.scrollTo({ top: 0, behavior: 'smooth' });
                }}
              />
            )}
          </div>

        </div>
      </main>
    </div>
  );
}

export default ScanResults;
