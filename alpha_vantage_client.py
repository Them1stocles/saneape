import requests
import logging
import time
import os
from datetime import datetime

class AlphaVantageClient:
    BASE_URL = "https://www.alphavantage.co/query"
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("ALPHAVANTAGE_API_KEY")
        if not self.api_key:
            logging.warning("ALPHAVANTAGE_API_KEY not found. Some features may be limited.")
        
        # Rate limiting: AlphaVantage free tier allows 5 calls per minute
        self.last_call_time = 0
        self.min_interval = 15.0  # 15 seconds between calls to be safe (4 calls/min)
        
    def _wait_for_rate_limit(self):
        """Ensure we don't exceed rate limits"""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            logging.info(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_call_time = time.time()

    def fetch_daily_adjusted(self, symbol):
        """Fetch daily adjusted time series data"""
        if not self.api_key:
            return None, "No API key provided"
            
        self._wait_for_rate_limit()
        
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "compact",  # 100 data points is enough for recent analysis
            "apikey": self.api_key
        }
        
        try:
            response = requests.get(self.BASE_URL, params=params)
            data = response.json()
            
            if "Note" in data:
                # API limit reached
                return None, f"API Limit Reached: {data['Note']}"
            
            if "Error Message" in data:
                return None, f"API Error: {data['Error Message']}"
                
            if "Time Series (Daily)" not in data:
                return None, "No time series data found"
                
            return data["Time Series (Daily)"], None
            
        except Exception as e:
            return None, str(e)

    def fetch_company_overview(self, symbol):
        """Fetch fundamental data (P/E, EPS, etc.)"""
        if not self.api_key:
            return None, "No API key provided"
            
        self._wait_for_rate_limit()
        
        params = {
            "function": "OVERVIEW",
            "symbol": symbol,
            "apikey": self.api_key
        }
        
        try:
            response = requests.get(self.BASE_URL, params=params)
            data = response.json()
            
            if "Note" in data:
                return None, f"API Limit Reached: {data['Note']}"
                
            if not data or "Symbol" not in data:
                return None, "No fundamental data found"
                
            return data, None
            
        except Exception as e:
            return None, str(e)
