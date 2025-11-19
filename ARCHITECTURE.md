# SniperSight Architecture

## System Overview

SniperSight is a modular, institutional-grade crypto market scanner built on strict separation of concerns, contract-driven interfaces, and verification-first design principles. The system processes multi-timeframe market data through a deterministic pipeline to generate complete, actionable trade signals.

## Core Architecture Principles

### 1. Preserve Smart-Money Edge
Every component honors multi-timeframe context, order blocks, FVGs, liquidity sweeps, BTC impulse gates, regime filters, and institutional heuristics that drive edge retention.

### 2. No-Null, Actionable Outputs
All outputs must be complete—no missing fields, no "TBD" placeholders, no null sections. Signals include full trade plans with populated rationale.

### 3. Verification-Ready
Deterministic fixtures, strong typing, schema validation, and comprehensive test coverage make backtests and validation trivial to execute.

### 4. Zero Silent Failures
Missing indicators, incomplete SMC data, or blank rationale trigger hard errors via `error_policy.py`. No half-formed signals reach notifications.

### 5. Plugin-Friendly & ML-Ready
Pluggable indicators, strategies, and hooks support future ML scoring and new feature integration without core refactoring.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI / API Layer                      │
│                    (sniper_sight_cli.py)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Engine Orchestrator                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Pipeline   │  │   Context    │  │    Hooks     │      │
│  │  Controller  │  │   Manager    │  │   System     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│    Data     │  │ Indicators  │  │  Strategy   │
│   Package   │  │   Package   │  │   Package   │
│             │  │             │  │             │
│ • Adapters  │  │ • Momentum  │  │ • SMC       │
│ • Cache     │  │ • Mean Rev  │  │ • Confluence│
│ • Pipeline  │  │ • Volume    │  │ • Planner   │
└─────────────┘  └─────────────┘  └─────────────┘
         │               │               │
         └───────────────┼───────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │      Risk Package             │
         │ • Position Sizing             │
         │ • Exposure Limits             │
         │ • Compliance Checks           │
         └───────────────┬───────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│     Bot     │  │ Telemetry   │  │   Audit     │
│  Executor   │  │  Analytics  │  │  Pipeline   │
│             │  │             │  │             │
│ • Telegram  │  │ • Logging   │  │ • Quality   │
│ • Charts    │  │ • Events    │  │   Gates     │
│ • Orders    │  │ • Stats     │  │ • Reporting │
└─────────────┘  └─────────────┘  └─────────────┘
```

## Data Flow Pipeline

```
Symbol Selection
      ↓
Multi-TF Data Ingestion (1W → 5m)
      ↓
Indicator Computation (per TF)
      ↓
SMC Detection (OB, FVG, BOS, CHoCH, Liquidity Sweeps)
      ↓
Regime Detection (Trend/Range, BTC Impulse)
      ↓
Confluence Scoring (Multi-factor + Synergy/Conflict)
      ↓
Quality Gates (HTF Alignment, Freshness, Displacement)
      ↓
Trade Plan Generation (Entry, Stops, Targets, RR)
      ↓
Risk Validation (Position Size, Exposure, Compliance)
      ↓
Notification / Execution (Telegram, Bot, Audit)
```

## Package Responsibilities

### shared/
**Purpose**: Cross-cutting models, configurations, and utilities used by all packages.

**Key Modules**:
- `config/`: Centralized defaults, profile-based tuning (balanced, trend, range, aggressive, mobile)
- `models/`: Typed dataclasses for OHLCV, indicators, SMC, scoring, plans, notifications
- `utils/`: Schema validation, serialization, caching primitives, error enforcement

**Contracts**: Defines canonical data shapes; all packages import from `shared.models`.

### contracts/
**Purpose**: API boundary definitions that enforce consistent interfaces across packages.

**Key Files**:
- `indicators_contract.py`: Indicator function signatures and output schemas
- `strategy_contract.py`: Strategy engine input/output specifications
- `risk_contract.py`: Risk calculation and validation interfaces
- `notification_contract.py`: Message payload structure requirements

**Usage**: Spark/Copilot must respect these contracts when modifying package internals.

### data/
**Purpose**: Multi-exchange data ingestion, caching, and normalization.

**Key Modules**:
- `adapters/`: Exchange-specific wrappers (Binance, Bybit, mocks) with retry/rate-limit handling
- `cache.py`: Persistent HTF candle storage and order-book snapshots
- `ingestion_pipeline.py`: Universe selection, parallel multi-TF downloads, DataFrame → dataclass conversion

**Output**: Produces `shared.models.data.MultiTimeframeData` objects.

### indicators/
**Purpose**: Technical analysis computation across all timeframes.

**Key Modules**:
- `momentum.py`: RSI, Stoch RSI, MFI
- `mean_reversion.py`: Bollinger Bands, z-scores
- `volatility.py`: ATR, realized volatility
- `volume.py`: Volume spikes, OBV
- `registry.py`: Plugin factory for extensible indicator bundles

**Output**: Produces `shared.models.indicators.IndicatorSet` keyed by timeframe.

### strategy/
**Purpose**: Smart-Money Concept detection, confluence scoring, and trade planning.

**Sub-packages**:

#### strategy/smc/
- `order_blocks.py`: OB detection with displacement, mitigation, freshness tracking
- `fvg.py`: Fair value gap identification with size/overlap analysis
- `bos_choch.py`: Structural breaks, CHoCH, BOS with HTF alignment
- `liquidity_sweeps.py`: Wick/close sweeps around key levels

#### strategy/confluence/
- `scorer.py`: Multi-factor aggregation with synergy bonuses and conflict penalties
- `regime_detection.py`: Trend/range, risk-on/off, BTC impulse classification
- `plugins.py`: Extensible scoring factor system

#### strategy/planner/
- `entry.py`: Dual entry zone calculation (near/far)
- `stops_targets.py`: ATR and structure-based stop/target generation
- `style_classifier.py`: Scalp/swing/intraday classification
- `planner_service.py`: Complete plan assembly with rationale synthesis

**Output**: Produces `shared.models.planner.TradePlan` with zero null fields.

### risk/
**Purpose**: Position sizing, exposure control, and compliance validation.

**Key Modules**:
- `position_sizing.py`: Account risk % → position size calculation
- `exposure_limits.py`: Per-asset, per-exchange, aggregate caps
- `compliance_checks.py`: Pre-execution sanity checks
- `audit_pipeline.py`: Decision logging for "proof of discipline"

**Output**: Produces `shared.models.risk.RiskPlan` or rejection with reason.

### bot/
**Purpose**: Notification delivery, optional execution, charting, and telemetry.

**Sub-packages**:

#### bot/executor/
- `trades.py`: Order staging, dry-run vs live execution
- `safeguards.py`: Dedupe, max risk enforcement, double-fire prevention

#### bot/notifications/
- `telegram.py`: Message dispatch with retry logic
- `formatters.py`: Plan → Markdown/JSON conversion
- `templates/`: Reusable message templates

#### bot/ui/
- `charts.py`: Price charts with OB/FVG/entry overlays
- `overlays.py`: SMC and indicator visualization

#### bot/telemetry/
- `analytics.py`: Hit-rate, RR distribution, regime performance
- `logging.py`: Structured stage-by-stage logs
- `events.py`: Typed telemetry events (setup_generated, setup_rejected, etc.)

### engine/
**Purpose**: Pipeline orchestration, context management, and plugin coordination.

**Key Modules**:
- `pipeline.py`: DAG execution controller (data → indicators → SMC → confluence → planner → risk → notify)
- `context.py`: `SniperContext` object holding symbol, multi-TF data, indicators, SMC, confluence, plan, risk, metadata
- `orchestrator.py`: High-level entry point for CLI, scripts, APIs
- `hooks.py`: Lifecycle hooks for debugging, tracing, ML integration
- `plugins/`: Base plugin interface and registry

### ml/
**Purpose**: Future ML integration hooks.

**Key Modules**:
- `feature_buffer.py`: Feature extraction from context/indicators/SMC
- `scoring_adapter.py`: ML-based signal re-ranking via hooks

### devtools/
**Purpose**: Development utilities and debugging tools.

**Key Modules**:
- `codegen_tools.py`: Stub generation, refactoring helpers
- `profiling.py`: Pipeline stage performance analysis
- `debug_cli.py`: Ad hoc debug commands

### tests/
**Purpose**: Comprehensive verification and regression testing.

**Structure**:
- `fixtures/`: Deterministic OHLCV and expected signal outputs
- `unit/`: Per-module tests
- `integration/`: Full pipeline tests
- `backtest/`: Historical simulation and validation

### docs/
**Purpose**: System documentation and specifications.

**Key Files**:
- `architecture.md`: This document
- `smc_playbook.md`: Smart-Money heuristics and detection rules
- `notification_spec.md`: Message format specifications
- `output_spec.md`: Signal payload schemas
- `quality_gates.md`: Validation criteria for setups
- `verification_checklist.md`: Pre-deployment verification steps
- `versioning.md`: Semantic versioning rules
- `deployment.md`: Deployment guidance

### scripts/
**Purpose**: Operational and maintenance scripts.

**Key Scripts**:
- `run_backtest.py`: Execute historical validation
- `run_quality_audit.py`: Comprehensive quality gate checks
- `sync_cache.py`: HTF data refresh

### examples/
**Purpose**: Usage demonstrations and integration examples.

**Structure**:
- `notebook_scenarios/`: Jupyter notebooks for interactive exploration
- `api_walkthroughs/`: Scripted library usage examples

## Context Object

The `SniperContext` is the central data structure passed through the pipeline:

```python
@dataclass
class SniperContext:
    symbol: str
    profile: str
    run_id: str
    timestamp: datetime
    
    # Pipeline stages populate these
    multi_tf_data: Optional[MultiTimeframeData] = None
    multi_tf_indicators: Optional[Dict[str, IndicatorSet]] = None
    smc_snapshot: Optional[SMCSnapshot] = None
    confluence_breakdown: Optional[ConfluenceBreakdown] = None
    plan: Optional[TradePlan] = None
    risk_plan: Optional[RiskPlan] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
```

Each pipeline stage:
1. Reads from earlier stages in the context
2. Performs its computation
3. Populates its output field in the context
4. Passes context to next stage

## Hook System

Hooks enable extensibility without modifying core logic:

```python
@hook_point("before_indicator_compute")
def compute_indicators(context: SniperContext) -> SniperContext:
    # Core logic
    pass

@hook_point("after_strategy")
def plan_trade(context: SniperContext) -> SniperContext:
    # Core logic
    pass
```

Plugins register callbacks:

```python
def ml_rescoring_hook(context: SniperContext) -> SniperContext:
    if context.confluence_breakdown:
        ml_score = ml_model.predict(context)
        context.confluence_breakdown.ml_adjustment = ml_score
    return context

register_hook("after_strategy", ml_rescoring_hook)
```

## Quality Gates

Quality gates enforce discipline at multiple checkpoints:

### Data Quality Gates
- Complete timeframe coverage (no missing TFs)
- Minimum candle count per TF
- Recent data (no stale cache)
- Valid OHLCV relationships (H≥C≥L, etc.)

### Indicator Quality Gates
- No null/NaN values in recent window
- Indicator computation success
- Reasonable value ranges

### SMC Quality Gates
- Fresh order blocks (not heavily mitigated)
- Sufficient displacement strength
- HTF structural alignment
- Valid liquidity sweep confirmation

### Confluence Quality Gates
- Minimum confluence score threshold
- Low conflict penalty
- Regime alignment
- BTC impulse gate (if enabled)

### Plan Quality Gates
- R:R ratio ≥ minimum threshold
- Stops not in FVG or OB zones
- Targets aligned with structure
- Complete rationale (no empty sections)

### Risk Quality Gates
- Position size within limits
- Total exposure below cap
- No existing conflicting positions
- Compliance check pass

## Error Handling Strategy

### Zero Silent Failures
```python
# BAD - Silent failure
if indicators is None:
    return None  # ❌ Silently propagates incomplete data

# GOOD - Explicit failure
if indicators is None:
    raise IncompleteIndicatorError(
        f"Missing indicators for {symbol} on {timeframe}"
    )  # ✅ Fails loudly with context
```

### Error Policy Enforcement
`shared/utils/error_policy.py` provides validators:

```python
validate_no_nulls(obj, "TradePlan")
validate_schema(obj, TradePlanSchema)
validate_quality_gates(context)
```

All pipeline stages must pass validation before proceeding.

## Extensibility Patterns

### Adding New Indicators
1. Implement in `indicators/` following contract
2. Register in `indicators/registry.py`
3. Add to `shared/models/indicators.py` if new output type
4. Update tests with deterministic fixtures

### Adding New SMC Detectors
1. Implement in `strategy/smc/` following contract
2. Update `shared/models/smc.py` for new detection types
3. Integrate into confluence scoring
4. Add verification fixtures

### Adding New Strategies
1. Create plugin in `strategy/confluence/plugins.py`
2. Define scoring logic
3. Register in plugin registry
4. Document in `smc_playbook.md`

### Adding New Exchanges
1. Implement adapter in `data/adapters/`
2. Follow common interface (rate limits, retry, normalization)
3. Add mock for tests
4. Update ingestion pipeline

## Performance Considerations

### Caching Strategy
- HTF data (1W, 1D) cached for 24h
- LTF data (15m, 5m) cached for 5min
- Indicator results cached per symbol/TF pair
- SMC detections cached with invalidation on new candles

### Parallel Processing
- Symbol scanning parallelized across symbols
- Multi-TF data fetches parallelized within symbol
- Indicator computation parallelized across TFs

### Rate Limit Management
- Adaptive throttling based on exchange limits
- Request batching where supported
- Fallback to cached data on rate limit

## Deployment Architecture

### Mobile (Pydroid)
- Lightweight profile configurations
- Reduced symbol universe
- Extended cache TTLs
- Background notification service

### Server / VPS
- Full symbol universe
- Scheduled scans via cron
- Telegram bot integration
- Persistent audit logging

### Docker
- Multi-stage build for minimal image
- Volume mounts for cache persistence
- Environment-based configuration
- Health check endpoints

### Cloud (AWS/GCP)
- Lambda/Cloud Functions for scheduled scans
- S3/Cloud Storage for cache and audit logs
- SNS/Pub-Sub for notifications
- CloudWatch/Stackdriver for telemetry

## Version Control Strategy

### Semantic Versioning
- **Major**: Breaking contract changes, schema migrations, algorithm overhauls
- **Minor**: New features, new indicators, new strategies (backward compatible)
- **Patch**: Bug fixes, performance improvements, documentation

### Migration Checklist
- Update contracts if interfaces change
- Migrate fixtures and expected outputs
- Run full backtest suite
- Update documentation
- Tag release with changelog
