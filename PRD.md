# SniperSight – Institutional-Grade Crypto Market Scanner

A modular, institution-grade crypto market scanner designed to evolve into a fully automated trading bot, leveraging Smart-Money Concepts across multi-timeframe analysis.

**Experience Qualities**:
1. **Precise** - Institutional tradecraft with zero ambiguity; every signal is complete, actionable, and deterministically verifiable
2. **Disciplined** - Multi-layered gating ensures only high-conviction setups pass through rigorous quality checks and alignment filters
3. **Transparent** - Full telemetry, audit trails, and human-readable rationale expose every decision point from data ingestion to notification

**Complexity Level**: Complex Application (advanced functionality, accounts)
- Multi-exchange data ingestion, sophisticated multi-timeframe Smart-Money analysis, ML-ready architecture, bot execution layer, comprehensive verification pipeline, and modular plugin system requiring institutional-grade architecture

## Essential Features

### Multi-Timeframe Market Scanning
- **Functionality**: Ingests and analyzes OHLCV data across 1W, 1D, 4H, 1H, 15m, 5m timeframes from multiple exchanges
- **Purpose**: Captures institutional Smart-Money footprints across all relevant timeframes for complete market context
- **Trigger**: CLI command, scheduled scan, or API invocation
- **Progression**: Symbol selection → Multi-TF data fetch → Cache check → Parallel ingestion → DataFrame conversion → Context creation
- **Success criteria**: Complete multi-TF datasets loaded within 30s for top-20 symbols with deterministic caching

### Smart-Money Concept Detection
- **Functionality**: Detects order blocks, fair value gaps (FVGs), change of character (CHoCH), break of structure (BOS), liquidity sweeps, and displacement patterns
- **Purpose**: Identifies institutional entry/exit zones where Smart Money operates
- **Trigger**: After indicator computation on multi-TF data
- **Progression**: Structure analysis → OB detection → FVG identification → BOS/CHoCH marking → Liquidity sweep validation → Freshness filtering
- **Success criteria**: 100% detection accuracy on deterministic fixtures, zero false positives on displacement checks

### Confluence Scoring Engine
- **Functionality**: Aggregates structure, momentum, volatility, volume, and regime signals into unified confluence breakdown with synergy bonuses and conflict penalties
- **Purpose**: Ranks setups by institutional quality and multi-factor alignment
- **Trigger**: After SMC detection completes
- **Progression**: Regime detection → HTF alignment check → BTC impulse gate → Multi-factor aggregation → Conflict penalty → Synergy bonus → Final score
- **Success criteria**: Produces deterministic scores (±0.01) for identical inputs, penalizes conflicting signals, rewards aligned confluence

### Complete Trade Planning
- **Functionality**: Generates full trade plans with dual entries (near/far), structure-based stops, tiered targets, R:R ratios, risk scores, and populated rationale
- **Purpose**: Provides operators with no-null, immediately actionable trade specifications
- **Trigger**: After confluence scoring passes quality gates
- **Progression**: Entry zone calculation → Stop placement → Target ladder generation → R:R validation → Style classification → Rationale synthesis
- **Success criteria**: Zero null fields, all entries/stops/targets populated, R:R > 2.0, human-readable rationale with specific price levels

### Interactive Chart Analysis & Visualization
- **Functionality**: Provides TradingView-style interactive candlestick charts with D3.js, overlaying entry zones, stop losses, take profits, order blocks, and fair value gaps with toggleable visibility controls and multi-timeframe switching
- **Purpose**: Enables visual confirmation of technical setups, pattern recognition, and level validation for high-conviction trade decisions
- **Trigger**: User clicks "View Chart" on any scan result
- **Progression**: Chart data generation → Candlestick rendering → Level overlay → Interactive controls → Multi-tab analysis (Chart/AI/Stats/Levels)
- **Success criteria**: Smooth rendering of 30-96 candles, accurate price level visualization, responsive toggles, AI analysis generation within 3s, comprehensive trading statistics display

### Crypto Wallet Authentication
- **Functionality**: Web3 wallet integration (MetaMask, WalletConnect, Coinbase Wallet) for secure, non-custodial user authentication without traditional credentials
- **Purpose**: Provides secure, decentralized authentication using public wallet addresses while maintaining complete user sovereignty over private keys
- **Trigger**: User clicks "Connect Wallet" in navigation or attempts to access wallet-gated features
- **Progression**: Provider selection → Wallet connection request → Address retrieval → Session persistence → Network monitoring → Authenticated state
- **Success criteria**: Successful connection with MetaMask, persistent session across reloads using KV storage, automatic network change detection, secure read-only address access, zero private key exposure, graceful disconnection handling

### AI-Powered Trade Analysis
- **Functionality**: Generates comprehensive markdown-formatted technical analysis reports using LLM, covering market structure, key levels, risk assessment, execution plan, and potential challenges
- **Purpose**: Augments technical indicators with contextual insights and human-readable strategic guidance
- **Trigger**: User requests analysis from Chart Modal AI Analysis tab
- **Progression**: Market data aggregation → LLM prompt construction → Analysis generation → Markdown rendering → Risk metrics display
- **Success criteria**: Complete analysis with all sections populated, actionable recommendations, clear profit/risk projections, regeneration capability

### Risk Management & Exposure Control
- **Functionality**: Validates position sizing, per-asset exposure limits, aggregate risk caps, and compliance checks before any execution or notification
- **Purpose**: Enforces institutional-grade risk discipline and prevents over-leverage
- **Trigger**: After trade plan generation
- **Progression**: Account balance fetch → Risk % validation → Position size calculation → Exposure limit check → Compliance audit → Approval/rejection
- **Success criteria**: Rejects setups exceeding limits, logs all decisions, maintains audit trail, prevents duplicate positions

### Telegram Notifications & Bot Interface
- **Functionality**: Sends ranked setup alerts with complete trade specifications, charts, confluence breakdown, and machine-readable JSON payloads
- **Purpose**: Delivers institutional-quality signals to operators and future automated execution systems
- **Trigger**: After risk approval
- **Progression**: Plan formatting → Chart generation → Markdown rendering → JSON payload creation → Telegram send → Delivery confirmation
- **Success criteria**: Messages render correctly on mobile, include all plan details, provide actionable entry/exit levels, include visual confirmation

### Verification & Quality Gates
- **Functionality**: Runs deterministic backtests, schema validation, unit tests, integration tests, and quality audits on every build
- **Purpose**: Ensures reproducibility, catches regressions, validates edge retention
- **Trigger**: Pre-commit, CI/CD pipeline, or manual audit command
- **Progression**: Fixture loading → Schema validation → Unit test execution → Integration test run → Backtest simulation → Quality report generation
- **Success criteria**: 100% schema compliance, >95% test coverage, deterministic backtest results, documented quality metrics

## Edge Case Handling

- **Missing Data**: Gracefully skip symbols with incomplete timeframes, log gaps, retry with exponential backoff, never proceed with partial context
- **Rate Limits**: Implement adaptive throttling, distributed fetching, and persistent caching to respect exchange limits without blocking scans
- **Conflicting Signals**: Apply explicit conflict penalties in confluence scoring, document contradictions in rationale, require manual override for high-conflict setups
- **Null/Invalid Indicators**: Hard error via error_policy.py, never allow empty SMC or missing rationale to reach notifications, fail loudly with diagnostic context
- **Execution Failures**: Safeguards prevent duplicate orders, over-leverage, and unverified trades; maintain strict audit log of all attempts and rejections
- **Network Interruptions**: Persist scan state, resume from last successful checkpoint, validate data integrity post-reconnection, never assume partial success

## Design Direction

The interface should feel institutional, precise, and data-dense while maintaining clarity and actionability. It must evoke confidence through rigorous organization, comprehensive information architecture, and zero ambiguity. The design should balance technical depth with operational efficiency—suitable for both manual operator review and automated bot consumption. A minimal, terminal-first aesthetic with strategic visual hierarchy serves the analytical, verification-focused workflow better than rich graphical interfaces.

## Color Selection

**Custom palette** - Professional trading terminal aesthetic with high-contrast data visualization and semantic color coding for different signal states and quality levels.

- **Primary Color**: Deep Blue `oklch(0.35 0.12 250)` - Communicates trust, precision, institutional gravitas; used for primary actions and key structural elements
- **Secondary Colors**: 
  - Charcoal `oklch(0.25 0.01 260)` - Terminal-style backgrounds, data panels
  - Slate Gray `oklch(0.45 0.02 250)` - Secondary text, dividers, muted elements
- **Accent Color**: Electric Cyan `oklch(0.72 0.15 195)` - Highlighting active signals, entry zones, key metrics; attention without distraction
- **Semantic Colors**:
  - Success Green `oklch(0.65 0.18 145)` - Long setups, profitable targets, passed gates
  - Warning Amber `oklch(0.70 0.15 75)` - Caution states, conflict flags, pending validations
  - Danger Red `oklch(0.58 0.22 25)` - Short setups, stop losses, failed validations, risk warnings

**Foreground/Background Pairings**:
- Background (Charcoal `oklch(0.25 0.01 260)`): Light Gray text `oklch(0.92 0.01 260)` - Ratio 12.8:1 ✓
- Card (Deep Blue `oklch(0.30 0.10 250)`): White text `oklch(0.98 0 0)` - Ratio 10.2:1 ✓
- Primary (Deep Blue `oklch(0.35 0.12 250)`): White text `oklch(0.98 0 0)` - Ratio 8.5:1 ✓
- Secondary (Slate Gray `oklch(0.45 0.02 250)`): White text `oklch(0.98 0 0)` - Ratio 6.1:1 ✓
- Accent (Electric Cyan `oklch(0.72 0.15 195)`): Charcoal text `oklch(0.25 0.01 260)` - Ratio 7.3:1 ✓
- Success (Green `oklch(0.65 0.18 145)`): Dark text `oklch(0.20 0.02 145)` - Ratio 8.9:1 ✓
- Warning (Amber `oklch(0.70 0.15 75)`): Dark text `oklch(0.20 0.02 75)` - Ratio 9.4:1 ✓
- Danger (Red `oklch(0.58 0.22 25)`): White text `oklch(0.98 0 0)` - Ratio 5.2:1 ✓

## Font Selection

Typefaces should convey technical precision, monospace clarity for numerical data, and high readability for dense information displays—evoking terminal interfaces and professional trading platforms.

- **Typographic Hierarchy**:
  - H1 (Page Title): JetBrains Mono Bold / 32px / -0.02em letter spacing
  - H2 (Section Headers): JetBrains Mono SemiBold / 24px / -0.01em letter spacing
  - H3 (Subsection): JetBrains Mono Medium / 18px / normal spacing
  - Body (Descriptions): Inter Regular / 15px / 0.01em / 1.6 line-height
  - Code/Data (Metrics, Prices): JetBrains Mono Regular / 14px / tabular-nums / monospace
  - Small (Labels, Meta): Inter Medium / 13px / 0.02em / uppercase for labels

## Animations

Animations should be purposeful and minimal—communicating state transitions, data updates, and loading states without unnecessary flourish. The system prioritizes instant feedback for data-intensive operations while maintaining terminal-like efficiency.

- **Purposeful Meaning**: Quick fade-ins for new signals (150ms), pulsing indicators for active scans, smooth transitions between scan results, no decorative motion
- **Hierarchy of Movement**: Prioritize updates to score changes, new signals appearing, quality gate transitions, chart overlays; avoid animating static reference data

## Component Selection

- **Components**: 
  - `Card` - Primary container for signal details, scan results, trade plans with custom borders for quality tiers
  - `Table` - Multi-symbol scan results, confluence breakdowns, historical performance metrics
  - `Tabs` - Timeframe switching, profile selection, scan history navigation
  - `Badge` - Signal classification (scalp/swing, trend/range), quality scores, regime labels
  - `Dialog` - Detailed trade plan review, verification reports, audit logs
  - `Accordion` - Collapsible SMC details, confluence factor breakdowns, rationale sections
  - `Progress` - Scan progress, data ingestion status, backtest execution
  - `Alert` - Quality gate failures, risk violations, data warnings
  - `Select` - Profile selection, symbol filtering, timeframe preferences
  - `Separator` - Visual segmentation between major sections
  
- **Customizations**: 
  - Custom `SignalCard` component with quality tier styling (gold/silver/bronze borders)
  - Custom `PriceLevel` component with monospace formatting and color-coded direction
  - Custom `ConfluenceBar` visual component showing factor weights
  - Custom `RRIndicator` component with visual R:R ratio representation
  
- **States**: 
  - Buttons: Distinct hover with subtle glow on accent color, active state with inset shadow, disabled with 40% opacity
  - Inputs: Focus state with accent border, error state with danger color, success validation with green checkmark
  - Cards: Hover elevation change, selected state with accent border, loading skeleton state
  
- **Icon Selection**: 
  - `TrendUp`/`TrendDown` - Directional bias
  - `Target` - Entry zones, price targets
  - `ShieldCheck` - Risk validation, quality gates
  - `Lightning` - High-conviction signals, displacement
  - `ChartBar` - Timeframe selection, analysis views
  - `Bell` - Notifications, alerts
  - `Check`/`X` - Validation states, gate pass/fail
  - `Warning` - Conflicts, cautions
  - `ArrowsClockwise` - Refresh, rescan
  - `Gear` - Settings, profile configuration
  
- **Spacing**: 
  - Card padding: `p-6` (24px)
  - Section gaps: `gap-8` (32px)
  - Component gaps: `gap-4` (16px)
  - Inline spacing: `gap-2` (8px)
  - Tight groupings: `gap-1` (4px)
  
- **Mobile**: 
  - Single-column layout for signal cards
  - Collapsible sections default to closed on mobile
  - Sticky header with profile selector
  - Bottom navigation for primary actions (Scan, History, Settings)
  - Horizontal scroll for wide tables with sticky first column
  - Touch-optimized tap targets (min 44px)
  - Simplified chart overlays on small screens
