# Visual snapshot framework

Per-route screenshot regression tests. Built for Phase 3 page-by-page rebuild.

## Workflow

1. `npm run dev:frontend` — run the app locally on port 5000.
2. `npm run snapshots:capture` — captures every declared state into `__pending__/`, diffs against `__baselines__/`. First-run states have no baseline; the spec fails with "no approved baseline" — this is intentional.
3. `npm run snapshots:show -- <route> <state>` — open baseline+current+diff side-by-side in browser.
4. `npm run snapshots:approve -- <route> <state>` — promote one pending → baseline.
5. `npm run snapshots:approve-all` — interactive bulk promote.
6. `npm run snapshots:audit` — drift diagnostic (orphans, missing, stale).

## Why two thresholds

Pixel-only diffing false-fires on antialiasing and sub-pixel font rendering — every CI run produces noise that trains everyone to ignore the signal. Two thresholds, both must pass:

| Threshold | Default | What it catches |
|---|---|---|
| `perPixel` (pixelmatch ΔE) | `0.1` | Real color/contrast changes |
| `regionPctOfViewport` | `0.001` (0.1%) | Layout shifts — moved/missing elements |

A 1px font-hinting difference scattered across the page racks up per-pixel noise but produces no large contiguous region. A moved button creates a small per-pixel diff but a region clearly above 0.1% of viewport. Both real failures cross both thresholds.

## Why approval is gated

A first capture can never become the baseline automatically. Auto-approval would lock in whatever visual bug the page currently has. The framework treats every first capture as `__pending__/`; the human runs `snapshots:approve` to accept.

## Why network mocks

Backend state (Phemex pill counters, signal_log, scan cycles) is non-deterministic — capturing twice in a row would produce two different baselines. Setup intercepts `/api/**` GETs and serves fixtures from `tests/visual/fixtures/`. Non-GET requests during capture fail the test (programmer error).

## Why animations are frozen

Spinners, pings, transitions — all suppressed via injected CSS at capture time. Without this, every capture is a coin flip on which animation frame got snapshotted.

## Schema/state symmetry

`audit.ts` enforces:

- every captured PNG matches one declared state in `states.ts`
- every declared state has either a baseline or a pending entry
- no duplicate `{route, state, viewport}` keys

Mismatches are flagged DEGRADED with specific reason codes.

## File layout

```
tests/visual/
  states.ts              # typed SnapshotState[]
  setup.ts               # animation freeze + network mocks + ready waits
  diff.ts                # pixelmatch + region detection
  capture.spec.ts        # Playwright spec
  approve.ts | show.ts | audit.ts | report.ts
  fixtures/              # deterministic JSON for /api/* mocks
  __baselines__/         # committed
  __pending__/           # gitignored
  __report__/            # gitignored
```

## Mirroring Phase 1 patterns

- **Output ordering**: short summary first → diagnostic groups → raw JSON last.
- **Audit**: same shape as `cycle_heartbeat_audit` — declared/captured/orphan/stale categories.
- **Concurrency**: Playwright workers parallelize capture; baselines are read-only during capture; `:approve` is single-threaded.
- **Lookup-miss**: 404-equivalent → fail loud with explicit reason code (`baseline_missing`).
