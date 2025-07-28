"""
Production-grade credit management system with dual credit types.
Handles subscription credits (expire monthly, no rollover) and top-up credits (never expire, unlimited rollover).
"""

import logging
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.exc import IntegrityError
from app import db
from models import User, CreditBalance, CreditTransaction, Subscription, PaymentFailure
from monitoring import monitoring, record_payment_success, record_payment_failure, AlertSeverity

logger = logging.getLogger(__name__)

class CreditManager:
    """
    Comprehensive credit management with dual credit system:
    - Subscription credits: Expire monthly with zero rollover
    - Top-up credits: Never expire with unlimited rollover
    """
    
    def __init__(self):
        self.standard_analysis_cost = 1
        self.brain_analysis_cost = 2
        
    def get_or_create_credit_balance(self, user_id: str) -> CreditBalance:
        """Get or create credit balance for user"""
        try:
            credit_balance = db.session.query(CreditBalance).filter_by(user_id=user_id).first()
            
            if not credit_balance:
                logger.info(f"Creating new credit balance for user {user_id}")
                credit_balance = CreditBalance(
                    user_id=user_id,
                    subscription_credits=0,
                    topup_credits=0,
                    credits_used_today=0,
                    credits_used_this_cycle=0,
                    last_reset_date=datetime.utcnow().date()
                )
                db.session.add(credit_balance)
                db.session.commit()
                
            return credit_balance
            
        except Exception as e:
            logger.error(f"Error getting/creating credit balance for user {user_id}: {e}")
            db.session.rollback()
            raise
    
    def check_and_reset_daily_usage(self, credit_balance: CreditBalance) -> bool:
        """Reset daily usage counters if new day"""
        today = datetime.utcnow().date()
        
        if credit_balance.last_reset_date < today:
            logger.debug(f"Resetting daily usage for user {credit_balance.user_id}")
            credit_balance.credits_used_today = 0
            credit_balance.last_reset_date = today
            return True
        return False
    
    def expire_subscription_credits(self, user_id: str) -> int:
        """
        Expire subscription credits at end of billing cycle.
        Returns number of credits expired.
        """
        try:
            credit_balance = self.get_or_create_credit_balance(user_id)
            
            # Check if subscription credits have expired
            if not credit_balance.subscription_credits_expired:
                return 0
                
            expired_credits = credit_balance.subscription_credits
            if expired_credits <= 0:
                return 0
                
            logger.info(f"Expiring {expired_credits} subscription credits for user {user_id}")
            
            # Remove expired credits
            credit_balance.subscription_credits = 0
            credit_balance.subscription_credits_expiry = None
            
            # Record expiration transaction
            expiry_transaction = CreditTransaction()
            expiry_transaction.user_id = user_id
            expiry_transaction.transaction_type = 'expiry'
            expiry_transaction.credit_type = 'subscription'
            expiry_transaction.credits_amount = -expired_credits
            expiry_transaction.description = f'Subscription credits expired - {expired_credits} credits removed'
            db.session.add(expiry_transaction)
            
            db.session.commit()
            
            # Alert monitoring system
            monitoring.create_alert(
                AlertSeverity.INFO,
                'Subscription Credits Expired',
                f'User {user_id} lost {expired_credits} subscription credits due to expiration'
            )
            
            return expired_credits
            
        except Exception as e:
            logger.error(f"Error expiring subscription credits for user {user_id}: {e}")
            db.session.rollback()
            raise
    
    def allocate_subscription_credits(self, user_id: str, credits: int, expiry_date: date = None) -> bool:
        """
        Grant subscription credits with expiry date.
        Replaces existing subscription credits (no rollover).
        """
        try:
            credit_balance = self.get_or_create_credit_balance(user_id)
            
            # Expire existing subscription credits first
            if credit_balance.subscription_credits > 0:
                logger.info(f"Replacing {credit_balance.subscription_credits} existing subscription credits for user {user_id}")
                
                # Record the credit replacement
                replacement_transaction = CreditTransaction()
                replacement_transaction.user_id = user_id
                replacement_transaction.transaction_type = 'expiry'
                replacement_transaction.credit_type = 'subscription'
                replacement_transaction.credits_amount = -credit_balance.subscription_credits
                replacement_transaction.description = 'Previous subscription credits replaced (no rollover)'
                db.session.add(replacement_transaction)
            
            # Grant new subscription credits
            credit_balance.subscription_credits = credits
            credit_balance.subscription_credits_expiry = expiry_date
            credit_balance.credits_used_this_cycle = 0  # Reset cycle usage
            
            # Record credit grant transaction
            grant_transaction = CreditTransaction()
            grant_transaction.user_id = user_id
            grant_transaction.transaction_type = 'subscription_grant'
            grant_transaction.credit_type = 'subscription'
            grant_transaction.credits_amount = credits
            grant_transaction.description = f'Subscription credits granted - expires {expiry_date}'
            db.session.add(grant_transaction)
            
            db.session.commit()
            
            logger.info(f"Granted {credits} subscription credits to user {user_id}, expires {expiry_date}")
            return True
            
        except Exception as e:
            logger.error(f"Error granting subscription credits to user {user_id}: {e}")
            db.session.rollback()
            return False
    
    def add_topup_credits(self, user_id: str, credits: int, payment_amount: float = None, 
                         stripe_payment_id: str = None, is_bonus: bool = False) -> bool:
        """
        Add top-up credits (never expire, unlimited rollover).
        """
        try:
            credit_balance = self.get_or_create_credit_balance(user_id)
            
            # Add credits to top-up balance
            credit_balance.topup_credits += credits
            
            # Determine transaction type
            transaction_type = 'bonus' if is_bonus else 'topup_purchase'
            description = f'Bonus credits added: {credits}' if is_bonus else f'Top-up purchase: {credits} credits'
            
            # Record credit purchase transaction
            purchase_transaction = CreditTransaction()
            purchase_transaction.user_id = user_id
            purchase_transaction.transaction_type = transaction_type
            purchase_transaction.credit_type = 'topup'
            purchase_transaction.credits_amount = credits
            purchase_transaction.description = description
            purchase_transaction.stripe_payment_id = stripe_payment_id
            purchase_transaction.amount_paid = payment_amount
            db.session.add(purchase_transaction)
            
            db.session.commit()
            
            # Record successful payment if this was a purchase
            if not is_bonus and payment_amount is not None:
                record_payment_success(user_id, payment_amount)
            
            logger.info(f"Added {credits} top-up credits to user {user_id} (total: {credit_balance.topup_credits})")
            return True
            
        except Exception as e:
            logger.error(f"Error adding top-up credits to user {user_id}: {e}")
            db.session.rollback()
            
            # Record payment failure if this was a purchase
            if not is_bonus and payment_amount is not None:
                record_payment_failure(user_id, payment_amount, str(e))
            
            return False
    
    def can_afford_analysis(self, user_id: str, is_brain: bool = False) -> Dict[str, Any]:
        """
        Check if user can afford analysis and return detailed breakdown.
        """
        try:
            credit_balance = self.get_or_create_credit_balance(user_id)
            
            # Reset daily usage if needed
            self.check_and_reset_daily_usage(credit_balance)
            
            # Expire subscription credits if needed
            self.expire_subscription_credits(user_id)
            
            cost = self.brain_analysis_cost if is_brain else self.standard_analysis_cost
            total_credits = credit_balance.total_credits
            
            return {
                'can_afford': total_credits >= cost,
                'cost': cost,
                'total_credits': total_credits,
                'subscription_credits': credit_balance.subscription_credits,
                'topup_credits': credit_balance.topup_credits,
                'credits_used_today': credit_balance.credits_used_today,
                'analysis_type': 'Maximum Brain' if is_brain else 'Standard'
            }
            
        except Exception as e:
            logger.error(f"Error checking affordability for user {user_id}: {e}")
            return {
                'can_afford': False,
                'error': str(e),
                'cost': self.brain_analysis_cost if is_brain else self.standard_analysis_cost
            }
    
    def deduct_credits_for_analysis(self, user_id: str, ticker: str, is_brain: bool = False) -> Dict[str, Any]:
        """
        Deduct credits for analysis with priority: top-up credits first.
        Returns transaction details and remaining balance.
        """
        try:
            credit_balance = self.get_or_create_credit_balance(user_id)
            
            # Check if user can afford analysis
            affordability = self.can_afford_analysis(user_id, is_brain)
            if not affordability['can_afford']:
                return {
                    'success': False,
                    'error': 'Insufficient credits',
                    'cost': affordability['cost'],
                    'total_credits': affordability.get('total_credits', 0)
                }
            
            cost = affordability['cost']
            analysis_type = 'brain' if is_brain else 'standard'
            
            # Deduct credits with priority: top-up first, then subscription
            topup_used = 0
            subscription_used = 0
            
            if credit_balance.topup_credits >= cost:
                # Use only top-up credits
                credit_balance.topup_credits -= cost
                topup_used = cost
            else:
                # Use combination: all top-up + remaining from subscription
                topup_used = credit_balance.topup_credits
                subscription_used = cost - topup_used
                
                credit_balance.topup_credits = 0
                credit_balance.subscription_credits -= subscription_used
            
            # Update usage counters
            credit_balance.credits_used_today += cost
            credit_balance.credits_used_this_cycle += cost
            credit_balance.updated_at = datetime.utcnow()
            
            # Record usage transaction
            usage_transaction = CreditTransaction()
            usage_transaction.user_id = user_id
            usage_transaction.transaction_type = 'usage'
            usage_transaction.credit_type = 'mixed' if topup_used > 0 and subscription_used > 0 else ('topup' if topup_used > 0 else 'subscription')
            usage_transaction.credits_amount = -cost
            usage_transaction.analysis_type = analysis_type
            usage_transaction.ticker_symbol = ticker
            usage_transaction.description = f'{analysis_type.title()} analysis for {ticker} - {cost} credits'
            db.session.add(usage_transaction)
            
            db.session.commit()
            
            logger.info(f"Deducted {cost} credits from user {user_id} for {analysis_type} analysis of {ticker}")
            
            return {
                'success': True,
                'cost': cost,
                'topup_used': topup_used,
                'subscription_used': subscription_used,
                'remaining_credits': credit_balance.total_credits,
                'remaining_topup': credit_balance.topup_credits,
                'remaining_subscription': credit_balance.subscription_credits,
                'credits_used_today': credit_balance.credits_used_today
            }
            
        except Exception as e:
            logger.error(f"Error deducting credits for user {user_id}: {e}")
            db.session.rollback()
            
            # Record the error
            monitoring.system_monitor.record_error('credit_deduction_error', str(e), {
                'user_id': user_id,
                'ticker': ticker,
                'is_brain': is_brain
            })
            
            return {
                'success': False,
                'error': str(e),
                'cost': self.brain_analysis_cost if is_brain else self.standard_analysis_cost
            }
    
    def refund_credits(self, user_id: str, credits: int, reason: str = "Analysis refund") -> bool:
        """
        Refund credits to user (added as top-up credits for flexibility).
        """
        try:
            credit_balance = self.get_or_create_credit_balance(user_id)
            
            # Add refunded credits as top-up credits
            credit_balance.topup_credits += credits
            credit_balance.updated_at = datetime.utcnow()
            
            # Record refund transaction
            refund_transaction = CreditTransaction()
            refund_transaction.user_id = user_id
            refund_transaction.transaction_type = 'refund'
            refund_transaction.credit_type = 'topup'
            refund_transaction.credits_amount = credits
            refund_transaction.description = f'Credit refund: {reason}'
            db.session.add(refund_transaction)
            
            db.session.commit()
            
            logger.info(f"Refunded {credits} credits to user {user_id}: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Error refunding credits to user {user_id}: {e}")
            db.session.rollback()
            return False
    
    def get_user_credit_info(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive credit information for dashboard display"""
        try:
            credit_balance = self.get_or_create_credit_balance(user_id)
            
            # Check and reset daily usage if needed
            self.check_and_reset_daily_usage(credit_balance)
            
            # Expire subscription credits if needed  
            self.expire_subscription_credits(user_id)
            
            # Refresh after potential changes
            db.session.refresh(credit_balance)
            
            return {
                'total_credits': credit_balance.total_credits,
                'subscription_credits': credit_balance.subscription_credits,
                'topup_credits': credit_balance.topup_credits,
                'credits_used_today': credit_balance.credits_used_today,
                'subscription_expiry': credit_balance.subscription_credits_expiry.isoformat() if credit_balance.subscription_credits_expiry else None,
                'standard_cost': self.standard_analysis_cost,
                'brain_cost': self.brain_analysis_cost,
                'daily_reset_time': credit_balance.last_reset_date.isoformat() if credit_balance.last_reset_date else None
            }
            
        except Exception as e:
            logger.error(f"Error getting credit info for user {user_id}: {e}")
            return {
                'total_credits': 0,
                'subscription_credits': 0,
                'topup_credits': 0,
                'credits_used_today': 0,
                'subscription_expiry': None,
                'standard_cost': self.standard_analysis_cost,
                'brain_cost': self.brain_analysis_cost,
                'error': 'Could not retrieve credit information'
            }
    
    def get_usage_analytics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive usage analytics for dashboard charts"""
        try:
            from datetime import timedelta
            from sqlalchemy import func
            
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get daily usage breakdown
            daily_usage = db.session.query(
                func.date(CreditTransaction.created_at).label('date'),
                func.sum(CreditTransaction.credits_amount).label('credits_used'),
                func.count(CreditTransaction.id).label('transaction_count')
            ).filter(
                CreditTransaction.user_id == user_id,
                CreditTransaction.transaction_type == 'usage',
                CreditTransaction.created_at >= start_date
            ).group_by(
                func.date(CreditTransaction.created_at)
            ).order_by('date').all()
            
            # Get analysis type breakdown
            analysis_breakdown = db.session.query(
                CreditTransaction.analysis_type,
                func.count(CreditTransaction.id).label('count'),
                func.sum(CreditTransaction.credits_amount).label('total_credits')
            ).filter(
                CreditTransaction.user_id == user_id,
                CreditTransaction.transaction_type == 'usage',
                CreditTransaction.created_at >= start_date
            ).group_by(
                CreditTransaction.analysis_type
            ).all()
            
            # Get total statistics
            total_analyses = db.session.query(func.count(CreditTransaction.id)).filter(
                CreditTransaction.user_id == user_id,
                CreditTransaction.transaction_type == 'usage',
                CreditTransaction.created_at >= start_date
            ).scalar() or 0
            
            total_credits_used = db.session.query(func.sum(CreditTransaction.credits_amount)).filter(
                CreditTransaction.user_id == user_id,
                CreditTransaction.transaction_type == 'usage',
                CreditTransaction.created_at >= start_date
            ).scalar() or 0
            
            return {
                'daily_usage': [
                    {
                        'date': usage.date.isoformat(),
                        'credits_used': int(abs(usage.credits_used)),
                        'transaction_count': usage.transaction_count
                    } for usage in daily_usage
                ],
                'analysis_breakdown': [
                    {
                        'analysis_type': breakdown.analysis_type or 'Unknown',
                        'count': breakdown.count,
                        'total_credits': int(abs(breakdown.total_credits))
                    } for breakdown in analysis_breakdown
                ],
                'summary': {
                    'total_analyses': total_analyses,
                    'total_credits_used': int(abs(total_credits_used)) if total_credits_used else 0,
                    'average_daily_usage': round(abs(total_credits_used) / days, 2) if days > 0 and total_credits_used else 0,
                    'period_days': days
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting usage analytics for user {user_id}: {e}")
            return {
                'daily_usage': [],
                'analysis_breakdown': [],
                'summary': {
                    'total_analyses': 0,
                    'total_credits_used': 0,
                    'average_daily_usage': 0,
                    'period_days': days
                },
                'error': 'Could not retrieve usage analytics'
            }

    def get_credit_history(self, user_id: str, limit: int = 50, page: int = 1, per_page: int = 20, transaction_type: str = None) -> Dict[str, Any]:
        """Get paginated credit transaction history for user"""
        try:
            query = CreditTransaction.query.filter_by(user_id=user_id)
            
            if transaction_type:
                query = query.filter_by(transaction_type=transaction_type)
            
            # Order by most recent first
            query = query.order_by(CreditTransaction.created_at.desc())
            
            # Handle pagination
            if page and per_page:
                from sqlalchemy.orm import defer
                pagination = query.paginate(
                    page=page, 
                    per_page=per_page, 
                    error_out=False
                )
                
                transactions = []
                for transaction in pagination.items:
                    transactions.append({
                        'id': transaction.id,
                        'transaction_type': transaction.transaction_type,
                        'credit_type': transaction.credit_type,
                        'credits_amount': transaction.credits_amount,
                        'analysis_type': transaction.analysis_type,
                        'ticker_symbol': transaction.ticker_symbol,
                        'created_at': transaction.created_at.isoformat(),
                        'description': self._format_transaction_description(transaction)
                    })
                
                return {
                    'items': transactions,
                    'total': pagination.total,
                    'pages': pagination.pages,
                    'page': page,
                    'per_page': per_page,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                }
            else:
                # Legacy format for backward compatibility
                transactions = query.limit(limit).all()
                return [{
                    'id': t.id,
                    'type': t.transaction_type,
                    'credit_type': t.credit_type,
                    'amount': t.credits_amount,
                    'description': t.description,
                    'analysis_type': t.analysis_type,
                    'ticker': t.ticker_symbol,
                    'amount_paid': t.amount_paid,
                    'created_at': t.created_at.isoformat()
                } for t in transactions]
            
        except Exception as e:
            logger.error(f"Error getting credit history for user {user_id}: {e}")
            if page and per_page:
                return {
                    'items': [],
                    'total': 0,
                    'pages': 0,
                    'page': page,
                    'per_page': per_page,
                    'has_next': False,
                    'has_prev': False,
                    'error': str(e)
                }
            return []
    
    def _format_transaction_description(self, transaction):
        """Format a human-readable description for transactions"""
        if transaction.transaction_type == 'usage':
            analysis_type = transaction.analysis_type or 'analysis'
            ticker = f" ({transaction.ticker_symbol})" if transaction.ticker_symbol else ""
            return f"{analysis_type.title()} analysis{ticker} - {abs(transaction.credits_amount)} credits used"
        elif transaction.transaction_type == 'subscription_grant':
            return f"Monthly subscription credits granted - {transaction.credits_amount} credits"
        elif transaction.transaction_type == 'topup_purchase':
            return f"Credit pack purchased - {transaction.credits_amount} credits added"
        elif transaction.transaction_type == 'expiry':
            return f"Subscription credits expired - {abs(transaction.credits_amount)} credits"
        elif transaction.transaction_type == 'refund':
            return f"Credit refund - {transaction.credits_amount} credits restored"
        else:
            return f"{transaction.transaction_type.replace('_', ' ').title()} - {transaction.credits_amount} credits"
    
    def get_user_credit_summary(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive credit summary for user"""
        try:
            credit_balance = self.get_or_create_credit_balance(user_id)
            
            # Check if daily reset is needed
            self.check_and_reset_daily_usage(credit_balance)
            
            # Check for expired subscription credits
            self.expire_subscription_credits(user_id)
            
            # Get user's subscription status
            user = db.session.get(User, user_id)
            subscription = user.get_active_subscription() if user else None
            
            return {
                'total_credits': credit_balance.total_credits,
                'subscription_credits': credit_balance.subscription_credits,
                'topup_credits': credit_balance.topup_credits,
                'credits_used_today': credit_balance.credits_used_today,
                'credits_used_this_cycle': credit_balance.credits_used_this_cycle,
                'subscription_credits_expiry': credit_balance.subscription_credits_expiry.isoformat() if credit_balance.subscription_credits_expiry else None,
                'has_active_subscription': subscription is not None,
                'subscription_status': subscription.status if subscription else None,
                'subscription_plan': subscription.plan_type if subscription else None,
                'days_until_renewal': subscription.days_until_renewal() if subscription else None,
                'can_afford_standard': credit_balance.total_credits >= self.standard_analysis_cost,
                'can_afford_brain': credit_balance.total_credits >= self.brain_analysis_cost
            }
            
        except Exception as e:
            logger.error(f"Error getting credit summary for user {user_id}: {e}")
            return {
                'error': str(e),
                'total_credits': 0,
                'can_afford_standard': False,
                'can_afford_brain': False
            }
    
    def process_subscription_renewal(self, user_id: str) -> bool:
        """
        Process monthly subscription renewal:
        1. Expire old subscription credits (no rollover)
        2. Grant new subscription credits
        """
        try:
            user = db.session.get(User, user_id)
            if not user:
                logger.error(f"User {user_id} not found for subscription renewal")
                return False
                
            subscription = user.get_active_subscription()
            if not subscription:
                logger.error(f"No active subscription found for user {user_id}")
                return False
            
            # Calculate new expiry date based on plan
            if subscription.plan_type == 'weekly':
                expiry_date = datetime.utcnow().date() + timedelta(days=7)
            else:  # monthly
                expiry_date = datetime.utcnow().date() + timedelta(days=30)
            
            # Grant new subscription credits (this will expire old ones)
            success = self.grant_subscription_credits(
                user_id, 
                subscription.credits_per_cycle, 
                expiry_date
            )
            
            if success:
                logger.info(f"Subscription renewed for user {user_id}: {subscription.credits_per_cycle} credits until {expiry_date}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error processing subscription renewal for user {user_id}: {e}")
            return False

# Global credit manager instance
credit_manager = CreditManager()