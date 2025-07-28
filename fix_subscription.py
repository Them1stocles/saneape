#!/usr/bin/env python3
"""Emergency fix to allocate credits for users who paid but didn't receive credits due to webhook issues"""

from app import app, db
from models import User, Subscription, CreditBalance, CreditTransaction
from credit_manager import CreditManager
from datetime import datetime, timedelta
import sys

def fix_user_subscription(user_id: str, plan_type: str = 'weekly'):
    """Manually create subscription and allocate credits for a user"""
    with app.app_context():
        try:
            # Find user
            user = User.query.get(user_id)
            if not user:
                print(f"❌ User {user_id} not found")
                return False
            
            print(f"✓ Found user: {user.email}")
            
            # Check if subscription already exists
            existing_sub = Subscription.query.filter_by(
                user_id=user_id,
                status='active'
            ).first()
            
            if existing_sub:
                print(f"⚠️  User already has active subscription: {existing_sub.stripe_subscription_id}")
            else:
                # Create subscription record
                subscription = Subscription()
                subscription.user_id = user_id
                subscription.stripe_subscription_id = f"manual_fix_{datetime.utcnow().timestamp()}"
                subscription.stripe_customer_id = f"cus_manual_{user_id}"
                subscription.plan_type = plan_type
                subscription.status = 'active'
                # credits_per_cycle is a property, not a field
                subscription.current_period_start = datetime.utcnow()
                subscription.current_period_end = datetime.utcnow() + timedelta(days=7 if plan_type == 'weekly' else 30)
                
                db.session.add(subscription)
                print(f"✓ Created {plan_type} subscription")
            
            # Get or create credit balance
            credit_balance = CreditBalance.query.filter_by(user_id=user_id).first()
            if not credit_balance:
                credit_balance = CreditBalance()
                credit_balance.user_id = user_id
                db.session.add(credit_balance)
                print("✓ Created credit balance")
            
            # Allocate credits
            old_credits = credit_balance.subscription_credits
            credit_balance.subscription_credits = 100
            credit_balance.subscription_credits_expiry = datetime.utcnow() + timedelta(days=7 if plan_type == 'weekly' else 30)
            
            # Create transaction record
            transaction = CreditTransaction()
            transaction.user_id = user_id
            transaction.transaction_type = 'subscription_allocation'
            transaction.credit_type = 'subscription'
            transaction.credits_amount = 100
            transaction.description = f'Manual fix: {plan_type} subscription credits allocated'
            transaction.stripe_reference = 'manual_fix'
            
            db.session.add(transaction)
            db.session.commit()
            
            print(f"✅ Successfully allocated 100 credits to user {user_id}")
            print(f"   Previous credits: {old_credits}")
            print(f"   New credits: 100")
            print(f"   Expires: {credit_balance.subscription_credits_expiry}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    # Fix for the specific user who reported the issue
    user_id = "39526636"  # jtrevorchapman
    plan_type = "weekly"  # Based on the $5/week shown in Stripe
    
    print(f"Fixing subscription for user {user_id}...")
    success = fix_user_subscription(user_id, plan_type)
    
    if success:
        print("\n✅ Fix completed! User should now see their credits and active subscription.")
    else:
        print("\n❌ Fix failed. Please check the error messages above.")