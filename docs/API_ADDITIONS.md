# API Additions for Cycle Translation System

## Backend: api_server.py

Add these endpoints after the four-year-cycle endpoint:

```python
# ============================================================================
# Symbol Cycle Intelligence Endpoint
# ============================================================================

@app.get("/api/market/symbol-cycles")
async def get_symbol_cycles(
    symbol: str = Query("BTC/USDT", description="Symbol to analyze"),
    exchange: str = Query("bybit", description="Exchange to fetch data from")
):
    """
    Get cycle intelligence for a specific symbol.
    """
    try:
        from backend.strategy.smc.symbol_cycle_detector import (
            detect_symbol_cycles,
            check_cycle_alerts
        )
        from backend.data.adapters import bybit, phemex, okx, bitget
        
        adapters = {
            'bybit': bybit.BybitAdapter(),
            'phemex': phemex.PhemexAdapter(),
            'okx': okx.OKXAdapter(),
            'bitget': bitget.BitgetAdapter()
        }
        adapter = adapters.get(exchange.lower())
        if not adapter:
            raise HTTPException(status_code=400, detail=f"Unknown exchange: {exchange}")
        
        normalized = symbol.replace("/", "").replace("-", "").upper()
        if not normalized.endswith("USDT"):
            normalized += "USDT"
        
        logger.info("Fetching daily data for %s cycle analysis", normalized)
        daily_df = await adapter.fetch_ohlcv(normalized, "1d", limit=120)
        
        if daily_df is None or len(daily_df) < 60:
            return {
                "status": "error",
                "error": f"Insufficient data for {symbol} cycle analysis",
                "data": None
            }
        
        if 'timestamp' in daily_df.columns:
            daily_df = daily_df.set_index('timestamp')
        
        cycles = detect_symbol_cycles(daily_df, symbol)
        alerts = check_cycle_alerts(cycles)
        
        return {
            "status": "success",
            "data": {
                **cycles.to_dict(),
                "alerts": [
                    {
                        "type": a.alert_type,
                        "cycle": a.cycle,
                        "message": a.message,
                        "details": a.details
                    }
                    for a in alerts
                ]
            }
        }
        
    except Exception as e:
        logger.error("Symbol cycle detection failed for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=f"Cycle detection error: {str(e)}") from e


@app.get("/api/market/btc-cycle-context")
async def get_btc_cycle_context():
    """
    Get complete BTC cycle context across all timeframes.
    """
    try:
        from backend.strategy.smc.symbol_cycle_detector import detect_symbol_cycles
        from backend.strategy.smc.four_year_cycle import (
            get_four_year_cycle_context,
            get_halving_info
        )
        from backend.data.adapters.bybit import BybitAdapter
        
        adapter = BybitAdapter()
        daily_df = await adapter.fetch_ohlcv("BTCUSDT", "1d", limit=120)
        
        if daily_df is None or len(daily_df) < 60:
            raise HTTPException(status_code=500, detail="Failed to fetch BTC data")
        
        if 'timestamp' in daily_df.columns:
            daily_df = daily_df.set_index('timestamp')
        
        cycles = detect_symbol_cycles(daily_df, "BTC/USDT")
        fyc = get_four_year_cycle_context()
        halving = get_halving_info()
        
        return {
            "status": "success",
            "data": {
                "symbol": "BTC/USDT",
                "dcl": cycles.dcl.to_dict(),
                "wcl": cycles.wcl.to_dict(),
                "four_year_cycle": {
                    "days_since_low": fyc.days_since_fyc_low,
                    "cycle_position_pct": round(fyc.cycle_position_pct, 1),
                    "phase": fyc.phase.value.upper(),
                    "phase_progress_pct": round(fyc.phase_progress_pct, 1),
                    "translation": "RTR" if fyc.macro_bias == "BULLISH" else ("LTR" if fyc.macro_bias == "BEARISH" else "MTR"),
                    "macro_bias": fyc.macro_bias,
                    "confidence": round(fyc.confidence, 1),
                    "last_low": {
                        "date": fyc.last_fyc_low_date.isoformat(),
                        "price": fyc.last_fyc_low_price
                    },
                    "expected_next_low": fyc.expected_next_low_date.isoformat(),
                    "is_danger_zone": fyc.is_in_danger_zone,
                    "is_opportunity_zone": fyc.is_in_opportunity_zone
                },
                "halving": {
                    "last_halving_date": halving['last_halving']['date'],
                    "next_halving_date": halving['next_halving']['estimated_date'],
                    "days_since_halving": halving['last_halving']['days_since'],
                    "days_until_halving": halving['next_halving']['days_until'],
                    "halving_history": halving.get('halving_history', [])
                },
                "overall": {
                    "dcl_bias": cycles.dcl.bias,
                    "wcl_bias": cycles.wcl.bias,
                    "macro_bias": fyc.macro_bias,
                    "alignment": _get_btc_alignment(cycles, fyc),
                    "warnings": cycles.warnings
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("BTC cycle context failed: %s", e)
        raise HTTPException(status_code=500, detail=f"BTC cycle error: {str(e)}") from e


def _get_btc_alignment(cycles, fyc) -> str:
    """Determine alignment of all BTC cycle timeframes."""
    biases = [cycles.dcl.bias, cycles.wcl.bias, fyc.macro_bias]
    macro_signal = "LONG" if fyc.macro_bias == "BULLISH" else ("SHORT" if fyc.macro_bias == "BEARISH" else "NEUTRAL")
    biases[2] = macro_signal
    
    long_count = biases.count("LONG")
    short_count = biases.count("SHORT")
    
    if long_count == 3:
        return "ALL_BULLISH"
    elif short_count == 3:
        return "ALL_BEARISH"
    elif long_count >= 2:
        return "MOSTLY_BULLISH"
    elif short_count >= 2:
        return "MOSTLY_BEARISH"
    else:
        return "MIXED"
```

## Frontend: src/utils/api.ts

Add these TypeScript types near the top with other type definitions:

```typescript
// Cycle Intelligence Types
export type TranslationType = 'right_translated' | 'mid_translated' | 'left_translated' | 'unknown';
export type CycleStatusType = 'healthy' | 'caution' | 'warning' | 'failed' | 'early' | 'unknown';
export type CycleBiasType = 'LONG' | 'SHORT' | 'NEUTRAL';
export type AlignmentType = 'ALIGNED' | 'MIXED' | 'CONFLICTING';
export type BTCAlignmentType = 'ALL_BULLISH' | 'ALL_BEARISH' | 'MOSTLY_BULLISH' | 'MOSTLY_BEARISH' | 'MIXED';

export interface CycleStateData {
  cycle_type: 'DCL' | 'WCL';
  bars_since_low: number;
  expected_length: { min: number; max: number; };
  midpoint: number;
  cycle_low: { price: number; bar: number; timestamp: string | null; };
  cycle_high: { price: number | null; bar: number | null; peak_bar: number | null; };
  translation: TranslationType;
  translation_pct: number;
  is_failed: boolean;
  is_in_window: boolean;
  status: CycleStatusType;
  bias: CycleBiasType;
}

export interface SymbolCyclesData {
  symbol: string;
  dcl: CycleStateData;
  wcl: CycleStateData;
  overall_bias: CycleBiasType;
  alignment: AlignmentType;
  warnings: string[];
  timestamp: string;
  alerts?: Array<{
    type: 'INFO' | 'WARNING' | 'CRITICAL';
    cycle: 'DCL' | 'WCL' | '4YC';
    message: string;
    details: Record<string, any>;
  }>;
}

export interface BTCCycleContextData {
  symbol: string;
  dcl: CycleStateData;
  wcl: CycleStateData;
  four_year_cycle: {
    days_since_low: number;
    cycle_position_pct: number;
    phase: 'ACCUMULATION' | 'MARKUP' | 'DISTRIBUTION' | 'MARKDOWN';
    phase_progress_pct: number;
    translation: 'RTR' | 'MTR' | 'LTR';
    macro_bias: 'BULLISH' | 'NEUTRAL' | 'BEARISH';
    confidence: number;
    last_low: { date: string; price: number; };
    expected_next_low: string;
    is_danger_zone: boolean;
    is_opportunity_zone: boolean;
  };
  halving: {
    last_halving_date: string;
    next_halving_date: string;
    days_since_halving: number;
    days_until_halving: number;
    halving_history: Array<{ date: string; block_height: number }>;
  };
  overall: {
    dcl_bias: CycleBiasType;
    wcl_bias: CycleBiasType;
    macro_bias: 'BULLISH' | 'NEUTRAL' | 'BEARISH';
    alignment: BTCAlignmentType;
    warnings: string[];
  };
  timestamp: string;
}
```

Add these API methods inside the ApiClient class:

```typescript
  // Symbol-specific cycle intelligence (DCL + WCL)
  async getSymbolCycles(symbol: string, exchange: string = 'bybit') {
    const params = new URLSearchParams({ symbol, exchange });
    return this.request<{
      status: string;
      data: SymbolCyclesData | null;
      error?: string;
    }>(`/market/symbol-cycles?${params.toString()}`, { 
      silent: import.meta.env.MODE === 'production',
      timeout: 60000 
    });
  }

  // BTC complete cycle context (DCL + WCL + 4YC)
  async getBTCCycleContext() {
    return this.request<{
      status: string;
      data: BTCCycleContextData;
    }>('/market/btc-cycle-context', { 
      silent: import.meta.env.MODE === 'production',
      timeout: 60000 
    });
  }
```
