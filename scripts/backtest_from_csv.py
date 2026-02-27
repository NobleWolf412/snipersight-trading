#!/usr/bin/env python3
"""
SniperSight Full Pipeline Backtest from CSV Data

This script runs a comprehensive backtest using the REAL SniperSight pipeline
(same as "Arm Scanner") but with CSV price data instead of live exchange feeds.

Features:
- Uses the real Orchestrator pipeline with all SMC detection, confluence scoring
- Simulates scans 3x per day (09:00, 14:00, 20:00) every other day
- Tests multiple sniper modes in rotation (OVERWATCH, BALANCED, SCALP, SWING)
- Computes profit, equity curve, win rate, and per-mode statistics
- Outputs detailed trade log to CSV

Usage:
    python scripts/backtest_from_csv.py

Data source:
    Uses backend/tests/backtest/backtest_multitimeframe_5000bars.csv
    (multi-symbol, multi-timeframe OHLCV data)
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import logging

from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode, MODES
from backend.engine.orchestrator import Orchestrator
from backend.shared.models.planner import TradePlan

# Configure logging
logging.basicConfig(level=logging.WARNING)  # Reduce noise from pipeline
logger = logging.getLogger(__name__)


# =============================================================================
# SNIPER MODES
# =============================================================================

class SniperMode(Enum):
    """Sniper trading modes."""
    OVERWATCH = "overwatch"
    RECON = "recon"
    STRIKE = "strike"
    SURGICAL = "surgical"

# Mode rotation pattern for sessions
MODE_ROTATION = [
    SniperMode.OVERWATCH,
    SniperMode.RECON,
    SniperMode.STRIKE,
    SniperMode.SURGICAL,
]


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class SimpleTradePlan:
    """Simplified trade plan for backtest tracking."""
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
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeResult:
    """Result of a simulated trade."""
    plan: SimpleTradePlan
    filled: bool
    filled_at: Optional[datetime]
    exit_at: Optional[datetime]
    exit_price: float
    exit_reason: str  # "TP1", "TP2", "TP3", "SL", "TIMEOUT", "NOT_FILLED"
    pnl: float
    r_multiple: float
    equity_before: float
    equity_after: float


# =============================================================================
# CSV DATA ADAPTER
# =============================================================================

class CSVDataAdapter:
    """
    Adapter that provides historical data from CSV for the orchestrator.
    Implements the same interface as exchange adapters (fetch_ohlcv, fetch_ticker).
    """
    
    def __init__(self, all_data: Dict[str, Dict[str, pd.DataFrame]], current_ts: datetime):
        """
        Args:
            all_data: Dict of symbol -> timeframe -> full DataFrame
            current_ts: Current simulation timestamp (only data <= this is visible)
        """
        self.all_data = all_data
        self.current_ts = current_ts
    
    def set_timestamp(self, ts: datetime):
        """Move simulation time."""
        self.current_ts = ts
    
    def fetch_ohlcv(
        self, 
        symbol: str, 
        timeframe: str, 
        limit: int = 500,
        since: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data up to current simulation timestamp.
        Returns data in the same format as exchange adapters.
        """
        # Normalize symbol (BTC/USDT -> BTCUSDT)
        symbol_key = symbol.replace('/', '')
        
        if symbol_key not in self.all_data:
            # Try to find matching symbol
            for key in self.all_data.keys():
                if symbol_key in key or key in symbol_key:
                    symbol_key = key
                    break
            else:
                logger.warning(f"Symbol {symbol} not found in CSV data")
                return pd.DataFrame()
        
        # Normalize timeframe (1H -> 1h)
        tf_key = timeframe.lower()
        
        if tf_key not in self.all_data[symbol_key]:
            logger.warning(f"Timeframe {timeframe} not found for {symbol_key}")
            return pd.DataFrame()
        
        df = self.all_data[symbol_key][tf_key].copy()
        
        # Filter to only data up to current timestamp
        df = df[df.index <= self.current_ts]
        
        # Return last `limit` candles
        df = df.tail(limit).reset_index()
        
        return df
    
    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get current price at simulation time."""
        symbol_key = symbol.replace('/', '')
        
        if symbol_key in self.all_data and '1h' in self.all_data[symbol_key]:
            df = self.all_data[symbol_key]['1h']
            df_filtered = df[df.index <= self.current_ts]
            if not df_filtered.empty:
                price = df_filtered['close'].iloc[-1]
                return {
                    'last': price,
                    'bid': price * 0.9999,
                    'ask': price * 1.0001,
                    'symbol': symbol
                }
        return {'last': 0, 'bid': 0, 'ask': 0, 'symbol': symbol}


# =============================================================================
# DATA LOADING
# =============================================================================

def load_csv_data(csv_path: str) -> Dict[str, Dict[str, pd.DataFrame]]:
    """
    Load multi-timeframe CSV data into Dict[symbol][timeframe] format.
    
    CSV format: timestamp,symbol,timeframe,exchange,open,high,low,close,volume
    """
    print(f"📂 Loading data from: {csv_path}")
    
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    print(f"   Total rows: {len(df):,}")
    
    # Get unique symbols and timeframes
    symbols = df['symbol'].unique()
    timeframes = df['timeframe'].unique()
    
    print(f"   Symbols: {list(symbols)}")
    print(f"   Timeframes: {list(timeframes)}")
    
    # Build nested dict structure
    all_data: Dict[str, Dict[str, pd.DataFrame]] = {}
    
    for symbol in symbols:
        all_data[symbol] = {}
        symbol_df = df[df['symbol'] == symbol]
        
        for tf in timeframes:
            tf_df = symbol_df[symbol_df['timeframe'] == tf].copy()
            
            if len(tf_df) == 0:
                continue
            
            # Sort and set index
            tf_df = tf_df.sort_values('timestamp')
            tf_df.set_index('timestamp', inplace=True)
            
            # Keep only OHLCV columns
            tf_df = tf_df[['open', 'high', 'low', 'close', 'volume']].copy()
            
            all_data[symbol][tf] = tf_df
        
        print(f"   ✓ {symbol}: {len(all_data[symbol])} timeframes")
    
    return all_data


def get_mtf_snapshot(
    all_data: Dict[str, Dict[str, pd.DataFrame]],
    symbol: str,
    snapshot_ts: datetime,
    limit: int = 500
) -> Dict[str, pd.DataFrame]:
    """
    Get multi-timeframe snapshot for a symbol at a given timestamp.
    Returns only data with timestamp <= snapshot_ts.
    """
    snapshot = {}
    symbol_data = all_data.get(symbol, {})
    
    for tf, df in symbol_data.items():
        filtered = df[df.index <= snapshot_ts].tail(limit)
        if not filtered.empty:
            snapshot[tf] = filtered
    
    return snapshot


# =============================================================================
# PIPELINE INTEGRATION
# =============================================================================

def run_snipersight_pipeline(
    symbols: List[str],
    adapter: CSVDataAdapter,
    mode: SniperMode
) -> List[SimpleTradePlan]:
    """
    Run the REAL SniperSight orchestrator pipeline.
    
    Args:
        symbols: List of symbols to scan (e.g., ["BTC/USDT"])
        adapter: CSV data adapter with current timestamp set
        mode: Sniper mode to use
        
    Returns:
        List of SimpleTradePlan objects
    """
    try:
        # Get mode config
        mode_config = get_mode(mode.value)
        
        # Configure scan
        cfg = ScanConfig(profile=mode.value)
        cfg.min_confluence_score = mode_config.min_confluence_score
        cfg.primary_planning_timeframe = mode_config.primary_planning_timeframe.lower()
        cfg.entry_timeframes = tuple(tf.lower() for tf in mode_config.entry_timeframes)
        cfg.structure_timeframes = tuple(tf.lower() for tf in mode_config.structure_timeframes)
        
        # Create orchestrator with CSV adapter
        orch = Orchestrator(
            config=cfg,
            exchange_adapter=adapter,
            debug_mode=False,
            concurrency_workers=1
        )
        
        # Run scan
        plans, rejections = orch.scan(symbols)
        
        # Convert to SimpleTradePlan
        simple_plans = []
        for plan in plans:
            simple_plan = SimpleTradePlan(
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
                metadata={
                    "rationale": plan.rationale[:200] if plan.rationale else "",
                    "rejection_count": rejections.get('total_rejected', 0)
                }
            )
            simple_plans.append(simple_plan)
        
        return simple_plans
        
    except Exception as e:
        logger.warning(f"Pipeline error for mode {mode.value}: {e}")
        return []


# =============================================================================
# SESSION GENERATION
# =============================================================================

def generate_sessions(
    start_date: datetime,
    end_date: datetime,
    session_hours: List[int] = [9, 14, 20]
) -> List[Tuple[datetime, SniperMode]]:
    """
    Generate scan sessions for the backtest period.
    
    Args:
        start_date: Start of backtest window
        end_date: End of backtest window
        session_hours: Hours of day to run sessions (UTC)
        
    Returns:
        List of (timestamp, mode) tuples
    """
    sessions = []
    current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_count = 0
    session_idx = 0
    
    while current_date < end_date:
        # Every other day
        if day_count % 2 == 0:
            for hour in session_hours:
                session_ts = current_date.replace(hour=hour)
                if start_date <= session_ts <= end_date:
                    mode = MODE_ROTATION[session_idx % len(MODE_ROTATION)]
                    sessions.append((session_ts, mode))
                    session_idx += 1
        
        current_date += timedelta(days=1)
        day_count += 1
    
    return sessions


# =============================================================================
# TRADE SIMULATION
# =============================================================================

def simulate_trade(
    plan: SimpleTradePlan,
    price_data: pd.DataFrame,
    risk_amount: float,
    equity_before: float
) -> TradeResult:
    """
    Simulate a trade using 5m/1h candle data.
    
    Args:
        plan: Trade plan to simulate
        price_data: OHLCV DataFrame with timestamp index
        risk_amount: Dollar amount risked on this trade
        equity_before: Equity before this trade
        
    Returns:
        TradeResult with P&L and exit details
    """
    is_long = plan.side == "long"
    
    # Filter to only candles after plan creation
    future_data = price_data[price_data.index >= plan.created_at].copy()
    
    if future_data.empty:
        return TradeResult(
            plan=plan,
            filled=False,
            filled_at=None,
            exit_at=None,
            exit_price=0,
            exit_reason="NOT_FILLED",
            pnl=0,
            r_multiple=0,
            equity_before=equity_before,
            equity_after=equity_before
        )
    
    # Calculate position size
    entry = plan.entry_price
    stop = plan.stop_price
    risk_distance = abs(entry - stop)
    
    if risk_distance == 0:
        return TradeResult(
            plan=plan, filled=False, filled_at=None, exit_at=None,
            exit_price=0, exit_reason="INVALID_PLAN", pnl=0, r_multiple=0,
            equity_before=equity_before, equity_after=equity_before
        )
    
    position_size = risk_amount / risk_distance
    
    # Step 1: Wait for entry fill
    filled = False
    filled_at = None
    
    for idx, candle in future_data.iterrows():
        low, high = candle['low'], candle['high']
        
        # Entry is filled if price passes through entry level
        if low <= entry <= high:
            filled = True
            filled_at = idx
            break
    
    if not filled:
        return TradeResult(
            plan=plan, filled=False, filled_at=None, exit_at=None,
            exit_price=0, exit_reason="NOT_FILLED", pnl=0, r_multiple=0,
            equity_before=equity_before, equity_after=equity_before
        )
    
    # Step 2: Simulate candle by candle after fill
    post_fill_data = future_data[future_data.index > filled_at]
    
    exit_price = 0
    exit_at = None
    exit_reason = "TIMEOUT"
    
    tp1 = plan.tp1
    
    for idx, candle in post_fill_data.iterrows():
        low, high, close = candle['low'], candle['high'], candle['close']
        
        if is_long:
            # For LONG: Check SL first (conservative)
            if low <= stop:
                exit_price = stop
                exit_at = idx
                exit_reason = "SL"
                break
            elif high >= tp1:
                exit_price = tp1
                exit_at = idx
                exit_reason = "TP1"
                break
        else:
            # For SHORT: Check TP first (conservative)
            if low <= tp1:
                exit_price = tp1
                exit_at = idx
                exit_reason = "TP1"
                break
            elif high >= stop:
                exit_price = stop
                exit_at = idx
                exit_reason = "SL"
                break
    
    # If no exit triggered, close at last price
    if exit_reason == "TIMEOUT":
        exit_price = post_fill_data['close'].iloc[-1] if not post_fill_data.empty else entry
        exit_at = post_fill_data.index[-1] if not post_fill_data.empty else filled_at
    
    # Calculate P&L
    if is_long:
        pnl = (exit_price - entry) * position_size
    else:
        pnl = (entry - exit_price) * position_size
    
    r_multiple = pnl / risk_amount if risk_amount > 0 else 0
    equity_after = equity_before + pnl
    
    return TradeResult(
        plan=plan,
        filled=True,
        filled_at=filled_at,
        exit_at=exit_at,
        exit_price=exit_price,
        exit_reason=exit_reason,
        pnl=pnl,
        r_multiple=r_multiple,
        equity_before=equity_before,
        equity_after=equity_after
    )


# =============================================================================
# MAIN BACKTEST RUNNER
# =============================================================================

def run_backtest(
    csv_path: str,
    initial_equity: float = 10000.0,
    risk_fraction: float = 0.01,  # 1% risk per trade
    backtest_days: int = 90,
    symbols: Optional[List[str]] = None
) -> Tuple[List[TradeResult], List[float]]:
    """
    Run the full backtest.
    
    Args:
        csv_path: Path to CSV data file
        initial_equity: Starting equity in USD
        risk_fraction: Fraction of equity to risk per trade
        backtest_days: Number of days to backtest
        symbols: Symbols to scan (defaults to all in CSV)
        
    Returns:
        Tuple of (trade_results, equity_curve)
    """
    print("=" * 70)
    print("🎯 SNIPERSIGHT FULL PIPELINE BACKTEST")
    print("=" * 70)
    
    # Load data
    all_data = load_csv_data(csv_path)
    
    if not all_data:
        print("❌ No data loaded!")
        return [], [initial_equity]
    
    # Determine symbols
    if symbols is None:
        symbols = [f"{s[:3]}/{s[3:]}" if 'USDT' in s else s for s in all_data.keys()]
        symbols = [s.replace('USDT', '/USDT') if '/USDT' not in s else s for s in symbols]
        symbols = [s.replace('//', '/') for s in symbols]
    
    print(f"\n📊 Symbols: {symbols}")
    
    # Determine date range
    first_symbol = list(all_data.keys())[0]
    ref_tf = '1h' if '1h' in all_data[first_symbol] else list(all_data[first_symbol].keys())[0]
    ref_df = all_data[first_symbol][ref_tf]
    
    data_start = ref_df.index.min()
    data_end = ref_df.index.max()
    
    # Use last N days for backtest
    backtest_start = max(data_start + timedelta(days=30), data_end - timedelta(days=backtest_days))
    backtest_end = data_end - timedelta(days=3)  # Leave room for trade resolution
    
    print(f"📅 Data range: {data_start} to {data_end}")
    print(f"📅 Backtest window: {backtest_start} to {backtest_end}")
    
    # Generate sessions
    sessions = generate_sessions(backtest_start, backtest_end)
    print(f"\n🔄 Generated {len(sessions)} scan sessions")
    
    # Initialize tracking
    equity = initial_equity
    equity_curve = [equity]
    all_results: List[TradeResult] = []
    
    # Create adapter
    adapter = CSVDataAdapter(all_data, backtest_start)
    
    print("\n" + "-" * 70)
    print("Running backtest...")
    print("-" * 70)
    
    # Process each session
    for i, (session_ts, mode) in enumerate(sessions):
        adapter.set_timestamp(session_ts)
        
        # Calculate risk amount
        risk_amount = equity * risk_fraction
        
        # Run pipeline
        plans = run_snipersight_pipeline(symbols, adapter, mode)
        
        if plans:
            print(f"\n[{i+1}/{len(sessions)}] {session_ts.strftime('%Y-%m-%d %H:%M')} | Mode: {mode.value.upper()} | Signals: {len(plans)}")
        
        # Simulate each trade
        for plan in plans:
            # Get simulation data (use 1h for trade resolution)
            symbol_key = plan.symbol.replace('/', '')
            sim_tf = '1h' if '1h' in all_data.get(symbol_key, {}) else '5m'
            
            if symbol_key not in all_data or sim_tf not in all_data[symbol_key]:
                continue
            
            sim_data = all_data[symbol_key][sim_tf]
            
            # Simulate trade
            result = simulate_trade(plan, sim_data, risk_amount, equity)
            all_results.append(result)
            
            if result.filled:
                equity = result.equity_after
                equity_curve.append(equity)
                
                emoji = "✅" if result.pnl > 0 else "❌"
                print(f"   {emoji} {plan.symbol} {plan.side.upper()}: ${result.pnl:+.2f} ({result.r_multiple:+.2f}R) | {result.exit_reason}")
    
    return all_results, equity_curve


# =============================================================================
# STATISTICS AND REPORTING
# =============================================================================

def print_statistics(results: List[TradeResult], equity_curve: List[float], initial_equity: float):
    """Print comprehensive backtest statistics."""
    
    # Filter to filled trades only
    filled_trades = [r for r in results if r.filled]
    
    if not filled_trades:
        print("\n❌ No trades were filled!")
        return
    
    # Basic stats
    total_trades = len(filled_trades)
    wins = [r for r in filled_trades if r.pnl > 0]
    losses = [r for r in filled_trades if r.pnl < 0]
    breakeven = [r for r in filled_trades if r.pnl == 0]
    
    win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
    
    final_equity = equity_curve[-1]
    total_pnl = final_equity - initial_equity
    total_return = (total_pnl / initial_equity) * 100
    
    # Max drawdown
    peak = initial_equity
    max_dd = 0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd
    
    # Profit factor
    gross_profit = sum(r.pnl for r in wins)
    gross_loss = abs(sum(r.pnl for r in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    # Average R
    avg_r = np.mean([r.r_multiple for r in filled_trades])
    
    print("\n" + "=" * 70)
    print("📊 BACKTEST RESULTS")
    print("=" * 70)
    print(f"  Total Sessions Run:     {len(results)}")
    print(f"  Total Trades Filled:    {total_trades}")
    print(f"  Not Filled:             {len(results) - total_trades}")
    print("-" * 70)
    print(f"  Wins:                   {len(wins)}")
    print(f"  Losses:                 {len(losses)}")
    print(f"  Breakeven:              {len(breakeven)}")
    print(f"  Win Rate:               {win_rate:.1f}%")
    print("-" * 70)
    print(f"  Initial Equity:         ${initial_equity:,.2f}")
    print(f"  Final Equity:           ${final_equity:,.2f}")
    print(f"  Total P&L:              ${total_pnl:+,.2f}")
    print(f"  Total Return:           {total_return:+.2f}%")
    print("-" * 70)
    print(f"  Max Drawdown:           {max_dd:.2f}%")
    print(f"  Profit Factor:          {profit_factor:.2f}")
    print(f"  Average R-Multiple:     {avg_r:+.2f}R")
    print("=" * 70)
    
    # Per-mode stats
    print("\n📈 PER-MODE STATISTICS:")
    print("-" * 70)
    
    mode_stats: Dict[str, Dict[str, Any]] = {}
    for r in filled_trades:
        mode = r.plan.mode
        if mode not in mode_stats:
            mode_stats[mode] = {'trades': 0, 'wins': 0, 'pnl': 0.0, 'r_sum': 0.0}
        mode_stats[mode]['trades'] += 1
        mode_stats[mode]['pnl'] += r.pnl
        mode_stats[mode]['r_sum'] += r.r_multiple
        if r.pnl > 0:
            mode_stats[mode]['wins'] += 1
    
    for mode, stats in sorted(mode_stats.items()):
        wr = stats['wins'] / stats['trades'] * 100 if stats['trades'] > 0 else 0
        avg_r = stats['r_sum'] / stats['trades'] if stats['trades'] > 0 else 0
        emoji = "✅" if stats['pnl'] > 0 else "❌"
        print(f"  {emoji} {mode.upper():<12}: {stats['trades']:>3} trades | WR: {wr:>5.1f}% | P&L: ${stats['pnl']:>+10.2f} | Avg R: {avg_r:>+.2f}")
    
    # By exit reason
    print("\n🎯 BY EXIT REASON:")
    print("-" * 70)
    
    exit_stats: Dict[str, Dict[str, Any]] = {}
    for r in filled_trades:
        reason = r.exit_reason
        if reason not in exit_stats:
            exit_stats[reason] = {'count': 0, 'pnl': 0.0}
        exit_stats[reason]['count'] += 1
        exit_stats[reason]['pnl'] += r.pnl
    
    for reason, stats in exit_stats.items():
        emoji = "🎯" if "TP" in reason else ("❌" if reason == "SL" else "⏱️")
        print(f"  {emoji} {reason:<12}: {stats['count']:>3} trades | P&L: ${stats['pnl']:>+10.2f}")
    
    # By symbol
    print("\n💹 BY SYMBOL:")
    print("-" * 70)
    
    symbol_stats: Dict[str, Dict[str, Any]] = {}
    for r in filled_trades:
        sym = r.plan.symbol
        if sym not in symbol_stats:
            symbol_stats[sym] = {'trades': 0, 'wins': 0, 'pnl': 0.0}
        symbol_stats[sym]['trades'] += 1
        symbol_stats[sym]['pnl'] += r.pnl
        if r.pnl > 0:
            symbol_stats[sym]['wins'] += 1
    
    for sym, stats in sorted(symbol_stats.items(), key=lambda x: -x[1]['pnl']):
        wr = stats['wins'] / stats['trades'] * 100 if stats['trades'] > 0 else 0
        emoji = "✅" if stats['pnl'] > 0 else "❌"
        print(f"  {emoji} {sym:<12}: {stats['trades']:>3} trades | WR: {wr:>5.1f}% | P&L: ${stats['pnl']:>+10.2f}")


def save_trade_log(results: List[TradeResult], output_path: str):
    """Save trade log to CSV."""
    rows = []
    for r in results:
        rows.append({
            'symbol': r.plan.symbol,
            'mode': r.plan.mode,
            'side': r.plan.side,
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
            'r_multiple': r.r_multiple,
            'equity_before': r.equity_before,
            'equity_after': r.equity_after
        })
    
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"\n📁 Trade log saved to: {output_path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run the full backtest."""
    # Find CSV file
    project_root = Path(__file__).parent.parent
    csv_path = project_root / "backend" / "tests" / "backtest" / "backtest_multitimeframe_5000bars.csv"
    
    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        return
    
    # Run backtest
    results, equity_curve = run_backtest(
        csv_path=str(csv_path),
        initial_equity=10000.0,
        risk_fraction=0.01,  # 1% risk per trade
        backtest_days=60,    # ~2 months
        symbols=None         # Use all symbols in CSV
    )
    
    # Print statistics
    print_statistics(results, equity_curve, 10000.0)
    
    # Save trade log
    output_path = project_root / "scripts" / "backtest_trades.csv"
    save_trade_log(results, str(output_path))
    
    return results, equity_curve


if __name__ == "__main__":
    main()
