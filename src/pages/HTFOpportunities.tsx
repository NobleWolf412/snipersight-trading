import { useScanner } from '@/context/ScannerContext';
import { HTFOpportunityCard } from '@/components/htf/HTFOpportunityCard';
import { Link } from 'react-router-dom';
import { ArrowLeft } from '@phosphor-icons/react';

export function HTFOpportunities() {
  const { htfOpportunities, refreshHTFOpportunities } = useScanner();
  return (
    <div className="min-h-screen pt-6 pb-16 px-4 sm:px-6 md:px-10 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="space-y-1">
          <h1 className="text-xl md:text-2xl font-bold tracking-wide flex items-center gap-3">
            High Timeframe Opportunities
            <span className="text-xs font-mono px-2 py-1 rounded bg-accent/10 text-accent border border-accent/30">
              {htfOpportunities.length} ACTIVE
            </span>
          </h1>
          <p className="text-xs text-muted-foreground max-w-xl">
            Structured setups approaching major support/resistance levels. Validate SMC context and risk parameters before committing. Refresh to pull latest tactical scan window.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => refreshHTFOpportunities()}
            className="px-3 py-2 rounded-md text-xs font-semibold bg-accent/15 hover:bg-accent/25 text-accent border border-accent/30 transition-colors"
          >
            Refresh
          </button>
          <Link to="/" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
            <ArrowLeft size={14} /> Home
          </Link>
        </div>
      </div>
      <div className="grid md:grid-cols-2 gap-6">
        {htfOpportunities.map((opp, i) => (
          <HTFOpportunityCard key={i} opp={opp as any} />
        ))}
      </div>

      {htfOpportunities.length === 0 && (
        <div className="mt-8 rounded-xl border border-border/50 bg-card/30 backdrop-blur-sm p-8 space-y-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-accent/10 border border-accent/30 flex items-center justify-center">
              <span className="text-accent text-xl">📡</span>
            </div>
            <div>
              <h3 className="font-semibold text-foreground">HTF Level Monitoring Active</h3>
              <p className="text-xs text-muted-foreground">Scanning 4H, 1D, and 1W timeframes for tactical opportunities</p>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="rounded-lg border border-border/40 bg-background/50 p-4 text-center">
              <div className="text-lg font-bold text-purple-400">FIB</div>
              <div className="text-[10px] text-muted-foreground">Retracement Levels</div>
              <div className="text-[9px] text-muted-foreground/60 mt-1">23.6%, 38.2%, 50%, 61.8%, 78.6%</div>
            </div>
            <div className="rounded-lg border border-border/40 bg-background/50 p-4 text-center">
              <div className="text-lg font-bold text-green-400">S</div>
              <div className="text-[10px] text-muted-foreground">Support Levels</div>
              <div className="text-[9px] text-muted-foreground/60 mt-1">Historical lows, demand zones</div>
            </div>
            <div className="rounded-lg border border-border/40 bg-background/50 p-4 text-center">
              <div className="text-lg font-bold text-red-400">R</div>
              <div className="text-[10px] text-muted-foreground">Resistance Levels</div>
              <div className="text-[9px] text-muted-foreground/60 mt-1">Historical highs, supply zones</div>
            </div>
            <div className="rounded-lg border border-border/40 bg-background/50 p-4 text-center">
              <div className="text-lg font-bold text-amber-400">⭐</div>
              <div className="text-[10px] text-muted-foreground">Golden Ratios</div>
              <div className="text-[9px] text-muted-foreground/60 mt-1">38.2% & 61.8% high-prob zones</div>
            </div>
          </div>

          <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
            <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
            Waiting for price to approach key levels...
          </div>
        </div>
      )}
    </div>
  );
}
