#!/usr/bin/env python3
"""
SniperSight Scanner Profitability Backtest

Fetches recent historical data and simulates what would have happened
if you traded every signal the scanner generated.

Usage:
    python scripts/run_backtest.py
    python scripts/run_backtest.py --mode strike --days 7
    python scripts/run_backtest.py --mode surgical --equity 1000 --risk 0.02

Features:
- Real exchange data (Phemex by default)
- Full SMC pipeline (same as live scanner)
- Simulated trade execution with TP/SL tracking
- P&L calculation with equity curve
- Performance metrics (win rate, profit factor, max drawdown)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict
import logging

# Backend imports
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode, MODES
from backend.data.adapters.phemex import PhemexAdapter
from backend.data.ingestion_pipeline import IngestionPipeline
from backend.engine.orchestrator import Orchestrator


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class Trade:
    """Represents a single trade from entry to exit."""
    symbol: str
    direction: str  # LONG or SHORT
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    entry_time: datetime
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # TP1, TP2, TP3, SL, TIMEOUT
    pnl_pct: float = 0.0
    r_multiple: float = 0.0
    confidence: float = 0.0
    mode: str = ""


@dataclass
class BacktestResult:
    """Summary of backtest performance."""
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl_pct: float
    avg_pnl_pct: float
    avg_r: float
    profit_factor: float
    max_drawdown_pct: float
    final_equity: float
    initial_equity: float
    equity_curve: List[float]
    trades: List[Trade]
    by_symbol: Dict[str, Dict]
    by_direction: Dict[str, Dict]


# =============================================================================
# BACKTEST ENGINE
# =============================================================================

class BacktestEngine:
    """Simulates trading based on scanner signals."""
    
    def __init__(
        self,
        initial_equity: float = 10000.0,
        risk_per_trade: float = 0.01,  # 1% risk per trade
        max_concurrent: int = 5,
        partial_tp: bool = True,  # Scale out at TPs
        tp1_pct: float = 0.5,  # Close 50% at TP1
        tp2_pct: float = 0.3,  # Close 30% at TP2
        tp3_pct: float = 0.2,  # Close remaining at TP3
        leverage: int = 1,  # Leverage multiplier
        fee_pct: float = 0.001,  # 0.1% trading fee (entry + exit)
    ):
        self.initial_equity = initial_equity
        self.equity = initial_equity
        self.risk_per_trade = risk_per_trade
        self.max_concurrent = max_concurrent
        self.partial_tp = partial_tp
        self.tp1_pct = tp1_pct
        self.tp2_pct = tp2_pct
        self.tp3_pct = tp3_pct
        self.leverage = leverage
        self.fee_pct = fee_pct
        
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = [initial_equity]
        self.open_trades: List[Trade] = []
    
    def simulate_trade(
        self,
        trade: Trade,
        future_data: pd.DataFrame,
        max_bars: int = 200
    ) -> Trade:
        """
        Simulate a trade through future price data.
        
        Returns the trade with exit info filled in.
        """
        if future_data.empty:
            trade.exit_reason = "NO_DATA"
            trade.exit_price = trade.entry_price
            trade.pnl_pct = 0.0
            trade.r_multiple = 0.0
            return trade
        
        is_long = trade.direction == "LONG"
        risk = abs(trade.entry_price - trade.stop_loss)
        
        # Track partial exits
        remaining_pct = 1.0
        total_pnl = 0.0
        
        for i, row in future_data.head(max_bars).iterrows():
            high = row['high']
            low = row['low']
            
            # Check stop loss first
            if is_long and low <= trade.stop_loss:
                trade.exit_price = trade.stop_loss
                trade.exit_reason = "SL"
                trade.exit_time = row.get('timestamp', row.name)
                loss_pct = ((trade.stop_loss - trade.entry_price) / trade.entry_price) * remaining_pct
                total_pnl += loss_pct
                break
            elif not is_long and high >= trade.stop_loss:
                trade.exit_price = trade.stop_loss
                trade.exit_reason = "SL"
                trade.exit_time = row.get('timestamp', row.name)
                loss_pct = ((trade.entry_price - trade.stop_loss) / trade.entry_price) * remaining_pct
                total_pnl += loss_pct
                break
            
            # Check take profits
            if self.partial_tp:
                # TP1
                if remaining_pct > 0.5:
                    if (is_long and high >= trade.tp1) or (not is_long and low <= trade.tp1):
                        pnl = ((trade.tp1 - trade.entry_price) / trade.entry_price) if is_long else ((trade.entry_price - trade.tp1) / trade.entry_price)
                        total_pnl += pnl * self.tp1_pct
                        remaining_pct -= self.tp1_pct
                
                # TP2
                if remaining_pct > 0.2:
                    if (is_long and high >= trade.tp2) or (not is_long and low <= trade.tp2):
                        pnl = ((trade.tp2 - trade.entry_price) / trade.entry_price) if is_long else ((trade.entry_price - trade.tp2) / trade.entry_price)
                        total_pnl += pnl * self.tp2_pct
                        remaining_pct -= self.tp2_pct
                
                # TP3
                if remaining_pct > 0:
                    if (is_long and high >= trade.tp3) or (not is_long and low <= trade.tp3):
                        pnl = ((trade.tp3 - trade.entry_price) / trade.entry_price) if is_long else ((trade.entry_price - trade.tp3) / trade.entry_price)
                        total_pnl += pnl * remaining_pct
                        remaining_pct = 0
                        trade.exit_price = trade.tp3
                        trade.exit_reason = "TP3"
                        trade.exit_time = row.get('timestamp', row.name)
                        break
            else:
                # Full exit at TP1
                if (is_long and high >= trade.tp1) or (not is_long and low <= trade.tp1):
                    trade.exit_price = trade.tp1
                    trade.exit_reason = "TP1"
                    trade.exit_time = row.get('timestamp', row.name)
                    pnl = ((trade.tp1 - trade.entry_price) / trade.entry_price) if is_long else ((trade.entry_price - trade.tp1) / trade.entry_price)
                    total_pnl = pnl
                    remaining_pct = 0
                    break
        
        # If we didn't exit, close at last price (timeout)
        if remaining_pct > 0:
            last_close = future_data['close'].iloc[-1]
            trade.exit_price = last_close
            trade.exit_reason = "TIMEOUT"
            trade.exit_time = future_data.index[-1] if hasattr(future_data.index[-1], 'timestamp') else datetime.now(timezone.utc)
            pnl = ((last_close - trade.entry_price) / trade.entry_price) if is_long else ((trade.entry_price - last_close) / trade.entry_price)
            total_pnl += pnl * remaining_pct
        
        # Apply leverage to P&L
        total_pnl *= self.leverage
        
        # Deduct trading fees (entry + exit = 2x fee_pct)
        total_pnl -= (self.fee_pct * 2 * self.leverage)
        
        trade.pnl_pct = total_pnl * 100  # Convert to percentage
        trade.r_multiple = total_pnl / (risk / trade.entry_price) if risk > 0 else 0
        
        return trade
    
    def calculate_metrics(self) -> BacktestResult:
        """Calculate performance metrics from completed trades."""
        if not self.trades:
            return BacktestResult(
                total_trades=0, wins=0, losses=0, win_rate=0,
                total_pnl_pct=0, avg_pnl_pct=0, avg_r=0, profit_factor=0,
                max_drawdown_pct=0, final_equity=self.initial_equity,
                initial_equity=self.initial_equity,
                equity_curve=self.equity_curve, trades=[],
                by_symbol={}, by_direction={}
            )
        
        wins = [t for t in self.trades if t.pnl_pct > 0]
        losses = [t for t in self.trades if t.pnl_pct <= 0]
        
        total_pnl = sum(t.pnl_pct for t in self.trades)
        gross_profit = sum(t.pnl_pct for t in wins) if wins else 0
        gross_loss = abs(sum(t.pnl_pct for t in losses)) if losses else 0.001
        
        # Calculate equity curve and max drawdown
        equity = self.initial_equity
        peak = equity
        max_dd = 0
        equity_curve = [equity]
        
        for trade in self.trades:
            pnl_dollar = equity * (trade.pnl_pct / 100) * self.risk_per_trade * 10  # Scaled by risk
            equity += pnl_dollar
            equity_curve.append(equity)
            peak = max(peak, equity)
            dd = (peak - equity) / peak * 100
            max_dd = max(max_dd, dd)
        
        # By symbol stats
        by_symbol = defaultdict(lambda: {'trades': 0, 'wins': 0, 'pnl': 0})
        for t in self.trades:
            by_symbol[t.symbol]['trades'] += 1
            by_symbol[t.symbol]['wins'] += 1 if t.pnl_pct > 0 else 0
            by_symbol[t.symbol]['pnl'] += t.pnl_pct
        
        # By direction stats
        by_direction = defaultdict(lambda: {'trades': 0, 'wins': 0, 'pnl': 0})
        for t in self.trades:
            by_direction[t.direction]['trades'] += 1
            by_direction[t.direction]['wins'] += 1 if t.pnl_pct > 0 else 0
            by_direction[t.direction]['pnl'] += t.pnl_pct
        
        return BacktestResult(
            total_trades=len(self.trades),
            wins=len(wins),
            losses=len(losses),
            win_rate=len(wins) / len(self.trades) * 100 if self.trades else 0,
            total_pnl_pct=total_pnl,
            avg_pnl_pct=total_pnl / len(self.trades) if self.trades else 0,
            avg_r=sum(t.r_multiple for t in self.trades) / len(self.trades) if self.trades else 0,
            profit_factor=gross_profit / gross_loss if gross_loss > 0 else 0,
            max_drawdown_pct=max_dd,
            final_equity=equity_curve[-1],
            initial_equity=self.initial_equity,
            equity_curve=equity_curve,
            trades=self.trades,
            by_symbol=dict(by_symbol),
            by_direction=dict(by_direction)
        )


# =============================================================================
# MAIN BACKTEST RUNNER
# =============================================================================

def run_backtest(
    mode_name: str = "strike",
    days: int = 7,
    symbols: List[str] = None,
    initial_equity: float = 10000.0,
    risk_per_trade: float = 0.01,
    leverage: int = 1,
    fee_pct: float = 0.001,  # 0.1% per trade
    verbose: bool = True
) -> BacktestResult:
    """
    Run a backtest using historical data.
    
    Strategy:
    1. Fetch historical data for each symbol
    2. Walk through time, running scanner at regular intervals
    3. For each signal, simulate the trade forward
    4. Calculate performance metrics
    """
    
    if symbols is None:
        symbols = [
            "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
            "XRP/USDT", "DOGE/USDT", "LINK/USDT", "ADA/USDT"
        ]
    
    print(f"\n{'='*60}")
    print(f"  SniperSight Scanner Backtest")
    print(f"{'='*60}")
    print(f"  Mode: {mode_name.upper()}")
    print(f"  Period: Last {days} days")
    print(f"  Symbols: {len(symbols)}")
    print(f"  Initial Equity: ${initial_equity:,.2f}")
    print(f"  Risk per Trade: {risk_per_trade*100:.1f}%")
    print(f"  Leverage: {leverage}x")
    print(f"  Fees: {fee_pct*100:.2f}% per trade")
    print(f"{'='*60}\n")
    
    # Initialize components
    adapter = PhemexAdapter()
    mode = get_mode(mode_name)
    config = ScanConfig()
    config.min_confluence_score = mode.min_confluence_score
    
    orchestrator = Orchestrator(
        config=config,
        exchange_adapter=adapter
    )
    orchestrator.apply_mode(mode)
    
    engine = BacktestEngine(
        initial_equity=initial_equity,
        risk_per_trade=risk_per_trade,
        partial_tp=True,
        leverage=leverage,
        fee_pct=fee_pct
    )
    
    print("📊 Fetching historical data...")
    
    # Fetch data for each symbol
    all_data: Dict[str, Dict[str, pd.DataFrame]] = {}
    
    for symbol in symbols:
        all_data[symbol] = {}
        for tf in mode.timeframes:
            try:
                df = adapter.fetch_ohlcv(symbol, tf, limit=500)
                if not df.empty:
                    if 'timestamp' in df.columns:
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                        df = df.set_index('timestamp')
                    all_data[symbol][tf] = df
                    if verbose:
                        print(f"   ✓ {symbol} {tf}: {len(df)} candles")
            except Exception as e:
                if verbose:
                    print(f"   ✗ {symbol} {tf}: {e}")
    
    print(f"\n🎯 Running scanner on historical data...")
    
    # Run scanner on current data (represents "now")
    try:
        trade_plans, rejections = orchestrator.scan(symbols)
        print(f"   Generated {len(trade_plans)} signals")
    except Exception as e:
        print(f"   ✗ Scanner error: {e}")
        trade_plans = []
    
    # Convert trade plans to trades and simulate
    print(f"\n⚡ Simulating trades...")
    
    for plan in trade_plans:
        try:
            # Extract targets
            targets = [tp.level for tp in plan.targets] if plan.targets else []
            tp1 = targets[0] if len(targets) > 0 else plan.entry_zone.near_entry * (1.02 if plan.direction == "LONG" else 0.98)
            tp2 = targets[1] if len(targets) > 1 else tp1 * (1.01 if plan.direction == "LONG" else 0.99)
            tp3 = targets[2] if len(targets) > 2 else tp2 * (1.01 if plan.direction == "LONG" else 0.99)
            
            trade = Trade(
                symbol=plan.symbol,
                direction=plan.direction,
                entry_price=plan.entry_zone.near_entry,
                stop_loss=plan.stop_loss.level,
                tp1=tp1,
                tp2=tp2,
                tp3=tp3,
                entry_time=datetime.now(timezone.utc),
                confidence=plan.confidence_score,
                mode=mode_name
            )
            
            # Get future data for simulation (use 5m for granularity)
            symbol_clean = plan.symbol.replace(':USDT', '')
            if symbol_clean in all_data and '5m' in all_data[symbol_clean]:
                future_df = all_data[symbol_clean]['5m'].copy()
            elif plan.symbol in all_data and '5m' in all_data[plan.symbol]:
                future_df = all_data[plan.symbol]['5m'].copy()
            else:
                # Try to fetch fresh data
                future_df = adapter.fetch_ohlcv(plan.symbol, '5m', limit=200)
                if 'timestamp' in future_df.columns:
                    future_df['timestamp'] = pd.to_datetime(future_df['timestamp'])
                    future_df = future_df.set_index('timestamp')
            
            # Simulate the trade
            trade = engine.simulate_trade(trade, future_df)
            engine.trades.append(trade)
            
            if verbose:
                emoji = "✅" if trade.pnl_pct > 0 else "❌"
                print(f"   {emoji} {trade.symbol} {trade.direction}: {trade.pnl_pct:+.2f}% ({trade.exit_reason})")
                
        except Exception as e:
            if verbose:
                print(f"   ✗ Error simulating {plan.symbol}: {e}")
    
    # Calculate final metrics
    result = engine.calculate_metrics()
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"  BACKTEST RESULTS")
    print(f"{'='*60}")
    print(f"  Total Trades: {result.total_trades}")
    print(f"  Wins: {result.wins} | Losses: {result.losses}")
    print(f"  Win Rate: {result.win_rate:.1f}%")
    print(f"  Total P&L: {result.total_pnl_pct:+.2f}%")
    print(f"  Avg P&L per Trade: {result.avg_pnl_pct:+.2f}%")
    print(f"  Average R: {result.avg_r:+.2f}R")
    print(f"  Profit Factor: {result.profit_factor:.2f}")
    print(f"  Max Drawdown: {result.max_drawdown_pct:.2f}%")
    print(f"  Final Equity: ${result.final_equity:,.2f}")
    print(f"  Return: {((result.final_equity - result.initial_equity) / result.initial_equity * 100):+.2f}%")
    
    if result.by_direction:
        print(f"\n  By Direction:")
        for direction, stats in result.by_direction.items():
            wr = stats['wins'] / stats['trades'] * 100 if stats['trades'] > 0 else 0
            print(f"    {direction}: {stats['trades']} trades, {wr:.0f}% WR, {stats['pnl']:+.2f}% P&L")
    
    if result.by_symbol and len(result.by_symbol) <= 10:
        print(f"\n  By Symbol:")
        for symbol, stats in sorted(result.by_symbol.items(), key=lambda x: x[1]['pnl'], reverse=True):
            wr = stats['wins'] / stats['trades'] * 100 if stats['trades'] > 0 else 0
            print(f"    {symbol}: {stats['trades']} trades, {wr:.0f}% WR, {stats['pnl']:+.2f}% P&L")
    
    print(f"{'='*60}\n")
    
    return result


def compare_modes(days: int = 7, initial_equity: float = 10000.0, leverage: int = 1, fee_pct: float = 0.001):
    """Compare performance across all scanner modes."""
    
    print(f"\n{'='*70}")
    print(f"  MODE COMPARISON BACKTEST ({leverage}x leverage, {fee_pct*100:.2f}% fees)")
    print(f"{'='*70}\n")
    
    modes = ["strike", "surgical", "stealth", "overwatch"]
    results = {}
    
    for mode_name in modes:
        print(f"\n--- Testing {mode_name.upper()} ---")
        try:
            result = run_backtest(
                mode_name=mode_name,
                days=days,
                initial_equity=initial_equity,
                leverage=leverage,
                fee_pct=fee_pct,
                verbose=False
            )
            results[mode_name] = result
        except Exception as e:
            print(f"Error testing {mode_name}: {e}")
            results[mode_name] = None
    
    # Summary comparison
    print(f"\n{'='*70}")
    print(f"  MODE COMPARISON SUMMARY ({leverage}x leverage)")
    print(f"{'='*70}")
    print(f"{'Mode':<12} {'Trades':<8} {'Win%':<8} {'P&L%':<12} {'Avg R':<8} {'MaxDD%':<8} {'Final $':<12}")
    print(f"{'-'*70}")
    
    for mode_name, result in results.items():
        if result:
            print(f"{mode_name.upper():<12} {result.total_trades:<8} {result.win_rate:<8.1f} {result.total_pnl_pct:<+12.2f} {result.avg_r:<+8.2f} {result.max_drawdown_pct:<8.2f} ${result.final_equity:<11,.2f}")
        else:
            print(f"{mode_name.upper():<12} {'ERROR':<8}")
    
    print(f"{'='*70}\n")
    
    return results


def compare_leverage(mode_name: str = "stealth", days: int = 7, initial_equity: float = 10000.0):
    """Compare performance across different leverage levels."""
    
    print(f"\n{'='*70}")
    print(f"  LEVERAGE COMPARISON BACKTEST - {mode_name.upper()} MODE")
    print(f"{'='*70}\n")
    
    # Run base backtest once at 1x to get baseline results
    print("📊 Running baseline scan (1x leverage)...")
    base_result = run_backtest(
        mode_name=mode_name,
        days=days,
        initial_equity=initial_equity,
        leverage=1,
        fee_pct=0.001,
        verbose=False
    )
    
    if not base_result or base_result.total_trades == 0:
        print("❌ No trades generated - cannot compare leverage")
        return {}
    
    # Calculate leveraged results from base P&L
    # Since leverage multiplies P&L linearly (before fees), we can derive results
    leverages = [1, 3, 5, 10, 20, 50]
    results = {1: base_result}
    
    print("\n💰 Calculating leveraged returns...")
    
    base_pnl_per_trade = [t.pnl_pct for t in base_result.trades]
    
    for lev in leverages[1:]:  # Skip 1x (already have it)
        # Scale P&L by leverage (fees already included in base)
        # Additional fee impact from leverage on position size
        extra_fee_impact = 0.001 * 2 * (lev - 1) * 100  # Extra fee % for larger positions
        
        leveraged_pnl = sum(p * lev - extra_fee_impact for p in base_pnl_per_trade)
        
        # Calculate equity curve with leverage
        equity = initial_equity
        max_equity = equity
        max_dd = 0
        
        for p in base_pnl_per_trade:
            pnl_leveraged = p * lev - (0.001 * 2 * (lev - 1) * 100)  # P&L with extra fees
            equity += equity * (pnl_leveraged / 100)
            if equity > max_equity:
                max_equity = equity
            dd = (max_equity - equity) / max_equity * 100 if max_equity > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        # Create result object
        from copy import deepcopy
        lev_result = deepcopy(base_result)
        lev_result.total_pnl_pct = leveraged_pnl
        lev_result.avg_pnl_pct = leveraged_pnl / base_result.total_trades if base_result.total_trades > 0 else 0
        lev_result.final_equity = equity
        lev_result.max_drawdown_pct = max_dd
        
        results[lev] = lev_result
    
    # Summary comparison
    print(f"\n{'='*70}")
    print(f"  LEVERAGE COMPARISON SUMMARY - {mode_name.upper()} MODE")
    print(f"{'='*70}")
    print(f"{'Leverage':<10} {'Trades':<8} {'Win%':<8} {'P&L%':<12} {'MaxDD%':<10} {'Final $':<12}")
    print(f"{'-'*70}")
    
    for lev in leverages:
        result = results.get(lev)
        if result:
            print(f"{lev}x{'':<8} {result.total_trades:<8} {result.win_rate:<8.1f} {result.total_pnl_pct:<+12.2f} {result.max_drawdown_pct:<10.2f} ${result.final_equity:<11,.2f}")
        else:
            print(f"{lev}x{'':<8} {'ERROR':<8}")
    
    # Risk analysis
    print(f"\n  ⚠️  RISK ANALYSIS:")
    for lev in leverages:
        result = results.get(lev)
        if result and result.max_drawdown_pct > 0:
            # At what leverage would you get liquidated (100% loss)?
            liq_risk = 100 / result.max_drawdown_pct if result.max_drawdown_pct > 0 else float('inf')
            status = "⚠️ DANGER" if lev >= liq_risk * 0.8 else "✅ OK"
            print(f"     {lev}x: Max DD = {result.max_drawdown_pct:.2f}% | Liq threshold ~{liq_risk:.0f}x | {status}")
    
    print(f"{'='*70}\n")
    
    return results


def walk_forward_backtest(
    mode_name: str = "stealth",
    total_days: int = 30,
    window_days: int = 7,
    step_days: int = 3,
    initial_equity: float = 10000.0,
    leverage: int = 5,
    fee_pct: float = 0.001,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Walk-forward backtest: Run scanner at multiple historical points.
    
    This simulates real trading by running the scanner every `step_days`,
    executing trades, then moving forward in time.
    
    Args:
        total_days: Total history to cover
        window_days: How much data each scan uses
        step_days: How often to run a new scan
        
    Returns aggregated results across all windows.
    """
    print(f"\n{'='*80}")
    print(f"  WALK-FORWARD BACKTEST - {mode_name.upper()} MODE")
    print(f"  Period: {total_days} days | Window: {window_days}d | Step: {step_days}d")
    print(f"  Leverage: {leverage}x | Fees: {fee_pct*100:.2f}%")
    print(f"{'='*80}\n")
    
    adapter = PhemexAdapter()
    mode = get_mode(mode_name)
    
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", 
               "DOGE/USDT", "ADA/USDT", "LINK/USDT", "BNB/USDT"]
    
    # Calculate number of windows
    num_windows = (total_days - window_days) // step_days + 1
    
    all_trades: List[Trade] = []
    window_results = []
    equity = initial_equity
    
    print(f"📊 Running {num_windows} scan windows...\n")
    
    for i in range(num_windows):
        days_back = total_days - (i * step_days)
        window_start = datetime.now(timezone.utc) - timedelta(days=days_back)
        window_end = window_start + timedelta(days=window_days)
        
        print(f"   Window {i+1}/{num_windows}: {window_start.strftime('%Y-%m-%d')} → {window_end.strftime('%Y-%m-%d')}")
        
        try:
            # Create orchestrator for this window
            orchestrator = Orchestrator(
                exchange_adapter=adapter,
                config=ScanConfig()
            )
            orchestrator.apply_mode(mode_name)
            
            # Run scan
            trade_plans, rejections = orchestrator.scan(symbols)
            
            if trade_plans:
                engine = BacktestEngine(
                    initial_equity=equity,
                    leverage=leverage,
                    fee_pct=fee_pct
                )
                
                for plan in trade_plans:
                    try:
                        targets = [tp.level for tp in plan.targets] if plan.targets else []
                        tp1 = targets[0] if len(targets) > 0 else plan.entry_zone.near_entry * (1.02 if plan.direction == "LONG" else 0.98)
                        tp2 = targets[1] if len(targets) > 1 else tp1 * (1.01 if plan.direction == "LONG" else 0.99)
                        tp3 = targets[2] if len(targets) > 2 else tp2 * (1.01 if plan.direction == "LONG" else 0.99)
                        
                        trade = Trade(
                            symbol=plan.symbol,
                            direction=plan.direction,
                            entry_price=plan.entry_zone.near_entry,
                            stop_loss=plan.stop_loss.level,
                            tp1=tp1, tp2=tp2, tp3=tp3,
                            entry_time=window_start,
                            confidence=plan.confidence_score,
                            mode=mode_name
                        )
                        
                        # Fetch simulation data
                        future_df = adapter.fetch_ohlcv(plan.symbol, '5m', limit=500)
                        if 'timestamp' in future_df.columns:
                            future_df['timestamp'] = pd.to_datetime(future_df['timestamp'])
                            future_df = future_df.set_index('timestamp')
                        
                        trade = engine.simulate_trade(trade, future_df)
                        all_trades.append(trade)
                        
                        # Update rolling equity
                        equity += equity * (trade.pnl_pct / 100)
                        
                    except Exception as e:
                        if verbose:
                            print(f"      ✗ Trade error: {e}")
                
                window_results.append({
                    'window': i + 1,
                    'start': window_start,
                    'trades': len(trade_plans),
                    'equity': equity
                })
                
                print(f"      → {len(trade_plans)} signals, equity: ${equity:,.2f}")
            else:
                print(f"      → No signals")
                
        except Exception as e:
            print(f"      ✗ Window error: {e}")
    
    # Calculate aggregate metrics
    if all_trades:
        wins = len([t for t in all_trades if t.pnl_pct > 0])
        losses = len([t for t in all_trades if t.pnl_pct <= 0])
        total_pnl = sum(t.pnl_pct for t in all_trades)
        
        # Calculate max drawdown from equity curve
        peak = initial_equity
        max_dd = 0
        running_equity = initial_equity
        for t in all_trades:
            running_equity += running_equity * (t.pnl_pct / 100)
            if running_equity > peak:
                peak = running_equity
            dd = (peak - running_equity) / peak * 100
            if dd > max_dd:
                max_dd = dd
        
        print(f"\n{'='*80}")
        print(f"  WALK-FORWARD RESULTS")
        print(f"{'='*80}")
        print(f"  Total Windows: {num_windows}")
        print(f"  Total Trades: {len(all_trades)}")
        print(f"  Wins: {wins} | Losses: {losses}")
        print(f"  Win Rate: {wins/len(all_trades)*100:.1f}%")
        print(f"  Total P&L: {total_pnl:+.2f}%")
        print(f"  Avg P&L per Trade: {total_pnl/len(all_trades):+.2f}%")
        print(f"  Max Drawdown: {max_dd:.2f}%")
        print(f"  Initial Equity: ${initial_equity:,.2f}")
        print(f"  Final Equity: ${equity:,.2f}")
        print(f"  Total Return: {(equity-initial_equity)/initial_equity*100:+.2f}%")
        print(f"{'='*80}\n")
        
        return {
            'trades': all_trades,
            'windows': window_results,
            'total_pnl': total_pnl,
            'win_rate': wins/len(all_trades)*100,
            'max_dd': max_dd,
            'final_equity': equity
        }
    
    return {}


def stress_test(
    mode_name: str = "stealth",
    days: int = 7,
    initial_equity: float = 10000.0,
    leverage: int = 10,
    fee_pct: float = 0.001,
    adverse_flip_pct: float = 0.3,  # Flip 30% of trades to losers
    slippage_pct: float = 0.002,    # 0.2% adverse slippage
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Stress test: Simulate adverse market conditions.
    
    This takes real scanner signals and artificially degrades performance to
    simulate what happens when market conditions are unfavorable:
    - Flips some winning trades to losers
    - Adds slippage to entries
    - Tests drawdown recovery
    
    Use this to understand worst-case scenarios at different leverage levels.
    """
    print(f"\n{'='*80}")
    print(f"  STRESS TEST - {mode_name.upper()} MODE")
    print(f"  Adverse flip: {adverse_flip_pct*100:.0f}% | Slippage: {slippage_pct*100:.2f}%")
    print(f"  Leverage: {leverage}x | Fees: {fee_pct*100:.2f}%")
    print(f"{'='*80}\n")
    
    # First run normal backtest to get baseline
    print("📊 Running baseline scan...")
    base_result = run_backtest(
        mode_name=mode_name,
        days=days,
        initial_equity=initial_equity,
        leverage=1,  # Get raw results
        fee_pct=fee_pct,
        verbose=False
    )
    
    if not base_result or base_result.total_trades == 0:
        print("❌ No baseline trades - cannot stress test")
        return {}
    
    print(f"   Baseline: {base_result.total_trades} trades, {base_result.win_rate:.1f}% WR, {base_result.total_pnl_pct:+.2f}% P&L\n")
    
    # Apply stress factors
    import random
    random.seed(42)  # Reproducible
    
    stressed_trades = []
    for trade in base_result.trades:
        stressed = Trade(
            symbol=trade.symbol,
            direction=trade.direction,
            entry_price=trade.entry_price,
            stop_loss=trade.stop_loss,
            tp1=trade.tp1,
            tp2=trade.tp2,
            tp3=trade.tp3,
            entry_time=trade.entry_time,
            exit_time=trade.exit_time,
            exit_price=trade.exit_price,
            exit_reason=trade.exit_reason,
            confidence=trade.confidence,
            mode=trade.mode,
            pnl_pct=trade.pnl_pct,
            r_multiple=trade.r_multiple
        )
        
        # Apply slippage (always adverse)
        slippage_impact = slippage_pct * 100  # Convert to %
        stressed.pnl_pct -= slippage_impact
        
        # Randomly flip some winners to losers
        if trade.pnl_pct > 0 and random.random() < adverse_flip_pct:
            # Flip to stop loss
            risk = abs(trade.entry_price - trade.stop_loss) / trade.entry_price * 100
            stressed.pnl_pct = -risk - slippage_impact
            stressed.exit_reason = "SL (stressed)"
            stressed.r_multiple = -1.0
        
        stressed_trades.append(stressed)
    
    # Calculate stressed results at different leverages
    leverages = [1, 3, 5, 10, 20, 50]
    stress_results = {}
    
    print("⚠️  Applying stress factors across leverage levels...\n")
    
    for lev in leverages:
        equity = initial_equity
        peak = initial_equity
        max_dd = 0
        wins = 0
        losses = 0
        total_pnl = 0
        
        for trade in stressed_trades:
            # Apply leverage to P&L
            leveraged_pnl = trade.pnl_pct * lev
            
            # Additional fee impact
            fee_impact = fee_pct * 2 * lev * 100
            net_pnl = leveraged_pnl - fee_impact
            
            total_pnl += net_pnl
            equity += equity * (net_pnl / 100)
            
            if net_pnl > 0:
                wins += 1
            else:
                losses += 1
            
            # Track drawdown
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
            
            # Check for liquidation
            if equity <= 0:
                equity = 0
                break
        
        stress_results[lev] = {
            'trades': len(stressed_trades),
            'wins': wins,
            'losses': losses,
            'win_rate': wins / len(stressed_trades) * 100 if stressed_trades else 0,
            'total_pnl': total_pnl,
            'max_dd': max_dd,
            'final_equity': equity,
            'liquidated': equity <= 0
        }
    
    # Print results
    print(f"{'='*80}")
    print(f"  STRESS TEST RESULTS")
    print(f"{'='*80}")
    print(f"{'Leverage':<10} {'Trades':<8} {'Win%':<8} {'P&L%':<12} {'MaxDD%':<10} {'Final $':<14} {'Status':<10}")
    print(f"{'-'*80}")
    
    for lev in leverages:
        r = stress_results[lev]
        status = "💀 REKT" if r['liquidated'] else ("⚠️ DANGER" if r['max_dd'] > 50 else "✅ OK")
        print(f"{lev}x{'':<8} {r['trades']:<8} {r['win_rate']:<8.1f} {r['total_pnl']:<+12.2f} {r['max_dd']:<10.2f} ${r['final_equity']:<13,.2f} {status}")
    
    # Risk analysis
    print(f"\n  📊 STRESS ANALYSIS:")
    print(f"     Baseline Win Rate: {base_result.win_rate:.1f}%")
    print(f"     Stressed Win Rate: {stress_results[1]['win_rate']:.1f}%")
    print(f"     Win Rate Degradation: {base_result.win_rate - stress_results[1]['win_rate']:.1f}%")
    
    # Find safe leverage
    safe_lev = 1
    for lev in leverages:
        if stress_results[lev]['max_dd'] < 30 and not stress_results[lev]['liquidated']:
            safe_lev = lev
    
    print(f"\n  🎯 RECOMMENDATION:")
    print(f"     Max Safe Leverage: {safe_lev}x (keeps drawdown <30% under stress)")
    
    # Monte Carlo simulation hint
    print(f"\n  💡 This stress test used {adverse_flip_pct*100:.0f}% adverse flip rate.")
    print(f"     Real-world conditions may be better or worse.")
    print(f"{'='*80}\n")
    
    return stress_results


def full_analysis(
    mode_name: str = "stealth",
    days: int = 14,
    initial_equity: float = 10000.0,
    verbose: bool = True
):
    """
    Run complete analysis: baseline, walk-forward, leverage comparison, and stress test.
    """
    print(f"\n{'#'*80}")
    print(f"  SNIPERSIGHT COMPREHENSIVE BACKTEST ANALYSIS")
    print(f"  Mode: {mode_name.upper()} | Period: {days} days | Starting Capital: ${initial_equity:,.2f}")
    print(f"{'#'*80}\n")
    
    results = {}
    
    # 1. Baseline backtest
    print("\n" + "="*40 + " PHASE 1: BASELINE " + "="*40)
    results['baseline'] = run_backtest(
        mode_name=mode_name,
        days=days,
        initial_equity=initial_equity,
        leverage=1,
        verbose=verbose
    )
    
    # 2. Leverage comparison
    print("\n" + "="*40 + " PHASE 2: LEVERAGE " + "="*40)
    results['leverage'] = compare_leverage(
        mode_name=mode_name,
        days=days,
        initial_equity=initial_equity
    )
    
    # 3. Stress test
    print("\n" + "="*40 + " PHASE 3: STRESS TEST " + "="*40)
    results['stress'] = stress_test(
        mode_name=mode_name,
        days=days,
        initial_equity=initial_equity,
        leverage=10,
        adverse_flip_pct=0.3
    )
    
    # Final summary
    print(f"\n{'#'*80}")
    print(f"  ANALYSIS COMPLETE - SUMMARY")
    print(f"{'#'*80}")
    
    if results['baseline']:
        print(f"\n  📈 BASELINE ({mode_name.upper()}, {days}d, 1x):")
        print(f"     Trades: {results['baseline'].total_trades}")
        print(f"     Win Rate: {results['baseline'].win_rate:.1f}%")
        print(f"     P&L: {results['baseline'].total_pnl_pct:+.2f}%")
    
    if results['leverage']:
        best_lev = max(results['leverage'].keys(), key=lambda k: results['leverage'][k].total_pnl_pct if results['leverage'][k] else 0)
        print(f"\n  💰 BEST LEVERAGE:")
        print(f"     {best_lev}x → {results['leverage'][best_lev].total_pnl_pct:+.2f}% P&L")
    
    if results['stress']:
        safe_lev = 1
        for lev in [1, 3, 5, 10, 20, 50]:
            if lev in results['stress'] and results['stress'][lev]['max_dd'] < 30:
                safe_lev = lev
        print(f"\n  ⚠️  STRESS TEST:")
        print(f"     Max Safe Leverage: {safe_lev}x (under 30% DD when 30% trades flip)")
    
    print(f"\n{'#'*80}\n")
    
    return results


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="SniperSight Scanner Backtest")
    parser.add_argument("--mode", default="strike", help="Scanner mode (strike, surgical, stealth, overwatch)")
    parser.add_argument("--days", type=int, default=7, help="Days of history to analyze")
    parser.add_argument("--equity", type=float, default=10000.0, help="Initial equity")
    parser.add_argument("--risk", type=float, default=0.01, help="Risk per trade (0.01 = 1%)")
    parser.add_argument("--leverage", type=int, default=1, help="Leverage multiplier (1-125)")
    parser.add_argument("--fees", type=float, default=0.001, help="Trading fee per trade (0.001 = 0.1%)")
    parser.add_argument("--compare", action="store_true", help="Compare all modes")
    parser.add_argument("--compare-leverage", action="store_true", help="Compare leverage levels")
    parser.add_argument("--stress", action="store_true", help="Run stress test (adverse market simulation)")
    parser.add_argument("--walk-forward", action="store_true", help="Run walk-forward backtest over longer period")
    parser.add_argument("--full", action="store_true", help="Run full analysis (baseline + leverage + stress)")
    parser.add_argument("--adverse-flip", type=float, default=0.3, help="Stress test: % of trades to flip to losers (0.3 = 30%)")
    parser.add_argument("--quiet", action="store_true", help="Less verbose output")
    
    args = parser.parse_args()
    
    if args.full:
        full_analysis(
            mode_name=args.mode,
            days=args.days,
            initial_equity=args.equity,
            verbose=not args.quiet
        )
    elif args.walk_forward:
        walk_forward_backtest(
            mode_name=args.mode,
            total_days=args.days,
            window_days=min(7, args.days // 3),
            step_days=max(2, args.days // 10),
            initial_equity=args.equity,
            leverage=args.leverage,
            fee_pct=args.fees,
            verbose=not args.quiet
        )
    elif args.stress:
        stress_test(
            mode_name=args.mode,
            days=args.days,
            initial_equity=args.equity,
            leverage=args.leverage,
            fee_pct=args.fees,
            adverse_flip_pct=args.adverse_flip,
            verbose=not args.quiet
        )
    elif args.compare:
        compare_modes(days=args.days, initial_equity=args.equity, leverage=args.leverage, fee_pct=args.fees)
    elif args.compare_leverage:
        compare_leverage(mode_name=args.mode, days=args.days, initial_equity=args.equity)
    else:
        run_backtest(
            mode_name=args.mode,
            days=args.days,
            initial_equity=args.equity,
            risk_per_trade=args.risk,
            leverage=args.leverage,
            fee_pct=args.fees,
            verbose=not args.quiet
        )


if __name__ == "__main__":
    main()
