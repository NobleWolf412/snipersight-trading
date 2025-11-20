"""
Strategy pipeline contracts.

Defines interfaces for SMC detection, confluence scoring, and trade planning.
Following ARCHITECTURE.md strategy pipeline flow.
"""
from abc import ABC, abstractmethod
from typing import List, Dict
import pandas as pd
from backend.shared.models.smc import SMCSnapshot, OrderBlock, FVG
from backend.shared.models.scoring import ConfluenceBreakdown
from backend.shared.models.planner import TradePlan


class SMCDetector(ABC):
    """Abstract interface for Smart-Money Concept detection."""
    
    @abstractmethod
    def detect_order_blocks(self, df: pd.DataFrame, config: Dict) -> List[OrderBlock]:
        """Detect order blocks in price data."""
        pass
    
    @abstractmethod
    def detect_fvgs(self, df: pd.DataFrame, config: Dict) -> List[FVG]:
        """Detect fair value gaps."""
        pass


class ConfluenceScorer(ABC):
    """Abstract interface for confluence scoring."""
    
    @abstractmethod
    def compute_score(self, context: 'SniperContext') -> ConfluenceBreakdown:
        """
        Compute confluence score from multi-timeframe context.
        
        Args:
            context: SniperContext with indicators, SMC, and market data
            
        Returns:
            ConfluenceBreakdown with total score and factor breakdown
        """
        pass


class TradePlanner(ABC):
    """Abstract interface for trade plan generation."""
    
    @abstractmethod
    def generate_plan(self, context: 'SniperContext') -> TradePlan:
        """
        Generate complete trade plan from analysis.
        
        Args:
            context: SniperContext with all analysis completed
            
        Returns:
            TradePlan with entries, stops, targets, and rationale
            
        Note:
            Must return complete plan with NO null fields (except metadata).
            Following "No-Null, Actionable Outputs" principle.
        """
        pass
