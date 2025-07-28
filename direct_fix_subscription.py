#!/usr/bin/env python3
"""Direct database fix for missing subscription and credits"""

import os
from datetime import datetime, timedelta
from app import app, db
from models import User, Subscription, CreditBalance, CreditTransaction
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def direct_fix_subscription(user_id: str):
    """Direct database fix without Stripe API calls"""
    with app.app_context():
        try:
            # Get user
            user = User.query.get(user_id)
            if not user:
                logger.error(f"User {user_id} not found")
                return False
                
            logger.info(f"Processing direct fix for user {user_id} ({user.email})")
            
            # Create subscription record directly
            # Based on user report: $5/week subscription active
            subscription = Subscription()
            subscription.user_id = user_id
            subscription.stripe_subscription_id = 'sub_1RpdpsDwyTs4lL4V6siZwpdy'  # From logs
            subscription.stripe_customer_id = 'cus_SlA9gcOtTxFyTY'  # From logs
            subscription.plan_type = 'weekly'
            subscription.status = 'active'
            
            # Set billing periods
            now = datetime.utcnow()
            subscription.current_period_start = now
            subscription.current_period_end = now + timedelta(days=7)
            
            db.session.add(subscription)
            logger.info("Created subscription record")
            
            # Create or update credit balance
            credit_balance = CreditBalance.query.filter_by(user_id=user_id).first()
            if not credit_balance:
                credit_balance = CreditBalance()
                credit_balance.user_id = user_id
                db.session.add(credit_balance)
                
            # Allocate 100 credits
            credit_balance.subscription_credits = 100
            credit_balance.subscription_credits_expiry = (now + timedelta(days=7)).date()
            
            # Create transaction record
            transaction = CreditTransaction()
            transaction.user_id = user_id
            transaction.transaction_type = 'subscription_allocation'
            transaction.credit_type = 'subscription'
            transaction.credits_amount = 100
            transaction.description = 'Weekly subscription credits allocated (manual fix)'
            transaction.stripe_payment_id = 'sub_1RpdpsDwyTs4lL4V6siZwpdy'
            
            db.session.add(transaction)
            db.session.commit()
            
            logger.info(f"✅ Successfully created subscription and allocated 100 credits")
            
            # Verify the fix
            user_sub = Subscription.query.filter_by(user_id=user_id, status='active').first()
            user_credits = CreditBalance.query.filter_by(user_id=user_id).first()
            
            if user_sub and user_credits:
                logger.info(f"✅ Verification successful:")
                logger.info(f"   - Subscription ID: {user_sub.id}")
                logger.info(f"   - Total credits: {user_credits.total_credits}")
                logger.info(f"   - Expires: {user_credits.subscription_credits_expiry}")
                return True
            else:
                logger.error("❌ Verification failed")
                return False
                
        except Exception as e:
            logger.error(f"Error in direct fix: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return False

if __name__ == "__main__":
    user_id = "39526636"
    
    print("=== Direct Database Fix ===")
    print(f"User ID: {user_id}")
    print("")
    
    success = direct_fix_subscription(user_id)
    
    if success:
        print("\n✅ PRODUCTION FIX COMPLETE")
        print("User now has:")
        print("- Active weekly subscription")
        print("- 100 credits allocated")
        print("- Ready to use the service")
    else:
        print("\n❌ FIX FAILED - Check error logs")