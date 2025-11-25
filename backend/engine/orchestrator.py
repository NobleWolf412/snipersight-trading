"""
SniperSight Orchestrator

The main pipeline controller that wires together all components:
1. Data ingestion (multi-timeframe)
2. Indicator computation
3. SMC detection
4. Confluence scoring
5. Trade planning
6. Risk validation
7. Signal generation

Orchestrates the complete flow from symbols to actionable trading signals.
"""

import uuid
import concurrent.futures
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
import logging
import time

from backend.shared.config.defaults import ScanConfig
from backend.shared.models.data import MultiTimeframeData
from backend.shared.models.indicators import IndicatorSet
from backend.shared.models.smc import SMCSnapshot
from backend.shared.models.scoring import ConfluenceBreakdown
from backend.shared.models.planner import TradePlan

from backend.engine.context import SniperContext
from backend.bot.telemetry.logger import get_telemetry_logger
from backend.bot.telemetry.events import (
    create_scan_started_event,
    create_scan_completed_event,
    create_signal_generated_event,
    create_signal_rejected_event,
    create_error_event
)
from backend.data.ingestion_pipeline import IngestionPipeline
from backend.data.adapters.binance import BinanceAdapter
from backend.indicators.momentum import compute_rsi, compute_stoch_rsi, compute_mfi
from backend.indicators.volatility import compute_atr, compute_bollinger_bands
from backend.indicators.volume import detect_volume_spike, compute_obv, compute_vwap
from backend.strategy.smc.order_blocks import detect_order_blocks
from backend.strategy.smc.fvg import detect_fvgs
from backend.strategy.smc.bos_choch import detect_structural_breaks
from backend.strategy.smc.liquidity_sweeps import detect_liquidity_sweeps
from backend.shared.config.smc_config import SMCConfig
from backend.strategy.confluence.scorer import calculate_confluence_score
from backend.strategy.planner.planner_service import generate_trade_plan
from backend.risk.risk_manager import RiskManager
from backend.risk.position_sizer import PositionSizer

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Main pipeline orchestrator.
    
    Coordinates all components to produce complete trading signals.
    Each scan produces a list of TradePlan objects with full context.
    
    Usage:
        orchestrator = Orchestrator(config)
        signals = orchestrator.scan(['BTC/USDT', 'ETH/USDT'])
        
        for signal in signals:
            print(f"{signal.symbol}: {signal.confidence_score:.1f}% confidence")
            print(f"Entry: {signal.entry_zone.near_entry} - {signal.entry_zone.far_entry}")
    """
    
    def __init__(
        self,
        config: ScanConfig,
        exchange_adapter: Optional[BinanceAdapter] = None,
        risk_manager: Optional[RiskManager] = None,
        position_sizer: Optional[PositionSizer] = None,
        concurrency_workers: int = 4
    ):
        """
        Initialize orchestrator.
        
        Args:
            config: Scan configuration
            exchange_adapter: Exchange data adapter (creates default if None)
            risk_manager: Risk manager (creates default if None)
            position_sizer: Position sizer (creates default if None)
        """
        self.config = config
        
        # Initialize telemetry
        self.telemetry = get_telemetry_logger()
        
        # Initialize components
        self.exchange_adapter = exchange_adapter or BinanceAdapter(testnet=False)
        self.ingestion_pipeline = IngestionPipeline(self.exchange_adapter)
        
        # Risk management components
        self.risk_manager = risk_manager or RiskManager(
            account_balance=10000,  # Default balance
            max_open_positions=5
        )
        self.position_sizer = position_sizer or PositionSizer(
            account_balance=10000,  # Default balance
            max_risk_pct=2.0
        )

        # Smart Money Concepts configuration (extracted parameters)
        self.smc_config = SMCConfig.defaults()
        
        # Concurrency settings
        self.concurrency_workers = max(1, concurrency_workers)

        logger.info("Orchestrator initialized with SniperSight pipeline (workers=%d)", self.concurrency_workers)
    
    def scan(self, symbols: List[str]) -> tuple[List[TradePlan], Dict[str, Any]]:
        """
        Execute complete scan pipeline for symbols.
        
        Args:
            symbols: List of trading pairs to scan
            
        Returns:
            Tuple of (TradePlans, rejection_stats dict)
            
        Raises:
            Exception: If critical pipeline stage fails
        """
        run_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now(timezone.utc)
        start_time = time.time()
        
        logger.info("🎯 Starting scan %s for %d symbols", run_id, len(symbols))
        
        # Log scan started event
        self.telemetry.log_event(create_scan_started_event(
            run_id=run_id,
            symbols=symbols,
            profile=self.config.profile
        ))
        
        signals = []
        rejected_count = 0
        rejection_stats: Dict[str, List[Dict[str, Any]]] = {
            "low_confluence": [],
            "no_data": [],
            "risk_validation": [],
            "no_trade_plan": [],
            "errors": []
        }
        
        # Parallel per-symbol processing
        def _safe_process(sym: str) -> tuple[Optional[TradePlan], Optional[Dict[str, Any]]]:
            try:
                return self._process_symbol(sym, run_id, timestamp)
            except Exception as e:  # pyright: ignore - intentional broad catch for robustness
                logger.error("❌ %s: Pipeline error - %s", sym, e)
                self.telemetry.log_event(create_error_event(
                    error_message=str(e),
                    error_type=type(e).__name__,
                    symbol=sym,
                    run_id=run_id
                ))
                return None, {"symbol": sym, "error": str(e)}

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrency_workers) as executor:
            future_map = {executor.submit(_safe_process, s): s for s in symbols}
            for future in concurrent.futures.as_completed(future_map):
                symbol = future_map[future]
                result, rejection_info = future.result()
                if result:
                    signals.append(result)
                    logger.info("✅ %s: Signal generated (%.1f%%)", symbol, result.confidence_score)
                else:
                    rejected_count += 1
                    # Categorize rejection
                    if rejection_info:
                        reason_type = rejection_info.get("reason_type", "errors")
                        rejection_stats[reason_type].append(rejection_info)
                    logger.debug("⚪ %s: No qualifying setup", symbol)
        
        # Log scan completed event
        duration = time.time() - start_time
        self.telemetry.log_event(create_scan_completed_event(
            run_id=run_id,
            symbols_scanned=len(symbols),
            signals_generated=len(signals),
            signals_rejected=rejected_count,
            duration_seconds=duration
        ))
        
        logger.info("🎯 Scan %s complete: %d/%d signals generated", run_id, len(signals), len(symbols))
        
        # Build rejection summary
        rejection_summary = {
            "total_rejected": rejected_count,
            "by_reason": {
                "low_confluence": len(rejection_stats["low_confluence"]),
                "no_data": len(rejection_stats["no_data"]),
                "risk_validation": len(rejection_stats["risk_validation"]),
                "no_trade_plan": len(rejection_stats["no_trade_plan"]),
                "errors": len(rejection_stats["errors"])
            },
            "details": rejection_stats
        }
        
        return signals, rejection_summary
    
    def _process_symbol(
        self, 
        symbol: str, 
        run_id: str, 
        timestamp: datetime
    ) -> tuple[Optional[TradePlan], Optional[Dict[str, Any]]]:
        """
        Process single symbol through complete pipeline.
        
        Args:
            symbol: Trading pair to process
            run_id: Unique scan run identifier  
            timestamp: Scan timestamp
            
        Returns:
            Tuple of (TradePlan if qualifying, rejection_info dict if rejected)
        """
        # Stage 1: Initialize context
        context = SniperContext(
            symbol=symbol,
            profile=self.config.profile,
            run_id=run_id,
            timestamp=timestamp
        )
        
        # Stage 2: Data ingestion
        logger.debug("%s: Fetching multi-timeframe data", symbol)
        context.multi_tf_data = self._ingest_data(symbol)
        
        if not context.multi_tf_data or not context.multi_tf_data.timeframes:
            logger.info("%s: REJECTED - No market data available (exchange may be restricted or offline)", symbol)
            return None, {
                "symbol": symbol,
                "reason_type": "no_data",
                "reason": "No market data available"
            }
        
        # Stage 3: Indicator computation
        logger.debug("%s: Computing indicators", symbol)
        context.multi_tf_indicators = self._compute_indicators(context.multi_tf_data)
        
        # Stage 4: SMC detection
        logger.debug("%s: Detecting SMC patterns", symbol)
        context.smc_snapshot = self._detect_smc_patterns(context.multi_tf_data)
        
        # Stage 5: Confluence scoring
        logger.debug("%s: Computing confluence score", symbol)
        context.confluence_breakdown = self._compute_confluence_score(context)
        
        # Check quality gate
        if context.confluence_breakdown.total_score < self.config.min_confluence_score:
            logger.info("%s: REJECTED - Confluence too low (%.1f < %.1f) | Factors: %s", 
                       symbol, 
                       context.confluence_breakdown.total_score, 
                       self.config.min_confluence_score,
                       ', '.join([f"{f.name}={f.score:.1f}" for f in context.confluence_breakdown.factors[:3]]))
            
            # Log rejection event
            self.telemetry.log_event(create_signal_rejected_event(
                run_id=run_id,
                symbol=symbol,
                reason="Below minimum confluence threshold",
                gate_name="confluence_score",
                score=context.confluence_breakdown.total_score,
                threshold=self.config.min_confluence_score
            ))
            
            return None, {
                "symbol": symbol,
                "reason_type": "low_confluence",
                "reason": f"Confluence score too low ({context.confluence_breakdown.total_score:.1f} < {self.config.min_confluence_score:.1f})",
                "score": context.confluence_breakdown.total_score,
                "threshold": self.config.min_confluence_score,
                "top_factors": [f"{f.name}: {f.score:.1f}" for f in context.confluence_breakdown.factors[:3]]
            }
        
        # Stage 6: Trade planning
        logger.debug("%s: Generating trade plan", symbol)
        current_price = self._get_current_price(context.multi_tf_data)
        context.plan = self._generate_trade_plan(context, current_price)
        
        # Stage 7: Risk validation
        logger.debug("%s: Validating risk parameters", symbol)
        if not context.plan or not self._validate_risk(context.plan):
            reason = "No trade plan generated" if not context.plan else "Failed risk validation"
            reason_type = "no_trade_plan" if not context.plan else "risk_validation"
            
            if context.plan:
                logger.info("%s: REJECTED - Risk validation failed | R:R=%.2f, Stop=%.2f, Entry=%.2f", 
                           symbol, 
                           context.plan.risk_reward if hasattr(context.plan, 'risk_reward') else 0,
                           context.plan.stop_loss.level if context.plan.stop_loss else 0,
                           context.plan.entry_zone.near_entry if context.plan.entry_zone else 0)
                rejection_info = {
                    "symbol": symbol,
                    "reason_type": reason_type,
                    "reason": f"Risk/Reward ratio too low ({context.plan.risk_reward:.2f})",
                    "risk_reward": context.plan.risk_reward
                }
            else:
                logger.info("%s: REJECTED - No trade plan could be generated (insufficient SMC patterns)", symbol)
                rejection_info = {
                    "symbol": symbol,
                    "reason_type": reason_type,
                    "reason": "Insufficient SMC patterns for entry/stop placement"
                }
            
            # Log rejection event
            self.telemetry.log_event(create_signal_rejected_event(
                run_id=run_id,
                symbol=symbol,
                reason=reason,
                gate_name="risk_validation"
            ))
            
            return None, rejection_info
        
        # Log successful signal generation
        if context.plan:
            self.telemetry.log_event(create_signal_generated_event(
                run_id=run_id,
                symbol=symbol,
                direction=context.plan.direction,
                confidence_score=context.plan.confidence_score,
                setup_type=context.plan.setup_type,
                entry_price=context.plan.entry_zone.near_entry,
                risk_reward_ratio=context.plan.risk_reward
            ))
        
        return context.plan, None
    
    def _ingest_data(self, symbol: str) -> Optional[MultiTimeframeData]:
        """
        Ingest multi-timeframe data for symbol.
        
        Args:
            symbol: Trading pair
            
        Returns:
            MultiTimeframeData or None if failed
        """
        try:
            return self.ingestion_pipeline.fetch_multi_timeframe(
                symbol=symbol,
                timeframes=list(self.config.timeframes)
            )
        except Exception:  # pyright: ignore - intentional broad catch for robustness
            logger.error("Data ingestion failed for %s", symbol)
            return None
    
    def _compute_indicators(self, multi_tf_data: MultiTimeframeData) -> IndicatorSet:
        """
        Compute technical indicators across all timeframes.
        
        Args:
            multi_tf_data: Multi-timeframe OHLCV data
            
        Returns:
            IndicatorSet with computed indicators
        """
        from backend.shared.models.indicators import IndicatorSnapshot
        
        by_timeframe = {}
        
        for timeframe, df in multi_tf_data.timeframes.items():
            if df.empty or len(df) < 50:  # Need minimum data for indicators
                continue
            
            try:
                # Momentum indicators
                rsi = compute_rsi(df)
                stoch_rsi = compute_stoch_rsi(df)
                mfi = compute_mfi(df)
                
                # Volatility indicators  
                atr = compute_atr(df)
                bb_upper, bb_middle, bb_lower = compute_bollinger_bands(df)
                
                # Volume indicators
                volume_spike = detect_volume_spike(df)
                obv = compute_obv(df)
                _ = compute_vwap(df)  # Computed for side effects
                
                # Create indicator snapshot
                # Handle stoch_rsi tuple (K, D) - extract K value
                if isinstance(stoch_rsi, tuple):
                    stoch_k, _ = stoch_rsi
                    stoch_k_value = stoch_k.iloc[-1]
                else:
                    stoch_k_value = stoch_rsi.iloc[-1]  # pyright: ignore - type narrowed by isinstance check
                
                snapshot = IndicatorSnapshot(
                    # Momentum (required)
                    rsi=rsi.iloc[-1],
                    stoch_rsi=stoch_k_value,
                    # Mean Reversion (required)  
                    bb_upper=bb_upper.iloc[-1],
                    bb_middle=bb_middle.iloc[-1],
                    bb_lower=bb_lower.iloc[-1],
                    # Volatility (required)
                    atr=atr.iloc[-1],
                    # Volume (required)
                    volume_spike=bool(volume_spike.iloc[-1]),
                    # Optional fields
                    mfi=mfi.iloc[-1],
                    obv=obv.iloc[-1]
                )
                
                by_timeframe[timeframe] = snapshot
                
            except Exception:  # noqa: BLE001  # type: ignore[misc] - intentional broad catch for robustness
                logger.warning("Indicator computation failed")
                continue
        
        return IndicatorSet(by_timeframe=by_timeframe)
    
    def _detect_smc_patterns(self, multi_tf_data: MultiTimeframeData) -> SMCSnapshot:
        """
        Detect Smart Money Concept patterns.
        
        Args:
            multi_tf_data: Multi-timeframe OHLCV data
            
        Returns:
            SMCSnapshot with detected patterns
        """
        all_order_blocks = []
        all_fvgs = []
        all_structure_breaks = []
        all_liquidity_sweeps = []
        
        for _timeframe, df in multi_tf_data.timeframes.items():
            if df.empty or len(df) < 20:
                continue
            
            try:
                # Order blocks
                obs = detect_order_blocks(df, self.smc_config)
                all_order_blocks.extend(obs)
                
                # Fair value gaps
                fvgs = detect_fvgs(df, self.smc_config)
                all_fvgs.extend(fvgs)
                
                # Structure breaks
                breaks = detect_structural_breaks(df, self.smc_config)
                all_structure_breaks.extend(breaks)
                
                # Liquidity sweeps
                sweeps = detect_liquidity_sweeps(df, self.smc_config)
                all_liquidity_sweeps.extend(sweeps)
                
            except Exception:  # noqa: BLE001  # type: ignore[misc] - intentional broad catch for robustness
                logger.warning("SMC detection failed")
                continue
        
        return SMCSnapshot(
            order_blocks=all_order_blocks,
            fvgs=all_fvgs,
            structural_breaks=all_structure_breaks,
            liquidity_sweeps=all_liquidity_sweeps
        )
    
    def _compute_confluence_score(self, context: SniperContext) -> ConfluenceBreakdown:
        """
        Compute confluence score from all available data.
        
        Args:
            context: SniperContext with data and indicators
            
        Returns:
            ConfluenceBreakdown with scoring details
        """
        # Type narrowing - these should always be present at this stage
        if not context.smc_snapshot or not context.multi_tf_indicators:
            raise ValueError(f"{context.symbol}: Missing SMC snapshot or indicators for confluence scoring")
        
        return calculate_confluence_score(
            smc_snapshot=context.smc_snapshot,
            indicators=context.multi_tf_indicators,
            config=self.config,
            direction="LONG"  # We'll determine this properly later
        )
    
    def _generate_trade_plan(self, context: SniperContext, current_price: float) -> Optional[TradePlan]:
        """
        Generate complete trade plan from analysis.
        
        Args:
            context: SniperContext with complete analysis
            current_price: Current market price
            
        Returns:
            TradePlan or None if unable to generate
        """
        if not all([context.smc_snapshot, context.multi_tf_indicators, context.confluence_breakdown]):
            logger.warning("Missing required data for trade planning")
            return None
        
        # Type narrowing - asserted non-None by check above
        assert context.smc_snapshot is not None
        assert context.multi_tf_indicators is not None
        assert context.confluence_breakdown is not None
        
        # Determine trade direction from confluence analysis
        direction = "LONG" if context.confluence_breakdown.regime in ["trend", "bullish"] else "SHORT"
        
        # Determine setup type based on SMC patterns
        setup_type = self._classify_setup_type(context.smc_snapshot)
        
        try:
            plan = generate_trade_plan(
                symbol=context.symbol,
                direction=direction,
                setup_type=setup_type,
                smc_snapshot=context.smc_snapshot,
                indicators=context.multi_tf_indicators,
                confluence_breakdown=context.confluence_breakdown,
                config=self.config,
                current_price=current_price
            )
            
            return plan
            
        except Exception as e:  # noqa: BLE001  # type: ignore[misc] - intentional broad catch for robustness
            logger.error("Trade plan generation failed: %s", e)
            return None
    
    def _classify_setup_type(self, smc_snapshot: SMCSnapshot) -> str:
        """
        Classify setup type based on SMC patterns.
        
        Args:
            smc_snapshot: Detected SMC patterns
            
        Returns:
            Setup type string
        """
        # Count pattern types
        ob_count = len(smc_snapshot.order_blocks)
        fvg_count = len(smc_snapshot.fvgs)
        break_count = len(smc_snapshot.structural_breaks)
        
        # Simple classification logic
        if ob_count > 0 and fvg_count > 0:
            return "OB_FVG_Confluence"
        elif ob_count > 0 and break_count > 0:
            return "OB_StructureBreak"
        elif fvg_count > 0:
            return "FVG_Setup"
        elif ob_count > 0:
            return "OrderBlock_Setup"
        else:
            return "Generic_Setup"
    
    def _validate_risk(self, plan: TradePlan) -> bool:
        """
        Validate trade plan against risk parameters.
        
        Args:
            plan: Generated trade plan
            
        Returns:
            True if plan passes risk validation
        """
        if not plan:
            return False
        
        # Calculate position size
        try:
            position_size = self.position_sizer.calculate_fixed_fractional(
                risk_pct=self.config.max_risk_pct,
                entry_price=plan.entry_zone.near_entry,
                stop_price=plan.stop_loss.level
            )
        except Exception as e:  # pyright: ignore - intentional broad catch for robustness
            logger.warning("Position sizing failed: %s", e)
            return False
        
        # Validate with risk manager
        risk_check = self.risk_manager.validate_new_trade(
            symbol=plan.symbol,
            direction=plan.direction,
            position_value=position_size.notional_value,
            risk_amount=position_size.risk_amount
        )
        
        if not risk_check.passed:
            logger.debug("Risk validation failed: {risk_check.reason}")
            return False
        
        return True
    
    def _get_current_price(self, multi_tf_data: MultiTimeframeData) -> float:
        """
        Get current price from most recent data.
        
        Args:
            multi_tf_data: Multi-timeframe data
            
        Returns:
            Current price (close of most recent candle)
        """
        # Use highest frequency timeframe (last in sorted list)
        timeframes = sorted(multi_tf_data.timeframes.keys())
        if timeframes:
            df = multi_tf_data.timeframes[timeframes[-1]]
            if not df.empty:
                return float(df['close'].iloc[-1])
        
        return 0.0
    
    def update_configuration(self, config: ScanConfig) -> None:
        """
        Update scan configuration.
        
        Args:
            config: New configuration
        """
        self.config = config
        logger.info("Configuration updated")

    def update_smc_config(self, new_cfg: SMCConfig) -> None:
        """Apply a new SMC configuration after validation."""
        new_cfg.validate()
        self.smc_config = new_cfg
        logger.info("SMC configuration updated")
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """
        Get status of all pipeline components.
        
        Returns:
            Status dictionary
        """
        return {
            'exchange_adapter': 'connected' if self.exchange_adapter else 'disconnected',
            'risk_manager': {
                'account_balance': self.risk_manager.account_balance,
                'open_positions': len(self.risk_manager.positions),
                'max_positions': self.risk_manager.max_open_positions
            },
            'position_sizer': {
                'account_balance': self.position_sizer.account_balance,
                'max_risk_pct': self.position_sizer.max_risk_pct
            },
            'config': {
                'timeframes': self.config.timeframes,
                'min_confluence_score': self.config.min_confluence_score,
                'profile': self.config.profile
            }
        }