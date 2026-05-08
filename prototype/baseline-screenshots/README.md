# Visual Regression Baseline — Phase 2 Decision Log

## Status: Intentionally Empty

A live screenshot baseline of the pre-eject app was attempted but skipped.
This README documents the reasoning so the §12 diagnostic gap is honest,
not invisible.

## Why no baseline screenshots

The Phase 2 eject of Tailwind will *intentionally* break visuals — every
`className="text-foreground bg-card border-border"` reference loses its
styling the moment Tailwind is removed. Pre-eject vs post-eject screenshots
would show massive expected differences: pages rendering as unstyled HTML.
That comparison is not informative.

## What replaces the baseline

The actual visual proof happens at Phase 3, page-by-page:

  - Each ported page (e.g. `src/pages/Scanner.tsx`) is compared directly
    against the prototype HTML it ports (`prototype/Scanner.html`) opened
    side-by-side in the browser.
  - The acceptance bar is "pixel-faithful to prototype" — not "matches
    pre-eject state". The pre-eject state is exactly what we are leaving.

## What guards against silent breakage during Phase 2 itself

  1. **Build still succeeds** at every Phase 2 checkpoint (`npm run build`
     does not regress).
  2. **TypeScript still compiles** (`tsc --noEmit` clean).
  3. **All routes still render** without runtime crashes — verified by
     `curl http://localhost:5000/{route}` returning 200, even if the page
     looks unstyled. This catches the class of regression that is invisible
     in screenshots: a missing import or a deleted hook that crashes the
     route.
  4. **shadcn/ui imports** are removed in lockstep with their consumers.
     Phase 4 is dedicated to converting kept components from Tailwind
     classes to vanilla CSS using prototype tokens.

## §12 honesty note

This is a real gap. A snapshot test framework (Playwright + Percy /
Chromatic / Loki) would catch silent UI regressions automatically. The
project has Playwright as a dep but no configured suite. Adding one is
out-of-scope for the rebuild but in-scope as a follow-up: see TODO at
the end of `ARCHIVE.md` once Phase 6 lands.
