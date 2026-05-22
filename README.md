# SniperSight

**Institutional-grade crypto scanner + paper trader + autonomous bot for Smart Money Concepts strategy execution.**

Confluence over conviction. Precision over volume. Truth over narrative.

---

## What this repo is

A working FastAPI backend + React HUD frontend that scans crypto markets across multiple timeframes, applies SMC (Smart Money Concepts) detection, scores confluence per-mode, and runs paper-traded + (gated) live trades through a four-mode scanner system.

Not a blueprint. The scanner is built and runs.

## Stack

- **Backend** — Python 3.10+, FastAPI, uvicorn (port 8000), ccxt for exchange connectivity
- **Frontend** — React 19, TypeScript, custom HUD CSS (no Tailwind — ejected in Phase 7), Vite (port 5000)
- **Data** — Phemex (production), Bybit, OKX, Bitget adapters
- **Storage** — SQLite (`backend/cache/telemetry.db`), JSONL (`backend/cache/trade_journal.jsonl`, `signals.jsonl`)
- **Testing** — pytest (backend), Playwright (visual snapshots)

## Scanner modes

Four modes, all on one orchestrator pipeline (configurations, not separate processes):

| Mode | Profile | Min Score | Critical TFs | Planning TF |
|------|---------|-----------|--------------|-------------|
| OVERWATCH | `macro_surveillance` | 72.0 | 1w, 1d | 4h |
| STRIKE | `intraday_aggressive` | 68.0 | 15m | 15m |
| SURGICAL | `precision` | 70.0 | 15m | 15m |
| STEALTH | `stealth_balanced` | 70.0 | 4h, 1h | 1h |

Bot production mode is STEALTH. The scanner mode picker is for strategy inspection; it does not write to bot state.

## Pipeline (single context object)

`SniperContext` ([backend/engine/context.py](backend/engine/context.py)) passes through every stage and gets progressively populated:

1. Data ingestion → `multi_tf_data`
2. Indicators → `multi_tf_indicators`
3. SMC detection → `smc_snapshot`
4. Macro context → `macro_context`
5. Confluence scoring → `confluence_breakdown`
6. Trade planning → `plan`
7. Risk validation → `risk_plan`

Entry point: `Orchestrator.scan(symbol, profile)` in [backend/engine/orchestrator.py](backend/engine/orchestrator.py).

## Smart-Money Concepts (what's detected)

- **Order Blocks (OB)** — institutional accumulation/distribution zones
- **Fair Value Gaps (FVG)** — liquidity imbalances
- **Break of Structure (BOS)** — trend continuation (preserves temporal ordering, not just level-cross)
- **Change of Character (CHoCH)** — potential reversals
- **Liquidity Sweeps** — stop-hunts before institutional moves
- **Wyckoff cycle logic** — accumulation/distribution phase detection
- **WCL failure** — feeds active short bias

Bullish/bearish detection is symmetric — same logic, same gates, same penalties.

## Confluence scoring

Mode-aware weighted sum with synergy bonuses, conflict penalties, and hard-failing pre-scoring gates (structural anchor, BTC impulse, regime, conflict density). HTF composite collapses correlated HTF inputs into one score. Per-mode minimum thresholds (table above). Frontend can override upward but never downward.

Pre-scoring gates run before scoring; gate failure skips scoring entirely. Soft penalties cannot compensate for a failed gate.

## Regime gating

Enforced, not advisory. Each mode has a `RegimePolicy` in [backend/analysis/regime_policies.py](backend/analysis/regime_policies.py) with `min_regime_score`, `allow_in_risk_off`, position-size adjustments, and confluence adjustments per regime label. Regime detector uses percentage-based ATR, not absolute.

## Workflow + audit discipline

Operating instructions for AI-assisted development live in **[CLAUDE.md](CLAUDE.md)**:
- §10 Standing fixes (do not regress)
- §16 Audit discipline — 14-point rubric enforced by autonomous subagent on every commit
- §17 Task router — declare task type + skills + agent upfront
- §18 Pre-flight discipline — Plan agent for features, diagnostic-in-same-diff for bug fixes, symmetry-guard auto-invoke for §10 surface edits
- §19 Decisions log at `backend/diagnostics/decisions/`
- §20 Backend integrity — contract snapshots at `backend/diagnostics/contracts/`, pipeline_smoke at `backend/diagnostics/pipeline_smoke.py`

Calibration history lives in [`backend/diagnostics/decisions/`](backend/diagnostics/decisions/). HUD rebuild Phase 0–7 archived to [`backend/diagnostics/phase_archive/`](backend/diagnostics/phase_archive/).

## Repository layout (actual)

```
snipersight-trading/
├── CLAUDE.md                              # operating instructions (authoritative)
├── DESIGN.md                              # HUD visual system
├── PRODUCT.md                             # product framing
├── backend/
│   ├── api_server.py                      # FastAPI app entry
│   ├── engine/
│   │   ├── orchestrator.py                # pipeline controller (scan entry point)
│   │   └── context.py                     # SniperContext dataclass
│   ├── strategy/
│   │   ├── confluence/scorer.py           # scoring + pre-scoring gates
│   │   ├── planner/                       # entry zones, stops, targets
│   │   └── smc/                           # OB / FVG / BOS / sweeps / cycles
│   ├── analysis/
│   │   ├── regime_detector.py             # % ATR regime classifier
│   │   └── regime_policies.py             # per-mode regime gating
│   ├── bot/
│   │   ├── paper_trading_service.py       # paper trading orchestration
│   │   ├── executor/                      # paper + live executors, position manager
│   │   └── telemetry/                     # event emission + SQLite storage
│   ├── services/                          # confluence / smc / indicator / scanner service layer
│   ├── shared/config/
│   │   └── scanner_modes.py               # the four modes + RELATIVITY_MAP
│   ├── data/adapters/                     # Phemex / Bybit / OKX / Bitget / Binance
│   ├── routers/                           # FastAPI routers (data, scanner, observability, htf)
│   ├── diagnostics/
│   │   ├── capture_contracts.py           # §20 contract snapshot driver
│   │   ├── pipeline_smoke.py              # §20 structural smoke
│   │   ├── contracts/                     # frozen API/telemetry/pipeline/DB baselines
│   │   ├── decisions/                     # §19 calibration learnings
│   │   ├── phase_archive/                 # completed phases
│   │   └── audit_halts/                   # §16 3-round-fail halts
│   └── tests/                             # pytest suites
├── src/                                   # React HUD frontend
│   ├── pages/                             # one page per route
│   ├── components/hud/                    # HUD primitives (Chip, PageHead, Reticle, etc.)
│   ├── services/                          # API client + scan history
│   ├── hooks/                             # React hooks
│   └── types/api.ts                       # generated from openapi.json
├── tests/visual/                          # Playwright snapshot framework
├── .claude/                               # Claude Code config
│   ├── agents/                            # subagent definitions
│   ├── skills/                            # invokable skills
│   ├── hooks/                             # PreToolUse + PostToolUse enforcement
│   └── settings.json
└── scripts/                               # ops + codegen helpers
```

## Quick start

Backend:
```
python -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8000 --reload
```

Frontend:
```
npm install
npm run dev -- --host 0.0.0.0 --port 5000
```

Combined (if `concurrently` installed):
```
npm run dev:all
```

Windows convenience launcher: `C:\start-sniper.bat`.

## Common operations

```bash
# Contract integrity (§20 Rubric 14)
python -m backend.diagnostics.capture_contracts diff
python -m backend.diagnostics.pipeline_smoke verify

# Type sync (frontend ↔ backend, see §20)
npm run gen:types

# Visual snapshots (Playwright)
npm run snapshots:capture
npm run snapshots:report
npm run snapshots:approve <route> <state>

# Backend tests
pytest

# TypeScript
npx tsc --noEmit
```

## Hard boundaries (CLAUDE.md §15)

- No live trading code paths touched without explicit approval
- No `min_confluence_score` or pre-scoring gate threshold changes without baseline data + documented reason
- No silent reformats, no scope creep
- No mock data swapped where real data is integrated
- Bot mode source is `botConfig.sniperMode`, never `ScannerContext.selectedMode`

## License

Internal. Operator: Matt (maccardi4431@gmail.com). Repo: `NobleWolf412/snipersight-trading`.
