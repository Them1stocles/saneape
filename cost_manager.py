"""
Cost Management System for OpenAI API usage tracking and billing protection.
Production-grade implementation with comprehensive error handling.
"""

from app import db
from models import SystemLimits
from datetime import datetime, date, timedelta
import logging

class CostManager:
    """Manages OpenAI API costs and daily spending limits"""
    
    # OpenAI GPT-4o pricing (as of 2025)
    INPUT_TOKEN_COST = 0.0025 / 1000  # $2.50 per 1M input tokens
    OUTPUT_TOKEN_COST = 0.01 / 1000   # $10.00 per 1M output tokens
    
    # Estimated token usage per analysis type
    STANDARD_INPUT_TOKENS = 1500
    STANDARD_OUTPUT_TOKENS = 300
    BRAIN_INPUT_TOKENS = 4000
    BRAIN_OUTPUT_TOKENS = 800
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_today_limits(self):
        """Get or create today's system limits record"""
        try:
            today = date.today()
            limits = SystemLimits.query.filter_by(date_created=today).first()
            
            if not limits:
                limits = SystemLimits()
                limits.date_created = today
                limits.daily_api_calls = 0
                limits.daily_cost_estimate = 0.0
                limits.max_daily_cost = 25.0
                limits.emergency_stop = False
                db.session.add(limits)
                db.session.commit()
                self.logger.info(f"Created new daily limits record for {today}")
            
            return limits
            
        except Exception as e:
            self.logger.error(f"Error getting today's limits: {str(e)}")
            db.session.rollback()
            return None
    
    def estimate_request_cost(self, maximum_brain=False):
        """Estimate cost for a single API request"""
        if maximum_brain:
            input_cost = self.BRAIN_INPUT_TOKENS * self.INPUT_TOKEN_COST
            output_cost = self.BRAIN_OUTPUT_TOKENS * self.OUTPUT_TOKEN_COST
        else:
            input_cost = self.STANDARD_INPUT_TOKENS * self.INPUT_TOKEN_COST
            output_cost = self.STANDARD_OUTPUT_TOKENS * self.OUTPUT_TOKEN_COST
        
        return input_cost + output_cost
    
    def can_afford_request(self, maximum_brain=False):
        """Check if we can afford this request within daily limits"""
        try:
            limits = self.get_today_limits()
            if not limits:
                self.logger.error("Could not get today's limits - denying request")
                return False, "System error - please try again later"
            
            # Check emergency stop
            if limits.emergency_stop:
                return False, "System temporarily unavailable - emergency stop activated"
            
            # Estimate cost of this request
            estimated_cost = self.estimate_request_cost(maximum_brain)
            projected_total = limits.daily_cost_estimate + estimated_cost
            
            # Check if projected cost exceeds limit
            if projected_total > limits.max_daily_cost:
                remaining_budget = limits.max_daily_cost - limits.daily_cost_estimate
                return False, f"Daily spending limit reached. Budget remaining: ${remaining_budget:.2f}"
            
            return True, None
            
        except Exception as e:
            self.logger.error(f"Error checking affordability: {str(e)}")
            return False, "System error - please try again later"
    
    def record_api_call(self, maximum_brain=False, actual_cost=None):
        """Record an API call and update cost tracking"""
        try:
            limits = self.get_today_limits()
            if not limits:
                self.logger.error("Could not get today's limits for recording")
                return False
            
            # Update call count
            limits.daily_api_calls += 1
            
            # Update cost estimate (use actual cost if provided)
            if actual_cost is not None:
                limits.daily_cost_estimate += actual_cost
            else:
                estimated_cost = self.estimate_request_cost(maximum_brain)
                limits.daily_cost_estimate += estimated_cost
            
            limits.last_updated = datetime.utcnow()
            db.session.commit()
            
            self.logger.info(f"Recorded API call: {limits.daily_api_calls} calls, ${limits.daily_cost_estimate:.4f} cost")
            return True
            
        except Exception as e:
            self.logger.error(f"Error recording API call: {str(e)}")
            db.session.rollback()
            return False
    
    def get_daily_stats(self):
        """Get current daily usage statistics"""
        try:
            limits = self.get_today_limits()
            if not limits:
                return None
            
            return {
                'date': limits.date_created.isoformat(),
                'api_calls': limits.daily_api_calls,
                'cost_estimate': round(limits.daily_cost_estimate, 4),
                'max_daily_cost': limits.max_daily_cost,
                'remaining_budget': round(limits.max_daily_cost - limits.daily_cost_estimate, 4),
                'emergency_stop': limits.emergency_stop,
                'last_updated': limits.last_updated.isoformat() if limits.last_updated else None
            }
            
        except Exception as e:
            self.logger.error(f"Error getting daily stats: {str(e)}")
            return None
    
    def set_emergency_stop(self, enabled=True):
        """Enable or disable emergency stop"""
        try:
            limits = self.get_today_limits()
            if not limits:
                return False
            
            limits.emergency_stop = enabled
            limits.last_updated = datetime.utcnow()
            db.session.commit()
            
            status = "enabled" if enabled else "disabled"
            self.logger.warning(f"Emergency stop {status}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting emergency stop: {str(e)}")
            db.session.rollback()
            return False
    
    def update_daily_limit(self, new_limit):
        """Update the daily spending limit"""
        try:
            if new_limit <= 0:
                return False, "Daily limit must be greater than 0"
            
            limits = self.get_today_limits()
            if not limits:
                return False, "Could not access system limits"
            
            old_limit = limits.max_daily_cost
            limits.max_daily_cost = float(new_limit)
            limits.last_updated = datetime.utcnow()
            db.session.commit()
            
            self.logger.info(f"Updated daily limit from ${old_limit} to ${new_limit}")
            return True, f"Daily limit updated to ${new_limit}"
            
        except Exception as e:
            self.logger.error(f"Error updating daily limit: {str(e)}")
            db.session.rollback()
            return False, "Error updating daily limit"
    
    def cleanup_old_records(self, days_to_keep=30):
        """Clean up old system limit records"""
        try:
            cutoff_date = date.today() - timedelta(days=days_to_keep)
            deleted = SystemLimits.query.filter(SystemLimits.date_created < cutoff_date).delete()
            db.session.commit()
            
            if deleted > 0:
                self.logger.info(f"Cleaned up {deleted} old system limit records")
            
            return deleted
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old records: {str(e)}")
            db.session.rollback()
            return 0