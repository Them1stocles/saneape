"""
Unit tests for database operations and performance.
Tests existing models and prepares for new user account models.
"""

import pytest
from datetime import datetime, timedelta
from app import db
from models import RateLimit, StockAnalysis, SystemLimits, AnalysisCache, SecurityLog

class TestExistingModels:
    """Test existing database models"""
    
    def test_rate_limit_model(self, test_db):
        """Test RateLimit model creation and queries"""
        rate_limit = RateLimit(
            ip_address='192.168.1.1',
            requests_today=5,
            brain_requests_today=1,
            last_request_date=datetime.utcnow().date()
        )
        
        test_db.session.add(rate_limit)
        test_db.session.commit()
        
        # Test retrieval
        retrieved = test_db.session.query(RateLimit).filter_by(ip_address='192.168.1.1').first()
        assert retrieved is not None
        assert retrieved.requests_today == 5
        assert retrieved.brain_requests_today == 1
    
    def test_stock_analysis_model(self, test_db):
        """Test StockAnalysis model creation and queries"""
        analysis = StockAnalysis(
            ticker='AAPL',
            recommendation='Yes, buy!',
            reasoning='Strong fundamentals',
            confidence=85,
            current_price=150.50,
            technical_analysis='{"sma_20": 148.75}',
            is_brain_analysis=False,
            analysis_cost=0.007
        )
        
        test_db.session.add(analysis)
        test_db.session.commit()
        
        # Test retrieval
        retrieved = test_db.session.query(StockAnalysis).filter_by(ticker='AAPL').first()
        assert retrieved is not None
        assert retrieved.recommendation == 'Yes, buy!'
        assert retrieved.confidence == 85
        assert retrieved.is_brain_analysis is False
    
    def test_system_limits_model(self, test_db):
        """Test SystemLimits model"""
        limits = SystemLimits(
            daily_api_calls=100,
            daily_cost_limit=25.0,
            current_api_calls=50,
            current_cost=12.50
        )
        
        test_db.session.add(limits)
        test_db.session.commit()
        
        retrieved = test_db.session.query(SystemLimits).first()
        assert retrieved.daily_cost_limit == 25.0
        assert retrieved.current_cost == 12.50
    
    def test_analysis_cache_model(self, test_db):
        """Test AnalysisCache model"""
        cache_entry = AnalysisCache(
            cache_key='AAPL_False',
            ticker='AAPL',
            result_data='{"recommendation": "Yes, buy!"}',
            expires_at=datetime.utcnow() + timedelta(hours=6)
        )
        
        test_db.session.add(cache_entry)
        test_db.session.commit()
        
        retrieved = test_db.session.query(AnalysisCache).filter_by(cache_key='AAPL_False').first()
        assert retrieved is not None
        assert retrieved.ticker == 'AAPL'
        assert 'Yes, buy!' in retrieved.result_data
    
    def test_security_log_model(self, test_db):
        """Test SecurityLog model"""
        log_entry = SecurityLog(
            ip_address='192.168.1.100',
            event_type='suspicious_activity',
            details='Rapid successive requests',
            severity='medium'
        )
        
        test_db.session.add(log_entry)
        test_db.session.commit()
        
        retrieved = test_db.session.query(SecurityLog).filter_by(ip_address='192.168.1.100').first()
        assert retrieved is not None
        assert retrieved.event_type == 'suspicious_activity'
        assert retrieved.severity == 'medium'

class TestDatabasePerformance:
    """Test database performance and indexing"""
    
    def test_bulk_rate_limit_inserts(self, test_db, performance_monitor):
        """Test performance of bulk rate limit inserts"""
        performance_monitor.start()
        
        # Create 100 rate limit entries
        entries = []
        for i in range(100):
            entry = RateLimit(
                ip_address=f'192.168.1.{i}',
                requests_today=i % 10,
                brain_requests_today=i % 3,
                last_request_date=datetime.utcnow().date()
            )
            entries.append(entry)
        
        test_db.session.add_all(entries)
        test_db.session.commit()
        
        # Should complete quickly
        performance_monitor.assert_duration_under(1.0)
        
        # Verify all entries were created
        count = test_db.session.query(RateLimit).count()
        assert count == 100
    
    def test_analysis_cache_queries(self, test_db, performance_monitor):
        """Test analysis cache query performance"""
        # Create test cache entries
        for i in range(50):
            entry = AnalysisCache(
                cache_key=f'TEST{i}_False',
                ticker=f'TEST{i}',
                result_data=f'{{"recommendation": "Test {i}"}}',
                expires_at=datetime.utcnow() + timedelta(hours=6)
            )
            test_db.session.add(entry)
        
        test_db.session.commit()
        
        performance_monitor.start()
        
        # Query specific cache entry
        result = test_db.session.query(AnalysisCache).filter_by(cache_key='TEST25_False').first()
        
        performance_monitor.assert_duration_under(0.1)
        
        assert result is not None
        assert result.ticker == 'TEST25'

class TestDatabaseIntegrity:
    """Test data integrity and constraints"""
    
    def test_unique_constraints(self, test_db):
        """Test unique constraints are enforced"""
        # Create first rate limit entry
        rate_limit1 = RateLimit(
            ip_address='192.168.1.1',
            requests_today=5,
            brain_requests_today=1,
            last_request_date=datetime.utcnow().date()
        )
        test_db.session.add(rate_limit1)
        test_db.session.commit()
        
        # Try to create duplicate
        rate_limit2 = RateLimit(
            ip_address='192.168.1.1',  # Same IP
            requests_today=3,
            brain_requests_today=0,
            last_request_date=datetime.utcnow().date()
        )
        test_db.session.add(rate_limit2)
        
        # Should raise integrity error
        with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
            test_db.session.commit()
    
    def test_foreign_key_constraints(self, test_db):
        """Test foreign key constraints (when they exist)"""
        # For now, just verify no issues with current schema
        # Will be more important when User model is added
        
        analysis = StockAnalysis(
            ticker='MSFT',
            recommendation='No, don\'t buy',
            reasoning='Overvalued',
            confidence=70,
            current_price=300.00,
            technical_analysis='{}',
            is_brain_analysis=True,
            analysis_cost=0.018
        )
        
        test_db.session.add(analysis)
        test_db.session.commit()
        
        # Should succeed without foreign key issues
        assert analysis.id is not None

class TestDatabaseTransactions:
    """Test database transaction handling"""
    
    def test_transaction_rollback(self, test_db):
        """Test transaction rollback functionality"""
        initial_count = test_db.session.query(RateLimit).count()
        
        try:
            # Start transaction
            rate_limit = RateLimit(
                ip_address='192.168.1.200',
                requests_today=5,
                brain_requests_today=1,
                last_request_date=datetime.utcnow().date()
            )
            test_db.session.add(rate_limit)
            
            # Force an error
            invalid_analysis = StockAnalysis(
                ticker=None,  # This should cause an error
                recommendation='Test',
                reasoning='Test',
                confidence=50,
                current_price=100.0,
                technical_analysis='{}',
                is_brain_analysis=False,
                analysis_cost=0.007
            )
            test_db.session.add(invalid_analysis)
            test_db.session.commit()
            
        except Exception:
            test_db.session.rollback()
        
        # Count should be unchanged
        final_count = test_db.session.query(RateLimit).count()
        assert final_count == initial_count
    
    def test_atomic_operations(self, test_db):
        """Test atomic database operations"""
        # Test that related operations succeed or fail together
        
        rate_limit = RateLimit(
            ip_address='192.168.1.300',
            requests_today=1,
            brain_requests_today=0,
            last_request_date=datetime.utcnow().date()
        )
        
        analysis = StockAnalysis(
            ticker='GOOGL',
            recommendation='Yes, buy!',
            reasoning='Innovation leader',
            confidence=90,
            current_price=2800.00,
            technical_analysis='{"rsi": 45}',
            is_brain_analysis=False,
            analysis_cost=0.007
        )
        
        # Add both in same transaction
        test_db.session.add(rate_limit)
        test_db.session.add(analysis)
        test_db.session.commit()
        
        # Both should exist
        assert test_db.session.query(RateLimit).filter_by(ip_address='192.168.1.300').first() is not None
        assert test_db.session.query(StockAnalysis).filter_by(ticker='GOOGL').first() is not None

class TestDatabaseMigrationPreparation:
    """Prepare for upcoming database migrations"""
    
    def test_existing_schema_compatibility(self, test_db):
        """Test current schema works correctly"""
        # Verify all existing tables can be created
        test_db.create_all()
        
        # Get table names
        tables = test_db.engine.table_names()
        
        expected_tables = [
            'rate_limit',
            'stock_analysis', 
            'system_limits',
            'analysis_cache',
            'security_log'
        ]
        
        for table in expected_tables:
            assert table in tables
    
    def test_index_preparation(self, test_db):
        """Test that indexes will work when added"""
        # This test prepares for the indexes we'll add in Phase 1
        
        # Create sample data that will benefit from indexes
        for i in range(20):
            rate_limit = RateLimit(
                ip_address=f'10.0.0.{i}',
                requests_today=i,
                brain_requests_today=i % 2,
                last_request_date=datetime.utcnow().date()
            )
            test_db.session.add(rate_limit)
        
        test_db.session.commit()
        
        # Test queries that will use future indexes
        # IP address lookups (will have index)
        result = test_db.session.query(RateLimit).filter_by(ip_address='10.0.0.10').first()
        assert result is not None
        
        # Date-based queries (will have index)
        today = datetime.utcnow().date()
        results = test_db.session.query(RateLimit).filter_by(last_request_date=today).all()
        assert len(results) == 20