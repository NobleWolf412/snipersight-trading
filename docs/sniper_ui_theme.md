# Sniper UI Theme & Terminology

This document defines the sniper-themed user interface language for SniperSight, mapping functional trading terms to tactical/military terminology.

## Overview

**Purpose**: Create an immersive, tactical user experience through consistent terminology while maintaining technical accuracy in backend systems.

**Scope**: UI labels, button text, screen titles, notifications, and user-facing documentation ONLY.

**Non-Scope**: Backend code, API endpoints, database schemas, type names, internal logs.

---

## Core Principle

> **UI speaks sniper language. Backend speaks technical language.**

The terminology layer is a pure presentation concern. All backend models, API contracts, and data structures use standard trading/technical terms. The frontend translates these to sniper terms for display.

---

## Complete Terminology Mapping

| Functional Term          | Sniper Term              | Context                          | Notes                                      |
|--------------------------|--------------------------|----------------------------------|--------------------------------------------|
| **Scan**                 | Sweep the Field          | Button label, action verb        | Primary CTA for initiating scans           |
| **Scanner Mode**         | Recon / Recon Mode       | Mode name, navigation tab        | Read-only signal generation mode           |
| **Signals List**         | Target Board             | Screen title, table header       | Leaderboard-style signal list              |
| **Signal**               | Target                   | Individual signal reference      | "5 targets acquired"                       |
| **Signal Details**       | Target Intel             | Screen title, drawer/dialog      | Detailed trade plan view                   |
| **Confluence Score**     | Precision Rating         | Metric label, score display      | 0-100 quality score                        |
| **Risk Score**           | Threat Index             | Risk level indicator             | Low/Medium/High threat assessment          |
| **Stop Loss**            | Extraction Point         | Trade plan field                 | Emergency exit price level                 |
| **Take Profit**          | Impact Point             | Trade plan field                 | Target price levels (TP1, TP2, TP3)        |
| **Entry Price**          | Entry Zone               | Trade plan field                 | Near/far entry prices                      |
| **Bot Start**            | Deploy SniperBot         | Button label, action             | Initiating bot automation                  |
| **Bot Stop**             | Cease Operation          | Button label, action             | Halting bot automation                     |
| **Bot Activity Log**     | Mission Log              | Screen title, log viewer         | Timeline of bot events                     |
| **Signal Generated**     | Target Acquired          | Log event, status message        | Successful signal creation                 |
| **Signal Rejected**      | Target Discarded         | Log event, status message        | Signal failed quality gates                |
| **Open Position**        | Active Engagement        | Position status, table title     | Currently held position                    |
| **Position**             | Engagement               | Position reference               | "2 active engagements"                     |
| **Close Position**       | Close Engagement         | Action label                     | Manually closing a position                |
| **Setup Style**          | Engagement Type          | Classification label             | Scalp / Swing / Intraday                   |
| **Max Open Positions**   | Max Active Engagements   | Risk parameter label             | Maximum concurrent positions               |
| **Position Size**        | Engagement Size          | Order parameter                  | Trade size/quantity                        |
| **Scan Summary**         | Field Report             | Results summary section          | High-level scan statistics                 |
| **Scan History**         | Recon History            | Historical scans view            | Past scan runs                             |
| **Exchange Profile**     | Data Source              | Profile selector label           | Which exchange to pull data from           |
| **Strategy Profile**     | Tactical Profile         | Strategy selector label          | Balanced/Trend/Range/Aggressive            |
| **Daily Loss Limit**     | Daily Loss Failsafe      | Risk parameter label             | Auto-stop threshold                        |
| **Risk Management**      | Threat Management        | Section title                    | Risk controls and limits                   |
| **Leverage**             | Force Multiplier         | Parameter label                  | Leverage setting                           |
| **Backtest**             | Historical Simulation    | Feature label                    | Past performance testing                   |
| **Quality Gate**         | Clearance Gate           | Validation checkpoint            | Signal quality threshold                   |
| **Confluence Breakdown** | Tactical Assessment      | Analysis section title           | Multi-factor score breakdown               |
| **HTF Alignment**        | Strategic Alignment      | Confluence factor                | Higher timeframe trend alignment           |
| **BTC Impulse Gate**     | Market Pulse Gate        | Confluence factor                | Bitcoin momentum filter                    |
| **Regime**               | Market Condition         | Market state label               | Trend/Range/Risk-On/Risk-Off               |
| **Order Block**          | Institutional Zone       | SMC element                      | Order block reference                      |
| **Fair Value Gap**       | Price Imbalance          | SMC element                      | FVG reference                              |
| **Displacement**         | Momentum Surge           | SMC characteristic               | Sharp price movement                       |
| **Liquidity Sweep**      | Liquidity Raid           | SMC event                        | Stop hunt pattern                          |

---

## Usage Guidelines

### 1. UI-Only Application

**✅ USE sniper terms in:**
- Button labels and CTA text
  - "Sweep the Field" button
  - "Deploy SniperBot" button
  - "View Target Intel" link
  
- Screen titles and headings
  - "Target Board"
  - "Mission Log"
  - "Recon History"
  
- Table column headers
  - "Precision Rating" instead of "Score"
  - "Engagement Type" instead of "Setup Style"
  
- Status messages and notifications
  - "5 targets acquired, 3 discarded"
  - "Active engagement opened: BTC/USDT LONG"
  
- Metric labels in cards
  - "Extraction Point: $41,200"
  - "Impact Points: $43,500 / $44,800 / $46,200"
  
- User-facing documentation and help text
  - "The Target Board displays all acquired targets from your latest field sweep."

---

### 2. Backend Unchanged

**❌ DO NOT use sniper terms in:**
- API endpoint paths
  - ✅ `/api/scan` (not `/api/sweep`)
  - ✅ `/api/bot/start` (not `/api/sniper/deploy`)
  
- JSON field names
  - ✅ `"stop_loss": 41200` (not `"extraction_point": 41200`)
  - ✅ `"score": 78.5` (not `"precision_rating": 78.5`)
  
- Database column names
  - ✅ `signals.stop_loss` (not `signals.extraction_point`)
  
- Python class/function names
  - ✅ `calculate_stop_loss()` (not `calculate_extraction_point()`)
  - ✅ `class SignalPayload` (not `class TargetIntel`)
  
- Internal logs and error messages
  - ✅ `"Signal failed HTF alignment gate"` (server logs)
  - ✅ `"Position opened at 42150"` (audit logs)
  
- Type definitions and schemas
  - ✅ `TradePlan.stop_loss: float` (not `.extraction_point`)

---

### 3. Translation Layer

Implement a terminology translator in the frontend:

```typescript
// src/utils/terminology.ts

const TERM_MAP: Record<string, string> = {
  'stop_loss': 'Extraction Point',
  'take_profit': 'Impact Point',
  'entry': 'Entry Zone',
  'score': 'Precision Rating',
  'risk_score': 'Threat Index',
  'signal': 'Target',
  'position': 'Engagement',
  'scan': 'Sweep',
  'bot_start': 'Deploy SniperBot',
  'bot_stop': 'Cease Operation',
  // ... complete mapping
}

export function toSniperTerm(technicalTerm: string): string {
  return TERM_MAP[technicalTerm] || technicalTerm
}

export function toTechnicalTerm(sniperTerm: string): string {
  const reversed = Object.fromEntries(
    Object.entries(TERM_MAP).map(([k, v]) => [v, k])
  )
  return reversed[sniperTerm] || sniperTerm
}

// Usage in components
<Label>{toSniperTerm('stop_loss')}</Label>
// Renders: <Label>Extraction Point</Label>

<TableHeader>{toSniperTerm('score')}</TableHeader>
// Renders: <TableHeader>Precision Rating</TableHeader>
```

**Benefits**:
- Centralized terminology management
- Easy to A/B test different phrasings
- Can toggle "Technical Mode" for advanced users
- Backend types remain unchanged

---

### 4. Consistency

**Always use the same sniper term for the same concept:**

✅ Good (consistent):
```
"Sweep the Field" button everywhere
"Target Board" screen title everywhere
"Extraction Point" for all stop loss references
```

❌ Bad (inconsistent):
```
"Sweep the Field" button on one screen
"Run Scan" button on another screen

"Target Board" on desktop
"Signals List" on mobile
```

---

### 5. Contextual Clarity

Some terms need context to be clear:

**Stop Loss → Extraction Point**
- Context needed: Trading jargon
- Sniper term clear: "Emergency exit price"
- Help text: "Extraction Point is your predetermined exit level if the trade moves against you."

**Take Profit → Impact Point**
- Context needed: Target price
- Sniper term clear: "Price objective"
- Help text: "Impact Points are your target price levels where you'll take profits."

**Quality Gate → Clearance Gate**
- Context needed: Validation checkpoint
- Sniper term maintains meaning: "Must pass clearance to proceed"

---

## Screen-by-Screen Terminology

### Scanner Mode Screens

#### Acquire Targets (Scan Control Panel)
- **Title**: "Acquire Targets"
- **Subtitle**: "Configure reconnaissance parameters"
- **Profile Selector**: "Tactical Profile"
- **Exchange Selector**: "Data Source"
- **Universe Selector**: "Target Universe" (Top 10 / Top 20 / Custom)
- **Primary CTA**: "Sweep the Field"
- **Results Summary**: "Field Report"
  - "Symbols scanned: 20"
  - "Targets acquired: 5"
  - "Targets discarded: 8"

#### Target Board (Signals List)
- **Title**: "Target Board"
- **Subtitle**: "Prioritized opportunities from latest sweep"
- **Table Columns**:
  - Symbol
  - Direction (LONG/SHORT)
  - Precision Rating (score)
  - R:R
  - Engagement Type (setup style)
  - Market Condition (regime)
  - Timestamp
- **Empty State**: "No targets acquired. Sweep the field to identify opportunities."

#### Target Intel (Signal Detail)
- **Title**: "Target Intel: [Symbol] [Direction]"
- **Sections**:
  - **Overview**
    - Engagement Type
    - Precision Rating
    - Threat Index
  - **Tactical Plan**
    - Entry Zones (near/far)
    - Extraction Point (SL)
    - Impact Points (TPs)
    - R:R Ratio
  - **Tactical Assessment** (Confluence Breakdown)
    - Factor scores with rationale
    - Strategic Alignment (HTF)
    - Market Pulse Gate (BTC impulse)
  - **Reasoning** (narrative)
  - **Raw Data** (JSON toggle)

#### Recon History
- **Title**: "Recon History"
- **Subtitle**: "Past field sweeps and acquired targets"
- **Table Columns**:
  - Sweep ID
  - Timestamp
  - Tactical Profile
  - Data Source
  - Targets Acquired

---

### SniperBot Mode Screens

#### SniperBot Command Center
- **Title**: "SniperBot Command Center"
- **Subtitle**: "Deploy and configure automated operations"
- **Mode Selector**:
  - "Safety" (OFF)
  - "Training Mode" (PAPER)
  - "Live Ammunition" (LIVE) ⚠️
- **Profile Selectors**:
  - "Tactical Profile"
  - "Data Source"
- **Risk Controls Section**:
  - "Threat Management"
  - "Max Risk Per Engagement"
  - "Max Active Engagements"
  - "Daily Loss Failsafe"
  - "Force Multiplier" (leverage)
- **Deployment**:
  - Button: "Deploy SniperBot"
  - Button: "Cease Operation"
  - Status: "Operational" / "Inactive" / "Training"

#### Active Engagements
- **Title**: "Active Engagements"
- **Subtitle**: "Currently held positions"
- **Table Columns**:
  - Symbol
  - Side
  - Entry
  - Extraction Point
  - Impact Points
  - Size
  - R:R
  - PnL
  - Status
- **Row Actions**:
  - "View Target Intel"
  - "Move Extraction Point to Breakeven"
  - "Close Engagement"

#### Mission Log
- **Title**: "Mission Log"
- **Subtitle**: "Bot activity timeline"
- **Event Types** (displayed as):
  - "Sweep Completed"
  - "Target Acquired"
  - "Target Discarded"
  - "Engagement Opened"
  - "Impact Point Hit" (partial TP)
  - "Extraction Triggered" (SL hit)
  - "Engagement Closed"
  - "Threat Limit Hit" (risk violation)
  - "Failsafe Triggered" (daily loss limit)

#### Bot Status Overview
- **Title**: "SniperBot Status"
- **Fields**:
  - Mode: "Live Ammunition" / "Training Mode" / "Safety"
  - Tactical Profile
  - Data Source
  - Status: "Operational" / "Inactive"
  - Active Engagements: "2 / 3 max"
  - Today's PnL
  - Last Sweep / Next Sweep
  - Health: "Operational" / "Warning" / "Error"

---

## Typography & Voice

### Tone
- **Precise**: Technical accuracy maintained
- **Tactical**: Mission-focused language
- **Confident**: No uncertainty or hesitation
- **Professional**: Institutional-grade seriousness

### Examples

✅ **Good** (sniper voice):
```
"5 targets acquired, 3 discarded due to clearance gate failures"
"Extraction point set at $41,200 below institutional zone"
"Deploy SniperBot in Training Mode to verify tactical profile"
"Impact Point 1 hit - 50% engagement closed at $43,500"
```

❌ **Bad** (too casual or unclear):
```
"Found 5 signals, rejected 3 others"
"Stop loss is $41,200 under the order block"
"Turn on the bot in paper mode to test"
"First target hit - sold half at $43,500"
```

---

## Accessibility Considerations

### Tooltips for Technical Users

Provide optional technical term tooltips:

```tsx
<Label>
  Extraction Point
  <Tooltip>Also known as: Stop Loss</Tooltip>
</Label>
```

### Search & Filter

Support both terminologies in search:

```typescript
function filterSignals(query: string, signals: Signal[]) {
  const normalizedQuery = query.toLowerCase()
  
  return signals.filter(s => 
    s.symbol.toLowerCase().includes(normalizedQuery) ||
    'stop_loss'.includes(normalizedQuery) ||
    'extraction point'.includes(normalizedQuery)  // Both work
  )
}
```

### Toggle Mode (Future)

Consider "Technical Mode" toggle for advanced users:

```tsx
const [useSniperTerms, setUseSniperTerms] = useState(true)

<Label>
  {useSniperTerms ? 'Extraction Point' : 'Stop Loss'}
</Label>
```

---

## Documentation

### User-Facing Docs

Use sniper terminology:

> **How to Deploy SniperBot**
> 
> 1. Navigate to the SniperBot Command Center
> 2. Select your Tactical Profile (Balanced recommended for beginners)
> 3. Choose a Data Source (exchange to pull market data from)
> 4. Configure Threat Management parameters
> 5. Select Training Mode for paper trading
> 6. Click "Deploy SniperBot"
> 
> SniperBot will now sweep the field every 15 minutes and open engagements when high-precision targets are acquired.

### Developer Docs

Use technical terminology:

> **Bot Start API**
> 
> Endpoint: `POST /api/bot/start`
> 
> Request body must include `mode` ("PAPER" or "LIVE"), `profile` (strategy profile name), and `exchange_profile` (exchange data source). The backend validates the request, checks profile capabilities, and initializes the bot loop.

---

## Glossary

Provide a glossary for users unfamiliar with either terminology:

| Sniper Term          | Technical Term    | Definition                                           |
|----------------------|-------------------|------------------------------------------------------|
| Sweep the Field      | Scan              | Analyze multiple trading pairs for opportunities     |
| Target               | Signal            | A trading opportunity that passed quality checks     |
| Precision Rating     | Confluence Score  | Quality score from 0-100 based on multiple factors   |
| Extraction Point     | Stop Loss         | Predetermined exit price if trade goes against you   |
| Impact Point         | Take Profit       | Target price level where you'll take profits         |
| Engagement           | Position          | An active trade you're currently holding             |
| Deploy SniperBot     | Start Bot         | Begin automated trading operations                   |
| Threat Index         | Risk Score        | Assessment of potential downside risk                |

---

## Future Enhancements

### Internationalization (i18n)

When translating to other languages, maintain the tactical theme:

**Spanish**:
- "Sweep the Field" → "Rastrear el Campo"
- "Target Board" → "Tablero de Objetivos"
- "Extraction Point" → "Punto de Extracción"

**French**:
- "Sweep the Field" → "Balayer le Terrain"
- "Target Board" → "Tableau des Cibles"
- "Extraction Point" → "Point d'Extraction"

### Theme Variants

Consider alternative themes for different user preferences:
- **Sniper Theme** (default): Tactical/military terminology
- **Technical Theme**: Standard trading terminology
- **Institutional Theme**: Corporate/professional terminology
  - "Sweep the Field" → "Run Analysis"
  - "Target Board" → "Opportunity Dashboard"
  - "Extraction Point" → "Risk Exit Level"

---

## Implementation Checklist

- [ ] Create `terminology.ts` utility with complete mapping
- [ ] Apply sniper terms to all UI labels and headings
- [ ] Ensure backend API uses technical terms
- [ ] Verify JSON responses use technical field names
- [ ] Add tooltips explaining technical equivalents
- [ ] Document sniper terms in user help/docs
- [ ] Test search works with both terminologies
- [ ] Review consistency across all screens
- [ ] Gather user feedback on clarity
- [ ] Consider Technical Mode toggle for power users
