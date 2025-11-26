import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';

interface ScannerConsoleProps {
  className?: string;
  isScanning: boolean;
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
          message: '> Loading market data feeds...', 
          type: 'info' 
        }]);
      }, 1500));

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
          message: '> Processing technical indicators...', 
          type: 'info' 
        }]);
      }, 3200));

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
          message: '> Scanning for Order Blocks...', 
          type: 'info' 
        }]);
      }, 5100));

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
          message: '> Analyzing Fair Value Gaps...', 
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
    <div className={cn("flex flex-col border border-border rounded-md bg-card overflow-hidden", className)}>
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-muted/30">
        <Terminal size={18} className="text-primary" />
        <span className="font-mono text-sm font-medium text-foreground">Scanner Console</span>
        {isScanning && (
          <Lightning size={16} className="text-warning animate-pulse ml-auto" />
        )}
      </div>
      
      <div 
        ref={scrollRef}
        className="flex-1 p-4 font-mono text-xs space-y-1 overflow-y-auto max-h-64 bg-card/50"
      >
        {logs.length > 0 ? (
          logs.map((log, i) => (
            <div key={i} className="flex gap-2">
              <span className="text-muted-foreground shrink-0">[{log.timestamp}]</span>
              <span className={cn(
                "flex-1",
                log.type === 'success' && "text-success",
                log.type === 'warning' && "text-warning",
}               log.type === 'error' && "text-destructive",
                log.type === 'info' && "text-foreground"
              )}>
                {log.message}
              </span>
            </div>
          ))
        ) : (
          <div className="text-muted-foreground italic">
            Awaiting scan initialization...
          </div>
        )}
      </div>
    </div>
  );
}
