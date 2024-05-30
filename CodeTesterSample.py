import pandas as pd
import json
import os
import pyupbit as pu
import datetime
import asyncio
import sys
import pytz
from collections import deque, defaultdict
from typing import Deque

class DataSaver:
    """
    Note.
      1. 버퍼역할을 하는 deque 또는 queue가 없이 사용시 DataSaver class 실행시 일부 데이터 누락이 발생했다.
         버퍼역할을 추가하고 다시 테스트 해볼필요가 있다.
    """
    def __init__(self, maxlen :int = 5_000):
        self.deque:Deque[list] = deque()
        self.maxlen = maxlen
        self.edited_data = None
        self.classname = self.__class__.__name__
        self.lock = asyncio.Lock()

    def AddData(self, deque):
        while deque:
            popLeft = deque.popleft()
            edited_data = await edit_data(popLeft)
            if self.deque:
                index_last_data = self.deque[-1].copy()
                check_timestamp = edited_data['trade_timestamp'] == index_last_data['trade_timestamp']
                check_price = edited_data['trade_price'] == index_last_data['trade_price']

                if all([check_timestamp, check_price]):
                    self.deque.pop() 
                    index_last_data.update({'volume_ask': edited_data['volume_ask'] + index_last_data['volume_ask'],
                                            'volume_bid': edited_data['volume_bid'] + index_last_data['volume_bid'],
                                            'count_ask' : edited_data['count_ask'] + index_last_data['count_ask'],
                                            'count_bid' : edited_data['count_bid'] + index_last_data['count_bid']})
                    self.deque.append(index_last_data)
                else:
                    self.deque.append(edited_data)
            else:
                self.deque.append(edited_data)

        if len(self.deque) >= self.maxlen:
            self.SaveData()
    
    def SaveData(self):
        directory_ = os.path.join(os.path.dirname(os.getcwd()), 'DataBase', self.deque[0]['code'])
        file_ = str(int(self.deque[0]['trade_timestamp'])) + '.json'
        if not os.path.exists(directory_):
            os.makedirs(directory_)
        path_ = os.path.join(directory_, file_)
        with self.lock:
            save_to_file(data=list(self.deque), path=path_)
            self.deque.clear()

async def websocket(deque):
    tickers_all = pu.get_tickers('KRW')
    WM_T = pu.WebSocketManager(type='trade', codes=tickers_all)
    while True:
        data = WM_T.get()
        # print(data)
        await deque.put(data)
        await asyncio.sleep(0)

async def play(deque):
    while True:
        while deque:
            data = await deque.get()
            print(data)
            await asyncio.sleep(0)
        print('end')
        await asyncio.sleep(10)

async def main():
    # deque_ = LockedDeque()
    deque_ = asyncio.Queue()

    websocket_task = asyncio.create_task(websocket(deque=deque_))
    play_task = asyncio.create_task(play(deque = deque_))

    await asyncio.gather(websocket_task,
                         play_task)

LockedDeque()
if __name__ == "__main__":
    time_ = datetime.datetime.now()
    print(time_.strftime('%Y-%m-%d %H:%M:%S'))
    asyncio.run(main())











