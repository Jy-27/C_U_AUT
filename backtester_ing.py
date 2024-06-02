#%%/

import glob
import os
import json
# import multiprocessing
from collections import deque
import pandas as pd
import pytz
from multiprocessing import Process, Queue
import numpy as np
class Loader:
    def __init__ (self, ticker):
        self.ticker = ticker
        self.deque = deque()

    def paths(self):
        directory =  os.path.join(os.path.dirname(os.getcwd()), 'DataBase', self.ticker)
        if not os.path.exists(directory):
            return None
        paths = glob.glob(f"{directory}/*.json")
        return paths

    def data(self):
        load_ = []
        paths = self.paths()
        if paths == None: return None
        for path in paths:
            with open(path, 'r')as f:
                load_ += json.load(f)
        load_ = sorted(load_, key=lambda x: x['trade_timestamp'])
        for d in load_:
            d['signal'] = None
        self.deque.extend(load_)
        return self.deque
        # return load_

# def ohlc_index()

def calculate_sum_past_5_min(current_index, df):
    start_time = current_index - pd.Timedelta(minutes=5)
    relevant_data = df[start_time:current_index]
    return relevant_data['volume'].sum()


def bollingerBands(Data, std_dev :int=2):
    key = 'trade_price'
    values = [item[key] for item in Data if key in item]
    SMA_ = np.mean(values)
    STD_ = np.std(values)
    uppper_ = SMA_ + (STD_ + std_dev)
    lower_ = SMA_ - (STD_ + std_dev)
    center_ = np.median([uppper_, lower_])
    data = {'upper' : uppper_,
            'center': center_,
            'lower' : lower_}
    return data

# apply를 사용하여 각 행에 대해 5분 전까지의 데이터 합계를 계산
# df['5min_volume_sum'] = df.apply(lambda row: calculate_sum_past_5_min(row.name, df), axis=1)

# 결과 출력
# print(df)

def ohlc(data, interval: int = 1):
    editData = data
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

class Backtest:
    def __init__(self, ticker, stepSize :int=1_000, type :str='realtime'):
        self.ticker = ticker
        self.status = None
        self.type = None
        self.deque = deque()
    
    def realtime(self, timeRange :int=1):
        minute_ = 60_000 * timeRange
        dataLoad = Loader(self.ticker).data()
        
        for data in dataLoad:
            self.deque.append(data)
            timestampMAX = self.deque[-1]['trade_timestamp']
            timestampMIN = timestampMAX - minute_
            while True:
                if self.deque[0]['trade_timestamp'] <= timestampMIN:
                    self.deque.popleft()
                else:
                    break
            # ohlc_ = ohlc(data=self.deque)
            # print(ohlc_)
            # len_ = len(self.deque)
            bollinger_ = bollingerBands(Data=self.deque)
            print(data)
            print(bollinger_)

if __name__ == "__main__":
    Backtest(ticker='KRW-BTC').realtime()
#     Backtest(ticker='KRW-ADA').realtime()
#     Backtest(ticker='KRW-XRP').realtime()
        
        
    
    
#     def play(self):
#         loadData = Loader(self.ticker).data()
        


 
    
#     (ticker :str='KRW-BTC')
# def main(loadData):
#     # Convert timestamps to integers
#     timestampMin = int(loadData[0]['trade_timestamp'])
#     timestampMax = int(loadData[-1]['trade_timestamp'])
    
#     # Define the time range for filtering
#     timestampRange = 60_000  # Time range in milliseconds
#     step_size = 10_000  # Step size for iteration
    
    
#     n = 0
#     # Iterate over the timestamp range
#     for start in range(timestampMin, timestampMax, step_size):
#         end = start + timestampRange
#         # Filter data within the time range
#         try:
#             filtered_data = [entry for entry in  loadData if start < entry["trade_timestamp"] <= end]
#             print(f'{n} - {ohlc(filtered_data).to_string()}')
#             n += 1
#         except:
#             pass
        
# if __name__ == "__main__":
#     import multiprocessing
#     # Ensure the Loader class is defined and returns data correctly
#     num_cores = multiprocessing.cpu_count()
#     ticker = 'KRW-BTC'
    # data = Loader(ticker).data()  # Load the data using the Loader
    # main(loadData=data)

# %%
