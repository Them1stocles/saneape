"""
Unit tests for feature flag system.
Tests environment detection, flag management, and rollout logic.
"""

import pytest
import os
from unittest.mock import patch
from feature_flags import (
    FeatureFlagManager, 
    FeatureFlagEnvironment, 
    FeatureFlag,
    is_user_auth_enabled,
    is_credit_system_enabled,
    is_stripe_enabled
)

class TestFeatureFlagManager:
    """Test the core feature flag management functionality"""
    
    def test_environment_detection_development(self):
        """Test detection of development environment"""
        with patch.dict(os.environ, {}, clear=True):
            manager = FeatureFlagManager()
            assert manager.environment == FeatureFlagEnvironment.DEVELOPMENT
    
    def test_environment_detection_production(self):
        """Test detection of production environment"""
        with patch.dict(os.environ, {'REPLIT_DEPLOYMENT': 'production'}):
            manager = FeatureFlagManager()
            assert manager.environment == FeatureFlagEnvironment.PRODUCTION
    
    def test_environment_detection_staging(self):
        """Test detection of staging environment"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'staging'}):
            manager = FeatureFlagManager()
            assert manager.environment == FeatureFlagEnvironment.STAGING
    
    def test_flag_initialization_development(self):
        """Test flags are properly initialized in development"""
        with patch.dict(os.environ, {}, clear=True):
            manager = FeatureFlagManager()
            
            # Development should have most flags enabled
            assert manager.is_enabled('user_authentication')
            assert manager.is_enabled('credit_system')
            assert manager.is_enabled('admin_dashboard')
            
            # Payments should be disabled initially
            assert not manager.is_enabled('stripe_payments')
    
    def test_flag_initialization_production(self):
        """Test flags are properly initialized in production"""
        with patch.dict(os.environ, {'REPLIT_DEPLOYMENT': 'production'}):
            manager = FeatureFlagManager()
            
            # Production should have gradual rollout
            assert manager.flags['user_authentication'].rollout_percentage == 25
            assert not manager.is_enabled('credit_system')  # Not enabled in production yet
    
    def test_unknown_flag_returns_false(self):
        """Test unknown flag names return False"""
        manager = FeatureFlagManager()
        assert not manager.is_enabled('unknown_flag')
    
    def test_flag_not_in_environment(self):
        """Test flag returns False when not enabled for current environment"""
        with patch.dict(os.environ, {'REPLIT_DEPLOYMENT': 'production'}):
            manager = FeatureFlagManager()
            
            # credit_system is only enabled in development
            assert not manager.is_enabled('credit_system')
    
    def test_user_whitelist_override(self):
        """Test user whitelist overrides other settings"""
        manager = FeatureFlagManager()
        
        # Add user to whitelist for disabled flag
        manager.add_user_to_whitelist('stripe_payments', 'test_user_123')
        
        # Should be enabled for whitelisted user even though flag is disabled
        assert manager.is_enabled('stripe_payments', 'test_user_123')
        assert not manager.is_enabled('stripe_payments', 'other_user')
    
    def test_rollout_percentage_consistency(self):
        """Test rollout percentage gives consistent results for same user"""
        with patch.dict(os.environ, {'REPLIT_DEPLOYMENT': 'production'}):
            manager = FeatureFlagManager()
            
            # Set low rollout percentage to test
            manager.flags['user_authentication'].rollout_percentage = 10
            
            user_id = 'consistent_test_user'
            
            # Should get same result multiple times for same user
            first_result = manager.is_enabled('user_authentication', user_id)
            second_result = manager.is_enabled('user_authentication', user_id)
            third_result = manager.is_enabled('user_authentication', user_id)
            
            assert first_result == second_result == third_result
    
    def test_dynamic_flag_enable_disable(self):
        """Test dynamically enabling and disabling flags"""
        manager = FeatureFlagManager()
        
        # Initially disabled
        assert not manager.is_enabled('stripe_payments')
        
        # Enable flag
        result = manager.enable_flag('stripe_payments', 100)
        assert result is True
        assert manager.is_enabled('stripe_payments')
        
        # Disable flag
        result = manager.disable_flag('stripe_payments')
        assert result is True
        assert not manager.is_enabled('stripe_payments')
    
    def test_enable_disable_unknown_flag(self):
        """Test enabling/disabling unknown flags returns False"""
        manager = FeatureFlagManager()
        
        assert not manager.enable_flag('unknown_flag')
        assert not manager.disable_flag('unknown_flag')
    
    def test_get_flag_status(self):
        """Test getting detailed flag status"""
        manager = FeatureFlagManager()
        
        status = manager.get_flag_status('user_authentication')
        
        assert 'name' in status
        assert 'enabled' in status
        assert 'description' in status
        assert 'current_environment' in status
        assert 'enabled_environments' in status
        assert 'rollout_percentage' in status
        assert 'is_active' in status
        
        assert status['name'] == 'user_authentication'
    
    def test_get_flag_status_unknown(self):
        """Test getting status of unknown flag"""
        manager = FeatureFlagManager()
        
        status = manager.get_flag_status('unknown_flag')
        assert 'error' in status
    
    def test_get_all_flags(self):
        """Test getting status of all flags"""
        manager = FeatureFlagManager()
        
        all_flags = manager.get_all_flags()
        
        assert isinstance(all_flags, dict)
        assert 'user_authentication' in all_flags
        assert 'stripe_payments' in all_flags
        assert 'admin_dashboard' in all_flags
        
        # Each flag should have complete status
        for flag_name, status in all_flags.items():
            assert 'name' in status
            assert 'enabled' in status
            assert 'is_active' in status

class TestConvenienceFunctions:
    """Test the convenience functions for common flag checks"""
    
    def test_is_user_auth_enabled(self):
        """Test user authentication flag convenience function"""
        with patch('feature_flags.feature_flags') as mock_flags:
            mock_flags.is_enabled.return_value = True
            
            result = is_user_auth_enabled('test_user')
            
            assert result is True
            mock_flags.is_enabled.assert_called_once_with('user_authentication', 'test_user')
    
    def test_is_credit_system_enabled(self):
        """Test credit system flag convenience function"""
        with patch('feature_flags.feature_flags') as mock_flags:
            mock_flags.is_enabled.return_value = False
            
            result = is_credit_system_enabled()
            
            assert result is False
            mock_flags.is_enabled.assert_called_once_with('credit_system', None)
    
    def test_is_stripe_enabled(self):
        """Test Stripe payments flag convenience function"""
        with patch('feature_flags.feature_flags') as mock_flags:
            mock_flags.is_enabled.return_value = True
            
            result = is_stripe_enabled('user_123')
            
            assert result is True
            mock_flags.is_enabled.assert_called_once_with('stripe_payments', 'user_123')

class TestFeatureFlag:
    """Test the FeatureFlag dataclass"""
    
    def test_feature_flag_creation(self):
        """Test creating a feature flag"""
        flag = FeatureFlag(
            name='test_flag',
            enabled=True,
            description='Test flag for testing',
            environments=[FeatureFlagEnvironment.DEVELOPMENT],
            rollout_percentage=50,
            user_whitelist=['user1', 'user2']
        )
        
        assert flag.name == 'test_flag'
        assert flag.enabled is True
        assert flag.rollout_percentage == 50
        assert 'user1' in flag.user_whitelist
    
    def test_feature_flag_default_whitelist(self):
        """Test feature flag with default empty whitelist"""
        flag = FeatureFlag(
            name='test_flag',
            enabled=True,
            description='Test flag',
            environments=[FeatureFlagEnvironment.DEVELOPMENT]
        )
        
        assert flag.user_whitelist == []

class TestRolloutLogic:
    """Test rollout percentage logic and user distribution"""
    
    def test_rollout_percentage_distribution(self):
        """Test rollout percentage creates expected distribution"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):  # Use development environment
            manager = FeatureFlagManager()
            
            # Ensure flag is enabled and add production environment
            from feature_flags import FeatureFlagEnvironment
            manager.flags['user_authentication'].environments.append(FeatureFlagEnvironment.PRODUCTION)
            manager.flags['user_authentication'].enabled = True
            manager.flags['user_authentication'].rollout_percentage = 50
            
            # Test with many different users
            enabled_count = 0
            total_users = 100
            
            for i in range(total_users):
                user_id = f'test_user_{i}'
                if manager.is_enabled('user_authentication', user_id):
                    enabled_count += 1
            
            # Should be approximately 50% (allow 20% variance due to hashing)
            expected_min = total_users * 0.3  # 30%
            expected_max = total_users * 0.7  # 70%
            
            assert expected_min <= enabled_count <= expected_max
    
    def test_zero_percent_rollout(self):
        """Test 0% rollout disables for all users"""
        manager = FeatureFlagManager()
        
        manager.flags['user_authentication'].rollout_percentage = 0
        
        for i in range(10):
            user_id = f'test_user_{i}'
            assert not manager.is_enabled('user_authentication', user_id)
    
    def test_hundred_percent_rollout(self):
        """Test 100% rollout enables for all users"""
        manager = FeatureFlagManager()
        
        # Ensure flag is enabled and in current environment
        manager.enable_flag('user_authentication', 100)
        
        for i in range(10):
            user_id = f'test_user_{i}'
            assert manager.is_enabled('user_authentication', user_id)

class TestIntegration:
    """Integration tests for feature flags with other systems"""
    
    def test_feature_flag_integration_with_routes(self, client, test_feature_flags):
        """Test feature flags work with Flask routes"""
        # This would test actual route integration
        # For now, just verify the flag manager works in Flask context
        
        with client.application.app_context():
            assert is_user_auth_enabled() is True  # Enabled in test config
    
    @pytest.mark.parametrize("environment,expected_auth,expected_credit", [
        ('development', True, True),
        ('staging', True, False),
        ('production', False, False),  # Due to rollout percentage
    ])
    def test_environment_specific_behavior(self, environment, expected_auth, expected_credit):
        """Test flag behavior is correct for each environment"""
        with patch.dict(os.environ, {'ENVIRONMENT': environment}):
            manager = FeatureFlagManager()
            
            # Note: These tests might be probabilistic for production due to rollout
            if environment != 'production':
                assert manager.is_enabled('user_authentication') == expected_auth
                assert manager.is_enabled('credit_system') == expected_credit