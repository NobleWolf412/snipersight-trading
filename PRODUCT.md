---
name: SniperSight
description: Smart Money Concepts trading intelligence with defensible signals and explicit confluence
register: product
---

# SniperSight

A trading intelligence system that scores Smart Money Concepts setups across timeframes, plans the trade, validates the risk, and either fires it (live or paper) or rejects it with reasons. Built for an operator who needs every signal to be defensible, every rejection to be loud, and every silent failure to surface.

## Users

**The Operator (primary).** One trader running the system end-to-end. Reads SMC fluently, codes in Python and React, treats the HUD as a cockpit not a dashboard. Wants signal, not narrative. Will paste log output into AI for diagnosis. Operates the bot and the scanner side-by-side. Tolerates density; refuses noise.

**The Reviewer (secondary).** The same operator, hours or days later, auditing why a trade fired or didn't. Needs the rejection panel, the cycle audit strip, and the journal to reconstruct what the engine saw and decided.

This product is not for casual finance users; it is built for experienced traders who want rigorous technical analysis and explicit decision evidence.

## Product purpose

Turn SMC theory into auditable, defensible signals. Specifically:

- Score confluence with weighted inputs, synergy bonuses, conflict penalties, and pre-scoring gates that fail loud
- Run four scanner modes (Overwatch / Strike / Surgical / Stealth) on one pipeline, each with its own thresholds and timeframe stack
- Detect regime (percentage-ATR-based) and gate signals through per-mode regime policies, not advisory hints
- Plan the trade (entry, stop, target) once confluence clears; validate the risk; let the bot execute if mode allows
- Surface every decision point as inspectable output — telemetry events, diagnostic scripts, structured logs, the rejection panel

The system optimizes for **observability**. A correct signal that's invisible is barely better than a wrong one.

## Brand register: PRODUCT

Design serves the product. The HUD is a working cockpit, not a marketing surface. The landing page is the one exception (brand register); every other route is product.

## Tone of voice

- **Direct.** No hedging copy, no "we" voice, no emoji. Imperative or declarative.
- **Terse.** Labels in `JetBrains Mono` uppercase. Six-character section titles where possible. Never a sentence where a chip will do.
- **Tactical, not military-LARP.** Words like SCAN, FIRE, REJECT, BREACH, ARMED — earned by the function, not sprinkled for vibe. No "engaging targets" or "mission critical."
- **Numeric where possible.** Show the score, the threshold, the delta. Show the regime label. Show the conflict density count. Don't paraphrase.
- **Loud failures.** Reject reasons are visible by default, not hidden behind an "expand" affordance. Diagnostic scripts return paste-friendly output: short summary first, structured detail second, raw data last.

## Anti-references

What SniperSight is **not** allowed to look or feel like:

- **Generic SaaS dashboards.** Inter for everything, purple-to-blue gradients, hero-metric cards in a 4-column grid, cards nested in cards, "Welcome back, Matt" headers. The whole training-data SaaS reflex.
- **Crypto-bro casino UIs.** Animated charts as decoration, RGB neon for showmanship, leaderboards, gamified XP, gradient buttons that pulse for no reason, "Are you bullish or bearish?" polls.
- **Consumer finance softness.** Robinhood / Coinbase pastels, illustrated empty states, friendly rounded everything, "Your portfolio is up 2.3% — nice work!" tone.
- **Bloomberg-terminal nostalgia LARP.** Pure `#0F0` on `#000`, unreadable density, gratuitous tickers that don't tick for anything, fake "subscribe" Easter eggs.
- **AI-tool landing-page reflex.** White background, vague purple-to-orange gradient, "Intelligent ___ for modern traders," hero image of a wireframe dashboard floating against a starfield.
- **Glassmorphism as decoration.** Blurred panels with no purpose. Glass is allowed only when it serves z-layering (the modal backdrop is the one earned case).
- **Em dashes in UI copy.** Replaced with commas, colons, semicolons, periods, or parentheses. Never `--` either.

## Strategic principles

These are non-negotiable. They come from the engine, not the design layer; the design layer just makes them visible.

1. **Confluence over conviction.** No single input gets to fire a signal. The score is a weighted sum with synergy bonuses and explicit conflict penalties. Pre-scoring gates hard-fail before scoring even runs.
2. **Precision over volume.** Four scanner modes, each with its own minimum threshold (68-72). The frontend can override upward but never downward.
3. **Truth over narrative.** Every signal must be defensible by its breakdown. The Confluence Breakdown and Rejection Panel are surfaces where the engine has to show its work.
4. **Symmetry.** Bullish and bearish signals are treated identically. Long/short test pairs are mandatory for direction-aware code.
5. **Observability first.** Every non-trivial decision produces inspectable output. Telemetry events, diagnostic scripts, structured rejection reasons. Silent skips are bugs.
6. **Loud failures.** Assertions over fallbacks. Explicit rejections logged with reason codes. Never suppress an exception to make output cleaner.
7. **One engine, many modes.** All scanner modes route through the same orchestrator pipeline. Mode is a profile string, not a separate process. Same for bot vs scanner: shared pipeline, mode-gated execution.

## Surface inventory

Routes that exist in the HUD, with register notes:

- `/` — Landing (brand register; the one identity-driven surface)
- `/scanner` — Scanner cockpit (product)
- `/bot` — Bot status + paper/live toggle (product, hard-gated copy near live mode)
- `/intel` — Macro intel: regime, sessions, kill zones, dominance (product)
- `/journal` — Trade history + per-trade breakdown (product)
- `/training` — SMC reference + interactive drills (product)
- `/settings` — Local-state preferences (product, deliberately quiet)

Every product surface uses the same chrome (Topbar, FooterStatus, panels, chips, metric-tiles). Landing is allowed to break the chrome to do its job.
