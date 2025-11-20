"""
Indicator computation contract.

Defines the interface that all indicator providers must implement.
Following ARCHITECTURE.md contracts/ package specifications.
"""
from abc import ABC, abstractmethod
from typing import Dict
import pandas as pd
from backend.shared.models.indicators import IndicatorSet


class IndicatorProvider(ABC):
    """
    Abstract base class for indicator computation.
    
    All indicator implementations must follow this contract to ensure
    consistent interface across the system.
    """
    
    @abstractmethod
    def compute(self, df: pd.DataFrame, config: Dict) -> IndicatorSet:
        """
        Compute indicators from OHLCV data.
        
        Args:
            df: OHLCV DataFrame with columns: timestamp, open, high, low, close, volume
            config: Configuration dictionary with indicator parameters
            
        Returns:
            IndicatorSet containing computed indicators
            
        Raises:
            ValueError: If DataFrame is invalid or missing required columns
            IncompleteIndicatorError: If computation fails for any indicator
        """
        pass
