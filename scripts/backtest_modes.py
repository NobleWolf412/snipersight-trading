#!/usr/bin/env python3
"""
SniperSight Mode Backtest

Simulates running the scanner in each mode on historical data.
- Scans 3x per day, every other day
- Tracks win/loss based on whether price hit TP1 or SL first
- Reports win rate, starting balance, ending balance per mode
"""

import logging
import sys
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import time

# Suppress noisy logs
logging.basicConfig(level=logging.WARNING)
for logger_name in ['backend.data', 'backend.strategy', 'backend.engine', 'backend.indicators']:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

from backend.engine.orchestrator import Orchestrator
from backend.data.adapters.phemex import PhemexAdapter
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode, MODES


@dataclass
class Trade:
    """Single trade record."""
    symbol: str
    direction: str  # LONG or SHORT
    entry_price: float
    stop_loss: float
    tp1_price: float
    tp1_pct: float  # percentage of position at TP1
    risk_reward: float
    confidence: float
    scan_time: datetime
    mode: str
    # Filled after resolution
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # 'TP1', 'SL', 'TIMEOUT'
    pnl_pct: Optional[float] = None
    resolved: bool = False


@dataclass
class ModeStats:
    """Statistics for a single mode."""
    mode: str
    starting_balance: float = 10000.0
    current_balance: float = 10000.0
    trades: List[Trade] = field(default_factory=list)
    wins: int = 0
    losses: int = 0
    timeouts: int = 0
    
    @property
    def total_trades(self) -> int:
        return self.wins + self.losses + self.timeouts
    
    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return (self.wins / self.total_trades) * 100
    
    @property
    def pnl_pct(self) -> float:
        return ((self.current_balance - self.starting_balance) / self.starting_balance) * 100


def fetch_future_candles(adapter: PhemexAdapter, symbol: str, timeframe: str, 
                          start_ts: int, limit: int = 100) -> List[Dict]:
    """Fetch candles after a specific timestamp for trade resolution."""
    try:
        # Phemex uses milliseconds
        candles = adapter.exchange.fetch_ohlcv(
            symbol, timeframe, since=start_ts, limit=limit
        )
        return [
            {'timestamp': c[0], 'open': c[1], 'high': c[2], 'low': c[3], 'close': c[4], 'volume': c[5]}
            for c in candles
        ]
    except Exception as e:
        logging.warning(f"Failed to fetch future candles for {symbol}: {e}")
        return []


def resolve_trade(trade: Trade, candles: List[Dict], max_hours: int = 48) -> Trade:
    """
    Resolve a trade by checking if TP1 or SL was hit first.
    
    Args:
        trade: The trade to resolve
        candles: Future candles after trade entry
        max_hours: Maximum time to hold before timeout
    """
    if not candles:
        trade.exit_reason = 'TIMEOUT'
        trade.pnl_pct = 0.0
        trade.resolved = True
        return trade
    
    entry = trade.entry_price
    sl = trade.stop_loss
    tp1 = trade.tp1_price
    
    for candle in candles:
        high = candle['high']
        low = candle['low']
        
        if trade.direction == 'LONG':
            # Check SL first (worst case)
            if low <= sl:
                trade.exit_price = sl
                trade.exit_reason = 'SL'
                trade.pnl_pct = ((sl - entry) / entry) * 100
                trade.resolved = True
                return trade
            # Check TP1
            if high >= tp1:
                trade.exit_price = tp1
                trade.exit_reason = 'TP1'
                trade.pnl_pct = ((tp1 - entry) / entry) * 100
                trade.resolved = True
                return trade
        else:  # SHORT
            # Check SL first (worst case)
            if high >= sl:
                trade.exit_price = sl
                trade.exit_reason = 'SL'
                trade.pnl_pct = ((entry - sl) / entry) * 100
                trade.resolved = True
                return trade
            # Check TP1
            if low <= tp1:
                trade.exit_price = tp1
                trade.exit_reason = 'TP1'
                trade.pnl_pct = ((entry - tp1) / entry) * 100
                trade.resolved = True
                return trade
    
    # Timeout - close at last candle's close
    if candles:
        last_close = candles[-1]['close']
        trade.exit_price = last_close
        trade.exit_reason = 'TIMEOUT'
        if trade.direction == 'LONG':
            trade.pnl_pct = ((last_close - entry) / entry) * 100
        else:
            trade.pnl_pct = ((entry - last_close) / entry) * 100
    else:
        trade.pnl_pct = 0.0
        trade.exit_reason = 'TIMEOUT'
    
    trade.resolved = True
    return trade


def run_backtest(
    modes: List[str],
    symbols: List[str],
    days_back: int = 14,
    scans_per_day: int = 3,
    scan_every_n_days: int = 2,
    risk_per_trade_pct: float = 2.0,
    starting_balance: float = 10000.0
) -> Dict[str, ModeStats]:
    """
    Run backtest across multiple modes.
    
    Args:
        modes: List of mode names to test
        symbols: Symbols to scan
        days_back: How many days of history to backtest
        scans_per_day: Number of scans per active day
        scan_every_n_days: Scan every N days (2 = every other day)
        risk_per_trade_pct: Risk percentage per trade
        starting_balance: Starting account balance
    
    Returns:
        Dict of mode name -> ModeStats
    """
    print(f"\n{'='*70}")
    print(f"🎯 SNIPERSIGHT MODE BACKTEST")
    print(f"{'='*70}")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Period: Last {days_back} days")
    print(f"Scan Schedule: {scans_per_day}x per day, every {scan_every_n_days} days")
    print(f"Risk per trade: {risk_per_trade_pct}%")
    print(f"Starting balance: ${starting_balance:,.2f}")
    print(f"{'='*70}\n")
    
    # Initialize adapter and orchestrator
    adapter = PhemexAdapter()
    default_config = ScanConfig(
        profile='recon',
        timeframes=('1h', '4h', '1d'),
        min_confluence_score=70.0,
        max_risk_pct=risk_per_trade_pct
    )
    orchestrator = Orchestrator(
        config=default_config,
        exchange_adapter=adapter,
        concurrency_workers=4
    )
    
    # Initialize stats for each mode
    mode_stats: Dict[str, ModeStats] = {
        mode: ModeStats(mode=mode, starting_balance=starting_balance, current_balance=starting_balance)
        for mode in modes
    }
    
    # Calculate scan timestamps (simulate historical scans)
    now = datetime.now(timezone.utc)
    scan_times = []
    
    for day_offset in range(days_back, 0, -1):
        if day_offset % scan_every_n_days != 0:
            continue
        
        base_date = now - timedelta(days=day_offset)
        # Scan at 8:00, 14:00, 20:00 UTC
        for hour in [8, 14, 20][:scans_per_day]:
            scan_time = base_date.replace(hour=hour, minute=0, second=0, microsecond=0)
            if scan_time < now - timedelta(days=2):  # Need 2 days for resolution
                scan_times.append(scan_time)
    
    print(f"📅 Simulating {len(scan_times)} scan sessions...")
    print()
    
    # Run scans for each mode
    for mode_name in modes:
        print(f"\n{'='*50}")
        print(f"🔫 Mode: {mode_name.upper()}")
        print(f"{'='*50}")
        
        mode = get_mode(mode_name)
        orchestrator.apply_mode(mode)
        
        stats = mode_stats[mode_name]
        signals_found = 0
        
        for i, scan_time in enumerate(scan_times):
            # Rate limiting
            if i > 0 and i % 5 == 0:
                time.sleep(1)  # Be nice to the API
            
            try:
                # Run scan
                signals, rejections = orchestrator.scan(symbols)
                
                if signals:
                    signals_found += len(signals)
                    
                    for signal in signals[:2]:  # Max 2 trades per scan
                        # Create trade record
                        entry_price = (signal.entry_zone.near_entry + signal.entry_zone.far_entry) / 2
                        tp1 = signal.targets[0] if signal.targets else None
                        
                        if not tp1:
                            continue
                        
                        trade = Trade(
                            symbol=signal.symbol,
                            direction=signal.direction,
                            entry_price=entry_price,
                            stop_loss=signal.stop_loss.price,
                            tp1_price=tp1.price,
                            tp1_pct=tp1.percentage,
                            risk_reward=signal.risk_reward,
                            confidence=signal.confidence_score,
                            scan_time=scan_time,
                            mode=mode_name
                        )
                        
                        # Fetch future candles to resolve trade
                        scan_ts_ms = int(scan_time.timestamp() * 1000)
                        future_candles = fetch_future_candles(
                            adapter, signal.symbol, '1h', scan_ts_ms, limit=48
                        )
                        
                        # Resolve trade
                        trade = resolve_trade(trade, future_candles, max_hours=48)
                        stats.trades.append(trade)
                        
                        # Update stats
                        if trade.exit_reason == 'TP1':
                            stats.wins += 1
                            pnl = stats.current_balance * (risk_per_trade_pct / 100) * signal.risk_reward
                        elif trade.exit_reason == 'SL':
                            stats.losses += 1
                            pnl = -stats.current_balance * (risk_per_trade_pct / 100)
                        else:  # TIMEOUT
                            stats.timeouts += 1
                            pnl = stats.current_balance * (trade.pnl_pct / 100) * (risk_per_trade_pct / 100)
                        
                        stats.current_balance += pnl
                        
            except Exception as e:
                logging.debug(f"Scan failed at {scan_time}: {e}")
                continue
        
        print(f"   Signals found: {signals_found}")
        print(f"   Trades taken: {stats.total_trades}")
        print(f"   Wins: {stats.wins} | Losses: {stats.losses} | Timeouts: {stats.timeouts}")
    
    return mode_stats


def print_results(mode_stats: Dict[str, ModeStats]):
    """Print formatted backtest results."""
    print(f"\n{'='*70}")
    print(f"📊 BACKTEST RESULTS")
    print(f"{'='*70}\n")
    
    # Header
    print(f"{'Mode':<12} {'Trades':>8} {'Wins':>6} {'Losses':>8} {'Win Rate':>10} {'Start $':>12} {'End $':>12} {'PnL %':>10}")
    print("-" * 90)
    
    # Sort by ending balance
    sorted_modes = sorted(mode_stats.items(), key=lambda x: x[1].current_balance, reverse=True)
    
    for mode_name, stats in sorted_modes:
        win_rate_str = f"{stats.win_rate:.1f}%"
        pnl_str = f"{stats.pnl_pct:+.1f}%"
        pnl_color = "🟢" if stats.pnl_pct >= 0 else "🔴"
        
        print(f"{mode_name.upper():<12} {stats.total_trades:>8} {stats.wins:>6} {stats.losses:>8} {win_rate_str:>10} ${stats.starting_balance:>10,.2f} ${stats.current_balance:>10,.2f} {pnl_color}{pnl_str:>8}")
    
    print("-" * 90)
    
    # Best performer
    best_mode = sorted_modes[0][0]
    best_stats = sorted_modes[0][1]
    print(f"\n🏆 Best Performer: {best_mode.upper()}")
    print(f"   Win Rate: {best_stats.win_rate:.1f}%")
    print(f"   Final Balance: ${best_stats.current_balance:,.2f}")
    print(f"   Total Return: {best_stats.pnl_pct:+.1f}%")
    
    # Trade details
    print(f"\n{'='*70}")
    print(f"📈 SAMPLE TRADES (Last 5 per mode)")
    print(f"{'='*70}")
    
    for mode_name, stats in sorted_modes:
        if not stats.trades:
            continue
        print(f"\n{mode_name.upper()}:")
        for trade in stats.trades[-5:]:
            emoji = "✅" if trade.exit_reason == 'TP1' else ("❌" if trade.exit_reason == 'SL' else "⏱️")
            print(f"  {emoji} {trade.symbol} {trade.direction} | Entry: ${trade.entry_price:.2f} | "
                  f"Exit: ${trade.exit_price:.2f} ({trade.exit_reason}) | PnL: {trade.pnl_pct:+.2f}%")


def main():
    """Main entry point."""
    modes_to_test = ['overwatch', 'recon', 'strike', 'surgical', 'ghost']
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
    
    try:
        mode_stats = run_backtest(
            modes=modes_to_test,
            symbols=symbols,
            days_back=14,        # Last 2 weeks
            scans_per_day=3,     # 3 scans per active day
            scan_every_n_days=2, # Every other day
            risk_per_trade_pct=2.0,
            starting_balance=10000.0
        )
        
        print_results(mode_stats)
        
    except KeyboardInterrupt:
        print("\n\nBacktest interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
