# SniperSight Project Structure Reference

This document provides a comprehensive map of the SniperSight codebase with detailed descriptions of every module's purpose, responsibilities, and interfaces.

## Project Root

```
snipersight/
├── README.md                          # Project overview, quick start, installation
├── pyproject.toml                     # Python project metadata, dependencies, build config
├── requirements.txt                   # Pinned dependencies for reproducible installs
├── sniper_sight_cli.py               # CLI entry point (Typer/Click commands)
├── contracts/                         # API boundary definitions
├── shared/                            # Cross-cutting models, configs, utilities
├── data/                              # Multi-exchange data ingestion and caching
├── indicators/                        # Technical analysis computation
├── strategy/                          # SMC detection, confluence, planning
├── risk/                              # Position sizing and exposure control
├── bot/                               # Notifications, execution, telemetry
├── engine/                            # Pipeline orchestration and context
├── ml/                                # ML integration hooks (future)
├── devtools/                          # Development utilities
├── tests/                             # Test suites and fixtures
├── docs/                              # Documentation
├── scripts/                           # Operational scripts
└── examples/                          # Usage demonstrations
```

---

## contracts/

**Purpose**: Define strict API boundaries that all packages must respect. Prevents signature drift and ensures consistent naming/typing across the codebase.

### `indicators_contract.py`
**Defines**: 
- Indicator function signatures: `compute_indicator(df: pd.DataFrame, config: dict) -> IndicatorResult`
- Required output fields for each indicator type
- Timeframe-specific computation rules

**Used by**: `indicators/` package implementations, `engine/pipeline.py` validation

### `strategy_contract.py`
**Defines**:
- Strategy engine input/output schemas
- SMC detection function signatures
- Confluence scoring interfaces
- Trade plan generation contracts

**Used by**: `strategy/` package, `engine/orchestrator.py`

### `risk_contract.py`
**Defines**:
- Position sizing calculation interface
- Exposure limit checking contract
- Compliance validation signatures
- Risk plan output schema

**Used by**: `risk/` package, `engine/pipeline.py`

### `notification_contract.py`
**Defines**:
- Minimal notification payload fields (symbol, direction, entry, stop, targets)
- Full notification payload (includes rationale, confluence, charts)
- Telegram message structure
- JSON export format

**Used by**: `bot/notifications/`, verification tests

---

## shared/

**Purpose**: Centralized models, configurations, and utilities used across all packages. Single source of truth for data structures.

### `shared/config/`

#### `defaults.py`
**Contains**:
- Global thresholds (ATR multipliers, RSI levels, volume spike thresholds)
- Window sizes (EMA periods, lookback windows)
- Feature flags (enable_btc_impulse_gate, enable_htf_override, enable_ml_scoring)
- Notification settings (max_signals_per_batch, min_confidence_threshold)
- Risk defaults (max_risk_per_trade, max_total_exposure)

#### `profiles/`
Profile-specific configuration overrides for different trading styles.

##### `balanced.py`
- Moderate thresholds
- Multi-factor confluence required
- R:R ≥ 2.5
- Medium timeframe bias (4H primary)

##### `trend.py`
- Trend-following emphasis
- Momentum indicators weighted higher
- HTF alignment strictly enforced
- Displacement requirement increased

##### `range.py`
- Mean-reversion focus
- Tighter entry zones
- Reduced target distances
- Oscillator-heavy scoring

##### `aggressive.py`
- Lower confluence thresholds
- Higher leverage allowance
- Shorter timeframe bias (15m/5m)
- Relaxed freshness requirements

##### `mobile.py`
- Reduced symbol universe (top 10)
- Extended cache TTLs
- Simplified rationale
- Battery-optimized scanning

#### `flags.py`
Runtime feature flags for A/B testing and gradual rollouts:
- `ENABLE_EXPERIMENTAL_ML_SCORING`
- `ENABLE_MULTI_EXCHANGE_ARBITRAGE`
- `ENABLE_EXECUTION_MODE`
- `STRICT_VALIDATION_MODE`

### `shared/models/`

#### `data.py`
**Dataclasses**:
```python
@dataclass
class OHLCV:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass
class MultiTimeframeData:
    symbol: str
    timeframes: Dict[str, List[OHLCV]]  # "1W", "1D", "4H", etc.
    metadata: Dict[str, Any]
```

#### `indicators.py`
**Dataclasses**:
```python
@dataclass
class IndicatorSnapshot:
    rsi: float
    stoch_rsi: float
    mfi: float
    bb_upper: float
    bb_lower: float
    atr: float
    volume_spike: bool
    # ... all computed indicators

@dataclass
class IndicatorSet:
    by_timeframe: Dict[str, IndicatorSnapshot]
```

#### `smc.py`
**Dataclasses**:
```python
@dataclass
class OrderBlock:
    timeframe: str
    direction: str  # "bullish" | "bearish"
    high: float
    low: float
    timestamp: datetime
    displacement_strength: float
    mitigation_level: float
    freshness_score: float

@dataclass
class FVG:
    timeframe: str
    direction: str
    top: float
    bottom: float
    timestamp: datetime
    size: float
    overlap_with_price: bool

@dataclass
class StructuralBreak:
    timeframe: str
    break_type: str  # "BOS" | "CHoCH"
    level: float
    timestamp: datetime
    htf_aligned: bool

@dataclass
class LiquiditySweep:
    level: float
    sweep_type: str  # "high" | "low"
    confirmation: bool
    timestamp: datetime

@dataclass
class SMCSnapshot:
    order_blocks: List[OrderBlock]
    fvgs: List[FVG]
    structural_breaks: List[StructuralBreak]
    liquidity_sweeps: List[LiquiditySweep]
```

#### `scoring.py`
**Dataclasses**:
```python
@dataclass
class ConfluenceFactor:
    name: str
    score: float
    weight: float
    rationale: str

@dataclass
class ConfluenceBreakdown:
    total_score: float
    factors: List[ConfluenceFactor]
    synergy_bonus: float
    conflict_penalty: float
    regime: str  # "trend" | "range" | "risk_on" | "risk_off"
    htf_aligned: bool
    btc_impulse_gate: bool
```

#### `planner.py`
**Dataclasses**:
```python
@dataclass
class EntryZone:
    near_entry: float
    far_entry: float
    rationale: str

@dataclass
class StopLoss:
    level: float
    distance_atr: float
    rationale: str

@dataclass
class Target:
    level: float
    percentage: float
    rationale: str

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
    rationale: str  # Multi-paragraph human-readable explanation
    metadata: Dict[str, Any]
```

#### `notifications.py`
**Dataclasses**:
```python
@dataclass
class TelegramMessage:
    text: str  # Markdown-formatted
    parse_mode: str
    chart_url: Optional[str]
    json_payload: Dict[str, Any]

@dataclass
class NotificationPayload:
    message: TelegramMessage
    priority: str  # "high" | "medium" | "low"
    timestamp: datetime
```

### `shared/utils/`

#### `schema_validator.py`
**Functions**:
- `validate_schema(obj: Any, schema: Type) -> bool`: Validates object against Pydantic/dataclass schema
- `validate_no_nulls(obj: Any, obj_name: str) -> None`: Ensures no null fields in critical objects
- `validate_ohlcv(candles: List[OHLCV]) -> bool`: OHLCV relationship checks (H≥C≥L, etc.)

#### `serialization.py`
**Functions**:
- `to_json(obj: Any) -> str`: Serialize dataclass/Pydantic to JSON
- `from_json(json_str: str, cls: Type) -> Any`: Deserialize JSON to typed object
- `to_dict(obj: Any) -> dict`: Convert to plain dict for logging/debugging

#### `caching.py`
**Classes**:
```python
class CacheManager:
    def get(key: str, ttl: int) -> Optional[Any]
    def set(key: str, value: Any, ttl: int) -> None
    def invalidate(pattern: str) -> None
    def clear_all() -> None
```

#### `error_policy.py`
**Functions**:
- `enforce_complete_indicators(indicators: IndicatorSet) -> None`: Raises if missing indicators
- `enforce_complete_smc(smc: SMCSnapshot) -> None`: Raises if SMC detection incomplete
- `enforce_complete_plan(plan: TradePlan) -> None`: Raises if any plan field is null/empty
- `enforce_quality_gates(context: SniperContext) -> None`: Validates all quality criteria

---

## data/

**Purpose**: Multi-exchange data ingestion, normalization, caching, and OHLCV pipeline.

### `crypto.py`
**Functions**:
- `fetch_ohlcv(symbol: str, timeframe: str, exchange: str) -> List[OHLCV]`
- `fetch_ticker(symbol: str, exchange: str) -> Ticker`
- `get_funding_rate(symbol: str, exchange: str) -> float`

### `cache.py`
**Classes**:
```python
class DataCache:
    def get_cached_ohlcv(symbol: str, tf: str) -> Optional[List[OHLCV]]
    def cache_ohlcv(symbol: str, tf: str, data: List[OHLCV], ttl: int) -> None
    def get_cached_orderbook(symbol: str) -> Optional[OrderBook]
```

### `adapters/`

#### `binance.py`
**Classes**:
```python
class BinanceAdapter:
    def fetch_klines(symbol: str, interval: str, limit: int) -> pd.DataFrame
    def fetch_depth(symbol: str, limit: int) -> OrderBook
    def _retry_on_rate_limit(func: Callable) -> Callable
```

#### `bybit.py`
**Classes**:
```python
class BybitAdapter:
    def fetch_klines(symbol: str, interval: str, limit: int) -> pd.DataFrame
    def fetch_depth(symbol: str, limit: int) -> OrderBook
```

#### `mocks.py`
**Functions**:
- `generate_mock_ohlcv(regime: str, bars: int) -> List[OHLCV]`: Generates deterministic test data
- `generate_trending_data() -> List[OHLCV]`
- `generate_ranging_data() -> List[OHLCV]`
- `generate_volatile_data() -> List[OHLCV]`

### `ingestion_pipeline.py`
**Classes**:
```python
class IngestionPipeline:
    def select_universe(profile: str) -> List[str]
    def fetch_multi_tf(symbol: str) -> MultiTimeframeData
    def parallel_fetch(symbols: List[str]) -> Dict[str, MultiTimeframeData]
    def normalize_and_validate(raw_data: Any) -> MultiTimeframeData
```

---

## indicators/

**Purpose**: Technical analysis computation using TA-Lib, pandas-ta, or custom implementations.

### `momentum.py`
**Functions**:
- `compute_rsi(df: pd.DataFrame, period: int) -> pd.Series`
- `compute_stoch_rsi(df: pd.DataFrame, period: int) -> Tuple[pd.Series, pd.Series]`
- `compute_mfi(df: pd.DataFrame, period: int) -> pd.Series`

### `mean_reversion.py`
**Functions**:
- `compute_bollinger_bands(df: pd.DataFrame, period: int, std: float) -> Tuple[pd.Series, pd.Series, pd.Series]`
- `compute_zscore(df: pd.DataFrame, window: int) -> pd.Series`

### `volatility.py`
**Functions**:
- `compute_atr(df: pd.DataFrame, period: int) -> pd.Series`
- `compute_realized_volatility(df: pd.DataFrame, window: int) -> pd.Series`

### `volume.py`
**Functions**:
- `detect_volume_spike(df: pd.DataFrame, threshold: float) -> pd.Series`
- `compute_obv(df: pd.DataFrame) -> pd.Series`

### `registry.py`
**Classes**:
```python
class IndicatorRegistry:
    def register(name: str, func: Callable) -> None
    def compute_bundle(df: pd.DataFrame, config: dict) -> IndicatorSnapshot
    def list_available() -> List[str]
```

---

## strategy/

**Purpose**: Smart-Money Concept detection, confluence scoring, and complete trade plan generation.

### `strategy/smc/`

#### `order_blocks.py`
**Functions**:
- `detect_order_blocks(df: pd.DataFrame, config: dict) -> List[OrderBlock]`
- `calculate_displacement_strength(df: pd.DataFrame, ob: OrderBlock) -> float`
- `check_mitigation(df: pd.DataFrame, ob: OrderBlock) -> float`
- `calculate_freshness(ob: OrderBlock, current_time: datetime) -> float`

#### `fvg.py`
**Functions**:
- `detect_fvgs(df: pd.DataFrame) -> List[FVG]`
- `calculate_fvg_size(fvg: FVG) -> float`
- `check_price_overlap(price: float, fvg: FVG) -> bool`

#### `bos_choch.py`
**Functions**:
- `detect_structural_breaks(df: pd.DataFrame, htf_trend: str) -> List[StructuralBreak]`
- `classify_break_type(break_level: float, prev_structure: str) -> str`
- `check_htf_alignment(ltf_break: StructuralBreak, htf_data: pd.DataFrame) -> bool`

#### `liquidity_sweeps.py`
**Functions**:
- `detect_liquidity_sweeps(df: pd.DataFrame, levels: List[float]) -> List[LiquiditySweep]`
- `confirm_sweep(df: pd.DataFrame, level: float) -> bool`

### `strategy/confluence/`

#### `scorer.py`
**Classes**:
```python
class ConfluenceScorer:
    def compute_score(context: SniperContext) -> ConfluenceBreakdown
    def calculate_synergy_bonus(factors: List[ConfluenceFactor]) -> float
    def calculate_conflict_penalty(factors: List[ConfluenceFactor]) -> float
```

#### `regime_detection.py`
**Functions**:
- `detect_regime(df: pd.DataFrame, indicators: IndicatorSnapshot) -> str`
- `check_btc_impulse(btc_data: pd.DataFrame) -> bool`
- `classify_risk_environment(multi_tf: MultiTimeframeData) -> str`

#### `plugins.py`
**Classes**:
```python
class ConfluencePlugin(ABC):
    @abstractmethod
    def calculate_factor(context: SniperContext) -> ConfluenceFactor

class PluginRegistry:
    def register(plugin: ConfluencePlugin) -> None
    def get_all_factors(context: SniperContext) -> List[ConfluenceFactor]
```

### `strategy/planner/`

#### `entry.py`
**Functions**:
- `calculate_entry_zones(smc: SMCSnapshot, volatility: float) -> EntryZone`
- `anchor_to_structure(price: float, obs: List[OrderBlock], fvgs: List[FVG]) -> float`

#### `stops_targets.py`
**Functions**:
- `calculate_stop_loss(entry: float, direction: str, atr: float, smc: SMCSnapshot) -> StopLoss`
- `generate_targets(entry: float, stop: float, direction: str, structure_levels: List[float]) -> List[Target]`
- `calculate_rr_ratio(entry: float, stop: float, targets: List[Target]) -> float`

#### `style_classifier.py`
**Functions**:
- `classify_setup_style(timeframe: str, holding_period_estimate: int) -> str`

#### `planner_service.py`
**Classes**:
```python
class PlannerService:
    def generate_plan(context: SniperContext) -> TradePlan
    def synthesize_rationale(context: SniperContext) -> str
    def validate_plan_completeness(plan: TradePlan) -> bool
```

---

## risk/

**Purpose**: Position sizing, exposure management, and compliance validation.

### `position_sizing.py`
**Functions**:
- `calculate_position_size(account_balance: float, risk_pct: float, entry: float, stop: float, leverage: float) -> float`
- `adjust_for_volatility(base_size: float, atr_ratio: float) -> float`

### `exposure_limits.py`
**Classes**:
```python
class ExposureManager:
    def check_per_asset_limit(symbol: str, proposed_size: float) -> bool
    def check_total_exposure(proposed_exposure: float) -> bool
    def get_available_capacity(symbol: str) -> float
```

### `compliance_checks.py`
**Functions**:
- `validate_risk_parameters(plan: TradePlan, account: Account) -> bool`
- `check_for_conflicts(symbol: str, direction: str, existing_positions: List[Position]) -> bool`
- `enforce_max_leverage(proposed_leverage: float, max_allowed: float) -> bool`

### `audit_pipeline.py`
**Classes**:
```python
class AuditLogger:
    def log_decision(context: SniperContext, decision: str, reason: str) -> None
    def log_quality_gate(gate_name: str, passed: bool, details: dict) -> None
    def generate_audit_report(run_id: str) -> AuditReport
```

---

## bot/

**Purpose**: Notifications, optional execution, charting, and telemetry.

### `bot/executor/`

#### `trades.py`
**Classes**:
```python
class TradeExecutor:
    def stage_order(plan: TradePlan, mode: str) -> Order  # mode: "dry-run" | "live"
    def submit_order(order: Order) -> ExecutionResult
    def monitor_execution(order_id: str) -> OrderStatus
```

#### `safeguards.py`
**Functions**:
- `check_duplicate_order(order: Order, recent_orders: List[Order]) -> bool`
- `enforce_max_position_risk(order: Order, account: Account) -> bool`
- `prevent_double_fire(symbol: str, direction: str, window_minutes: int) -> bool`

### `bot/notifications/`

#### `telegram.py`
**Classes**:
```python
class TelegramNotifier:
    def send_message(chat_id: str, message: TelegramMessage) -> bool
    def send_batch_summary(signals: List[TradePlan]) -> bool
    def send_alert(alert_type: str, details: dict) -> bool
```

#### `formatters.py`
**Functions**:
- `format_markdown(plan: TradePlan) -> str`
- `format_json(plan: TradePlan) -> dict`
- `format_confluence_breakdown(breakdown: ConfluenceBreakdown) -> str`
- `format_rationale(plan: TradePlan) -> str`

#### `templates/`
**Files**:
- `signal_template.md`: Template for single signal notification
- `batch_summary_template.md`: Template for multi-signal batch
- `alert_template.md`: Template for system alerts
- `audit_report_template.md`: Template for quality audit summaries

### `bot/ui/`

#### `charts.py`
**Functions**:
- `generate_chart(symbol: str, data: MultiTimeframeData, plan: TradePlan) -> str`  # Returns image URL
- `add_ob_overlays(chart: Chart, obs: List[OrderBlock]) -> Chart`
- `add_fvg_overlays(chart: Chart, fvgs: List[FVG]) -> Chart`
- `add_entry_stop_target_markers(chart: Chart, plan: TradePlan) -> Chart`

#### `overlays.py`
**Functions**:
- `create_smc_overlay(smc: SMCSnapshot) -> Overlay`
- `create_indicator_overlay(indicators: IndicatorSet) -> Overlay`

### `bot/telemetry/`

#### `analytics.py`
**Classes**:
```python
class Analytics:
    def track_signal_generated(plan: TradePlan) -> None
    def track_signal_rejected(reason: str) -> None
    def calculate_hit_rate(time_period: str) -> float
    def get_rr_distribution() -> Dict[str, int]
    def get_regime_performance() -> Dict[str, float]
```

#### `logging.py`
**Functions**:
- `log_structured(stage: str, level: str, data: dict) -> None`
- `log_pipeline_stage(stage_name: str, context: SniperContext) -> None`

#### `events.py`
**Dataclasses**:
```python
@dataclass
class TelemetryEvent:
    event_type: str
    timestamp: datetime
    context: dict

class EventTypes:
    SETUP_GENERATED = "setup_generated"
    SETUP_REJECTED = "setup_rejected"
    PLAN_CREATED = "plan_created"
    NOTIFICATION_SENT = "notification_sent"
    EXECUTION_ATTEMPTED = "execution_attempted"
    ERROR_OCCURRED = "error_occurred"
```

---

## engine/

**Purpose**: Pipeline orchestration, context management, hook system, and plugin coordination.

### `pipeline.py`
**Classes**:
```python
class Pipeline:
    def run(context: SniperContext) -> SniperContext:
        """
        Executes the full DAG:
        data → indicators → SMC → confluence → planner → risk → notifications
        """
        context = self._fetch_data(context)
        context = self._compute_indicators(context)
        context = self._detect_smc(context)
        context = self._score_confluence(context)
        context = self._generate_plan(context)
        context = self._validate_risk(context)
        context = self._notify(context)
        return context
```

### `context.py`
**Dataclasses**:
```python
@dataclass
class SniperContext:
    symbol: str
    profile: str
    run_id: str
    timestamp: datetime
    multi_tf_data: Optional[MultiTimeframeData] = None
    multi_tf_indicators: Optional[Dict[str, IndicatorSet]] = None
    smc_snapshot: Optional[SMCSnapshot] = None
    confluence_breakdown: Optional[ConfluenceBreakdown] = None
    plan: Optional[TradePlan] = None
    risk_plan: Optional[RiskPlan] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### `orchestrator.py`
**Classes**:
```python
class Orchestrator:
    def scan(symbols: List[str], profile: str) -> List[TradePlan]
    def scan_single(symbol: str, profile: str) -> Optional[TradePlan]
    def backtest(symbols: List[str], date_range: Tuple[datetime, datetime], profile: str) -> BacktestResults
```

### `hooks.py`
**Functions**:
- `register_hook(hook_name: str, callback: Callable) -> None`
- `execute_hooks(hook_name: str, context: SniperContext) -> SniperContext`
- `hook_point(name: str) -> Callable`  # Decorator

**Available Hooks**:
- `before_data_fetch`, `after_data_fetch`
- `before_indicator_compute`, `after_indicator_compute`
- `before_strategy`, `after_strategy`
- `before_risk`, `after_risk`
- `before_notify`, `after_notify`

### `plugins/`

#### `base.py`
**Classes**:
```python
class PluginBase(ABC):
    @abstractmethod
    def initialize(config: dict) -> None
    
    @abstractmethod
    def execute(context: SniperContext) -> SniperContext
```

#### `registry.py`
**Classes**:
```python
class PluginRegistry:
    def register(plugin: PluginBase) -> None
    def get_plugin(name: str) -> Optional[PluginBase]
    def list_plugins() -> List[str]
```

---

## ml/

**Purpose**: Future machine learning integration hooks.

### `feature_buffer.py`
**Classes**:
```python
class FeatureBuffer:
    def extract_features(context: SniperContext) -> np.ndarray
    def feature_names() -> List[str]
```

### `scoring_adapter.py`
**Classes**:
```python
class MLScoringAdapter:
    def load_model(model_path: str) -> None
    def predict(features: np.ndarray) -> float
    def rescore_signal(context: SniperContext) -> float
```

---

## devtools/

**Purpose**: Development and debugging utilities.

### `codegen_tools.py`
**Functions**:
- `generate_indicator_stub(name: str) -> str`
- `generate_strategy_stub(name: str) -> str`

### `profiling.py`
**Functions**:
- `profile_pipeline(context: SniperContext) -> ProfilingReport`
- `measure_stage_time(stage_name: str, func: Callable) -> Tuple[Any, float]`

### `debug_cli.py`
**Commands**:
- `debug inspect-context <run_id>`
- `debug replay-signal <signal_id>`
- `debug validate-fixtures`

---

## tests/

**Purpose**: Comprehensive test coverage and verification.

### `conftest.py`
**Fixtures**:
- `mock_ohlcv_trending()`
- `mock_ohlcv_ranging()`
- `mock_indicators()`
- `mock_smc_snapshot()`
- `mock_context()`

### `fixtures/`

#### `fixtures/ohlcv/`
**Files**:
- `trending_1w.json`
- `trending_1d.json`
- `ranging_4h.json`
- `volatile_1h.json`

#### `fixtures/signals/`
**Files**:
- `expected_ob_detection.json`
- `expected_fvg_detection.json`
- `expected_confluence_scores.json`

### `unit/`
**Test files**:
- `test_indicators.py`
- `test_smc_order_blocks.py`
- `test_smc_fvg.py`
- `test_confluence_scorer.py`
- `test_planner.py`
- `test_risk.py`
- `test_formatters.py`

### `integration/`
**Test files**:
- `test_full_pipeline.py`
- `test_data_to_notification.py`
- `test_quality_gates.py`

### `backtest/`
**Scripts**:
- `test_historical_accuracy.py`
- `test_regime_performance.py`

---

## docs/

**Purpose**: Comprehensive documentation.

### `architecture.md`
System architecture, data flow, package responsibilities (this document).

### `smc_playbook.md`
Smart-Money Concepts playbook: OB detection rules, FVG criteria, BOS/CHoCH logic, liquidity sweep confirmation.

### `notification_spec.md`
Telegram and JSON notification format specifications.

### `output_spec.md`
Strict schema for signal payloads with field types and non-null guarantees.

### `quality_gates.md`
Quality gate criteria: thresholds, gating logic, acceptance criteria.

### `verification_checklist.md`
Step-by-step verification process for new builds and releases.

### `versioning.md`
Semantic versioning rules and migration guidelines.

### `deployment.md`
Deployment instructions for mobile, server, Docker, and cloud environments.

---

## scripts/

**Purpose**: Operational and maintenance scripts.

### `run_backtest.py`
**Usage**: `python scripts/run_backtest.py --profile trend --start 2024-01-01 --end 2024-12-31 --output results.json`

### `run_quality_audit.py`
**Usage**: `python scripts/run_quality_audit.py --verbose`

### `sync_cache.py`
**Usage**: `python scripts/sync_cache.py --timeframes 1W,1D --symbols BTC/USDT,ETH/USDT`

---

## examples/

**Purpose**: Usage demonstrations and integration walkthroughs.

### `notebook_scenarios/`
**Notebooks**:
- `01_basic_scan.ipynb`
- `02_visualize_smc.ipynb`
- `03_compare_profiles.ipynb`
- `04_backtest_walkthrough.ipynb`

### `api_walkthroughs/`
**Scripts**:
- `library_integration.py`: Using SniperSight as a library
- `custom_strategy_plugin.py`: Extending with custom strategies
- `ml_integration_example.py`: Adding ML scoring

---

## CLI Commands

### `sniper_sight_cli.py`

#### `snipersight scan`
**Usage**: `snipersight scan --profile balanced --symbols top20`
**Options**:
- `--profile`: Configuration profile (balanced, trend, range, aggressive, mobile)
- `--symbols`: Symbol universe (top20, top50, custom list)
- `--output`: Output format (json, markdown, telegram)

#### `snipersight backtest`
**Usage**: `snipersight backtest --profile trend --start 2024-01-01 --end 2024-12-31 --output results.json`

#### `snipersight audit`
**Usage**: `snipersight audit --verbose`

#### `snipersight cache`
**Usage**: `snipersight cache sync --timeframes 1W,1D`

---

## Development Workflow

### Adding New Features

1. **Define contract** in `contracts/`
2. **Add model** to `shared/models/` if new data type
3. **Implement feature** in appropriate package
4. **Add tests** in `tests/unit/` and `tests/integration/`
5. **Add fixtures** for deterministic verification
6. **Update documentation** in `docs/`
7. **Run quality audit**: `snipersight audit`

### Running Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Full backtest
python scripts/run_backtest.py --profile balanced

# Quality audit
python scripts/run_quality_audit.py --verbose
```

### Debugging

```bash
# Inspect specific run context
python -m devtools.debug_cli inspect-context <run_id>

# Replay signal generation
python -m devtools.debug_cli replay-signal <signal_id>

# Profile pipeline performance
python -m devtools.profiling profile-scan --symbol BTC/USDT
```

---

This structure ensures:
- ✅ Clear separation of concerns
- ✅ Contract-driven development
- ✅ Deterministic verification
- ✅ Extensibility via plugins and hooks
- ✅ Zero silent failures
- ✅ Complete, actionable outputs
- ✅ Institutional-grade discipline
