import asyncio
from backend.bot.paper_trading_service import PaperTradingService, PaperTradingConfig

async def main():
    service = PaperTradingService()
    config = PaperTradingConfig(sniper_mode='stealth', initial_balance=10000, symbols=['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'SOL/USDT', 'BNB/USDT'])
    try:
        await service.start(config)
        print('Started')
        await service._run_scan()
        print('Scan complete')
        for act in service.activity_log:
            print(act['event_type'], act.get('data', {}))
    except Exception as e:
        print('Error:', e)

asyncio.run(main())
