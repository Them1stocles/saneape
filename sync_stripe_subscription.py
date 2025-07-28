#!/usr/bin/env python3
"""Production-grade Stripe subscription synchronization"""

import stripe
import os
import logging
from datetime import datetime, timedelta
from app import app, db
from models import User, Subscription, CreditBalance, CreditTransaction
from credit_manager import CreditManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

class StripeSubscriptionSync:
    """Production-grade synchronization of Stripe subscriptions with local database"""
    
    def __init__(self):
        self.credit_manager = CreditManager()
    
    def sync_user_subscription(self, user_id: str) -> bool:
        """
        Complete synchronization of a user's Stripe subscription
        
        Args:
            user_id: The user ID to sync
            
        Returns:
            bool: True if sync successful, False otherwise
        """
        with app.app_context():
            try:
                # Get user
                user = User.query.get(user_id)
                if not user:
                    logger.error(f"User {user_id} not found")
                    return False
                
                logger.info(f"Starting subscription sync for user {user_id} ({user.email})")
                
                # Find Stripe customer
                customer_id = self._find_stripe_customer(user.email)
                if not customer_id:
                    logger.error(f"No Stripe customer found for {user.email}")
                    return False
                
                # Get active Stripe subscription
                stripe_sub = self._get_active_subscription(customer_id)
                if not stripe_sub:
                    logger.error(f"No active Stripe subscription found for customer {customer_id}")
                    return False
                
                # Sync to database
                success = self._sync_subscription_to_db(user_id, stripe_sub, customer_id)
                if not success:
                    logger.error("Failed to sync subscription to database")
                    return False
                
                # Allocate credits
                success = self._allocate_credits(user_id, stripe_sub)
                if not success:
                    logger.error("Failed to allocate credits")
                    return False
                
                logger.info(f"✅ Successfully synced subscription for user {user_id}")
                return True
                
            except Exception as e:
                logger.error(f"Error syncing subscription: {e}")
                db.session.rollback()
                return False
    
    def _find_stripe_customer(self, email: str) -> str:
        """Find Stripe customer ID by email"""
        try:
            customers = stripe.Customer.list(email=email, limit=1)
            if customers.data:
                customer = customers.data[0]
                logger.info(f"Found Stripe customer {customer.id} for {email}")
                return customer.id
            return None
        except Exception as e:
            logger.error(f"Error finding Stripe customer: {e}")
            return None
    
    def _get_active_subscription(self, customer_id: str):
        """Get active subscription for a customer"""
        try:
            subscriptions = stripe.Subscription.list(
                customer=customer_id,
                status='active',
                limit=1
            )
            
            if subscriptions.data:
                sub = subscriptions.data[0]
                logger.info(f"Found active subscription {sub.id}")
                return sub
            return None
        except Exception as e:
            logger.error(f"Error getting subscription: {e}")
            return None
    
    def _sync_subscription_to_db(self, user_id: str, stripe_sub, customer_id: str) -> bool:
        """Sync Stripe subscription to database"""
        try:
            # Check if subscription already exists
            existing = Subscription.query.filter_by(
                stripe_subscription_id=stripe_sub.id
            ).first()
            
            if existing:
                # Update existing subscription
                try:
                    existing.status = stripe_sub.status
                    existing.current_period_start = datetime.fromtimestamp(stripe_sub.current_period_start)
                    existing.current_period_end = datetime.fromtimestamp(stripe_sub.current_period_end)
                    existing.updated_at = datetime.utcnow()
                    logger.info(f"Updated existing subscription {existing.id}")
                except Exception as e:
                    logger.error(f"Error updating subscription attributes: {e}")
                    logger.error(f"Subscription attributes: {dir(existing)}")
                    raise
            else:
                # Create new subscription
                subscription = Subscription()
                subscription.user_id = user_id
                subscription.stripe_subscription_id = stripe_sub.id
                subscription.stripe_customer_id = customer_id
                subscription.status = stripe_sub.status
                subscription.current_period_start = datetime.fromtimestamp(stripe_sub.current_period_start)
                subscription.current_period_end = datetime.fromtimestamp(stripe_sub.current_period_end)
                
                # Determine plan type from interval
                if stripe_sub.items.data[0].price.recurring.interval == 'week':
                    subscription.plan_type = 'weekly'
                else:
                    subscription.plan_type = 'monthly'
                
                db.session.add(subscription)
                logger.info(f"Created new subscription record")
            
            db.session.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error syncing subscription to DB: {e}")
            db.session.rollback()
            return False
    
    def _allocate_credits(self, user_id: str, stripe_sub) -> bool:
        """Allocate credits for the subscription"""
        try:
            # Calculate expiry date (end of current period)
            expiry_date = datetime.fromtimestamp(stripe_sub.current_period_end).date()
            
            # Use CreditManager to allocate credits properly
            success = self.credit_manager.allocate_subscription_credits(
                user_id, 
                100,  # Both weekly and monthly get 100 credits
                expiry_date=expiry_date
            )
            
            if success:
                logger.info(f"Allocated 100 credits to user {user_id}, expires {expiry_date}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error allocating credits: {e}")
            return False

def main():
    """Main entry point"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python sync_stripe_subscription.py <user_id>")
        sys.exit(1)
    
    user_id = sys.argv[1]
    
    syncer = StripeSubscriptionSync()
    success = syncer.sync_user_subscription(user_id)
    
    if success:
        print(f"\n✅ Successfully synced subscription for user {user_id}")
        print("The user should now see their subscription and credits.")
    else:
        print(f"\n❌ Failed to sync subscription for user {user_id}")
        print("Check the logs above for error details.")
        
        # Provide helpful next steps
        print("\nTroubleshooting steps:")
        print("1. Verify the user has completed payment in Stripe")
        print("2. Check that STRIPE_SECRET_KEY environment variable is set")
        print("3. Ensure the user's email in our database matches their Stripe customer email")
        print("4. Configure webhook endpoint in Stripe Dashboard: https://yourdomain.com/payment/webhook")

if __name__ == "__main__":
    main()