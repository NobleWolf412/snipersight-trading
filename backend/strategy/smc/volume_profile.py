"""
Volume Profile Analysis Module

Institutional-grade volume analysis for confluence scoring.
Implements Volume-at-Price (VAP), high volume nodes (HVN),
low volume nodes (LVN), and Point of Control (POC).

Volume profile identifies price levels where significant volume
has traded, indicating:
- Support/resistance zones (HVN)
- Weak areas prone to breakouts (LVN)
- Fair value area (POC)

Addresses professional review feedback:
"Volume profile: Institutionals care about volume-at-price.
Knowing if you're buying into a high-volume node (HVN) or
low-volume node (LVN) matters."
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from loguru import logger


@dataclass
class VolumeNode:
    """
    Volume concentration at specific price level.
    
    Attributes:
        price_level: Price level
        volume: Total volume at this level
        volume_pct: Percentage of total volume
        node_type: 'HVN' (high), 'LVN' (low), or 'POC' (point of control)
    """
    price_level: float
    volume: float
    volume_pct: float
    node_type: str
    
    def __repr__(self):
        return f"VolumeNode({self.node_type} @ {self.price_level:.2f}, {self.volume_pct:.1f}%)"


@dataclass
class VolumeProfile:
    """
    Complete volume profile analysis.
    
    Attributes:
        poc: Point of Control (highest volume level)
        value_area_high: Upper bound of value area (70% volume)
        value_area_low: Lower bound of value area
        high_volume_nodes: List of HVN levels
        low_volume_nodes: List of LVN levels
        total_volume: Total volume analyzed
        price_range: (low, high) price range
    """
    poc: VolumeNode
    value_area_high: float
    value_area_low: float
    high_volume_nodes: List[VolumeNode]
    low_volume_nodes: List[VolumeNode]
    total_volume: float
    price_range: Tuple[float, float]
    
    def get_node_at_price(self, price: float, tolerance: float = 0.01) -> Optional[VolumeNode]:
        """
        Find volume node near given price.
        
        Args:
            price: Price to check
            tolerance: Price tolerance (% of price range)
            
        Returns:
            VolumeNode if found within tolerance, None otherwise
        """
        price_range_size = self.price_range[1] - self.price_range[0]
        tolerance_absolute = price_range_size * tolerance
        
        # Check POC first
        if abs(price - self.poc.price_level) <= tolerance_absolute:
            return self.poc
        
        # Check HVNs
        for node in self.high_volume_nodes:
            if abs(price - node.price_level) <= tolerance_absolute:
                return node
        
        # Check LVNs
        for node in self.low_volume_nodes:
            if abs(price - node.price_level) <= tolerance_absolute:
                return node
        
        return None
    
    def is_in_value_area(self, price: float) -> bool:
        """Check if price is within value area."""
        return self.value_area_low <= price <= self.value_area_high


def calculate_volume_profile(
    df: pd.DataFrame,
    num_bins: int = 50,
    hvn_threshold_pct: float = 75.0,
    lvn_threshold_pct: float = 25.0
) -> VolumeProfile:
    """
    Calculate volume profile from OHLCV data.
    
    Process:
    1. Divide price range into bins
    2. Accumulate volume for each price bin
    3. Identify POC (highest volume bin)
    4. Calculate value area (70% of volume around POC)
    5. Identify HVNs and LVNs
    
    Args:
        df: DataFrame with 'high', 'low', 'close', 'volume' columns
        num_bins: Number of price bins
        hvn_threshold_pct: Volume percentile for HVN classification
        lvn_threshold_pct: Volume percentile for LVN classification
        
    Returns:
        VolumeProfile with complete analysis
        
    Raises:
        ValueError: If required columns missing or insufficient data
    """
    required_cols = ['high', 'low', 'close', 'volume']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    if len(df) < 10:
        raise ValueError(f"Insufficient data for volume profile: {len(df)} rows")
    
    # Define price range
    price_low = df['low'].min()
    price_high = df['high'].max()
    price_range = (price_low, price_high)
    
    if price_low >= price_high:
        raise ValueError(f"Invalid price range: {price_low} to {price_high}")
    
    # Create price bins
    bin_edges = np.linspace(price_low, price_high, num_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    # Accumulate volume in each bin
    volume_by_bin = np.zeros(num_bins)
    
    for idx, row in df.iterrows():
        # Distribute volume across bins touched by candle range
        candle_low = row['low']
        candle_high = row['high']
        candle_volume = row['volume']
        
        # Find bins this candle touches
        bins_touched = []
        for i in range(num_bins):
            bin_low = bin_edges[i]
            bin_high = bin_edges[i + 1]
            
            # Check if candle overlaps with bin
            if not (candle_high < bin_low or candle_low > bin_high):
                bins_touched.append(i)
        
        if bins_touched:
            # Distribute volume equally across touched bins
            volume_per_bin = candle_volume / len(bins_touched)
            for bin_idx in bins_touched:
                volume_by_bin[bin_idx] += volume_per_bin
    
    total_volume = volume_by_bin.sum()
    
    if total_volume == 0:
        raise ValueError("Total volume is zero - cannot calculate profile")
    
    # Calculate volume percentages
    volume_pct = (volume_by_bin / total_volume) * 100
    
    # --- Find Point of Control (POC) ---
    poc_idx = volume_by_bin.argmax()
    poc = VolumeNode(
        price_level=bin_centers[poc_idx],
        volume=volume_by_bin[poc_idx],
        volume_pct=volume_pct[poc_idx],
        node_type='POC'
    )
    
    # --- Calculate Value Area (70% of volume) ---
    value_area_volume_target = total_volume * 0.70
    
    # Start from POC and expand both directions
    value_area_indices = {poc_idx}
    current_volume = volume_by_bin[poc_idx]
    
    expand_up = poc_idx + 1
    expand_down = poc_idx - 1
    
    while current_volume < value_area_volume_target:
        # Determine which direction has more volume
        up_volume = volume_by_bin[expand_up] if expand_up < num_bins else 0
        down_volume = volume_by_bin[expand_down] if expand_down >= 0 else 0
        
        if up_volume == 0 and down_volume == 0:
            break  # No more volume to add
        
        # Expand in direction with more volume
        if up_volume >= down_volume and expand_up < num_bins:
            value_area_indices.add(expand_up)
            current_volume += up_volume
            expand_up += 1
        elif expand_down >= 0:
            value_area_indices.add(expand_down)
            current_volume += down_volume
            expand_down -= 1
        else:
            break
    
    # Get value area bounds
    value_area_bins = sorted(value_area_indices)
    value_area_low = bin_edges[value_area_bins[0]]
    value_area_high = bin_edges[value_area_bins[-1] + 1]
    
    # --- Identify HVNs and LVNs ---
    hvn_volume_threshold = np.percentile(volume_by_bin[volume_by_bin > 0], hvn_threshold_pct)
    lvn_volume_threshold = np.percentile(volume_by_bin[volume_by_bin > 0], lvn_threshold_pct)
    
    high_volume_nodes = []
    low_volume_nodes = []
    
    for i in range(num_bins):
        if volume_by_bin[i] == 0:
            continue
        
        if i == poc_idx:
            continue  # POC already identified
        
        if volume_by_bin[i] >= hvn_volume_threshold:
            node = VolumeNode(
                price_level=bin_centers[i],
                volume=volume_by_bin[i],
                volume_pct=volume_pct[i],
                node_type='HVN'
            )
            high_volume_nodes.append(node)
        
        elif volume_by_bin[i] <= lvn_volume_threshold:
            node = VolumeNode(
                price_level=bin_centers[i],
                volume=volume_by_bin[i],
                volume_pct=volume_pct[i],
                node_type='LVN'
            )
            low_volume_nodes.append(node)
    
    # Sort nodes by price
    high_volume_nodes.sort(key=lambda n: n.price_level)
    low_volume_nodes.sort(key=lambda n: n.price_level)
    
    profile = VolumeProfile(
        poc=poc,
        value_area_high=value_area_high,
        value_area_low=value_area_low,
        high_volume_nodes=high_volume_nodes,
        low_volume_nodes=low_volume_nodes,
        total_volume=total_volume,
        price_range=price_range
    )
    
    logger.info(
        f"Volume Profile: POC @ {poc.price_level:.2f} ({poc.volume_pct:.1f}%), "
        f"VA: {value_area_low:.2f}-{value_area_high:.2f}, "
        f"{len(high_volume_nodes)} HVNs, {len(low_volume_nodes)} LVNs"
    )
    
    return profile


def analyze_entry_volume_context(
    entry_price: float,
    volume_profile: VolumeProfile,
    direction: str
) -> Dict:
    """
    Analyze volume context at entry price.
    
    Determines if entry is at favorable volume level:
    - Buying near LVN (low resistance) = favorable for longs
    - Buying near HVN (support) = favorable for longs
    - Selling near LVN (low support) = favorable for shorts
    - Selling near HVN (resistance) = favorable for shorts
    
    Args:
        entry_price: Proposed entry price
        volume_profile: VolumeProfile analysis
        direction: 'bullish' or 'bearish'
        
    Returns:
        Dict with volume context analysis
    """
    # Find nearest node
    node = volume_profile.get_node_at_price(entry_price, tolerance=0.02)
    
    # Check if in value area
    in_value_area = volume_profile.is_in_value_area(entry_price)
    
    # Calculate distance to POC
    poc_distance = abs(entry_price - volume_profile.poc.price_level)
    poc_distance_pct = (poc_distance / entry_price) * 100
    
    # Determine favorability
    favorability_score = 50.0  # Neutral baseline
    rationale_parts = []
    
    if node:
        if node.node_type == 'POC':
            rationale_parts.append(f"Entry at POC ({node.price_level:.2f})")
            if direction == 'bullish':
                favorability_score = 70.0  # POC often acts as support
                rationale_parts.append("POC provides volume support for longs")
            else:
                favorability_score = 70.0  # POC acts as resistance
                rationale_parts.append("POC provides volume resistance for shorts")
        
        elif node.node_type == 'HVN':
            rationale_parts.append(f"Entry at HVN ({node.price_level:.2f}, {node.volume_pct:.1f}%)")
            if direction == 'bullish':
                if entry_price < volume_profile.poc.price_level:
                    favorability_score = 80.0  # Buying at support below POC
                    rationale_parts.append("HVN below POC = strong support for longs")
                else:
                    favorability_score = 60.0  # Buying above POC
                    rationale_parts.append("HVN above POC = potential resistance")
            else:  # bearish
                if entry_price > volume_profile.poc.price_level:
                    favorability_score = 80.0  # Selling at resistance above POC
                    rationale_parts.append("HVN above POC = strong resistance for shorts")
                else:
                    favorability_score = 60.0  # Selling below POC
                    rationale_parts.append("HVN below POC = potential support")
        
        elif node.node_type == 'LVN':
            rationale_parts.append(f"Entry at LVN ({node.price_level:.2f}, {node.volume_pct:.1f}%)")
            if direction == 'bullish':
                if entry_price > volume_profile.poc.price_level:
                    favorability_score = 75.0  # Buying through LVN above POC
                    rationale_parts.append("LVN above POC = low resistance for upside breakout")
                else:
                    favorability_score = 40.0  # Buying at LVN below POC
                    rationale_parts.append("LVN below POC = weak support, risky")
            else:  # bearish
                if entry_price < volume_profile.poc.price_level:
                    favorability_score = 75.0  # Selling through LVN below POC
                    rationale_parts.append("LVN below POC = low support for downside breakout")
                else:
                    favorability_score = 40.0  # Selling at LVN above POC
                    rationale_parts.append("LVN above POC = weak resistance, risky")
    else:
        rationale_parts.append(f"No significant volume node at entry ({entry_price:.2f})")
        
        if in_value_area:
            favorability_score = 60.0
            rationale_parts.append("Entry within value area (fair value zone)")
        else:
            if entry_price < volume_profile.value_area_low:
                if direction == 'bullish':
                    favorability_score = 65.0
                    rationale_parts.append("Entry below value area - cheap for longs")
                else:
                    favorability_score = 45.0
                    rationale_parts.append("Entry below value area - risky for shorts")
            else:  # above value area
                if direction == 'bearish':
                    favorability_score = 65.0
                    rationale_parts.append("Entry above value area - expensive for shorts")
                else:
                    favorability_score = 45.0
                    rationale_parts.append("Entry above value area - risky for longs")
    
    rationale_parts.append(f"Distance to POC: {poc_distance_pct:.2f}%")
    
    return {
        'favorability_score': favorability_score,
        'nearest_node': node,
        'in_value_area': in_value_area,
        'poc_distance_pct': poc_distance_pct,
        'rationale': " | ".join(rationale_parts)
    }


def find_volume_zones(
    volume_profile: VolumeProfile,
    direction: str,
    current_price: float
) -> Dict[str, List[float]]:
    """
    Find key volume-based support/resistance zones.
    
    Args:
        volume_profile: VolumeProfile analysis
        direction: 'bullish' or 'bearish'
        current_price: Current market price
        
    Returns:
        Dict with 'support' and 'resistance' lists of price levels
    """
    support_zones = []
    resistance_zones = []
    
    if direction == 'bullish':
        # For longs: HVNs below = support, HVNs above = resistance
        support_zones.append(volume_profile.poc.price_level)  # POC is key support
        
        for node in volume_profile.high_volume_nodes:
            if node.price_level < current_price:
                support_zones.append(node.price_level)
            else:
                resistance_zones.append(node.price_level)
    
    else:  # bearish
        # For shorts: HVNs above = resistance, HVNs below = support
        resistance_zones.append(volume_profile.poc.price_level)  # POC is key resistance
        
        for node in volume_profile.high_volume_nodes:
            if node.price_level > current_price:
                resistance_zones.append(node.price_level)
            else:
                support_zones.append(node.price_level)
    
    # Sort zones
    support_zones.sort(reverse=True)  # Closest first
    resistance_zones.sort()  # Closest first
    
    return {
        'support': support_zones[:5],  # Top 5 nearest
        'resistance': resistance_zones[:5]
    }


def calculate_volume_confluence_factor(
    entry_price: float,
    volume_profile: VolumeProfile,
    direction: str
) -> Dict:
    """
    Calculate volume profile contribution to confluence score.
    
    This integrates volume analysis into the existing confluence scoring system.
    
    Args:
        entry_price: Proposed entry price
        volume_profile: VolumeProfile analysis
        direction: Trade direction
        
    Returns:
        Dict with score, weight, and rationale for confluence integration
    """
    # Analyze entry context
    context = analyze_entry_volume_context(entry_price, volume_profile, direction)
    
    # Volume profile factor weight (suggested: 0.15 in confluence scoring)
    weight = 0.15
    
    # Score is favorability score (0-100)
    score = context['favorability_score']
    
    # Build detailed rationale
    rationale_parts = [
        f"Volume Profile Analysis:",
        context['rationale']
    ]
    
    # Add value area context
    if context['in_value_area']:
        rationale_parts.append("✓ Entry within value area (70% volume zone)")
    else:
        if entry_price < volume_profile.value_area_low:
            rationale_parts.append("⚠ Entry below value area")
        else:
            rationale_parts.append("⚠ Entry above value area")
    
    rationale = "\n".join(rationale_parts)
    
    return {
        'name': 'Volume Profile',
        'score': score,
        'weight': weight,
        'rationale': rationale,
        'metadata': {
            'nearest_node': str(context['nearest_node']) if context['nearest_node'] else None,
            'in_value_area': context['in_value_area'],
            'poc_price': volume_profile.poc.price_level,
            'value_area': (volume_profile.value_area_low, volume_profile.value_area_high)
        }
    }
