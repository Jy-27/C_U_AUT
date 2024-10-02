import Utility
import os
from pprint import pprint

path = '/Users/nnn/Desktop/API/binance.json'
tickers = ['xrpusdt', 'adausdt', 'dogeusdt']

u = Utility.Utility(tickers)
u.initialize_client(path)
u.get_account_balance()

print(tickers)
print(path)
print('instance_name : u\n')

print(u.account_balance)
