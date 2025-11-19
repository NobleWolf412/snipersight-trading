import { useState } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { FileText, SquaresFour, Tree, Lightbulb, ChartLineUp } from '@phosphor-icons/react'
import { MarkdownViewer } from '@/components/MarkdownViewer'
import { ProgressTrackerDetailed } from '@/components/ProgressTrackerDetailed'

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

## 🎯 Quick Start: Where to Begin

This **Spark app** is your **Implementation Dashboard** for building SniperSight.

**SniperSight backend** = Python crypto scanner (what you'll build)
**This Spark app** = TypeScript/React documentation viewer & progress tracker (what you're looking at now)

## Step-by-Step Implementation Path

### 1️⃣ Create Python Repository (5 minutes)

\`\`\`bash
# Outside this Spark directory, create Python backend
mkdir snipersight-backend
cd snipersight-backend
python -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate
\`\`\`

### 2️⃣ Set Up Project Structure (10 minutes)

\`\`\`bash
# Create core package folders
mkdir -p contracts shared/{config,models,utils}
mkdir -p data/adapters indicators
mkdir -p strategy/{smc,confluence,planner}
mkdir -p risk bot/{executor,notifications,ui,telemetry}
mkdir -p engine/plugins ml devtools
mkdir -p tests/{fixtures,unit,integration,backtest}
mkdir -p docs scripts examples

# Create entry point
touch sniper_sight_cli.py
\`\`\`

### 3️⃣ Install Dependencies (15 minutes)

Create \`requirements.txt\`:
\`\`\`
pandas>=2.0.0
numpy>=1.24.0
ccxt>=4.0.0
python-binance>=1.0.0
ta-lib>=0.4.0
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.0.0
python-telegram-bot>=20.0
typer>=0.9.0
loguru>=0.7.0
\`\`\`

Install: \`pip install -r requirements.txt\`

### 4️⃣ Start Building (Follow Progress Tracker)

Go to the **Progress** tab and check off tasks as you complete them!

#### Week 1: Foundation
- Create data models in \`shared/models/data.py\`
- Define contracts in \`contracts/\`
- Build config system in \`shared/config/\`

#### Week 2: Data Layer
- Implement \`BinanceAdapter\` in \`data/adapters/binance.py\`
- Build \`IngestionPipeline\` in \`data/ingestion_pipeline.py\`
- Test fetching multi-timeframe OHLCV data

#### Week 3-4: Analysis
- Compute indicators (RSI, ATR, volume)
- Detect order blocks and FVGs
- Build confluence scoring engine

#### Week 5+: Risk, Bot, Testing
- Add risk management
- Build Telegram notifications
- Create backtest framework

## 📚 Resources Available in This Spark App

### Overview Tab (You Are Here)
Quick start guide and navigation to other sections

### Progress Tab ⭐
Interactive checklist of all 30 implementation tasks
Check off tasks as you complete them (persists between sessions)

### PRD Tab
Product requirements and design specifications

### Architecture Tab
System design, data flow, dual operation modes (Scanner vs Bot)

### Structure Tab
Detailed module breakdown and package responsibilities

## 🔗 External Documentation Files

After reviewing this Spark app, check these files in the project root:

- \`PRD.md\` - Complete product requirements
- \`ARCHITECTURE.md\` - Full system architecture
- \`PROJECT_STRUCTURE.md\` - Package structure details
- \`IMPLEMENTATION_ROADMAP.md\` - Detailed code examples & setup guide

## 💡 Key Architecture Principles

1. **Preserve Smart-Money Edge** - Multi-timeframe context drives everything
2. **No-Null Outputs** - Every signal must be complete with all fields populated
3. **Verification-Ready** - Build tests alongside code, use deterministic fixtures
4. **Zero Silent Failures** - Fail loudly when critical data is missing
5. **Plugin-Friendly** - Easy to add new indicators, strategies, exchanges

## 🎯 Your Next 3 Actions

1. **Review the Progress tab** to see all 30 implementation tasks
2. **Read IMPLEMENTATION_ROADMAP.md** for detailed code examples
3. **Create your Python repo** and start with Phase 1: Foundation

## ⚠️ Important Notes

This **Spark app** (TypeScript/React) is NOT the trading system.

The **Python backend** you'll create is the actual SniperSight scanner.

Use this app as your **command center** to track progress and review architecture while you build.

Good luck, sniper! 🎯`

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
                            <Card className="border-accent/30 bg-accent/5">
                                <CardHeader>
                                    <div className="flex items-center gap-3">
                                        <div className="w-12 h-12 bg-accent rounded-lg flex items-center justify-center">
                                            <Lightbulb size={28} weight="fill" className="text-accent-foreground" />
                                        </div>
                                        <div>
                                            <CardTitle>Getting Started: Your Next Steps</CardTitle>
                                            <CardDescription>Quick actions to begin implementing SniperSight</CardDescription>
                                        </div>
                                    </div>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid gap-3">
                                        <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                                            <div className="w-6 h-6 bg-accent rounded flex items-center justify-center shrink-0 mt-0.5">
                                                <span className="text-xs font-bold text-accent-foreground">1</span>
                                            </div>
                                            <div>
                                                <div className="font-medium text-sm text-foreground mb-1">Review the Progress Tracker</div>
                                                <div className="text-sm text-muted-foreground">Click the <strong>Progress</strong> tab to see all 30 implementation tasks organized by phase</div>
                                            </div>
                                        </div>
                                        <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                                            <div className="w-6 h-6 bg-accent rounded flex items-center justify-center shrink-0 mt-0.5">
                                                <span className="text-xs font-bold text-accent-foreground">2</span>
                                            </div>
                                            <div>
                                                <div className="font-medium text-sm text-foreground mb-1">Read the Implementation Roadmap</div>
                                                <div className="text-sm text-muted-foreground">Open <code className="text-accent px-1">IMPLEMENTATION_ROADMAP.md</code> for detailed code examples and setup instructions</div>
                                            </div>
                                        </div>
                                        <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                                            <div className="w-6 h-6 bg-accent rounded flex items-center justify-center shrink-0 mt-0.5">
                                                <span className="text-xs font-bold text-accent-foreground">3</span>
                                            </div>
                                            <div>
                                                <div className="font-medium text-sm text-foreground mb-1">Create Python Repository</div>
                                                <div className="text-sm text-muted-foreground mb-2">Set up your Python backend in a separate directory</div>
                                                <code className="block text-xs bg-muted p-2 rounded monospace text-foreground">
                                                    mkdir snipersight-backend && cd snipersight-backend<br />
                                                    python -m venv venv && source venv/bin/activate
                                                </code>
                                            </div>
                                        </div>
                                        <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                                            <div className="w-6 h-6 bg-accent rounded flex items-center justify-center shrink-0 mt-0.5">
                                                <span className="text-xs font-bold text-accent-foreground">4</span>
                                            </div>
                                            <div>
                                                <div className="font-medium text-sm text-foreground mb-1">Start Building Phase 1</div>
                                                <div className="text-sm text-muted-foreground">Begin with shared models, contracts, and configuration - the foundation of SniperSight</div>
                                            </div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

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
                        <ProgressTrackerDetailed />
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