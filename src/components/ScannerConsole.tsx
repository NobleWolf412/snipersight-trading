import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { TerminalWindow, Lightning, Cpu, WifiHigh, Pulse, Crosshair } from '@phosphor-icons/react';
import { useScanner } from '@/context/ScannerContext';
import { debugLogger, DebugLogEntry } from '@/utils/debugLogger';
import { motion, AnimatePresence } from 'framer-motion';

interface ScannerConsoleProps { className?: string; isScanning: boolean; }

export function ScannerConsole({ isScanning, className }: ScannerConsoleProps) {
  const { consoleLogs } = useScanner();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [scanLogs, setScanLogs] = useState<DebugLogEntry[]>([]);
  const wasScanning = useRef(false);

  // Simulated system metrics
  const [metrics, setMetrics] = useState({ cpu: 12, mem: 45, net: 24 });

  // Subscribe to debug logger (FILTERED for tactical updates only)
  useEffect(() => {
    if (isScanning && !wasScanning.current) {
      setScanLogs([]);
      wasScanning.current = true;
    }

    if (!isScanning && wasScanning.current) {
      wasScanning.current = false;
    }

    if (isScanning) {
      const unsubscribe = debugLogger.subscribe((entry) => {
        // Filter: Only show scanner source logs (not API network spam)
        if (entry.source === 'scanner') {
          // Further filter: Skip verbose API-related messages
          const isSpam = entry.message.includes('Response:') ||
            entry.message.includes('Request successful') ||
            entry.message.includes('Connecting to:') ||
            entry.message.includes('Timeout:') ||
            entry.message.includes('Sending request') ||
            entry.message.includes('Poll failed');

          if (!isSpam) {
            setScanLogs(prev => [...prev, entry]);
          }
        }
      });
      return () => unsubscribe();
    }
  }, [isScanning]);

  // Timer and Metrics Simulation
  useEffect(() => {
    let interval: any;
    let startTime = Date.now();

    if (isScanning) {
      interval = setInterval(() => {
        setElapsedMs(Date.now() - startTime);
        // Fluctuate metrics
        setMetrics(prev => ({
          cpu: Math.min(99, Math.max(5, prev.cpu + (Math.random() * 10 - 5))),
          mem: Math.min(90, Math.max(20, prev.mem + (Math.random() * 4 - 2))),
          net: Math.min(100, Math.max(10, prev.net + (Math.random() * 20 - 10))),
        }));
      }, 1000);
    } else {
      setElapsedMs(0);
      setMetrics({ cpu: 12, mem: 45, net: 24 });
    }

    return () => clearInterval(interval);
  }, [isScanning]);

  const formatElapsed = (ms: number) => {
    const totalSeconds = Math.floor(ms / 1000);
    const m = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
    const s = (totalSeconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const mergedLogs = [...consoleLogs, ...scanLogs].sort((a, b) => a.timestamp - b.timestamp);

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [mergedLogs.length, metrics]); // Scroll on metrics update too to keep it alive

  return (
    <div className={cn(
      "flex flex-col h-full max-h-full overflow-hidden rounded-lg relative z-0 border border-primary/20 bg-black/90 shadow-[0_0_30px_rgba(0,255,0,0.1)]",
      className
    )}>

      {/* CRT Scanline Effect */}
      <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] z-[5] bg-[length:100%_2px,3px_100%] opacity-20" />

      {/* Header / Status Bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-primary/30 bg-primary/5 relative z-10">
        <div className="flex items-center gap-3">
          <TerminalWindow size={18} className="text-primary animate-pulse" />
          <span className="font-mono text-sm font-bold text-primary tracking-widest">SNIPER.SIGHT // CONSOLE</span>
        </div>

        {/* System Metrics */}
        <div className="flex items-center gap-6 text-xs font-mono text-primary/70">
          <div className="flex items-center gap-1.5">
            <Cpu size={14} />
            <span>CPU: {Math.floor(metrics.cpu)}%</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Pulse size={14} />
            <span>MEM: {Math.floor(metrics.mem)}%</span>
          </div>
          <div className="flex items-center gap-1.5">
            <WifiHigh size={14} />
            <span>NET: {Math.floor(metrics.net)}ms</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {isScanning ? (
            <div className="flex items-center gap-2 bg-primary/10 px-2 py-0.5 rounded border border-primary/30">
              <span className="text-xs font-mono text-primary animate-pulse">SCANNING</span>
              <span className="text-xs font-mono text-primary">{formatElapsed(elapsedMs)}</span>
              <Lightning size={14} className="text-warning animate-spin-slow" />
            </div>
          ) : (
            <div className="flex items-center gap-2 px-2 py-0.5">
              <span className="text-xs font-mono text-muted-foreground">IDLE</span>
              <div className="w-2 h-2 rounded-full bg-muted-foreground/50" />
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="relative flex-1 flex min-h-0 max-h-full overflow-hidden">

        {/* Log Stream */}
        <div
          ref={scrollRef}
          className="flex-1 p-4 font-mono text-xs space-y-1.5 overflow-y-auto overflow-x-hidden min-h-0 scrollbar-thin scrollbar-thumb-primary/20 scrollbar-track-transparent"
        >
          <AnimatePresence initial={false}>
            {mergedLogs.length > 0 ? (
              mergedLogs.map((log, i) => (
                <motion.div
                  key={`${log.timestamp}-${i}`}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="flex gap-3 group hover:bg-primary/5 p-0.5 rounded transition-colors min-w-0"
                >
                  <span className="text-primary/40 shrink-0 select-none">
                    {new Date(log.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>

                  {/* Source Badge */}
                  <span className={cn(
                    "shrink-0 w-16 text-center text-[10px] uppercase tracking-wider border rounded px-1 py-px select-none",
                    (log as DebugLogEntry).source === 'api' ? "border-cyan-500/30 text-cyan-400" :
                      (log as DebugLogEntry).source === 'scanner' ? "border-primary/30 text-primary" :
                        "border-slate-700 text-slate-500"
                  )}>
                    {(log as DebugLogEntry).source || 'system'}
                  </span>

                  <span className={cn(
                    "flex-1 break-words overflow-hidden whitespace-pre-wrap",
                    "[word-break:break-word]",
                    log.type === 'success' && "text-emerald-400 font-bold",
                    log.type === 'warning' && "text-amber-400",
                    log.type === 'error' && "text-rose-500 font-bold",
                    log.type === 'api' && "text-cyan-300",
                    (log.type === 'info' || !log.type) && "text-slate-300",
                    log.type === 'config' && "text-slate-500 italic"
                  )}>
                    {log.type === 'success' && '✓ '}
                    {log.type === 'error' && '✗ '}
                    {log.type === 'warning' && '⚠ '}
                    {log.message}
                  </span>
                </motion.div>
              ))
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center opacity-30">
                <Crosshair size={48} className="text-primary mb-4 animate-[spin_10s_linear_infinite]" />
                <p className="text-primary tracking-widest text-sm">SYSTEM READY</p>
                <p className="text-xs mt-2">AWAITING TARGET PARAMETERS...</p>
              </div>
            )}
          </AnimatePresence>

          {/* Typing Cursor */}
          {isScanning && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-2 text-primary/50 mt-2 pl-24"
            >
              <span className="animate-pulse">_</span>
            </motion.div>
          )}
        </div>

        {/* Right Side Visualizer (Decorative) */}
        <div className="w-12 border-l border-primary/20 bg-black/50 flex flex-col items-center py-4 gap-1">
          {Array.from({ length: 20 }).map((_, i) => (
            <div
              key={i}
              className={cn(
                "w-1.5 rounded-full transition-all duration-300",
                isScanning
                  ? (Math.random() > 0.5 ? "bg-primary/80 h-3 shadow-[0_0_5px_rgba(0,255,0,0.5)]" : "bg-primary/20 h-1")
                  : "bg-primary/10 h-1"
              )}
            />
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-1 bg-primary/5 border-t border-primary/20 flex justify-between items-center text-[10px] font-mono text-primary/40">
        <span>VER 2.4.0-ALPHA</span>
        <span>SECURE CONNECTION // ENCRYPTED</span>
      </div>
    </div>
  );
}
