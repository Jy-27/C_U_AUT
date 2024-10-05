from DataProcessor import *       
import nest_asyncio
import datetime
from pprint import pprint

class Analysis(EnhancedDataHandler):
    def __init__(self, tickers):
        super().__init__(tickers=tickers)
        self.real_time_range: Dict[int, int] = {1: 6, 3: 2, 5: 4, 15: 4}    #check_high_low_exceedance의 래핑에 영향을 끼친다.
        
    def analysis_case1(self):
        # 가격 변동 트렌드를 확인하는 함수
        def check_price_trend(prices):
            # 가격이 상승하는지 확인
            is_increasing = all(prices[i] <= prices[i + 1] for i in range(len(prices) - 1))
            # 가격이 하락하는지 확인
            is_decreasing = all(prices[i] >= prices[i + 1] for i in range(len(prices) - 1))
            
            if is_increasing:
                return False  # 가격 상승: limit_trader_value가 크면 'SHORT'
            elif is_decreasing:
                return True   # 가격 하락: limit_trader_value가 작으면 'LONG'
            
            return None  # 명확한 트렌드가 없음

        # 고가 및 저가를 초과했는지 확인하는 함수
        def check_high_low_exceedance(interval, ticker):
            interval_str = {1:"12H",
                            3:"9H",
                            5:"6H",
                            15:"3H"}.get(interval, "24H")
            
            target_data = self.max_min_for_ranges[ticker][interval_str]
            current_close_price = self.processed_data[ticker.upper()][interval][interval]['OHLCVV']['close']

            if not target_data or not current_close_price:
                return None

            price_low = target_data['low']
            price_high = target_data['high']
            
            if current_close_price > price_high:
                return True  # 가격이 고가를 초과함
            elif current_close_price < price_low:
                return False  # 가격이 저가를 밑돌음
            
            return None  # 범위를 벗어나지 않음

        # 거래량 우위를 확인하는 함수
        def check_trade_volume_dominance(interval, ticker):
            limit_volume = self.processed_data[ticker.upper()][interval][interval]['limit']['value']
            market_volume = self.processed_data[ticker.upper()][interval][interval]['market']['value']
            
            if market_volume > limit_volume:
                return True  # 시장 거래량이 우세
            elif market_volume < limit_volume:
                return False  # 제한 거래량이 우세
            
            return None  # 우위가 명확하지 않음

        # 데이터가 완전히 채워져 있는지 확인하는 함수
        def is_data_fully_populated(data):
            def check_dict_recursively(d):
                if not isinstance(d, dict) or not d:
                    return False  # 값이 딕셔너리가 아니거나 빈 딕셔너리인 경우
                
                for key, value in d.items():
                    if isinstance(value, dict):
                        if not check_dict_recursively(value):
                            return False  # 하위 딕셔너리에서 빈 값이 발견되면 False 반환
                    elif value == {}:
                        return False  # 빈 딕셔너리 값이 발견되면 False 반환
                
                return True
            
            return check_dict_recursively(data)

        # processed_data가 채워졌는지 확인
        if not is_data_fully_populated(self.processed_data):
            return None

        result = {}
        
        for ticker in self.tickers:
            ticker = ticker.upper()
            result[ticker] = {True: [], False: []}  # True와 False 각각에 대해 빈 리스트 초기화

            for interval in self.real_time_range:
                close_prices = []
                # 가격 데이터를 수집
                
                start_and_step = interval
                stop_ = interval * self.real_time_range.get(interval)
                
                for minute in range(start_and_step, stop_, start_and_step):
                    price = self.processed_data[ticker][interval][minute]['OHLCVV']['close']
                    close_prices.append(price)

                # 조건 평가
                condition1 = check_price_trend(close_prices)
                condition2 = check_high_low_exceedance(interval, ticker)
                condition3 = check_trade_volume_dominance(interval, ticker)
                # condition4 = check_stick_body_size(interval, ticker)

                # 조건이 모두 동일할 경우 결과 누적
                for bool_ in [True, False]:
                    if condition1 == condition2 == condition3 == bool_:
                        result[ticker][bool_].append(interval)  # interval을 리스트에 추가
                    else:
                        pass
        return result

    def TEST_PRINT(self, data):
        for ticker, bool_dict in data.items():
            for bool_value, lst in bool_dict.items():
                if lst:  # 리스트에 값이 있으면 True 반환
                    return True
        return False  # 리스트가 모두 비어 있으면 False 반환

    async def case_print(self):
        #TEST ZONE
        while True:
            case_1 = self.analysis_case1()
            if case_1 and self.TEST_PRINT(data=case_1):
                print(f"{case_1} - {datetime.datetime.now()}")
            await asyncio.sleep(5)

async def main():
    """메인 함수: 비동기 작업을 생성하고 실행합니다."""
    tickers = ['btcusdt', 'xrpusdt', 'solusdt', 'dogeusdt', 'hifiusdt', 'bnbusdt']
    handler = Analysis(tickers=tickers)
    pprint(handler.__dict__)
    print(tickers)
    print('START!')
    tasks = [
        asyncio.create_task(handler.get_max_min_for_ranges()),
        asyncio.create_task(handler.connect_websocket()),  # 웹소켓 연결
        asyncio.create_task(handler.fetch_ohlcv_data()),   # OHLCV 데이터 가져오기
        asyncio.create_task(handler.update_data_periodically()),  # 데이터 주기적 업데이트
        asyncio.create_task(handler.case_print()),
    ]
    await asyncio.gather(*tasks)  # 모든 비동기 작업 실행

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(main())