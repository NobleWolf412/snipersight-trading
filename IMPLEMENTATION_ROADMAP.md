# SniperSight Implementation Roadmap

## Important: Tech Stack Clarification

**SniperSight Backend** should be built in **Python** following the architecture in `ARCHITECTURE.md` and `PROJECT_STRUCTURE.md`.

**This Spark App** is a **TypeScript/React documentation viewer and progress tracker** to help you manage the Python implementation.

## Quick Start Guide

### Step 1: Set Up Python Repository

Create a new Python repository separate from this Spark app:

```bash
# Create new directory for Python backend
mkdir snipersight-backend
cd snipersight-backend

# Initialize Python project
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Create pyproject.toml
touch pyproject.toml
```

### Step 2: Initial Project Structure

Create the base folder structure as defined in `PROJECT_STRUCTURE.md`:

```bash
# Core packages
mkdir -p contracts shared/{config,models,utils}
mkdir -p data/adapters indicators
mkdir -p strategy/{smc,confluence,planner}
mkdir -p risk bot/{executor,notifications,ui,telemetry}
mkdir -p engine/plugins ml devtools
mkdir -p tests/{fixtures/{ohlcv,signals},unit,integration,backtest}
mkdir -p docs scripts examples
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

### 🚧 Phase 4: Risk & Bot (Week 5)
- [ ] Implement position sizing
- [ ] Build risk management rules
- [ ] Create notification system (Telegram)
- [ ] Add executor layer (paper/live modes)

**Status:** See PHASE4_IMPLEMENTATION.md and PHASE4_STEP_BY_STEP.md for detailed guides

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

## Using This Spark App

This TypeScript/React Spark app serves as your **Implementation Dashboard**:

1. **📊 Progress Tracker** - Track which phases/modules are complete
2. **📖 Documentation Viewer** - Read PRD, Architecture, and API specs
3. **✅ Verification Checklist** - Mark off implementation milestones
4. **🎯 Next Steps Suggestions** - Get guidance on what to build next

The Python backend is the actual SniperSight implementation.
This Spark app helps you organize and track that work.

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

1. Create Python repository: `snipersight-backend/`
2. Set up virtual environment and install dependencies
3. Create base folder structure
4. Implement `shared/models/data.py` with data classes
5. Build first exchange adapter for Binance
6. Test fetching OHLCV data for BTC/USDT across timeframes

Good luck! 🎯
