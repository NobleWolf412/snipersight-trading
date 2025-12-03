"""
Comprehensive Backtesting Framework for SniperSight

Tests the trading system under various conditions:
- Market regimes: trending, ranging, volatile, crash, pump
- Scanner modes: overwatch, recon, strike, surgical, ghost
- Holding periods: immediate (scalp), short (intraday), medium (swing)

Tracks and validates:
- Entry price accuracy
- Stop loss triggering
- Take profit execution
- Overall profitability
- Win rate by mode/regime

Usage:
    python -m backend.tests.backtest.comprehensive_backtest
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
from enum import Enum
from loguru import logger

from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode, ScannerMode, MODES
from backend.shared.models.planner import TradePlan
from backend.engine.orchestrator import Orchestrator


# =============================================================================
# MARKET REGIME DATA GENERATORS
# =============================================================================

class MarketRegime(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    CRASH = "crash"
    PUMP = "pump"


def generate_market_data(
    regime: MarketRegime,
    bars: int = 500,
    base_price: float = 40000.0,
    seed: int = 42,
    timeframe_minutes: int = 60
) -> pd.DataFrame:
    """Generate realistic OHLCV data for a given market regime with clear structure."""
    np.random.seed(seed)
    
    timestamps = [datetime(2024, 1, 1) + timedelta(minutes=timeframe_minutes * i) for i in range(bars)]
    
    prices = [base_price]
    
    if regime == MarketRegime.TRENDING_UP:
        # Strong uptrend with HEALTHY pullbacks (10-15% corrections)
        # This creates clear swing lows for stop placement
        trend = 0.0015  # 0.15% per bar average
        volatility = 0.012
        in_pullback = False
        pullback_bars = 0
        
        for i in range(bars - 1):
            # Start pullback every 30-50 bars
            if not in_pullback and i > 20 and (i % 40 == 30 or np.random.random() < 0.02):
                in_pullback = True
                pullback_bars = np.random.randint(8, 15)  # 8-15 bar pullbacks
            
            if in_pullback:
                change = -0.015 * prices[-1] + np.random.normal(0, volatility * 0.5) * prices[-1]
                pullback_bars -= 1
                if pullback_bars <= 0:
                    in_pullback = False
            else:
                change = (trend + np.random.normal(0, volatility)) * prices[-1]
            
            # Keep price within reasonable bounds
            new_price = prices[-1] + change
            new_price = max(new_price, prices[-1] * 0.92)  # Max 8% single bar drop
            new_price = min(new_price, prices[-1] * 1.05)  # Max 5% single bar gain
            prices.append(new_price)
    
    elif regime == MarketRegime.TRENDING_DOWN:
        # Bear market with relief rallies (creates clear swing highs)
        trend = -0.0012
        volatility = 0.015
        in_rally = False
        rally_bars = 0
        
        for i in range(bars - 1):
            if not in_rally and i > 20 and (i % 35 == 25 or np.random.random() < 0.03):
                in_rally = True
                rally_bars = np.random.randint(6, 12)
            
            if in_rally:
                change = 0.012 * prices[-1] + np.random.normal(0, volatility * 0.5) * prices[-1]
                rally_bars -= 1
                if rally_bars <= 0:
                    in_rally = False
            else:
                change = (trend + np.random.normal(0, volatility)) * prices[-1]
            
            new_price = prices[-1] + change
            new_price = max(new_price, base_price * 0.4)  # Floor at 40% of base
            prices.append(new_price)
    
    elif regime == MarketRegime.RANGING:
        # Sideways consolidation with clear support/resistance
        mean_price = base_price
        range_width = 0.06  # 6% range
        volatility = 0.008
        for i in range(bars - 1):
            # Strong mean reversion behavior
            deviation = (prices[-1] - mean_price) / mean_price
            reversion = -deviation * 0.15
            noise = np.random.normal(0, volatility)
            prices.append(mean_price * (1 + noise + reversion))
    
    elif regime == MarketRegime.VOLATILE:
        # High volatility with large swings
        volatility = 0.04  # 4% per candle
        for i in range(bars - 1):
            # Occasional extreme moves
            if np.random.random() < 0.05:
                change = np.random.choice([-1, 1]) * np.random.uniform(0.05, 0.08) * prices[-1]
            else:
                change = np.random.normal(0, volatility) * prices[-1]
            prices.append(max(prices[-1] + change, base_price * 0.3))
    
    elif regime == MarketRegime.CRASH:
        # Sharp crash followed by dead cat bounces
        for i in range(bars - 1):
            if i < 50:
                change = -0.01 * prices[-1]  # Gradual decline
            elif 50 <= i < 100:
                change = -0.025 * prices[-1]  # Accelerated selling
            elif 100 <= i < 150:
                change = -0.04 * prices[-1] + np.random.normal(0, 0.02) * prices[-1]  # Panic
            else:
                # Dead cat bounce / consolidation
                change = np.random.normal(0.003, 0.025) * prices[-1]
            prices.append(max(prices[-1] + change, base_price * 0.2))
    
    elif regime == MarketRegime.PUMP:
        # Parabolic rally followed by distribution
        for i in range(bars - 1):
            if i < 100:
                change = 0.002 * prices[-1]  # Slow accumulation
            elif 100 <= i < 250:
                change = (0.008 + 0.0001 * (i - 100)) * prices[-1]  # Acceleration
            elif 250 <= i < 350:
                change = 0.015 * prices[-1] + np.random.normal(0, 0.02) * prices[-1]  # FOMO
            else:
                # Distribution
                change = np.random.normal(-0.005, 0.03) * prices[-1]
            prices.append(max(prices[-1] + change, base_price * 0.5))
    
    # Build OHLC from close prices
    data = []
    for i, close in enumerate(prices):
        if i == 0:
            open_price = close
        else:
            open_price = prices[i - 1]
        
        # Generate realistic wicks
        body = abs(close - open_price)
        wick_factor = np.random.uniform(0.2, 0.8)
        
        if close >= open_price:
            high = close + body * wick_factor + abs(np.random.normal(0, 0.005 * close))
            low = open_price - body * wick_factor * 0.5 - abs(np.random.normal(0, 0.003 * close))
        else:
            high = open_price + body * wick_factor * 0.5 + abs(np.random.normal(0, 0.003 * close))
            low = close - body * wick_factor - abs(np.random.normal(0, 0.005 * close))
        
        high = max(high, max(open_price, close) * 1.001)
        low = min(low, min(open_price, close) * 0.999)
        
        # Volume correlates with volatility
        base_volume = 100000
        vol_multiplier = 1 + abs(close - open_price) / open_price * 10
        volume = base_volume * vol_multiplier * np.random.uniform(0.5, 1.5)
        
        data.append({
            'timestamp': timestamps[i],
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close, 2),
            'volume': round(volume, 2)
        })
    
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    return df


# =============================================================================
# MOCK ADAPTER FOR BACKTESTING
# =============================================================================

class BacktestAdapter:
    """Adapter that provides historical data for backtesting."""
    
    def __init__(self, data_by_tf: Dict[str, pd.DataFrame]):
        """
        Initialize with pre-generated data for each timeframe.
        
        Args:
            data_by_tf: Dict mapping timeframe strings to DataFrames
        """
        self.data_by_tf = data_by_tf
        self._current_bar_index = {}  # Track simulation position per TF
        
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
        """Fetch OHLCV data for backtesting."""
        if timeframe not in self.data_by_tf:
            # Try to resample from base timeframe
            base_tf = list(self.data_by_tf.keys())[0]
            df = self._resample_to_tf(self.data_by_tf[base_tf], timeframe)
        else:
            df = self.data_by_tf[timeframe].copy()
        
        # Return last `limit` bars
        return df.tail(limit).reset_index()
    
    def _resample_to_tf(self, df: pd.DataFrame, target_tf: str) -> pd.DataFrame:
        """Resample data to target timeframe."""
        tf_map = {
            '5m': '5min', '15m': '15min', '30m': '30min',
            '1h': '1H', '1H': '1H',
            '4h': '4H', '4H': '4H',
            '1d': '1D', '1D': '1D',
            '1w': '1W', '1W': '1W'
        }
        
        rule = tf_map.get(target_tf, '1H')
        
        # Ensure index is datetime
        if 'timestamp' in df.columns:
            df = df.set_index('timestamp')
        
        resampled = df.resample(rule).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        return resampled


# =============================================================================
# TRADE SIMULATOR
# =============================================================================

@dataclass
class TradeResult:
    """Result of a simulated trade."""
    symbol: str
    direction: str
    entry_price: float
    planned_entry_near: float
    planned_entry_far: float
    stop_loss: float
    targets: List[Tuple[float, float]]  # (level, percentage)
    exit_price: float
    exit_reason: str  # 'SL', 'TP1', 'TP2', 'TP3', 'TIMEOUT', 'MANUAL'
    pnl_pct: float
    pnl_usd: float
    holding_bars: int
    max_drawdown_pct: float
    max_runup_pct: float
    confidence_score: float
    risk_reward_planned: float
    risk_reward_actual: float
    mode: str
    regime: str
    issues: List[str] = field(default_factory=list)


@dataclass
class BacktestConfig:
    """Configuration for backtest run."""
    initial_capital: float = 10000.0
    position_size_pct: float = 5.0  # % of capital per trade
    max_holding_bars: int = 100  # Max bars before forced exit
    slippage_bps: float = 5.0  # Basis points slippage
    fee_rate: float = 0.001  # 0.1% fee per trade
    use_far_entry: bool = False  # Use aggressive (near) or conservative (far) entry


class TradeSimulator:
    """Simulates trade execution against historical data."""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.trades: List[TradeResult] = []
        self.capital = config.initial_capital
        self.equity_curve: List[float] = [config.initial_capital]
        
    def simulate_trade(
        self,
        plan: TradePlan,
        price_data: pd.DataFrame,
        start_bar: int,
        mode_name: str,
        regime_name: str
    ) -> Optional[TradeResult]:
        """
        Simulate a trade based on TradePlan against price data.
        
        Args:
            plan: The trade plan to execute
            price_data: OHLCV DataFrame
            start_bar: Index to start simulation from
            mode_name: Scanner mode used
            regime_name: Market regime
            
        Returns:
            TradeResult or None if trade couldn't be simulated
        """
        issues = []
        
        # Determine entry price
        if self.config.use_far_entry:
            planned_entry = plan.entry_zone.far_entry
        else:
            planned_entry = plan.entry_zone.near_entry
        
        current_price = price_data.iloc[start_bar]['close']
        
        # Check if entry is reachable
        is_long = plan.direction == "LONG"
        
        # For simulation, we'll enter at the next bar's open with slippage
        if start_bar + 1 >= len(price_data):
            return None
        
        next_bar = price_data.iloc[start_bar + 1]
        slippage = next_bar['open'] * (self.config.slippage_bps / 10000)
        
        if is_long:
            entry_price = next_bar['open'] + slippage
            # Check if entry was within our zone
            if entry_price > plan.entry_zone.near_entry * 1.02:
                issues.append(f"Entry {entry_price:.2f} above near entry {plan.entry_zone.near_entry:.2f}")
        else:
            entry_price = next_bar['open'] - slippage
            if entry_price < plan.entry_zone.near_entry * 0.98:
                issues.append(f"Entry {entry_price:.2f} below near entry {plan.entry_zone.near_entry:.2f}")
        
        # Position sizing
        position_value = self.capital * (self.config.position_size_pct / 100)
        position_size = position_value / entry_price
        
        # Track trade progress
        max_drawdown_pct = 0.0
        max_runup_pct = 0.0
        exit_price = None
        exit_reason = None
        holding_bars = 0
        
        # Build target levels for tracking
        remaining_targets = [(t.level, t.percentage) for t in plan.targets]
        partial_pnl = 0.0
        remaining_position_pct = 100.0
        
        # Simulate bar by bar
        for bar_idx in range(start_bar + 2, min(start_bar + 2 + self.config.max_holding_bars, len(price_data))):
            bar = price_data.iloc[bar_idx]
            holding_bars += 1
            
            high = bar['high']
            low = bar['low']
            close = bar['close']
            
            # Calculate current P&L
            if is_long:
                current_pnl_pct = ((close - entry_price) / entry_price) * 100
                bar_high_pnl = ((high - entry_price) / entry_price) * 100
                bar_low_pnl = ((low - entry_price) / entry_price) * 100
            else:
                current_pnl_pct = ((entry_price - close) / entry_price) * 100
                bar_high_pnl = ((entry_price - low) / entry_price) * 100
                bar_low_pnl = ((entry_price - high) / entry_price) * 100
            
            max_runup_pct = max(max_runup_pct, bar_high_pnl)
            max_drawdown_pct = min(max_drawdown_pct, bar_low_pnl)
            
            # Check stop loss
            if is_long:
                if low <= plan.stop_loss.level:
                    exit_price = plan.stop_loss.level - slippage
                    exit_reason = "SL"
                    if low < plan.stop_loss.level * 0.98:
                        issues.append(f"Stop slippage: low {low:.2f} below SL {plan.stop_loss.level:.2f}")
                    break
            else:
                if high >= plan.stop_loss.level:
                    exit_price = plan.stop_loss.level + slippage
                    exit_reason = "SL"
                    if high > plan.stop_loss.level * 1.02:
                        issues.append(f"Stop slippage: high {high:.2f} above SL {plan.stop_loss.level:.2f}")
                    break
            
            # Check targets (in order)
            for i, (target_level, target_pct) in enumerate(remaining_targets[:]):
                hit = False
                if is_long and high >= target_level:
                    hit = True
                elif not is_long and low <= target_level:
                    hit = True
                
                if hit:
                    # Partial close at this target
                    close_pct = target_pct * (remaining_position_pct / 100)
                    if is_long:
                        partial_pnl += ((target_level - entry_price) / entry_price) * close_pct
                    else:
                        partial_pnl += ((entry_price - target_level) / entry_price) * close_pct
                    remaining_position_pct -= close_pct
                    remaining_targets.remove((target_level, target_pct))
                    
                    if remaining_position_pct <= 1.0:
                        exit_price = target_level
                        exit_reason = f"TP{i+1}"
                        break
            
            if exit_reason:
                break
        
        # Handle timeout (max holding period)
        if not exit_reason:
            exit_price = price_data.iloc[min(bar_idx, len(price_data) - 1)]['close']
            if is_long:
                exit_price -= slippage
            else:
                exit_price += slippage
            exit_reason = "TIMEOUT"
            issues.append(f"Trade timed out after {holding_bars} bars")
        
        # Calculate final P&L
        if remaining_position_pct > 0 and exit_price:
            if is_long:
                final_pnl_pct = ((exit_price - entry_price) / entry_price) * 100 * (remaining_position_pct / 100)
            else:
                final_pnl_pct = ((entry_price - exit_price) / entry_price) * 100 * (remaining_position_pct / 100)
            total_pnl_pct = partial_pnl + final_pnl_pct
        else:
            total_pnl_pct = partial_pnl
        
        # Apply fees
        fee_pct = self.config.fee_rate * 100 * 2  # Entry + exit
        total_pnl_pct -= fee_pct
        
        pnl_usd = position_value * (total_pnl_pct / 100)
        
        # Calculate actual R:R
        risk_distance = abs(entry_price - plan.stop_loss.level)
        if exit_price and risk_distance > 0:
            reward_distance = abs(exit_price - entry_price) if exit_reason != "SL" else 0
            risk_reward_actual = reward_distance / risk_distance if exit_reason != "SL" else -1.0
        else:
            risk_reward_actual = -1.0
        
        # Validate entry vs current price
        if is_long and planned_entry > current_price * 1.05:
            issues.append(f"Bullish entry {planned_entry:.2f} > 5% above current {current_price:.2f}")
        if not is_long and planned_entry < current_price * 0.95:
            issues.append(f"Bearish entry {planned_entry:.2f} > 5% below current {current_price:.2f}")
        
        # Validate stop makes sense
        if is_long and plan.stop_loss.level >= entry_price:
            issues.append(f"LONG stop {plan.stop_loss.level:.2f} >= entry {entry_price:.2f}")
        if not is_long and plan.stop_loss.level <= entry_price:
            issues.append(f"SHORT stop {plan.stop_loss.level:.2f} <= entry {entry_price:.2f}")
        
        # Validate targets make sense
        for i, t in enumerate(plan.targets):
            if is_long and t.level <= entry_price:
                issues.append(f"LONG target {i+1} {t.level:.2f} <= entry {entry_price:.2f}")
            if not is_long and t.level >= entry_price:
                issues.append(f"SHORT target {i+1} {t.level:.2f} >= entry {entry_price:.2f}")
        
        result = TradeResult(
            symbol=plan.symbol,
            direction=plan.direction,
            entry_price=entry_price,
            planned_entry_near=plan.entry_zone.near_entry,
            planned_entry_far=plan.entry_zone.far_entry,
            stop_loss=plan.stop_loss.level,
            targets=[(t.level, t.percentage) for t in plan.targets],
            exit_price=exit_price or entry_price,
            exit_reason=exit_reason or "UNKNOWN",
            pnl_pct=total_pnl_pct,
            pnl_usd=pnl_usd,
            holding_bars=holding_bars,
            max_drawdown_pct=max_drawdown_pct,
            max_runup_pct=max_runup_pct,
            confidence_score=plan.confidence_score,
            risk_reward_planned=plan.risk_reward,
            risk_reward_actual=risk_reward_actual,
            mode=mode_name,
            regime=regime_name,
            issues=issues
        )
        
        # Update capital
        self.capital += pnl_usd
        self.equity_curve.append(self.capital)
        self.trades.append(result)
        
        return result


# =============================================================================
# MAIN BACKTEST RUNNER
# =============================================================================

def run_comprehensive_backtest(
    modes: List[str] = None,
    regimes: List[MarketRegime] = None,
    symbols: List[str] = None,
    bars_per_tf: int = 500,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Run comprehensive backtest across modes and market regimes.
    
    Args:
        modes: List of mode names to test (default: all)
        regimes: List of market regimes to test (default: all)
        symbols: List of symbols to test
        bars_per_tf: Number of bars to generate per timeframe
        seed: Random seed for reproducibility
        
    Returns:
        Dict containing all results and analysis
    """
    if modes is None:
        modes = list(MODES.keys())
    
    if regimes is None:
        regimes = list(MarketRegime)
    
    if symbols is None:
        symbols = ["BTC/USDT", "ETH/USDT"]
    
    all_results = []
    all_issues = []
    
    print("=" * 80)
    print("COMPREHENSIVE SNIPERSIGHT BACKTEST")
    print("=" * 80)
    print(f"Modes: {modes}")
    print(f"Regimes: {[r.value for r in regimes]}")
    print(f"Symbols: {symbols}")
    print(f"Bars per TF: {bars_per_tf}")
    print("=" * 80)
    
    for regime in regimes:
        print(f"\n{'='*40}")
        print(f"REGIME: {regime.value.upper()}")
        print(f"{'='*40}")
        
        for mode_name in modes:
            print(f"\n--- Mode: {mode_name} ---")
            
            try:
                mode = get_mode(mode_name)
            except ValueError:
                print(f"  [SKIP] Unknown mode: {mode_name}")
                continue
            
            # Map timeframe strings to minutes for data generation
            tf_minutes_map = {
                '1m': 1, '5m': 5, '15m': 15, '30m': 30,
                '1h': 60, '4h': 240, '1d': 1440, '1w': 10080
            }
            
            # Generate data for ALL timeframes required by this mode
            # Include both mode.timeframes AND mode.critical_timeframes
            required_tfs = set(mode.timeframes) | set(mode.critical_timeframes)
            print(f"  Required TFs: {sorted(required_tfs)}")
            print(f"  Critical TFs: {list(mode.critical_timeframes)}")
            
            data_by_tf = {}
            for tf in required_tfs:
                tf_lower = tf.lower()
                if tf_lower not in tf_minutes_map:
                    print(f"  [WARN] Unknown timeframe: {tf}")
                    continue
                tf_minutes = tf_minutes_map[tf_lower]
                data_by_tf[tf_lower] = generate_market_data(
                    regime=regime,
                    bars=bars_per_tf,
                    seed=seed + hash(f"{regime.value}_{tf_lower}") % 1000,
                    timeframe_minutes=tf_minutes
                )
            
            # Verify critical timeframes are present
            missing_critical = [tf for tf in mode.critical_timeframes if tf.lower() not in data_by_tf]
            if missing_critical:
                print(f"  [SKIP] Missing critical TFs: {missing_critical}")
                continue
            
            adapter = BacktestAdapter(data_by_tf)
            
            # Configure scan - NOTE: config.profile must be the MODE NAME not profile type
            # The orchestrator calls get_mode(config.profile) in __init__
            cfg = ScanConfig(profile=mode_name)  # Use mode name, not mode.profile
            cfg.timeframes = tuple(data_by_tf.keys())  # Use all generated TFs
            cfg.min_confluence_score = mode.min_confluence_score
            cfg.primary_planning_timeframe = mode.primary_planning_timeframe.lower()  # Normalize case
            cfg.entry_timeframes = tuple(tf.lower() for tf in mode.entry_timeframes)
            cfg.structure_timeframes = tuple(tf.lower() for tf in mode.structure_timeframes)
            
            # Run scanner
            try:
                orch = Orchestrator(
                    config=cfg,
                    exchange_adapter=adapter,
                    debug_mode=False,
                    concurrency_workers=2
                )
                # apply_mode already called implicitly via __init__ when profile=mode_name
                
                plans, rejections = orch.scan(symbols)
            except Exception as e:
                print(f"  [ERROR] Scan failed: {e}")
                continue
            
            print(f"  Signals: {len(plans)} | Rejected: {rejections.get('total_rejected', 0)}")
            
            if not plans:
                print(f"  No signals generated")
                continue
            
            # Simulate trades
            simulator = TradeSimulator(BacktestConfig(
                initial_capital=10000.0,
                position_size_pct=5.0,
                max_holding_bars=100
            ))
            
            for plan in plans:
                # Get the primary TF data for simulation (normalize case)
                primary_tf = mode.primary_planning_timeframe.lower()
                if primary_tf in data_by_tf:
                    sim_data = data_by_tf[primary_tf]
                else:
                    # Fallback to first available TF
                    sim_data = list(data_by_tf.values())[0]
                
                # Find a reasonable starting point (middle of data)
                start_bar = len(sim_data) // 2
                
                result = simulator.simulate_trade(
                    plan=plan,
                    price_data=sim_data.reset_index(),
                    start_bar=start_bar,
                    mode_name=mode_name,
                    regime_name=regime.value
                )
                
                if result:
                    all_results.append(result)
                    if result.issues:
                        all_issues.extend([{
                            'mode': mode_name,
                            'regime': regime.value,
                            'symbol': result.symbol,
                            'issue': issue
                        } for issue in result.issues])
            
            # Print mode summary
            mode_results = [r for r in all_results if r.mode == mode_name and r.regime == regime.value]
            if mode_results:
                wins = len([r for r in mode_results if r.pnl_pct > 0])
                losses = len([r for r in mode_results if r.pnl_pct <= 0])
                total_pnl = sum(r.pnl_pct for r in mode_results)
                avg_pnl = total_pnl / len(mode_results)
                win_rate = (wins / len(mode_results)) * 100 if mode_results else 0
                
                print(f"  Results: {wins}W / {losses}L ({win_rate:.1f}% WR)")
                print(f"  Avg PnL: {avg_pnl:.2f}% | Total: {total_pnl:.2f}%")
                
                issues_count = len([i for i in all_issues if i['mode'] == mode_name and i['regime'] == regime.value])
                if issues_count > 0:
                    print(f"  ⚠️  Issues found: {issues_count}")
    
    # =============================================================================
    # FINAL ANALYSIS
    # =============================================================================
    
    print("\n" + "=" * 80)
    print("FINAL ANALYSIS")
    print("=" * 80)
    
    if not all_results:
        print("No trades to analyze!")
        return {"results": [], "issues": all_issues, "analysis": {}}
    
    # Overall statistics
    df_results = pd.DataFrame([{
        'mode': r.mode,
        'regime': r.regime,
        'symbol': r.symbol,
        'direction': r.direction,
        'pnl_pct': r.pnl_pct,
        'pnl_usd': r.pnl_usd,
        'exit_reason': r.exit_reason,
        'holding_bars': r.holding_bars,
        'max_drawdown_pct': r.max_drawdown_pct,
        'rr_planned': r.risk_reward_planned,
        'rr_actual': r.risk_reward_actual,
        'confidence': r.confidence_score,
        'issues': len(r.issues)
    } for r in all_results])
    
    print(f"\nTotal Trades: {len(df_results)}")
    print(f"Overall Win Rate: {(df_results['pnl_pct'] > 0).mean() * 100:.1f}%")
    print(f"Avg PnL: {df_results['pnl_pct'].mean():.2f}%")
    print(f"Total PnL: {df_results['pnl_pct'].sum():.2f}%")
    print(f"Max Drawdown: {df_results['max_drawdown_pct'].min():.2f}%")
    
    # By mode
    print("\n--- Results by Mode ---")
    mode_stats = df_results.groupby('mode').agg({
        'pnl_pct': ['count', 'mean', 'sum'],
        'rr_actual': 'mean',
        'issues': 'sum'
    }).round(2)
    print(mode_stats.to_string())
    
    # By regime
    print("\n--- Results by Regime ---")
    regime_stats = df_results.groupby('regime').agg({
        'pnl_pct': ['count', 'mean', 'sum'],
        'rr_actual': 'mean',
        'issues': 'sum'
    }).round(2)
    print(regime_stats.to_string())
    
    # By exit reason
    print("\n--- Exit Reasons ---")
    exit_stats = df_results.groupby('exit_reason').agg({
        'pnl_pct': ['count', 'mean']
    }).round(2)
    print(exit_stats.to_string())
    
    # Mode x Regime matrix
    print("\n--- Mode x Regime Win Rates ---")
    pivot = df_results.pivot_table(
        values='pnl_pct',
        index='mode',
        columns='regime',
        aggfunc=lambda x: f"{(x > 0).mean() * 100:.0f}%"
    )
    print(pivot.to_string())
    
    # Issues summary
    print("\n--- Issues Found ---")
    if all_issues:
        issues_df = pd.DataFrame(all_issues)
        issue_counts = issues_df.groupby('issue').size().sort_values(ascending=False)
        print(f"Total issues: {len(all_issues)}")
        print("\nTop issues:")
        for issue, count in issue_counts.head(10).items():
            print(f"  [{count}x] {issue}")
    else:
        print("No issues found!")
    
    return {
        "results": all_results,
        "issues": all_issues,
        "df_results": df_results,
        "analysis": {
            "total_trades": len(df_results),
            "win_rate": (df_results['pnl_pct'] > 0).mean(),
            "avg_pnl": df_results['pnl_pct'].mean(),
            "total_pnl": df_results['pnl_pct'].sum(),
            "max_drawdown": df_results['max_drawdown_pct'].min()
        }
    }


def run_holding_period_analysis(
    mode: str = "recon",
    regime: MarketRegime = MarketRegime.TRENDING_UP,
    holding_periods: List[int] = None,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Analyze how different holding periods affect profitability.
    
    Args:
        mode: Scanner mode to test
        regime: Market regime
        holding_periods: List of max holding bars to test
        seed: Random seed
        
    Returns:
        Analysis results by holding period
    """
    if holding_periods is None:
        holding_periods = [10, 25, 50, 100, 200]  # Scalp to swing
    
    print("=" * 80)
    print("HOLDING PERIOD ANALYSIS")
    print(f"Mode: {mode} | Regime: {regime.value}")
    print("=" * 80)
    
    results_by_period = {}
    
    # Generate data once
    base_data = generate_market_data(regime=regime, bars=600, seed=seed)
    
    mode_cfg = get_mode(mode)
    data_by_tf = {'1h': base_data.copy()}
    
    for tf in ['5m', '15m', '4h', '1d']:
        tf_minutes = {'5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440}[tf]
        data_by_tf[tf] = generate_market_data(
            regime=regime,
            bars=600,
            seed=seed + hash(tf) % 1000,
            timeframe_minutes=tf_minutes
        )
    
    adapter = BacktestAdapter(data_by_tf)
    
    # Get signals once
    cfg = ScanConfig(profile=mode)  # Use mode name, not mode_cfg.profile
    cfg.timeframes = tuple([tf for tf in mode_cfg.timeframes if tf in data_by_tf])
    cfg.min_confluence_score = mode_cfg.min_confluence_score
    cfg.primary_planning_timeframe = mode_cfg.primary_planning_timeframe
    cfg.entry_timeframes = mode_cfg.entry_timeframes
    cfg.structure_timeframes = mode_cfg.structure_timeframes
    
    orch = Orchestrator(config=cfg, exchange_adapter=adapter, debug_mode=False)
    
    plans, _ = orch.scan(["BTC/USDT", "ETH/USDT"])
    
    if not plans:
        print("No signals generated!")
        return {}
    
    print(f"Testing {len(plans)} signals across {len(holding_periods)} holding periods")
    
    for max_hold in holding_periods:
        simulator = TradeSimulator(BacktestConfig(
            initial_capital=10000.0,
            position_size_pct=5.0,
            max_holding_bars=max_hold
        ))
        
        for plan in plans:
            primary_tf = mode_cfg.primary_planning_timeframe
            sim_data = data_by_tf.get(primary_tf, data_by_tf['1h'])
            start_bar = len(sim_data) // 2
            
            simulator.simulate_trade(
                plan=plan,
                price_data=sim_data.reset_index(),
                start_bar=start_bar,
                mode_name=mode,
                regime_name=regime.value
            )
        
        # Analyze results for this holding period
        if simulator.trades:
            results_by_period[max_hold] = {
                'trades': len(simulator.trades),
                'win_rate': len([t for t in simulator.trades if t.pnl_pct > 0]) / len(simulator.trades),
                'avg_pnl': sum(t.pnl_pct for t in simulator.trades) / len(simulator.trades),
                'total_pnl': sum(t.pnl_pct for t in simulator.trades),
                'avg_holding': sum(t.holding_bars for t in simulator.trades) / len(simulator.trades),
                'sl_hit': len([t for t in simulator.trades if t.exit_reason == 'SL']),
                'tp_hit': len([t for t in simulator.trades if 'TP' in t.exit_reason]),
                'timeout': len([t for t in simulator.trades if t.exit_reason == 'TIMEOUT']),
                'final_capital': simulator.capital
            }
    
    # Print analysis
    print("\n--- Holding Period Analysis ---")
    print(f"{'Period':<10} {'Trades':<8} {'WR%':<8} {'Avg PnL':<10} {'SL':<6} {'TP':<6} {'Timeout':<8}")
    print("-" * 66)
    
    for period, stats in results_by_period.items():
        print(f"{period:<10} {stats['trades']:<8} {stats['win_rate']*100:.1f}%{'':<3} "
              f"{stats['avg_pnl']:.2f}%{'':<4} {stats['sl_hit']:<6} {stats['tp_hit']:<6} {stats['timeout']:<8}")
    
    return results_by_period


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--holding":
        # Run holding period analysis
        run_holding_period_analysis(
            mode="recon",
            regime=MarketRegime.TRENDING_UP
        )
    else:
        # Run full comprehensive backtest
        results = run_comprehensive_backtest(
            modes=["recon", "strike", "surgical"],  # Start with subset
            regimes=[MarketRegime.TRENDING_UP, MarketRegime.RANGING, MarketRegime.VOLATILE],
            symbols=["BTC/USDT"],
            bars_per_tf=300
        )
