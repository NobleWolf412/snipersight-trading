export type TradingSession = 'ASIA' | 'LONDON' | 'NEW_YORK' | 'SYDNEY';

export function getCurrentTradingSession(): TradingSession {
  const now = new Date();
  const utcHour = now.getUTCHours();

  if (utcHour >= 0 && utcHour < 6) return 'SYDNEY';
  if (utcHour >= 6 && utcHour < 8) return 'ASIA';
  if (utcHour >= 8 && utcHour < 13) return 'LONDON';
  if (utcHour >= 13 && utcHour < 22) return 'NEW_YORK';
  return 'SYDNEY';
}

export function getSessionColor(session: TradingSession): string {
  const colors = {
    ASIA: 'text-accent',
    LONDON: 'text-accent',
    NEW_YORK: 'text-accent',
    SYDNEY: 'text-accent',
  };
  return colors[session];
}
