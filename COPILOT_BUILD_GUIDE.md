# Copilot Implementation Guide for SniperSight Backend

This guide provides step-by-step instructions for building the Python backend using GitHub Copilot, with all context already available in this workspace.

## Prerequisites

All planning documents are already in this workspace:
- `ARCHITECTURE.md` - System architecture and design
- `PROJECT_STRUCTURE.md` - Detailed module descriptions
- `PRD.md` - Product requirements
- `IMPLEMENTATION_ROADMAP.md` - Phased implementation plan

## Phase 1: Foundation (Week 1)

### Step 1.1: Set Up Python Environment

**Terminal Commands:**
```bash
# Create Python virtual environment
python -m venv venv
source venv/bin/activate

# Create Python config files
touch requirements.txt
touch pyproject.toml
```

### Step 1.2: Create requirements.txt

**Prompt for Copilot:**
```
Create requirements.txt with the following Python dependencies for a crypto trading scanner:
- pandas>=2.0.0, numpy>=1.24.0
- ccxt>=4.0.0 (multi-exchange)
- fastapi>=0.104.0, uvicorn>=0.24.0, pydantic>=2.0.0
- python-telegram-bot>=20.0, aiohttp>=3.9.0
- typer>=0.9.0 (CLI), loguru>=0.7.0 (logging)
- python-dotenv>=1.0.0
- pytest>=7.4.0, pytest-asyncio>=0.21.0 (testing)

Include proper version constraints and comments.
```

### Step 1.3: Create pyproject.toml

**Prompt for Copilot:**
```
Create pyproject.toml for a Python project named "snipersight" following modern Python standards.
- Build system: setuptools
- Python version: >=3.10
- Project metadata: institutional-grade crypto market scanner
- Include dev dependencies for testing and linting
```

### Step 1.4: Create Base Directory Structure

**Terminal Commands:**
```bash
# Create all backend directories
mkdir -p backend/{contracts,shared/{config,models,utils},data/adapters,indicators}
mkdir -p backend/strategy/{smc,confluence,planner}
mkdir -p backend/{risk,engine/plugins,ml,devtools}
mkdir -p backend/bot/{executor,notifications,ui,telemetry}
mkdir -p backend/tests/{fixtures/{ohlcv,signals},unit,integration,backtest}
mkdir -p backend/{scripts,examples}

# Create __init__.py files
find backend -type d -exec touch {}/__init__.py \;
```

### Step 1.5: Create Shared Models - Data

**File:** `backend/shared/models/data.py`

**Prompt for Copilot:**
```
Following ARCHITECTURE.md and PROJECT_STRUCTURE.md, create backend/shared/models/data.py with:

1. OHLCV dataclass with fields: timestamp (datetime), open, high, low, close, volume (all float)
2. MultiTimeframeData dataclass with: symbol (str), timeframes (Dict[str, pd.DataFrame])
3. Use @dataclass decorator, type hints, and docstrings
4. Import: dataclasses, datetime, typing, pandas

Ensure clean, typed Python following the architecture specs.
```

### Step 1.6: Create Shared Models - SMC

**File:** `backend/shared/models/smc.py`

**Prompt for Copilot:**
```
Following PROJECT_STRUCTURE.md section on shared/models/smc.py, create:

1. OrderBlock dataclass: timeframe, direction ("bullish"/"bearish"), high, low, timestamp, displacement_strength, mitigation_level, freshness_score
2. FVG dataclass: timeframe, direction, top, bottom, timestamp, size, overlap_with_price
3. StructuralBreak dataclass: timeframe, break_type ("BOS"/"CHoCH"), level, timestamp, htf_aligned
4. LiquiditySweep dataclass: level, sweep_type ("high"/"low"), confirmation, timestamp
5. SMCSnapshot dataclass: Lists of all the above types

Use proper type hints and docstrings.
```

### Step 1.7: Create Shared Models - Indicators

**File:** `backend/shared/models/indicators.py`

**Prompt for Copilot:**
```
reate backend/shared/models/indicators.py following PROJECT_STRUCTURE.md:

1. IndicatorSnapshot dataclass with: rsi, stoch_rsi, mfi, bb_upper, bb_lower, atr, volume_spike (bool), and other standard indicators
2. IndicatorSet dataclass with: by_timeframe (Dict[str, IndicatorSnapshot])

Include all indiCcators mentioned in ARCHITECTURE.md under indicators/ package.
```

### Step 1.8: Create Shared Models - Scoring

**File:** `backend/shared/models/scoring.py`

**Prompt for Copilot:**
```
Create backend/shared/models/scoring.py per PROJECT_STRUCTURE.md:

1. ConfluenceFactor dataclass: name, score, weight, rationale
2. ConfluenceBreakdown dataclass: total_score, factors (List), synergy_bonus, conflict_penalty, regime, htf_aligned, btc_impulse_gate

Follow the confluence scoring system described in ARCHITECTURE.md.
```

### Step 1.9: Create Shared Models - Planner

**File:** `backend/shared/models/planner.py`

**Prompt for Copilot:**
```
Create backend/shared/models/planner.py following PROJECT_STRUCTURE.md:

1. EntryZone: near_entry, far_entry, rationale
2. StopLoss: level, distance_atr, rationale
3. Target: level, percentage, rationale
4. TradePlan: symbol, direction, setup_type, entry_zone, stop_loss, targets (List), risk_reward, confidence_score, confluence_breakdown, rationale, metadata

This is the core output model - ensure no nullable fields except metadata.
```

### Step 1.10: Create Config - Defaults

**File:** `backend/shared/config/defaults.py`

**Prompt for Copilot:**
```
Create backend/shared/config/defaults.py following ARCHITECTURE.md:

1. ScanConfig dataclass with:
   - timeframes: Tuple[str, ...] = ('1W', '1D', '4H', '1H', '15m', '5m')
   - min_confluence_score: float = 65.0
   - min_rr_ratio: float = 2.0
   - btc_impulse_gate_enabled: bool = True
   - max_symbols: int = 20
   
2. Global thresholds for ATR multipliers, RSI levels, volume spike thresholds
3. Window sizes (EMA periods, lookback windows)

Reference ARCHITECTURE.md for institutional-grade defaults.
```

### Step 1.11: Create Config - Profiles

**Files:** `backend/shared/config/profiles/{balanced,trend,range,aggressive}.py`

**Prompt for Copilot:**
```
Create four profile configs in backend/shared/config/profiles/ following ARCHITECTURE.md:

1. balanced.py - Moderate thresholds, R:R ≥ 2.5, 4H primary timeframe
2. trend.py - Trend-following, momentum weighted, strict HTF alignment
3. range.py - Mean-reversion, tighter entries, oscillator-heavy
4. aggressive.py - Lower thresholds, higher leverage, 15m/5m bias

Each should override ScanConfig defaults appropriately.
```

### Step 1.12: Create Contracts - Indicators

**File:** `backend/contracts/indicators_contract.py`

**Prompt for Copilot:**
```
Create backend/contracts/indicators_contract.py following ARCHITECTURE.md contracts/ package:

1. Abstract IndicatorProvider class with:
   - compute(df: pd.DataFrame, config: dict) -> IndicatorSet (abstract method)
   
2. Document the contract for indicator computation following the architecture specs.
Use ABC and abstractmethod.
```

### Step 1.13: Create Contracts - Strategy

**File:** `backend/contracts/strategy_contract.py`

**Prompt for Copilot:**
```
Create backend/contracts/strategy_contract.py per PROJECT_STRUCTURE.md:

1. Abstract interfaces for:
   - SMC detection function signatures
   - Confluence scoring interfaces
   - Trade plan generation contracts
   
Reference ARCHITECTURE.md for the strategy pipeline flow.
```

### Step 1.14: Create Contracts - Risk

**File:** `backend/contracts/risk_contract.py`

**Prompt for Copilot:**
```
Create backend/contracts/risk_contract.py following PROJECT_STRUCTURE.md:

Define interfaces for:
- Position sizing calculation
- Exposure limit checking
- Compliance validation
- RiskPlan output schema

Align with ARCHITECTURE.md risk package specifications.
```

### Step 1.15: Create Context Model

**File:** `backend/engine/context.py`

**Prompt for Copilot:**
```
Create backend/engine/context.py following ARCHITECTURE.md:

SniperContext dataclass with:
- symbol, profile, run_id, timestamp
- Optional fields: multi_tf_data, multi_tf_indicators, smc_snapshot, confluence_breakdown, plan, risk_plan
- metadata: Dict[str, Any]

This is the central data structure passed through the entire pipeline.
Import all shared models.
```

### Step 1.16: Create Error Policy Utilities

**File:** `backend/shared/utils/error_policy.py`

**Prompt for Copilot:**
```
Create backend/shared/utils/error_policy.py per ARCHITECTURE.md "Zero Silent Failures" principle:

Functions:
- enforce_complete_indicators(indicators: IndicatorSet) -> None: Raises if missing
- enforce_complete_smc(smc: SMCSnapshot) -> None: Raises if incomplete
- enforce_complete_plan(plan: TradePlan) -> None: Raises if any field is null/empty
- enforce_quality_gates(context: SniperContext) -> None: Validates all criteria

Create custom exceptions: IncompleteIndicatorError, IncompleteSMCError, IncompletePlanError
```

### Step 1.17: Create CLI Skeleton

**File:** `backend/cli.py`

**Prompt for Copilot:**
```
Create backend/cli.py using Typer following IMPLEMENTATION_ROADMAP.md Step 7:

Commands:
- scan: Run market scan with profile, symbols, exchange params
- backtest: Historical validation
- audit: Quality checks

Use typer decorators, provide help text, include placeholder orchestrator calls.
Reference ARCHITECTURE.md for sniper-themed output messages.
```

### Step 1.18: Validation Checkpoint

**Run these checks:**
```bash
# Verify structure
tree backend/ -L 3

# Check Python syntax
python -m py_compile backend/**/*.py

# Verify imports
cd backend && python -c "from shared.models.data import MultiTimeframeData; print('✓ Models OK')"
cd backend && python -c "from shared.config.defaults import ScanConfig; print('✓ Config OK')"
cd backend && python -c "from engine.context import SniperContext; print('✓ Context OK')"
```

## Phase 2: Data Layer (Week 2)

### Step 2.1: Create Binance Adapter

**File:** `backend/data/adapters/binance.py`

**Prompt for Copilot:**
```
Create backend/data/adapters/binance.py following IMPLEMENTATION_ROADMAP.md Step 5.1 and PROJECT_STRUCTURE.md:

BinanceAdapter class with:
- __init__(testnet: bool = False): Initialize ccxt.binance with rate limiting
- fetch_ohlcv(symbol, timeframe, limit=500) -> pd.DataFrame: Returns OHLCV with timestamp conversion
- fetch_ticker(symbol) -> dict
- _retry_on_rate_limit(func): Decorator for retry logic

Use ccxt library, handle errors gracefully, return normalized DataFrames.
```

### Step 2.2: Create Mock Data Adapter

**File:** `backend/data/adapters/mocks.py`

**Prompt for Copilot:**
```
Create backend/data/adapters/mocks.py per PROJECT_STRUCTURE.md:

Functions to generate deterministic test data:
- generate_mock_ohlcv(regime: str, bars: int) -> List[OHLCV]
- generate_trending_data() -> List[OHLCV]
- generate_ranging_data() -> List[OHLCV]
- generate_volatile_data() -> List[OHLCV]

Use numpy for reproducible randomness with fixed seeds.
Import shared.models.data.OHLCV.
```

### Step 2.3: Create Cache Manager

**File:** `backend/shared/utils/caching.py`

**Prompt for Copilot:**
```
Create backend/shared/utils/caching.py following PROJECT_STRUCTURE.md:

CacheManager class with:
- get(key: str, ttl: int) -> Optional[Any]
- set(key: str, value: Any, ttl: int) -> None
- invalidate(pattern: str) -> None
- clear_all() -> None

Use file-based caching (pickle) or redis if available.
Implement TTL expiration logic per ARCHITECTURE.md caching strategy.
```

### Step 2.4: Create Ingestion Pipeline

**File:** `backend/data/ingestion_pipeline.py`

**Prompt for Copilot:**
```
Create backend/data/ingestion_pipeline.py per IMPLEMENTATION_ROADMAP.md Step 5.2:

IngestionPipeline class:
- __init__(adapter): Store exchange adapter
- fetch_multi_timeframe(symbol, timeframes) -> MultiTimeframeData: Fetch all TFs
- parallel_fetch(symbols: List[str]) -> Dict[str, MultiTimeframeData]: Parallel symbol fetching
- normalize_and_validate(raw_data) -> MultiTimeframeData: Data quality checks

Reference ARCHITECTURE.md data flow pipeline.
```

### Step 2.5: Validation Checkpoint

**Test data fetching:**
```bash
# Create test script
cat > backend/tests/test_data_fetch.py << 'EOF'
from data.adapters.binance import BinanceAdapter
from data.ingestion_pipeline import IngestionPipeline

adapter = BinanceAdapter()
pipeline = IngestionPipeline(adapter)
data = pipeline.fetch_multi_timeframe('BTC/USDT', ['1D', '4H', '1H'])
print(f"✓ Fetched {len(data.timeframes)} timeframes for BTC/USDT")
EOF

# Run test
cd backend && python tests/test_data_fetch.py
```

## Phase 3: Analysis Layer (Week 3-4)

### Step 3.1: Create Momentum Indicators

**File:** `backend/indicators/momentum.py`

**Prompt for Copilot:**
```
Create backend/indicators/momentum.py following PROJECT_STRUCTURE.md:

Functions:
- compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series
- compute_stoch_rsi(df, period) -> Tuple[pd.Series, pd.Series]
- compute_mfi(df, period) -> pd.Series

Use pandas for calculations, handle edge cases, return Series with proper index alignment.
Reference IMPLEMENTATION_ROADMAP.md Step 6.1.
```

### Step 3.2: Create Volatility Indicators

**File:** `backend/indicators/volatility.py`

**Prompt for Copilot:**
```
Create backend/indicators/volatility.py per PROJECT_STRUCTURE.md:

Functions:
- compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series
- compute_realized_volatility(df, window) -> pd.Series

Use standard ATR calculation, handle true range properly.
```

### Step 3.3: Create Volume Indicators

**File:** `backend/indicators/volume.py`

**Prompt for Copilot:**
```
Create backend/indicators/volume.py:

Functions:
- detect_volume_spike(df, threshold=2.0) -> pd.Series (boolean)
- compute_obv(df) -> pd.Series

Volume spike = volume > threshold * rolling mean.
```

### Step 3.4: Create Order Block Detection

**File:** `backend/strategy/smc/order_blocks.py`

**Prompt for Copilot:**
```
Create backend/strategy/smc/order_blocks.py following ARCHITECTURE.md SMC detection:

Functions:
- detect_order_blocks(df: pd.DataFrame, config: dict) -> List[OrderBlock]
- calculate_displacement_strength(df, ob: OrderBlock) -> float
- check_mitigation(df, ob) -> float
- calculate_freshness(ob, current_time) -> float

Implement Smart-Money order block detection:
- Find strong rejection candles (large wicks)
- Verify displacement (strong move away from zone)
- Track mitigation level (how much price revisited)
- Calculate freshness score (time since formation)

Reference ARCHITECTURE.md for OB detection rules.
Import shared.models.smc.OrderBlock.
```

### Step 3.5: Create FVG Detection

**File:** `backend/strategy/smc/fvg.py`

**Prompt for Copilot:**
```
Create backend/strategy/smc/fvg.py per ARCHITECTURE.md:

Functions:
- detect_fvgs(df: pd.DataFrame) -> List[FVG]
- calculate_fvg_size(fvg: FVG) -> float
- check_price_overlap(price: float, fvg: FVG) -> bool

FVG = gap between candle 1's high/low and candle 3's low/high (candle 2 doesn't fill the gap).
Import shared.models.smc.FVG.
```

### Continue with remaining phases...

---

## Quick Reference: Key Prompts

### For any new file:
```
Create [file_path] following [ARCHITECTURE.md | PROJECT_STRUCTURE.md | IMPLEMENTATION_ROADMAP.md]:

[Specific requirements from docs]

Include proper type hints, docstrings, and error handling.
```

### For validation:
```
Review [file_path] against [doc_reference] and ensure:
- Matches architecture specifications
- Follows "Zero Silent Failures" principle
- Has complete type annotations
- Includes docstrings
```

### For debugging:
```
Fix [issue] in [file_path] while maintaining compatibility with:
- ARCHITECTURE.md specifications
- Existing models in shared/models/
- Contract interfaces in contracts/
```

## Progress Tracking

Track completion in `IMPLEMENTATION_ROADMAP.md` by checking off items in each phase.

## Architecture Reference Quick Links

- **Data Flow:** ARCHITECTURE.md > "Data Flow Pipeline"
- **SMC Rules:** ARCHITECTURE.md > "strategy/smc/" section
- **Quality Gates:** ARCHITECTURE.md > "Quality Gates"
- **No-Null Policy:** ARCHITECTURE.md > "No-Null, Actionable Outputs"
- **Error Handling:** ARCHITECTURE.md > "Error Handling Strategy"

---

**Start with Phase 1, Steps 1.1-1.18 to build the foundation, then proceed to Phase 2.**
