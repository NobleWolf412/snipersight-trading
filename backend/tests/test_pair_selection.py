from backend.analysis.pair_selection import select_symbols, DEFAULT_FALLBACK


class DummyAdapter:
    def __init__(self, symbols):
        self._symbols = symbols

    def get_top_symbols(self, n: int = 20, quote_currency: str = "USDT"):
        return self._symbols[:n]


def test_select_symbols_basic_filters():
    adapter = DummyAdapter([
        "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
        "DOGE/USDT", "SHIB/USDT", "PEPE/USDT", "FOO/USDT", "BAR/USDT",
    ])
    assert select_symbols(adapter, 10, True, False, False) == [
        "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
    ]
    assert select_symbols(adapter, 5, False, False, True) == [
        "DOGE/USDT", "SHIB/USDT", "PEPE/USDT",
    ]
    assert select_symbols(adapter, 10, False, True, False) == ["FOO/USDT", "BAR/USDT"]


def test_select_symbols_underfills_strict_categories_and_orders_enabled_buckets():
    adapter = DummyAdapter([
        "DOGE/USDT", "FOO/USDT", "BTC/USDT", "SHIB/USDT", "ETH/USDT", "BAR/USDT",
    ])
    assert select_symbols(adapter, 8, False, False, True) == ["DOGE/USDT", "SHIB/USDT"]
    assert select_symbols(adapter, 6, True, True, True) == [
        "BTC/USDT", "ETH/USDT", "DOGE/USDT", "SHIB/USDT", "FOO/USDT", "BAR/USDT",
    ]


def test_select_symbols_fallback_when_adapter_empty():
    adapter = DummyAdapter([])
    out = select_symbols(adapter, limit=7, majors=True, altcoins=True, meme_mode=False)
    assert out  # not empty
    assert all(s in DEFAULT_FALLBACK for s in out)
