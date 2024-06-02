import time
import pandas as pd
import AT_240529 as AT
import os
import pyupbit as pu

pd.set_option('display.max_rows', None)
paths = os.path.join(os.path.dirname(os.getcwd()), 'DataBase')
tickers = []
start = '2024-06-01 19:04:00'
for i in os.listdir(paths):
    if i.startswith('KRW'):
        load_ = AT.DataLoader(ticker=i).Load()
        ohlc_ = AT.ohlc(load_)
        ohlc_['volume'] = ohlc_['volume_ask'] + ohlc_['volume_bid']
        start_ = start
        end_ = ohlc_.iloc[-2].name
        up_ = pu.get_ohlcv(ticker=i, interval='minute1', count=200)
        
        my_ = ohlc_.loc[ohlc_.index >= start_]
        your_ = up_.loc[up_.index >= start_]
        
        print(i)
        print(my_['volume'].round(10) - your_['volume'].round(10))
        print('\n')

        
