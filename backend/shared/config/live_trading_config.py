"""
Live Trading Configuration

Defines configuration and credential management for live exchange trading.
Testnet is always the default — production requires explicit opt-in.
"""

import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


@dataclass
class LiveTradingConfig:
    """
    Configuration for a live trading session on Phemex.

    All fields mirror PaperTradingConfig where applicable.
    Live-specific safety parameters are appended at the end.
    """

    # --- Shared with PaperTradingConfig ---
    exchange: str = "phemex"
    sniper_mode: str = "stealth"
    risk_per_trade: float = 1.0
    max_positions: int = 3
    leverage: int = 1
    duration_hours: int = 24
    scan_interval_minutes: int = 2
    trailing_stop: bool = True
    trailing_activation: float = 1.5
    breakeven_after_target: int = 1
    min_confluence: Optional[float] = None
    confluence_soft_floor: Optional[float] = None
    sensitivity_preset: str = "balanced"
    symbols: List[str] = field(default_factory=list)
    exclude_symbols: List[str] = field(default_factory=list)
    majors: bool = True
    altcoins: bool = False
    meme_mode: bool = False
    fee_rate: float = 0.001
    max_hours_open: float = 72.0
    max_drawdown_pct: Optional[float] = 10.0

    # --- Live-specific safety parameters ---
    testnet: bool = True                        # Default True — must be explicitly disabled
    max_position_size_usd: float = 100.0        # Hard cap per position
    max_total_exposure_usd: float = 500.0       # Hard cap on total open exposure
    min_balance_usd: float = 50.0              # Refuse orders if balance drops below this
    kill_switch_enabled: bool = True
    balance_reconcile_interval: int = 60        # Seconds between exchange balance syncs
    order_timeout_seconds: int = 30
    dry_run: bool = False                       # Log orders without sending to exchange

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LiveTradingConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def load_phemex_credentials() -> tuple[Optional[str], Optional[str]]:
    """Load Phemex API credentials from environment variables."""
    api_key = os.getenv("PHEMEX_API_KEY")
    api_secret = os.getenv("PHEMEX_API_SECRET")
    return api_key, api_secret


def is_testnet_mode() -> bool:
    """Check if testnet mode is active via environment variable."""
    return os.getenv("PHEMEX_TESTNET", "true").lower() != "false"
