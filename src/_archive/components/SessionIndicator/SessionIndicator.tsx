import { useState, useEffect } from 'react';
import { getCurrentTradingSession, type TradingSession } from '@/utils/tradingSessions';
import { Globe } from '@phosphor-icons/react';

export function SessionIndicator() {
  const [currentSession, setCurrentSession] = useState<TradingSession>(getCurrentTradingSession());

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentSession(getCurrentTradingSession());
    }, 60000);

    return () => clearInterval(interval);
  }, []);

  const sessionLabels: Record<TradingSession, string> = {
    ASIA: 'Asia',
    LONDON: 'London',
    NEW_YORK: 'NY',
    SYDNEY: 'Sydney'
  };

  // Volume/liquidity indicators for each session
  const sessionActivity: Record<TradingSession, 'high' | 'medium' | 'low'> = {
    LONDON: 'high',      // Highest volume - overlaps with Asia and NY
    NEW_YORK: 'high',    // Highest volume - overlaps with London
    ASIA: 'medium',      // Moderate volume
    SYDNEY: 'low'        // Lower volume
  };

  const sessions: TradingSession[] = ['ASIA', 'LONDON', 'NEW_YORK', 'SYDNEY'];

  const getActivityIndicator = (activity: 'high' | 'medium' | 'low') => {
    switch (activity) {
      case 'high':
        return (
          <div className="flex items-center gap-1">
            <div className="w-0.5 h-2 bg-success rounded-full" />
            <div className="w-0.5 h-2.5 bg-success rounded-full" />
            <div className="w-0.5 h-3 bg-success rounded-full" />
          </div>
        );
      case 'medium':
        return (
          <div className="flex items-center gap-1">
            <div className="w-0.5 h-2 bg-warning rounded-full" />
            <div className="w-0.5 h-2.5 bg-warning rounded-full" />
            <div className="w-0.5 h-3 bg-muted-foreground/30 rounded-full" />
          </div>
        );
      case 'low':
        return (
          <div className="flex items-center gap-1">
            <div className="w-0.5 h-2 bg-muted-foreground/50 rounded-full" />
            <div className="w-0.5 h-2.5 bg-muted-foreground/30 rounded-full" />
            <div className="w-0.5 h-3 bg-muted-foreground/20 rounded-full" />
          </div>
        );
    }
  };

  return (
    <div className="flex items-center gap-5 bg-black/55 border border-primary/40 px-6 py-3 rounded-md backdrop-blur-sm shadow-[0_0_16px_-2px_rgba(0,255,170,0.35)] w-full max-w-2xl md:max-w-3xl">
      <div className="flex items-center gap-2 pr-2">
        <Globe size={22} weight="bold" className="text-primary drop-shadow-[0_0_6px_rgba(0,255,170,0.4)]" />
      </div>
      <div className="grid grid-cols-4 gap-3 w-full">
        {sessions.map(session => {
          const isActive = currentSession === session;
          const activity = sessionActivity[session];
          return (
            <div
              key={session}
              className={`relative px-4 py-2 rounded-sm text-sm md:text-base font-bold tracking-[0.18em] uppercase transition-all w-full ${
                isActive
                  ? 'text-primary bg-primary/15 border border-primary/60 shadow-[0_0_10px_rgba(0,255,170,0.45)]'
                  : 'text-muted-foreground/70 bg-black/30 border border-border/30'
              }`}
            >
              {isActive && (
                <div className="absolute -left-1.5 top-1/2 -translate-y-1/2 w-2 h-2 bg-primary rounded-full scan-pulse shadow-[0_0_8px_currentColor]" />
              )}
              <div className="flex flex-col items-center gap-1 text-center">
                <span className="relative z-10 hud-terminal drop-shadow-[0_1px_2px_rgba(0,0,0,0.6)]">{sessionLabels[session]}</span>
                <div className="relative z-10" title={`${activity.charAt(0).toUpperCase() + activity.slice(1)} volume`}>
                  {getActivityIndicator(activity)}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
