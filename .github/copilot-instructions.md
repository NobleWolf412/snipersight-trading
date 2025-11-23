# SniperSight AI Agent Instructions

## Project Architecture

**Dual-Stack Trading Platform**: Python backend (FastAPI) + React/TypeScript frontend (Vite/Spark).

**Backend** (`/backend/`): Institutional-grade crypto scanner using Smart-Money Concepts (SMC). Core pipeline: data ingestion → indicators → SMC detection (order blocks, FVGs, BOS/CHoCH, liquidity sweeps) → confluence scoring → trade planning → risk validation → signal generation.

**Frontend** (`/src/`): GitHub Spark-based UI with React 19, Tailwind v4, shadcn/ui components. Uses `@github/spark` for state management via `useKV` hook (persistent key-value storage).

## Key Architectural Patterns

### Backend Pipeline (Orchestrator)
`backend/engine/orchestrator.py` coordinates the full analysis pipeline. Each scan processes symbols through:
1. **MultiTimeframeData** ingestion (6 TFs: 1W/1D/4H/1H/15m/5m)
2. **Indicator computation** (RSI, ATR, volume spikes, Bollinger Bands)
3. **SMC detection** (order blocks in `strategy/smc/order_blocks.py`, FVGs, structural breaks)
4. **Confluence scoring** weighted by HTF alignment, BTC impulse gate, market regime
5. **Trade planning** with entry zones, structure-based stops, tiered targets
6. **Risk validation** via `RiskManager` (exposure limits, correlation matrix)

Never bypass quality gates—signals must pass all validation layers (data quality, SMC freshness, confluence thresholds, plan completeness).

### Frontend State Architecture
- **Providers wrap app in order**: `BrowserRouter` → `WalletProvider` → `ScannerProvider` → `ErrorBoundary`
- **Context hooks**: `useScanner()` for scan/bot config, `useWallet()` for Web3 auth, `useTelemetry()` for system metrics
- **Page state persistence**: `useKV<T>('key', default)` for scan results, metadata, config—survives navigation
- **Routing convention**: Setup pages (`/scanner/setup`, `/bot/setup`) configure parameters; Status pages (`/scanner/status`, `/bot/status`) display real-time telemetry; Results page (`/results`) shows generated signals

### API Integration Layer
`src/utils/api.ts` provides typed client wrapping backend endpoints:
- Scanner: `getSignals()`, `getScannerModes()`, `startScanner()`, `stopScanner()`
- Bot: `getBotStatus()`, `getPositions()`, `placeOrder()`
- Risk: `getRiskSummary()`
- Market: `getPrice()`, `getCandles()`

Always check `response.error` before accessing `response.data`—fallback to mock data generators (`src/utils/mockData.ts`) when backend unavailable.

## Critical Workflows

### Running the Full Stack
```bash
# Backend (FastAPI server on :5000)
cd /workspaces/snipersight-trading
python -m uvicorn backend.api_server:app --host 0.0.0.0 --port 5000 --reload

# Frontend (Vite dev server on :5173)
npm run dev

# Production build
npm run build
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
- **Scanner modes** (`scanner_modes.py`): predefined profiles (overwatch, recon, strike, rapid-fire) with timeframes, min confluence, risk-reward targets
- **Defaults** (`defaults.py`): global thresholds (ATR multipliers, RSI levels, volume spike thresholds)
- **SMC config** (`smc_config.py`): displacement requirements, freshness scoring, structural break detection params

Always load mode via `get_mode('recon')` rather than hardcoding—modes are backend-driven.

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

**State mutations via context setters** (never direct KV writes):
```tsx
const { scanConfig, setScanConfig } = useScanner();
setScanConfig({ ...scanConfig, leverage: 10 });
```

**Telemetry integration**: `ActivityFeed` polls `telemetryService.getRecentEvents()` every 3-4s; `useTelemetry()` provides system metrics (latency, activeTargets, signalsRejected).

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
4. Store in KV: `setScanResults(results)`, `setScanMetadata({ mode, timeframes, ... })`
5. Navigate to `/results`, `ScanResults` page reads from KV

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

Currently uses mock hook `useMockMarketRegime('scanner')`—backend endpoint `/market/regime` pending.

## Critical Files Reference

**Backend Core**:
- `backend/engine/orchestrator.py`: Main pipeline coordinator
- `backend/strategy/smc/`: SMC detection modules (order_blocks, fvg, bos_choch, liquidity_sweeps)
- `backend/strategy/confluence/scorer.py`: Multi-factor confluence calculation
- `backend/strategy/planner/planner_service.py`: Trade plan generation with structure-based stops
- `backend/risk/risk_manager.py`: Exposure limits + correlation matrix
- `backend/api_server.py`: FastAPI endpoints

**Frontend Core**:
- `src/App.tsx`: Route definitions
- `src/main.tsx`: Provider hierarchy (Router → Wallet → Scanner → ErrorBoundary)
- `src/context/ScannerContext.tsx`: Scan/bot config state management
- `src/pages/ScannerSetup.tsx`: Configuration UI with leverage/mode selection
- `src/pages/ScanResults.tsx`: Signal display with chart/details modals
- `src/components/SniperModeSelector.tsx`: Dynamic mode selector (fetches from backend)
- `src/utils/api.ts`: Typed API client

**Config & Contracts**:
- `backend/shared/config/scanner_modes.py`: Predefined trading profiles
- `backend/shared/models/`: Dataclass definitions (data, indicators, smc, scoring, planner)
- `backend/contracts/`: API boundary contracts (prevent signature drift)

## Advanced Features

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

### Missing Backend Implementations
**Market Regime Endpoint**: Frontend `MarketRegimeLens` currently uses `useMockMarketRegime()` hook. Backend implementation pending:
- Target endpoint: `GET /api/market/regime`
- Required fields: `regime_label`, `visibility`, `btc_dominance`, `usdt_dominance`, `alt_dominance`, `guidance_lines`
- Integration point: Add to `backend/api_server.py`, wire into confluence scorer as regime filter

**Risk Summary Endpoint**: `GET /api/risk/summary` defined in API client but not yet consumed in UI—ready for integration into Status pages.

**Positions Panel**: `api.getPositions()` exists but no dedicated UI component yet—candidate for Bot Status page enhancement.

## Common Pitfalls

1. **Never use `<a href>` in frontend**—always `<Link to>` from `react-router-dom` for SPA navigation
2. **Backend signals must have complete rationale**—check `planner_service.py` generates full trade context
3. **Don't bypass Orchestrator**—direct SMC detection skips quality gates and telemetry
4. **Frontend imports from `@/`**—path alias configured in `tsconfig.json`, not relative imports
5. **KV state is page-specific**—`scan-results` key shared across setup/status/results pages
6. **Spark components require `@github/spark/spark` import in main.tsx**—already present, don't remove
7. **Duplicate implementations**—always check existing files before creating new ones; prefer extending existing components over creating redundant variants

## UI/UX Standards

**Modern React Patterns**: Use functional components, hooks, and composition over inheritance. Prefer `PageLayout` + `PageHeader` + `PageSection` composition for consistent page structure.

**Aesthetic Guidelines**:
- Tailwind v4 with utility-first approach—no inline styles
- Dark theme optimized with `bg-background`, `text-foreground`, tactical grid overlays
- shadcn/ui components for consistency—never mix competing UI libraries
- Phosphor Icons for all iconography (already imported)
- Accent colors: `text-accent` (scanner), `text-primary` (bot), `text-warning` (alerts)
- Animations: `scan-pulse` for live indicators, `transition-all duration-300` for hover states
- Typography: Tabular nums for metrics (`font-mono`), tracking-wider for headers

**Component Reuse**: Check `src/components/` before creating—existing: `MarketRegimeLens`, `ActivityFeed`, `SniperModeSelector`, `LiveTicker`, `PriceDisplay`, `SystemStatus`, `WalletConnect`, `SessionIndicator`, `NotificationStatus`.

## When Modifying

**Adding new scanner mode**: Update `backend/shared/config/scanner_modes.py` `SCANNER_MODES` dict → backend restart → frontend `SniperModeSelector` auto-fetches.

**New backend endpoint**: Add route in `api_server.py` → update `src/utils/api.ts` client → call via `api.newMethod()` in components.

**New SMC pattern**: Create detector in `backend/strategy/smc/` → wire into `Orchestrator._detect_smc()` → add to `SMCSnapshot` dataclass → update confluence scorer weights.

**UI page addition**: Create in `src/pages/` → register route in `App.tsx` → add navigation links in relevant pages.
