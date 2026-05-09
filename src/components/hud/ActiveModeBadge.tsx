// HUD ActiveModeBadge — persistent topbar badge showing the current
// scanner mode (Phase 5 sub-step 2 — plan §2/§5b).
//
// Source-of-truth resolution:
//   1. `selectedMode.name` from ScannerContext (set after the backend
//      /api/scanner/modes fetch resolves — this is the authoritative
//      value the bot is actually using).
//   2. `scanConfig.sniperMode` (operator's last-saved choice in
//      localStorage) as a fallback while modes-fetch is in flight or if
//      the backend is unreachable. ScannerContext only writes
//      selectedMode in the success path, so without this fallback the
//      badge would render `MODE · —` whenever the modes endpoint 500s
//      — exactly when the operator most needs to know which mode is
//      configured.
//   3. `—` only if neither source has a value (cold-start, no
//      localStorage entry, no backend).
//
// The badge is display-only — clicking it does NOT mutate the mode; the
// picker on /scanner is the only mutation surface, so the badge can
// never drift from what the bot will use on the next cycle.
//
// Mode → Chip kind mapping is kept type-safe against `ChipKind`:
//   overwatch → blue (cyan is unavailable as a typed ChipKind, blue is
//                     the closest macro-surveillance accent the type
//                     allows)
//   strike    → amber
//   surgical  → red
//   stealth   → green

import { Chip, type ChipKind } from './Chip';
import { useScanner } from '@/context/ScannerContext';

const MODE_KIND: Record<string, ChipKind> = {
  overwatch: 'blue',
  strike: 'amber',
  surgical: 'red',
  stealth: 'green',
};

export function ActiveModeBadge() {
  const { selectedMode, scanConfig } = useScanner();
  const name = (selectedMode?.name || scanConfig?.sniperMode || '').toLowerCase();
  // Unknown / legacy mode names (e.g. recon/ghost/custom from older
  // SniperMode union members) fall through to 'accent' so the badge
  // never renders an unkinded chip — keeps the visual cue present even
  // if someone reintroduces a non-canonical mode upstream.
  const kind = MODE_KIND[name] || 'accent';
  const label = name ? name.toUpperCase() : '—';
  return <Chip kind={kind}>MODE · {label}</Chip>;
}
