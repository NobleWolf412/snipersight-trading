/**
 * Shared formatting utilities for consistent display across components.
 */

/**
 * Format a price value based on its magnitude for display.
 * - Large prices (≥1000): Locale-formatted with 2 decimals
 * - Medium prices (≥1): 4 decimal places
 * - Small prices (<1): 6 decimal places (crypto micro-caps)
 * 
 * @param price - The price value to format
 * @returns Formatted price string (without currency symbol)
 */
export function formatPrice(price: number): string {
  if (price >= 1000) {
    return price.toLocaleString('en-US', { 
      minimumFractionDigits: 2, 
      maximumFractionDigits: 2 
    });
  }
  if (price >= 1) {
    return price.toFixed(4);
  }
  return price.toFixed(6);
}

/**
 * Format a volume value with appropriate suffix (K/M/B).
 * 
 * @param volume - The volume value to format
 * @returns Formatted volume string with $ prefix
 */
export function formatVolume(volume: number): string {
  if (volume >= 1e9) return `$${(volume / 1e9).toFixed(2)}B`;
  if (volume >= 1e6) return `$${(volume / 1e6).toFixed(2)}M`;
  if (volume >= 1e3) return `$${(volume / 1e3).toFixed(2)}K`;
  return `$${volume.toFixed(2)}`;
}

/**
 * Format a percentage value for display.
 * 
 * @param value - The percentage value
 * @param decimals - Number of decimal places (default: 2)
 * @returns Formatted percentage string with % suffix
 */
export function formatPercent(value: number, decimals: number = 2): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(decimals)}%`;
}

/**
 * Format a number with appropriate precision based on magnitude.
 * 
 * @param value - The number to format
 * @param significantDigits - Target significant digits (default: 4)
 * @returns Formatted number string
 */
export function formatNumber(value: number, significantDigits: number = 4): string {
  if (value === 0) return '0';
  const magnitude = Math.floor(Math.log10(Math.abs(value)));
  const decimals = Math.max(0, significantDigits - magnitude - 1);
  return value.toFixed(decimals);
}
