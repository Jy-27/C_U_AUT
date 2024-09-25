import asyncio
import datetime
import json
import os
import requests
import websockets
import re
from collections import deque, defaultdict
from typing import List, Union, Dict, Tuple, Any
from pprint import pprint


class BinanceDataHandler:
    def __init__(self, tickers: Union[List[str], str] = ['btcusdt', 'ethusdt', 'xrpusdt', 'solusdt']):
        self.tickers: List[str] = tickers if isinstance(tickers, list) else [tickers]
        self.trade_data_queue: deque[Tuple[str, float, float, int, int, bool, float]] = deque()
        self.ohlc_data: defaultdict[str, defaultdict[str, Any]] = defaultdict(lambda: defaultdict(dict))
        self.scheduled_save_minutes = 30  # minutes
        self.current_time = None
        self.ohlc_intervals = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]
        self.ohlc_last_update_time: defaultdict[str, datetime.datetime] = defaultdict(lambda: datetime.datetime.min)  # 타입 힌트 추가
        self.websocket_columns = ["Symbol", "Price", "Quantity", "Number of trades", "Trade Time", "Maker flag", "Trade value"]
        self.ohlc_columns = [
            "Open Time", "Open", "High", "Low", "Close", "Volume",
            "Close Time", "Quote Asset Volume", "Number of Trades",
            "Taker Buy Base Asset Volume", "Taker Buy Quote Asset Volume", "Ignore"
        ]

    async def connect_websocket(self):
        """
        Connects to Binance WebSocket to receive real-time trade data.
        """
        url_base = "wss://fstream.binance.com/stream?streams="
        url = url_base + "/".join(f"{ticker.lower()}@aggTrade" for ticker in self.tickers)

        async with websockets.connect(url) as websocket:
            try:
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)

                    # Convert incoming data to desired format
                    trade_data = data['data']
                    trade_value = float(trade_data['p']) * float(trade_data['q'])  # Trade value
                    trade_count = trade_data['l'] - trade_data['f'] + 1  # Trade count

                    formatted_trade: Tuple[str, float, float, int, int, bool, float] = (
                        trade_data['s'],   # Symbol
                        float(trade_data['p']),  # Price
                        float(trade_data['q']),  # Quantity
                        int(trade_count),  # Number of trades
                        int(trade_data['T']),  # Trade time
                        bool(trade_data['m']),  # Maker flag
                        float(trade_value)  # Trade value
                    )

                    self.trade_data_queue.append(formatted_trade)
            except websockets.ConnectionClosed as e:
                print(f"WebSocket connection closed: {e}")
            except Exception as e:
                print(f"Error: {e}")

    def _get_ohlcv_fetch_params(self, interval: str) -> Tuple[int, datetime.timedelta]:
        """
        Calculates the number of records to fetch and the fetch frequency based on the interval.
        """
        match_number = re.search(r'\d+', interval)
        match_unit = re.search(r'[a-zA-Z]+', interval)

        if not match_number or not match_unit:
            raise ValueError(f"Invalid interval: {interval}")

        num = float(match_number.group(0))
        unit = match_unit.group(0)
        factor = 0.2

        unit_params = {
            'm': (1440, datetime.timedelta(minutes=factor * num)),  # 24 hours
            'h': (48, datetime.timedelta(hours=factor * num)),      # 48 hours
            'd': (30, datetime.timedelta(days=factor * num)),       # 30 days
            'w': (52, datetime.timedelta(weeks=factor * num)),      # 52 weeks
            'M': (12, datetime.timedelta(days=7))                   # 12 months
        }.get(unit)

        if unit_params:
            records_to_fetch = int(unit_params[0] / num)
            return records_to_fetch, unit_params[1]
        else:
            raise ValueError(f"Invalid time unit in interval: {unit}")

    async def fetch_ohlcv_data(self):
        """
        Fetches OHLCV data from Binance API at periodic intervals.
        """
        url = "https://api.binance.com/api/v3/klines"

        while True:
            self.current_time = datetime.datetime.now()

            for interval in self.ohlc_intervals:
                record_count, update_frequency = self._get_ohlcv_fetch_params(interval)

                # Check if enough time has passed to fetch new data
                if not self.ohlc_last_update_time[interval] or \
                        (self.current_time > self.ohlc_last_update_time[interval] + update_frequency):
                    
                    for ticker in self.tickers:
                        params = {'symbol': ticker.upper(), 'interval': interval, 'limit': record_count}
                        
                        try:
                            response = requests.get(url, params=params)
                            response.raise_for_status()
                            ohlcv_data = [[float(value) for value in entry] for entry in response.json()]
                            self.ohlc_data[ticker.upper()][interval] = ohlcv_data
                            self.ohlc_last_update_time[interval] = self.current_time
                        except requests.RequestException as e:
                            print(f"Failed to fetch OHLCV data for {ticker} at {interval}: {e}")
                        await asyncio.sleep(0.2)  # To avoid hitting rate limits

            await asyncio.sleep(1)  # Fetch every minute

    async def save_trade_data_periodically(self):
        """
        Processes and saves trade data at regular intervals.
        """
        while True:
            current_time = datetime.datetime.now()
            target_time = (current_time - datetime.timedelta(minutes=self.scheduled_save_minutes)).timestamp() * 1_000
            data_to_save = []

            while self.trade_data_queue and self.trade_data_queue[0][4] <= target_time:
                data_to_save.append(self.trade_data_queue.popleft())

            if len(data_to_save) >= 5000:
                save_directory = os.path.join(os.getcwd(), 'WebSocketTradeData')
                os.makedirs(save_directory, exist_ok=True)
                file_name = f"{int(current_time.timestamp())}.json"
                file_path = os.path.join(save_directory, file_name)

                with open(file_path, 'w') as file:
                    json.dump(data_to_save, file, indent=2)

                data_to_save.clear()

            await asyncio.sleep(1800)  # Wait 30 minutes before next save

    async def monitor_data(self):
        """
        Periodically prints the current state of OHLCV and trade data.
        """
        while True:
            pprint(self.ohlc_data)
            pprint(self.trade_data_queue)
            await asyncio.sleep(5)

async def main():
    tickers = ['btcusdt', 'xrpusdt', 'ethusdt', 'solusdt', 'dogeusdt', 'hifiusdt']
    handler = BinanceDataHandler(tickers=tickers)

    websocket_task = asyncio.create_task(handler.connect_websocket())
    ohlcv_task = asyncio.create_task(handler.fetch_ohlcv_data())
    save_task = asyncio.create_task(handler.save_trade_data_periodically())
    monitor_task = asyncio.create_task(handler.monitor_data())

    await asyncio.gather(websocket_task,
                         ohlcv_task,
                         save_task,
                         monitor_task)  # monitor_task optional

if __name__ == "__main__":
    asyncio.run(main())