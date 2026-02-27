from backend.analysis.pair_selection import select_symbols, DEFAULT_FALLBACK


class DummyAdapter:
    def __init__(self, symbols):
        self._symbols = symbols

    def get_top_symbols(self, n: int = 20, quote_currency: str = "USDT"):
        return self._symbols[:n]


def test_select_symbols_basic_filters():
    symbols = [
        "BTC/USDT",
        "ETH/USDT",
        "BNB/USDT",
        "SOL/USDT",
        "XRP/USDT",
        "DOGE/USDT",
        "SHIB/USDT",
        "PEPE/USDT",
    ]
    adapter = DummyAdapter(symbols)

    # Majors only
    out = select_symbols(adapter, limit=10, majors=True, altcoins=False, meme_mode=False)
    proportional = max(1, int(len(symbols) * 0.2))
    # First chunk should come from majors slice; backfill may include others to reach limit
    proportional = max(1, int(len(symbols) * 0.2))
    majors_first = symbols[: max(3, min(10, proportional))]
    assert set(out[: len(majors_first)]).issubset(set(majors_first))
    assert len(out) >= len(majors_first)
    assert len(out) <= 10

    # Meme only: should include available memes, then backfill to reach limit
    out = select_symbols(adapter, limit=5, majors=False, altcoins=False, meme_mode=True)
    memes = {"DOGE/USDT", "SHIB/USDT", "PEPE/USDT"}
    assert memes.issubset(set(out))
    assert len(out) == 5

    # Alts only (exclude majors & memes)
    out = select_symbols(adapter, limit=2, majors=False, altcoins=True, meme_mode=False)
    proportional = max(1, int(len(symbols) * 0.2))
    majors_dyn = set(symbols[: max(3, min(10, proportional))])
    memes = {"DOGE/USDT", "SHIB/USDT", "PEPE/USDT"}
    assert all(s not in majors_dyn and s not in memes for s in out)


def test_select_symbols_handles_all_combos_and_backfill():
    # Construct limited dataset to force backfill
    symbols = [
        "BTC/USDT",
        "ETH/USDT",
        "BNB/USDT",
        "SOL/USDT",
        "XRP/USDT",
        "DOGE/USDT",
        "SHIB/USDT",
        "PEPE/USDT",
        "ADA/USDT",
        "AVAX/USDT",
    ]
    adapter = DummyAdapter(symbols)

    # Request more memes than available -> should backfill with remaining symbols
    out = select_symbols(adapter, limit=8, majors=False, altcoins=False, meme_mode=True)
    assert len(out) == 8
    assert set({"DOGE/USDT", "SHIB/USDT", "PEPE/USDT"}).issubset(set(out))

    # All toggles checked, ensure we reach limit and preserve ranking
    out = select_symbols(adapter, limit=7, majors=True, altcoins=True, meme_mode=True)
    assert len(out) == 7
    # First symbols should start from majors slice then include others
    assert out[0] in {"BTC/USDT", "ETH/USDT", "BNB/USDT"}


def test_select_symbols_fallback_when_adapter_empty():
    adapter = DummyAdapter([])
    out = select_symbols(adapter, limit=7, majors=True, altcoins=True, meme_mode=False)
    assert out  # not empty
    assert all(s in DEFAULT_FALLBACK for s in out)
