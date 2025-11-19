# SniperSight Implementation Roadmap

## Important: Tech Stack Clarification

**SniperSight Backend** should be built in **Python** following the architecture in `ARCHITECTURE.md` and `PROJECT_STRUCTURE.md`.

**This workspace** contains both the TypeScript/React frontend (in `src/`) and the Python backend (in `backend/`) as a **monorepo**.

## Quick Start Guide

### Step 1: Set Up Python Environment in This Workspace

You're already in the correct workspace. Set up Python here:

```bash
# Initialize Python virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Create Python configuration files
touch requirements.txt
touch pyproject.toml
```

### Step 2: Initial Project Structure

Create the backend folder structure in this workspace:

```bash
# Create backend directory and all subdirectories
mkdir -p backend/{contracts,shared/{config/profiles,models,utils},data/adapters,indicators}
mkdir -p backend/strategy/{smc,confluence,planner}
mkdir -p backend/{risk,engine/plugins,ml,devtools}
mkdir -p backend/bot/{executor,notifications,ui,telemetry}
mkdir -p backend/tests/{fixtures/{ohlcv,signals},unit,integration,backtest}
mkdir -p backend/{scripts,examples}

# Create __init__.py files for Python packages
find backend -type d -exec touch {}/__init__.py \;
```

**Final structure:**
```
/workspaces/snipersight-trading/
├── backend/           # Python backend (NEW)
├── src/              # TypeScript frontend (existing)
├── docs/             # Shared documentation (existing)
├── requirements.txt  # Python dependencies
├── pyproject.toml    # Python configuration
└── package.json      # TypeScript dependencies
```

### Step 3: Install Core Dependencies

Create `requirements.txt`:

```txt
# Data & Analysis
pandas>=2.0.0
numpy>=1.24.0
ccxt>=4.0.0  # Multi-exchange crypto library
python-binance>=1.0.0
ta-lib>=0.4.0  # Technical analysis
polars>=0.19.0  # Optional: faster dataframes

# API & Web
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.0.0
python-dotenv>=1.0.0

# Bot & Notifications
python-telegram-bot>=20.0
aiohttp>=3.9.0

# Utilities
typer>=0.9.0  # CLI
loguru>=0.7.0  # Logging
redis>=5.0.0  # Caching (optional)
```

Install:
```bash
pip install -r requirements.txt
```

### Step 4: Start with Foundation (Phase 1)

#### 4.1 Create Shared Models

`shared/models/data.py`:
```python
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List
import pandas as pd

@dataclass
class OHLCVData:
    symbol: str
    timeframe: str
    df: pd.DataFrame  # columns: timestamp, open, high, low, close, volume
    timestamp: datetime

@dataclass
class MultiTimeframeData:
    symbol: str
    timeframes: Dict[str, pd.DataFrame]  # '1W' -> DataFrame, '1D' -> DataFrame, etc.
```

`shared/models/smc.py`:
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class OrderBlock:
    price: float
    timeframe: str
    direction: str  # 'bullish' or 'bearish'
    strength: float
    fresh: bool
    timestamp: datetime

@dataclass
class FairValueGap:
    top: float
    bottom: float
    timeframe: str
    direction: str
    filled: bool
```

#### 4.2 Create Configuration

`shared/config/defaults.py`:
```python
from dataclasses import dataclass

@dataclass
class ScanConfig:
    timeframes: List[str] = ('1W', '1D', '4H', '1H', '15m', '5m')
    min_confluence_score: float = 65.0
    min_rr_ratio: float = 2.0
    btc_impulse_gate_enabled: bool = True
    max_symbols: int = 20
```

#### 4.3 Create Contracts

`contracts/indicators_contract.py`:
```python
from abc import ABC, abstractmethod
from shared.models.indicators import IndicatorSet
import pandas as pd

class IndicatorProvider(ABC):
    @abstractmethod
    def compute(self, df: pd.DataFrame, config: dict) -> IndicatorSet:
        """Compute indicators from OHLCV data"""
        pass
```

### Step 5: Build Data Layer (Phase 2)

#### 5.1 Exchange Adapter

`data/adapters/binance.py`:
```python
import ccxt
from typing import List
import pandas as pd

class BinanceAdapter:
    def __init__(self, testnet: bool = False):
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        if testnet:
            self.exchange.set_sandbox_mode(True)
    
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
        """Fetch OHLCV data and return as DataFrame"""
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
```

#### 5.2 Ingestion Pipeline

`data/ingestion_pipeline.py`:
```python
from typing import Dict, List
from data.adapters.binance import BinanceAdapter
from shared.models.data import MultiTimeframeData

class IngestionPipeline:
    def __init__(self, adapter):
        self.adapter = adapter
    
    def fetch_multi_timeframe(self, symbol: str, timeframes: List[str]) -> MultiTimeframeData:
        """Fetch data across multiple timeframes"""
        tf_data = {}
        for tf in timeframes:
            df = self.adapter.fetch_ohlcv(symbol, tf)
            tf_data[tf] = df
        
        return MultiTimeframeData(symbol=symbol, timeframes=tf_data)
```

### Step 6: Build Analysis Layer (Phase 3)

#### 6.1 Indicators

`indicators/momentum.py`:
```python
import pandas as pd

def compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute RSI indicator"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi
```

#### 6.2 SMC Detection

`strategy/smc/order_blocks.py`:
```python
from typing import List
from shared.models.smc import OrderBlock

def detect_order_blocks(df: pd.DataFrame, config: dict) -> List[OrderBlock]:
    """Detect order blocks in price data"""
    obs = []
    # Implementation: find strong rejection candles with displacement
    # This is simplified - real implementation needs more sophistication
    for i in range(len(df) - 1):
        # Bullish OB: strong down candle followed by bullish displacement
        # Bearish OB: strong up candle followed by bearish displacement
        pass
    return obs
```

### Step 7: CLI Entry Point

`sniper_sight_cli.py`:
```python
import typer
from engine.orchestrator import Orchestrator
from shared.config.defaults import ScanConfig

app = typer.Typer()

@app.command()
def scan(
    profile: str = "balanced",
    symbols: str = "top20",
    exchange: str = "binance"
):
    """Run a market scan"""
    typer.echo(f"🎯 SniperSight - Sweeping the field...")
    typer.echo(f"Profile: {profile}, Symbols: {symbols}, Exchange: {exchange}")
    
    config = ScanConfig()
    orchestrator = Orchestrator(config)
    results = orchestrator.run_scan(symbols.split(','))
    
    typer.echo(f"✅ Scan complete: {len(results)} targets acquired")

if __name__ == "__main__":
    app()
```

## Implementation Phases Summary

### ✅ Phase 1: Foundation (Week 1)
- [ ] Set up Python project structure
- [ ] Create shared models (data, smc, indicators, scoring)
- [ ] Create contracts (API boundaries)
- [ ] Set up configuration system
- [ ] Create CLI skeleton

### ✅ Phase 2: Data Layer (Week 2)
- [ ] Implement Binance adapter
- [ ] Implement Bybit adapter (optional)
- [ ] Build caching system
- [ ] Create ingestion pipeline
- [ ] Add mock data fixtures for testing

### ✅ Phase 3: Analysis Layer (Week 3-4)
- [ ] Build indicator computation (RSI, ATR, Volume, etc.)
- [ ] Implement SMC detection (OBs, FVGs, BOS/CHoCH)
- [ ] Create confluence scoring engine
- [ ] Build trade planner (entries, stops, targets)

### ✅ Phase 4: Risk & Bot (Week 5)
- [ ] Implement position sizing
- [ ] Build risk management rules
- [ ] Create notification system (Telegram)
- [ ] Add executor layer (paper/live modes)

### ✅ Phase 5: Orchestration (Week 6)
- [ ] Build pipeline controller
- [ ] Implement context management
- [ ] Create hook system
- [ ] Wire up CLI commands

### ✅ Phase 6: Quality & Testing (Week 7-8)
- [ ] Add unit tests for all modules
- [ ] Create integration tests
- [ ] Build backtest framework
- [ ] Add verification checklist
- [ ] Performance profiling

## Using This Workspace

This is a **monorepo** containing both frontend and backend:

1. **📊 Progress Tracker** - TypeScript frontend in `src/` tracks implementation
2. **📖 Documentation** - Shared docs in `docs/` for both frontend and backend
3. **🐍 Python Backend** - Core trading engine in `backend/`
4. **🎯 Build Guide** - See `COPILOT_BUILD_GUIDE.md` for detailed Copilot prompts

**Advantages:**
- All context in one place for Copilot
- Frontend can immediately consume backend APIs
- Single source of truth for documentation

## Key Architecture Principles to Remember

1. **Preserve Smart-Money Edge** - Multi-timeframe context is king
2. **No-Null Outputs** - Every signal must be complete
3. **Verification-Ready** - Build tests alongside code
4. **Zero Silent Failures** - Fail loudly when data is missing
5. **Plugin-Friendly** - Make it easy to add new indicators/strategies

## Getting Help

- Review `ARCHITECTURE.md` for system design
- Check `PROJECT_STRUCTURE.md` for module details
- Read `docs/api_contract.md` for API specifications
- Use the Progress Tracker tab to see what's next

## Next Immediate Steps

1. ✅ **Review `COPILOT_BUILD_GUIDE.md`** - Detailed step-by-step prompts for Copilot
2. Set up Python virtual environment: `python -m venv venv && source venv/bin/activate`
3. Create `requirements.txt` and `pyproject.toml` (prompts in build guide)
4. Create backend folder structure (command in Step 2 above)
5. Follow Phase 1 in COPILOT_BUILD_GUIDE.md to build foundation
6. Use the exact Copilot prompts provided - they reference your architecture docs

**For Copilot implementation, use:** `COPILOT_BUILD_GUIDE.md`

Good luck! 🎯
