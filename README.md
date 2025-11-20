# SniperSight – Crypto Trading Scanner & Bot

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Status](https://img.shields.io/badge/status-active-green)
![Type](https://img.shields.io/badge/type-trading--bot-purple)

**An institutional-grade crypto market scanner with automated trading capabilities leveraging Smart-Money Concepts across multi-timeframe analysis.**

---

## 🎯 What is SniperSight?

SniperSight is a **full-stack crypto trading platform** combining market analysis, risk management, and automated trading execution.

### Current Features

- ✅ **Smart-Money Concepts Detection** (Order Blocks, FVG, Liquidity Sweeps)
- ✅ **Multi-Timeframe Analysis** (1m, 5m, 15m, 1h, 4h, 1d)
- ✅ **Advanced Risk Management** (Position Sizing, Portfolio Controls, Loss Limits)
- ✅ **Paper Trading Executor** (Realistic simulation with slippage)
- ✅ **Wallet Authentication** (MetaMask, WalletConnect)
- ✅ **TradingView Integration** (Chart analysis & visualization)
- ✅ **REST API Backend** (FastAPI with comprehensive endpoints)
- ✅ **Modern React UI** (TypeScript, Tailwind CSS)

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- npm or yarn

### Installation

```bash
# Clone repository
git clone https://github.com/NobleWolf412/snipersight-trading.git
cd snipersight-trading

# Install dependencies
pip install -r requirements.txt
npm install

# Start both backend and frontend
./start.sh
```

Access the application:
- **Frontend UI**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## 📚 Documentation

### Core Documents

| Document | Description |
|----------|-------------|
| **[PRD.md](PRD.md)** | Complete product requirements, features, design specifications |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | System architecture, data flow, core design principles |
| **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** | Detailed module breakdown with responsibilities |
| **[QUICKSTART.md](QUICKSTART.md)** | Quick start guide and implementation roadmap |
| **[INTEGRATION_GUIDE.md](docs/INTEGRATION_GUIDE.md)** | Backend-Frontend integration guide |
| **[WALLET_AUTHENTICATION.md](docs/WALLET_AUTHENTICATION.md)** | Wallet connection setup |

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React/TypeScript)               │
│     Scanner Setup • Bot Config • Chart Analysis • Wallet     │
└────────────────────────┬────────────────────────────────────┘
                         │ REST API
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  Backend API (FastAPI)                       │
│      Endpoints • Authentication • Data Aggregation           │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   Scanner    │ │ Risk Manager │ │   Executor   │
│   Engine     │ │ & Sizer      │ │   (Paper)    │
└──────────────┘ └──────────────┘ └──────────────┘
         │               │               │
         └───────────────┼───────────────┘
                         ▼
              ┌────────────────────┐
              │ Exchange Adapters  │
              │ (Binance, ByBit)   │
              └────────────────────┘
```

### Backend Components

**FastAPI Server** (`backend/api_server.py`):
- 14 REST endpoints across scanner, bot, risk, and market domains
- Automatic OpenAPI documentation at `/docs`
- CORS-enabled for cross-origin requests
- Integrated with PositionSizer, RiskManager, PaperExecutor

**Risk Management** (`backend/risk/`):
- **PositionSizer**: Kelly Criterion-based position sizing (15 tests, 84% coverage)
- **RiskManager**: Portfolio-level controls with loss limits (17 tests, 95% coverage)

**Trading Executor** (`backend/bot/executor/`):
- **PaperExecutor**: Realistic paper trading with slippage simulation (20 tests, 93% coverage)

**Market Scanner** (`backend/strategy/`):
- Smart-Money Concepts detection (Order Blocks, FVG, Liquidity Sweeps)
- Multi-timeframe confluence scoring
- Signal generation with entry/exit levels

### Frontend Components

**TypeScript API Client** (`src/utils/api.ts`):
- Type-safe wrapper for all backend endpoints
- Error handling and response validation
- Singleton pattern for easy imports

**React Pages**:
- `ScannerSetup.tsx` - Configure market scanning parameters
- `ScanResults.tsx` - View detected trading signals
- `BotSetup.tsx` - Configure automated trading bot
- `BotStatus.tsx` - Monitor active positions and performance

**Wallet Integration**:
- MetaMask and WalletConnect support
- Secure authentication flow
- Transaction signing

---

## 🔧 Development

### Project Structure

```
snipersight-trading/
├── backend/
│   ├── api_server.py          # FastAPI REST API
│   ├── risk/                  # Risk management
│   │   ├── position_sizer.py
│   │   └── risk_manager.py
│   ├── bot/executor/          # Trading execution
│   │   └── paper_executor.py
│   ├── strategy/              # SMC analysis
│   │   ├── smc/
│   │   └── confluence/
│   └── tests/                 # Backend tests
│       ├── test_api.py        # Integration tests
│       └── unit/
├── src/
│   ├── pages/                 # React pages
│   ├── components/            # Reusable UI components
│   ├── utils/api.ts           # API client
│   └── context/               # React context providers
├── docs/                      # Documentation
└── start.sh                   # Startup script
```

### Running Tests

**Backend Tests**:
```bash
# Unit tests with coverage
pytest backend/tests/unit/ --cov=backend --cov-report=term-missing

# Integration tests
python backend/test_api.py
```

**Frontend Tests**:
```bash
npm test
```

### API Development

Start the backend API server independently:
```bash
python -m backend.api_server
```

View API documentation: http://localhost:8000/docs

### Frontend Development

Start the frontend dev server independently:
```bash
npm run dev
```

The Vite proxy automatically routes `/api/*` requests to the backend on port 8000.

---

## 📊 API Endpoints

### Scanner

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/scanner/config` | Create scanner configuration |
| GET | `/api/scanner/config` | List scanner configurations |
| POST | `/api/scanner/{id}/start` | Start scanner |
| POST | `/api/scanner/{id}/stop` | Stop scanner |
| GET | `/api/scanner/signals` | Get detected signals |

### Bot

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/bot/config` | Create bot configuration |
| GET | `/api/bot/config` | List bot configurations |
| POST | `/api/bot/{id}/start` | Start trading bot |
| POST | `/api/bot/{id}/stop` | Stop trading bot |
| GET | `/api/bot/status` | Get bot status |
| GET | `/api/bot/positions` | Get active positions |
| POST | `/api/bot/order` | Place manual order |
| GET | `/api/bot/trades` | Get trade history |

### Risk

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/risk/summary` | Get portfolio risk summary |

### Market

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/market/price/{symbol}` | Get current price |
| GET | `/api/market/candles/{symbol}` | Get OHLCV candles |

---

## 🧪 Testing Strategy

### Integration Tests

`backend/test_api.py` validates end-to-end workflows:

1. **Health Check**: Verify all components are ready
2. **Scanner Workflow**: Config → Start → Signal retrieval
3. **Bot Workflow**: Config → Order → Position tracking
4. **Risk Management**: Portfolio summary retrieval

All 4 tests passing with actual API calls.

### Unit Tests

- **Position Sizer**: 15 tests, 84% coverage
- **Risk Manager**: 17 tests, 95% coverage
- **Paper Executor**: 20 tests, 93% coverage

---

## 🎨 UI Theme

SniperSight uses a custom dark theme optimized for trading interfaces:

- **Primary Color**: `#10B981` (Emerald) for bullish signals
- **Accent Color**: `#EF4444` (Red) for bearish signals
- **Background**: Dark mode with high contrast for readability
- **Chart Integration**: TradingView Lightweight Charts

See [docs/sniper_ui_theme.md](docs/sniper_ui_theme.md) for complete design specifications.

---

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

The implementation follows a modular architecture with clear separation of concerns:

```
snipersight/
├── backend/
│   ├── api_server.py       # FastAPI REST API
│   ├── contracts/          # API boundary definitions
│   ├── shared/             # Cross-cutting models, configs, utilities
│   ├── data/               # Multi-exchange data ingestion and caching
│   ├── indicators/         # Technical analysis computation
│   ├── strategy/           # SMC detection, confluence scoring, planning
│   │   ├── smc/           # Order blocks, FVGs, BOS/CHoCH, liquidity sweeps
│   │   ├── confluence/    # Scoring, regime detection, plugins
│   │   └── planner/       # Entry zones, stops, targets, R:R
│   ├── risk/              # Position sizing, exposure control, compliance
│   ├── bot/               # Notifications, execution, charts, telemetry
│   ├── engine/            # Pipeline orchestration, context, hooks, plugins
│   ├── ml/                # ML integration hooks (future)
│   └── tests/             # Fixtures, unit, integration, backtest
├── src/                   # Frontend React application
│   ├── pages/            # Main application pages
│   ├── components/       # Reusable UI components
│   ├── utils/            # Frontend utilities and API client
│   └── context/          # React context providers
├── docs/                  # Documentation
├── scripts/              # Operational scripts
└── examples/             # Usage demonstrations
```

---

## 🛣️ Implementation Roadmap

SniperSight is being implemented in **Python** (backend) and **TypeScript/React** (frontend) following these phases:

### ✅ Phase 1: Foundation
- Core data models
- Configuration management
- Logging infrastructure

### ✅ Phase 2: Data Layer
- Exchange adapters (Binance, ByBit)
- Market data ingestion
- OHLCV caching

### ✅ Phase 3: Analysis Layer
- Technical indicators
- SMC detection (Order Blocks, FVG, Liquidity Sweeps)
- Multi-timeframe confluence
- Hybrid validation framework

### ✅ Phase 4: Risk Management & Bot Layer
- **Position Sizer** - Kelly Criterion-based sizing (15 tests, 84% coverage)
- **Risk Manager** - Portfolio controls with loss limits (17 tests, 95% coverage)
- **Paper Executor** - Realistic simulation with slippage (20 tests, 93% coverage)
- ✅ **Backend-Frontend Integration** - FastAPI REST API with TypeScript client

### 🔄 Phase 5: Orchestration (In Progress)
- Live trading executor (Binance integration)
- Telegram notifications
- Telemetry and analytics

### 📋 Phase 6: Testing & Optimization
- Backtesting framework
- Performance optimization
- Production deployment

---

## 🚀 Getting Started

### Prerequisites Check

```bash
# Verify Python version
python --version  # Should be 3.12+

# Verify Node.js version
node --version   # Should be 18+
```

### Installation Steps

1. **Clone the repository**:
```bash
git clone https://github.com/NobleWolf412/snipersight-trading.git
cd snipersight-trading
```

2. **Install backend dependencies**:
```bash
pip install -r requirements.txt
```

3. **Install frontend dependencies**:
```bash
npm install
```

4. **Start the application**:
```bash
./start.sh
```

The startup script will:
- Create/activate a Python virtual environment
- Start the FastAPI backend on port 8000
- Start the React frontend on port 5173
- Perform a health check
- Display access URLs

### Access Points

After starting, you can access:

- **Frontend Application**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **API Alternative Docs**: http://localhost:8000/redoc (ReDoc)

---

## 📖 Learning Path

### For New Users

1. **Start with the PRD**: Read [PRD.md](PRD.md) to understand the product vision and features
2. **Review Architecture**: Study [ARCHITECTURE.md](ARCHITECTURE.md) for system design
3. **Explore the UI**: Launch the application and explore the scanner and bot interfaces
4. **Read Integration Guide**: Check [docs/INTEGRATION_GUIDE.md](docs/INTEGRATION_GUIDE.md) for API details

### For Developers

1. **Understand Project Structure**: Review [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
2. **Set Up Development Environment**: Follow the installation steps above
3. **Run Tests**: Execute backend and frontend test suites
4. **Explore API**: Use the Swagger UI at http://localhost:8000/docs
5. **Check Implementation Roadmap**: See [COPILOT_BUILD_GUIDE.md](COPILOT_BUILD_GUIDE.md)

---

## 💡 Usage Examples

### Starting a Market Scanner

```bash
# Using the UI
# 1. Navigate to http://localhost:5173
# 2. Go to Scanner Setup page
# 3. Configure symbols, timeframes, and SMC parameters
# 4. Click "Start Scanner"
# 5. View signals on Scan Results page

# Using the API directly
curl -X POST http://localhost:8000/api/scanner/config \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["BTC/USDT", "ETH/USDT"],
    "timeframes": ["1h", "4h"],
    "exchange": "binance"
  }'

# Start the scanner
curl -X POST http://localhost:8000/api/scanner/scanner_1/start

# Get signals
curl http://localhost:8000/api/scanner/signals
```

### Configuring a Trading Bot

```bash
# Create bot configuration
curl -X POST http://localhost:8000/api/bot/config \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDT",
    "exchange": "binance",
    "initial_capital": 10000,
    "risk_per_trade": 0.02,
    "max_positions": 3
  }'

# Start the bot
curl -X POST http://localhost:8000/api/bot/bot_1/start

# Check bot status
curl http://localhost:8000/api/bot/status
```

### Placing Manual Orders

```bash
curl -X POST http://localhost:8000/api/bot/order \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDT",
    "side": "buy",
    "order_type": "limit",
    "price": 50000,
    "stop_loss": 49000,
    "take_profit": 52000
  }'
```

---

## 🔒 Security

### API Key Management

Exchange API keys should be stored in environment variables:

```bash
export BINANCE_API_KEY="your_api_key"
export BINANCE_API_SECRET="your_api_secret"
export BYBIT_API_KEY="your_api_key"
export BYBIT_API_SECRET="your_api_secret"
```

See [SECURITY.md](SECURITY.md) for complete security guidelines.

### Wallet Authentication

The frontend supports MetaMask and WalletConnect for secure wallet authentication. See [docs/WALLET_AUTHENTICATION.md](docs/WALLET_AUTHENTICATION.md) for setup instructions.

---

## 🤝 Contributing

SniperSight is currently in active development. Contributions are welcome!

### Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest backend/tests/` and `npm test`)
5. Commit with clear messages (`git commit -m 'Add amazing feature'`)
6. Push to your branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Code Standards

- **Python**: Follow PEP 8, use type hints, maintain >80% test coverage
- **TypeScript**: Use strict mode, follow ESLint rules, maintain type safety
- **Testing**: All new features require unit and integration tests
- **Documentation**: Update relevant docs for any API or architecture changes

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Smart Money Concepts**: Trading methodology based on institutional order flow analysis
- **TradingView**: Chart integration and visualization
- **FastAPI**: Modern Python web framework
- **React**: Frontend framework for building the UI

---

## 📞 Support

For questions, issues, or feature requests:

- **Issues**: [GitHub Issues](https://github.com/NobleWolf412/snipersight-trading/issues)
- **Documentation**: Check [docs/](docs/) folder for detailed guides
- **API Reference**: http://localhost:8000/docs when server is running

---

## 🗺️ Roadmap

### Current (Q1 2025)
- ✅ Backend-Frontend Integration
- ✅ Paper Trading Executor
- ✅ Risk Management System
- 🔄 Live Trading Executor (Binance)

### Near Term (Q2 2025)
- Telegram Notifications
- Advanced Analytics Dashboard
- Backtesting Framework
- Multi-Exchange Support Enhancement

### Future
- Machine Learning Signal Scoring
- Portfolio Optimization
- Social Trading Features
- Mobile Application

---

**Built with ❤️ for serious crypto traders**
