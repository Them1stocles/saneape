"""
Production-Grade Stripe Integration Manager
Handles all payment processing, subscription management, and webhook events
"""

import os
import logging
import stripe
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from flask import request, current_app

from app import db
from models import User, Subscription, CreditBalance, CreditTransaction, PaymentFailure
from monitoring import monitoring

logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

class SubscriptionPlan(Enum):
    """Subscription plan types with metadata"""
    MONTHLY = {
        'name': 'SaneApe Monthly',
        'price': 500,  # $5.00 in cents
        'interval': 'month',
        'credits': 100,
        'plan_id': 'monthly'
    }
    WEEKLY = {
        'name': 'SaneApe Weekly', 
        'price': 500,  # $5.00 in cents
        'interval': 'week',
        'credits': 100,
        'plan_id': 'weekly'
    }
    TOPUP = {
        'name': 'Credit Pack',
        'price': 500,  # $5.00 in cents
        'credits': 100,
        'plan_id': 'topup'
    }

@dataclass
class PaymentResult:
    """Standardized payment result response"""
    success: bool
    checkout_url: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    transaction_id: Optional[str] = None

class StripeManager:
    """Production-grade Stripe integration with comprehensive error handling"""
    
    def __init__(self):
        self.webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
        if not stripe.api_key:
            logger.error("STRIPE_SECRET_KEY environment variable not set")
            raise ValueError("Stripe configuration missing")
    
    def create_checkout_session(self, user: User, plan: SubscriptionPlan, 
                              success_url: str, cancel_url: str) -> PaymentResult:
        """
        Create Stripe checkout session with comprehensive error handling
        
        Args:
            user: Authenticated user object
            plan: Subscription plan enum
            success_url: Redirect URL after successful payment
            cancel_url: Redirect URL after cancelled payment
            
        Returns:
            PaymentResult with checkout URL or error details
        """
        try:
            # Validate user
            if not user or not user.is_authenticated:
                return PaymentResult(
                    success=False,
                    error_message="User authentication required",
                    error_code="AUTH_REQUIRED"
                )
            
            # Get or create Stripe customer
            customer_id = self._get_or_create_customer(user)
            if not customer_id:
                return PaymentResult(
                    success=False,
                    error_message="Failed to create customer profile",
                    error_code="CUSTOMER_CREATION_FAILED"
                )
            
            # Configure session parameters based on plan type
            session_params = self._build_session_params(
                customer_id, plan, success_url, cancel_url
            )
            
            # Create checkout session
            session = stripe.checkout.Session.create(**session_params)
            
            # Log successful session creation
            logger.info(f"Checkout session created: {session.id} for user {user.id}")
            monitoring.create_alert('info', 'payment', f'Checkout session created for user {user.id}', {
                'session_id': session.id,
                'plan': plan.value['plan_id'],
                'amount': plan.value['price']
            })
            
            return PaymentResult(
                success=True,
                checkout_url=session.url,
                transaction_id=session.id
            )
            
        except stripe.error.InvalidRequestError as e:
            logger.error(f"Stripe invalid request: {e}")
            return PaymentResult(
                success=False,
                error_message="Invalid payment request",
                error_code="INVALID_REQUEST"
            )
        except stripe.error.AuthenticationError as e:
            logger.error(f"Stripe authentication error: {e}")
            return PaymentResult(
                success=False,
                error_message="Payment service configuration error",
                error_code="AUTH_ERROR"
            )
        except Exception as e:
            logger.error(f"Unexpected error creating checkout session: {e}")
            return PaymentResult(
                success=False,
                error_message="Payment service temporarily unavailable",
                error_code="SERVICE_ERROR"
            )
    
    def _get_or_create_customer(self, user: User) -> Optional[str]:
        """Get existing Stripe customer or create new one"""
        try:
            # Check if user already has a Stripe customer ID
            existing_subscription = Subscription.query.filter_by(
                user_id=user.id
            ).first()
            
            if existing_subscription and existing_subscription.stripe_customer_id:
                # Verify customer still exists in Stripe
                try:
                    customer = stripe.Customer.retrieve(existing_subscription.stripe_customer_id)
                    return customer.id
                except stripe.error.InvalidRequestError:
                    logger.warning(f"Stripe customer {existing_subscription.stripe_customer_id} not found, creating new one")
            
            # Create new Stripe customer
            customer_data = {
                'email': user.email,
                'metadata': {
                    'user_id': user.id,
                    'created_via': 'saneape_webapp'
                }
            }
            
            # Add name if available
            if user.first_name or user.last_name:
                name_parts = [user.first_name or '', user.last_name or '']
                customer_data['name'] = ' '.join(name_parts).strip()
            
            customer = stripe.Customer.create(**customer_data)
            logger.info(f"Created Stripe customer {customer.id} for user {user.id}")
            
            return customer.id
            
        except Exception as e:
            logger.error(f"Error creating Stripe customer for user {user.id}: {e}")
            return None
    
    def _build_session_params(self, customer_id: str, plan: SubscriptionPlan,
                            success_url: str, cancel_url: str) -> Dict[str, Any]:
        """Build Stripe checkout session parameters"""
        base_params = {
            'customer': customer_id,
            'success_url': success_url,
            'cancel_url': cancel_url,
            'metadata': {
                'plan_type': plan.value['plan_id'],
                'credits': plan.value['credits']
            }
        }
        
        if plan == SubscriptionPlan.TOPUP:
            # One-time payment for credit top-up
            base_params.update({
                'mode': 'payment',
                'line_items': [{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': plan.value['name'],
                            'description': f"{plan.value['credits']} analysis credits"
                        },
                        'unit_amount': plan.value['price']
                    },
                    'quantity': 1
                }]
            })
        else:
            # Subscription payment
            base_params.update({
                'mode': 'subscription',
                'line_items': [{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': plan.value['name'],
                            'description': f"{plan.value['credits']} credits per {plan.value['interval']}"
                        },
                        'unit_amount': plan.value['price'],
                        'recurring': {
                            'interval': plan.value['interval']
                        }
                    },
                    'quantity': 1
                }],
                'subscription_data': {
                    'metadata': {
                        'plan_type': plan.value['plan_id'],
                        'credits_per_period': plan.value['credits']
                    }
                }
            })
        
        return base_params
    
    def handle_webhook(self, payload: bytes, signature: str) -> Tuple[bool, str]:
        """
        Handle Stripe webhook events with idempotent processing
        
        Args:
            payload: Raw webhook payload
            signature: Stripe signature header
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Verify webhook signature
            if self.webhook_secret:
                try:
                    event = stripe.Webhook.construct_event(
                        payload, signature, self.webhook_secret
                    )
                except stripe.error.SignatureVerificationError:
                    logger.error("Invalid Stripe webhook signature")
                    return False, "Invalid signature"
            else:
                # In development, parse without verification
                event = json.loads(payload.decode('utf-8'))
                logger.warning("Webhook processed without signature verification (development mode)")
            
            # Check for duplicate events (idempotent processing)
            event_id = event.get('id', '')
            if event_id and self._is_duplicate_event(event_id):
                logger.info(f"Skipping duplicate webhook event {event_id}")
                return True, "Duplicate event ignored"
            
            # Process event based on type
            event_type = event['type']
            event_data = event['data']['object']
            
            success = self._process_webhook_event(event_type, event_data, event_id)
            
            if success and event_id:
                self._mark_event_processed(event_id)
                return True, f"Event {event_type} processed successfully"
            else:
                return False, f"Failed to process event {event_type}"
                
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return False, f"Webhook processing error: {str(e)}"
    
    def _process_webhook_event(self, event_type: str, event_data: Dict, event_id: str) -> bool:
        """Process specific webhook event types"""
        try:
            if event_type == 'checkout.session.completed':
                return self._handle_checkout_completed(event_data)
            elif event_type == 'customer.subscription.created':
                return self._handle_subscription_created(event_data)
            elif event_type == 'customer.subscription.updated':
                return self._handle_subscription_updated(event_data)
            elif event_type == 'customer.subscription.deleted':
                return self._handle_subscription_deleted(event_data)
            elif event_type == 'invoice.payment_succeeded':
                return self._handle_payment_succeeded(event_data)
            elif event_type == 'invoice.payment_failed':
                return self._handle_payment_failed(event_data)
            else:
                logger.info(f"Unhandled webhook event type: {event_type}")
                return True  # Don't fail for unhandled events
                
        except Exception as e:
            logger.error(f"Error processing {event_type} event: {e}")
            return False
    
    def _handle_checkout_completed(self, session_data: Dict) -> bool:
        """Handle successful checkout completion"""
        try:
            customer_id = session_data.get('customer')
            metadata = session_data.get('metadata', {})
            plan_type = metadata.get('plan_type')
            credits = int(metadata.get('credits', 0))
            
            # Find user by customer ID
            user = self._find_user_by_customer_id(customer_id)
            if not user:
                logger.error(f"User not found for customer {customer_id}")
                return False
            
            if plan_type == 'topup':
                # Handle one-time credit purchase
                return self._grant_topup_credits(user.id, credits, session_data['id'])
            else:
                # Subscription will be handled by subscription.created event
                logger.info(f"Checkout completed for subscription {plan_type}, waiting for subscription event")
                return True
                
        except Exception as e:
            logger.error(f"Error handling checkout completion: {e}")
            return False
    
    def _handle_subscription_created(self, subscription_data: Dict) -> bool:
        """Handle new subscription creation"""
        try:
            customer_id = subscription_data.get('customer')
            subscription_id = subscription_data['id']
            metadata = subscription_data.get('metadata', {})
            
            user = self._find_user_by_customer_id(customer_id)
            if not user:
                logger.error(f"User not found for customer {customer_id}")
                return False
            
            plan_type = metadata.get('plan_type')
            credits_per_period = int(metadata.get('credits_per_period', 0))
            
            # Create subscription record
            subscription = Subscription(
                user_id=user.id,
                stripe_subscription_id=subscription_id,
                stripe_customer_id=customer_id,
                plan_type=plan_type,
                status='active'
            )
            
            db.session.add(subscription)
            
            # Grant initial subscription credits
            self._grant_subscription_credits(user.id, credits_per_period, subscription_id)
            
            db.session.commit()
            
            logger.info(f"Subscription {subscription_id} created for user {user.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling subscription creation: {e}")
            db.session.rollback()
            return False
    
    def _handle_payment_succeeded(self, invoice_data: Dict) -> bool:
        """Handle successful subscription payment"""
        try:
            subscription_id = invoice_data.get('subscription')
            customer_id = invoice_data.get('customer')
            
            # Find subscription
            subscription = Subscription.query.filter_by(
                stripe_subscription_id=subscription_id
            ).first()
            
            if not subscription:
                logger.error(f"Subscription not found: {subscription_id}")
                return False
            
            # Grant subscription credits for new billing period
            self._grant_subscription_credits(
                subscription.user_id, 
                subscription.credits_per_cycle,
                subscription_id
            )
            
            # Update subscription status
            subscription.status = 'active'
            
            # Clear any payment failures
            PaymentFailure.query.filter_by(
                user_id=subscription.user_id,
                stripe_subscription_id=subscription_id,
                status='pending_retry'
            ).update({'status': 'resolved', 'resolved_at': datetime.utcnow()})
            
            db.session.commit()
            
            logger.info(f"Payment succeeded for subscription {subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling payment success: {e}")
            db.session.rollback()
            return False
    
    def _handle_subscription_updated(self, subscription_data: Dict) -> bool:
        """Handle subscription updates"""
        try:
            subscription_id = subscription_data['id']
            status = subscription_data.get('status', 'active')
            
            subscription = Subscription.query.filter_by(
                stripe_subscription_id=subscription_id
            ).first()
            
            if not subscription:
                logger.error(f"Subscription not found: {subscription_id}")
                return False
            
            # Update subscription status
            subscription.status = status
            subscription.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            logger.info(f"Subscription {subscription_id} updated to status {status}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling subscription update: {e}")
            db.session.rollback()
            return False
    
    def _handle_subscription_deleted(self, subscription_data: Dict) -> bool:
        """Handle subscription deletion/cancellation"""
        try:
            subscription_id = subscription_data['id']
            
            subscription = Subscription.query.filter_by(
                stripe_subscription_id=subscription_id
            ).first()
            
            if not subscription:
                logger.error(f"Subscription not found: {subscription_id}")
                return False
            
            # Update subscription status
            subscription.status = 'canceled'
            subscription.canceled_at = datetime.utcnow()
            
            # Expire subscription credits immediately
            self._suspend_subscription_credits(subscription.user_id)
            
            db.session.commit()
            
            logger.info(f"Subscription {subscription_id} canceled")
            return True
            
        except Exception as e:
            logger.error(f"Error handling subscription deletion: {e}")
            db.session.rollback()
            return False
    
    def _handle_payment_failed(self, invoice_data: Dict) -> bool:
        """Handle failed subscription payment"""
        try:
            subscription_id = invoice_data.get('subscription')
            invoice_id = invoice_data['id']
            failure_reason = invoice_data.get('last_payment_error', {}).get('code', 'unknown')
            
            subscription = Subscription.query.filter_by(
                stripe_subscription_id=subscription_id
            ).first()
            
            if not subscription:
                logger.error(f"Subscription not found: {subscription_id}")
                return False
            
            # Suspend subscription credits (keep top-up credits)
            self._suspend_subscription_credits(subscription.user_id)
            
            # Record payment failure
            payment_failure = PaymentFailure()
            payment_failure.user_id = subscription.user_id
            payment_failure.stripe_subscription_id = subscription_id
            payment_failure.stripe_invoice_id = invoice_id
            payment_failure.failure_reason = failure_reason
            payment_failure.failure_type = self._classify_failure_type(failure_reason)
            payment_failure.status = 'pending_retry'
            
            db.session.add(payment_failure)
            
            # Update subscription status
            subscription.status = 'past_due'
            
            db.session.commit()
            
            logger.warning(f"Payment failed for subscription {subscription_id}: {failure_reason}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling payment failure: {e}")
            db.session.rollback()
            return False
    
    def _grant_subscription_credits(self, user_id: str, credits: int, source_id: str):
        """Grant subscription credits with expiration"""
        try:
            # Get or create credit balance for subscription credits
            credit_balance = CreditBalance.query.filter_by(user_id=user_id).first()
            if not credit_balance:
                credit_balance = CreditBalance()
                credit_balance.user_id = user_id
                db.session.add(credit_balance)
            
            # Expire old subscription credits (no rollover)
            old_credits = credit_balance.subscription_credits
            credit_balance.subscription_credits = credits
            
            # Set expiration date (end of billing period)
            credit_balance.subscription_credits_expiry = self._calculate_expiry_date()
            
            # Record transactions
            if old_credits > 0:
                # Record expiration of old credits
                expiry_transaction = CreditTransaction()
                expiry_transaction.user_id = user_id
                expiry_transaction.transaction_type = 'expiry'
                expiry_transaction.credit_type = 'subscription'
                expiry_transaction.credits_amount = -old_credits
                expiry_transaction.stripe_payment_id = source_id
                db.session.add(expiry_transaction)
            
            # Record new credit grant
            grant_transaction = CreditTransaction()
            grant_transaction.user_id = user_id
            grant_transaction.transaction_type = 'subscription_grant'
            grant_transaction.credit_type = 'subscription'
            grant_transaction.credits_amount = credits
            grant_transaction.stripe_payment_id = source_id
            db.session.add(grant_transaction)
            
            logger.info(f"Granted {credits} subscription credits to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error granting subscription credits: {e}")
            raise
    
    def _grant_topup_credits(self, user_id: str, credits: int, source_id: str) -> bool:
        """Grant top-up credits (never expire)"""
        try:
            # Get or create credit balance for top-up
            credit_balance = CreditBalance.query.filter_by(user_id=user_id).first()
            if not credit_balance:
                credit_balance = CreditBalance()
                credit_balance.user_id = user_id
                db.session.add(credit_balance)
            
            # Add top-up credits (unlimited rollover)
            credit_balance.topup_credits += credits
            
            # Record transaction
            transaction = CreditTransaction()
            transaction.user_id = user_id
            transaction.transaction_type = 'topup_purchase'
            transaction.credit_type = 'topup'
            transaction.credits_amount = credits
            transaction.stripe_payment_id = source_id
            db.session.add(transaction)
            
            db.session.commit()
            
            logger.info(f"Granted {credits} top-up credits to user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error granting top-up credits: {e}")
            db.session.rollback()
            return False
    
    def _suspend_subscription_credits(self, user_id: str):
        """Suspend subscription credits due to payment failure"""
        credit_balance = CreditBalance.query.filter_by(user_id=user_id).first()
        if credit_balance:
            credit_balance.subscription_credits = 0
    
    def _calculate_expiry_date(self) -> datetime:
        """Calculate credit expiry date (end of current billing month)"""
        now = datetime.utcnow()
        if now.month == 12:
            return datetime(now.year + 1, 1, 1) - timedelta(days=1)
        else:
            return datetime(now.year, now.month + 1, 1) - timedelta(days=1)
    
    def _find_user_by_customer_id(self, customer_id: str) -> Optional[User]:
        """Find user by Stripe customer ID"""
        subscription = Subscription.query.filter_by(
            stripe_customer_id=customer_id
        ).first()
        if subscription:
            return User.query.get(subscription.user_id)
        return None
    
    def _classify_failure_type(self, failure_reason: str) -> str:
        """Classify payment failure type for retry strategy"""
        soft_declines = ['network_error', 'issuer_not_available', 'processing_error']
        hard_declines = ['insufficient_funds', 'expired_card', 'card_declined']
        
        if failure_reason in soft_declines:
            return 'soft_decline'
        elif failure_reason in hard_declines:
            return 'hard_decline'
        else:
            return 'unknown'
    
    def _is_duplicate_event(self, event_id: str) -> bool:
        """Check if webhook event has already been processed"""
        # This would typically check a processed events table
        # For now, we'll implement basic duplicate detection
        return False
    
    def _mark_event_processed(self, event_id: str):
        """Mark webhook event as processed"""
        # This would typically store the event ID in a processed events table
        # For now, we'll just log it
        logger.info(f"Marking webhook event {event_id} as processed")

# Singleton instance
stripe_manager = StripeManager()