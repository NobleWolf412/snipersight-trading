/**
 * Promote __pending__/<key>.png → __baselines__/<key>.png with explicit
 * human approval. No capture happens here; this script ONLY moves files
 * that already exist in __pending__/ from a prior `snapshots:capture` run.
 *
 * Usage:
 *   npm run snapshots:approve -- <route> <state>
 *   npm run snapshots:approve -- /scanner/setup default
 *   npm run snapshots:approve-all                       # interactive
 */
import { existsSync, copyFileSync, readdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createInterface } from 'node:readline/promises';
import { stdin, stdout } from 'node:process';
import { STATES, stateKey, type SnapshotState } from './states';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const BASE_DIR = resolve(__dirname, '__baselines__');
const PEND_DIR = resolve(__dirname, '__pending__');

function approveOne(route: string, state: string): boolean {
  const decl = STATES.find((s: SnapshotState) => s.route === route && s.state === state);
  if (!decl) {
    console.error(`[approve] no declared state for route=${route} state=${state}`);
    return false;
  }
  const key = stateKey(decl);
  const src = resolve(PEND_DIR, `${key}.png`);
  const dst = resolve(BASE_DIR, `${key}.png`);
  if (!existsSync(src)) {
    console.error(`[approve] no pending capture at ${src}; run 'npm run snapshots:capture' first.`);
    return false;
  }
  copyFileSync(src, dst);
  console.log(`[approve] ✔ ${key}`);
  return true;
}

async function approveAllInteractive(): Promise<void> {
  const pendings = readdirSync(PEND_DIR).filter(f => f.endsWith('.png'));
  if (pendings.length === 0) {
    console.log('[approve-all] no pending captures.');
    return;
  }
  console.log(`[approve-all] ${pendings.length} pending captures:`);
  for (const f of pendings) console.log(`  - ${f.replace('.png', '')}`);
  const rl = createInterface({ input: stdin, output: stdout });
  const ans = (await rl.question('\nApprove ALL of these as new baselines? [y/N] ')).trim().toLowerCase();
  rl.close();
  if (ans !== 'y' && ans !== 'yes') {
    console.log('[approve-all] aborted.');
    return;
  }
  let n = 0;
  for (const f of pendings) {
    const src = resolve(PEND_DIR, f);
    const dst = resolve(BASE_DIR, f);
    copyFileSync(src, dst);
    n++;
  }
  console.log(`[approve-all] ✔ ${n} baselines updated.`);
}

async function main() {
  const args = process.argv.slice(2);
  if (args[0] === '--all' || args[0] === 'all') {
    await approveAllInteractive();
    return;
  }
  if (args.length !== 2) {
    console.error('Usage: snapshots:approve <route> <state>   OR   snapshots:approve-all');
    process.exit(2);
  }
  const ok = approveOne(args[0], args[1]);
  process.exit(ok ? 0 : 1);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
