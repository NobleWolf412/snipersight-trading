import React, { useEffect, useRef, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import { TerminalWindow, CaretDown, CaretUp } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

export function SystemTerminal() {
    const terminalRef = useRef<HTMLDivElement>(null);
    const xtermInstance = useRef<Terminal | null>(null);
    const fitAddonRef = useRef<FitAddon | null>(null);
    const [isOpen, setIsOpen] = useState(false);
    const [unreadCount, setUnreadCount] = useState(0);

    // Initialize Terminal
    useEffect(() => {
        if (!terminalRef.current) return;

        // Cleanup any existing instance (safety for StrictMode)
        if (xtermInstance.current) {
            xtermInstance.current.dispose();
            xtermInstance.current = null;
        }

        const term = new Terminal({
            theme: {
                background: '#050505',
                foreground: '#00ff88',
                cursor: '#00ff88',
                selectionBackground: 'rgba(0, 255, 136, 0.3)',
                black: '#000000',
                red: '#ef4444',
                green: '#00ff88',
                yellow: '#eab308',
                blue: '#3b82f6',
                magenta: '#d946ef',
                cyan: '#06b6d4',
                white: '#ffffff',
            },
            fontFamily: '"JetBrains Mono", "Fira Code", monospace',
            fontSize: 12,
            lineHeight: 1.2,
            cursorBlink: true,
            disableStdin: true,
            rows: 10,
            allowProposedApi: true,
        });

        const fitAddon = new FitAddon();
        term.loadAddon(fitAddon);
        fitAddonRef.current = fitAddon;
        xtermInstance.current = term;

        // Mount
        term.open(terminalRef.current);

        // Immediate fit
        try {
            fitAddon.fit();
        } catch (e) {
            // ignore sizing errors on init if hidden
        }

        // Boot Sequence
        const bootTimer = setTimeout(() => {
            // Verify instance is still valid before writing
            if (xtermInstance.current === term) {
                simulateBoot(term);
            }
        }, 100);

        return () => {
            clearTimeout(bootTimer);
            term.dispose();
            xtermInstance.current = null;
            fitAddonRef.current = null;
        };
    }, []);

    // Handle Resize
    useEffect(() => {
        const handleResize = () => {
            fitAddonRef.current?.fit();
        };
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    // Handle Open Toggle
    useEffect(() => {
        if (isOpen) {
            setUnreadCount(0);
            setTimeout(() => {
                fitAddonRef.current?.fit();
            }, 300);
        }
    }, [isOpen]);

    // Simulate logs
    useEffect(() => {
        if (!xtermInstance.current) return;

        const logs = [
            "Scanning sector 7G...",
            "Market volatility spike detected [WARN]",
            "Uplink established: 45ms latency",
            "Encryption key rotation scheduled",
            "Analyzing order book depth...",
            "Signal confidence updated: BTC-USDT +2.4%",
            "Packet loss: 0.001%",
            "System temperature: Optimal",
            "Neural net weights updated",
        ];

        const interval = setInterval(() => {
            if (!xtermInstance.current) return;

            const randomLog = logs[Math.floor(Math.random() * logs.length)];
            const time = new Date().toISOString().split('T')[1].slice(0, 12);

            // Safety check for disposed terminal
            try {
                xtermInstance.current.writeln(`\x1b[2m[${time}]\x1b[0m ${randomLog} `);
            } catch (e) {
                // If write fails, it's likely disposed
            }

            if (!isOpen) {
                setUnreadCount(prev => Math.min(prev + 1, 99));
            }
        }, 3000);

        return () => clearInterval(interval);
    }, [isOpen]);

    const simulateBoot = (term: Terminal) => {
        try {
            term.writeln('\x1b[1;32mSNIPERSIGHT OS v4.2.0\x1b[0m');
            term.writeln('Initializing core modules...');
            let i = 0;
            const modules = ['NET', 'CRYPTO', 'AI', 'UI', 'RENDER'];

            const interval = setInterval(() => {
                // Check if term is still the active one
                if (xtermInstance.current !== term) {
                    clearInterval(interval);
                    return;
                }

                if (i >= modules.length) {
                    clearInterval(interval);
                    term.writeln('----------------------------------------');
                    term.writeln('\x1b[1;32mSYSTEM READY\x1b[0m');
                    return;
                }
                term.writeln(`[OK] Module \x1b[36m${modules[i]} \x1b[0m loaded.`);
                i++;
            }, 200);
        } catch (e) { console.warn("Terminal boot interrupted"); }
    }

    return (
        <div className={cn(
            "fixed bottom-0 right-0 z-50 border-t border-l border-white/10 bg-black/90 backdrop-blur-md transition-all duration-300 shadow-[0_-5px_20px_rgba(0,0,0,0.5)]",
            isOpen ? "w-[600px] h-[300px]" : "w-[300px] h-[40px]"
        )}>
            {/* Header / Toggle */}
            <div
                className="flex items-center justify-between px-4 py-2 cursor-pointer hover:bg-white/5 border-b border-white/5 h-[40px]"
                onClick={() => setIsOpen(!isOpen)}
            >
                <div className="flex items-center gap-3">
                    <TerminalWindow className="text-accent" />
                    <span className="text-xs font-mono font-bold text-zinc-400">SYSTEM LOGS</span>
                    {!isOpen && unreadCount > 0 && (
                        <span className="bg-red-500 text-white text-[9px] px-1.5 rounded-full animate-pulse">
                            {unreadCount}
                        </span>
                    )}
                </div>
                <div className="text-zinc-500 hover:text-white">
                    {isOpen ? <CaretDown /> : <CaretUp />}
                </div>
            </div>

            {/* Terminal Container */}
            <div
                className={cn(
                    "w-full h-[calc(100%-40px)] overflow-hidden p-2 relative bg-[#050505]",
                    !isOpen && "hidden"
                )}
            >
                <div className="absolute inset-0 scanner-line opacity-10 pointer-events-none z-10" />
                <div ref={terminalRef} className="w-full h-full" />
            </div>
        </div>
    );
}
