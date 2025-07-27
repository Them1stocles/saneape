"""
Database models for SaneApe stock analysis platform.
Enhanced with user accounts, payment processing, and comprehensive monitoring.
"""

from app import db
from datetime import datetime, timedelta
from flask_login import UserMixin
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from sqlalchemy import Index, UniqueConstraint

class RateLimit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    request_count = db.Column(db.Integer, default=0, nullable=False)
    maximum_brain_count = db.Column(db.Integer, default=0, nullable=False)
    last_request = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    date_created = db.Column(db.Date, default=datetime.utcnow().date, nullable=False)

    def __repr__(self):
        return f'<RateLimit {self.ip_address}: {self.request_count}/{self.maximum_brain_count}>'

class StockAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=False)
    recommendation = db.Column(db.String(20), nullable=False)
    confidence = db.Column(db.String(10), nullable=False)
    analysis_data = db.Column(db.Text, nullable=False)
    maximum_brain = db.Column(db.Boolean, default=False, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        brain_mode = " (Max Brain)" if self.maximum_brain else ""
        return f'<StockAnalysis {self.ticker}: {self.recommendation}{brain_mode}>'

class SystemLimits(db.Model):
    """Global daily API tracking and spend limits"""
    id = db.Column(db.Integer, primary_key=True)
    daily_api_calls = db.Column(db.Integer, default=0, nullable=False)
    daily_cost_estimate = db.Column(db.Float, default=0.0, nullable=False)
    max_daily_cost = db.Column(db.Float, default=25.0, nullable=False)
    emergency_stop = db.Column(db.Boolean, default=False, nullable=False)
    date_created = db.Column(db.Date, default=datetime.utcnow().date, nullable=False, unique=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<SystemLimits {self.date_created}: {self.daily_api_calls} calls, ${self.daily_cost_estimate:.2f}>'

class AnalysisCache(db.Model):
    """6-hour cache for duplicate analysis prevention"""
    id = db.Column(db.Integer, primary_key=True)
    ticker_symbol = db.Column(db.String(10), nullable=False, index=True)
    maximum_brain = db.Column(db.Boolean, default=False, nullable=False)
    analysis_data = db.Column(db.Text, nullable=False)
    cache_expiry = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.cache_expiry:
            self.cache_expiry = datetime.utcnow() + timedelta(hours=6)

    @property
    def is_expired(self):
        return datetime.utcnow() > self.cache_expiry

    def __repr__(self):
        brain_mode = " (Max Brain)" if self.maximum_brain else ""
        return f'<AnalysisCache {self.ticker_symbol}{brain_mode}: expires {self.cache_expiry}>'

class SecurityLog(db.Model):
    """Suspicious activity tracking"""
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    event_count = db.Column(db.Integer, default=1, nullable=False)
    event_details = db.Column(db.Text)
    last_attempt = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    date_created = db.Column(db.Date, default=datetime.utcnow().date, nullable=False)

    def __repr__(self):
        return f'<SecurityLog {self.ip_address}: {self.event_type} x{self.event_count}>'


# =====================================
# USER ACCOUNTS & AUTHENTICATION MODELS
# =====================================

class User(UserMixin, db.Model):
    """Replit-authenticated users with subscription and credit management"""
    __tablename__ = 'users'
    
    id = db.Column(db.String, primary_key=True)  # Replit user ID
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    profile_image_url = db.Column(db.String(500), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    subscriptions = db.relationship('Subscription', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    credit_balance = db.relationship('CreditBalance', backref='user', uselist=False, cascade='all, delete-orphan')
    credit_transactions = db.relationship('CreditTransaction', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    oauth_tokens = db.relationship('OAuth', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_email', 'email'),
        Index('idx_user_created', 'created_at'),
    )
    
    def __repr__(self):
        return f'<User {self.id}: {self.email}>'
    
    @property
    def display_name(self):
        """Get user's display name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.email:
            return self.email.split('@')[0]
        else:
            return f"User {self.id}"
    
    def get_active_subscription(self):
        """Get user's active subscription"""
        return self.subscriptions.filter_by(status='active').first()
    
    def has_active_subscription(self):
        """Check if user has an active subscription"""
        return self.get_active_subscription() is not None


class OAuth(OAuthConsumerMixin, db.Model):
    """OAuth token storage for Replit authentication"""
    __tablename__ = 'oauth_tokens'
    
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    browser_session_key = db.Column(db.String(255), nullable=False)
    
    # Unique constraint for user + session + provider
    __table_args__ = (
        UniqueConstraint('user_id', 'browser_session_key', 'provider', 
                        name='uq_user_browser_session_provider'),
        Index('idx_oauth_user_provider', 'user_id', 'provider'),
    )


# =====================================
# SUBSCRIPTION & PAYMENT MODELS
# =====================================

class Subscription(db.Model):
    """User subscription tracking with Stripe integration"""
    __tablename__ = 'subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    
    # Stripe information
    stripe_subscription_id = db.Column(db.String(255), unique=True, nullable=True, index=True)
    stripe_customer_id = db.Column(db.String(255), nullable=True, index=True)
    
    # Subscription details
    plan_type = db.Column(db.String(20), nullable=False)  # 'monthly', 'weekly'
    status = db.Column(db.String(20), nullable=False, index=True)  # 'active', 'canceled', 'past_due', 'suspended'
    
    # Billing information
    current_period_start = db.Column(db.DateTime, nullable=True)
    current_period_end = db.Column(db.DateTime, nullable=True)
    cancel_at_period_end = db.Column(db.Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    canceled_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    payment_failures = db.relationship('PaymentFailure', backref='subscription', lazy='dynamic', cascade='all, delete-orphan')
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_subscription_user_status', 'user_id', 'status'),
        Index('idx_subscription_stripe', 'stripe_subscription_id'),
        Index('idx_subscription_period', 'current_period_end'),
    )
    
    def __repr__(self):
        return f'<Subscription {self.user_id}: {self.plan_type} ({self.status})>'
    
    @property
    def is_active(self):
        """Check if subscription is currently active"""
        return self.status == 'active'
    
    @property
    def credits_per_cycle(self):
        """Get credits granted per billing cycle"""
        return 100  # Both monthly and weekly plans get 100 credits
    
    def days_until_renewal(self):
        """Get days until next renewal"""
        if not self.current_period_end:
            return 0
        delta = self.current_period_end - datetime.utcnow()
        return max(0, delta.days)


class CreditBalance(db.Model):
    """User credit tracking with dual credit system"""
    __tablename__ = 'credit_balances'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # Dual credit system
    subscription_credits = db.Column(db.Integer, default=0, nullable=False)  # Expire monthly, no rollover
    topup_credits = db.Column(db.Integer, default=0, nullable=False)  # Never expire, unlimited rollover
    
    # Usage tracking
    credits_used_today = db.Column(db.Integer, default=0, nullable=False)
    credits_used_this_cycle = db.Column(db.Integer, default=0, nullable=False)
    
    # Reset tracking
    last_reset_date = db.Column(db.Date, default=datetime.utcnow().date, nullable=False)
    subscription_credits_expiry = db.Column(db.Date, nullable=True)  # End of current billing cycle
    
    # Timestamps
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_credit_balance_user', 'user_id'),
        Index('idx_credit_balance_expiry', 'subscription_credits_expiry'),
    )
    
    def __repr__(self):
        return f'<CreditBalance {self.user_id}: {self.total_credits} credits>'
    
    @property
    def total_credits(self):
        """Get total available credits"""
        return self.subscription_credits + self.topup_credits
    
    @property
    def subscription_credits_expired(self):
        """Check if subscription credits have expired"""
        if not self.subscription_credits_expiry:
            return False
        return datetime.utcnow().date() > self.subscription_credits_expiry
    
    def can_afford_analysis(self, is_brain=False):
        """Check if user can afford an analysis"""
        cost = 2 if is_brain else 1
        return self.total_credits >= cost
    
    def deduct_credits(self, is_brain=False):
        """Deduct credits for analysis (priority: top-up first)"""
        cost = 2 if is_brain else 1
        
        if not self.can_afford_analysis(is_brain):
            return False
        
        # Use top-up credits first
        if self.topup_credits >= cost:
            self.topup_credits -= cost
        else:
            # Use combination of top-up and subscription credits
            remaining_cost = cost - self.topup_credits
            self.topup_credits = 0
            self.subscription_credits -= remaining_cost
        
        self.credits_used_today += cost
        self.credits_used_this_cycle += cost
        self.updated_at = datetime.utcnow()
        
        return True


class CreditTransaction(db.Model):
    """Credit usage and purchase history"""
    __tablename__ = 'credit_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    
    # Transaction details
    transaction_type = db.Column(db.String(20), nullable=False, index=True)  
    # Types: 'subscription_grant', 'topup_purchase', 'usage', 'expiry', 'refund', 'bonus'
    credit_type = db.Column(db.String(15), nullable=False)  # 'subscription', 'topup'
    credits_amount = db.Column(db.Integer, nullable=False)  # Can be negative for usage
    
    # Context information
    analysis_type = db.Column(db.String(10), nullable=True)  # 'standard', 'brain'
    ticker_symbol = db.Column(db.String(10), nullable=True)
    description = db.Column(db.String(255), nullable=True)
    
    # Payment information
    stripe_payment_id = db.Column(db.String(255), nullable=True, index=True)
    amount_paid = db.Column(db.Float, nullable=True)  # USD amount for purchases
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_credit_transaction_user_created', 'user_id', 'created_at'),
        Index('idx_credit_transaction_type', 'transaction_type'),
        Index('idx_credit_transaction_stripe', 'stripe_payment_id'),
    )
    
    def __repr__(self):
        return f'<CreditTransaction {self.user_id}: {self.transaction_type} {self.credits_amount}>'


class PaymentFailure(db.Model):
    """Payment failure tracking and retry management"""
    __tablename__ = 'payment_failures'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), nullable=True)
    
    # Stripe information
    stripe_subscription_id = db.Column(db.String(255), nullable=False, index=True)
    stripe_invoice_id = db.Column(db.String(255), nullable=False, index=True)
    stripe_payment_intent_id = db.Column(db.String(255), nullable=True)
    
    # Failure details
    failure_reason = db.Column(db.String(100), nullable=False)  # 'insufficient_funds', 'expired_card', 'fraud', etc.
    failure_type = db.Column(db.String(20), nullable=False)  # 'soft_decline', 'hard_decline', 'authentication_required'
    failure_code = db.Column(db.String(50), nullable=True)  # Stripe decline code
    
    # Retry management
    retry_count = db.Column(db.Integer, default=0, nullable=False)
    max_retries = db.Column(db.Integer, default=3, nullable=False)
    next_retry_date = db.Column(db.DateTime, nullable=True)
    retry_schedule = db.Column(db.String(50), default='1d,3d,7d', nullable=False)  # Days between retries
    
    # Status tracking
    status = db.Column(db.String(20), nullable=False, default='pending_retry')  
    # Status: 'pending_retry', 'retrying', 'resolved', 'abandoned', 'requires_action'
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_payment_failure_user_status', 'user_id', 'status'),
        Index('idx_payment_failure_retry', 'next_retry_date', 'status'),
        Index('idx_payment_failure_stripe', 'stripe_subscription_id'),
    )
    
    def __repr__(self):
        return f'<PaymentFailure {self.user_id}: {self.failure_reason} (retry {self.retry_count}/{self.max_retries})>'
    
    @property
    def can_retry(self):
        """Check if payment failure can be retried"""
        return (self.retry_count < self.max_retries and 
                self.status in ['pending_retry', 'retrying'] and
                self.next_retry_date and 
                datetime.utcnow() >= self.next_retry_date)
    
    def schedule_next_retry(self):
        """Schedule the next retry attempt"""
        if self.retry_count >= self.max_retries:
            self.status = 'abandoned'
            return False
        
        retry_days = self.retry_schedule.split(',')
        if self.retry_count < len(retry_days):
            days_to_wait = int(retry_days[self.retry_count].replace('d', ''))
            self.next_retry_date = datetime.utcnow() + timedelta(days=days_to_wait)
            self.status = 'pending_retry'
            return True
        
        self.status = 'abandoned'
        return False


# =====================================
# ENHANCED RATE LIMITING FOR USERS
# =====================================

class UserRateLimit(db.Model):
    """User-based rate limiting for authenticated users"""
    __tablename__ = 'user_rate_limits'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # Daily limits
    requests_today = db.Column(db.Integer, default=0, nullable=False)
    brain_requests_today = db.Column(db.Integer, default=0, nullable=False)
    
    # Advanced rate limiting
    requests_this_hour = db.Column(db.Integer, default=0, nullable=False)
    last_request_time = db.Column(db.DateTime, nullable=True)
    burst_count = db.Column(db.Integer, default=0, nullable=False)  # Rapid requests in short time
    
    # Reset tracking
    last_daily_reset = db.Column(db.Date, default=datetime.utcnow().date, nullable=False)
    last_hourly_reset = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Temporary restrictions
    is_temporarily_blocked = db.Column(db.Boolean, default=False, nullable=False)
    block_until = db.Column(db.DateTime, nullable=True)
    block_reason = db.Column(db.String(100), nullable=True)
    
    # Timestamps
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_rate_limit_user', 'user_id'),
        Index('idx_user_rate_limit_block', 'is_temporarily_blocked', 'block_until'),
    )
    
    def __repr__(self):
        return f'<UserRateLimit {self.user_id}: {self.requests_today}/{self.brain_requests_today}>'
    
    @property
    def is_blocked(self):
        """Check if user is currently blocked"""
        if not self.is_temporarily_blocked:
            return False
        if self.block_until and datetime.utcnow() > self.block_until:
            return False
        return True
    
    def should_reset_daily(self):
        """Check if daily counters should be reset"""
        return self.last_daily_reset < datetime.utcnow().date()
    
    def should_reset_hourly(self):
        """Check if hourly counters should be reset"""
        return (datetime.utcnow() - self.last_hourly_reset).total_seconds() > 3600
    
    def detect_burst_activity(self):
        """Detect if user is making burst requests"""
        if not self.last_request_time:
            return False
        
        time_since_last = (datetime.utcnow() - self.last_request_time).total_seconds()
        
        # If less than 10 seconds between requests, increment burst count
        if time_since_last < 10:
            self.burst_count += 1
        else:
            self.burst_count = 0
        
        # Block if more than 5 burst requests
        return self.burst_count > 5
