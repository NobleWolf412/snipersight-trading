import { useSyncExternalStore } from 'react';
export interface BrowserPreferences { tacticalBackground: boolean; reticle: boolean }
const defaults: BrowserPreferences = { tacticalBackground: true, reticle: true };
const key = 'sniper.browser.preferences.v2';
let snapshot: BrowserPreferences | undefined;
const listeners = new Set<() => void>();
function read(): BrowserPreferences {
  try {
    const data = JSON.parse(localStorage.getItem(key) ?? '{}');
    return { tacticalBackground: typeof data?.tacticalBackground === 'boolean' ? data.tacticalBackground : defaults.tacticalBackground,
      reticle: typeof data?.reticle === 'boolean' ? data.reticle : defaults.reticle };
  } catch { return defaults; }
}
function getSnapshot() { return snapshot ??= read(); }
function subscribe(fn: () => void) {
  listeners.add(fn);
  const changed = (event: StorageEvent) => {
    if (event.key === key || event.key === null) { snapshot = read(); fn(); }
  };
  window.addEventListener('storage', changed);
  return () => { listeners.delete(fn); window.removeEventListener('storage', changed); };
}
export function saveBrowserPreferences(value: BrowserPreferences) {
  localStorage.setItem(key, JSON.stringify(value));
  snapshot = { ...value }; listeners.forEach(fn => fn());
}
export const useBrowserPreferences = () => useSyncExternalStore(subscribe, getSnapshot, () => defaults);
