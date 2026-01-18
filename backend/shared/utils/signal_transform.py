"""
Signal Transform Utility

Shared logic for transforming TradePlan objects to API response format.
Consolidates duplicate code from scanner.py and scanner_service.py.
"""

from typing import List, Dict, Any, Tuple
from dataclasses import asdict
import logging

logger = logging.getLogger(__name__)

# Maximum allowed drift between entry zone and live price
MAX_ENTRY_DRIFT_PCT = 20.0


def transform_trade_plans_to_signals(
    trade_plans: List, mode, adapter=None, validate_prices: bool = True
) -> Tuple[List[Dict], List[Dict]]:
    """
    Transform TradePlan objects to API response format.

    Args:
        trade_plans: List of TradePlan objects from orchestrator
        mode: Scanner mode with timeframe config
        adapter: Exchange adapter for live price validation (optional)
        validate_prices: Whether to filter stale signals by price drift

    Returns:
        Tuple of (valid_signals, rejected_signals)
    """
    signals = []
    rejected_signals = []

    for plan in trade_plans:
        # Clean symbol: remove '/' and ':USDT' suffix (exchange swap notation)
        clean_symbol = plan.symbol.replace("/", "").replace(":USDT", "")

        # Extract SMC geometry lists from plan.metadata
        ob_list = plan.metadata.get("order_blocks_list", []) if plan.metadata else []
        fvg_list = plan.metadata.get("fvgs_list", []) if plan.metadata else []
        bos_list = plan.metadata.get("structural_breaks_list", []) if plan.metadata else []
        sweep_list = plan.metadata.get("liquidity_sweeps_list", []) if plan.metadata else []
        pool_list = plan.metadata.get("liquidity_pools_list", []) if plan.metadata else []

        # Extract equal_highs and equal_lows from pools for frontend fallback
        equal_highs = [p["level"] for p in pool_list if p.get("type") == "highs"]
        equal_lows = [p["level"] for p in pool_list if p.get("type") == "lows"]

        signal = {
            "symbol": clean_symbol,
            "original_symbol": plan.symbol,  # Preserve original for validation
            "direction": plan.direction,
            "sniper_mode": mode.name,  # Vital for frontend chart timeframe selection
            "score": plan.confidence_score,
            "entry_near": plan.entry_zone.near_entry,
            "entry_far": plan.entry_zone.far_entry,
            "stop_loss": plan.stop_loss.level,
            "targets": [{"level": tp.level, "percentage": tp.percentage} for tp in plan.targets],
            "primary_timeframe": mode.timeframes[-1] if mode.timeframes else "",
            "current_price": plan.entry_zone.near_entry,
            "analysis": {
                "order_blocks": len(ob_list),
                "fvgs": len(fvg_list),
                "structural_breaks": len(bos_list),
                "liquidity_sweeps": len(sweep_list),
                "trend": plan.direction.lower(),
                "risk_reward": plan.risk_reward,
                "confluence_score": (
                    plan.confluence_breakdown.total_score
                    if hasattr(plan, "confluence_breakdown") and plan.confluence_breakdown
                    else plan.confidence_score
                ),
                "expected_value": plan.metadata.get("expected_value") if plan.metadata else None,
            },
            "rationale": plan.rationale,
            # FIX: Send raw code (e.g. 'intraday') not display label ('Day Trade') so frontend can classify correctly
            "setup_type": getattr(plan, "trade_type", plan.setup_type),
            "plan_type": getattr(plan, "plan_type", "SMC"),
            "conviction_class": getattr(plan, "conviction_class", None),
            "missing_critical_timeframes": (
                plan.metadata.get("missing_critical_timeframes", []) if plan.metadata else []
            ),
            "regime": {
                "global_regime": plan.metadata.get("global_regime") if plan.metadata else None,
                "symbol_regime": plan.metadata.get("symbol_regime") if plan.metadata else None,
            },
            "macro": plan.metadata.get("macro") if plan.metadata else None,
            # SMC geometry for chart overlays - actual OB/FVG price ranges
            "smc_geometry": {
                "order_blocks": ob_list[:10],  # Limit for payload size
                "fvgs": fvg_list[:10],
                "bos_choch": bos_list[:10],
                "liquidity_sweeps": sweep_list[:10],
                "liquidity_pools": pool_list[:10],
                "equal_highs": equal_highs[:10],  # Flat array for frontend fallback
                "equal_lows": equal_lows[:10],  # Flat array for frontend fallback
            },
        }

        # Add confluence breakdown if available
        if hasattr(plan, "confluence_breakdown") and plan.confluence_breakdown:
            signal["analysis"]["confluence_breakdown"] = {
                "total_score": plan.confluence_breakdown.total_score,
                "synergy_bonus": plan.confluence_breakdown.synergy_bonus,
                "conflict_penalty": plan.confluence_breakdown.conflict_penalty,
                "regime": plan.confluence_breakdown.regime,
                "htf_aligned": plan.confluence_breakdown.htf_aligned,
                "btc_impulse_gate": plan.confluence_breakdown.btc_impulse_gate,
                "factors": [
                    {
                        "name": f.name,
                        "score": f.score,
                        "weight": f.weight,
                        "rationale": f.rationale,
                        "weighted_score": f.weighted_score,
                    }
                    for f in plan.confluence_breakdown.factors
                ],
            }
            # Also expose at top level for easier access
            try:
                signal["confluence_breakdown"] = asdict(plan.confluence_breakdown)
            except Exception:
                signal["confluence_breakdown"] = signal["analysis"]["confluence_breakdown"]

        # Expose reversal context for UI notification
        if plan.metadata:
            reversal_data = plan.metadata.get("reversal")
            if reversal_data and reversal_data.get("is_reversal_setup"):
                signal["reversal_context"] = {
                    "is_reversal_setup": reversal_data.get("is_reversal_setup", False),
                    "direction": reversal_data.get("direction", ""),
                    "cycle_aligned": reversal_data.get("cycle_aligned", False),
                    "htf_bypass_active": reversal_data.get("htf_bypass_active", False),
                    "confidence": reversal_data.get("confidence", 0.0),
                    "rationale": reversal_data.get("rationale", ""),
                }

        signals.append(signal)

    # Validate prices if adapter provided
    if validate_prices and adapter:
        signals, rejected_from_validation = _validate_signal_prices(signals, adapter)
        rejected_signals.extend(rejected_from_validation)

    stale_filtered = len(rejected_signals)
    if stale_filtered > 0:
        logger.info(
            "🧹 Filtered %d stale signals (entry >%.0f%% from live price)",
            stale_filtered,
            MAX_ENTRY_DRIFT_PCT,
        )

    # Final safety: recursively sanitize any remaining numpy types
    return _sanitize_for_json(signals), _sanitize_for_json(rejected_signals)


def _validate_signal_prices(signals: List[Dict], adapter) -> Tuple[List[Dict], List[Dict]]:
    """
    Filter signals where entry zone is too far from live price.

    This prevents stale cached data from producing invalid trade plans.

    Args:
        signals: List of signal dictionaries
        adapter: Exchange adapter with fetch_ticker method

    Returns:
        Tuple of (validated_signals, rejected_signals)
    """
    validated_signals = []
    rejected_signals = []

    for sig in signals:
        try:
            # Get live ticker price from exchange
            # Prefer original symbol if preserved, otherwise reconstructed
            ticker_symbol = sig.get("original_symbol")
            if not ticker_symbol:
                ticker_symbol = sig["symbol"].replace("/", "") + ":USDT"

            ticker = adapter.exchange.fetch_ticker(ticker_symbol)
            live_price = ticker.get("last") or ticker.get("close") or 0

            if live_price > 0:
                avg_entry = (sig["entry_near"] + sig["entry_far"]) / 2
                drift_pct = abs(avg_entry - live_price) / live_price * 100

                # Update signal with actual live price
                sig["current_price"] = live_price
                sig["_price_validation"] = {
                    "live_price": live_price,
                    "avg_entry": avg_entry,
                    "drift_pct": round(drift_pct, 2),
                    "validated": drift_pct <= MAX_ENTRY_DRIFT_PCT,
                }

                if drift_pct > MAX_ENTRY_DRIFT_PCT:
                    logger.warning(
                        "⚠️ STALE SIGNAL FILTERED: %s entry $%.2f is %.1f%% from live price $%.2f",
                        sig["symbol"],
                        avg_entry,
                        drift_pct,
                        live_price,
                    )
                    # Add to rejected list with detailed reason
                    rejected_signals.append(
                        {
                            "symbol": sig["symbol"],
                            "reason": f"Entry price drift {drift_pct:.1f}% > {MAX_ENTRY_DRIFT_PCT}%",
                            "reason_type": "risk_validation",
                            "details": {
                                "live_price": live_price,
                                "entry_avg": avg_entry,
                                "drift_pct": drift_pct,
                                "max_drift": MAX_ENTRY_DRIFT_PCT,
                            },
                        }
                    )
                    continue  # Skip this stale signal

            validated_signals.append(sig)
        except Exception as e:
            logger.warning("Price validation failed for %s: %s - keeping signal", sig["symbol"], e)
            # Add to rejected list with detailed reason if validation itself fails
            rejected_signals.append(
                {
                    "symbol": sig["symbol"],
                    "reason": f"Price validation failed: {e}",
                    "reason_type": "validation_error",
                    "details": {"error_message": str(e)},
                }
            )
            continue  # Skip this signal if validation fails

    return validated_signals, rejected_signals


def _sanitize_for_json(obj: Any) -> Any:
    """
    Recursively convert numpy types to native Python types for JSON serialization.
    """
    import numpy as np

    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    elif isinstance(obj, (np.integer, int)):
        return int(obj)
    elif isinstance(obj, (np.floating, float)):
        return float(obj)
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return _sanitize_for_json(obj.tolist())
    else:
        return obj
