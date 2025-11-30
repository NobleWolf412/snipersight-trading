"""
HTF Opportunities API Endpoint (moved from backend/api/ to avoid module name collision)

Detects major swing setups at higher timeframe levels and recommends mode switches.
"""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from backend.analysis.htf_levels import HTFLevelDetector  # future use

router = APIRouter(prefix="/api/htf", tags=["HTF Opportunities"])


class HTFLevelResponse(BaseModel):
    price: float
    level_type: str
    timeframe: str
    strength: float
    touches: int
    proximity_pct: float


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
    try:
        detector = HTFLevelDetector(proximity_threshold=proximity_threshold)  # placeholder for future real use
        mock_opportunities = [
            OpportunityResponse(
                symbol="BTC/USDT",
                level=HTFLevelResponse(
                    price=43200.0,
                    level_type="support",
                    timeframe="1d",
                    strength=85.0,
                    touches=4,
                    proximity_pct=0.8,
                ),
                current_price=43550.0,
                recommended_mode="overwatch",
                rationale="Daily support with high confluence - major swing setup",
                confluence_factors=[
                    "Price approaching 1d support at $43200.00000",
                    "Very strong level (4 touches)",
                    "Support OB present near level",
                    "FVG gap coincides with support",
                    "Risk-on regime favors support bounces",
                ],
                expected_move_pct=3.5,
                confidence=88.0,
            ),
            OpportunityResponse(
                symbol="ETH/USDT",
                level=HTFLevelResponse(
                    price=2295.0,
                    level_type="resistance",
                    timeframe="4h",
                    strength=72.0,
                    touches=3,
                    proximity_pct=1.2,
                ),
                current_price=2268.0,
                recommended_mode="surgical",
                rationale="4H resistance with solid confluence - precision swing entry",
                confluence_factors=[
                    "Price approaching 4h resistance at $2295.00000",
                    "Strong level (3 touches)",
                    "Resistance OB present near level",
                    "Recent BOS/CHoCH supports directional bias",
                ],
                expected_move_pct=2.0,
                confidence=75.0,
            ),
            OpportunityResponse(
                symbol="SOL/USDT",
                level=HTFLevelResponse(
                    price=96.50,
                    level_type="support",
                    timeframe="4h",
                    strength=68.0,
                    touches=2,
                    proximity_pct=1.8,
                ),
                current_price=98.20,
                recommended_mode="surgical",
                rationale="4H level - balanced approach recommended",
                confluence_factors=[
                    "Price approaching 4h support at $96.50000",
                    "Strong level (2 touches)",
                    "Support OB present near level",
                ],
                expected_move_pct=2.5,
                confidence=70.0,
            ),
        ]
        filtered = [opp for opp in mock_opportunities if opp.confidence >= min_confidence]
        return HTFOpportunitiesResponse(
            opportunities=filtered, total=len(filtered), timestamp=datetime.now().isoformat()
        )
    except Exception as e:  # pragma: no cover - simple error path
        raise HTTPException(status_code=500, detail=f"Failed to detect opportunities: {e}")


@router.get("/levels/{symbol}")
async def get_symbol_levels(symbol: str, min_strength: float = 50.0):
    try:
        mock_levels = [
            HTFLevelResponse(
                price=43200.0,
                level_type="support",
                timeframe="1d",
                strength=85.0,
                touches=4,
                proximity_pct=0.8,
            ),
            HTFLevelResponse(
                price=44500.0,
                level_type="resistance",
                timeframe="1d",
                strength=78.0,
                touches=3,
                proximity_pct=2.2,
            ),
            HTFLevelResponse(
                price=42800.0,
                level_type="support",
                timeframe="4h",
                strength=65.0,
                touches=2,
                proximity_pct=1.5,
            ),
        ]
        filtered = [level for level in mock_levels if level.strength >= min_strength]
        return {
            "symbol": symbol,
            "levels": filtered,
            "total": len(filtered),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Failed to fetch levels: {e}")
