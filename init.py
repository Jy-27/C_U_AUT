import Utility
import os
from pprint import pprint

path = '/Volumes/TEST_ZONE/API/binance.json'
tickers = ['xrpusdt', 'adausdt', 'dogeusdt']

u = Utility.Utility(tickers)
u.init_client(path)
u.get_account_balance()

print(tickers)
print(path)
print('instance_name : u\n')

pprint(u.account_balance)
u.close_position()
u.open_position('long', 'dogeusdt')
u.open_position('long', 'dogeusdt')
print('END!')