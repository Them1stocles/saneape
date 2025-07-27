"""
Production-grade feature flag system for gradual rollout and A/B testing.
Enables safe deployment of user accounts and payment features.
"""

import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class FeatureFlagEnvironment(Enum):
    """Environment types for feature flag configuration"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

@dataclass
class FeatureFlag:
    """Feature flag configuration with environment support"""
    name: str
    enabled: bool
    description: str
    environments: list[FeatureFlagEnvironment]
    rollout_percentage: int = 100  # 0-100, for gradual rollouts
    user_whitelist: list[str] = None  # Specific user IDs for testing
    
    def __post_init__(self):
        if self.user_whitelist is None:
            self.user_whitelist = []

class FeatureFlagManager:
    """Centralized feature flag management with environment awareness"""
    
    def __init__(self):
        self.environment = self._detect_environment()
        self.flags = self._initialize_flags()
        logger.info(f"Feature flags initialized for {self.environment.value} environment")
    
    def _detect_environment(self) -> FeatureFlagEnvironment:
        """Detect current environment from environment variables"""
        env = os.environ.get('REPLIT_DEPLOYMENT', 'development').lower()
        
        if env == 'production' or os.environ.get('ENVIRONMENT') == 'production':
            return FeatureFlagEnvironment.PRODUCTION
        elif env == 'staging' or os.environ.get('ENVIRONMENT') == 'staging':
            return FeatureFlagEnvironment.STAGING
        else:
            return FeatureFlagEnvironment.DEVELOPMENT
    
    def _initialize_flags(self) -> Dict[str, FeatureFlag]:
        """Initialize all feature flags with environment-specific settings"""
        
        # Development: All features enabled for testing
        # Staging: User features enabled, payments careful
        # Production: Gradual rollout
        
        dev_envs = [FeatureFlagEnvironment.DEVELOPMENT]
        staging_envs = [FeatureFlagEnvironment.DEVELOPMENT, FeatureFlagEnvironment.STAGING]
        all_envs = [FeatureFlagEnvironment.DEVELOPMENT, FeatureFlagEnvironment.STAGING, FeatureFlagEnvironment.PRODUCTION]
        
        flags = {
            # Phase 1: User Authentication
            'user_authentication': FeatureFlag(
                name='user_authentication',
                enabled=True,
                description='Enable Replit-based user authentication and session management',
                environments=all_envs,  # Enable in all environments for demo
                rollout_percentage=100
            ),
            
            'user_registration': FeatureFlag(
                name='user_registration',
                enabled=True,
                description='Allow new user registration and profile creation',
                environments=dev_envs if self.environment == FeatureFlagEnvironment.DEVELOPMENT else staging_envs,
                rollout_percentage=100 if self.environment != FeatureFlagEnvironment.PRODUCTION else 25
            ),
            
            # Phase 2: Credit System
            'credit_system': FeatureFlag(
                name='credit_system',
                enabled=True,
                description='Enable credit-based analysis system for authenticated users',
                environments=all_envs,  # Enable in all environments for demo
                rollout_percentage=100
            ),
            
            'credit_display': FeatureFlag(
                name='credit_display',
                enabled=self.environment == FeatureFlagEnvironment.DEVELOPMENT,
                description='Show credit balance and usage in UI',
                environments=dev_envs,
                rollout_percentage=100 if self.environment == FeatureFlagEnvironment.DEVELOPMENT else 0
            ),
            
            # Phase 2: Stripe Payments
            'stripe_payments': FeatureFlag(
                name='stripe_payments',
                enabled=False,  # Disabled until Stripe integration complete
                description='Enable Stripe payment processing for subscriptions and top-ups',
                environments=dev_envs,
                rollout_percentage=0  # Will be manually enabled after testing
            ),
            
            'subscription_management': FeatureFlag(
                name='subscription_management',
                enabled=False,
                description='Enable subscription creation, updates, and cancellation',
                environments=dev_envs,
                rollout_percentage=0
            ),
            
            'topup_purchases': FeatureFlag(
                name='topup_purchases',
                enabled=False,
                description='Enable one-time credit pack purchases',
                environments=dev_envs,
                rollout_percentage=0
            ),
            
            # Phase 3: Enhanced Features
            'enhanced_rate_limiting': FeatureFlag(
                name='enhanced_rate_limiting',
                enabled=self.environment == FeatureFlagEnvironment.DEVELOPMENT,
                description='Use hybrid user/IP rate limiting with credit deduction',
                environments=dev_envs,
                rollout_percentage=100 if self.environment == FeatureFlagEnvironment.DEVELOPMENT else 0
            ),
            
            'dual_credit_system': FeatureFlag(
                name='dual_credit_system',
                enabled=False,
                description='Enable subscription + top-up credit separation with different expiration rules',
                environments=dev_envs,
                rollout_percentage=0
            ),
            
            # Admin and Monitoring
            'admin_dashboard': FeatureFlag(
                name='admin_dashboard',
                enabled=True,
                description='Enable enhanced admin dashboard with payment monitoring',
                environments=all_envs,
                rollout_percentage=100
            ),
            
            'payment_monitoring': FeatureFlag(
                name='payment_monitoring',
                enabled=True,
                description='Enable comprehensive payment failure monitoring and alerting',
                environments=all_envs,
                rollout_percentage=100
            ),
            
            # A/B Testing
            'subscription_bonus': FeatureFlag(
                name='subscription_bonus',
                enabled=False,
                description='Give 20% bonus credits on top-up purchases for subscribers',
                environments=staging_envs,
                rollout_percentage=50  # A/B test at 50%
            )
        }
        
        return flags
    
    def is_enabled(self, flag_name: str, user_id: Optional[str] = None) -> bool:
        """
        Check if a feature flag is enabled for the current environment and user.
        
        Args:
            flag_name: Name of the feature flag
            user_id: Optional user ID for user-specific testing
            
        Returns:
            True if feature is enabled, False otherwise
        """
        if flag_name not in self.flags:
            logger.warning(f"Unknown feature flag: {flag_name}")
            return False
            
        flag = self.flags[flag_name]
        
        # Check if flag is enabled in current environment
        if self.environment not in flag.environments:
            return False
            
        # Check user whitelist first (overrides all other settings)
        if user_id and user_id in flag.user_whitelist:
            logger.debug(f"Feature {flag_name} enabled for whitelisted user {user_id}")
            return True
            
        # Check if flag is globally disabled
        if not flag.enabled:
            return False
            
        # Check rollout percentage (for gradual rollouts)
        if flag.rollout_percentage < 100:
            # Use user_id hash for consistent user experience
            if user_id:
                import hashlib
                user_hash = int(hashlib.md5(f"{flag_name}_{user_id}".encode()).hexdigest()[:8], 16)
                user_percentage = user_hash % 100
                return user_percentage < flag.rollout_percentage
            else:
                # For anonymous users, use random rollout
                import random
                return random.randint(0, 99) < flag.rollout_percentage
        
        return True
    
    def get_flag_status(self, flag_name: str) -> Dict[str, Any]:
        """Get detailed status information for a feature flag"""
        if flag_name not in self.flags:
            return {"error": f"Unknown feature flag: {flag_name}"}
            
        flag = self.flags[flag_name]
        return {
            "name": flag.name,
            "enabled": flag.enabled,
            "description": flag.description,
            "current_environment": self.environment.value,
            "enabled_environments": [env.value for env in flag.environments],
            "rollout_percentage": flag.rollout_percentage,
            "user_whitelist_count": len(flag.user_whitelist),
            "is_active": self.is_enabled(flag_name)
        }
    
    def get_all_flags(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all feature flags"""
        return {name: self.get_flag_status(name) for name in self.flags.keys()}
    
    def enable_flag(self, flag_name: str, rollout_percentage: int = 100) -> bool:
        """
        Dynamically enable a feature flag (admin use).
        
        Args:
            flag_name: Name of flag to enable
            rollout_percentage: Percentage of users to enable for (0-100)
            
        Returns:
            True if successful, False if flag doesn't exist
        """
        if flag_name not in self.flags:
            return False
            
        self.flags[flag_name].enabled = True
        self.flags[flag_name].rollout_percentage = rollout_percentage
        logger.info(f"Feature flag {flag_name} enabled at {rollout_percentage}% rollout")
        return True
    
    def disable_flag(self, flag_name: str) -> bool:
        """
        Dynamically disable a feature flag (emergency use).
        
        Args:
            flag_name: Name of flag to disable
            
        Returns:
            True if successful, False if flag doesn't exist
        """
        if flag_name not in self.flags:
            return False
            
        self.flags[flag_name].enabled = False
        logger.warning(f"Feature flag {flag_name} disabled")
        return True
    
    def add_user_to_whitelist(self, flag_name: str, user_id: str) -> bool:
        """Add user to feature flag whitelist for testing"""
        if flag_name not in self.flags:
            return False
            
        if user_id not in self.flags[flag_name].user_whitelist:
            self.flags[flag_name].user_whitelist.append(user_id)
            logger.info(f"User {user_id} added to {flag_name} whitelist")
        return True

# Global feature flag manager instance
feature_flags = FeatureFlagManager()

# Convenience functions for common checks
def is_user_auth_enabled(user_id: Optional[str] = None) -> bool:
    """Check if user authentication is enabled"""
    return feature_flags.is_enabled('user_authentication', user_id)

def is_credit_system_enabled(user_id: Optional[str] = None) -> bool:
    """Check if credit system is enabled"""
    return feature_flags.is_enabled('credit_system', user_id)

def is_stripe_enabled(user_id: Optional[str] = None) -> bool:
    """Check if Stripe payments are enabled"""
    return feature_flags.is_enabled('stripe_payments', user_id)

def is_enhanced_rate_limiting_enabled(user_id: Optional[str] = None) -> bool:
    """Check if enhanced rate limiting is enabled"""
    return feature_flags.is_enabled('enhanced_rate_limiting', user_id)