---
name: SniperSight
description: Tactical HUD for SMC trading intelligence
colors:
  bg: "oklch(0.18 0.008 120)"
  bg-2: "oklch(0.22 0.010 125)"
  card: "oklch(0.26 0.012 125)"
  card-2: "oklch(0.30 0.012 125)"
  border: "oklch(0.36 0.015 130)"
  border-soft: "oklch(0.32 0.015 130 / 0.6)"
  fg: "oklch(0.94 0.012 150)"
  fg-2: "oklch(0.78 0.012 150)"
  fg-3: "oklch(0.78 0.012 150)"
  fg-4: "oklch(0.72 0.012 150)"
  green: "#00ffaa"
  green-soft: "#4ade80"
  amber: "#ffc266"
  amber-2: "#fbbf24"
  red: "#ff6464"
  red-2: "#f87171"
  blue: "#60a5fa"
  cyan: "#22d3ee"
  purple: "#c084fc"
typography:
  display:
    fontFamily: "'Share Tech Mono', ui-monospace, monospace"
    fontSize: "clamp(38px, 5.4vw, 68px)"
    fontWeight: 400
    lineHeight: "0.98"
    letterSpacing: "0.01em"
  page-title:
    fontFamily: "'Share Tech Mono', monospace"
    fontSize: "32px"
    fontWeight: 400
    lineHeight: "1"
    letterSpacing: "0.2em"
  section-title:
    fontFamily: "'Share Tech Mono', monospace"
    fontSize: "13px"
    fontWeight: 400
    letterSpacing: "0.22em"
  metric-value:
    fontFamily: "'Share Tech Mono', 'JetBrains Mono', monospace"
    fontSize: "26px"
    fontWeight: 800
    lineHeight: "1"
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: "1.55"
    letterSpacing: "normal"
  label:
    fontFamily: "'JetBrains Mono', monospace"
    fontSize: "10px"
    fontWeight: 600
    letterSpacing: "0.18em"
  mono:
    fontFamily: "'JetBrains Mono', monospace"
    fontSize: "11.5px"
    fontWeight: 400
    fontFeature: "tabular-nums"
rounded:
  sm: "8px"
  md: "10px"
  lg: "12px"
  xl: "14px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "14px"
  lg: "18px"
  xl: "24px"
  shell-x: "28px"
components:
  panel:
    backgroundColor: "linear-gradient(135deg, rgba(0,0,0,0.55), oklch(0.22 0.010 125 / 0.6))"
    textColor: "{colors.fg}"
    rounded: "{rounded.xl}"
    padding: "0"
  chip:
    backgroundColor: "rgba(255,255,255,0.04)"
    textColor: "{colors.fg-2}"
    rounded: "{rounded.pill}"
    padding: "3px 8px"
    typography: "{typography.label}"
  chip-accent:
    backgroundColor: "rgba(0,255,170,0.10)"
    textColor: "{colors.green}"
    rounded: "{rounded.pill}"
    padding: "3px 8px"
  chip-red:
    backgroundColor: "rgba(248,113,113,0.08)"
    textColor: "{colors.red-2}"
    rounded: "{rounded.pill}"
    padding: "3px 8px"
  chip-cyan:
    backgroundColor: "rgba(34,211,238,0.08)"
    textColor: "{colors.cyan}"
    rounded: "{rounded.pill}"
    padding: "3px 8px"
  btn:
    backgroundColor: "rgba(255,255,255,0.03)"
    textColor: "{colors.fg-2}"
    rounded: "{rounded.md}"
    padding: "9px 14px"
  btn-cyan:
    backgroundColor: "linear-gradient(180deg, #164e63 0%, #0e3a4a 60%, #0a2d3a 100%)"
    textColor: "#67e8f9"
    rounded: "{rounded.md}"
    padding: "9px 14px"
  btn-red:
    backgroundColor: "rgba(248,113,113,0.10)"
    textColor: "{colors.red-2}"
    rounded: "{rounded.md}"
    padding: "9px 14px"
  metric-tile:
    backgroundColor: "rgba(0,0,0,0.4)"
    textColor: "{colors.fg}"
    rounded: "{rounded.lg}"
    padding: "14px 16px"
---

# Design System: SniperSight

## Direction (reviewed 2026-10-10)

**Pro trading terminal with a tactical HUD soul.** Chart-led and crisp like a modern pro terminal, but unmistakably SniperSight: olive surfaces, mono chrome, scanlines, reticles, glow and deliberate motion. The operator likes effects and motion; use them with intent rather than stripping them out. The identity is tactical; the usability is pro-grade.

**Phone and desktop are equals.** The operator spends about 90% of the time on a phone. Every screen must look as good at 390px as at 1440px. The phone layout is designed on purpose, not squeezed from desktop. Charts and the Play Inspector go full-screen on phones.

**Detail lives in modals, not dropdowns.** When a surface has more to show, open a modal (full-screen sheet on phones) with real layout: chart, tables, labeled sections. Never expand a dropdown or accordion into a wall of text. See [PRODUCT.md](PRODUCT.md#progressive-disclosure-modals-not-text-piles).

[PRODUCT.md](PRODUCT.md) owns screen intent, truthful state and priorities. [tokens.css](src/styles/tokens.css) is the sole palette owner; [hud.css](src/styles/hud.css) carries the tactical treatment; [workspace.css](src/styles/workspace.css) carries responsive, focus and touch rules. Retained requirements: readable muted text, 44px touch targets, native dialogs, visible keyboard focus, reduced-motion support (decorative animation off), and pointer reticles hidden on coarse pointers. Saved browser appearance preferences are authoritative; the default is tactical. Checkpoint history is in [docs/audits/](docs/audits/) (latest: [HUD restoration](docs/audits/UI_HUD_RESTORE_2026-10-10.md)).

## 1. Overview

**Creative North Star: "The Tactical Cockpit"**

SniperSight is a HUD overlaid on a working terminal, not a dashboard with a tactical theme. Every glyph earns its rent. The system is dark by intent. Picture two scenes and design for both: the operator at a desk scanning multi-timeframe SMC structure, and the same operator on a phone in daylight between errands, checking whether the bot's limit filled and nudging a stop with a thumb. Desktop can carry density; the phone carries one clear thing at a time, large. Light mode is not on the roadmap.

The look reads as legible-aggressive: olive-tinted near-black surfaces, electric green as the default "GO" accent (with red on live mode and amber on warnings), mono type that owns the chrome, repeating CRT scanlines on every panel. Corner brackets and animated reticles establish the tactical identity. They are decorative; explicit state labels determine whether the system is armed or idle. Motion is a feature: ambient motion is slow and repetitive (radar sweeps, pulse rings, drifting glow), while interaction motion is quick and purposeful (modals and sheets sliding in, chart lines tracking a drag, values ticking to new numbers, reveal sweeps on earned insignia). Nothing bounces. Nothing throws confetti.

This system explicitly rejects: the generic SaaS dashboard (Inter for everything, purple-to-blue gradients, identical card grids), the consumer finance softness (rounded everything, pastels, friendly empty states), the crypto-casino aesthetic (RGB neon, gamified XP, animated charts as decoration), and AI-tool landing-page reflex (white surface, vague gradient, "intelligent trading" copy). It also refuses Bloomberg-terminal nostalgia LARP: pure `#0F0` on `#000` with unreadable density. Olive-tint backgrounds and OKLCH neutrals are the difference.

**Key Characteristics:**
- Olive-tinted dark surfaces, never pure black
- Mono type owns the chrome (Share Tech Mono for display, JetBrains Mono for labels and numbers, Inter only for prose body)
- Accent is green today; a state-driven accent (amber warning, red live) is the target, not yet wired
- Repeating scanlines on every `.panel` as a 2-bit overlay, not a hero effect
- Corner brackets, reticles, and orbs as decorative HUD treatments
- High density, low ornamentation; every chip is structural

## 2. Colors: The Olive-Tactical Palette

The system runs on tinted neutrals plus a status-coded accent family. Strategy is **Restrained at rest, Committed under state.** Tiles and panels are tinted-neutral by default; saturated color only enters via accent edges, status chips, and live-mode chrome shifts. The accent itself is a CSS variable, so a panel marked `.panel-accent` will inherit the screen's operating state once the dynamic accent is wired (target: green at rest, amber on warning, red live; fixed green today).

### Primary
- **Electric Mantis Green** (`#00ffaa`): the default accent. Used for the operating accent variable, brand mark, success states, "GO" affordances, the equity-up direction. Appears as edge glow on `.panel-accent`, as the brand text-shadow, and as the dynamic `--accent` token.

### Secondary
- **Live Mode Red** (`#ff6464` / softer `#f87171`): the live-trading state, danger affordances, sell-side direction, breach indicators. Page titles switch to red when bot mode is live. Used in `.btn-red`, `.chip-red`, `.hud-glow-red`.

### Tertiary
- **Warning Amber** (`#ffc266` / `#fbbf24`): the page-title default tone, warning chips, paper-mode demarcation, regime-cautious states. The non-live, non-success middle band.
- **Strike Cyan** (`#22d3ee`): the Strike-mode accent and the primary CTA pressable. `.btn-cyan` is the only 3D-pressable button in the system. Used sparingly.

### Neutral (olive-tinted, OKLCH)
- **Surface Deep** (`oklch(0.18 0.008 120)`): page background. Never pure black; the 0.008 chroma pulls toward olive so saturated accents read as on-brand.
- **Surface Mid** (`oklch(0.22 0.010 125)`): panel gradient lower stop, scope tile background.
- **Surface Card** (`oklch(0.26 0.012 125)`): elevated card layer.
- **Surface Card Hover** (`oklch(0.30 0.012 125)`): hover/focus elevation.
- **Border** (`oklch(0.36 0.015 130)`): hard divider, button outline default.
- **Border Soft** (`oklch(0.32 0.015 130 / 0.6)`): primary divider, panel outline.
- **FG Primary** (`oklch(0.94 0.012 150)`): primary text, metric values.
- **FG Secondary** (`oklch(0.78 0.012 150)`): body prose, button text.
- **FG Tertiary** (`oklch(0.78 0.012 150)`): nav links at rest, supporting copy. Raised to equal FG Secondary for readability; hierarchy comes from size, weight and color, not dimming.
- **FG Quaternary** (`oklch(0.72 0.012 150)`): labels, timestamps, dim metadata. The floor for readable muted text; do not go darker.

### Named Rules

**The No-Pure-Black Rule.** Surfaces are olive-tinted near-black, never `#000`. The chroma is small (0.008-0.015) but non-zero; it's what stops the HUD from feeling like a Bloomberg terminal. If you ever write `#000` or `#fff`, rewrite the value.

**The Dynamic Accent Rule (target).** Every chip, button, panel edge and orb that wants the operating-state color references `var(--accent)`, not a hard-coded hue. Today `--accent` is fixed green: `applyTweaks` in `src/components/hud/applyTweaks.ts` can rebind it but is not called. The intended mapping is green at rest, amber on warning surfaces and red in live mode. Wiring it to real session state is planned work. Live mode is currently signaled by the red page title and explicit LIVE chips.

**The 10% Saturation Rule.** Saturated colors cover ≤10% of any single screen. Green edges, red chips, amber labels, cyan buttons: each used in pixels-not-percentages. The remaining 90% is olive-tinted neutrals. Drenched surfaces are forbidden in product register; landing is allowed exceptions.

## 3. Typography

**Display Font:** `Share Tech Mono` (with `ui-monospace, monospace` fallback)
**Body Font:** `Inter` (with `ui-sans-serif, system-ui, sans-serif` fallback)
**Label/Mono Font:** `JetBrains Mono` (with `monospace` fallback)
**Retro Terminal:** `VT323` (used sparingly, only for `.term` artefacts)

**Character:** Mono dominates. `Share Tech Mono` carries every uppercase chrome element (brand mark, page titles, section titles, metric values, hero) with wide letter-spacing and no lowercase. `JetBrains Mono` carries every label, every chip, every numeric readout (tabular-nums, monospace digit alignment). `Inter` only enters when prose is genuinely prose: hero subhead, modal body copy, journal notes. The pairing reads as terminal-native without LARPing as one. Share Tech Mono is decorative-mono, not punch-card-mono.

### Hierarchy
- **Display** (Share Tech Mono, `clamp(38px, 5.4vw, 68px)`, weight 400, line-height 0.98, letter-spacing 0.01em): hero title on landing only. Uppercase. Used once per surface.
- **Page Title** (Share Tech Mono, 32px, weight 400, line-height 1, letter-spacing 0.2em): the `<PageHead>` h1 on every product route. Tinted amber at rest, red in live mode, with text-shadow glow.
- **Section Title** (Share Tech Mono, 13px, letter-spacing 0.22em, uppercase): panel headers. Always paired with the pulsing accent dot.
- **Metric Value** (Share Tech Mono / JetBrains Mono, 26px, weight 800, line-height 1, letter-spacing -0.01em): the prominent number on `.metric-tile`. The one place the type goes heavy.
- **Body** (Inter, 13px, weight 400, line-height 1.55): the only prose font. Used for hero subhead, modal text, journal notes. Capped at 65-75ch for prose contexts.
- **Label** (JetBrains Mono, 9-11px, weight 600, letter-spacing 0.18-0.20em, uppercase): every chip, every metric-tile label, every nav link, every timestamp, every corner-tag.
- **Mono Numeric** (JetBrains Mono, 11.5px, tabular-nums): journal rows, log rows, scan output, price ticks. Where alignment matters more than style.

### Named Rules

**The Mono-Owns-Chrome Rule.** Every label, chip, button, nav link, section title, page title, brand mark, and metric value is mono. Inter only appears in deliberate prose blocks: hero subhead, modal body, journal note text. If chrome reads as sans-serif, the chrome is wrong.

**The Letter-Spacing-Is-A-Token Rule.** Mono uppercase carries 0.16-0.22em letter-spacing depending on tier (chips 0.18, section titles 0.22, page titles 0.2). The spacing is what makes the type feel HUD; without it, mono uppercase reads as console output, not heads-up display.

**The Tabular-Nums Rule.** Every numeric readout uses `font-variant-numeric: tabular-nums` (declared on `html`/`body` and on `.mono`). Price ticks, scores, latency readouts, percentages: all alignable column-wise without manual padding.

## 4. Elevation

The system is **flat at rest, glowing on state.** No drop shadows on cards or panels in their default state. Depth comes from:

1. Tonal layering: page bg sits under `.panel` gradient, which sits under `.metric-tile`, which sits under chips. Same hue, stepped lightness.
2. Soft edge glow when a panel is `.panel-accent`, using `box-shadow: 0 8px 40px rgba(0,0,0,0.4)` plus a colored 1px outline. Treats the accent as light spilling from the panel.
3. Ambient radial gradients in the tactical background, slowly drifting (`@keyframes glowDrift`, 30s).
4. Backdrop-blur on the modal overlay only; the one earned glassmorphism in the system.

### Shadow Vocabulary

- **Panel Accent Glow** (`box-shadow: 0 0 0 1px color-mix(in oklch, var(--accent) 8%, transparent), 0 8px 40px rgba(0,0,0,0.4)`): only on `.panel-accent`. The screen's operating state spilling from the bordered surface.
- **Orb Glow** (`box-shadow: 0 0 18px var(--accent)` on the 14px core): the pulsing status indicator. Green/amber/red variants.
- **Button Cyan Press** (`box-shadow: 0 4px 0 0 #061e27, 0 0 12px rgba(34,211,238,0.18), inset 0 1px 0 rgba(255,255,255,0.07)`): the 3D-pressable Strike CTA. Compresses to `0 1px 0 0` on `:active`.
- **Modal Lift** (`box-shadow: 0 30px 80px rgba(0,0,0,0.6), 0 0 0 1px color-mix(in oklch, var(--accent) 15%, transparent)`): the one earned heavy shadow, used for modal centering against the blurred backdrop.
- **HUD Text Glow** (`text-shadow: 0 0 6px ..., 0 0 14px ...`): applied to `.hud-glow`, `.hud-glow-amber`, `.hud-glow-red` and to page titles. The CRT bloom; the type is illuminated, not just colored.

### Named Rules

**The Flat-Default Rule.** Panels, cards, chips, buttons, and tiles ship flat. Shadows appear only when state demands it (accent panel, hover, modal, button press). A drop-shadow on a default surface is a bug.

**The Ambient-Versus-Signal Rule.** Two classes of effect, never confused:
- **Ambient (decorative, always allowed):** tactical background drift, scanlines, reticles, corner brackets, brand and title text glow. They set the mood and never imply activity.
- **Signals (must reflect real state):** the orb, `.panel-accent` glow, live/armed colors, pulse rings on status indicators and anything labeled LIVE, STREAMING or ARMED. If the state isn't real, the signal doesn't render. A pulsing orb on an idle bot is a bug.

## 5. Components

### Panels
- **Shape:** 14px radius, 1px `var(--border-soft)` outline.
- **Background:** `linear-gradient(135deg, rgba(0,0,0,0.55), oklch(0.22 0.010 125 / 0.6))`. Gradient anchors top-left.
- **Overlay:** every `.panel` carries a `::before` repeating-linear-gradient scanline at 2px intervals, `rgba(255,255,255,0.012)` opacity. Toggleable via `.scanlines-off`.
- **Accent variant:** `.panel-accent` adds the colored outline + halo glow described under Elevation.
- **Corner brackets:** `.brackets` class adds two 14px corner brackets (top-left, bottom-right) drawn from accent color. Ambient decoration; they frame a panel but do not signal state.
- **Section header:** internal `.sec-head` divider with `.sec-title` (Share Tech Mono, 13px) and the pulsing accent dot. Separator is `border-bottom: 1px solid var(--border-soft)`.

### Buttons
- **Shape:** 10px radius. Padding 9px 14px.
- **Default (`.btn`):** transparent-ish ghost. Background `rgba(255,255,255,0.03)`, border `var(--border)`, color `var(--fg-2)`, mono uppercase 11.5px, letter-spacing 0.18em, font-weight 800.
- **Variants:** `.btn-red` (live actions), `.btn-orange` (intermediate caution), `.btn-green` (confirm), `.btn-cyan` (primary CTA, 3D-pressable).
- **Cyan CTA:** the standout. Gradient face (`#164e63 → #0e3a4a → #0a2d3a`), 4px bottom shadow as physical depth, inset highlight on the top edge, cyan glow halo. Active state compresses 1px and the bottom shadow halves. This is the one button in the system with weight.
- **Hover:** ghost variants brighten by 3% surface opacity and one fg step. Cyan brightens by `filter: brightness(1.15)`. No transform on hover for ghost variants; Cyan only translates on `:active`.

### Chips
- **Style:** 999px pill, 1px outlined, 10px JetBrains Mono uppercase font, letter-spacing 0.18em. Padding 3px 8px, gap 6px (icon + text).
- **Default:** transparent-tinted background, `var(--fg-2)` text.
- **State variants:** `.chip-accent` (uses dynamic `--accent`), `.chip-green`, `.chip-red`, `.chip-amber`, `.chip-blue`, `.chip-cyan`, `.chip-purple`. Each variant uses an 8-10% tinted background, 30-35% tinted border, and the saturated text color.
- **Used for:** mode tags (STEALTH / STRIKE / SURGICAL / OVERWATCH), state flags (ARMED / LIVE / PAPER), classification (SWING / INTRADAY / SCALP), regime labels.

### Cards / Containers
- **Corner Style:** 12-14px radius depending on tier (panels 14px, metric-tiles 12px, pos cards 12px).
- **Background:** rgba(0,0,0,0.4) or panel-gradient depending on tier.
- **Shadow Strategy:** flat by default, see Elevation.
- **Border:** 1px soft.
- **Internal Padding:** 14-18px depending on density mode (`.density-dense` collapses to 10-12px, `.density-sparse` expands to 18-20px).

### Metric Tile
- **Shape:** 12px radius, 1px `rgba(255,255,255,0.06)` outline.
- **Background:** flat `rgba(0,0,0,0.4)`. Sits on top of `.panel`.
- **Layout:** small uppercase label (top, JetBrains Mono 9.5px, letter-spacing 0.2em), heavy value (Share Tech Mono 26px weight 800), optional sub (JetBrains Mono 10px, letter-spacing 0.12em).
- **Density-aware:** all three values scale via `.density-sparse` / `.density-dense` modifiers on the shell.

### Inputs / Fields
- **Style:** inherited from base. No dedicated `.input` class yet; fields use ghost-button-style outlines. Inputs exist in scanner setup, bot/paper setup, journal filters and Settings, and plan editing will add price fields to the Play Inspector.
- **Numeric fields:** JetBrains Mono, tabular-nums, right-aligned, unit suffix visible (price, %, R). On phones use `inputmode="decimal"` and at least 44px height.
- **Focus:** 2px outline using `var(--accent)`, offset 2px (`outline:2px solid var(--accent); outline-offset:2px`). Used on the hamburger button and adopted across keyboardable affordances.

### Navigation
- **Topbar:** brand mark + nav links + topbar-right status cluster. Read `Topbar.tsx` for its current contents; don't assume a specific pill set.
- **Nav links:** JetBrains Mono 11px weight 600, uppercase, letter-spacing 0.16em, `var(--fg-3)` at rest. Active link picks up `var(--accent)` text, accent-tinted border and background. Hover lifts to `var(--fg)` with a faint white overlay.
- **Mobile:** ≤700px collapses the nav into a slide-in drawer keyed to the right edge, backdrop-blur darkened. Hamburger appears in the topbar; the nav and status cluster move into the drawer. A running bot session should stay visible from the collapsed topbar.

### Play Inspector (signature component)
- One chart modal, `src/components/hud/PlayInspector.tsx`, used for scanner setups, open positions, pending entries and journal trades (replay planned). Extend it; don't fork it per screen. Read-only today; the edit state below is the target.
- **Layout:** chart dominant (≥60% of the modal on desktop, full-width and most of the height on phones). A compact header strip shows symbol, side chip, mode chip, PAPER/LIVE chip and the order state. Below or beside it: risk, size, R:R, unrealized/estimated P&L and distance-to-stop/targets as metric tiles. Then the "why" (score vs threshold, top families, anchor structure). Then actions.
- **Chart lines:** entry (or zone band), stop (red), targets (green, numbered), current price. Lines are draggable when editing is allowed; values tick live and R:R/P&L recompute as the line moves.
- **Edit state:** a visible MODIFIED chip, the original plan as a faint ghost line, and a risk meter that turns red and blocks save on a breach. Save and revert are explicit; LIVE adds a confirm step.
- **Phone:** full-screen sheet, chart on top, sticky action bar at the bottom within thumb reach.

### Modal / Sheet
- Desktop: centered native dialog, Modal Lift shadow, blurred backdrop. Phone: full-screen sheet sliding up (transform/opacity only, ~200ms ease-out), with a sticky header holding title and close.
- Content inside uses real layout (tiles, tables, charts, labeled sections), not paragraphs of text.

### Rank insignia (future)
- For the deferred rank system: HUD-patch style insignia using the accent family and Share Tech Mono labels, with a scan-sweep or glow reveal when earned. No confetti, coins or slot animations.

### Orb (signature component)
- 40px square, contains a 14px solid core, a pinging ring (opacity 0.25, scales to 2.2x over 2.5s), and a blurred halo. Green/amber/red variants matching status. The product's defining live-indicator. Appears in BotStatus, ActiveScanBeacon, and any "is this running?" question the operator might have.

### Reticle (signature component)
- An SVG crosshair scaled to 120% of container, two counter-rotating rings (45s and 30s), opacity 0.18. Sits behind primary content on Scanner and Landing scope panels. Toggleable via `.hud-overlays-off`. Conveys "the system is watching" without competing for attention.

### Tactical Background (signature component)
- A four-layer composition pinned at z-index -10: gradient base, drifting radial glows in the accent color (30s loop), a soft dot grid (40px spacing, drifting 120s), a sweeping scanline (8s sweep), and a fractal-noise grain overlay (0.04 opacity, 0.5s flicker). All four layers read `var(--accent)`, so the ambient color will follow state once the dynamic accent is wired.

### HUD Progress Bar (signature component)
- 6px height, gradient from red (left = stop loss) through neutral mid through green (right = take profit). 12px circular marker with accent border and glow, animated `left` transition with `cubic-bezier(0.22, 0.9, 0.3, 1)` over 0.8s. Used on open positions to show price-relative-to-plan in a single glance.

## 6. Do's and Don'ts

### Do:
- **Do** use `var(--accent)` for any element that reflects operating state. It is fixed green today and will rebind by state; hard-coded colors are a bug either way.
- **Do** tint every neutral toward olive. Surfaces sit at chroma 0.008-0.015 on hues 120-150. Pure-gray neutrals read wrong on this palette.
- **Do** reach for chips and labels before reaching for prose. If a status can be a pill, it is a pill.
- **Do** stack monospace fonts by role: Share Tech Mono for display chrome, JetBrains Mono for labels and numerics, Inter only for actual prose.
- **Do** use letter-spacing 0.16-0.22em on every mono uppercase string. The spacing is structural, not cosmetic.
- **Do** keep panels flat at rest. Glow only on `.panel-accent` and live-state surfaces.
- **Do** put the accent dot on every `.sec-title`. The pulsing dot signals the panel is participating in the current state.
- **Do** capitalize mode labels and signal tags (STEALTH, ARMED, FIRED, REJECTED). Lowercase chrome reads as a SaaS dashboard.
- **Do** include a `density-sparse` / `density-dense` modifier path on any new tile or row component.
- **Do** design the phone layout deliberately for every new surface and check it at 390px before calling it done.
- **Do** use motion to explain change: values ticking, lines tracking drags, sheets sliding. Respect reduced motion.

### Don't:
- **Don't** use `#000` or `#fff`. Every neutral is olive-tinted OKLCH. Pure-black backgrounds are forbidden.
- **Don't** use Inter for chrome (labels, buttons, chips, page titles, section titles, metric values). Inter is for prose only.
- **Don't** use em dashes in UI copy. Use commas, colons, semicolons, periods, or parentheses. Two hyphens (`--`) is also banned.
- **Don't** use purple-to-blue gradients, especially on hero metrics or CTAs. This is the SaaS-template reflex the system explicitly rejects.
- **Don't** stack cards inside cards. A panel may contain metric-tiles or pos cards, but a `.metric-tile` inside a `.metric-tile` inside a `.panel` is wrong.
- **Don't** use side-stripe borders. No `border-left: 4px solid <color>` as a status accent. Use a corner-tag, a chip, full-border + tint, or the panel-accent glow.
- **Don't** use bounce or elastic easing. Animations use exponential ease-out (the marker transition uses `cubic-bezier(0.22, 0.9, 0.3, 1)`; the glow loops are simple `ease-in-out`). No `cubic-bezier` with overshoot.
- **Don't** drop-shadow surfaces by default. Shadows are state, not decoration. Glassmorphism (`backdrop-filter: blur(...)`) is allowed only on the modal backdrop, where the blur serves z-layering.
- **Don't** animate layout properties (width, height, top, left, padding, margin). Animate transforms and opacity. The marker bar animates `left`, which is the one tolerated exception, and only because the bar is purely decorative geometry, not layout.
- **Don't** use illustrated empty states, soft pastels, "Welcome back!" copy, or any consumer-finance softness. The empty state for a scan with no candidates is a chip that says `NO CANDIDATES` and a one-line reason, not a friendly illustration.
- **Don't** introduce a hero-metric template (big number + tiny label + supporting stat + gradient accent). That's the AI-tool landing reflex; product surfaces don't get it, and landing has its own register-specific hero treatment.
- **Don't** change scores, thresholds, weights or mode minimums from the design layer. They belong to the operator and change only on explicit request with evidence (see PRODUCT.md strategic principles). The design layer displays them; it doesn't tune them.
- **Don't** hide detail in dropdowns or accordions that expand into text walls. Use a modal or sheet with structure.
- **Don't** let an ambient effect look like a state signal (for example, a pulsing orb on idle).
