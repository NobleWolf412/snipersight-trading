import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type { ScanResult } from '@/utils/mockData';
import { IntelDeck } from './IntelDeck';
import { ChartAnalysis } from './ChartAnalysis';
// import { TradingViewChart } from './TradingViewChart'; // Assuming this exists or using placeholder

interface ChartModalProps {
  isOpen: boolean;
  onClose: () => void;
  result: ScanResult;
}

export function ChartModal({ isOpen, onClose, result }: ChartModalProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-[95vw] w-full lg:max-w-[1400px] h-[90vh] p-0 gap-0 overflow-hidden flex flex-col lg:flex-row bg-background">

        {/* HEADER (Screen Reader Only - we use custom toolbar) */}
        <div className="sr-only">
          <DialogHeader>
            <DialogTitle>{result.pair} Analysis</DialogTitle>
            <DialogDescription>Interactive Command Center</DialogDescription>
          </DialogHeader>
        </div>

        {/* LEFT PANE: CHART & MAIN VISUALS (70-75%) */}
        <div className="flex-1 flex flex-col h-full min-h-[50vh] lg:min-h-0 border-r border-border/40 relative bg-background">
          {/* Custom Toolbar / Header */}
          <div className="h-14 border-b border-border/40 flex items-center justify-between px-4 bg-muted/5 shrink-0">
            <div className="flex items-center gap-3">
              <span className="text-xl font-bold font-mono tracking-tight">{result.pair}</span>
              <Badge variant="outline" className={result.trendBias === 'BULLISH' ? 'bg-success/10 text-success border-success/30' : result.trendBias === 'BEARISH' ? 'bg-destructive/10 text-destructive border-destructive/30' : 'bg-muted text-muted-foreground'}>
                {result.trendBias}
              </Badge>
              <Badge variant="secondary" className="font-mono text-xs">
                {result.classification}
              </Badge>
            </div>
          </div>

          {/* CHART AREA */}
          <div className="flex-1 bg-black/5 dark:bg-black/20 w-full h-full relative group overflow-hidden">

            <Tabs defaultValue="chart" className="w-full h-full flex flex-col">
              <div className="absolute top-3 right-4 z-10 w-auto">
                <TabsList className="grid w-[200px] grid-cols-2 h-8 bg-background/80 backdrop-blur border border-border/40">
                  <TabsTrigger value="chart" className="text-xs h-6">Chart</TabsTrigger>
                  <TabsTrigger value="report" className="text-xs h-6">Full Report</TabsTrigger>
                </TabsList>
              </div>

              <TabsContent value="chart" className="flex-1 h-full m-0 p-0 outline-none relative">
                {/* Placeholder for TradingView Chart - In production this would be the actual Chart component */}
                <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground/30 pointer-events-none">
                  <svg className="w-24 h-24 mb-4 opacity-20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
                  </svg>
                  <span className="text-sm uppercase tracking-widest font-semibold opacity-50">TradingView Chart Integration</span>
                </div>
                {/* <TradingViewChart result={result} /> */}
              </TabsContent>

              <TabsContent value="report" className="flex-1 h-full m-0 p-0 bg-background overflow-y-auto">
                <div className="p-8 max-w-4xl mx-auto">
                  <ChartAnalysis result={result} />
                </div>
              </TabsContent>
            </Tabs>
          </div>
        </div>

        {/* RIGHT PANE: INTEL DECK (25-30%) */}
        <div className="w-full lg:w-[380px] h-[40vh] lg:h-full flex-shrink-0 bg-card z-10 shadow-[-5px_0_20px_rgba(0,0,0,0.1)] border-t lg:border-t-0 border-border/40">
          <IntelDeck result={result} />
        </div>

      </DialogContent>
    </Dialog>
  );
}
