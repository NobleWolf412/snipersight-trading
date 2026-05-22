# 2026-05-22 — Docs rewrite: blueprint → built scanner reality

## Headline
README.md rewritten end-to-end to reflect the actual built scanner (FastAPI backend + React HUD + paper trader + 4-mode system) rather than the "pre-implementation blueprint / Spark application / docs viewer" framing of the original. ARCHITECTURE.md, PROJECT_STRUCTURE.md, and QUICKSTART.md gained status banners pointing readers at README.md + CLAUDE.md as authoritative; QUICKSTART.md additionally got real run-the-app instructions prepended above the historical blueprint content.

## Context
Stale-drift item carried since 2026-05-20 janitor manifest. Pain points:

1. **README claimed "blueprint / not a working scanner"** — patently false; the scanner has been operational since the HUD-rebuild Phase 0-7 commits in early 2026.
2. **Tech stack claims out of date** — "Tailwind CSS v4 / shadcn/ui components" was ejected in Phase 7 (commit `26a7c1f`); custom HUD CSS is now the system.
3. **Implementation phases 1-6 over 8 weeks** — fictional roadmap that has no relationship to current state (Tier 1-4b workflow enhancements just shipped).
4. **Confluence threshold reference** — README said `≥ 7.0/10`; actual is 68-72 on a 0-100 scale per the four-mode table in CLAUDE.md §4.
5. **References to PRD.md** in README + QUICKSTART pointed at a file that was removed from the repo earlier.
6. **ARCHITECTURE.md** has nine "Recon mode" references; the system has had four modes (OVERWATCH/STRIKE/SURGICAL/STEALTH) since CLAUDE.md §10 fix #6 was enforced.

## Resolution

### README.md — full rewrite (307 lines)
- New framing: "Working scanner + paper trader + autonomous bot" — not a blueprint.
- Accurate stack: Python/FastAPI backend, React/TS frontend, custom HUD CSS (no Tailwind), Phemex/Bybit/OKX/Bitget adapters, SQLite + JSONL storage.
- Four-mode table reproduced from CLAUDE.md §4.
- Pipeline section: SniperContext stages with file:line refs.
- §15 hard boundaries called out.
- "Common operations" replaces fictional roadmap with actual commands: `capture_contracts diff`, `pipeline_smoke verify`, `gen:types`, snapshot tooling, pytest, tsc.
- Repository layout reflects actual `backend/` + `src/` + `tests/visual/` + `.claude/` structure (not the spec `snipersight/` tree).
- Cross-refs to CLAUDE.md §10/§15/§16/§17/§18/§19/§20 + decisions log + phase archive.

### ARCHITECTURE.md / PROJECT_STRUCTURE.md / QUICKSTART.md — status banner
Full rewrites of these (1760 + 951 + 406 lines) are out of round scope. Each gets a banner at the top:
- Identifies the doc as pre-implementation blueprint, partially stale
- Points reader at README.md + CLAUDE.md as authoritative
- Calls out the specific drift the operator is most likely to encounter
- Permits reader to treat the doc as historical reference

QUICKSTART.md additionally got a real "Run the application" section prepended (backend uvicorn command, frontend npm dev command, dev:all, start-sniper.bat, snapshot verify, type sync, common diagnostics) with the original blueprint content preserved below under "Historical blueprint reference."

ARCHITECTURE.md Recon-mode prose left in place under the banner — surgical replacement would have hit 9 line locations and risked breaking adjacent prose; the banner contextualizes the stale references as historical.

### Decisions log
This entry. No code changes, no contract drift, no §10 surface touched.

## Why it matters next time
README is the first file a new contributor or returning operator reads. Having it match reality cuts onboarding friction and removes the "is this still a blueprint?" question every time someone clones the repo. The status banners on ARCHITECTURE/PROJECT_STRUCTURE/QUICKSTART perform the same function for those docs without committing to a multi-thousand-line rewrite this round.

Future incremental work, none blocking:
- Full rewrite of ARCHITECTURE.md to reflect SniperContext pipeline + four-mode confluence flow (estimated 1-2 hour rewrite of 1760-line doc)
- Full rewrite of PROJECT_STRUCTURE.md mapping the actual `backend/` + `src/` tree
- Delete the "Historical blueprint reference" section from QUICKSTART.md once ARCHITECTURE.md is properly rewritten (currently retained because some readers may still come from links to the old content)

## Affected files (commit boundary)

MOD:
- `README.md` — full rewrite (307 lines)
- `ARCHITECTURE.md` — status banner prepended
- `PROJECT_STRUCTURE.md` — status banner prepended
- `QUICKSTART.md` — banner + real quick start prepended; original content retained under "Historical blueprint reference"

NEW:
- `backend/diagnostics/decisions/2026-05-22__docs-rewrite-blueprint-to-built.md` (this file)

NOT touched: `PRODUCT.md`, `DESIGN.md`, `SECURITY.md`, `SETUP_INSTRUCTIONS.md`, `CLAUDE.md`.

Cross-ref: commits 72f64fe (Tier 1), 9024ef2 (Tier 2), 373c51c (Tier 3), 712f494 (Tier 4a), 55f076e (Tier 2.5a), 56435d7 (Tier 4b); CLAUDE.md §4/§10/§15-§20.
