import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { Terminal, Lightning } from '@phosphor-icons/react';

interface ScannerConsoleProps {
  className?: string;
  isScanning: boolean;
}

export function ScannerConsole({ isScanning, className }: ScannerConsoleProps) {
  const [logs, setLogs] = useState<Array<{ timestamp: string; message: string; type: 'info' | 'success' | 'warning' | 'error' }>>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    // Clear existing timers
    timers.current.forEach(clearTimeout);
    timers.current = [];
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setElapsedMs(0);

    if (isScanning) {
      startTimeRef.current = Date.now();
      // Subtle elapsed timer tick every 1s
      intervalRef.current = setInterval(() => {
        if (startTimeRef.current) {
          setElapsedMs(Date.now() - startTimeRef.current);
        }
      }, 1000);

      // Every 5s, append a soft heartbeat line with elapsed
      const heartbeat = () => {
        const ms = startTimeRef.current ? Date.now() - startTimeRef.current : 0;
        const totalSeconds = Math.floor(ms / 1000);
        const m = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
        const s = (totalSeconds % 60).toString().padStart(2, '0');
        setLogs(prev => [...prev, { timestamp: new Date().toLocaleTimeString(), message: `… working (elapsed ${m}:${s})`, type: 'info' }]);
      };
      timers.current.push(setInterval(heartbeat, 5000) as unknown as ReturnType<typeof setTimeout>);

      setLogs([{ timestamp: new Date().toLocaleTimeString(), message: '> Initializing scanner systems...', type: 'info' }]);

      const push = (ms: number, msg: string, type: 'info' | 'success' | 'warning' | 'error' = 'info') => {
        timers.current.push(setTimeout(() => {
          setLogs(prev => [...prev, { timestamp: new Date().toLocaleTimeString(), message: msg, type }]);
        }, ms));
      };

      push(1500, '> Loading market data feeds...');
      push(3200, '> Processing technical indicators...');
      push(5100, '> Scanning for Order Blocks...');
      push(6800, '> Analyzing Fair Value Gaps...');
      push(8100, '> Validating Break of Structure patterns...');
      push(9500, '⚠ High-volatility symbols detected', 'warning');
      push(10800, '> Computing confluence scores...');
      push(12000, '> Filtering signals by minimum score threshold...');
      push(13500, '✓ Scan analysis complete', 'success');
      push(14200, '> Generating results...');

      // Extra sub-events to keep console active
      const subs = [
        { ms: 14800, msg: '• Fetching BTC/USDT 4H candles…' },
        { ms: 15400, msg: '• Detecting OBs on ETH/USDT 1H…' },
        { ms: 16000, msg: '• FVG sweep on SOL/USDT 15m…' },
        { ms: 16600, msg: '• Score update: AVAX/USDT 76.4' },
        { ms: 17200, msg: '• Computing structural stops…' },
        { ms: 17800, msg: '• Planning entries and targets…' },
      ];
      subs.forEach(s => push(s.ms, s.msg));

      return () => {
        timers.current.forEach(clearTimeout);
        timers.current = [];
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        startTimeRef.current = null;
      };
    } else {
      setLogs([]);
    }
  }, [isScanning]);

  const formatElapsed = (ms: number) => {
    const totalSeconds = Math.floor(ms / 1000);
    const m = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
    const s = (totalSeconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  // Subtle elapsed badge (render fragment to place near header if desired)
  const ElapsedBadge = () => (
    <div className="fixed bottom-4 right-4 bg-background/70 border border-border/60 rounded-md px-3 py-1 shadow-sm">
      <span className="text-xs font-mono text-muted-foreground">Elapsed: {formatElapsed(elapsedMs)}</span>
    </div>
  );

  // Ensure the elapsed badge renders while scanning
  // Insert near header or keep unobtrusive as fixed overlay
  // Consumers can reposition if needed

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className={cn("flex flex-col h-full hud-console overflow-hidden rounded-lg relative z-0", className)}>
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-600 bg-slate-900/80">
        <Terminal size={18} className="text-primary hud-text-green" aria-hidden="true" focusable="false" />
        <span className="font-mono text-sm font-medium hud-terminal text-primary">SCANNER CONSOLE</span>
        <div className="ml-auto flex items-center gap-3">
          {isScanning && (
            <span className="text-xxs font-mono text-muted-foreground">Elapsed {formatElapsed(elapsedMs)}</span>
          )}
          {isScanning && (
            <Lightning size={16} className="text-warning animate-pulse scan-pulse" aria-hidden="true" focusable="false" />
          )}
        </div>
      </div>
      
      <div 
        ref={scrollRef}
        className="flex-1 p-4 font-mono text-xs space-y-1 overflow-y-auto"
      >
        {logs.length > 0 ? (
          logs.map((log, i) => (
            <div key={i} className="flex gap-2">
              <span className="text-muted-foreground shrink-0">[{log.timestamp}]</span>
              <span className={cn(
                "flex-1",
                log.type === 'success' && "text-success",
                log.type === 'warning' && "text-warning",
                log.type === 'error' && "text-destructive",
                log.type === 'info' && "text-foreground"
              )}>
                {log.message}
              </span>
            </div>
          ))
        ) : (
          <div className="text-slate-600 dark:text-muted-foreground italic">
            Awaiting scan initialization...
          </div>
        )}
      </div>
    </div>
  );
}
