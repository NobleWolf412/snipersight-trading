/**
 * Snapshot state matrix.
 *
 * Each entry declares one captureable state of the app. The capture spec
 * iterates this list, sets up each state, waits for `data-snapshot-ready`,
 * and writes a PNG keyed by `{route}__{state}__{viewport}.png`.
 *
 * Schema/state symmetry rule (verified by audit.ts):
 *   - every captured PNG must match exactly one declared state
 *   - every declared state must have either an approved baseline or a pending
 *   - no duplicate {route, state, viewport} triples
 *
 * Keep `state` slugs lowercase, hyphenated, and stable. Renaming a slug
 * orphans the existing baseline (audit will flag it).
 */
import type { Page } from '@playwright/test';

export interface SnapshotState {
  /** Route path (matches react-router). */
  route: string;
  /** State slug — lowercase, hyphenated, stable. */
  state: string;
  /** Setup callback runs after navigation, before screenshot. */
  setup?: (page: Page) => Promise<void>;
  /** Optional viewport override (default 1440×900). */
  viewport?: { width: number; height: number };
  /** Optional per-state diff threshold override. */
  threshold?: { perPixel?: number; regionPctOfViewport?: number };
}

export const DEFAULT_VIEWPORT = { width: 1440, height: 900 };

/**
 * Default thresholds. Both must pass for a state to be considered unchanged.
 *   - perPixel: pixelmatch diff ratio (1.0 = max difference per channel).
 *               0.1 tolerates antialiasing / sub-pixel font rendering.
 *   - regionPctOfViewport: any contiguous changed region larger than this
 *               fraction of viewport area = fail. Catches real layout shifts
 *               that per-pixel alone misses.
 */
export const DEFAULT_THRESHOLD = {
  perPixel: 0.1,
  regionPctOfViewport: 0.001, // 0.1% of viewport area
};

/**
 * Helper: composite key used for filenames and dedup.
 */
export function stateKey(s: SnapshotState): string {
  const vp = s.viewport ?? DEFAULT_VIEWPORT;
  const safeRoute = s.route.replace(/^\//, '').replace(/\//g, '_') || 'root';
  return `${safeRoute}__${s.state}__${vp.width}x${vp.height}`;
}

/**
 * The full state matrix. Adjust counts as page rewrites land.
 *
 * Phase 3 plan reference (from peppy-sniffing-owl.md):
 *   Landing 1, Settings 5, Training 3, Intel 3, Scanner 4, Journal 5, Bot 10.
 *   31 states total at full coverage.
 *
 * Ship lean: start with the "default" state of each route; add more states
 * as each Phase 3 sub-step lands. Pending future entries are commented but
 * present so the structure is visible.
 */
export const STATES: SnapshotState[] = [
  // ─── Landing (1 state) ────────────────────────────────────────────────
  {
    route: '/',
    state: 'default',
  },

  // ─── Settings (5 planned, 1 shipped) ──────────────────────────────────
  {
    route: '/settings',
    state: 'default',
  },
  // { route: '/settings', state: 'api-keys-panel-open', setup: ... },
  // { route: '/settings', state: 'notifications-panel', setup: ... },
  // { route: '/settings', state: 'danger-zone', setup: ... },
  // { route: '/settings', state: 'save-flash-visible', setup: ... },

  // ─── Training (3 planned, 1 shipped) ──────────────────────────────────
  {
    route: '/training',
    state: 'default',
  },

  // ─── Intel (3 planned, 1 shipped) ─────────────────────────────────────
  {
    route: '/intel',
    state: 'default',
  },

  // ─── Scanner (4 planned, 1 shipped — current ScannerSetup route) ──────
  {
    route: '/scanner/setup',
    state: 'default',
  },

  // ─── Journal (5 planned, 1 shipped) ───────────────────────────────────
  {
    route: '/journal',
    state: 'default',
  },

  // ─── Bot (10 planned, 2 shipped — current /bot/setup + /bot/status) ───
  {
    route: '/bot/setup',
    state: 'default',
  },
  {
    route: '/bot/status',
    state: 'default',
  },
];

/**
 * Runtime guard: assert no duplicate keys at config-load time.
 * Called from setup.ts before any capture runs.
 */
export function assertUniqueStateKeys(states: SnapshotState[]): void {
  const seen = new Set<string>();
  const dups: string[] = [];
  for (const s of states) {
    const k = stateKey(s);
    if (seen.has(k)) dups.push(k);
    seen.add(k);
  }
  if (dups.length) {
    throw new Error(
      `[snapshot states] duplicate state keys detected: ${dups.join(', ')}\n` +
        `Each {route, state, viewport} triple must be unique.`,
    );
  }
}

/**
 * Symmetry standing-fix guard (CLAUDE.md §10 #3).
 *
 * Any state slug whose suffix is `__long` or `__short` MUST have its
 * matching counterpart declared in the same matrix, on the same route,
 * at the same viewport. This prevents asymmetric coverage at the visual
 * layer — e.g. shipping a `bot_position_open__long` baseline with no
 * `bot_position_open__short` to compare against.
 *
 * Asymmetry detected at config-load time = setup failure (loud). Direction-
 * agnostic states (no `__long`/`__short` suffix) are unaffected.
 *
 * Lands as Phase 3f sub-step 0, before any Scanner page edits, per the
 * peppy-sniffing-owl plan's symmetry-config-load assertion pin.
 */
export function assertSymmetricDirectionalKeys(states: SnapshotState[]): void {
  const SUFFIX_LONG = '__long';
  const SUFFIX_SHORT = '__short';

  // Index all directional states by {route, viewport, base-slug-without-suffix}.
  // Each entry tracks which directions are present.
  type Bucket = { long?: SnapshotState; short?: SnapshotState };
  const buckets = new Map<string, Bucket>();

  const bucketKey = (s: SnapshotState, baseSlug: string) => {
    const vp = s.viewport ?? DEFAULT_VIEWPORT;
    return `${s.route}::${vp.width}x${vp.height}::${baseSlug}`;
  };

  for (const s of states) {
    let baseSlug: string | null = null;
    let dir: 'long' | 'short' | null = null;
    if (s.state.endsWith(SUFFIX_LONG)) {
      baseSlug = s.state.slice(0, -SUFFIX_LONG.length);
      dir = 'long';
    } else if (s.state.endsWith(SUFFIX_SHORT)) {
      baseSlug = s.state.slice(0, -SUFFIX_SHORT.length);
      dir = 'short';
    }
    if (dir == null) continue; // not a directional state, skip
    if (baseSlug == null || baseSlug.length === 0) {
      // A state whose entire slug is `__long` (or `__short`) is malformed —
      // there's no base to pair against. Loud-fail.
      throw new Error(
        `[snapshot states] state slug "${s.state}" is bare directional suffix; ` +
          `expected "<base>__long" or "<base>__short".`,
      );
    }
    const k = bucketKey(s, baseSlug);
    const b = buckets.get(k) ?? {};
    if (b[dir]) {
      // Two states with the same {route, viewport, base, direction} — that's
      // a duplicate, but uniqueness is enforced separately by
      // assertUniqueStateKeys. Don't double-report; just keep the first.
    } else {
      b[dir] = s;
    }
    buckets.set(k, b);
  }

  // Every bucket must have BOTH long AND short present.
  const missing: string[] = [];
  for (const [k, b] of buckets) {
    if (!b.long) {
      missing.push(`${k} — present: __short, missing: __long`);
    }
    if (!b.short) {
      missing.push(`${k} — present: __long, missing: __short`);
    }
  }

  if (missing.length) {
    throw new Error(
      `[snapshot states] asymmetric directional state matrix — ` +
        `each __long/__short pair must be declared together.\n` +
        missing.map((m) => `  • ${m}`).join('\n') +
        `\n\nDocumented standing fix: CLAUDE.md §10 #3 (bull/bear symmetry). ` +
        `Asymmetry at the visual layer defeats the symmetry guarantee. ` +
        `Either declare the missing direction OR remove the orphan suffix.`,
    );
  }
}
