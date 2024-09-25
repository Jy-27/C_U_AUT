import asyncio
import datetime
import numpy as np
from typing import List, Union, Dict, Tuple
from pprint import pprint
from collections import defaultdict
from DataHandler import BinanceDataHandler

class EnhancedDataHandler(BinanceDataHandler):
    def __init__(self, tickers: Union[List[str], str] = ['btcusdt', 'ethusdt', 'xrpusdt', 'solusdt']):
        super().__init__(tickers=tickers)
        self.real_time_range: Dict[int, int] = {1: 6, 3: 2, 5: 4, 15: 4, 30:4}
        # self.real_time_range: Dict[int, int] = {1: 6, 3: 6, 5: 4, 15: 4, 30:4}
        self.processed_data: Dict[str, Dict[int, Dict[str, Dict[str, float]]]] = defaultdict(lambda: defaultdict(dict))
        self.is_data_full: bool = False
        self.scheduled_save_minutes: int = self._calculate_scheduled_minutes()
        self.max_min_for_ranges = defaultdict(lambda: defaultdict(dict))

    def _calculate_scheduled_minutes(self) -> int:
        """최대 시간 간격과 그에 대한 데이터 건수를 기반으로 스케줄링 분 단위를 계산합니다."""
        max_interval = max(self.real_time_range.keys())
        max_count = self.real_time_range[max_interval]
        return max_interval * max_count

    def _is_last_entry_empty(self) -> bool:
        """처리된 데이터의 가장 최근 항목이 비어있는지 확인합니다."""
        if not self.processed_data:
            return True
        latest_ticker_data = self.processed_data.get(self.tickers[0].upper(), {})
        if not latest_ticker_data:
            return True
        latest_interval = max(latest_ticker_data.keys())
        latest_entry = latest_ticker_data.get(latest_interval, {})
        return not any(latest_entry.values())

    def has_no_empty_dicts(self, d: Dict) -> bool:
        """중첩된 딕셔너리에서 빈 딕셔너리({})가 없으면 True를 반환하는 함수."""
        def contains_empty_dict(d: Dict) -> bool:
            """중첩된 딕셔너리에서 빈 딕셔너리({})가 존재하는지 검사하는 내부 함수."""
            if isinstance(d, dict):
                for value in d.values():
                    if isinstance(value, dict):
                        if not value:
                            return True
                        if contains_empty_dict(value):
                            return True
            return False
        self.is_data_full = not contains_empty_dict(d)
        return self.is_data_full

    def _extract_data(self, interval_minutes: int, data_array: np.ndarray) -> Dict[str, Dict[int, Dict[str, Dict[str, float]]]]:
        """특정 시간 간격에 대해 데이터를 처리합니다."""

        if self.current_time is None:
            return self.processed_data

        # 타겟 시간 범위 생성 (시작과 끝 시간)
        time_ranges = [
            (
                (self.current_time - datetime.timedelta(minutes=interval_minutes * (i + 1))).timestamp() * 1_000,
                (self.current_time - datetime.timedelta(minutes=interval_minutes * i)).timestamp() * 1_000
            )
            for i in range(self.real_time_range.get(interval_minutes, 7))
        ]

        processed: Dict[str, Dict[int, Dict[str, Dict[str, float]]]] = defaultdict(lambda: defaultdict(dict))
        tickers = [ticker.upper() for ticker in self.tickers]

        for ticker in tickers:
            ticker_filter = data_array[:, 0] == ticker
            ticker_data: Dict[int, Dict[str, Dict[str, float]]] = {}

            for idx, (start_time, end_time) in enumerate(time_ranges):
                # 시간 필터 생성
                time_filter = (data_array[:, 4] > start_time) & (data_array[:, 4] <= end_time)
                interval_data: Dict[str, Dict[str, float]] = self._process_interval_data(data_array, ticker_filter, time_filter)

                # OHLCVV 데이터 처리
                ohlcv_data = data_array[ticker_filter & time_filter]
                if ohlcv_data.size > 0:
                    interval_data['OHLCVV'] = {
                        'open': ohlcv_data[0, 1],
                        'high': np.max(ohlcv_data[:, 1]),
                        'low': np.min(ohlcv_data[:, 1]),
                        'close': ohlcv_data[-1, 1],
                        'value': np.sum(ohlcv_data[:, 6]),
                        'volume': np.sum(ohlcv_data[:, 2])
                    }

                # 처리된 데이터를 시간 간격에 맞게 저장
                ticker_data[interval_minutes * (idx + 1)] = interval_data

            if ticker_data:
                self.processed_data[ticker][interval_minutes] = ticker_data

            self.is_data_full = self.has_no_empty_dicts(self.processed_data)
        
        return self.processed_data

    def _process_interval_data(self, data_array: np.ndarray, ticker_filter: np.ndarray, time_filter: np.ndarray) -> Dict[str, Dict[str, float]]:
        """시간 필터에 따른 데이터 처리를 수행합니다."""
        interval_data: Dict[str, Dict[str, float]] = {}

        for is_limit in [True, False]:
            trade_type = 'limit' if is_limit else 'market'
            trade_filter = data_array[:, 5] == is_limit
            filtered_data = data_array[ticker_filter & time_filter & trade_filter]

            if filtered_data.size > 0:
                interval_data[trade_type] = {
                    'volume': np.sum(filtered_data[:, 2]),
                    'value': np.sum(filtered_data[:, 6]),
                    'trades': np.count_nonzero(filtered_data[:, 3])
                }

        return interval_data

    async def get_max_min_for_ranges(self):
        while True:
            if self.current_time is None:
                await asyncio.sleep(5)
                continue
            result = {}
            now = int(self.current_time.timestamp() * 1000)  # 현재 시간(ms)
            one_minute_ago = now - 1 * 60 * 1000
            ranges = [
                (one_minute_ago - 12 * 60 * 60 * 1000, one_minute_ago, "12H"),
                (one_minute_ago - 9 * 60 * 60 * 1000, one_minute_ago, "9H"),
                (one_minute_ago - 6 * 60 * 60 * 1000, one_minute_ago, "6H"),
                (one_minute_ago - 3 * 60 * 60 * 1000, one_minute_ago, "3H")
            ]

            for ticker in self.tickers:
                ticker = ticker.upper()
                ohlc_data = self.ohlc_data.get(ticker.upper(), {}).get('1m', [])
                result[ticker] = {}
                
                if not ohlc_data:
                    continue

                data = np.array(ohlc_data)
                
                if data.ndim != 2 or data.shape[1] < 4:
                    print(f"Data for {ticker} is not in the expected format. Skipping...")
                    continue

                for start, end, interval in ranges:
                    data_filter = (data[:, 0] > start) & (data[:, 0] <= end)
                    filtered_data = data[data_filter]

                    if filtered_data.size == 0:
                        continue

                    highs = [float(candle[2]) for candle in filtered_data]
                    lows = [float(candle[3]) for candle in filtered_data]

                    max_high = max(highs) if highs else None
                    min_low = min(lows) if lows else None

                    result[ticker][interval] = {'high': max_high, 'low': min_low}
                    self.max_min_for_ranges = result
                    # pprint(self.max_min_for_ranges)
            await asyncio.sleep(60)

    async def update_data_periodically(self):
        """데이터를 주기적으로 업데이트하고 출력합니다."""
        while True:
            try:
                if not self.trade_data_queue:
                    await asyncio.sleep(5)
                    continue

                # 데이터 배열로 변환
                data_array = np.array(self.trade_data_queue, dtype=object)
                for interval in self.real_time_range.keys():
                    # 데이터 처리
                    self._extract_data(interval_minutes=interval, data_array=data_array)
                    # 데이터 출력 (DEBUG ZONE)
                    # pprint(self.processed_data.keys())

                await asyncio.sleep(5)  # 간격을 두고 대기
            except Exception as e:
                print(f"Error in update_data_periodically: {e}")

async def main():
    """메인 함수: 비동기 작업을 생성하고 실행합니다."""
    tickers = ['btcusdt', 'xrpusdt', 'solusdt', 'dogeusdt', 'hifiusdt', 'bnbusdt']
    handler = EnhancedDataHandler(tickers=tickers)
    tasks = [
        asyncio.create_task(handler.get_max_min_for_ranges()),
        asyncio.create_task(handler.connect_websocket()),  # 웹소켓 연결
        asyncio.create_task(handler.fetch_ohlcv_data()),   # OHLCV 데이터 가져오기
        asyncio.create_task(handler.update_data_periodically())  # 데이터 주기적 업데이트
    ]
    await asyncio.gather(*tasks)  # 모든 비동기 작업 실행

if __name__ == "__main__":
    asyncio.run(main())