---
name: SniperSight
description: Smart Money Concepts trading intelligence with defensible signals and explicit evidence
register: product
---

# SniperSight

A trading intelligence system that scores Smart Money Concepts setups across timeframes, plans the trade, validates the risk, and either executes it (paper, testnet or live) or rejects it with reasons. Built for an operator who needs every signal to be defensible, every rejection to be loud, and every silent failure to surface.

Implemented behavior is documented in [docs/ARCHITECTURE_INDEX.md](docs/ARCHITECTURE_INDEX.md). When this file and the index disagree about mechanics, the index wins. This file owns intent, users, tone and design principles.

## Users

**The Operator (primary).** One trader running the system end-to-end. Reads SMC fluently, codes in Python and React, treats the HUD as a cockpit, not a dashboard. Wants signal, not narrative. Will paste log output into AI for diagnosis. Operates the bot and the scanner side by side. Tolerates density; refuses noise.

**The Reviewer (secondary).** The same operator, hours or days later, auditing why a trade fired or didn't. Needs the rejection panel, the gauntlet breakdown and the journal to reconstruct what the engine saw and decided.

This product is not for casual finance users; it is built for experienced traders who want rigorous technical analysis and explicit decision evidence.

## Product purpose

Turn SMC theory into auditable, defensible signals. Specifically:

- Score setups against fixed evidence-family budgets with explicit eligibility. Correlated alternatives, missing data and macro overlays cannot enlarge a family's credit. Gates fail loud before a score is accepted. Mechanics: [Score and plan](docs/ARCHITECTURE_INDEX.md#entry-points-and-state-owners).
- Run four scanner modes (Overwatch / Strike / Surgical / Stealth) on one pipeline. Each mode resolves a complete playbook: profile, timeframes, planner settings and minimum thresholds.
- Detect market regime from shared daily data and offer mode advice (allowed mode, stand aside, or unavailable). Advice is a hypothesis, not a win probability. Scanner mode choice stays manual.
- Plan the trade (entry, stop, target) once evidence clears; validate the risk; let the bot execute if the session allows.
- Surface every decision point as inspectable output: telemetry events, diagnostic scripts, structured logs, the rejection panel.

Scores and score/RR ranking are not yet calibrated against outcomes. The UI must not present them as probabilities.

The system optimizes for **observability**. A correct signal that's invisible is barely better than a wrong one.

## Brand register: PRODUCT

Design serves the product. The HUD is a working cockpit, not a marketing surface. The landing page is the one exception (brand register); every other route is product. Even on the landing page, examples must be labeled as examples, and claims must describe implemented capabilities.

## Tone of voice

- **Direct.** No hedging copy, no "we" voice, no emoji. Imperative or declarative.
- **Terse.** Never a sentence where a chip will do.
- **Type roles.** `JetBrains Mono` for numbers, symbols, chips and short state labels (uppercase allowed there). Sentence case for headings, explanations, errors and anything longer than a few words. Small dim uppercase text is not a substitute for hierarchy.
- **Tactical, not military LARP.** Words like SCAN, FIRE, REJECT, BREACH, ARMED are earned by the function, not sprinkled for vibe. No "engaging targets" or "mission critical."
- **Numeric where possible.** Show the score, the threshold, the delta. Show the regime label. Don't paraphrase.
- **Loud failures.** Reject reasons are visible by default, not hidden behind an "expand" affordance. Supporting detail (family ledgers, raw inputs, diagnostics) may collapse; the reason itself may not. Diagnostic scripts return paste-friendly output: short summary first, structured detail second, raw data last.

## Simplicity

- **One primary task per screen.** Secondary evidence is arranged around it, not stacked in front of it. On a phone, the primary action is reachable without scrolling past setup chrome.
- **No ornament that implies activity.** Animation, glow, pulsing and "live" labels only where an actual event or stream backs them. A static or stale surface looks static or stale.
- **State is explicit.** Paper, testnet and live are always distinguishable. Idle, loading, error, partial, stale and recovery states each have a visible form. Unknown quantities, fees and P&L render as unknown, never as zero.
- **One owner per behavior.** Scan lifecycle, sessions, feeds, replay and financial display keep their current owners (see the index). Simplifying the UI never means merging these into a generic context, cache or retrying client.
- **Fix in place before moving.** Split oversized screens where they live. Directory restructures need a concrete problem they solve, not a target layout.

## Anti-references

What SniperSight is **not** allowed to look or feel like:

- **Generic SaaS dashboards.** Inter for everything, purple-to-blue gradients, hero-metric cards in a 4-column grid, cards nested in cards, "Welcome back, Matt" headers. The whole training-data SaaS reflex.
- **Crypto-bro casino UIs.** Animated charts as decoration, RGB neon for showmanship, leaderboards, gamified XP, gradient buttons that pulse for no reason, "Are you bullish or bearish?" polls.
- **Consumer finance softness.** Robinhood / Coinbase pastels, illustrated empty states, friendly rounded everything, "Your portfolio is up 2.3%, nice work!" tone.
- **Bloomberg-terminal nostalgia LARP.** Pure `#0F0` on `#000`, unreadable density, gratuitous tickers that don't tick for anything, fake "subscribe" Easter eggs.
- **AI-tool landing-page reflex.** White background, vague purple-to-orange gradient, "Intelligent ___ for modern traders," hero image of a wireframe dashboard floating against a starfield.
- **Glassmorphism as decoration.** Blurred panels with no purpose. Glass is allowed only when it serves z-layering (the modal backdrop is the one earned case).
- **Em dashes in UI copy.** Replaced with commas, colons, semicolons, periods, or parentheses. Never `--` either.

## Strategic principles

These are non-negotiable. They come from the engine, not the design layer; the design layer just makes them visible.

1. **Confluence over conviction.** No single input fires a signal. Positive credit comes from fixed evidence-family budgets; no family can be inflated by correlated or missing inputs. Gates hard-fail before a score is accepted.
2. **Precision over volume.** Scanner modes provide default thresholds. Request and bot-session overrides can change effective values; read the current configuration path before interpreting a score cutoff. See [configuration ownership](docs/ARCHITECTURE_INDEX.md#decision-contracts-and-configuration-precedence).
3. **Truth over narrative.** Every signal must be defensible by its breakdown. The gauntlet breakdown and rejection panel are where the engine shows its work.
4. **Symmetry.** Bullish and bearish signals are treated identically. Long/short test pairs are mandatory for direction-aware code.
5. **Observability first.** Every non-trivial decision produces inspectable output. Silent skips are bugs.
6. **Loud failures.** Assertions over fallbacks. Explicit rejections logged with reason codes. Never suppress an exception to make output cleaner.
7. **One engine, many modes.** All scanner modes route through the same orchestrator pipeline. Mode is a profile, not a separate process. Paper and live sessions keep separate services and execution paths.

## Surface inventory

Status: **implemented** = working end to end; **partial** = works with known gaps; **scaffold** = placeholder, not a usable feature.

| Route | Purpose | Status |
|---|---|---|
| `/` | Landing (brand register). Explain the tool, open the scanner | Implemented; static examples must be labeled as examples |
| `/scanner` | Choose a mode, run a scan, review setups and rejections | Implemented |
| `/bot` | Route to the current session owner | Implemented |
| `/bot/setup` | Review risk and start a live session | Implemented; explicit LIVE preflight. Testnet is supported by the service, not selectable on this screen |
| `/bot/status` | Monitor and control the running session | Implemented |
| `/training/range` | Configure and run a paper session | Implemented |
| `/journal` | Review completed execution records; filter and export | Implemented; research controls live in /training/drills |
| `/intel` | Market context: regime, mode advice, sessions, funding | Implemented; some fields can be unavailable |
| `/training` | Hub for learning and research tools | Implemented |
| `/training/replay` | Step through historical candles with causal evidence | Implemented; candle/structure playback. Signal replay is unavailable when required historical inputs are missing |
| `/training/drills` | Experimental model tools | Partial; research only |
| `/training/lessons` | Lesson library | Implemented; nine lazy chapters with browser read/resume progress. Historical teaching examples are labeled |
| `/settings` | Browser preferences (deliberately quiet) | Implemented |

Redirects: `/scan`, `/results`, `/scanner/setup`, `/scanner/status` → `/scanner`; `/market`, `/htf` → `/intel`. Unknown routes show recovery links.

Every product surface uses the same chrome (Topbar, FooterStatus, panels, chips). Landing is allowed to break the chrome to do its job. Update this table in the same commit that changes a route's status.

## Development progress (gamified)

The game lives in development tracking, never in the product UI.

- **Points come from verified outcomes**, such as a P1 or P2 finding fixed and verified, a screen meeting its acceptance criteria, or a confirmed orphan removed with reference checks.
- **One change scores once.** Removing a module, its provider and its dependency in one change counts as one item.
- **No points for** line counts, moving code, comment deletion, generated files, weakened tests, historical records, or fabricated measurements.
- **Trading results never score.** Signals, orders, win rate and P&L are not development progress.
- **A level clears only when its stated gate is met**, and reopens if later evidence fails it.
- **Progress claims must be committed.** Work that exists only in a local tree doesn't count.

## Third-party attribution

License obligations that must surface visibly in the UI:

- **CoinGecko (Demo API plan):** terms require visible attribution wherever CoinGecko data is rendered or implicitly relied on. Used by `backend/analysis/symbol_classifier.py` to categorize symbols (MAJOR/MEME/DEFI/AI/GAMING/LAYER1/LAYER2). Suggested placement: a one-line "Market category data: CoinGecko" credit in `FooterStatus` so it appears on every product route. Linked to `https://www.coingecko.com`.
