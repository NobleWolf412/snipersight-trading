import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { Terminal, Lightning } from '@phosphor-icons/react';

interface ScannerConsoleProps {
  isScanning: boolean;
  className?: string;
}

export function ScannerConsole({ isScanning, className }: ScannerConsoleProps) {
  const [logs, setLogs] = useState<Array<{ timestamp: string; message: string; type: 'info' | 'success' | 'warning' | 'error' }>>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isScanning) {
      setLogs([{ 
        timestamp: new Date().toLocaleTimeString(), 
        message: '> Initializing scanner systems...', 
        type: 'info' 
      }]);

      const timeouts: NodeJS.Timeout[] = [];

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
          message: '> Loading exchange connection...', 
          type: 'info' 
        }]);
      }, 300));

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
          message: '✓ Exchange connection established', 
          type: 'success' 
        }]);
      }, 800));

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
          message: '> Fetching market data...', 
          type: 'info' 
        }]);
      }, 1200));

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
          message: '✓ Market data loaded', 
          type: 'success' 
        }]);
      }, 1800));

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
          message: '> Analyzing symbols across timeframes...', 
          type: 'info' 
        }]);
      }, 2200));

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
          message: '> Processing technical indicators...', 
          type: 'info' 
        }]);
      }, 3000));

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
          message: '> Detecting Smart Money Concepts...', 
          type: 'info' 
        }]);
      }, 4200));

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
          message: '> Scanning for Order Blocks...', 
          type: 'info' 
        }]);
      }, 5500));

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
          message: '> Identifying Fair Value Gaps...', 
          type: 'info' 
        }]);
      }, 6800));

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
          message: '> Validating Break of Structure patterns...', 
          type: 'info' 
        }]);
      }, 8100));

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
          message: '⚠ High-volatility symbols detected', 
          type: 'warning' 
        }]);
      }, 9500));

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
          message: '> Computing confluence scores...', 
          type: 'info' 
        }]);
      }, 10800));

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
          message: '> Filtering signals by minimum score threshold...', 
          type: 'info' 
        }]);
      }, 12000));

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
          message: '✓ Scan analysis complete', 
          type: 'success' 
        }]);
      }, 13500));

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
          message: '> Generating results...', 
          type: 'info' 
        }]);
      }, 14200));

      return () => {
        timeouts.forEach(clearTimeout);
      };
    }
  }, [isScanning]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className={cn("flex flex-col h-full", className)}>
      <div className="flex items-center gap-2 pb-3 border-b border-border/60">
        <Terminal size={18} className="text-primary" weight="bold" />
        <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
          Scanner Console
        </span>
        {isScanning && (
          <Lightning size={14} className="text-primary animate-pulse ml-auto" weight="fill" />
        )}
      </div>

      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto mt-3 space-y-1 font-mono text-xs bg-background/20 rounded-md p-3 border border-border/40"
        style={{ maxHeight: '400px' }}
      >
        {logs.length === 0 ? (
          <div className="text-muted-foreground/60 italic">
            Awaiting scan initialization...
          </div>
        ) : (
          logs.map((log, idx) => (
            <div 
              key={idx} 
              className={cn(
                "flex gap-2 leading-relaxed",
                log.type === 'success' && "text-success",
                log.type === 'warning' && "text-warning",
                log.type === 'error' && "text-destructive",
                log.type === 'info' && "text-foreground/80"
              )}
            >
              <span className="text-muted-foreground/60 shrink-0">[{log.timestamp}]</span>
              <span className="break-all">{log.message}</span>
            </div>
          ))
        )}
      </div>

      {!isScanning && logs.length === 0 && (
        <div className="mt-3 text-xs text-muted-foreground/60 text-center italic">
          Console will display scan progress when scanner is armed
        </div>
      )}
    </div>
  );
}
