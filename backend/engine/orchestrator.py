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
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
import logging
import time

from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode
from backend.shared.models.data import MultiTimeframeData
from backend.shared.models.indicators import IndicatorSet
from backend.shared.models.smc import SMCSnapshot
from backend.shared.models.scoring import ConfluenceBreakdown
from backend.shared.models.planner import TradePlan
from backend.shared.models.regime import MarketRegime, SymbolRegime
from backend.analysis.regime_detector import get_regime_detector
from backend.analysis.regime_policies import get_regime_policy

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
from backend.indicators.momentum import compute_rsi, compute_stoch_rsi, compute_mfi, compute_macd
from backend.indicators.volatility import compute_atr, compute_bollinger_bands, compute_realized_volatility
from backend.indicators.volume import detect_volume_spike, compute_obv, compute_vwap, compute_relative_volume
from backend.strategy.smc.order_blocks import detect_order_blocks
from backend.strategy.smc.fvg import detect_fvgs
from backend.strategy.smc.bos_choch import detect_structural_breaks
from backend.strategy.smc.liquidity_sweeps import detect_liquidity_sweeps
from backend.shared.config.smc_config import SMCConfig
from backend.strategy.confluence.scorer import calculate_confluence_score
from backend.analysis.htf_levels import HTFLevelDetector
from backend.strategy.planner.planner_service import generate_trade_plan
from backend.risk.risk_manager import RiskManager
from backend.risk.position_sizer import PositionSizer
from backend.analysis.macro_context import MacroContext, compute_macro_score

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
        exchange_adapter: Optional[Any] = None,
        risk_manager: Optional[RiskManager] = None,
        position_sizer: Optional[PositionSizer] = None,
        debug_mode: bool = False,
        concurrency_workers: int = 4
    ):
        """
        Initialize orchestrator.
        
        Args:
            config: Scan configuration
            exchange_adapter: Exchange data adapter (required - pass Bybit, Phemex, OKX, or Bitget)
            risk_manager: Risk manager (creates default if None)
            position_sizer: Position sizer (creates default if None)
        """
        self.config = config
        
        # Debug mode and diagnostics tracking
        self.debug_mode = debug_mode or os.getenv('SS_DEBUG', '0') == '1'
        self.diagnostics: Dict[str, Any] = {
            'data_failures': [],
            'indicator_failures': [],
            'smc_rejections': [],
            'confluence_rejections': [],
            'planner_rejections': [],
            'risk_rejections': []
        }
        
        # Initialize telemetry
        self.telemetry = get_telemetry_logger()
        
        # Initialize components
        if exchange_adapter is None:
            raise ValueError("exchange_adapter is required - pass BybitAdapter, PhemexAdapter, OKXAdapter, or BitgetAdapter")
        self.exchange_adapter = exchange_adapter
        self.ingestion_pipeline = IngestionPipeline(self.exchange_adapter)
        
        # Risk management components
        self.risk_manager = risk_manager or RiskManager(
            account_balance=10000,  # Default balance
            max_open_positions=5,
            max_asset_exposure_pct=50.0  # Increased for intraday tight-stop strategies
        )
        self.position_sizer = position_sizer or PositionSizer(
            account_balance=10000,  # Default balance
            max_risk_pct=2.0
        )

        # Smart Money Concepts configuration (extracted parameters)
        self.smc_config = SMCConfig.defaults()
        
        # Load scanner mode for critical timeframe tracking
        self.scanner_mode = get_mode(self.config.profile)
        
        # Regime detection
        self.regime_detector = get_regime_detector()
        self.regime_policy = get_regime_policy(self.config.profile)
        self.current_regime: Optional[MarketRegime] = None
        # Macro context (dominance/flows); compute once per scan when available
        self.macro_context: Optional[MacroContext] = None
        
        # Concurrency settings
        self.concurrency_workers = max(1, concurrency_workers)

        logger.info("Orchestrator initialized with SniperSight pipeline (mode=%s, workers=%d)", 
                   self.config.profile, self.concurrency_workers)
    
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
        
        # Detect global market regime from BTC
        try:
            self.current_regime = self._detect_global_regime()
            if self.current_regime:
                logger.info("🌍 Global regime: %s (score=%.1f)", 
                           self.current_regime.composite, 
                           self.current_regime.score)
                
                # Check regime gate for mode
                if self.current_regime.score < self.regime_policy.min_regime_score:
                    logger.warning("⚠️ Regime score %.1f below mode minimum %.1f - signals may be limited",
                                 self.current_regime.score,
                                 self.regime_policy.min_regime_score)
        except Exception as e:
            logger.warning("Regime detection failed: %s - continuing without regime context", e)
            self.current_regime = None

        # Optionally compute macro dominance context once (safe no-op if unavailable)
        try:
            self.macro_context = self._compute_macro_context(symbols)
        except Exception as _mc_err:
            logger.debug("Macro context computation skipped: %s", _mc_err)
            self.macro_context = None
        
        signals = []
        rejected_count = 0
        rejection_stats: Dict[str, List[Dict[str, Any]]] = {
            "low_confluence": [],
            "no_data": [],
            "missing_critical_tf": [],
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
                "missing_critical_tf": len(rejection_stats["missing_critical_tf"]),
                "risk_validation": len(rejection_stats["risk_validation"]),
                "no_trade_plan": len(rejection_stats["no_trade_plan"]),
                "errors": len(rejection_stats["errors"])
            },
            "details": rejection_stats,
            "regime": {
                "composite": self.current_regime.composite if self.current_regime else "unknown",
                "score": self.current_regime.score if self.current_regime else 0,
                "policy_min_score": self.regime_policy.min_regime_score
            } if self.current_regime else None
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
        # Generate trace_id for correlation
        trace_id = f"{run_id}_{symbol.replace('/', '_')}_{int(timestamp.timestamp())}"
        
        # Stage 1: Initialize context
        context = SniperContext(
            symbol=symbol,
            profile=self.config.profile,
            run_id=run_id,
            timestamp=timestamp
        )
        
        # Stage 2: Data ingestion
        logger.debug("%s [%s]: Fetching multi-timeframe data", symbol, trace_id)
        context.multi_tf_data = self._ingest_data(symbol)
        
        if not context.multi_tf_data or not context.multi_tf_data.timeframes:
            logger.info("%s [%s]: REJECTED - No market data available", symbol, trace_id)
            self.diagnostics['data_failures'].append({'symbol': symbol, 'trace_id': trace_id})
            return None, {
                "symbol": symbol,
                "reason_type": "no_data",
                "reason": "No market data available",
                "trace_id": trace_id
            }
        
        # Stage 2.5: Check critical timeframe availability
        missing_critical_tfs = self._check_critical_timeframes(context.multi_tf_data)
        if missing_critical_tfs:
            logger.info("%s: REJECTED - Missing critical timeframes: %s", symbol, ', '.join(missing_critical_tfs))
            
            # Log telemetry event
            self.telemetry.log_event(create_signal_rejected_event(
                run_id=run_id,
                symbol=symbol,
                reason=f"Missing critical timeframes: {', '.join(missing_critical_tfs)}",
                gate_name="critical_timeframes"
            ))
            
            return None, {
                "symbol": symbol,
                "reason_type": "missing_critical_tf",
                "reason": f"Missing critical timeframes: {', '.join(missing_critical_tfs)}",
                "missing_timeframes": missing_critical_tfs,
                "required_timeframes": list(self.scanner_mode.critical_timeframes)
            }
        
        # Store missing TFs for plan metadata (even if empty)
        context.metadata['missing_critical_timeframes'] = missing_critical_tfs
        
        # Stage 3: Indicator computation
        logger.debug("%s: Computing indicators", symbol)
        context.multi_tf_indicators = self._compute_indicators(context.multi_tf_data)
        
        # Stage 3.5: Detect symbol-specific regime (after indicators computed)
        if context.multi_tf_data and context.multi_tf_indicators and self.regime_detector:
            try:
                symbol_regime = self.regime_detector.detect_symbol_regime(
                    symbol=symbol,
                    data=context.multi_tf_data,
                    indicators=context.multi_tf_indicators
                )
                context.metadata['symbol_regime'] = symbol_regime
                logger.debug("%s: Symbol regime: %s (score=%.1f)", symbol, symbol_regime.trend, symbol_regime.score)
            except Exception as e:
                logger.debug("%s: Symbol regime detection skipped: %s", symbol, e)
        
        # Stage 4: SMC detection
        logger.debug("%s: Detecting SMC patterns", symbol)
        context.smc_snapshot = self._detect_smc_patterns(context.multi_tf_data)
        
        # Stage 5: Confluence scoring
        logger.debug("%s [%s]: Computing confluence score", symbol, trace_id)
        context.confluence_breakdown = self._compute_confluence_score(context)
        
        # Check quality gate
        if context.confluence_breakdown.total_score < self.config.min_confluence_score:
            logger.info("%s [%s]: REJECTED - Confluence too low (%.1f < %.1f)", 
                       symbol, trace_id,
                       context.confluence_breakdown.total_score, 
                       self.config.min_confluence_score)
            
            self.diagnostics['confluence_rejections'].append({
                'symbol': symbol,
                'trace_id': trace_id,
                'score': context.confluence_breakdown.total_score,
                'threshold': self.config.min_confluence_score
            })
            
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
                "top_factors": [f"{f.name}: {f.score:.1f}" for f in context.confluence_breakdown.factors[:3]],
                "all_factors": [
                    {
                        "name": f.name,
                        "score": f.score,
                        "weight": f.weight,
                        "weighted_contribution": f.score * f.weight,
                        "rationale": f.rationale
                    }
                    for f in context.confluence_breakdown.factors
                ],
                "synergy_bonus": context.confluence_breakdown.synergy_bonus,
                "conflict_penalty": context.confluence_breakdown.conflict_penalty,
                "htf_aligned": context.confluence_breakdown.htf_aligned,
                "btc_impulse_gate": context.confluence_breakdown.btc_impulse_gate
            }
        
        # Stage 6: Trade planning
        logger.debug("%s [%s]: Generating trade plan", symbol, trace_id)
        current_price = self._get_current_price(context.multi_tf_data)
        context.plan = self._generate_trade_plan(context, current_price)
        
        # Stage 7: Risk validation
        logger.debug("%s [%s]: Validating risk parameters", symbol, trace_id)
        risk_failure_reason = None
        if context.plan:
            # Store the actual risk validation failure reason
            if not self._validate_risk(context.plan):
                # Extract actual reason from last risk_manager call (stored in instance variable)
                risk_failure_reason = getattr(self, '_last_risk_failure', 'Failed risk validation')
        
        if not context.plan or risk_failure_reason:
            reason = "No trade plan generated" if not context.plan else risk_failure_reason
            reason_type = "no_trade_plan" if not context.plan else "risk_validation"
            
            if context.plan:
                logger.info("%s [%s]: REJECTED - Risk validation failed | R:R=%.2f | Reason: %s", 
                           symbol, trace_id,
                           context.plan.risk_reward if hasattr(context.plan, 'risk_reward') else 0,
                           risk_failure_reason)
                self.diagnostics['risk_rejections'].append({
                    'symbol': symbol,
                    'trace_id': trace_id,
                    'rr': context.plan.risk_reward,
                    'reason': risk_failure_reason
                })
                rejection_info = {
                    "symbol": symbol,
                    "reason_type": reason_type,
                    "reason": risk_failure_reason or "Failed risk validation",
                    "risk_reward": context.plan.risk_reward,
                    "trace_id": trace_id
                }
            else:
                logger.info("%s [%s]: REJECTED - No trade plan generated", symbol, trace_id)
                self.diagnostics['planner_rejections'].append({
                    'symbol': symbol,
                    'trace_id': trace_id,
                    'reason': 'no_plan'
                })
                rejection_info = {
                    "symbol": symbol,
                    "reason_type": reason_type,
                    "reason": "Insufficient SMC patterns for entry/stop placement",
                    "trace_id": trace_id
                }
            
            # Log rejection event with diagnostics for UI visibility
            diagnostics = {}
            if context.plan:
                try:
                    avg_entry = (context.plan.entry_zone.near_entry + context.plan.entry_zone.far_entry) / 2
                    diagnostics = {
                        "risk_reward": round(context.plan.risk_reward, 2),
                        "entry_near": round(context.plan.entry_zone.near_entry, 6),
                        "entry_far": round(context.plan.entry_zone.far_entry, 6),
                        "avg_entry": round(avg_entry, 6),
                        "stop_level": round(context.plan.stop_loss.level, 6),
                        "stop_distance_atr": round(context.plan.stop_loss.distance_atr, 2),
                        "stop_rationale": context.plan.stop_loss.rationale,
                        "first_target": round(context.plan.targets[0].level, 6) if context.plan.targets else None,
                    }
                except Exception:
                    diagnostics = {"risk_reward": getattr(context.plan, 'risk_reward', None)}

            self.telemetry.log_event(create_signal_rejected_event(
                run_id=run_id,
                symbol=symbol,
                reason=reason,
                gate_name="risk_validation",
                diagnostics=diagnostics
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
        except Exception as e:
            logger.error("Data ingestion failed for %s: %s", symbol, e)
            self.diagnostics['data_failures'].append({'symbol': symbol, 'error': str(e)})
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
                macd_line, macd_signal, macd_hist = (None, None, None)
                try:
                    macd_line, macd_signal, macd_hist = compute_macd(df)
                except Exception as e:
                    logger.debug("MACD computation failed for %s: %s", timeframe, e)
                    macd_line, macd_signal = (None, None)
                
                # Volatility indicators  
                atr = compute_atr(df)
                bb_upper, bb_middle, bb_lower = compute_bollinger_bands(df)
                realized_vol = None
                try:
                    realized_vol = compute_realized_volatility(df)
                except Exception as e:
                    logger.debug("Realized volatility computation failed for %s: %s", timeframe, e)
                
                # Volume indicators
                volume_spike = detect_volume_spike(df)
                obv = compute_obv(df)
                _ = compute_vwap(df)  # Computed for side effects
                volume_ratio = None
                try:
                    volume_ratio = compute_relative_volume(df)
                except Exception as e:
                    logger.debug("Volume ratio computation failed for %s: %s", timeframe, e)
                
                # Create indicator snapshot
                # Handle stoch_rsi tuple (K, D) - extract both K and D values
                stoch_k_value = None
                stoch_d_value = None
                if isinstance(stoch_rsi, tuple):
                    stoch_k, stoch_d = stoch_rsi
                    stoch_k_value = stoch_k.iloc[-1]
                    stoch_d_value = stoch_d.iloc[-1]
                else:
                    stoch_k_value = stoch_rsi.iloc[-1]  # pyright: ignore - type narrowed by isinstance check
                
                # Get current price for ATR percentage
                current_price = df['close'].iloc[-1]
                atr_value = atr.iloc[-1]
                atr_pct = (atr_value / current_price * 100) if current_price > 0 else None
                
                snapshot = IndicatorSnapshot(
                    # Momentum (required)
                    rsi=rsi.iloc[-1],
                    stoch_rsi=stoch_k_value,
                    # Mean Reversion (required)  
                    bb_upper=bb_upper.iloc[-1],
                    bb_middle=bb_middle.iloc[-1],
                    bb_lower=bb_lower.iloc[-1],
                    # Volatility (required)
                    atr=atr_value,
                    # Volume (required)
                    volume_spike=bool(volume_spike.iloc[-1]),
                    # Optional fields - Momentum
                    mfi=mfi.iloc[-1],
                    stoch_rsi_k=stoch_k_value,
                    stoch_rsi_d=stoch_d_value,
                    # Optional fields - Volatility
                    atr_percent=atr_pct,
                    realized_volatility=realized_vol.iloc[-1] if realized_vol is not None else None,
                    # Optional fields - Volume
                    obv=obv.iloc[-1],
                    volume_ratio=volume_ratio.iloc[-1] if volume_ratio is not None else None
                )
                # Attach MACD values and series if available (for mode-aware persistence checks)
                if macd_line is not None and macd_signal is not None:
                    try:
                        snapshot.macd_line = float(macd_line.iloc[-1])  # type: ignore[attr-defined]
                        snapshot.macd_signal = float(macd_signal.iloc[-1])  # type: ignore[attr-defined]
                        if macd_hist is not None:
                            snapshot.macd_histogram = float(macd_hist.iloc[-1])  # type: ignore[attr-defined]
                            # Store last 5 values for persistence checks (newest last)
                            n_persist = 5
                            snapshot.macd_line_series = macd_line.iloc[-n_persist:].tolist()  # type: ignore[attr-defined]
                            snapshot.macd_signal_series = macd_signal.iloc[-n_persist:].tolist()  # type: ignore[attr-defined]
                            snapshot.macd_histogram_series = macd_hist.iloc[-n_persist:].tolist()  # type: ignore[attr-defined]
                    except Exception as e:
                        logger.debug("MACD series persistence failed for %s: %s", timeframe, e)
                
                by_timeframe[timeframe] = snapshot
                
            except Exception as e:
                logger.warning("Indicator computation failed for %s: %s", timeframe, e)
                self.diagnostics['indicator_failures'].append({'timeframe': timeframe, 'error': str(e)})
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
                
            except Exception as e:
                logger.warning("SMC detection failed for %s: %s", _timeframe, e)
                self.diagnostics['smc_rejections'].append({'timeframe': _timeframe, 'error': str(e)})
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
        
        # Compute HTF proximity context for both directions (support/resistance)
        htf_ctx_long = None
        htf_ctx_short = None
        try:
            # Prepare HTF data map
            ohlcv_map = {}
            tf_map = {"4H": "4h", "1D": "1d", "1W": "1w"}
            for k, v in context.multi_tf_data.timeframes.items():
                if k in tf_map:
                    ohlcv_map[tf_map[k]] = v
            if ohlcv_map:
                current_price = self._get_current_price(context.multi_tf_data)
                # Use planning TF ATR for ATR-normalized distance
                primary_tf = getattr(self.config, 'primary_planning_timeframe', '4H')
                ind = context.multi_tf_indicators.by_timeframe.get(primary_tf)
                atr = float(ind.atr) if ind and ind.atr else None
                if current_price and atr and atr > 0:
                    detector = HTFLevelDetector()
                    levels = detector.detect_levels(context.symbol, ohlcv_map, current_price)
                    if levels:
                        # Nearest support and resistance
                        supports = [lvl for lvl in levels if lvl.level_type == 'support' and current_price >= lvl.price]
                        resistances = [lvl for lvl in levels if lvl.level_type == 'resistance' and current_price <= lvl.price]
                        if supports:
                            sup = min(supports, key=lambda l: abs(current_price - l.price))
                            htf_ctx_long = {
                                'within_atr': abs(current_price - sup.price) / atr,
                                'within_pct': sup.proximity_pct,
                                'timeframe': sup.timeframe,
                                'type': 'support'
                            }
                        if resistances:
                            res = min(resistances, key=lambda l: abs(current_price - l.price))
                            htf_ctx_short = {
                                'within_atr': abs(current_price - res.price) / atr,
                                'within_pct': res.proximity_pct,
                                'timeframe': res.timeframe,
                                'type': 'resistance'
                            }
        except Exception:
            # If HTF proximity computation fails, continue without it
            htf_ctx_long = None
            htf_ctx_short = None

        # Evaluate both directions and choose the stronger confluence
        long_breakdown = calculate_confluence_score(
            smc_snapshot=context.smc_snapshot,
            indicators=context.multi_tf_indicators,
            config=self.config,
            direction="LONG",
            htf_context=htf_ctx_long
        )
        short_breakdown = calculate_confluence_score(
            smc_snapshot=context.smc_snapshot,
            indicators=context.multi_tf_indicators,
            config=self.config,
            direction="SHORT",
            htf_context=htf_ctx_short
        )

        # Regime-aware adjustment: optionally penalize contrarian setups
        def regime_adjust(score: float, direction: str) -> float:
            try:
                symbol_regime = context.metadata.get('symbol_regime')
                trend = (symbol_regime.trend if symbol_regime else None) or 'neutral'
                if trend == 'bullish' and direction == 'SHORT':
                    return score - 2.0
                if trend == 'bearish' and direction == 'LONG':
                    return score - 2.0
            except Exception:
                pass
            return score

        long_breakdown.total_score = regime_adjust(long_breakdown.total_score, 'LONG')
        short_breakdown.total_score = regime_adjust(short_breakdown.total_score, 'SHORT')

        chosen = long_breakdown if long_breakdown.total_score >= short_breakdown.total_score else short_breakdown
        # Persist alt scores for analytics/debugging
        context.metadata['alt_confluence'] = {
            'long': long_breakdown.total_score,
            'short': short_breakdown.total_score
        }
        # Store chosen direction for downstream planning
        context.metadata['chosen_direction'] = 'LONG' if chosen is long_breakdown else 'SHORT'
        
        # Apply regime adjustments if regime is available
        if self.current_regime:
            symbol_regime = context.metadata.get('symbol_regime')
            adjusted_score = self._apply_regime_adjustments(
                base_score=chosen.total_score,
                symbol_regime=symbol_regime
            )
            chosen.total_score = adjusted_score

        # Apply macro overlay adjustments if enabled and context available
        try:
            if getattr(self.config, 'macro_overlay_enabled', False) and self.macro_context:
                direction = context.metadata.get('chosen_direction', 'LONG')
                sym_upper = (context.symbol or '').upper()
                is_btc = sym_upper.startswith('BTC/') or sym_upper == 'BTCUSDT'
                is_alt = not is_btc
                mac_adj = compute_macro_score(
                    ctx=self.macro_context,
                    direction=direction,
                    is_btc=is_btc,
                    is_alt=is_alt,
                )
                # Adjust chosen score and clamp 0-100
                chosen.total_score = max(0.0, min(100.0, chosen.total_score + float(mac_adj)))
                # Surface macro metadata for UI/telemetry via context
                try:
                    ctx = self.macro_context
                    context.metadata['macro'] = {
                        'state': getattr(ctx.macro_state, 'name', 'NEUTRAL').lower(),
                        'score': int(getattr(ctx, 'macro_score', 0)),
                        'cluster_score': int(getattr(ctx, 'cluster_score', 0)),
                        'btc_velocity_1h': float(getattr(ctx, 'btc_velocity_1h', 0.0)),
                        'alt_velocity_1h': float(getattr(ctx, 'alt_velocity_1h', 0.0)),
                        'stable_velocity_1h': float(getattr(ctx, 'stable_velocity_1h', 0.0)),
                        'velocity_spread_1h': float(getattr(ctx, 'velocity_spread_1h', 0.0)),
                        'percent_alts_up': float(getattr(ctx, 'percent_alts_up', 0.0)),
                        'btc_volatility_1h': float(getattr(ctx, 'btc_volatility_1h', 0.0)),
                        'notes': list(getattr(ctx, 'notes', []))
                    }
                except Exception:
                    pass
        except Exception as _macro_err:
            logger.debug("Macro overlay adjustment skipped: %s", _macro_err)

        return chosen
    
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
        
        # Determine trade direction from chosen confluence evaluation
        direction = context.metadata.get('chosen_direction', "LONG")
        
        # Determine setup type based on SMC patterns
        setup_type = self._classify_setup_type(context.smc_snapshot)
        
        try:
            # Enforce TF responsibility by filtering SMC snapshot to allowed TFs
            mode = self.scanner_mode
            allowed_entry = set(getattr(self.config, 'entry_timeframes', getattr(mode, 'entry_timeframes', ())))
            allowed_structure = set(getattr(self.config, 'structure_timeframes', getattr(mode, 'structure_timeframes', ())))
            allowed_stop = set(getattr(self.config, 'stop_timeframes', getattr(mode, 'stop_timeframes', ()))) or allowed_structure
            allowed_target = set(getattr(self.config, 'target_timeframes', getattr(mode, 'target_timeframes', ()))) or allowed_structure

            def _tf(val):
                try:
                    return str(getattr(val, 'timeframe', '')).lower()
                except Exception:
                    return ''

            # Build filtered snapshot respecting responsibilities
            filtered_snapshot = SMCSnapshot(
                order_blocks=[ob for ob in context.smc_snapshot.order_blocks if _tf(ob) in (allowed_entry | allowed_structure)],
                fvgs=[fvg for fvg in context.smc_snapshot.fvgs if _tf(fvg) in allowed_target],
                structural_breaks=[brk for brk in context.smc_snapshot.structural_breaks if _tf(brk) in allowed_structure],
                liquidity_sweeps=context.smc_snapshot.liquidity_sweeps  # sweeps used for context; keep as-is
            )

            plan = generate_trade_plan(
                symbol=context.symbol,
                direction=direction,
                setup_type=setup_type,
                smc_snapshot=filtered_snapshot,
                indicators=context.multi_tf_indicators,
                confluence_breakdown=context.confluence_breakdown,
                config=self.config,
                current_price=current_price,
                missing_critical_timeframes=context.metadata.get('missing_critical_timeframes', []),
                multi_tf_data=context.multi_tf_data
            )
            
            # Enrich plan metadata with SMC geometry for chart overlays
            if plan and context.smc_snapshot:
                plan.metadata['order_blocks_list'] = [
                    {
                        'timeframe': str(ob.timeframe),
                        'type': str(ob.direction),
                        'price': float(ob.midpoint),
                        'low': float(ob.low),
                        'high': float(ob.high),
                        'timestamp': ob.timestamp.isoformat() if hasattr(ob, 'timestamp') and ob.timestamp else None,
                        'freshness_score': float(ob.freshness_score)
                    }
                    for ob in context.smc_snapshot.order_blocks
                ]
                plan.metadata['fvgs_list'] = [
                    {
                        'timeframe': str(fvg.timeframe),
                        'type': str(fvg.direction),
                        'low': float(fvg.bottom),
                        'high': float(fvg.top),
                        'timestamp': fvg.timestamp.isoformat() if hasattr(fvg, 'timestamp') and fvg.timestamp else None
                    }
                    for fvg in context.smc_snapshot.fvgs
                ]
                plan.metadata['structural_breaks_list'] = [
                    {
                        'timeframe': str(brk.timeframe),
                        'type': str(brk.break_type),
                        'level': float(brk.level),
                        'timestamp': brk.timestamp.isoformat() if hasattr(brk, 'timestamp') and brk.timestamp else None,
                        'direction': 'bullish' if brk.break_type == 'BOS' else 'bearish'
                    }
                    for brk in context.smc_snapshot.structural_breaks
                ]
                plan.metadata['liquidity_sweeps_list'] = [
                    {
                        'level': float(sweep.level),
                        'timestamp': sweep.timestamp.isoformat() if hasattr(sweep, 'timestamp') and sweep.timestamp else None,
                        'type': str(sweep.sweep_type),
                        'confirmed': bool(sweep.confirmation)
                    }
                    for sweep in context.smc_snapshot.liquidity_sweeps
                ]
            
            # Add timeframe responsibility metadata
            if plan:
                try:
                    # Infer source timeframes heuristically since core models do not carry TF fields
                    allowed_entry = set(getattr(self.config, 'entry_timeframes', ()))
                    allowed_stop = set(getattr(self.config, 'stop_timeframes', ())) or set(getattr(self.config, 'structure_timeframes', ()))
                    allowed_target = set(getattr(self.config, 'target_timeframes', ())) or set(getattr(self.config, 'structure_timeframes', ()))

                    order_blocks_list = plan.metadata.get('order_blocks_list', [])
                    fvgs_list = plan.metadata.get('fvgs_list', [])

                    avg_entry = (plan.entry_zone.near_entry + plan.entry_zone.far_entry) / 2.0 if plan.entry_zone else None
                    # Entry OB: closest OB midpoint from allowed entry TFs matching direction
                    entry_tf_inferred = None
                    if avg_entry is not None:
                        candidate_obs = [ob for ob in order_blocks_list if ob.get('timeframe') in allowed_entry]
                        if candidate_obs:
                            entry_tf_inferred = min(candidate_obs, key=lambda ob: abs(ob.get('price', ob.get('midpoint', 0)) - avg_entry)).get('timeframe')

                    # Stop TF: choose OB of opposite direction whose boundary near stop level within allowed_stop
                    sl_level = plan.stop_loss.level if plan.stop_loss else None
                    sl_tf_inferred = None
                    if sl_level is not None:
                        opposite_obs = [ob for ob in order_blocks_list if ob.get('timeframe') in allowed_stop]
                        if opposite_obs:
                            sl_tf_inferred = min(opposite_obs, key=lambda ob: min(abs(ob.get('low', sl_level) - sl_level), abs(ob.get('high', sl_level) - sl_level))).get('timeframe')

                    # Target TF: pick highest percentage target and map to closest structure (FVG or OB) in allowed_target
                    tp_tf_inferred = None
                    if plan.targets:
                        primary_target = max(plan.targets, key=lambda t: t.percentage)
                        tgt_level = primary_target.level
                        structures = [s for s in fvgs_list + order_blocks_list if s.get('timeframe') in allowed_target]
                        if structures:
                            tp_tf_inferred = min(structures, key=lambda s: min(abs(s.get('low', s.get('bottom', tgt_level)) - tgt_level), abs(s.get('high', s.get('top', tgt_level)) - tgt_level))).get('timeframe')

                    # RR source TF: attribute to target timeframe inferred
                    rr_source_tf = tp_tf_inferred
                    min_rr_passed = bool(plan.risk_reward >= getattr(self.config, 'min_rr_ratio', 0))

                    tf_meta = {
                        'bias_tfs': list(getattr(self.scanner_mode, 'bias_timeframes', ())),
                        'entry_tfs_allowed': list(getattr(self.config, 'entry_timeframes', ())),
                        'structure_tfs_allowed': list(getattr(self.config, 'structure_timeframes', ())),
                        'stop_tfs_allowed': list(getattr(self.config, 'stop_timeframes', ())),
                        'target_tfs_allowed': list(getattr(self.config, 'target_timeframes', ())),
                        'entry_timeframe': entry_tf_inferred,
                        'sl_timeframe': sl_tf_inferred,
                        'tp_timeframe': tp_tf_inferred,
                        'rr_source_tf': rr_source_tf,
                        'min_rr_passed': min_rr_passed
                    }
                    plan.metadata['tf_responsibility'] = tf_meta
                except Exception:
                    plan.metadata['tf_responsibility'] = {
                        'bias_tfs': list(getattr(self.scanner_mode, 'bias_timeframes', ()))
                    }

            # Enrich plan with regime context
            if plan and self.current_regime:
                plan.metadata['global_regime'] = {
                    'composite': self.current_regime.composite,
                    'score': self.current_regime.score,
                    'trend': self.current_regime.dimensions.trend,
                    'volatility': self.current_regime.dimensions.volatility,
                    'liquidity': self.current_regime.dimensions.liquidity
                }
                
                symbol_regime = context.metadata.get('symbol_regime')
                if symbol_regime:
                    plan.metadata['symbol_regime'] = {
                        'trend': symbol_regime.trend,
                        'volatility': symbol_regime.volatility,
                        'score': symbol_regime.score
                    }

            # Attach macro metadata if present from confluence stage
            if plan and 'macro' in context.metadata:
                try:
                    plan.metadata['macro'] = context.metadata.get('macro')
                except Exception:
                    pass
            
            # Compute simple EV estimate for ranking/prioritization
            try:
                # Map confluence score (0-100) to win prob (0.35-0.70)
                score = float(context.confluence_breakdown.total_score)
                p_win = max(0.35, min(0.70, 0.35 + (score / 100.0) * (0.70 - 0.35)))
                R = float(plan.risk_reward)
                ev = p_win * R - (1 - p_win) * 1.0
                plan.metadata['ev'] = round(ev, 3)
                plan.metadata['p_win'] = round(p_win, 3)
            except Exception:
                plan.metadata['ev'] = None

            # --- Post-plan real-time price revalidation ---
            # Fetch a fresh price (direct adapter ticker if available) to ensure the
            # generated entry zone is still logically positioned relative to live market.
            try:
                live_price = None
                # Prefer direct adapter ccxt call for freshest tick
                if hasattr(self.exchange_adapter, 'exchange') and hasattr(self.exchange_adapter.exchange, 'fetch_ticker'):
                    fetch_symbol = context.symbol
                    # OKX swap symbol format handling (mirror api_server logic)
                    if 'okx' in str(type(self.exchange_adapter)).lower() and '/USDT' in fetch_symbol and ':USDT' not in fetch_symbol:
                        fetch_symbol = fetch_symbol.replace('/USDT', '/USDT:USDT')
                    try:
                        ticker = self.exchange_adapter.exchange.fetch_ticker(fetch_symbol)
                        live_price = ticker.get('last') or ticker.get('close')
                    except Exception:
                        live_price = None
                if live_price is None:
                    # Fallback to previously computed price from multi timeframe data
                    live_price = self._get_current_price(context.multi_tf_data)
                live_price = float(live_price) if live_price is not None else current_price

                # Drift & sanity checks vs fresh price
                avg_entry = (plan.entry_zone.near_entry + plan.entry_zone.far_entry) / 2.0
                drift_abs = abs(live_price - avg_entry)
                atr_val = float(plan.metadata.get('atr') or 0.0)
                drift_pct = drift_abs / max(avg_entry, 1e-12)
                drift_atr = drift_abs / max(atr_val, 1e-12) if atr_val > 0 else 0.0
                max_drift_pct = float(getattr(self.config, 'max_entry_drift_pct', 0.15))
                max_drift_atr = float(getattr(self.config, 'max_entry_drift_atr', 3.0))
                is_bullish = (plan.direction == 'LONG')

                invalid_reason = None
                # Use strict inequality for consistency with planner validation
                if is_bullish and plan.entry_zone.near_entry > live_price:
                    invalid_reason = 'revalidation_entry_above_price'
                elif (not is_bullish) and plan.entry_zone.far_entry < live_price:
                    invalid_reason = 'revalidation_entry_below_price'
                elif drift_pct > max_drift_pct or drift_atr > max_drift_atr:
                    invalid_reason = 'revalidation_price_drift'

                if invalid_reason:
                    # Emit telemetry rejection and drop plan
                    self.telemetry.log_event(create_signal_rejected_event(
                        run_id=context.run_id,
                        symbol=context.symbol,
                        reason=invalid_reason,
                        gate_name='post_plan_revalidation',
                        diagnostics={
                            'live_price': live_price,
                            'near_entry': plan.entry_zone.near_entry,
                            'far_entry': plan.entry_zone.far_entry,
                            'drift_pct': drift_pct,
                            'drift_atr': drift_atr,
                            'max_drift_pct': max_drift_pct,
                            'max_drift_atr': max_drift_atr
                        }
                    ))
                    return None
                else:
                    # Store live price & drift metrics for downstream visibility
                    plan.metadata['live_price_revalidation'] = {
                        'live_price': live_price,
                        'drift_pct': round(drift_pct, 6),
                        'drift_atr': round(drift_atr, 6),
                        'max_drift_pct': max_drift_pct,
                        'max_drift_atr': max_drift_atr,
                        'validated': True
                    }
            except Exception as _reval_err:
                # Non-fatal; log debug and proceed with original plan
                logger.debug("Post-plan revalidation skipped: %s", _reval_err)

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
            logger.warning("Risk validation failed for %s: %s | Limits: %s", 
                         plan.symbol, risk_check.reason, risk_check.limits_hit)
            # Store the actual failure reason for better rejection messages
            self._last_risk_failure = risk_check.reason
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

    def apply_mode(self, mode) -> None:
        """Apply a ScannerMode object to orchestrator config & internal state.

        Ensures critical timeframe expectations, regime policy, and profile sync.

        Args:
            mode: ScannerMode instance (from get_mode())
        """
        try:
            # Update configuration fields
            self.config.profile = mode.profile
            # Build minimal ingestion set = union of responsibility TFs to avoid unused overhead
            tf_union = set(mode.timeframes) | set(mode.entry_timeframes) | set(mode.structure_timeframes) | set(getattr(mode, 'stop_timeframes', ())) | set(getattr(mode, 'target_timeframes', ()))
            self.config.timeframes = tuple(sorted(tf_union, key=lambda x: ["1m","5m","15m","1h","4h","1d","1w"].index(x) if x in ["1m","5m","15m","1h","4h","1d","1w"] else 999))
            # Keep existing min_confluence_score if caller intentionally raised it; otherwise adopt baseline
            if hasattr(self.config, 'min_confluence_score'):
                self.config.min_confluence_score = max(self.config.min_confluence_score, mode.min_confluence_score)
            
            # Wire planner-specific knobs from mode into config
            self.config.primary_planning_timeframe = mode.primary_planning_timeframe
            self.config.max_pullback_atr = mode.max_pullback_atr
            self.config.min_stop_atr = mode.min_stop_atr
            self.config.max_stop_atr = mode.max_stop_atr
            # Enforce timeframe responsibility into config for planner
            self.config.entry_timeframes = mode.entry_timeframes
            self.config.structure_timeframes = mode.structure_timeframes
            self.config.stop_timeframes = getattr(mode, 'stop_timeframes', ())
            self.config.target_timeframes = getattr(mode, 'target_timeframes', ())
            # Apply per-mode overrides if present
            if getattr(mode, 'overrides', None):
                ov = mode.overrides
                if 'min_rr_ratio' in ov:
                    self.config.min_rr_ratio = ov['min_rr_ratio']
                if 'atr_floor' in ov:
                    self.config.atr_floor = ov['atr_floor']
                if 'bias_gate' in ov:
                    self.config.bias_gate = ov['bias_gate']
            
            # Refresh scanner_mode reference and regime policy
            self.scanner_mode = mode
            from backend.analysis.regime_policies import get_regime_policy
            self.regime_policy = get_regime_policy(mode.profile)
            logger.debug("Applied scanner mode: %s | timeframes=%s | critical=%s | planning_tf=%s", 
                        mode.name, self.config.timeframes, mode.critical_timeframes, mode.primary_planning_timeframe)
        except Exception as e:
            logger.warning("Failed to apply mode %s: %s", getattr(mode, 'name', 'unknown'), e)

    def _check_critical_timeframes(self, multi_tf_data: MultiTimeframeData) -> List[str]:
        """
        Check if critical timeframes are available in data.
        
        Args:
            multi_tf_data: Fetched multi-timeframe data
            
        Returns:
            List of missing critical timeframes (empty if all present)
        """
        available_tfs = set(multi_tf_data.timeframes.keys())
        critical_tfs = set(self.scanner_mode.critical_timeframes)
        missing = critical_tfs - available_tfs
        return sorted(missing)
    
    def _detect_global_regime(self) -> Optional[MarketRegime]:
        """
        Detect global market regime from BTC/USDT.
        
        Returns:
            MarketRegime or None if detection fails
        """
        try:
            # Fetch BTC data
            btc_data = self._ingest_data('BTC/USDT')
            if not btc_data or not btc_data.timeframes:
                logger.warning("Unable to fetch BTC data for regime detection")
                return None
            
            # Compute BTC indicators
            btc_indicators = self._compute_indicators(btc_data)
            if not btc_indicators.by_timeframe:
                logger.warning("Unable to compute BTC indicators for regime detection")
                return None
            
            # Detect regime
            regime = self.regime_detector.detect_global_regime(
                btc_data=btc_data,
                btc_indicators=btc_indicators
            )
            
            return regime
            
        except Exception as e:
            logger.error("Global regime detection failed: %s", e)
            return None
    
    def _apply_regime_adjustments(self, base_score: float, symbol_regime: Optional[SymbolRegime]) -> float:
        """
        Apply regime-based adjustments to confluence score.
        
        Args:
            base_score: Base confluence score before regime adjustments
            symbol_regime: Symbol-specific regime (if detected)
            
        Returns:
            Adjusted confluence score
        """
        if not self.current_regime:
            return base_score
        
        adjusted_score = base_score
        
        # Get regime-specific adjustment from policy
        composite = self.current_regime.composite
        if composite in self.regime_policy.confluence_adjustment:
            adjustment = self.regime_policy.confluence_adjustment[composite]
            adjusted_score += adjustment
            logger.debug("Regime adjustment for %s: %.1f → %.1f (adjustment: %+.1f)",
                        composite, base_score, adjusted_score, adjustment)
        
        # Apply symbol regime bonus if available
        if symbol_regime and symbol_regime.score >= 70:
            bonus = 2.0  # Bonus for strong local regime
            adjusted_score += bonus
            logger.debug("Symbol regime bonus: +%.1f (symbol score=%.1f)", bonus, symbol_regime.score)
        
        # Clamp to 0-100 range
        return max(0.0, min(100.0, adjusted_score))
    
    def update_smc_config(self, new_cfg: SMCConfig) -> None:
        """Apply a new SMC configuration after validation."""
        new_cfg.validate()
        self.smc_config = new_cfg
        logger.info("SMC configuration updated")
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """
        Get status of all pipeline components.
        
        Returns:
            Dictionary with component statuses and diagnostics
        """
        return {
            'config': {
                'profile': self.config.profile,
                'timeframes': self.config.timeframes,
                'mode': self.scanner_mode.name if self.scanner_mode else None
            },
            'diagnostics': self.diagnostics,
            'debug_mode': self.debug_mode
        }

    def _compute_macro_context(self, symbols: List[str]) -> Optional[MacroContext]:
        """
        Compute macro dominance/flow context.

        Uses basket-based proxies from available market data:
        - btc_velocity_1h: 1h percent change for BTC/USDT
        - alt_velocity_1h: equal-weight 1h percent change across non-BTC symbols in scan set
        - stable_velocity_1h: inferred from breadth (alts up/down %) as a proxy for stables flow
        - percent_alts_up: share of alts with last close > previous close on 1h
        - btc_volatility_1h: ATR(14) / price for BTC on 1h
        """
        try:
            # Ensure BTC present for reference
            btc_symbol = 'BTC/USDT'
            scan_symbols = list({s for s in symbols if isinstance(s, str) and s})
            if btc_symbol not in scan_symbols:
                scan_symbols.append(btc_symbol)

            # Fetch 1h data for all symbols involved (limit small for percent change)
            data_map = self.ingestion_pipeline.parallel_fetch(
                symbols=scan_symbols,
                timeframes=['1h'],
                limit=60,
                max_workers=max(2, self.concurrency_workers)
            )

            def pct_change_last(df) -> Optional[float]:
                try:
                    closes = df['close'].tail(2).to_list()
                    if len(closes) < 2:
                        return None
                    prev, curr = float(closes[-2]), float(closes[-1])
                    if prev == 0:
                        return None
                    return (curr - prev) / prev * 100.0
                except Exception:
                    return None

            # BTC 1h velocity and volatility
            btc_data = data_map.get(btc_symbol)
            if not btc_data or '1h' not in btc_data.timeframes:
                return None
            btc_df = btc_data.timeframes['1h']
            btc_vel = pct_change_last(btc_df) or 0.0

            # ATR% proxy for BTC on 1h
            try:
                from backend.indicators.volatility import compute_atr
                atr_series = compute_atr(btc_df)
                atr_val = float(atr_series.iloc[-1]) if atr_series is not None and len(atr_series) else 0.0
                price = float(btc_df['close'].iloc[-1]) if len(btc_df) else 0.0
                btc_vol_pct = (atr_val / price) if price > 0 else 0.0
            except Exception:
                btc_vol_pct = 0.0

            # Alt basket = non-BTC symbols in provided list that we have data for
            alt_syms = [s for s in scan_symbols if s != btc_symbol]
            alt_velocities: List[float] = []
            alts_up = 0
            alts_total = 0
            for s in alt_syms:
                mtf = data_map.get(s)
                if not mtf or '1h' not in mtf.timeframes:
                    continue
                df = mtf.timeframes['1h']
                change = pct_change_last(df)
                if change is None:
                    continue
                alt_velocities.append(change)
                alts_total += 1
                if change > 0:
                    alts_up += 1

            alt_vel = (sum(alt_velocities) / len(alt_velocities)) if alt_velocities else 0.0
            percent_alts_up = (alts_up / alts_total * 100.0) if alts_total > 0 else 50.0

            # Infer stable flow direction from breadth
            # Heuristic: strong breadth up -> stables down, strong breadth down -> stables up
            if percent_alts_up >= 65.0:
                stable_vel = -0.3
            elif percent_alts_up <= 35.0:
                stable_vel = 0.3
            else:
                stable_vel = 0.0

            # Build MacroContext directly
            from backend.analysis.macro_context import MacroContext, _dir_from_pct, compute_cluster_score
            ctx = MacroContext(
                btc_dom=0.0,
                alt_dom=0.0,
                stable_dom=0.0,
                percent_alts_up=percent_alts_up,
                btc_volatility_1h=btc_vol_pct,
            )
            ctx.btc_velocity_1h = btc_vel
            ctx.alt_velocity_1h = alt_vel
            ctx.stable_velocity_1h = stable_vel
            ctx.velocity_spread_1h = btc_vel - alt_vel
            ctx.btc_dir = _dir_from_pct(btc_vel)
            ctx.alt_dir = _dir_from_pct(alt_vel)
            ctx.stable_dir = _dir_from_pct(stable_vel)

            from backend.analysis.macro_context import classify_macro_state
            ctx.macro_state = classify_macro_state(ctx)
            ctx.cluster_score = compute_cluster_score(ctx)
            return ctx
        except Exception:
            return None
    
    def export_debug_bundle(self, symbol: str, trace_id: str, **data) -> Optional[str]:
        """
        Export debug bundle to disk for replay and analysis.
        
        Args:
            symbol: Trading symbol
            trace_id: Unique trace identifier
            **data: Analysis snapshot (multi_tf_data, indicators, smc, plan, etc.)
            
        Returns:
            Path to saved bundle or None if disabled
        """
        if not self.debug_mode:
            return None
        
        try:
            cache_dir = Path('backend/cache/debug') / symbol.replace('/', '_')
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            bundle_path = cache_dir / f"{trace_id}_{timestamp}.json"
            
            # Serialize dataclass objects to dict
            serialized = {
                'trace_id': trace_id,
                'symbol': symbol,
                'timestamp': timestamp,
                'metadata': {
                    k: self._serialize_obj(v) for k, v in data.items()
                }
            }
            
            with open(bundle_path, 'w') as f:
                json.dump(serialized, f, indent=2, default=str)
            
            logger.debug("Debug bundle exported: %s", bundle_path)
            return str(bundle_path)
            
        except Exception as e:
            logger.warning("Failed to export debug bundle for %s: %s", symbol, e)
            return None
    
    def _serialize_obj(self, obj):
        """Convert dataclass/object to serializable dict."""
        if hasattr(obj, '__dict__'):
            return {k: self._serialize_obj(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, dict):
            return {k: self._serialize_obj(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._serialize_obj(x) for x in obj]
        else:
            return obj
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get detailed system status.
        
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