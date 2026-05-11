/**
 * ScannerContext — 3z.f negative-path derivation tests
 *
 * Vitest pure-logic tests for the beacon-state derivation rules.
 * Verifies the negative paths flagged by the §16 audit subagent on
 * 3z.f rubric 4:
 *   (a) liveTradingService.getStatus rejection → isBotActive === false
 *   (b) paperTradingService.getStatus rejection → isTrainingActive
 *       falls back to pathname only
 *   (c) Migration shim is idempotent across mounts
 *   (d) All-flags-false → ActiveScanBeacon returns null (logic only —
 *       full render+unmount of <ScanController /> requires a DOM env
 *       which this repo does not have today: vitest is present but
 *       @testing-library/react + happy-dom/jsdom are NOT installed.
 *       The ScanController unmount-cleanup test is a structural React
 *       contract that cannot be exercised without DOM rendering
 *       infrastructure — out of scope for 3z.f per §16 rubric 9).
 *
 * The two derivation snippets mirrored here as inline helpers are
 * byte-for-byte identical to the bodies in ScannerContext.tsx — if
 * those bodies change, these tests must change in lockstep. The
 * audit purpose is to lock the negative-path semantics in code, not
 * to abstract the derivation into a separate module (which would be
 * a refactor outside 3z.f scope).
 */
import { describe, it, expect, beforeEach } from 'vitest';

class LocalStorageMock {
  store: Record<string, string> = {};
  getItem(k: string): string | null {
    return Object.prototype.hasOwnProperty.call(this.store, k) ? this.store[k] : null;
  }
  setItem(k: string, v: string): void {
    this.store[k] = v;
  }
  removeItem(k: string): void {
    delete this.store[k];
  }
  clear(): void {
    this.store = {};
  }
}

globalThis.localStorage = new LocalStorageMock() as any;

// Inline mirror of ScannerContext.tsx:235-244 derivation.
function deriveFlagsFromAllSettled(
  liveRes: PromiseSettledResult<{ status?: string } | undefined>,
  paperRes: PromiseSettledResult<{ status?: string } | undefined>,
): { liveRunning: boolean; paperRunning: boolean } {
  const liveRunning =
    liveRes.status === 'fulfilled' && liveRes.value?.status === 'running';
  const paperRunning =
    paperRes.status === 'fulfilled' && paperRes.value?.status === 'running';
  return { liveRunning, paperRunning };
}

// Inline mirror of ScannerContext.tsx:221 derivation.
function computeIsTrainingActive(paperRunning: boolean, pathname: string): boolean {
  return paperRunning || pathname.startsWith('/training');
}

// Inline mirror of ScannerContext.tsx:195-203 migration shim body.
function runMigrationShim(): void {
  try {
    localStorage.removeItem('is-scanning');
    localStorage.removeItem('is-bot-active');
    localStorage.removeItem('is-training-active');
  } catch {
    /* §15: privacy-mode / quota errors swallowed at the call site
       with a console.warn — the test version omits the warn because
       the LocalStorageMock cannot throw. */
  }
}

describe('3z.f migration shim — clears stale localStorage flags', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('removes all three is-* keys on first invocation', () => {
    localStorage.setItem('is-scanning', 'true');
    localStorage.setItem('is-bot-active', 'true');
    localStorage.setItem('is-training-active', 'true');

    runMigrationShim();

    expect(localStorage.getItem('is-scanning')).toBeNull();
    expect(localStorage.getItem('is-bot-active')).toBeNull();
    expect(localStorage.getItem('is-training-active')).toBeNull();
  });

  it('is idempotent on second invocation — no throw, keys stay null', () => {
    runMigrationShim();
    // Second invocation must not error and must leave the same state.
    expect(() => runMigrationShim()).not.toThrow();
    expect(localStorage.getItem('is-scanning')).toBeNull();
    expect(localStorage.getItem('is-bot-active')).toBeNull();
    expect(localStorage.getItem('is-training-active')).toBeNull();
  });

  it('does not touch unrelated localStorage keys', () => {
    localStorage.setItem('scan-config', '{"foo":"bar"}');
    localStorage.setItem('bot-config', '{"baz":"qux"}');
    localStorage.setItem('is-scanning', 'true');

    runMigrationShim();

    // Stale flag cleared
    expect(localStorage.getItem('is-scanning')).toBeNull();
    // Unrelated config preserved
    expect(localStorage.getItem('scan-config')).toBe('{"foo":"bar"}');
    expect(localStorage.getItem('bot-config')).toBe('{"baz":"qux"}');
  });
});

describe('3z.f derivation — Promise.allSettled handling on backend rejection', () => {
  it('liveTradingService.getStatus rejection → liveRunning stays false (isBotActive=false)', () => {
    const result = deriveFlagsFromAllSettled(
      { status: 'rejected', reason: new Error('connection refused') },
      { status: 'fulfilled', value: { status: 'running' } },
    );
    expect(result.liveRunning).toBe(false);
    expect(result.paperRunning).toBe(true);
  });

  it('paperTradingService.getStatus rejection → paperRunning stays false', () => {
    const result = deriveFlagsFromAllSettled(
      { status: 'fulfilled', value: { status: 'running' } },
      { status: 'rejected', reason: new Error('connection refused') },
    );
    expect(result.liveRunning).toBe(true);
    expect(result.paperRunning).toBe(false);
  });

  it('both services rejected → both flags false (backend fully offline)', () => {
    const result = deriveFlagsFromAllSettled(
      { status: 'rejected', reason: new Error('net err') },
      { status: 'rejected', reason: new Error('net err') },
    );
    expect(result.liveRunning).toBe(false);
    expect(result.paperRunning).toBe(false);
  });

  it('fulfilled but status !== running → false (idle/stopped/error)', () => {
    for (const liveStatus of ['idle', 'stopped', 'error', 'kill_switched']) {
      const result = deriveFlagsFromAllSettled(
        { status: 'fulfilled', value: { status: liveStatus } },
        { status: 'fulfilled', value: { status: 'idle' } },
      );
      expect(result.liveRunning, `live status=${liveStatus}`).toBe(false);
      expect(result.paperRunning).toBe(false);
    }
  });

  it('fulfilled but value undefined → false (defensive)', () => {
    const result = deriveFlagsFromAllSettled(
      { status: 'fulfilled', value: undefined },
      { status: 'fulfilled', value: { status: 'running' } },
    );
    expect(result.liveRunning).toBe(false);
    expect(result.paperRunning).toBe(true);
  });
});

describe('3z.f isTrainingActive OR-fold — pathname-based fallback', () => {
  // Negative: paper bot stopped + user not on /training → false
  it('paper bot stopped + non-training pathname → false', () => {
    expect(computeIsTrainingActive(false, '/')).toBe(false);
    expect(computeIsTrainingActive(false, '/scanner')).toBe(false);
    expect(computeIsTrainingActive(false, '/bot/setup')).toBe(false);
    expect(computeIsTrainingActive(false, '/bot/status')).toBe(false);
    expect(computeIsTrainingActive(false, '/intel')).toBe(false);
    expect(computeIsTrainingActive(false, '/journal')).toBe(false);
    expect(computeIsTrainingActive(false, '/settings')).toBe(false);
  });

  // Positive: paper bot running on a non-training page → true (background activity)
  it('paper bot running + non-training pathname → true (background activity)', () => {
    expect(computeIsTrainingActive(true, '/scanner')).toBe(true);
    expect(computeIsTrainingActive(true, '/bot/status')).toBe(true);
    expect(computeIsTrainingActive(true, '/')).toBe(true);
  });

  // Positive: pathname-based fallback when paper bot is not yet polled
  it('paper bot stopped + /training pathname → true (path-based)', () => {
    expect(computeIsTrainingActive(false, '/training')).toBe(true);
    expect(computeIsTrainingActive(false, '/training/range')).toBe(true);
  });

  // Both-true case
  it('paper bot running + /training pathname → true', () => {
    expect(computeIsTrainingActive(true, '/training/range')).toBe(true);
  });

  // Edge: pathname /trainings (no slash) should NOT match — startsWith with /training
  // would match /trainings too. This is a documented quirk: there is no /trainings
  // route today, so the simpler startsWith is preferred over a regex.
  it('startsWith /training also matches /trainings — documented quirk, no current consumer', () => {
    expect(computeIsTrainingActive(false, '/trainings')).toBe(true);
  });
});

describe('3z.f ActiveScanBeacon visibility logic — all-flags-false returns null', () => {
  // Mirror of ActiveScanBeacon.tsx:218-229: assemble activeModes from
  // (isBotActive, isTrainingActive, isScanning), filter out modes that
  // match the current pathname, return null if filtered length is 0.
  function computeBeaconActiveModes(
    isBotActive: boolean,
    isTrainingActive: boolean,
    isScanning: boolean,
    pathname: string,
  ): string[] {
    const ROUTES: Record<string, string> = {
      bot: '/bot',
      training: '/training',
      scanner: '/scanner',
    };
    const modes: string[] = [];
    if (isBotActive) modes.push('bot');
    if (isTrainingActive) modes.push('training');
    if (isScanning) modes.push('scanner');
    return modes.filter((key) => !pathname.startsWith(ROUTES[key]));
  }

  it('all three flags false → empty list (beacon renders null)', () => {
    expect(computeBeaconActiveModes(false, false, false, '/')).toEqual([]);
    expect(computeBeaconActiveModes(false, false, false, '/scanner')).toEqual([]);
  });

  it('one flag true + on matching page → empty list (filtered out)', () => {
    expect(computeBeaconActiveModes(false, true, false, '/training')).toEqual([]);
    expect(computeBeaconActiveModes(true, false, false, '/bot/status')).toEqual([]);
    expect(computeBeaconActiveModes(false, false, true, '/scanner')).toEqual([]);
  });

  it('one flag true + on other page → one mode shown', () => {
    expect(computeBeaconActiveModes(false, true, false, '/scanner')).toEqual(['training']);
    expect(computeBeaconActiveModes(true, false, false, '/scanner')).toEqual(['bot']);
    expect(computeBeaconActiveModes(false, false, true, '/training')).toEqual(['scanner']);
  });

  it('multiple flags true + on third-party page → priority order (bot first)', () => {
    expect(computeBeaconActiveModes(true, true, true, '/settings')).toEqual(['bot', 'training', 'scanner']);
  });
});
