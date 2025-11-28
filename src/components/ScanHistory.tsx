/**
 * Scan History Component
 * 
 * Displays historical scans with details and management controls
 */

import { useState, useEffect } from 'react';
import { scanHistoryService, type ScanHistoryEntry } from '@/services/scanHistoryService';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Clock,
  Crosshair,
  Target,
  XCircle,
  Trash,
  CaretDown,
  CaretUp,
  ClockCounterClockwise,
} from '@phosphor-icons/react';
import { formatDistanceToNow } from 'date-fns';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';

interface ScanHistoryProps {
  maxEntries?: number;
}

export function ScanHistory({ maxEntries = 10 }: ScanHistoryProps) {
  const [scans, setScans] = useState<ScanHistoryEntry[]>([]);
  const [expanded, setExpanded] = useState(true);
  const [selectedTimeframe, setSelectedTimeframe] = useState<'1h' | '24h' | '7d' | 'all'>('24h');

  const loadScans = () => {
    let allScans: ScanHistoryEntry[] = [];
    if (selectedTimeframe === 'all') {
      allScans = scanHistoryService.getAllScans();
    } else {
      const hours = selectedTimeframe === '1h' ? 1 : selectedTimeframe === '24h' ? 24 : 168;
      allScans = scanHistoryService.getRecentScans(hours);
    }
    setScans(allScans.slice(0, maxEntries));
  };

  useEffect(() => {
    loadScans();
    // Refresh when localStorage changes (from other tabs or new scans)
    const handleStorageChange = () => loadScans();
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [maxEntries, selectedTimeframe]);

  const handleClearScans = (timeframe: '1h' | '24h' | '7d' | 'all') => {
    let count = 0;
    if (timeframe === 'all') {
      count = scanHistoryService.clearAllScans();
    } else {
      const hours = timeframe === '1h' ? 1 : timeframe === '24h' ? 24 : 168; // 7d = 168h
      count = scanHistoryService.clearRecentScans(hours);
    }
    loadScans();
    console.log(`Cleared ${count} scans from ${timeframe}`);
  };

  const formatTimestamp = (timestamp: string) => {
    try {
      return formatDistanceToNow(new Date(timestamp), { addSuffix: true });
    } catch {
      return 'Unknown';
    }
  };

  const getModeColor = (mode: string) => {
    const colors: Record<string, string> = {
      overwatch: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
      recon: 'bg-green-500/20 text-green-400 border-green-500/30',
      strike: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
      surgical: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
      ghost: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
    };
    return colors[mode.toLowerCase()] || 'bg-accent/20 text-accent border-accent/30';
  };

  if (scans.length === 0) {
    return (
      <Card className="bg-card/30 border-slate-700/40">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-slate-200">
            <ClockCounterClockwise size={20} weight="bold" />
            Scan History
          </CardTitle>
          <CardDescription>No scans recorded yet</CardDescription>
        </CardHeader>
        <CardContent className="text-center py-8 text-slate-300">
          <Target size={48} weight="thin" className="mx-auto mb-3 opacity-30" />
          <p>Run a scan to begin tracking history</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-card/30 border-slate-700/40">
      <CardHeader
        className="cursor-pointer select-none hover:bg-accent/5 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ClockCounterClockwise size={20} weight="bold" className="text-accent" />
            <CardTitle className="text-slate-200">Scan History</CardTitle>
            <Badge variant="outline" className="border-accent/40 text-accent">
              {scans.length}
            </Badge>
          </div>
          <div className="flex items-center gap-3">
            <AlertDialog>
              <AlertDialogTrigger asChild onClick={(e) => e.stopPropagation()}>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 border-red-500/30 text-red-400 hover:bg-red-500/10 hover:border-red-500/50"
                >
                  <Trash size={14} weight="bold" className="mr-1.5" />
                  Clear History
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent className="bg-background/95 border-slate-700">
                <AlertDialogHeader>
                  <AlertDialogTitle>Clear Scan History</AlertDialogTitle>
                  <AlertDialogDescription>
                    Choose which scans to delete. This action cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <div className="grid grid-cols-2 gap-3 py-4">
                  <Button
                    variant="outline"
                    onClick={() => {
                      handleClearScans('1h');
                      setSelectedTimeframe('1h');
                    }}
                    className="h-auto py-3 flex-col gap-1 hover:border-accent/50"
                  >
                    <span className="font-semibold">All Time</span>
                    <span className="text-xs text-slate-300">
                      {scanHistoryService.getScans().length} total
                    </span>
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      handleClearScans('24h');
                      setSelectedTimeframe('24h');
                    }}
                    className="h-auto py-3 flex-col gap-1 hover:border-accent/50"
                  >
                    <span className="font-semibold">Last 24 Hours</span>
                    <span className="text-xs text-slate-300">
                      {scanHistoryService.getRecentScans(24).length} scans
                    </span>
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      handleClearScans('7d');
                      setSelectedTimeframe('7d');
                    }}
                    className="h-auto py-3 flex-col gap-1 hover:border-accent/50"
                  >
                    <span className="font-semibold">Last 7 Days</span>
                    <span className="text-xs text-slate-300">
                      {scanHistoryService.getRecentScans(168).length} scans
                    </span>
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      handleClearScans('all');
                      setSelectedTimeframe('all');
                    }}
                    className="h-auto py-3 flex-col gap-1 border-red-500/30 text-red-400 hover:bg-red-500/10 hover:border-red-500/50"
                  >
                    <span className="font-semibold">All History</span>
                    <span className="text-xs text-red-400/70">{scans.length} scans</span>
                  </Button>
                </div>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
            {expanded ? (
              <CaretUp size={20} weight="bold" className="text-slate-300" />
            ) : (
              <CaretDown size={20} weight="bold" className="text-slate-300" />
            )}
          </div>
        </div>
        <CardDescription>Recent scan results and metrics</CardDescription>
      </CardHeader>

      {expanded && (
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2 items-center justify-between">
            <div className="flex gap-2">
              {(['1h','24h','7d','all'] as const).map(tf => (
                <Button
                  key={tf}
                  variant={selectedTimeframe === tf ? 'default' : 'outline'}
                  size="sm"
                  className={selectedTimeframe === tf ? 'bg-accent text-foreground' : ''}
                  onClick={() => setSelectedTimeframe(tf)}
                >
                  {tf.toUpperCase()}
                </Button>
              ))}
            </div>
            <TimeframeStats timeframe={selectedTimeframe} />
          </div>
          <div className="space-y-3">
          {scans.map((scan) => {
            const total = scan.signalsGenerated + scan.signalsRejected;
            const successRate = total > 0 ? (scan.signalsGenerated / total) * 100 : 0;

            return (
              <div
                key={scan.id}
                className="rounded-lg border border-slate-700/50 bg-black/20 p-4 hover:border-accent/30 transition-all"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Badge className={getModeColor(scan.mode)}>
                      {scan.mode.toUpperCase()}
                    </Badge>
                    <span className="text-xs text-slate-300">
                      <Clock size={12} weight="bold" className="inline mr-1" />
                      {formatTimestamp(scan.timestamp)}
                    </span>
                  </div>
                  <Badge
                    variant={successRate >= 50 ? 'default' : 'secondary'}
                    className={
                      successRate >= 50
                        ? 'bg-green-500/20 text-green-400 border-green-500/30'
                        : 'bg-orange-500/20 text-orange-400 border-orange-500/30'
                    }
                  >
                    {successRate.toFixed(0)}% Success
                  </Badge>
                </div>

                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <div className="text-xs text-slate-300 mb-1">Scanned</div>
                    <div className="text-lg font-mono text-slate-200">
                      <Crosshair size={14} weight="bold" className="inline mr-1 text-accent" />
                      {scan.symbolsScanned}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-300 mb-1">Signals</div>
                    <div className="text-lg font-mono text-green-400">
                      <Target size={14} weight="bold" className="inline mr-1" />
                      {scan.signalsGenerated}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-300 mb-1">Rejected</div>
                    <div className="text-lg font-mono text-orange-400">
                      <XCircle size={14} weight="bold" className="inline mr-1" />
                      {scan.signalsRejected}
                    </div>
                  </div>
                </div>

                {scan.timeframes && scan.timeframes.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-700/30">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs text-slate-300">Timeframes:</span>
                      {scan.timeframes.map((tf) => (
                        <Badge
                          key={tf}
                          variant="outline"
                          className="text-xs border-slate-600/50 text-slate-300"
                        >
                          {tf}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
          </div>
        </CardContent>
      )}
    </Card>
  );
}

function TimeframeStats({ timeframe }: { timeframe: '1h' | '24h' | '7d' | 'all' }) {
  const hours = timeframe === '1h' ? 1 : timeframe === '24h' ? 24 : timeframe === '7d' ? 168 : undefined;
  const stats = scanHistoryService.getStatistics(hours);
  if (stats.totalScans === 0) {
    return <div className="text-xs text-slate-500">No scans in range</div>;
  }
  return (
    <div className="flex gap-4 text-xs font-mono text-slate-300">
      <div className="flex items-center gap-1"><span className="text-slate-500">Scans:</span>{stats.totalScans}</div>
      <div className="flex items-center gap-1"><span className="text-slate-500">Signals:</span>{stats.totalSignals}</div>
      <div className="flex items-center gap-1"><span className="text-slate-500">Avg/Scan:</span>{stats.avgSignalsPerScan}</div>
      <div className="flex items-center gap-1"><span className="text-slate-500">Success%:</span>{stats.avgSuccessRate}%</div>
    </div>
  );
}
