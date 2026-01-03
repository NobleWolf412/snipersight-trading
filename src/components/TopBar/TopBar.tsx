import { Link } from 'react-router-dom';
import { Crosshair, GearSix, CaretDown } from '@phosphor-icons/react';
import { SessionIndicator } from '@/components/SessionIndicator/SessionIndicator';
import { WalletConnect } from '@/components/WalletConnect';
import { HTFAlertBeacon } from '@/components/htf/HTFAlertBeacon';
import { BTCPricePill } from './BTCPricePill';
import { debugLogger, LogLevel } from '@/utils/debugLogger';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import { useState } from 'react';
import { cn } from '@/lib/utils';

export function TopBar() {
  const [showSettings, setShowSettings] = useState(false);
  const [verbosity, setVerbosity] = useLocalStorage<'silent' | 'essential' | 'verbose'>(
    'log-verbosity',
    (import.meta.env.MODE === 'production') ? 'essential' : 'verbose'
  );

  // Apply verbosity to debugLogger
  const appliedLevel = verbosity === 'silent' ? LogLevel.SILENT : verbosity === 'essential' ? LogLevel.WARN : LogLevel.INFO;
  debugLogger.setLogLevel(appliedLevel);

  return (
    <header
      className="sticky top-0 z-50 border-b border-cyan-500/30 bg-black/80 backdrop-blur-xl animate-[glow-pulse_3s_ease-in-out_infinite]"
      style={{
        boxShadow: '0 0 20px rgba(0,255,255,0.08), inset 0 -1px 0 rgba(0,255,255,0.15), 0 4px 30px -10px rgba(0,255,255,0.2)'
      }}
      role="banner"
    >
      {/* Main TopBar */}
      <div className="max-w-[1800px] mx-auto px-4 sm:px-6">
        <div className="flex items-center h-18 min-h-[72px] gap-6">

          {/* Brand */}
          <Link
            to="/"
            className="group flex items-center gap-3"
            aria-label="SniperSight Home"
          >
            <div className="relative w-11 h-11 rounded-lg bg-cyan-500/10 flex items-center justify-center ring-1 ring-cyan-500/40 shadow-[0_0_15px_-3px_rgba(0,255,255,0.6)] group-hover:shadow-[0_0_20px_0_rgba(0,255,255,0.7)] transition-shadow">
              <Crosshair size={24} weight="bold" className="text-cyan-400" />
            </div>
            <div className="hidden sm:flex flex-col">
              <span className="text-base font-bold tracking-tight text-cyan-100">SNIPERSIGHT</span>
              <span className="text-[10px] tracking-[0.2em] text-cyan-400/60">PRECISION SYSTEM</span>
            </div>
          </Link>

          {/* Center: Session Indicator + BTC Price */}
          <div className="flex flex-1 items-center justify-center gap-6">
            {/* Session indicator - centered */}
            <div className="hidden lg:block">
              <SessionIndicator />
            </div>
            <BTCPricePill />
          </div>

          {/* Right Utilities Section - Grid Layout */}
          <div className="grid grid-cols-[auto_auto_auto] gap-16 items-center text-base">
            <div className="flex justify-center">
              <HTFAlertBeacon />
            </div>

            <div className="flex justify-center">
              <WalletConnect />
            </div>

            <div className="flex justify-center relative">
              <button
                onClick={() => setShowSettings(!showSettings)}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 rounded-md text-base font-medium transition-colors",
                  showSettings
                    ? "bg-cyan-500/20 text-cyan-400"
                    : "text-zinc-500 hover:text-cyan-300 hover:bg-cyan-500/10"
                )}
                title="Settings"
              >
                <GearSix size={22} weight="bold" />
                <CaretDown size={14} className={cn("transition-transform duration-200", showSettings && "rotate-180")} />
              </button>

              {showSettings && (
                <div className="absolute right-0 top-full mt-2 w-48 py-2 rounded-lg bg-black/95 border border-cyan-500/20 shadow-xl backdrop-blur-xl z-50">
                  <div className="px-3 py-2 border-b border-cyan-500/10">
                    <label className="text-[10px] font-bold tracking-wider text-cyan-400/60 uppercase">
                      Log Verbosity
                    </label>
                    <select
                      aria-label="Log verbosity"
                      className="w-full mt-1 px-2 py-1.5 rounded bg-black/50 border border-cyan-500/20 text-sm text-foreground outline-none focus:border-cyan-500/50"
                      value={verbosity}
                      onChange={(e) => setVerbosity(e.target.value as any)}
                    >
                      <option value="silent">Silent</option>
                      <option value="essential">Essential</option>
                      <option value="verbose">Verbose</option>
                    </select>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Mobile: BTC Price strip */}
      <div className="sm:hidden border-t border-cyan-500/10 bg-black/90 px-4 py-2.5 flex justify-center">
        <BTCPricePill />
      </div>
    </header>
  );
}
