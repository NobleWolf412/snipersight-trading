"""
SniperContext - Central data structure for the pipeline.

This context object is passed through all pipeline stages and accumulates
data from each stage. Following ARCHITECTURE.md pipeline design.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from backend.shared.models.data import MultiTimeframeData
from backend.shared.models.indicators import IndicatorSet
from backend.shared.models.smc import SMCSnapshot
from backend.shared.models.scoring import ConfluenceBreakdown
from backend.shared.models.planner import TradePlan
from backend.contracts.risk_contract import RiskPlan


@dataclass
class SniperContext:
    """
    Central context object passed through the entire pipeline.
    
    Pipeline flow:
    1. Data ingestion populates multi_tf_data
    2. Indicator computation populates multi_tf_indicators
    3. SMC detection populates smc_snapshot
    4. Confluence scoring populates confluence_breakdown
    5. Trade planner populates plan
    6. Risk manager populates risk_plan
    
    Each stage reads from previous stages and adds its own output.
    """
    # Required fields - set at pipeline start
    symbol: str
    profile: str
    run_id: str
    timestamp: datetime
    
    # Pipeline stage outputs - populated progressively
    multi_tf_data: Optional[MultiTimeframeData] = None
    multi_tf_indicators: Optional[IndicatorSet] = None
    smc_snapshot: Optional[SMCSnapshot] = None
    confluence_breakdown: Optional[ConfluenceBreakdown] = None
    plan: Optional[TradePlan] = None
    risk_plan: Optional[RiskPlan] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
