import { useState, useEffect } from 'react';
import { getCurrentTradingSession, getSessionColor, type TradingSession } from '@/utils/tradingSessions';
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

  const sessions: TradingSession[] = ['ASIA', 'LONDON', 'NEW_YORK', 'SYDNEY'];

  return (
    <div className="flex items-center gap-4 bg-card/50 border border-border px-5 py-2.5 rounded-lg hud-glow-cyan">
      <div className="flex items-center gap-2">
        <Globe size={18} weight="bold" className="text-accent" />
        <span className="text-xs font-bold text-muted-foreground tracking-wider uppercase">Sessions</span>
      </div>
      <div className="h-5 w-px bg-border" />
      <div className="flex gap-3">
        {sessions.map((session) => {
          const isActive = currentSession === session;
          return (
            <div
              key={session}
              className={`relative px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
                isActive
                  ? `${getSessionColor(session)} bg-accent/30 border border-accent hud-glow-cyan shadow-lg scale-105`
                  : 'text-muted-foreground bg-background/50'
              }`}
            >
              {isActive && (
                <div className="absolute -left-1 top-1/2 -translate-y-1/2 w-1.5 h-1.5 bg-accent rounded-full scan-pulse-fast" />
              )}
              {sessionLabels[session]}
            </div>
          );
        })}
      </div>
    </div>
  );
}
