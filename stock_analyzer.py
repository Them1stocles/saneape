import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
from openai import OpenAI
import logging

# Technical analysis libraries for Maximum Brain mode
import stockstats
from scipy.signal import find_peaks
from income_analyzer import IncomeAnalyzer

class StockAnalyzer:
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.income_analyzer = IncomeAnalyzer()
    
    def fetch_stock_data(self, ticker):
        """Fetch historical stock data using yfinance"""
        try:
            # Set a temporary cache directory to avoid I/O errors
            import tempfile
            temp_cache_dir = tempfile.mkdtemp(prefix="yfinance_cache_")
            os.environ['YFINANCE_CACHE_DIR'] = temp_cache_dir
            
            # Clear any existing cache files that might be corrupted
            cache_locations = [
                os.path.expanduser("~/.cache/py-yfinance"),
                os.path.join(os.getcwd(), ".cache/py-yfinance"),
                "/home/runner/workspace/.cache/py-yfinance"
            ]
            
            for cache_dir in cache_locations:
                if os.path.exists(cache_dir):
                    try:
                        import shutil
                        shutil.rmtree(cache_dir)
                        logging.info(f"Cleared cache at: {cache_dir}")
                    except Exception as e:
                        logging.warning(f"Could not clear cache at {cache_dir}: {e}")
            
            stock = yf.Ticker(ticker)
            
            # Get 2 years of historical data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=730)  # 2 years
            
            hist = stock.history(start=start_date, end=end_date)
            
            if hist.empty:
                return None, f"No data found for ticker {ticker}. Please verify the ticker symbol."
            
            # Get additional info
            info = stock.info
            
            # Clean up temp cache
            try:
                import shutil
                shutil.rmtree(temp_cache_dir)
            except:
                pass
            
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
            
            # Try to use stockstats, but fall back to pure pandas if it fails
            try:
                # Ensure proper column names for stockstats
                df_clean = df.copy()
                df_clean.columns = df_clean.columns.str.lower()
                
                # Convert to StockDataFrame for enhanced functionality
                stockstats_df = stockstats.StockDataFrame.retype(df_clean)
                use_stockstats = True
            except Exception as stockstats_error:
                logging.warning(f"Stockstats conversion failed: {stockstats_error}. Using pure pandas calculations.")
                use_stockstats = False
                stockstats_df = None
            
            # === CORE INDICATORS (pandas_ta alternatives using stockstats and custom) ===
            
            # 1. RSI (Relative Strength Index)
            if use_stockstats:
                try:
                    stock_df['rsi_14'] = stockstats_df['rsi']
                except:
                    use_stockstats = False
            
            if not use_stockstats:
                # Pure pandas RSI calculation
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                stock_df['rsi_14'] = 100 - (100 / (1 + rs))
            
            # 2. MACD (Moving Average Convergence Divergence)
            if use_stockstats:
                try:
                    stock_df['macd'] = stockstats_df['macd']
                    stock_df['macd_signal'] = stockstats_df['macds']
                    stock_df['macd_histogram'] = stockstats_df['macdh']
                except:
                    use_stockstats = False
                    
            if not use_stockstats:
                # Pure pandas MACD calculation
                exp1 = df['Close'].ewm(span=12).mean()
                exp2 = df['Close'].ewm(span=26).mean()
                stock_df['macd'] = exp1 - exp2
                stock_df['macd_signal'] = stock_df['macd'].ewm(span=9).mean()
                stock_df['macd_histogram'] = stock_df['macd'] - stock_df['macd_signal']
            
            # 3-5. Moving Averages
            if use_stockstats:
                try:
                    stock_df['sma_20'] = stockstats_df['close_20_sma']
                    stock_df['sma_50'] = stockstats_df['close_50_sma'] 
                    stock_df['sma_200'] = stockstats_df['close_200_sma']
                    stock_df['ema_12'] = stockstats_df['close_12_ema']
                    stock_df['ema_26'] = stockstats_df['close_26_ema']
                except:
                    use_stockstats = False
                    
            if not use_stockstats:
                # Pure pandas calculation
                stock_df['sma_20'] = df['Close'].rolling(20).mean()
                stock_df['sma_50'] = df['Close'].rolling(50).mean()
                stock_df['sma_200'] = df['Close'].rolling(200).mean()
                stock_df['ema_12'] = df['Close'].ewm(span=12).mean()
                stock_df['ema_26'] = df['Close'].ewm(span=26).mean()
            
            # 6. Bollinger Bands
            if use_stockstats:
                try:
                    stock_df['bb_upper'] = stockstats_df['boll_ub']
                    stock_df['bb_middle'] = stockstats_df['boll']
                    stock_df['bb_lower'] = stockstats_df['boll_lb']
                except:
                    use_stockstats = False
                    
            if not use_stockstats:
                # Pure pandas Bollinger Bands
                sma_20 = df['Close'].rolling(20).mean()
                std_20 = df['Close'].rolling(20).std()
                stock_df['bb_upper'] = sma_20 + (std_20 * 2)
                stock_df['bb_middle'] = sma_20
                stock_df['bb_lower'] = sma_20 - (std_20 * 2)
            
            # 7. Stochastic Oscillator - Always use pure pandas (more reliable)
            low_14 = df['Low'].rolling(14).min()
            high_14 = df['High'].rolling(14).max()
            stock_df['stoch_k'] = 100 * ((df['Close'] - low_14) / (high_14 - low_14))
            stock_df['stoch_d'] = stock_df['stoch_k'].rolling(3).mean()
            
            # 8. ADX (Average Directional Index) - Always use simplified calculation
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift())
            low_close = np.abs(df['Low'] - df['Close'].shift())
            tr = np.maximum(high_low, np.maximum(high_close, low_close))
            atr = tr.rolling(14).mean()
            stock_df['adx'] = atr * 5  # Simplified ADX proxy
            
            # 9. CCI (Commodity Channel Index) - Always use pure pandas
            tp = (df['High'] + df['Low'] + df['Close']) / 3
            sma_tp = tp.rolling(20).mean()
            mad = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean())
            stock_df['cci'] = (tp - sma_tp) / (0.015 * mad)
            
            # 10. Williams %R - Always use pure pandas
            high_14 = df['High'].rolling(14).max()
            low_14 = df['Low'].rolling(14).min()
            stock_df['williams_r'] = -100 * ((high_14 - df['Close']) / (high_14 - low_14))
            
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
            
            # 26. Fibonacci Retracements - Basic levels
            recent_high = df['High'].rolling(50).max()
            recent_low = df['Low'].rolling(50).min()
            diff = recent_high - recent_low
            stock_df['fib_23.6'] = recent_high - (diff * 0.236)
            stock_df['fib_38.2'] = recent_high - (diff * 0.382)
            stock_df['fib_61.8'] = recent_high - (diff * 0.618)
            
            # 27. Support/Resistance Levels using peak detection
            try:
                highs = df['High'].values
                lows = df['Low'].values
                resistance_peaks, _ = find_peaks(highs, distance=10, prominence=highs.std()*0.5)
                support_peaks, _ = find_peaks(-lows, distance=10, prominence=lows.std()*0.5)
                
                stock_df['resistance_level'] = np.nan
                stock_df['support_level'] = np.nan
                if len(resistance_peaks) > 0:
                    stock_df.iloc[resistance_peaks, stock_df.columns.get_loc('resistance_level')] = highs[resistance_peaks]
                if len(support_peaks) > 0:
                    stock_df.iloc[support_peaks, stock_df.columns.get_loc('support_level')] = lows[support_peaks]
                    
                stock_df['resistance_level'] = stock_df['resistance_level'].ffill()
                stock_df['support_level'] = stock_df['support_level'].ffill()
            except:
                stock_df['resistance_level'] = df['High'].rolling(20).max()
                stock_df['support_level'] = df['Low'].rolling(20).min()
            
            # 28. RMI (Relative Momentum Index) - Custom RSI variant
            momentum_changes = df['Close'].diff(1).diff(1)  # Second-order momentum
            gain_rmi = momentum_changes.where(momentum_changes > 0, 0).rolling(14).mean()
            loss_rmi = (-momentum_changes.where(momentum_changes < 0, 0)).rolling(14).mean()
            rs_rmi = gain_rmi / loss_rmi
            stock_df['rmi'] = 100 - (100 / (1 + rs_rmi))
            
            # 29. Supertrend - Use calculated ATR
            hl2 = (df['High'] + df['Low']) / 2
            atr_mult = atr * 3
            upper_band = hl2 + atr_mult
            lower_band = hl2 - atr_mult
            stock_df['supertrend'] = np.where(df['Close'] <= lower_band, lower_band, 
                                            np.where(df['Close'] >= upper_band, upper_band, np.nan))
            stock_df['supertrend'] = stock_df['supertrend'].ffill()
            
            # 30-35. Pattern Detection Flags
            stock_df['trend_strength'] = abs(stock_df['adx'])
            stock_df['volume_trend'] = np.where(df['Volume'] > df['Volume'].rolling(20).mean(), 1, 0)
            stock_df['price_momentum'] = np.where(df['Close'] > df['Close'].shift(5), 1, 0)
            stock_df['volatility'] = df['Close'].rolling(20).std()
            stock_df['rsi_divergence'] = np.where((stock_df['rsi_14'] > 70) | (stock_df['rsi_14'] < 30), 1, 0)
            stock_df['macd_crossover'] = np.where(stock_df['macd'] > stock_df['macd_signal'], 1, 0)
            
            return stock_df
            
        except Exception as e:
            logging.error(f"Error calculating comprehensive indicators: {str(e)}")
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
                # Comprehensive indicator values for Maximum Brain Analysis
                latest_row = df.iloc[-1]
                summary['indicator_values'] = {
                    'RSI': self.safe_get_value(latest_row, 'rsi_14'),
                    'ADX': self.safe_get_value(latest_row, 'adx'),
                    'MACD': self.safe_get_value(latest_row, 'macd'),
                    'MACD_Signal': self.safe_get_value(latest_row, 'macd_signal'),
                    'MACD_Histogram': self.safe_get_value(latest_row, 'macd_histogram'),
                    'SMA_20': self.safe_get_value(latest_row, 'sma_20'),
                    'SMA_50': self.safe_get_value(latest_row, 'sma_50'),
                    'SMA_200': self.safe_get_value(latest_row, 'sma_200'),
                    'EMA_12': self.safe_get_value(latest_row, 'ema_12'),
                    'EMA_26': self.safe_get_value(latest_row, 'ema_26'),
                    'Bollinger_Upper': self.safe_get_value(latest_row, 'bb_upper'),
                    'Bollinger_Middle': self.safe_get_value(latest_row, 'bb_middle'),
                    'Bollinger_Lower': self.safe_get_value(latest_row, 'bb_lower'),
                    'Stochastic_K': self.safe_get_value(latest_row, 'stoch_k'),
                    'Stochastic_D': self.safe_get_value(latest_row, 'stoch_d'),
                    'CCI': self.safe_get_value(latest_row, 'cci'),
                    'Williams_R': self.safe_get_value(latest_row, 'williams_r'),
                    'MFI': self.safe_get_value(latest_row, 'mfi'),
                    'OBV': self.safe_get_value(latest_row, 'obv'),
                    'ATR': self.safe_get_value(latest_row, 'atr'),
                    'Ultimate_Oscillator': self.safe_get_value(latest_row, 'ultimate_osc'),
                    'TRIX': self.safe_get_value(latest_row, 'trix'),
                    'Momentum': self.safe_get_value(latest_row, 'momentum'),
                    'ROC': self.safe_get_value(latest_row, 'roc'),
                    'Donchian_Upper': self.safe_get_value(latest_row, 'donchian_upper'),
                    'Donchian_Lower': self.safe_get_value(latest_row, 'donchian_lower'),
                    'Keltner_Upper': self.safe_get_value(latest_row, 'keltner_upper'),
                    'Keltner_Lower': self.safe_get_value(latest_row, 'keltner_lower'),
                    'Aroon_Up': self.safe_get_value(latest_row, 'aroon_up'),
                    'Aroon_Down': self.safe_get_value(latest_row, 'aroon_down'),
                    'Parabolic_SAR': self.safe_get_value(latest_row, 'sar'),
                    'VWAP': self.safe_get_value(latest_row, 'vwap'),
                    'AD_Line': self.safe_get_value(latest_row, 'ad_line'),
                    'Tenkan_Sen': self.safe_get_value(latest_row, 'tenkan_sen'),
                    'Kijun_Sen': self.safe_get_value(latest_row, 'kijun_sen'),
                    'Pivot_Point': self.safe_get_value(latest_row, 'pivot'),
                    'Resistance_R1': self.safe_get_value(latest_row, 'r1'),
                    'Support_S1': self.safe_get_value(latest_row, 's1'),
                    'Fibonacci_23.6': self.safe_get_value(latest_row, 'fib_23.6'),
                    'Fibonacci_38.2': self.safe_get_value(latest_row, 'fib_38.2'),
                    'Fibonacci_61.8': self.safe_get_value(latest_row, 'fib_61.8'),
                    'Resistance_Level': self.safe_get_value(latest_row, 'resistance_level'),
                    'Support_Level': self.safe_get_value(latest_row, 'support_level'),
                    'RMI': self.safe_get_value(latest_row, 'rmi'),
                    'Supertrend': self.safe_get_value(latest_row, 'supertrend'),
                    'Trend_Strength': self.safe_get_value(latest_row, 'trend_strength'),
                    'Volume_Trend': self.safe_get_value(latest_row, 'volume_trend'),
                    'Price_Momentum': self.safe_get_value(latest_row, 'price_momentum'),
                    'Volatility': self.safe_get_value(latest_row, 'volatility'),
                    'RSI_Divergence_Flag': self.safe_get_value(latest_row, 'rsi_divergence'),
                    'MACD_Crossover_Flag': self.safe_get_value(latest_row, 'macd_crossover')
                }
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



            # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
            # do not change this unless explicitly requested by the user
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert technical analyst. Always respond with valid JSON format."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
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
            logging.error(f"Error in AI analysis: {str(e)}")
            return None, f"Error analyzing stock data: {str(e)}"
    
    def analyze_stock(self, ticker, maximum_brain=False, income_focus=False):
        """Main method to analyze a stock with optional income-focused analysis"""
        try:
            # Auto-detect if ticker is a yield ETF
            is_yield_etf = self.income_analyzer.is_yield_etf(ticker)
            if is_yield_etf and not income_focus:
                logging.info(f"Auto-detected {ticker} as yield ETF, enabling income analysis")
                income_focus = True
            
            # Fetch stock data
            stock_data, error = self.fetch_stock_data(ticker)
            if error or stock_data is None:
                return {'success': False, 'error': error or 'Failed to fetch stock data'}
            
            # Calculate technical indicators (pass maximum_brain parameter)
            df_with_indicators = self.calculate_technical_indicators(stock_data['history'], maximum_brain)
            
            # Summarize data (pass maximum_brain parameter)
            summary = self.summarize_data(df_with_indicators, stock_data['info'], maximum_brain)
            
            # Calculate income metrics if requested or auto-detected
            income_metrics = None
            if income_focus:
                income_metrics = self.income_analyzer.calculate_income_metrics(ticker, stock_data['history'])
                logging.info(f"Income metrics calculated for {ticker}: {income_metrics is not None}")
            
            # Get AI analysis (with income focus if applicable)
            analysis, error = self.analyze_with_ai(summary, maximum_brain, income_focus, income_metrics)
            if error or analysis is None:
                return {'success': False, 'error': error or 'Failed to get AI analysis'}
            
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
