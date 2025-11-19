import { useState } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { FileText, SquaresFour, Tree, Lightbulb, ChartLineUp } from '@phosphor-icons/react'
import { MarkdownViewer } from '@/components/MarkdownViewer'
import { ProgressTracker } from '@/components/ProgressTracker'

const prdContent = `# SniperSight – Institutional-Grade Crypto Market Scanner

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

## Design Direction

The interface should feel institutional, precise, and data-dense while maintaining clarity and actionability. It must evoke confidence through rigorous organization, comprehensive information architecture, and zero ambiguity.`

const architectureOverview = `# SniperSight Architecture Overview

## Dual Operation Modes

SniperSight operates in **two primary modes** sharing the same core engine:

### Scanner Mode (Recon / Manual)
- User-triggered scans for manual review
- Read-only exchange access (no API keys needed)
- Endpoints: \`/api/scan\`, \`/api/signals/{run_id}\`, \`/api/signal/{signal_id}\`
- User reviews "Target Board" and "Target Intel" before trading manually

### SniperBot Mode (Automated)
- Scheduled/continuous scanning with optional execution
- Three modes: OFF, PAPER (Training), LIVE (Live Ammunition)
- Endpoints: \`/api/bot/start\`, \`/api/bot/stop\`, \`/api/bot/status\`, \`/api/bot/positions\`
- Quality-gated execution with strict risk controls
- Server-side API keys (never exposed to frontend)

**Both modes use identical**: Same \`SniperContext\` and \`SignalPayload\` models, same quality gates and SMC detection, same risk validation. Difference is trigger (user vs scheduled) and execution authority (manual vs automated).

## System Architecture

\`\`\`
API Layer: Scanner Endpoints + Bot Endpoints
    ↓
Engine Orchestrator (Pipeline, Context, Hooks, Bot Loop)
    ↓
Data Package → Indicators Package → Strategy Package
    ↓
Risk Package (Position Sizing, Exposure Limits, Compliance)
    ↓
Bot Executor + Telemetry + Audit Pipeline
    ↓
Exchange Profile Manager (Server-side API keys)
\`\`\`

## Core Architecture Principles

### 1. Preserve Smart-Money Edge
Every component honors multi-timeframe context, order blocks, FVGs, liquidity sweeps, BTC impulse gates, and institutional heuristics.

### 2. No-Null, Actionable Outputs
All outputs must be complete—no missing fields, no "TBD" placeholders, no null sections.

### 3. Verification-Ready
Deterministic fixtures, strong typing, schema validation, and comprehensive test coverage.

### 4. Zero Silent Failures
Missing indicators, incomplete SMC data, or blank rationale trigger hard errors.

### 5. Plugin-Friendly & ML-Ready
Pluggable indicators, strategies, and hooks support future ML scoring.

### 6. Security-First Design
API keys stored server-side only (never in frontend). Exchange profiles with capability flags. RBAC for bot operations.`

const projectStructureOverview = `# Project Structure

## Package Organization

\`\`\`
snipersight/
├── contracts/          # API boundary definitions
├── shared/            # Cross-cutting models, configs, utilities
├── data/              # Multi-exchange data ingestion
├── indicators/        # Technical analysis computation
├── strategy/          # SMC detection, confluence, planning
├── risk/              # Position sizing and exposure control
├── bot/               # Notifications, execution, telemetry
├── engine/            # Pipeline orchestration
├── ml/                # ML integration hooks
├── tests/             # Test suites and fixtures
├── docs/              # Documentation
└── scripts/           # Operational scripts
\`\`\`

## Key Packages

### shared/
Cross-cutting models, configurations, and utilities used by all packages.

### contracts/
API boundary definitions that enforce consistent interfaces.

### data/
Multi-exchange data ingestion, caching, and normalization.

### indicators/
Technical analysis computation across all timeframes.

### strategy/
Smart-Money Concept detection, confluence scoring, and trade planning.

### risk/
Position sizing, exposure control, and compliance validation.

### bot/
Notification delivery, optional execution, charting, and telemetry.

### engine/
Pipeline orchestration, context management, and plugin coordination.`

const implementationGuide = `# Implementation Guide

## Getting Started

This is a **reference implementation** for the SniperSight architecture. The documents provided serve as a comprehensive blueprint for building an institutional-grade crypto market scanner with dual operation modes:

- **Scanner Mode (Recon)**: User-triggered scans for manual signal review and trading
- **SniperBot Mode**: Automated scanning with optional paper/live execution

## What You Have

✅ **PRD.md** - Complete product requirements and design specifications
✅ **ARCHITECTURE.md** - Full system architecture including Scanner + Bot modes
✅ **PROJECT_STRUCTURE.md** - Detailed package structure with module responsibilities
✅ **docs/api_contract.md** - Complete API endpoint specifications
✅ **docs/exchange_profiles.md** - Exchange profile system and security
✅ **docs/security.md** - API key handling and security architecture
✅ **docs/sniper_ui_theme.md** - UI terminology and sniper-themed design

## Implementation Approach

### Phase 1: Foundation
1. Set up Python project structure
2. Implement \`shared/models/\` data structures
3. Create \`contracts/\` API definitions
4. Build \`shared/config/\` system

### Phase 2: Data Layer
1. Implement exchange adapters (\`data/adapters/\`)
2. Build caching system (\`data/cache.py\`)
3. Create ingestion pipeline (\`data/ingestion_pipeline.py\`)
4. Add deterministic test fixtures

### Phase 3: Analysis Layer
1. Build indicator computation (\`indicators/\`)
2. Implement SMC detection (\`strategy/smc/\`)
3. Create confluence scoring (\`strategy/confluence/\`)
4. Build trade planner (\`strategy/planner/\`)

### Phase 4: Risk & Execution
1. Implement risk management (\`risk/\`)
2. Build notification system (\`bot/notifications/\`)
3. Create executor layer (\`bot/executor/\`)
4. Add telemetry (\`bot/telemetry/\`)

### Phase 5: Orchestration
1. Build pipeline controller (\`engine/pipeline.py\`)
2. Implement context management (\`engine/context.py\`)
3. Create hook system (\`engine/hooks.py\`)
4. Build CLI (\`sniper_sight_cli.py\`)

### Phase 6: Quality & Testing
1. Implement quality gates
2. Build backtest framework
3. Create verification checklist
4. Add comprehensive test coverage

## Key Design Decisions

### No-Null Outputs
Every signal must have complete trade plans with zero null fields.

### Deterministic Verification
All components must be testable with deterministic fixtures.

### Contract-Driven Development
Respect API contracts defined in \`contracts/\` package.

### Quality Gates
Multi-layered gating ensures only high-quality signals proceed.

## Next Steps

1. **Review the documentation** in PRD.md, ARCHITECTURE.md, and PROJECT_STRUCTURE.md
2. **Set up your Python environment** with required dependencies
3. **Start with \`shared/\` package** to establish data models
4. **Follow the phase-by-phase approach** outlined above
5. **Maintain verification-first mindset** with tests at every layer

## Important Notes

⚠️ This is a **TypeScript/React Spark application** serving as a **documentation viewer** for the Python-based SniperSight architecture.

⚠️ The actual SniperSight implementation should be built in **Python** following the architectural blueprint provided.

⚠️ Use this interface to **explore the architecture**, understand the design principles, and reference the detailed specifications.`

function App() {
    const [activeTab, setActiveTab] = useState('overview')

    return (
        <div className="min-h-screen bg-background">
            <div className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-10">
                <div className="container mx-auto px-4 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-accent rounded flex items-center justify-center">
                                <SquaresFour size={24} weight="bold" className="text-accent-foreground" />
                            </div>
                            <div>
                                <h1 className="text-2xl font-bold text-foreground monospace">SniperSight</h1>
                                <p className="text-sm text-muted-foreground">Architecture & Project Blueprint</p>
                            </div>
                        </div>
                        <Badge variant="outline" className="bg-accent/10 text-accent border-accent/30">
                            v1.0.0
                        </Badge>
                    </div>
                </div>
            </div>

            <div className="container mx-auto px-4 py-8">
                <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                    <TabsList className="grid w-full grid-cols-5 mb-8">
                        <TabsTrigger value="overview" className="gap-2">
                            <Lightbulb size={18} />
                            <span className="hidden sm:inline">Overview</span>
                        </TabsTrigger>
                        <TabsTrigger value="progress" className="gap-2">
                            <ChartLineUp size={18} />
                            <span className="hidden sm:inline">Progress</span>
                        </TabsTrigger>
                        <TabsTrigger value="prd" className="gap-2">
                            <FileText size={18} />
                            <span className="hidden sm:inline">PRD</span>
                        </TabsTrigger>
                        <TabsTrigger value="architecture" className="gap-2">
                            <Tree size={18} />
                            <span className="hidden sm:inline">Architecture</span>
                        </TabsTrigger>
                        <TabsTrigger value="structure" className="gap-2">
                            <SquaresFour size={18} />
                            <span className="hidden sm:inline">Structure</span>
                        </TabsTrigger>
                    </TabsList>

                    <TabsContent value="overview">
                        <div className="grid gap-6">
                            <Card className="border-accent/30">
                                <CardHeader>
                                    <CardTitle>Implementation Guide</CardTitle>
                                    <CardDescription>Getting started with SniperSight</CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <ScrollArea className="h-[600px] pr-4">
                                        <MarkdownViewer content={implementationGuide} />
                                    </ScrollArea>
                                </CardContent>
                            </Card>

                            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                                <Card className="border-accent/30 hover:border-accent/50 transition-colors cursor-pointer"
                                    onClick={() => setActiveTab('progress')}>
                                    <CardHeader>
                                        <ChartLineUp size={32} className="text-accent mb-2" />
                                        <CardTitle className="text-lg">Progress Tracker</CardTitle>
                                        <CardDescription>
                                            Monitor implementation phases and completion status
                                        </CardDescription>
                                    </CardHeader>
                                </Card>

                                <Card className="border-success/30 hover:border-success/50 transition-colors cursor-pointer"
                                    onClick={() => setActiveTab('prd')}>
                                    <CardHeader>
                                        <FileText size={32} className="text-success mb-2" />
                                        <CardTitle className="text-lg">Product Requirements</CardTitle>
                                        <CardDescription>
                                            Complete PRD with features, design direction, and specifications
                                        </CardDescription>
                                    </CardHeader>
                                </Card>

                                <Card className="border-warning/30 hover:border-warning/50 transition-colors cursor-pointer"
                                    onClick={() => setActiveTab('architecture')}>
                                    <CardHeader>
                                        <Tree size={32} className="text-warning mb-2" />
                                        <CardTitle className="text-lg">Architecture</CardTitle>
                                        <CardDescription>
                                            System design, data flow, and core principles
                                        </CardDescription>
                                    </CardHeader>
                                </Card>

                                <Card className="border-accent/30 hover:border-accent/50 transition-colors cursor-pointer"
                                    onClick={() => setActiveTab('structure')}>
                                    <CardHeader>
                                        <SquaresFour size={32} className="text-accent mb-2" />
                                        <CardTitle className="text-lg">Project Structure</CardTitle>
                                        <CardDescription>
                                            Detailed module breakdown with responsibilities
                                        </CardDescription>
                                    </CardHeader>
                                </Card>
                            </div>
                        </div>
                    </TabsContent>

                    <TabsContent value="progress">
                        <ProgressTracker />
                    </TabsContent>

                    <TabsContent value="prd">
                        <Card>
                            <CardHeader>
                                <CardTitle>Product Requirements Document</CardTitle>
                                <CardDescription>
                                    Complete specifications for SniperSight institutional-grade scanner
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <ScrollArea className="h-[700px] pr-4">
                                    <MarkdownViewer content={prdContent} />
                                    <Separator className="my-6" />
                                    <div className="bg-muted/30 p-4 rounded-lg border border-border">
                                        <p className="text-sm text-muted-foreground">
                                            📄 <strong className="text-foreground">Complete PRD available</strong> at <code className="text-accent">PRD.md</code> in the project root
                                        </p>
                                    </div>
                                </ScrollArea>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    <TabsContent value="architecture">
                        <Card>
                            <CardHeader>
                                <CardTitle>System Architecture</CardTitle>
                                <CardDescription>
                                    Design principles, data flow, and package responsibilities
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <ScrollArea className="h-[700px] pr-4">
                                    <MarkdownViewer content={architectureOverview} />
                                    <Separator className="my-6" />
                                    <div className="bg-muted/30 p-4 rounded-lg border border-border">
                                        <p className="text-sm text-muted-foreground">
                                            📄 <strong className="text-foreground">Complete architecture documentation</strong> at <code className="text-accent">ARCHITECTURE.md</code> in the project root
                                        </p>
                                    </div>
                                </ScrollArea>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    <TabsContent value="structure">
                        <Card>
                            <CardHeader>
                                <CardTitle>Project Structure Reference</CardTitle>
                                <CardDescription>
                                    Comprehensive module map with detailed responsibilities
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <ScrollArea className="h-[700px] pr-4">
                                    <MarkdownViewer content={projectStructureOverview} />
                                    <Separator className="my-6" />
                                    <div className="bg-muted/30 p-4 rounded-lg border border-border">
                                        <p className="text-sm text-muted-foreground">
                                            📄 <strong className="text-foreground">Complete structure reference</strong> at <code className="text-accent">PROJECT_STRUCTURE.md</code> in the project root
                                        </p>
                                    </div>
                                </ScrollArea>
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>
            </div>
        </div>
    )
}

export default App