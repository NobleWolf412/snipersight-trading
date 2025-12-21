"""
HTF Opportunities API Endpoint

Detects major swing setups at higher timeframe levels and recommends mode switches.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

from backend.analysis.htf_levels import HTFLevelDetector, LevelOpportunity, HTFLevel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/htf", tags=["HTF Opportunities"])


class HTFLevelResponse(BaseModel):
    """HTF level data for API."""
    price: float
    level_type: str
    timeframe: str
    strength: float
    touches: int
    proximity_pct: float


class OpportunityResponse(BaseModel):
    """Swing opportunity recommendation."""
    symbol: str
    level: HTFLevelResponse
    current_price: float
    recommended_mode: str
    rationale: str
    confluence_factors: List[str]
    expected_move_pct: float
    confidence: float


class HTFOpportunitiesResponse(BaseModel):
    """Response containing detected opportunities."""
    opportunities: List[OpportunityResponse]
    total: int
    timestamp: str


# Default symbols to scan if none provided
DEFAULT_HTF_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
HTF_TIMEFRAMES = ["4h", "1d"]


@router.get("/opportunities", response_model=HTFOpportunitiesResponse)
async def get_htf_opportunities(
    symbols: Optional[str] = None,  # Comma-separated list
    min_confidence: float = 65.0,
    proximity_threshold: float = 2.0
):
    """
    Scan for major swing setups at HTF support/resistance levels.
    
    Args:
        symbols: Comma-separated symbols to scan (default: top 5)
        min_confidence: Minimum confidence score (default 65)
        proximity_threshold: Max % from level to alert (default 2%)
        
    Returns:
        List of tactical opportunities with mode recommendations
    """
    try:
        from backend.data.adapters.phemex import PhemexAdapter
        from backend.data.ingestion_pipeline import IngestionPipeline
        
        # Parse symbols
        symbol_list = symbols.split(",") if symbols else DEFAULT_HTF_SYMBOLS
        symbol_list = [s.strip() for s in symbol_list]
        
        # Initialize detector and adapter
        detector = HTFLevelDetector(proximity_threshold=proximity_threshold)
        adapter = PhemexAdapter()
        pipeline = IngestionPipeline(adapter)
        
        all_opportunities: List[OpportunityResponse] = []
        
        for symbol in symbol_list:
            try:
                # Fetch HTF data
                multi_tf = pipeline.fetch_multi_timeframe(symbol, HTF_TIMEFRAMES, limit=200)
                if not multi_tf or not multi_tf.timeframes:
                    continue
                
                # Get current price
                current_price = None
                for tf in HTF_TIMEFRAMES:
                    df = multi_tf.timeframes.get(tf)
                    if df is not None and len(df) > 0:
                        current_price = float(df['close'].iloc[-1])
                        break
                
                if not current_price:
                    continue
                
                # Detect levels - only include non-None, non-empty DataFrames
                ohlcv_data = {}
                for tf in HTF_TIMEFRAMES:
                    df = multi_tf.timeframes.get(tf)
                    if df is not None and not df.empty:
                        ohlcv_data[tf] = df
                
                if not ohlcv_data:
                    logger.warning(f"No OHLCV data available for {symbol}, skipping")
                    continue
                
                levels = detector.detect_levels(symbol, ohlcv_data, current_price)
                
                # Also detect Fib levels
                fib_levels = detector.detect_fib_levels(symbol, ohlcv_data, current_price)
                all_levels = levels + fib_levels
                
                if not all_levels:
                    continue
                
                # Find opportunities (using empty SMC context for now)
                smc_context = {"order_blocks": [], "fvgs": [], "breaks": []}
                opportunities = detector.find_opportunities(
                    symbol, all_levels, current_price, smc_context
                )
                
                # Convert to response format
                for opp in opportunities:
                    if opp.confidence >= min_confidence:
                        all_opportunities.append(OpportunityResponse(
                            symbol=opp.symbol,
                            level=HTFLevelResponse(
                                price=opp.level.price,
                                level_type=opp.level.level_type,
                                timeframe=opp.level.timeframe,
                                strength=opp.level.strength,
                                touches=opp.level.touches,
                                proximity_pct=opp.level.proximity_pct
                            ),
                            current_price=opp.current_price,
                            recommended_mode=opp.recommended_mode,
                            rationale=opp.rationale,
                            confluence_factors=opp.confluence_factors,
                            expected_move_pct=opp.expected_move_pct,
                            confidence=opp.confidence
                        ))
                        
            except Exception as sym_error:
                # Log but continue with other symbols
                logger.warning(f"Failed to detect levels for {symbol}: {sym_error}")
                continue
        
        # Sort by confidence
        all_opportunities.sort(key=lambda x: x.confidence, reverse=True)
        
        return HTFOpportunitiesResponse(
            opportunities=all_opportunities,
            total=len(all_opportunities),
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to detect opportunities: {str(e)}")


@router.get("/levels/{symbol}")
async def get_symbol_levels(
    symbol: str,
    min_strength: float = 50.0
):
    """
    Get all detected HTF levels for a specific symbol.
    
    Args:
        symbol: Trading pair (e.g., BTC/USDT)
        min_strength: Minimum level strength score (default 50)
        
    Returns:
        List of detected support/resistance levels
    """
    try:
        from backend.data.adapters.phemex import PhemexAdapter
        from backend.data.ingestion_pipeline import IngestionPipeline
        
        # Normalize symbol format (support BTCUSDT, BTC-USDT, BTC/USDT)
        normalized_symbol = symbol.upper().replace("-", "/")
        if "/" not in normalized_symbol and "USDT" in normalized_symbol:
            normalized_symbol = normalized_symbol.replace("USDT", "/USDT")
        # Add Phemex perpetual suffix if not present
        if ":USDT" not in normalized_symbol and normalized_symbol.endswith("/USDT"):
            normalized_symbol = normalized_symbol + ":USDT"
        
        # Initialize detector and adapter
        detector = HTFLevelDetector(proximity_threshold=5.0)  # Wider threshold for level listing
        adapter = PhemexAdapter()
        pipeline = IngestionPipeline(adapter)
        
        # Fetch HTF data
        multi_tf = pipeline.fetch_multi_timeframe(normalized_symbol, HTF_TIMEFRAMES, limit=200)
        if not multi_tf or not multi_tf.timeframes:
            return {
                "symbol": symbol,
                "levels": [],
                "total": 0,
                "timestamp": datetime.now().isoformat(),
                "error": "No data available for symbol"
            }
        
        # Get current price
        current_price = None
        for tf in HTF_TIMEFRAMES:
            df = multi_tf.timeframes.get(tf)
            if df is not None and len(df) > 0:
                current_price = float(df['close'].iloc[-1])
                break
        
        if not current_price:
            return {
                "symbol": symbol,
                "levels": [],
                "total": 0,
                "timestamp": datetime.now().isoformat(),
                "error": "Could not determine current price"
            }
        
        # Detect levels - only include non-None, non-empty DataFrames
        ohlcv_data = {}
        for tf in HTF_TIMEFRAMES:
            df = multi_tf.timeframes.get(tf)
            if df is not None and not df.empty:
                ohlcv_data[tf] = df
        
        if not ohlcv_data:
            return {
                "symbol": symbol,
                "levels": [],
                "total": 0,
                "current_price": current_price,
                "timestamp": datetime.now().isoformat(),
                "error": "No valid OHLCV data for level detection"
            }
        
        levels = detector.detect_levels(normalized_symbol, ohlcv_data, current_price)
        
        # Also add Fib levels
        fib_levels = detector.detect_fib_levels(normalized_symbol, ohlcv_data, current_price)
        all_levels = levels + fib_levels
        
        # Convert to response format and filter
        response_levels = []
        for level in all_levels:
            if level.strength >= min_strength:
                response_levels.append(HTFLevelResponse(
                    price=level.price,
                    level_type=level.level_type,
                    timeframe=level.timeframe,
                    strength=level.strength,
                    touches=level.touches,
                    proximity_pct=level.proximity_pct
                ))
        
        # Sort by strength
        response_levels.sort(key=lambda x: x.strength, reverse=True)
        
        return {
            "symbol": symbol,
            "levels": response_levels,
            "total": len(response_levels),
            "current_price": current_price,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch levels: {str(e)}")

