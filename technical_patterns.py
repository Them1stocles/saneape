import numpy as np
import pandas as pd
import logging
from scipy.signal import argrelextrema

class TechnicalPatternScanner:
    """
    Advanced Technical Pattern Scanner for Institutional Analysis.
    
    Capabilities:
    1. Smart Money Concepts (SMC): Fair Value Gaps (FVG), Order Blocks (OB)
    2. Harmonic Patterns: Gartley, Bat, Butterfly, Crab
    3. Elliott Wave: Simplified momentum-based wave counting
    4. Anchored VWAP: Institutional interest levels
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def analyze_patterns(self, df):
        """
        Run all pattern scans on the dataframe.
        
        Args:
            df (pd.DataFrame): Dataframe with Open, High, Low, Close, Volume
            
        Returns:
            dict: Detected patterns and signals
        """
        try:
            if df is None or len(df) < 50:
                return {}

            # 1. Smart Money Concepts
            fvgs = self._find_fair_value_gaps(df)
            order_blocks = self._find_order_blocks(df)
            
            # 2. Harmonic Patterns
            harmonics = self._scan_harmonics(df)
            
            # 3. Elliott Wave (Simplified)
            elliott_wave = self._analyze_elliott_wave(df)
            
            # 4. Anchored VWAP
            anchored_vwap = self._calculate_anchored_vwap(df)
            
            return {
                "fair_value_gaps": fvgs,
                "order_blocks": order_blocks,
                "harmonic_patterns": harmonics,
                "elliott_wave": elliott_wave,
                "anchored_vwap": anchored_vwap
            }
            
        except Exception as e:
            self.logger.error(f"Error in pattern analysis: {str(e)}")
            return {}

    def _find_fair_value_gaps(self, df, lookback=20):
        """
        Identify Fair Value Gaps (FVG) / Imbalances.
        A 3-candle sequence where wicks don't overlap.
        """
        fvgs = []
        try:
            # We only care about recent FVGs that haven't been filled
            recent_df = df.tail(lookback)
            
            for i in range(len(recent_df) - 2):
                c1 = recent_df.iloc[i]     # Candle 1
                c2 = recent_df.iloc[i+1]   # Candle 2 (The big move)
                c3 = recent_df.iloc[i+2]   # Candle 3
                
                # Bullish FVG: Candle 1 High < Candle 3 Low
                if c1['High'] < c3['Low'] and c2['Close'] > c2['Open']:
                    fvgs.append({
                        "type": "Bullish FVG",
                        "top": c3['Low'],
                        "bottom": c1['High'],
                        "date": recent_df.index[i+1].strftime('%Y-%m-%d')
                    })
                
                # Bearish FVG: Candle 1 Low > Candle 3 High
                elif c1['Low'] > c3['High'] and c2['Close'] < c2['Open']:
                    fvgs.append({
                        "type": "Bearish FVG",
                        "top": c1['Low'],
                        "bottom": c3['High'],
                        "date": recent_df.index[i+1].strftime('%Y-%m-%d')
                    })
            
            # Filter: Keep only the most recent 3
            return fvgs[-3:]
            
        except Exception as e:
            self.logger.error(f"FVG Error: {e}")
            return []

    def _find_order_blocks(self, df, lookback=50):
        """
        Identify potential Order Blocks.
        Bullish OB: Last down candle before a strong up move that breaks structure.
        Bearish OB: Last up candle before a strong down move.
        """
        obs = []
        try:
            # Simplified logic: Look for strong engulfing moves
            recent_df = df.tail(lookback)
            
            for i in range(1, len(recent_df) - 1):
                prev = recent_df.iloc[i-1]
                curr = recent_df.iloc[i]
                next_c = recent_df.iloc[i+1]
                
                # Bullish OB Candidate
                # Previous candle red, Current candle green and engulfs previous
                if prev['Close'] < prev['Open'] and curr['Close'] > curr['Open']:
                    if curr['Close'] > prev['High'] and curr['Volume'] > prev['Volume'] * 1.2:
                        obs.append({
                            "type": "Bullish OB",
                            "price_level": prev['High'], # Often retested
                            "date": recent_df.index[i].strftime('%Y-%m-%d')
                        })
                        
                # Bearish OB Candidate
                # Previous candle green, Current candle red and engulfs previous
                if prev['Close'] > prev['Open'] and curr['Close'] < curr['Open']:
                    if curr['Close'] < prev['Low'] and curr['Volume'] > prev['Volume'] * 1.2:
                        obs.append({
                            "type": "Bearish OB",
                            "price_level": prev['Low'],
                            "date": recent_df.index[i].strftime('%Y-%m-%d')
                        })
            
            return obs[-3:]
            
        except Exception as e:
            self.logger.error(f"OB Error: {e}")
            return []

    def _scan_harmonics(self, df, err_allowed=0.10):
        """
        Scan for XABCD Harmonic Patterns (Gartley, Bat, Butterfly, Crab).
        Uses local extrema to find pivots.
        """
        patterns = []
        try:
            # Find peaks and troughs
            # order=5 means we look 5 candles left and right for a peak
            highs = argrelextrema(df['High'].values, np.greater, order=5)[0]
            lows = argrelextrema(df['Low'].values, np.less, order=5)[0]
            
            # Combine and sort pivots
            pivots = np.concatenate((highs, lows))
            pivots.sort()
            
            # We need at least 5 pivots for XABCD
            if len(pivots) < 5:
                return []
            
            # Check the last 5 pivots
            last_5 = pivots[-5:]
            
            # Get price values
            prices = df['Close'].values # Using Close for simplicity, usually High/Low is better but noisier
            X = prices[last_5[0]]
            A = prices[last_5[1]]
            B = prices[last_5[2]]
            C = prices[last_5[3]]
            D = prices[last_5[4]]
            
            # Calculate Ratios
            XA = A - X
            AB = B - A
            BC = C - B
            CD = D - C
            
            # Direction
            is_bullish = X < A and B < A and C > B and D < C # M-shape (Bullish)
            is_bearish = X > A and B > A and C < B and D > C # W-shape (Bearish)
            
            if not (is_bullish or is_bearish):
                return []
            
            # Calculate Retracements
            # XB_ret: B retracement of XA
            XB_ret = abs(B - X) / abs(A - X)
            # AC_ret: C retracement of AB
            AC_ret = abs(C - A) / abs(B - A)
            # BD_ret: D retracement of BC
            BD_ret = abs(D - B) / abs(C - B)
            # XD_ret: D retracement of XA
            XD_ret = abs(D - X) / abs(A - X)
            
            # Pattern Definitions (Target Ratios)
            # Gartley: XB=0.618, AC=0.382-0.886, BD=1.272-1.618, XD=0.786
            # Bat: XB=0.382-0.50, AC=0.382-0.886, BD=1.618-2.618, XD=0.886
            
            # Check Gartley
            if abs(XB_ret - 0.618) < err_allowed and abs(XD_ret - 0.786) < err_allowed:
                patterns.append({
                    "name": "Gartley",
                    "signal": "Buy" if is_bullish else "Sell",
                    "confidence": "High"
                })
                
            # Check Bat
            elif (0.382 - err_allowed < XB_ret < 0.50 + err_allowed) and abs(XD_ret - 0.886) < err_allowed:
                patterns.append({
                    "name": "Bat",
                    "signal": "Buy" if is_bullish else "Sell",
                    "confidence": "High"
                })
                
            # Check Butterfly (Extension pattern)
            elif abs(XB_ret - 0.786) < err_allowed and abs(XD_ret - 1.27) < err_allowed:
                patterns.append({
                    "name": "Butterfly",
                    "signal": "Buy" if is_bullish else "Sell",
                    "confidence": "Medium"
                })
                
            return patterns
            
        except Exception as e:
            self.logger.error(f"Harmonic Error: {e}")
            return []

    def _analyze_elliott_wave(self, df):
        """
        Simplified Elliott Wave Analysis using Awesome Oscillator (AO).
        Wave 3 is typically the strongest and has the highest AO peak.
        Wave 4 usually retraces but AO stays above zero (in uptrend).
        Wave 5 makes new price high but AO diverges (lower peak).
        """
        try:
            # Calculate Awesome Oscillator (AO)
            # AO = SMA(5) of Median Price - SMA(34) of Median Price
            median_price = (df['High'] + df['Low']) / 2
            ao = median_price.rolling(5).mean() - median_price.rolling(34).mean()
            
            current_ao = ao.iloc[-1]
            current_price = df['Close'].iloc[-1]
            
            # Find recent peaks in AO
            # This is a very simplified heuristic
            recent_ao = ao.tail(50)
            max_ao = recent_ao.max()
            min_ao = recent_ao.min()
            
            status = "Indeterminate"
            
            # Bullish Scenario
            if current_ao > 0:
                if current_ao > max_ao * 0.9:
                    status = "Potential Wave 3 (Strong Momentum)"
                elif current_ao < max_ao * 0.5 and current_ao > 0:
                    status = "Potential Wave 4 (Pullback)"
                elif current_price > df['Close'].tail(50).max() * 0.95 and current_ao < max_ao:
                    status = "Potential Wave 5 (Divergence - Be Careful)"
            
            # Bearish Scenario
            elif current_ao < 0:
                if current_ao < min_ao * 0.9:
                    status = "Potential Wave 3 Down (Strong Momentum)"
                elif current_ao > min_ao * 0.5 and current_ao < 0:
                    status = "Potential Wave 4 Up (Pullback)"
            
            return {
                "current_wave_status": status,
                "ao_value": round(current_ao, 2)
            }
            
        except Exception as e:
            self.logger.error(f"Elliott Error: {e}")
            return {"current_wave_status": "Error", "ao_value": 0}

    def _calculate_anchored_vwap(self, df):
        """
        Calculate VWAP anchored to the lowest low of the last 90 days.
        Institutional support level.
        """
        try:
            # Find index of lowest low in last 90 days
            lookback = 90
            if len(df) < lookback:
                lookback = len(df)
                
            subset = df.tail(lookback)
            lowest_idx = subset['Low'].idxmin()
            
            # Slice from that index to end
            anchored_df = df.loc[lowest_idx:]
            
            # Calculate VWAP
            vwap = (anchored_df['Close'] * anchored_df['Volume']).cumsum() / anchored_df['Volume'].cumsum()
            
            current_avwap = vwap.iloc[-1]
            current_price = df['Close'].iloc[-1]
            
            signal = "Bullish" if current_price > current_avwap else "Bearish"
            
            return {
                "anchored_price": round(current_avwap, 2),
                "anchor_date": lowest_idx.strftime('%Y-%m-%d'),
                "signal": signal,
                "distance_pct": round(((current_price - current_avwap) / current_avwap) * 100, 2)
            }
            
        except Exception as e:
            self.logger.error(f"AVWAP Error: {e}")
            return None
