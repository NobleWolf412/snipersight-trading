/**
 * Phase 3f sub-step 0 — assertSymmetricDirectionalKeys test suite.
 *
 * Required coverage (per CLAUDE.md §16 #4 — negative tests paired with
 * positive tests):
 *   1. Positive bull/bear pair: state matrix with both `__long` and
 *      `__short` for the same base passes.
 *   2. Negative bull-only: `__long` present without matching `__short`
 *      throws.
 *   3. Negative bear-only: `__short` present without matching `__long`
 *      throws (mirror of test 2 — symmetric assertion of the symmetric
 *      assertion).
 *   4. Direction-agnostic: state with no `__long`/`__short` suffix
 *      passes regardless.
 *   5. Cross-route guard: `__long` on /scanner does not satisfy
 *      `__short` on /bot — pairs are scoped per-route.
 *   6. Cross-viewport guard: same base/direction at different viewport
 *      pairs are scoped per-viewport (a 1440x900 `__long` does not
 *      satisfy a 768x1024 `__short`).
 *   7. Bare-suffix malformed slug: state slug equal to `__long` (no
 *      base) throws with a clear message.
 *   8. Empty matrix: vacuously passes.
 *   9. Multi-base under same route: each base must independently
 *      balance.
 */
import { describe, test, expect } from 'vitest';
import { assertSymmetricDirectionalKeys } from './states';
import type { SnapshotState } from './states';

const decl = (
  route: string,
  state: string,
  viewport?: { width: number; height: number },
): SnapshotState => (viewport ? { route, state, viewport } : { route, state });

describe('assertSymmetricDirectionalKeys', () => {
  test('balanced bull/bear pair passes', () => {
    expect(() =>
      assertSymmetricDirectionalKeys([
        decl('/scanner', 'card_open__long'),
        decl('/scanner', 'card_open__short'),
      ]),
    ).not.toThrow();
  });

  test('orphan __long without matching __short throws', () => {
    expect(() =>
      assertSymmetricDirectionalKeys([decl('/bot/status', 'position_open__long')]),
    ).toThrow(/missing: __short/);
  });

  test('orphan __short without matching __long throws (mirror)', () => {
    expect(() =>
      assertSymmetricDirectionalKeys([decl('/bot/status', 'position_open__short')]),
    ).toThrow(/missing: __long/);
  });

  test('direction-agnostic states pass through unchecked', () => {
    expect(() =>
      assertSymmetricDirectionalKeys([
        decl('/', 'default'),
        decl('/intel', 'default'),
        decl('/training', 'default'),
      ]),
    ).not.toThrow();
  });

  test('cross-route does not satisfy pairing — pairs are route-scoped', () => {
    expect(() =>
      assertSymmetricDirectionalKeys([
        decl('/scanner', 'card_open__long'),
        decl('/bot/status', 'card_open__short'),
      ]),
    ).toThrow(/missing: __short/);
  });

  test('cross-viewport does not satisfy pairing — pairs are viewport-scoped', () => {
    expect(() =>
      assertSymmetricDirectionalKeys([
        decl('/scanner', 'card_open__long', { width: 1440, height: 900 }),
        decl('/scanner', 'card_open__short', { width: 768, height: 1024 }),
      ]),
    ).toThrow(/missing: __short/);
  });

  test('bare directional suffix slug throws with clear message', () => {
    expect(() =>
      assertSymmetricDirectionalKeys([decl('/scanner', '__long')]),
    ).toThrow(/bare directional suffix/);
  });

  test('empty matrix vacuously passes', () => {
    expect(() => assertSymmetricDirectionalKeys([])).not.toThrow();
  });

  test('multi-base under same route — each base must balance independently', () => {
    // bot_position_open balanced; gauntlet_signal orphan-bear → throws.
    expect(() =>
      assertSymmetricDirectionalKeys([
        decl('/bot/status', 'position_open__long'),
        decl('/bot/status', 'position_open__short'),
        decl('/bot/status', 'gauntlet_signal__short'),
      ]),
    ).toThrow(/gauntlet_signal — present: __short, missing: __long/);
  });

  test('balanced multi-base under same route passes', () => {
    expect(() =>
      assertSymmetricDirectionalKeys([
        decl('/bot/status', 'position_open__long'),
        decl('/bot/status', 'position_open__short'),
        decl('/bot/status', 'gauntlet_signal__long'),
        decl('/bot/status', 'gauntlet_signal__short'),
      ]),
    ).not.toThrow();
  });

  test('mixed direction-agnostic + balanced directional — both classes coexist', () => {
    expect(() =>
      assertSymmetricDirectionalKeys([
        decl('/', 'default'),
        decl('/scanner', 'default'),
        decl('/scanner', 'card_open__long'),
        decl('/scanner', 'card_open__short'),
        decl('/bot/status', 'default'),
      ]),
    ).not.toThrow();
  });
});
