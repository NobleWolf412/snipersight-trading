#!/usr/bin/env python3
"""
SniperSight Full Pipeline Backtest - Real Market Conditions Simulator

This script runs comprehensive backtests using the REAL SniperSight pipeline
across different market regimes to simulate real-world trading conditions.

Features:
- Full pipeline: SMC detection → Confluence scoring → Trade planning
- ALL sniper modes: OVERWATCH, RECON, STRIKE, SURGICAL, GHOST
- Market regime detection: UPTREND, DOWNTREND, CHOPPY, VOLATILE, RANGING
- Multiple configurations: leverage, risk levels, partial TP strategies
- Per-regime performance analysis
- Detailed debug logging for pipeline improvements

Usage:
    python scripts/backtest_full_pipeline.py
    python scripts/backtest_full_pipeline.py --mode recon --days 30
    python scripts/backtest_full_pipeline.py --compare-modes
    python scripts/backtest_full_pipeline.py --compare-configs
    python scripts/backtest_full_pipeline.py --debug

Data source:
    backend/tests/backtest/backtest_multitimeframe_5000bars.csv
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import logging
import traceback

from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode, MODES
from backend.engine.orchestrator import Orchestrator


# =============================================================================
# CONFIGURATION
# =============================================================================

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger(__name__)


class SniperMode(Enum):
    """All available sniper modes."""
    OVERWATCH = "overwatch"
    RECON = "recon"
    STRIKE = "strike"
    SURGICAL = "surgical"
    GHOST = "ghost"


class MarketRegime(Enum):
    """Market regime classifications."""
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    CHOPPY = "choppy"
    VOLATILE = "volatile"
    RANGING = "ranging"
    UNKNOWN = "unknown"


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""
    name: str = "default"
    initial_equity: float = 10000.0
    risk_fraction: float = 0.01  # 1% risk per trade
    leverage: int = 1
    use_partial_tp: bool = True  # Scale out at TP1/TP2/TP3
    tp1_close_pct: float = 0.5   # Close 50% at TP1
    tp2_close_pct: float = 0.3   # Close 30% at TP2
    tp3_close_pct: float = 0.2   # Close 20% at TP3
    max_concurrent_trades: int = 5
    max_trade_duration_hours: int = 72  # Force close after 72h
    mode: Optional[SniperMode] = None  # None = rotate all modes
    symbols: Optional[List[str]] = None  # None = all symbols


# Preset configurations to test
BACKTEST_CONFIGS = {
    "conservative": BacktestConfig(
        name="conservative",
        risk_fraction=0.005,  # 0.5% risk
        leverage=1,
        use_partial_tp=True,
    ),
    "moderate": BacktestConfig(
        name="moderate",
        risk_fraction=0.01,  # 1% risk
        leverage=2,
        use_partial_tp=True,
    ),
    "aggressive": BacktestConfig(
        name="aggressive",
        risk_fraction=0.02,  # 2% risk
        leverage=5,
        use_partial_tp=True,
    ),
    "scalper": BacktestConfig(
        name="scalper",
        risk_fraction=0.015,
        leverage=10,
        use_partial_tp=False,  # Full close at TP1
        max_trade_duration_hours=24,
    ),
}


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class TradePlan:
    """Trade plan from pipeline."""
    symbol: str
    side: str  # "long" or "short"
    mode: str
    entry_price: float
    stop_price: float
    tp1: float
    tp2: Optional[float]
    tp3: Optional[float]
    created_at: datetime
    confidence: float
    risk_reward: float
    regime: MarketRegime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeResult:
    """Result of a simulated trade."""
    plan: TradePlan
    filled: bool
    filled_at: Optional[datetime]
    exit_at: Optional[datetime]
    exit_price: float
    exit_reason: str
    pnl: float
    pnl_pct: float
    r_multiple: float
    equity_before: float
    equity_after: float
    duration_hours: float = 0.0
    partial_exits: List[Dict] = field(default_factory=list)


@dataclass
class RegimeStats:
    """Statistics for a market regime."""
    regime: MarketRegime
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    avg_r: float = 0.0
    win_rate: float = 0.0


@dataclass 
class BacktestResults:
    """Complete backtest results."""
    config: BacktestConfig
    trades: List[TradeResult]
    equity_curve: List[float]
    regime_stats: Dict[MarketRegime, RegimeStats]
    mode_stats: Dict[str, Dict]
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_r: float


# =============================================================================
# MARKET REGIME DETECTION
# =============================================================================

def detect_market_regime(df: pd.DataFrame, lookback: int = 50) -> MarketRegime:
    """
    Detect current market regime from price data.
    
    Uses multiple indicators:
    - Trend: EMA alignment and slope
    - Volatility: ATR relative to price
    - Choppiness: ADX and price range compression
    """
    if len(df) < lookback:
        return MarketRegime.UNKNOWN
    
    recent = df.tail(lookback).copy()
    close = recent['close']
    high = recent['high']
    low = recent['low']
    
    # Calculate EMAs
    ema_fast = close.ewm(span=9).mean()
    ema_mid = close.ewm(span=21).mean()
    ema_slow = close.ewm(span=50).mean()
    
    # Current values
    price = close.iloc[-1]
    ema_f = ema_fast.iloc[-1]
    ema_m = ema_mid.iloc[-1]
    ema_s = ema_slow.iloc[-1]
    
    # Trend alignment
    bullish_aligned = ema_f > ema_m > ema_s
    bearish_aligned = ema_f < ema_m < ema_s
    
    # EMA slope (momentum)
    ema_slope = (ema_mid.iloc[-1] - ema_mid.iloc[-10]) / ema_mid.iloc[-10] * 100
    
    # ATR for volatility
    tr = pd.concat([
        high - low,
        abs(high - close.shift(1)),
        abs(low - close.shift(1))
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]
    atr_pct = (atr / price) * 100
    
    # Price range compression (choppiness)
    highest = high.rolling(20).max().iloc[-1]
    lowest = low.rolling(20).min().iloc[-1]
    range_pct = (highest - lowest) / lowest * 100
    
    # Directional movement
    returns = close.pct_change().dropna()
    pos_returns = (returns > 0).sum()
    neg_returns = (returns < 0).sum()
    direction_bias = pos_returns / len(returns) if len(returns) > 0 else 0.5
    
    # Classification logic
    if atr_pct > 3.0:  # High volatility
        return MarketRegime.VOLATILE
    
    if range_pct < 5.0 and abs(ema_slope) < 1.0:  # Tight range, no momentum
        return MarketRegime.RANGING
    
    if bullish_aligned and ema_slope > 1.5 and direction_bias > 0.55:
        return MarketRegime.UPTREND
    
    if bearish_aligned and ema_slope < -1.5 and direction_bias < 0.45:
        return MarketRegime.DOWNTREND
    
    # Check for choppiness (frequent direction changes)
    direction_changes = (returns.shift(1) * returns < 0).sum()
    chop_ratio = direction_changes / len(returns) if len(returns) > 0 else 0
    
    if chop_ratio > 0.45 or (not bullish_aligned and not bearish_aligned):
        return MarketRegime.CHOPPY
    
    return MarketRegime.UNKNOWN


def analyze_regime_periods(
    df: pd.DataFrame,
    window_hours: int = 24
) -> List[Tuple[datetime, datetime, MarketRegime]]:
    """
    Analyze data and identify regime periods.
    Returns list of (start, end, regime) tuples.
    """
    periods = []
    
    if len(df) < 100:
        return periods
    
    step = window_hours
    current_regime = None
    period_start = None
    
    for i in range(50, len(df), step):
        ts = df.index[i]
        regime = detect_market_regime(df.iloc[:i+1])
        
        if regime != current_regime:
            if current_regime is not None and period_start is not None:
                periods.append((period_start, ts, current_regime))
            current_regime = regime
            period_start = ts
    
    if current_regime is not None and period_start is not None:
        periods.append((period_start, df.index[-1], current_regime))
    
    return periods


# =============================================================================
# CSV DATA ADAPTER
# =============================================================================

class CSVDataAdapter:
    """Adapter providing historical CSV data to the orchestrator."""
    
    def __init__(self, all_data: Dict[str, Dict[str, pd.DataFrame]], current_ts: datetime):
        self.all_data = all_data
        self.current_ts = current_ts
        self._request_log = []
    
    def set_timestamp(self, ts: datetime):
        self.current_ts = ts
    
    def fetch_ohlcv(
        self, 
        symbol: str, 
        timeframe: str, 
        limit: int = 500,
        since: Optional[int] = None
    ) -> pd.DataFrame:
        """Fetch OHLCV data up to current simulation timestamp."""
        symbol_key = symbol.replace('/', '')
        tf_key = timeframe.lower()
        
        if symbol_key not in self.all_data:
            for key in self.all_data.keys():
                if symbol_key in key or key in symbol_key:
                    symbol_key = key
                    break
            else:
                logger.debug(f"Symbol {symbol} not found")
                return pd.DataFrame()
        
        if tf_key not in self.all_data[symbol_key]:
            logger.debug(f"Timeframe {timeframe} not found for {symbol_key}")
            return pd.DataFrame()
        
        df = self.all_data[symbol_key][tf_key].copy()
        df = df[df.index <= self.current_ts]
        df = df.tail(limit).reset_index()
        
        self._request_log.append({
            'symbol': symbol,
            'timeframe': timeframe,
            'ts': self.current_ts,
            'rows': len(df)
        })
        
        return df
    
    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get current price at simulation time."""
        symbol_key = symbol.replace('/', '')
        
        if symbol_key in self.all_data and '1h' in self.all_data[symbol_key]:
            df = self.all_data[symbol_key]['1h']
            df_filtered = df[df.index <= self.current_ts]
            if not df_filtered.empty:
                price = df_filtered['close'].iloc[-1]
                return {'last': price, 'bid': price * 0.9999, 'ask': price * 1.0001}
        return {'last': 0, 'bid': 0, 'ask': 0}
    
    def get_regime_at_time(self, symbol: str, ts: datetime) -> MarketRegime:
        """Get market regime for a symbol at a specific time."""
        symbol_key = symbol.replace('/', '')
        
        if symbol_key in self.all_data and '1h' in self.all_data[symbol_key]:
            df = self.all_data[symbol_key]['1h']
            df_filtered = df[df.index <= ts]
            if len(df_filtered) >= 50:
                return detect_market_regime(df_filtered)
        
        return MarketRegime.UNKNOWN


# =============================================================================
# DATA LOADING
# =============================================================================

def load_csv_data(csv_path: str) -> Dict[str, Dict[str, pd.DataFrame]]:
    """Load multi-timeframe CSV data."""
    print(f"📂 Loading: {csv_path}")
    
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    symbols = df['symbol'].unique()
    timeframes = df['timeframe'].unique()
    
    print(f"   Rows: {len(df):,}")
    print(f"   Symbols: {list(symbols)}")
    print(f"   Timeframes: {list(timeframes)}")
    
    all_data: Dict[str, Dict[str, pd.DataFrame]] = {}
    
    for symbol in symbols:
        all_data[symbol] = {}
        symbol_df = df[df['symbol'] == symbol]
        
        for tf in timeframes:
            tf_df = symbol_df[symbol_df['timeframe'] == tf].copy()
            if len(tf_df) == 0:
                continue
            
            tf_df = tf_df.sort_values('timestamp')
            tf_df.set_index('timestamp', inplace=True)
            tf_df = tf_df[['open', 'high', 'low', 'close', 'volume']].copy()
            all_data[symbol][tf] = tf_df
    
    return all_data


# =============================================================================
# PIPELINE INTEGRATION
# =============================================================================

def run_pipeline(
    symbols: List[str],
    adapter: CSVDataAdapter,
    mode: SniperMode,
    debug: bool = False
) -> Tuple[List[TradePlan], Dict]:
    """
    Run the REAL SniperSight orchestrator pipeline.
    """
    debug_info = {
        'mode': mode.value,
        'timestamp': adapter.current_ts,
        'symbols_scanned': len(symbols),
        'signals_generated': 0,
        'rejections': {},
        'errors': [],
    }
    
    try:
        mode_config = get_mode(mode.value)
        
        cfg = ScanConfig(profile=mode.value)
        cfg.min_confluence_score = mode_config.min_confluence_score
        cfg.primary_planning_timeframe = mode_config.primary_planning_timeframe.lower()
        cfg.entry_timeframes = tuple(tf.lower() for tf in mode_config.entry_timeframes)
        cfg.structure_timeframes = tuple(tf.lower() for tf in mode_config.structure_timeframes)
        
        if debug:
            logger.info(f"Pipeline: mode={mode.value}, min_score={cfg.min_confluence_score}")
        
        orch = Orchestrator(
            config=cfg,
            exchange_adapter=adapter,
            debug_mode=debug,
            concurrency_workers=1
        )
        
        plans, rejections = orch.scan(symbols)
        
        debug_info['rejections'] = rejections
        debug_info['signals_generated'] = len(plans)
        
        trade_plans = []
        for plan in plans:
            regime = adapter.get_regime_at_time(plan.symbol, adapter.current_ts)
            
            trade_plan = TradePlan(
                symbol=plan.symbol,
                side="long" if plan.direction == "LONG" else "short",
                mode=mode.value,
                entry_price=(plan.entry_zone.near_entry + plan.entry_zone.far_entry) / 2,
                stop_price=plan.stop_loss.level,
                tp1=plan.targets[0].level if len(plan.targets) > 0 else 0,
                tp2=plan.targets[1].level if len(plan.targets) > 1 else None,
                tp3=plan.targets[2].level if len(plan.targets) > 2 else None,
                created_at=adapter.current_ts,
                confidence=plan.confidence_score,
                risk_reward=plan.risk_reward,
                regime=regime,
                metadata={
                    'rationale': plan.rationale[:300] if plan.rationale else "",
                    'entry_zone_near': plan.entry_zone.near_entry,
                    'entry_zone_far': plan.entry_zone.far_entry,
                }
            )
            trade_plans.append(trade_plan)
            
            if debug:
                logger.info(f"Signal: {plan.symbol} {plan.direction} | Conf: {plan.confidence_score:.1f}% | R:R: {plan.risk_reward:.2f}")
        
        return trade_plans, debug_info
        
    except Exception as e:
        debug_info['errors'].append(str(e))
        if debug:
            logger.error(f"Pipeline error: {e}")
            traceback.print_exc()
        return [], debug_info


# =============================================================================
# TRADE SIMULATION
# =============================================================================

def simulate_trade(
    plan: TradePlan,
    price_data: pd.DataFrame,
    config: BacktestConfig,
    equity_before: float
) -> TradeResult:
    """Simulate a trade with partial TP support."""
    is_long = plan.side == "long"
    
    future_data = price_data[price_data.index >= plan.created_at].copy()
    
    if future_data.empty:
        return TradeResult(
            plan=plan, filled=False, filled_at=None, exit_at=None,
            exit_price=0, exit_reason="NO_DATA", pnl=0, pnl_pct=0,
            r_multiple=0, equity_before=equity_before, equity_after=equity_before
        )
    
    entry = plan.entry_price
    stop = plan.stop_price
    risk_distance = abs(entry - stop)
    
    if risk_distance == 0:
        return TradeResult(
            plan=plan, filled=False, filled_at=None, exit_at=None,
            exit_price=0, exit_reason="INVALID_PLAN", pnl=0, pnl_pct=0,
            r_multiple=0, equity_before=equity_before, equity_after=equity_before
        )
    
    risk_amount = equity_before * config.risk_fraction
    base_position_size = risk_amount / risk_distance
    position_size = base_position_size * config.leverage
    
    # Wait for entry fill
    filled = False
    filled_at = None
    
    for idx, candle in future_data.iterrows():
        if candle['low'] <= entry <= candle['high']:
            filled = True
            filled_at = idx
            break
    
    if not filled:
        return TradeResult(
            plan=plan, filled=False, filled_at=None, exit_at=None,
            exit_price=0, exit_reason="NOT_FILLED", pnl=0, pnl_pct=0,
            r_multiple=0, equity_before=equity_before, equity_after=equity_before
        )
    
    post_fill = future_data[future_data.index > filled_at]
    max_duration = timedelta(hours=config.max_trade_duration_hours)
    
    remaining_position = 1.0
    realized_pnl = 0.0
    partial_exits = []
    exit_price = entry
    exit_at = filled_at
    exit_reason = "TIMEOUT"
    
    tp_levels = [
        (plan.tp1, config.tp1_close_pct, "TP1"),
    ]
    if plan.tp2 and config.use_partial_tp:
        tp_levels.append((plan.tp2, config.tp2_close_pct, "TP2"))
    if plan.tp3 and config.use_partial_tp:
        tp_levels.append((plan.tp3, config.tp3_close_pct, "TP3"))
    
    tp_hit_flags = {t[2]: False for t in tp_levels}
    
    for idx, candle in post_fill.iterrows():
        if idx - filled_at > max_duration:
            exit_price = candle['close']
            exit_at = idx
            exit_reason = "TIMEOUT"
            break
        
        low, high, close = candle['low'], candle['high'], candle['close']
        
        # Check stop loss first
        sl_hit = (low <= stop) if is_long else (high >= stop)
        if sl_hit:
            exit_price = stop
            exit_at = idx
            exit_reason = "SL"
            if is_long:
                realized_pnl += (stop - entry) * position_size * remaining_position
            else:
                realized_pnl += (entry - stop) * position_size * remaining_position
            remaining_position = 0
            break
        
        # Check TPs
        if config.use_partial_tp:
            for tp_price, close_pct, tp_name in tp_levels:
                if remaining_position <= 0 or tp_hit_flags[tp_name]:
                    continue
                
                tp_hit = (high >= tp_price) if is_long else (low <= tp_price)
                if tp_hit:
                    close_amount = min(close_pct, remaining_position)
                    if is_long:
                        partial_pnl = (tp_price - entry) * position_size * close_amount
                    else:
                        partial_pnl = (entry - tp_price) * position_size * close_amount
                    
                    realized_pnl += partial_pnl
                    remaining_position -= close_amount
                    tp_hit_flags[tp_name] = True
                    
                    partial_exits.append({
                        'level': tp_name,
                        'price': tp_price,
                        'pnl': partial_pnl,
                        'time': idx
                    })
                    
                    if remaining_position <= 0.01:
                        exit_price = tp_price
                        exit_at = idx
                        exit_reason = tp_name
                        break
        else:
            # Full close at TP1
            tp1_hit = (high >= plan.tp1) if is_long else (low <= plan.tp1)
            if tp1_hit:
                exit_price = plan.tp1
                exit_at = idx
                exit_reason = "TP1"
                if is_long:
                    realized_pnl = (plan.tp1 - entry) * position_size
                else:
                    realized_pnl = (entry - plan.tp1) * position_size
                remaining_position = 0
                break
        
        if remaining_position <= 0.01:
            break
    
    # Handle remaining position on timeout
    if remaining_position > 0.01:
        final_price = post_fill['close'].iloc[-1] if not post_fill.empty else entry
        if is_long:
            realized_pnl += (final_price - entry) * position_size * remaining_position
        else:
            realized_pnl += (entry - final_price) * position_size * remaining_position
        exit_price = final_price
        exit_at = post_fill.index[-1] if not post_fill.empty else filled_at
    
    pnl = realized_pnl
    pnl_pct = (pnl / equity_before) * 100 if equity_before > 0 else 0
    r_multiple = pnl / risk_amount if risk_amount > 0 else 0
    equity_after = equity_before + pnl
    
    duration = (exit_at - filled_at).total_seconds() / 3600 if exit_at and filled_at else 0
    
    return TradeResult(
        plan=plan,
        filled=True,
        filled_at=filled_at,
        exit_at=exit_at,
        exit_price=exit_price,
        exit_reason=exit_reason,
        pnl=pnl,
        pnl_pct=pnl_pct,
        r_multiple=r_multiple,
        equity_before=equity_before,
        equity_after=equity_after,
        duration_hours=duration,
        partial_exits=partial_exits
    )


# =============================================================================
# SESSION GENERATION
# =============================================================================

def generate_sessions(
    start: datetime,
    end: datetime,
    modes: List[SniperMode],
    hours: List[int] = [9, 14, 20],
    every_n_days: int = 1
) -> List[Tuple[datetime, SniperMode]]:
    """Generate scan sessions with mode rotation."""
    sessions = []
    current = start.replace(hour=0, minute=0, second=0, microsecond=0)
    day_count = 0
    mode_idx = 0
    
    while current < end:
        if day_count % every_n_days == 0:
            for hour in hours:
                ts = current.replace(hour=hour)
                if start <= ts <= end:
                    mode = modes[mode_idx % len(modes)]
                    sessions.append((ts, mode))
                    mode_idx += 1
        
        current += timedelta(days=1)
        day_count += 1
    
    return sessions


# =============================================================================
# MAIN BACKTEST RUNNER
# =============================================================================

def run_backtest(
    csv_path: str,
    config: BacktestConfig,
    backtest_days: int = 60,
    debug: bool = False
) -> BacktestResults:
    """Run full backtest with given configuration."""
    
    print("=" * 70)
    print(f"🎯 SNIPERSIGHT BACKTEST: {config.name.upper()}")
    print("=" * 70)
    print(f"   Risk: {config.risk_fraction*100:.1f}% | Leverage: {config.leverage}x | Partial TP: {config.use_partial_tp}")
    
    all_data = load_csv_data(csv_path)
    if not all_data:
        raise ValueError("No data loaded!")
    
    symbols = config.symbols
    if symbols is None:
        symbols = []
        for s in all_data.keys():
            if 'USDT' in s:
                formatted = s.replace('USDT', '/USDT')
            else:
                formatted = s
            symbols.append(formatted)
    
    print(f"\n📊 Symbols: {symbols}")
    
    first_sym = list(all_data.keys())[0]
    ref_df = all_data[first_sym].get('1h', list(all_data[first_sym].values())[0])
    data_start = ref_df.index.min()
    data_end = ref_df.index.max()
    
    bt_start = max(data_start + timedelta(days=30), data_end - timedelta(days=backtest_days))
    bt_end = data_end - timedelta(days=3)
    
    print(f"📅 Data: {data_start.date()} to {data_end.date()}")
    print(f"📅 Backtest: {bt_start.date()} to {bt_end.date()}")
    
    print("\n📈 Analyzing market regimes...")
    regime_periods = analyze_regime_periods(ref_df)
    regime_counts = {}
    for _, _, regime in regime_periods:
        regime_counts[regime.value] = regime_counts.get(regime.value, 0) + 1
    print(f"   Regime distribution: {regime_counts}")
    
    modes = [config.mode] if config.mode else list(SniperMode)
    sessions = generate_sessions(bt_start, bt_end, modes, every_n_days=1)
    print(f"\n🔄 Sessions: {len(sessions)}")
    
    adapter = CSVDataAdapter(all_data, bt_start)
    equity = config.initial_equity
    equity_curve = [equity]
    all_results: List[TradeResult] = []
    
    regime_stats: Dict[MarketRegime, RegimeStats] = {r: RegimeStats(r) for r in MarketRegime}
    mode_stats: Dict[str, Dict] = {}
    
    print("\n" + "-" * 70)
    print("Running backtest...")
    print("-" * 70)
    
    for i, (session_ts, mode) in enumerate(sessions):
        adapter.set_timestamp(session_ts)
        
        plans, debug_info = run_pipeline(symbols, adapter, mode, debug=debug)
        
        if plans:
            print(f"\n[{i+1}/{len(sessions)}] {session_ts.strftime('%Y-%m-%d %H:%M')} | "
                  f"{mode.value.upper()} | Signals: {len(plans)}")
        
        for plan in plans:
            open_trades = len([r for r in all_results if r.filled and r.exit_at and r.exit_at > session_ts])
            if open_trades >= config.max_concurrent_trades:
                continue
            
            symbol_key = plan.symbol.replace('/', '')
            sim_tf = '1h' if '1h' in all_data.get(symbol_key, {}) else '5m'
            
            if symbol_key not in all_data or sim_tf not in all_data[symbol_key]:
                continue
            
            result = simulate_trade(plan, all_data[symbol_key][sim_tf], config, equity)
            all_results.append(result)
            
            if result.filled:
                equity = result.equity_after
                equity_curve.append(equity)
                
                regime_stats[plan.regime].total_trades += 1
                regime_stats[plan.regime].total_pnl += result.pnl
                if result.pnl > 0:
                    regime_stats[plan.regime].wins += 1
                else:
                    regime_stats[plan.regime].losses += 1
                
                if plan.mode not in mode_stats:
                    mode_stats[plan.mode] = {'trades': 0, 'wins': 0, 'pnl': 0.0, 'r_sum': 0.0}
                mode_stats[plan.mode]['trades'] += 1
                mode_stats[plan.mode]['pnl'] += result.pnl
                mode_stats[plan.mode]['r_sum'] += result.r_multiple
                if result.pnl > 0:
                    mode_stats[plan.mode]['wins'] += 1
                
                emoji = "✅" if result.pnl > 0 else "❌"
                regime_str = plan.regime.value[:4].upper()
                print(f"   {emoji} {plan.symbol} {plan.side.upper()} [{regime_str}]: "
                      f"${result.pnl:+.2f} ({result.r_multiple:+.2f}R) | {result.exit_reason}")
    
    filled_trades = [r for r in all_results if r.filled]
    total_trades = len(filled_trades)
    wins = len([r for r in filled_trades if r.pnl > 0])
    
    final_equity = equity_curve[-1]
    total_return = ((final_equity - config.initial_equity) / config.initial_equity) * 100
    
    peak = config.initial_equity
    max_dd = 0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        max_dd = max(max_dd, dd)
    
    gross_profit = sum(r.pnl for r in filled_trades if r.pnl > 0)
    gross_loss = abs(sum(r.pnl for r in filled_trades if r.pnl < 0))
    pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    win_rate = wins / total_trades * 100 if total_trades > 0 else 0
    avg_r = np.mean([r.r_multiple for r in filled_trades]) if filled_trades else 0
    
    for regime in regime_stats.values():
        if regime.total_trades > 0:
            regime.win_rate = regime.wins / regime.total_trades * 100
    
    return BacktestResults(
        config=config,
        trades=all_results,
        equity_curve=equity_curve,
        regime_stats=regime_stats,
        mode_stats=mode_stats,
        final_equity=final_equity,
        total_return_pct=total_return,
        max_drawdown_pct=max_dd,
        win_rate=win_rate,
        profit_factor=pf,
        total_trades=total_trades,
        avg_r=avg_r
    )


# =============================================================================
# REPORTING
# =============================================================================

def print_results(results: BacktestResults):
    """Print comprehensive results."""
    
    print("\n" + "=" * 70)
    print("📊 BACKTEST RESULTS")
    print("=" * 70)
    
    print(f"\n  Configuration: {results.config.name}")
    print(f"  Risk: {results.config.risk_fraction*100:.1f}% | Leverage: {results.config.leverage}x")
    print("-" * 70)
    
    print(f"  Initial Equity:    ${results.config.initial_equity:>12,.2f}")
    print(f"  Final Equity:      ${results.final_equity:>12,.2f}")
    print(f"  Total Return:      {results.total_return_pct:>12.2f}%")
    print(f"  Max Drawdown:      {results.max_drawdown_pct:>12.2f}%")
    print("-" * 70)
    
    print(f"  Total Trades:      {results.total_trades:>12}")
    print(f"  Win Rate:          {results.win_rate:>12.1f}%")
    print(f"  Profit Factor:     {results.profit_factor:>12.2f}")
    print(f"  Average R:         {results.avg_r:>12.2f}")
    
    print("\n📈 BY MARKET REGIME:")
    print("-" * 70)
    for regime, stats in results.regime_stats.items():
        if stats.total_trades > 0:
            emoji = "✅" if stats.total_pnl > 0 else "❌"
            print(f"  {emoji} {regime.value:<12}: {stats.total_trades:>3} trades | "
                  f"WR: {stats.win_rate:>5.1f}% | P&L: ${stats.total_pnl:>+10.2f}")
    
    print("\n🎯 BY SNIPER MODE:")
    print("-" * 70)
    for mode, stats in sorted(results.mode_stats.items()):
        if stats['trades'] > 0:
            wr = stats['wins'] / stats['trades'] * 100
            avg_r = stats['r_sum'] / stats['trades']
            emoji = "✅" if stats['pnl'] > 0 else "❌"
            print(f"  {emoji} {mode.upper():<12}: {stats['trades']:>3} trades | "
                  f"WR: {wr:>5.1f}% | P&L: ${stats['pnl']:>+10.2f} | Avg R: {avg_r:+.2f}")
    
    print("\n🚪 BY EXIT REASON:")
    print("-" * 70)
    exit_stats = {}
    for r in results.trades:
        if r.filled:
            reason = r.exit_reason
            if reason not in exit_stats:
                exit_stats[reason] = {'count': 0, 'pnl': 0.0}
            exit_stats[reason]['count'] += 1
            exit_stats[reason]['pnl'] += r.pnl
    
    for reason, stats in exit_stats.items():
        emoji = "🎯" if "TP" in reason else ("❌" if reason == "SL" else "⏱️")
        print(f"  {emoji} {reason:<12}: {stats['count']:>3} trades | P&L: ${stats['pnl']:>+10.2f}")
    
    print("=" * 70)


def compare_modes(csv_path: str, backtest_days: int = 30) -> Dict[str, BacktestResults]:
    """Run backtest for each mode separately and compare."""
    print("\n" + "=" * 70)
    print("🔬 MODE COMPARISON TEST")
    print("=" * 70)
    
    results = {}
    
    for mode in SniperMode:
        print(f"\n--- Testing {mode.value.upper()} ---")
        config = BacktestConfig(name=f"mode_{mode.value}", mode=mode)
        
        try:
            result = run_backtest(csv_path, config, backtest_days, debug=False)
            results[mode.value] = result
        except Exception as e:
            print(f"   Error: {e}")
    
    print("\n" + "=" * 70)
    print("📊 MODE COMPARISON SUMMARY")
    print("=" * 70)
    print(f"{'Mode':<12} {'Trades':>8} {'WR%':>8} {'Return%':>10} {'MaxDD%':>10} {'PF':>8}")
    print("-" * 70)
    
    for mode, result in sorted(results.items(), key=lambda x: -x[1].total_return_pct):
        emoji = "✅" if result.total_return_pct > 0 else "❌"
        print(f"{emoji} {mode:<10} {result.total_trades:>8} {result.win_rate:>7.1f}% "
              f"{result.total_return_pct:>+9.2f}% {result.max_drawdown_pct:>9.2f}% "
              f"{result.profit_factor:>7.2f}")
    
    return results


def compare_configs(csv_path: str, backtest_days: int = 30) -> Dict[str, BacktestResults]:
    """Test different configurations."""
    print("\n" + "=" * 70)
    print("🔬 CONFIGURATION COMPARISON TEST")
    print("=" * 70)
    
    results = {}
    
    for name, config in BACKTEST_CONFIGS.items():
        print(f"\n--- Testing {name.upper()} ---")
        try:
            result = run_backtest(csv_path, config, backtest_days, debug=False)
            results[name] = result
        except Exception as e:
            print(f"   Error: {e}")
    
    print("\n" + "=" * 70)
    print("📊 CONFIG COMPARISON SUMMARY")
    print("=" * 70)
    print(f"{'Config':<12} {'Risk%':>6} {'Lev':>4} {'Trades':>7} {'Return%':>10} {'MaxDD%':>10}")
    print("-" * 70)
    
    for name, result in sorted(results.items(), key=lambda x: -x[1].total_return_pct):
        emoji = "✅" if result.total_return_pct > 0 else "❌"
        print(f"{emoji} {name:<10} {result.config.risk_fraction*100:>5.1f}% {result.config.leverage:>3}x "
              f"{result.total_trades:>7} {result.total_return_pct:>+9.2f}% {result.max_drawdown_pct:>9.2f}%")
    
    return results


def save_results(results: BacktestResults, output_path: str):
    """Save trade log to CSV."""
    rows = []
    for r in results.trades:
        rows.append({
            'symbol': r.plan.symbol,
            'mode': r.plan.mode,
            'side': r.plan.side,
            'regime': r.plan.regime.value,
            'entry': r.plan.entry_price,
            'stop': r.plan.stop_price,
            'tp1': r.plan.tp1,
            'tp2': r.plan.tp2,
            'tp3': r.plan.tp3,
            'confidence': r.plan.confidence,
            'risk_reward': r.plan.risk_reward,
            'created_at': r.plan.created_at,
            'filled': r.filled,
            'filled_at': r.filled_at,
            'exit_at': r.exit_at,
            'exit_price': r.exit_price,
            'exit_reason': r.exit_reason,
            'pnl': r.pnl,
            'pnl_pct': r.pnl_pct,
            'r_multiple': r.r_multiple,
            'duration_hours': r.duration_hours,
            'equity_before': r.equity_before,
            'equity_after': r.equity_after,
        })
    
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"\n📁 Trade log saved: {output_path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='SniperSight Full Pipeline Backtest')
    parser.add_argument('--mode', type=str, help='Single mode to test (overwatch/recon/strike/surgical/ghost)')
    parser.add_argument('--days', type=int, default=30, help='Backtest days')
    parser.add_argument('--risk', type=float, default=0.01, help='Risk fraction (0.01 = 1%%)')
    parser.add_argument('--leverage', type=int, default=1, help='Leverage multiplier')
    parser.add_argument('--compare-modes', action='store_true', help='Compare all modes')
    parser.add_argument('--compare-configs', action='store_true', help='Compare preset configs')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    csv_path = project_root / "backend" / "tests" / "backtest" / "backtest_multitimeframe_5000bars.csv"
    
    if not csv_path.exists():
        print(f"❌ CSV not found: {csv_path}")
        return
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.compare_modes:
        results = compare_modes(str(csv_path), args.days)
    elif args.compare_configs:
        results = compare_configs(str(csv_path), args.days)
    else:
        config = BacktestConfig(
            name="custom" if args.mode else "default",
            risk_fraction=args.risk,
            leverage=args.leverage,
            mode=SniperMode(args.mode) if args.mode else None
        )
        
        results = run_backtest(str(csv_path), config, args.days, args.debug)
        print_results(results)
        
        output_path = project_root / "scripts" / "backtest_trades.csv"
        save_results(results, str(output_path))


if __name__ == "__main__":
    main()
