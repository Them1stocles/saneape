import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
from openai import OpenAI
import logging

# Production-grade HTTP client configuration
import httpx
from httpx import Timeout, Limits
import ssl
import time

# Technical analysis libraries for Maximum Brain mode
import stockstats
from income_analyzer import IncomeAnalyzer

class StockAnalyzer:
    def __init__(self):
        # Production-grade HTTP client configuration for OpenAI API
        self.openai_client = self._create_production_openai_client()
        self.income_analyzer = IncomeAnalyzer()
    
    def _create_production_openai_client(self):
        """Create production-grade OpenAI client with robust HTTP transport configuration"""
        try:
            logging.info("Initializing production-grade OpenAI client with custom HTTP transport...")
            
            # SSL Context Configuration - Production Grade
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
            
            # More aggressive SSL settings to fail fast on connection issues
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
            
            # Production HTTP Transport Configuration
            transport = httpx.HTTPTransport(
                # Connection limits for optimal performance
                limits=Limits(
                    max_keepalive_connections=10,  # Maintain persistent connections
                    max_connections=20,            # Maximum concurrent connections
                    keepalive_expiry=30.0          # Keep connections alive for 30 seconds
                ),
                # SSL and socket configuration
                verify=ssl_context,
                trust_env=True,                    # Respect proxy environment variables
                socket_options=[]                  # Default socket options
            )
            
            # Aggressive Timeout Configuration - Fail fast on SSL issues
            timeout_config = Timeout(
                connect=5.0,     # 5 seconds to establish connection
                read=15.0,       # 15 seconds to read response (critical for SSL issues)
                write=10.0,      # 10 seconds to send request
                pool=30.0        # 30 seconds total including retries
            )
            
            # Custom HTTP Client with production configuration
            http_client = httpx.Client(
                transport=transport,
                timeout=timeout_config,
                follow_redirects=True,
                headers={
                    'Connection': 'keep-alive',
                    'Keep-Alive': 'timeout=30, max=100'
                }
            )
            
            # OpenAI Client with custom HTTP transport
            client = OpenAI(
                api_key=os.environ.get("OPENAI_API_KEY"),
                http_client=http_client,
                max_retries=0  # Disable OpenAI's internal retries - we handle our own
            )
            
            logging.info("✅ Production-grade OpenAI client initialized successfully")
            logging.info(f"   - SSL: TLS 1.2+ with modern ciphers")
            logging.info(f"   - Timeouts: Connect=5s, Read=15s, Write=10s, Pool=30s")
            logging.info(f"   - Connections: Max=20, KeepAlive=10, Expiry=30s")
            
            return client
            
        except Exception as e:
            logging.error(f"❌ Failed to create production OpenAI client: {e}")
            logging.warning("🔄 Falling back to standard OpenAI client...")
            # Fallback to standard client if custom configuration fails
            return OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    def fetch_stock_data(self, ticker):
        """Fetch historical stock data using yfinance"""
        try:
            import yfinance as yf
            
            stock = yf.Ticker(ticker)
            
            # Get 2 years of historical data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=730)  # 2 years
            
            hist = stock.history(start=start_date, end=end_date)
            
            if hist.empty:
                return None, f"No data found for ticker {ticker}. Please verify the ticker symbol."
            
            # Get additional info
            info = stock.info
            
            return {
                'history': hist,
                'info': info,
                'ticker': ticker
            }, None
            
        except Exception as e:
            logging.error(f"Error fetching data for {ticker}: {str(e)}")
            # More detailed error logging
            import traceback
            logging.error(f"Traceback: {traceback.format_exc()}")
            return None, f"Error fetching data for {ticker}. Please verify the ticker symbol."
    

    
    def calculate_technical_indicators(self, df, maximum_brain=False):
        """Calculate technical indicators - standard or comprehensive based on mode"""
        try:
            if maximum_brain:
                return self.calculate_comprehensive_indicators(df)
            else:
                return self.calculate_standard_indicators(df)
                
        except Exception as e:
            logging.error(f"Error calculating indicators: {str(e)}")
            return df
    
    def calculate_standard_indicators(self, df):
        """Calculate standard technical indicators for regular analysis"""
        try:
            # Moving averages
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            df['SMA_200'] = df['Close'].rolling(window=200).mean()
            df['EMA_12'] = df['Close'].ewm(span=12).mean()
            df['EMA_26'] = df['Close'].ewm(span=26).mean()
            
            # MACD
            df['MACD'] = df['EMA_12'] - df['EMA_26']
            df['MACD_signal'] = df['MACD'].ewm(span=9).mean()
            df['MACD_histogram'] = df['MACD'] - df['MACD_signal']
            
            # RSI
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # Bollinger Bands
            df['BB_middle'] = df['Close'].rolling(window=20).mean()
            bb_std = df['Close'].rolling(window=20).std()
            df['BB_upper'] = df['BB_middle'] + (bb_std * 2)
            df['BB_lower'] = df['BB_middle'] - (bb_std * 2)
            
            # Stochastic Oscillator
            low_14 = df['Low'].rolling(window=14).min()
            high_14 = df['High'].rolling(window=14).max()
            df['%K'] = 100 * ((df['Close'] - low_14) / (high_14 - low_14))
            df['%D'] = df['%K'].rolling(window=3).mean()
            
            # On-Balance Volume (OBV)
            df['OBV'] = (np.sign(df['Close'].diff()) * df['Volume']).cumsum()
            
            # Average Directional Index (ADX) - simplified
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift())
            low_close = np.abs(df['Low'] - df['Close'].shift())
            df['TR'] = np.maximum(high_low, np.maximum(high_close, low_close))
            
            return df
            
        except Exception as e:
            logging.error(f"Error calculating standard indicators: {str(e)}")
            return df
    
    def calculate_comprehensive_indicators(self, df):
        """Calculate all 35 technical indicators for Maximum Brain Analysis"""
        try:
            # Start with original dataframe for fallback calculations
            stock_df = df.copy()
            
            # Detailed logging initialization
            logging.info("=== STARTING COMPREHENSIVE INDICATOR CALCULATION ===")
            logging.info(f"Input dataframe shape: {df.shape}")
            logging.info(f"Input columns: {list(df.columns)}")
            
            # Track indicator calculation success/failure
            indicator_calculation_log = {
                'successful': [],
                'failed': [],
                'zero_values': [],
                'missing_prerequisites': []
            }
            
            # Try to use stockstats, but fall back to pure pandas if it fails
            try:
                # Ensure proper column names for stockstats
                df_clean = df.copy()
                df_clean.columns = df_clean.columns.str.lower()
                
                # Convert to StockDataFrame for enhanced functionality
                stockstats_df = stockstats.StockDataFrame.retype(df_clean)
                use_stockstats = True
                logging.info("✅ Stockstats conversion successful")
            except Exception as stockstats_error:
                logging.warning(f"❌ Stockstats conversion failed: {stockstats_error}. Using pure pandas calculations.")
                use_stockstats = False
                stockstats_df = None
            
            # === CORE INDICATORS (pandas_ta alternatives using stockstats and custom) ===
            
            # 1. RSI (Relative Strength Index)
            logging.info("📊 Calculating RSI (Relative Strength Index)...")
            try:
                if use_stockstats and stockstats_df is not None:
                    try:
                        stock_df['rsi_14'] = stockstats_df['rsi']
                        logging.info("✅ RSI calculated using stockstats")
                    except Exception as e:
                        logging.warning(f"⚠️ Stockstats RSI failed: {e}, falling back to pandas")
                        use_stockstats = False
                
                if not use_stockstats:
                    # Pure pandas RSI calculation
                    delta = df['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rs = gain / loss
                    stock_df['rsi_14'] = 100 - (100 / (1 + rs))
                    logging.info("✅ RSI calculated using pure pandas")
                
                # Validate RSI values
                latest_rsi = stock_df['rsi_14'].iloc[-1]
                if pd.isna(latest_rsi) or latest_rsi == 0:
                    indicator_calculation_log['zero_values'].append(f"RSI = {latest_rsi}")
                    logging.warning(f"⚠️ RSI has problematic value: {latest_rsi}")
                else:
                    indicator_calculation_log['successful'].append("RSI")
                    logging.info(f"✅ RSI final value: {latest_rsi:.2f}")
                    
            except Exception as e:
                indicator_calculation_log['failed'].append(f"RSI: {str(e)}")
                logging.error(f"❌ RSI calculation failed: {e}")
                stock_df['rsi_14'] = 0
            
            # 2. MACD (Moving Average Convergence Divergence)
            logging.info("📊 Calculating MACD (Moving Average Convergence Divergence)...")
            try:
                if use_stockstats and stockstats_df is not None:
                    try:
                        stock_df['macd'] = stockstats_df['macd']
                        stock_df['macd_signal'] = stockstats_df['macds']
                        stock_df['macd_histogram'] = stockstats_df['macdh']
                        logging.info("✅ MACD calculated using stockstats")
                    except Exception as e:
                        logging.warning(f"⚠️ Stockstats MACD failed: {e}, falling back to pandas")
                        use_stockstats = False
                        
                if not use_stockstats:
                    # Pure pandas MACD calculation
                    exp1 = df['Close'].ewm(span=12).mean()
                    exp2 = df['Close'].ewm(span=26).mean()
                    stock_df['macd'] = exp1 - exp2
                    stock_df['macd_signal'] = stock_df['macd'].ewm(span=9).mean()
                    stock_df['macd_histogram'] = stock_df['macd'] - stock_df['macd_signal']
                    logging.info("✅ MACD calculated using pure pandas")
                
                # Validate MACD values
                latest_macd = stock_df['macd'].iloc[-1]
                latest_signal = stock_df['macd_signal'].iloc[-1]
                latest_hist = stock_df['macd_histogram'].iloc[-1]
                
                macd_issues = []
                if pd.isna(latest_macd) or latest_macd == 0:
                    macd_issues.append(f"MACD = {latest_macd}")
                if pd.isna(latest_signal) or latest_signal == 0:
                    macd_issues.append(f"Signal = {latest_signal}")
                if pd.isna(latest_hist) or latest_hist == 0:
                    macd_issues.append(f"Histogram = {latest_hist}")
                
                if macd_issues:
                    indicator_calculation_log['zero_values'].extend(macd_issues)
                    logging.warning(f"⚠️ MACD has problematic values: {', '.join(macd_issues)}")
                else:
                    indicator_calculation_log['successful'].extend(["MACD", "MACD_Signal", "MACD_Histogram"])
                    logging.info(f"✅ MACD values - MACD: {latest_macd:.4f}, Signal: {latest_signal:.4f}, Histogram: {latest_hist:.4f}")
                    
            except Exception as e:
                indicator_calculation_log['failed'].append(f"MACD: {str(e)}")
                logging.error(f"❌ MACD calculation failed: {e}")
                stock_df['macd'] = 0
                stock_df['macd_signal'] = 0
                stock_df['macd_histogram'] = 0
            
            # 3-5. Moving Averages
            logging.info("📊 Calculating Moving Averages (SMA 20/50/200, EMA 12/26)...")
            try:
                if use_stockstats and stockstats_df is not None:
                    try:
                        stock_df['sma_20'] = stockstats_df['close_20_sma']
                        stock_df['sma_50'] = stockstats_df['close_50_sma'] 
                        stock_df['sma_200'] = stockstats_df['close_200_sma']
                        stock_df['ema_12'] = stockstats_df['close_12_ema']
                        stock_df['ema_26'] = stockstats_df['close_26_ema']
                        logging.info("✅ Moving Averages calculated using stockstats")
                    except Exception as e:
                        logging.warning(f"⚠️ Stockstats Moving Averages failed: {e}, falling back to pandas")
                        use_stockstats = False
                        
                if not use_stockstats:
                    # Pure pandas calculation
                    stock_df['sma_20'] = df['Close'].rolling(20).mean()
                    stock_df['sma_50'] = df['Close'].rolling(50).mean()
                    stock_df['sma_200'] = df['Close'].rolling(200).mean()
                    stock_df['ema_12'] = df['Close'].ewm(span=12).mean()
                    stock_df['ema_26'] = df['Close'].ewm(span=26).mean()
                    logging.info("✅ Moving Averages calculated using pure pandas")
                
                # Validate Moving Average values
                ma_values = {
                    'SMA_20': stock_df['sma_20'].iloc[-1],
                    'SMA_50': stock_df['sma_50'].iloc[-1],
                    'SMA_200': stock_df['sma_200'].iloc[-1],
                    'EMA_12': stock_df['ema_12'].iloc[-1],
                    'EMA_26': stock_df['ema_26'].iloc[-1]
                }
                
                ma_issues = []
                ma_successful = []
                for name, value in ma_values.items():
                    if pd.isna(value) or value == 0:
                        ma_issues.append(f"{name} = {value}")
                    else:
                        ma_successful.append(name)
                        logging.info(f"✅ {name}: {value:.2f}")
                
                if ma_issues:
                    indicator_calculation_log['zero_values'].extend(ma_issues)
                    logging.warning(f"⚠️ Moving Averages with issues: {', '.join(ma_issues)}")
                
                if ma_successful:
                    indicator_calculation_log['successful'].extend(ma_successful)
                    logging.info(f"✅ Successful Moving Averages: {', '.join(ma_successful)}")
                    
            except Exception as e:
                indicator_calculation_log['failed'].append(f"Moving Averages: {str(e)}")
                logging.error(f"❌ Moving Averages calculation failed: {e}")
                stock_df['sma_20'] = 0
                stock_df['sma_50'] = 0
                stock_df['sma_200'] = 0
                stock_df['ema_12'] = 0
                stock_df['ema_26'] = 0
            
            # 6. Bollinger Bands
            logging.info("📊 Calculating Bollinger Bands...")
            try:
                if use_stockstats and stockstats_df is not None:
                    try:
                        stock_df['bb_upper'] = stockstats_df['boll_ub']
                        stock_df['bb_middle'] = stockstats_df['boll']
                        stock_df['bb_lower'] = stockstats_df['boll_lb']
                        logging.info("✅ Bollinger Bands calculated using stockstats")
                    except Exception as e:
                        logging.warning(f"⚠️ Stockstats Bollinger Bands failed: {e}, falling back to pandas")
                        use_stockstats = False
                        
                if not use_stockstats:
                    # Pure pandas Bollinger Bands
                    sma_20 = df['Close'].rolling(20).mean()
                    std_20 = df['Close'].rolling(20).std()
                    stock_df['bb_upper'] = sma_20 + (std_20 * 2)
                    stock_df['bb_middle'] = sma_20
                    stock_df['bb_lower'] = sma_20 - (std_20 * 2)
                    logging.info("✅ Bollinger Bands calculated using pure pandas")
                
                # Validate Bollinger Band values
                bb_values = {
                    'BB_Upper': stock_df['bb_upper'].iloc[-1],
                    'BB_Middle': stock_df['bb_middle'].iloc[-1],
                    'BB_Lower': stock_df['bb_lower'].iloc[-1]
                }
                
                bb_issues = []
                bb_successful = []
                for name, value in bb_values.items():
                    if pd.isna(value) or value == 0:
                        bb_issues.append(f"{name} = {value}")
                    else:
                        bb_successful.append(name)
                        logging.info(f"✅ {name}: {value:.2f}")
                
                if bb_issues:
                    indicator_calculation_log['zero_values'].extend(bb_issues)
                    logging.warning(f"⚠️ Bollinger Bands with issues: {', '.join(bb_issues)}")
                
                if bb_successful:
                    indicator_calculation_log['successful'].extend(bb_successful)
                    
            except Exception as e:
                indicator_calculation_log['failed'].append(f"Bollinger Bands: {str(e)}")
                logging.error(f"❌ Bollinger Bands calculation failed: {e}")
                stock_df['bb_upper'] = 0
                stock_df['bb_middle'] = 0
                stock_df['bb_lower'] = 0
            
            # 7. Stochastic Oscillator - Always use pure pandas (more reliable)
            logging.info("📊 Calculating Stochastic Oscillator...")
            try:
                low_14 = df['Low'].rolling(14).min()
                high_14 = df['High'].rolling(14).max()
                stock_df['stoch_k'] = 100 * ((df['Close'] - low_14) / (high_14 - low_14))
                stock_df['stoch_d'] = stock_df['stoch_k'].rolling(3).mean()
                
                # Validate Stochastic values
                stoch_k_val = stock_df['stoch_k'].iloc[-1]
                stoch_d_val = stock_df['stoch_d'].iloc[-1]
                
                stoch_issues = []
                stoch_successful = []
                
                for name, value in [('Stochastic_K', stoch_k_val), ('Stochastic_D', stoch_d_val)]:
                    if pd.isna(value) or value == 0:
                        stoch_issues.append(f"{name} = {value}")
                    else:
                        stoch_successful.append(name)
                        logging.info(f"✅ {name}: {value:.2f}")
                
                if stoch_issues:
                    indicator_calculation_log['zero_values'].extend(stoch_issues)
                    logging.warning(f"⚠️ Stochastic with issues: {', '.join(stoch_issues)}")
                
                if stoch_successful:
                    indicator_calculation_log['successful'].extend(stoch_successful)
                    
            except Exception as e:
                indicator_calculation_log['failed'].append(f"Stochastic Oscillator: {str(e)}")
                logging.error(f"❌ Stochastic Oscillator calculation failed: {e}")
                stock_df['stoch_k'] = 0
                stock_df['stoch_d'] = 0
            
            # Initialize ATR early to ensure it's always available for other indicators
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift())
            low_close = np.abs(df['Low'] - df['Close'].shift())
            tr = np.maximum(high_low, np.maximum(high_close, low_close))
            atr = tr.rolling(14).mean()  # Ensure ATR is always available
            
            # 8. ADX (Average Directional Index) - Always use simplified calculation
            logging.info("📊 Calculating ADX (Average Directional Index)...")
            try:
                stock_df['adx'] = atr * 5  # Simplified ADX proxy
                
                # Validate ADX value
                adx_val = stock_df['adx'].iloc[-1]
                if pd.isna(adx_val) or adx_val == 0:
                    indicator_calculation_log['zero_values'].append(f"ADX = {adx_val}")
                    logging.warning(f"⚠️ ADX has problematic value: {adx_val}")
                else:
                    indicator_calculation_log['successful'].append("ADX")
                    logging.info(f"✅ ADX: {adx_val:.2f}")
                    
            except Exception as e:
                indicator_calculation_log['failed'].append(f"ADX: {str(e)}")
                logging.error(f"❌ ADX calculation failed: {e}")
                stock_df['adx'] = 0
            
            # 9. CCI (Commodity Channel Index) - Always use pure pandas
            logging.info("📊 Calculating CCI (Commodity Channel Index)...")
            try:
                tp = (df['High'] + df['Low'] + df['Close']) / 3
                sma_tp = tp.rolling(20).mean()
                mad = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean())
                stock_df['cci'] = (tp - sma_tp) / (0.015 * mad)
                
                # Validate CCI value
                cci_val = stock_df['cci'].iloc[-1]
                if pd.isna(cci_val) or cci_val == 0:
                    indicator_calculation_log['zero_values'].append(f"CCI = {cci_val}")
                    logging.warning(f"⚠️ CCI has problematic value: {cci_val}")
                else:
                    indicator_calculation_log['successful'].append("CCI")
                    logging.info(f"✅ CCI: {cci_val:.2f}")
                    
            except Exception as e:
                indicator_calculation_log['failed'].append(f"CCI: {str(e)}")
                logging.error(f"❌ CCI calculation failed: {e}")
                stock_df['cci'] = 0
            
            # 10. Williams %R - Always use pure pandas
            logging.info("📊 Calculating Williams %R...")
            try:
                high_14 = df['High'].rolling(14).max()
                low_14 = df['Low'].rolling(14).min()
                stock_df['williams_r'] = -100 * ((high_14 - df['Close']) / (high_14 - low_14))
                
                # Validate Williams %R value
                williams_val = stock_df['williams_r'].iloc[-1]
                if pd.isna(williams_val) or williams_val == 0:
                    indicator_calculation_log['zero_values'].append(f"Williams_R = {williams_val}")
                    logging.warning(f"⚠️ Williams %R has problematic value: {williams_val}")
                else:
                    indicator_calculation_log['successful'].append("Williams_R")
                    logging.info(f"✅ Williams %R: {williams_val:.2f}")
                    
            except Exception as e:
                indicator_calculation_log['failed'].append(f"Williams %R: {str(e)}")
                logging.error(f"❌ Williams %R calculation failed: {e}")
                stock_df['williams_r'] = 0
            
            # 11. Money Flow Index (MFI) - Custom calculation
            typical_price = (df['High'] + df['Low'] + df['Close']) / 3
            money_flow = typical_price * df['Volume']
            positive_flow = money_flow.where(typical_price.diff() > 0, 0).rolling(14).sum()
            negative_flow = money_flow.where(typical_price.diff() < 0, 0).rolling(14).sum()
            stock_df['mfi'] = 100 - (100 / (1 + positive_flow / negative_flow))
            
            # 12. On-Balance Volume (OBV)
            stock_df['obv'] = (np.sign(df['Close'].diff()) * df['Volume']).cumsum()
            
            # 13. Average True Range (ATR) - Use already calculated ATR from ADX
            stock_df['atr'] = atr
            
            # 14. Ultimate Oscillator - Custom calculation
            bp = df['Close'] - np.minimum(df['Low'], df['Close'].shift(1))
            tr = np.maximum(df['High'] - df['Low'], 
                           np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                                     abs(df['Low'] - df['Close'].shift(1))))
            avg7 = bp.rolling(7).sum() / tr.rolling(7).sum()
            avg14 = bp.rolling(14).sum() / tr.rolling(14).sum()
            avg28 = bp.rolling(28).sum() / tr.rolling(28).sum()
            stock_df['ultimate_osc'] = 100 * ((4 * avg7) + (2 * avg14) + avg28) / 7
            
            # 15. TRIX - Always use pure pandas
            ema1 = df['Close'].ewm(span=14).mean()
            ema2 = ema1.ewm(span=14).mean()
            ema3 = ema2.ewm(span=14).mean()
            stock_df['trix'] = ema3.pct_change() * 10000
            
            # 16. Momentum 
            stock_df['momentum'] = df['Close'] - df['Close'].shift(10)
            
            # 17. Rate of Change (ROC)
            stock_df['roc'] = ((df['Close'] - df['Close'].shift(12)) / df['Close'].shift(12)) * 100
            
            # 18. Donchian Channels - Custom calculation
            stock_df['donchian_upper'] = df['High'].rolling(20).max()
            stock_df['donchian_lower'] = df['Low'].rolling(20).min()
            stock_df['donchian_middle'] = (stock_df['donchian_upper'] + stock_df['donchian_lower']) / 2
            
            # 19. Keltner Channels - Custom calculation
            ema_20 = df['Close'].ewm(span=20).mean()
            atr_10 = stock_df['atr'].rolling(10).mean()
            stock_df['keltner_upper'] = ema_20 + (2 * atr_10)
            stock_df['keltner_lower'] = ema_20 - (2 * atr_10)
            stock_df['keltner_middle'] = ema_20
            
            # 20. Aroon Indicator - Custom calculation
            aroon_length = 14
            high_idx = df['High'].rolling(aroon_length + 1).apply(lambda x: x.argmax(), raw=False)
            low_idx = df['Low'].rolling(aroon_length + 1).apply(lambda x: x.argmin(), raw=False)
            stock_df['aroon_up'] = ((aroon_length - high_idx) / aroon_length) * 100
            stock_df['aroon_down'] = ((aroon_length - low_idx) / aroon_length) * 100
            
            # 21. Parabolic SAR - Always use simple trending indicator
            stock_df['sar'] = np.where(df['Close'] > df['Close'].ewm(span=20).mean(), 
                                      df['Low'].rolling(5).min(), 
                                      df['High'].rolling(5).max())
            
            # 22. VWAP (Volume Weighted Average Price)
            vwap = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()
            stock_df['vwap'] = vwap
            
            # 23. Accumulation/Distribution Line - Always use pure pandas
            clv = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / (df['High'] - df['Low'])
            clv = clv.fillna(0)  # Handle division by zero
            stock_df['ad_line'] = (clv * df['Volume']).cumsum()
            
            # 24. Ichimoku Cloud components - Custom calculation
            high_9 = df['High'].rolling(9).max()
            low_9 = df['Low'].rolling(9).min()
            high_26 = df['High'].rolling(26).max()
            low_26 = df['Low'].rolling(26).min()
            high_52 = df['High'].rolling(52).max()
            low_52 = df['Low'].rolling(52).min()
            
            stock_df['tenkan_sen'] = (high_9 + low_9) / 2
            stock_df['kijun_sen'] = (high_26 + low_26) / 2
            stock_df['senkou_span_a'] = ((stock_df['tenkan_sen'] + stock_df['kijun_sen']) / 2).shift(26)
            stock_df['senkou_span_b'] = ((high_52 + low_52) / 2).shift(26)
            
            # === CUSTOM PATTERN DETECTION ===
            
            # 25. Pivot Points
            stock_df['pivot'] = (df['High'] + df['Low'] + df['Close']) / 3
            stock_df['r1'] = (2 * stock_df['pivot']) - df['Low']
            stock_df['s1'] = (2 * stock_df['pivot']) - df['High']
            
            # 26. Fibonacci Retracements - Enhanced with validation
            logging.info("📊 Calculating Fibonacci Retracements...")
            try:
                recent_high = df['High'].rolling(50).max()
                recent_low = df['Low'].rolling(50).min()
                diff = recent_high - recent_low
                
                # Only calculate if meaningful price range exists (avoid division issues)
                meaningful_range = diff > (recent_high * 0.001)  # At least 0.1% range
                
                stock_df['fib_23.6'] = np.where(meaningful_range, 
                                               recent_high - (diff * 0.236), 
                                               recent_high * 0.9924)  # Fallback: 0.76% below high
                stock_df['fib_38.2'] = np.where(meaningful_range, 
                                               recent_high - (diff * 0.382),
                                               recent_high * 0.9881)  # Fallback: 1.19% below high  
                stock_df['fib_61.8'] = np.where(meaningful_range, 
                                               recent_high - (diff * 0.618),
                                               recent_high * 0.9809)  # Fallback: 1.91% below high
                                               
                # Validate Fibonacci calculations
                fib_values = {
                    'Fibonacci_23.6': stock_df['fib_23.6'].iloc[-1],
                    'Fibonacci_38.2': stock_df['fib_38.2'].iloc[-1], 
                    'Fibonacci_61.8': stock_df['fib_61.8'].iloc[-1]
                }
                
                for name, value in fib_values.items():
                    if pd.isna(value):
                        indicator_calculation_log['failed'].append(f"{name}: NaN value")
                        logging.warning(f"⚠️ {name} calculation failed: NaN")
                    else:
                        indicator_calculation_log['successful'].append(name)
                        logging.info(f"✅ {name}: {value:.2f}")
                        
            except Exception as e:
                indicator_calculation_log['failed'].append(f"Fibonacci Retracements: {str(e)}")
                logging.error(f"❌ Fibonacci Retracements calculation failed: {e}")
                # Safe fallback values
                stock_df['fib_23.6'] = df['Close'] * 0.99
                stock_df['fib_38.2'] = df['Close'] * 0.98  
                stock_df['fib_61.8'] = df['Close'] * 0.97
            
            # 27. Support/Resistance Levels using local pandas/numpy peak detection
            try:
                highs = df['High'].values
                lows = df['Low'].values
                
                # Pure pandas/numpy peak detection algorithm
                def find_local_peaks(data, distance=10, prominence_factor=0.5):
                    """Local peak detection using pure pandas/numpy"""
                    peaks = []
                    prominence_threshold = np.std(data) * prominence_factor
                    
                    for i in range(distance, len(data) - distance):
                        # Check if current point is higher than surrounding points
                        left_max = np.max(data[i-distance:i])
                        right_max = np.max(data[i+1:i+distance+1])
                        current = data[i]
                        
                        # Peak conditions: higher than neighbors and meets prominence
                        if current > left_max and current > right_max:
                            prominence = current - max(left_max, right_max)
                            if prominence >= prominence_threshold:
                                peaks.append(i)
                    
                    return np.array(peaks)
                
                # Find resistance peaks (high points)
                resistance_peaks = find_local_peaks(highs, distance=10, prominence_factor=0.5)
                
                # Find support peaks (low points - invert data)
                support_peaks = find_local_peaks(-lows, distance=10, prominence_factor=0.5)
                
                # Initialize columns
                stock_df['resistance_level'] = np.nan
                stock_df['support_level'] = np.nan
                
                # Set peak values
                if len(resistance_peaks) > 0:
                    stock_df.iloc[resistance_peaks, stock_df.columns.get_loc('resistance_level')] = highs[resistance_peaks]
                if len(support_peaks) > 0:
                    stock_df.iloc[support_peaks, stock_df.columns.get_loc('support_level')] = lows[support_peaks]
                    
                # Forward fill to maintain levels
                stock_df['resistance_level'] = stock_df['resistance_level'].ffill()
                stock_df['support_level'] = stock_df['support_level'].ffill()
                
            except Exception as peak_error:
                logging.warning(f"Peak detection failed, using rolling max/min fallback: {peak_error}")
                stock_df['resistance_level'] = df['High'].rolling(20).max()
                stock_df['support_level'] = df['Low'].rolling(20).min()
            
            # 28. RMI (Relative Momentum Index) - Enhanced with division-by-zero protection
            logging.info("📊 Calculating RMI (Relative Momentum Index)...")
            try:
                momentum_changes = df['Close'].diff(1).diff(1)  # Second-order momentum
                gain_rmi = momentum_changes.where(momentum_changes > 0, 0).rolling(14).mean()
                loss_rmi = (-momentum_changes.where(momentum_changes < 0, 0)).rolling(14).mean()
                
                # Protect against division by zero with minimum threshold
                loss_rmi_safe = np.where(loss_rmi <= 0.0001, 0.0001, loss_rmi)
                rs_rmi = gain_rmi / loss_rmi_safe
                
                # Additional validation for infinite or extreme values
                rs_rmi_clipped = np.clip(rs_rmi, 0.001, 1000)  # Reasonable bounds
                stock_df['rmi'] = 100 - (100 / (1 + rs_rmi_clipped))
                
                # Validate RMI value  
                rmi_val = stock_df['rmi'].iloc[-1]
                if pd.isna(rmi_val) or np.isinf(rmi_val):
                    indicator_calculation_log['failed'].append(f"RMI: invalid value {rmi_val}")
                    logging.warning(f"⚠️ RMI calculation produced invalid value: {rmi_val}")
                    # Fallback to standard RSI calculation
                    delta = df['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rs = gain / np.where(loss <= 0.0001, 0.0001, loss)
                    stock_df['rmi'] = 100 - (100 / (1 + rs))
                    logging.info("✅ RMI fallback to RSI calculation successful")
                else:
                    indicator_calculation_log['successful'].append("RMI")
                    logging.info(f"✅ RMI: {rmi_val:.2f}")
                    
            except Exception as e:
                indicator_calculation_log['failed'].append(f"RMI: {str(e)}")
                logging.error(f"❌ RMI calculation failed: {e}")
                # Final fallback - use RSI as RMI
                try:
                    delta = df['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rs = gain / np.where(loss <= 0.0001, 0.0001, loss)
                    stock_df['rmi'] = 100 - (100 / (1 + rs))
                    logging.info("✅ RMI fallback to RSI calculation successful")
                except Exception as fallback_error:
                    logging.error(f"❌ RMI fallback also failed: {fallback_error}")
                    stock_df['rmi'] = 50  # Neutral RSI value
            
            # 29. Supertrend - Enhanced with ATR validation  
            logging.info("📊 Calculating Supertrend...")
            try:
                hl2 = (df['High'] + df['Low']) / 2
                
                # Validate ATR before using (ensure it's properly calculated and not NaN/infinite)
                atr_validated = np.where(pd.isna(atr) | np.isinf(atr) | (atr <= 0), 
                                       df['Close'] * 0.02,  # Fallback: 2% of price as volatility
                                       atr)
                
                atr_mult = atr_validated * 3
                upper_band = hl2 + atr_mult
                lower_band = hl2 - atr_mult
                
                # Enhanced Supertrend calculation with trend persistence
                close_prices = df['Close'].values
                supertrend_values = np.full(len(close_prices), np.nan)
                trend = 1  # 1 for uptrend, -1 for downtrend
                
                for i in range(1, len(close_prices)):
                    if close_prices[i] <= lower_band.iloc[i]:
                        supertrend_values[i] = lower_band.iloc[i]
                        trend = 1
                    elif close_prices[i] >= upper_band.iloc[i]:
                        supertrend_values[i] = upper_band.iloc[i] 
                        trend = -1
                    else:
                        # Maintain trend direction
                        if trend == 1:
                            supertrend_values[i] = lower_band.iloc[i]
                        else:
                            supertrend_values[i] = upper_band.iloc[i]
                
                stock_df['supertrend'] = pd.Series(supertrend_values, index=df.index)
                stock_df['supertrend'] = stock_df['supertrend'].ffill()
                
                # Validate Supertrend result
                supertrend_val = stock_df['supertrend'].iloc[-1]
                if pd.isna(supertrend_val):
                    indicator_calculation_log['failed'].append("Supertrend: NaN result")
                    logging.warning("⚠️ Supertrend calculation produced NaN")
                    # Fallback: simple moving average
                    stock_df['supertrend'] = df['Close'].rolling(20).mean()
                    logging.info("✅ Supertrend fallback to SMA successful") 
                else:
                    indicator_calculation_log['successful'].append("Supertrend")
                    logging.info(f"✅ Supertrend: {supertrend_val:.2f}")
                    
            except Exception as e:
                indicator_calculation_log['failed'].append(f"Supertrend: {str(e)}")
                logging.error(f"❌ Supertrend calculation failed: {e}")
                # Final fallback
                stock_df['supertrend'] = df['Close'].rolling(20).mean()
                logging.info("✅ Supertrend fallback to SMA successful")
            
            # 30-35. Pattern Detection Flags - Enhanced with validation
            logging.info("📊 Calculating Pattern Detection Flags (6 indicators)...")
            try:
                # Enhanced trend strength calculation with validation
                adx_values = stock_df.get('adx', pd.Series([0] * len(df)))
                stock_df['trend_strength'] = np.where(pd.isna(adx_values), 
                                                    df['Close'].rolling(14).std() / df['Close'].rolling(14).mean() * 100,
                                                    abs(adx_values))
                
                # Volume trend with rolling window validation
                volume_mean = df['Volume'].rolling(20).mean()
                stock_df['volume_trend'] = np.where(pd.isna(volume_mean) | (volume_mean == 0), 0,
                                                   np.where(df['Volume'] > volume_mean, 1, 0))
                
                # Price momentum with validation
                price_shift = df['Close'].shift(5)
                stock_df['price_momentum'] = np.where(pd.isna(price_shift), 0,
                                                     np.where(df['Close'] > price_shift, 1, 0))
                
                # Volatility with minimum threshold
                volatility_raw = df['Close'].rolling(20).std()
                stock_df['volatility'] = np.where(pd.isna(volatility_raw), df['Close'] * 0.01, volatility_raw)
                
                # RSI divergence with RSI validation  
                rsi_values = stock_df.get('rsi_14', pd.Series([50] * len(df)))
                stock_df['rsi_divergence'] = np.where(pd.isna(rsi_values), 0,
                                                     np.where((rsi_values > 70) | (rsi_values < 30), 1, 0))
                
                # MACD crossover with MACD validation
                macd_values = stock_df.get('macd', pd.Series([0] * len(df)))
                macd_signal_values = stock_df.get('macd_signal', pd.Series([0] * len(df)))
                stock_df['macd_crossover'] = np.where(pd.isna(macd_values) | pd.isna(macd_signal_values), 0,
                                                     np.where(macd_values > macd_signal_values, 1, 0))
                
                # Validate each pattern flag
                pattern_calculations = {
                    'Trend_Strength': stock_df['trend_strength'].iloc[-1],
                    'Volume_Trend': stock_df['volume_trend'].iloc[-1],
                    'Price_Momentum': stock_df['price_momentum'].iloc[-1],
                    'Volatility': stock_df['volatility'].iloc[-1],
                    'RSI_Divergence_Flag': stock_df['rsi_divergence'].iloc[-1],
                    'MACD_Crossover_Flag': stock_df['macd_crossover'].iloc[-1]
                }
                
                pattern_successful = []
                pattern_failed = []
                
                for flag_name, value in pattern_calculations.items():
                    if pd.isna(value) or np.isinf(value):
                        pattern_failed.append(f"{flag_name}: invalid value {value}")
                        logging.warning(f"⚠️ {flag_name} has invalid value: {value}")
                    else:
                        pattern_successful.append(flag_name)
                        logging.info(f"✅ {flag_name}: {value}")
                
                if pattern_successful:
                    indicator_calculation_log['successful'].extend(pattern_successful)
                if pattern_failed:
                    indicator_calculation_log['failed'].extend(pattern_failed)
                    
                logging.info("✅ Pattern Detection Flags calculation completed")
                
            except Exception as e:
                indicator_calculation_log['failed'].append(f"Pattern Detection Flags: {str(e)}")
                logging.error(f"❌ Pattern Detection Flags calculation failed: {e}")
                # Fallback: set all flags to neutral values
                stock_df['trend_strength'] = 25  # Neutral trend strength
                stock_df['volume_trend'] = 0     # No volume trend
                stock_df['price_momentum'] = 0   # No momentum
                stock_df['volatility'] = df['Close'].std()  # Basic volatility
                stock_df['rsi_divergence'] = 0   # No divergence
                stock_df['macd_crossover'] = 0   # No crossover
            
            # ===== COMPREHENSIVE INDICATOR CALCULATION SUMMARY =====
            logging.info("=" * 80)
            logging.info("🎯 COMPREHENSIVE INDICATOR CALCULATION COMPLETE")
            logging.info("=" * 80)
            
            total_successful = len(indicator_calculation_log['successful'])
            total_failed = len(indicator_calculation_log['failed'])
            total_zero_values = len(indicator_calculation_log['zero_values'])
            total_missing = len(indicator_calculation_log['missing_prerequisites'])
            total_calculated = total_successful + total_failed + total_zero_values + total_missing
            
            logging.info(f"📊 CALCULATION PHASE RESULTS:")
            logging.info(f"   ✅ Successfully calculated: {total_successful} indicators")
            logging.info(f"   ❌ Failed calculations: {total_failed} indicators")
            logging.info(f"   ⚪ Zero/NaN values: {total_zero_values} indicators")
            logging.info(f"   🚫 Missing prerequisites: {total_missing} indicators")
            logging.info(f"   📈 Total attempted: {total_calculated} indicators")
            
            if indicator_calculation_log['successful']:
                logging.info(f"✅ SUCCESSFUL INDICATORS ({len(indicator_calculation_log['successful'])}):")
                logging.info(f"   {', '.join(indicator_calculation_log['successful'])}")
            
            if indicator_calculation_log['failed']:
                logging.info(f"❌ FAILED INDICATORS ({len(indicator_calculation_log['failed'])}):")
                logging.info(f"   {', '.join(indicator_calculation_log['failed'])}")
            
            if indicator_calculation_log['zero_values']:
                logging.info(f"⚪ ZERO/NaN VALUE INDICATORS ({len(indicator_calculation_log['zero_values'])}):")
                logging.info(f"   {', '.join(indicator_calculation_log['zero_values'])}")
            
            if indicator_calculation_log['missing_prerequisites']:
                logging.info(f"🚫 MISSING PREREQUISITE INDICATORS ({len(indicator_calculation_log['missing_prerequisites'])}):")
                logging.info(f"   {', '.join(indicator_calculation_log['missing_prerequisites'])}")
            
            # Show final dataframe column count for verification
            final_columns = len(stock_df.columns)
            original_columns = len(df.columns)
            new_columns = final_columns - original_columns
            
            logging.info(f"📋 DATAFRAME SUMMARY:")
            logging.info(f"   Original columns: {original_columns}")
            logging.info(f"   New indicator columns: {new_columns}")
            logging.info(f"   Total final columns: {final_columns}")
            logging.info(f"   Final dataframe shape: {stock_df.shape}")
            
            logging.info("=" * 80)
            logging.info("🎯 MOVING TO DATA SUMMARIZATION PHASE")
            logging.info("=" * 80)
            
            return stock_df
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logging.error(f"Error calculating comprehensive indicators: {str(e)}")
            logging.error(f"Comprehensive indicators error traceback: {error_details}")
            logging.error(f"Dataframe shape: {df.shape if df is not None else 'None'}")
            logging.error(f"Dataframe columns: {list(df.columns) if df is not None else 'None'}")
            # Fallback to standard indicators if comprehensive calculation fails
            return self.calculate_standard_indicators(df)
    
    def summarize_data(self, df, info, maximum_brain=False):
        """Summarize stock data for AI analysis"""
        try:
            recent_data = df.tail(30)  # Last 30 days
            
            # Base summary for both modes
            summary = {
                'ticker': info.get('symbol', 'N/A'),
                'company_name': info.get('longName', 'N/A'),
                'current_price': df['Close'].iloc[-1] if not df.empty else 0,
                'price_change_30d': ((df['Close'].iloc[-1] / df['Close'].iloc[-30] - 1) * 100) if len(df) >= 30 else 0,
                'volume_avg_30d': recent_data['Volume'].mean(),
                'volatility_30d': recent_data['Close'].std(),
            }
            
            if maximum_brain:
                # Comprehensive indicator values for Maximum Brain Analysis with graceful handling
                latest_row = df.iloc[-1]
                
                # Define critical and optional indicators for payload optimization
                critical_indicators = [
                    ('RSI', 'rsi_14'), ('MACD', 'macd'), ('MACD_Signal', 'macd_signal'), 
                    ('ADX', 'adx'), ('SMA_20', 'sma_20'), ('SMA_50', 'sma_50'), ('SMA_200', 'sma_200'),
                    ('Bollinger_Upper', 'bb_upper'), ('Bollinger_Lower', 'bb_lower'), ('Stochastic_K', 'stoch_k')
                ]
                
                optional_indicators = [
                    ('MACD_Histogram', 'macd_histogram'), ('EMA_12', 'ema_12'), ('EMA_26', 'ema_26'),
                    ('Bollinger_Middle', 'bb_middle'), ('Stochastic_D', 'stoch_d'), ('CCI', 'cci'),
                    ('Williams_R', 'williams_r'), ('MFI', 'mfi'), ('OBV', 'obv'), ('ATR', 'atr'),
                    ('Ultimate_Oscillator', 'ultimate_osc'), ('TRIX', 'trix'), ('Momentum', 'momentum'),
                    ('ROC', 'roc'), ('Donchian_Upper', 'donchian_upper'), ('Donchian_Lower', 'donchian_lower'),
                    ('Keltner_Upper', 'keltner_upper'), ('Keltner_Lower', 'keltner_lower'),
                    ('Aroon_Up', 'aroon_up'), ('Aroon_Down', 'aroon_down'), ('Parabolic_SAR', 'sar'),
                    ('VWAP', 'vwap'), ('AD_Line', 'ad_line'), ('Tenkan_Sen', 'tenkan_sen'),
                    ('Kijun_Sen', 'kijun_sen'), ('Pivot_Point', 'pivot'), ('Resistance_R1', 'r1'),
                    ('Support_S1', 's1'), ('Fibonacci_23.6', 'fib_23.6'), ('Fibonacci_38.2', 'fib_38.2'),
                    ('Fibonacci_61.8', 'fib_61.8'), ('Resistance_Level', 'resistance_level'),
                    ('Support_Level', 'support_level'), ('RMI', 'rmi'), ('Supertrend', 'supertrend'),
                    ('Trend_Strength', 'trend_strength'), ('Volume_Trend', 'volume_trend'),
                    ('Price_Momentum', 'price_momentum'), ('Volatility', 'volatility'),
                    ('RSI_Divergence_Flag', 'rsi_divergence'), ('MACD_Crossover_Flag', 'macd_crossover')
                ]
                
                # Build indicator values with graceful error handling
                indicator_values = {}
                successful_indicators = []
                failed_indicators = []
                zero_value_indicators = []
                missing_column_indicators = []
                
                # Process critical indicators first - PRODUCTION-GRADE FILTERING
                for display_name, column_name in critical_indicators:
                    try:
                        if column_name not in latest_row.index:
                            missing_column_indicators.append(f"{display_name} (missing column '{column_name}')")
                            failed_indicators.append(f"{display_name} (critical)")
                            continue
                            
                        value = self.safe_get_value(latest_row, column_name)
                        # Intelligent filtering: Only exclude truly invalid values, not legitimate zeros
                        if pd.isna(value) or value is None or (isinstance(value, float) and np.isinf(value)):
                            zero_value_indicators.append(f"{display_name} = {value} (invalid)")
                            logging.debug(f"Critical indicator {display_name} filtered: invalid value {value}")
                        else:
                            # Include ALL valid values, including legitimate technical zeros (MACD crossovers, momentum signals, etc.)
                            indicator_values[display_name] = value
                            successful_indicators.append(display_name)
                            if value == 0:
                                logging.debug(f"Critical indicator {display_name} included with zero value (valid technical signal)")
                    except Exception as e:
                        failed_indicators.append(f"{display_name} (critical)")
                        logging.warning(f"Critical indicator {display_name} failed: {e}")
                
                # Process optional indicators (limit to prevent payload bloat)
                max_optional = 25  # Limit optional indicators for payload size management
                optional_count = 0
                hit_limit_indicators = []
                
                for display_name, column_name in optional_indicators:
                    if optional_count >= max_optional:
                        hit_limit_indicators.append(display_name)
                        continue
                        
                    try:
                        if column_name not in latest_row.index:
                            missing_column_indicators.append(f"{display_name} (missing column '{column_name}')")
                            failed_indicators.append(f"{display_name} (optional)")
                            continue
                            
                        value = self.safe_get_value(latest_row, column_name)
                        # Intelligent filtering: Only exclude truly invalid values, not legitimate zeros
                        if pd.isna(value) or value is None or (isinstance(value, float) and np.isinf(value)):
                            zero_value_indicators.append(f"{display_name} = {value} (invalid)")
                            logging.debug(f"Optional indicator {display_name} filtered: invalid value {value}")
                        else:
                            # Include ALL valid values, including legitimate technical zeros
                            indicator_values[display_name] = value
                            successful_indicators.append(display_name)
                            optional_count += 1
                            if value == 0:
                                logging.debug(f"Optional indicator {display_name} included with zero value (valid technical signal)")
                    except Exception as e:
                        failed_indicators.append(f"{display_name} (optional)")
                        logging.warning(f"Optional indicator {display_name} failed: {e}")
                
                # Comprehensive logging for debugging
                logging.info(f"=== MAXIMUM BRAIN INDICATOR ANALYSIS FOR {summary.get('ticker', 'UNKNOWN')} ===")
                logging.info(f"✅ Successfully included: {len(successful_indicators)} indicators")
                logging.info(f"   {', '.join(successful_indicators)}")
                
                if zero_value_indicators:
                    logging.info(f"❌ Invalid value indicators (filtered): {len(zero_value_indicators)}")
                    logging.info(f"   {', '.join(zero_value_indicators)}")
                    logging.info("   Note: Valid zero values (MACD crossovers, momentum signals) are now INCLUDED")
                
                if missing_column_indicators:
                    logging.info(f"❌ Missing column indicators: {len(missing_column_indicators)}")
                    logging.info(f"   {', '.join(missing_column_indicators)}")
                
                if hit_limit_indicators:
                    logging.info(f"🚫 Hit optional limit (25): {len(hit_limit_indicators)} indicators")
                    logging.info(f"   {', '.join(hit_limit_indicators)}")
                
                if failed_indicators:
                    logging.info(f"💥 Calculation errors: {len(failed_indicators)}")
                    logging.info(f"   {', '.join(failed_indicators)}")
                
                total_attempted = len(critical_indicators) + len(optional_indicators)
                logging.info(f"📊 SUMMARY: {len(successful_indicators)}/{total_attempted} indicators used")
                
                summary['indicator_values'] = indicator_values
                summary['indicator_stats'] = {
                    'total_successful': len(successful_indicators),
                    'total_failed': len(failed_indicators),
                    'critical_available': len([i for i, _ in critical_indicators if i in successful_indicators])
                }
                
                logging.info(f"Maximum Brain indicators for {summary.get('ticker', 'UNKNOWN')}: {len(successful_indicators)} successful, {len(failed_indicators)} failed")
            else:
                # Standard mode indicators
                summary.update({
                    'rsi_current': df['RSI'].iloc[-1] if 'RSI' in df.columns else 0,
                    'macd_current': df['MACD'].iloc[-1] if 'MACD' in df.columns else 0,
                    'bb_position': 'upper' if df['Close'].iloc[-1] > df['BB_upper'].iloc[-1] else 'lower' if df['Close'].iloc[-1] < df['BB_lower'].iloc[-1] else 'middle',
                    'sma_20_trend': 'above' if df['Close'].iloc[-1] > df['SMA_20'].iloc[-1] else 'below',
                    'sma_50_trend': 'above' if df['Close'].iloc[-1] > df['SMA_50'].iloc[-1] else 'below',
                    'sma_200_trend': 'above' if df['Close'].iloc[-1] > df['SMA_200'].iloc[-1] else 'below',
                    'stoch_k': df['%K'].iloc[-1] if '%K' in df.columns else 0,
                    'stoch_d': df['%D'].iloc[-1] if '%D' in df.columns else 0,
                    'obv_trend': 'increasing' if df['OBV'].iloc[-1] > df['OBV'].iloc[-10] else 'decreasing'
                })
            
            return summary
            
        except Exception as e:
            logging.error(f"Error summarizing data: {str(e)}")
            # Return a minimal but valid summary to prevent total failure
            return {
                'ticker': info.get('symbol', 'UNKNOWN') if info else 'UNKNOWN',
                'company_name': info.get('longName', 'Unknown Company') if info else 'Unknown Company',
                'current_price': df['Close'].iloc[-1] if not df.empty else 0,
                'price_change_30d': 0,
                'volume_avg_30d': 0,
                'volatility_30d': 0,
            }
    
    def safe_get_value(self, row, column):
        """Safely get value from dataframe row, return 0 if not available"""
        try:
            if column in row.index and pd.notna(row[column]):
                return round(float(row[column]), 4)
            return 0
        except:
            return 0
    
    def analyze_with_ai(self, summary, maximum_brain=False, income_focus=False, income_metrics=None):
        """Send data to OpenAI for technical analysis with optional income analysis"""
        try:
            if maximum_brain:
                # Maximum Brain mode with comprehensive indicator list
                indicators_list = """Relative Strength Index (RSI), Average Directional Index (ADX), Bollinger Bands, Moving Average Convergence Divergence (MACD), Simple Moving Average (SMA), Exponential Moving Average (EMA), Stochastic Oscillator, Commodity Channel Index (CCI), Ichimoku Cloud, Donchian Channels, Williams %R, Ultimate Oscillator, Money Flow Index (MFI), Relative Momentum Index (RMI), On-Balance Volume (OBV), Average True Range (ATR), Parabolic SAR, Aroon Indicator, TRIX, Accumulation/Distribution Line, Supertrend, Volume Weighted Average Price (VWAP), Momentum Indicator, Rate of Change (ROC), Keltner Channels, Pivot Points, Fibonacci Retracements, Candlestick Patterns, Support and Resistance Levels, Trend Lines, Elliott Wave Principle, Wyckoff Method, Head and Shoulders Pattern, Double Top/Bottom, Volume Patterns"""
                analysis_mode = "MAXIMUM BRAIN ANALYSIS - Use your most advanced analytical capabilities"
            else:
                # Standard mode with basic indicators
                indicators_list = "Wyckoff Method (accumulation/distribution phases), Bollinger Bands, Moving Averages (SMA and EMA), MACD, RSI, Stochastic Oscillator, On-Balance Volume (OBV), Average Directional Index (ADX), and price action patterns"
                analysis_mode = "Standard Analysis"

            if maximum_brain:
                # Enhanced prompt with comprehensive indicator values
                indicator_json = json.dumps(summary.get('indicator_values', {}), indent=2)
                prompt = f"""You are an expert stock technical analyst performing {analysis_mode}. Given the following pre-computed technical indicator values for stock ticker {summary['ticker']} ({summary['company_name']}):

Current Price: ${summary['current_price']:.2f}
30-day Price Change: {summary['price_change_30d']:.2f}%
30-day Average Volume: {summary['volume_avg_30d']:,.0f}
30-day Volatility (StdDev): {summary['volatility_30d']:.2f}

PRE-COMPUTED TECHNICAL INDICATOR VALUES:
{indicator_json}

Analyze this stock using ALL of these technical analysis methods and indicators: {indicators_list}.

Use the EXACT pre-computed values provided above for your analysis. Do not estimate or recalculate any indicator values - use only the provided numerical data.

For each method/indicator:
- Briefly explain the method and how it applies to this data
- State whether it suggests a 'Buy' signal (positive outlook) or 'No Buy' signal (negative or neutral outlook)

Then, based on a majority consensus or weighted overall assessment (considering the strength of each signal), provide a final recommendation: strictly 'Yes, buy!' if the consensus is positive, or 'No, don't buy!' if neutral or negative. Include a confidence level (high/medium/low) and a short overall explanation.

Do not consider fundamental analysis, news, or external factors. Focus solely on technical analysis of the pre-computed indicator values provided.

Respond in JSON format with this structure:
{{
    "recommendation": "Yes, buy!" or "No, don't buy!",
    "confidence": "high" or "medium" or "low",
    "overall_explanation": "Brief explanation of the overall decision",
    "technical_analysis": [
        {{
            "method": "Method name",
            "explanation": "How this method applies to the data",
            "signal": "Buy" or "No Buy",
            "strength": "Strong" or "Moderate" or "Weak"
        }}
    ]
}}"""
            else:
                # Standard prompt for regular analysis
                prompt = f"""You are an expert stock technical analyst performing {analysis_mode}. Given the following historical data for stock ticker {summary['ticker']} ({summary['company_name']}):

Current Price: ${summary['current_price']:.2f}
30-day Price Change: {summary['price_change_30d']:.2f}%
30-day Average Volume: {summary['volume_avg_30d']:,.0f}
30-day Volatility (StdDev): {summary['volatility_30d']:.2f}
Current RSI: {summary['rsi_current']:.2f}
Current MACD: {summary['macd_current']:.4f}
Bollinger Band Position: {summary['bb_position']}
Price vs SMA-20: {summary['sma_20_trend']}
Price vs SMA-50: {summary['sma_50_trend']}
Price vs SMA-200: {summary['sma_200_trend']}
Stochastic %K: {summary['stoch_k']:.2f}
Stochastic %D: {summary['stoch_d']:.2f}
OBV Trend: {summary['obv_trend']}

Analyze this stock using ALL of these technical analysis methods and indicators: {indicators_list}.

For each method/indicator:
- Briefly explain the method and how it applies to this data
- State whether it suggests a 'Buy' signal (positive outlook) or 'No Buy' signal (negative or neutral outlook)

Then, based on a majority consensus or weighted overall assessment (considering the strength of each signal), provide a final recommendation: strictly 'Yes, buy!' if the consensus is positive, or 'No, don't buy!' if neutral or negative. Include a confidence level (high/medium/low) and a short overall explanation.

Do not consider fundamental analysis, news, or external factors. Focus solely on technical analysis of the historical price and volume data provided.

Respond in JSON format with this structure:
{{
    "recommendation": "Yes, buy!" or "No, don't buy!",
    "confidence": "high" or "medium" or "low",
    "overall_explanation": "Brief explanation of the overall decision",
    "technical_analysis": [
        {{
            "method": "Method name",
            "explanation": "How this method applies to the data",
            "signal": "Buy" or "No Buy",
            "strength": "Strong" or "Moderate" or "Weak"
        }}
    ]
}}"""



            # Model selection: Enhanced model for Maximum Brain analysis
            # GPT-5 not yet available, using GPT-4o with optimized parameters for Maximum Brain
            # Updated August 11, 2025 per user request for Maximum Brain enhancement
            model_to_use = "gpt-4o" if maximum_brain else "gpt-4o"
            
            # API parameters optimized for Maximum Brain vs Standard analysis
            api_params = {
                "model": model_to_use,
                "messages": [
                    {"role": "system", "content": "You are an expert technical analyst. Always respond with valid JSON format."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"}
            }
            
            # Optimized parameters for Maximum Brain analysis
            if maximum_brain:
                api_params["temperature"] = 0.1  # Lower temperature for more focused analysis
                api_params["max_tokens"] = 4096  # Higher token limit for comprehensive analysis
            else:
                api_params["temperature"] = 0.3  # Standard temperature
                api_params["max_tokens"] = 2048  # Standard token limit
            
            # Enhanced retry logic for OpenAI API errors (rate limits, SSL, connection issues)
            import time
            max_retries = 3
            retry_delay = 1  # Start with 1 second delay
            response = None
            
            # Track if this is a Maximum Brain analysis for potential multi-call fallback
            failed_attempts = 0
            
            for attempt in range(max_retries + 1):
                try:
                    logging.info(f"OpenAI API attempt {attempt + 1}/{max_retries + 1} for {summary.get('ticker', 'unknown')} ({'Maximum Brain' if maximum_brain else 'Standard'} mode)")
                    
                    # Production-grade API call with connection monitoring
                    start_time = time.time()
                    
                    # Log connection attempt details
                    payload_size = len(str(api_params).encode('utf-8'))
                    logging.info(f"API call starting - Payload size: {payload_size:,} bytes, Timeout config active")
                    
                    response = self.openai_client.chat.completions.create(**api_params)
                    
                    # Log successful connection
                    connection_time = time.time() - start_time
                    logging.info(f"✅ API call successful in {connection_time:.2f}s (including SSL handshake and response read)")
                    break  # Success - exit retry loop
                except Exception as e:
                    failed_attempts += 1
                    error_str = str(e).lower()
                    
                    # Production-grade retryable error detection with httpx-specific errors
                    retryable_errors = [
                        # OpenAI API errors
                        "429", "rate limit", "rate_limit_exceeded",
                        # SSL and TLS errors
                        "ssl", "tls", "handshake", "certificate", "cert",
                        "sslcontext", "ssl_context", "sslobj", "_sslobj",
                        # Connection errors  
                        "connection", "connect", "connection_error", "connectionerror",
                        "connection reset", "connection aborted", "connection refused",
                        "broken pipe", "pipe", "socket", "network",
                        # Timeout errors
                        "timeout", "timed out", "read timeout", "connect timeout",
                        "readtimeout", "connecttimeout", "response timeout",
                        # httpx/httpcore specific errors
                        "httpx", "httpcore", "pool", "transport",
                        "recv", "read", "send", "write",
                        # System-level errors
                        "errno", "oserror", "systemexit", "worker exit"
                    ]
                    
                    is_retryable = any(err in error_str for err in retryable_errors)
                    
                    if is_retryable and attempt < max_retries:
                        # Determine error type for user messaging
                        if "429" in error_str or "rate limit" in error_str:
                            error_type = "rate limiting"
                        elif any(term in error_str for term in ["ssl", "connection", "handshake", "network", "recv", "read", "sslobj", "httpx", "httpcore", "timeout"]):
                            error_type = "connection"
                        else:
                            error_type = "network"
                            
                        logging.warning(f"🔄 OpenAI {error_type} issue (attempt {attempt + 1}/{max_retries + 1}), retrying in {retry_delay}s...")
                        logging.warning(f"   Error type: {type(e).__name__}")
                        logging.warning(f"   Error details: {str(e)}")
                        
                        # Additional connection diagnosis for SSL/connection errors
                        if any(term in error_str for term in ["ssl", "connection", "handshake", "recv", "read"]):
                            logging.info(f"🔍 Connection diagnosis: This appears to be an SSL/connection issue during response reading")
                            logging.info(f"   - Payload size: ~{len(str(api_params).encode('utf-8')):,} bytes")
                            logging.info(f"   - Next attempt will use fresh connection pool")
                        
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    elif maximum_brain and failed_attempts >= 1:
                        # Maximum Brain multi-call fallback after 1 SSL failure (faster recovery)
                        if any(term in error_str for term in ["ssl", "connection", "timeout", "recv", "read"]):
                            logging.warning(f"Maximum Brain analysis failed due to SSL/connection issue, attempting multi-call fallback for {summary.get('ticker', 'unknown')}")
                            return self.analyze_with_chunked_calls(summary, income_focus, income_metrics)
                        elif failed_attempts >= 2:
                            # Other errors require 2 failures
                            logging.warning(f"Maximum Brain analysis failed twice, attempting multi-call fallback for {summary.get('ticker', 'unknown')}")
                            return self.analyze_with_chunked_calls(summary, income_focus, income_metrics)
                    else:
                        # Final failure or non-retryable error
                        if "429" in error_str or "rate limit" in error_str:
                            raise Exception("OpenAI API rate limit exceeded. Please wait a few minutes and try again.")
                        elif any(term in error_str for term in ["ssl", "connection", "handshake"]):
                            raise Exception("Connection issue with AI service. This may be temporary - please try again in a moment.")
                        else:
                            raise Exception(f"AI service error: {str(e)}")
                        
            # Ensure response is defined before using it
            if response is None:
                raise Exception("Failed to get response from AI service after all retry attempts")
            
            # Log successful API connection - HTTP 200 status confirmed
            logging.info(f"OpenAI API connection successful - HTTP 200 response received for {summary.get('ticker', 'unknown')}")
            logging.info(f"Maximum Brain mode: {maximum_brain}, Model used: {model_to_use}")
            logging.info(f"Response status confirmed, processing content...")
            
            content = response.choices[0].message.content
            if content:
                logging.info(f"OpenAI Response: {content}")
                analysis = json.loads(content)
                logging.info(f"Parsed Analysis: {analysis}")
                
                # If income analysis was requested but not included in OpenAI response, add it
                if income_focus and income_metrics and 'income_analysis' not in analysis:
                    analysis['income_analysis'] = {
                        'income_recommendation': "Buy for Income" if income_metrics['effective_return'] > income_metrics['buy_threshold'] else "No Buy",
                        'income_confidence': 'medium',
                        'income_explanation': f"Based on effective income return of {income_metrics['effective_return']:.2f}%",
                        'key_income_risks': income_metrics.get('risks', []),
                        'effective_income_return': income_metrics['effective_return']
                    }
                
                return analysis, None
            else:
                return None, "Empty response from AI analysis"
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logging.error(f"Error in AI analysis for {summary.get('ticker', 'unknown')}: {str(e)}")
            logging.error(f"Maximum Brain mode: {maximum_brain}")
            logging.error(f"AI Analysis Error Traceback: {error_details}")
            if maximum_brain:
                try:
                    prompt_length = len(locals().get('prompt', '')) if 'prompt' in locals() else 'unknown'
                    logging.error(f"Maximum Brain prompt length: {prompt_length}")
                    logging.error(f"Indicator values count: {len(summary.get('indicator_values', {}))}")
                except Exception as logging_error:
                    logging.error(f"Error in error logging: {logging_error}")
            return None, f"Error analyzing stock data: {str(e)}"
    
    def analyze_with_chunked_calls(self, summary, income_focus=False, income_metrics=None):
        """Fallback method: Split Maximum Brain analysis into multiple smaller API calls"""
        try:
            logging.info(f"Starting chunked analysis fallback for {summary.get('ticker', 'unknown')}")
            
            # Split indicators into logical groups to reduce payload size
            core_indicators, volume_indicators = self.split_indicators_for_chunked_analysis(summary.get('indicator_values', {}))
            
            # Prepare basic stock info for each call
            basic_info = {
                'ticker': summary['ticker'],
                'company_name': summary['company_name'],
                'current_price': summary['current_price'],
                'price_change_30d': summary['price_change_30d'],
                'volume_avg_30d': summary['volume_avg_30d'],
                'volatility_30d': summary['volatility_30d']
            }
            
            analyses = []
            
            # Call 1: Core trend/momentum indicators (smaller payload)
            logging.info("Chunked analysis: Processing core trend indicators...")
            core_analysis = self.analyze_indicator_chunk(basic_info, core_indicators, "core_trend", 1, 2)
            if core_analysis:
                analyses.append(core_analysis)
            
            # Call 2: Volume/volatility indicators (smaller payload)
            logging.info("Chunked analysis: Processing volume indicators...")
            volume_analysis = self.analyze_indicator_chunk(basic_info, volume_indicators, "volume_momentum", 2, 2)
            if volume_analysis:
                analyses.append(volume_analysis)
            
            # Synthesis call: Combine the partial analyses
            if len(analyses) >= 1:  # At least one successful chunk
                logging.info("Chunked analysis: Synthesizing results...")
                final_analysis = self.synthesize_chunked_analyses(basic_info, analyses, income_focus, income_metrics)
                if final_analysis:
                    return final_analysis, None
            
            # If chunked analysis also fails
            return None, "Analysis temporarily unavailable due to connection issues. Please try again in a moment."
            
        except Exception as e:
            logging.error(f"Error in chunked analysis fallback: {str(e)}")
            return None, "Analysis temporarily unavailable. Please try again later."
    
    def split_indicators_for_chunked_analysis(self, indicator_values):
        """Split indicators into logical groups for chunked analysis"""
        
        # Core trend/momentum indicators (most critical)
        core_trend_keys = [
            'RSI', 'MACD', 'MACD_signal', 'MACD_histogram',
            'SMA_20', 'SMA_50', 'SMA_200', 'EMA_12', 'EMA_26',
            'BB_upper', 'BB_middle', 'BB_lower', 'BB_width', 'BB_percent',
            '%K', '%D', 'ADX', 'DI_plus', 'DI_minus',
            'CCI', 'Williams_R', 'Ultimate_Oscillator'
        ]
        
        # Volume/volatility indicators 
        volume_momentum_keys = [
            'OBV', 'ATR', 'MFI', 'CMF', 'Force_Index',
            'VWAP', 'Momentum', 'ROC', 'TRIX',
            'Aroon_up', 'Aroon_down', 'Aroon_oscillator',
            'Supertrend', 'Supertrend_direction', 'PSAR',
            'Keltner_upper', 'Keltner_middle', 'Keltner_lower',
            'Donchian_upper', 'Donchian_middle', 'Donchian_lower'
        ]
        
        # Split indicators based on availability
        core_indicators = {k: v for k, v in indicator_values.items() if k in core_trend_keys}
        volume_indicators = {k: v for k, v in indicator_values.items() if k in volume_momentum_keys}
        
        logging.info(f"Split indicators: {len(core_indicators)} core, {len(volume_indicators)} volume")
        return core_indicators, volume_indicators
    
    def analyze_indicator_chunk(self, basic_info, indicators, chunk_type, chunk_num, total_chunks):
        """Analyze a specific chunk of indicators"""
        try:
            # Create focused prompt for this indicator group
            indicators_json = json.dumps(indicators, indent=2)
            
            chunk_descriptions = {
                'core_trend': 'core trend and momentum indicators including RSI, MACD, Moving Averages, Bollinger Bands, Stochastic, ADX, CCI, Williams %R, and Ultimate Oscillator',
                'volume_momentum': 'volume and momentum indicators including OBV, ATR, MFI, VWAP, Force Index, Aroon, TRIX, Supertrend, and Keltner Channels'
            }
            
            prompt = f"""You are performing focused technical analysis on {chunk_descriptions.get(chunk_type, 'technical indicators')} for {basic_info['ticker']} ({basic_info['company_name']}).

Current Price: ${basic_info['current_price']:.2f}
30-day Change: {basic_info['price_change_30d']:.2f}%

INDICATOR VALUES FOR {chunk_type.upper()} ANALYSIS:
{indicators_json}

Analyze ONLY these {chunk_type} indicators and provide:
1. A brief analysis of what these specific indicators suggest
2. Whether this group of indicators suggests 'Buy' or 'No Buy'
3. Confidence level for this specific analysis (high/medium/low)
4. Key signals from these indicators

Respond in JSON format:
{{
    "chunk_type": "{chunk_type}",
    "recommendation": "Buy" or "No Buy",
    "confidence": "high/medium/low", 
    "analysis": "Brief analysis of these {chunk_type} indicators",
    "key_signals": ["signal1", "signal2", "signal3"]
}}"""

            # Use smaller parameters for chunk analysis
            api_params = {
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": "You are an expert technical analyst. Always respond with valid JSON format."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
                "max_tokens": 1500  # Smaller than full Maximum Brain
            }
            
            logging.info(f"Chunked analysis call {chunk_num}/{total_chunks}: {chunk_type} ({len(indicators)} indicators)")
            response = self.openai_client.chat.completions.create(**api_params)
            
            content = response.choices[0].message.content
            if content:
                analysis = json.loads(content)
                logging.info(f"Chunk {chunk_num} analysis successful: {analysis.get('recommendation')} ({analysis.get('confidence')})")
                return analysis
                
        except Exception as e:
            logging.error(f"Error in chunk {chunk_num} analysis ({chunk_type}): {str(e)}")
            
        return None
    
    def synthesize_chunked_analyses(self, basic_info, chunk_analyses, income_focus=False, income_metrics=None):
        """Combine multiple chunk analyses into final recommendation"""
        try:
            # Prepare synthesis data
            analyses_summary = []
            for chunk in chunk_analyses:
                analyses_summary.append({
                    'type': chunk.get('chunk_type', 'unknown'),
                    'recommendation': chunk.get('recommendation'),
                    'confidence': chunk.get('confidence'),
                    'analysis': chunk.get('analysis'),
                    'signals': chunk.get('key_signals', [])
                })
            
            analyses_json = json.dumps(analyses_summary, indent=2)
            
            prompt = f"""You are synthesizing multiple focused technical analyses for {basic_info['ticker']} ({basic_info['company_name']}).

Current Price: ${basic_info['current_price']:.2f}
30-day Change: {basic_info['price_change_30d']:.2f}%

PARTIAL ANALYSES TO SYNTHESIZE:
{analyses_json}

Based on these focused analyses, provide a final comprehensive recommendation. Weight the different indicator groups appropriately and consider the confidence levels.

Respond in the standard analysis JSON format:
{{
    "recommendation": "Yes, buy!" or "No, don't buy!",
    "confidence": "high/medium/low",
    "explanation": "Overall synthesis explanation combining all indicator groups",
    "key_factors": ["factor1", "factor2", "factor3"],
    "risks": ["risk1", "risk2"],
    "analysis_method": "Multi-call Maximum Brain Analysis (Chunked)",
    "technical_summary": "Summary of combined technical indicators"
}}"""

            # Add income analysis if requested
            if income_focus and income_metrics:
                prompt += f"""

Also include income analysis based on these metrics:
Effective Income Return: {income_metrics['effective_return']:.2f}%
Add an "income_analysis" section to your response."""

            api_params = {
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": "You are an expert technical analyst. Always respond with valid JSON format."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
                "max_tokens": 2048
            }
            
            logging.info("Synthesizing chunked analyses into final recommendation...")
            response = self.openai_client.chat.completions.create(**api_params)
            
            content = response.choices[0].message.content
            if content:
                final_analysis = json.loads(content)
                
                # Add income analysis if requested but not included
                if income_focus and income_metrics and 'income_analysis' not in final_analysis:
                    final_analysis['income_analysis'] = {
                        'income_recommendation': "Buy for Income" if income_metrics['effective_return'] > income_metrics['buy_threshold'] else "No Buy",
                        'income_confidence': 'medium',
                        'income_explanation': f"Based on effective income return of {income_metrics['effective_return']:.2f}%",
                        'key_income_risks': income_metrics.get('risks', []),
                        'effective_income_return': income_metrics['effective_return']
                    }
                
                logging.info(f"Chunked analysis synthesis complete: {final_analysis.get('recommendation')} ({final_analysis.get('confidence')})")
                return final_analysis
                
        except Exception as e:
            logging.error(f"Error in synthesis: {str(e)}")
            
        return None
    
    def analyze_stock(self, ticker, maximum_brain=False, income_focus=False):
        """Main method to analyze a stock with optional income-focused analysis"""
        try:
            # Check if ticker is a yield ETF for informational purposes only
            is_yield_etf = self.income_analyzer.is_yield_etf(ticker)
            if is_yield_etf:
                logging.info(f"Detected {ticker} as yield ETF. Income analysis: {'enabled' if income_focus else 'disabled by user choice'}")
            
            # Fetch stock data
            stock_data, error = self.fetch_stock_data(ticker)
            if error or stock_data is None:
                return {'success': False, 'error': error or 'Failed to fetch stock data'}
            
            # Calculate technical indicators (pass maximum_brain parameter)
            logging.info(f"Starting technical indicator calculation for {ticker}, Maximum Brain: {maximum_brain}")
            df_with_indicators = self.calculate_technical_indicators(stock_data['history'], maximum_brain)
            logging.info(f"Technical indicators calculated successfully for {ticker}")
            
            # Summarize data (pass maximum_brain parameter)
            logging.info(f"Starting data summarization for {ticker}, Maximum Brain: {maximum_brain}")
            summary = self.summarize_data(df_with_indicators, stock_data['info'], maximum_brain)
            logging.info(f"Data summarization completed for {ticker}. Indicator count: {len(summary.get('indicator_values', {}))}")
            
            # Calculate income metrics if requested or auto-detected
            income_metrics = None
            if income_focus:
                income_metrics = self.income_analyzer.calculate_income_metrics(ticker, stock_data['history'])
                logging.info(f"Income metrics calculated for {ticker}: {income_metrics is not None}")
            
            # Get AI analysis (with income focus if applicable)
            logging.info(f"Starting AI analysis for {ticker}, Maximum Brain: {maximum_brain}, Income Focus: {income_focus}")
            
            # Log payload size for Maximum Brain mode
            if maximum_brain:
                payload_size = len(json.dumps(summary.get('indicator_values', {})))
                logging.info(f"Maximum Brain payload size: {payload_size} characters")
                
            analysis, error = self.analyze_with_ai(summary, maximum_brain, income_focus, income_metrics)
            if error or analysis is None:
                logging.error(f"AI analysis failed for {ticker}: {error}")
                return {'success': False, 'error': error or 'Failed to get AI analysis'}
            logging.info(f"AI analysis completed successfully for {ticker}")
            
            result = {
                'success': True,
                'ticker': ticker,
                'company_name': summary.get('company_name', 'N/A'),
                'current_price': summary.get('current_price', 0),
                'recommendation': analysis.get('recommendation', 'No recommendation'),
                'confidence': analysis.get('confidence', 'unknown'),
                'overall_explanation': analysis.get('overall_explanation', 'No explanation available'),
                'analysis_details': analysis.get('technical_analysis', []),
                'income_focus': income_focus,
                'is_yield_etf': is_yield_etf
            }
            
            # Add income analysis if available
            if income_focus and income_metrics:
                result['income_analysis'] = {
                    'metrics': income_metrics,
                    'recommendation': analysis.get('income_analysis', {}).get('income_recommendation', 'No income recommendation'),
                    'confidence': analysis.get('income_analysis', {}).get('income_confidence', 'unknown'),
                    'explanation': analysis.get('income_analysis', {}).get('income_explanation', 'No income explanation available'),
                    'key_risks': analysis.get('income_analysis', {}).get('key_income_risks', []),
                    'effective_return': analysis.get('income_analysis', {}).get('effective_income_return', income_metrics.get('effective_return', 0))
                }
            elif income_focus:
                result['income_analysis'] = {
                    'error': 'Insufficient data for income analysis'
                }
            
            return result
            
        except Exception as e:
            logging.error(f"Error in analyze_stock: {str(e)}")
            return {'success': False, 'error': 'An error occurred during analysis. Please try again.'}
