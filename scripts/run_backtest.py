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
    ):
        self.initial_equity = initial_equity
        self.equity = initial_equity
        self.risk_per_trade = risk_per_trade
        self.max_concurrent = max_concurrent
        self.partial_tp = partial_tp
        self.tp1_pct = tp1_pct
        self.tp2_pct = tp2_pct
        self.tp3_pct = tp3_pct
        
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
        partial_tp=True
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


def compare_modes(days: int = 7, initial_equity: float = 10000.0):
    """Compare performance across all scanner modes."""
    
    print(f"\n{'='*60}")
    print(f"  MODE COMPARISON BACKTEST")
    print(f"{'='*60}\n")
    
    modes = ["strike", "surgical", "stealth", "overwatch"]
    results = {}
    
    for mode_name in modes:
        print(f"\n--- Testing {mode_name.upper()} ---")
        try:
            result = run_backtest(
                mode_name=mode_name,
                days=days,
                initial_equity=initial_equity,
                verbose=False
            )
            results[mode_name] = result
        except Exception as e:
            print(f"Error testing {mode_name}: {e}")
            results[mode_name] = None
    
    # Summary comparison
    print(f"\n{'='*60}")
    print(f"  MODE COMPARISON SUMMARY")
    print(f"{'='*60}")
    print(f"{'Mode':<12} {'Trades':<8} {'Win%':<8} {'P&L%':<10} {'Avg R':<8} {'PF':<8}")
    print(f"{'-'*60}")
    
    for mode_name, result in results.items():
        if result:
            print(f"{mode_name.upper():<12} {result.total_trades:<8} {result.win_rate:<8.1f} {result.total_pnl_pct:<+10.2f} {result.avg_r:<+8.2f} {result.profit_factor:<8.2f}")
        else:
            print(f"{mode_name.upper():<12} {'ERROR':<8}")
    
    print(f"{'='*60}\n")
    
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
    parser.add_argument("--compare", action="store_true", help="Compare all modes")
    parser.add_argument("--quiet", action="store_true", help="Less verbose output")
    
    args = parser.parse_args()
    
    if args.compare:
        compare_modes(days=args.days, initial_equity=args.equity)
    else:
        run_backtest(
            mode_name=args.mode,
            days=args.days,
            initial_equity=args.equity,
            risk_per_trade=args.risk,
            verbose=not args.quiet
        )


if __name__ == "__main__":
    main()
