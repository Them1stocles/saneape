from app import db
from models import RateLimit
from datetime import datetime, date
from cost_manager import CostManager
from cache_manager import CacheManager
from security_monitor import SecurityMonitor
from credit_manager import CreditManager
from flask_login import current_user
from feature_flags import is_credit_system_enabled, is_user_auth_enabled
import logging

class RateLimiter:
    """
    Production-grade hybrid rate limiter supporting both credit-based (authenticated users) 
    and IP-based (anonymous users) rate limiting with comprehensive protection layers.
    """
    
    def __init__(self, max_requests_per_day=6, max_brain_requests_per_day=2):
        self.max_requests_per_day = max_requests_per_day
        self.max_brain_requests_per_day = max_brain_requests_per_day
        self.logger = logging.getLogger(__name__)
        
        # Lazy initialization to avoid circular imports and improve performance
        self._cost_manager = None
        self._cache_manager = None
        self._security_monitor = None
        self._credit_manager = None
    
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
    
    @property
    def credit_manager(self):
        if self._credit_manager is None:
            self._credit_manager = CreditManager()
        return self._credit_manager
    
    def is_allowed(self, ip_address, maximum_brain=False, ticker=None):
        """
        Production-grade hybrid permission check supporting both credit-based and IP-based limiting.
        
        For authenticated users with credit system enabled: Uses credit deduction
        For anonymous users: Uses IP-based rate limiting
        
        Returns: (allowed: bool, error_message: str|None, credit_info: dict|None)
        """
        try:
            # Security check first - applies to all users
            if self.security_monitor.is_ip_suspicious(ip_address):
                self.security_monitor.log_security_event(
                    ip_address, 
                    SecurityMonitor.REPEATED_ATTEMPTS,
                    "Blocked due to suspicious activity"
                )
                return False, "Access temporarily restricted due to suspicious activity", None
            
            # Global cost limit check
            can_afford, cost_error = self.cost_manager.can_afford_request(maximum_brain)
            if not can_afford:
                self.security_monitor.log_security_event(ip_address, SecurityMonitor.COST_LIMIT_HIT, cost_error)
                return False, cost_error, None
            
            # Hybrid rate limiting: Credit-based for authenticated users, IP-based for anonymous
            auth_status = current_user.is_authenticated
            credit_enabled = is_credit_system_enabled()
            user_auth_enabled = is_user_auth_enabled()
            
            self.logger.info(f"Rate limit check: auth={auth_status}, credit_system={credit_enabled}, user_auth={user_auth_enabled}")
            
            if (auth_status and credit_enabled and user_auth_enabled):
                # CREDIT-BASED RATE LIMITING (Authenticated Users)
                self.logger.info(f"Using credit-based rate limiting for user {current_user.id}")
                return self._check_credit_limits(current_user.id, maximum_brain, ticker, ip_address)
            else:
                # IP-BASED RATE LIMITING (Anonymous Users)
                self.logger.info(f"Using IP-based rate limiting for {ip_address}")
                allowed, error_message = self._check_ip_limits(ip_address, maximum_brain)
                return allowed, error_message, None
                
        except Exception as e:
            self.logger.error(f"Error in rate limiting check: {e}")
            # Fail secure: deny access if there's an error
            return False, f"System error during rate limit check: {str(e)}", None
    
    def _check_credit_limits(self, user_id, maximum_brain, ticker, ip_address):
        """
        Credit-based rate limiting for authenticated users with atomic operations.
        """
        try:
            # Check if user can afford the analysis
            affordability = self.credit_manager.can_afford_analysis(user_id, maximum_brain)
            
            if not affordability['can_afford']:
                # Log insufficient credits as security event for monitoring
                self.security_monitor.log_security_event(
                    ip_address,
                    SecurityMonitor.RATE_LIMIT_EXCEEDED,
                    f"User {user_id} insufficient credits: {affordability['total_credits']} < {affordability['cost']}"
                )
                
                return False, f"Insufficient credits. Need {affordability['cost']} credits, have {affordability['total_credits']}", affordability
            
            # Check cache first to avoid unnecessary credit deduction
            if ticker:
                cached_result = self.cache_manager.get_cached_analysis(ticker, maximum_brain)
                if cached_result:
                    self.logger.info(f"Cache hit for {ticker} (brain={maximum_brain}) - no credit deduction")
                    return True, None, affordability
            
            # Deduct credits atomically (this commits to database immediately)
            deduction_result = self.credit_manager.deduct_credits_for_analysis(user_id, ticker, maximum_brain)
            
            if not deduction_result['success']:
                self.logger.error(f"Credit deduction failed for user {user_id}: {deduction_result.get('error')}")
                return False, f"Credit deduction failed: {deduction_result.get('error', 'Unknown error')}", None
            
            # Success - credits deducted
            self.logger.info(f"Credits deducted for user {user_id}: {deduction_result['cost']} credits")
            
            return True, None, {
                'deduction_result': deduction_result,
                'analysis_type': 'Maximum Brain' if maximum_brain else 'Standard'
            }
            
        except Exception as e:
            self.logger.error(f"Error in credit-based rate limiting for user {user_id}: {e}")
            return False, f"Error processing credit check: {str(e)}", None
    
    def _check_ip_limits(self, ip_address, maximum_brain):
        """
        Traditional IP-based rate limiting for anonymous users.
        """
        try:
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
                    return False, f"Maximum Brain analysis limit exceeded. You can only make {self.max_brain_requests_per_day} Maximum Brain analyses per day."
            else:
                allowed = rate_limit.request_count < self.max_requests_per_day
                if not allowed:
                    self.security_monitor.log_security_event(
                        ip_address,
                        SecurityMonitor.RATE_LIMIT_EXCEEDED,
                        f"Daily limit exceeded: {rate_limit.request_count}/{self.max_requests_per_day}"
                    )
                    return False, f"Daily limit exceeded. You can only make {self.max_requests_per_day} requests per day."
            
            return True, None
            
        except Exception as e:
            self.logger.error(f"Error in IP-based rate limiting for {ip_address}: {e}")
            return False, f"Error checking rate limits: {str(e)}"
    
    def record_request(self, ip_address, maximum_brain=False, user_id=None):
        """
        Record a successful request for IP-based rate limiting (anonymous users only).
        For authenticated users, credit deduction is handled in _check_credit_limits.
        """
        try:
            # Only record IP-based requests for anonymous users
            if user_id and is_credit_system_enabled() and is_user_auth_enabled():
                self.logger.debug(f"Skipping IP rate limit recording for authenticated user {user_id}")
                return True
            
            today = date.today()
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
            
            db.session.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"Error recording request for {ip_address}: {e}")
            db.session.rollback()
            return False
    
    def get_user_credit_info(self, user_id):
        """
        Get credit information for authenticated users.
        """
        try:
            if not (is_credit_system_enabled() and is_user_auth_enabled()):
                return None
                
            credit_balance = self.credit_manager.get_or_create_credit_balance(user_id)
            
            # Reset daily usage if needed
            self.credit_manager.check_and_reset_daily_usage(credit_balance)
            
            # Expire subscription credits if needed
            self.credit_manager.expire_subscription_credits(user_id)
            
            return {
                'total_credits': credit_balance.total_credits,
                'subscription_credits': credit_balance.subscription_credits,
                'topup_credits': credit_balance.topup_credits,
                'credits_used_today': credit_balance.credits_used_today,
                'subscription_expiry': credit_balance.subscription_credits_expiry.isoformat() if credit_balance.subscription_credits_expiry else None,
                'standard_cost': self.credit_manager.standard_analysis_cost,
                'brain_cost': self.credit_manager.brain_analysis_cost
            }
            
        except Exception as e:
            self.logger.error(f"Error getting credit info for user {user_id}: {e}")
            return None
    
    def get_remaining_requests(self, ip_address):
        """Get remaining request counts for IP-based rate limiting (anonymous users)"""
        try:
            today = date.today()
            rate_limit = RateLimit.query.filter_by(
                ip_address=ip_address,
                date_created=today
            ).first()
            
            if not rate_limit:
                return {
                    'remaining_standard': self.max_requests_per_day,
                    'remaining_brain': self.max_brain_requests_per_day,
                    'used_standard': 0,
                    'used_brain': 0
                }
            
            return {
                'remaining_standard': max(0, self.max_requests_per_day - rate_limit.request_count),
                'remaining_brain': max(0, self.max_brain_requests_per_day - rate_limit.maximum_brain_count),
                'used_standard': rate_limit.request_count,
                'used_brain': rate_limit.maximum_brain_count
            }
            
        except Exception as e:
            self.logger.error(f"Error getting remaining requests for {ip_address}: {e}")
            return {
                'remaining_standard': 0,
                'remaining_brain': 0,
                'used_standard': self.max_requests_per_day,
                'used_brain': self.max_brain_requests_per_day
            }
    
    def check_api_rate_limit(self, ip_address: str, endpoint_type: str = 'general') -> bool:
        """
        Production-grade API rate limiting for account endpoints
        
        Args:
            ip_address: Client IP address
            endpoint_type: Type of endpoint ('account_api', 'general', etc.)
        
        Returns:
            bool: True if request is allowed, False if rate limited
        """
        try:
            from datetime import timedelta
            
            # More lenient limits for authenticated API endpoints
            if endpoint_type == 'account_api':
                max_per_minute = 60  # 60 requests per minute for authenticated APIs
                max_per_hour = 1000   # 1000 requests per hour
            else:
                max_per_minute = 20   # 20 requests per minute for general APIs
                max_per_hour = 200    # 200 requests per hour
            
            # Check minute-based rate limit
            minute_key = f"api_limit_{endpoint_type}_{ip_address}_{datetime.now().strftime('%Y%m%d%H%M')}"
            minute_requests = self._get_cache_value(minute_key, 0)
            
            if minute_requests >= max_per_minute:
                self.logger.warning(f"API rate limit exceeded for {ip_address} on {endpoint_type}: {minute_requests}/min")
                return False
            
            # Check hourly rate limit
            hour_key = f"api_limit_{endpoint_type}_{ip_address}_{datetime.now().strftime('%Y%m%d%H')}"
            hour_requests = self._get_cache_value(hour_key, 0)
            
            if hour_requests >= max_per_hour:
                self.logger.warning(f"Hourly API rate limit exceeded for {ip_address} on {endpoint_type}: {hour_requests}/hour")
                return False
            
            # Increment counters
            self._increment_cache_value(minute_key, expiry_minutes=1)
            self._increment_cache_value(hour_key, expiry_minutes=60)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking API rate limit for {ip_address}: {e}")
            # Fail secure - deny on error
            return False
    
    def _get_cache_value(self, key: str, default: int = 0) -> int:
        """Get value from cache with fallback"""
        try:
            # Simple in-memory cache for now
            if not hasattr(self, '_rate_cache'):
                self._rate_cache = {}
            
            if key in self._rate_cache:
                value, expiry = self._rate_cache[key]
                if datetime.now() < expiry:
                    return value
                else:
                    del self._rate_cache[key]
            
            return default
        except Exception:
            return default
    
    def _increment_cache_value(self, key: str, expiry_minutes: int = 60):
        """Increment cache value with expiry"""
        try:
            from datetime import timedelta
            if not hasattr(self, '_rate_cache'):
                self._rate_cache = {}
            
            current_value = self._get_cache_value(key, 0)
            expiry_time = datetime.now() + timedelta(minutes=expiry_minutes)
            self._rate_cache[key] = (current_value + 1, expiry_time)
            
        except Exception as e:
            self.logger.error(f"Error incrementing cache value {key}: {e}")
    
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
