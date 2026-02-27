#!/usr/bin/env python3
"""
SniperSight Deep Confluence Analysis Tool v1.0

Comprehensive analysis tool that investigates:
1. Full symbol scan across all modes
2. Structural breaks scoring breakdown (why only 40%?)
3. HTF gate blocking analysis
4. FVG detection gaps
5. Grade distribution analysis (A/B/C)
6. Confluence factor contribution weights
7. Missing indicators/data gaps

Usage:
    python debug_confluence_deep.py --all-symbols
    python debug_confluence_deep.py --mode strike --analyze-gates
    python debug_confluence_deep.py --symbol BTC/USDT --deep
"""

import argparse
import asyncio
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import json

# Add project root to path
sys.path.insert(0, "/home/maccardi4431/snipersight-trading")

from loguru import logger

# Configure minimal logging
logger.remove()
logger.add(sys.stderr, level="WARNING", format="{message}")


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
    DIM = '\033[2m'
    END = '\033[0m'
    
    @classmethod
    def grade(cls, g: str) -> str:
        if g == 'A':
            return f"{cls.GREEN}{cls.BOLD}A{cls.END}"
        elif g == 'B':
            return f"{cls.YELLOW}B{cls.END}"
        else:
            return f"{cls.RED}C{cls.END}"
    
    @classmethod
    def score_color(cls, score: float, threshold: float = 50) -> str:
        if score >= threshold * 1.2:
            return cls.GREEN
        elif score >= threshold:
            return cls.YELLOW
        else:
            return cls.RED


def print_header(text: str):
    print(f"\n{Colors.CYAN}{'═' * 90}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{text.center(90)}{Colors.END}")
    print(f"{Colors.CYAN}{'═' * 90}{Colors.END}")


def print_section(text: str):
    print(f"\n{Colors.YELLOW}{'─' * 70}{Colors.END}")
    print(f"{Colors.YELLOW}{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.YELLOW}{'─' * 70}{Colors.END}")


def print_subsection(text: str):
    print(f"\n{Colors.BLUE}{text}{Colors.END}")


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class SymbolAnalysis:
    """Complete analysis for a single symbol."""
    symbol: str
    mode: str
    direction: str = "bullish"
    final_score: float = 0.0
    threshold: float = 60.0
    passed: bool = False
    
    # Detailed breakdowns
    indicator_status: Dict[str, bool] = field(default_factory=dict)
    smc_grades: Dict[str, Dict[str, int]] = field(default_factory=dict)  # {pattern_type: {A: n, B: n, C: n}}
    confluence_factors: Dict[str, float] = field(default_factory=dict)
    htf_gates: Dict[str, Dict] = field(default_factory=dict)
    
    # Issues
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Raw data for deep analysis
    raw_smc_patterns: List[Any] = field(default_factory=list)
    raw_indicators: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModeAnalysis:
    """Aggregate analysis for a scanner mode."""
    mode: str
    symbols_analyzed: int = 0
    symbols_passed: int = 0
    avg_score: float = 0.0
    
    # Common issues
    most_common_errors: List[Tuple[str, int]] = field(default_factory=list)
    weakest_factors: List[Tuple[str, float]] = field(default_factory=list)
    strongest_factors: List[Tuple[str, float]] = field(default_factory=list)
    
    # Gate analysis
    gate_block_rates: Dict[str, float] = field(default_factory=dict)
    
    # Grade distribution
    grade_distribution: Dict[str, Dict[str, int]] = field(default_factory=dict)


# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

async def analyze_symbol(
    symbol: str,
    mode: str,
    verbose: bool = False
) -> SymbolAnalysis:
    """Perform deep analysis on a single symbol."""
    from backend.data.adapters.phemex import PhemexAdapter
    from backend.data.ingestion_pipeline import IngestionPipeline
    from backend.shared.config.scanner_modes import get_mode
    from backend.shared.config.defaults import ScanConfig
    from backend.shared.models.indicators import IndicatorSet, IndicatorSnapshot
    from backend.strategy.smc.order_blocks import detect_order_blocks
    from backend.strategy.smc.fvg import detect_fvgs
    from backend.strategy.smc.bos_choch import detect_structural_breaks
    from backend.strategy.smc.liquidity_sweeps import detect_liquidity_sweeps
    from backend.shared.models.smc import SMCSnapshot
    from backend.shared.config.smc_config import SMCConfig
    from backend.indicators.momentum import compute_rsi, compute_stoch_rsi, compute_mfi, compute_macd
    from backend.indicators.volatility import compute_atr, compute_bollinger_bands
    from backend.indicators.volume import detect_volume_spike
    from backend.strategy.confluence.scorer import (
        calculate_confluence_score,
        evaluate_htf_structural_proximity,
        evaluate_htf_momentum_gate,
        resolve_timeframe_conflicts,
        _score_order_blocks,
        _score_fvgs,
        _score_structural_breaks,
        _score_liquidity_sweeps
    )
    
    analysis = SymbolAnalysis(symbol=symbol, mode=mode)
    
    # Get mode config
    try:
        mode_config = get_mode(mode)
        analysis.threshold = mode_config.min_confluence_score
    except Exception as e:
        analysis.errors.append(f"Failed to load mode: {e}")
        return analysis
    
    timeframes = mode_config.timeframes
    
    # Fetch data
    try:
        adapter = PhemexAdapter()
        pipeline = IngestionPipeline(adapter)
        multi_tf_data = await asyncio.to_thread(
            pipeline.fetch_multi_timeframe, symbol, list(timeframes)
        )
    except Exception as e:
        analysis.errors.append(f"Data fetch failed: {e}")
        return analysis
    
    # Get current price
    primary_tf = mode_config.primary_planning_timeframe
    current_price = None
    if primary_tf in multi_tf_data.timeframes:
        candles = multi_tf_data.timeframes[primary_tf]
        current_price = candles.iloc[-1]['close']
    
    # Compute indicators for each timeframe
    indicators_by_tf = {}
    smc_cfg = SMCConfig.defaults()
    
    for tf in timeframes:
        if tf not in multi_tf_data.timeframes:
            analysis.indicator_status[tf] = False
            analysis.warnings.append(f"No data for {tf}")
            continue
        
        candles_df = multi_tf_data.timeframes[tf]
        
        try:
            rsi = compute_rsi(candles_df)
            stoch_rsi = compute_stoch_rsi(candles_df)
            atr = compute_atr(candles_df)
            bb_upper, bb_middle, bb_lower = compute_bollinger_bands(candles_df)
            volume_spike = detect_volume_spike(candles_df)
            
            stoch_k = stoch_rsi[0].iloc[-1] if isinstance(stoch_rsi, tuple) else stoch_rsi.iloc[-1]
            
            try:
                macd_line, macd_signal, macd_hist = compute_macd(candles_df)
                macd_l, macd_s, macd_h = macd_line.iloc[-1], macd_signal.iloc[-1], macd_hist.iloc[-1]
            except:
                macd_l, macd_s, macd_h = None, None, None
            
            snapshot = IndicatorSnapshot(
                rsi=rsi.iloc[-1],
                stoch_rsi=stoch_k,
                atr=atr.iloc[-1],
                bb_upper=bb_upper.iloc[-1],
                bb_middle=bb_middle.iloc[-1],
                bb_lower=bb_lower.iloc[-1],
                volume_spike=bool(volume_spike.iloc[-1]),
                macd_line=macd_l,
                macd_signal=macd_s,
                macd_histogram=macd_h
            )
            
            indicators_by_tf[tf] = snapshot
            analysis.indicator_status[tf] = True
            analysis.raw_indicators[tf] = {
                'rsi': snapshot.rsi,
                'stoch_rsi': snapshot.stoch_rsi,
                'atr': snapshot.atr,
                'macd_line': snapshot.macd_line,
                'macd_signal': snapshot.macd_signal,
            }
            
        except Exception as e:
            analysis.indicator_status[tf] = False
            analysis.errors.append(f"Indicator computation failed for {tf}: {e}")
    
    indicator_set = IndicatorSet(by_timeframe=indicators_by_tf)
    
    # Detect SMC patterns
    all_order_blocks = []
    all_fvgs = []
    all_structural_breaks = []
    all_sweeps = []
    
    analysis.smc_grades = {
        'order_block': {'A': 0, 'B': 0, 'C': 0},
        'fvg': {'A': 0, 'B': 0, 'C': 0},
        'bos': {'A': 0, 'B': 0, 'C': 0},
        'choch': {'A': 0, 'B': 0, 'C': 0},
        'liquidity_sweep': {'A': 0, 'B': 0, 'C': 0}
    }
    
    for tf in timeframes:
        if tf not in multi_tf_data.timeframes or tf not in indicators_by_tf:
            continue
        
        candles_df = multi_tf_data.timeframes[tf]
        atr = indicators_by_tf[tf].atr
        
        # Order Blocks
        try:
            obs = detect_order_blocks(candles_df, smc_cfg)
            for ob in obs:
                grade = getattr(ob, 'grade', 'B')
                analysis.smc_grades['order_block'][grade] = analysis.smc_grades['order_block'].get(grade, 0) + 1
                all_order_blocks.append(ob)
        except Exception as e:
            analysis.warnings.append(f"OB detection failed for {tf}: {e}")
        
        # FVGs
        try:
            fvgs = detect_fvgs(candles_df, smc_cfg)
            for fvg in fvgs:
                grade = getattr(fvg, 'grade', 'B')
                analysis.smc_grades['fvg'][grade] = analysis.smc_grades['fvg'].get(grade, 0) + 1
                all_fvgs.append(fvg)
        except Exception as e:
            analysis.warnings.append(f"FVG detection failed for {tf}: {e}")
        
        # Structural Breaks
        try:
            breaks = detect_structural_breaks(candles_df, smc_cfg)
            for brk in breaks:
                grade = getattr(brk, 'grade', 'B')
                pattern_type = 'bos' if brk.break_type == 'BOS' else 'choch'
                analysis.smc_grades[pattern_type][grade] = analysis.smc_grades[pattern_type].get(grade, 0) + 1
                all_structural_breaks.append(brk)
        except Exception as e:
            analysis.warnings.append(f"BOS/CHoCH detection failed for {tf}: {e}")
        
        # Liquidity Sweeps
        try:
            sweeps = detect_liquidity_sweeps(candles_df, smc_cfg)
            for sweep in sweeps:
                grade = getattr(sweep, 'grade', 'B')
                analysis.smc_grades['liquidity_sweep'][grade] = analysis.smc_grades['liquidity_sweep'].get(grade, 0) + 1
                all_sweeps.append(sweep)
        except Exception as e:
            analysis.warnings.append(f"Sweep detection failed for {tf}: {e}")
    
    # Create SMC snapshot
    smc_snapshot = SMCSnapshot(
        order_blocks=all_order_blocks,
        fvgs=all_fvgs,
        structural_breaks=all_structural_breaks,
        liquidity_sweeps=all_sweeps
    )
    
    # Determine direction
    direction = "bullish"
    if smc_snapshot.structural_breaks:
        latest_break = max(smc_snapshot.structural_breaks, key=lambda b: b.timestamp)
        direction = latest_break.direction
    analysis.direction = direction
    
    # Score individual factors
    try:
        analysis.confluence_factors['order_blocks'] = _score_order_blocks(smc_snapshot.order_blocks, direction)
    except Exception as e:
        analysis.confluence_factors['order_blocks'] = 0
        analysis.errors.append(f"OB scoring: {e}")
    
    try:
        analysis.confluence_factors['fvgs'] = _score_fvgs(smc_snapshot.fvgs, direction)
    except Exception as e:
        analysis.confluence_factors['fvgs'] = 0
        analysis.errors.append(f"FVG scoring: {e}")
    
    try:
        analysis.confluence_factors['structural_breaks'] = _score_structural_breaks(smc_snapshot.structural_breaks, direction)
    except Exception as e:
        analysis.confluence_factors['structural_breaks'] = 0
        analysis.errors.append(f"Structure scoring: {e}")
    
    try:
        analysis.confluence_factors['liquidity_sweeps'] = _score_liquidity_sweeps(smc_snapshot.liquidity_sweeps, direction)
    except Exception as e:
        analysis.confluence_factors['liquidity_sweeps'] = 0
        analysis.errors.append(f"Sweep scoring: {e}")
    
    # Convert mode config to scan config for gates
    scan_config = ScanConfig(
        profile=mode_config.profile,
        timeframes=mode_config.timeframes,
        min_confluence_score=mode_config.min_confluence_score,
        min_rr_ratio=mode_config.overrides.get('min_rr_ratio', 1.5) if mode_config.overrides else 1.5,
        primary_planning_timeframe=mode_config.primary_planning_timeframe,
    )
    
    # HTF Gates
    if current_price:
        try:
            htf_prox = evaluate_htf_structural_proximity(
                smc_snapshot, indicator_set, current_price, direction, scan_config
            )
            analysis.htf_gates['structural_proximity'] = htf_prox
        except Exception as e:
            analysis.htf_gates['structural_proximity'] = {'error': str(e), 'valid': False}
        
        try:
            htf_momentum = evaluate_htf_momentum_gate(indicator_set, direction, scan_config)
            analysis.htf_gates['momentum_gate'] = htf_momentum
        except Exception as e:
            analysis.htf_gates['momentum_gate'] = {'error': str(e), 'passed': False}
        
        try:
            tf_conflicts = resolve_timeframe_conflicts(indicator_set, direction, scan_config)
            analysis.htf_gates['timeframe_conflicts'] = tf_conflicts
        except Exception as e:
            analysis.htf_gates['timeframe_conflicts'] = {'error': str(e), 'resolution': 'error'}
    
    # Full confluence score
    if current_price:
        try:
            breakdown = calculate_confluence_score(
                smc_snapshot=smc_snapshot,
                indicators=indicator_set,
                config=scan_config,
                direction=direction,
                current_price=current_price
            )
            analysis.final_score = breakdown.total_score
            analysis.passed = analysis.final_score >= analysis.threshold
        except Exception as e:
            analysis.errors.append(f"Confluence scoring: {e}")
    
    return analysis


def analyze_structural_breaks_deep(analysis: SymbolAnalysis) -> Dict:
    """Deep analysis of why structural breaks might be scoring low."""
    results = {
        'total_breaks': 0,
        'bullish_breaks': 0,
        'bearish_breaks': 0,
        'direction_aligned': 0,
        'direction_opposed': 0,
        'bos_count': 0,
        'choch_count': 0,
        'grade_distribution': analysis.smc_grades.get('bos', {}).copy(),
        'issues': []
    }
    
    # Count from grades
    bos_grades = analysis.smc_grades.get('bos', {})
    choch_grades = analysis.smc_grades.get('choch', {})
    
    results['bos_count'] = sum(bos_grades.values())
    results['choch_count'] = sum(choch_grades.values())
    results['total_breaks'] = results['bos_count'] + results['choch_count']
    
    # Merge grade distributions
    for grade in ['A', 'B', 'C']:
        results['grade_distribution'][grade] = bos_grades.get(grade, 0) + choch_grades.get(grade, 0)
    
    # Identify issues
    if results['total_breaks'] == 0:
        results['issues'].append("No structural breaks detected at all")
    
    grade_c_pct = results['grade_distribution'].get('C', 0) / max(results['total_breaks'], 1) * 100
    if grade_c_pct > 30:
        results['issues'].append(f"High Grade C percentage: {grade_c_pct:.1f}%")
    
    if results['bos_count'] > 0 and results['choch_count'] == 0:
        results['issues'].append("Only BOS detected, no CHoCH (may indicate trending market)")
    
    return results


def analyze_htf_gates_deep(analysis: SymbolAnalysis) -> Dict:
    """Deep analysis of HTF gate blocking."""
    results = {
        'gates_analyzed': 0,
        'gates_passed': 0,
        'gates_blocked': 0,
        'blocking_reasons': [],
        'recommendations': []
    }
    
    for gate_name, gate_result in analysis.htf_gates.items():
        results['gates_analyzed'] += 1
        
        if isinstance(gate_result, dict):
            if gate_result.get('error'):
                results['gates_blocked'] += 1
                results['blocking_reasons'].append(f"{gate_name}: ERROR - {gate_result['error']}")
            elif gate_result.get('valid', gate_result.get('passed', gate_result.get('resolution') == 'allowed')):
                results['gates_passed'] += 1
            else:
                results['gates_blocked'] += 1
                reason = gate_result.get('reason', gate_result.get('resolution', 'Unknown'))
                results['blocking_reasons'].append(f"{gate_name}: {reason[:80]}")
    
    # Generate recommendations
    if 'momentum_gate' in analysis.htf_gates:
        mg = analysis.htf_gates['momentum_gate']
        if not mg.get('passed') and 'neutral' in str(mg.get('reason', '')).lower():
            results['recommendations'].append(
                "Momentum gate blocked due to neutral HTF - consider if this is appropriate for scalp modes"
            )
    
    if 'timeframe_conflicts' in analysis.htf_gates:
        tc = analysis.htf_gates['timeframe_conflicts']
        adj = tc.get('score_adjustment', 0)
        if adj < -10:
            results['recommendations'].append(
                f"TF conflict penalty of {adj} applied - check if swing_structure is being passed"
            )
    
    return results


def analyze_fvg_detection(analysis: SymbolAnalysis) -> Dict:
    """Analyze FVG detection issues."""
    fvg_grades = analysis.smc_grades.get('fvg', {})
    total_fvgs = sum(fvg_grades.values())
    
    results = {
        'total_detected': total_fvgs,
        'grade_a': fvg_grades.get('A', 0),
        'grade_b': fvg_grades.get('B', 0),
        'grade_c': fvg_grades.get('C', 0),
        'score': analysis.confluence_factors.get('fvgs', 0),
        'issues': [],
        'recommendations': []
    }
    
    if total_fvgs == 0:
        results['issues'].append("No FVGs detected across any timeframe")
        results['recommendations'].append("Check SMC config fvg_min_gap_atr threshold - may be too high")
    
    if results['score'] == 0 and total_fvgs > 0:
        results['issues'].append(f"FVGs detected ({total_fvgs}) but score is 0 - direction mismatch?")
        results['recommendations'].append("Check if detected FVGs match trade direction")
    
    return results


# ============================================================================
# REPORTING FUNCTIONS
# ============================================================================

def print_symbol_analysis(analysis: SymbolAnalysis, deep: bool = False):
    """Print detailed analysis for a symbol."""
    status_color = Colors.GREEN if analysis.passed else Colors.RED
    status_text = "PASSED" if analysis.passed else "FAILED"
    
    print(f"\n  {Colors.BOLD}{analysis.symbol}{Colors.END} [{analysis.mode}]")
    print(f"  Score: {status_color}{analysis.final_score:.1f}%{Colors.END} / {analysis.threshold}% - {status_color}{status_text}{Colors.END}")
    print(f"  Direction: {analysis.direction}")
    
    # Confluence factors
    print(f"\n  {Colors.CYAN}Confluence Factors:{Colors.END}")
    for factor, score in sorted(analysis.confluence_factors.items(), key=lambda x: x[1], reverse=True):
        bar_len = int(score / 2)
        bar = '█' * bar_len + '░' * (50 - bar_len)
        color = Colors.GREEN if score >= 60 else Colors.YELLOW if score >= 40 else Colors.RED
        print(f"    {factor:20} [{color}{bar}{Colors.END}] {score:.1f}")
    
    # SMC Grade Distribution
    print(f"\n  {Colors.CYAN}SMC Pattern Grades:{Colors.END}")
    for pattern, grades in analysis.smc_grades.items():
        total = sum(grades.values())
        if total > 0:
            a_pct = grades.get('A', 0) / total * 100
            print(f"    {pattern:18} Total={total:3}  A={grades.get('A',0):3} ({a_pct:5.1f}%)  B={grades.get('B',0):3}  C={grades.get('C',0):3}")
    
    # HTF Gates
    print(f"\n  {Colors.CYAN}HTF Gates:{Colors.END}")
    for gate, result in analysis.htf_gates.items():
        if isinstance(result, dict):
            passed = result.get('valid', result.get('passed', result.get('resolution') == 'allowed'))
            adj = result.get('score_adjustment', 0)
            status = f"{Colors.GREEN}PASS{Colors.END}" if passed else f"{Colors.RED}BLOCK{Colors.END}"
            print(f"    {gate:25} {status}  adj={adj:+.1f}")
    
    # Indicators
    if deep:
        print(f"\n  {Colors.CYAN}Indicator Status:{Colors.END}")
        for tf, status in analysis.indicator_status.items():
            status_icon = f"{Colors.GREEN}✓{Colors.END}" if status else f"{Colors.RED}✗{Colors.END}"
            print(f"    {tf:6} {status_icon}")
    
    # Errors/Warnings
    if analysis.errors:
        print(f"\n  {Colors.RED}Errors:{Colors.END}")
        for err in analysis.errors[:5]:
            print(f"    ✗ {err[:70]}")
    
    if analysis.warnings and deep:
        print(f"\n  {Colors.YELLOW}Warnings:{Colors.END}")
        for warn in analysis.warnings[:5]:
            print(f"    ⚠ {warn[:70]}")


def print_mode_summary(mode_analysis: ModeAnalysis):
    """Print aggregate analysis for a mode."""
    pass_rate = mode_analysis.symbols_passed / max(mode_analysis.symbols_analyzed, 1) * 100
    
    print_section(f"MODE SUMMARY: {mode_analysis.mode.upper()}")
    
    print(f"\n  Symbols Analyzed: {mode_analysis.symbols_analyzed}")
    print(f"  Symbols Passed: {mode_analysis.symbols_passed} ({pass_rate:.1f}%)")
    print(f"  Average Score: {mode_analysis.avg_score:.1f}%")
    
    if mode_analysis.weakest_factors:
        print(f"\n  {Colors.CYAN}Weakest Factors (dragging scores down):{Colors.END}")
        for factor, avg_score in mode_analysis.weakest_factors[:5]:
            color = Colors.RED if avg_score < 30 else Colors.YELLOW
            print(f"    {factor:25} avg={color}{avg_score:.1f}{Colors.END}")
    
    if mode_analysis.gate_block_rates:
        print(f"\n  {Colors.CYAN}Gate Block Rates:{Colors.END}")
        for gate, rate in mode_analysis.gate_block_rates.items():
            color = Colors.RED if rate > 50 else Colors.YELLOW if rate > 20 else Colors.GREEN
            print(f"    {gate:25} {color}{rate:.1f}%{Colors.END} blocked")
    
    if mode_analysis.grade_distribution:
        print(f"\n  {Colors.CYAN}Grade Distribution (across all patterns):{Colors.END}")
        for pattern, grades in mode_analysis.grade_distribution.items():
            total = sum(grades.values())
            if total > 0:
                a_pct = grades.get('A', 0) / total * 100
                print(f"    {pattern:18} A={a_pct:5.1f}%  (of {total} total)")


def generate_recommendations(analyses: List[SymbolAnalysis], mode: str) -> List[str]:
    """Generate actionable recommendations based on analysis."""
    recommendations = []
    
    # Aggregate data
    all_factors = defaultdict(list)
    gate_blocks = defaultdict(int)
    total_analyses = len(analyses)
    
    for a in analyses:
        for factor, score in a.confluence_factors.items():
            all_factors[factor].append(score)
        for gate, result in a.htf_gates.items():
            if isinstance(result, dict):
                if not result.get('valid', result.get('passed', result.get('resolution') == 'allowed')):
                    gate_blocks[gate] += 1
    
    # Check for consistently low factors
    for factor, scores in all_factors.items():
        avg = sum(scores) / len(scores)
        if avg < 30:
            recommendations.append(
                f"Factor '{factor}' averages only {avg:.1f}% - investigate scoring weights or detection thresholds"
            )
    
    # Check for high gate block rates
    for gate, blocks in gate_blocks.items():
        rate = blocks / total_analyses * 100
        if rate > 60:
            if gate == 'momentum_gate':
                recommendations.append(
                    f"Momentum gate blocks {rate:.0f}% of symbols - consider if HTF momentum requirement matches mode intent"
                )
            elif gate == 'timeframe_conflicts':
                recommendations.append(
                    f"TF conflicts block {rate:.0f}% - check swing_structure availability or adjust penalties"
                )
    
    # Check FVG detection
    fvg_zeros = sum(1 for a in analyses if a.confluence_factors.get('fvgs', 0) == 0)
    if fvg_zeros / total_analyses > 0.5:
        recommendations.append(
            f"FVGs scoring 0 for {fvg_zeros}/{total_analyses} symbols - check direction alignment or fvg_min_gap_atr config"
        )
    
    # Check structural breaks
    struct_low = sum(1 for a in analyses if a.confluence_factors.get('structural_breaks', 0) < 50)
    if struct_low / total_analyses > 0.5:
        recommendations.append(
            f"Structural breaks scoring <50% for {struct_low}/{total_analyses} symbols - may need direction alignment check"
        )
    
    return recommendations


# ============================================================================
# MAIN ANALYSIS
# ============================================================================

async def run_full_analysis(
    symbols: List[str],
    mode: str,
    verbose: bool = False,
    deep: bool = False
) -> Tuple[List[SymbolAnalysis], ModeAnalysis]:
    """Run full analysis across all symbols for a mode."""
    analyses = []
    
    for symbol in symbols:
        print(f"  Analyzing {symbol}...", end=" ", flush=True)
        try:
            analysis = await analyze_symbol(symbol, mode, verbose)
            analyses.append(analysis)
            status = f"{Colors.GREEN}✓{Colors.END}" if analysis.passed else f"{Colors.RED}✗{Colors.END}"
            print(f"{status} {analysis.final_score:.1f}%")
        except Exception as e:
            print(f"{Colors.RED}ERROR: {e}{Colors.END}")
    
    # Aggregate into mode analysis
    mode_analysis = ModeAnalysis(mode=mode)
    mode_analysis.symbols_analyzed = len(analyses)
    mode_analysis.symbols_passed = sum(1 for a in analyses if a.passed)
    mode_analysis.avg_score = sum(a.final_score for a in analyses) / max(len(analyses), 1)
    
    # Aggregate factors
    factor_scores = defaultdict(list)
    for a in analyses:
        for factor, score in a.confluence_factors.items():
            factor_scores[factor].append(score)
    
    factor_avgs = {f: sum(s)/len(s) for f, s in factor_scores.items()}
    mode_analysis.weakest_factors = sorted(factor_avgs.items(), key=lambda x: x[1])[:5]
    mode_analysis.strongest_factors = sorted(factor_avgs.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Aggregate gate blocks
    gate_block_counts = defaultdict(int)
    for a in analyses:
        for gate, result in a.htf_gates.items():
            if isinstance(result, dict):
                if not result.get('valid', result.get('passed', result.get('resolution') == 'allowed')):
                    gate_block_counts[gate] += 1
    
    mode_analysis.gate_block_rates = {g: c/len(analyses)*100 for g, c in gate_block_counts.items()}
    
    # Aggregate grades
    grade_totals = defaultdict(lambda: {'A': 0, 'B': 0, 'C': 0})
    for a in analyses:
        for pattern, grades in a.smc_grades.items():
            for grade, count in grades.items():
                grade_totals[pattern][grade] += count
    mode_analysis.grade_distribution = dict(grade_totals)
    
    return analyses, mode_analysis


async def main():
    parser = argparse.ArgumentParser(description="SniperSight Deep Confluence Analysis")
    parser.add_argument("--symbol", "-s", help="Single symbol to analyze")
    parser.add_argument("--mode", "-m", default="strike", help="Scanner mode")
    parser.add_argument("--all-symbols", "-a", action="store_true", help="Analyze all default symbols")
    parser.add_argument("--all-modes", action="store_true", help="Analyze across all modes")
    parser.add_argument("--deep", "-d", action="store_true", help="Show deep analysis details")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--analyze-gates", action="store_true", help="Focus on HTF gate analysis")
    parser.add_argument("--analyze-structure", action="store_true", help="Focus on structural break analysis")
    
    args = parser.parse_args()
    
    print(f"""
{Colors.CYAN}{'━' * 90}{Colors.END}
{Colors.BOLD}   ███████╗███╗   ██╗██╗██████╗ ███████╗██████╗ ███████╗██╗ ██████╗ ██╗  ██╗████████╗
   ██╔════╝████╗  ██║██║██╔══██╗██╔════╝██╔══██╗██╔════╝██║██╔════╝ ██║  ██║╚══██╔══╝
   ███████╗██╔██╗ ██║██║██████╔╝█████╗  ██████╔╝███████╗██║██║  ███╗███████║   ██║   
   ╚════██║██║╚██╗██║██║██╔═══╝ ██╔══╝  ██╔══██╗╚════██║██║██║   ██║██╔══██║   ██║   
   ███████║██║ ╚████║██║██║     ███████╗██║  ██║███████║██║╚██████╔╝██║  ██║   ██║   
   ╚══════╝╚═╝  ╚═══╝╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝{Colors.END}

{Colors.YELLOW}                    DEEP CONFLUENCE ANALYSIS TOOL v1.0{Colors.END}
{Colors.CYAN}{'━' * 90}{Colors.END}

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Mode: {args.mode}
""")
    
    default_symbols = [
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
        "ADA/USDT", "DOGE/USDT", "MATIC/USDT", "DOT/USDT", "AVAX/USDT"
    ]
    
    modes_to_analyze = ["strike", "surgical", "stealth", "overwatch"] if args.all_modes else [args.mode]
    symbols = default_symbols if args.all_symbols else ([args.symbol] if args.symbol else default_symbols[:5])
    
    all_mode_analyses = {}
    
    for mode in modes_to_analyze:
        print_header(f"ANALYZING MODE: {mode.upper()}")
        
        analyses, mode_analysis = await run_full_analysis(symbols, mode, args.verbose, args.deep)
        all_mode_analyses[mode] = (analyses, mode_analysis)
        
        # Print individual symbol analyses
        if args.deep or len(symbols) <= 3:
            for a in analyses:
                print_symbol_analysis(a, deep=args.deep)
        
        # Print mode summary
        print_mode_summary(mode_analysis)
        
        # Deep dives if requested
        if args.analyze_structure:
            print_section("STRUCTURAL BREAK DEEP DIVE")
            for a in analyses[:3]:  # Top 3
                struct_analysis = analyze_structural_breaks_deep(a)
                print(f"\n  {a.symbol}:")
                print(f"    Total breaks: {struct_analysis['total_breaks']}")
                print(f"    BOS: {struct_analysis['bos_count']}  CHoCH: {struct_analysis['choch_count']}")
                for issue in struct_analysis['issues']:
                    print(f"    {Colors.YELLOW}⚠ {issue}{Colors.END}")
        
        if args.analyze_gates:
            print_section("HTF GATE DEEP DIVE")
            for a in analyses[:3]:  # Top 3
                gate_analysis = analyze_htf_gates_deep(a)
                print(f"\n  {a.symbol}:")
                print(f"    Gates: {gate_analysis['gates_passed']}/{gate_analysis['gates_analyzed']} passed")
                for reason in gate_analysis['blocking_reasons']:
                    print(f"    {Colors.RED}✗ {reason}{Colors.END}")
                for rec in gate_analysis['recommendations']:
                    print(f"    {Colors.CYAN}→ {rec}{Colors.END}")
        
        # Generate recommendations
        recommendations = generate_recommendations(analyses, mode)
        if recommendations:
            print_section("RECOMMENDATIONS")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")
    
    # Cross-mode comparison
    if args.all_modes:
        print_header("CROSS-MODE COMPARISON")
        
        print(f"\n  {'Mode':<12} {'Pass Rate':<12} {'Avg Score':<12} {'Weakest Factor':<25}")
        print(f"  {'-'*12} {'-'*12} {'-'*12} {'-'*25}")
        
        for mode, (analyses, mode_analysis) in all_mode_analyses.items():
            pass_rate = mode_analysis.symbols_passed / mode_analysis.symbols_analyzed * 100
            weakest = mode_analysis.weakest_factors[0][0] if mode_analysis.weakest_factors else "N/A"
            print(f"  {mode:<12} {pass_rate:>10.1f}% {mode_analysis.avg_score:>10.1f}% {weakest:<25}")
        
        # Best mode recommendation
        best_mode = max(all_mode_analyses.items(), key=lambda x: x[1][1].symbols_passed)
        print(f"\n  {Colors.GREEN}Best Performing Mode: {best_mode[0].upper()}{Colors.END}")


if __name__ == "__main__":
    asyncio.run(main())
