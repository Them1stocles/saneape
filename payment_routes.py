"""
Production-Grade Payment Routes for Stripe Integration
Handles subscription checkout, webhooks, and payment management
"""

import logging
from flask import Blueprint, request, jsonify, redirect, url_for, render_template, flash
from flask_login import login_required, current_user

from app import db
from stripe_manager import stripe_manager, SubscriptionPlan, PaymentResult
from models import User, Subscription, CreditBalance
from feature_flags import feature_flags
from monitoring import monitoring, AlertSeverity

logger = logging.getLogger(__name__)

# Create payment blueprint
payment_bp = Blueprint('payment', __name__, url_prefix='/payment')

@payment_bp.route('/subscribe/<plan_type>')
@login_required
def create_subscription(plan_type):
    """Create Stripe checkout session for subscription"""
    try:
        # Validate plan type
        plan_map = {
            'monthly': SubscriptionPlan.MONTHLY,
            'weekly': SubscriptionPlan.WEEKLY,
            'topup': SubscriptionPlan.TOPUP
        }
        
        if plan_type not in plan_map:
            flash('Invalid subscription plan selected', 'error')
            return redirect(url_for('subscription_plans'))
        
        plan = plan_map[plan_type]
        
        # Check if user already has active subscription for subscription plans
        if plan_type != 'topup':
            active_subscription = current_user.get_active_subscription()
            if active_subscription:
                flash(f'You already have an active {active_subscription.plan_type} subscription', 'warning')
                return redirect(url_for('account_dashboard'))
        
        # Build success and cancel URLs
        success_url = url_for('payment.payment_success', _external=True) + f'?session_id={{CHECKOUT_SESSION_ID}}'
        cancel_url = url_for('subscription_plans', _external=True)
        
        # Validate current_user is authenticated
        if not current_user or not hasattr(current_user, 'id'):
            flash('Authentication required', 'error')
            return redirect(url_for('index'))
        
        # Create checkout session with type casting for current_user
        user = User.query.get(current_user.id) if current_user.is_authenticated else None
        if not user:
            flash('Authentication error', 'error')
            return redirect(url_for('index'))
            
        result = stripe_manager.create_checkout_session(
            user=user,
            plan=plan,
            success_url=success_url,
            cancel_url=cancel_url
        )
        
        if result.success and result.checkout_url:
            logger.info(f"Redirecting user {current_user.id} to Stripe checkout for {plan_type}")
            monitoring.create_alert(AlertSeverity.INFO, 'payment', f'User initiated {plan_type} checkout', {
                'user_id': current_user.id,
                'plan': plan_type,
                'session_id': result.transaction_id
            })
            return redirect(result.checkout_url)
        else:
            logger.error(f"Failed to create checkout session: {result.error_message}")
            flash(f'Payment setup failed: {result.error_message}', 'error')
            return redirect(url_for('subscription_plans'))
            
    except Exception as e:
        logger.error(f"Error in create_subscription: {e}")
        flash('Payment service temporarily unavailable. Please try again later.', 'error')
        return redirect(url_for('subscription_plans'))

@payment_bp.route('/success')
@login_required
def payment_success():
    """Handle successful payment completion"""
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            flash('Payment session not found', 'error')
            return redirect(url_for('subscription_plans'))
        
        # Log successful payment
        logger.info(f"Payment success for user {current_user.id}, session {session_id}")
        monitoring.create_alert(AlertSeverity.INFO, 'payment', f'Payment completed successfully', {
            'user_id': current_user.id,
            'session_id': session_id
        })
        
        # Refresh user data to get updated subscription/credits
        db.session.refresh(current_user)
        
        flash('Payment successful! Your subscription is now active.', 'success')
        return redirect(url_for('account_dashboard'))
        
    except Exception as e:
        logger.error(f"Error in payment_success: {e}")
        flash('Payment processing error. Please contact support if issues persist.', 'error')
        return redirect(url_for('account_dashboard'))

@payment_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    try:
        payload = request.get_data()
        signature = request.headers.get('Stripe-Signature', '')
        
        if not payload:
            logger.error("Empty webhook payload received")
            return jsonify({'error': 'Empty payload'}), 400
        
        # Process webhook with Stripe manager
        success, message = stripe_manager.handle_webhook(payload, signature)
        
        if success:
            logger.info(f"Webhook processed successfully: {message}")
            return jsonify({'status': 'success', 'message': message}), 200
        else:
            logger.error(f"Webhook processing failed: {message}")
            monitoring.create_alert(AlertSeverity.ERROR, 'payment', f'Webhook processing failed: {message}')
            return jsonify({'error': message}), 400
            
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        monitoring.create_alert(AlertSeverity.CRITICAL, 'payment', f'Webhook exception: {str(e)}')
        return jsonify({'error': 'Webhook processing error'}), 500

@payment_bp.route('/cancel-subscription', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancel user's active subscription"""
    try:
        active_subscription = current_user.get_active_subscription()
        if not active_subscription:
            flash('No active subscription found', 'error')
            return redirect(url_for('account_dashboard'))
        
        # Cancel subscription in Stripe
        import stripe
        stripe.Subscription.modify(
            active_subscription.stripe_subscription_id,
            cancel_at_period_end=True
        )
        
        # Update local subscription record
        active_subscription.cancel_at_period_end = True
        db.session.commit()
        
        flash('Subscription will be canceled at the end of your current billing period', 'info')
        logger.info(f"User {current_user.id} canceled subscription {active_subscription.id}")
        
        return redirect(url_for('account_dashboard'))
        
    except Exception as e:
        logger.error(f"Error canceling subscription: {e}")
        db.session.rollback()
        flash('Failed to cancel subscription. Please contact support.', 'error')
        return redirect(url_for('account_dashboard'))

@payment_bp.route('/billing-portal')
@login_required
def billing_portal():
    """Redirect to Stripe customer billing portal"""
    try:
        active_subscription = current_user.get_active_subscription()
        if not active_subscription or not active_subscription.stripe_customer_id:
            flash('No billing information found', 'error')
            return redirect(url_for('account_dashboard'))
        
        # Create billing portal session
        import stripe
        portal_session = stripe.billing_portal.Session.create(
            customer=active_subscription.stripe_customer_id,
            return_url=url_for('account_dashboard', _external=True)
        )
        
        return redirect(portal_session.url)
        
    except Exception as e:
        logger.error(f"Error creating billing portal session: {e}")
        flash('Billing portal temporarily unavailable', 'error')
        return redirect(url_for('account_dashboard'))

@payment_bp.route('/credit-balance')
@login_required
def get_credit_balance():
    """API endpoint to get user's current credit balance"""
    try:
        credit_balance = CreditBalance.query.filter_by(user_id=current_user.id).first()
        
        if not credit_balance:
            return jsonify({
                'subscription_credits': 0,
                'topup_credits': 0,
                'total_credits': 0,
                'subscription_expires': None
            })
        
        return jsonify({
            'subscription_credits': credit_balance.subscription_credits,
            'topup_credits': credit_balance.topup_credits,
            'total_credits': credit_balance.subscription_credits + credit_balance.topup_credits,
            'subscription_expires': credit_balance.subscription_credits_expiry.isoformat() if credit_balance.subscription_credits_expiry else None
        })
        
    except Exception as e:
        logger.error(f"Error getting credit balance: {e}")
        return jsonify({'error': 'Failed to retrieve credit balance'}), 500

# Error handlers for payment blueprint
@payment_bp.errorhandler(404)
def payment_not_found(error):
    flash('Payment page not found', 'error')
    return redirect(url_for('subscription_plans'))

@payment_bp.errorhandler(500)
def payment_error(error):
    logger.error(f"Payment blueprint error: {error}")
    flash('Payment service error. Please try again later.', 'error')
    return redirect(url_for('subscription_plans'))