from extensions import db
from models import RateLimit
from datetime import datetime, date
from cost_manager import CostManager
from security_monitor import SecurityMonitor
import logging

class RateLimiter:
    """
    Simplified rate limiter for Vercel migration.
    Supports IP-based rate limiting for all users.
    """
    
    def __init__(self, max_requests_per_day=6, max_brain_requests_per_day=2):
        self.max_requests_per_day = max_requests_per_day
        self.max_brain_requests_per_day = max_brain_requests_per_day
        self.logger = logging.getLogger(__name__)
        
        self._cost_manager = None
        self._security_monitor = None
    
    @property
    def cost_manager(self):
        if self._cost_manager is None:
            self._cost_manager = CostManager()
        return self._cost_manager
    
    @property
    def security_monitor(self):
        if self._security_monitor is None:
            self._security_monitor = SecurityMonitor()
        return self._security_monitor
    
    def is_allowed(self, ip_address, maximum_brain=False, ticker=None):
        """
        Check if request is allowed based on IP limits and global cost limits.
        Returns: (allowed: bool, error_message: str|None)
        """
        try:
            # Security check
            if self.security_monitor.is_ip_suspicious(ip_address):
                self.security_monitor.log_security_event(
                    ip_address, 
                    SecurityMonitor.REPEATED_ATTEMPTS,
                    "Blocked due to suspicious activity"
                )
                return False, "Access temporarily restricted due to suspicious activity"
            
            # Global cost limit check
            can_afford, cost_error = self.cost_manager.can_afford_request(maximum_brain)
            if not can_afford:
                self.security_monitor.log_security_event(ip_address, SecurityMonitor.COST_LIMIT_HIT, cost_error)
                return False, cost_error
            
            # IP-based rate limiting
            return self._check_ip_limits(ip_address, maximum_brain)
                
        except Exception as e:
            self.logger.error(f"Error in rate limiting check: {e}")
            return False, f"System error during rate limit check: {str(e)}"
    
    def _check_ip_limits(self, ip_address, maximum_brain):
        """
        Check daily limits for IP address.
        """
        try:
            today = date.today()
            stmt = db.select(RateLimit).filter_by(
                ip_address=ip_address,
                date_created=today
            )
            rate_limit = db.session.execute(stmt).scalars().first()
            
            if not rate_limit:
                return True, None  # First request of the day
            
            # Check specific limits
            if maximum_brain:
                allowed = rate_limit.maximum_brain_count < self.max_brain_requests_per_day
                if not allowed:
                    return False, f"Maximum Brain analysis limit exceeded. You can only make {self.max_brain_requests_per_day} Maximum Brain analyses per day."
            else:
                allowed = rate_limit.request_count < self.max_requests_per_day
                if not allowed:
                    return False, f"Daily limit exceeded. You can only make {self.max_requests_per_day} requests per day."
            
            return True, None
            
        except Exception as e:
            self.logger.error(f"Error in IP-based rate limiting for {ip_address}: {e}")
            return False, f"Error checking rate limits: {str(e)}"
    
    def record_request(self, ip_address, maximum_brain=False):
        """
        Record a successful request for IP-based rate limiting.
        """
        try:
            today = date.today()
            stmt = db.select(RateLimit).filter_by(
                ip_address=ip_address,
                date_created=today
            )
            rate_limit = db.session.execute(stmt).scalars().first()
            
            if rate_limit:
                if maximum_brain:
                    rate_limit.maximum_brain_count += 1
                else:
                    rate_limit.request_count += 1
                rate_limit.last_request = datetime.utcnow()
            else:
                rate_limit = RateLimit()
                rate_limit.ip_address = ip_address
                rate_limit.request_count = 1 if not maximum_brain else 0
                rate_limit.maximum_brain_count = 1 if maximum_brain else 0
                rate_limit.last_request = datetime.utcnow()
                rate_limit.date_created = today
                db.session.add(rate_limit)
            
            db.session.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"Error recording request for {ip_address}: {e}")
            db.session.rollback()
            return False
    
    def get_remaining_requests(self, ip_address):
        """Get remaining request counts for IP"""
        try:
            today = date.today()
            stmt = db.select(RateLimit).filter_by(
                ip_address=ip_address,
                date_created=today
            )
            rate_limit = db.session.execute(stmt).scalars().first()
            
            if not rate_limit:
                return {
                    'remaining_standard': self.max_requests_per_day,
                    'remaining_brain': self.max_brain_requests_per_day
                }
            
            return {
                'remaining_standard': max(0, self.max_requests_per_day - rate_limit.request_count),
                'remaining_brain': max(0, self.max_brain_requests_per_day - rate_limit.maximum_brain_count)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting remaining requests for {ip_address}: {e}")
            return {
                'remaining_standard': 0,
                'remaining_brain': 0
            }

    def get_system_status(self):
        """Get comprehensive system status for admin dashboard"""
        try:
            cost_stats = self.cost_manager.get_daily_stats()
            security_stats = self.security_monitor.get_security_metrics()
            
            return {
                'cost_management': cost_stats,
                'security_metrics': security_stats,
                'rate_limits': {
                    'standard_per_day': self.max_requests_per_day,
                    'brain_per_day': self.max_brain_requests_per_day
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system status: {str(e)}")
            return None
