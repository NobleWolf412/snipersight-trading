---
name: SniperSight
description: Smart Money Concepts trading intelligence with defensible signals, explicit evidence and a tactical pro-terminal feel
register: product
---

# SniperSight

A trading intelligence system that scores Smart Money Concepts setups across timeframes, plans the trade, validates the risk, and either executes it (paper, testnet or live) or rejects it with reasons. Built for an operator who needs every signal to be defensible, every rejection to be loud, and every silent failure to surface. It should feel like a pro trading terminal wearing a tactical HUD: chart-led, crisp and fast, with the SniperSight identity in the motion, type and effects.

Implemented behavior is documented in [docs/ARCHITECTURE_INDEX.md](docs/ARCHITECTURE_INDEX.md). When this file and the index disagree about mechanics, the index wins. This file owns intent, users, tone, priorities and product principles. [DESIGN.md](DESIGN.md) owns the visual system.

## Current phase (reviewed 2026-10-10)

Two tracks run in parallel:

1. **Backend: debug and prove the trading logic.** Execution, accounting and silent failures come first, then strategy correctness. Paper results are evidence, not proof.
2. **UI: reach the target look and feel.** The tactical HUD is restored but not yet where the operator wants it. Priorities are the phone experience, the Play Inspector, visible rejection reasons and bot-entry editing (below).

Deferred until the trading logic is proven: ML training and activation (deferred to avoid training on false results), product gamification, and token integration. Agents do not build these yet. They do leave room for them in layouts and data models.

## Users

**The Operator (primary, today).** One trader running the system end to end, about 90% of the time **from a phone while out and about**, and on a desktop for deep work. Reads SMC fluently. Directs the build and audits results. Wants signal, not narrative. Checks bot status, charts, setups and positions on the go, and expects to act from the phone as easily as from the PC. Tolerates density on desktop; refuses clutter on the phone.

**The Reviewer (same person, later).** Audits why a trade fired or didn't. Needs the rejection reasons, the gauntlet breakdown and the journal to reconstruct what the engine saw and decided, and whether a manual override changed the outcome.

**Public traders (future).** SniperSight will eventually open to other experienced traders, with ranks, achievements and a token. Don't build accounts, multi-tenancy or token plumbing yet. Avoid choices that would make them impossible later (for example, hard-coding single-user assumptions into journal record shapes).

This product is not for casual finance users. It is for traders who want rigorous technical analysis and explicit decision evidence.

## Product purpose

Turn SMC theory into auditable, defensible signals and make them actionable from anywhere:

- Score setups against fixed evidence-family budgets with explicit eligibility. Correlated alternatives, missing data and macro overlays cannot enlarge a family's credit. Gates fail loud before a score is accepted. Mechanics: [Score and plan](docs/ARCHITECTURE_INDEX.md#entry-points-and-state-owners).
- Run four scanner modes (Overwatch / Strike / Surgical / Stealth) on one pipeline. Each mode resolves a complete playbook: profile, timeframes, planner settings and minimum thresholds.
- Detect market regime from shared daily data and offer mode advice (allowed mode, stand aside, or unavailable). Advice is a hypothesis, not a win probability. Scanner mode choice stays manual.
- Plan the trade (entry, stop, target) once evidence clears; validate the risk; let the bot execute if the session allows; let the operator inspect and adjust it.
- Surface every decision point as inspectable output: telemetry events, diagnostic scripts, structured logs, the rejection view.

Scores and score/RR ranking are not yet calibrated against outcomes. The UI must not present them as probabilities.

The system optimizes for **observability**. A correct signal that's invisible is barely better than a wrong one.

## Core experiences (UI priorities)

These are the screens and interactions that define whether the product feels right. Build toward them.

### Play Inspector

Tapping or clicking any **open position, pending limit order or bot-planned entry** opens a chart modal with everything about that play:

- Real candles with entry (or entry zone), stop, every target and current price drawn on the chart.
- Side, mode, size, risk in account currency and %, R:R, unrealized and estimated P&L, distance to stop and targets.
- Why the engine took it: score versus threshold, the family breakdown and the key structure it anchored on.
- Order state and lifecycle (pending, partial, filled, protected), with unknowns shown as unknown.
- Actions: modify (below), cancel or close, each with a deliberate confirm.

The same modal component serves scanner setups, bot status, the journal (read-only) and replay. Build one inspector, not four.

### Editing a bot-planned or open play

When the bot has planned an entry or placed an order, the operator may modify entry, stop and targets from the chart (dragging lines or entering values). As values change, the UI recomputes R:R, risk, estimated profit/loss and size **live**. If the operator does nothing, the bot executes exactly as planned.

Guardrails, identical for paper and live:

- **Risk cap enforced.** An edit cannot push planned risk past the session's risk-per-trade budget or available margin. The UI shows the breach and blocks the save. It does not silently clamp.
- **A stop always exists.** The stop can move; it cannot be removed.
- **LIVE needs an explicit extra confirm.** Paper and testnet use the same flow without the extra step.
- **Overrides are recorded.** The journal stores the bot's original plan beside the operator's edit, so results can be compared later (bot plan versus manual override).

### Rejection reasons at a glance

The operator must see quickly why setups are gated out or rejected: per scan and per symbol, grouped by reason, with the score, threshold and delta. The top reasons are visible without opening anything. Per-symbol detail opens in a modal, not an inline wall of text.

### Phone first-class

Phone and desktop must look equally good. On a phone:

- Bot status, open plays, setups and charts are reachable within one or two taps.
- Charts are large, touch-friendly and readable; the Play Inspector is full-screen.
- The primary action is reachable without scrolling past setup chrome. Nothing important hides in a dropdown.

### Landing

Keep the brand landing page. Remove its route-card grid (Intel, Scanner, Bot status, Journal, Training, Setup), which duplicates the top bar. Keep the hero and its primary CTAs. When a bot session is running, the landing page shows a prominent live entry point to `/bot/status` with the session's real state (paper/live, mode, open positions), and no indicator when nothing is running.

## Progressive disclosure: modals, not text piles

When a surface has more detail than fits, open it in a **modal or dedicated panel** with a proper layout: chart, tables, labeled sections. Never expand a dropdown, accordion or `<details>` into an unformatted wall of text. Collapsible rows are acceptable only for short, structured content (a few labeled values). This applies everywhere, especially Training (lessons, drills, replay), the journal, the gauntlet and the rejection view.

## Brand register: PRODUCT

Design serves the product. The HUD is a working cockpit, not a marketing surface. The landing page is the one brand-register exception. Even there, examples must be labeled as examples and claims must describe implemented capabilities.

## Tone of voice

- **Direct.** No hedging copy, no "we" voice, no emoji. Imperative or declarative.
- **Terse.** Never a sentence where a chip will do.
- **Type roles.** `JetBrains Mono` for numbers, symbols, chips and short state labels (uppercase allowed there). `Share Tech Mono` for HUD display headings; uppercase is allowed in display headings and concise console names. Sentence case for explanations, errors and prose. Small dim uppercase text is not a substitute for hierarchy.
- **Tactical, not LARP.** Words like SCAN, FIRE, REJECT, BREACH and ARMED are earned by the function, not sprinkled for vibe. Military rank language is welcome in the future rank system. "Engaging targets" or "mission critical" filler is not.
- **Numeric where possible.** Show the score, the threshold, the delta. Show the regime label. Don't paraphrase.
- **Loud failures.** Reject reasons are visible by default. Supporting detail (family ledgers, raw inputs, diagnostics) may move into a modal; the reason itself may not. Diagnostic scripts return paste-friendly output: short summary first, structured detail second, raw data last.

## Simplicity

- **One primary task per screen.** Secondary evidence is arranged around it, not stacked in front of it. Keep decision requirements beside the choice, including requirements inside each scanner mode card on every device. Hiding essential configuration behind a dropdown is not simplification.
- **Keep the tactical identity.** Olive surfaces, glow, scanlines, ambient motion and reticles are wanted. The operator likes effects and motion. Ambient effects are decoration; state signals (the orb, accent panel glow, live colors) must reflect real state (see DESIGN.md). Reduced motion and appearance controls remain supported.
- **State is explicit.** Paper, testnet and live are always distinguishable. Idle, loading, error, partial, stale and recovery states each have a visible form. Unknown quantities, fees and P&L render as unknown, never as zero.
- **One owner per behavior.** Scan lifecycle, sessions, feeds, replay and financial display keep their current owners (see the index). Simplifying the UI never means merging these into a generic context, cache or retrying client.
- **Fix in place before moving.** Split oversized screens where they live. Directory restructures need a concrete problem they solve, not a target layout.

## Anti-references

What SniperSight is **not** allowed to look or feel like:

- **Generic SaaS dashboards.** Inter for everything, purple-to-blue gradients, hero-metric cards in a 4-column grid, cards nested in cards, "Welcome back" headers.
- **Crypto-casino UIs.** Slot-machine feedback, confetti, gradient buttons that pulse for no reason, "Are you bullish or bearish?" polls, rewards for gambling behavior. (Ranks and achievements are coming, styled as earned tactical insignia, not casino loot.)
- **Consumer finance softness.** Pastels, illustrated empty states, friendly rounded everything, "Your portfolio is up 2.3%, nice work!" tone.
- **Bloomberg-terminal nostalgia LARP.** Pure `#0F0` on `#000`, unreadable density, tickers that don't tick for anything.
- **AI-tool landing-page reflex.** White background, vague purple-to-orange gradient, "Intelligent ___ for modern traders," a wireframe dashboard floating against a starfield.
- **Glassmorphism as decoration.** Blur is allowed only where it serves z-layering (modal and sheet backdrops).
- **Dropdown text dumps.** See progressive disclosure above.
- **Em dashes in UI copy.** Use commas, colons, semicolons, periods or parentheses. Never `--` either.

## Strategic principles

These are non-negotiable. They come from the engine; the design layer makes them visible.

1. **Confluence over conviction.** No single input fires a signal. Positive credit comes from fixed evidence-family budgets; no family can be inflated by correlated or missing inputs. Gates hard-fail before a score is accepted.
2. **Precision over volume.** Scanner modes provide default thresholds. Request and bot-session overrides can change effective values; read the current configuration path before interpreting a score cutoff. See [configuration ownership](docs/ARCHITECTURE_INDEX.md#decision-contracts-and-configuration-precedence).
3. **Strategy numbers belong to the operator.** Weights, thresholds and mode minimums change only when the operator explicitly asks, with a recorded baseline and evidence. Agents may flag a number that looks wrong; they do not change it on their own.
4. **Truth over narrative.** Every signal must be defensible by its breakdown. The gauntlet breakdown and rejection view are where the engine shows its work.
5. **Symmetry.** Bullish and bearish signals are treated identically. Long/short test pairs are mandatory for direction-aware code.
6. **Observability first.** Every non-trivial decision produces inspectable output. Silent skips are bugs.
7. **Loud failures.** Assertions over fallbacks. Explicit rejections logged with reason codes. Never suppress an exception to make output cleaner.
8. **One engine, many modes.** All scanner modes route through the same orchestrator pipeline. Mode is a profile, not a separate process. Paper and live sessions keep separate services and execution paths.
9. **Prove logic before ML.** ML stays deferred until scoring, planning and execution are verified, so models are not trained on false results.

## Surface inventory

Status: **implemented** = working end to end; **partial** = works with known gaps; **scaffold** = placeholder, not a usable feature; **planned** = specified here, not built.

| Route / surface | Purpose | Status |
|---|---|---|
| `/` | Landing (brand register). Explain the tool, open the scanner, jump to a running bot | Implemented; route-card grid to be removed and running-bot entry added (planned) |
| `/scanner` | Choose a mode, run a scan, review setups and rejections | Implemented; at-a-glance rejection grouping planned |
| `/bot` | Route to the current session owner | Implemented |
| `/bot/setup` | Review risk and start a live session | Implemented; explicit LIVE preflight. Testnet is supported by the service, not selectable on this screen |
| `/bot/status` | Monitor and control the running session | Implemented; Play Inspector and plan editing planned |
| `/training/range` | Configure and run a paper session | Implemented |
| `/journal` | Review completed execution records; filter and export | Implemented; override comparison planned |
| `/intel` | Market context: regime, mode advice, sessions, funding | Implemented; some fields can be unavailable |
| `/training` | Hub for learning and research tools | Implemented; layout to move detail into modals |
| `/training/replay` | Step through historical candles with causal evidence | Implemented; signal replay is unavailable when required historical inputs are missing |
| `/training/drills` | Experimental model tools | Partial; research only |
| `/training/lessons` | Lesson library | Implemented; nine lazy chapters with browser read/resume progress. Historical teaching examples are labeled |
| `/settings` | Browser preferences (deliberately quiet) | Implemented |
| Play Inspector (modal) | Chart modal for any position, order or planned entry | Planned. `ScannerSetupModal` is the starting point |
| Ranks and achievements | Operator rank and earned insignia | Planned, deferred |

Redirects: `/scan`, `/results`, `/scanner/setup`, `/scanner/status` → `/scanner`; `/market`, `/htf` → `/intel`. Unknown routes show recovery links.

Every product surface uses the same chrome (Topbar, FooterStatus, panels, chips). Landing may break the chrome to do its job. Update this table in the same commit that changes a surface's status.

## Gamification (vision, deferred)

SniperSight will become fun to use the way a good crypto trading platform is: ranks, achievements and, eventually, a token. Build it only after the trading logic is proven. Until then, record the design intent here and leave room in layouts and journal data.

- **Military-rank tactical.** Ranks progress like a service career (for example Recruit → Marksman → Sharpshooter → Sniper → Ghost). Achievements are HUD-style patches and insignia with motion and effects (reveal animations, glow, scan sweeps), never confetti or slot-machine feedback.
- **What earns rank.** All four count, weighted so discipline cannot be bypassed:
  - **Discipline:** followed the plan, kept the stop, respected risk caps, journaled the trade, rule-following streaks.
  - **Risk-adjusted results:** R-multiple, expectancy and drawdown control over a minimum sample size.
  - **Learning:** lessons, drills and replay sessions completed.
  - **Raw P&L and win rate:** counted, but only alongside the minimum sample and risk-cap compliance, so a lucky oversized trade can't buy rank.
- **Honest data only.** Achievements come from recorded evidence (journal, execution records), never from unknown or estimated values. Paper and live achievements are labeled separately.
- **Token (future).** Out of scope until gamification exists and the operator authorizes the work. No wallet, chain or token code before then.

## Development tracking

Separate from product gamification: development progress is scored in the audit ledgers (`docs/audits/`) only for verified outcomes (a P1/P2 fix verified, a screen meeting acceptance criteria, a confirmed orphan removed). One change scores once. No points for line counts, moved code, generated files, weakened tests or fabricated measurements. Trading results never score development progress. Progress claims must be committed.

## Third-party attribution

License obligations that must surface visibly in the UI:

- **CoinGecko (Demo API plan):** terms require visible attribution wherever CoinGecko data is rendered or relied on. It supplies symbol categories (`backend/analysis/symbol_classifier.py`) and the global dominance snapshot behind regime and mode advice (`backend/analysis/dominance_service.py`). The credit is implemented in `FooterStatus` on every product route; its wording ("Market category data") should broaden to cover dominance (for example, "Market data: CoinGecko").
