/**
 * Visual baseline diagnostic.
 *
 * Walks both __baselines__/ and __pending__/ plus the declared STATES
 * config, reports:
 *
 *   declared_no_baseline   — declared state with no approved baseline yet.
 *   pending_no_baseline    — pending capture but never approved.
 *   orphan_baseline        — baseline file with no matching declared state
 *                            (slug renamed or state removed).
 *   orphan_pending         — pending file with no matching declared state.
 *   stale_baseline         — baseline older than STALE_DAYS (default 30).
 *   declared_no_capture    — declared state with neither baseline nor pending.
 *
 * Output is intentionally short-summary-first; raw counts last.
 *
 * Mirrors the cycle_heartbeat_audit / status_cache pattern from Phase 1:
 * summary → diagnostic groups → raw paths.
 */
import { readdirSync, statSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { STATES, stateKey, type SnapshotState } from './states';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const BASE_DIR = resolve(__dirname, '__baselines__');
const PEND_DIR = resolve(__dirname, '__pending__');
const STALE_DAYS = 30;
const STALE_MS = STALE_DAYS * 24 * 60 * 60 * 1000;

function listPngs(dir: string): string[] {
  try {
    return readdirSync(dir).filter(f => f.endsWith('.png'));
  } catch {
    return [];
  }
}

function ageDays(path: string): number {
  return (Date.now() - statSync(path).mtimeMs) / 86_400_000;
}

interface AuditResult {
  declaredNoBaseline: string[];
  declaredNoCapture: string[];
  orphanBaseline: string[];
  orphanPending: string[];
  staleBaseline: Array<{ key: string; ageDays: number }>;
  pendingAwaitingApproval: string[];
  ok: boolean;
}

export function audit(): AuditResult {
  const declaredKeys = new Set<string>(STATES.map((s: SnapshotState) => stateKey(s)));
  const baselineFiles = listPngs(BASE_DIR);
  const pendingFiles = listPngs(PEND_DIR);
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

  const staleBaseline: Array<{ key: string; ageDays: number }> = [];
  for (const k of baselineKeys) {
    const age = ageDays(resolve(BASE_DIR, `${k}.png`));
    if (age > STALE_DAYS) staleBaseline.push({ key: k, ageDays: Math.round(age) });
  }

  const pendingAwaitingApproval = [...pendingKeys].filter(
    (k: string) => declaredKeys.has(k) && !baselineKeys.has(k),
  );

  const ok =
    declaredNoCapture.length === 0 &&
    orphanBaseline.length === 0 &&
    orphanPending.length === 0;

  return {
    declaredNoBaseline,
    declaredNoCapture,
    orphanBaseline,
    orphanPending,
    staleBaseline,
    pendingAwaitingApproval,
    ok,
  };
}

function printAudit(r: AuditResult): void {
  console.log('━━━ visual snapshot audit ━━━');
  console.log(
    `declared:${STATES.length}  baseline:${STATES.length - r.declaredNoBaseline.length}  pending-awaiting-approval:${r.pendingAwaitingApproval.length}  orphans:${r.orphanBaseline.length + r.orphanPending.length}  stale:${r.staleBaseline.length}`,
  );
  console.log('');

  if (r.declaredNoCapture.length) {
    console.log(`◇ declared_no_capture (${r.declaredNoCapture.length}) — never captured:`);
    for (const k of r.declaredNoCapture) console.log(`    ${k}`);
  }
  if (r.pendingAwaitingApproval.length) {
    console.log(`◇ pending_awaiting_approval (${r.pendingAwaitingApproval.length}) — run snapshots:approve <route> <state>:`);
    for (const k of r.pendingAwaitingApproval) console.log(`    ${k}`);
  }
  if (r.orphanBaseline.length) {
    console.log(`◇ orphan_baseline (${r.orphanBaseline.length}) — no matching declared state (slug renamed?):`);
    for (const k of r.orphanBaseline) console.log(`    ${k}`);
  }
  if (r.orphanPending.length) {
    console.log(`◇ orphan_pending (${r.orphanPending.length}):`);
    for (const k of r.orphanPending) console.log(`    ${k}`);
  }
  if (r.staleBaseline.length) {
    console.log(`◇ stale_baseline (${r.staleBaseline.length}) — older than ${STALE_DAYS}d:`);
    for (const s of r.staleBaseline) console.log(`    ${s.key} (${s.ageDays}d)`);
  }

  console.log('');
  console.log(r.ok ? 'status: OK' : 'status: DEGRADED');
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
  printAudit(r);
  process.exit(r.ok ? 0 : 1);
}
