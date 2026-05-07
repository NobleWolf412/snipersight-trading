# Prototype — HUD Design Reference

Source-of-truth design for the SniperSight HUD rebuild (branch `claude/hud-rebuild`).

These files are the verbatim downloads from the design environment. They are
**not** built or imported by the application — the live app under `src/` is a
TypeScript/Vite/React port of these designs wired to the real FastAPI backend.

## Contents

### Pages (HTML shells + JSX bodies)
- `Landing.html` + `landing.jsx` + `landing.css` — marketing landing with animated Scope SVG hero
- `Intel.html` + `intel.jsx` — macro / regime / funding / liquidations / news
- `Scanner.html` + `scanner.jsx` — live signal grid with radar, console, filter rail
- `Bot.html` + `bot-shell.jsx` — tabbed shell wrapping Setup + Status
- `setup.jsx` — Bot SETUP tab
- `Journal.html` + `journal.jsx` — trade analytics, equity curve, MAE/MFE, calendar
- `Training.html` + `training.jsx` — training-ground hub
- `Settings.html` + `settings.jsx` — account, API keys, notifications

### Shared chrome / utilities
- `shared.jsx` + `shared.css` — Topbar, PageHead, FooterStatus, Reticle, Modal,
  SectionHead, Chip, Mini, RiskBar, applyTweaks, formatters (`SS.*` namespace)
- `tweaks-panel.jsx` — floating dev tweaks panel
- `scanner-modes.jsx` — 4-mode picker (OVERWATCH/STRIKE/SURGICAL/STEALTH)
- `gauntlet.jsx` — Gauntlet Breakdown signal funnel
- `app.jsx` — design-environment entrypoint (NOT used in real app)

## Notes
- Vanilla JSX served via Babel `<script>` tags — no build step.
- All data is mock / synthetic — `SEED` constants, no API calls.
- All chrome lives on the `window.SS` global namespace.
- The real port lives under `src/` and replaces `window.SS.*` with proper TS imports.

## Migration plan
See `C:\Users\macca\.claude\plans\peppy-sniffing-owl.md` (or repo `docs/`
once moved) for the full HUD rebuild plan, phase order, and mapping
of each prototype file to the TSX file that replaces it.
