import logging
import pandas as pd
import numpy as np

class FundamentalAnalyzer:
    """
    Analyzes fundamental data to calculate institutional-grade metrics:
    1. Piotroski F-Score (Financial Strength)
    2. Altman Z-Score (Bankruptcy Risk)
    3. Beneish M-Score (Earnings Manipulation)
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _safe_float(self, value):
        """Safely convert string to float, returning 0.0 if failed"""
        try:
            if value is None or value == 'None' or value == '-':
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def calculate_scores(self, balance_sheet, income_statement, cash_flow, overview):
        """
        Calculate all fundamental scores based on financial statements.
        
        Args:
            balance_sheet (dict): AlphaVantage BALANCE_SHEET response
            income_statement (dict): AlphaVantage INCOME_STATEMENT response
            cash_flow (dict): AlphaVantage CASH_FLOW response
            overview (dict): AlphaVantage OVERVIEW response
            
        Returns:
            dict: Dictionary containing scores and interpretations
        """
        try:
            # Extract annual reports (most recent first)
            bs_annual = balance_sheet.get('annualReports', [])
            is_annual = income_statement.get('annualReports', [])
            cf_annual = cash_flow.get('annualReports', [])
            
            if not bs_annual or not is_annual or not cf_annual:
                self.logger.warning("Insufficient data for fundamental analysis")
                return None

            # We need at least 2 years of data for some calculations
            if len(bs_annual) < 2 or len(is_annual) < 2 or len(cf_annual) < 2:
                self.logger.warning("Need at least 2 years of data for fundamental analysis")
                return None

            # Current Year (T) and Previous Year (T-1)
            bs_t = bs_annual[0]
            bs_t_1 = bs_annual[1]
            is_t = is_annual[0]
            is_t_1 = is_annual[1]
            cf_t = cf_annual[0]
            
            # --- 1. Piotroski F-Score (0-9) ---
            f_score = 0
            f_score_details = []
            
            # Profitability
            net_income = self._safe_float(is_t.get('netIncome'))
            roa = net_income / self._safe_float(bs_t.get('totalAssets'))
            op_cash_flow = self._safe_float(cf_t.get('operatingCashflow'))
            
            # 1. Positive Net Income
            if net_income > 0:
                f_score += 1
                f_score_details.append("Positive Net Income")
            
            # 2. Positive ROA
            if roa > 0:
                f_score += 1
                f_score_details.append("Positive ROA")
                
            # 3. Positive Operating Cash Flow
            if op_cash_flow > 0:
                f_score += 1
                f_score_details.append("Positive Operating Cash Flow")
                
            # 4. Cash Flow > Net Income (Quality of Earnings)
            if op_cash_flow > net_income:
                f_score += 1
                f_score_details.append("Cash Flow > Net Income")
                
            # Leverage, Liquidity, Source of Funds
            long_term_debt_t = self._safe_float(bs_t.get('longTermDebt'))
            long_term_debt_t_1 = self._safe_float(bs_t_1.get('longTermDebt'))
            current_ratio_t = self._safe_float(bs_t.get('totalCurrentAssets')) / self._safe_float(bs_t.get('totalCurrentLiabilities')) if self._safe_float(bs_t.get('totalCurrentLiabilities')) else 0
            current_ratio_t_1 = self._safe_float(bs_t_1.get('totalCurrentAssets')) / self._safe_float(bs_t_1.get('totalCurrentLiabilities')) if self._safe_float(bs_t_1.get('totalCurrentLiabilities')) else 0
            shares_t = self._safe_float(bs_t.get('commonStockSharesOutstanding'))
            shares_t_1 = self._safe_float(bs_t_1.get('commonStockSharesOutstanding'))
            
            # 5. Lower Long Term Debt (or no debt)
            if long_term_debt_t <= long_term_debt_t_1:
                f_score += 1
                f_score_details.append("Lower/Stable Long Term Debt")
                
            # 6. Higher Current Ratio
            if current_ratio_t > current_ratio_t_1:
                f_score += 1
                f_score_details.append("Higher Current Ratio")
                
            # 7. No New Shares Issued (Dilution check)
            if shares_t <= shares_t_1:
                f_score += 1
                f_score_details.append("No Share Dilution")
                
            # Operating Efficiency
            gross_margin_t = (self._safe_float(is_t.get('grossProfit')) / self._safe_float(is_t.get('totalRevenue'))) if self._safe_float(is_t.get('totalRevenue')) else 0
            gross_margin_t_1 = (self._safe_float(is_t_1.get('grossProfit')) / self._safe_float(is_t_1.get('totalRevenue'))) if self._safe_float(is_t_1.get('totalRevenue')) else 0
            asset_turnover_t = self._safe_float(is_t.get('totalRevenue')) / self._safe_float(bs_t.get('totalAssets')) if self._safe_float(bs_t.get('totalAssets')) else 0
            asset_turnover_t_1 = self._safe_float(is_t_1.get('totalRevenue')) / self._safe_float(bs_t_1.get('totalAssets')) if self._safe_float(bs_t_1.get('totalAssets')) else 0
            
            # 8. Higher Gross Margin
            if gross_margin_t > gross_margin_t_1:
                f_score += 1
                f_score_details.append("Higher Gross Margin")
                
            # 9. Higher Asset Turnover
            if asset_turnover_t > asset_turnover_t_1:
                f_score += 1
                f_score_details.append("Higher Asset Turnover")

            # --- 2. Altman Z-Score ---
            # Z = 1.2A + 1.4B + 3.3C + 0.6D + 1.0E
            # A = Working Capital / Total Assets
            # B = Retained Earnings / Total Assets
            # C = EBIT / Total Assets
            # D = Market Value of Equity / Total Liabilities
            # E = Sales / Total Assets
            
            total_assets = self._safe_float(bs_t.get('totalAssets'))
            total_liabilities = self._safe_float(bs_t.get('totalLiabilities'))
            working_capital = self._safe_float(bs_t.get('totalCurrentAssets')) - self._safe_float(bs_t.get('totalCurrentLiabilities'))
            retained_earnings = self._safe_float(bs_t.get('retainedEarnings'))
            ebit = self._safe_float(is_t.get('ebit'))
            market_cap = self._safe_float(overview.get('MarketCapitalization'))
            sales = self._safe_float(is_t.get('totalRevenue'))
            
            z_score = 0
            if total_assets > 0 and total_liabilities > 0:
                A = working_capital / total_assets
                B = retained_earnings / total_assets
                C = ebit / total_assets
                D = market_cap / total_liabilities
                E = sales / total_assets
                
                z_score = (1.2 * A) + (1.4 * B) + (3.3 * C) + (0.6 * D) + (1.0 * E)
            
            # --- 3. Beneish M-Score (Simplified) ---
            # Focus on key red flags: DSRI (Days Sales in Receivables Index) and GMI (Gross Margin Index)
            # Full 8-variable model is complex and data-sensitive, so we use a simplified version for "Red Flag" detection
            
            # DSRI = (Receivables_t / Sales_t) / (Receivables_t-1 / Sales_t-1)
            receivables_t = self._safe_float(bs_t.get('netReceivables'))
            receivables_t_1 = self._safe_float(bs_t_1.get('netReceivables'))
            sales_t = self._safe_float(is_t.get('totalRevenue'))
            sales_t_1 = self._safe_float(is_t_1.get('totalRevenue'))
            
            dsri = 1.0
            if sales_t > 0 and sales_t_1 > 0 and receivables_t_1 > 0:
                dsri = (receivables_t / sales_t) / (receivables_t_1 / sales_t_1)
                
            # GMI = GrossMargin_t-1 / GrossMargin_t
            gmi = 1.0
            if gross_margin_t > 0:
                gmi = gross_margin_t_1 / gross_margin_t
                
            # SGI = Sales_t / Sales_t-1
            sgi = 1.0
            if sales_t_1 > 0:
                sgi = sales_t / sales_t_1
                
            # Simplified M-Score heuristic (not the full regression formula, but a risk indicator)
            # High DSRI (>1.5) suggests channel stuffing
            # High GMI (>1.5) suggests deteriorating margins
            # High SGI (>1.5) suggests unsustainable growth
            
            earnings_manipulation_risk = "Low"
            if dsri > 1.5 or gmi > 1.5 or sgi > 1.5:
                earnings_manipulation_risk = "High"
            elif dsri > 1.2 or gmi > 1.2:
                earnings_manipulation_risk = "Medium"

            return {
                "piotroski_f_score": f_score,
                "piotroski_interpretation": self._interpret_f_score(f_score),
                "piotroski_details": f_score_details,
                "altman_z_score": round(z_score, 2),
                "altman_interpretation": self._interpret_z_score(z_score),
                "beneish_m_risk": earnings_manipulation_risk,
                "beneish_details": {
                    "DSRI": round(dsri, 2),
                    "GMI": round(gmi, 2),
                    "SGI": round(sgi, 2)
                }
            }

        except Exception as e:
            self.logger.error(f"Error calculating fundamental scores: {str(e)}")
            return None

    def _interpret_f_score(self, score):
        if score >= 7: return "Very Strong"
        if score >= 5: return "Strong"
        if score >= 3: return "Weak"
        return "Very Weak"

    def _interpret_z_score(self, score):
        if score > 3.0: return "Safe Zone"
        if score > 1.8: return "Grey Zone"
        return "Distress Zone"
