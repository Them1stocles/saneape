#!/usr/bin/env python3
"""Test stock data fetching to diagnose I/O error"""

import yfinance as yf
import logging
import os
import sys
from datetime import datetime, timedelta

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_yfinance():
    """Test yfinance functionality"""
    ticker = "AAPL"
    
    print(f"Testing yfinance for ticker: {ticker}")
    print(f"Python version: {sys.version}")
    print(f"yfinance version: {yf.__version__}")
    print()
    
    try:
        # Test 1: Create ticker object
        print("1. Creating ticker object...")
        stock = yf.Ticker(ticker)
        print("✓ Ticker object created")
        
        # Test 2: Get basic info
        print("\n2. Getting stock info...")
        try:
            info = stock.info
            print(f"✓ Got info - Company: {info.get('longName', 'N/A')}")
        except Exception as e:
            print(f"✗ Error getting info: {e}")
        
        # Test 3: Get historical data
        print("\n3. Getting historical data...")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)  # Just 30 days for testing
        
        try:
            hist = stock.history(start=start_date, end=end_date)
            if not hist.empty:
                print(f"✓ Got {len(hist)} days of historical data")
                print(f"   Latest close: ${hist['Close'].iloc[-1]:.2f}")
            else:
                print("✗ Historical data is empty")
        except Exception as e:
            print(f"✗ Error getting history: {e}")
            import traceback
            traceback.print_exc()
            
        # Test 4: Check file system permissions
        print("\n4. Checking file system...")
        temp_file = "/tmp/yfinance_test.txt"
        try:
            with open(temp_file, 'w') as f:
                f.write("test")
            os.remove(temp_file)
            print("✓ File system write/read working")
        except Exception as e:
            print(f"✗ File system error: {e}")
            
        # Test 5: Check environment
        print("\n5. Environment check...")
        print(f"   HOME: {os.environ.get('HOME', 'Not set')}")
        print(f"   USER: {os.environ.get('USER', 'Not set')}")
        print(f"   PWD: {os.getcwd()}")
        
    except Exception as e:
        print(f"\n✗ General error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_yfinance()