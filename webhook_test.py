#!/usr/bin/env python3
"""Production-grade webhook testing and manual subscription creation"""

import stripe
import os
import json
from datetime import datetime, timedelta
from app import app, db
from models import User, Subscription, CreditBalance, CreditTransaction
from stripe_manager import StripeManager
from credit_manager import CreditManager

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

def test_webhook_configuration():
    """Test if webhooks are properly configured in Stripe"""
    try:
        # List webhook endpoints
        endpoints = stripe.WebhookEndpoint.list(limit=10)
        
        print("=== Stripe Webhook Configuration ===")
        if endpoints.data:
            for endpoint in endpoints.data:
                print(f"\nEndpoint: {endpoint.url}")
                print(f"Status: {endpoint.status}")
                print(f"Events: {', '.join(endpoint.enabled_events[:5])}...")
                print(f"Created: {datetime.fromtimestamp(endpoint.created)}")
        else:
            print("❌ No webhook endpoints configured in Stripe!")
            print("\nTo fix this, configure a webhook in Stripe Dashboard:")
            print("1. Go to https://dashboard.stripe.com/webhooks")
            print("2. Add endpoint: https://yourdomain.com/payment/webhook")
            print("3. Select events: checkout.session.completed, customer.subscription.*")
            
        return bool(endpoints.data)
        
    except Exception as e:
        print(f"❌ Error checking webhooks: {e}")
        return False

def find_customer_for_user(user_id: str):
    """Find Stripe customer ID for a user"""
    try:
        user = User.query.get(user_id)
        if not user or not user.email:
            print(f"❌ User {user_id} not found or has no email")
            return None
            
        # Search for customer by email
        customers = stripe.Customer.list(email=user.email, limit=1)
        
        if customers.data:
            customer = customers.data[0]
            print(f"✓ Found Stripe customer: {customer.id} ({customer.email})")
            return customer.id
        else:
            print(f"❌ No Stripe customer found for email: {user.email}")
            return None
            
    except Exception as e:
        print(f"❌ Error finding customer: {e}")
        return None

def check_stripe_subscriptions(customer_id: str):
    """Check Stripe subscriptions for a customer"""
    try:
        subscriptions = stripe.Subscription.list(customer=customer_id, limit=10)
        
        print(f"\n=== Stripe Subscriptions for {customer_id} ===")
        if subscriptions.data:
            for sub in subscriptions.data:
                print(f"\nSubscription ID: {sub.id}")
                print(f"Status: {sub.status}")
                print(f"Created: {datetime.fromtimestamp(sub.created)}")
                print(f"Current Period: {datetime.fromtimestamp(sub.current_period_start)} - {datetime.fromtimestamp(sub.current_period_end)}")
                
                # Get plan details
                if sub.items and sub.items.data:
                    item = sub.items.data[0]
                    if item.price:
                        print(f"Plan: ${item.price.unit_amount/100:.2f}/{item.price.recurring.interval}")
                        
            return subscriptions.data[0] if subscriptions.data else None
        else:
            print("❌ No subscriptions found in Stripe")
            return None
            
    except Exception as e:
        print(f"❌ Error checking subscriptions: {e}")
        return None

def sync_subscription_from_stripe(user_id: str, stripe_sub):
    """Sync a Stripe subscription to our database"""
    with app.app_context():
        try:
            # Check if subscription already exists
            existing = Subscription.query.filter_by(
                stripe_subscription_id=stripe_sub.id
            ).first()
            
            if existing:
                print(f"✓ Subscription already exists in database: {existing.id}")
                return existing
                
            # Create new subscription record
            subscription = Subscription()
            subscription.user_id = user_id
            subscription.stripe_subscription_id = stripe_sub.id
            subscription.stripe_customer_id = stripe_sub.customer
            subscription.status = stripe_sub.status
            subscription.current_period_start = datetime.fromtimestamp(stripe_sub.current_period_start)
            subscription.current_period_end = datetime.fromtimestamp(stripe_sub.current_period_end)
            
            # Determine plan type from price
            if stripe_sub.items and stripe_sub.items.data:
                price = stripe_sub.items.data[0].price
                if price.recurring.interval == 'week':
                    subscription.plan_type = 'weekly'
                elif price.recurring.interval == 'month':
                    subscription.plan_type = 'monthly'
                    
            db.session.add(subscription)
            db.session.commit()
            
            print(f"✅ Created subscription record: {subscription.id}")
            
            # Allocate credits
            credit_mgr = CreditManager()
            credit_mgr.allocate_subscription_credits(user_id, 100)
            
            print(f"✅ Allocated 100 credits to user {user_id}")
            
            return subscription
            
        except Exception as e:
            print(f"❌ Error syncing subscription: {e}")
            db.session.rollback()
            return None

def fix_user_subscription(user_id: str):
    """Complete production-grade fix for a user's subscription"""
    with app.app_context():
        print(f"\n=== Fixing Subscription for User {user_id} ===")
        
        # 1. Check webhook configuration
        webhooks_configured = test_webhook_configuration()
        
        # 2. Find Stripe customer
        customer_id = find_customer_for_user(user_id)
        if not customer_id:
            print("\n⚠️  Cannot proceed without Stripe customer ID")
            return False
            
        # 3. Check Stripe subscriptions
        stripe_sub = check_stripe_subscriptions(customer_id)
        if not stripe_sub:
            print("\n⚠️  No active subscription found in Stripe")
            return False
            
        # 4. Sync to database
        db_sub = sync_subscription_from_stripe(user_id, stripe_sub)
        if not db_sub:
            print("\n⚠️  Failed to sync subscription to database")
            return False
            
        # 5. Verify credits
        credit_balance = CreditBalance.query.filter_by(user_id=user_id).first()
        if credit_balance:
            print(f"\n✅ User now has {credit_balance.total_credits} total credits")
            print(f"   - Subscription credits: {credit_balance.subscription_credits}")
            print(f"   - Top-up credits: {credit_balance.topup_credits}")
        
        return True

if __name__ == "__main__":
    # Fix for specific user
    user_id = "39526636"
    
    success = fix_user_subscription(user_id)
    
    if success:
        print("\n✅ Production-grade fix completed successfully!")
        print("The user should now see their subscription and credits.")
    else:
        print("\n❌ Fix incomplete. Please address the issues above.")
        print("\nNext steps:")
        print("1. Ensure webhook endpoint is configured in Stripe Dashboard")
        print("2. Verify the user has a valid subscription in Stripe")
        print("3. Check application logs for webhook processing errors")