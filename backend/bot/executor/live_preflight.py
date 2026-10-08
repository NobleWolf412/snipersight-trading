"""Read-only exchange checks; never construct an order-capable executor."""
import math
import time


def read_only_preflight(adapter, min_balance_usd=50.0):
    result = {"ok": False, "balance": None, "equity": None, "basis": "exchange_mark",
              "open_positions": [], "issues": []}
    if not adapter.supports_trading():
        result["issues"].append("No API keys configured")
        return result
    try:
        observed = adapter.fetch_account_observation()
        if not observed.complete:
            raise ValueError(', '.join(observed.reasons))
        free = observed.free
        result["balance"] = float(free)
        result["equity"] = float(observed.equity)
        if float(free) < min_balance_usd:
            result["issues"].append(f"Balance below minimum ${min_balance_usd:.2f}")
    except Exception as exc:
        result["issues"].append(f"Balance unavailable: {exc}")
    else:
        result['open_positions'] = [{'symbol': p.symbol, 'size': float(p.base_quantity)}
                                    for p in observed.positions if p.contracts]
    try:
        skew = abs(float(adapter.exchange.fetch_time()) - time.time() * 1000) / 1000
        if not math.isfinite(skew):
            raise ValueError("Invalid server timestamp")
        result["clock_skew_seconds"] = round(skew, 2)
        if skew > 30:
            result["issues"].append(f"Local clock is {skew:.1f}s off exchange time")
    except Exception as exc:
        result["issues"].append(f"Clock check unavailable: {exc}")
    result["ok"] = not result["issues"]
    return result
