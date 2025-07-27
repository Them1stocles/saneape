from app import db
from models import RateLimit
from datetime import datetime, date
import logging

class RateLimiter:
    def __init__(self, max_requests_per_day=2):
        self.max_requests_per_day = max_requests_per_day
    
    def is_allowed(self, ip_address):
        """Check if IP address is allowed to make a request"""
        try:
            today = date.today()
            
            # Get or create rate limit record for this IP and date
            rate_limit = RateLimit.query.filter_by(
                ip_address=ip_address,
                date_created=today
            ).first()
            
            if not rate_limit:
                return True  # First request of the day
            
            return rate_limit.request_count < self.max_requests_per_day
            
        except Exception as e:
            logging.error(f"Error checking rate limit: {str(e)}")
            return True  # Allow request if there's an error
    
    def record_request(self, ip_address):
        """Record a request for the IP address"""
        try:
            today = date.today()
            
            # Get or create rate limit record for this IP and date
            rate_limit = RateLimit.query.filter_by(
                ip_address=ip_address,
                date_created=today
            ).first()
            
            if rate_limit:
                rate_limit.request_count += 1
                rate_limit.last_request = datetime.utcnow()
            else:
                rate_limit = RateLimit()
                rate_limit.ip_address = ip_address
                rate_limit.request_count = 1
                rate_limit.last_request = datetime.utcnow()
                rate_limit.date_created = today
                db.session.add(rate_limit)
            
            db.session.commit()
            
        except Exception as e:
            logging.error(f"Error recording request: {str(e)}")
            db.session.rollback()
    
    def get_remaining_requests(self, ip_address):
        """Get remaining requests for the IP address"""
        try:
            today = date.today()
            
            rate_limit = RateLimit.query.filter_by(
                ip_address=ip_address,
                date_created=today
            ).first()
            
            if not rate_limit:
                return self.max_requests_per_day
            
            return max(0, self.max_requests_per_day - rate_limit.request_count)
            
        except Exception as e:
            logging.error(f"Error getting remaining requests: {str(e)}")
            return self.max_requests_per_day
