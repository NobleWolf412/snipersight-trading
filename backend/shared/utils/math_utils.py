"""
Math and Precision Utilities for Trading.
"""
import math

def round_to_tick(price: float, tick_size: float) -> float:
    """
    Round a price to the nearest exchange tick size.
    Formula: rounded_price = round(price / tick_size) * tick_size
    
    Args:
        price: Raw price to round
        tick_size: Exchange tick size (e.g., 0.01)
        
    Returns:
        Rounded price aligned with exchange requirements
    """
    if not tick_size or tick_size <= 0:
        return price
        
    # Standard price rounding to tick size
    return round(price / tick_size) * tick_size

def round_to_lot(quantity: float, lot_size: float) -> float:
    """
    Round a quantity to the nearest lot size (step size).
    Uses floor to avoid rounding UP into insufficient margin.
    
    Args:
        quantity: Raw quantity to round
        lot_size: Exchange lot size / step size (e.g., 0.001)
        
    Returns:
        Rounded quantity aligned with exchange requirements
    """
    if not lot_size or lot_size <= 0:
        return quantity
        
    # Use floor for quantities to stay safe within margin
    return math.floor(quantity / lot_size) * lot_size
