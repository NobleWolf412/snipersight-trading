import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { Terminal, Lightning, WifiHigh, WifiSlash } from '@phosphor-icons/react';
import { useScanner } from '@/context/ScannerContext';
import { debugLogger, DebugLogEntry } from '@/utils/debugLogger';

interface ScannerConsoleProps { className?: string; isScanning: boolean; }

export function ScannerConsole({ isScanning, className }: ScannerConsoleProps) {
  const { consoleLogs, scanConfig } = useScanner();
  const scrollRef = useRef<HTMLDivElement>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [apiLogs, setApiLogs] = useState<DebugLogEntry[]>([]);

  // Subscribe to debug logger for real API activity
  useEffect(() => {
    const unsubscribe = debugLogger.subscribe((entry) => {
      setApiLogs(prev => [...prev.slice(-100), entry]); // Keep last 100 logs
    });
    
    // Load existing logs on mount
    setApiLogs(debugLogger.getLogs());
    
    return () => unsubscribe();
  }, []);

  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setElapsedMs(0);

    if (isScanning) {
      startTimeRef.current = Date.now();
      // Timer tick every 1s
      intervalRef.current = setInterval(() => {
        if (startTimeRef.current) {
          setElapsedMs(Date.now() - startTimeRef.current);
        }
      }, 1000);

      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        startTimeRef.current = null;
      };
    }
  }, [isScanning]);

  const formatElapsed = (ms: number) => {
    const totalSeconds = Math.floor(ms / 1000);
    const m = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
    const s = (totalSeconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  // Merge config logs with API logs, sorted by timestamp
  const mergedLogs = [...consoleLogs, ...apiLogs].sort((a, b) => a.timestamp - b.timestamp);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [mergedLogs.length]);

  // Check if we have recent API activity
  const lastApiLog = apiLogs[apiLogs.length - 1];
  const hasRecentApiActivity = lastApiLog && (Date.now() - lastApiLog.timestamp) < 10000;

  return (
    <div className={cn("flex flex-col h-full hud-console overflow-hidden rounded-lg relative z-0", className)}>
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-600 bg-slate-900/80">
        <Terminal size={18} className="text-primary hud-text-green" aria-hidden="true" focusable="false" />
        <span className="font-mono text-sm font-medium hud-terminal text-primary">SCANNER CONSOLE</span>
        <div className="ml-auto flex items-center gap-3">
          {/* API Status Indicator */}
          <div className="flex items-center gap-1.5" title={hasRecentApiActivity ? 'API Connected' : 'No recent API activity'}>
            {hasRecentApiActivity ? (
              <WifiHigh size={14} className="text-success" />
            ) : (
              <WifiSlash size={14} className="text-muted-foreground" />
            )}
            <span className="text-xxs font-mono text-muted-foreground">
              {hasRecentApiActivity ? 'LIVE' : 'IDLE'}
            </span>
          </div>
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
        {mergedLogs.length > 0 ? (
          mergedLogs.map((log, i) => (
            <div key={`${log.timestamp}-${i}`} className="flex gap-2">
              <span className="text-muted-foreground shrink-0">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
              {/* Source badge for API logs */}
              {'source' in log && log.source === 'api' && (
                <span className="text-cyan-400 shrink-0">[API]</span>
              )}
              <span className={cn(
                "flex-1",
                log.type === 'success' && "text-success",
                log.type === 'warning' && "text-warning",
                log.type === 'error' && "text-destructive",
                log.type === 'api' && "text-cyan-400",
                (log.type === 'info' || !log.type) && "text-foreground",
                log.type === 'config' && "text-muted-foreground"
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
      
      {/* Clear logs button */}
      <div className="px-4 py-2 border-t border-slate-700 bg-slate-900/60 flex justify-between items-center">
        <span className="text-xxs text-muted-foreground">{mergedLogs.length} log entries</span>
        <button
          onClick={() => {
            debugLogger.clear();
            setApiLogs([]);
          }}
          className="text-xxs text-muted-foreground hover:text-foreground transition-colors"
        >
          Clear
        </button>
      </div>
    </div>
  );
}
