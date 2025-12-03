"""
SniperSight Historical Backtest Harness

Simulates trading P&L using scanner signals across historical periods.
Uses real exchange data to walk through time and evaluate profitability.

Usage:
    python -m backend.tests.backtest.historical_backtest --capital 10000 --mode strike
"""

import sys
sys.path.insert(0, '.')

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import time
import argparse

from backend.shared.config.scanner_modes import get_mode
from backend.shared.config.defaults import ScanConfig
from backend.engine.orchestrator import Orchestrator
from backend.shared.models.planner import TradePlan


class TradeStatus(Enum):
    OPEN = "open"
    TP1_HIT = "tp1_hit"
    TP2_HIT = "tp2_hit"
    TP3_HIT = "tp3_hit"
    STOPPED_OUT = "stopped_out"
    EXPIRED = "expired"


@dataclass
class BacktestTrade:
    """Represents a single trade in the backtest."""
    symbol: str
    direction: str  # LONG or SHORT
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    tp1_pct: float  # Percentage of position to close at TP1
    tp2_pct: float
    tp3_pct: float
    position_size: float  # In USD
    entry_time: datetime
    confidence_score: float
    risk_reward: float
    
    # Results
    status: TradeStatus = TradeStatus.OPEN
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    
    # Partial tracking
    realized_pnl: float = 0.0
    remaining_position: float = 1.0  # 1.0 = full position


@dataclass
class BacktestResult:
    """Complete backtest results."""
    start_capital: float
    final_capital: float
    total_pnl: float
    total_pnl_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    
    def summary(self) -> str:
        return f"""
╔══════════════════════════════════════════════════════════════════╗
║                    BACKTEST RESULTS                               ║
╠══════════════════════════════════════════════════════════════════╣
║  Starting Capital:    ${self.start_capital:>12,.2f}               ║
║  Final Capital:       ${self.final_capital:>12,.2f}               ║
║  Total P&L:           ${self.total_pnl:>12,.2f} ({self.total_pnl_pct:>+6.2f}%)         ║
╠══════════════════════════════════════════════════════════════════╣
║  Total Trades:        {self.total_trades:>6}                                  ║
║  Winning Trades:      {self.winning_trades:>6} ({self.win_rate*100:>5.1f}%)                      ║
║  Losing Trades:       {self.losing_trades:>6}                                  ║
╠══════════════════════════════════════════════════════════════════╣
║  Average Win:         ${self.avg_win:>12,.2f}                      ║
║  Average Loss:        ${self.avg_loss:>12,.2f}                      ║
║  Profit Factor:       {self.profit_factor:>8.2f}                              ║
╠══════════════════════════════════════════════════════════════════╣
║  Max Drawdown:        ${self.max_drawdown:>12,.2f} ({self.max_drawdown_pct:>5.2f}%)          ║
║  Sharpe Ratio:        {self.sharpe_ratio:>8.2f}                              ║
╚══════════════════════════════════════════════════════════════════╝
"""


class HistoricalDataAdapter:
    """
    Adapter that provides historical data snapshots for backtesting.
    Simulates what the scanner would have seen at each point in time.
    """
    
    def __init__(self, all_data: Dict[str, Dict[str, pd.DataFrame]], current_index: int = -1):
        """
        Args:
            all_data: Dict of symbol -> timeframe -> full historical DataFrame
            current_index: Index into the data representing "now" in the simulation
        """
        self.all_data = all_data
        self.current_index = current_index  # -1 means latest
        
    def set_time_index(self, index: int):
        """Move the simulation time forward."""
        self.current_index = index
        
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
        """Return historical data up to current_index."""
        if symbol not in self.all_data:
            symbol = list(self.all_data.keys())[0]
        if timeframe not in self.all_data[symbol]:
            timeframe = '1h'
            
        df = self.all_data[symbol][timeframe]
        
        if self.current_index == -1 or self.current_index >= len(df):
            return df.tail(limit).reset_index()
        else:
            end_idx = self.current_index + 1
            start_idx = max(0, end_idx - limit)
            return df.iloc[start_idx:end_idx].reset_index()
    
    def get_ticker(self, symbol: str) -> dict:
        """Get current price at simulation time."""
        if symbol in self.all_data and '1h' in self.all_data[symbol]:
            df = self.all_data[symbol]['1h']
            if self.current_index == -1 or self.current_index >= len(df):
                price = df['close'].iloc[-1]
            else:
                price = df['close'].iloc[self.current_index]
            return {'last': price}
        return {'last': 0}
    
    def get_future_candles(self, symbol: str, timeframe: str, start_index: int, num_candles: int) -> pd.DataFrame:
        """Get candles AFTER the current index for trade resolution."""
        if symbol not in self.all_data or timeframe not in self.all_data[symbol]:
            return pd.DataFrame()
        
        df = self.all_data[symbol][timeframe]
        end_idx = min(start_index + num_candles, len(df))
        return df.iloc[start_index:end_idx]


class BacktestEngine:
    """
    Main backtest engine that simulates trading over historical data.
    """
    
    def __init__(
        self,
        symbols: List[str],
        start_capital: float = 10000,
        risk_per_trade: float = 0.02,  # 2% risk per trade
        mode: str = 'strike',
        max_concurrent_trades: int = 3,
        leverage: int = 1
    ):
        self.symbols = symbols
        self.start_capital = start_capital
        self.current_capital = start_capital
        self.risk_per_trade = risk_per_trade
        self.mode = mode
        self.max_concurrent_trades = max_concurrent_trades
        self.leverage = leverage
        
        self.trades: List[BacktestTrade] = []
        self.open_trades: List[BacktestTrade] = []
        self.equity_curve: List[float] = [start_capital]
        
        # Statistics
        self.peak_equity = start_capital
        self.max_drawdown = 0
        
    def fetch_historical_data(self, days: int = 30) -> Dict[str, Dict[str, pd.DataFrame]]:
        """Fetch historical data from exchange."""
        print(f"📊 Fetching {days} days of historical data...")
        
        exchange = ccxt.cryptocom({'enableRateLimit': True})
        timeframes = ['5m', '15m', '1h', '4h']
        all_data = {}
        
        # Calculate candle limits based on days
        tf_limits = {
            '5m': min(days * 288, 1000),   # 288 per day
            '15m': min(days * 96, 1000),   # 96 per day
            '1h': min(days * 24, 1000),    # 24 per day
            '4h': min(days * 6, 500)       # 6 per day
        }
        
        for symbol in self.symbols:
            all_data[symbol] = {}
            for tf in timeframes:
                try:
                    ohlcv = exchange.fetch_ohlcv(symbol, tf, limit=tf_limits[tf])
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    df.set_index('timestamp', inplace=True)
                    all_data[symbol][tf] = df
                    time.sleep(0.2)
                except Exception as e:
                    print(f"   Warning: Failed to fetch {symbol} {tf}: {e}")
            print(f"   ✓ {symbol}: {len(all_data[symbol].get('1h', []))} 1H candles")
        
        return all_data
    
    def calculate_position_size(self, entry_price: float, stop_loss: float) -> float:
        """
        Calculate position size based on risk management.
        Risk = (Entry - Stop) / Entry * Position Size
        Position Size = Risk Amount / (Entry - Stop) * Entry
        """
        risk_amount = self.current_capital * self.risk_per_trade
        risk_per_unit = abs(entry_price - stop_loss)
        
        if risk_per_unit == 0:
            return 0
            
        # Position size in USD
        position_size = (risk_amount / risk_per_unit) * entry_price
        
        # Apply leverage
        position_size *= self.leverage
        
        # Cap at available capital
        max_position = self.current_capital * self.leverage * 0.5  # Max 50% per trade
        position_size = min(position_size, max_position)
        
        return position_size
    
    def resolve_trade(
        self, 
        trade: BacktestTrade, 
        future_candles: pd.DataFrame
    ) -> BacktestTrade:
        """
        Simulate trade outcome using future price action.
        Uses OHLC to determine if stops/targets were hit.
        """
        if future_candles.empty:
            trade.status = TradeStatus.EXPIRED
            return trade
        
        is_long = trade.direction == "LONG"
        remaining_position = 1.0
        realized_pnl = 0.0
        
        for idx, candle in future_candles.iterrows():
            high = candle['high']
            low = candle['low']
            close = candle['close']
            candle_time = idx if isinstance(idx, datetime) else candle.get('timestamp', datetime.now())
            
            # Check stop loss first (worst case)
            stop_hit = (low <= trade.stop_loss) if is_long else (high >= trade.stop_loss)
            
            if stop_hit:
                # Full remaining position stopped out
                trade.exit_price = trade.stop_loss
                trade.exit_time = candle_time
                
                if is_long:
                    loss_pct = (trade.stop_loss - trade.entry_price) / trade.entry_price
                else:
                    loss_pct = (trade.entry_price - trade.stop_loss) / trade.entry_price
                
                loss = trade.position_size * remaining_position * loss_pct
                realized_pnl += loss
                trade.status = TradeStatus.STOPPED_OUT
                break
            
            # Check TP1
            if remaining_position > 0 and trade.status == TradeStatus.OPEN:
                tp1_hit = (high >= trade.tp1) if is_long else (low <= trade.tp1)
                if tp1_hit:
                    # Close TP1 portion
                    if is_long:
                        profit_pct = (trade.tp1 - trade.entry_price) / trade.entry_price
                    else:
                        profit_pct = (trade.entry_price - trade.tp1) / trade.entry_price
                    
                    portion = trade.tp1_pct / 100
                    profit = trade.position_size * portion * profit_pct
                    realized_pnl += profit
                    remaining_position -= portion
                    trade.status = TradeStatus.TP1_HIT
            
            # Check TP2
            if remaining_position > 0 and trade.status == TradeStatus.TP1_HIT:
                tp2_hit = (high >= trade.tp2) if is_long else (low <= trade.tp2)
                if tp2_hit:
                    if is_long:
                        profit_pct = (trade.tp2 - trade.entry_price) / trade.entry_price
                    else:
                        profit_pct = (trade.entry_price - trade.tp2) / trade.entry_price
                    
                    portion = trade.tp2_pct / 100
                    profit = trade.position_size * portion * profit_pct
                    realized_pnl += profit
                    remaining_position -= portion
                    trade.status = TradeStatus.TP2_HIT
            
            # Check TP3
            if remaining_position > 0 and trade.status == TradeStatus.TP2_HIT:
                tp3_hit = (high >= trade.tp3) if is_long else (low <= trade.tp3)
                if tp3_hit:
                    if is_long:
                        profit_pct = (trade.tp3 - trade.entry_price) / trade.entry_price
                    else:
                        profit_pct = (trade.entry_price - trade.tp3) / trade.entry_price
                    
                    portion = trade.tp3_pct / 100
                    profit = trade.position_size * portion * profit_pct
                    realized_pnl += profit
                    remaining_position = 0
                    trade.status = TradeStatus.TP3_HIT
                    trade.exit_price = trade.tp3
                    trade.exit_time = candle_time
                    break
        
        # If trade didn't fully close, mark as expired and close at last price
        if remaining_position > 0 and trade.status != TradeStatus.STOPPED_OUT:
            last_close = future_candles['close'].iloc[-1]
            trade.exit_price = last_close
            trade.exit_time = future_candles.index[-1] if hasattr(future_candles.index[-1], 'timestamp') else datetime.now()
            
            if is_long:
                final_pnl_pct = (last_close - trade.entry_price) / trade.entry_price
            else:
                final_pnl_pct = (trade.entry_price - last_close) / trade.entry_price
            
            final_pnl = trade.position_size * remaining_position * final_pnl_pct
            realized_pnl += final_pnl
            
            if trade.status == TradeStatus.OPEN:
                trade.status = TradeStatus.EXPIRED
        
        trade.pnl = realized_pnl
        trade.pnl_pct = (realized_pnl / trade.position_size) * 100 if trade.position_size > 0 else 0
        trade.remaining_position = remaining_position
        trade.realized_pnl = realized_pnl
        
        return trade
    
    def run_backtest(
        self, 
        all_data: Dict[str, Dict[str, pd.DataFrame]],
        scan_interval: int = 24,  # Scan every N 1H candles (24 = daily)
        max_trade_duration: int = 72,  # Max candles to hold a trade
        verbose: bool = True
    ) -> BacktestResult:
        """
        Run the full backtest simulation.
        
        Args:
            all_data: Historical data dict
            scan_interval: How often to scan for new signals (in 1H candles)
            max_trade_duration: Maximum candles to hold a trade before expiry
            verbose: Print progress
        """
        # Get the minimum data length across all symbols
        min_candles = min(len(all_data[s]['1h']) for s in self.symbols)
        
        # Need at least 200 candles for indicators + some room for trades
        start_index = 200
        end_index = min_candles - max_trade_duration
        
        if end_index <= start_index:
            print("❌ Not enough data for backtest")
            return BacktestResult(
                start_capital=self.start_capital,
                final_capital=self.start_capital,
                total_pnl=0, total_pnl_pct=0,
                total_trades=0, winning_trades=0, losing_trades=0,
                win_rate=0, avg_win=0, avg_loss=0, profit_factor=0,
                max_drawdown=0, max_drawdown_pct=0, sharpe_ratio=0
            )
        
        adapter = HistoricalDataAdapter(all_data)
        mode_config = get_mode(self.mode)
        available_tfs = list(all_data[self.symbols[0]].keys())
        
        print(f"\n🚀 Starting backtest: {start_index} to {end_index} ({end_index - start_index} scan points)")
        print(f"   Mode: {self.mode} | Capital: ${self.start_capital:,.2f} | Risk: {self.risk_per_trade*100:.1f}%")
        
        signals_generated = 0
        
        # Walk through time
        for i in range(start_index, end_index, scan_interval):
            adapter.set_time_index(i)
            current_time = all_data[self.symbols[0]]['1h'].index[i]
            
            # Skip if at max concurrent trades
            if len(self.open_trades) >= self.max_concurrent_trades:
                continue
            
            # Run scanner at this point in time
            try:
                cfg = ScanConfig(profile=self.mode)
                cfg.timeframes = tuple(tf for tf in mode_config.timeframes if tf in available_tfs)
                cfg.min_confluence_score = mode_config.min_confluence_score
                cfg.primary_planning_timeframe = mode_config.primary_planning_timeframe
                cfg.entry_timeframes = mode_config.entry_timeframes
                cfg.structure_timeframes = mode_config.structure_timeframes
                
                orch = Orchestrator(
                    config=cfg,
                    exchange_adapter=adapter,
                    debug_mode=False,
                    concurrency_workers=1
                )
                
                plans, _ = orch.scan(self.symbols)
                
                for plan in plans:
                    if len(self.open_trades) >= self.max_concurrent_trades:
                        break
                    
                    # Skip if already have trade in this symbol
                    if any(t.symbol == plan.symbol for t in self.open_trades):
                        continue
                    
                    signals_generated += 1
                    
                    # Create trade from plan
                    avg_entry = (plan.entry_zone.near_entry + plan.entry_zone.far_entry) / 2
                    position_size = self.calculate_position_size(avg_entry, plan.stop_loss.level)
                    
                    if position_size < 10:  # Minimum $10 position
                        continue
                    
                    trade = BacktestTrade(
                        symbol=plan.symbol,
                        direction=plan.direction,
                        entry_price=avg_entry,
                        stop_loss=plan.stop_loss.level,
                        tp1=plan.targets[0].level if len(plan.targets) > 0 else avg_entry * 1.02,
                        tp2=plan.targets[1].level if len(plan.targets) > 1 else avg_entry * 1.04,
                        tp3=plan.targets[2].level if len(plan.targets) > 2 else avg_entry * 1.06,
                        tp1_pct=plan.targets[0].percentage if len(plan.targets) > 0 else 50,
                        tp2_pct=plan.targets[1].percentage if len(plan.targets) > 1 else 30,
                        tp3_pct=plan.targets[2].percentage if len(plan.targets) > 2 else 20,
                        position_size=position_size,
                        entry_time=current_time,
                        confidence_score=plan.confidence_score,
                        risk_reward=plan.risk_reward
                    )
                    
                    # Get future candles to resolve trade
                    future_candles = adapter.get_future_candles(
                        plan.symbol, '1h', i + 1, max_trade_duration
                    )
                    
                    # Resolve trade outcome
                    trade = self.resolve_trade(trade, future_candles)
                    
                    # Update capital
                    self.current_capital += trade.pnl
                    self.trades.append(trade)
                    self.equity_curve.append(self.current_capital)
                    
                    # Track drawdown
                    if self.current_capital > self.peak_equity:
                        self.peak_equity = self.current_capital
                    drawdown = self.peak_equity - self.current_capital
                    if drawdown > self.max_drawdown:
                        self.max_drawdown = drawdown
                    
                    if verbose and signals_generated % 5 == 0:
                        status_emoji = "✅" if trade.pnl > 0 else "❌"
                        print(f"   {status_emoji} {trade.symbol} {trade.direction}: ${trade.pnl:+,.2f} ({trade.status.value})")
                        
            except Exception as e:
                # Silently continue on errors
                pass
        
        # Calculate final statistics
        return self._calculate_results()
    
    def _calculate_results(self) -> BacktestResult:
        """Calculate final backtest statistics."""
        if not self.trades:
            return BacktestResult(
                start_capital=self.start_capital,
                final_capital=self.current_capital,
                total_pnl=0, total_pnl_pct=0,
                total_trades=0, winning_trades=0, losing_trades=0,
                win_rate=0, avg_win=0, avg_loss=0, profit_factor=0,
                max_drawdown=0, max_drawdown_pct=0, sharpe_ratio=0
            )
        
        total_pnl = sum(t.pnl for t in self.trades)
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]
        
        total_wins = sum(t.pnl for t in winning_trades)
        total_losses = abs(sum(t.pnl for t in losing_trades))
        
        avg_win = total_wins / len(winning_trades) if winning_trades else 0
        avg_loss = total_losses / len(losing_trades) if losing_trades else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Calculate Sharpe ratio (simplified - daily returns assumed)
        returns = []
        for i in range(1, len(self.equity_curve)):
            ret = (self.equity_curve[i] - self.equity_curve[i-1]) / self.equity_curve[i-1]
            returns.append(ret)
        
        if returns:
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe = (mean_return / std_return) * np.sqrt(252) if std_return > 0 else 0
        else:
            sharpe = 0
        
        max_dd_pct = (self.max_drawdown / self.peak_equity) * 100 if self.peak_equity > 0 else 0
        
        return BacktestResult(
            start_capital=self.start_capital,
            final_capital=self.current_capital,
            total_pnl=total_pnl,
            total_pnl_pct=(total_pnl / self.start_capital) * 100,
            total_trades=len(self.trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=len(winning_trades) / len(self.trades) if self.trades else 0,
            avg_win=avg_win,
            avg_loss=-avg_loss,  # Show as negative
            profit_factor=profit_factor,
            max_drawdown=self.max_drawdown,
            max_drawdown_pct=max_dd_pct,
            sharpe_ratio=sharpe,
            trades=self.trades,
            equity_curve=self.equity_curve
        )


def print_trade_log(trades: List[BacktestTrade], limit: int = 20):
    """Print detailed trade log."""
    print("\n" + "=" * 90)
    print("TRADE LOG (Last {} trades)".format(min(limit, len(trades))))
    print("=" * 90)
    print(f"{'Symbol':<12} {'Dir':<6} {'Entry':>10} {'Exit':>10} {'P&L':>12} {'Status':<15}")
    print("-" * 90)
    
    for trade in trades[-limit:]:
        pnl_str = f"${trade.pnl:+,.2f}"
        pnl_color = "✅" if trade.pnl > 0 else "❌"
        print(f"{trade.symbol:<12} {trade.direction:<6} ${trade.entry_price:>9,.2f} ${trade.exit_price or 0:>9,.2f} {pnl_str:>12} {pnl_color} {trade.status.value}")


def print_equity_chart(equity_curve: List[float], width: int = 60):
    """Print ASCII equity curve."""
    if len(equity_curve) < 2:
        return
    
    print("\n" + "=" * 70)
    print("EQUITY CURVE")
    print("=" * 70)
    
    min_eq = min(equity_curve)
    max_eq = max(equity_curve)
    range_eq = max_eq - min_eq or 1
    
    height = 15
    chart = []
    
    # Sample points if too many
    step = max(1, len(equity_curve) // width)
    sampled = equity_curve[::step][:width]
    
    for row in range(height, -1, -1):
        line = ""
        threshold = min_eq + (range_eq * row / height)
        
        for val in sampled:
            if val >= threshold:
                line += "█"
            else:
                line += " "
        
        # Add Y-axis labels
        if row == height:
            line = f"${max_eq:>10,.0f} |" + line
        elif row == 0:
            line = f"${min_eq:>10,.0f} |" + line
        else:
            line = f"{'':>11} |" + line
        
        chart.append(line)
    
    for line in chart:
        print(line)
    
    print(" " * 12 + "+" + "-" * len(sampled))
    print(" " * 12 + f"Start{' ' * (len(sampled) - 10)}End")


def main():
    parser = argparse.ArgumentParser(description='SniperSight Historical Backtest')
    parser.add_argument('--capital', type=float, default=10000, help='Starting capital in USD')
    parser.add_argument('--risk', type=float, default=0.02, help='Risk per trade (0.02 = 2%)')
    parser.add_argument('--mode', type=str, default='strike', help='Scanner mode')
    parser.add_argument('--days', type=int, default=30, help='Days of historical data')
    parser.add_argument('--leverage', type=int, default=1, help='Leverage multiplier')
    parser.add_argument('--scan-interval', type=int, default=12, help='Scan every N hours')
    parser.add_argument('--symbols', type=str, default='BTC/USDT,ETH/USDT,SOL/USDT', help='Comma-separated symbols')
    
    args = parser.parse_args()
    
    symbols = [s.strip() for s in args.symbols.split(',')]
    
    print("=" * 70)
    print("🎯 SNIPERSIGHT HISTORICAL BACKTEST")
    print("=" * 70)
    print(f"Capital: ${args.capital:,.2f} | Risk: {args.risk*100:.1f}% | Mode: {args.mode}")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Period: {args.days} days | Leverage: {args.leverage}x")
    print("=" * 70)
    
    engine = BacktestEngine(
        symbols=symbols,
        start_capital=args.capital,
        risk_per_trade=args.risk,
        mode=args.mode,
        leverage=args.leverage
    )
    
    # Fetch data
    all_data = engine.fetch_historical_data(days=args.days)
    
    # Run backtest
    result = engine.run_backtest(
        all_data=all_data,
        scan_interval=args.scan_interval,
        verbose=True
    )
    
    # Print results
    print(result.summary())
    
    if result.trades:
        print_trade_log(result.trades)
        print_equity_chart(result.equity_curve)
        
        # Additional stats
        print("\n" + "=" * 70)
        print("TRADE BREAKDOWN BY STATUS")
        print("=" * 70)
        
        status_counts = {}
        for trade in result.trades:
            status = trade.status.value
            if status not in status_counts:
                status_counts[status] = {'count': 0, 'pnl': 0}
            status_counts[status]['count'] += 1
            status_counts[status]['pnl'] += trade.pnl
        
        for status, data in sorted(status_counts.items()):
            emoji = "🎯" if 'tp' in status else ("❌" if 'stop' in status else "⏱️")
            print(f"  {emoji} {status:<15}: {data['count']:>3} trades | P&L: ${data['pnl']:>+10,.2f}")
    
    return result


if __name__ == "__main__":
    result = main()
