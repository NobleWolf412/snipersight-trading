"""
SMC Trading Sessions and Kill Zones Module

Defines trading session times and "kill zones" for SMC-based trading.

STOLEN from smartmoneyconcepts library - kill zones are high-probability
windows when institutional order flow is most active:
- London Open Kill Zone: 02:00-05:00 EST (07:00-10:00 UTC)
- New York Open Kill Zone: 07:00-10:00 EST (12:00-15:00 UTC)
- Asian Session: 19:00-23:00 EST (00:00-04:00 UTC)
- London Close: 11:00-12:00 EST (16:00-17:00 UTC)

Crypto markets are 24/7 but still show patterns aligned with traditional sessions.

Integrates with smc_preset for mode-specific behavior.
"""

from typing import List, Optional, Tuple, Literal
from dataclasses import dataclass
from datetime import datetime, time, timezone
from enum import Enum
import pandas as pd


class TradingSession(str, Enum):
    """Major trading sessions."""
    ASIAN = "asian"
    LONDON = "london"
    NEW_YORK = "new_york"
    LONDON_CLOSE = "london_close"
    OVERLAP = "overlap"  # London-NY overlap


class KillZone(str, Enum):
    """High-probability kill zones."""
    LONDON_OPEN = "london_open"      # 02:00-05:00 EST
    NEW_YORK_OPEN = "new_york_open"  # 07:00-10:00 EST
    ASIAN_OPEN = "asian_open"        # 19:00-22:00 EST
    LONDON_CLOSE = "london_close"    # 11:00-12:00 EST


# Session times in EST (Eastern Standard Time / UTC-5)
# Format: (start_hour, start_minute, end_hour, end_minute)
SESSION_TIMES_EST = {
    TradingSession.ASIAN: (19, 0, 4, 0),     # 7pm-4am EST (rolls over midnight)
    TradingSession.LONDON: (2, 0, 12, 0),    # 2am-12pm EST
    TradingSession.NEW_YORK: (7, 0, 17, 0),  # 7am-5pm EST
    TradingSession.LONDON_CLOSE: (11, 0, 12, 0),  # 11am-12pm EST
    TradingSession.OVERLAP: (7, 0, 12, 0),   # 7am-12pm EST (London-NY overlap)
}

KILL_ZONE_TIMES_EST = {
    KillZone.ASIAN_OPEN: (19, 0, 22, 0),     # 7pm-10pm EST
    KillZone.LONDON_OPEN: (2, 0, 5, 0),      # 2am-5am EST
    KillZone.NEW_YORK_OPEN: (7, 0, 10, 0),   # 7am-10am EST
    KillZone.LONDON_CLOSE: (11, 0, 12, 0),   # 11am-12pm EST
}


@dataclass
class SessionInfo:
    """
    Information about the current trading session.
    
    Attributes:
        current_session: Active trading session
        in_kill_zone: Whether currently in a kill zone
        kill_zone: Which kill zone if in one
        session_progress: How far through the session (0-100%)
        session_start_price: Price at session start
        session_high: Session high so far
        session_low: Session low so far
    """
    current_session: Optional[TradingSession] = None
    in_kill_zone: bool = False
    kill_zone: Optional[KillZone] = None
    session_progress: float = 0.0
    session_start_price: Optional[float] = None
    session_high: Optional[float] = None
    session_low: Optional[float] = None
    
    @property
    def is_high_probability_time(self) -> bool:
        """Check if current time is high-probability for trading."""
        return self.in_kill_zone or self.current_session == TradingSession.OVERLAP


def _time_in_range(check_time: time, start: Tuple[int, int], end: Tuple[int, int]) -> bool:
    """
    Check if a time is within a range, handling overnight ranges.
    
    Args:
        check_time: Time to check
        start: (hour, minute) start
        end: (hour, minute) end
        
    Returns:
        bool: True if time is in range
    """
    start_time = time(start[0], start[1])
    end_time = time(end[0], end[1])
    
    if start_time <= end_time:
        # Normal range (doesn't cross midnight)
        return start_time <= check_time <= end_time
    else:
        # Crosses midnight (e.g., 19:00 to 04:00)
        return check_time >= start_time or check_time <= end_time


def get_current_session(timestamp: datetime) -> Optional[TradingSession]:
    """
    Get the active trading session for a timestamp.
    
    Args:
        timestamp: Datetime (assumed EST or will be converted)
        
    Returns:
        TradingSession or None if outside main sessions
    """
    # Convert to EST if timezone aware
    if timestamp.tzinfo is not None:
        from datetime import timedelta
        est_offset = timedelta(hours=-5)
        timestamp = timestamp.replace(tzinfo=None) + (timestamp.utcoffset() or timedelta(0)) - est_offset
    
    current_time = timestamp.time()
    
    for session, (sh, sm, eh, em) in SESSION_TIMES_EST.items():
        if _time_in_range(current_time, (sh, sm), (eh, em)):
            return session
    
    return None


def get_current_kill_zone(timestamp: datetime) -> Optional[KillZone]:
    """
    Get the active kill zone for a timestamp.
    
    Args:
        timestamp: Datetime (assumed EST or will be converted)
        
    Returns:
        KillZone or None if not in a kill zone
    """
    # Convert to EST if timezone aware
    if timestamp.tzinfo is not None:
        from datetime import timedelta
        est_offset = timedelta(hours=-5)
        timestamp = timestamp.replace(tzinfo=None) + (timestamp.utcoffset() or timedelta(0)) - est_offset
    
    current_time = timestamp.time()
    
    for kz, (sh, sm, eh, em) in KILL_ZONE_TIMES_EST.items():
        if _time_in_range(current_time, (sh, sm), (eh, em)):
            return kz
    
    return None


def get_session_info(
    df: pd.DataFrame,
    timestamp: Optional[datetime] = None
) -> SessionInfo:
    """
    Get comprehensive session information for a timestamp.
    
    Args:
        df: OHLCV DataFrame for calculating session highs/lows
        timestamp: Optional timestamp (defaults to latest candle)
        
    Returns:
        SessionInfo with current session and kill zone data
    """
    if len(df) == 0:
        return SessionInfo()
    
    if timestamp is None:
        timestamp = df.index[-1].to_pydatetime()
    
    current_session = get_current_session(timestamp)
    kill_zone = get_current_kill_zone(timestamp)
    
    # Calculate session high/low (simplified - looks at last 8 hours)
    session_start = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
    if current_session == TradingSession.ASIAN:
        session_start = session_start.replace(hour=19)
    elif current_session == TradingSession.LONDON:
        session_start = session_start.replace(hour=2)
    elif current_session == TradingSession.NEW_YORK:
        session_start = session_start.replace(hour=7)
    
    session_mask = df.index >= session_start
    session_df = df[session_mask]
    
    session_info = SessionInfo(
        current_session=current_session,
        in_kill_zone=kill_zone is not None,
        kill_zone=kill_zone,
        session_progress=0.0,
    )
    
    if len(session_df) > 0:
        session_info.session_start_price = session_df['open'].iloc[0]
        session_info.session_high = session_df['high'].max()
        session_info.session_low = session_df['low'].min()
    
    return session_info


def filter_candles_in_kill_zone(
    df: pd.DataFrame,
    kill_zone: KillZone
) -> pd.DataFrame:
    """
    Filter DataFrame to only include candles within a kill zone.
    
    Args:
        df: OHLCV DataFrame with DatetimeIndex
        kill_zone: Kill zone to filter by
        
    Returns:
        Filtered DataFrame with only kill zone candles
    """
    if kill_zone not in KILL_ZONE_TIMES_EST:
        return df
    
    sh, sm, eh, em = KILL_ZONE_TIMES_EST[kill_zone]
    
    mask = df.index.to_series().apply(
        lambda ts: _time_in_range(ts.time(), (sh, sm), (eh, em))
    )
    
    return df[mask]


def is_kill_zone_active(timestamp: datetime) -> bool:
    """Quick check if any kill zone is active."""
    return get_current_kill_zone(timestamp) is not None
