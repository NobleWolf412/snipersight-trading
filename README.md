# SniperSight – Architecture & Project Blueprint

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Status](https://img.shields.io/badge/status-blueprint-orange)
![Type](https://img.shields.io/badge/type-documentation-green)

**An institutional-grade crypto market scanner architecture leveraging Smart-Money Concepts across multi-timeframe analysis.**

---

## 🎯 What is SniperSight?

SniperSight is a **comprehensive architectural blueprint** for building a modular, institutional-grade crypto market scanner designed to evolve into a fully automated trading bot.

This repository contains:

- ✅ **Complete Product Requirements Document (PRD)**
- ✅ **Detailed System Architecture**
- ✅ **Comprehensive Project Structure Reference**
- ✅ **Implementation Guidelines**
- ✅ **Interactive Documentation Viewer**

## 📚 Documentation

### Core Documents

| Document | Description |
|----------|-------------|
| **[PRD.md](PRD.md)** | Complete product requirements, features, design specifications |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | System architecture, data flow, core design principles |
| **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** | Detailed module breakdown with responsibilities |
| **[QUICKSTART.md](QUICKSTART.md)** | Quick start guide and implementation roadmap |

### Interactive Viewer

This repository includes a **Spark application** (TypeScript/React) that serves as an interactive documentation viewer. Launch it to explore the architecture in a user-friendly interface.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI / API Layer                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Engine Orchestrator                       │
│     Pipeline Controller • Context Manager • Hook System      │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
   ┌─────────┐    ┌──────────┐    ┌──────────┐
   │  Data   │    │Indicators│    │ Strategy │
   └─────────┘    └──────────┘    └──────────┘
         │               │               │
         └───────────────┼───────────────┘
                         │
                         ▼
                  ┌─────────────┐
                  │    Risk     │
                  └──────┬──────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
   ┌─────────┐    ┌──────────┐    ┌──────────┐
   │   Bot   │    │Telemetry │    │  Audit   │
   └─────────┘    └──────────┘    └──────────┘
```

## 🎨 Core Principles

### 1. Preserve Smart-Money Edge
Every component honors multi-timeframe context, order blocks, FVGs, liquidity sweeps, BTC impulse gates, regime filters, and institutional heuristics.

### 2. No-Null, Actionable Outputs
All outputs complete—no missing fields, no "TBD" placeholders, no null sections. Signals include full trade plans with populated rationale.

### 3. Verification-Ready
Deterministic fixtures, strong typing, schema validation, and comprehensive test coverage make backtests and validation trivial.

### 4. Zero Silent Failures
Missing indicators, incomplete SMC data, or blank rationale trigger hard errors. No half-formed signals reach notifications.

### 5. Plugin-Friendly & ML-Ready
Pluggable indicators, strategies, and hooks support future ML scoring without core refactoring.

## 📦 Package Structure

```
snipersight/
├── contracts/          # API boundary definitions
├── shared/            # Cross-cutting models, configs, utilities
├── data/              # Multi-exchange data ingestion and caching
├── indicators/        # Technical analysis computation
├── strategy/          # SMC detection, confluence scoring, planning
│   ├── smc/          # Order blocks, FVGs, BOS/CHoCH, liquidity sweeps
│   ├── confluence/   # Scoring, regime detection, plugins
│   └── planner/      # Entry zones, stops, targets, R:R
├── risk/              # Position sizing, exposure control, compliance
├── bot/               # Notifications, execution, charts, telemetry
├── engine/            # Pipeline orchestration, context, hooks, plugins
├── ml/                # ML integration hooks (future)
├── devtools/          # Development utilities
├── tests/             # Fixtures, unit, integration, backtest
├── docs/              # Documentation
├── scripts/           # Operational scripts
└── examples/          # Usage demonstrations
```

## 🚀 Quick Start

### 1. Explore the Documentation

```bash
# Read the core documents
cat PRD.md
cat ARCHITECTURE.md
cat PROJECT_STRUCTURE.md
cat QUICKSTART.md
```

### 2. Launch the Interactive Viewer

This repository includes a Spark application for browsing the documentation:

```bash
# The viewer is already configured and ready to run
# Simply open the project in your Spark environment
```

### 3. Understand the Architecture

- Review the **data flow pipeline** (data → indicators → SMC → confluence → planner → risk → notify)
- Study the **contract definitions** for API boundaries
- Examine the **data models** in the structure reference
- Understand the **quality gates** that ensure signal quality

### 4. Implementation Roadmap

The actual SniperSight scanner should be implemented in **Python** following these phases:

**Phase 1: Foundation** (Week 1-2)
- Set up Python project structure
- Implement data models (`shared/models/`)
- Create API contracts (`contracts/`)
- Build configuration system

**Phase 2: Data Layer** (Week 2-3)
- Exchange adapters (Binance, Bybit)
- Caching system
- Ingestion pipeline
- Test fixtures

**Phase 3: Analysis Layer** (Week 3-5)
- Indicator computation
- SMC detection (OB, FVG, BOS/CHoCH, sweeps)
- Confluence scoring
- Trade planner

**Phase 4: Risk & Execution** (Week 5-6)
- Risk management
- Notification system (Telegram)
- Optional executor
- Telemetry

**Phase 5: Orchestration** (Week 6-7)
- Pipeline controller
- Context management
- Hook system
- CLI interface

**Phase 6: Quality & Testing** (Week 7-8)
- Quality gates
- Backtest framework
- Verification checklist
- Comprehensive tests

## 🎯 Smart-Money Concepts

SniperSight leverages institutional trading concepts:

- **Order Blocks (OB)**: Institutional accumulation/distribution zones
- **Fair Value Gaps (FVG)**: Liquidity imbalances to be filled
- **Break of Structure (BOS)**: Trend continuation confirmations
- **Change of Character (CHoCH)**: Potential trend reversals
- **Liquidity Sweeps**: Stop hunts before institutional moves
- **Displacement**: Strong directional moves indicating conviction

## 📊 Multi-Timeframe Analysis

Analyzes 6 timeframes simultaneously:

- **1W** (Weekly) - Major trend direction
- **1D** (Daily) - Primary market structure
- **4H** - Intermediate structure and alignment
- **1H** - Entry refinement and context
- **15m** - Precise entry zones
- **5m** - Execution timeframe

## 🛡️ Quality Gates

Multi-layered filtering ensures institutional-grade signals:

1. **Data Quality** - Complete, valid, recent data
2. **Indicator Quality** - No null/NaN values in critical indicators
3. **SMC Quality** - Fresh structures, proper displacement
4. **Confluence Quality** - Multi-factor alignment, low conflicts
5. **Plan Quality** - Complete plans, valid R:R ratios
6. **Risk Quality** - Position sizing, exposure limits

## 📋 Configuration Profiles

### Balanced (Default)
Moderate thresholds, multi-factor confluence, R:R ≥ 2.5, 4H primary

### Trend
Trend-following emphasis, momentum-heavy, strict HTF alignment

### Range
Mean-reversion focus, oscillator-heavy, tighter zones

### Aggressive
Lower thresholds, higher leverage, shorter timeframes

### Mobile
Reduced universe, extended cache, battery-optimized

## 🔧 Technology Stack

### Recommended for Python Implementation

**Core**
- Python 3.10+
- pandas / numpy
- TA-Lib / pandas-ta

**Data**
- ccxt (exchange connectivity)
- requests
- redis (optional caching)

**Testing**
- pytest
- hypothesis

**Utilities**
- pydantic (validation)
- typer / click (CLI)
- python-telegram-bot
- plotly / matplotlib

### This Repository (Documentation Viewer)

**Frontend**
- React 19
- TypeScript
- Tailwind CSS v4
- shadcn/ui components

## 📈 Expected Outcomes

### Signal Quality Targets
- Confluence Score: ≥ 7.0/10
- R:R Ratio: ≥ 2.0 (balanced), ≥ 2.5 (trend)
- Freshness Score: ≥ 0.7 for order blocks
- Displacement: ≥ 1.5 ATR

### Backtest Targets
- Win Rate: ≥ 55% (balanced), ≥ 60% (trend)
- Average R:R: ≥ 2.5
- Profit Factor: ≥ 2.0
- Max Drawdown: ≤ 15%

## ⚠️ Important Notes

- This is a **blueprint and architectural specification**, not a working scanner
- The actual implementation should be in **Python** following the documented architecture
- This Spark application serves as an **interactive documentation viewer**
- Focus on **discipline, verification, and quality gates** in your implementation
- Every component must be **testable with deterministic fixtures**

## 📖 Philosophy

SniperSight embodies institutional trading discipline:

✨ **Precision over Speed** - Wait for high-quality setups
✨ **Verification over Trust** - Test everything deterministically
✨ **Discipline over Discretion** - Follow the gates
✨ **Completeness over Convenience** - No half-formed signals
✨ **Clarity over Complexity** - Transparent, auditable decisions

Build with the mindset of an institution protecting capital, not a gambler chasing gains.

## 📄 License

This architectural blueprint and documentation is provided as-is for reference and implementation purposes.

## 🤝 Contributing

This is an architectural specification. Contributions to improve documentation clarity, add implementation examples, or enhance the interactive viewer are welcome.

---

**Ready to build?** Start with [QUICKSTART.md](QUICKSTART.md) and implement phase by phase with rigorous testing at every step.
