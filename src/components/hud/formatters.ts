// HUD formatters — verbatim port of prototype/shared.jsx fmt* helpers.
// Used across all HUD components for consistent number/currency/duration display.

export function fmtMoney(v: number, d?: number): string {
  const decimals = d == null ? 2 : d;
  const sign = v < 0 ? '-$' : '$';
  return sign + Math.abs(v).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function fmtPct(v: number, d?: number): string {
  const decimals = d == null ? 2 : d;
  return (v >= 0 ? '+' : '') + v.toFixed(decimals) + '%';
}

export function fmtPrice(p: number): string {
  if (p < 1) return '$' + p.toFixed(5);
  if (p < 100) return '$' + p.toFixed(4);
  return '$' + p.toFixed(2);
}

export function fmtDur(seconds: number): string {
  if (seconds < 60) return seconds + 's';
  if (seconds < 3600) return Math.floor(seconds / 60) + 'm ' + (seconds % 60) + 's';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h + 'h ' + m + 'm';
}

export function fmtNum(v: number): string {
  if (Math.abs(v) >= 1e9) return (v / 1e9).toFixed(2) + 'B';
  if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(2) + 'M';
  if (Math.abs(v) >= 1e3) return (v / 1e3).toFixed(2) + 'K';
  return v.toFixed(2);
}
