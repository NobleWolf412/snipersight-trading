#!/usr/bin/env python3
"""
SniperSight Confluence Debug Tool v1.0

Comprehensive debugging tool for confluence scoring workflow including:
- Indicator computation (Bollinger Bands, RSI, ATR, etc.)
- SMC pattern detection with A/B/C grading
- HTF gates and structural proximity
- Full confluence factor breakdown
- Error detection and gap analysis

Usage:
    python debug_confluence.py --symbol BTC/USDT
    python debug_confluence.py --symbol BTC/USDT --mode strike --verbose
    python debug_confluence.py --all-symbols --mode stealth
"""

import argparse
import asyncio
import sys
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

# Add project root to path
sys.path.insert(0, "/home/maccardi4431/snipersight-trading")

from loguru import logger

# Configure minimal logging to reduce noise
logger.remove()
logger.add(sys.stderr, level="WARNING", format="{message}")


# ============================================================================
# DATA CLASSES FOR DEBUG RESULTS
# ============================================================================

@dataclass
class IndicatorDebug:
    """Debug info for indicator computation."""
    timeframe: str
    success: bool
    error: Optional[str] = None
    rsi: Optional[float] = None
    stoch_rsi: Optional[float] = None
    atr: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    volume_spike: Optional[bool] = None
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    warnings: List[str] = field(default_factory=list)


@dataclass  
class SMCPatternDebug:
    """Debug info for SMC patterns."""
    pattern_type: str  # order_block, fvg, bos_choch, liquidity_sweep
    timeframe: str
    direction: str
    grade: str  # A, B, C
    score: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfluenceDebug:
    """Full confluence debug breakdown."""
    symbol: str
    mode: str
    direction: Optional[str] = None
    final_score: Optional[float] = None
    threshold: float = 0.0
    passed: bool = False
    
    # Components
    indicators: Dict[str, IndicatorDebug] = field(default_factory=dict)
    smc_patterns: List[SMCPatternDebug] = field(default_factory=list)
    confluence_factors: Dict[str, float] = field(default_factory=dict)
    htf_gate_results: Dict[str, Any] = field(default_factory=dict)
    
    # Errors and warnings
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    workflow_gaps: List[str] = field(default_factory=list)


# ============================================================================
# COLOR OUTPUT
# ============================================================================

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    
    @classmethod
    def grade(cls, g: str) -> str:
        """Color by grade."""
        if g == 'A':
            return f"{cls.GREEN}{cls.BOLD}A{cls.END}"
        elif g == 'B':
            return f"{cls.YELLOW}B{cls.END}"
        else:
            return f"{cls.RED}C{cls.END}"


def print_header(text: str):
    print(f"\n{Colors.CYAN}{'═' * 80}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{text.center(80)}{Colors.END}")
    print(f"{Colors.CYAN}{'═' * 80}{Colors.END}")


def print_section(text: str):
    print(f"\n{Colors.YELLOW}{'─' * 60}{Colors.END}")
    print(f"{Colors.YELLOW}{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.YELLOW}{'─' * 60}{Colors.END}")


def print_subsection(text: str):
    print(f"\n{Colors.BLUE}{text}{Colors.END}")


def print_error(text: str):
    print(f"{Colors.RED}✗ ERROR: {text}{Colors.END}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ WARNING: {text}{Colors.END}")


def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_info(text: str):
    print(f"  {text}")


# ============================================================================
# DEBUG FUNCTIONS
# ============================================================================

def debug_indicators(
    symbol: str,
    multi_tf_data: Any,
    timeframes: Tuple[str, ...],
    verbose: bool = False
) -> Dict[str, IndicatorDebug]:
    """Debug indicator computation for all timeframes."""
    from backend.indicators.momentum import compute_rsi, compute_stoch_rsi, compute_mfi, compute_macd
    from backend.indicators.volatility import compute_atr, compute_bollinger_bands
    from backend.indicators.volume import detect_volume_spike
    
    results = {}
    
    for tf in timeframes:
        debug = IndicatorDebug(timeframe=tf, success=False)
        
        try:
            if tf not in multi_tf_data.timeframes:
                debug.error = f"No data for timeframe {tf}"
                debug.warnings.append(f"Missing candle data")
                results[tf] = debug
                continue
            
            candles_df = multi_tf_data.timeframes[tf]
            
            # Check data quality
            if len(candles_df) < 50:
                debug.warnings.append(f"Only {len(candles_df)} candles (need 50+ for reliable indicators)")
            
            # Check for zero volume
            zero_vol_count = (candles_df['volume'] == 0).sum()
            zero_vol_pct = zero_vol_count / len(candles_df) * 100
            if zero_vol_pct > 10:
                debug.warnings.append(f"{zero_vol_count} zero volume bars ({zero_vol_pct:.1f}%)")
            
            # Compute indicators one by one to identify specific failures
            try:
                rsi = compute_rsi(candles_df)
                debug.rsi = float(rsi.iloc[-1])
            except Exception as e:
                debug.warnings.append(f"RSI failed: {e}")
            
            try:
                stoch_rsi = compute_stoch_rsi(candles_df)
                if isinstance(stoch_rsi, tuple):
                    debug.stoch_rsi = float(stoch_rsi[0].iloc[-1])  # K value
                else:
                    debug.stoch_rsi = float(stoch_rsi.iloc[-1])
            except Exception as e:
                debug.warnings.append(f"Stoch RSI failed: {e}")
            
            try:
                atr = compute_atr(candles_df)
                debug.atr = float(atr.iloc[-1])
            except Exception as e:
                debug.warnings.append(f"ATR failed: {e}")
            
            try:
                bb_upper, bb_middle, bb_lower = compute_bollinger_bands(candles_df)
                debug.bb_upper = float(bb_upper.iloc[-1])
                debug.bb_middle = float(bb_middle.iloc[-1])
                debug.bb_lower = float(bb_lower.iloc[-1])
                
                # Validate Bollinger Bands
                if not (debug.bb_upper > debug.bb_middle > debug.bb_lower):
                    debug.warnings.append(
                        f"BB invalid: upper={debug.bb_upper:.4f}, "
                        f"middle={debug.bb_middle:.4f}, lower={debug.bb_lower:.4f}"
                    )
            except Exception as e:
                debug.warnings.append(f"Bollinger Bands failed: {e}")
            
            try:
                volume_spike = detect_volume_spike(candles_df)
                debug.volume_spike = bool(volume_spike.iloc[-1])
            except Exception as e:
                debug.warnings.append(f"Volume spike failed: {e}")
            
            try:
                macd_line, macd_signal, macd_hist = compute_macd(candles_df)
                debug.macd_line = float(macd_line.iloc[-1])
                debug.macd_signal = float(macd_signal.iloc[-1])
                debug.macd_histogram = float(macd_hist.iloc[-1])
            except Exception as e:
                debug.warnings.append(f"MACD failed: {e}")
            
            # Check if we have minimum required indicators
            if debug.rsi is not None and debug.atr is not None and debug.bb_upper is not None:
                debug.success = True
            else:
                debug.error = "Missing required indicators (RSI, ATR, or Bollinger Bands)"
                
        except Exception as e:
            debug.error = f"{type(e).__name__}: {str(e)}"
            debug.warnings.append(f"Unexpected error: {traceback.format_exc()}")
        
        results[tf] = debug
    
    return results


def debug_smc_patterns(
    symbol: str,
    multi_tf_data: Any,
    indicators_by_tf: Dict[str, Any],
    timeframes: Tuple[str, ...],
    verbose: bool = False
) -> Tuple[List[SMCPatternDebug], Optional[Any]]:
    """Debug SMC pattern detection with grade breakdown."""
    from backend.strategy.smc.order_blocks import detect_order_blocks
    from backend.strategy.smc.fvg import detect_fvgs
    from backend.strategy.smc.bos_choch import detect_structural_breaks
    from backend.strategy.smc.liquidity_sweeps import detect_liquidity_sweeps
    from backend.shared.models.smc import SMCSnapshot
    from backend.shared.config.smc_config import SMCConfig
    
    patterns = []
    smc_cfg = SMCConfig.defaults()
    
    # Aggregate all SMC data
    all_order_blocks = []
    all_fvgs = []
    all_structural_breaks = []
    all_sweeps = []
    
    for tf in timeframes:
        if tf not in multi_tf_data.timeframes:
            continue
        
        candles_df = multi_tf_data.timeframes[tf]
        ind = indicators_by_tf.get(tf)
        atr = ind.atr if ind and ind.atr else None
        
        if not atr:
            continue
        
        # Order Blocks - only takes df and config
        try:
            obs = detect_order_blocks(candles_df, smc_cfg)
            for ob in obs:
                grade = getattr(ob, 'grade', 'B')
                # Add timeframe manually since function doesn't set it
                ob = ob._replace(timeframe=tf) if hasattr(ob, '_replace') else ob
                if hasattr(ob, 'timeframe'):
                    pass  # Already has it
                else:
                    ob.timeframe = tf
                all_order_blocks.append(ob)
                patterns.append(SMCPatternDebug(
                    pattern_type="order_block",
                    timeframe=tf,
                    direction=ob.direction,
                    grade=grade,
                    score=ob.freshness_score * 100,
                    details={
                        'freshness': ob.freshness_score,
                        'displacement': getattr(ob, 'displacement_strength', None),
                        'mitigation': ob.mitigation_level,
                        'high': ob.high,
                        'low': ob.low
                    }
                ))
        except Exception as e:
            patterns.append(SMCPatternDebug(
                pattern_type="order_block",
                timeframe=tf,
                direction="error",
                grade="X",
                score=0,
                details={'error': str(e)}
            ))
        
        # FVGs - only takes df and config
        try:
            fvgs = detect_fvgs(candles_df, smc_cfg)
            for fvg in fvgs:
                grade = getattr(fvg, 'grade', 'B')
                # Add timeframe to FVG since detect_fvgs doesn't set it
                if not hasattr(fvg, 'timeframe') or not fvg.timeframe:
                    fvg.timeframe = tf
                all_fvgs.append(fvg)
                # Use correct attribute: overlap_with_price (not filled)
                fill_pct = getattr(fvg, 'overlap_with_price', 0)
                patterns.append(SMCPatternDebug(
                    pattern_type="fvg",
                    timeframe=tf,
                    direction=fvg.direction,
                    grade=grade,
                    score=fvg.size / atr * 100 if atr else 0,
                    details={
                        'size': fvg.size,
                        'overlap_with_price': fill_pct,
                        'top': fvg.top,
                        'bottom': fvg.bottom,
                        'freshness_score': getattr(fvg, 'freshness_score', 1.0)
                    }
                ))
        except Exception as e:
            patterns.append(SMCPatternDebug(
                pattern_type="fvg",
                timeframe=tf,
                direction="error",
                grade="X",
                score=0,
                details={'error': str(e)}
            ))
        
        # BOS/CHoCH - only takes df and config (not atr as positional)
        try:
            breaks = detect_structural_breaks(candles_df, smc_cfg)
            for brk in breaks:
                grade = getattr(brk, 'grade', 'B')
                # Add timeframe manually
                if not hasattr(brk, 'timeframe') or not brk.timeframe:
                    brk.timeframe = tf
                all_structural_breaks.append(brk)
                # Use correct attribute names: level (not break_level), break_distance_atr (not break_distance)
                break_distance = getattr(brk, 'break_distance_atr', 0)
                patterns.append(SMCPatternDebug(
                    pattern_type=brk.break_type,
                    timeframe=tf,
                    direction=brk.direction,
                    grade=grade,
                    score=50 + (break_distance * 10) if break_distance else 50,
                    details={
                        'break_type': brk.break_type,
                        'level': brk.level,  # Correct attr name
                        'break_distance_atr': break_distance,
                        'htf_aligned': brk.htf_aligned
                    }
                ))
        except Exception as e:
            patterns.append(SMCPatternDebug(
                pattern_type="bos_choch",
                timeframe=tf,
                direction="error",
                grade="X",
                score=0,
                details={'error': str(e)}
            ))
        
        # Liquidity Sweeps - only takes df and config
        try:
            sweeps = detect_liquidity_sweeps(candles_df, smc_cfg)
            for sweep in sweeps:
                grade = getattr(sweep, 'grade', 'B')
                # Add timeframe manually
                if not hasattr(sweep, 'timeframe') or not sweep.timeframe:
                    sweep.timeframe = tf
                all_sweeps.append(sweep)
                # Use correct attribute: sweep_type (not direction), level (not sweep_level)
                # Derive direction from sweep_type: "high" sweep = bearish (trapped longs), "low" sweep = bullish
                derived_direction = "bearish" if sweep.sweep_type == "high" else "bullish"
                reversal_strength = getattr(sweep, 'reversal_strength', 0) or 0
                patterns.append(SMCPatternDebug(
                    pattern_type="liquidity_sweep",
                    timeframe=tf,
                    direction=derived_direction,
                    grade=grade,
                    score=reversal_strength / atr * 100 if atr and reversal_strength else 50,
                    details={
                        'level': sweep.level,
                        'sweep_type': sweep.sweep_type,
                        'confirmation': sweep.confirmation,
                        'reversal_strength': reversal_strength
                    }
                ))
        except Exception as e:
            patterns.append(SMCPatternDebug(
                pattern_type="liquidity_sweep",
                timeframe=tf,
                direction="error",
                grade="X",
                score=0,
                details={'error': str(e)}
            ))
    
    # Create SMC snapshot for confluence scoring
    smc_snapshot = SMCSnapshot(
        order_blocks=all_order_blocks,
        fvgs=all_fvgs,
        structural_breaks=all_structural_breaks,
        liquidity_sweeps=all_sweeps
    )
    
    return patterns, smc_snapshot


def debug_confluence_scoring(
    symbol: str,
    smc_snapshot: Any,
    indicators: Any,
    mode_config: Any,
    direction: str,
    current_price: float,
    verbose: bool = False
) -> Dict[str, Any]:
    """Debug confluence scoring factors."""
    from backend.strategy.confluence.scorer import (
        calculate_confluence_score,
        evaluate_htf_structural_proximity,
        evaluate_htf_momentum_gate,
        resolve_timeframe_conflicts,
        GRADE_WEIGHTS,
        _score_order_blocks,
        _score_fvgs,
        _score_structural_breaks,
        _score_liquidity_sweeps
    )
    
    results = {
        'factors': {},
        'htf_gates': {},
        'errors': [],
        'warnings': []
    }
    
    # Score individual SMC components
    try:
        results['factors']['order_blocks'] = _score_order_blocks(smc_snapshot.order_blocks, direction)
    except Exception as e:
        results['errors'].append(f"order_blocks scoring: {e}")
        results['factors']['order_blocks'] = 0
    
    try:
        results['factors']['fvgs'] = _score_fvgs(smc_snapshot.fvgs, direction)
    except Exception as e:
        results['errors'].append(f"fvgs scoring: {e}")
        results['factors']['fvgs'] = 0
    
    try:
        results['factors']['structural_breaks'] = _score_structural_breaks(
            smc_snapshot.structural_breaks, direction
        )
    except Exception as e:
        results['errors'].append(f"structural_breaks scoring: {e}")
        results['factors']['structural_breaks'] = 0
    
    try:
        results['factors']['liquidity_sweeps'] = _score_liquidity_sweeps(
            smc_snapshot.liquidity_sweeps, direction
        )
    except Exception as e:
        results['errors'].append(f"liquidity_sweeps scoring: {e}")
        results['factors']['liquidity_sweeps'] = 0
    
    # HTF Gates
    try:
        htf_prox = evaluate_htf_structural_proximity(
            smc_snapshot, indicators, current_price, direction, mode_config
        )
        results['htf_gates']['structural_proximity'] = htf_prox
    except Exception as e:
        results['errors'].append(f"HTF structural proximity: {e}")
        results['htf_gates']['structural_proximity'] = {'error': str(e)}
    
    try:
        htf_momentum = evaluate_htf_momentum_gate(
            indicators, direction, mode_config
        )
        results['htf_gates']['momentum_gate'] = htf_momentum
    except Exception as e:
        results['errors'].append(f"HTF momentum gate: {e}")
        results['htf_gates']['momentum_gate'] = {'error': str(e)}
    
    try:
        tf_conflicts = resolve_timeframe_conflicts(
            indicators, direction, mode_config
        )
        results['htf_gates']['timeframe_conflicts'] = tf_conflicts
    except Exception as e:
        results['errors'].append(f"Timeframe conflict resolution: {e}")
        results['htf_gates']['timeframe_conflicts'] = {'error': str(e)}
    
    # Full confluence score
    try:
        breakdown = calculate_confluence_score(
            smc_snapshot=smc_snapshot,
            indicators=indicators,
            config=mode_config,
            direction=direction,
            current_price=current_price
        )
        results['full_breakdown'] = breakdown
        results['final_score'] = breakdown.total_score
    except Exception as e:
        results['errors'].append(f"Full confluence scoring: {e}")
        results['full_breakdown'] = None
        results['final_score'] = 0
    
    return results


def analyze_workflow_gaps(debug_result: ConfluenceDebug) -> List[str]:
    """Analyze confluence debug result for workflow gaps and issues."""
    gaps = []
    
    # Check indicator coverage
    failed_tfs = [tf for tf, ind in debug_result.indicators.items() if not ind.success]
    if failed_tfs:
        gaps.append(f"Indicator computation failed for {len(failed_tfs)} timeframes: {', '.join(failed_tfs)}")
    
    # Check for BB validation errors
    bb_errors = [tf for tf, ind in debug_result.indicators.items() 
                 if ind.error and "Bollinger" in ind.error]
    if bb_errors:
        gaps.append(f"Bollinger Band validation errors in: {', '.join(bb_errors)}")
    
    # Check SMC pattern errors
    pattern_errors = [p for p in debug_result.smc_patterns if p.grade == 'X']
    if pattern_errors:
        gaps.append(f"{len(pattern_errors)} SMC pattern detection errors")
    
    # Check grade distribution
    grades = [p.grade for p in debug_result.smc_patterns if p.grade != 'X']
    if grades:
        grade_a = grades.count('A')
        grade_b = grades.count('B')
        grade_c = grades.count('C')
        if grade_a == 0 and len(grades) > 5:
            gaps.append(f"No Grade A patterns detected (B={grade_b}, C={grade_c})")
        if grade_c > grade_a + grade_b:
            gaps.append(f"Majority Grade C patterns ({grade_c}/{len(grades)}) - weak setups")
    
    # Check HTF gate results
    htf_gates = debug_result.htf_gate_results
    if htf_gates.get('structural_proximity', {}).get('error'):
        gaps.append(f"HTF structural proximity gate error")
    if htf_gates.get('momentum_gate', {}).get('error'):
        gaps.append(f"HTF momentum gate error")
    
    # Check confluence factor balance
    factors = debug_result.confluence_factors
    if factors:
        low_factors = [k for k, v in factors.items() if v < 30]
        if len(low_factors) >= 3:
            gaps.append(f"Multiple low-scoring factors (<30): {', '.join(low_factors)}")
    
    return gaps


# ============================================================================
# MAIN DEBUG FUNCTION
# ============================================================================

async def debug_symbol(
    symbol: str,
    mode: str = "strike",
    verbose: bool = False
) -> ConfluenceDebug:
    """Run full confluence debug for a symbol."""
    from backend.data.adapters.phemex import PhemexAdapter
    from backend.data.ingestion_pipeline import IngestionPipeline
    from backend.shared.config.scanner_modes import get_mode
    from backend.shared.models.indicators import IndicatorSet
    
    debug_result = ConfluenceDebug(symbol=symbol, mode=mode)
    
    # Get mode config
    try:
        mode_config = get_mode(mode)
        debug_result.threshold = mode_config.min_confluence_score
    except Exception as e:
        debug_result.errors.append(f"Failed to load mode '{mode}': {e}")
        return debug_result
    
    timeframes = mode_config.timeframes
    
    # Fetch data
    try:
        adapter = PhemexAdapter()
        pipeline = IngestionPipeline(adapter)
        multi_tf_data = await asyncio.to_thread(
            pipeline.fetch_multi_timeframe, symbol, list(timeframes)
        )
    except Exception as e:
        debug_result.errors.append(f"Data fetch failed: {e}")
        return debug_result
    
    # Get current price
    try:
        primary_tf = mode_config.primary_planning_timeframe
        if primary_tf in multi_tf_data.timeframes:
            candles = multi_tf_data.timeframes[primary_tf]
            current_price = candles.iloc[-1]['close']
        else:
            current_price = None
    except Exception as e:
        debug_result.warnings.append(f"Could not get current price: {e}")
        current_price = None
    
    # Debug indicators
    print_subsection(f"Debugging Indicators for {symbol}")
    debug_result.indicators = debug_indicators(symbol, multi_tf_data, timeframes, verbose)
    
    # Build indicator set
    indicators_by_tf = {}
    for tf, ind_debug in debug_result.indicators.items():
        if ind_debug.success:
            from backend.shared.models.indicators import IndicatorSnapshot
            indicators_by_tf[tf] = IndicatorSnapshot(
                rsi=ind_debug.rsi,
                stoch_rsi=ind_debug.stoch_rsi,
                atr=ind_debug.atr,
                bb_upper=ind_debug.bb_upper,
                bb_middle=ind_debug.bb_middle,
                bb_lower=ind_debug.bb_lower,
                volume_spike=ind_debug.volume_spike or False,
                macd_line=ind_debug.macd_line,
                macd_signal=ind_debug.macd_signal,
                macd_histogram=ind_debug.macd_histogram
            )
    
    indicator_set = IndicatorSet(by_timeframe=indicators_by_tf)
    
    # Debug SMC patterns
    print_subsection(f"Debugging SMC Patterns for {symbol}")
    debug_result.smc_patterns, smc_snapshot = debug_smc_patterns(
        symbol, multi_tf_data, indicators_by_tf, timeframes, verbose
    )
    
    # Determine direction from latest structural break
    direction = "bullish"  # Default
    if smc_snapshot and smc_snapshot.structural_breaks:
        latest_break = max(smc_snapshot.structural_breaks, key=lambda b: b.timestamp)
        direction = latest_break.direction
    debug_result.direction = direction
    
    # Debug confluence scoring
    if smc_snapshot and current_price:
        print_subsection(f"Debugging Confluence Scoring for {symbol}")
        
        # Convert ScannerMode to ScanConfig for confluence scoring
        from backend.shared.config.defaults import ScanConfig
        scan_config = ScanConfig(
            profile=mode_config.profile,
            timeframes=mode_config.timeframes,
            min_confluence_score=mode_config.min_confluence_score,
            min_rr_ratio=mode_config.overrides.get('min_rr_ratio', 1.5) if mode_config.overrides else 1.5,
            primary_planning_timeframe=mode_config.primary_planning_timeframe,
            max_pullback_atr=mode_config.max_pullback_atr,
            min_stop_atr=mode_config.min_stop_atr,
            max_stop_atr=mode_config.max_stop_atr,
        )
        
        confluence_debug = debug_confluence_scoring(
            symbol, smc_snapshot, indicator_set, scan_config, direction, current_price, verbose
        )
        
        debug_result.confluence_factors = confluence_debug.get('factors', {})
        debug_result.htf_gate_results = confluence_debug.get('htf_gates', {})
        debug_result.final_score = confluence_debug.get('final_score')
        debug_result.errors.extend(confluence_debug.get('errors', []))
        debug_result.warnings.extend(confluence_debug.get('warnings', []))
        
        if debug_result.final_score is not None:
            debug_result.passed = debug_result.final_score >= debug_result.threshold
    
    # Analyze workflow gaps
    debug_result.workflow_gaps = analyze_workflow_gaps(debug_result)
    
    return debug_result


def print_debug_result(result: ConfluenceDebug, verbose: bool = False):
    """Print formatted debug result."""
    print_header(f"CONFLUENCE DEBUG: {result.symbol}")
    
    print(f"\n  Mode: {result.mode}")
    print(f"  Direction: {result.direction}")
    print(f"  Final Score: {result.final_score:.1f}%" if result.final_score else "  Final Score: N/A")
    print(f"  Threshold: {result.threshold}%")
    print(f"  Status: {Colors.GREEN}PASSED{Colors.END}" if result.passed else f"  Status: {Colors.RED}FAILED{Colors.END}")
    
    # Indicators
    print_section("INDICATOR COMPUTATION")
    
    for tf, ind in sorted(result.indicators.items()):
        status = f"{Colors.GREEN}✓{Colors.END}" if ind.success else f"{Colors.RED}✗{Colors.END}"
        print(f"\n  {status} {tf}:")
        
        if ind.success:
            print(f"      RSI: {ind.rsi:.1f}  |  StochRSI: {ind.stoch_rsi:.1f}  |  ATR: {ind.atr:.4f}")
            print(f"      BB: [{ind.bb_lower:.4f}, {ind.bb_middle:.4f}, {ind.bb_upper:.4f}]")
            if ind.macd_line:
                print(f"      MACD: {ind.macd_line:.4f} / Signal: {ind.macd_signal:.4f} / Hist: {ind.macd_histogram:.4f}")
        else:
            print_error(f"      {ind.error}")
        
        for warn in ind.warnings:
            print_warning(f"      {warn}")
    
    # SMC Patterns
    print_section("SMC PATTERN DETECTION")
    
    # Group by pattern type
    by_type = defaultdict(list)
    for p in result.smc_patterns:
        by_type[p.pattern_type].append(p)
    
    for pattern_type, patterns in by_type.items():
        print(f"\n  {pattern_type.upper().replace('_', ' ')}:")
        
        # Grade distribution
        grades = [p.grade for p in patterns if p.grade != 'X']
        errors = [p for p in patterns if p.grade == 'X']
        
        if grades:
            grade_str = f"A={grades.count('A')} B={grades.count('B')} C={grades.count('C')}"
            print(f"      Grades: {grade_str}")
        
        if verbose:
            for p in patterns[:5]:  # Show first 5
                if p.grade == 'X':
                    print_error(f"      {p.timeframe}: {p.details.get('error', 'unknown error')}")
                else:
                    grade_colored = Colors.grade(p.grade)
                    print(f"      {p.timeframe} [{grade_colored}] {p.direction}: score={p.score:.1f}")
        
        if errors:
            print_error(f"      {len(errors)} detection errors")
    
    # Confluence Factors
    print_section("CONFLUENCE FACTOR BREAKDOWN")
    
    if result.confluence_factors:
        sorted_factors = sorted(result.confluence_factors.items(), key=lambda x: x[1], reverse=True)
        for factor, score in sorted_factors:
            bar_len = int(score / 2)
            bar = '█' * bar_len + '░' * (50 - bar_len)
            color = Colors.GREEN if score >= 60 else Colors.YELLOW if score >= 40 else Colors.RED
            print(f"  {factor:30} [{color}{bar}{Colors.END}] {score:.1f}")
    
    # HTF Gates
    print_section("HTF GATE RESULTS")
    
    for gate, result_data in result.htf_gate_results.items():
        if isinstance(result_data, dict):
            if 'error' in result_data:
                print_error(f"  {gate}: {result_data['error']}")
            else:
                valid = result_data.get('valid', result_data.get('passed', None))
                score = result_data.get('score_adjustment', result_data.get('adjustment', 0))
                reason = result_data.get('reason', result_data.get('nearest_structure', 'N/A'))
                
                status = f"{Colors.GREEN}PASSED{Colors.END}" if valid else f"{Colors.RED}BLOCKED{Colors.END}"
                print(f"  {gate}: {status}")
                print(f"      Adjustment: {score:+.1f}")
                if verbose and reason:
                    print(f"      Reason: {reason[:60]}...")
    
    # Errors
    if result.errors:
        print_section("ERRORS DETECTED")
        for err in result.errors:
            print_error(f"  {err}")
    
    # Warnings
    if result.warnings:
        print_section("WARNINGS")
        for warn in result.warnings:
            print_warning(f"  {warn}")
    
    # Workflow Gaps
    if result.workflow_gaps:
        print_section("WORKFLOW GAPS IDENTIFIED")
        for gap in result.workflow_gaps:
            print(f"  {Colors.RED}→{Colors.END} {gap}")
    
    # Summary
    print_section("SUMMARY")
    
    if result.passed:
        print_success(f"Confluence score {result.final_score:.1f}% meets threshold {result.threshold}%")
    else:
        if result.final_score:
            gap = result.threshold - result.final_score
            print(f"  {Colors.RED}Confluence score {result.final_score:.1f}% below threshold {result.threshold}%{Colors.END}")
            print(f"  {Colors.YELLOW}Gap: {gap:.1f} points needed{Colors.END}")
        
        # Diagnosis
        if result.errors:
            print(f"\n  {Colors.RED}⚠ ERRORS are blocking confluence calculation{Colors.END}")
        elif result.workflow_gaps:
            print(f"\n  {Colors.YELLOW}⚠ Workflow gaps may be reducing score artificially{Colors.END}")
        else:
            print(f"\n  {Colors.CYAN}ℹ Low confluence appears legitimate - weak setup{Colors.END}")


# ============================================================================
# MAIN
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(description="SniperSight Confluence Debug Tool")
    parser.add_argument("--symbol", "-s", default="BTC/USDT", help="Symbol to debug")
    parser.add_argument("--mode", "-m", default="strike", help="Scanner mode")
    parser.add_argument("--all-symbols", "-a", action="store_true", help="Debug all default symbols")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    
    args = parser.parse_args()
    
    print(f"""
{Colors.CYAN}{'━' * 80}{Colors.END}
{Colors.BOLD}   ███████╗███╗   ██╗██╗██████╗ ███████╗██████╗ ███████╗██╗ ██████╗ ██╗  ██╗████████╗
   ██╔════╝████╗  ██║██║██╔══██╗██╔════╝██╔══██╗██╔════╝██║██╔════╝ ██║  ██║╚══██╔══╝
   ███████╗██╔██╗ ██║██║██████╔╝█████╗  ██████╔╝███████╗██║██║  ███╗███████║   ██║   
   ╚════██║██║╚██╗██║██║██╔═══╝ ██╔══╝  ██╔══██╗╚════██║██║██║   ██║██╔══██║   ██║   
   ███████║██║ ╚████║██║██║     ███████╗██║  ██║███████║██║╚██████╔╝██║  ██║   ██║   
   ╚══════╝╚═╝  ╚═══╝╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝{Colors.END}

{Colors.YELLOW}                    CONFLUENCE DEBUG TOOL v1.0{Colors.END}
{Colors.CYAN}{'━' * 80}{Colors.END}

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Mode: {args.mode}
Verbose: {args.verbose}
""")
    
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"] if args.all_symbols else [args.symbol]
    
    all_results = []
    for symbol in symbols:
        print(f"\n{Colors.CYAN}Processing {symbol}...{Colors.END}")
        result = await debug_symbol(symbol, args.mode, args.verbose)
        all_results.append(result)
        print_debug_result(result, args.verbose)
    
    # Summary across all symbols
    if len(all_results) > 1:
        print_header("CROSS-SYMBOL SUMMARY")
        
        passed = [r for r in all_results if r.passed]
        failed = [r for r in all_results if not r.passed]
        errors = [r for r in all_results if r.errors]
        
        print(f"\n  Total: {len(all_results)}")
        print(f"  {Colors.GREEN}Passed: {len(passed)}{Colors.END}")
        print(f"  {Colors.RED}Failed: {len(failed)}{Colors.END}")
        print(f"  {Colors.RED}Errors: {len(errors)}{Colors.END}")
        
        # Common issues
        all_gaps = []
        for r in all_results:
            all_gaps.extend(r.workflow_gaps)
        
        if all_gaps:
            print(f"\n  Common Issues:")
            from collections import Counter
            for gap, count in Counter(all_gaps).most_common(5):
                print(f"    {count}x: {gap}")


if __name__ == "__main__":
    asyncio.run(main())
