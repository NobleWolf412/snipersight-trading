# Tactical HUD restoration, 2026-10-10

The user requested the earlier cool factor back. This restores the tactical presentation while retaining the usable navigation, truthful state and code cleanup from the previous refactor. The current source, PRODUCT.md and DESIGN.md now agree on that direction.

## Restored presentation

- Olive dark surfaces, panel depth and gradients, scanlines, glowing HUD headings and accent buttons.
- Branded landing layout with the large logo, six console cards, example setups and operating doctrine. Examples remain labeled static; implemented capabilities replace unsupported performance/live-feed claims.
- Colored scanner mode cards on desktop/tablet, using native keyboard-operable buttons and the existing manual selection handler. Mode thresholds come from current definitions, with missing values shown as unavailable. Phones keep the compact selector and early Run scan action.
- Tactical background and decorative reticle defaults are enabled. Saved appearance preferences still win. Reduced motion disables animations and hides the pointer reticle; coarse-pointer surfaces also hide it. Reticles have no accessibility-tree semantics.

Native dialogs, focus restoration, shared touch targets, phone navigation, journal pagination, visible failure causes, lessons, screen splits, transport ownership and orphan/provider/dependency removals remain in place. No trading/session/ML behavior changed. Concurrent backend edits are outside this commit.

## Verification

The [evidence record](UI_HUD_RESTORE_2026-10-10.json) retains source hashes, the independent rubric review, initial candidates and passing targeted retests. The [new inventory](UI_HUD_RESTORE_2026-10-10_inventory.json) is a checkpoint, not a deletion list.

- TypeScript no-emit compiler passes; 177 active tests in 15 files pass. A final five-test scanner policy retest passes after the missing-limit display correction. Tests were not weakened or changed.
- Vite frontend build passes with 4,714 modules; Storybook passes with 348 modules. Existing metadata/glob/large-preview warnings remain non-failing.
- Main JS: 287,307 bytes; all JS: 874,673 bytes; all CSS: 75,641 bytes. The larger landing CSS is used restored presentation, not a new performance claim. Earlier measurements stay intact in the October 9 ledger.
- Independent intercepted Edge fixtures cover five routes at 320/390/768/1280px, 20 expanded layout cases and 20 reduced-motion samples. Menu focus/Escape, keyboard mode cards, manual recommendation application, nested health dialog and saved appearance preferences pass. No document overflow, render errors or API mutation attempts in these samples.
- Two bounded candidates were corrected: the landing secondary CTA now reaches 44px at all four widths, and missing mode R:R renders Unavailable. Initial evidence is retained separately from retests.
- In-app browser review confirms the restored landing and four desktop mode cards. No scans, orders or session operations were issued.

The inventory has 163 active files, 153 archived files, 18 retained candidates and 1055 inline style objects. No files or dependencies were resurrected to recreate unused polling/scaffolds.

Safari, native 200% zoom, actual mobile hardware, full WCAG/state acceptance, ambient-gradient contrast and performance profiling remain unverified. This presentation check does not certify exchange or whole-system correctness.

## Development progress

The prior committed score remains 315. This preference restoration earns no duplicate cleanup points. A08/A09 and the complete native cross-browser Level 07 gate remain partial/open. Historical quiet-style and gross-removal measurements describe their original checkpoint; this record supersedes the appearance direction and supplies current asset measurements.
