"""
HTF Level Detection Service

Identifies major support/resistance levels on higher timeframes (4H/1D/1W)
and detects when price approaches these levels for swing trade opportunities.
"""

from dataclasses import dataclass
from typing import List, Optional, Literal
from datetime import datetime, timedelta
import numpy as np


@dataclass
class HTFLevel:
    """Represents a significant support/resistance level."""
    price: float
    level_type: Literal['support', 'resistance']
    timeframe: str
    strength: float  # 0-100 score based on touches, age, volume
    touches: int
    first_seen: datetime
    last_touch: datetime
    proximity_pct: float  # Distance from current price (%)


@dataclass
class LevelOpportunity:
    """Detected swing opportunity at HTF level."""
    symbol: str
    level: HTFLevel
    current_price: float
    recommended_mode: str  # 'overwatch', 'surgical', 'recon'
    rationale: str
    confluence_factors: List[str]
    expected_move_pct: float  # Estimated % move if level holds
    confidence: float  # 0-100


class HTFLevelDetector:
    """Detects major support/resistance levels on higher timeframes."""
    
    def __init__(self, proximity_threshold: float = 2.0):
        """
        Args:
            proximity_threshold: % distance from level to consider "approaching" (default 2%)
        """
        self.proximity_threshold = proximity_threshold
    
    def detect_levels(
        self, 
        symbol: str,
        ohlcv_data: dict,  # {timeframe: DataFrame}
        current_price: float
    ) -> List[HTFLevel]:
        """
        Identify major support/resistance levels from HTF candles.
        
        Args:
            symbol: Trading pair
            ohlcv_data: Dict of timeframe -> OHLCV DataFrame
            current_price: Current market price
            
        Returns:
            List of detected HTF levels sorted by strength
        """
        levels = []
        
        # Analyze 4H, 1D, 1W timeframes
        for tf in ['4h', '1d', '1w']:
            if tf not in ohlcv_data:
                continue
            
            df = ohlcv_data[tf]
            if df.empty:
                continue
            
            # Find swing highs/lows (local extrema)
            swing_highs = self._find_swing_highs(df, window=5)
            swing_lows = self._find_swing_lows(df, window=5)
            
            # Cluster nearby levels (within 0.5% = same level)
            high_clusters = self._cluster_levels(swing_highs, tolerance_pct=0.5)
            low_clusters = self._cluster_levels(swing_lows, tolerance_pct=0.5)
            
            # Score and filter significant levels
            for price, touches_info in high_clusters.items():
                strength = self._score_level(
                    price=price,
                    touches=touches_info['count'],
                    first_seen=touches_info['first'],
                    last_touch=touches_info['last'],
                    volume_profile=touches_info.get('volume', []),
                    timeframe=tf
                )
                
                # Only keep strong levels (>50 score)
                if strength > 50:
                    proximity = abs((current_price - price) / price) * 100
                    levels.append(HTFLevel(
                        price=price,
                        level_type='resistance',
                        timeframe=tf,
                        strength=strength,
                        touches=touches_info['count'],
                        first_seen=touches_info['first'],
                        last_touch=touches_info['last'],
                        proximity_pct=proximity
                    ))
            
            for price, touches_info in low_clusters.items():
                strength = self._score_level(
                    price=price,
                    touches=touches_info['count'],
                    first_seen=touches_info['first'],
                    last_touch=touches_info['last'],
                    volume_profile=touches_info.get('volume', []),
                    timeframe=tf
                )
                
                if strength > 50:
                    proximity = abs((current_price - price) / price) * 100
                    levels.append(HTFLevel(
                        price=price,
                        level_type='support',
                        timeframe=tf,
                        strength=strength,
                        touches=touches_info['count'],
                        first_seen=touches_info['first'],
                        last_touch=touches_info['last'],
                        proximity_pct=proximity
                    ))
        
        # Sort by strength descending
        levels.sort(key=lambda x: x.strength, reverse=True)
        return levels
    
    def find_opportunities(
        self,
        symbol: str,
        levels: List[HTFLevel],
        current_price: float,
        smc_context: dict,  # OBs, FVGs, BOS/CHoCH from scanner
        regime: Optional[dict] = None
    ) -> List[LevelOpportunity]:
        """
        Identify swing trade opportunities when price approaches HTF levels.
        
        Args:
            symbol: Trading pair
            levels: Detected HTF levels
            current_price: Current price
            smc_context: SMC structures (order blocks, FVGs, etc.)
            regime: Market regime data
            
        Returns:
            List of tactical opportunities with mode recommendations
        """
        opportunities = []
        
        for level in levels:
            # Check if price is approaching this level
            if level.proximity_pct > self.proximity_threshold:
                continue
            
            # Build confluence factors
            confluence = []
            expected_move = 0.0
            
            # 1. Level type + price position
            if level.level_type == 'support' and current_price > level.price:
                confluence.append(f"Price approaching {level.timeframe} support at ${level.price:.5f}")
                expected_move = 2.0  # Base 2% bounce expectation
            elif level.level_type == 'resistance' and current_price < level.price:
                confluence.append(f"Price approaching {level.timeframe} resistance at ${level.price:.5f}")
                expected_move = 2.0
            else:
                continue  # Wrong side of level
            
            # 2. Level strength
            if level.strength >= 80:
                confluence.append(f"Very strong level ({level.touches} touches)")
                expected_move += 1.0
            elif level.strength >= 65:
                confluence.append(f"Strong level ({level.touches} touches)")
                expected_move += 0.5
            
            # 3. SMC alignment
            ob_aligned = self._check_ob_alignment(level, smc_context.get('order_blocks', []))
            if ob_aligned:
                confluence.append(f"{level.level_type.capitalize()} OB present near level")
                expected_move += 0.5
            
            fvg_aligned = self._check_fvg_alignment(level, smc_context.get('fvgs', []))
            if fvg_aligned:
                confluence.append(f"FVG gap coincides with {level.level_type}")
                expected_move += 0.5
            
            # 4. Structural breaks
            if smc_context.get('bos_choch'):
                confluence.append("Recent BOS/CHoCH supports directional bias")
                expected_move += 0.5
            
            # 5. Regime fit
            regime_boost = 0
            if regime:
                composite = regime.get('composite', '').upper()
                if composite in ['ALTSEASON', 'BTC_DRIVE'] and level.level_type == 'support':
                    confluence.append("Risk-on regime favors support bounces")
                    regime_boost = 10
                elif composite in ['DEFENSIVE', 'PANIC'] and level.level_type == 'resistance':
                    confluence.append("Risk-off regime favors resistance rejections")
                    regime_boost = 10
            
            # Calculate confidence score
            base_confidence = level.strength
            confluence_bonus = len(confluence) * 5
            confidence = min(95, base_confidence + confluence_bonus + regime_boost)
            
            # Recommend mode based on timeframe and confluence
            if level.timeframe in ['1w', '1d'] and len(confluence) >= 4:
                recommended_mode = 'overwatch'  # Big swing potential
                rationale = "Weekly/Daily level with high confluence - major swing setup"
            elif level.timeframe == '4h' and len(confluence) >= 3:
                recommended_mode = 'surgical'  # Precision 4H setup
                rationale = "4H level with solid confluence - precision swing entry"
            elif len(confluence) >= 2:
                recommended_mode = 'recon'  # Moderate setup
                rationale = f"{level.timeframe.upper()} level - balanced approach recommended"
            else:
                continue  # Not enough confluence
            
            opportunities.append(LevelOpportunity(
                symbol=symbol,
                level=level,
                current_price=current_price,
                recommended_mode=recommended_mode,
                rationale=rationale,
                confluence_factors=confluence,
                expected_move_pct=expected_move,
                confidence=confidence
            ))
        
        # Sort by confidence descending
        opportunities.sort(key=lambda x: x.confidence, reverse=True)
        return opportunities
    
    def _find_swing_highs(self, df, window: int = 5) -> List[tuple]:
        """Find local maxima (swing highs)."""
        highs = []
        for i in range(window, len(df) - window):
            is_swing = True
            current = df.iloc[i]['high']
            
            # Check if current high is highest in window
            for j in range(i - window, i + window + 1):
                if j != i and df.iloc[j]['high'] >= current:
                    is_swing = False
                    break
            
            if is_swing:
                highs.append((df.iloc[i]['timestamp'], current, df.iloc[i].get('volume', 0)))
        
        return highs
    
    def _find_swing_lows(self, df, window: int = 5) -> List[tuple]:
        """Find local minima (swing lows)."""
        lows = []
        for i in range(window, len(df) - window):
            is_swing = True
            current = df.iloc[i]['low']
            
            # Check if current low is lowest in window
            for j in range(i - window, i + window + 1):
                if j != i and df.iloc[j]['low'] <= current:
                    is_swing = False
                    break
            
            if is_swing:
                lows.append((df.iloc[i]['timestamp'], current, df.iloc[i].get('volume', 0)))
        
        return lows
    
    def _cluster_levels(self, swing_points: List[tuple], tolerance_pct: float = 0.5) -> dict:
        """Group nearby swing points into level clusters."""
        if not swing_points:
            return {}
        
        clusters = {}
        
        for timestamp, price, volume in swing_points:
            # Find if price belongs to existing cluster
            matched = False
            for cluster_price in list(clusters.keys()):
                if abs((price - cluster_price) / cluster_price) * 100 <= tolerance_pct:
                    # Add to existing cluster
                    clusters[cluster_price]['count'] += 1
                    clusters[cluster_price]['last'] = max(clusters[cluster_price]['last'], timestamp)
                    clusters[cluster_price]['volume'].append(volume)
                    matched = True
                    break
            
            if not matched:
                # Create new cluster
                clusters[price] = {
                    'count': 1,
                    'first': timestamp,
                    'last': timestamp,
                    'volume': [volume]
                }
        
        return clusters
    
    def _score_level(
        self,
        price: float,
        touches: int,
        first_seen: datetime,
        last_touch: datetime,
        volume_profile: List[float],
        timeframe: str
    ) -> float:
        """
        Score level strength (0-100).
        
        Factors:
        - Number of touches (more = stronger)
        - Age (older = more established)
        - Recency of last touch (recent = more relevant)
        - Volume at touches (higher = more significant)
        - Timeframe weight (1W > 1D > 4H)
        """
        score = 0.0
        
        # Touch count (max 40 points)
        score += min(40, touches * 10)
        
        # Age (max 20 points) - levels >30 days old are established
        age_days = (datetime.now() - first_seen).days
        score += min(20, (age_days / 30) * 20)
        
        # Recency (max 20 points) - last touch within 7 days is relevant
        recency_days = (datetime.now() - last_touch).days
        if recency_days <= 7:
            score += 20
        elif recency_days <= 14:
            score += 15
        elif recency_days <= 30:
            score += 10
        
        # Volume strength (max 10 points)
        if volume_profile:
            avg_vol = np.mean(volume_profile)
            if avg_vol > 0:
                score += min(10, (avg_vol / 1000000) * 10)  # Normalize
        
        # Timeframe weight (max 10 points)
        tf_weights = {'1w': 10, '1d': 7, '4h': 5}
        score += tf_weights.get(timeframe, 0)
        
        return min(100, score)
    
    def _check_ob_alignment(self, level: HTFLevel, order_blocks: List[dict]) -> bool:
        """Check if order blocks align with this level."""
        for ob in order_blocks:
            ob_price = ob.get('price', 0)
            if abs((ob_price - level.price) / level.price) * 100 <= 1.0:
                # OB within 1% of level
                if (level.level_type == 'support' and ob.get('type') == 'bullish') or \
                   (level.level_type == 'resistance' and ob.get('type') == 'bearish'):
                    return True
        return False
    
    def _check_fvg_alignment(self, level: HTFLevel, fvgs: List[dict]) -> bool:
        """Check if FVGs align with this level."""
        for fvg in fvgs:
            fvg_mid = (fvg.get('low', 0) + fvg.get('high', 0)) / 2
            if abs((fvg_mid - level.price) / level.price) * 100 <= 1.5:
                return True
        return False
