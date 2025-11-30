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
        {htfOpportunities.length === 0 && (
          <div className="text-xs text-muted-foreground italic">No opportunities detected. Try again shortly.</div>
        )}
      </div>
    </div>
  );
}
