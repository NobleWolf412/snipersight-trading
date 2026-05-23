import asyncio
from backend.data.adapters.phemex import PhemexAdapter
async def f():
    a = PhemexAdapter()
    t = await a.fetch_ticker('BTC/USDT')
    print(t)
    await a.close()
asyncio.run(f())
