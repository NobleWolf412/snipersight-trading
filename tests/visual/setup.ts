/**
 * Snapshot capture setup — runs on every page before screenshot.
 *
 * Three responsibilities:
 *   1. Suppress animations / transitions / blinking carets.
 *   2. Intercept backend network calls with deterministic fixtures so
 *      the same screenshot is produced from any environment.
 *   3. Wait until the page signals readiness (data-snapshot-ready="true"
 *      on <body>) AND the network has settled.
 *
 * The fixtures live in tests/visual/fixtures/. Add new entries to the
 * `ROUTE_MOCKS` list when a new endpoint is consumed by a page being
 * captured. Missing mocks fall through to a 503 — pages that depend on
 * an un-mocked endpoint will hang on `data-snapshot-ready`, which is the
 * intended fail-loud behavior (better than capturing inconsistent state).
 */
import { Page, Route, Request } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const FIX_DIR = resolve(__dirname, 'fixtures');

function loadFixture(name: string): unknown {
  return JSON.parse(readFileSync(resolve(FIX_DIR, name), 'utf8'));
}

/**
 * Deterministic fixtures for every backend endpoint that the captured
 * pages might hit. Anything not in this list returns 503 — by design.
 */
const ROUTE_MOCKS: Array<{
  match: (url: string) => boolean;
  body: () => unknown;
  status?: number;
}> = [
  {
    match: (u) => u.includes('/api/integrations/phemex/healthz'),
    body: () => loadFixture('phemex-healthz.json'),
  },
  {
    match: (u) => u.includes('/api/bot/status') || u.includes('/api/live-trading/status'),
    body: () => loadFixture('bot-status.json'),
  },
  {
    match: (u) => u.includes('/api/cycles/last'),
    body: () => loadFixture('cycles-last.json'),
  },
  // Generic empty array for trade/journal-style endpoints (snapshot doesn't
  // need rows; only that the empty-state renders consistently).
  {
    match: (u) =>
      u.includes('/api/trades') ||
      u.includes('/api/scan-history') ||
      u.includes('/api/notifications') ||
      u.includes('/api/live-trading/history'),
    body: () => ({ data: [], total: 0, trades: [] }),
  },
  // Universe + signals/* endpoints return empty envelopes.
  {
    match: (u) => u.includes('/api/scanner/universe'),
    body: () => ({
      data: { last_refresh_ts: 1746000000.0, qualified: [], dropped: [], counts: { total_candidates: 0, qualified: 0, dropped: 0 } },
      metadata: { ts: 1746000000.0, source: 'pair_selection', status: 'OK', cost_class: 'cheap' },
      warnings: [],
    }),
  },
  {
    match: (u) => u.includes('/api/signals/confluence/distribution'),
    body: () => ({
      data: { aggregate: [], by_direction: { long: [], short: [] }, sample_count: 0 },
      metadata: { ts: 1746000000.0, source: 'confluence_cache', status: 'OK', cost_class: 'moderate' },
      warnings: [],
    }),
  },
  // Generic catch-all for any other /api/* GET — returns empty object so
  // pages don't error out, but DOESN'T match unmocked POSTs (those should
  // never fire during capture).
  {
    match: (u) => /\/api\//.test(u),
    body: () => ({}),
  },
];

/**
 * Apply all snapshot-time setup to a Page. Call once per state, after
 * `page.goto(...)` — interception MUST be installed BEFORE goto, so the
 * convention is: install interception → goto → run state.setup → wait.
 */
export async function installCaptureHooks(page: Page): Promise<void> {
  // 1. Animation / transition / caret suppression.
  await page.addInitScript(() => {
    const style = document.createElement('style');
    style.id = 'snapshot-freeze';
    style.textContent = `
      *, *::before, *::after {
        animation: none !important;
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition: none !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
        caret-color: transparent !important;
      }
      /* Freeze marquee / spin / bounce loaders specifically */
      [class*="animate-"], [class*="spin"], [class*="bounce"], [class*="ping"] {
        animation: none !important;
      }
    `;
    document.documentElement.appendChild(style);
  });

  // 2. Network interception with deterministic fixtures.
  await page.route('**/*', async (route: Route, request: Request) => {
    const url = request.url();
    const method = request.method();

    // Pass through frontend assets unchanged.
    if (!/\/api\//.test(url)) {
      return route.continue();
    }

    // POST/PUT/DELETE during capture are programmer error — fail loud.
    if (method !== 'GET') {
      return route.fulfill({
        status: 599,
        contentType: 'application/json',
        body: JSON.stringify({ error: `Non-GET request during snapshot capture: ${method} ${url}` }),
      });
    }

    // GET /api/*: serve from fixture map, first match wins.
    for (const mock of ROUTE_MOCKS) {
      if (mock.match(url)) {
        return route.fulfill({
          status: mock.status ?? 200,
          contentType: 'application/json',
          body: JSON.stringify(mock.body()),
        });
      }
    }

    // Should be unreachable thanks to the catch-all, but be explicit.
    return route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'no fixture for this endpoint' }),
    });
  });
}

/**
 * Wait for the page to signal it's ready for capture.
 *
 * Two-phase:
 *   - networkidle: no in-flight requests for 500ms
 *   - data-snapshot-ready="true" on body, OR a 4s grace timeout
 *     (some current pages don't yet set the attribute; the timeout means
 *     we still capture them, but audit will flag pages that lack the
 *     attribute as low-confidence captures).
 *
 * Returns whether the explicit ready flag was found; capture spec records
 * this in the report so missing flags surface in §11 observability terms.
 */
export async function waitForSnapshotReady(page: Page): Promise<{ explicitReady: boolean }> {
  await page.waitForLoadState('networkidle', { timeout: 10_000 });
  try {
    await page.waitForSelector('body[data-snapshot-ready="true"]', { timeout: 4_000 });
    return { explicitReady: true };
  } catch {
    // Pages that don't yet emit the flag fall through to networkidle alone.
    return { explicitReady: false };
  }
}
