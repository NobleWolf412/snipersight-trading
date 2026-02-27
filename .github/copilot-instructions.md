# SniperSight AI Agent Instructions

## Project Architecture

**Dual-Stack Trading Platform**: Python backend (FastAPI) + React/TypeScript frontend (Vite/Spark).

**Backend** (`/backend/`): Institutional-grade crypto scanner using Smart-Money Concepts (SMC). Core pipeline: data ingestion → indicators → SMC detection (order blocks, FVGs, BOS/CHoCH, liquidity sweeps) → confluence scoring → trade planning → risk validation → signal generation.

**Frontend** (`/src/`): GitHub Spark-based UI with React 19, Tailwind v4, shadcn/ui components. Uses React Context (`ScannerContext`, `WalletContext`) + localStorage for state management via custom `useLocalStorage` hook. Spark provides LLM integration via `window.spark.llm()` for AI-powered chart analysis.

## Key Architectural Patterns

### Backend Pipeline (Orchestrator)
`backend/engine/orchestrator.py` coordinates the full analysis pipeline. Each scan processes symbols through:
`backend/engine/orchestrator.py` coordinates the full analysis pipeline. Each scan processes symbols through:
1. **Global Regime Detection** - BTC-based market regime classification
2. **Bulk Data Fetch** - Single parallel_fetch() for all symbols × all timeframes (no duplicates)
3. **MacroContext Computation** - Combines DominanceService (BTC.D/Alt.D/Stable.D from CryptoCompare) with 1h velocity metrics from pre-fetched data
4. **Per-Symbol Processing** (parallel, using pre-fetched data):
   - Indicator computation (RSI, ATR, volume spikes, Bollinger Bands)
   - SMC detection (order blocks, FVGs, BOS/CHoCH, liquidity sweeps)
   - Confluence scoring weighted by HTF alignment, BTC impulse gate, market regime
   - Trade planning with entry zones, structure-based stops, tiered targets
   - Risk validation via `RiskManager` (exposure limits, correlation matrix)

**Key Optimization**: Data is fetched ONCE via bulk fetch, then passed to both MacroContext computation and per-symbol processing. No duplicate API calls.

Never bypass quality gates—signals must pass all validation layers (data quality, SMC freshness, confluence thresholds, plan completeness).

### Frontend State Architecture
- **Providers wrap app in order**: `BrowserRouter` → `WalletProvider` → `ScannerProvider` → `ErrorBoundary`
- **Context hooks**: `useScanner()` for scan/bot config, `useWallet()` for Web3 auth
- **State persistence**: `useLocalStorage<T>(key, default)` custom hook (in `src/hooks/useLocalStorage.ts`) backed by localStorage—survives page reloads
- **Scan results flow**: `ScannerSetup` saves to localStorage → `ScanResults` reads on mount → uses local state (`useState`) for display
- **Routing convention**: Setup pages (`/scanner/setup`, `/bot/setup`) configure parameters; Status pages (`/scanner/status`, `/bot/status`) display real-time telemetry; Results page (`/results`) shows generated signals
- **Spark Integration**: `@github/spark/spark` imported in `main.tsx` provides `window.spark.llm()` for LLM features (chart analysis, trade commentary generation)

### API Integration Layer
`src/utils/api.ts` provides typed client wrapping backend endpoints:
- Scanner: `getSignals()`, `getScannerModes()` (deprecated - modes now static in frontend), `startScanner()`, `stopScanner()`
- Bot: `getBotStatus()`, `getPositions()`, `placeOrder()`
- Risk: `getRiskSummary()`
- Market: `getPrice()`, `getCandles()`, `getMarketRegime()`
- Telemetry: `getRecentTelemetry()`, `getTelemetryEvents()`, `getTelemetryAnalytics()`

Always check `response.error` before accessing `response.data`—fallback to mock data generators (`src/utils/mockData.ts`) when backend unavailable.

## Critical Workflows

### Running the Full Stack
```bash
# Backend (FastAPI server on :8001)
cd /workspaces/snipersight-trading
python -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8001 --reload

# Frontend (Vite dev server on :5000)
npm run dev:frontend

# Or use the combined startup script (recommended)
./scripts/start_dev.sh

# Production build
npm run build

# Kill ports if needed
npm run kill
```

### Testing Backend Components
```bash
# Run all tests with coverage
pytest backend/tests -v --cov=backend

# Test specific module
pytest backend/tests/test_orchestrator.py -v

# Integration tests require mock exchange data
pytest backend/tests/integration/ -v
```

### Backend Configuration System
Configuration lives in `backend/shared/config/`:
- **Scanner modes** (`scanner_modes.py`): predefined profiles (overwatch, strike, surgical, stealth) with timeframes, min confluence, risk-reward targets. Note: `recon` and `ghost` were merged into `stealth` mode.
- **Defaults** (`defaults.py`): global thresholds (ATR multipliers, RSI levels, volume spike thresholds)
- **SMC config** (`smc_config.py`): displacement requirements, freshness scoring, structural break detection params

Always load mode via `get_mode('stealth')` rather than hardcoding—modes are backend-driven. Frontend has STATIC mode definitions in `ScannerContext.tsx` (const `SCANNER_MODES`) for UI display only—these should mirror backend definitions but are not fetched from API.

## Project-Specific Conventions

### Smart-Money Concepts Terminology
- **Order Block (OB)**: Last opposing candle before strong move (bullish OB = last red before green surge)
- **Fair Value Gap (FVG)**: Price gap indicating liquidity imbalance (middle of 3-candle pattern)
- **BOS (Break of Structure)**: Higher high (bullish) or lower low (bearish) confirming trend continuation
- **CHoCH (Change of Character)**: Counter-trend structure break signaling potential reversal
- **Displacement**: Strong directional move (≥1.5 ATR threshold) showing institutional conviction
- **Liquidity Sweep**: Wick beyond recent high/low followed by rejection (stop hunt)

### Quality Gate Philosophy
**No half-formed signals**—system fails loudly rather than producing incomplete data:
- Missing indicators → hard error (`ValueError` in backend, build failure in frontend)
- Null rationale → signal rejected, telemetry event logged
- Invalid R:R → trade plan discarded at planner stage
- Incomplete SMC snapshot → confluence scoring aborts

Check `backend/strategy/planner/planner_service.py` `generate_trade_plan()` for stop-loss validation—no ATR-only fallbacks; structural stops required.

### Frontend Component Patterns
**Page layouts use composition**:
```tsx
<PageLayout maxWidth="lg">
  <PageHeader title="..." description="..." icon={<Icon />} actions={<Button />} />
  <PageSection title="CONTEXT">
    <MarketRegimeLens {...regimeProps} />
  </PageSection>
  <Card>...</Card>
</PageLayout>
```

**State mutations via context setters** (never direct localStorage writes):
```tsx
const { scanConfig, setScanConfig } = useScanner();
setScanConfig({ ...scanConfig, leverage: 10 });
```

**Scan results persistence** (manual localStorage operations in page components):
```tsx
// In ScannerSetup.tsx - after successful scan
localStorage.setItem('scan-results', JSON.stringify(results));
localStorage.setItem('scan-metadata', JSON.stringify(metadata));
localStorage.setItem('scan-rejections', JSON.stringify(rejections));

// In ScanResults.tsx - on mount
const resultsStr = localStorage.getItem('scan-results');
const results = resultsStr ? JSON.parse(resultsStr) : [];
setScanResults(results); // Local state for display
```

**Telemetry integration**: `ActivityFeed` polls `telemetryService.getRecentEvents()` every 3-4s for real-time updates.

### Naming Conventions
- **Backend modules**: snake_case files, PascalCase classes (`OrderBlockDetector`)
- **Frontend components**: PascalCase files/exports (`ScannerSetup.tsx` → `export function ScannerSetup()`)
- **API endpoints**: REST-style (`/scanner/signals`, `/bot/status`, `/risk/summary`)
- **Route paths**: kebab-case segments (`/scanner/setup`, `/bot/status`)

## Integration Points

### Backend → Frontend Signal Flow
1. Backend `Orchestrator.scan()` returns `List[TradePlan]`
2. API endpoint `/scanner/signals` serializes to `SignalsResponse` with metadata
3. Frontend `api.getSignals()` fetches, `convertSignalToScanResult()` transforms to `ScanResult[]`
4. Store in localStorage: `localStorage.setItem('scan-results', JSON.stringify(results))`
5. Navigate to `/results`, `ScanResults` page reads from localStorage via `useEffect` on mount

### Telemetry Event Pipeline
Backend logs events via `get_telemetry_logger()`:
```python
telemetry.log_event(create_signal_generated_event(
    symbol="BTC/USDT", direction="LONG", confidence_score=87.5, ...
))
```
Frontend polls `/api/telemetry/recent` → `ActivityFeed` displays with icons/colors per event type (`scan_started`, `signal_generated`, `signal_rejected`, `error_occurred`).

### Market Regime Integration
`MarketRegimeLens` component displays:
- Regime label (ALTSEASON, BTC_DRIVE, DEFENSIVE, PANIC, CHOPPY)
- Visibility % (target acquisition clarity)
- Dominance metrics (BTC.D, USDT.D, ALT.D) with trend arrows
- Guidance lines (regime-specific trading advice)

Backend endpoint `/api/market/regime` implemented—returns regime detection from BTC/USDT analysis.

## Critical Files Reference

**Backend Core**:
- `backend/engine/orchestrator.py`: Main pipeline coordinator with `apply_mode()` method for mode switching
- `backend/analysis/dominance_service.py`: CryptoCompare API for BTC.D/Alt.D/Stable.D with 24h file cache
- `backend/analysis/macro_context.py`: MacroContext dataclass combining dominance + velocity metrics
- `backend/strategy/smc/`: SMC detection modules (order_blocks, fvg, bos_choch, liquidity_sweeps)
- `backend/strategy/confluence/scorer.py`: Multi-factor confluence calculation
- `backend/strategy/planner/planner_service.py`: Trade plan generation with structure-based stops
- `backend/risk/risk_manager.py`: Exposure limits + correlation matrix
- `backend/api_server.py`: FastAPI endpoints (defaults to Phemex adapter, configurable per-scan)

**Frontend Core**:
- `src/App.tsx`: Route definitions (9 routes including Training Ground, Market Overview)
- `src/main.tsx`: Provider hierarchy (Router → Wallet → Scanner → ErrorBoundary)
- `src/context/ScannerContext.tsx`: Scan/bot config state management with STATIC mode definitions
- `src/context/WalletContext.tsx`: Web3 wallet authentication (MetaMask, WalletConnect, Coinbase)
- `src/hooks/useLocalStorage.ts`: Custom hook mimicking Spark's useKV API, backed by localStorage
- `src/pages/ScannerSetup.tsx`: Configuration UI with leverage/mode selection, saves results to localStorage
- `src/pages/ScanResults.tsx`: Signal display reading from localStorage, chart/details modals
- `src/components/SniperModeSelector.tsx`: Dynamic mode selector displaying static frontend modes
- `src/components/ChartModal/`: Interactive D3.js chart with AI analysis via `window.spark.llm()`
- `src/utils/api.ts`: Typed API client

**Config & Contracts**:
- `backend/shared/config/scanner_modes.py`: Predefined trading profiles (4 modes: overwatch, strike, surgical, stealth)
- `backend/shared/models/`: Dataclass definitions (data, indicators, smc, scoring, planner)
- `backend/contracts/`: API boundary contracts (prevent signature drift)

## Advanced Features

### Exchange Adapters (Tier 1 Only)
`backend/data/adapters/` contains production-ready exchange integrations:
- **PhemexAdapter** (default): No geo-blocking, fast, works with US IPs
- **BybitAdapter**: Best overall but may be geo-blocked in some regions
- **OKXAdapter**: Institutional-tier exchange
- **BitgetAdapter**: Bot-friendly features
- **BinanceAdapter**: Deprecated - geo-restricted in many regions

All adapters implement retry logic, rate limiting, and CCXT integration. Orchestrator takes `exchange_adapter` parameter—API server provides factory in `EXCHANGE_ADAPTERS` dict.

### Scanner Modes (Backend Truth)
Backend `scanner_modes.py` defines 4 tactical modes with critical timeframe requirements:
- **overwatch**: 6 TFs (1w→5m), 75% min score, macro surveillance
- **strike**: 4 TFs (4h→5m), 60% min score, intraday aggressive
- **surgical**: 3 TFs (1h→5m), 70% min score, precision scalping
- **stealth**: 5 TFs (1d→5m), 65% min score, balanced swing trading (merged from recon+ghost; use `stealth_strict=True` override for higher conviction)

Each mode specifies `critical_timeframes` tuple—symbols missing these are rejected with telemetry event.

### ML Integration (Future)
`backend/ml/` directory reserved for machine learning enhancements:
- **Confluence scoring plugins**: ML models can override or augment rule-based scoring
- **Pattern recognition**: Train models on historical SMC patterns for quality prediction
- **Entry optimization**: ML-driven entry zone refinement based on backtest results
- **Risk prediction**: Dynamic stop-loss placement using learned volatility patterns

Integration points in `backend/strategy/confluence/scorer.py` via plugin hooks—current implementation uses rule-based multi-factor analysis.

### Correlation Matrix & Risk Controls
`RiskManager` (`backend/risk/risk_manager.py`) maintains dynamic correlation matrix:
- **Pearson correlation** computed between active positions using price returns
- **Correlation threshold** (default 0.7): pairs above this share correlation exposure limits
- **Correlated exposure cap** (default 40% of account): prevents over-concentration in correlated assets
- **Matrix update frequency**: refreshed periodically as positions evolve

Example: If BTC/USDT and ETH/USDT correlation = 0.85, opening both positions counts toward correlated exposure limit, capping combined risk even if individual asset limits aren't hit.

Check `_get_correlated_exposure()` for correlation-aware exposure calculations—falls back to static groups (BTC/ETH/BNB, SOL/AVAX/MATIC) when matrix unavailable.

### Wallet Authentication (Web3)
`WalletContext` (`src/context/WalletContext.tsx`) provides decentralized authentication:
- **MetaMask**: Full integration with account/chain change listeners
- **WalletConnect**: Coming soon (placeholder implemented)
- **Coinbase Wallet**: Coming soon (placeholder implemented)
- **Session persistence**: Stored in localStorage via `useLocalStorage` hook
- **Network monitoring**: Automatically detects chain changes, account switches, disconnects

Used by `WalletConnect` component and `WalletGate` wrapper for protected features.

## Common Pitfalls

1. **Never use `<a href>` in frontend**—always `<Link to>` from `react-router-dom` for SPA navigation
2. **Backend signals must have complete rationale**—check `planner_service.py` generates full trade context
3. **Don't bypass Orchestrator**—direct SMC detection skips quality gates and telemetry
4. **Frontend imports from `@/`**—path alias configured in `tsconfig.json`, not relative imports
5. **Scan results use direct localStorage operations** in page components, not context persistence
6. **Spark components require `@github/spark/spark` import in main.tsx**—already present, don't remove
7. **Duplicate implementations**—always check existing files before creating new ones; prefer extending existing components over creating redundant variants
8. **Static frontend modes**—`ScannerContext.tsx` defines SCANNER_MODES const for UI display; backend modes in `scanner_modes.py` are source of truth for pipeline behavior
9. **Exchange adapter required**—Orchestrator constructor requires explicit adapter (Phemex, Bybit, OKX, or Bitget); no default fallback

## UI/UX Standards

**Modern React Patterns**: Use functional components, hooks, and composition over inheritance. Prefer `PageLayout` + `PageHeader` + `PageSection` composition for consistent page structure.

**Aesthetic Guidelines**:
- Tailwind v4 with utility-first approach—no inline styles
- Dark theme optimized with `bg-background`, `text-foreground`, tactical grid overlays
- shadcn/ui components for consistency—never mix competing UI libraries
- Phosphor Icons for all iconography (already imported, `@phosphor-icons/react`)
- Accent colors: `text-accent` (scanner), `text-primary` (bot), `text-warning` (alerts)
- Animations: `scan-pulse` for live indicators, `transition-all duration-300` for hover states
- Typography: Tabular nums for metrics (`font-mono`), tracking-wider for headers

**Component Reuse**: Check `src/components/` before creating—existing:
- **Layout**: `PageLayout`, `PageHeader`, `PageSection`, `HomeButton`, `TopBar`
- **Data Display**: `LiveTicker`, `PriceDisplay`, `PriceCard`, `ConvictionBadge`, `RegimeIndicator`, `RejectionSummary`
- **Interactive**: `SniperModeSelector`, `ChartModal`, `DetailsModal`, `WalletConnect`, `NotificationStatus`, `SessionIndicator`
- **Telemetry**: `ActivityFeed`, `TelemetryAnalytics` (in telemetry/ subdirectory)
- **Market**: `MarketRegimeLens`, `DominanceMetrics` (in market/ subdirectory)

## When Modifying

**Adding new scanner mode**: Update `backend/shared/config/scanner_modes.py` `MODES` dict → backend restart → optionally update frontend `SCANNER_MODES` in `ScannerContext.tsx` for UI consistency.

**New backend endpoint**: Add route in `api_server.py` → update `src/utils/api.ts` client → call via `api.newMethod()` in components.

**New SMC pattern**: Create detector in `backend/strategy/smc/` → wire into `Orchestrator._detect_smc()` → add to `SMCSnapshot` dataclass → update confluence scorer weights.

**UI page addition**: Create in `src/pages/` → register route in `App.tsx` → add navigation links in relevant pages.

**localStorage schema change**: Update both save (in `ScannerSetup.tsx`) and load (in `ScanResults.tsx`) logic—no automatic migration, users lose old data on schema mismatch.

**Exchange adapter addition**: Create in `backend/data/adapters/` following CCXT pattern → add to `EXCHANGE_ADAPTERS` dict in `api_server.py` → expose in API query params.
