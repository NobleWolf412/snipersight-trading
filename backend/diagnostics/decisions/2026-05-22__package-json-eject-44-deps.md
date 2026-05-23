# 2026-05-22 — package.json eject: 44 unused frontend dependencies removed

## Headline
Ejected 44 unused npm packages from `package.json` `dependencies`. node_modules diff: ~30-40 MB reduction. npm-audit count: 22 → 20 vulnerabilities (incidental). All four verification gates passed post-eject: `tsc --noEmit` exit 0, `vite build` success (5.87s), `capture_contracts diff` CLEAN, `pipeline_smoke verify` CLEAN.

## Context
The last remaining item on the operator's workflow queue. Per the 2026-05-20 janitor manifest (now archived in [`backend/diagnostics/phase_archive/2026-05-21__hud_rebuild_phases_0_through_7.md`](../phase_archive/2026-05-21__hud_rebuild_phases_0_through_7.md)) and memory pointer `project_package_json_eject.md`: "~30 frontend deps unused after Phase 7 (Radix, cmdk, vaul, recharts, sonner, react-hook-form); manifest never propagated."

Phase 7 ejected Tailwind + shadcn-primitive layer (commits `56cc164..26a7c1f`); the supporting deps that shadcn/Radix/etc. brought in were never cleaned up. The package.json still carried 27 `@radix-ui/*` packages, plus react-hook-form, recharts, cmdk, vaul, etc. — all dead weight in node_modules + lockfile.

## Resolution

### Methodology
1. Run depcheck on the repo: `npx --yes depcheck --json`. Got 11 `dependencies` flagged unused.
2. Hand-verify each via grep on active `src/` (excluding `src/_archive/`): `grep -lr "from ['\"]<pkg>" src/ --include="*.ts" --include="*.tsx" | grep -v _archive`. All 11 confirmed zero-use.
3. Hand-audit remaining `@radix-ui/*` (depcheck only flagged `@radix-ui/react-icons`; the other 26 weren't caught because they appeared in some discoverable position — likely ambient type imports or transitively pulled). Grep `src/` for any `@radix-ui` import → zero hits in active code. All 27 Radix packages confirmed dead.
4. Hand-audit the explicit operator-named eject targets (`react-hook-form`, `recharts`, `cmdk`, `vaul`, `sonner`): all zero-use in active `src/`. Plus three more from the same UI family found by same method: `input-otp`, `embla-carousel-react`, `react-resizable-panels`.

### Removed (44 packages)
**Radix primitives (27)** — entire `@radix-ui/*` family. Ejected when shadcn-primitives were removed in Phase 7; nothing in active HUD imports any of them:
- accordion, alert-dialog, aspect-ratio, avatar, checkbox, collapsible, context-menu, dialog, dropdown-menu, hover-card, icons, label, menubar, navigation-menu, popover, progress, radio-group, scroll-area, select, separator, slider, slot, switch, tabs, toggle, toggle-group, tooltip

**UI-stack dead weight (7)**:
- react-hook-form + @hookform/resolvers (form library)
- recharts (charting lib — echarts is the live charting via echarts-for-react)
- cmdk (command palette)
- vaul (drawer)
- input-otp (OTP input)
- embla-carousel-react (carousel)
- react-resizable-panels (resizable panels)

**Other (10)**:
- @gsap/react + gsap (GSAP animations — framer-motion is the live animation lib)
- @react-spring/three + @react-spring/web (react-spring — also redundant with framer-motion)
- leva (3D debug UI — not used in any active three.js scene)
- marked (markdown parser — unused)
- uuid (UUID lib — backend uses Python uuid)
- xterm (legacy package; `@xterm/xterm` scoped package is the active one — retained)
- zod (schema validation — TS types from openapi-typescript cover the wire)

### Retained (called out explicitly):
- `class-variance-authority` — memory note "Intentionally retained orphan-but-not-Tailwind: class-variance-authority" out of Phase 7 scope; left untouched this round (zero `src/` hits but retained per the prior decision; potential future eject if no consumer materializes)
- `framer-motion` — actively used
- `lightweight-charts` + `echarts` + `echarts-for-react` — live charting stack
- `@phosphor-icons/react` + `lucide-react` — live icon sets
- `@xterm/xterm` + `@xterm/addon-fit` — active terminal renderer
- `@react-three/drei` + `@react-three/fiber` + `@react-three/postprocessing` + `three` + `postprocessing` — active 3D scene stack
- `numeral` + `date-fns` — active formatters

### Verification gates (post-eject)
- `npx tsc --noEmit -p tsconfig.json` → exit 0 (no type regressions; active `src/` truly didn't import any of the removed packages)
- `npx vite build` → success in 5.87s; all bundle chunks built normally (verified per-chunk output in the originating conversation)
- `python -m backend.diagnostics.capture_contracts diff` → CLEAN (0 changes; backend untouched)
- `python -m backend.diagnostics.pipeline_smoke verify` → CLEAN (0 changes)

### Operator-side authorization
The auto-mode classifier blocked the initial bulk uninstall on the grounds that "depcheck output is untrusted input for choosing removal targets" and "no explicit user authorization for this specific destructive package removal." Operator gave explicit per-list authorization ("approve eject") after reviewing the full 44-package manifest inline. Recorded per §16 calibration rule (Plan + verbatim + explicit-auth-before-destructive).

## Why it matters next time
Compound clutter in package.json hides actual deps and inflates install time + node_modules size + lockfile churn. Removing the 44 unused packages:
- Speeds up `npm install` materially
- Removes ~30-40 MB from node_modules
- Removes 2 npm-audit vulnerabilities (incidental side effect; the eject specifically dropped some Radix transitives that had outstanding advisories)
- Reduces TypeScript-language-server scan time on cold start
- Makes the "what does this project actually use" question answerable from package.json without grep

Future incremental opportunities:
- `class-variance-authority` re-evaluate if Phase 7 successor decisions land
- Storybook addons (`@chromatic-com/storybook`, `@storybook/addon-*`) — currently `eslint-plugin-storybook` is wired via `eslintConfig.extends` so storybook stays for now, but if the operator decides storybook isn't worth maintaining (most `.stories.tsx` are in `src/_archive/`), the addon set could go in a follow-up
- depcheck devDependency false-positives (`@vitejs/plugin-react`, `cross-env`, eslint plugins) deliberately left in place — they ARE used by build-config / test-config / npm scripts that depcheck doesn't trace; removing them would break the build

## Affected files (commit boundary)
MOD:
- `package.json` — 44 entries removed from `dependencies` (53 lines deleted)
- `package-lock.json` — lockfile rewrites following the uninstall (npm regenerated; bulk of diff is here)

NEW:
- `backend/diagnostics/decisions/2026-05-22__package-json-eject-44-deps.md` (this file)

Cross-ref: commit `26a7c1f` (Phase 7.7 ARCHIVE.md ledger which never propagated this dep eject); commits `72f64fe` (Tier 1), `9024ef2` (Tier 2), `373c51c` (Tier 3 + memory archive), `712f494` (Tier 4a hooks), `55f076e` (Tier 2.5a pipeline_smoke), `56435d7` (Tier 4b TS-sync), `6f2bad0` (Tier 3 followup + docs rewrite), `f40069e` (Tier 4c scheduled janitor).
