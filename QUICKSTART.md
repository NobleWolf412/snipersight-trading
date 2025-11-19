# SniperSight Quick Start Guide

## What is SniperSight?

SniperSight is a comprehensive architectural blueprint for building an **institutional-grade crypto market scanner** that leverages Smart-Money Concepts (SMC) to identify high-probability trading setups across multiple timeframes.

This is a **documentation and reference implementation** that provides:

✅ Complete Product Requirements Document (PRD)
✅ Detailed System Architecture
✅ Comprehensive Project Structure Reference
✅ Implementation Guidelines
✅ Contract Definitions and Data Models
✅ Quality Gates and Verification Checklists

## Understanding This Repository

### What You're Looking At

This is a **Spark application** (TypeScript/React) that serves as an **interactive documentation viewer** for the SniperSight architecture.

The actual SniperSight scanner should be **implemented in Python** following the architectural blueprint provided in the documentation files.

### Key Documentation Files

📄 **PRD.md** - Complete product requirements, features, design specifications
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
⚠️ This is a **blueprint and specification**, not a working scanner
⚠️ Actual implementation should be in **Python** following the architecture
⚠️ Focus on **discipline, verification, and quality gates**
⚠️ Every component must be **testable and deterministic**

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
