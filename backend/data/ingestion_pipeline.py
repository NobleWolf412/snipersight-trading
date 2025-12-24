"""
Data ingestion pipeline for multi-timeframe market data fetching.
Handles parallel symbol fetching and data normalization.
Includes smart OHLCV caching to reduce API calls.
"""

import time
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from loguru import logger

from backend.shared.models.data import MultiTimeframeData
from backend.data.ohlcv_cache import get_ohlcv_cache, OHLCVCache


class IngestionPipeline:
    """
    Pipeline for fetching and normalizing multi-timeframe market data.
    Supports parallel fetching across symbols and timeframes.
    Uses smart OHLCV caching to minimize API calls.
    """

    def __init__(self, adapter, use_cache: bool = True):
        """
        Initialize ingestion pipeline with exchange adapter.

        Args:
            adapter: Exchange adapter instance (e.g., BinanceAdapter)
            use_cache: Whether to use OHLCV caching (default: True)
        """
        self.adapter = adapter
        self.use_cache = use_cache
        self._cache: OHLCVCache = get_ohlcv_cache() if use_cache else None
        
        cache_status = "enabled" if use_cache else "disabled"
        logger.info(f"Ingestion pipeline initialized with {adapter.__class__.__name__} (cache: {cache_status})")

    @staticmethod
    def get_limit_for_mode(timeframe: str, mode_profile: str = "balanced") -> int:
        """
        Get appropriate candle limit based on timeframe and mode profile.
        
        Swing modes (overwatch, stealth) need more HTF candles for proper
        swing high/low detection. Intraday modes (surgical, strike) use
        standard limits to avoid unnecessary data.
        
        Args:
            timeframe: Timeframe string (e.g., '1w', '1d', '4h')
            mode_profile: Scanner mode profile name
        
        Returns:
            Number of candles to fetch
        """
        tf_lower = timeframe.lower()
        profile_lower = (mode_profile or "balanced").lower()
        
        # Swing modes: more candles on HTF for swing detection
        is_swing_mode = profile_lower in ('macro_surveillance', 'overwatch', 'stealth_balanced', 'stealth')
        
        if is_swing_mode:
            if tf_lower in ('1w', '1m'):  # 1M = monthly
                return 500  # ~10 years weekly, already sufficient
            elif tf_lower == '1d':
                return 750  # ~2 years daily
            elif tf_lower == '4h':
                return 750  # ~125 days
            elif tf_lower == '1h':
                return 750  # ~31 days
            else:
                return 500  # LTF stays standard
        else:
            # Intraday modes: standard limits
            return 500

    def fetch_multi_timeframe(
        self,
        symbol: str,
        timeframes: List[str],
        limit: int = 500
    ) -> MultiTimeframeData:
        """
        Fetch OHLCV data across multiple timeframes for a single symbol.
        Uses caching to avoid redundant API calls.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframes: List of timeframe strings (e.g., ['1W', '1D', '4H'])
            limit: Number of candles to fetch per timeframe

        Returns:
            MultiTimeframeData object with dataframes for each timeframe

        Raises:
            ValueError: If any timeframe data is missing or invalid
        """
        logger.debug(f"Fetching multi-timeframe data for {symbol}: {timeframes}")
        
        tf_data = {}
        missing_timeframes = []
        cache_hits = 0
        cache_misses = 0

        for tf in timeframes:
            try:
                df = None
                
                # Try cache first
                if self.use_cache and self._cache:
                    df = self._cache.get(symbol, tf)
                    if df is not None:
                        cache_hits += 1
                        logger.debug(f"✓ Cache HIT for {symbol} {tf} ({len(df)} candles)")
                        tf_data[tf] = df
                        continue
                
                # Cache miss - fetch from exchange
                cache_misses += 1
                df = self.adapter.fetch_ohlcv(symbol, tf, limit=limit)
                
                if df.empty:
                    logger.warning(f"No data returned for {symbol} {tf}")
                    missing_timeframes.append(tf)
                    continue

                # Validate data
                validated_df = self.normalize_and_validate(df, symbol, tf)
                tf_data[tf] = validated_df
                
                # Cache the validated data
                if self.use_cache and self._cache:
                    self._cache.set(symbol, tf, validated_df)

                logger.debug(f"✓ Fetched {len(validated_df)} candles for {symbol} {tf}")

            except Exception as e:
                logger.error(f"Failed to fetch {symbol} {tf}: {e}")
                missing_timeframes.append(tf)

        # Log cache efficiency
        total_requests = cache_hits + cache_misses
        if total_requests > 0:
            hit_rate = cache_hits / total_requests * 100
            logger.debug(f"{symbol}: cache {cache_hits}/{total_requests} ({hit_rate:.0f}% hit rate)")

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
        Uses caching to dramatically reduce API calls on subsequent scans.

        Args:
            symbols: List of trading pair symbols
            timeframes: List of timeframe strings
            limit: Number of candles to fetch per timeframe
            max_workers: Maximum number of concurrent workers

        Returns:
            Dictionary mapping symbol to MultiTimeframeData

        """
        # Log cache stats before fetch
        if self.use_cache and self._cache:
            stats_before = self._cache.get_stats()
            logger.info(
                f"Cache stats before fetch: {stats_before['entries']} entries, "
                f"{stats_before['hit_rate_pct']}% hit rate"
            )
        
        logger.info(
            f"Starting parallel fetch for {len(symbols)} symbols "
            f"across {len(timeframes)} timeframes with {max_workers} workers"
        )

        results = {}
        failed_symbols = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit tasks with small stagger delay to avoid exchange rate limits
            # Phemex returns error 30000 when concurrent requests hit too fast
            future_to_symbol = {}
            for i, symbol in enumerate(symbols):
                future = executor.submit(
                    self.fetch_multi_timeframe,
                    symbol,
                    timeframes,
                    limit
                )
                future_to_symbol[future] = symbol
                # Small stagger (100ms) between submissions to avoid concurrent burst
                if i < len(symbols) - 1:
                    time.sleep(0.1)

            # Collect results with timeout
            try:
                # Use a total timeout for the entire batch to prevent indefinite hangs
                # 45s should be enough for parallel fetching of 10-20 symbols
                for future in as_completed(future_to_symbol, timeout=45):
                    symbol = future_to_symbol[future]
                    try:
                        data = future.result()
                        results[symbol] = data
                        logger.debug(f"✓ Completed fetch for {symbol}")
                    except Exception as e:
                        logger.error(f"✗ Failed to fetch {symbol}: {e}")
                        failed_symbols.append(symbol)
            except TimeoutError:
                logger.error("Parallel fetch timed out after 45s - some symbols may be missing")
                # Cancel remaining futures
                for f in future_to_symbol:
                    f.cancel()
                # Log which ones failed/timed out
                for f, s in future_to_symbol.items():
                    if not f.done():
                        failed_symbols.append(s)
                        logger.warning(f"TIMEOUT: {s} fetch cancelled")

        # Log cache stats after fetch
        if self.use_cache and self._cache:
            stats_after = self._cache.get_stats()
            logger.info(
                f"Cache stats after fetch: {stats_after['entries']} entries, "
                f"{stats_after['hit_rate_pct']}% hit rate, "
                f"{stats_after['total_candles_cached']} candles cached"
            )

        logger.info(
            f"Parallel fetch complete: {len(results)} succeeded, "
            f"{len(failed_symbols)} failed"
        )

        if failed_symbols:
            logger.warning(f"Failed symbols: {', '.join(failed_symbols)}")

        return results

    def _to_pandas_freq(self, timeframe: str) -> Optional[str]:
        """Convert exchange timeframe to pandas frequency."""
        if not timeframe:
            return None
        if timeframe.endswith('m'):
            return f"{timeframe[:-1]}T" # m -> T (min)
        if timeframe.endswith('h'):
            return f"{timeframe[:-1]}H"
        if timeframe.endswith('d'):
            return f"{timeframe[:-1]}D"
        if timeframe.endswith('w'):
            return f"{timeframe[:-1]}W-MON"
        if timeframe.endswith('M'):
            return "ME"
        return None

    def _fill_time_gaps(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """
        Fill missing candles in the time series.
        
        Strategy:
        - Reindex to continuous timeframe grid
        - Close: Forward fill (price persists)
        - Open, High, Low: Fill with Close (flat candle)
        - Volume: Fill with 0
        """
        if df.empty:
            return df
            
        freq = self._to_pandas_freq(timeframe)
        if not freq:
            # Can't determine frequency, return as is
            return df

        # Ensure index is datetime and sorted
        if 'timestamp' not in df.columns and not isinstance(df.index, pd.DatetimeIndex):
             return df
             
        if not isinstance(df.index, pd.DatetimeIndex):
            # Use timestamp column if index is not datetime
            df = df.set_index('timestamp', drop=False)
            
        df = df.sort_index()
        
        # Create full range index
        try:
            full_idx = pd.date_range(start=df.index.min(), end=df.index.max(), freq=freq)
        except ValueError:
            # Handle cases where freq might be incompatible or range is weird
            return df
            
        # Reindex
        df_filled = df.reindex(full_idx)
        
        # Check if we actually added rows (gaps existed)
        if len(df_filled) == len(df):
            return df_filled.reset_index(drop=True) # No gaps
            
        logger.debug(f"Filling {len(df_filled) - len(df)} gaps in {timeframe} data")

        # 1. Volume -> 0
        df_filled['volume'] = df_filled['volume'].fillna(0)
        
        # 2. Close -> ffill (Last price persists)
        df_filled['close'] = df_filled['close'].ffill()
        
        # 3. Open/High/Low -> Fill with the *filled* Close
        # (If no trade, O=H=L=C = Previous Close)
        df_filled['open'] = df_filled['open'].fillna(df_filled['close'])
        df_filled['high'] = df_filled['high'].fillna(df_filled['close'])
        df_filled['low'] = df_filled['low'].fillna(df_filled['close'])
        
        # Restore timestamp column
        df_filled['timestamp'] = df_filled.index
        
        return df_filled.reset_index(drop=True)

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

        # Fill proper time gaps (critical for Phemex/CCXT data)
        df = self._fill_time_gaps(df, timeframe)

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
        quote_currency: str = 'USDT',
        market_type: Optional[str] = None
    ) -> List[str]:
        """
        Get symbol list based on universe selection.

        Args:
            universe: Universe identifier ('top10', 'top20', 'top50')
            quote_currency: Quote currency to filter by
            market_type: Market type ('spot' or 'swap')

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
        
        logger.info(f"Fetching {universe} symbols ({n} symbols) type={market_type}")
        
        if hasattr(self.adapter, 'get_top_symbols'):
            # Only pass market_type if the adapter's method accepts it
            # Python's inspect could be used, but consistent adapter interface is better
            # For now, we assume updated adapters support it (like PhemexAdapter)
            try:
                return self.adapter.get_top_symbols(n=n, quote_currency=quote_currency, market_type=market_type)
            except TypeError:
                # Fallback for adapters not yet updated
                logger.warning(f"Adapter {self.adapter.__class__.__name__} does not support market_type in get_top_symbols")
                return self.adapter.get_top_symbols(n=n, quote_currency=quote_currency)
        else:
            # Fallback to hardcoded list if adapter doesn't support it
            logger.warning("Adapter doesn't support get_top_symbols, using default list")
            default_symbols = [
                'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
                'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT', 'LINK/USDT'
            ]
            return default_symbols[:n]

    def get_cache_stats(self) -> Dict:
        """Get OHLCV cache statistics."""
        if not self.use_cache or not self._cache:
            return {"enabled": False}
        
        stats = self._cache.get_stats()
        stats["enabled"] = True
        return stats
    
    def clear_cache(self) -> None:
        """Clear all cached OHLCV data."""
        if self.use_cache and self._cache:
            self._cache.clear()
            logger.info("OHLCV cache cleared")
    
    def invalidate_symbol_cache(self, symbol: str, timeframe: Optional[str] = None) -> int:
        """
        Invalidate cache for a specific symbol.
        
        Args:
            symbol: Trading pair to invalidate
            timeframe: Specific timeframe (None = all timeframes)
            
        Returns:
            Number of cache entries invalidated
        """
        if not self.use_cache or not self._cache:
            return 0
        return self._cache.invalidate(symbol, timeframe)
