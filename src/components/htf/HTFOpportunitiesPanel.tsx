import { useState } from 'react';
import { useScanner } from '@/context/ScannerContext';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { HTFOpportunityCard } from './HTFOpportunityCard';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Crosshair, Lightning } from '@phosphor-icons/react';

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}

export function HTFOpportunitiesPanel({ open, onOpenChange }: Props) {
  const { htfOpportunities, setSelectedMode, scannerModes, addConsoleLog } = useScanner();
  const [switching, setSwitching] = useState<string | null>(null);

  function handleSwitchMode(modeName: string) {
    setSwitching(modeName);
    const match = scannerModes.find(m => m.name === modeName);
    if (match) {
      setSelectedMode(match);
      addConsoleLog(`Switched tactical mode to ${match.name}`, 'config');
    } else {
      addConsoleLog(`Unable to switch mode: '${modeName}' not found`, 'warning');
    }
    // TODO: emit telemetry event to backend when implemented
    setTimeout(() => setSwitching(null), 650);
  }

  function handleViewChart(symbol: string) {
    // Could integrate with existing chart modal trigger mechanism
    // For now, dispatch a custom event consumed by ChartModal parent
    window.dispatchEvent(new CustomEvent('open-chart', { detail: { symbol } }));
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>      
      <DialogContent className="max-w-2xl p-0 overflow-hidden">
        <DialogHeader className="px-6 pt-5 pb-2 border-b">
          <DialogTitle className="flex items-center gap-2 text-sm tracking-wide font-semibold">
            <Lightning size={18} className="text-yellow-400" /> High Timeframe Tactical Opportunities
          </DialogTitle>
          <DialogDescription asChild>
            <p className="text-xs text-muted-foreground mt-1 px-1">
              Levels approaching inflection zones. Consider recommended tactical mode for optimal risk structuring.
            </p>
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="h-[480px] px-6 py-5 space-y-4">
          {htfOpportunities.length === 0 && (
            <div className="text-xs text-muted-foreground italic">No high timeframe tactical opportunities detected in the last scan window.</div>
          )}
          {htfOpportunities.map((opp, idx) => (
            <HTFOpportunityCard
              key={idx}
              opp={opp as any}
              onSwitchMode={handleSwitchMode}
              onViewChart={handleViewChart}
            />
          ))}
        </ScrollArea>
        <div className="px-6 pb-4 pt-2 border-t flex items-center justify-between">
          <div className="text-[11px] text-muted-foreground flex items-center gap-1">
            <Crosshair size={12} /> Recommended mode switches are heuristic suggestions; validate structure before committing.
          </div>
          {switching && (
            <div className="text-[11px] font-mono text-accent animate-pulse">Switching to {switching.toUpperCase()}...</div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
