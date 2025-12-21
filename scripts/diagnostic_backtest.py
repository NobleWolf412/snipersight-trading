#!/usr/bin/env python3
"""
SniperSight Diagnostic Backtest

Runs comprehensive backtests across all modes with:
- 60+ diagnostic probes
- Checkpoint-based resumability  
- Win rate tracking by mode and regime
- Anomaly detection and logging
- Comprehensive report generation

Usage:
    python scripts/diagnostic_backtest.py --modes stealth,surgical --days 14
    python scripts/diagnostic_backtest.py --resume-from cp_20251220_120000_0001
"""

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.diagnostics import (
    DiagnosticLogger, ProbeCategory, Severity,
    CheckpointManager, ProbeRunner, ProbeResult,
    ReportGenerator, ModeStats
)
from backend.data.adapters.phemex import PhemexAdapter
from backend.engine.orchestrator import Orchestrator
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode, MODES

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger("diagnostic_backtest")


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_MODES = ["overwatch", "strike", "surgical", "stealth"]
DEFAULT_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "BNB/USDT",
    "XRP/USDT", "LINK/USDT", "ARB/USDT", "LTC/USDT", "DOGE/USDT"
]


@dataclass
class BacktestConfig:
    """Configuration for a diagnostic backtest run."""
    modes: List[str] = field(default_factory=lambda: DEFAULT_MODES)
    symbols: List[str] = field(default_factory=lambda: DEFAULT_SYMBOLS)
    days: int = 14
    checkpoint_interval: int = 5  # Save every N symbols
    scans_per_day: int = 3
    max_trade_hold_hours: int = 48
    risk_per_trade_pct: float = 2.0
    starting_balance: float = 10000.0
    skip_resolution: bool = True  # Skip trade resolution by default (Phemex rate limits)


@dataclass 
class TradeRecord:
    """Record of a single trade for win/loss tracking."""
    symbol: str
    mode: str
    direction: str
    entry_price: float
    stop_price: float
    tp1_price: float
    confidence: float
    rr_ratio: float
    scan_time: datetime
    regime: str = "unknown"
    resolved: bool = False
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl_pct: Optional[float] = None


# =============================================================================
# TRADE RESOLUTION
# =============================================================================

def resolve_trade(
    trade: TradeRecord, 
    future_candles: List[Dict],
    max_hours: int = 48
) -> TradeRecord:
    """
    Resolve a trade by checking if TP1 or SL was hit first.
    
    Args:
        trade: The trade to resolve
        future_candles: Candles after trade entry
        max_hours: Maximum hold time before timeout
        
    Returns:
        Updated TradeRecord with resolution
    """
    if not future_candles:
        trade.resolved = True
        trade.exit_reason = "no_data"
        return trade
    
    is_long = trade.direction.upper() == "LONG"
    
    for candle in future_candles:
        high = candle.get("high", 0)
        low = candle.get("low", 0)
        
        if is_long:
            # LONG: TP1 hit if high >= tp1, SL hit if low <= stop
            if high >= trade.tp1_price:
                trade.resolved = True
                trade.exit_reason = "tp1"
                trade.exit_price = trade.tp1_price
                trade.pnl_pct = (trade.tp1_price - trade.entry_price) / trade.entry_price * 100
                return trade
            
            if low <= trade.stop_price:
                trade.resolved = True
                trade.exit_reason = "stop_loss"
                trade.exit_price = trade.stop_price
                trade.pnl_pct = (trade.stop_price - trade.entry_price) / trade.entry_price * 100
                return trade
        else:
            # SHORT: TP1 hit if low <= tp1, SL hit if high >= stop
            if low <= trade.tp1_price:
                trade.resolved = True
                trade.exit_reason = "tp1"
                trade.exit_price = trade.tp1_price
                trade.pnl_pct = (trade.entry_price - trade.tp1_price) / trade.entry_price * 100
                return trade
            
            if high >= trade.stop_price:
                trade.resolved = True
                trade.exit_reason = "stop_loss"
                trade.exit_price = trade.stop_price
                trade.pnl_pct = (trade.entry_price - trade.stop_price) / trade.entry_price * 100
                return trade
    
    # Timeout
    trade.resolved = True
    trade.exit_reason = "timeout"
    last_close = future_candles[-1].get("close", trade.entry_price)
    trade.exit_price = last_close
    if is_long:
        trade.pnl_pct = (last_close - trade.entry_price) / trade.entry_price * 100
    else:
        trade.pnl_pct = (trade.entry_price - last_close) / trade.entry_price * 100
    
    return trade


# =============================================================================
# DIAGNOSTIC BACKTEST RUNNER
# =============================================================================

class DiagnosticBacktestRunner:
    """
    Main runner for diagnostic backtests.
    """
    
    def __init__(self, config: BacktestConfig, output_dir: Optional[Path] = None):
        self.config = config
        
        # Setup output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = output_dir or PROJECT_ROOT / "logs" / f"diagnostic_{timestamp}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.logger = DiagnosticLogger(self.output_dir, min_severity=Severity.INFO)
        self.checkpoint_mgr = CheckpointManager(self.output_dir)
        self.report_gen = ReportGenerator(self.output_dir, self.logger)
        
        # Phemex adapter for live data
        self.adapter = PhemexAdapter()
        
        # Tracking
        self.trades: List[TradeRecord] = []
        self.mode_stats: Dict[str, ModeStats] = {}
        self.regime_stats: Dict[str, Dict[str, Any]] = {}
        
        # Initialize mode stats
        for mode in config.modes:
            self.mode_stats[mode] = ModeStats(mode=mode)
        
        self.start_time = datetime.now()
    
    def run(self, resume_from: Optional[str] = None):
        """
        Run the full diagnostic backtest.
        
        Args:
            resume_from: Checkpoint ID to resume from
        """
        logger.info("="*60)
        logger.info("SNIPERSIGHT DIAGNOSTIC BACKTEST")
        logger.info("="*60)
        logger.info(f"Output: {self.output_dir}")
        logger.info(f"Modes: {self.config.modes}")
        logger.info(f"Symbols: {len(self.config.symbols)}")
        logger.info(f"Days: {self.config.days}")
        logger.info("="*60)
        
        # Resume from checkpoint if specified
        modes_to_run = self.config.modes
        symbols_remaining = self.config.symbols.copy()
        current_mode_idx = 0
        
        if resume_from:
            checkpoint = self.checkpoint_mgr.load(resume_from)
            if checkpoint:
                logger.info(f"Resuming from checkpoint: {checkpoint.id}")
                modes_to_run = [checkpoint.current_mode] + checkpoint.modes_remaining
                symbols_remaining = checkpoint.symbols_remaining
                current_mode_idx = 0
                # Restore stats
                for mode, wins in checkpoint.wins_by_mode.items():
                    if mode in self.mode_stats:
                        self.mode_stats[mode].wins = wins
                for mode, losses in checkpoint.losses_by_mode.items():
                    if mode in self.mode_stats:
                        self.mode_stats[mode].losses = losses
        
        # Run each mode
        for mode_idx, mode in enumerate(modes_to_run):
            logger.info(f"\n{'='*40}")
            logger.info(f"MODE: {mode.upper()} ({mode_idx + 1}/{len(modes_to_run)})")
            logger.info(f"{'='*40}")
            
            self.logger.set_context(mode=mode)
            
            # Get mode config
            mode_config = get_mode(mode)
            if not mode_config:
                logger.error(f"Unknown mode: {mode}")
                continue
            
            # Create probe runner for this mode
            probe_runner = ProbeRunner(self.logger, mode)
            
            # Symbols to process (might be partial if resuming)
            symbols = symbols_remaining if mode_idx == 0 else self.config.symbols.copy()
            symbols_done = []
            
            for sym_idx, symbol in enumerate(symbols):
                logger.info(f"\n[{sym_idx + 1}/{len(symbols)}] {symbol}")
                self.logger.set_context(symbol=symbol)
                
                try:
                    # Run scan for this symbol
                    trades_generated = self._scan_symbol(
                        symbol, mode, mode_config, probe_runner
                    )
                    
                    logger.info(f"  → Generated {len(trades_generated)} trade(s)")
                    self.trades.extend(trades_generated)
                    
                    # Update mode stats
                    self.mode_stats[mode].trades += len(trades_generated)
                    
                except Exception as e:
                    logger.error(f"  ✗ Error scanning {symbol}: {e}")
                    self.logger.error(
                        "SCAN_ERROR", ProbeCategory.UNEXPECTED,
                        f"Scan failed: {str(e)}",
                        context={"symbol": symbol, "mode": mode, "error": str(e)}
                    )
                
                symbols_done.append(symbol)
                
                # Checkpoint every N symbols
                if len(symbols_done) % self.config.checkpoint_interval == 0:
                    self._save_checkpoint(
                        mode, 
                        modes_to_run[mode_idx + 1:] if mode_idx < len(modes_to_run) - 1 else [],
                        symbol,
                        symbols_done,
                        [s for s in symbols if s not in symbols_done]
                    )
            
            # Resolve trades for this mode
            logger.info(f"\nResolving trades for {mode}...")
            self._resolve_trades(mode)
            
            # Reset symbols for next mode
            symbols_remaining = self.config.symbols.copy()
        
        # Final report
        end_time = datetime.now()
        logger.info("\n" + "="*60)
        logger.info("GENERATING REPORT...")
        logger.info("="*60)
        
        report_path = self.report_gen.generate(
            mode_stats=self.mode_stats,
            regime_stats=self.regime_stats,
            config={
                "modes": self.config.modes,
                "symbols": self.config.symbols,
                "days": self.config.days,
                "scans_per_day": self.config.scans_per_day
            },
            start_time=self.start_time,
            end_time=end_time
        )
        
        self.logger.save_stats()
        
        logger.info(f"\n✓ Report saved: {report_path}")
        logger.info(f"✓ Anomalies: {self.output_dir / 'anomalies.jsonl'}")
        logger.info(f"✓ Stats: {self.output_dir / 'stats.json'}")
        
        # Print summary
        self._print_summary()
    
    def _scan_symbol(
        self, 
        symbol: str, 
        mode: str, 
        mode_config: Dict,
        probe_runner: ProbeRunner
    ) -> List[TradeRecord]:
        """
        Scan a single symbol using the orchestrator.
        
        Returns list of TradeRecords generated.
        """
        trades = []
        scan_start = time.time()
        
        # Create scan config from ScannerMode dataclass
        scan_config = ScanConfig(
            profile=mode_config.profile,
            timeframes=list(mode_config.timeframes),
            min_confluence_score=mode_config.min_confluence_score
        )
        
        # Initialize orchestrator
        orchestrator = Orchestrator(
            config=scan_config,
            exchange_adapter=self.adapter,
            debug_mode=True
        )
        
        # Run scan
        try:
            results, rejection_stats = orchestrator.scan([symbol])
            scan_duration = time.time() - scan_start
            
            # Performance probe
            if scan_duration > 120:
                self.logger.warning(
                    "PERF_001", ProbeCategory.PERF_SLOW_SCAN,
                    f"Scan took {scan_duration:.1f}s (> 120s limit)",
                    context={"duration": scan_duration, "symbol": symbol}
                )
            
            # Process results (TradePlan dataclass objects)
            for result in results:
                # Extract trade data from TradePlan dataclass
                direction = result.direction
                entry_near = result.entry_zone.near_entry
                entry_far = result.entry_zone.far_entry
                entry = (entry_near + entry_far) / 2
                stop = result.stop_loss.level
                targets = result.targets
                tp1 = targets[0].level if targets else entry * (1.02 if direction == "LONG" else 0.98)
                confidence = result.confidence_score
                rr = result.risk_reward
                
                # Get current price from metadata if available
                current_price = result.metadata.get("current_price", entry) if result.metadata else entry
                
                # Run probes
                target_levels = [t.level for t in targets]
                probe_runner.check_plan_001(direction, entry, stop, target_levels)
                probe_runner.check_plan_002(direction, entry, stop, target_levels)
                probe_runner.check_plan_rr(rr)
                
                if entry_near and entry_far:
                    probe_runner.check_entry_zone_width(entry_near, entry_far, current_price)
                
                # SMC probes from metadata - read from order_blocks_list (populated by planner)
                obs = result.metadata.get("order_blocks_list", []) if result.metadata else []
                
                # Get OB score from confluence breakdown
                ob_score = 0
                if result.confluence_breakdown and result.confluence_breakdown.factors:
                    for factor in result.confluence_breakdown.factors:
                        if factor.name.lower() == "order block":
                            ob_score = factor.score
                            break
                
                probe_runner.check_smc_ob_empty(ob_score, obs)
                
                sweeps = result.metadata.get("liquidity_sweeps_list", []) if result.metadata else []
                probe_runner.check_smc_liquidity_sweep_noise(sweeps)
                
                # Create trade record
                trade = TradeRecord(
                    symbol=symbol,
                    mode=mode,
                    direction=direction,
                    entry_price=entry,
                    stop_price=stop,
                    tp1_price=tp1,
                    confidence=confidence,
                    rr_ratio=rr,
                    scan_time=datetime.now()
                )
                trades.append(trade)
                
                # Log trade
                self.logger.log_trade({
                    "symbol": symbol,
                    "mode": mode,
                    "direction": direction,
                    "entry": entry,
                    "stop": stop,
                    "tp1": tp1,
                    "confidence": confidence,
                    "rr": rr
                })
            
            # Log rejections
            if rejection_stats:
                total_rejected = rejection_stats.get("total_rejected", 0)
                if total_rejected > 0:
                    self.logger.info(
                        "REJECTION", ProbeCategory.RISK_NEAR_MISS,
                        f"{total_rejected} signals rejected",
                        context={"by_reason": rejection_stats.get("by_reason", {})}
                    )
        
        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            raise
        
        return trades
    
    def _resolve_trades(self, mode: str):
        """Resolve trades for a mode by fetching future candles."""
        mode_trades = [t for t in self.trades if t.mode == mode and not t.resolved]
        
        if not mode_trades:
            return
        
        # Skip resolution if configured (Phemex has IP-level rate limits after heavy fetching)
        if self.config.skip_resolution:
            logger.info(f"  Resolution skipped (--skip-resolution enabled). {len(mode_trades)} trades marked unresolved.")
            for trade in mode_trades:
                trade.resolved = True
                trade.exit_reason = "skipped"
            stats = self.mode_stats.get(mode)
            if stats:
                stats.avg_rr = sum(t.rr_ratio for t in mode_trades if t.rr_ratio) / len(mode_trades) if mode_trades else 0
            return
        
        wins = 0
        losses = 0
        timeouts = 0
        total_rr = 0
        
        for trade in mode_trades:
            try:
                # Fetch future candles (1h timeframe for resolution)
                # Phemex adapter expects BTC/USDT format (with slash)
                future_candles = self.adapter.fetch_ohlcv(
                    trade.symbol,  # Keep original format with slash
                    "1h",
                    limit=self.config.max_trade_hold_hours
                )
                
                if future_candles is not None and len(future_candles) > 0:
                    candle_dicts = future_candles.to_dict('records')
                    resolve_trade(trade, candle_dicts, self.config.max_trade_hold_hours)
                else:
                    trade.resolved = True
                    trade.exit_reason = "no_data"
            
            except Exception as e:
                logger.warning(f"Could not resolve {trade.symbol}: {e}")
                trade.resolved = True
                trade.exit_reason = "error"
            
            # Update stats
            if trade.exit_reason == "tp1":
                wins += 1
            elif trade.exit_reason == "stop_loss":
                losses += 1
            else:
                timeouts += 1
            
            if trade.rr_ratio:
                total_rr += trade.rr_ratio
        
        # Update mode stats
        if mode in self.mode_stats:
            stats = self.mode_stats[mode]
            stats.wins = wins
            stats.losses = losses
            stats.win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            stats.avg_rr = total_rr / len(mode_trades) if mode_trades else 0
            stats.issues_found = len(self.logger.get_entries(mode=mode))
        
        logger.info(f"  Resolved: {wins}W / {losses}L / {timeouts}T = {stats.win_rate:.1f}% WR")
    
    def _save_checkpoint(
        self,
        current_mode: str,
        modes_remaining: List[str],
        current_symbol: str,
        symbols_done: List[str],
        symbols_remaining: List[str]
    ):
        """Save a checkpoint."""
        checkpoint = self.checkpoint_mgr.create_checkpoint(
            current_mode=current_mode,
            modes_completed=[m for m in self.config.modes if m not in [current_mode] + modes_remaining],
            modes_remaining=modes_remaining,
            current_symbol=current_symbol,
            symbols_completed=symbols_done,
            symbols_remaining=symbols_remaining,
            trades_count=len(self.trades),
            signals_count=len(self.trades),
            anomalies_count=self.logger.get_stats()["counts"]["total"],
            wins_by_mode={m: s.wins for m, s in self.mode_stats.items()},
            losses_by_mode={m: s.losses for m, s in self.mode_stats.items()},
            config={
                "modes": self.config.modes,
                "symbols": self.config.symbols,
                "days": self.config.days
            }
        )
        
        path = self.checkpoint_mgr.save(checkpoint)
        logger.info(f"  💾 Checkpoint saved: {checkpoint.id}")
    
    def _print_summary(self):
        """Print final summary."""
        print("\n" + "="*60)
        print("DIAGNOSTIC BACKTEST SUMMARY")
        print("="*60)
        
        stats = self.logger.get_stats()
        
        print(f"\n📊 RESULTS BY MODE:")
        print("-" * 50)
        for mode, ms in sorted(self.mode_stats.items()):
            wr_icon = "🟢" if ms.win_rate >= 50 else "🔴"
            print(f"  {mode.upper():12} {wr_icon} {ms.win_rate:5.1f}% WR | "
                  f"{ms.wins}W/{ms.losses}L | "
                  f"R:R {ms.avg_rr:.2f} | "
                  f"{ms.issues_found} issues")
        
        print(f"\n⚠️ ISSUES FOUND: {stats['counts']['total']}")
        print("-" * 50)
        print(f"  Critical: {stats['counts'].get('critical', 0)}")
        print(f"  Errors:   {stats['counts'].get('error', 0)}")
        print(f"  Warnings: {stats['counts'].get('warning', 0)}")
        
        print(f"\n📁 OUTPUT: {self.output_dir}")
        print("="*60)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="SniperSight Diagnostic Backtest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python diagnostic_backtest.py --modes stealth --days 7
  python diagnostic_backtest.py --modes overwatch,strike,surgical,stealth --days 14
  python diagnostic_backtest.py --resume-from cp_20251220_120000_0001
        """
    )
    
    parser.add_argument(
        "--modes",
        type=str,
        default=",".join(DEFAULT_MODES),
        help=f"Comma-separated modes to test (default: {','.join(DEFAULT_MODES)})"
    )
    
    parser.add_argument(
        "--symbols",
        type=str,
        default=",".join(DEFAULT_SYMBOLS),
        help="Comma-separated symbols to scan"
    )
    
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Number of days to backtest (default: 14)"
    )
    
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=5,
        help="Save checkpoint every N symbols (default: 5)"
    )
    
    parser.add_argument(
        "--resume-from",
        type=str,
        default=None,
        help="Resume from checkpoint ID"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory (default: logs/diagnostic_<timestamp>)"
    )
    
    args = parser.parse_args()
    
    # Parse config
    config = BacktestConfig(
        modes=[m.strip() for m in args.modes.split(",")],
        symbols=[s.strip() for s in args.symbols.split(",")],
        days=args.days,
        checkpoint_interval=args.checkpoint_interval
    )
    
    output_dir = Path(args.output_dir) if args.output_dir else None
    
    # Run backtest
    runner = DiagnosticBacktestRunner(config, output_dir)
    runner.run(resume_from=args.resume_from)


if __name__ == "__main__":
    main()
