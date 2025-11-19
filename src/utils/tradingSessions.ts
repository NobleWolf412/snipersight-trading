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
    ASIA: 'text-yellow-500',
    LONDON: 'text-blue-500',
    NEW_YORK: 'text-green-500',
    SYDNEY: 'text-purple-500',
  };
  return colors[session];
}
