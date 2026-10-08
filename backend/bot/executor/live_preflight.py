"""Read-only exchange checks; never construct an order-capable executor."""
import math
import time


def read_only_preflight(adapter, min_balance_usd=50.0):
    result = {"ok": False, "balance": 0.0, "open_positions": [], "issues": []}
    if not adapter.supports_trading():
        result["issues"].append("No API keys configured")
        return result
    try:
        free = adapter.fetch_balance()["free"]["USDT"]
        if isinstance(free, bool) or not math.isfinite(float(free)) or float(free) < 0:
            raise ValueError("Invalid USDT free balance")
        result["balance"] = float(free)
        if float(free) < min_balance_usd:
            result["issues"].append(f"Balance below minimum ${min_balance_usd:.2f}")
    except Exception as exc:
        result["issues"].append(f"Balance unavailable: {exc}")
    try:
        rows = adapter.fetch_positions()
        if not isinstance(rows, list):
            raise ValueError("Position collection unavailable")
        for row in rows:
            qty = row["contracts"]
            if isinstance(qty, bool) or not math.isfinite(float(qty)) or float(qty) < 0 or not row.get("symbol"):
                raise ValueError("Invalid position")
            if float(qty) > 0:
                result["open_positions"].append({"symbol": row["symbol"], "size": float(qty)})
    except Exception as exc:
        result["issues"].append(f"Position check failed: {exc}")
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
