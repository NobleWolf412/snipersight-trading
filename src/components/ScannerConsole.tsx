import { useEffect, useRef, useState, useMemo, ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { TerminalWindow, Lightning, Crosshair } from '@phosphor-icons/react';
import { useScanner } from '@/context/ScannerContext';
import { debugLogger, DebugLogEntry } from '@/utils/debugLogger';
import { motion, AnimatePresence } from 'framer-motion';
import { TacticalRadar } from './scanner/TacticalRadar';
import { WaveformMonitor } from './scanner/WaveformMonitor';
import { SystemVitals } from './scanner/SystemVitals';

interface ScannerConsoleProps {
  className?: string;
  isScanning: boolean;
}

// Regex to match crypto trading pairs like BTC/USDT, ETH/USDT, SOL/USDT, etc.
const SYMBOL_REGEX = /([A-Z0-9]{2,10}\/(?:USDT|USD|USDC|BTC|ETH|BUSD))/g;

// Regex to match confluence scores like "78%" or "Confluence: 78%"
const SCORE_REGEX = /(?:Confluence[:\s]*)?(\d{1,3})%/gi;

// Mini progress bar for scores
function ScoreBadge({ score }: { score: number }) {
  const barCount = 10;
  const filledBars = Math.round((score / 100) * barCount);
  const color = score >= 70 ? '#00ff88' : score >= 50 ? '#ffaa00' : '#ff4444';
  const status = score >= 70 ? 'PASS' : score >= 50 ? 'WEAK' : 'FAIL';

  return (
    <span className="inline-flex items-center gap-1.5 mx-1 px-1.5 py-0.5 rounded bg-black/40 border border-white/10">
      <span className="font-bold tabular-nums" style={{ color }}>{score}%</span>
      <span className="flex gap-px">
        {Array.from({ length: barCount }).map((_, i) => (
          <span
            key={i}
            className="w-1 h-2.5 rounded-sm"
            style={{
              backgroundColor: i < filledBars ? color : 'rgba(255,255,255,0.1)',
              boxShadow: i < filledBars ? `0 0 4px ${color}` : 'none',
            }}
          />
        ))}
      </span>
      <span className="text-[9px] font-bold tracking-wider" style={{ color }}>{status}</span>
    </span>
  );
}

// Parse log message and highlight crypto symbols + scores
function highlightSymbols(message: string): ReactNode[] {
  const parts: ReactNode[] = [];
  let key = 0;

  // First pass: split by symbols
  const symbolSplits = message.split(SYMBOL_REGEX);

  symbolSplits.forEach((part, partIndex) => {
    // Check if this part matches a symbol
    if (SYMBOL_REGEX.test(part)) {
      SYMBOL_REGEX.lastIndex = 0; // Reset
      parts.push(
        <span
          key={key++}
          className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-[#00ff88]/15 border border-[#00ff88]/30 text-[#00ff88] font-bold text-[11px] tracking-wide"
        >
          {part}
        </span>
      );
    } else {
      // Second pass on non-symbol parts: find scores
      const scoreParts = part.split(SCORE_REGEX);

      scoreParts.forEach((scorePart, scoreIndex) => {
        // Check if this is a score number
        const scoreNum = parseInt(scorePart);
        if (!isNaN(scoreNum) && scoreNum >= 0 && scoreNum <= 100 && /^\d{1,3}$/.test(scorePart)) {
          parts.push(<ScoreBadge key={key++} score={scoreNum} />);
        } else if (scorePart) {
          parts.push(scorePart);
        }
      });
    }
  });

  return parts.length > 0 ? parts : [message];
}

export function ScannerConsole({ isScanning, className }: ScannerConsoleProps) {
  const { consoleLogs } = useScanner();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [scanLogs, setScanLogs] = useState<DebugLogEntry[]>([]);
  const wasScanning = useRef(false);
  const [radarBlips, setRadarBlips] = useState<{ symbol: string; score: number; angle: number; distance: number }[]>([]);

  // Subscribe to debug logger
  useEffect(() => {
    if (isScanning && !wasScanning.current) {
      setScanLogs([]);
      setRadarBlips([]);
      wasScanning.current = true;
    }

    if (!isScanning && wasScanning.current) {
      wasScanning.current = false;
    }

    if (isScanning) {
      const unsubscribe = debugLogger.subscribe((entry) => {
        if (entry.source === 'scanner') {
          const isSpam = entry.message.includes('Response:') ||
            entry.message.includes('Request successful') ||
            entry.message.includes('Connecting to:') ||
            entry.message.includes('Timeout:') ||
            entry.message.includes('Sending request') ||
            entry.message.includes('Poll failed');

          if (!isSpam) {
            setScanLogs(prev => [...prev, entry]);

            // Add radar blip for completed symbol analysis
            if (entry.message.includes('Confluence:') || entry.message.includes('rejected')) {
              const scoreMatch = entry.message.match(/(\d+)%/);
              const symbolMatch = entry.message.match(/([A-Z]+\/USDT)/);
              if (symbolMatch) {
                const score = scoreMatch ? parseInt(scoreMatch[1]) : 30;
                setRadarBlips(prev => [...prev.slice(-15), {
                  symbol: symbolMatch[1],
                  score,
                  angle: Math.random() * Math.PI * 2,
                  distance: 0.3 + Math.random() * 0.6,
                }]);
              }
            }
          }
        }
      });
      return () => unsubscribe();
    }
  }, [isScanning]);

  // Timer
  useEffect(() => {
    let interval: number;
    const startTime = Date.now();

    if (isScanning) {
      interval = window.setInterval(() => {
        setElapsedMs(Date.now() - startTime);
      }, 100);
    } else {
      setElapsedMs(0);
    }

    return () => clearInterval(interval);
  }, [isScanning]);

  const formatElapsed = (ms: number) => {
    const totalSeconds = Math.floor(ms / 1000);
    const m = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
    const s = (totalSeconds % 60).toString().padStart(2, '0');
    const cs = Math.floor((ms % 1000) / 10).toString().padStart(2, '0');
    return `${m}:${s}.${cs}`;
  };

  const mergedLogs = useMemo(() =>
    [...consoleLogs, ...scanLogs].sort((a, b) => a.timestamp - b.timestamp),
    [consoleLogs, scanLogs]
  );

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [mergedLogs.length]);

  return (
    <div className={cn(
      "flex flex-col h-full max-h-full overflow-hidden rounded-xl relative border border-[#00ff88]/30 bg-[#0a0f0a] shadow-[0_0_40px_rgba(0,255,136,0.15),inset_0_0_60px_rgba(0,0,0,0.8)]",
      className
    )}>

      {/* CRT Scanline Effect */}
      <div
        className="absolute inset-0 pointer-events-none z-50 opacity-[0.03]"
        style={{
          backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.3) 2px, rgba(0,0,0,0.3) 4px)',
        }}
      />

      {/* Vignette Effect */}
      <div
        className="absolute inset-0 pointer-events-none z-40"
        style={{
          background: 'radial-gradient(ellipse at center, transparent 0%, transparent 60%, rgba(0,0,0,0.4) 100%)',
        }}
      />

      {/* Header Bar */}
      <div className="relative z-10 flex items-center justify-between px-4 py-2.5 border-b border-[#00ff88]/30 bg-gradient-to-r from-[#00ff88]/10 via-transparent to-[#00ff88]/10">
        <div className="flex items-center gap-3">
          <TerminalWindow size={18} className="text-[#00ff88]" weight="bold" />
          <span className="font-mono text-sm font-bold text-[#00ff88] tracking-[0.2em]">
            SNIPERSIGHT // TACTICAL OPS CONSOLE
          </span>
        </div>

        <div className="flex items-center gap-4">
          {/* Elapsed timer */}
          <div className="font-mono text-xs text-[#00ff88]/70 tabular-nums">
            T+{formatElapsed(elapsedMs)}
          </div>

          {/* Status badge */}
          {isScanning ? (
            <div className="flex items-center gap-2 px-3 py-1 rounded border border-[#00ff88]/50 bg-[#00ff88]/10">
              <div className="w-2 h-2 rounded-full bg-[#00ff88] animate-pulse shadow-[0_0_8px_rgba(0,255,136,0.8)]" />
              <span className="text-xs font-mono font-bold text-[#00ff88] tracking-widest">SCANNING</span>
              <Lightning size={14} className="text-amber-400 animate-pulse" />
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1 rounded border border-muted-foreground/30">
              <div className="w-2 h-2 rounded-full bg-muted-foreground/50" />
              <span className="text-xs font-mono text-muted-foreground tracking-widest">STANDBY</span>
            </div>
          )}
        </div>
      </div>

      {/* Main Content - Multi-Panel Layout */}
      <div className="relative z-10 flex-1 flex min-h-0 overflow-hidden">

        {/* Left Panel - Radar + Vitals */}
        <div className="w-56 border-r border-[#00ff88]/20 flex flex-col bg-black/40">
          {/* Radar */}
          <div className="h-56 p-2 border-b border-[#00ff88]/20">
            <TacticalRadar
              isScanning={isScanning}
              blips={radarBlips}
              className="w-full h-full"
            />
          </div>

          {/* System Vitals */}
          <div className="flex-1 p-3 overflow-y-auto">
            <SystemVitals
              isScanning={isScanning}
              targetsFound={radarBlips.length}
              targetsTotal={isScanning ? 50 : 0}
            />
          </div>
        </div>

        {/* Right Panel - Log + Waveform */}
        <div className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden">

          {/* Operation Log */}
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            <div className="px-4 py-2 border-b border-[#00ff88]/20 bg-black/30 shrink-0">
              <span className="text-[10px] font-mono text-[#00ff88]/60 tracking-wider">OPERATION LOG</span>
            </div>

            <div
              ref={scrollRef}
              className="flex-1 p-3 font-mono text-xs space-y-1 overflow-y-auto overflow-x-hidden min-h-0 scrollbar-thin scrollbar-thumb-[#00ff88]/20 scrollbar-track-transparent"
            >
              <AnimatePresence initial={false}>
                {mergedLogs.length > 0 ? (
                  mergedLogs.slice(-100).map((log, i) => (
                    <motion.div
                      key={`${log.timestamp}-${i}`}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="flex gap-2 group hover:bg-[#00ff88]/5 px-1 py-0.5 rounded transition-colors"
                    >
                      <span className="text-[#00ff88]/30 shrink-0 select-none tabular-nums">
                        {new Date(log.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </span>

                      <span className={cn(
                        "shrink-0 text-[9px] uppercase tracking-wider border rounded px-1 py-px select-none",
                        (log as DebugLogEntry).source === 'api' ? "border-blue-500/30 text-blue-400/70 bg-blue-500/5" :
                          (log as DebugLogEntry).source === 'scanner' ? "border-[#00ff88]/30 text-[#00ff88]/70 bg-[#00ff88]/5" :
                            "border-slate-600 text-slate-500"
                      )}>
                        {(log as DebugLogEntry).source === 'api' ? 'FE·API' :
                          (log as DebugLogEntry).source === 'scanner' ? 'BE·SCAN' :
                            (log as DebugLogEntry).source || 'SYS'}
                      </span>

                      <span className={cn(
                        "flex-1 break-words overflow-hidden",
                        log.type === 'success' && "text-emerald-400 font-bold",
                        log.type === 'warning' && "text-amber-400",
                        log.type === 'error' && "text-rose-400 font-bold",
                        log.type === 'api' && "text-cyan-300",
                        (log.type === 'info' || !log.type) && "text-slate-300",
                        log.type === 'config' && "text-slate-500 italic"
                      )}>
                        {log.type === 'success' && '✓ '}
                        {log.type === 'error' && '✗ '}
                        {log.type === 'warning' && '⚠ '}
                        {highlightSymbols(log.message)}
                      </span>
                    </motion.div>
                  ))
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-center opacity-40">
                    <Crosshair size={40} className="text-[#00ff88] mb-3 animate-[spin_15s_linear_infinite]" />
                    <p className="text-[#00ff88] tracking-[0.3em] text-xs font-bold">SYSTEM READY</p>
                    <p className="text-[10px] text-[#00ff88]/60 mt-1">AWAITING OPERATIONAL PARAMETERS</p>
                  </div>
                )}
              </AnimatePresence>

              {/* Blinking cursor */}
              {isScanning && (
                <div className="flex items-center gap-1 text-[#00ff88]/50 mt-2">
                  <span className="animate-pulse">▌</span>
                </div>
              )}
            </div>
          </div>

          {/* Waveform Monitor */}
          <div className="h-24 border-t border-[#00ff88]/20 bg-black/30">
            <WaveformMonitor
              isActive={isScanning}
              intensity={isScanning ? 0.7 : 0.1}
              className="w-full h-full"
            />
          </div>
        </div>
      </div>

      {/* Footer Status Bar */}
      <div className="relative z-10 px-4 py-1.5 bg-gradient-to-r from-[#00ff88]/5 via-black to-[#00ff88]/5 border-t border-[#00ff88]/20 flex justify-between items-center text-[10px] font-mono">
        <div className="flex items-center gap-4 text-[#00ff88]/50">
          <span>VER 3.0.0-TACTICAL</span>
          <span className="text-[#00ff88]/30">│</span>
          <span className="flex items-center gap-1">
            <div className="w-1 h-1 rounded-full bg-[#00ff88]" />
            UPLINK: ENCRYPTED
          </span>
        </div>
        <div className="flex items-center gap-4 text-[#00ff88]/50">
          <span>BUFFER: {mergedLogs.length} ENTRIES</span>
          <span className="text-[#00ff88]/30">│</span>
          <span className="flex items-center gap-1.5">
            <div className={cn(
              "w-1.5 h-1.5 rounded-full",
              isScanning ? "bg-[#00ff88] animate-pulse" : "bg-muted-foreground/50"
            )} />
            {isScanning ? 'LIVE FEED' : 'IDLE'}
          </span>
        </div>
      </div>
    </div>
  );
}
