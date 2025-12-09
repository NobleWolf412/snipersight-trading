"""
SMC Detection Service - Smart Money Concepts pattern detection extracted from orchestrator.py

Detects all SMC patterns across timeframes:
- Order Blocks
- Fair Value Gaps (FVGs)
- Structure Breaks (BOS/CHoCH)
- Liquidity Sweeps
- Equal Highs/Lows (Liquidity Pools)
- Swing Structure (HH/HL/LH/LL)
- Premium/Discount Zones
- Key Levels (PDH/PDL/PWH/PWL)

This service encapsulates SMC detection logic previously in
orchestrator._detect_smc_patterns()
"""

import logging
from typing import Dict, List, Any, Optional

from backend.shared.models.data import MultiTimeframeData
from backend.shared.models.smc import SMCSnapshot
from backend.shared.config.smc_config import SMCConfig

# SMC Detection functions
from backend.strategy.smc.order_blocks import detect_order_blocks
from backend.strategy.smc.fvg import detect_fvgs
from backend.strategy.smc.bos_choch import detect_structural_breaks
from backend.strategy.smc.liquidity_sweeps import detect_liquidity_sweeps, detect_equal_highs_lows
from backend.strategy.smc.swing_structure import detect_swing_structure
from backend.strategy.smc.mitigation_tracker import update_ob_mitigation

# Analysis functions
from backend.analysis.premium_discount import detect_premium_discount
from backend.analysis.key_levels import detect_key_levels

logger = logging.getLogger(__name__)


class SMCDetectionService:
    """
    Service for detecting Smart Money Concepts (SMC) patterns.
    
    Centralizes all SMC pattern detection with proper error handling
    and consistent return types.
    
    Usage:
        service = SMCDetectionService(smc_config=config)
        snapshot = service.detect(multi_tf_data, current_price)
    """
    
    def __init__(self, smc_config: Optional[SMCConfig] = None):
        """
        Initialize SMC detection service.
        
        Args:
            smc_config: SMC configuration for detection parameters
        """
        self._smc_config = smc_config or SMCConfig()
        self._diagnostics: Dict[str, list] = {'smc_rejections': []}
    
    @property
    def diagnostics(self) -> Dict[str, list]:
        """Get diagnostic information from last detection."""
        return self._diagnostics
    
    def update_config(self, config: SMCConfig):
        """Update SMC configuration dynamically."""
        self._smc_config = config
    
    def detect(
        self, 
        multi_tf_data: MultiTimeframeData, 
        current_price: float
    ) -> SMCSnapshot:
        """
        Detect Smart Money Concept patterns across all timeframes.
        
        Args:
            multi_tf_data: Multi-timeframe OHLCV data
            current_price: Current market price (for P/D and key levels)
            
        Returns:
            SMCSnapshot with all detected patterns
        """
        self._diagnostics = {'smc_rejections': []}
        
        # Aggregate patterns across timeframes
        all_order_blocks = []
        all_fvgs = []
        all_structure_breaks = []
        all_liquidity_sweeps = []
        all_equal_highs = []
        all_equal_lows = []
        all_liquidity_pools: List = []
        swing_structure_by_tf = {}
        premium_discount_by_tf = {}
        
        for timeframe, df in multi_tf_data.timeframes.items():
            if df.empty or len(df) < 20:
                continue
            
            try:
                # Detect core SMC patterns
                patterns = self._detect_timeframe_patterns(timeframe, df, current_price)
                
                all_order_blocks.extend(patterns['order_blocks'])
                all_fvgs.extend(patterns['fvgs'])
                all_structure_breaks.extend(patterns['structure_breaks'])
                all_liquidity_sweeps.extend(patterns['liquidity_sweeps'])
                all_equal_highs.extend(patterns['equal_highs'])
                all_equal_lows.extend(patterns['equal_lows'])
                all_liquidity_pools.extend(patterns['liquidity_pools'])
                
                if patterns['swing_structure']:
                    swing_structure_by_tf[timeframe] = patterns['swing_structure']
                if patterns['premium_discount']:
                    premium_discount_by_tf[timeframe] = patterns['premium_discount']
                
                # Log SMC detections per timeframe
                logger.info("🎯 %s SMC: OB=%d | FVG=%d | BOS/CHoCH=%d | Sweeps=%d",
                           timeframe,
                           len(patterns['order_blocks']),
                           len(patterns['fvgs']),
                           len(patterns['structure_breaks']),
                           len(patterns['liquidity_sweeps']))
                
            except Exception as e:
                logger.warning("SMC detection failed for %s: %s", timeframe, e)
                self._diagnostics['smc_rejections'].append({
                    'timeframe': timeframe, 
                    'error': str(e)
                })
                continue
        
        # Deduplicate equal highs/lows
        unique_equal_highs = list(set(all_equal_highs))
        unique_equal_lows = list(set(all_equal_lows))
        
        if unique_equal_highs or unique_equal_lows:
            logger.info("💧 Liquidity pools: %d equal highs, %d equal lows",
                       len(unique_equal_highs), len(unique_equal_lows))
        
        # Log liquidity pools summary
        self._log_liquidity_pools_summary(all_liquidity_pools)
        
        # Log HTF swing structure summary
        self._log_swing_structure_summary(swing_structure_by_tf)
        
        # Detect key levels (PDH/PDL/PWH/PWL)
        key_levels_data = self._detect_key_levels(multi_tf_data, current_price)
        
        # Update OB mitigation
        all_order_blocks = self._update_mitigation(multi_tf_data, all_order_blocks)
        
        return SMCSnapshot(
            order_blocks=all_order_blocks,
            fvgs=all_fvgs,
            structural_breaks=all_structure_breaks,
            liquidity_sweeps=all_liquidity_sweeps,
            equal_highs=unique_equal_highs,
            equal_lows=unique_equal_lows,
            liquidity_pools=all_liquidity_pools,
            swing_structure=swing_structure_by_tf,
            premium_discount=premium_discount_by_tf,
            key_levels=key_levels_data
        )
    
    def _detect_timeframe_patterns(
        self, 
        timeframe: str, 
        df, 
        current_price: float
    ) -> Dict[str, Any]:
        """Detect all SMC patterns for a single timeframe."""
        result = {
            'order_blocks': [],
            'fvgs': [],
            'structure_breaks': [],
            'liquidity_sweeps': [],
            'equal_highs': [],
            'equal_lows': [],
            'liquidity_pools': [],
            'swing_structure': None,
            'premium_discount': None,
        }
        
        # Order blocks
        result['order_blocks'] = detect_order_blocks(df, self._smc_config)
        
        # Fair value gaps
        result['fvgs'] = detect_fvgs(df, self._smc_config)
        
        # Structure breaks
        result['structure_breaks'] = detect_structural_breaks(df, self._smc_config)
        
        # Liquidity sweeps
        result['liquidity_sweeps'] = detect_liquidity_sweeps(df, self._smc_config)
        
        # Equal highs/lows (liquidity pools)
        self._detect_equal_highs_lows(timeframe, df, result)
        
        # Swing structure (for HTF bias)
        if timeframe.lower() in ('1w', '1d', '4h'):
            self._detect_swing_structure(timeframe, df, result)
        
        # Premium/Discount zones
        self._detect_premium_discount(timeframe, df, current_price, result)
        
        return result
    
    def _detect_equal_highs_lows(self, timeframe: str, df, result: Dict):
        """Detect equal highs/lows with structured liquidity pools."""
        try:
            ehl = detect_equal_highs_lows(
                df, 
                config=self._smc_config,
                timeframe=timeframe
            )
            result['equal_highs'] = ehl.get('equal_highs', [])
            result['equal_lows'] = ehl.get('equal_lows', [])
            pools = ehl.get('pools', [])
            result['liquidity_pools'] = pools
            
            if pools:
                logger.debug("💧 %s: %d liquidity pools (tol=%.4f%%, min_touches=%d)",
                           timeframe,
                           len(pools),
                           ehl.get('metadata', {}).get('tolerance_used', 0) * 100,
                           ehl.get('metadata', {}).get('min_touches', 2))
        except Exception:
            pass  # Non-critical, continue without
    
    def _detect_swing_structure(self, timeframe: str, df, result: Dict):
        """Detect swing structure (HH/HL/LH/LL) for HTF bias."""
        try:
            swing_struct = detect_swing_structure(
                df, 
                lookback=getattr(self._smc_config, 'structure_swing_lookback', 15)
            )
            result['swing_structure'] = swing_struct.to_dict()
            logger.debug("📊 %s Swing structure: trend=%s, last_HH=%s, last_HL=%s",
                       timeframe, swing_struct.trend,
                       f"{swing_struct.last_hh.price:.4f}" if swing_struct.last_hh else "N/A",
                       f"{swing_struct.last_hl.price:.4f}" if swing_struct.last_hl else "N/A")
        except Exception as e:
            logger.debug("Swing structure detection failed for %s: %s", timeframe, e)
    
    def _detect_premium_discount(self, timeframe: str, df, current_price: float, result: Dict):
        """Detect premium/discount zones."""
        try:
            pd_zone = detect_premium_discount(df, lookback=50, current_price=current_price)
            result['premium_discount'] = pd_zone.to_dict()
            logger.debug("📊 %s P/D Zone: %s (%.1f%%)", 
                       timeframe, pd_zone.current_zone, pd_zone.zone_percentage or 50)
        except Exception as e:
            logger.debug("Premium/Discount detection failed for %s: %s", timeframe, e)
    
    def _detect_key_levels(self, multi_tf_data: MultiTimeframeData, current_price: float) -> Optional[Dict]:
        """Detect key levels (PDH/PDL/PWH/PWL)."""
        try:
            df_daily = multi_tf_data.timeframes.get('1D') or multi_tf_data.timeframes.get('1d')
            df_weekly = multi_tf_data.timeframes.get('1W') or multi_tf_data.timeframes.get('1w')
            if df_daily is not None and len(df_daily) >= 2:
                key_levels = detect_key_levels(df_daily, df_weekly, current_price)
                logger.info("🔑 Key Levels: PDH=%.4f PDL=%.4f PWH=%s PWL=%s",
                           key_levels.pdh.price if key_levels.pdh else 0,
                           key_levels.pdl.price if key_levels.pdl else 0,
                           f"{key_levels.pwh.price:.4f}" if key_levels.pwh else "N/A",
                           f"{key_levels.pwl.price:.4f}" if key_levels.pwl else "N/A")
                return key_levels.to_dict()
        except Exception as e:
            logger.debug("Key levels detection failed: %s", e)
        return None
    
    def _update_mitigation(self, multi_tf_data: MultiTimeframeData, order_blocks: List) -> List:
        """Update order block mitigation status."""
        if not order_blocks:
            return order_blocks
        
        try:
            ltf_df = (multi_tf_data.timeframes.get('15m') or 
                     multi_tf_data.timeframes.get('1H') or
                     multi_tf_data.timeframes.get('1h'))
            if ltf_df is not None and len(ltf_df) > 0:
                order_blocks, mitigation_status = update_ob_mitigation(
                    order_blocks, ltf_df, max_mitigation=0.5
                )
                if mitigation_status.fully_mitigated_count > 0:
                    logger.info("🔄 OB Mitigation: %d fully mitigated, %d partial, %d fresh",
                               mitigation_status.fully_mitigated_count,
                               mitigation_status.partially_mitigated_count,
                               mitigation_status.fresh_count)
        except Exception as e:
            logger.debug("Mitigation tracking failed: %s", e)
        
        return order_blocks
    
    def _log_liquidity_pools_summary(self, pools: List):
        """Log summary of graded liquidity pools."""
        if not pools:
            return
        grade_a = sum(1 for p in pools if p.grade == 'A')
        grade_b = sum(1 for p in pools if p.grade == 'B')
        grade_c = sum(1 for p in pools if p.grade == 'C')
        logger.info("🎯 Liquidity pools graded: A=%d B=%d C=%d (total=%d)",
                   grade_a, grade_b, grade_c, len(pools))
    
    def _log_swing_structure_summary(self, swing_structure_by_tf: Dict):
        """Log HTF swing structure summary."""
        for tf, ss in swing_structure_by_tf.items():
            logger.info("📈 %s Structure: %s trend", tf, ss.get('trend', 'unknown'))


# Singleton
_smc_service: Optional[SMCDetectionService] = None


def get_smc_service() -> Optional[SMCDetectionService]:
    """Get the singleton SMCDetectionService instance."""
    return _smc_service


def configure_smc_service(smc_config: Optional[SMCConfig] = None) -> SMCDetectionService:
    """Configure and return the singleton SMCDetectionService."""
    global _smc_service
    _smc_service = SMCDetectionService(smc_config=smc_config)
    return _smc_service
