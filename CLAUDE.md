# CLAUDE.md - AI Assistant Guide for SniperSight Trading Platform

> **Last Updated:** December 4, 2025
> **Version:** 1.0.0
> **Status:** Active Development

This document provides comprehensive guidance for AI assistants working with the SniperSight codebase. It covers architecture, conventions, workflows, and best practices.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture & Tech Stack](#architecture--tech-stack)
3. [Repository Structure](#repository-structure)
4. [Development Workflows](#development-workflows)
5. [Coding Conventions](#coding-conventions)
6. [Key Concepts](#key-concepts)
7. [Common Tasks](#common-tasks)
8. [Quality Gates & Testing](#quality-gates--testing)
9. [Troubleshooting](#troubleshooting)
10. [References](#references)

---

## Project Overview

**SniperSight** is an institutional-grade cryptocurrency market scanner and trading platform that leverages Smart-Money Concepts (SMC) for multi-timeframe technical analysis. The system operates in two primary modes:

- **Scanner Mode (Recon)**: User-triggered scans for manual review and trading decisions
- **SniperBot Mode (Automated)**: Scheduled/continuous scanning with optional automated execution (paper/live)

### Core Philosophy

1. **Preserve Smart-Money Edge**: Honor multi-timeframe context, order blocks, FVGs, liquidity sweeps, BTC impulse gates, and institutional heuristics
2. **No-Null, Actionable Outputs**: All outputs complete—no "TBD" placeholders, no null sections
3. **Verification-Ready**: Deterministic fixtures, strong typing, schema validation, comprehensive test coverage
4. **Zero Silent Failures**: Missing indicators or incomplete data trigger hard errors—no half-formed signals
5. **Plugin-Friendly & ML-Ready**: Extensible architecture supporting future ML integration

---

## Architecture & Tech Stack

### Dual-Stack Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Frontend (React/TypeScript)                 │
│  Vite + React 19 + Tailwind v4 + shadcn/ui              │
│  Port: 5000                                             │
└────────────────────┬────────────────────────────────────┘
                     │ REST API
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Backend (Python/FastAPI)                    │
│  FastAPI + CCXT + pandas + TA-Lib                       │
│  Port: 8001                                             │
└─────────────────────────────────────────────────────────┘
```

### Frontend Stack

- **Framework**: React 19 with TypeScript
- **Build Tool**: Vite 6.x
- **Styling**: Tailwind CSS v4 (utility-first)
- **UI Components**: shadcn/ui (Radix UI primitives)
- **Icons**: Phosphor Icons (`@phosphor-icons/react`)
- **Routing**: React Router DOM v7
- **State Management**: React Context + localStorage (via custom `useLocalStorage` hook)
- **Charts**: D3.js for interactive price charts
- **LLM Integration**: GitHub Spark (`@github/spark`) for AI-powered features

### Backend Stack

- **Framework**: FastAPI (async REST API)
- **Language**: Python 3.10+
- **Exchange Integration**: CCXT (multi-exchange support)
- **Data Processing**: pandas, numpy
- **Technical Analysis**: TA-Lib, pandas-ta
- **Validation**: Pydantic v2 (data models and validation)
- **CLI**: Typer (command-line interface)
- **Testing**: pytest, pytest-asyncio
- **Logging**: Loguru (structured logging)

### Exchange Adapters (Tier 1)

Production-ready integrations in `backend/data/adapters/`:

1. **PhemexAdapter** (default): No geo-blocking, fast, works globally
2. **BybitAdapter**: Best overall, may have geo-restrictions
3. **OKXAdapter**: Institutional-tier exchange
4. **BitgetAdapter**: Bot-friendly features
5. **BinanceAdapter**: Deprecated due to geo-restrictions

All adapters implement retry logic, rate limiting, and standardized data normalization.

---

## Repository Structure

```
snipersight-trading/
├── backend/                      # Python backend (FastAPI)
│   ├── api_server.py            # Main FastAPI application
│   ├── cli.py                   # CLI entry point (Typer)
│   ├── contracts/               # API boundary definitions
│   ├── shared/                  # Cross-cutting models, configs, utilities
│   │   ├── config/             # Configuration system
│   │   │   ├── defaults.py     # Global thresholds and defaults
│   │   │   ├── scanner_modes.py # Predefined trading profiles
│   │   │   ├── smc_config.py   # SMC detection parameters
│   │   │   └── profiles/       # Mode-specific configs (balanced, trend, range, etc.)
│   │   ├── models/             # Dataclass definitions
│   │   │   ├── data.py         # OHLCV, MultiTimeframeData
│   │   │   ├── indicators.py   # IndicatorSnapshot, IndicatorSet
│   │   │   ├── smc.py          # OrderBlock, FVG, StructuralBreak, etc.
│   │   │   ├── scoring.py      # ConfluenceFactor, ConfluenceBreakdown
│   │   │   └── planner.py      # TradePlan, EntryZone, StopLoss, Target
│   │   └── utils/              # Utilities
│   │       ├── caching.py      # Cache manager
│   │       └── error_policy.py # Quality gate enforcement
│   ├── data/                    # Multi-exchange data ingestion
│   │   ├── adapters/           # Exchange adapters (Binance, Bybit, OKX, etc.)
│   │   │   ├── binance.py
│   │   │   ├── bybit.py
│   │   │   ├── okx.py
│   │   │   ├── phemex.py
│   │   │   ├── bitget.py
│   │   │   ├── mocks.py        # Mock data generators for testing
│   │   │   └── retry.py        # Retry logic decorator
│   │   └── ingestion_pipeline.py # Multi-TF data fetching
│   ├── indicators/              # Technical analysis computation
│   │   ├── momentum.py         # RSI, Stoch RSI, MFI
│   │   ├── volatility.py       # ATR, realized volatility
│   │   └── volume.py           # Volume spikes, OBV
│   ├── strategy/                # SMC detection & confluence scoring
│   │   ├── smc/                # Smart-Money Concepts detection
│   │   │   ├── order_blocks.py # Order block detection
│   │   │   ├── fvg.py          # Fair Value Gap detection
│   │   │   ├── bos_choch.py    # Break of Structure / Change of Character
│   │   │   └── liquidity_sweeps.py # Liquidity sweep detection
│   │   ├── confluence/         # Multi-factor scoring
│   │   │   ├── scorer.py       # Confluence calculation engine
│   │   │   └── regime_detection.py # Market regime classification
│   │   └── planner/            # Trade plan generation
│   │       ├── entry.py        # Entry zone calculation
│   │       ├── stops_targets.py # Stop-loss and target generation
│   │       └── planner_service.py # Complete trade plan assembly
│   ├── risk/                    # Risk management
│   │   ├── risk_manager.py     # Position sizing, exposure limits
│   │   └── correlation_matrix.py # Asset correlation tracking
│   ├── engine/                  # Pipeline orchestration
│   │   ├── orchestrator.py     # Main pipeline coordinator
│   │   ├── context.py          # SniperContext dataclass
│   │   └── plugins/            # Plugin system
│   ├── bot/                     # Bot automation & telemetry
│   │   ├── executor/           # Trade execution (paper/live)
│   │   ├── notifications/      # Telegram integration
│   │   └── telemetry/          # Event logging and analytics
│   ├── ml/                      # ML integration (future)
│   ├── tests/                   # Test suites
│   │   ├── fixtures/           # Deterministic test data
│   │   ├── unit/               # Unit tests
│   │   ├── integration/        # Integration tests
│   │   └── backtest/           # Backtesting framework
│   └── scripts/                 # Operational scripts
│
├── src/                         # React/TypeScript frontend
│   ├── App.tsx                 # Root component with routing
│   ├── main.tsx                # Entry point with provider hierarchy
│   ├── components/             # Reusable UI components
│   │   ├── common/             # Base components (Button, Card, Badge, etc.)
│   │   ├── scanner/            # Scanner-specific components
│   │   ├── bot/                # Bot control panel components
│   │   ├── market/             # Market regime components
│   │   ├── telemetry/          # Telemetry display components
│   │   └── ChartModal/         # D3.js chart with AI analysis
│   ├── pages/                  # Route pages
│   │   ├── ScannerSetup.tsx   # Scanner configuration
│   │   ├── ScanResults.tsx    # Signal display
│   │   ├── BotSetup.tsx       # Bot configuration
│   │   ├── BotStatus.tsx      # Bot monitoring
│   │   ├── MarketOverview.tsx # Market dashboard
│   │   └── TrainingGround.tsx # Educational mode
│   ├── context/                # React Context providers
│   │   ├── ScannerContext.tsx # Scan/bot config state
│   │   └── WalletContext.tsx  # Web3 wallet authentication
│   ├── hooks/                  # Custom React hooks
│   │   ├── useLocalStorage.ts # localStorage persistence hook
│   │   ├── useScanner.ts      # Scanner state hook
│   │   ├── useMarketRegime.ts # Market regime data hook
│   │   └── useTelemetry.ts    # Telemetry polling hook
│   ├── services/               # API client services
│   ├── types/                  # TypeScript type definitions
│   └── utils/                  # Utility functions
│       ├── api.ts              # Typed API client
│       └── mockData.ts         # Mock data generators
│
├── docs/                        # Documentation
│   ├── TELEMETRY_GUIDE.md     # Telemetry system guide
│   ├── INTEGRATION_GUIDE.md   # API integration guide
│   ├── security.md            # Security best practices
│   ├── exchange_profiles.md   # Exchange configuration
│   └── SMC_PIPELINE_REFACTOR.md # SMC pipeline documentation
│
├── scripts/                     # Development scripts
│   ├── start_dev.sh           # Combined frontend + backend startup
│   ├── auto_sync.sh           # Git auto-sync utility
│   └── safe_sync.sh           # Safe git sync with confirmation
│
├── package.json                # Frontend dependencies
├── requirements.txt            # Backend dependencies
├── pyproject.toml             # Python project config
├── vite.config.ts             # Vite configuration
├── tsconfig.json              # TypeScript configuration
└── tailwind.config.js         # Tailwind CSS configuration
```

### Critical Files Reference

**Backend Core:**
- `backend/engine/orchestrator.py` - Main pipeline coordinator
- `backend/api_server.py` - FastAPI application with all endpoints
- `backend/shared/config/scanner_modes.py` - Predefined trading profiles
- `backend/strategy/planner/planner_service.py` - Trade plan generation

**Frontend Core:**
- `src/App.tsx` - Route definitions
- `src/main.tsx` - Provider hierarchy setup
- `src/context/ScannerContext.tsx` - Scanner state management
- `src/pages/ScannerSetup.tsx` - Configuration UI
- `src/pages/ScanResults.tsx` - Signal display
- `src/utils/api.ts` - Typed API client

---

## Development Workflows

### Starting the Development Environment

```bash
# Option 1: Combined startup (recommended)
./scripts/start_dev.sh

# Option 2: Manual startup
# Terminal 1 - Backend (FastAPI on :8001)
python -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8001 --reload

# Terminal 2 - Frontend (Vite on :5000)
npm run dev:frontend

# Kill processes on ports if needed
npm run kill  # Kills :5000 and :8001
```

### Running Tests

```bash
# Backend tests
pytest backend/tests -v --cov=backend

# Specific module
pytest backend/tests/test_orchestrator.py -v

# Integration tests
pytest backend/tests/integration/ -v

# Frontend tests
npm run test

# Smoke tests
npm run test:smoke
```

### Building for Production

```bash
# Frontend build
npm run build

# Backend build (placeholder)
npm run build:backend

# Full build
npm run build
```

### Common npm Scripts

```bash
npm run dev                # Start Vite dev server
npm run dev:frontend       # Start frontend on :5000
npm run backend            # Start backend on :8001
npm run dev:all            # Start both (concurrently)
npm run build              # Production build
npm run lint               # ESLint
npm run preview            # Preview production build
npm run storybook          # Start Storybook on :6006
```

---

## Coding Conventions

### Backend (Python)

**Naming Conventions:**
- **Modules/Files**: `snake_case` (e.g., `order_blocks.py`, `risk_manager.py`)
- **Classes**: `PascalCase` (e.g., `OrderBlockDetector`, `RiskManager`)
- **Functions/Methods**: `snake_case` (e.g., `detect_order_blocks()`, `calculate_risk()`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RISK_PER_TRADE`, `DEFAULT_TIMEFRAMES`)
- **Private methods**: `_leading_underscore` (e.g., `_internal_helper()`)

**Type Hints & Validation:**
```python
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# Dataclasses for internal models
@dataclass
class OrderBlock:
    timeframe: str
    direction: str  # "bullish" | "bearish"
    high: float
    low: float
    displacement_strength: float

# Pydantic for API contracts
class ScanRequest(BaseModel):
    symbols: List[str]
    mode: str = Field(..., description="Scanner mode")
    leverage: float = Field(default=1.0, ge=1.0, le=20.0)
```

**Error Handling:**
```python
# NEVER silently return None
# BAD
if indicators is None:
    return None  # ❌ Silent failure

# GOOD
if indicators is None:
    raise IncompleteIndicatorError(
        f"Missing indicators for {symbol} on {timeframe}"
    )  # ✅ Explicit failure
```

**Docstrings:**
```python
def detect_order_blocks(
    df: pd.DataFrame,
    config: dict
) -> List[OrderBlock]:
    """
    Detect institutional order blocks using Smart-Money Concepts.

    Args:
        df: OHLCV DataFrame with timestamp index
        config: Detection configuration (displacement_threshold, etc.)

    Returns:
        List of OrderBlock instances with displacement and freshness scores

    Raises:
        ValueError: If DataFrame is empty or missing required columns
    """
    pass
```

**Quality Gates:**
- All functions must have type hints
- Use dataclasses for internal models, Pydantic for API boundaries
- Validate inputs early (fail fast)
- No null/None in critical output fields
- Log all decisions for audit trail

### Frontend (TypeScript/React)

**Naming Conventions:**
- **Files/Components**: `PascalCase` (e.g., `ScannerSetup.tsx`, `ChartModal.tsx`)
- **Functions**: `camelCase` (e.g., `handleScanStart`, `fetchMarketData`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `API_BASE_URL`, `DEFAULT_LEVERAGE`)
- **Route paths**: `kebab-case` (e.g., `/scanner/setup`, `/bot/status`)

**Component Patterns:**
```typescript
// Functional components with TypeScript
interface ScanResultsProps {
  results: ScanResult[];
  onRefresh: () => void;
}

export function ScanResults({ results, onRefresh }: ScanResultsProps) {
  const [selectedSignal, setSelectedSignal] = useState<ScanResult | null>(null);

  useEffect(() => {
    // Load from localStorage on mount
    const storedResults = localStorage.getItem('scan-results');
    if (storedResults) {
      // Handle deserialization
    }
  }, []);

  return (
    <PageLayout maxWidth="xl">
      {/* Component JSX */}
    </PageLayout>
  );
}
```

**State Management:**
```typescript
// Context usage
const { scanConfig, setScanConfig } = useScanner();

// localStorage persistence via custom hook
const [config, setConfig] = useLocalStorage<ScanConfig>(
  'scan-config',
  DEFAULT_CONFIG
);

// Manual localStorage (in page components for scan results)
localStorage.setItem('scan-results', JSON.stringify(results));
const results = JSON.parse(localStorage.getItem('scan-results') || '[]');
```

**API Integration:**
```typescript
// Always check for errors
const response = await api.getSignals(runId);
if (response.error) {
  console.error('Failed to fetch signals:', response.error);
  // Fallback to mock data or show error UI
  return;
}
const signals = response.data;
```

**Styling:**
- Use Tailwind utility classes (no inline styles)
- Dark theme optimized: `bg-background`, `text-foreground`
- Accent colors: `text-accent` (scanner), `text-primary` (bot)
- Consistent spacing: `space-y-4`, `gap-6`, `p-6`
- Responsive: `md:grid-cols-2 lg:grid-cols-3`

**Component Composition:**
```typescript
<PageLayout maxWidth="lg">
  <PageHeader
    title="Scanner Setup"
    description="Configure your scan parameters"
    icon={<Crosshair />}
  />
  <PageSection title="CONFIGURATION">
    <Card>
      {/* Content */}
    </Card>
  </PageSection>
</PageLayout>
```

---

## Key Concepts

### Smart-Money Concepts (SMC)

**Order Block (OB):**
- Last opposing candle before strong directional move
- Bullish OB = last red candle before green surge
- Bearish OB = last green candle before red drop
- Requires displacement ≥ 1.5 ATR to confirm institutional presence

**Fair Value Gap (FVG):**
- Price gap indicating liquidity imbalance
- Identified by 3-candle pattern where middle candle doesn't fill gap
- Markets tend to "fill the gap" (return to FVG zone)

**Break of Structure (BOS):**
- Higher high (bullish) or lower low (bearish)
- Confirms trend continuation
- Must align with higher timeframe trend

**Change of Character (CHoCH):**
- Counter-trend structure break
- Signals potential trend reversal
- Requires confirmation from other factors

**Liquidity Sweep:**
- Wick beyond recent high/low followed by rejection
- "Stop hunt" - institutional traders trigger retail stops before reversing
- Confirmation: close back inside previous range

**Displacement:**
- Strong directional move ≥ 1.5 ATR
- Shows institutional conviction
- Required for valid order blocks

### Multi-Timeframe Analysis

SniperSight analyzes **6 timeframes simultaneously**:

| Timeframe | Purpose | Weight |
|-----------|---------|--------|
| 1W (Weekly) | Major trend direction | Highest |
| 1D (Daily) | Primary market structure | High |
| 4H | Intermediate structure & alignment | Medium-High |
| 1H | Entry refinement & context | Medium |
| 15m | Precise entry zones | Medium-Low |
| 5m | Execution timeframe | Low |

**HTF (Higher Timeframe) Alignment:**
- Entry on 15m must align with 1H, 4H, 1D trend
- Signals rejected if HTF shows opposing structure
- Quality gate enforced in `ConfluenceScorer`

### Scanner Modes (Backend Truth)

Defined in `backend/shared/config/scanner_modes.py`:

| Mode | Timeframes | Min Score | R:R | Description |
|------|-----------|-----------|-----|-------------|
| **overwatch** | 6 TFs (1w→5m) | 75% | 3.0 | Macro surveillance, strict quality |
| **recon** | 5 TFs (1d→5m) | 65% | 2.5 | Balanced multi-timeframe |
| **strike** | 4 TFs (4h→5m) | 60% | 2.0 | Intraday aggressive |
| **surgical** | 3 TFs (1h→5m) | 70% | 2.5 | Precision scalping |
| **ghost** | 5 TFs (1d→5m) | 70% | 2.5 | Stealth balanced |

**Critical Timeframes:**
- Each mode specifies required timeframes
- Symbols missing critical TFs are rejected
- Logged to telemetry with reason

**Frontend Static Modes:**
- `src/context/ScannerContext.tsx` has STATIC mode definitions for UI display
- Should mirror backend but are NOT fetched from API
- Backend modes in `scanner_modes.py` are source of truth for pipeline behavior

### Pipeline Flow

```
1. Symbol Selection
   ↓
2. Multi-TF Data Ingestion (via exchange adapter)
   ↓
3. Indicator Computation (per timeframe)
   ↓
4. SMC Detection (order blocks, FVGs, BOS/CHoCH, liquidity sweeps)
   ↓
5. Regime Detection (trend/range, BTC impulse gate)
   ↓
6. Confluence Scoring (multi-factor with synergy/conflict)
   ↓
7. Quality Gates (HTF alignment, freshness, displacement)
   ↓
8. Trade Plan Generation (entry zones, stops, targets, R:R)
   ↓
9. Risk Validation (position sizing, exposure limits, correlation)
   ↓
10. Notification / Execution (Telegram, bot, audit logging)
```

### Quality Gates

**Data Quality:**
- Complete timeframe coverage (no missing TFs)
- Minimum candle count per TF (500+ for reliability)
- Recent data (no stale cache beyond TTL)
- Valid OHLCV relationships (H≥C≥L, H≥O, L≤O)

**Indicator Quality:**
- No null/NaN values in recent window
- Successful computation for all indicators
- Reasonable value ranges (RSI 0-100, etc.)

**SMC Quality:**
- Fresh order blocks (not heavily mitigated)
- Sufficient displacement strength (≥1.5 ATR)
- HTF structural alignment required
- Valid liquidity sweep confirmation

**Confluence Quality:**
- Minimum score threshold (mode-dependent)
- Low conflict penalty (<5 points)
- Regime alignment (trend mode in trending market)
- BTC impulse gate (if enabled)

**Plan Quality:**
- R:R ratio ≥ mode minimum (2.0-3.0)
- Stops not placed in FVG or OB zones
- Targets aligned with structural levels
- Complete rationale (no empty sections)

**Risk Quality:**
- Position size within limits (max 2% per trade)
- Total exposure below cap (max 10% aggregate)
- No conflicting positions (opposing directions in same symbol)
- Correlation-aware exposure (correlated assets share limits)

### Telemetry System

**Event Types:**
```python
# Scanner events
"scan_started"           # Scan initiated
"scan_completed"         # Scan finished
"signal_generated"       # Valid signal created
"signal_rejected"        # Signal failed quality gates

# Bot events
"bot_started"            # Bot deployed
"bot_stopped"            # Bot ceased operation
"position_opened"        # Trade entered
"position_closed"        # Trade exited

# Error events
"error_occurred"         # System error
"quality_gate_failed"    # Specific gate failure
```

**Logging Pattern:**
```python
from backend.bot.telemetry.events import create_signal_generated_event
from backend.bot.telemetry.logging import get_telemetry_logger

telemetry = get_telemetry_logger()
telemetry.log_event(create_signal_generated_event(
    symbol="BTC/USDT",
    direction="LONG",
    confidence_score=87.5,
    risk_reward=3.2,
    regime="trending"
))
```

**Frontend Polling:**
- `ActivityFeed` component polls `/api/telemetry/recent` every 3-4 seconds
- Displays events with icons/colors per event type
- Auto-scrolls to latest events

---

## Common Tasks

### Adding a New Scanner Mode

1. **Update backend configuration** (`backend/shared/config/scanner_modes.py`):
```python
MODES = {
    # ... existing modes ...
    "new_mode": ScannerMode(
        name="new_mode",
        timeframes=("1d", "4h", "1h", "15m"),
        critical_timeframes=("1d", "4h", "1h"),
        min_confluence=70.0,
        min_rr_ratio=2.5,
        # ... other params ...
    )
}
```

2. **Restart backend**:
```bash
# Backend will auto-reload if using --reload flag
# Otherwise restart manually
```

3. **Optionally update frontend** (`src/context/ScannerContext.tsx`):
```typescript
const SCANNER_MODES = [
  // ... existing modes ...
  {
    id: 'new_mode',
    name: 'New Mode',
    description: 'Description of new mode',
    // ... mirror backend config ...
  }
];
```

### Adding a New Backend Endpoint

1. **Add route in `backend/api_server.py`**:
```python
@app.get("/api/new-endpoint")
async def new_endpoint(param: str = Query(...)):
    """Endpoint description."""
    try:
        result = some_function(param)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"New endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

2. **Update frontend API client** (`src/utils/api.ts`):
```typescript
export const api = {
  // ... existing methods ...

  async newEndpoint(param: string): Promise<ApiResponse<ResultType>> {
    return await apiRequest<ResultType>('/api/new-endpoint', {
      method: 'GET',
      params: { param }
    });
  }
};
```

3. **Use in components**:
```typescript
const { data, error } = await api.newEndpoint('value');
if (error) {
  // Handle error
  return;
}
// Use data
```

### Adding a New SMC Pattern Detector

1. **Create detector module** (`backend/strategy/smc/new_pattern.py`):
```python
from typing import List
from backend.shared.models.smc import NewPattern

def detect_new_pattern(
    df: pd.DataFrame,
    config: dict
) -> List[NewPattern]:
    """
    Detect new SMC pattern.

    Args:
        df: OHLCV DataFrame
        config: Detection parameters

    Returns:
        List of detected patterns
    """
    patterns = []
    # Detection logic
    return patterns
```

2. **Add to `SMCSnapshot` dataclass** (`backend/shared/models/smc.py`):
```python
@dataclass
class SMCSnapshot:
    order_blocks: List[OrderBlock]
    fvgs: List[FVG]
    # ... existing fields ...
    new_patterns: List[NewPattern]  # Add this
```

3. **Wire into Orchestrator** (`backend/engine/orchestrator.py`):
```python
def _detect_smc(self, context: SniperContext) -> SniperContext:
    # ... existing detection ...

    # Add new pattern detection
    from backend.strategy.smc.new_pattern import detect_new_pattern
    new_patterns = detect_new_pattern(df, self.config)

    context.smc_snapshot.new_patterns = new_patterns
    return context
```

4. **Update confluence scorer** (`backend/strategy/confluence/scorer.py`):
```python
# Add new factor for pattern in confluence calculation
if context.smc_snapshot.new_patterns:
    factors.append(ConfluenceFactor(
        name="new_pattern",
        score=calculate_pattern_score(context.smc_snapshot.new_patterns),
        weight=0.15,
        rationale="New pattern detected with X characteristics"
    ))
```

### Adding a New UI Page

1. **Create page component** (`src/pages/NewPage.tsx`):
```typescript
import { PageLayout, PageHeader } from '@/components/common';

export function NewPage() {
  return (
    <PageLayout maxWidth="xl">
      <PageHeader
        title="New Page"
        description="Page description"
        icon={<Icon />}
      />
      {/* Page content */}
    </PageLayout>
  );
}
```

2. **Register route** (`src/App.tsx`):
```typescript
function App() {
  return (
    <Routes>
      {/* ... existing routes ... */}
      <Route path="/new-page" element={<NewPage />} />
    </Routes>
  );
}
```

3. **Add navigation link** (in relevant component):
```typescript
<Link to="/new-page">
  <Button>Go to New Page</Button>
</Link>
```

### Working with localStorage

**ScanResults Pattern:**

**Save (in `ScannerSetup.tsx`):**
```typescript
// After successful scan
localStorage.setItem('scan-results', JSON.stringify(results));
localStorage.setItem('scan-metadata', JSON.stringify({
  timestamp: new Date().toISOString(),
  mode: scanConfig.mode,
  symbolCount: results.length
}));
```

**Load (in `ScanResults.tsx`):**
```typescript
useEffect(() => {
  const resultsStr = localStorage.getItem('scan-results');
  const metadataStr = localStorage.getItem('scan-metadata');

  if (resultsStr) {
    const results = JSON.parse(resultsStr);
    setScanResults(results);
  }

  if (metadataStr) {
    const metadata = JSON.parse(metadataStr);
    setScanMetadata(metadata);
  }
}, []);
```

**Using Custom Hook:**
```typescript
import { useLocalStorage } from '@/hooks/useLocalStorage';

function Component() {
  const [config, setConfig] = useLocalStorage<Config>(
    'my-config-key',
    DEFAULT_CONFIG
  );

  // Acts like useState but persists to localStorage
  setConfig({ ...config, newValue: 'updated' });
}
```

---

## Quality Gates & Testing

### Backend Testing

**Unit Tests:**
```bash
# Test specific module
pytest backend/tests/unit/test_order_blocks.py -v

# With coverage
pytest backend/tests/unit/ -v --cov=backend.strategy.smc
```

**Integration Tests:**
```bash
# Full pipeline tests
pytest backend/tests/integration/ -v

# Specific integration scenario
pytest backend/tests/integration/test_full_pipeline.py -v
```

**Test Fixtures:**
- Deterministic OHLCV data in `backend/tests/fixtures/ohlcv/`
- Expected signal outputs in `backend/tests/fixtures/signals/`
- Use `conftest.py` for shared fixtures

**Example Test:**
```python
import pytest
from backend.strategy.smc.order_blocks import detect_order_blocks
from backend.tests.conftest import mock_ohlcv_trending

def test_order_block_detection():
    df = mock_ohlcv_trending()
    config = {"displacement_threshold": 1.5}

    obs = detect_order_blocks(df, config)

    assert len(obs) > 0
    assert all(ob.displacement_strength >= 1.5 for ob in obs)
    assert all(ob.freshness_score >= 0 for ob in obs)
```

### Frontend Testing

**Component Tests:**
```bash
npm run test

# Specific component
npm run test -- ScannerSetup.test.tsx
```

**Smoke Tests:**
```bash
npm run test:smoke
```

### Quality Gate Enforcement

**In Backend Code:**
```python
from backend.shared.utils.error_policy import (
    enforce_complete_indicators,
    enforce_complete_smc,
    enforce_complete_plan
)

# After indicator computation
enforce_complete_indicators(context.multi_tf_indicators)

# After SMC detection
enforce_complete_smc(context.smc_snapshot)

# After plan generation
enforce_complete_plan(context.plan)
```

**Validation Checklist:**
- [ ] All type hints present
- [ ] No null/None in critical output fields
- [ ] Docstrings for public functions
- [ ] Error cases handled explicitly
- [ ] Tests written for new functionality
- [ ] Telemetry events logged for important actions

---

## Troubleshooting

### Backend Issues

**Import Errors:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # or .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Check Python path
python -c "import sys; print(sys.path)"
```

**Exchange API Errors:**
```python
# Check adapter configuration
from backend.data.adapters.phemex import PhemexAdapter
adapter = PhemexAdapter()
# Test data fetch
df = adapter.fetch_ohlcv('BTC/USDT', '1h', limit=100)
print(df.head())
```

**Indicator Computation Errors:**
- Ensure sufficient data (500+ candles recommended)
- Check for NaN/inf values in OHLCV data
- Verify ATR period doesn't exceed data length

**Quality Gate Failures:**
```python
# Check telemetry for rejection reasons
from backend.bot.telemetry.logging import get_telemetry_logger
logger = get_telemetry_logger()
# Review recent events for "signal_rejected" events
```

### Frontend Issues

**Build Errors:**
```bash
# Clear cache and rebuild
rm -rf node_modules/.vite
npm run build

# Check TypeScript errors
npm run lint
```

**State Not Persisting:**
```typescript
// Check localStorage in DevTools
console.log(localStorage.getItem('scan-results'));

// Clear if corrupted
localStorage.clear();
```

**API Connection Issues:**
```bash
# Verify backend is running
curl http://localhost:8001/health

# Check CORS configuration in backend
# api_server.py should have:
# app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
```

**Component Not Rendering:**
- Check React DevTools for component tree
- Verify imports are correct (use `@/` path alias)
- Check for errors in browser console
- Ensure providers are properly nested in `main.tsx`

### Common Pitfalls

1. **Never use `<a href>`** - Always use `<Link to>` from `react-router-dom`
2. **Backend signals must have complete rationale** - Check `planner_service.py`
3. **Don't bypass Orchestrator** - Direct SMC detection skips quality gates
4. **Frontend imports use `@/`** - Path alias in `tsconfig.json`
5. **Scan results use direct localStorage** - Not context persistence
6. **Spark components require import** - `@github/spark/spark` in `main.tsx`
7. **Check existing components first** - Avoid duplicate implementations
8. **Exchange adapter required** - Orchestrator needs explicit adapter (no default)

---

## References

### Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture, data flow, design principles
- **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - Detailed module breakdown
- **[PRD.md](PRD.md)** - Product requirements and specifications
- **[IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md)** - Phased implementation plan
- **[COPILOT_BUILD_GUIDE.md](COPILOT_BUILD_GUIDE.md)** - Step-by-step build instructions
- **[.github/copilot-instructions.md](.github/copilot-instructions.md)** - GitHub Copilot integration guide
- **[docs/TELEMETRY_GUIDE.md](docs/TELEMETRY_GUIDE.md)** - Telemetry system documentation
- **[docs/INTEGRATION_GUIDE.md](docs/INTEGRATION_GUIDE.md)** - API integration guide
- **[docs/security.md](docs/security.md)** - Security best practices
- **[docs/exchange_profiles.md](docs/exchange_profiles.md)** - Exchange configuration

### Key Endpoints

**Scanner:**
- `POST /api/scanner/scan` - Initiate scan
- `GET /api/scanner/signals` - Get scan results
- `GET /api/scanner/modes` - Get available scanner modes

**Bot:**
- `POST /api/bot/start` - Start bot
- `POST /api/bot/stop` - Stop bot
- `GET /api/bot/status` - Get bot status
- `GET /api/bot/positions` - Get open positions

**Market:**
- `GET /api/market/price/{symbol}` - Get current price
- `GET /api/market/candles/{symbol}` - Get OHLCV data
- `GET /api/market/regime` - Get market regime

**Telemetry:**
- `GET /api/telemetry/recent` - Get recent events
- `GET /api/telemetry/events` - Get filtered events
- `GET /api/telemetry/analytics` - Get analytics summary

**Risk:**
- `GET /api/risk/summary` - Get risk summary
- `GET /api/risk/correlation-matrix` - Get correlation matrix

### External Resources

- **CCXT Documentation**: https://docs.ccxt.com/
- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **React Documentation**: https://react.dev/
- **Tailwind CSS**: https://tailwindcss.com/
- **shadcn/ui**: https://ui.shadcn.com/
- **Phosphor Icons**: https://phosphoricons.com/

---

## Version History

- **v1.0.0** (2025-12-04) - Initial comprehensive guide

---

**For questions or clarifications, refer to the documentation files listed in the References section or review the inline comments in the codebase.**
