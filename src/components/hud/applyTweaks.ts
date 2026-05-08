// HUD theme/tweak applier — port of prototype/shared.jsx applyTweaks.
// Mutates document.documentElement / document.body to apply theme tokens.
// Called from TweaksPanel; safe to call repeatedly.

export type AccentKey = 'green' | 'amber' | 'blue' | 'cyan' | 'purple' | 'red' | 'page';
export type DensityKey = 'sparse' | 'balanced' | 'dense';

export interface Tweaks {
  theme: AccentKey;
  density: DensityKey;
  tacticalBg: boolean;
  hudOverlays: boolean;
  simSpeed: number;
}

export const SHARED_TWEAK_DEFAULTS: Tweaks = {
  theme: 'page',
  density: 'balanced',
  tacticalBg: true,
  hudOverlays: true,
  simSpeed: 1,
};

const ACCENTS: Record<Exclude<AccentKey, 'page'>, { c: string; bg: string; bd: string }> = {
  green: { c: '#00ffaa', bg: 'rgba(0,255,170,.10)', bd: 'rgba(0,255,170,.30)' },
  amber: { c: '#fbbf24', bg: 'rgba(251,191,36,.10)', bd: 'rgba(251,191,36,.35)' },
  blue: { c: '#60a5fa', bg: 'rgba(96,165,250,.10)', bd: 'rgba(96,165,250,.30)' },
  cyan: { c: '#22d3ee', bg: 'rgba(34,211,238,.10)', bd: 'rgba(34,211,238,.30)' },
  purple: { c: '#c084fc', bg: 'rgba(192,132,252,.10)', bd: 'rgba(192,132,252,.30)' },
  red: { c: '#f87171', bg: 'rgba(248,113,113,.10)', bd: 'rgba(248,113,113,.35)' },
};

export function applyTweaks(t: Tweaks, pageAccent: Exclude<AccentKey, 'page'>): void {
  const root = document.documentElement;
  const themeKey = t.theme === 'page' ? pageAccent : t.theme;
  const a = ACCENTS[themeKey] || ACCENTS[pageAccent] || ACCENTS.green;
  root.style.setProperty('--accent', a.c);
  root.style.setProperty('--accent-bg', a.bg);
  root.style.setProperty('--accent-border', a.bd);

  const bg = document.getElementById('tactical-bg');
  if (bg) bg.classList.toggle('off', !t.tacticalBg);

  document.body.classList.toggle('hud-overlays-off', !t.hudOverlays);

  document.body.classList.remove('density-sparse', 'density-balanced', 'density-dense');
  document.body.classList.add('density-' + (t.density || 'balanced'));
}
