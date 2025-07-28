#!/usr/bin/env python3
"""Verify user subscription and credits are working"""

from app import app, db
from models import User, Subscription, CreditBalance
from feature_flags import feature_flags

with app.app_context():
    user_id = "39526636"
    
    print("=== VERIFICATION REPORT ===")
    print()
    
    # Check feature flags
    print("Feature Flag Status:")
    print(f"- stripe_payments: {feature_flags.is_enabled('stripe_payments')}")
    print(f"- subscription_management: {feature_flags.is_enabled('subscription_management')}")
    print(f"- credit_display: {feature_flags.is_enabled('credit_display')}")
    print(f"- dual_credit_system: {feature_flags.is_enabled('dual_credit_system')}")
    print()
    
    # Check user
    user = User.query.get(user_id)
    if user:
        print(f"User: {user.email}")
        
        # Check subscription
        sub = Subscription.query.filter_by(user_id=user_id, status='active').first()
        if sub:
            print(f"✅ Active subscription: {sub.plan_type} (expires {sub.current_period_end})")
        else:
            print("❌ No active subscription found")
            
        # Check credits
        credits = CreditBalance.query.filter_by(user_id=user_id).first()
        if credits:
            print(f"✅ Credits: {credits.total_credits} total")
            print(f"   - Subscription: {credits.subscription_credits} (expires {credits.subscription_credits_expiry})")
            print(f"   - Top-up: {credits.topup_credits}")
        else:
            print("❌ No credit balance found")
    else:
        print("❌ User not found")