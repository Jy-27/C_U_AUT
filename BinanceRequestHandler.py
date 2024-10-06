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


class BinanceRequestHandler:
    def __init__(self):
        self.url = None
        self.config_path = None
        self.api_key = None
        self.api_secret = None
        self.client = None
    
    def update_url(self, url: str):
        self.url = url
        
    def update_config_path(self, path: str):
        self.config_path = path
        
    def update_api_client(self):
        try:
            with open(self.config_path, 'r') as file:
                config_data = json.load(file)
                api_key = config_data.get('apiKey')
                api_secret = config_data.get('secret')
                self.client = Client(api_key, api_secret)
        except FileNotFoundError:
            print("Config file not found.")
        except PermissionError:
            print("Permission denied to access config file.")
        except OSError as e:
            print(f"OS error occurred: {e}")


    
    def init_client(self, config_path: str = '/Volumes/SSD_256GB/C_U_AUT/API/binance.json') -> tuple:
        """Load API keys from a JSON configuration file."""
        global client, api_key, api_secret
        with open(config_path, 'r') as file:
            config_data = json.load(file)