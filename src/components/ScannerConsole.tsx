import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { Terminal, Lightning } from '@phosphor-icons/react';
import { useScanner } from '@/context/ScannerContext';
import { debugLogger, DebugLogEntry } from '@/utils/debugLogger';

interface ScannerConsoleProps { className?: string; isScanning: boolean; }

export function ScannerConsole({ isScanning, className }: ScannerConsoleProps) {
  const { consoleLogs } = useScanner();
  const scrollRef = useRef<HTMLDivElement>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [scanLogs, setScanLogs] = useState<DebugLogEntry[]>([]);
  const wasScanning = useRef(false);

  // Subscribe to debug logger ONLY when scanning starts
  // Filter to only scanner-related logs
  useEffect(() => {
    if (isScanning && !wasScanning.current) {
      // Scan just started - clear previous logs and start fresh
      setScanLogs([]);
      wasScanning.current = true;
    }
    
    if (!isScanning && wasScanning.current) {
      // Scan just ended
      wasScanning.current = false;
    }

    // Only subscribe while scanning
    if (isScanning) {
      const unsubscribe = debugLogger.subscribe((entry) => {
        // Only capture scanner-related logs (source = 'scanner' or 'api')
        if (entry.source === 'scanner' || entry.source === 'api') {
          setScanLogs(prev => [...prev, entry]);
        }
      });
      
      return () => unsubscribe();
    }
  }, [isScanning]);

  // Elapsed timer
  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setElapsedMs(0);

    if (isScanning) {
      startTimeRef.current = Date.now();
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

  // Merge config logs (from context) with scan logs, sorted by timestamp
  const mergedLogs = [...consoleLogs, ...scanLogs].sort((a, b) => a.timestamp - b.timestamp);

  // Auto-scroll to bottom when new logs appear
  useEffect(() => {
    if (scrollRef.current && mergedLogs.length > 0) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [mergedLogs.length]);

  return (
    <div className={cn("flex flex-col hud-console overflow-hidden rounded-lg relative z-0", className)} style={{ maxHeight: '300px' }}>
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-600 bg-slate-900/80">
        <Terminal size={18} className="text-primary hud-text-green" aria-hidden="true" focusable="false" />
        <span className="font-mono text-sm font-medium hud-terminal text-primary">SCANNER CONSOLE</span>
        <div className="ml-auto flex items-center gap-3">
          {isScanning && (
            <>
              <span className="text-xxs font-mono text-muted-foreground">Elapsed {formatElapsed(elapsedMs)}</span>
              <Lightning size={16} className="text-warning animate-pulse scan-pulse" aria-hidden="true" focusable="false" />
            </>
          )}
        </div>
      </div>
      
      <div 
        ref={scrollRef}
        className="flex-1 p-4 font-mono text-xs space-y-1 overflow-y-auto"
        style={{ minHeight: '150px', maxHeight: '220px' }}
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
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <Terminal size={32} className="text-muted-foreground/50 mb-3" />
            <p className="text-muted-foreground italic">Awaiting scan initialization...</p>
            <p className="text-muted-foreground/60 text-xxs mt-1">Click "Arm Scanner" to begin</p>
          </div>
        )}
      </div>
    </div>
  );
}
