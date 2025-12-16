"""
Indicator Service - Technical indicator computation extracted from orchestrator.py

Computes all technical indicators across timeframes:
- Momentum: RSI, StochRSI, MFI, MACD
- Volatility: ATR, Bollinger Bands, Realized Volatility
- Volume: OBV, Volume Spikes, Relative Volume, Volume Acceleration

This service encapsulates indicator computation logic previously in
orchestrator._compute_indicators()
"""

import logging
from typing import Dict, Any, Optional

import pandas as pd

from backend.shared.models.data import MultiTimeframeData
from backend.shared.models.indicators import IndicatorSet, IndicatorSnapshot

# Momentum indicators
from backend.indicators.momentum import (
    compute_rsi,
    compute_stoch_rsi,
    compute_mfi,
    compute_macd,
)

# Volatility indicators
from backend.indicators.volatility import (
    compute_atr,
    compute_bollinger_bands,
    compute_keltner_channels,
    compute_realized_volatility,
)

# Volume indicators
from backend.indicators.volume import (
    detect_volume_spike,
    compute_obv,
    compute_vwap,
    compute_relative_volume,
    detect_volume_acceleration,
)

logger = logging.getLogger(__name__)


class IndicatorService:
    """
    Service for computing technical indicators across multiple timeframes.
    
    Centralizes all indicator computation logic with proper error handling
    and consistent return types.
    
    Usage:
        service = IndicatorService(scanner_mode=mode)
        indicators = service.compute(multi_tf_data)
    """
    
    def __init__(
        self,
        scanner_mode: Optional[Any] = None,
        min_candles: int = 50,
    ):
        """
        Initialize indicator service.
        
        Args:
            scanner_mode: Scanner mode for mode-aware settings (e.g., volume_accel_lookback)
            min_candles: Minimum candles required for indicator computation
        """
        self._scanner_mode = scanner_mode
        self._min_candles = min_candles
        self._diagnostics: Dict[str, list] = {'indicator_failures': []}
    
    @property
    def diagnostics(self) -> Dict[str, list]:
        """Get diagnostic information from last computation."""
        return self._diagnostics
    
    def set_mode(self, scanner_mode):
        """Update scanner mode dynamically."""
        self._scanner_mode = scanner_mode
    
    def compute(self, multi_tf_data: MultiTimeframeData) -> IndicatorSet:
        """
        Compute technical indicators across all timeframes.
        
        Args:
            multi_tf_data: Multi-timeframe OHLCV data
            
        Returns:
            IndicatorSet with computed indicators per timeframe
        """
        self._diagnostics = {'indicator_failures': []}
        by_timeframe: Dict[str, IndicatorSnapshot] = {}
        
        for timeframe, df in multi_tf_data.timeframes.items():
            if df.empty or len(df) < self._min_candles:
                continue
            
            try:
                snapshot = self._compute_timeframe_indicators(timeframe, df)
                if snapshot:
                    by_timeframe[timeframe] = snapshot
            except Exception as e:
                logger.warning("Indicator computation failed for %s: %s", timeframe, e)
                self._diagnostics['indicator_failures'].append({
                    'timeframe': timeframe, 
                    'error': str(e)
                })
                continue
        
        return IndicatorSet(by_timeframe=by_timeframe)
    
    def _compute_timeframe_indicators(self, timeframe: str, df: pd.DataFrame) -> Optional[IndicatorSnapshot]:
        """Compute all indicators for a single timeframe."""
        # Momentum indicators
        rsi = compute_rsi(df)
        stoch_rsi = compute_stoch_rsi(df)
        mfi = compute_mfi(df)
        
        macd_line, macd_signal, macd_hist = self._safe_compute_macd(df, timeframe)
        
        # Volatility indicators
        atr = compute_atr(df)
        bb_upper, bb_middle, bb_lower = compute_bollinger_bands(df)
        realized_vol = self._safe_compute_realized_volatility(df, timeframe)
        
        # Volume indicators
        volume_spike = detect_volume_spike(df)
        obv = compute_obv(df)
        _ = compute_vwap(df)  # Computed for side effects
        volume_ratio = self._safe_compute_volume_ratio(df, timeframe)
        vol_accel_data = self._safe_compute_volume_acceleration(df, timeframe)
        
        # Log indicator values
        current_price = df['close'].iloc[-1]
        logger.info(
            "📊 %s indicators: RSI=%.1f | MFI=%.1f | ATR=%.2f (%.2f%%) | "
            "BB(%.2f-%.2f-%.2f) | VolSpike=%s",
            timeframe,
            rsi.iloc[-1],
            mfi.iloc[-1],
            atr.iloc[-1],
            (atr.iloc[-1] / current_price * 100) if current_price > 0 else 0,
            bb_lower.iloc[-1], bb_middle.iloc[-1], bb_upper.iloc[-1],
            bool(volume_spike.iloc[-1])
        )
        
        # TTM Squeeze Calculation
        # Standard Settings: BB(20, 2.0) vs KC(20, 1.5)
        # Squeeze ON = BB inside KC (low volatility)
        # Squeeze FIRE = BB expands outside KC (high volatility)
        kc_upper, kc_mid, kc_lower = compute_keltner_channels(df, ema_period=20, atr_multiplier=1.5)
        
        # Determine Squeeze State
        bb_up_val = bb_upper.iloc[-1]
        bb_lo_val = bb_lower.iloc[-1]
        kc_up_val = kc_upper.iloc[-1]
        kc_lo_val = kc_lower.iloc[-1]
        
        ttm_squeeze_on = (bb_up_val < kc_up_val) and (bb_lo_val > kc_lo_val)
        
        # Check if squeeze JUST fired (was on yesterday, off today)
        ttm_squeeze_firing = False
        if len(df) > 1:
            prev_bb_up = bb_upper.iloc[-2]
            prev_bb_lo = bb_lower.iloc[-2]
            prev_kc_up = kc_upper.iloc[-2]
            prev_kc_lo = kc_lower.iloc[-2]
            prev_squeeze_on = (prev_bb_up < prev_kc_up) and (prev_bb_lo > prev_kc_lo)
            
            if prev_squeeze_on and not ttm_squeeze_on:
                ttm_squeeze_firing = True

        
        # Extract stoch_rsi values (handles both tuple and series)
        stoch_k_value, stoch_d_value = self._extract_stoch_values(stoch_rsi)
        
        # Calculate ATR percentage
        atr_value = atr.iloc[-1]
        atr_pct = (atr_value / current_price * 100) if current_price > 0 else None
        
        # Create snapshot
        snapshot = IndicatorSnapshot(
            # Momentum (required)
            rsi=rsi.iloc[-1],
            stoch_rsi=stoch_k_value,
            # Mean Reversion (required)
            bb_upper=bb_upper.iloc[-1],
            bb_middle=bb_middle.iloc[-1],
            bb_lower=bb_lower.iloc[-1],
            # TTM Squeeze
            ttm_squeeze_on=ttm_squeeze_on,
            ttm_squeeze_firing=ttm_squeeze_firing,
            kc_upper=kc_up_val,
            kc_lower=kc_lo_val,
            # Volatility (required)
            atr=atr_value,
            # Volume (required)
            volume_spike=bool(volume_spike.iloc[-1]),
            # Optional fields - Momentum
            mfi=mfi.iloc[-1],
            stoch_rsi_k=stoch_k_value,
            stoch_rsi_d=stoch_d_value,
            # Optional fields - Volatility
            atr_percent=atr_pct,
            realized_volatility=realized_vol.iloc[-1] if realized_vol is not None else None,
            # Optional fields - Volume
            obv=obv.iloc[-1],
            volume_ratio=volume_ratio.iloc[-1] if volume_ratio is not None else None,
            # Optional fields - Volume acceleration
            volume_acceleration=vol_accel_data['acceleration'] if vol_accel_data else None,
            volume_consecutive_increases=vol_accel_data['consecutive_increases'] if vol_accel_data else None,
            volume_is_accelerating=vol_accel_data['is_accelerating'] if vol_accel_data else None,
            volume_accel_direction=vol_accel_data['direction'] if vol_accel_data else None,
            volume_exhaustion=vol_accel_data['exhaustion'] if vol_accel_data else None,
        )
        
        # Attach MACD values if available
        self._attach_macd_data(snapshot, macd_line, macd_signal, macd_hist, timeframe)
        
        return snapshot
    
    def _safe_compute_macd(self, df: pd.DataFrame, timeframe: str):
        """Safely compute MACD with error handling."""
        try:
            return compute_macd(df)
        except Exception as e:
            logger.debug("MACD computation failed for %s: %s", timeframe, e)
            return None, None, None
    
    def _safe_compute_realized_volatility(self, df: pd.DataFrame, timeframe: str):
        """Safely compute realized volatility with error handling."""
        try:
            return compute_realized_volatility(df)
        except Exception as e:
            logger.debug("Realized volatility computation failed for %s: %s", timeframe, e)
            return None
    
    def _safe_compute_volume_ratio(self, df: pd.DataFrame, timeframe: str):
        """Safely compute volume ratio with error handling."""
        try:
            return compute_relative_volume(df)
        except Exception as e:
            logger.debug("Volume ratio computation failed for %s: %s", timeframe, e)
            return None
    
    def _safe_compute_volume_acceleration(self, df: pd.DataFrame, timeframe: str) -> Optional[Dict]:
        """Safely compute volume acceleration with mode-aware lookback."""
        try:
            accel_lookback = getattr(self._scanner_mode, 'volume_accel_lookback', 5)
            vol_accel_data = detect_volume_acceleration(df, lookback=accel_lookback)
            logger.debug(
                "📈 %s vol_accel: slope=%.3f, consec=%d, dir=%s, accelerating=%s",
                timeframe,
                vol_accel_data['acceleration'],
                vol_accel_data['consecutive_increases'],
                vol_accel_data['direction'],
                vol_accel_data['is_accelerating']
            )
            return vol_accel_data
        except Exception as e:
            logger.debug("Volume acceleration computation failed for %s: %s", timeframe, e)
            return None
    
    def _extract_stoch_values(self, stoch_rsi):
        """Extract K and D values from stoch_rsi (handles tuple or series)."""
        stoch_k_value = None
        stoch_d_value = None
        if isinstance(stoch_rsi, tuple):
            stoch_k, stoch_d = stoch_rsi
            stoch_k_value = stoch_k.iloc[-1]
            stoch_d_value = stoch_d.iloc[-1]
        else:
            stoch_k_value = stoch_rsi.iloc[-1]
        return stoch_k_value, stoch_d_value
    
    def _attach_macd_data(self, snapshot: IndicatorSnapshot, macd_line, macd_signal, macd_hist, timeframe: str):
        """Attach MACD values and series to snapshot if available."""
        if macd_line is None or macd_signal is None:
            return
        
        try:
            snapshot.macd_line = float(macd_line.iloc[-1])
            snapshot.macd_signal = float(macd_signal.iloc[-1])
            if macd_hist is not None:
                snapshot.macd_histogram = float(macd_hist.iloc[-1])
                # Store last 5 values for persistence checks
                n_persist = 5
                snapshot.macd_line_series = macd_line.iloc[-n_persist:].tolist()
                snapshot.macd_signal_series = macd_signal.iloc[-n_persist:].tolist()
                snapshot.macd_histogram_series = macd_hist.iloc[-n_persist:].tolist()
        except Exception as e:
            logger.debug("MACD series persistence failed for %s: %s", timeframe, e)


# Singleton
_indicator_service: Optional[IndicatorService] = None


def get_indicator_service() -> Optional[IndicatorService]:
    """Get the singleton IndicatorService instance."""
    return _indicator_service


def configure_indicator_service(scanner_mode=None) -> IndicatorService:
    """Configure and return the singleton IndicatorService."""
    global _indicator_service
    _indicator_service = IndicatorService(scanner_mode=scanner_mode)
    return _indicator_service
