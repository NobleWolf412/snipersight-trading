/**
 * Phase 3a sub-step 0 — audit.ts test suite.
 *
 * Required coverage (per audit-discipline pin):
 *   1. Status taxonomy regression — OK / AWAITING_APPROVAL / DEGRADED transitions
 *      on the right inputs, with the right exit codes.
 *   2. All five existing categories continue to behave (regression check).
 *   3. stale_pending positive: pending older than watch-path mtime → fires.
 *   4. stale_pending negative: pending newer than all watch paths → does not fire.
 *   5. stale_pending edge: empty __pending__/ → no fire (vacuous).
 *   6. stale_pending edge: missing watch path → don't crash; treat as mtime=0
 *      (so a deleted dependency doesn't fire false-stale across the board).
 *
 * Tests inject deterministic state via tmp dirs + fs.utimesSync, never touching
 * real __baselines__/ or __pending__/.
 */
import { describe, test, expect, beforeEach, afterEach } from 'vitest';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, utimesSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { audit, exitCodeForStatus, latestWatchPathMtime, STALE_PENDING_WATCH_PATHS } from './audit';
import type { SnapshotState } from './states';

const FIXED_NOW = 1_700_000_000_000; // 2023-11-14
const ONE_DAY_MS = 86_400_000;

function freshTmp(): string {
  return mkdtempSync(resolve(tmpdir(), 'audit-test-'));
}

function dropPng(dir: string, key: string, mtimeMs: number): string {
  const p = resolve(dir, `${key}.png`);
  writeFileSync(p, Buffer.from([0x89, 0x50, 0x4e, 0x47])); // PNG magic header — content irrelevant
  const t = mtimeMs / 1000;
  utimesSync(p, t, t);
  return p;
}

const decl = (route: string, state: string): SnapshotState => ({ route, state });

describe('audit — status taxonomy', () => {
  let baseDir: string;
  let pendDir: string;
  let watchRoot: string;

  beforeEach(() => {
    baseDir = freshTmp();
    pendDir = freshTmp();
    watchRoot = freshTmp();
  });

  afterEach(() => {
    rmSync(baseDir, { recursive: true, force: true });
    rmSync(pendDir, { recursive: true, force: true });
    rmSync(watchRoot, { recursive: true, force: true });
  });

  test('OK — every declared has baseline, no pending, no orphans', () => {
    const states = [decl('/', 'default')];
    dropPng(baseDir, 'root__default__1440x900', FIXED_NOW - ONE_DAY_MS);
    const r = audit({ baseDir, pendDir, watchRoot, declaredStates: states, now: FIXED_NOW });
    expect(r.status).toBe('OK');
    expect(exitCodeForStatus(r.status)).toBe(0);
  });

  test('AWAITING_APPROVAL — pending exists, no orphans/stale, declared_no_capture==0', () => {
    const states = [decl('/', 'default')];
    dropPng(pendDir, 'root__default__1440x900', FIXED_NOW - 60_000);
    const r = audit({ baseDir, pendDir, watchRoot, declaredStates: states, now: FIXED_NOW });
    expect(r.status).toBe('AWAITING_APPROVAL');
    expect(r.pendingAwaitingApproval).toEqual(['root__default__1440x900']);
    expect(r.declaredNoCapture).toEqual([]);
    expect(exitCodeForStatus(r.status)).toBe(0); // first-run is not a failure
  });

  test('DEGRADED — declared_no_capture (no baseline AND no pending)', () => {
    const states = [decl('/', 'default')];
    const r = audit({ baseDir, pendDir, watchRoot, declaredStates: states, now: FIXED_NOW });
    expect(r.status).toBe('DEGRADED');
    expect(r.declaredNoCapture).toEqual(['root__default__1440x900']);
    expect(exitCodeForStatus(r.status)).toBe(1);
  });

  test('DEGRADED beats AWAITING_APPROVAL when both conditions present', () => {
    // Two declared states: one captured-pending (would be AWAITING), one totally missing (DEGRADED).
    const states = [decl('/', 'default'), decl('/intel', 'default')];
    dropPng(pendDir, 'root__default__1440x900', FIXED_NOW - 60_000);
    const r = audit({ baseDir, pendDir, watchRoot, declaredStates: states, now: FIXED_NOW });
    expect(r.status).toBe('DEGRADED');
    expect(r.pendingAwaitingApproval.length).toBe(1);
    expect(r.declaredNoCapture).toEqual(['intel__default__1440x900']);
  });
});

describe('audit — orphan + stale_baseline regression', () => {
  let baseDir: string;
  let pendDir: string;
  let watchRoot: string;

  beforeEach(() => {
    baseDir = freshTmp();
    pendDir = freshTmp();
    watchRoot = freshTmp();
  });
  afterEach(() => {
    rmSync(baseDir, { recursive: true, force: true });
    rmSync(pendDir, { recursive: true, force: true });
    rmSync(watchRoot, { recursive: true, force: true });
  });

  test('orphan_baseline — baseline file with no declared state → DEGRADED', () => {
    const states = [decl('/', 'default')];
    dropPng(baseDir, 'root__default__1440x900', FIXED_NOW - ONE_DAY_MS);
    dropPng(baseDir, 'old_route__default__1440x900', FIXED_NOW - ONE_DAY_MS);
    const r = audit({ baseDir, pendDir, watchRoot, declaredStates: states, now: FIXED_NOW });
    expect(r.status).toBe('DEGRADED');
    expect(r.orphanBaseline).toEqual(['old_route__default__1440x900']);
  });

  test('orphan_pending — pending file with no declared state → DEGRADED', () => {
    const states = [decl('/', 'default')];
    dropPng(pendDir, 'old_pending__default__1440x900', FIXED_NOW - 60_000);
    const r = audit({ baseDir, pendDir, watchRoot, declaredStates: states, now: FIXED_NOW });
    expect(r.status).toBe('DEGRADED');
    expect(r.orphanPending).toEqual(['old_pending__default__1440x900']);
  });

  test('stale_baseline — older than threshold → DEGRADED + age in days', () => {
    const states = [decl('/', 'default')];
    dropPng(baseDir, 'root__default__1440x900', FIXED_NOW - 45 * ONE_DAY_MS);
    const r = audit({
      baseDir,
      pendDir,
      watchRoot,
      declaredStates: states,
      now: FIXED_NOW,
      staleBaselineDays: 30,
    });
    expect(r.status).toBe('DEGRADED');
    expect(r.staleBaseline.length).toBe(1);
    expect(r.staleBaseline[0]!.ageDays).toBe(45);
  });
});

describe('audit — stale_pending detector', () => {
  let baseDir: string;
  let pendDir: string;
  let watchRoot: string;

  beforeEach(() => {
    baseDir = freshTmp();
    pendDir = freshTmp();
    watchRoot = freshTmp();
    // Build a watch tree that mirrors the real STALE_PENDING_WATCH_PATHS structure.
    mkdirSync(resolve(watchRoot, 'src/components/hud'), { recursive: true });
    mkdirSync(resolve(watchRoot, 'src/styles'), { recursive: true });
    mkdirSync(resolve(watchRoot, 'src'), { recursive: true });
    mkdirSync(resolve(watchRoot, 'tests/visual/fixtures'), { recursive: true });
  });
  afterEach(() => {
    rmSync(baseDir, { recursive: true, force: true });
    rmSync(pendDir, { recursive: true, force: true });
    rmSync(watchRoot, { recursive: true, force: true });
  });

  test('positive — pending older than max watch-path mtime → fires (DEGRADED)', () => {
    const states = [decl('/', 'default')];
    // Watch file mtime: T = FIXED_NOW - 1h
    const watchMtime = FIXED_NOW - 3_600_000;
    const watchFile = resolve(watchRoot, 'src/styles/hud.css');
    writeFileSync(watchFile, '/* theme */');
    const t = watchMtime / 1000;
    utimesSync(watchFile, t, t);

    // Pending mtime: 2h before watch file → stale
    dropPng(pendDir, 'root__default__1440x900', FIXED_NOW - 7_200_000);

    const r = audit({ baseDir, pendDir, watchRoot, declaredStates: states, now: FIXED_NOW });
    expect(r.stalePending.length).toBe(1);
    expect(r.stalePending[0]!.key).toBe('root__default__1440x900');
    expect(r.stalePending[0]!.latestWatchPathMtime).toBe(watchMtime);
    expect(r.status).toBe('DEGRADED');
  });

  test('negative — pending newer than all watch paths → does not fire', () => {
    const states = [decl('/', 'default')];
    const watchMtime = FIXED_NOW - 7_200_000;
    const watchFile = resolve(watchRoot, 'src/styles/hud.css');
    writeFileSync(watchFile, '/* theme */');
    const t = watchMtime / 1000;
    utimesSync(watchFile, t, t);
    // Also touch a glob-pattern file to ensure the recursive walk path is exercised
    const hudFile = resolve(watchRoot, 'src/components/hud/Topbar.tsx');
    writeFileSync(hudFile, 'export {};');
    utimesSync(hudFile, t, t);

    // Pending mtime AFTER watch file → fresh
    dropPng(pendDir, 'root__default__1440x900', FIXED_NOW - 60_000);

    const r = audit({ baseDir, pendDir, watchRoot, declaredStates: states, now: FIXED_NOW });
    expect(r.stalePending).toEqual([]);
    expect(r.status).toBe('AWAITING_APPROVAL');
  });

  test('edge — empty __pending__/ → no fire (vacuous)', () => {
    const states = [decl('/', 'default')];
    const watchFile = resolve(watchRoot, 'src/styles/hud.css');
    writeFileSync(watchFile, '/* theme */');
    dropPng(baseDir, 'root__default__1440x900', FIXED_NOW - ONE_DAY_MS);

    const r = audit({ baseDir, pendDir, watchRoot, declaredStates: states, now: FIXED_NOW });
    expect(r.stalePending).toEqual([]);
    expect(r.status).toBe('OK');
  });

  test('edge — all watch paths missing → no fire (vacuous true, do not crash)', () => {
    // Empty watchRoot with NO files at all under any of the declared watch paths
    rmSync(watchRoot, { recursive: true, force: true });
    mkdirSync(watchRoot, { recursive: true });

    const states = [decl('/', 'default')];
    dropPng(pendDir, 'root__default__1440x900', FIXED_NOW - ONE_DAY_MS);

    expect(latestWatchPathMtime(watchRoot)).toBe(0);
    const r = audit({ baseDir, pendDir, watchRoot, declaredStates: states, now: FIXED_NOW });
    expect(r.stalePending).toEqual([]);
    // Pending exists, no other problems → AWAITING_APPROVAL
    expect(r.status).toBe('AWAITING_APPROVAL');
  });

  test('edge — recursive glob path with newer file deeply nested → fires', () => {
    const states = [decl('/', 'default')];
    // Drop a nested file under a glob-watched path (src/components/hud/**/*)
    const watchMtime = FIXED_NOW - 1_800_000; // 30 min ago
    const nested = resolve(watchRoot, 'src/components/hud/PhemexStatusPill/index.tsx');
    mkdirSync(resolve(watchRoot, 'src/components/hud/PhemexStatusPill'), { recursive: true });
    writeFileSync(nested, 'export {};');
    const t = watchMtime / 1000;
    utimesSync(nested, t, t);

    // Pending older than the nested file → stale
    dropPng(pendDir, 'root__default__1440x900', FIXED_NOW - 3_600_000);

    const r = audit({ baseDir, pendDir, watchRoot, declaredStates: states, now: FIXED_NOW });
    expect(r.stalePending.length).toBe(1);
    expect(r.stalePending[0]!.latestWatchPathMtime).toBe(watchMtime);
  });
});

describe('audit — STALE_PENDING_WATCH_PATHS contract', () => {
  test('exported as constant array of strings (not magic-stringed inline)', () => {
    expect(Array.isArray(STALE_PENDING_WATCH_PATHS)).toBe(true);
    for (const p of STALE_PENDING_WATCH_PATHS) {
      expect(typeof p).toBe('string');
      expect(p.length).toBeGreaterThan(0);
    }
  });

  test('includes the four expected categories: hud components, hud styles, index.css, capture setup, fixtures', () => {
    const has = (s: string) => STALE_PENDING_WATCH_PATHS.some(p => p.includes(s));
    expect(has('src/components/hud')).toBe(true);
    expect(has('src/styles/hud.css')).toBe(true);
    expect(has('src/index.css')).toBe(true);
    expect(has('tests/visual/setup.ts')).toBe(true);
    expect(has('tests/visual/fixtures')).toBe(true);
  });
});
