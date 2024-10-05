import Utility
import os
from pprint import pprint
import asyncio

async def main():
    path = '/Volumes/TEST_ZONE/API/binance.json'
    tickers = ['celousdt', 'adausdt', 'dogeusdt', 'xrpusdt', 'ltcusdt', 'storjusdt']
    u = Utility.Utility(tickers)
    u.init_client(path)
    u.get_account_balance()
    
    await asyncio.sleep(5)
    
    u.update_isPending()
    
    for ticker in tickers:
        u.set_margin_leverage(symbol=ticker, leverage=5)
    
    pprint(u.__dict__)
    
    tasks = [asyncio.create_task(u.fetch_ohlcv_data()),
             asyncio.create_task(u.get_max_min_for_ranges()),
             asyncio.create_task(u.update_data_periodically()),
             asyncio.create_task(u._position_stopper()),
             asyncio.create_task(u._order_signal())]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())