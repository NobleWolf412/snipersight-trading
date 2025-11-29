import { useState, useEffect } from 'react';
import { getCurrentTradingSession, getSessionColor, type TradingSession } from '@/utils/tradingSessions';
import { Globe, TrendUp } from '@phosphor-icons/react';

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
    <div className="flex items-center gap-4 bg-background/60 border border-primary/30 px-5 py-2.5 rounded-sm backdrop-blur-sm shadow-[0_0_12px_rgba(0,255,170,0.15)]">
      <div className="flex items-center gap-2">
        <Globe size={20} weight="bold" className="text-primary" />
      </div>
      <div className="flex gap-4">
        {sessions.map((session) => {
          const isActive = currentSession === session;
          const activity = sessionActivity[session];
          return (
            <div
              key={session}
              className={`relative px-4 py-2 rounded-sm text-xs font-bold tracking-[0.12em] uppercase transition-all ${
                isActive
                  ? 'text-primary bg-primary/20 border border-primary/60 shadow-[0_0_8px_rgba(0,255,170,0.3)]'
                  : 'text-muted-foreground/60 bg-background/30 border border-border/20'
              }`}
            >
              {isActive && (
                <div className="absolute -left-1 top-1/2 -translate-y-1/2 w-1.5 h-1.5 bg-primary rounded-full scan-pulse shadow-[0_0_6px_currentColor]" />
              )}
              <div className="flex items-center gap-2">
                <span className="relative z-10 hud-terminal">{sessionLabels[session]}</span>
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
