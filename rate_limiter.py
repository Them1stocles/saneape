from app import db
from models import RateLimit
from datetime import datetime, date
from cost_manager import CostManager
from cache_manager import CacheManager
from security_monitor import SecurityMonitor
import logging

class RateLimiter:
    """Enhanced rate limiter with cost management, caching, and security monitoring"""
    
    def __init__(self, max_requests_per_day=6, max_brain_requests_per_day=2):
        self.max_requests_per_day = max_requests_per_day
        self.max_brain_requests_per_day = max_brain_requests_per_day
        self.logger = logging.getLogger(__name__)
        
        # Lazy initialization to avoid circular imports and improve performance
        self._cost_manager = None
        self._cache_manager = None
        self._security_monitor = None
    
    @property
    def cost_manager(self):
        if self._cost_manager is None:
            self._cost_manager = CostManager()
        return self._cost_manager
    
    @property
    def cache_manager(self):
        if self._cache_manager is None:
            self._cache_manager = CacheManager()
        return self._cache_manager
    
    @property
    def security_monitor(self):
        if self._security_monitor is None:
            self._security_monitor = SecurityMonitor()
        return self._security_monitor
    
    def is_allowed(self, ip_address, maximum_brain=False):
        """Enhanced permission check with multiple protection layers"""
        try:
            # Check if IP is flagged as suspicious
            if self.security_monitor.is_ip_suspicious(ip_address):
                self.security_monitor.log_security_event(
                    ip_address, 
                    SecurityMonitor.REPEATED_ATTEMPTS,
                    "Blocked due to suspicious activity"
                )
                return False, "Access temporarily restricted due to suspicious activity"
            
            # Check global cost limits
            can_afford, cost_error = self.cost_manager.can_afford_request(maximum_brain)
            if not can_afford:
                self.security_monitor.log_security_event(ip_address, SecurityMonitor.COST_LIMIT_HIT, cost_error)
                return False, cost_error
            
            # Check IP-specific rate limits
            today = date.today()
            rate_limit = RateLimit.query.filter_by(
                ip_address=ip_address,
                date_created=today
            ).first()
            
            if not rate_limit:
                return True, None  # First request of the day
            
            # Check specific limits
            if maximum_brain:
                allowed = rate_limit.maximum_brain_count < self.max_brain_requests_per_day
                if not allowed:
                    self.security_monitor.log_security_event(
                        ip_address, 
                        SecurityMonitor.RATE_LIMIT_EXCEEDED,
                        f"Maximum Brain limit exceeded: {rate_limit.maximum_brain_count}/{self.max_brain_requests_per_day}"
                    )
                    return False, f"Maximum Brain analysis limit exceeded. You can only make {self.max_brain_requests_per_day} Maximum Brain analysis per day."
            else:
                allowed = rate_limit.request_count < self.max_requests_per_day
                if not allowed:
                    self.security_monitor.log_security_event(
                        ip_address, 
                        SecurityMonitor.RATE_LIMIT_EXCEEDED,
                        f"Standard limit exceeded: {rate_limit.request_count}/{self.max_requests_per_day}"
                    )
                    return False, f"Daily limit exceeded. You can only make {self.max_requests_per_day} requests per day."
            
            return True, None
            
        except Exception as e:
            self.logger.error(f"Error checking rate limit: {str(e)}")
            # SECURITY: Deny requests during database errors instead of allowing them
            self.security_monitor.log_security_event(ip_address, "system_error", str(e))
            return False, "System temporarily unavailable. Please try again later."
    
    def check_cache_first(self, ticker, maximum_brain=False):
        """Check if analysis is cached before proceeding with API call"""
        try:
            cached_result = self.cache_manager.get_cached_analysis(ticker, maximum_brain)
            if cached_result:
                self.logger.info(f"Serving cached result for {ticker} (brain: {maximum_brain})")
                return cached_result
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking cache: {str(e)}")
            return None
    
    def record_request(self, ip_address, maximum_brain=False):
        """Record a successful request with cost tracking"""
        try:
            today = date.today()
            
            # Update IP-specific rate limits
            rate_limit = RateLimit.query.filter_by(
                ip_address=ip_address,
                date_created=today
            ).first()
            
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
            
            # Record global API call and cost
            self.cost_manager.record_api_call(maximum_brain)
            
            db.session.commit()
            self.logger.info(f"Recorded request for {ip_address}: brain={maximum_brain}")
            
        except Exception as e:
            self.logger.error(f"Error recording request: {str(e)}")
            db.session.rollback()
    
    def cache_result(self, ticker, result, maximum_brain=False):
        """Cache the analysis result"""
        try:
            self.cache_manager.store_analysis(ticker, result, maximum_brain)
        except Exception as e:
            self.logger.error(f"Error caching result: {str(e)}")
    
    def get_remaining_requests(self, ip_address):
        """Get remaining requests for the IP address with detailed info"""
        try:
            today = date.today()
            
            rate_limit = RateLimit.query.filter_by(
                ip_address=ip_address,
                date_created=today
            ).first()
            
            if not rate_limit:
                return {
                    'standard_remaining': self.max_requests_per_day,
                    'brain_remaining': self.max_brain_requests_per_day,
                    'total_used': 0
                }
            
            standard_remaining = max(0, self.max_requests_per_day - rate_limit.request_count)
            brain_remaining = max(0, self.max_brain_requests_per_day - rate_limit.maximum_brain_count)
            
            return {
                'standard_remaining': standard_remaining,
                'brain_remaining': brain_remaining,
                'total_used': rate_limit.request_count + rate_limit.maximum_brain_count,
                'last_request': rate_limit.last_request.isoformat() if rate_limit.last_request else None
            }
            
        except Exception as e:
            self.logger.error(f"Error getting remaining requests: {str(e)}")
            return {
                'standard_remaining': 0,
                'brain_remaining': 0,
                'total_used': 0,
                'error': 'Could not retrieve limit information'
            }
    
    def reset_limits_for_ip(self, ip_address):
        """Admin function to reset limits for a specific IP"""
        try:
            today = date.today()
            rate_limit = RateLimit.query.filter_by(
                ip_address=ip_address,
                date_created=today
            ).first()
            
            if rate_limit:
                rate_limit.request_count = 0
                rate_limit.maximum_brain_count = 0
                db.session.commit()
                self.logger.info(f"Reset limits for IP: {ip_address}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error resetting limits for {ip_address}: {str(e)}")
            db.session.rollback()
            return False
    
    def get_system_status(self):
        """Get comprehensive system status for admin dashboard"""
        try:
            cost_stats = self.cost_manager.get_daily_stats()
            cache_stats = self.cache_manager.get_cache_stats()
            security_stats = self.security_monitor.get_security_metrics()
            
            return {
                'cost_management': cost_stats,
                'cache_performance': cache_stats,
                'security_metrics': security_stats,
                'rate_limits': {
                    'standard_per_day': self.max_requests_per_day,
                    'brain_per_day': self.max_brain_requests_per_day
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system status: {str(e)}")
            return None
