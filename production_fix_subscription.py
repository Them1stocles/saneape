#!/usr/bin/env python3
"""Production-grade fix for missing subscription and credits"""

import stripe
import os
from datetime import datetime, timedelta
from app import app, db
from models import User, Subscription, CreditBalance, CreditTransaction
from credit_manager import CreditManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

def fix_subscription_and_credits(user_id: str):
    """Production fix for user who paid but didn't receive subscription/credits"""
    with app.app_context():
        try:
            # Get user
            user = User.query.get(user_id)
            if not user:
                logger.error(f"User {user_id} not found")
                return False
                
            logger.info(f"Processing fix for user {user_id} ({user.email})")
            
            # Find Stripe customer
            customers = stripe.Customer.list(email=user.email, limit=1)
            if not customers.data:
                logger.error(f"No Stripe customer found for {user.email}")
                return False
                
            customer = customers.data[0]
            logger.info(f"Found Stripe customer: {customer.id}")
            
            # Get active subscription from Stripe
            subscriptions = stripe.Subscription.list(
                customer=customer.id,
                status='active',
                limit=1
            )
            
            if not subscriptions.data:
                logger.error("No active subscription found in Stripe")
                return False
                
            stripe_sub = subscriptions.data[0]
            logger.info(f"Found active subscription: {stripe_sub.id}")
            
            # Determine plan type
            plan_type = 'monthly'
            try:
                if hasattr(stripe_sub, 'items') and stripe_sub.items and stripe_sub.items.get('data'):
                    first_item = stripe_sub.items['data'][0]
                    if 'price' in first_item and 'recurring' in first_item['price']:
                        interval = first_item['price']['recurring'].get('interval')
                        if interval == 'week':
                            plan_type = 'weekly'
            except Exception as e:
                logger.warning(f"Could not determine plan type from Stripe data: {e}")
                # Default to weekly based on user's report
                plan_type = 'weekly'
                
            # Create subscription record in database
            subscription = Subscription()
            subscription.user_id = user_id
            subscription.stripe_subscription_id = stripe_sub.id
            subscription.stripe_customer_id = customer.id
            subscription.plan_type = plan_type
            subscription.status = 'active'
            subscription.current_period_start = datetime.fromtimestamp(stripe_sub.current_period_start)
            subscription.current_period_end = datetime.fromtimestamp(stripe_sub.current_period_end)
            
            db.session.add(subscription)
            logger.info("Created subscription record")
            
            # Allocate credits using CreditManager
            credit_manager = CreditManager()
            expiry_date = datetime.fromtimestamp(stripe_sub.current_period_end).date()
            
            # Create or get credit balance
            credit_balance = CreditBalance.query.filter_by(user_id=user_id).first()
            if not credit_balance:
                credit_balance = CreditBalance()
                credit_balance.user_id = user_id
                db.session.add(credit_balance)
                
            # Set subscription credits
            credit_balance.subscription_credits = 100
            credit_balance.subscription_credits_expiry = expiry_date
            
            # Create transaction record
            transaction = CreditTransaction()
            transaction.user_id = user_id
            transaction.transaction_type = 'subscription_allocation'
            transaction.credit_type = 'subscription'
            transaction.credits_amount = 100
            transaction.description = f'{plan_type.title()} subscription credits allocated'
            transaction.stripe_payment_id = stripe_sub.id
            
            db.session.add(transaction)
            db.session.commit()
            
            logger.info(f"✅ Successfully allocated 100 credits to user {user_id}")
            logger.info(f"✅ Subscription expires: {expiry_date}")
            
            # Verify the fix
            user_sub = User.query.get(user_id).get_active_subscription()
            user_credits = CreditBalance.query.filter_by(user_id=user_id).first()
            
            if user_sub and user_credits:
                logger.info(f"✅ Verification successful:")
                logger.info(f"   - Active subscription: {user_sub.stripe_subscription_id}")
                logger.info(f"   - Total credits: {user_credits.total_credits}")
                logger.info(f"   - Subscription credits: {user_credits.subscription_credits}")
                return True
            else:
                logger.error("❌ Verification failed")
                return False
                
        except Exception as e:
            logger.error(f"Error fixing subscription: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    user_id = "39526636"
    
    print("=== Production Fix for Missing Subscription ===")
    print(f"User ID: {user_id}")
    print("")
    
    success = fix_subscription_and_credits(user_id)
    
    if success:
        print("\n✅ FIX COMPLETE - User now has:")
        print("   - Active subscription in database")
        print("   - 100 credits allocated")
        print("   - Ready to use the service")
    else:
        print("\n❌ FIX FAILED - Check error logs above")