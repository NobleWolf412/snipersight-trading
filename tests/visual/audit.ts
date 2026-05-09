/**
 * Visual baseline diagnostic.
 *
 * Walks both __baselines__/ and __pending__/ plus the declared STATES
 * config and watch-paths, reports six categories:
 *
 *   declared_no_baseline      — declared state with no approved baseline yet.
 *   declared_no_capture       — declared state with neither baseline nor pending.
 *   pending_awaiting_approval — pending capture not yet approved (informational).
 *   orphan_baseline           — baseline file with no matching declared state.
 *   orphan_pending            — pending file with no matching declared state.
 *   stale_baseline            — baseline older than STALE_BASELINE_DAYS (default 30).
 *   stale_pending             — pending older than the most recent watch-path mtime.
 *                               (Captured before a shared-chrome / theme / capture
 *                               -setup change; re-capture before next page rewrite.)
 *
 * Status taxonomy (3 outcomes, worst-wins):
 *
 *   OK                 — no problems detected.
 *   AWAITING_APPROVAL  — legitimate first-run / mid-rewrite state. Pending PNGs
 *                        exist but no orphans / staleness / declared-without-capture.
 *                        Exit 0. Not a failure. Pinned now to avoid §15 noise tax.
 *   DEGRADED           — actual problem requiring attention. Exit 1.
 *
 * Output ordering: short summary first → diagnostic groups → status line last.
 * Mirrors the cycle_heartbeat_audit / status_cache pattern from Phase 1.
 */
import { readdirSync, statSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { STATES, stateKey, type SnapshotState } from './states';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = resolve(__dirname, '..', '..');
const BASE_DIR = resolve(__dirname, '__baselines__');
const PEND_DIR = resolve(__dirname, '__pending__');
const STALE_BASELINE_DAYS = 30;

/**
 * Files whose mtime invalidates ALL existing __pending__/ captures.
 * When any of these change, every pending PNG is presumed stale until
 * re-captured. Page-specific files are NOT in this list — those only
 * invalidate their own page's pending, which gets re-captured anyway
 * as part of that page's rewrite sub-step.
 *
 * Constant (not magic strings) so that drift during Phase 7 Tailwind
 * eject is a deliberate edit, not a silent regression.
 *
 * Pattern: paths ending `/**\/*` are treated as recursive globs of that
 * directory. Plain paths are statSync'd directly.
 */
export const STALE_PENDING_WATCH_PATHS: readonly string[] = [
  'src/components/hud/**/*',
  'src/styles/hud.css',
  'src/index.css',
  'tests/visual/setup.ts',
  'tests/visual/fixtures/**/*',
];

export type AuditStatus = 'OK' | 'AWAITING_APPROVAL' | 'DEGRADED';

export interface AuditResult {
  declaredNoBaseline: string[];
  declaredNoCapture: string[];
  pendingAwaitingApproval: string[];
  orphanBaseline: string[];
  orphanPending: string[];
  staleBaseline: Array<{ key: string; ageDays: number }>;
  stalePending: Array<{ key: string; ageMs: number; latestWatchPathMtime: number }>;
  status: AuditStatus;
}

export interface AuditOpts {
  /** Override baseline directory (default: tests/visual/__baselines__). */
  baseDir?: string;
  /** Override pending directory (default: tests/visual/__pending__). */
  pendDir?: string;
  /** Override repo root for resolving STALE_PENDING_WATCH_PATHS (default: repo root). */
  watchRoot?: string;
  /** Override declared states (default: STATES). */
  declaredStates?: ReadonlyArray<SnapshotState>;
  /** Override "now" for deterministic age computation (default: Date.now()). */
  now?: number;
  /** Override stale-baseline threshold in days (default: 30). */
  staleBaselineDays?: number;
}

function listPngs(dir: string): string[] {
  try {
    return readdirSync(dir).filter(f => f.endsWith('.png'));
  } catch {
    return [];
  }
}

function safeMtimeMs(p: string): number {
  try {
    return statSync(p).mtimeMs;
  } catch {
    return 0;
  }
}

/**
 * Recursively walk a directory and return the maximum mtime found.
 * Returns 0 if the directory does not exist.
 */
function walkMaxMtime(dir: string): number {
  let max = 0;
  try {
    const entries = readdirSync(dir, { withFileTypes: true });
    for (const e of entries) {
      const full = resolve(dir, e.name);
      if (e.isDirectory()) {
        max = Math.max(max, walkMaxMtime(full));
      } else if (e.isFile()) {
        max = Math.max(max, safeMtimeMs(full));
      }
    }
  } catch {
    // dir missing → 0
  }
  return max;
}

/**
 * Resolve a watch pattern against the repo root and return the most
 * recent file mtime under it. Returns 0 if no matching file exists
 * (treated as "never modified", which means it doesn't trigger
 * stale_pending — correct: a deleted dependency shouldn't fire false-stale).
 */
function watchPatternMtime(repoRoot: string, pattern: string): number {
  if (pattern.endsWith('/**/*')) {
    const dir = pattern.slice(0, -('/**/*'.length));
    return walkMaxMtime(resolve(repoRoot, dir));
  }
  return safeMtimeMs(resolve(repoRoot, pattern));
}

/**
 * Compute the latest mtime across all configured watch paths.
 * Public for testability — same value the audit uses when classifying stale_pending.
 */
export function latestWatchPathMtime(repoRoot: string = REPO_ROOT): number {
  let max = 0;
  for (const p of STALE_PENDING_WATCH_PATHS) {
    max = Math.max(max, watchPatternMtime(repoRoot, p));
  }
  return max;
}

export function audit(opts: AuditOpts = {}): AuditResult {
  const baseDir = opts.baseDir ?? BASE_DIR;
  const pendDir = opts.pendDir ?? PEND_DIR;
  const watchRoot = opts.watchRoot ?? REPO_ROOT;
  const states = opts.declaredStates ?? STATES;
  const now = opts.now ?? Date.now();
  const staleDays = opts.staleBaselineDays ?? STALE_BASELINE_DAYS;

  const declaredKeys = new Set<string>(states.map((s: SnapshotState) => stateKey(s)));
  const baselineFiles = listPngs(baseDir);
  const pendingFiles = listPngs(pendDir);
  const baselineKeys = new Set<string>(baselineFiles.map((f: string) => f.replace(/\.png$/, '')));
  const pendingKeys = new Set<string>(pendingFiles.map((f: string) => f.replace(/\.png$/, '')));

  const declaredNoBaseline: string[] = [];
  const declaredNoCapture: string[] = [];
  for (const k of declaredKeys) {
    if (!baselineKeys.has(k)) declaredNoBaseline.push(k);
    if (!baselineKeys.has(k) && !pendingKeys.has(k)) declaredNoCapture.push(k);
  }

  const orphanBaseline = [...baselineKeys].filter((k: string) => !declaredKeys.has(k));
  const orphanPending = [...pendingKeys].filter((k: string) => !declaredKeys.has(k));

  const staleBaselineMs = staleDays * 86_400_000;
  const staleBaseline: Array<{ key: string; ageDays: number }> = [];
  for (const k of baselineKeys) {
    const age = now - safeMtimeMs(resolve(baseDir, `${k}.png`));
    if (age > staleBaselineMs) {
      staleBaseline.push({ key: k, ageDays: Math.round(age / 86_400_000) });
    }
  }

  // Stale pending: any pending PNG older than the most recent watch-path mtime.
  // 0 watch-path mtime (all paths missing) → no entries can be stale (vacuous true).
  const watchMtime = latestWatchPathMtime(watchRoot);
  const stalePending: Array<{ key: string; ageMs: number; latestWatchPathMtime: number }> = [];
  if (watchMtime > 0) {
    for (const k of pendingKeys) {
      const m = safeMtimeMs(resolve(pendDir, `${k}.png`));
      if (m > 0 && m < watchMtime) {
        stalePending.push({ key: k, ageMs: watchMtime - m, latestWatchPathMtime: watchMtime });
      }
    }
  }

  const pendingAwaitingApproval = [...pendingKeys].filter(
    (k: string) => declaredKeys.has(k) && !baselineKeys.has(k),
  );

  // Status precedence (worst-wins).
  let status: AuditStatus;
  const hasDegraded =
    declaredNoCapture.length > 0 ||
    orphanBaseline.length > 0 ||
    orphanPending.length > 0 ||
    staleBaseline.length > 0 ||
    stalePending.length > 0;
  if (hasDegraded) {
    status = 'DEGRADED';
  } else if (pendingAwaitingApproval.length > 0) {
    status = 'AWAITING_APPROVAL';
  } else {
    status = 'OK';
  }

  return {
    declaredNoBaseline,
    declaredNoCapture,
    pendingAwaitingApproval,
    orphanBaseline,
    orphanPending,
    staleBaseline,
    stalePending,
    status,
  };
}

export function exitCodeForStatus(s: AuditStatus): 0 | 1 {
  return s === 'DEGRADED' ? 1 : 0;
}

function printAudit(r: AuditResult, declaredCount: number): void {
  console.log('━━━ visual snapshot audit ━━━');
  console.log(
    `declared:${declaredCount}  baseline:${declaredCount - r.declaredNoBaseline.length}` +
      `  pending-awaiting-approval:${r.pendingAwaitingApproval.length}` +
      `  orphans:${r.orphanBaseline.length + r.orphanPending.length}` +
      `  stale-baseline:${r.staleBaseline.length}` +
      `  stale-pending:${r.stalePending.length}`,
  );
  console.log('');

  if (r.declaredNoCapture.length) {
    console.log(`◇ declared_no_capture (${r.declaredNoCapture.length}) — never captured:`);
    for (const k of r.declaredNoCapture) console.log(`    ${k}`);
  }
  if (r.pendingAwaitingApproval.length) {
    console.log(
      `◇ pending_awaiting_approval (${r.pendingAwaitingApproval.length}) — run snapshots:approve <route> <state>:`,
    );
    for (const k of r.pendingAwaitingApproval) console.log(`    ${k}`);
  }
  if (r.orphanBaseline.length) {
    console.log(
      `◇ orphan_baseline (${r.orphanBaseline.length}) — no matching declared state (slug renamed?):`,
    );
    for (const k of r.orphanBaseline) console.log(`    ${k}`);
  }
  if (r.orphanPending.length) {
    console.log(`◇ orphan_pending (${r.orphanPending.length}):`);
    for (const k of r.orphanPending) console.log(`    ${k}`);
  }
  if (r.staleBaseline.length) {
    console.log(`◇ stale_baseline (${r.staleBaseline.length}) — older than ${STALE_BASELINE_DAYS}d:`);
    for (const s of r.staleBaseline) console.log(`    ${s.key} (${s.ageDays}d)`);
  }
  if (r.stalePending.length) {
    const watched = r.stalePending[0]!.latestWatchPathMtime;
    console.log(
      `◇ stale_pending (${r.stalePending.length}) — captured before latest shared-chrome mtime ${new Date(watched).toISOString()}; re-capture:`,
    );
    for (const s of r.stalePending) {
      const mins = Math.round(s.ageMs / 60_000);
      console.log(`    ${s.key} (${mins}m behind)`);
    }
  }

  console.log('');
  console.log(`status: ${r.status}`);
}

// Cross-platform main-module check (Windows file:// has 3 slashes + drive letter).
const isMain = (() => {
  try {
    const argvUrl = pathToFileURL(process.argv[1]).href;
    return import.meta.url === argvUrl;
  } catch {
    return false;
  }
})();

if (isMain) {
  const r = audit();
  printAudit(r, STATES.length);
  process.exit(exitCodeForStatus(r.status));
}
