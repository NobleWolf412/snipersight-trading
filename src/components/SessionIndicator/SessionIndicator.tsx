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
    <div className="flex items-center gap-6 bg-card/50 border border-border px-7 py-3.5 rounded-lg hud-glow-cyan">
      <div className="flex items-center gap-3">
        <Globe size={22} weight="bold" className="text-accent" />
      </div>
      <div className="flex gap-6">
        {sessions.map((session) => {
          const isActive = currentSession === session;
          const activity = sessionActivity[session];
          return (
            <div
              key={session}
              className={`relative px-5 py-2.5 rounded-md text-xs font-bold tracking-wide transition-all ${
                isActive
                  ? `${getSessionColor(session)} bg-accent/30 border border-accent hud-glow-cyan shadow-lg scale-105`
                  : 'text-muted-foreground bg-background/50 border border-border/30'
              }`}
            >
              {isActive && (
                <div className="absolute -left-1.5 top-1/2 -translate-y-1/2 w-2 h-2 bg-accent rounded-full scan-pulse-fast shadow-[0_0_8px_currentColor]" />
              )}
              <div className="flex items-center gap-2.5">
                <span className="relative z-10">{sessionLabels[session]}</span>
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
