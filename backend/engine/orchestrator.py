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
    create_error_event,
    create_info_event
)
from backend.data.ingestion_pipeline import IngestionPipeline
from backend.indicators.momentum import compute_rsi, compute_stoch_rsi, compute_mfi, compute_macd
from backend.indicators.volatility import compute_atr, compute_bollinger_bands, compute_realized_volatility
from backend.indicators.volume import detect_volume_spike, compute_obv, compute_vwap, compute_relative_volume
from backend.strategy.smc.order_blocks import detect_order_blocks
from backend.strategy.smc.fvg import detect_fvgs
from backend.strategy.smc.bos_choch import detect_structural_breaks
from backend.strategy.smc.liquidity_sweeps import detect_liquidity_sweeps, detect_equal_highs_lows
from backend.strategy.smc.swing_structure import detect_swing_structure, SwingStructure
from backend.strategy.smc.cycle_detector import detect_cycle_context, should_boost_direction, CycleConfig
from backend.strategy.smc.reversal_detector import detect_reversal_context, get_reversal_rationale_for_plan
from backend.strategy.smc.volume_profile import calculate_volume_profile, VolumeProfile
from backend.strategy.smc.mitigation_tracker import update_ob_mitigation, MitigationStatus
from backend.shared.config.smc_config import SMCConfig
from backend.strategy.confluence.scorer import calculate_confluence_score
from backend.analysis.htf_levels import HTFLevelDetector
from backend.analysis.premium_discount import detect_premium_discount, PremiumDiscountZone, get_optimal_entry_zone
from backend.analysis.key_levels import detect_key_levels, KeyLevels, get_nearest_level
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
        
        # Entry cooldown tracking - prevents re-entry after recent stop-outs
        # Structure: {symbol: {'timestamp': datetime, 'price': float, 'direction': str}}
        self._symbol_cooldowns: Dict[str, Dict[str, Any]] = {}
        self._cooldown_hours = 24  # Hours to wait after a stop-out before re-entering same direction
        
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
        # Try mode name first, then fall back to profile lookup
        try:
            self.scanner_mode = get_mode(self.config.profile)
        except ValueError:
            # Profile is not a mode name - use reverse lookup
            from backend.shared.config.scanner_modes import get_mode_by_profile
            self.scanner_mode = get_mode_by_profile(self.config.profile)
        
        # Apply mode settings to config (min_stop_atr, max_stop_atr, timeframe responsibility, etc.)
        # This ensures planner uses mode-specific thresholds, not ScanConfig defaults
        self.apply_mode(self.scanner_mode)
        
        # Regime detection
        self.regime_detector = get_regime_detector()
        self.regime_policy = get_regime_policy(self.config.profile)
        self.current_regime: Optional[MarketRegime] = None
        # Macro context (dominance/flows); compute once per scan when available
        self.macro_context: Optional[MacroContext] = None
        
        # Concurrency settings
        self.concurrency_workers = max(1, concurrency_workers)

        # Log detailed mode configuration
        critical_tfs = list(getattr(self.scanner_mode, 'critical_timeframes', ()))
        entry_tfs = list(getattr(self.config, 'entry_timeframes', getattr(self.scanner_mode, 'entry_timeframes', ())))
        structure_tfs = list(getattr(self.config, 'structure_timeframes', getattr(self.scanner_mode, 'structure_timeframes', ())))
        min_score = float(getattr(self.config, 'min_confluence_score', getattr(self.scanner_mode, 'min_confluence_score', 0)))
        min_rr = float(getattr(self.config, 'min_rr_ratio', getattr(self.scanner_mode, 'min_rr_ratio', 0)))
        
        logger.info("🚀 Orchestrator initialized: mode=%s | workers=%d", 
                   self.config.profile.upper(), self.concurrency_workers)
        logger.info("📋 Mode config: MinScore=%.1f%% | MinRR=%.1f:1 | CriticalTFs=%s",
                   min_score, min_rr, ', '.join(critical_tfs))
        logger.info("⏱️  TF Responsibility: Entry=%s | Structure=%s",
                   ', '.join(entry_tfs), ', '.join(structure_tfs))
        
        self._progress("BOOT", {
            "mode": getattr(self.scanner_mode, 'name', self.config.profile),
            "profile": self.config.profile,
            "critical_timeframes": critical_tfs,
            "entry_timeframes": entry_tfs,
            "structure_timeframes": structure_tfs,
            "ingestion_timeframes": list(self.config.timeframes),
            "min_confluence": min_score,
            "min_rr": min_rr
        })
    
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
        self._progress("START", {
            "run_id": run_id,
            "mode": getattr(self.scanner_mode, 'name', self.config.profile),
            "symbols": symbols,
            "timeframes": list(self.config.timeframes),
            "critical_timeframes": list(getattr(self.scanner_mode, 'critical_timeframes', ())),
            "gates": {
                "regime_min_score": float(getattr(self.regime_policy, 'min_regime_score', 0)),
                "confluence_min": float(getattr(self.config, 'min_confluence_score', 0)),
                "min_rr_ratio": float(getattr(self.config, 'min_rr_ratio', 0))
            }
        })
        
        # Log scan started event
        self.telemetry.log_event(create_scan_started_event(
            run_id=run_id,
            symbols=symbols,
            profile=self.config.profile
        ))
        
        # ========== BULK DATA FETCH (single API call per symbol) ==========
        # Fetch all multi-timeframe data upfront to avoid duplicate API calls
        # This data is reused for regime detection, macro context, and per-symbol processing
        logger.info("📥 Bulk fetching data for %d symbols...", len(symbols))
        self._progress("BULK_FETCH_START", {"symbols": symbols, "timeframes": list(self.config.timeframes)})
        
        prefetched_data: Dict[str, MultiTimeframeData] = {}
        fetch_failures: List[str] = []
        
        # Ensure BTC is included for regime/macro context even if not in scan list
        symbols_to_fetch = list(symbols)
        if 'BTC/USDT' not in symbols_to_fetch:
            symbols_to_fetch.append('BTC/USDT')
        
        # Use parallel_fetch for efficiency (staggered to avoid rate limits)
        try:
            prefetched_data = self.ingestion_pipeline.parallel_fetch(
                symbols=symbols_to_fetch,
                timeframes=list(self.config.timeframes),
                limit=500,
                max_workers=self.concurrency_workers
            )
            fetch_failures = [s for s in symbols_to_fetch if s not in prefetched_data]
        except Exception as e:
            logger.error("Bulk fetch failed: %s - falling back to per-symbol fetch", e)
            # Fallback handled in _process_symbol
        
        logger.info("📥 Bulk fetch complete: %d succeeded, %d failed", 
                   len(prefetched_data), len(fetch_failures))
        self._progress("BULK_FETCH_COMPLETE", {
            "succeeded": len(prefetched_data),
            "failed": len(fetch_failures),
            "failed_symbols": fetch_failures
        })

        # Detect global market regime from pre-fetched BTC data (no duplicate API call)
        try:
            btc_data = prefetched_data.get('BTC/USDT')
            self.current_regime = self._detect_global_regime(prefetched_btc_data=btc_data)
            if self.current_regime:
                logger.info("🌍 Global regime: %s (score=%.1f)", 
                           self.current_regime.composite, 
                           self.current_regime.score)
                self._progress("REGIME", {
                    "composite": self.current_regime.composite,
                    "score": float(self.current_regime.score),
                    "min_required": float(getattr(self.regime_policy, 'min_regime_score', 0)),
                    "gate_passed": bool(self.current_regime.score >= getattr(self.regime_policy, 'min_regime_score', 0))
                })
                
                # Check regime gate for mode
                if self.current_regime.score < self.regime_policy.min_regime_score:
                    logger.warning("⚠️ Regime score %.1f below mode minimum %.1f - signals may be limited",
                                 self.current_regime.score,
                                 self.regime_policy.min_regime_score)
        except Exception as e:
            logger.warning("Regime detection failed: %s - continuing without regime context", e)
            self.current_regime = None

        # Compute macro context using pre-fetched data (no additional API calls)
        try:
            self.macro_context = self._compute_macro_context_from_data(prefetched_data)
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
            "cooldown_active": [],  # Added: symbols in cooldown after recent stop-out
            "errors": []
        }
        
        # Direction analytics tracking
        direction_stats = {
            "longs_generated": 0,
            "shorts_generated": 0,
            "tie_breaks_long": 0,
            "tie_breaks_short": 0,
            "tie_breaks_neutral_default": 0
        }
        
        # Parallel per-symbol processing (using pre-fetched data)
        def _safe_process(sym: str) -> tuple[Optional[TradePlan], Optional[Dict[str, Any]]]:
            try:
                # Pass pre-fetched data to avoid duplicate API calls
                prefetched = prefetched_data.get(sym)
                return self._process_symbol(sym, run_id, timestamp, prefetched_data=prefetched)
            except Exception as e:  # pyright: ignore - intentional broad catch for robustness
                import traceback
                tb = traceback.format_exc()
                logger.error("❌ %s: Pipeline error - %s\n%s", sym, e, tb)
                self.telemetry.log_event(create_error_event(
                    error_message=str(e),
                    error_type=type(e).__name__,
                    symbol=sym,
                    run_id=run_id
                ))
                return None, {"symbol": sym, "error": str(e), "reason_type": "errors", "reason": str(e)}

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrency_workers) as executor:
            future_map = {executor.submit(_safe_process, s): s for s in symbols}
            for future in concurrent.futures.as_completed(future_map):
                symbol = future_map[future]
                try:
                    result, rejection_info = future.result(timeout=30)  # 30s timeout per symbol
                except concurrent.futures.TimeoutError:
                    logger.warning("⏱️ %s: Symbol processing timed out after 30s", symbol)
                    result, rejection_info = None, {
                        "symbol": symbol,
                        "reason_type": "errors",
                        "reason": "Processing timed out after 30 seconds"
                    }
                if result:
                    signals.append(result)
                    # Track direction stats
                    if result.direction == "LONG":
                        direction_stats["longs_generated"] += 1
                    else:
                        direction_stats["shorts_generated"] += 1
                    # Track tie-break usage from metadata
                    alt_confluence = getattr(result, 'metadata', {}).get('alt_confluence', {})
                    tie_break = alt_confluence.get('tie_break_used')
                    if tie_break == 'regime_bullish':
                        direction_stats["tie_breaks_long"] += 1
                    elif tie_break == 'regime_bearish':
                        direction_stats["tie_breaks_short"] += 1
                    elif tie_break == 'neutral_default_long':
                        direction_stats["tie_breaks_neutral_default"] += 1
                    logger.info("✅ %s: Signal generated (%.1f%%) - %s", symbol, result.confidence_score, result.direction)
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
                "cooldown_active": len(rejection_stats["cooldown_active"]),
                "errors": len(rejection_stats["errors"])
            },
            "details": rejection_stats,
            "direction_stats": direction_stats,
            "regime": {
                "composite": self.current_regime.composite if self.current_regime else "unknown",
                "score": self.current_regime.score if self.current_regime else 0,
                "policy_min_score": self.regime_policy.min_regime_score
            } if self.current_regime else None
        }
        
        self._progress("COMPLETE", {
            "run_id": run_id,
            "signals_generated": len(signals),
            "symbols_scanned": len(symbols),
            "rejected": rejected_count,
            "duration_sec": round(duration, 2)
        })
        return signals, rejection_summary
    
    def _process_symbol(
        self, 
        symbol: str, 
        run_id: str, 
        timestamp: datetime,
        prefetched_data: Optional[MultiTimeframeData] = None
    ) -> tuple[Optional[TradePlan], Optional[Dict[str, Any]]]:
        """
        Process single symbol through complete pipeline.
        
        Args:
            symbol: Trading pair to process
            run_id: Unique scan run identifier  
            timestamp: Scan timestamp
            prefetched_data: Optional pre-fetched multi-timeframe data (avoids duplicate API call)
            
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
        
        # Stage 2: Data ingestion (use pre-fetched data if available, else fetch)
        if prefetched_data is not None:
            context.multi_tf_data = prefetched_data
            logger.debug("📊 %s: Using pre-fetched data", symbol)
        else:
            context.multi_tf_data = self._ingest_data(symbol)
        try:
            tf_list = list(context.multi_tf_data.timeframes.keys()) if context.multi_tf_data else []
            candle_counts = {tf: len(df) for tf, df in (context.multi_tf_data.timeframes.items() if context.multi_tf_data else [])}
            logger.info("📊 %s data: TFs=%s | Candles=%s", symbol, ', '.join(tf_list), candle_counts)
            self._progress("INGEST", {"symbol": symbol, "timeframes": tf_list, "candle_counts": candle_counts})
        except Exception:
            pass
        
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
            logger.info("%s: ❌ GATE FAIL (critical_tfs) | Missing: %s | Required: %s",
                       symbol,
                       ', '.join(missing_critical_tfs),
                       ', '.join(self.scanner_mode.critical_timeframes))
            self._progress("GATE_FAIL", {
                "symbol": symbol,
                "gate": "critical_timeframes",
                "missing": missing_critical_tfs,
                "required": list(self.scanner_mode.critical_timeframes)
            })
            
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
        context.multi_tf_indicators = self._compute_indicators(context.multi_tf_data)
        try:
            ind_tfs = list(context.multi_tf_indicators.by_timeframe.keys()) if context.multi_tf_indicators else []
            self._progress("INDICATORS", {"symbol": symbol, "timeframes": ind_tfs})
        except Exception:
            pass
        
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
        context.smc_snapshot = self._detect_smc_patterns(context.multi_tf_data)
        try:
            snap = context.smc_snapshot
            self._progress("SMC", {
                "symbol": symbol,
                "order_blocks": len(getattr(snap, 'order_blocks', []) or []),
                "fvgs": len(getattr(snap, 'fvgs', []) or []),
                "structure_breaks": len(getattr(snap, 'structural_breaks', []) or []),
                "liquidity_sweeps": len(getattr(snap, 'liquidity_sweeps', []) or []),
                "equal_highs": len(getattr(snap, 'equal_highs', []) or []),
                "equal_lows": len(getattr(snap, 'equal_lows', []) or [])
            })
        except Exception:
            pass
        
        # Stage 4b: Volume Profile calculation (institutional-grade VAP analysis)
        try:
            # Use 4H timeframe for volume profile (balance of detail and significance)
            vp_tf = '4h'
            vp_df = context.multi_tf_data.timeframes.get(vp_tf)
            if vp_df is None or len(vp_df) < 50:
                # Fallback to 1H if 4H not available
                vp_tf = '1h'
                vp_df = context.multi_tf_data.timeframes.get(vp_tf)
            
            if vp_df is not None and len(vp_df) >= 50:
                volume_profile = calculate_volume_profile(vp_df, num_bins=40)
                context.metadata['volume_profile'] = {
                    'poc': volume_profile.poc.price_level,
                    'poc_volume_pct': volume_profile.poc.volume_pct,
                    'value_area_high': volume_profile.value_area_high,
                    'value_area_low': volume_profile.value_area_low,
                    'hvn_count': len(volume_profile.high_volume_nodes),
                    'lvn_count': len(volume_profile.low_volume_nodes),
                    'timeframe': vp_tf
                }
                # Store full profile object for confluence scoring
                context.metadata['_volume_profile_obj'] = volume_profile
                logger.info("📊 Volume Profile (%s): POC=%.4f (%.1f%%), VA=%.4f-%.4f, %d HVN, %d LVN",
                           vp_tf,
                           volume_profile.poc.price_level,
                           volume_profile.poc.volume_pct,
                           volume_profile.value_area_low,
                           volume_profile.value_area_high,
                           len(volume_profile.high_volume_nodes),
                           len(volume_profile.low_volume_nodes))
        except Exception as e:
            logger.debug("Volume profile calculation skipped: %s", e)
        
        # Stage 5: Confluence scoring
        context.confluence_breakdown = self._compute_confluence_score(context)
        try:
            br = context.confluence_breakdown
            top_factors = [
                {
                    "name": f.name,
                    "score": float(f.score),
                    "weight": float(f.weight),
                    "contrib": float(f.score * f.weight)
                }
                for f in (br.factors[:5] if getattr(br, 'factors', None) else [])
            ]
            self._progress("CONFLUENCE", {
                "symbol": symbol,
                "direction": context.metadata.get('chosen_direction', 'LONG'),
                "score": float(getattr(br, 'total_score', 0)),
                "min_required": float(getattr(self.config, 'min_confluence_score', 0)),
                "htf_aligned": bool(getattr(br, 'htf_aligned', False)),
                "btc_impulse_gate": bool(getattr(br, 'btc_impulse_gate', False)),
                "synergy_bonus": float(getattr(br, 'synergy_bonus', 0)),
                "conflict_penalty": float(getattr(br, 'conflict_penalty', 0)),
                "top_factors": top_factors
            })
        except Exception:
            pass
        
        # Check quality gate
        if context.confluence_breakdown.total_score < self.config.min_confluence_score:
            top_factors_str = ' | '.join([f"{f.name}={f.score:.1f}" for f in context.confluence_breakdown.factors[:3]])
            logger.info("%s [%s]: ❌ GATE FAIL (confluence) | Score=%.1f < %.1f | Top: %s", 
                       symbol, trace_id,
                       context.confluence_breakdown.total_score, 
                       self.config.min_confluence_score,
                       top_factors_str)
            
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
            self._progress("GATE_FAIL", {
                "symbol": symbol,
                "gate": "confluence",
                "score": float(context.confluence_breakdown.total_score),
                "threshold": float(self.config.min_confluence_score)
            })
            
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
        
        # Stage 5.5: Check cooldown before trade planning
        proposed_direction = context.metadata.get('chosen_direction', 'LONG')
        current_price = self._get_current_price(context.multi_tf_data)
        
        cooldown_rejection = self._check_cooldown(symbol, proposed_direction, current_price)
        if cooldown_rejection:
            logger.info("%s [%s]: ❌ GATE FAIL (cooldown) | Direction=%s | %s",
                       symbol, trace_id, proposed_direction, cooldown_rejection['reason'])
            
            self._progress("GATE_FAIL", {
                "symbol": symbol,
                "gate": "cooldown",
                "direction": proposed_direction,
                "hours_remaining": cooldown_rejection.get('cooldown_hours_remaining', 0),
                "stop_price": cooldown_rejection.get('stop_price', 0)
            })
            
            # Log telemetry event
            self.telemetry.log_event(create_signal_rejected_event(
                run_id=run_id,
                symbol=symbol,
                reason=cooldown_rejection['reason'],
                gate_name="cooldown",
                score=context.confluence_breakdown.total_score,
                threshold=0
            ))
            
            cooldown_rejection['trace_id'] = trace_id
            return None, cooldown_rejection
        
        # Stage 6: Trade planning
        logger.debug("%s [%s]: Generating trade plan", symbol, trace_id)
        # current_price already computed above for cooldown check
        context.plan = self._generate_trade_plan(context, current_price)
        try:
            if context.plan:
                tf_meta = context.plan.metadata.get('tf_responsibility', {})
                self._progress("PLANNER", {
                    "symbol": symbol,
                    "direction": context.plan.direction,
                    "setup": context.plan.setup_type,
                    "rr": float(getattr(context.plan, 'risk_reward', 0)),
                    "entry": {
                        "near": float(context.plan.entry_zone.near_entry),
                        "far": float(context.plan.entry_zone.far_entry)
                    },
                    "stop": float(context.plan.stop_loss.level) if context.plan.stop_loss else None,
                    "targets": [float(t.level) for t in (context.plan.targets or [])],
                    "tf": {
                        "entry": tf_meta.get('entry_timeframe'),
                        "stop": tf_meta.get('sl_timeframe'),
                        "target": tf_meta.get('tp_timeframe')
                    }
                })
            else:
                self._progress("PLANNER_FAIL", {"symbol": symbol, "reason": "no_plan"})
        except Exception:
            pass
        
        # Stage 7: Risk validation
        logger.debug("%s [%s]: Validating risk parameters", symbol, trace_id)
        risk_failure_reason = None
        if context.plan:
            # Store the actual risk validation failure reason
            if not self._validate_risk(context.plan):
                # Extract actual reason from last risk_manager call (stored in instance variable)
                risk_failure_reason = getattr(self, '_last_risk_failure', 'Failed risk validation')
                logger.info("%s [%s]: ❌ GATE FAIL (risk) | R:R=%.2f | Reason: %s",
                           symbol, trace_id,
                           context.plan.risk_reward if hasattr(context.plan, 'risk_reward') else 0,
                           risk_failure_reason)
            else:
                logger.info("%s [%s]: ✅ GATE PASS (risk) | R:R=%.2f",
                           symbol, trace_id,
                           context.plan.risk_reward if hasattr(context.plan, 'risk_reward') else 0)
        
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
                # Use actual failure reason if available from planner
                actual_reason = context.metadata.get('plan_failure_reason', 'Insufficient SMC patterns for entry/stop placement')
                self.diagnostics['planner_rejections'].append({
                    'symbol': symbol,
                    'trace_id': trace_id,
                    'reason': actual_reason
                })
                rejection_info = {
                    "symbol": symbol,
                    "reason_type": reason_type,
                    "reason": actual_reason,
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
            try:
                self._progress("GATE_FAIL", {
                    "symbol": symbol,
                    "gate": "risk_validation",
                    "reason": reason,
                    "rr": float(getattr(context.plan, 'risk_reward', 0)) if context.plan else None
                })
            except Exception:
                pass
            
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
        try:
            if context.plan:
                self._progress("PASS", {"symbol": symbol, "stage": "risk_validation"})
        except Exception:
            pass
        
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
                
                # Log detailed indicator values for visibility
                current_price = df['close'].iloc[-1]
                logger.info("📊 %s indicators: RSI=%.1f | MFI=%.1f | ATR=%.2f (%.2f%%) | BB(%.2f-%.2f-%.2f) | VolSpike=%s",
                           timeframe,
                           rsi.iloc[-1],
                           mfi.iloc[-1],
                           atr.iloc[-1],
                           (atr.iloc[-1] / current_price * 100) if current_price > 0 else 0,
                           bb_lower.iloc[-1], bb_middle.iloc[-1], bb_upper.iloc[-1],
                           bool(volume_spike.iloc[-1]))
                
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
        all_equal_highs = []
        all_equal_lows = []
        swing_structure_by_tf = {}  # HTF swing structure (HH/HL/LH/LL)
        premium_discount_by_tf = {}  # Premium/Discount zone analysis
        
        # Get current price for premium/discount and key level detection
        current_price = self._get_current_price(multi_tf_data)
        
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
                
                # Equal highs/lows (liquidity pools)
                try:
                    ehl = detect_equal_highs_lows(df)
                    all_equal_highs.extend(ehl.get('equal_highs', []))
                    all_equal_lows.extend(ehl.get('equal_lows', []))
                except Exception:
                    pass  # Non-critical, continue without
                
                # Swing structure (HH/HL/LH/LL) - primarily for HTF bias
                # Run on Weekly, Daily, 4H for directional bias detection
                # NOTE: Use lowercase to match scanner mode timeframe conventions
                if _timeframe.lower() in ('1w', '1d', '4h'):
                    try:
                        swing_struct = detect_swing_structure(
                            df, 
                            lookback=getattr(self.smc_config, 'structure_swing_lookback', 15)
                        )
                        swing_structure_by_tf[_timeframe] = swing_struct.to_dict()
                        logger.debug("📊 %s Swing structure: trend=%s, last_HH=%s, last_HL=%s",
                                   _timeframe, swing_struct.trend,
                                   f"{swing_struct.last_hh.price:.4f}" if swing_struct.last_hh else "N/A",
                                   f"{swing_struct.last_hl.price:.4f}" if swing_struct.last_hl else "N/A")
                    except Exception as e:
                        logger.debug("Swing structure detection failed for %s: %s", _timeframe, e)
                
                # Premium/Discount zone detection - run on all TFs for entry optimization
                try:
                    pd_zone = detect_premium_discount(df, lookback=50, current_price=current_price)
                    premium_discount_by_tf[_timeframe] = pd_zone.to_dict()
                    logger.debug("📊 %s P/D Zone: %s (%.1f%%)", 
                               _timeframe, pd_zone.current_zone, pd_zone.zone_percentage or 50)
                except Exception as e:
                    logger.debug("Premium/Discount detection failed for %s: %s", _timeframe, e)
                
                # Log SMC detections per timeframe
                logger.info("🎯 %s SMC: OB=%d | FVG=%d | BOS/CHoCH=%d | Sweeps=%d",
                           _timeframe,
                           len(obs),
                           len(fvgs),
                           len(breaks),
                           len(sweeps))
                
            except Exception as e:
                logger.warning("SMC detection failed for %s: %s", _timeframe, e)
                self.diagnostics['smc_rejections'].append({'timeframe': _timeframe, 'error': str(e)})
                continue
        
        # Deduplicate equal highs/lows (they may repeat across TFs)
        unique_equal_highs = list(set(all_equal_highs))
        unique_equal_lows = list(set(all_equal_lows))
        
        if unique_equal_highs or unique_equal_lows:
            logger.info("💧 Liquidity pools: %d equal highs, %d equal lows",
                       len(unique_equal_highs), len(unique_equal_lows))
        
        # Log HTF swing structure summary
        if swing_structure_by_tf:
            for tf, ss in swing_structure_by_tf.items():
                logger.info("📈 %s Structure: %s trend", tf, ss.get('trend', 'unknown'))
        
        # --- Key Levels Detection (PWH/PWL/PDH/PDL) ---
        key_levels_data = None
        try:
            df_daily = multi_tf_data.timeframes.get('1D')
            df_weekly = multi_tf_data.timeframes.get('1W')
            if df_daily is not None and len(df_daily) >= 2:
                key_levels = detect_key_levels(df_daily, df_weekly, current_price)
                key_levels_data = key_levels.to_dict()
                logger.info("🔑 Key Levels: PDH=%.4f PDL=%.4f PWH=%s PWL=%s",
                           key_levels.pdh.price if key_levels.pdh else 0,
                           key_levels.pdl.price if key_levels.pdl else 0,
                           f"{key_levels.pwh.price:.4f}" if key_levels.pwh else "N/A",
                           f"{key_levels.pwl.price:.4f}" if key_levels.pwl else "N/A")
        except Exception as e:
            logger.debug("Key levels detection failed: %s", e)
        
        # --- Mitigation Tracking (update OB freshness) ---
        # Use the most recent LTF data to check for mitigation
        try:
            ltf_df = multi_tf_data.timeframes.get('15m') or multi_tf_data.timeframes.get('1H')
            if ltf_df is not None and len(ltf_df) > 0 and all_order_blocks:
                all_order_blocks, mitigation_status = update_ob_mitigation(
                    all_order_blocks, ltf_df, max_mitigation=0.5
                )
                if mitigation_status.fully_mitigated_count > 0:
                    logger.info("🔄 OB Mitigation: %d fully mitigated, %d partial, %d fresh",
                               mitigation_status.fully_mitigated_count,
                               mitigation_status.partially_mitigated_count,
                               mitigation_status.fresh_count)
        except Exception as e:
            logger.debug("Mitigation tracking failed: %s", e)
        
        return SMCSnapshot(
            order_blocks=all_order_blocks,
            fvgs=all_fvgs,
            structural_breaks=all_structure_breaks,
            liquidity_sweeps=all_liquidity_sweeps,
            equal_highs=unique_equal_highs,
            equal_lows=unique_equal_lows,
            swing_structure=swing_structure_by_tf,
            premium_discount=premium_discount_by_tf,
            key_levels=key_levels_data
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
        
        # Get current price EARLY - required for confluence scoring
        current_price = self._get_current_price(context.multi_tf_data)
        if current_price is None or current_price <= 0:
            raise ValueError(f"{context.symbol}: Cannot determine current price for confluence scoring")
        
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
                # current_price already defined above
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

        # --- CYCLE CONTEXT DETECTION ---
        # Detect cycle timing context from daily/weekly data for cycle-aware scoring
        cycle_context = None
        reversal_context_long = None
        reversal_context_short = None
        
        try:
            # Prefer daily data for cycle detection, fall back to 4H
            daily_df = context.multi_tf_data.timeframes.get('1D') or context.multi_tf_data.timeframes.get('1d')
            weekly_df = context.multi_tf_data.timeframes.get('1W') or context.multi_tf_data.timeframes.get('1w')
            
            # Use daily if available, otherwise try 4H (less accurate for cycle timing)
            cycle_df = daily_df if daily_df is not None and len(daily_df) >= 50 else None
            
            if cycle_df is not None:
                cycle_context = detect_cycle_context(
                    df=cycle_df,
                    config=None,  # Use crypto defaults
                    structural_breaks=context.smc_snapshot.structural_breaks if context.smc_snapshot else None
                )
                
                # Detect reversal contexts for both directions
                if context.smc_snapshot:
                    primary_tf = getattr(self.config, 'primary_planning_timeframe', '15m')
                    primary_indicators = context.multi_tf_indicators.by_timeframe.get(primary_tf) if context.multi_tf_indicators else None
                    
                    reversal_context_long = detect_reversal_context(
                        smc_snapshot=context.smc_snapshot,
                        cycle_context=cycle_context,
                        indicators=primary_indicators,
                        direction="LONG"
                    )
                    reversal_context_short = detect_reversal_context(
                        smc_snapshot=context.smc_snapshot,
                        cycle_context=cycle_context,
                        indicators=primary_indicators,
                        direction="SHORT"
                    )
                
                # Log cycle context
                if cycle_context and cycle_context.phase.value != "unknown":
                    logger.info("🔄 Cycle: phase=%s, translation=%s, DCL_days=%s, bias=%s (%.0f%%)",
                               cycle_context.phase.value,
                               cycle_context.translation.value,
                               cycle_context.dcl_days_since,
                               cycle_context.trade_bias,
                               cycle_context.confidence)
                    
                    # Store in context metadata for downstream use
                    context.metadata['cycle'] = {
                        'phase': cycle_context.phase.value,
                        'translation': cycle_context.translation.value,
                        'dcl_days_since': cycle_context.dcl_days_since,
                        'wcl_days_since': cycle_context.wcl_days_since,
                        'in_dcl_zone': cycle_context.in_dcl_zone,
                        'in_wcl_zone': cycle_context.in_wcl_zone,
                        'trade_bias': cycle_context.trade_bias,
                        'confidence': cycle_context.confidence
                    }
        except Exception as e:
            logger.debug("Cycle detection skipped: %s", e)
            cycle_context = None

        # Get volume profile for confluence scoring
        volume_profile_obj = context.metadata.get('_volume_profile_obj')
        
        # Evaluate both directions and choose the stronger confluence
        long_breakdown = calculate_confluence_score(
            smc_snapshot=context.smc_snapshot,
            indicators=context.multi_tf_indicators,
            config=self.config,
            direction="LONG",
            htf_context=htf_ctx_long,
            cycle_context=cycle_context,
            reversal_context=reversal_context_long,
            volume_profile=volume_profile_obj,
            current_price=current_price
        )
        short_breakdown = calculate_confluence_score(
            smc_snapshot=context.smc_snapshot,
            indicators=context.multi_tf_indicators,
            config=self.config,
            direction="SHORT",
            htf_context=htf_ctx_short,
            cycle_context=cycle_context,
            reversal_context=reversal_context_short,
            volume_profile=volume_profile_obj,
            current_price=current_price
        )

        # Log bidirectional confluence comparison
        logger.info("⚖️  Direction eval: LONG=%.1f vs SHORT=%.1f",
                   long_breakdown.total_score,
                   short_breakdown.total_score)

        # Cycle + Regime aware adjustment: BONUS for aligned setups, NO PENALTY for contrarian
        # This replaces the old penalty system with additive bonuses
        def cycle_regime_adjust(score: float, direction: str) -> float:
            bonus = 0.0
            try:
                # === CYCLE-BASED BONUS ===
                # Add bonus when direction aligns with cycle context
                if cycle_context:
                    should_boost, boost_amount = should_boost_direction(cycle_context, direction)
                    if should_boost:
                        bonus += boost_amount
                        logger.debug("📊 Cycle bonus: %s setup aligns with cycle (+%.1f)",
                                   direction, boost_amount)
                
                # === REGIME-BASED BONUS ===
                # Add bonus when direction aligns with regime trend
                # NO PENALTY for contrarian - just no bonus
                symbol_regime = context.metadata.get('symbol_regime')
                trend = (symbol_regime.trend if symbol_regime else None) or 'neutral'
                
                if trend == 'bullish' and direction == 'LONG':
                    bonus += 3.0
                    logger.debug("📈 Regime bonus: LONG aligns with bullish regime (+3.0)")
                elif trend == 'bearish' and direction == 'SHORT':
                    bonus += 3.0
                    logger.debug("📉 Regime bonus: SHORT aligns with bearish regime (+3.0)")
                # Note: No penalty for contrarian trades - they just don't get the bonus
                # This allows cycle turns at regime extremes to pass through
                
            except Exception:
                pass
            return score + bonus

        long_breakdown.total_score = cycle_regime_adjust(long_breakdown.total_score, 'LONG')
        short_breakdown.total_score = cycle_regime_adjust(short_breakdown.total_score, 'SHORT')

        # Choose direction - avoid long-side bias by using > instead of >=
        # Ties are broken by regime trend, then HTF momentum, then skip
        if long_breakdown.total_score > short_breakdown.total_score:
            chosen = long_breakdown
            tie_break_used = None
            logger.info("✅ Direction: LONG selected (score %.1f > %.1f)",
                       long_breakdown.total_score, short_breakdown.total_score)
        elif short_breakdown.total_score > long_breakdown.total_score:
            chosen = short_breakdown
            tie_break_used = None
            logger.info("✅ Direction: SHORT selected (score %.1f > %.1f)",
                       short_breakdown.total_score, long_breakdown.total_score)
        else:
            # Exact tie - use regime trend as tie-breaker
            regime_trend = (context.metadata.get('symbol_regime').trend 
                           if context.metadata.get('symbol_regime') else 'neutral')
            if regime_trend == 'bullish':
                chosen = long_breakdown
                tie_break_used = 'regime_bullish'
                logger.info("🔄 TIE (%.1f) broken by regime: LONG (bullish regime)", long_breakdown.total_score)
            elif regime_trend == 'bearish':
                chosen = short_breakdown
                tie_break_used = 'regime_bearish'
                logger.info("🔄 TIE (%.1f) broken by regime: SHORT (bearish regime)", short_breakdown.total_score)
            else:
                # True neutral tie - default to long but flag it
                chosen = long_breakdown
                tie_break_used = 'neutral_default_long'
                logger.info("🔄 TIE (%.1f) with neutral regime: defaulting to LONG", long_breakdown.total_score)
        
        # Persist alt scores for analytics/debugging
        context.metadata['alt_confluence'] = {
            'long': long_breakdown.total_score,
            'short': short_breakdown.total_score,
            'tie_break_used': tie_break_used if 'tie_break_used' in dir() else None
        }
        # Store chosen direction for downstream planning
        chosen_direction = 'LONG' if chosen is long_breakdown else 'SHORT'
        context.metadata['chosen_direction'] = chosen_direction
        
        # Store reversal context for the chosen direction (used in plan rationale generation)
        chosen_reversal = reversal_context_long if chosen_direction == 'LONG' else reversal_context_short
        if chosen_reversal and chosen_reversal.is_reversal_setup:
            context.metadata['reversal'] = {
                'is_reversal_setup': chosen_reversal.is_reversal_setup,
                'direction': chosen_reversal.direction,
                'cycle_aligned': chosen_reversal.cycle_aligned,
                'htf_bypass_active': chosen_reversal.htf_bypass_active,
                'confidence': chosen_reversal.confidence,
                'rationale': chosen_reversal.rationale
            }
        
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
            
            # Attach cycle context for rationale enrichment and UI display
            if plan and 'cycle' in context.metadata:
                try:
                    plan.metadata['cycle'] = context.metadata.get('cycle')
                except Exception:
                    pass
            
            # Attach reversal context for rationale enrichment and UI display
            if plan and 'reversal' in context.metadata:
                try:
                    plan.metadata['reversal'] = context.metadata.get('reversal')
                    
                    # Enrich rationale with cycle/reversal context
                    reversal_rationale = get_reversal_rationale_for_plan(
                        reversal_metadata=context.metadata.get('reversal'),
                        cycle_metadata=context.metadata.get('cycle')
                    )
                    if reversal_rationale:
                        plan.rationale = f"{reversal_rationale}\n\n{plan.rationale}"
                except Exception:
                    pass
            
            # Attach volume profile for UI display
            if plan and 'volume_profile' in context.metadata:
                try:
                    plan.metadata['volume_profile'] = context.metadata.get('volume_profile')
                except Exception:
                    pass
            
            # Attach liquidity pools (equal highs/lows) for UI display
            if plan and context.smc_snapshot:
                try:
                    if context.smc_snapshot.equal_highs or context.smc_snapshot.equal_lows:
                        plan.metadata['liquidity_pools'] = {
                            'equal_highs': context.smc_snapshot.equal_highs[:5],  # Top 5
                            'equal_lows': context.smc_snapshot.equal_lows[:5]
                        }
                except Exception:
                    pass
            
            # Attach direction analytics (alt scores, tie-break info) for monitoring
            if plan and 'alt_confluence' in context.metadata:
                try:
                    plan.metadata['alt_confluence'] = context.metadata.get('alt_confluence')
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
            # Store the actual failure reason for accurate rejection reporting
            context.metadata['plan_failure_reason'] = str(e)
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
    
    def _detect_global_regime(
        self, 
        prefetched_btc_data: Optional[MultiTimeframeData] = None
    ) -> Optional[MarketRegime]:
        """
        Detect global market regime from BTC/USDT.
        
        Args:
            prefetched_btc_data: Optional pre-fetched BTC data (avoids duplicate API call)
        
        Returns:
            MarketRegime or None if detection fails
        """
        try:
            # Use pre-fetched data if available, otherwise fetch (fallback)
            if prefetched_btc_data is not None:
                btc_data = prefetched_btc_data
                logger.debug("Using pre-fetched BTC data for regime detection")
            else:
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

    def _compute_macro_context_from_data(
        self, 
        data_map: Dict[str, MultiTimeframeData]
    ) -> Optional[MacroContext]:
        """
        Compute macro dominance/flow context from pre-fetched data.

        Uses basket-based proxies from available market data:
        - btc_velocity_1h: 1h percent change for BTC/USDT
        - alt_velocity_1h: equal-weight 1h percent change across non-BTC symbols in scan set
        - stable_velocity_1h: inferred from breadth (alts up/down %) as a proxy for stables flow
        - percent_alts_up: share of alts with last close > previous close on 1h
        - btc_volatility_1h: ATR(14) / price for BTC on 1h
        
        Args:
            data_map: Pre-fetched multi-timeframe data keyed by symbol
            
        Returns:
            MacroContext with computed metrics, or None if insufficient data
        """
        from backend.analysis.dominance_service import get_dominance_for_macro
        from backend.analysis.macro_context import MacroContext, _dir_from_pct, compute_cluster_score, classify_macro_state
        from backend.indicators.volatility import compute_atr
        
        try:
            btc_symbol = 'BTC/USDT'

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
                logger.debug("Macro context: No BTC 1h data available")
                return None
            btc_df = btc_data.timeframes['1h']
            btc_vel = pct_change_last(btc_df) or 0.0

            # ATR% proxy for BTC on 1h
            try:
                atr_series = compute_atr(btc_df)
                atr_val = float(atr_series.iloc[-1]) if atr_series is not None and len(atr_series) else 0.0
                price = float(btc_df['close'].iloc[-1]) if len(btc_df) else 0.0
                btc_vol_pct = (atr_val / price) if price > 0 else 0.0
            except Exception:
                btc_vol_pct = 0.0

            # Alt basket = non-BTC symbols in provided list that we have data for
            alt_syms = [s for s in data_map.keys() if s != btc_symbol]
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

            # Fetch real dominance data from DominanceService (cached, no API delay)
            btc_dom, alt_dom, stable_dom = get_dominance_for_macro()
            
            # Build MacroContext
            ctx = MacroContext(
                btc_dom=btc_dom,
                alt_dom=alt_dom,
                stable_dom=stable_dom,
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
            ctx.macro_state = classify_macro_state(ctx)
            ctx.cluster_score = compute_cluster_score(ctx)
            
            logger.info("📈 Macro context: BTC vel=%.2f%%, Alt vel=%.2f%%, Alts up=%.0f%%, State=%s",
                       btc_vel, alt_vel, percent_alts_up, ctx.macro_state.name)
            return ctx
        except Exception as e:
            logger.debug("Macro context computation failed: %s", e)
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

    # ======================== COOLDOWN MANAGEMENT ========================
    
    def register_stop_out(
        self, 
        symbol: str, 
        price: float, 
        direction: str,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Register a stop-out event to prevent immediate re-entry.
        
        Called after a trade hits its stop-loss. Prevents the system from
        immediately generating a new signal at the same price level.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            price: Stop-out price level
            direction: Trade direction ('LONG' or 'SHORT')
            timestamp: When the stop-out occurred (defaults to now)
        """
        ts = timestamp or datetime.now(timezone.utc)
        key = f"{symbol}_{direction}"  # Direction-specific cooldown
        
        self._symbol_cooldowns[key] = {
            'timestamp': ts,
            'price': price,
            'direction': direction,
            'symbol': symbol
        }
        
        logger.info("🚫 %s: Registered stop-out (dir=%s, price=%.4f) - cooldown for %d hours",
                   symbol, direction, price, self._cooldown_hours)
        
        # Log telemetry event
        self.telemetry.log_event(create_info_event(
            message=f"Stop-out registered for {symbol} {direction}",
            stage="COOLDOWN",
            payload={
                'symbol': symbol,
                'direction': direction,
                'stop_price': price,
                'cooldown_hours': self._cooldown_hours,
                'cooldown_expires': (ts.timestamp() + self._cooldown_hours * 3600)
            }
        ))
    
    def _check_cooldown(
        self, 
        symbol: str, 
        proposed_direction: str,
        current_price: float
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a symbol is in cooldown and should not receive new signals.
        
        Args:
            symbol: Trading pair
            proposed_direction: Direction of the proposed new trade
            current_price: Current market price
            
        Returns:
            None if no cooldown active, or rejection dict with reason
        """
        key = f"{symbol}_{proposed_direction}"
        
        if key not in self._symbol_cooldowns:
            return None
        
        cooldown_info = self._symbol_cooldowns[key]
        cooldown_ts = cooldown_info['timestamp']
        now = datetime.now(timezone.utc)
        
        # Calculate time since stop-out
        hours_elapsed = (now - cooldown_ts).total_seconds() / 3600
        
        # Check if cooldown has expired
        if hours_elapsed >= self._cooldown_hours:
            # Cooldown expired - remove entry and allow trading
            del self._symbol_cooldowns[key]
            logger.debug("%s: Cooldown expired (%.1f hours elapsed)", symbol, hours_elapsed)
            return None
        
        # Still in cooldown - check if price has moved significantly
        stop_price = cooldown_info['price']
        price_move_pct = abs(current_price - stop_price) / stop_price * 100
        
        # Allow re-entry if price moved >5% away from stop-out level
        if price_move_pct > 5.0:
            logger.info("%s: Cooldown bypassed - price moved %.1f%% from stop-out level",
                       symbol, price_move_pct)
            del self._symbol_cooldowns[key]
            return None
        
        # Still in cooldown - reject
        hours_remaining = self._cooldown_hours - hours_elapsed
        logger.info("%s: 🚫 COOLDOWN ACTIVE | %.1f hours remaining | Stop-out price=%.4f | Current=%.4f",
                   symbol, hours_remaining, stop_price, current_price)
        
        return {
            "symbol": symbol,
            "reason_type": "cooldown_active",
            "reason": f"Recent stop-out at {stop_price:.4f} ({hours_elapsed:.1f}h ago) - wait {hours_remaining:.1f}h or until price moves >5%",
            "cooldown_hours_remaining": hours_remaining,
            "stop_price": stop_price,
            "current_price": current_price,
            "price_distance_pct": price_move_pct,
            "direction": proposed_direction
        }
    
    def clear_cooldown(self, symbol: str, direction: Optional[str] = None) -> None:
        """
        Manually clear cooldown for a symbol.
        
        Args:
            symbol: Trading pair
            direction: Specific direction to clear, or None to clear both
        """
        if direction:
            key = f"{symbol}_{direction}"
            if key in self._symbol_cooldowns:
                del self._symbol_cooldowns[key]
                logger.info("%s: Cooldown cleared for %s", symbol, direction)
        else:
            # Clear both directions
            for dir in ['LONG', 'SHORT']:
                key = f"{symbol}_{dir}"
                if key in self._symbol_cooldowns:
                    del self._symbol_cooldowns[key]
            logger.info("%s: All cooldowns cleared", symbol)

    def _progress(self, stage: str, payload: Dict[str, Any]) -> None:
        """Emit a standardized progress snapshot for user-facing consoles and telemetry.

        Writes a concise line to the console and mirrors the payload into telemetry as an INFO event.
        Safe to call anywhere; failures are swallowed.
        """
        try:
            line = {
                "stage": stage,
                "ts": int(time.time()),
                **payload
            }
            logger.info("PIPELINE %s | %s", stage, json.dumps(line, default=str))
            if hasattr(self, 'telemetry') and self.telemetry:
                try:
                    self.telemetry.log_event(create_info_event(
                        message=f"Pipeline progress: {stage}",
                        stage=stage,
                        payload=payload
                    ))
                except Exception:
                    pass
        except Exception:
            pass