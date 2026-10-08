"""Raw-field account and execution contracts under scripted transport."""
from copy import deepcopy
from decimal import Decimal as D
from types import SimpleNamespace as S
from unittest.mock import Mock
import pytest
from backend.bot.executor.accounting_models import AccountingError
from backend.data.adapters.phemex_accounting import normalize_account, normalize_order, normalize_execution
from backend.data.adapters.phemex import PhemexAdapter
from backend.tests.unit.test_accounting_models import context


def market():
    return dict(id="BTCUSDT", symbol="BTC/USDT:USDT", swap=True, linear=True, inverse=False,
                quote="USDT", settle="USDT", contractSize=1)


def account(side="Buy"):
    return {"code": 0, "data": {"account": {"accountId": 1, "currency": "USDT", "accountBalanceRv": "1000",
        "totalUsedBalanceRv": "250", "bonusBalanceRv": "0"}, "positions": [
        {"accountID": 1, "currency": "USDT", "symbol": "BTCUSDT", "side": side, "sizeRq": "10",
         "posMode": "OneWay", "posSide": "Merged", "avgEntryPriceRp": "100", "markPriceRp": "106",
         "unRealisedPnlRv": "60" if side == "Buy" else "-60"}]}}


def normalize(body, metadata=None):
    return normalize_account(body, {"btc": metadata or market()}, context())


@pytest.mark.parametrize("side,pnl", [("Buy", 60), ("Sell", -60)])
def test_combined_wallet_margin_and_mark_pnl(side, pnl):
    result = normalize(account(side))
    assert result.complete and result.wallet == 1000 and result.free == 750
    assert result.unrealized_pnl == pnl and result.equity == 1000 + pnl
    assert result.positions[0].base_quantity == 10


def test_reader_is_one_request_without_independent_fallbacks():
    adapter = object.__new__(PhemexAdapter)
    adapter.testnet, adapter.default_type = True, "swap"
    adapter.exchange = S(apiKey="fixture", secret="fixture", markets={"btc": market()},
        privateGetGAccountsPositions=Mock(return_value=account()), fetch_balance=Mock(), fetch_positions=Mock())
    result = adapter.fetch_account_observation()
    assert result.complete and result.context.environment == "testnet"
    adapter.exchange.privateGetGAccountsPositions.assert_called_once_with({"currency": "USDT"})
    adapter.exchange.fetch_balance.assert_not_called()
    adapter.exchange.fetch_positions.assert_not_called()
    adapter.exchange.privateGetGAccountsPositions.side_effect = RuntimeError("throttled")
    with pytest.raises(RuntimeError, match="throttled"):
        adapter.fetch_account_observation()
    assert adapter.exchange.privateGetGAccountsPositions.call_count == 2


@pytest.mark.parametrize("field,value", [("side", "unexpected"), ("sizeRq", True), ("sizeRq", "NaN"),
    ("currency", "BTC"), ("accountID", 2), ("markPriceRp", "0"), ("symbol", "")])
def test_invalid_raw_position_cannot_become_flat(field, value):
    body = account()
    body["data"]["positions"][0][field] = value
    with pytest.raises(AccountingError):
        normalize(body)


@pytest.mark.parametrize("case", ["bonus", "missing_bonus", "hedge", "missing_pnl", "unknown_market", "multiplier"])
def test_unsupported_evidence_preserved_without_usable_equity(case):
    body, metadata = account(), market()
    row = body["data"]["positions"][0]
    if case == "bonus": body["data"]["account"]["bonusBalanceRv"] = "10"
    if case == "missing_bonus": del body["data"]["account"]["bonusBalanceRv"]
    if case == "hedge": row.update(posMode="Hedged", posSide="Long")
    if case == "missing_pnl": del row["unRealisedPnlRv"]
    if case == "unknown_market": row["symbol"] = "UNKNOWN"
    if case == "multiplier": metadata["contractSize"] = 10
    result = normalize(body, metadata)
    assert not result.complete and result.equity is None and result.reasons
    assert result.positions[0].contracts == 10


def test_duplicate_zero_and_negative_balance_contracts():
    body = account()
    body["data"]["positions"] *= 2
    with pytest.raises(AccountingError, match="DUPLICATE"):
        normalize(body)
    body["data"]["positions"] = []
    body["data"]["account"]["accountBalanceRv"] = "-100"
    result = normalize(body)
    assert result.complete and result.equity == -100 and result.free == -350
    zero = account()
    zero["data"]["positions"][0].update(sizeRq="0", side="None", avgEntryPriceRp="0", unRealisedPnlRv="0")
    assert normalize(zero).positions[0].side is None


def raw_order():
    return dict(symbol="BTCUSDT", side="Buy", clOrdID="order", orderID="remote", ordStatus="Filled",
                cumQtyRq="10", orderQtyRq="10", cumValueRv="1060", priceRp="110", execFeeRv="1")


def test_order_uses_only_executed_cost_and_requires_consistent_aliases():
    raw = raw_order()
    assert normalize_order(raw, market(), context()).cost == 1060
    del raw["cumValueRv"]
    assert normalize_order(raw, market(), context()).cost is None
    raw["cumQty"] = "9"
    with pytest.raises(AccountingError, match="ALIAS_CONFLICT"):
        normalize_order(raw, market(), context())


@pytest.mark.parametrize("fee", ["0", "-0.2", "0.2"])
def test_identified_execution_actual_fee_and_currency(fee):
    raw = raw_order()
    raw.update(tradeType="Trade", execID="e1", execQtyRq="10", execValueRv="1060", execFeeRv=fee, currency="USDT")
    result = normalize_execution(raw, market(), context())
    assert result.fees[0].amount == D(fee) and result.cost == 1060
    del raw["currency"]
    with pytest.raises(AccountingError, match="FEE_CURRENCY"):
        normalize_execution(raw, market(), context())


def test_execution_unknown_id_and_price_are_not_invented():
    raw = raw_order()
    del raw["execFeeRv"]
    raw.update(tradeType="Trade", execQtyRq="10")
    result = normalize_execution(raw, market(), context())
    assert result.execution_id is None and result.cost is None and result.fees is None
    raw.update(execPriceRp="106", ptFeeRv="-1")
    result = normalize_execution(raw, market(), context())
    assert result.cost == 1060 and result.fees[0].currency == "PT"


@pytest.mark.parametrize("field,value", [("hasMore", True), ("nextCursor", "remaining"), ("total", 2)])
def test_partial_account_response_cannot_claim_complete(field, value):
    body = account()
    body["data"][field] = value
    with pytest.raises(AccountingError, match="PARTIAL"):
        normalize(body)


@pytest.mark.parametrize("field,value", [("accountID", True), ("accountID", "bad"), ("accountID", 0)])
def test_account_identity_raw_validation(field, value):
    body = account()
    body["data"]["positions"][0][field] = value
    with pytest.raises(AccountingError, match="ACCOUNT_ID"):
        normalize(body)
