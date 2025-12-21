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
            <div className="rounded-lg border border-border/40 bg-background/30 p-6 space-y-4">
              <div className="flex items-center gap-3">
                <span className="text-2xl">📡</span>
                <div>
                  <h4 className="font-semibold text-sm">Monitoring HTF Levels</h4>
                  <p className="text-[10px] text-muted-foreground">Scanning 4H, 1D, 1W charts for tactical setups</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 text-center">
                <div className="rounded border border-purple-500/30 bg-purple-500/5 p-2">
                  <div className="text-xs font-bold text-purple-400">FIB</div>
                  <div className="text-[9px] text-muted-foreground">Retracements</div>
                </div>
                <div className="rounded border border-amber-500/30 bg-amber-500/5 p-2">
                  <div className="text-xs font-bold text-amber-400">⭐ GOLDEN</div>
                  <div className="text-[9px] text-muted-foreground">38.2% / 61.8%</div>
                </div>
                <div className="rounded border border-green-500/30 bg-green-500/5 p-2">
                  <div className="text-xs font-bold text-green-400">SUPPORT</div>
                  <div className="text-[9px] text-muted-foreground">Buy Zones</div>
                </div>
                <div className="rounded border border-red-500/30 bg-red-500/5 p-2">
                  <div className="text-xs font-bold text-red-400">RESISTANCE</div>
                  <div className="text-[9px] text-muted-foreground">Sell Zones</div>
                </div>
              </div>
              <div className="flex items-center justify-center gap-2 text-[10px] text-muted-foreground">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
                Waiting for price to approach key levels...
              </div>
            </div>
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
