import requests
import Utility

class FuturesTicker(Utility):
    def __init__(self):
        self.tickers = None
        self.url = 'https://fapi.binance.com/fapi/v1/ticker/price'
        self.get_data = None

    def get_data(self):
        response = response.get(self.url)
        data = response.json()
        self.get_data = data
        return data
    
    def isValidTicker(self, radio :float = 0.25, symbol: str, tetherBalance: float):
        self.get_account_balance()
        symbol = symbol.upper()
        
        for data in self.get_data():
            if str(data.get('symbol')).upper().endswith('USDT'):
                price = float(data.get('price'))
                