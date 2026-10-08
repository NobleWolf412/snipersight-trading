"""Explicit synthetic raw exchange evidence for runtime migration regression tests.

Legacy fixture dictionaries describe scripted fills; this boundary materializes
their raw decimal evidence. Production code never derives cost from unified data.
"""
from decimal import Decimal
from types import SimpleNamespace as S
from unittest.mock import Mock
import time
from backend.tests.unit.test_accounting_models import context
from backend.data.adapters.phemex_accounting import normalize_account


def raw_response(ex, result, oid=None):
    if not isinstance(result, dict) or 'info' in result:
        return result
    cid = result.get('clientOrderId') or oid
    order = ex.get_order(oid) if oid else None
    if order is None:
        return result
    statuses = {'open': 'New', 'new': 'New', 'partiallyfilled': 'PartiallyFilled',
                'closed': 'Filled', 'filled': 'Filled', 'canceled': 'Canceled', 'cancelled': 'Canceled', 'rejected': 'Rejected'}
    raw = dict(symbol=order.symbol.replace('/', '').replace(':USDT', ''), side=order.side.value.title(),
        clOrdID=cid, orderID=result.get('id'), ordStatus=statuses.get(result.get('status'), result.get('status')),
        orderQtyRq=str(order.quantity))
    if 'filled' in result:
        raw['cumQtyRq'] = str(result['filled'])
        if result['filled'] == 0:
            raw['cumValueRv'] = '0'
        elif result.get('average') is not None:
            raw['cumValueRv'] = str(Decimal(str(result['filled'])) * Decimal(str(result['average'])))
    return {**result, 'info': raw}


class RawOrderTransport(Mock):
    def __call__(self, *args, **kwargs):
        result = super().__call__(*args, **kwargs)
        ex = self.fixture_adapter.fixture_executor
        oid = kwargs.get('params', {}).get('clientOrderId')
        if oid is None and args:
            oid = ex._reverse_order_map.get(args[0]) or (args[0] if args[0] in ex._orders else None)
        return raw_response(ex, result, oid)


def prepare_adapter(ad, symbol='A', binding='fixture'):
    ad.testnet = True
    if not hasattr(ad, 'exchange'):
        ad.exchange = S()
    ad.exchange.markets = {symbol: dict(symbol=symbol, id=symbol.replace('/', '').replace(':USDT', ''),
        linear=True, swap=True, inverse=False, contract=True, contractSize=1, quote='USDT', settle='USDT')}
    ad.fixture_binding = binding
    for name in ('create_order', 'fetch_order', 'fetch_order_by_client_id', 'cancel_order'):
        old = getattr(ad, name, Mock())
        transport = RawOrderTransport(return_value=old.return_value, side_effect=old.side_effect)
        transport.fixture_adapter = ad
        setattr(ad, name, transport)
    def account():
        rows = getattr(getattr(ad, 'fetch_positions', None), 'return_value', [])
        rows = rows if isinstance(rows, list) else []
        positions = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('contracts'), (int, float)):
                continue
            positions.append(dict(symbol=ad.exchange.markets[symbol]['id'], currency='USDT', accountID=1,
                side='Buy' if row.get('side') == 'long' else 'Sell', sizeRq=str(row['contracts']),
                posMode='OneWay', posSide='Merged', avgEntryPriceRp=str(row.get('entryPrice', 100)),
                markPriceRp='100', unRealisedPnlRv='0'))
        now = time.monotonic()
        return normalize_account({'code': 0, 'data': {'account': {'accountId': 1, 'currency': 'USDT',
            'accountBalanceRv': '1000', 'totalUsedBalanceRv': '0', 'bonusBalanceRv': '0'}, 'positions': positions}},
            ad.exchange.markets, context(binding=binding, started_monotonic=now, ended_monotonic=now))
    ad.fetch_account_observation = Mock(side_effect=account)
    return ad


def initialize_fixture(ex):
    ex._adapter.fixture_executor = ex
    if not ex._recovery_only:
        ex._accounting.establish_flat_baseline()
    ex.reconcile_account(force=True)
    ex.set_entry_admission(True)
    return ex


def fixture_ws(ex, remote, client, status, quantity, price):
    result = raw_response(ex, {'id': remote, 'clientOrderId': client, 'status': status,
                              'filled': quantity, 'average': price}, client)
    return ex.apply_ws_order(result['info'])
