# SniperSight Quick Start

> **Note:** Earlier versions of this doc described the project as a "blueprint" / "Spark application" / "documentation viewer." That framing is stale — the scanner is built and runs. Below is the actual quick start for the working application. See [README.md](README.md) for the canonical overview, [CLAUDE.md](CLAUDE.md) for operating instructions, and the "Historical blueprint reference" section at the bottom of this file for the original pre-implementation content.

## Run the application

**Prerequisites:**
- Python 3.10+ with `venv` activated
- Node.js + npm installed
- (Optional) Playwright browsers: `npx playwright install chromium` for visual snapshot tests

**Backend (FastAPI on port 8000):**
```bash
python -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend (Vite on port 5000):**
```bash
npm install
npm run dev -- --host 0.0.0.0 --port 5000
```

**Both concurrently:**
```bash
npm run dev:all
```

**Windows convenience launcher:** `C:\start-sniper.bat`.

## Verify the install

```bash
# Backend tests
pytest

# TypeScript type check
npx tsc --noEmit

# Backend contract baselines (§20)
python -m backend.diagnostics.capture_contracts diff   # should print CLEAN
python -m backend.diagnostics.pipeline_smoke verify    # should print CLEAN

# Visual snapshot regression (needs vite dev server on 5000 first)
npm run snapshots:capture
npm run snapshots:report
```

## Scanner modes (CLAUDE.md §4)

| Mode | Profile | Min Score | Critical TFs | Planning TF |
|------|---------|-----------|--------------|-------------|
| OVERWATCH | `macro_surveillance` | 72.0 | 1w, 1d | 4h |
| STRIKE | `intraday_aggressive` | 68.0 | 15m | 15m |
| SURGICAL | `precision` | 70.0 | 15m | 15m |
| STEALTH | `stealth_balanced` | 70.0 | 4h, 1h | 1h |

Bot production mode is STEALTH.

## Where things live

| Topic | Path |
|-------|------|
| Operating instructions | [CLAUDE.md](CLAUDE.md) |
| Pipeline entry | [backend/engine/orchestrator.py](backend/engine/orchestrator.py) → `Orchestrator.scan` |
| Scanner modes | [backend/shared/config/scanner_modes.py](backend/shared/config/scanner_modes.py) |
| Confluence scorer | [backend/strategy/confluence/scorer.py](backend/strategy/confluence/scorer.py) |
| Paper trader | [backend/bot/paper_trading_service.py](backend/bot/paper_trading_service.py) |
| HUD pages | [src/pages/](src/pages/) |
| Decisions log | [backend/diagnostics/decisions/](backend/diagnostics/decisions/) |
| Phase archive | [backend/diagnostics/phase_archive/](backend/diagnostics/phase_archive/) |

## Common diagnostics

```bash
# Why didn't <symbol> generate a signal?
# Use the rejection-forensics agent or:
python -c "from backend.diagnostics import logger; ..."

# Last scan cycle details
curl http://localhost:8000/api/cycles/last

# Symbol cycle context
curl http://localhost:8000/api/market/symbol-cycles?symbol=BTC/USDT
```

## Historical blueprint reference

The content below was authored before the scanner was built. Kept for historical context only — do not treat as authoritative current state.

---

## What is SniperSight (pre-implementation framing)

SniperSight is a comprehensive architectural blueprint for building an **institutional-grade crypto market scanner** that leverages Smart-Money Concepts (SMC) to identify high-probability trading setups across multiple timeframes.

This is a **documentation and reference implementation** that provides:

✅ Complete Product Requirements Document (PRD)
✅ Detailed System Architecture
✅ Comprehensive Project Structure Reference
✅ Implementation Guidelines
✅ Contract Definitions and Data Models
✅ Quality Gates and Verification Checklists

## Understanding This Repository (pre-implementation framing)

### What You're Looking At

This is a **Spark application** (TypeScript/React) that serves as an **interactive documentation viewer** for the SniperSight architecture.

The actual SniperSight scanner should be **implemented in Python** following the architectural blueprint provided in the documentation files.

### Key Documentation Files

📄 **PRD.md** - Complete product requirements, features, design specifications (NOTE: PRD.md has been removed from the repo; see [PRODUCT.md](PRODUCT.md) for current product framing)
📄 **ARCHITECTURE.md** - System architecture, data flow, core principles
📄 **PROJECT_STRUCTURE.md** - Detailed module breakdown with responsibilities

## Core Concepts

### Smart-Money Concepts (SMC)

SniperSight is built around institutional trading concepts:

- **Order Blocks (OB)**: Institutional entry/exit zones
- **Fair Value Gaps (FVG)**: Liquidity imbalances
- **Break of Structure (BOS)**: Trend continuation signals
- **Change of Character (CHoCH)**: Potential reversals
- **Liquidity Sweeps**: Stop hunts before reversals
- **Displacement**: Strong directional moves

### Multi-Timeframe Analysis

The system analyzes 6 timeframes simultaneously:
- **1W** (Weekly) - Major trend
- **1D** (Daily) - Primary structure
- **4H** - Intermediate structure
- **1H** - Entry refinement
- **15m** - Precise entries
- **5m** - Execution timeframe

### Quality Gates

Multi-layered filtering ensures only high-quality signals:

1. **Data Quality Gates** - Complete, valid, recent data
2. **Indicator Quality Gates** - No null/NaN values
3. **SMC Quality Gates** - Fresh structures, proper displacement
4. **Confluence Quality Gates** - Multi-factor alignment, low conflicts
5. **Plan Quality Gates** - Complete plans, valid R:R ratios
6. **Risk Quality Gates** - Position sizing, exposure limits

## Architecture Overview

```
Data Ingestion → Indicators → SMC Detection → Confluence Scoring
    ↓                ↓              ↓                 ↓
  Cache         Multi-TF       Order Blocks      HTF Alignment
  System        Analysis          FVGs           BTC Impulse
                                  BOS/CHoCH      Regime Filter
                                  Sweeps
                                     ↓
                            Trade Plan Generation
                                     ↓
                            Risk Validation
                                     ↓
                            Notification / Execution
```

## Package Structure

```
snipersight/
├── contracts/          # API boundaries (what Spark/Copilot must respect)
├── shared/            # Models, configs, utilities (single source of truth)
├── data/              # Exchange adapters, caching, ingestion
├── indicators/        # Technical analysis computation
├── strategy/          # SMC detection, confluence, planning
│   ├── smc/          # Order blocks, FVGs, BOS/CHoCH, sweeps
│   ├── confluence/   # Scoring, regime detection, plugins
│   └── planner/      # Entry, stops, targets, R:R
├── risk/              # Position sizing, exposure, compliance
├── bot/               # Telegram, execution, charts, telemetry
├── engine/            # Pipeline orchestration, hooks, plugins
├── ml/                # Future ML integration
├── tests/             # Fixtures, unit, integration, backtest
├── docs/              # Documentation
└── scripts/           # Operational scripts
```

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
- Set up Python project
- Implement `shared/models/` data structures
- Create `contracts/` API definitions
- Build configuration system

### Phase 2: Data Layer (Week 2-3)
- Exchange adapters (Binance, Bybit)
- Caching system
- Ingestion pipeline
- Test fixtures

### Phase 3: Analysis Layer (Week 3-5)
- Indicator computation
- SMC detection (OB, FVG, BOS/CHoCH, sweeps)
- Confluence scoring
- Trade planner

### Phase 4: Risk & Execution (Week 5-6)
- Risk management
- Notification system (Telegram)
- Optional executor
- Telemetry

### Phase 5: Orchestration (Week 6-7)
- Pipeline controller
- Context management
- Hook system
- CLI interface

### Phase 6: Quality & Testing (Week 7-8)
- Quality gates implementation
- Backtest framework
- Verification checklist
- Comprehensive tests

## Key Design Principles

### 1. No-Null, Actionable Outputs
Every signal must include:
- Complete trade plan
- Populated rationale (no empty sections)
- All entries, stops, targets defined
- Risk metrics calculated

### 2. Zero Silent Failures
- Missing indicators → Hard error
- Incomplete SMC data → Hard error
- Blank rationale → Hard error
- Quality gate failures → Explicit rejection with reason

### 3. Verification-Ready
- Deterministic fixtures for testing
- Schema validation on all outputs
- Backtest framework built-in
- Quality metrics tracked

### 4. Plugin-Friendly & ML-Ready
- Pluggable indicators via registry
- Extensible confluence scoring
- Hook system for ML integration
- Contract-driven interfaces

### 5. Preserve Smart-Money Edge
- Multi-timeframe context required
- HTF alignment enforced
- BTC impulse gating
- Freshness and displacement checks
- Structural discipline

## Configuration Profiles

### Balanced (Default)
- Moderate thresholds
- Multi-factor confluence required
- R:R ≥ 2.5
- 4H primary timeframe

### Trend
- Trend-following emphasis
- Momentum indicators weighted higher
- Strict HTF alignment
- Higher displacement requirements

### Range
- Mean-reversion focus
- Tighter entry zones
- Oscillator-heavy scoring
- Reduced target distances

### Aggressive
- Lower confluence thresholds
- Higher leverage allowance
- Shorter timeframe bias (15m/5m)
- Relaxed freshness requirements

### Mobile
- Reduced symbol universe (top 10)
- Extended cache TTLs
- Simplified rationale
- Battery-optimized scanning

## CLI Commands

```bash
# Scan markets with balanced profile
snipersight scan --profile balanced --symbols top20

# Run backtest
snipersight backtest --profile trend --start 2024-01-01 --end 2024-12-31

# Quality audit
snipersight audit --verbose

# Sync cache
snipersight cache sync --timeframes 1W,1D
```

## Notification Output

### Telegram Message Format
```
🎯 SNIPER SIGNAL #42

Symbol: BTC/USDT
Direction: LONG
Setup: Swing Trade (Trend-Following)

📊 CONFLUENCE SCORE: 8.4/10
✅ HTF Bullish Alignment (1W/1D/4H)
✅ Fresh Bullish OB @ 42,150
✅ FVG Fill Confirmed
✅ Liquidity Sweep Confirmed
✅ BTC Impulse Gate: PASSED
⚠️ Minor Conflict: RSI Slightly Overbought

📍 ENTRY ZONES:
Near Entry: 42,250
Far Entry: 42,150 (preferred)

🛡️ STOP LOSS: 41,800 (1.06% risk)

🎯 TARGETS:
T1: 43,200 (2.24% | 50% position)
T2: 44,500 (5.54% | 30% position)
T3: 45,800 (8.60% | 20% position)

📈 RISK:REWARD: 1:3.2

📝 RATIONALE:
Higher timeframes show strong bullish structure...
[Complete multi-paragraph explanation]

[Chart Image]
[JSON Payload]
```

## Data Models

### SniperContext
Central object passed through pipeline:
```python
@dataclass
class SniperContext:
    symbol: str
    profile: str
    run_id: str
    timestamp: datetime
    multi_tf_data: Optional[MultiTimeframeData]
    multi_tf_indicators: Optional[Dict[str, IndicatorSet]]
    smc_snapshot: Optional[SMCSnapshot]
    confluence_breakdown: Optional[ConfluenceBreakdown]
    plan: Optional[TradePlan]
    risk_plan: Optional[RiskPlan]
    metadata: Dict[str, Any]
```

### TradePlan
Complete trade specification:
```python
@dataclass
class TradePlan:
    symbol: str
    direction: str  # "LONG" | "SHORT"
    setup_type: str  # "scalp" | "swing" | "intraday"
    entry_zone: EntryZone
    stop_loss: StopLoss
    targets: List[Target]
    risk_reward: float
    confidence_score: float
    confluence_breakdown: ConfluenceBreakdown
    rationale: str
    metadata: Dict[str, Any]
```

## Quality Metrics

### Signal Quality Targets
- Confluence Score: ≥ 7.0/10
- R:R Ratio: ≥ 2.0 (balanced), ≥ 2.5 (trend)
- HTF Alignment: Required for confluence > 8.0
- Freshness Score: ≥ 0.7 for order blocks
- Displacement Strength: ≥ 1.5 ATR

### Backtest Targets
- Win Rate: ≥ 55% (balanced), ≥ 60% (trend)
- Average R:R: ≥ 2.5
- Profit Factor: ≥ 2.0
- Max Drawdown: ≤ 15%

## Technology Stack

### Core
- Python 3.10+
- pandas / numpy (data manipulation)
- TA-Lib / pandas-ta (indicators)

### Data
- ccxt (exchange connectivity)
- requests (HTTP)
- redis (optional caching)

### Testing
- pytest (test framework)
- hypothesis (property-based testing)

### Utilities
- pydantic (data validation)
- typer / click (CLI)
- python-telegram-bot (notifications)
- plotly / matplotlib (charting)

## Next Steps

### 1. Study the Documentation
- Read **PRD.md** for complete requirements
- Review **ARCHITECTURE.md** for system design
- Explore **PROJECT_STRUCTURE.md** for detailed module specs

### 2. Set Up Development Environment
```bash
# Create Python virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install pandas numpy ccxt ta-lib pydantic pytest typer

# Create project structure
mkdir -p snipersight/{contracts,shared,data,indicators,strategy,risk,bot,engine,ml,tests,docs,scripts}
```

### 3. Start with Foundation
- Implement data models in `shared/models/`
- Define contracts in `contracts/`
- Set up configuration system
- Create test fixtures

### 4. Follow Phased Approach
- Build layer by layer (data → indicators → strategy → risk → bot)
- Test each module in isolation
- Integrate incrementally
- Validate against quality gates

### 5. Maintain Discipline
- ✅ No null fields in outputs
- ✅ Deterministic test fixtures
- ✅ Schema validation everywhere
- ✅ Quality gates enforced
- ✅ Complete rationale always

## Support & Resources

### Documentation Files
- `PRD.md` - Product requirements
- `ARCHITECTURE.md` - System architecture
- `PROJECT_STRUCTURE.md` - Module reference
- `QUICKSTART.md` - This file

### Reference Implementation
This Spark application serves as interactive documentation browser. Use it to explore the architecture and understand the design principles.

### Implementation Notes
✅ This is a **fully functional market scanner** with working backend and UI
✅ Backend is **Python-based** following the architecture documented here
✅ Focus on **discipline, verification, and quality gates**
✅ Every component is **testable and deterministic**

## Philosophy

SniperSight embodies institutional trading discipline:

**Precision over Speed** - Wait for high-quality setups
**Verification over Trust** - Test everything deterministically
**Discipline over Discretion** - Follow the gates
**Completeness over Convenience** - No half-formed signals
**Clarity over Complexity** - Transparent, auditable decisions

Build with the mindset of an institution protecting capital, not a gambler chasing gains.

---

**Ready to build?** Start with the PRD, understand the architecture, and implement phase by phase with rigorous testing at every step.
