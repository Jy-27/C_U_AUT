import glob
import os
import json
import multiprocessing
from collections import deque
import pandas as pd

class Loader:
    def __init__ (self, ticker):
        self.ticker = ticker

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
        return load_


if __name__ == "__main__":
    num_cores = multiprocessing.cpu_count()
    ticker = 'KRW-BTC'
    data = Loader(ticker).data()
    data = deque(data)
    start_ = int(data[0]['trade_timestamp'])
    end_ = int(data[-1]['trade_timestamp'])

    for timestamp in range(start_, end_, 1):
        data_ = targetData(data, end=timestamp, range=60_000)
        data_ = edit_data(data)
        ohlc_ = ohlc(data_)
        print(ohlc_)