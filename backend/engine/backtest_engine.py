"""
Backtest Engine for SniperSight.

This module provides the infrastructure to run the SniperSight orchestrator
against historical data for validation and testing.
"""

import pandas as pd
from typing import List, Dict
import logging
from pathlib import Path

from backend.shared.config.defaults import ScanConfig
from backend.engine.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

# Path to historical data
# Assuming the file is at backend/tests/backtest/backtest_multitimeframe_real.csv
# adjusted relative to this file (backend/engine/backtest_engine.py)
DATA_PATH = Path(__file__).parent.parent / "tests" / "backtest" / "backtest_multitimeframe_real.csv"


class BacktestAdapter:
    """
    Mock exchange adapter that serves historical data from CSV.
    Implements the interface required by IngestionPipeline.
    """

    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self._data = self._load_data()
        self.symbols = self._data["symbol"].unique().tolist()
        logger.info(f"BacktestAdapter initialized with {len(self.symbols)} symbols from {csv_path}")

    def _load_data(self) -> pd.DataFrame:
        """Load and normalize CSV data."""
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Backtest data not found at {self.csv_path}")

        df = pd.read_csv(self.csv_path)

        # Ensure timestamp is datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Normalize columns if needed (already correct in checked CSV)
        return df

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
        """
        Fetch OHLCV data for a specific symbol and timeframe.

        Args:
            symbol: Trading pair
            timeframe: Timeframe (e.g. '15m', '1H', '4H')
            limit: Unused in backtest (returns available data), kept for interface compatibility

        Returns:
            DataFrame with OHLCV data
        """
        # Filter by symbol and timeframe
        mask = (self._data["symbol"] == symbol) & (self._data["timeframe"] == timeframe)
        df = self._data[mask].copy()

        if df.empty:
            logger.warning(f"No backtest data for {symbol} {timeframe}")
            return pd.DataFrame()

        # Select and order columns required by IngestionPipeline
        required_cols = ["timestamp", "open", "high", "low", "close", "volume"]

        # Sort and return
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df[required_cols]

    def get_top_symbols(self, n: int = 20, quote_currency: str = "USDT") -> List[str]:
        """Return available symbols in the backtest dataset."""
        return self.symbols[:n]


class BacktestEngine:
    """
    Engine to run backtests using the Orchestrator with historical data.
    """

    def __init__(self, profile: str = "balanced"):
        self.profile = profile
        self.adapter = BacktestAdapter(DATA_PATH)

        # Configure scanner
        self.config = ScanConfig(
            profile=profile,
            timeframes=(
                ["1W", "1D", "4H", "1H", "15m"] if profile == "balanced" else ["4H", "1H", "15m"]
            ),
            min_confluence_score=60.0,  # Slightly lower for backtest validation
        )

        # Initialize orchestrator with mock adapter
        # Disable caching for backtest to ensure clean state
        # IngestionPipeline is initialized inside Orchestrator using the passed adapter
        self.orchestrator = Orchestrator(
            config=self.config, exchange_adapter=self.adapter, debug_mode=True
        )
        # Hack: Force ingestion pipeline to NOT use cache if it was initialized with one?
        # The Orchestrator initializes IngestionPipeline(adapter). IngestionPipeline defaults use_cache=True.
        # Ideally we should pass use_cache=False to Orchestrator or IngestionPipeline, but Orchestrator doesn't expose it.
        # However, since IngestionPipeline uses a singleton cache, let's just clear it or let it handle it.
        # Actually, since our adapter returns consistent data, caching is fine (it will just hit cache after first fetch).
        # But for backtest purity, we might want to clear it first.
        if hasattr(self.orchestrator.ingestion_pipeline, "clear_cache"):
            self.orchestrator.ingestion_pipeline.clear_cache()

    def run(self, start_date: str, end_date: str, symbols: str) -> List[Dict]:
        """
        Run the backtest.

        Args:
            start_date: YYYY-MM-DD (Not filtering by date yet, using full CSV data for this v1)
            end_date: YYYY-MM-DD
            symbols: Comma-separated or 'all'

        Returns:
            List of trade plans (as dicts or objects)
        """
        logger.info(f"Starting backtest for profile={self.profile}")

        # Parse symbols
        if symbols.lower() == "all":
            symbol_list = self.adapter.symbols
        else:
            symbol_list = [s.strip() for s in symbols.split(",")]
            # Validate symbols exist in data
            symbol_list = [s for s in symbol_list if s in self.adapter.symbols]

        if not symbol_list:
            logger.error("No valid symbols found for backtest")
            return []

        logger.info(f"Backtesting on {len(symbol_list)} symbols: {symbol_list}")

        # Run scan
        # Note: robust backtest would iterate through time; this v1 runs a "scan" on the *entire* dataset provided.
        # This effectively treats the end of the CSV as "now".
        results, rejection_stats = self.orchestrator.scan(symbol_list)

        logger.info(f"Backtest complete. Generated {len(results)} signals.")
        return results
