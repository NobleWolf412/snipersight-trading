import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { Terminal, Lightning } from '@phosphor-icons/react';

  className?: string;
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
          type: 'info
      }]);

      const timeouts: NodeJS.Timeout[] = [];

      timeouts.push(setTimeout(() => {
        setLogs(prev => [...prev, { 
          timestamp: new Date().toLocaleTimeString(), 
        }]);

        setL
          messa


        setLogs(prev => [...prev, { 
          message: '> Processing technical indicators.
        }]);

        setL
          messa


        setLogs(prev => [...prev, { 
          message: '> Scanning for Order Blocks...', 
        }]);

        setL
          messag


        setLogs(prev => [...prev, { 
          message: '> Validating Break of Structure pa
        }]);

        setL
          messag


        setLogs(prev => [...prev, { 
          message: '> Computing confluence scores...',
        }]);

        setL
          messag


        setLogs(prev => [...prev, { 
          message: '✓ Scan analysis complete', 
        }]);

        setL
          messag


        timeouts.forEach(clearTimeou
    }

    if (scrollRef.curre
    }


        <Terminal size={18} className=
          Scanner Console
        {isScanning && (
        )}

        ref=
        style={{

            Awaiting scan initializati
        ) : (
            <div 
              className={cn(
                log.typ
            
              )}

            </div>
        )}

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



























































