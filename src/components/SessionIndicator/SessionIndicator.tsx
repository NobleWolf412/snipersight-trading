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

  const sessions: TradingSession[] = ['ASIA', 'LONDON', 'NEW_YORK', 'SYDNEY'];

  return (
    <div className="flex items-center gap-3 bg-card/50 border border-border px-4 py-2 rounded">
      <Globe size={16} className="text-muted-foreground" />
      <div className="flex gap-2">
        {sessions.map((session) => (
          <div
            key={session}
            className={`px-2 py-1 rounded text-xs font-medium transition-all ${
              currentSession === session
                ? `${getSessionColor(session)} bg-accent/20 border border-accent/50`
                : 'text-muted-foreground'
            }`}
          >
            {session}
          </div>
        ))}
      </div>
    </div>
  );
}
