"""
Production-grade test configuration for SaneApe user accounts and payment system.
Provides fixtures, test database setup, and mocking utilities.
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from contextlib import contextmanager

# Test imports
from app import app, db
from models import RateLimit, StockAnalysis, SystemLimits, AnalysisCache, SecurityLog
from feature_flags import FeatureFlagManager, FeatureFlagEnvironment
from monitoring import MonitoringManager
from rate_limiter import RateLimiter
from cost_manager import CostManager

@pytest.fixture(scope="session")
def test_app():
    """Create test Flask application with test configuration"""
    
    # Create temporary database
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    
    # Configure test app
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret-key',
        'OPENAI_API_KEY': 'test-openai-key',
        'ENVIRONMENT': 'testing'
    })
    
    # Create application context
    with app.app_context():
        db.create_all()
        yield app
        
    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def client(test_app):
    """Test client for making HTTP requests"""
    return test_app.test_client()

@pytest.fixture
def test_db(test_app):
    """Clean database for each test"""
    with test_app.app_context():
        db.create_all()
        yield db
        db.session.remove()
        db.drop_all()

@pytest.fixture
def sample_user_data():
    """Sample user data for testing"""
    return {
        'id': 'test_user_123',
        'email': 'test@example.com',
        'first_name': 'Test',
        'last_name': 'User',
        'profile_image_url': 'https://example.com/avatar.png'
    }

@pytest.fixture
def authenticated_user(test_db, sample_user_data):
    """Create an authenticated test user"""
    # Note: User model will be created in Phase 1
    # For now, return mock user data
    return sample_user_data

@pytest.fixture
def mock_openai():
    """Mock OpenAI API responses"""
    with patch('stock_analyzer.openai.chat.completions.create') as mock_create:
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = """
        {
            "recommendation": "Yes, buy!",
            "confidence": 85,
            "reasoning": "Strong technical indicators and positive momentum"
        }
        """
        mock_create.return_value = mock_response
        yield mock_create

@pytest.fixture
def mock_yfinance():
    """Mock yfinance data for testing"""
    with patch('stock_analyzer.yf.download') as mock_download:
        import pandas as pd
        import numpy as np
        
        # Create sample stock data
        dates = pd.date_range(start='2023-01-01', end='2024-12-31', freq='D')
        data = pd.DataFrame({
            'Open': np.random.uniform(100, 200, len(dates)),
            'High': np.random.uniform(150, 250, len(dates)),
            'Low': np.random.uniform(50, 150, len(dates)),
            'Close': np.random.uniform(100, 200, len(dates)),
            'Volume': np.random.randint(1000000, 10000000, len(dates))
        }, index=dates)
        
        mock_download.return_value = data
        yield mock_download

@pytest.fixture
def mock_stripe():
    """Mock Stripe API responses"""
    stripe_mocks = {}
    
    # Mock Stripe Customer
    with patch('stripe.Customer') as customer_mock:
        customer_mock.create.return_value = Mock(id='cus_test123')
        customer_mock.retrieve.return_value = Mock(id='cus_test123', email='test@example.com')
        stripe_mocks['customer'] = customer_mock
        
        # Mock Stripe Subscription
        with patch('stripe.Subscription') as subscription_mock:
            subscription_mock.create.return_value = Mock(
                id='sub_test123',
                status='active',
                current_period_end=1234567890
            )
            stripe_mocks['subscription'] = subscription_mock
            
            # Mock Stripe Payment Intent
            with patch('stripe.PaymentIntent') as payment_intent_mock:
                payment_intent_mock.create.return_value = Mock(
                    id='pi_test123',
                    status='succeeded',
                    amount=500
                )
                stripe_mocks['payment_intent'] = payment_intent_mock
                
                yield stripe_mocks

@pytest.fixture
def clean_monitoring():
    """Reset monitoring state for each test"""
    # Reset singleton instance
    MonitoringManager._instance = None
    yield
    # Clean up after test
    MonitoringManager._instance = None

@pytest.fixture
def test_feature_flags():
    """Feature flags configured for testing"""
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing'}):
        flags = FeatureFlagManager()
        # Enable all features for testing
        flags.enable_flag('user_authentication', 100)
        flags.enable_flag('credit_system', 100)
        flags.enable_flag('enhanced_rate_limiting', 100)
        yield flags

@pytest.fixture
def rate_limiter(test_db):
    """Clean rate limiter for each test"""
    return RateLimiter()

@pytest.fixture
def cost_manager(test_db):
    """Clean cost manager for each test"""
    return CostManager()

# Helper functions for test data creation

def create_test_analysis(ticker='AAPL', is_brain=False, recommendation='Yes, buy!'):
    """Create test stock analysis data"""
    return {
        'ticker': ticker,
        'recommendation': recommendation,
        'confidence': 85,
        'reasoning': 'Test analysis reasoning',
        'current_price': 150.50,
        'technical_analysis': {
            'sma_20': 148.75,
            'rsi': 65.2,
            'macd': 1.5
        },
        'is_brain_analysis': is_brain,
        'analysis_cost': 0.018 if is_brain else 0.007,
        'created_at': datetime.utcnow()
    }

def create_test_subscription(user_id='test_user_123', plan_type='monthly', status='active'):
    """Create test subscription data"""
    return {
        'user_id': user_id,
        'stripe_subscription_id': f'sub_test_{user_id}',
        'plan_type': plan_type,
        'status': status,
        'created_at': datetime.utcnow()
    }

def create_test_credit_balance(user_id='test_user_123', subscription_credits=100, topup_credits=0):
    """Create test credit balance data"""
    return {
        'user_id': user_id,
        'subscription_credits': subscription_credits,
        'topup_credits': topup_credits,
        'credits_used_today': 0,
        'last_reset_date': datetime.utcnow().date(),
        'subscription_credits_expiry': datetime.utcnow().date() + timedelta(days=30)
    }

# Test database utilities

@contextmanager
def assert_db_rollback(test_db):
    """Context manager to ensure database rollback on assertion failures"""
    try:
        yield
        test_db.session.commit()
    except Exception:
        test_db.session.rollback()
        raise

def count_table_rows(test_db, model_class):
    """Count rows in a table"""
    return test_db.session.query(model_class).count()

# Mock environment variables for testing

@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing"""
    env_vars = {
        'OPENAI_API_KEY': 'test-openai-key',
        'STRIPE_SECRET_KEY': 'sk_test_stripe_key',
        'DATABASE_URL': 'sqlite:///test.db',
        'SESSION_SECRET': 'test-session-secret',
        'REPL_ID': 'test-repl-id',
        'ENVIRONMENT': 'testing'
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars

# Integration test helpers

class TestStockAnalysisFlow:
    """Helper class for testing complete stock analysis flows"""
    
    def __init__(self, client, test_db):
        self.client = client
        self.db = test_db
    
    def submit_analysis_request(self, ticker='AAPL', is_brain=False, user_id=None):
        """Submit a stock analysis request"""
        data = {'ticker': ticker}
        if is_brain:
            data['brain'] = 'true'
            
        # Add session data if user_id provided
        if user_id:
            with self.client.session_transaction() as sess:
                sess['user_id'] = user_id
                
        return self.client.post('/', data=data, follow_redirects=True)
    
    def verify_analysis_stored(self, ticker='AAPL'):
        """Verify analysis was stored in database"""
        analysis = self.db.session.query(StockAnalysis).filter_by(ticker=ticker).first()
        return analysis is not None
    
    def verify_rate_limit_updated(self, ip_address='127.0.0.1'):
        """Verify rate limit was properly updated"""
        rate_limit = self.db.session.query(RateLimit).filter_by(ip_address=ip_address).first()
        return rate_limit is not None and rate_limit.requests_today > 0

@pytest.fixture
def analysis_flow(client, test_db):
    """Stock analysis testing flow helper"""
    return TestStockAnalysisFlow(client, test_db)

# Performance testing utilities

@pytest.fixture
def performance_monitor():
    """Monitor performance during tests"""
    import time
    
    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            
        def start(self):
            self.start_time = time.time()
            
        def end(self):
            self.end_time = time.time()
            return self.end_time - self.start_time if self.start_time else 0
            
        def assert_duration_under(self, max_seconds):
            duration = self.end()
            assert duration < max_seconds, f"Operation took {duration}s, expected under {max_seconds}s"
    
    return PerformanceMonitor()

# Async testing support

@pytest.fixture
def async_test_runner():
    """Helper for running async tests"""
    import asyncio
    
    def run_async(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    return run_async

# Custom assertions

def assert_valid_json_response(response, expected_status=200):
    """Assert response is valid JSON with expected status"""
    assert response.status_code == expected_status
    assert response.content_type == 'application/json'
    return response.get_json()

def assert_contains_text(response, text):
    """Assert response contains specific text"""
    assert text in response.get_data(as_text=True)

def assert_redirects_to(response, expected_location):
    """Assert response redirects to expected location"""
    assert response.status_code in [301, 302, 303, 307, 308]
    assert expected_location in response.location