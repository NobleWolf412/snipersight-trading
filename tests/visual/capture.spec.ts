/**
 * Visual snapshot capture spec.
 *
 * For each declared SnapshotState:
 *   1. Install capture hooks (animation freeze + network mocks).
 *   2. Navigate to the route at the configured viewport.
 *   3. Run the state-specific setup() if any.
 *   4. Wait for snapshot-ready (data-snapshot-ready or networkidle).
 *   5. Capture full-page PNG to __pending__/.
 *   6. If an approved baseline exists in __baselines__/, diff against it.
 *      - Pass → leave pending in place but flag SAME-AS-BASELINE.
 *      - Fail → leave pending + emit diff PNG; the test FAILS.
 *      - Missing baseline → test FAILS with "no approved baseline" message;
 *        operator must run `npm run snapshots:approve <route> <state>` to promote.
 *
 * No auto-promotion. Ever.
 */
import { test, expect, type Page } from '@playwright/test';
import { existsSync, mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  STATES,
  DEFAULT_VIEWPORT,
  DEFAULT_THRESHOLD,
  stateKey,
  assertUniqueStateKeys,
  type SnapshotState,
} from './states';
import { installCaptureHooks, waitForSnapshotReady } from './setup';
import { diffPngs } from './diff';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const BASE_DIR = resolve(__dirname, '__baselines__');
const PEND_DIR = resolve(__dirname, '__pending__');
const REPORT_DIR = resolve(__dirname, '__report__');

mkdirSync(BASE_DIR, { recursive: true });
mkdirSync(PEND_DIR, { recursive: true });
mkdirSync(REPORT_DIR, { recursive: true });

assertUniqueStateKeys(STATES);

type StateRecord = {
  key: string;
  state: SnapshotState;
  status: 'baseline-missing' | 'pass' | 'fail' | 'capture-error';
  perPixelDiffPct?: number;
  largestRegionPctOfViewport?: number;
  reasons?: string[];
  baselinePath?: string;
  pendingPath: string;
  diffPath?: string;
  explicitReady?: boolean;
};

const RECORDS: StateRecord[] = [];

function writeReport() {
  const summary = RECORDS.map(r => ({
    key: r.key,
    status: r.status,
    perPixelDiffPct: r.perPixelDiffPct,
    largestRegionPctOfViewport: r.largestRegionPctOfViewport,
    reasons: r.reasons ?? [],
    explicitReady: r.explicitReady,
  }));
  writeFileSync(resolve(REPORT_DIR, 'summary.json'), JSON.stringify(summary, null, 2));
}

test.describe('visual snapshots', () => {
  test.afterAll(() => {
    writeReport();
  });

  for (const s of STATES) {
    const key = stateKey(s);
    const vp = s.viewport ?? DEFAULT_VIEWPORT;
    const threshold = {
      perPixel: s.threshold?.perPixel ?? DEFAULT_THRESHOLD.perPixel,
      regionPctOfViewport:
        s.threshold?.regionPctOfViewport ?? DEFAULT_THRESHOLD.regionPctOfViewport,
    };
    const baselinePath = resolve(BASE_DIR, `${key}.png`);
    const pendingPath = resolve(PEND_DIR, `${key}.png`);
    const diffPath = resolve(REPORT_DIR, `${key}.diff.png`);

    test(`${key}`, async ({ page }) => {
      await page.setViewportSize(vp);
      await installCaptureHooks(page);

      let explicitReady = false;
      try {
        await page.goto(s.route, { waitUntil: 'domcontentloaded', timeout: 15_000 });
        if (s.setup) await s.setup(page);
        ({ explicitReady } = await waitForSnapshotReady(page));
        await page.screenshot({ path: pendingPath, fullPage: true });
      } catch (err) {
        const rec: StateRecord = {
          key,
          state: s,
          status: 'capture-error',
          reasons: [`capture threw: ${(err as Error).message}`],
          pendingPath,
          explicitReady: false,
        };
        RECORDS.push(rec);
        throw err;
      }

      if (!existsSync(baselinePath)) {
        const rec: StateRecord = {
          key,
          state: s,
          status: 'baseline-missing',
          reasons: [`no approved baseline; run: npm run snapshots:approve ${s.route} ${s.state}`],
          pendingPath,
          explicitReady,
        };
        RECORDS.push(rec);
        // Capture succeeded; PNG is in __pending__/. The test FAILS so CI
        // surfaces "this state needs approval" — the operator runs
        // snapshots:approve to promote pending → baseline. Per §11
        // discipline: fail loud, not silently. Audit script distinguishes
        // first-run (AWAITING_APPROVAL) from real DEGRADED separately.
        expect(
          existsSync(baselinePath),
          `no approved baseline for ${key}; pending captured at ${pendingPath}. ` +
            `Run: npm run snapshots:approve ${s.route} ${s.state}`,
        ).toBe(true);
        return;
      }

      const result = diffPngs({
        baselinePath,
        currentPath: pendingPath,
        diffOutputPath: diffPath,
        perPixelThreshold: threshold.perPixel,
        regionPctOfViewport: threshold.regionPctOfViewport,
      });

      const rec: StateRecord = {
        key,
        state: s,
        status: result.pass ? 'pass' : 'fail',
        perPixelDiffPct: result.perPixelDiffPct,
        largestRegionPctOfViewport: result.largestRegionPctOfViewport,
        reasons: result.reasons,
        baselinePath,
        pendingPath,
        diffPath: result.diffPngPath,
        explicitReady,
      };
      RECORDS.push(rec);

      expect(result.pass, result.reasons.join('; ')).toBe(true);
    });
  }
});
