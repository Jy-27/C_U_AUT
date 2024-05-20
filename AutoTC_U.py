#%%
import asyncio.selector_events
import pandas as pd
import pyupbit as pu # type: ignore
import json
import datetime
import os
import asyncio
import sys
import pprint
import ccxt # type: ignore
import websocket
print(sys._getframe().f_lineno)
# pd.set_option('dispaly.max_row, 100')

def Trade_data(ticker :str, amount :float, tradeType :str):
    #거래발생시 해당내역을 json으로 저장한다.
    path = os.path.join(os.getcwd(), 'TradeData.json')
    time_now = datetime.datetime.now().timestamp()
    data = {'Trade_Time':time_now, 'Code':ticker, 'Type':tradeType, 'Amount':amount}
    try:
        with open(path, 'a', encoding='utf-8')as file:
            json.dump(data, file)
            file.write('\n')
    except Exception as e:
        print(e)
        pass

def get_api_key(market :str='upbit'):
    """
    거래소별로 등록된 api keys를 저장한 json파일을 불러온다. file명을 거래소명으로 저장해야 한다.
    return 형태 {"access": "XXXXX", "secret": "XXXXX"}
    """
    path = os.path.join(os.path.dirname(os.getcwd()), 'API', market+'.json')
    with open(path, 'r')as file:
        api_key = json.load(file)
        return api_key

upbit = pu.Upbit(access=get_api_key(market='upbit')['access'],
                secret=get_api_key(market='upbit')['secret'])
binance = ccxt.binance(config=get_api_key(market='binance'))


class get_tickers:
    def __init__(self):
        self.all_ = None
        self.update_complete = asyncio.Event()

    async def update(self, days: int = 365):
        print('Ticker updating...')
        all_tickers = []
        upbit_tickers = pu.get_tickers(fiat='KRW', is_details=True)
        binance_tickers = [symbol.split("/")[0] for symbol in binance.fetch_tickers(params={"type": "futures"}) if symbol.endswith('/USDT')]

        for data in upbit_tickers:
            ticker = data['market']
            ticker_split = ticker.split('-')[1]
            if ticker_split in binance_tickers:
                all_tickers.append(ticker)

        value = {}
        for ticker in all_tickers:
            ohlcv_ = pu.get_ohlcv(ticker=ticker, interval='day', count=days)
            describe_ = ohlcv_.describe()
            value_min = describe_.loc['25%']['value']
            value[ticker] = value_min
            await asyncio.sleep(0)

        sorted_keys = sorted(value, key=value.get, reverse=True)
        self.all_ = sorted_keys
        print(self.all_)
        time_ = datetime.datetime.now()
        print(f'tickers update complete - {time_.strftime('%Y-%m-%d %H:%M:%S')}')
    async def get_data(self, type, rank:int=25):
        if type == 'all':
            return self.all_
        elif type == 'target':
            if self.all_ is None:
                return None
            elif self.all_ is not None:
                price = pu.get_current_price(self.all_, verbose=True)
                sorted_list = sorted(price, key=lambda x: x['acc_trade_price_24h'], reverse=True)
                market_values = [item['market'] for item in sorted_list][:rank]
                return market_values

class Data_Storage:
    def __init__(self):
        self.storage = []
        self.lock = asyncio.Lock()

    async def data_update(self, data):
        dataFilter = {
            'trade_timestamp': float(data['trade_timestamp']),
            'trade_price': float(data['trade_price']),
            'volume_ask': float(data['trade_volume'] if data['ask_bid'] == 'ASK' else 0),
            'volume_bid': float(data['trade_volume'] if data['ask_bid'] == 'BID' else 0),
            'count_ask': int(1 if data['ask_bid'] == 'ASK' else 0),
            'count_bid': int(1 if data['ask_bid'] == 'BID' else 0)
        }

        async with self.lock:
            if self.storage:
                columns = ['trade_timestamp', 'trade_price']
                bool_ = []

                for column in columns:
                    bool_.append(self.storage[-1][column] == dataFilter[column])

                if all(bool_):
                    self.storage[-1]['volume_ask'] += dataFilter['volume_ask']
                    self.storage[-1]['volume_bid'] += dataFilter['volume_bid']
                    self.storage[-1]['count_ask'] += dataFilter['count_ask']
                    self.storage[-1]['count_bid'] += dataFilter['count_bid']
                else:
                    self.storage.append(dataFilter)
            else:
                self.storage.append(dataFilter)

    async def get_data(self, interval=60):
        timestamp_min = (datetime.datetime.now().timestamp() * 1_000) - (60_000 * interval)
        # async with self.lock:
        index_data = [data for data in self.storage if data['trade_timestamp'] > timestamp_min]
        self.storage = index_data.copy()
        index_data.clear()

        return self.storage

class analysis:
    def __init__(self, websocket_data):
        self.websocket_data = websocket_data
        pprint.pprint(self.realtime_data)
        self.realtime_data = None
        pprint.pprint(self.realtime_data)
        self.ohlcv = pu.get_ohlcv(ticker=websocket_data['code'], interval='minute15', count=48)
        pprint.pprint(self.realtime_data)
        

    async def data_processing(self, interval :int=5, count :int=3):
        default = {'open':None,
                   'high':None,
                   'low':None,
                   'close':None,
                   'volume_ask':None,
                   'volume_bid':None,
                   'value_ask':None,
                   'value_bid':None,
                   'count_ask':None,
                   'count_bid':None,
                   'count_seller':None,
                   'count_buyer':None,
                   'V_bid_high_price':None,
                   'V_bid_low_price':None,
                   'V_ask_high_price':None,
                   'V_ask_low_price':None,
                   'execution_speed_bid':None,
                   'execution_speed_ask':None} 
        data_dict = {n: default.copy() for n in range(count)}
        print(sys._getframe().f_lineno)
        timestamp_now = datetime.datetime.now().timestamp() * 1_000
        timestamp_line = []
        print(sys._getframe().f_lineno)
        for n_A in range(count+1):
            timestamp_line.append(timestamp_now - (60_000 * n_A * interval))
        print(sys._getframe().f_lineno)
        for n_B in range(count):
            max_timestamp = timestamp_line[n_B]
            min_timestamp = timestamp_line[n_B+1]
            data_index = [d for d in self.websocket_data if d.get('trade_timestamp') and max_timestamp >= d['trade_timestamp'] > min_timestamp]
            if data_index:
                data_dict[n_B]['open'] = min(data_index, key=lambda x: x.get('trade_timestamp')).get('trade_price')
                data_dict[n_B]['high'] = max(data_index, key=lambda x: x.get('trade_price')).get('trade_price')
                data_dict[n_B]['low'] = min(data_index, key=lambda x: x.get('trade_price')).get('trade_price')
                data_dict[n_B]['close'] = max(data_index, key=lambda x: x.get('trade_timestamp')).get('trade_price')
                data_dict[n_B]['volume_ask'] = sum([d['volume_ask'] for d in data_index if 'volume_ask' in d])
                data_dict[n_B]['volume_bid'] = sum([d['volume_bid'] for d in data_index if 'volume_bid' in d])
                data_dict[n_B]['count_ask'] = sum([d['count_ask'] for d in data_index if 'count_ask' in d])
                data_dict[n_B]['value_ask'] = sum(item['trade_price'] * item['volume_ask'] for item in data_index)
                data_dict[n_B]['value_bid'] = sum(item['trade_price'] * item['volume_bid'] for item in data_index)
                data_dict[n_B]['count_bid'] = sum([d['count_bid'] for d in data_index if 'count_bid' in d])
                data_dict[n_B]['count_seller'] = sum(1 for d in data_index if 'count_ask' in d and d['count_ask'] > 0)
                data_dict[n_B]['count_buyer'] = sum(1 for d in data_index if 'count_bid' in d and d['count_bid'] > 0)

                ask_v = {}
                bid_v = {}
                for data in data_index:
                    bid_v[data['trade_price']] = bid_v.get(data['trade_price'], 0) + data['trade_price'] * data['volume_bid']
                    ask_v[data['trade_price']] = ask_v.get(data['trade_price'], 0) + data['trade_price'] * data['volume_ask']
                
                data_dict[n_B]['V_bid_high_price'] = max(bid_v, key=bid_v.get)
                data_dict[n_B]['V_bid_low_price'] = min(bid_v, key=bid_v.get)
                data_dict[n_B]['V_ask_high_price'] = max(ask_v, key=ask_v.get)
                data_dict[n_B]['V_ask_low_price'] = max(ask_v, key=ask_v.get)
                if data_dict[n_B]['count_buyer'] != 0:
                    data_dict[n_B]['execution_speed_bid'] = 60/data_dict[n_B]['count_buyer']
                    
                if data_dict[n_B]['count_seller'] != 0:
                    data_dict[n_B]['execution_speed_ask'] = 60/data_dict[n_B]['count_seller']
    
        self.realtime_data = data_dict

    async def case_1_UL(self):
        print(sys._getframe().f_lineno)
        await self.data_processing(interval=5, count=6)
        value_min = 500_000_000
        data_count = len(self.realtime_data.keys())
        data_keys = list(self.realtime_data.keys())
        whileEXIT = False
        pprint.pprint(self.realtime_data)

        n = 0
        while not whileEXIT:
            if n > max(data_keys)-1 or self.realtime_data[n]['close'] < self.realtime_data[n]['open'] or None is self.realtime_data[data_keys[-1]]['open']:
                whileEXIT = True
            elif n <= max(data_keys):
                open_close = self.realtime_data[n]['close'] > self.realtime_data[n+1]['close']
                value = (self.realtime_data[n]['value_ask'] + self.realtime_data[n]['value_bid']) >= value_min
                value_bid_high_low_price = self.realtime_data[n]['V_bid_high_price'] > self.realtime_data[n]['V_bid_low_price']
                value_bid_ask_high_price = self.realtime_data[n]['V_bid_high_price'] > self.realtime_data[n]['V_ask_high_price']
                if all(open_close, value, value_bid_ask_high_price, value_bid_high_low_price):
                    n +=1
                else:
                    whileEXIT = True
            await asyncio.sleep(0)
        if n < 3:
            return False
        else:
            Hours_ = [None, None, None, 12, 9, 6, 3]
            timeNow = datetime.datetime.now()
            timedelta = timeNow - datetime.timedelta(hours=Hours_[n])
            # delta_str = timedelta.strftime('%Y-%m-%d %H:%M:%S')
            close_price_max = max(self.ohlcv[self.ohlcv.index >= timedelta][:-1]['close'])
            close_price_real = self.websocket_data['close']
            bool_ = close_price_max <= close_price_real
            return bool_


    async def case_2_UL(self):
        print(sys._getframe().f_lineno)
        await self.data_processing(interval=1, count=3)
        if self.realtime_data[count-1]['open'] is not None:
            timeNow = datetime.datetime.now()
            timedelta = timeNow - datetime.timedelta(hours=6)            
            trade_speed_min = float(1)
            trade_value_min = 200_000_000

            trade_value_ = self.realtime_data[0]['value_bid'] > trade_value_min
            trade_speed_ = self.realtime_data[0]['execution_speed_bid'] <= trade_speed_min
            open_close_now_ = self.realtime_data[0]['open'] < self.realtime_data[0]['close']
            value_high_bid_ask = self.realtime_data[0]['V_bid_high_price'] > self.realtime_data[0]['V_ask_high_price']
            trade_later_data = self.realtime_data[0]['close'] > self.realtime_data[1]['close'] > self.realtime_data[2]['close']
            trade_price_max_ = max(self.ohlcv[self.ohlcv.index >= timedelta][:-1]['close']) < self.websocket_data['trade_price']

            all_bool = [trade_value_, trade_speed_, open_close_now_, value_high_bid_ask, trade_later_data, trade_price_max_]

            if all(all_bool):
                return True
            else:
                return False
            
class close_posision_price:
    """거래('long' or 'short')발생시 거래내역 정보를 저장하고 손절 or 익절 목표 단가를 반환한다."""
    
    position_info = {}

    def __init__(self, initial_dict=None):
        if initial_dict:
            self.reference_price.update(initial_dict)
    
    @classmethod
    async def trade_order_type(cls, open_position_info :dict):
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
    async def data_update(cls, trade_price :dict):
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
    async def target_price(cls, ticker, percent :float=0.012):
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

class MarketOrder:
    def __init__(self, ticker=None , target:int=10):
        self.ticker = ticker
        self.target = target
        self.balances = upbit.get_balances()
        self.MIN_TRADE_AMOUNT = 6_000
        self.MIN_KRW_BALANCE = 5_500

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

    async def Buy_order(self) -> int:
        amount = self.Get_MinAmount()

        if amount > 0 and self.ticker not in self.Get_HoldingTickers():
            try:
                upbit.buy_market_order(self.ticker, amount)
                position = {'code':self.ticker,
                            'market':'upbit',
                            'position':'long'}
                await close_posision_price.trade_order_type(open_position_info=position)
                Trade_data(ticker=self.ticker, amount=amount, tradeType='BUY')
                print(f'Order completed (Buy) : {self.ticker}')
            except EOFError as e:
                print(e)
        else:
            print(f'Order fail (Buy) : {self.ticker}')

    async def Sell_order(self) -> int:
        Balance_ = self.Get_Balances()
        index = next((index for index, Balance_ in enumerate(Balance_) if Balance_['code'] == self.ticker), None)
        amount = Balance_[index]['volume']
        if amount > 0 and self.ticker in self.Get_HoldingTickers():
            try:
                before_selling_KRW_ = int(upbit.get_balance('KRW'))
                upbit.sell_market_order(self.ticker, amount)
                after_selling_KRW_ = int(upbit.get_balance('KRW'))
                await close_posision_price.remove_ticker(self.ticker)
                sell_value = after_selling_KRW_ - before_selling_KRW_
                Trade_data(ticker=self.ticker, amount=sell_value, tradeType='SELL')
                print(f'Order complete (Sell): {self.ticker}')
            except EOFError as e:
                print(e)
        else:
            print(f'Order fail (Sell): {self.ticker}')


async def websocket(updater, queue, hour :int=2, dataType :str='trade'):
    """
    Note.
    dataType 를 ticker로 설정해서 개고생했다.
    """
    while True:
        tickers_all = await updater.get_data(type='target', rank=50)
        if tickers_all is not None:
            WM_ = pu.WebSocketManager(type=dataType, codes=tickers_all)
            TimeNow = datetime.datetime.now()
            WhileEXIT = (TimeNow + datetime.timedelta(hours=hour)).timestamp() * 1_000
            stop_timestamp = 0

            while stop_timestamp <= WhileEXIT:
                try:
                    data = WM_.get()
                    await queue.put(data)
                    stop_timestamp = float(data['trade_timestamp'])
                    await asyncio.sleep(0)
                except:
                    pass
            WM_.terminate()
        await asyncio.sleep(0)

async def updater_1(instance):
    while True:
        await instance.update()
        await asyncio.sleep(60*60*4)

async def monitoring(updater_ticker, queue, interval :int=2):
    storage = {}
    while True:
        tickers_target = await updater_ticker.get_data(type='target', rank=30)
        if tickers_target is not None:
            while not queue.empty():
                data = await queue.get()
                await close_posision_price.data_update({data['code']:data['trade_price']})
                try:
                    if data['trade_price'] < await close_posision_price.target_price(ticker=data['code']):
                        await MarketOrder(ticker=data['code']).Sell_order()
                except:
                    pass
                if data['code'] not in storage.keys():
                    storage[data['code']] = Data_Storage()
                    print(storage[data['code']])
                await storage[data['code']].data_update(data)
                queue.task_done()
                # await asyncio.sleep(0)    <<불필요하다. 이유는 await queue.get()에서 이미 비동기식으로 움직이고 있기 때문이다.
                # print(f'현재 11줄 번호 >>> {sys._getframe().f_lineno}')
            await asyncio.sleep(0)
            for ticker in tickers_target:
                if ticker in storage.keys():
                    print(sys._getframe().f_lineno)
                    print(sys._getframe().f_lineno)
                    print(sys._getframe().f_lineno)
                    # try:
                    print(ticker)
                    get_data = await storage[ticker].get_data()
                    print(get_data)
                    print(sys._getframe().f_lineno)
                    analysys_ = analysis(websocket_data=get_data)
                    print(sys._getframe().f_lineno)
                    case_1_check = await analysys_.case_1_UL()
                    print(sys._getframe().f_lineno)
                    case_2_check = await analysys_.case_2_UL()

                    check = [case_1_check, case_2_check]

                    if any(check):
                        await MarketOrder(ticker=ticker).Buy_order()
                    # print(sys._getframe().f_lineno)
                    await asyncio.sleep(0)
                    # except:
                    #     pass
        print(sys._getframe().f_lineno)
        await asyncio.sleep(interval)

async def main():
    tickers_ = get_tickers()
    updater_1_task = asyncio.create_task(updater_1(instance=tickers_))
    
    q_ = asyncio.Queue()
    websocket_task = asyncio.create_task(websocket(queue=q_, updater=tickers_))
    monitoring_task = asyncio.create_task(monitoring(queue=q_, updater_ticker=tickers_))

    await asyncio.gather(updater_1_task,
                         websocket_task,
                         monitoring_task)

if __name__ == "__main__":
    time_ = datetime.datetime.now()
    print(time_.strftime('%Y-%m-%d %H:%M:%S'))
    asyncio.run(main())

# %%
