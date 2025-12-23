"""HTF Opportunities API Endpoint (moved from backend/api/ to avoid module name collision)

Detects major swing setups at higher timeframe levels and recommends mode switches.
"""
from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import logging

from backend.analysis.htf_levels import HTFLevelDetector
from backend.data.adapters.phemex import PhemexAdapter
import pandas as pd

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/htf", tags=["HTF Opportunities"])

# Singleton detector and adapter for reuse
_detector: Optional[HTFLevelDetector] = None
_adapter: Optional[PhemexAdapter] = None

def _get_detector(proximity_threshold: float = 2.0) -> HTFLevelDetector:
    global _detector
    if _detector is None or _detector.proximity_threshold != proximity_threshold:
        _detector = HTFLevelDetector(proximity_threshold=proximity_threshold)
    return _detector

def _get_adapter() -> PhemexAdapter:
    global _adapter
    if _adapter is None:
        _adapter = PhemexAdapter()
    return _adapter


class HTFLevelResponse(BaseModel):
    price: float
    level_type: str
    timeframe: str
    strength: float
    touches: int
    proximity_pct: float
    fib_ratio: Optional[float] = None
    trend_direction: Optional[str] = None


class OpportunityResponse(BaseModel):
    symbol: str
    level: HTFLevelResponse
    current_price: float
    recommended_mode: str
    rationale: str
    confluence_factors: List[str]
    expected_move_pct: float
    confidence: float


class HTFOpportunitiesResponse(BaseModel):
    opportunities: List[OpportunityResponse]
    total: int
    timestamp: str


@router.get("/opportunities", response_model=HTFOpportunitiesResponse)
async def get_htf_opportunities(
    symbols: Optional[str] = None,
    min_confidence: float = 65.0,
    proximity_threshold: float = 2.0,
):
    """
    Detect HTF swing opportunities across major symbols.
    
    Analyzes 4H/1D/1W levels for significant support/resistance with SMC context.
    Returns opportunities filtered by confidence threshold.
    """
    try:
        detector = _get_detector(proximity_threshold)
        adapter = _get_adapter()
        
        # Default symbols if none provided
        target_symbols = symbols.split(',') if symbols else ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
        target_symbols = [s.strip() for s in target_symbols]
        
        # Run blocking analysis in thread pool
        import asyncio
        loop = asyncio.get_event_loop()
        
        tasks = []
        for symbol in target_symbols:
            tasks.append(
                loop.run_in_executor(
                    None, 
                    _analyze_symbol_sync, 
                    symbol, 
                    detector, 
                    adapter, 
                    min_confidence
                )
            )
            
        results = await asyncio.gather(*tasks)
        
        # Flatten results
        all_opportunities = []
        for res in results:
            all_opportunities.extend(res)
        
        # Sort by confidence descending
        all_opportunities.sort(key=lambda x: x.confidence, reverse=True)
        
        return HTFOpportunitiesResponse(
            opportunities=all_opportunities,
            total=len(all_opportunities),
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"HTF opportunities detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to detect opportunities: {e}")


def _analyze_symbol_sync(
    symbol: str, 
    detector: HTFLevelDetector, 
    adapter: PhemexAdapter, 
    min_confidence: float
) -> List[OpportunityResponse]:
    """Synchronous helper for single symbol analysis (run in thread)."""
    opportunities: List[OpportunityResponse] = []
    try:
        # Fetch OHLCV data for HTF analysis
        ohlcv_data = {}
        for tf in ['4h', '1d']:
            try:
                # API Call (Blocking)
                df = adapter.fetch_ohlcv(symbol, timeframe=tf, limit=100)
                if df is not None and not df.empty:
                    ohlcv_data[tf] = df
            except Exception as tf_err:
                logger.warning(f"Failed to fetch {tf} data for {symbol}: {tf_err}")
                continue
        
        if not ohlcv_data:
            return []
        
        # Get current price (Blocking)
        ticker = adapter.fetch_ticker(symbol)
        current_price = ticker.get('last', 0) if ticker else 0
        if not current_price:
            return []
        
        # Detect levels (CPU Bound)
        sr_levels = detector.detect_levels(symbol, ohlcv_data, current_price)
        fib_levels = detector.detect_fib_levels(symbol, ohlcv_data, current_price)
        all_levels = sr_levels + fib_levels
        
        if not all_levels:
            return []
        
        # Find opportunities
        smc_context = {'order_blocks': [], 'fvgs': [], 'bos_choch': None}
        raw_opps = detector.find_opportunities(
            symbol=symbol,
            levels=all_levels,
            current_price=current_price,
            smc_context=smc_context,
            regime=None
        )
        
        # Filter and convert
        for opp in raw_opps:
            if opp.confidence >= min_confidence:
                opportunities.append(OpportunityResponse(
                    symbol=opp.symbol,
                    level=HTFLevelResponse(
                        price=opp.level.price,
                        level_type=opp.level.level_type,
                        timeframe=opp.level.timeframe,
                        strength=opp.level.strength,
                        touches=opp.level.touches,
                        proximity_pct=opp.level.proximity_pct,
                        fib_ratio=getattr(opp.level, 'fib_ratio', None),
                        trend_direction=getattr(opp.level, 'trend_direction', None),
                    ),
                    current_price=opp.current_price,
                    recommended_mode=opp.recommended_mode,
                    rationale=opp.rationale,
                    confluence_factors=opp.confluence_factors,
                    expected_move_pct=opp.expected_move_pct,
                    confidence=opp.confidence,
                ))
                
    except Exception as e:
        logger.error(f"Error processing {symbol} for HTF opportunities: {e}")
        
    return opportunities


@router.get("/levels/{symbol}")
async def get_symbol_levels(symbol: str, min_strength: float = 50.0, proximity_threshold: float = 5.0):
    """
    Get detected HTF support/resistance levels for a specific symbol.
    
    Analyzes 4H/1D candles to identify significant price levels.
    """
    try:
        detector = _get_detector(proximity_threshold)
        adapter = _get_adapter()
        
        # Run blocking analysis in thread pool
        import asyncio
        loop = asyncio.get_event_loop()
        
        result = await loop.run_in_executor(
            None,
            _get_symbol_levels_sync,
            symbol,
            detector,
            adapter,
            min_strength
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to fetch levels for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch levels: {e}")


def _get_symbol_levels_sync(
    symbol: str,
    detector: HTFLevelDetector,
    adapter: PhemexAdapter,
    min_strength: float
) -> Dict[str, Any]:
    """Synchronous helper for single symbol level detection."""
    try:
        # Fetch OHLCV data
        ohlcv_data = {}
        for tf in ['4h', '1d']:
            try:
                df = adapter.fetch_ohlcv(symbol, timeframe=tf, limit=100)
                if df is not None and not df.empty:
                    ohlcv_data[tf] = df
            except Exception as tf_err:
                logger.warning(f"Failed to fetch {tf} data for {symbol}: {tf_err}")
                continue
        
        if not ohlcv_data:
            return {
                "symbol": symbol,
                "levels": [],
                "total": 0,
                "timestamp": datetime.now().isoformat(),
                "error": "No OHLCV data available"
            }
        
        # Get current price
        ticker = adapter.fetch_ticker(symbol)
        current_price = ticker.get('last', 0) if ticker else 0
        if not current_price:
            return {
                "symbol": symbol,
                "levels": [],
                "total": 0,
                "timestamp": datetime.now().isoformat(),
                "error": "No price data available"
            }
        
        # Detect levels
        levels = detector.detect_levels(symbol, ohlcv_data, current_price)
        
        # Filter and convert to response
        filtered = []
        for level in levels:
            if level.strength >= min_strength:
                filtered.append(HTFLevelResponse(
                    price=level.price,
                    level_type=level.level_type,
                    timeframe=level.timeframe,
                    strength=level.strength,
                    touches=level.touches,
                    proximity_pct=level.proximity_pct,
                ))
        
        return {
            "symbol": symbol,
            "levels": filtered,
            "total": len(filtered),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error in _get_symbol_levels_sync for {symbol}: {e}")
        raise
