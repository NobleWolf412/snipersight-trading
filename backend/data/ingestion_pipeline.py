"""
Data ingestion pipeline for multi-timeframe market data fetching.
Handles parallel symbol fetching and data normalization.
"""

from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from loguru import logger

from backend.shared.models.data import MultiTimeframeData


class IngestionPipeline:
    """
    Pipeline for fetching and normalizing multi-timeframe market data.
    Supports parallel fetching across symbols and timeframes.
    """

    def __init__(self, adapter):
        """
        Initialize ingestion pipeline with exchange adapter.

        Args:
            adapter: Exchange adapter instance (e.g., BinanceAdapter)
        """
        self.adapter = adapter
        logger.info(f"Ingestion pipeline initialized with {adapter.__class__.__name__}")

    def fetch_multi_timeframe(
        self,
        symbol: str,
        timeframes: List[str],
        limit: int = 500
    ) -> MultiTimeframeData:
        """
        Fetch OHLCV data across multiple timeframes for a single symbol.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframes: List of timeframe strings (e.g., ['1W', '1D', '4H'])
            limit: Number of candles to fetch per timeframe

        Returns:
            MultiTimeframeData object with dataframes for each timeframe

        Raises:
            ValueError: If any timeframe data is missing or invalid
        """
        logger.info(f"Fetching multi-timeframe data for {symbol}: {timeframes}")
        
        tf_data = {}
        missing_timeframes = []

        for tf in timeframes:
            try:
                df = self.adapter.fetch_ohlcv(symbol, tf, limit=limit)
                
                if df.empty:
                    logger.warning(f"No data returned for {symbol} {tf}")
                    missing_timeframes.append(tf)
                    continue

                # Validate data
                validated_df = self.normalize_and_validate(df, symbol, tf)
                tf_data[tf] = validated_df

                logger.debug(f"✓ Fetched {len(validated_df)} candles for {symbol} {tf}")

            except Exception as e:
                logger.error(f"Failed to fetch {symbol} {tf}: {e}")
                missing_timeframes.append(tf)

        # Check if we have complete data
        if missing_timeframes:
            logger.warning(
                f"Missing timeframes for {symbol}: {missing_timeframes}. "
                f"Got {len(tf_data)}/{len(timeframes)} timeframes"
            )

        if not tf_data:
            raise ValueError(f"No data fetched for {symbol} across any timeframe")

        return MultiTimeframeData(symbol=symbol, timeframes=tf_data)

    def parallel_fetch(
        self,
        symbols: List[str],
        timeframes: List[str],
        limit: int = 500,
        max_workers: int = 5
    ) -> Dict[str, MultiTimeframeData]:
        """
        Fetch multi-timeframe data for multiple symbols in parallel.

        Args:
            symbols: List of trading pair symbols
            timeframes: List of timeframe strings
            limit: Number of candles to fetch per timeframe
            max_workers: Maximum number of concurrent workers

        Returns:
            Dictionary mapping symbol to MultiTimeframeData

        """
        logger.info(
            f"Starting parallel fetch for {len(symbols)} symbols "
            f"across {len(timeframes)} timeframes with {max_workers} workers"
        )

        results = {}
        failed_symbols = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all fetch tasks
            future_to_symbol = {
                executor.submit(
                    self.fetch_multi_timeframe,
                    symbol,
                    timeframes,
                    limit
                ): symbol
                for symbol in symbols
            }

            # Collect results as they complete
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    data = future.result()
                    results[symbol] = data
                    logger.info(f"✓ Completed fetch for {symbol}")
                except Exception as e:
                    logger.error(f"✗ Failed to fetch {symbol}: {e}")
                    failed_symbols.append(symbol)

        logger.info(
            f"Parallel fetch complete: {len(results)} succeeded, "
            f"{len(failed_symbols)} failed"
        )

        if failed_symbols:
            logger.warning(f"Failed symbols: {', '.join(failed_symbols)}")

        return results

    def normalize_and_validate(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str
    ) -> pd.DataFrame:
        """
        Normalize and validate OHLCV DataFrame.

        Args:
            df: Raw OHLCV DataFrame
            symbol: Symbol name for logging
            timeframe: Timeframe for logging

        Returns:
            Validated and normalized DataFrame

        Raises:
            ValueError: If data validation fails
        """
        if df.empty:
            raise ValueError(f"Empty DataFrame for {symbol} {timeframe}")

        # Check required columns
        required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        missing_cols = set(required_cols) - set(df.columns)
        if missing_cols:
            raise ValueError(
                f"Missing required columns for {symbol} {timeframe}: {missing_cols}"
            )

        # Ensure proper data types
        df = df.copy()
        df['open'] = pd.to_numeric(df['open'], errors='coerce')
        df['high'] = pd.to_numeric(df['high'], errors='coerce')
        df['low'] = pd.to_numeric(df['low'], errors='coerce')
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

        # Check for NaN values
        if df[required_cols].isnull().any().any():
            null_counts = df[required_cols].isnull().sum()
            logger.warning(f"Found NaN values in {symbol} {timeframe}: {null_counts.to_dict()}")
            df = df.dropna(subset=required_cols)

        # Validate OHLCV relationships: high >= low, high >= close, high >= open, low <= close, low <= open
        invalid_hl = df['high'] < df['low']
        invalid_hc = df['high'] < df['close']
        invalid_ho = df['high'] < df['open']
        invalid_lc = df['low'] > df['close']
        invalid_lo = df['low'] > df['open']

        invalid_mask = invalid_hl | invalid_hc | invalid_ho | invalid_lc | invalid_lo
        
        if invalid_mask.any():
            invalid_count = invalid_mask.sum()
            logger.warning(
                f"Found {invalid_count} invalid OHLCV rows in {symbol} {timeframe}, removing them"
            )
            df = df[~invalid_mask]

        # Check for duplicate timestamps
        duplicates = df['timestamp'].duplicated()
        if duplicates.any():
            dup_count = duplicates.sum()
            logger.warning(f"Found {dup_count} duplicate timestamps in {symbol} {timeframe}, keeping first")
            df = df.drop_duplicates(subset=['timestamp'], keep='first')

        # Sort by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)

        # Set timestamp as index for SMC detection functions (keep as column too for validation)
        df = df.set_index('timestamp', drop=False)        # Final validation
        if len(df) == 0:
            raise ValueError(f"No valid data remaining for {symbol} {timeframe} after validation")

        logger.debug(f"Validated {len(df)} candles for {symbol} {timeframe}")
        return df

    def fetch_universe_symbols(
        self,
        universe: str,
        quote_currency: str = 'USDT'
    ) -> List[str]:
        """
        Get symbol list based on universe selection.

        Args:
            universe: Universe identifier ('top10', 'top20', 'top50')
            quote_currency: Quote currency to filter by

        Returns:
            List of symbol strings
        """
        universe_map = {
            'top10': 10,
            'top20': 20,
            'top50': 50,
            'top100': 100
        }

        n = universe_map.get(universe.lower(), 20)
        
        logger.info(f"Fetching {universe} symbols ({n} symbols)")
        
        if hasattr(self.adapter, 'get_top_symbols'):
            return self.adapter.get_top_symbols(n=n, quote_currency=quote_currency)
        else:
            # Fallback to hardcoded list if adapter doesn't support it
            logger.warning("Adapter doesn't support get_top_symbols, using default list")
            default_symbols = [
                'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
                'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT', 'LINK/USDT'
            ]
            return default_symbols[:n]
