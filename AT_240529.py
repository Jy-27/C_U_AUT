#%%
import pandas as pd
import json
import os
import pyupbit as pu
import datetime
import asyncio
import sys
import pytz
import threading
from collections import deque, defaultdict
from typing import Deque


def get_api_key(market :str='upbit'):
    """
    거래소별로 등록된 api keys를 저장한 json파일을 불러온다. file명을 거래소명으로 저장해야 한다.
    return 형태 {"access": "XXXXX", "secret": "XXXXX"}
    """
    path = os.path.join(os.path.dirname(os.getcwd()), 'API', market+'.json')
    with open(path, 'r')as file:
        api_key = json.load(file)
        return api_key

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

def edit_data(data):
    edited_data = {
        'code':str(data['code']),
        'trade_timestamp':float(data['trade_timestamp']),
        'trade_price':float(data['trade_price']),
        'volume_ask':float(data['trade_volume'] if data['ask_bid'] == 'ASK' else 0),
        'volume_bid':float(data['trade_volume'] if data['ask_bid'] == 'BID' else 0),
        'count_ask':int(1 if data['ask_bid'] == 'ASK' else 0),
        'count_bid':int(1 if data['ask_bid'] == 'BID' else 0),
        'seller':int(1 if data['ask_bid'] == 'ASK' else 0),
        'buyer':int(1 if data['ask_bid'] == 'BID' else 0)}
    return edited_data


#============================================================================

# async def monitoring():
#     while True:
#         target_ticker = g



#============================================================================

class PositionStopper:
    """거래('long' or 'short')발생시 거래내역 정보를 저장하고 손절 or 익절 목표 단가를 반환한다."""

    position_info = {}

    def __init__(self, initial_dict=None):
        self.classname = self.__class__.__name__
        if initial_dict:
            self.reference_price.update(initial_dict)

    @classmethod
    def trade_order_type(cls, open_position_info :dict):
        """
        1. open_position_info 입력예시
            open_position_info = {'code':ticker,
                                  'market':'upbit' or 'binance',
                                  'position':'long' or 'short'}
        2. 용도 및 목적 : 진입 포지션 정보를 기준으로 익절 or 손절값 반환
        3. 실제 주문완료 후 position 입력할 것.
        """
        ticker = open_position_info['code']

        if ticker not in cls.position_info.keys() and open_position_info['market']=='upbit':
            cls.position_info[ticker] = open_position_info

            for balance in upbit.get_balances():
                if balance['currency']==ticker.split('-')[1]:
                    cls.position_info[ticker]['position_price'] = float(balance['avg_buy_price'])

    @classmethod
    #수신된 최종 거래금액을 기존 등록된 금액과 비교 후 max값을 저장한다. order_type에 해당 Ticker가 보유시에만 업데이트 된다.
    def data_update(cls, trade_price :dict):
        """
        1. trade_price 입력예시 : {'KRW-BTC':85_000_000}
        2. 용도 및 목적 : cls.reference_price의 최종 정보를 update 한다.
        3. 결과물
            예) cls.order_type >> short일 경우 cls.reference_price 값과 trade_price값중 Min값 update.
            예) cls.order_type >> long일 경우 cls.reference_price 값과 trade_price값중 Min값 update.
        """

        #trade_price에서 ticker정보를 추출한다.
        ticker = list(map(str, trade_price.keys()))[0]

        # print(cls.position_info[ticker].keys())

        #cls.order_type값을 참고하여 매수 포지션('long' 또는 'short')에 따라 cls.reference_price정보를 update한다.
        if ticker in cls.position_info:
            reference_price_exist_ = 'reference_price' in cls.position_info[ticker].keys()
            market_ = cls.position_info[ticker]['market']
            position_ = cls.position_info[ticker]['position']
            if position_ == "long" and market_ == 'upbit' and reference_price_exist_:
                cls.position_info[ticker]['reference_price'] = max(cls.position_info[ticker]['reference_price'], list(trade_price.values())[0])

            elif position_ == "long" and market_ == 'upbit' and not reference_price_exist_:
                cls.position_info[ticker]['reference_price'] = list(trade_price.values())[0]

        """
        Note...
        binance의 long / short position진입도 항목에 넣을 것.
        """

    @classmethod
    def target_price(cls, ticker, percent :float=0.012):
        """
        1. 입력 예시
            1) ticker = 'KRW-BTC'
            2) percent = 0.012
        2. 용도 및 목적 : 손절 or 익절 target price를 지정한다.
        3. 특기사항 : 매입가, cls.reference_price의 계산을 통하여 target_price는 유동적으로 변한다. trade_price의 등락 변동폭에 대한 유동적 대응을 위함이다.
        """
        if cls.position_info[ticker]['position'] == "long":
            sell_percent = 1 - min((float(cls.position_info[ticker]['position_price'] / cls.position_info[ticker]['reference_price'])*0.2)+percent, percent)
            result = cls.position_info[ticker]['reference_price'] * sell_percent
            return result

        elif cls.position_info[ticker]['position'] == "short":
            sell_percent = 1 + min((float(cls.position_info[ticker]['reference_price'] / cls.position_info[ticker]['position_price'])*0.2)+percent, percent)
            result = cls.position_info[ticker]['reference_price'] * sell_percent
            return result

    @classmethod
    def remove_ticker(cls, ticker):
        """
        1. ticker 입력예시 : 'KRW-BTC'
        2. 용도 및 목적 : 'long' or 'short'포지션 종료시 거래정보 초기화한다.
        3. 결과물 : classmethod 변수값에서 ticker정보 삭제
        """
        del cls.position_info[ticker]

class DataSaver:
    """
    Note.
      1. 버퍼역할을 하는 deque 또는 queue가 없이 사용시 DataSaver class 실행시 일부 데이터 누락이 발생했다.
         버퍼역할을 추가하고 다시 테스트 해볼필요가 있다.
    """
    def __init__(self, maxlen :int = 5_000):
        self.deque_inside = deque()
        self.deque_save = deque()
        self.maxlen = maxlen
        self.edited_data = None
        self.classname = self.__class__.__name__
        # self.lock = asyncio.Lock

    async def Append(self, queue_input):
        while not queue_input.empty():
            getData = await queue_input.get()
            edited_data = edit_data(getData)
            if self.deque_inside:
                index_last_data = self.deque_inside[-1]
                check_timestamp = edited_data['trade_timestamp'] == index_last_data['trade_timestamp']
                check_price = edited_data['trade_price'] == index_last_data['trade_price']

                if all([check_timestamp, check_price]):
                    index_last_data = self.deque_inside.pop()
                    index_last_data.update({'volume_ask': edited_data['volume_ask'] + index_last_data['volume_ask'],
                                            'volume_bid': edited_data['volume_bid'] + index_last_data['volume_bid'],
                                            'count_ask' : edited_data['count_ask'] + index_last_data['count_ask'],
                                            'count_bid' : edited_data['count_bid'] + index_last_data['count_bid']})
                    self.deque_inside.append(index_last_data)
                else:
                    self.deque_inside.append(edited_data)
            else:
                self.deque_inside.append(edited_data)
            await asyncio.sleep(0)

        if len(self.deque_inside) >= self.maxlen:
            await self.Dump()
    
    async def Dump(self):
        directory_ = os.path.join(os.path.dirname(os.getcwd()),
                                  'DataBase',
                                  self.deque_inside[0]['code'])
        file_ = str(int(self.deque_inside[0]['trade_timestamp'])) + '.json'
        if not os.path.exists(directory_):
            os.makedirs(directory_)
        path_ = os.path.join(directory_, file_)
        for _ in range(len(self.deque_inside)):
            popLeft = self.deque_inside.popleft()
            self.deque_save.append(popLeft)
            await asyncio.sleep(0)
        with open(path_, "w", encoding='utf-8') as f:
            json.dump(list(self.deque_save), f, ensure_ascii=False, indent=4)
        self.deque_save.clear()

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

class DataMerge:
    def __init__(self, maxlen :int=5_000):
        self.mergeData = Deque(maxlen=maxlen)
        self.classname = self.__class__.__name__

    def AddLoadData(self, loadData):
        if loadData:
            self.mergeData.extend(loadData)
        else:
            pass

    def AddRealtimeData(self, realtimeData):
        edited_data = edit_data(data=realtimeData)
        if not self.mergeData:
            self.mergeData.append(edited_data)

        elif self.mergeData:
            index_last_data = self.mergeData[-1].copy()
            check_timestamp = edited_data['trade_timestamp'] == index_last_data['trade_timestamp']
            check_price = edited_data['trade_price'] == index_last_data['trade_price']
            if all([check_timestamp, check_price]):
                self.mergeData.pop()
                index_last_data.update({'volume_ask': edited_data['volume_ask'] + index_last_data['volume_ask'],
                                        'volume_bid': edited_data['volume_bid'] + index_last_data['volume_bid'],
                                        'count_ask' : edited_data['count_ask'] + index_last_data['count_ask'],
                                        'count_bid' : edited_data['count_bid'] + index_last_data['count_bid']})
                self.mergeData.append(index_last_data)
            else:
                self.mergeData.append(edited_data)

    def GetData(self):
        return list(self.mergeData)

async def DataManager(queue, SaveMaxlen :int=2_000, MergeMaxlen :int=10_000, timeSleep :int=5):
    saver_ = {}
    merge_ = {}
    queue_ = {}
    while True:
        tickers = pu.get_tickers('KRW')
        for ticker in tickers:
            if ticker not in saver_.keys():
                saver_[ticker] = DataSaver(maxlen=SaveMaxlen)
                merge_[ticker] = DataMerge(maxlen=MergeMaxlen)
                queue_[ticker] = asyncio.Queue()
        timeNow = datetime.datetime.now()
        timeDelta = datetime.timedelta(hours=2)
        whileExit = timeNow + timeDelta

        while timeNow <= whileExit:
            while not queue.empty():
                q_data = await queue.get()
                ticker = q_data['code']
                if ticker in queue_.keys():
                    await queue_[ticker].put(q_data)
                    # await self.merge_[code].AddRealtimeData(realtimeData=q_data)

                    await saver_[ticker].Append(queue_input=queue_[ticker])
                    # await (saver_[ticker]).process(deque_[ticker])
                    # cls.saver_[code].process(data=cls.deque_[code])
                    # await cls.saver_[code].process(data=cls.deque_[code])
                    # .process(data=cls.deque_[code])
                    # .process(data=cls.deque_[code])
                    # print(f'{sys._getframe().f_lineno}')
                    await asyncio.sleep(0)

                #// TEST ZONE START
                # for ticker in tickers:
                #     data = await cls.merge_[ticker].GetData()
                #     if data:
                #         df_ = await ohlc(editData=data, interval=1)
                #         print(ticker)
                #         print(df_)
                #     else:
                #         print('data가 없습니다')
                #// TEST ZONE END
            await asyncio.sleep(timeSleep)

#=============================================================================================





class MarketOrder:
    def __init__(self, ticker=None , target:int=10):
        self.ticker = ticker
        self.target = target
        self.balances = upbit.get_balances()
        self.MIN_TRADE_AMOUNT = 6_000
        self.MIN_KRW_BALANCE = 5_500
        self.classname = self.__class__.__name__

    def Get_HoldingTickers(self):
        #Upbit 지갑속 KRW로 거래가능한 코인종류를 반환한다.
        balances_ = self.Get_Balances()
        result = []
        if balances_ is None:
            return result
        elif balances_ is not None:
            for data in balances_:
                code = data['code']
                result.append(code)
            return result

    def Get_Balances(self):
        #Upbit 지갑속 KRW 거래가능하며, 현재 가치 5,000원 이상의 코인에 대해서 정보를 반홚나다.
        result = []
        balances_ = upbit.get_balances()  # Assuming get_balances() doesn't take any arguments
        tickers_all = pu.get_tickers('KRW')
        for data in balances_:
            code = 'KRW-' + data['currency']
            if code in tickers_all:
                price_ = float(pu.get_current_price(code))
                volume_ = float(data['balance'])
                avg_buy_price = float(data['avg_buy_price'])
                now_value_ = price_ * volume_

                if now_value_ >= 5_000:
                    asset_data = {'code': code, 'avg_buy_price': avg_buy_price, 'now_price': price_, 'volume': volume_, 'value': now_value_}
                    result.append(asset_data)
        if not result:
            result = None
        return result

    def Get_Chance(self):
        #구매가능한 코인의 종류를 반환한다. 정보 확인용
        if self.Get_HoldingTickers() is None:
            return self.target
        elif self.Get_HoldingTickers() is not None:
            count = len(self.Get_HoldingTickers())
            calculator_1 = int(self.target - count)
            MinAmount = self.Get_MinAmount()
            KRW_ = int(upbit.get_balance('KRW'))
            calculator_2 = int(KRW_ / MinAmount)
            return min(calculator_1, calculator_2)

    def Get_MinAmount(self):
        #한번에 거래할 수 있는 최소 대금을 계산한다. 기본 5,000원 이상이지만 타이트하게 설정할 경우 거래대금 기준가 미달확률이 매우 높다.

        #보유중이면서 거래가능한 Ticker 개수를 확인한다.
        ticker_count = len(self.Get_HoldingTickers()) if self.Get_HoldingTickers() is not None else 0

        #현금 보유량을 확인한다.
        KRW_ = int(upbit.get_balance('KRW'))

        #첫째자리 이하 금액 버림처리 위한 코드
        target_amount = KRW_ / (10-ticker_count)
        len_ = int(len(str(target_amount)))-3
        nearest_amount = round(target_amount, (len_ * -1))

        possible_amount = KRW_ / self.MIN_TRADE_AMOUNT

        if KRW_ < self.MIN_TRADE_AMOUNT:
            amount = 0
        elif nearest_amount > self.MIN_TRADE_AMOUNT:
            amount = nearest_amount
        elif possible_amount > 0:
            amount = self.MIN_TRADE_AMOUNT
        return int(amount)

    def Buy_order(self) -> int:
        amount = self.Get_MinAmount()

        if amount > 0 and self.ticker not in self.Get_HoldingTickers():
            try:
                upbit.buy_market_order(self.ticker, amount)
                position = {'code':self.ticker,
                            'market':'upbit',
                            'position':'long'}
                close_posision_price.trade_order_type(open_position_info=position)
                Trade_data(ticker=self.ticker, amount=amount, tradeType='BUY')
                print(f'Order completed (Buy) : {self.ticker}')
            except EOFError as e:
                print(e)
        else:
            print(f'Order fail (Buy) : {self.ticker}')

    def Sell_order(self) -> int:
        Balance_ = self.Get_Balances()
        index = next((index for index, Balance_ in enumerate(Balance_) if Balance_['code'] == self.ticker), None)
        amount = Balance_[index]['volume']
        if amount > 0 and self.ticker in self.Get_HoldingTickers():
            try:
                before_selling_KRW_ = int(upbit.get_balance('KRW'))
                upbit.sell_market_order(self.ticker, amount)
                after_selling_KRW_ = int(upbit.get_balance('KRW'))
                close_posision_price.remove_ticker(self.ticker)
                sell_value = after_selling_KRW_ - before_selling_KRW_
                Trade_data(ticker=self.ticker, amount=sell_value, tradeType='SELL')
                print(f'Order complete (Sell): {self.ticker}')
            except EOFError as e:
                print(e)
        else:
            print(f'Order fail (Sell): {self.ticker}')

async def websocket(queue, restartRange :int=12):#updater, queue, hour :int=2, dataType :str='trade'):
    tickers_all = pu.get_tickers(fiat='KRW')
    WM_T = pu.WebSocketManager(type='trade', codes=tickers_all)

    while True:
        try:
            data_t = WM_T.get()
            await queue.put(data_t)
            await asyncio.sleep(0)
        except Exception as e:
            print(e)
            WM_T.terminate()
            tickers_all = pu.get_tickers(fiat='KRW')
            WM_T = pu.WebSocketManager(type='trade', codes=tickers_all)

async def main():
    MAXLEN_SAVE = 10
    MAXLEN_MERGE = 10_000
    # print(MAXLEN_)
    q_ = asyncio.Queue()

    websocket_task = asyncio.create_task(websocket(queue=q_))
    handler_task = asyncio.create_task(DataManager(queue=q_, SaveMaxlen=MAXLEN_SAVE, MergeMaxlen=MAXLEN_MERGE))

    await asyncio.gather(websocket_task,
                        handler_task)

if __name__ == "__main__":
    time_ = datetime.datetime.now()
    print(time_.strftime('%Y-%m-%d %H:%M:%S'))
    asyncio.run(main())


# %%
