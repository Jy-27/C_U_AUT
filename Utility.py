import json
from binance.client import Client
from binance.exceptions import BinanceAPIException
from pprint import pprint
import requests
import math
import time
import hmac
import hashlib
from Analysis import *
from collections import defaultdict
import nest_asyncio

# class Utility(Analysis):
class Utility(Analysis):
    def __init__(self, tickers):
        super().__init__(tickers=tickers)
        self.isPending: Dict[str, bool] = {}
        self.account_balance: Dict[str, Dict[str, int | float]] = None
        self.check_balance_optimal: Tuple[bool, float] = None
        self.position_stopper: Dict[str, Dict[str, dict]]= {}
        self.binance_account_info = None
        # self.real_time_range: Dict[int, int] = {1: 3}#, 3: 2}

    def init_client(self, config_path: str = '/Volumes/SSD_256GB/C_U_AUT/API/binance.json') -> tuple:
        """Load API keys from a JSON configuration file."""
        global client, api_key, api_secret
        with open(config_path, 'r') as file:
            config_data = json.load(file)
        api_key = config_data.get('apiKey')
        api_secret = config_data.get('secret')
        client = Client(api_key, api_secret)
    
    def get_account_balance(self, account_type: str = 'futures') -> dict:
        """Fetch account balance information for the specified account type."""
        if account_type == 'spot':
            self.binance_account_info = client.get_account()
            balances = self.binance_account_info.get('balances', [])
            
            account_data = {}
            for balance in balances:
                asset = balance.get('asset')
                free_balance = float(balance.get('free', 0))
                locked_balance = float(balance.get('locked', 0))
                
                if free_balance > 0 or locked_balance > 0:
                    account_data[asset] = {
                        'Free': free_balance,
                        'Locked': locked_balance
                    }
            self.account_balance = account_data
            return account_data
        
        elif account_type == 'futures':
            self.binance_account_info = client.futures_account()
            assets = self.binance_account_info.get('assets', [])
            
            account_data = {}
            for asset in assets:
                asset_name = asset.get('asset')
                wallet_balance = float(asset.get('walletBalance', 0))
                unrealized_profit = float(asset.get('unrealizedProfit', 0))
                
                if wallet_balance > 0 or unrealized_profit > 0:
                    account_data[asset_name] = {
                        'Wallet Balance': wallet_balance,
                        'Unrealized Profit': unrealized_profit
                    }
                    
            positions = client.futures_position_information()
            
            for position in positions:
                # 포지션 데이터가 있는 경우만 필터링
                if float(position['positionAmt']) != 0:
                    account_data[position['symbol']] = {
                        'positionAmt': float(position['positionAmt']),
                        'entryPrice': float(position['entryPrice']),
                        'breakEvenPrice': float(position['breakEvenPrice']),
                        'markPrice': float(position['markPrice']),
                        'unRealizedProfit': float(position['unRealizedProfit']),
                        'leverage': int(position['leverage']),
                        'isolatedMargin': float(position['isolatedMargin']),
                        'liquidationPrice': float(position['liquidationPrice']),
                        'marginType': str(position['marginType'])
                        }
                    
                    open_position = "LONG" if float(position['positionAmt']) > 0 else "SHORT"
                    position_columns = "highPrice" if open_position =="LONG" else "lowPrice"
                    self.position_stopper[position['symbol']] = {"position": "LONG" if float(position['positionAmt']) > 0 else "SHORT",
                                                     "entryPrice" : float(position['entryPrice']),
                                                     position_columns : float(position['entryPrice']),
                                                     "targetPrice" : None}
            self.account_balance = account_data
            return account_data

    def get_minimum_quantity(self, symbol: str) -> float:
        symbol = symbol.upper()
        url = 'https://fapi.binance.com/fapi/v1/exchangeInfo'
        
        try:
            response = requests.get(url)
            response.raise_for_status()  # HTTP 오류가 발생하면 예외를 발생시킵니다
            data = response.json().get('symbols')

            # 지정된 심볼의 필터 데이터를 찾습니다
            for symbol_data in data:
                if symbol_data.get('symbol') == symbol:
                    filters = symbol_data.get('filters')
                    min_qty = None
                    notional = None
                    
                    # 필터를 순회하여 최소 수량(minQty)과 최소 거래 금액(notional)을 찾습니다
                    for filter_item in filters:
                        if filter_item['filterType'] in ['LOT_SIZE', 'MARKET_LOT_SIZE']:
                            min_qty = float(filter_item.get('minQty'))
                        if filter_item['filterType'] == 'MIN_NOTIONAL':
                            notional = float(filter_item.get('notional'))
                    
                    if min_qty is None or notional is None:
                        raise ValueError("Required filter data not found.")
                    
                    # 현재 가격을 가져옵니다
                    try:
                        current_price = float(client.futures_symbol_ticker(symbol=symbol).get('price'))
                    except BinanceAPIException as e:
                        print(f"Error fetching price: {e}")
                        raise

                    # 최소 거래 금액과 현재 가격을 이용하여 최소 주문 수량을 계산합니다
                    min_order_value = notional / current_price
                    minimum_order_quantity = math.ceil(min_order_value / min_qty) * min_qty
                    if '.' in str(min_qty):
                        minimum_order_quantity = round(minimum_order_quantity, len(str(min_qty).split('.')[1]))
                    else:
                        minimum_order_quantity = round(minimum_order_quantity, 0)
                        
                    return minimum_order_quantity + float(min_qty)

        except requests.RequestException as e:
            print(f"HTTP request error: {e}")
        except ValueError as e:
            print(f"Value error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        return None

    def set_margin_leverage(self, symbol: str, leverage: int, margin_type: str="ISOLATED"):
        """
        Configure both margin type and leverage for a symbol.
        
        Parameters:
        - symbol: The trading symbol (e.g., 'ADAUSDT').
        - margin_type: The margin type to set ('ISOLATED' or 'CROSSED').
        - leverage: The leverage to set (e.g., 1, 10, 20, etc.).
        
        Returns:
        - Response from margin type change and leverage change APIs.
        """
        positions = client.futures_position_information()
        symbol = symbol.upper()
        margin_type = margin_type.upper()  # 'ISOLATED' or 'CROSSED'
        responses = {}

        # 설정된 마진 타입 변경
        for position in positions:
            if position.get('symbol') == symbol:
                margin_type_gen = {'ISOLATED':'ISOLATED',
                                   'CROSSED':'CROSS'}.get(margin_type, None)
                
                if str(position.get('marginType')).upper() != margin_type_gen:
                    try:
                        margin_response = client.futures_change_margin_type(symbol=symbol, marginType=margin_type)
                        responses['margin_type_change'] = margin_response
                        print(f"Margin type for {symbol} set to {margin_type}.")
                    except BinanceAPIException as e:
                        print(f"An error occurred while setting margin type: {e}")
                        responses['margin_type_change'] = str(e)

                if int(position.get('leverage')) != leverage:
                    try:
                        leverage_response = client.futures_change_leverage(symbol=symbol, leverage=leverage)
                        responses['leverage_change'] = leverage_response
                        print(f"Leverage for {symbol} set to {leverage}.")
                    except Exception as e:
                        print(f"An error occurred while setting leverage: {e}")
                        responses['leverage_change'] = str(e)

        return responses

    def update_isPending(self):
        """
        get_account_balance를 기준하여 position open 처리하려 하였으나,
        통신 시간의 차이에 따른 즉시 기준잡을 데이터가 없음. 이에 따른 기준점 생성.
        """
        # 기본적으로 모든 키에 대해 False로 설정
        if self.isPending:
            for key in self.isPending.keys():
                self.isPending[key] = False
        else:
            # 키가 있는 경우에 대해서만 True로 설정, 없는 경우 False로 설정
            for key in self.account_balance.keys():
                self.isPending[key] = key in self.account_balance

        return self.isPending

    def place_market_order(self, symbol: str, position: str, quantity: float, reduce: bool=False):
        """
            symbol : 쌍거래 Ticker정보, 
            position : 'LONG', 'SHORT',
            quantity : 주문 수량    (최수주문 수량계산 함수는 'get_minimum_quantity'),
            reduce : True(open) / False(close)
        """
        
        position = position.upper()
        symbol = symbol.upper()
        side = {'LONG':'BUY',
                'SHORT':'SELL'}.get(position, None)
        
        try:
            response = client.futures_create_order(
                symbol = symbol,
                side = side,  # 'BUY' 또는 'SELL'
                type = 'MARKET',
                quantity = quantity,
                reduce_only = reduce
            )
            print(f"Market order placed: {response}")
            
            self.isPending[symbol] = not reduce
            self.get_account_balance()
            
            if reduce:
                entry_price = self.account_balance.get(symbol, {}).get('entryPrice')
                self.position_stopper[symbol] = {'entryPrice':entry_price,
                                                 'targetPrice':None,
                                                 'position':side}
            elif not reduce:
                if self.position_stopper:
                    self.position_stopper[symbol] = None
            self.check_balance_optimal = self.check_optimal_balance(balance_ratio=0.4)
            return response
        
        except BinanceAPIException as e:
            print(f"An error occurred: {e}")

    def close_position(self, symbol: str='all'):
        """
        특정 종목(symbol) 또는 전체(All) 포지션을 종료하는 함수
        symbol: 종목(symbol) 이름 또는 'ALL' (모든 포지션 종료)
        """
        symbol = symbol.upper()  # 대문자로 변환하여 종목 일관성 유지
        account_balance = self.account_balance  # 계좌 잔고 및 포지션 정보 가져오기

        def close_single_position(symbol, position_info):
            """
            단일 종목 포지션 종료 처리 함수
            symbol: 종목(symbol) 이름
            position_info: 해당 종목의 포지션 정보
            """
            position_amount = float(position_info['positionAmt'])  # 현재 포지션 수량
            if position_amount == 0:
                print(f"{symbol}에 대한 열린 포지션이 없습니다.")
                return
            
            # 포지션이 음수면 숏 포지션이므로 매수로 종료, 양수면 롱 포지션이므로 매도로 종료
            position = 'LONG' if position_amount < 0 else 'SHORT'
            quantity = abs(position_amount)
            
            # 시장가 주문을 통해 포지션 종료
            self.place_market_order(symbol=symbol, position=position, quantity=quantity, reduce=True)
            self.isPending[symbol] = False
            print(f"{symbol} 포지션을 {position}로 {quantity} 개 종료했습니다.")

        if symbol != 'ALL':  # 단일 종목 종료
            if symbol in account_balance.keys():
                close_single_position(symbol, account_balance[symbol])
            else:
                print(f"{symbol}에 대한 포지션이 없습니다.")
        
        else:  # 'ALL'이 입력된 경우 모든 포지션 종료
            if len(account_balance) > 1:  # USDT 이외의 자산이 있는지 확인
                for sym, pos_info in account_balance.items():
                    if sym != 'USDT':
                        close_single_position(sym, pos_info)
            else:
                print("종료할 포지션이 없습니다.")

    def open_position(self, position: str, symbol: str):
        symbol = symbol.upper()
        isPending = self.isPending.get(symbol, False)
        self.check_balance_optimal = self.check_optimal_balance()
        if not self.account_balance:
            self.get_account_balance()
        if self.check_balance_optimal is not None and bool(self.check_balance_optimal[0]) and not isPending:
            Qty = self.get_minimum_quantity(symbol)

            "===== DEBUG ====="
            print(Qty)
            self.isPending[symbol] = True
            self.place_market_order(symbol=symbol, position=position, quantity=Qty)
        else:
            print(f'설정 잔액 부족 {self.check_balance_optimal}')
            
    def check_optimal_balance(self, balance_ratio: float = 0.45) -> tuple:
        """
        잔액 확인과 최적의 잔액을 계산하여 현재 잔액이 요구되는 잔액 이상인지 확인.
        
        Parameters:
        - balance_ratio: 계산에 사용할 비율 (기본값 0.3)
        
        Returns:
        - (bool, optimal_balance): 잔액이 요구되는 잔액을 충족하는지 여부와 최적 잔액
        """
        # 잔액이 없는 경우 계좌 잔액을 가져옴
        if not self.account_balance:
            self.get_account_balance()

        # USDT 잔액 가져오기
        usdt_balance = self.account_balance.get('USDT', {}).get('Wallet Balance', 0)
        total_entry_price = 0

        # 각 포지션에 대한 진입 가격 및 수량 계산
        if len(self.account_balance) >= 2:
            for key, data in self.account_balance.items():
                if key != 'USDT':
                    entry_price = float(data.get('entryPrice', 0))
                    position_qty = abs(float(data.get('positionAmt', 0)))
                    total_entry_price += entry_price * position_qty

        # 예상 잔액 계산 (USDT 잔액에서 모든 포지션의 진입 가격 합을 뺌)
        expected_balance = usdt_balance - total_entry_price

        # 최적의 잔액을 계산하는 로직
        target_amount = usdt_balance
        multiplier_list = [2, 5]
        initial_balance = 10
        current_balance = initial_balance
        max_balance_below_target = None
        optimal_balance = None

        while True:
            for multiplier in reversed(multiplier_list):
                potential_balance = current_balance * balance_ratio
                if current_balance <= target_amount:
                    if max_balance_below_target is None or current_balance > max_balance_below_target:
                        max_balance_below_target = current_balance
                        optimal_balance = potential_balance
                current_balance *= multiplier
                if current_balance > target_amount:
                    required_balance = optimal_balance
                    break
            if current_balance > target_amount:
                break

        # 예상 잔액이 요구되는 잔액 이상인지 여부를 반환
        is_balance_sufficient = expected_balance >= required_balance
        return is_balance_sufficient, optimal_balance

    async def _position_stopper(self, ratio: float = 0.7):
        standard_ratio = 0.02
        
        while True:
            # 큐에 데이터가 없으면 바로 처리하지 않도록 함
            if len(self.trade_data_queue) < 100 or not self.position_stopper:
                await asyncio.sleep(5)
                print(self.position_stopper)
                continue
            
            # position_stopper에서 관리되는 모든 심볼에 대해 처리
            print(f"\n{datetime.datetime.now()}")
            
            for symbol, data in self.position_stopper.items():
                real_data_100_items = list(self.trade_data_queue)[-100:]
                symbol_items = [item for item in real_data_100_items if item[0] == symbol]
                values = [item[1] for item in symbol_items]
                
                if not values:
                    continue
                
                max_value = max(values)
                min_value = min(values)
                last_price = values[-5:]
                
                entryPrice = self.position_stopper[symbol]['entryPrice']
                
                pprint(self.position_stopper[symbol])
                
                
                if data['position'] == 'LONG':
                    highPrice = max(self.position_stopper[symbol]['highPrice'], max_value)
                    calculator_target = highPrice + ratio * (highPrice - entryPrice)
                    targetPrice = min(calculator_target, highPrice * (1 - standard_ratio))
                    self.position_stopper[symbol]['targetPrice'] = targetPrice
                    self.position_stopper[symbol]['highPrice'] = highPrice

                elif data['position'] == 'SHORT':
                    lowPrice = min(self.position_stopper[symbol]['lowPrice'], min_value)
                    calculator_target = entryPrice - ratio * (entryPrice - lowPrice)
                    targetPrice = max(calculator_target, lowPrice * (1 + standard_ratio))
                    self.position_stopper[symbol]['targetPrice'] = targetPrice
                    self.position_stopper[symbol]['lowPrice'] = lowPrice
    
                # 포지션 정보 업데이트
                self.position_stopper[symbol]['targetPrice'] = targetPrice
                
                # 목표가와 실시간 가격 비교 후 포지션 청산
                if (data['position'] == 'LONG' and targetPrice > min(last_price)) or \
                    (data['position'] == 'SHORT' and targetPrice < max(last_price)):
                    self.close_position(symbol=symbol)
                    # del self.position_stopper[symbol]
    
            await asyncio.sleep(5)

    async def _order_signal(self):
        while True:
            case1 = self.analysis_case1()

            # === DEBUG ZONE ===
            if case1 is not None:
                for symbol in self.tickers:
                    symbol = symbol.upper()
                    for bool_ in [True, False]:
                        case1_data = case1.get(symbol, {}).get(bool_, {})
                        if case1_data != {}:
                            position = {True:'LONG',
                                        False:'SHORT'}.get(bool_)
                            self.open_position(symbol=symbol, position=position)
                await asyncio.sleep(5)
                

async def main():
    tickers = ['btcusdt', 'xrpusdt', 'solusdt', 'dogeusdt', 'hifiusdt', 'bnbusdt']
    instance_ = Utility(tickers=tickers)

    path = '/Users/nnn/Desktop/API/binance.json'
    
    instance_.init_client(path)
    pprint(instance_.get_account_balance())
    
    instance_.set_margin_leverage(symbol=tickers[3], leverage=1)
    instance_.open_position(position='short', symbol=tickers[1])
    instance_.open_position(position='short', symbol=tickers[1])
    instance_.get_account_balance()
    pprint(instance_.position_stopper)
    
    tasks = [asyncio.create_task(instance_.fetch_ohlcv_data()),
            asyncio.create_task(instance_.get_max_min_for_ranges()),
            asyncio.create_task(instance_.update_data_periodically()),
            asyncio.create_task(instance_._position_stopper())
            ]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(main())