"""Pure normalization of raw USDT-linear Phemex financial evidence.

Unified CCXT price/cost/UPnL fields may be inferred. Only explicit raw execution
and account fields are admitted here. Unsupported evidence remains unavailable.
"""
from decimal import Decimal
from backend.bot.executor.accounting_models import (
    AccountingError, AccountObservation, AccountPositionObservation, ExecutionFact,
    Fee, OrderExecutionObservation, amount, exact_product, exact_sum,
)


def _row(value):
    if type(value) is not dict:
        raise AccountingError("OBJECT_REQUIRED")
    return value


def _alias(row, *names, numeric=False, required=False):
    values = [row[n] for n in names if n in row and row[n] is not None]
    if numeric:
        values = [amount(v) for v in values]
    if not values:
        if required:
            raise AccountingError("FIELD_MISSING:" + names[0])
        return None
    if any(v != values[0] for v in values):
        raise AccountingError("ALIAS_CONFLICT:" + names[0])
    return values[0]


def _market(market):
    _row(market)
    if (market.get("swap") is not True or market.get("linear") is not True
            or market.get("inverse") is True or market.get("settle") != "USDT"
            or market.get("quote") != "USDT" or not market.get("symbol") or not market.get("id")):
        raise AccountingError("MARKET_SCOPE_UNSUPPORTED")
    # CCXT metadata uses floats; this is explicit metadata conversion, not raw
    # execution-price conversion. Unit-one only avoids base/contract ambiguity.
    multiplier = amount(str(market.get("contractSize")))
    if multiplier != 1:
        raise AccountingError("CONTRACT_MULTIPLIER_UNSUPPORTED")
    return market["symbol"], multiplier


def _side(value, zero=False):
    if zero and value in (None, "None", "Buy", "Sell"):
        return None
    if value not in ("Buy", "Sell"):
        raise AccountingError("RAW_SIDE_INVALID")
    return "BUY" if value == "Buy" else "SELL"


def normalize_account(response, markets, context):
    _row(response)
    if type(response.get("code")) is not int or response["code"] != 0:
        raise AccountingError("ACCOUNT_RESPONSE_INVALID")
    data = _row(response.get("data"))
    account = _row(data.get("account"))
    if account.get("currency") != "USDT" or type(data.get("positions")) is not list:
        raise AccountingError("ACCOUNT_SCOPE_OR_COLLECTION_INVALID")
    if any(container.get(key) for container in (response, data)
           for key in ("hasMore", "nextPage", "nextCursor")):
        raise AccountingError("ACCOUNT_PARTIAL_RESPONSE")
    if "total" in data and (type(data["total"]) is not int or data["total"] != len(data["positions"])):
        raise AccountingError("ACCOUNT_PARTIAL_RESPONSE")
    wallet = _alias(account, "accountBalanceRv", numeric=True, required=True)
    used = _alias(account, "totalUsedBalanceRv", numeric=True, required=True)
    bonus = _alias(account, "bonusBalanceRv", numeric=True)
    if used < 0:
        raise AccountingError("USED_MARGIN_INVALID")
    reasons = set()
    if bonus != 0:
        reasons.add("BONUS_POLICY_UNRESOLVED")
    inventory = {}
    for market in markets.values():
        _row(market)
        if market.get("swap") and market.get("settle") == "USDT":
            key = market.get("id")
            if not key or key in inventory:
                raise AccountingError("MARKET_INVENTORY_AMBIGUOUS")
            inventory[key] = market
    if not inventory:
        raise AccountingError("MARKET_INVENTORY_UNAVAILABLE")
    positions, seen = [], set()
    for raw in data["positions"]:
        _row(raw)
        market_id = raw.get("symbol")
        if not isinstance(market_id, str) or not market_id:
            raise AccountingError("POSITION_MARKET_MISSING")
        if raw.get("currency") != "USDT":
            raise AccountingError("POSITION_SETTLEMENT_MISMATCH")
        for identity in (raw.get("accountID"), account.get("accountId")):
            if identity is not None and (type(identity) not in (str, int) or not str(identity).isdigit() or int(identity) <= 0):
                raise AccountingError("ACCOUNT_ID_INVALID")
        if raw.get("accountID") is not None and str(raw["accountID"]) != str(account.get("accountId")):
            raise AccountingError("POSITION_ACCOUNT_MISMATCH")
        key = (market_id, raw.get("posSide"))
        if key in seen:
            raise AccountingError("POSITION_DUPLICATE")
        seen.add(key)
        qty = _alias(raw, "sizeRq", "size", numeric=True, required=True)
        side = _side(raw.get("side"), zero=qty == 0)
        row_reasons = set()
        symbol = multiplier = None
        try:
            symbol, multiplier = _market(inventory.get(market_id))
        except AccountingError as exc:
            row_reasons.add(str(exc))
        if raw.get("posMode") != "OneWay" or raw.get("posSide") != "Merged":
            row_reasons.add("POSITION_MODE_UNSUPPORTED")
        entry = _alias(raw, "avgEntryPriceRp", numeric=True, required=qty > 0)
        mark = _alias(raw, "markPriceRp", numeric=True, required=qty > 0)
        upnl = _alias(raw, "unRealisedPnlRv", numeric=True)
        if upnl is None:
            row_reasons.add("RAW_MARK_PNL_MISSING")
        if qty == 0:
            entry = None if entry == 0 else entry
            mark = None if mark == 0 else mark
            if upnl not in (None, Decimal(0)):
                raise AccountingError("FLAT_POSITION_PNL_CONFLICT")
        position = AccountPositionObservation(market_id, symbol, side, qty, multiplier,
                    qty if multiplier == 1 else None, entry, mark, upnl, tuple(sorted(row_reasons)))
        positions.append(position)
        reasons.update(row_reasons)
    # Different mode labels must not allow duplicate one-way rows for a symbol.
    one_way = [p.market_id for p in positions if not p.reasons]
    if len(one_way) != len(set(one_way)):
        raise AccountingError("POSITION_DUPLICATE")
    upnl = exact_sum(p.unrealized_pnl for p in positions) if all(p.unrealized_pnl is not None for p in positions) else None
    free = exact_sum((wallet, used.copy_negate())) if bonus == 0 else None
    equity = exact_sum((wallet, upnl)) if upnl is not None and not reasons else None
    return AccountObservation(context, wallet, used, free, bonus, upnl, equity,
                              tuple(positions), tuple(sorted(reasons)))


def _execution(raw, market):
    _row(raw)
    symbol, _ = _market(market)
    if raw.get("symbol") != market["id"]:
        raise AccountingError("EXECUTION_MARKET_MISMATCH")
    return (symbol, _side(raw.get("side")),
            _alias(raw, "clOrdID", "clOrdId"), _alias(raw, "orderID", "orderId"))


def normalize_order(raw, market, context):
    symbol, side, client, remote = _execution(raw, market)
    statuses = {"New": "OPEN", "PartiallyFilled": "OPEN", "Filled": "FILLED",
                "Canceled": "CANCELLED", "Cancelled": "CANCELLED", "Rejected": "REJECTED"}
    status = statuses.get(raw.get("ordStatus"))
    if status is None:
        raise AccountingError("RAW_ORDER_STATUS_UNSUPPORTED")
    qty = _alias(raw, "cumQtyRq", "cumQty", numeric=True, required=True)
    cost = _alias(raw, "cumValueRv", "cumValue", numeric=True)
    requested = _alias(raw, "orderQtyRq", "orderQty", numeric=True)
    if requested is not None and (requested <= 0 or qty > requested):
        raise AccountingError("RAW_ORDER_QUANTITY_CONFLICT")
    return OrderExecutionObservation(context, symbol, side, client, remote, qty, cost, status,
                                     "raw_cumulative_value" if cost is not None else None)


def normalize_execution(raw, market, context):
    symbol, side, client, remote = _execution(raw, market)
    kind = {"Trade": "TRADE", "Funding": "FUNDING", "LiqTrade": "LIQUIDATION", "AdlTrade": "ADL"}.get(raw.get("tradeType"))
    if kind is None:
        raise AccountingError("RAW_EXECUTION_KIND_UNSUPPORTED")
    qty = _alias(raw, "execQtyRq", numeric=True, required=True)
    cost = _alias(raw, "execValueRv", numeric=True)
    provenance = "raw_execution_value" if cost is not None else None
    price = _alias(raw, "execPriceRp", numeric=True)
    if price is not None and price <= 0:
        raise AccountingError("EXECUTION_PRICE_INVALID")
    if cost is None and price is not None:
        cost, provenance = exact_product(qty, price), "raw_execution_price_times_quantity"
    fees = []
    if raw.get("execFeeRv") is not None:
        if raw.get("currency") != "USDT":
            raise AccountingError("FEE_CURRENCY_REQUIRED")
        fees.append(Fee("USDT", amount(raw["execFeeRv"]), "raw_execFeeRv"))
    if raw.get("ptFeeRv") is not None:
        fees.append(Fee("PT", amount(raw["ptFeeRv"]), "raw_ptFeeRv"))
    return ExecutionFact(context, symbol, side, _alias(raw, "execID", "execId"), client, remote,
                         qty, cost, tuple(fees) if fees else None, kind, provenance)
