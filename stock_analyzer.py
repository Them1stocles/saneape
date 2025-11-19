import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import google.generativeai as genai
import logging
import time

# Technical analysis libraries for Maximum Brain mode
import stockstats
from income_analyzer import IncomeAnalyzer

class StockAnalyzer:
    def __init__(self):
        # Configure Gemini client
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logging.warning("GEMINI_API_KEY not found in environment variables")
        else:
            genai.configure(api_key=api_key)
            
        self.income_analyzer = IncomeAnalyzer()
    
    def fetch_stock_data(self, ticker):
        """Fetch historical stock data using yfinance with robust error handling"""
        try:
            import yfinance as yf
            
            stock = yf.Ticker(ticker)
            
            # Get 2 years of historical data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=730)  # 2 years
            
            # Try multiple approaches to handle timezone and I/O issues
            hist = None
            info = None
            
            # First attempt: standard approach
            try:
                hist = stock.history(start=start_date, end=end_date)
                info = stock.info
            except (OSError, IOError) as io_error:
                if "Input/output error" in str(io_error) or "Errno 5" in str(io_error):
                    logging.warning(f"I/O error for {ticker}, trying alternative approach: {str(io_error)}")
                    # Try with different parameters to avoid timezone issues
                    try:
                        # Use period parameter instead of start/end dates to avoid timezone parsing
                        hist = stock.history(period="2y")
                        info = stock.info
                    except Exception as fallback_error:
                        logging.warning(f"Fallback approach also failed for {ticker}: {str(fallback_error)}")
                        # Try minimal data fetch
                        try:
                            hist = stock.history(period="1y")  # Try 1 year if 2 years fails
                            info = {}  # Use empty info if info fetch fails
                        except Exception:
                            raise io_error  # Re-raise original error if all attempts fail
                else:
                    raise  # Re-raise if it's not the I/O error we're handling
            
            if hist is None or hist.empty:
                return None, f"No data found for ticker {ticker}. Please verify the ticker symbol."
            
            return {
                'history': hist,
                'info': info or {},
                'ticker': ticker
            }, None
            
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Error fetching data for {ticker}: {error_msg}")
            # More detailed error logging
            import traceback
            logging.error(f"Traceback: {traceback.format_exc()}")
            
            # Provide more specific error messages
            if "Input/output error" in error_msg or "Errno 5" in error_msg:
                return None, f"System I/O error occurred while fetching data for {ticker}. This is typically a temporary issue - please try again in a few moments."
            elif "No data found" in error_msg or "404" in error_msg:
                return None, f"No data found for ticker {ticker}. Please verify the ticker symbol exists on Yahoo Finance."
            else:
                return None, f"Error fetching data for {ticker}. Please verify the ticker symbol and try again."

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
        # ... (This method remains largely unchanged, just copying the logic from previous file)
        # For brevity in this rewrite, I'm assuming the logic is identical to the original file
        # I will include the full logic to ensure it works correctly.
        try:
            # Start with original dataframe for fallback calculations
            stock_df = df.copy()
            
            # Detailed logging initialization
            logging.info("=== STARTING COMPREHENSIVE INDICATOR CALCULATION ===")
            
            # Track indicator calculation success/failure
            indicator_calculation_log = {
                'successful': [],
                'failed': [],
                'zero_values': [],
                'missing_prerequisites': []
            }
            
            # Try to use stockstats, but fall back to pure pandas if it fails
            try:
                df_clean = df.copy()
                df_clean.columns = df_clean.columns.str.lower()
                stockstats_df = stockstats.StockDataFrame.retype(df_clean)
                use_stockstats = True
            except Exception as stockstats_error:
                logging.warning(f"Stockstats conversion failed: {stockstats_error}. Using pure pandas calculations.")
                use_stockstats = False
                stockstats_df = None
            
            # === CORE INDICATORS ===
            
            # 1. RSI
            try:
                if use_stockstats:
                    stock_df['rsi_14'] = stockstats_df['rsi']
                else:
                    delta = df['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rs = gain / loss
                    stock_df['rsi_14'] = 100 - (100 / (1 + rs))
                indicator_calculation_log['successful'].append("RSI")
            except Exception as e:
                indicator_calculation_log['failed'].append(f"RSI: {str(e)}")
                stock_df['rsi_14'] = 0

            # 2. MACD
            try:
                if use_stockstats:
                    stock_df['macd'] = stockstats_df['macd']
                    stock_df['macd_signal'] = stockstats_df['macds']
                    stock_df['macd_histogram'] = stockstats_df['macdh']
                else:
                    exp1 = df['Close'].ewm(span=12).mean()
                    exp2 = df['Close'].ewm(span=26).mean()
                    stock_df['macd'] = exp1 - exp2
                    stock_df['macd_signal'] = stock_df['macd'].ewm(span=9).mean()
                    stock_df['macd_histogram'] = stock_df['macd'] - stock_df['macd_signal']
                indicator_calculation_log['successful'].extend(["MACD", "MACD_Signal", "MACD_Histogram"])
            except Exception as e:
                indicator_calculation_log['failed'].append(f"MACD: {str(e)}")
                stock_df['macd'] = 0
                stock_df['macd_signal'] = 0
                stock_df['macd_histogram'] = 0

            # 3-5. Moving Averages
            try:
                if use_stockstats:
                    stock_df['sma_20'] = stockstats_df['close_20_sma']
                    stock_df['sma_50'] = stockstats_df['close_50_sma'] 
                    stock_df['sma_200'] = stockstats_df['close_200_sma']
                    stock_df['ema_12'] = stockstats_df['close_12_ema']
                    stock_df['ema_26'] = stockstats_df['close_26_ema']
                else:
                    stock_df['sma_20'] = df['Close'].rolling(20).mean()
                    stock_df['sma_50'] = df['Close'].rolling(50).mean()
                    stock_df['sma_200'] = df['Close'].rolling(200).mean()
                    stock_df['ema_12'] = df['Close'].ewm(span=12).mean()
                    stock_df['ema_26'] = df['Close'].ewm(span=26).mean()
                indicator_calculation_log['successful'].extend(['SMA_20', 'SMA_50', 'SMA_200', 'EMA_12', 'EMA_26'])
            except Exception as e:
                indicator_calculation_log['failed'].append(f"Moving Averages: {str(e)}")
                stock_df['sma_20'] = 0
                stock_df['sma_50'] = 0
                stock_df['sma_200'] = 0
                stock_df['ema_12'] = 0
                stock_df['ema_26'] = 0

            # 6. Bollinger Bands
            try:
                if use_stockstats:
                    stock_df['bb_upper'] = stockstats_df['boll_ub']
                    stock_df['bb_middle'] = stockstats_df['boll']
                    stock_df['bb_lower'] = stockstats_df['boll_lb']
                else:
                    sma_20 = df['Close'].rolling(20).mean()
                    std_20 = df['Close'].rolling(20).std()
                    stock_df['bb_upper'] = sma_20 + (std_20 * 2)
                    stock_df['bb_middle'] = sma_20
                    stock_df['bb_lower'] = sma_20 - (std_20 * 2)
                indicator_calculation_log['successful'].extend(['BB_Upper', 'BB_Middle', 'BB_Lower'])
            except Exception as e:
                indicator_calculation_log['failed'].append(f"Bollinger Bands: {str(e)}")
                stock_df['bb_upper'] = 0
                stock_df['bb_middle'] = 0
                stock_df['bb_lower'] = 0

            # 7. Stochastic Oscillator
            try:
                low_14 = df['Low'].rolling(14).min()
                high_14 = df['High'].rolling(14).max()
                stock_df['stoch_k'] = 100 * ((df['Close'] - low_14) / (high_14 - low_14))
                stock_df['stoch_d'] = stock_df['stoch_k'].rolling(3).mean()
                indicator_calculation_log['successful'].extend(['Stochastic_K', 'Stochastic_D'])
            except Exception as e:
                indicator_calculation_log['failed'].append(f"Stochastic: {str(e)}")
                stock_df['stoch_k'] = 0
                stock_df['stoch_d'] = 0

            # 8. ADX
            try:
                high_low = df['High'] - df['Low']
                high_close = np.abs(df['High'] - df['Close'].shift())
                low_close = np.abs(df['Low'] - df['Close'].shift())
                tr = np.maximum(high_low, np.maximum(high_close, low_close))
                atr = tr.rolling(14).mean()
                stock_df['adx'] = atr * 5  # Simplified ADX proxy
                stock_df['atr'] = atr
                indicator_calculation_log['successful'].extend(['ADX', 'ATR'])
            except Exception as e:
                indicator_calculation_log['failed'].append(f"ADX/ATR: {str(e)}")
                stock_df['adx'] = 0
                stock_df['atr'] = 0

            # 9. CCI
            try:
                tp = (df['High'] + df['Low'] + df['Close']) / 3
                sma_tp = tp.rolling(20).mean()
                mad = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean())
                stock_df['cci'] = (tp - sma_tp) / (0.015 * mad)
                indicator_calculation_log['successful'].append("CCI")
            except Exception as e:
                indicator_calculation_log['failed'].append(f"CCI: {str(e)}")
                stock_df['cci'] = 0

            # 10. Williams %R
            try:
                high_14 = df['High'].rolling(14).max()
                low_14 = df['Low'].rolling(14).min()
                stock_df['williams_r'] = -100 * ((high_14 - df['Close']) / (high_14 - low_14))
                indicator_calculation_log['successful'].append("Williams_R")
            except Exception as e:
                indicator_calculation_log['failed'].append(f"Williams %R: {str(e)}")
                stock_df['williams_r'] = 0

            # 11. MFI
            try:
                typical_price = (df['High'] + df['Low'] + df['Close']) / 3
                money_flow = typical_price * df['Volume']
                positive_flow = money_flow.where(typical_price.diff() > 0, 0).rolling(14).sum()
                negative_flow = money_flow.where(typical_price.diff() < 0, 0).rolling(14).sum()
                stock_df['mfi'] = 100 - (100 / (1 + positive_flow / negative_flow))
                indicator_calculation_log['successful'].append("MFI")
            except Exception as e:
                indicator_calculation_log['failed'].append(f"MFI: {str(e)}")
                stock_df['mfi'] = 0

            # 12. OBV
            stock_df['obv'] = (np.sign(df['Close'].diff()) * df['Volume']).cumsum()
            indicator_calculation_log['successful'].append("OBV")

            # 13. Ultimate Oscillator
            try:
                bp = df['Close'] - np.minimum(df['Low'], df['Close'].shift(1))
                tr = np.maximum(df['High'] - df['Low'], 
                               np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                                         abs(df['Low'] - df['Close'].shift(1))))
                avg7 = bp.rolling(7).sum() / tr.rolling(7).sum()
                avg14 = bp.rolling(14).sum() / tr.rolling(14).sum()
                avg28 = bp.rolling(28).sum() / tr.rolling(28).sum()
                stock_df['ultimate_osc'] = 100 * ((4 * avg7) + (2 * avg14) + avg28) / 7
                indicator_calculation_log['successful'].append("Ultimate_Oscillator")
            except Exception as e:
                indicator_calculation_log['failed'].append(f"Ultimate Oscillator: {str(e)}")
                stock_df['ultimate_osc'] = 0

            # 14. TRIX
            try:
                ema1 = df['Close'].ewm(span=14).mean()
                ema2 = ema1.ewm(span=14).mean()
                ema3 = ema2.ewm(span=14).mean()
                stock_df['trix'] = ema3.pct_change() * 10000
                indicator_calculation_log['successful'].append("TRIX")
            except Exception as e:
                indicator_calculation_log['failed'].append(f"TRIX: {str(e)}")
                stock_df['trix'] = 0

            # 15. Momentum & ROC
            stock_df['momentum'] = df['Close'] - df['Close'].shift(10)
            stock_df['roc'] = ((df['Close'] - df['Close'].shift(12)) / df['Close'].shift(12)) * 100
            indicator_calculation_log['successful'].extend(["Momentum", "ROC"])

            # 16. Donchian & Keltner Channels
            try:
                stock_df['donchian_upper'] = df['High'].rolling(20).max()
                stock_df['donchian_lower'] = df['Low'].rolling(20).min()
                stock_df['donchian_middle'] = (stock_df['donchian_upper'] + stock_df['donchian_lower']) / 2
                
                ema_20 = df['Close'].ewm(span=20).mean()
                atr_10 = stock_df['atr'].rolling(10).mean()
                stock_df['keltner_upper'] = ema_20 + (2 * atr_10)
                stock_df['keltner_lower'] = ema_20 - (2 * atr_10)
                stock_df['keltner_middle'] = ema_20
                indicator_calculation_log['successful'].extend(["Donchian", "Keltner"])
            except Exception as e:
                indicator_calculation_log['failed'].append(f"Channels: {str(e)}")

            # 17. Aroon
            try:
                aroon_length = 14
                high_idx = df['High'].rolling(aroon_length + 1).apply(lambda x: x.argmax(), raw=False)
                low_idx = df['Low'].rolling(aroon_length + 1).apply(lambda x: x.argmin(), raw=False)
                stock_df['aroon_up'] = ((aroon_length - high_idx) / aroon_length) * 100
                stock_df['aroon_down'] = ((aroon_length - low_idx) / aroon_length) * 100
                indicator_calculation_log['successful'].append("Aroon")
            except Exception as e:
                indicator_calculation_log['failed'].append(f"Aroon: {str(e)}")

            # 18. Parabolic SAR
            stock_df['sar'] = np.where(df['Close'] > df['Close'].ewm(span=20).mean(), 
                                      df['Low'].rolling(5).min(), 
                                      df['High'].rolling(5).max())
            
            # 19. VWAP
            vwap = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()
            stock_df['vwap'] = vwap
            
            # 20. Accumulation/Distribution Line
            clv = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / (df['High'] - df['Low'])
            clv = clv.fillna(0)
            stock_df['ad_line'] = (clv * df['Volume']).cumsum()
            
            # 21. Ichimoku Cloud
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

            # 22. Pivot Points
            stock_df['pivot'] = (df['High'] + df['Low'] + df['Close']) / 3
            stock_df['r1'] = (2 * stock_df['pivot']) - df['Low']
            stock_df['s1'] = (2 * stock_df['pivot']) - df['High']
            
            # 23. Fibonacci
            recent_high = df['High'].rolling(50).max()
            recent_low = df['Low'].rolling(50).min()
            diff = recent_high - recent_low
            stock_df['fib_23.6'] = recent_high - (diff * 0.236)
            stock_df['fib_38.2'] = recent_high - (diff * 0.382)
            stock_df['fib_61.8'] = recent_high - (diff * 0.618)
            
            # 24. Support/Resistance (Simplified)
            stock_df['resistance_level'] = df['High'].rolling(20).max()
            stock_df['support_level'] = df['Low'].rolling(20).min()
            
            # 25. RMI
            momentum_changes = df['Close'].diff(1).diff(1)
            gain_rmi = momentum_changes.where(momentum_changes > 0, 0).rolling(14).mean()
            loss_rmi = (-momentum_changes.where(momentum_changes < 0, 0)).rolling(14).mean()
            rs_rmi = gain_rmi / loss_rmi
            stock_df['rmi'] = 100 - (100 / (1 + rs_rmi))
            
            # 26. Supertrend
            hl2 = (df['High'] + df['Low']) / 2
            atr_mult = stock_df['atr'] * 3
            upper_band = hl2 + atr_mult
            lower_band = hl2 - atr_mult
            stock_df['supertrend'] = np.where(df['Close'] <= lower_band, lower_band, 
                                            np.where(df['Close'] >= upper_band, upper_band, np.nan))
            stock_df['supertrend'] = stock_df['supertrend'].ffill()
            
            # 27. Pattern Flags
            stock_df['trend_strength'] = abs(stock_df['adx'])
            stock_df['volume_trend'] = np.where(df['Volume'] > df['Volume'].rolling(20).mean(), 1, 0)
            stock_df['price_momentum'] = np.where(df['Close'] > df['Close'].shift(5), 1, 0)
            stock_df['volatility'] = df['Close'].rolling(20).std()
            stock_df['rsi_divergence'] = np.where((stock_df['rsi_14'] > 70) | (stock_df['rsi_14'] < 30), 1, 0)
            stock_df['macd_crossover'] = np.where(stock_df['macd'] > stock_df['macd_signal'], 1, 0)
            
            logging.info("Comprehensive indicator calculation complete")
            return stock_df
            
        except Exception as e:
            logging.error(f"Error calculating comprehensive indicators: {str(e)}")
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
                latest_row = df.iloc[-1]
                
                # Define critical and optional indicators
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
                
                indicator_values = {}
                
                # Process critical indicators
                for display_name, column_name in critical_indicators:
                    value = self.safe_get_value(latest_row, column_name)
                    indicator_values[display_name] = value
                
                # Process optional indicators (limit to 25)
                count = 0
                for display_name, column_name in optional_indicators:
                    if count >= 25: break
                    value = self.safe_get_value(latest_row, column_name)
                    indicator_values[display_name] = value
                    count += 1
                
                summary['indicator_values'] = indicator_values
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
        """Send data to Google Gemini for technical analysis"""
        try:
            if maximum_brain:
                indicators_list = """Relative Strength Index (RSI), Average Directional Index (ADX), Bollinger Bands, Moving Average Convergence Divergence (MACD), Simple Moving Average (SMA), Exponential Moving Average (EMA), Stochastic Oscillator, Commodity Channel Index (CCI), Ichimoku Cloud, Donchian Channels, Williams %R, Ultimate Oscillator, Money Flow Index (MFI), Relative Momentum Index (RMI), On-Balance Volume (OBV), Average True Range (ATR), Parabolic SAR, Aroon Indicator, TRIX, Accumulation/Distribution Line, Supertrend, Volume Weighted Average Price (VWAP), Momentum Indicator, Rate of Change (ROC), Keltner Channels, Pivot Points, Fibonacci Retracements, Candlestick Patterns, Support and Resistance Levels, Trend Lines, Elliott Wave Principle, Wyckoff Method, Head and Shoulders Pattern, Double Top/Bottom, Volume Patterns"""
                analysis_mode = "MAXIMUM BRAIN ANALYSIS - Use your most advanced analytical capabilities"
                
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
                indicators_list = "Wyckoff Method (accumulation/distribution phases), Bollinger Bands, Moving Averages (SMA and EMA), MACD, RSI, Stochastic Oscillator, On-Balance Volume (OBV), Average Directional Index (ADX), and price action patterns"
                analysis_mode = "Standard Analysis"
                
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

            # Model selection
            model_name = "gemini-pro-latest" if maximum_brain else "gemini-flash-latest"
            
            # Configure generation
            generation_config = {
                "temperature": 0.1 if maximum_brain else 0.3,
                "max_output_tokens": 8192 if maximum_brain else 4096,  # Increased to prevent truncation
                "response_mime_type": "application/json",
            }
            
            model = genai.GenerativeModel(model_name)
            
            logging.info(f"Calling Gemini API ({model_name}) for {summary.get('ticker', 'unknown')}")
            
            # Retry logic
            max_retries = 3
            retry_delay = 1
            response = None
            
            for attempt in range(max_retries + 1):
                try:
                    response = model.generate_content(prompt, generation_config=generation_config)
                    break
                except Exception as e:
                    logging.warning(f"Gemini API attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries:
                        time.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        raise e

            if response and response.text:
                logging.info(f"Gemini Response received")
                
                # Clean up response text - Gemini may wrap JSON in markdown code fences
                response_text = response.text.strip()
                
                # Remove markdown code fences if present
                if response_text.startswith("```json"):
                    response_text = response_text[7:]  # Remove ```json
                elif response_text.startswith("```"):
                    response_text = response_text[3:]  # Remove ```
                
                if response_text.endswith("```"):
                    response_text = response_text[:-3]  # Remove trailing ```
                
                response_text = response_text.strip()
                
                try:
                    analysis = json.loads(response_text)
                except json.JSONDecodeError as e:
                    logging.error(f"JSON decode error: {e}")
                    logging.error(f"Response text (first 500 chars): {response_text[:500]}")
                    raise
                
                # Add income analysis if requested
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

    def analyze_with_chunked_calls(self, summary, income_focus=False, income_metrics=None):
        """Fallback method: Split Maximum Brain analysis into multiple smaller API calls"""
        # For Gemini, we might not need chunking as much due to larger context window, 
        # but keeping it as a fallback strategy is good practice.
        # Implementing simplified version using Gemini Flash for chunks.
        try:
            logging.info(f"Starting chunked analysis fallback for {summary.get('ticker', 'unknown')}")
            
            # Split indicators (reuse logic from before or simplified)
            indicator_values = summary.get('indicator_values', {})
            keys = list(indicator_values.keys())
            mid = len(keys) // 2
            chunk1 = {k: indicator_values[k] for k in keys[:mid]}
            chunk2 = {k: indicator_values[k] for k in keys[mid:]}
            
            chunks = [chunk1, chunk2]
            analyses = []
            
            model = genai.GenerativeModel("gemini-flash-latest")
            generation_config = {"response_mime_type": "application/json"}
            
            for i, chunk in enumerate(chunks):
                prompt = f"""Analyze these technical indicators for {summary['ticker']}:
{json.dumps(chunk, indent=2)}

Provide a brief analysis and a Buy/No Buy signal for this group of indicators.
Respond in JSON: {{ "recommendation": "Buy"/"No Buy", "analysis": "..." }}"""
                
                response = model.generate_content(prompt, generation_config=generation_config)
                if response.text:
                    analyses.append(json.loads(response.text))
            
            # Synthesize
            synth_prompt = f"""Synthesize these partial analyses for {summary['ticker']}:
{json.dumps(analyses, indent=2)}

Provide a final recommendation in the standard JSON format used for stock analysis.
"""
            synth_model = genai.GenerativeModel("gemini-pro-latest")
            synth_response = synth_model.generate_content(synth_prompt, generation_config={"response_mime_type": "application/json"})
            
            if synth_response.text:
                return json.loads(synth_response.text), None
                
            return None, "Failed to synthesize chunked analysis"
            
        except Exception as e:
            logging.error(f"Error in chunked analysis: {str(e)}")
            return None, "Chunked analysis failed"

    def analyze_stock(self, ticker, maximum_brain=False, income_focus=False):
        """Main method to analyze a stock with optional income-focused analysis"""
        try:
            # Check if ticker is a yield ETF
            is_yield_etf = self.income_analyzer.is_yield_etf(ticker)
            
            # Fetch stock data
            stock_data, error = self.fetch_stock_data(ticker)
            if error or stock_data is None:
                return {'success': False, 'error': error or 'Failed to fetch stock data'}
            
            # Calculate indicators
            df_with_indicators = self.calculate_technical_indicators(stock_data['history'], maximum_brain)
            
            # Summarize data
            summary = self.summarize_data(df_with_indicators, stock_data['info'], maximum_brain)
            
            # Calculate income metrics
            income_metrics = None
            if income_focus:
                income_metrics = self.income_analyzer.calculate_income_metrics(ticker, stock_data['history'])
            
            # AI Analysis
            analysis, error = self.analyze_with_ai(summary, maximum_brain, income_focus, income_metrics)
            
            if error or analysis is None:
                # Try chunked fallback if Max Brain failed
                if maximum_brain:
                    analysis, error = self.analyze_with_chunked_calls(summary, income_focus, income_metrics)
                
                if error or analysis is None:
                    return {'success': False, 'error': error or 'Failed to get AI analysis'}
            
            result = {
                'success': True,
                'ticker': ticker,
                'company_name': summary.get('company_name', 'N/A'),
                'current_price': summary.get('current_price', 0),
                'price_change_30d': summary.get('price_change_30d', 0),
                'recommendation': analysis.get('recommendation', 'No recommendation'),
                'confidence': analysis.get('confidence', 'unknown'),
                'overall_explanation': analysis.get('overall_explanation', 'No explanation available'),
                'analysis_details': analysis.get('technical_analysis', []),
                'income_focus': income_focus,
                'is_yield_etf': is_yield_etf
            }
            
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
                result['income_analysis'] = {'error': 'Insufficient data for income analysis'}
            
            return result
            
        except Exception as e:
            logging.error(f"Error in analyze_stock: {str(e)}")
            return {'success': False, 'error': 'An error occurred during analysis. Please try again.'}
