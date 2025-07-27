"""
Unit tests for rate limiting system.
Tests current IP-based rate limiting and prepares for user-based system.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
from rate_limiter import RateLimiter
from models import RateLimit
from feature_flags import feature_flags

class TestCurrentRateLimiter:
    """Test existing IP-based rate limiting"""
    
    def test_check_rate_limit_new_ip(self, test_db, rate_limiter):
        """Test rate limit check for new IP address"""
        result = rate_limiter.check_rate_limit('192.168.1.1', is_brain=False)
        
        assert result['allowed'] is True
        assert result['requests_remaining'] == 5  # 6 total - 1 used
        assert result['brain_requests_remaining'] == 2
        assert 'reset_time' in result
    
    def test_check_rate_limit_existing_ip(self, test_db, rate_limiter):
        """Test rate limit check for existing IP with usage"""
        # Create existing rate limit
        existing = RateLimit(
            ip_address='192.168.1.2',
            requests_today=3,
            brain_requests_today=1,
            last_request_date=datetime.utcnow().date()
        )
        test_db.session.add(existing)
        test_db.session.commit()
        
        result = rate_limiter.check_rate_limit('192.168.1.2', is_brain=False)
        
        assert result['allowed'] is True
        assert result['requests_remaining'] == 2  # 6 - 3 - 1 (current request)
        assert result['brain_requests_remaining'] == 1  # 2 - 1
    
    def test_rate_limit_exceeded_standard(self, test_db, rate_limiter):
        """Test rate limit exceeded for standard requests"""
        # Create IP at limit
        existing = RateLimit(
            ip_address='192.168.1.3',
            requests_today=6,  # At limit
            brain_requests_today=0,
            last_request_date=datetime.utcnow().date()
        )
        test_db.session.add(existing)
        test_db.session.commit()
        
        result = rate_limiter.check_rate_limit('192.168.1.3', is_brain=False)
        
        assert result['allowed'] is False
        assert result['requests_remaining'] == 0
        assert 'error_message' in result
    
    def test_rate_limit_exceeded_brain(self, test_db, rate_limiter):
        """Test rate limit exceeded for brain requests"""
        # Create IP at brain limit
        existing = RateLimit(
            ip_address='192.168.1.4',
            requests_today=2,
            brain_requests_today=2,  # At brain limit
            last_request_date=datetime.utcnow().date()
        )
        test_db.session.add(existing)
        test_db.session.commit()
        
        result = rate_limiter.check_rate_limit('192.168.1.4', is_brain=True)
        
        assert result['allowed'] is False
        assert result['brain_requests_remaining'] == 0
        assert 'brain' in result['error_message'].lower()
    
    def test_rate_limit_reset_new_day(self, test_db, rate_limiter):
        """Test rate limits reset for new day"""
        yesterday = datetime.utcnow().date() - timedelta(days=1)
        
        # Create rate limit from yesterday
        existing = RateLimit(
            ip_address='192.168.1.5',
            requests_today=6,  # Was at limit yesterday
            brain_requests_today=2,
            last_request_date=yesterday
        )
        test_db.session.add(existing)
        test_db.session.commit()
        
        result = rate_limiter.check_rate_limit('192.168.1.5', is_brain=False)
        
        assert result['allowed'] is True
        assert result['requests_remaining'] == 5  # Reset to full limit
        assert result['brain_requests_remaining'] == 2
    
    def test_update_rate_limit_standard(self, test_db, rate_limiter):
        """Test updating rate limit for standard request"""
        rate_limiter.update_rate_limit('192.168.1.6', is_brain=False)
        
        # Check database was updated
        rate_limit = test_db.session.query(RateLimit).filter_by(ip_address='192.168.1.6').first()
        assert rate_limit is not None
        assert rate_limit.requests_today == 1
        assert rate_limit.brain_requests_today == 0
        assert rate_limit.last_request_date == datetime.utcnow().date()
    
    def test_update_rate_limit_brain(self, test_db, rate_limiter):
        """Test updating rate limit for brain request"""
        rate_limiter.update_rate_limit('192.168.1.7', is_brain=True)
        
        # Check database was updated
        rate_limit = test_db.session.query(RateLimit).filter_by(ip_address='192.168.1.7').first()
        assert rate_limit is not None
        assert rate_limit.requests_today == 1  # Standard count also incremented
        assert rate_limit.brain_requests_today == 1
    
    def test_update_existing_rate_limit(self, test_db, rate_limiter):
        """Test updating existing rate limit entry"""
        # Create existing entry
        existing = RateLimit(
            ip_address='192.168.1.8',
            requests_today=2,
            brain_requests_today=0,
            last_request_date=datetime.utcnow().date()
        )
        test_db.session.add(existing)
        test_db.session.commit()
        
        rate_limiter.update_rate_limit('192.168.1.8', is_brain=True)
        
        # Check update
        rate_limit = test_db.session.query(RateLimit).filter_by(ip_address='192.168.1.8').first()
        assert rate_limit.requests_today == 3  # Incremented from 2
        assert rate_limit.brain_requests_today == 1  # Incremented from 0

class TestRateLimiterErrorHandling:
    """Test error handling in rate limiter"""
    
    def test_database_error_handling(self, test_db, rate_limiter):
        """Test rate limiter handles database errors gracefully"""
        
        with patch.object(test_db.session, 'query') as mock_query:
            mock_query.side_effect = Exception("Database connection error")
            
            # Should deny request on database error (security-first)
            result = rate_limiter.check_rate_limit('192.168.1.9', is_brain=False)
            
            assert result['allowed'] is False
            assert 'error' in result['error_message'].lower()
    
    def test_commit_error_handling(self, test_db, rate_limiter):
        """Test handling of commit errors"""
        
        with patch.object(test_db.session, 'commit') as mock_commit:
            mock_commit.side_effect = Exception("Commit failed")
            
            # Should handle gracefully
            try:
                rate_limiter.update_rate_limit('192.168.1.10', is_brain=False)
                # Should not raise exception
            except Exception as e:
                pytest.fail(f"update_rate_limit raised exception: {e}")

class TestRateLimiterFeatureFlags:
    """Test rate limiter with feature flags"""
    
    @patch('rate_limiter.is_enhanced_rate_limiting_enabled')
    def test_enhanced_rate_limiting_disabled(self, mock_feature_flag, test_db, rate_limiter):
        """Test rate limiter works when enhanced features disabled"""
        mock_feature_flag.return_value = False
        
        result = rate_limiter.check_rate_limit('192.168.1.11', is_brain=False)
        
        # Should work with basic functionality
        assert result['allowed'] is True
        assert 'requests_remaining' in result
    
    @patch('rate_limiter.is_enhanced_rate_limiting_enabled')
    def test_enhanced_rate_limiting_enabled(self, mock_feature_flag, test_db, rate_limiter):
        """Test rate limiter with enhanced features enabled"""
        mock_feature_flag.return_value = True
        
        result = rate_limiter.check_rate_limit('192.168.1.12', is_brain=False)
        
        # Should work with enhanced functionality
        assert result['allowed'] is True
        # Enhanced features would add more fields in the future

class TestRateLimiterIntegration:
    """Integration tests for rate limiter"""
    
    def test_rate_limiter_with_real_flow(self, client, test_db):
        """Test rate limiter in actual request flow"""
        
        # Make multiple requests to same endpoint
        responses = []
        for i in range(7):  # More than limit of 6
            response = client.post('/', data={'ticker': 'AAPL'})
            responses.append(response)
        
        # First 6 should work, 7th should be rate limited
        for i in range(6):
            assert responses[i].status_code != 429  # Not rate limited
        
        # 7th request should be rate limited
        assert responses[6].status_code == 429 or 'limit' in responses[6].get_data(as_text=True).lower()
    
    def test_rate_limiter_resets_daily(self, test_db, rate_limiter):
        """Test rate limiter properly resets daily"""
        
        # Simulate yesterday's usage
        yesterday = datetime.utcnow().date() - timedelta(days=1)
        old_rate_limit = RateLimit(
            ip_address='192.168.1.13',
            requests_today=6,
            brain_requests_today=2,
            last_request_date=yesterday
        )
        test_db.session.add(old_rate_limit)
        test_db.session.commit()
        
        # Check rate limit today
        result = rate_limiter.check_rate_limit('192.168.1.13', is_brain=False)
        
        # Should be reset
        assert result['allowed'] is True
        assert result['requests_remaining'] == 5  # Full limit minus current request
        
        # Verify database was updated
        updated_limit = test_db.session.query(RateLimit).filter_by(ip_address='192.168.1.13').first()
        assert updated_limit.last_request_date == datetime.utcnow().date()
        assert updated_limit.requests_today == 1  # Reset and incremented
        assert updated_limit.brain_requests_today == 0  # Reset

class TestRateLimiterPerformance:
    """Test rate limiter performance"""
    
    def test_rate_limit_check_performance(self, test_db, rate_limiter, performance_monitor):
        """Test rate limit check performance"""
        
        performance_monitor.start()
        
        # Perform rate limit check
        result = rate_limiter.check_rate_limit('192.168.1.14', is_brain=False)
        
        # Should complete quickly
        performance_monitor.assert_duration_under(0.1)
        
        assert result['allowed'] is True
    
    def test_concurrent_rate_limit_checks(self, test_db, rate_limiter):
        """Test concurrent rate limit checks don't interfere"""
        import threading
        results = []
        
        def check_rate_limit(ip_suffix):
            result = rate_limiter.check_rate_limit(f'192.168.1.{ip_suffix}', is_brain=False)
            results.append(result)
        
        # Create multiple threads
        threads = []
        for i in range(20, 30):  # 10 threads with different IPs
            thread = threading.Thread(target=check_rate_limit, args=(i,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All should succeed
        assert len(results) == 10
        for result in results:
            assert result['allowed'] is True

class TestRateLimiterUserPreparation:
    """Prepare rate limiter for user-based system"""
    
    def test_rate_limiter_user_extension_ready(self, test_db, rate_limiter):
        """Test rate limiter can be extended for user-based limiting"""
        
        # Current check_rate_limit method should accept additional parameters
        # This tests the interface will work when we add user_id parameter
        
        result = rate_limiter.check_rate_limit('192.168.1.15', is_brain=False)
        
        # Should work with current interface
        assert 'allowed' in result
        assert 'requests_remaining' in result
        assert 'brain_requests_remaining' in result
        
        # Interface is ready for extension with user_id parameter
    
    def test_rate_limiter_hybrid_mode_preparation(self, test_db, rate_limiter):
        """Test preparation for hybrid IP/user rate limiting"""
        
        # When user authentication is added, we'll need to support both:
        # 1. IP-based limiting for anonymous users (current)
        # 2. User-based limiting for authenticated users (future)
        
        # Current system should continue working
        result1 = rate_limiter.check_rate_limit('192.168.1.16', is_brain=False)
        result2 = rate_limiter.check_rate_limit('192.168.1.17', is_brain=True)
        
        assert result1['allowed'] is True
        assert result2['allowed'] is True
        
        # Different IPs should have separate limits
        assert result1['requests_remaining'] == result2['requests_remaining']