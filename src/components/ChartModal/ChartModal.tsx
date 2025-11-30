import { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { TradingViewChart } from './TradingViewChart';
import { ChartAnalysis } from './ChartAnalysis';
import { TradingStats } from './TradingStats';
import type { ScanResult } from '@/utils/mockData';

interface ChartModalProps {
  isOpen: boolean;
  onClose: () => void;
  result: ScanResult;
}

export function ChartModal({ isOpen, onClose, result }: ChartModalProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      {/* Responsive: use viewport width on mobile; keep content simple */}
      <DialogContent className="w-[95vw] sm:max-w-5xl max-h-[95vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            <span>{result.pair}</span>
            <Badge variant="outline" className="bg-accent/20 text-accent border-accent/50">
              {result.trendBias}
            </Badge>
          </DialogTitle>
          <DialogDescription>Interactive chart analysis with technical levels and AI insights</DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="chart" className="w-full">
          <TabsList className="grid w-full grid-cols-4 mb-4">
            <TabsTrigger value="chart">Chart View</TabsTrigger>
            <TabsTrigger value="analysis">AI Analysis</TabsTrigger>
            <TabsTrigger value="stats">Trading Stats</TabsTrigger>
            <TabsTrigger value="levels">Level Details</TabsTrigger>
          </TabsList>

          <TabsContent value="chart" className={"space-y-4"}>
            {/* Simple fixed-height container; TradingView fills it without stretching */}
            <div className="w-full h-[60vh]">
              <TradingViewChart result={result} />
            </div>
          </TabsContent>

          <TabsContent value="analysis" className="space-y-4">
            <ChartAnalysis result={result} />
          </TabsContent>

          <TabsContent value="stats" className="space-y-4">
            <TradingStats result={result} />
          </TabsContent>

          <TabsContent value="levels" className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <h4 className="font-bold text-sm text-foreground">ENTRY ZONE</h4>
                <div className="bg-success/10 border border-success/50 rounded p-3 space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">High:</span>
                    <span className="font-mono text-success">${result.entryZone.high.toFixed(5)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Low:</span>
                    <span className="font-mono text-success">${result.entryZone.low.toFixed(5)}</span>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <h4 className="font-bold text-sm text-foreground">STOP LOSS</h4>
                <div className="bg-destructive/10 border border-destructive/50 rounded p-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Level:</span>
                    <span className="font-mono text-destructive">${result.stopLoss.toFixed(5)}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <h4 className="font-bold text-sm text-foreground">TAKE PROFIT TARGETS</h4>
              <div className="grid grid-cols-3 gap-2">
                {result.takeProfits.map((tp, i) => (
                  <div key={i} className="bg-accent/10 border border-accent/50 rounded p-3">
                    <div className="text-xs text-muted-foreground mb-1">TP{i + 1}</div>
                    <div className="font-mono text-accent font-bold">${tp.toFixed(5)}</div>
                  </div>
                ))}
              </div>
            </div>

            <Separator />

            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <h4 className="font-bold text-sm text-foreground">ORDER BLOCKS</h4>
                <div className="space-y-2">
                  {result.orderBlocks.map((ob, i) => (
                    <div key={i} className="bg-card border border-border rounded p-2 text-xs">
                      <div className="flex justify-between">
                        <Badge variant="outline" className="text-xs">
                          {ob.type.toUpperCase()}
                        </Badge>
                        <span className="text-muted-foreground">{ob.timeframe}</span>
                      </div>
                      <div className="font-mono mt-1">${ob.price.toFixed(5)}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <h4 className="font-bold text-sm text-foreground">FAIR VALUE GAPS</h4>
                <div className="space-y-2">
                  {result.fairValueGaps.map((fvg, i) => (
                    <div key={i} className="bg-card border border-border rounded p-2 text-xs">
                      <Badge variant="outline" className="text-xs mb-2">
                        {fvg.type.toUpperCase()}
                      </Badge>
                      <div className="space-y-1">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">High:</span>
                          <span className="font-mono">${fvg.high.toFixed(5)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Low:</span>
                          <span className="font-mono">${fvg.low.toFixed(5)}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
