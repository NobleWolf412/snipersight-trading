# Scanner setup correction, 2026-10-10

The earlier visual restoration kept essential scanner information outside the cards and collapsed inputs. The user's correction replaces that interaction model: mode requirements accompany each choice, the recommendation leads the screen, and optional explanation uses help dialogs.

## Interface

- Recommendation first, with backend reason, warning and regime. Available recommendations require a fresh observation and matching mode definition; stand-aside and unavailable remain explicit. Use mode is a manual action with a freshness check.
- Four colored cards at every width. Default score, minimum R:R, planning timeframe, critical required data and analysis timeframes are visible inside each card. No mode-requirements dropdown or phone-only mode selector remains.
- A separate information button opens each mode's optional description and timeframe-role detail in the existing native dialog. Opening help does not select the mode. Recommendation provenance also uses a labeled help dialog.
- Scan inputs are visible in a responsive grid. Existing changes/reset/reload, next-scan scope and busy disabling remain intact.
- Result filters open from the results toolbar in a native dialog; the passing/total count stays visible on its trigger. Filter handlers and reset are unchanged.

Run scan stays below the recommendation and above the cards on phones, so it is reachable without scrolling past all four choices. Selection remains explicit. This correction preserves the tactical palette, glow, scanlines and typography.

## Evidence

The [evidence record](SCANNER_SETUP_2026-10-10.json) retains the independent rubric review and fixture checkpoints; the [inventory](SCANNER_SETUP_2026-10-10_inventory.json) records current imports without deleting retained candidates.

TypeScript and the frontend build pass; 180 active unit tests in 15 files pass, including three additional requirement/stale/unknown-mode regressions. Selected scanner score/workflow/policy checks pass after the final display guards. No tests were weakened. Build bytes: main JS 287307; all JS 879316; all CSS 79409. These are asset measurements, not latency claims.

Independent fixtures cover 320/390/768/1280px, available/stand-aside/unavailable/stale/unknown/partial mode states, manual selection, busy inputs and native dialogs. Initial partial-metadata title crash and undersized portal slider were fixed and retested; initial evidence is retained separately. Source ownership and current mode thresholds remain unchanged. The parent inspected the actual scanner and help/Escape focus restoration without running a scan or touching a session.

Safari, native 200% zoom, full WCAG, every state and hardware performance remain unverified. Existing recommendation expiry normalization is unchanged. This presentation review makes no trading or whole-system correctness claim.

## Progress

No additional points. The prior committed score remains 315; A08/A09 and the full Level 07 journey gate remain partial. The October 9 audit and earlier October 10 restoration are preserved as checkpoints; this record supersedes their compact-selector/dropdown direction for scanner setup.
