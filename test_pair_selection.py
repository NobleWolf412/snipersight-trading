import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from backend.data.adapters.phemex import PhemexAdapter
from backend.analysis.pair_selection import select_symbols

adapter = PhemexAdapter()
syms = adapter.get_top_symbols(n=10, quote_currency="USDT", market_type='swap')
print("Phemex top symbols raw:", syms)

selected = select_symbols(
    adapter=adapter,
    limit=10,
    majors=False,
    altcoins=True,
    meme_mode=False,
    leverage=5,
    market_type='swap'
)
print("Select symbols:", selected)
