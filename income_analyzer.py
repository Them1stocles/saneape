import yfinance as yf
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta

class IncomeAnalyzer:
    """Specialized analyzer for income-generating ETFs like YieldMax products"""
    
    # Predefined list of yield ETFs (YieldMax and similar products)
    YIELD_ETFS = [
        'MSTY', 'ULTY', 'PLTY', 'TSLY', 'OARK', 'APLY', 'NVDY', 'AMZY', 
        'FBY', 'GOOY', 'NFLY', 'CONY', 'DISO', 'XOMO', 'MRNY', 'AIYY', 
        'SQYY', 'YMAX', 'AMDY', 'PYPY', 'JPMO', 'MCDO', 'MAXI', 'YBIT', 
        'CRSY', 'JPMY', 'HOOY', 'CVNY'
    ]
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def is_yield_etf(self, ticker):
        """Check if ticker is in the predefined yield ETF list"""
        return ticker.upper() in self.YIELD_ETFS
    
    def calculate_income_metrics(self, ticker, price_data):
        """Calculate comprehensive income metrics for yield ETFs with proper payment frequency detection"""
        try:
            # Get ticker info and dividend data
            ticker_obj = yf.Ticker(ticker)
            ticker_info = ticker_obj.info
            
            # Get 1 year of dividend data for accurate frequency detection
            dividend_data = ticker_obj.dividends
            if len(dividend_data) > 0:
                # Get the last 365 days of dividends with proper timezone handling
                if dividend_data.index.tz is not None:
                    # Dividend data is timezone-aware
                    one_year_ago = pd.Timestamp.now(tz=dividend_data.index.tz) - pd.Timedelta(days=365)
                else:
                    # Dividend data is timezone-naive
                    one_year_ago = pd.Timestamp.now() - pd.Timedelta(days=365)
                recent_dividends = dividend_data[dividend_data.index >= one_year_ago]
            else:
                recent_dividends = dividend_data  # Empty series
            
            # Basic validation
            if price_data is None or len(price_data) < 30:
                return None
                
            # 1. Detect Payment Frequency and Calculate Annualized Distribution Yield
            trailing_yield = ticker_info.get('trailingAnnualDividendYield', 0)
            payment_frequency = self.detect_payment_frequency(recent_dividends, ticker)
            
            if trailing_yield and trailing_yield > 0:
                annualized_yield = trailing_yield * 100
                self.logger.info(f"{ticker}: Using trailing yield {annualized_yield:.2f}% (frequency: {payment_frequency})")
            elif len(recent_dividends) > 0:
                # Calculate based on actual payment frequency
                total_dividends_year = recent_dividends.sum()
                current_price = price_data['Close'].iloc[-1]
                annualized_yield = (total_dividends_year / current_price) * 100
                self.logger.info(f"{ticker}: Calculated yield {annualized_yield:.2f}% from {len(recent_dividends)} payments (frequency: {payment_frequency})")
            else:
                # No dividend data available - use conservative estimate based on known patterns
                if ticker.upper() == 'ULTY':
                    annualized_yield = 45.0  # ULTY typically ~45% (weekly)
                elif ticker.upper() in ['TSLY', 'NVDY', 'MSTY']:
                    annualized_yield = 25.0  # Monthly YieldMax typically ~25%
                else:
                    annualized_yield = 20.0  # Conservative estimate
                self.logger.warning(f"{ticker}: No dividend data, using estimate {annualized_yield:.2f}%")
            
            # 2. Annualized NAV Decay Rate
            if len(price_data) > 1:
                start_price = price_data['Close'].iloc[0]
                end_price = price_data['Close'].iloc[-1]
                price_change = (end_price - start_price) / start_price
                days_elapsed = len(price_data)
                annualized_decay = -(price_change / (days_elapsed / 365)) * 100
                # If positive, it's actually appreciation, not decay
                if annualized_decay < 0:
                    annualized_decay = 0
            else:
                annualized_decay = 0
            
            # 3. Expense Ratio
            expense_ratio = ticker_info.get('expenseRatio', 0.0099) * 100  # Default 0.99% for YieldMax
            if expense_ratio == 0:
                expense_ratio = 0.99  # Default for YieldMax products
            
            # 4. Estimated Tax Drag (assume 25% for ordinary income/ROC)
            estimated_tax_drag = 6.25  # 25% of typical 25% yield = ~6.25%
            
            # 5. Effective Income Return
            effective_return = annualized_yield - annualized_decay - expense_ratio - estimated_tax_drag
            
            # 6. ROC Percentage (Return of Capital - typically ~95% for YieldMax)
            roc_percentage = 95.0  # Conservative estimate for YieldMax products
            
            # 7. Total Return with Reinvestment
            if 'Dividends' in price_data.columns:
                price_data_copy = price_data.copy()
                price_data_copy['Cum_Div'] = price_data_copy['Dividends'].cumsum()
                total_return = ((price_data_copy['Close'].iloc[-1] + price_data_copy['Cum_Div'].iloc[-1]) / 
                               price_data_copy['Close'].iloc[0] - 1) * 100
            else:
                # Fallback: just price return
                total_return = ((price_data['Close'].iloc[-1] / price_data['Close'].iloc[0]) - 1) * 100
            
            # 8. Income Recommendation
            buy_threshold = 5.0  # Configurable threshold
            income_recommendation = "Buy for Income" if effective_return > buy_threshold else "No Buy"
            
            # 9. Risk Assessment
            risks = []
            if annualized_decay > 10:
                risks.append("High NAV erosion risk")
            if roc_percentage > 90:
                risks.append("High return of capital (tax complexity)")
            if effective_return < 0:
                risks.append("Negative effective return after costs")
            if annualized_yield > 30:
                risks.append("Unsustainably high yield")
                
            return {
                'annualized_yield': round(annualized_yield, 2),
                'annualized_decay': round(annualized_decay, 2),
                'expense_ratio': round(expense_ratio, 2),
                'estimated_tax_drag': round(estimated_tax_drag, 2),
                'effective_return': round(effective_return, 2),
                'roc_percentage': round(roc_percentage, 2),
                'total_return': round(total_return, 2),
                'income_recommendation': income_recommendation,
                'buy_threshold': buy_threshold,
                'risks': risks,
                'payment_frequency': payment_frequency,
                'payments_per_year': self.get_payments_per_year(payment_frequency),
                'analysis_date': datetime.now().strftime('%Y-%m-%d'),
                'data_period_days': len(price_data),
                'dividend_count_last_year': len(recent_dividends)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating income metrics for {ticker}: {str(e)}")
            return None
    
    def detect_payment_frequency(self, dividend_data, ticker):
        """Detect payment frequency from dividend payment intervals"""
        if len(dividend_data) < 2:
            # Use known patterns for specific tickers
            if ticker.upper() == 'ULTY':
                return 'weekly'
            elif ticker.upper() in self.YIELD_ETFS:
                return 'monthly'
            else:
                return 'quarterly'
        
        # Calculate intervals between payments
        intervals = []
        for i in range(1, len(dividend_data)):
            days_diff = (dividend_data.index[i] - dividend_data.index[i-1]).days
            intervals.append(days_diff)
        
        if not intervals:
            return 'unknown'
            
        avg_interval = sum(intervals) / len(intervals)
        
        # Classify based on average interval and payment count
        # Also consider total payment count for better detection
        payments_per_year = len(dividend_data) if len(dividend_data) > 0 else 0
        
        # Classify based on average interval with payment count validation
        if avg_interval <= 10 or payments_per_year >= 40:  # ~7 days or 40+ payments
            return 'weekly'
        elif avg_interval <= 20 or payments_per_year >= 20:  # ~14 days or 20+ payments  
            return 'bi-weekly'
        elif avg_interval <= 35 or payments_per_year >= 10:  # ~30 days or 10+ payments
            return 'monthly'
        elif avg_interval <= 100:  # ~90 days
            return 'quarterly'
        elif avg_interval <= 200:  # ~180 days
            return 'semi-annual'
        else:
            return 'annual'
    
    def get_payments_per_year(self, frequency):
        """Get number of payments per year based on frequency"""
        frequency_map = {
            'weekly': 52,
            'bi-weekly': 26,
            'monthly': 12,
            'quarterly': 4,
            'semi-annual': 2,
            'annual': 1,
            'unknown': 12  # Default to monthly
        }
        return frequency_map.get(frequency, 12)
    
    def generate_income_prompt_addition(self, income_metrics):
        """Generate additional prompt text for OpenAI when income analysis is requested"""
        if not income_metrics:
            return "Income analysis requested but insufficient data available."
        
        return f"""
        
INCOME-FOCUSED ANALYSIS REQUIRED:
This is an income-generating ETF requiring specialized analysis for income seekers.

COMPUTED INCOME METRICS:
- Payment Frequency: {income_metrics['payment_frequency']} ({income_metrics['payments_per_year']} payments/year)
- Dividend Payments Last Year: {income_metrics['dividend_count_last_year']}
- Annualized Distribution Yield: {income_metrics['annualized_yield']}%
- Annualized NAV Decay Rate: {income_metrics['annualized_decay']}%
- Expense Ratio: {income_metrics['expense_ratio']}%
- Estimated Tax Drag: {income_metrics['estimated_tax_drag']}%
- Effective Income Return: {income_metrics['effective_return']}%
- Return of Capital Percentage: {income_metrics['roc_percentage']}%
- Total Return (with reinvestment): {income_metrics['total_return']}%

INCOME ANALYSIS INSTRUCTIONS:
1. Calculate: Effective Income Return = Annualized Distribution Yield - Annualized NAV Decay Rate - Expense Ratio - Estimated Tax Drag
2. Recommend "Buy for Income" if Effective Income Return > {income_metrics['buy_threshold']}%, otherwise "No Buy"
3. Focus on income sustainability vs. capital preservation trade-off
4. Explain risks: NAV erosion, return of capital tax implications, yield sustainability
5. Compare to alternative income strategies (bonds, dividend stocks, REITs)
6. Provide income-specific outlook and considerations

Your response must include a separate "income_analysis" section in the JSON with:
- income_recommendation: "Buy for Income" or "No Buy"
- income_confidence: "high", "medium", or "low"  
- income_explanation: detailed explanation focusing on income generation
- key_income_risks: array of main risks for income investors
- effective_income_return: the calculated effective return percentage
"""