#%%


import pandas as pd
import pyupbit as pu
import os
import datetime
import json
import pytz
import time
class DataLoader:
    def __init__(self, ticker :str, start :int=7):
        self.ticker = ticker
        self.start = start
        self.directory = os.path.join(os.path.dirname(os.getcwd()),
                                      'DataBase',
                                      ticker)
        self.loadData = None
        self.classname = self.__class__.__name__
    def paths(self):
        paths_ = []
        try:
            if os.path.exists(self.directory):
                timeNow = datetime.datetime.now()
                timeDelta = datetime.timedelta(days=self.start)
                timestart = str((timeNow - timeDelta).timestamp() * 1_000) + '.json'

                files = [file for file in os.listdir(self.directory) if file.endswith('.json')]
                if files:
                    for target_file in files:
                        if timestart <= target_file:
                            path = os.path.join(self.directory, target_file)
                            paths_.append(path)
        finally:
            return paths_

    def Load(self):
        paths = self.paths()
        load = []
        if paths:
            for path in paths:
                with open(path, 'r', encoding='utf-8')as file:
                    load += json.load(file)
        return load

def ohlc(editData, interval: int = 1):
    df_ = pd.DataFrame(editData)
    df_['date'] = pd.to_datetime(df_['trade_timestamp'], unit='ms', utc=True).dt.tz_convert(pytz.timezone('Asia/Seoul'))
    df_.set_index('date', inplace=True)
    df_.index = df_.index.tz_localize(None)
    ohlc = df_.resample(f'{interval}min').agg({'trade_price': 'ohlc',
                                               'volume_ask': 'sum',
                                               'volume_bid': 'sum',
                                               'count_ask': 'sum',
                                               'count_bid': 'sum',
                                               'seller':'sum',
                                               'buyer':'sum'})
    ohlc.columns = [col[1] for col in ohlc.columns.values]
    return ohlc



# ticker_ = 'KRW-GLM'
target_ = '2024-06-01 07:30:00'

pd.set_option('display.max_rows', None)

def my_py(ticker :str, date :str):
    DataLoader(ticker=ticker).Load()
    ohlc_ = ohlc(DataLoader(ticker=ticker).Load())
    ohlc_['volume'] = ohlc_['volume_ask'] + ohlc_['volume_bid']
    up_ = pu.get_ohlcv(ticker, interval='minute1', count=60*24)
    up_ = up_.loc[up_.index >= target_].round(10)
    my_ = ohlc_.loc[ohlc_.index >= target_].copy().round(10)
    print(up_['volume'] - my_['volume'])

def get_tickers():
    tickers = []
    list_ = os.listdir(os.path.join(os.path.dirname(os.getcwd()), 'DataBase'))
    for i in list_:
        if i.startswith('KRW'):
            tickers.append(i)
    return tickers

while True:
    tickers_ = get_tickers()
    for ticker in tickers_:
        try:
            print(ticker)
            my_py(ticker=ticker, date=target_)
            print('\n')
        except:
            pass
    time.sleep(60)
# %%
