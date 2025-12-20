import { useScanner } from '@/context/ScannerContext';
import { Target, WarningCircle } from '@phosphor-icons/react';
import { useState } from 'react';
import { HTFOpportunitiesPanel } from './HTFOpportunitiesPanel';
import { useNavigate } from 'react-router-dom';

export function HTFAlertBeacon() {
  const { htfOpportunities, hasHTFAlert } = useScanner();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const activeCount = htfOpportunities.length;
  const alertActive = hasHTFAlert && activeCount > 0;

  return (
    <>
      <div className="relative">
        <button
          type="button"
          aria-label={alertActive ? 'High timeframe tactical opportunities' : 'Monitoring high timeframe levels'}
          className={
            'relative w-10 h-10 flex items-center justify-center rounded-md border shadow-md transition-all group overflow-hidden ' +
            (alertActive
              ? 'border-red-500/70 bg-red-600/20 text-red-400 shadow-[0_0_12px_3px_rgba(255,0,0,0.45)] animate-pulse ring-2 ring-red-500/40'
              : 'border-border/60 bg-card/40 text-muted-foreground hover:border-accent/40 hover:text-accent')
          }
          onClick={() => navigate('/htf')}
        >
          {alertActive ? <WarningCircle size={22} weight="fill" /> : <Target size={22} />}
          <span className={
            'absolute -top-1 -right-1 min-w-[22px] h-6 px-1 rounded-full bg-background/95 border text-[10px] font-bold flex items-center justify-center font-mono transition-colors ' +
            (alertActive ? 'border-red-500/60 text-red-500' : 'border-border text-muted-foreground')
          }>
            {activeCount}
          </span>
          <span className="absolute -bottom-5 left-1/2 -translate-x-1/2 whitespace-nowrap pointer-events-none select-none text-[10px] font-medium tracking-wide text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
            {alertActive ? 'TARGETS LOCKED' : 'SCANNING...'}
          </span>
          {alertActive && (
            <span className="absolute inset-0 rounded-md pointer-events-none animate-ping bg-red-600/10" />
          )}
        </button>
        {/* Quick panel trigger */}
        <button
          type="button"
          aria-label="Quick HTF panel"
          onClick={(e) => { e.preventDefault(); setOpen(true); }}
          className={
            'absolute -top-1 -left-1 w-5 h-5 flex items-center justify-center rounded-full border text-[9px] font-bold transition-all ' +
            (alertActive
              ? 'bg-red-600/30 border-red-500/60 text-red-200 hover:bg-red-600/40'
              : 'bg-background/80 border-border text-muted-foreground hover:bg-background')
          }
          title="Open quick panel"
        >
          •
        </button>
      </div>
      {open && <HTFOpportunitiesPanel open={open} onOpenChange={setOpen} />}
    </>
  );
}
