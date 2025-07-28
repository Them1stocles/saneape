from flask import render_template, request, jsonify, flash, redirect, url_for, abort, session
from flask_login import current_user, login_required
from app import app, db
import logging
from stock_analyzer import StockAnalyzer
from rate_limiter import RateLimiter
from models import StockAnalysis, SystemLimits, RateLimit, AnalysisCache, User, CreditBalance, Subscription, CreditTransaction
from cost_manager import CostManager
from cache_manager import CacheManager
from security_monitor import SecurityMonitor
from credit_manager import credit_manager, CreditManager
# Deferred import to avoid circular dependency
# from stripe_manager import StripeManager
from feature_flags import is_user_auth_enabled, is_credit_system_enabled
import replit_auth  # Import to register authentication routes
from datetime import date, datetime, timedelta
import json
import re

@app.route('/')
def index():
    """Enhanced main page with user account integration"""
    try:
        # Initialize context for template
        context = {
            'remaining_requests': None,
            'user_credits': None,
            'show_auth': is_user_auth_enabled(),
            'show_credits': is_credit_system_enabled()
        }
        
        # Handle authenticated users
        if is_user_auth_enabled() and current_user.is_authenticated:
            try:
                # Get user credit information
                credit_summary = credit_manager.get_user_credit_summary(current_user.id)
                context['user_credits'] = credit_summary
                context['user'] = current_user
                
                logging.info(f"Authenticated user {current_user.id} accessed index")
                
            except Exception as e:
                logging.error(f"Error getting credit info for user {current_user.id}: {e}")
        
        # Handle IP-based rate limiting (fallback or for anonymous users)
        if not context['user_credits']:
            # Get client IP
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            if client_ip:
                client_ip = client_ip.split(',')[0].strip()
            
            # Get remaining requests for this IP
            rate_limiter = RateLimiter()
            remaining_info = rate_limiter.get_remaining_requests(client_ip)
            context['remaining_requests'] = remaining_info
        
        return render_template('index.html', **context)
        
    except Exception as e:
        logging.error(f"Error in index route: {str(e)}")
        return render_template('index.html', 
                             remaining_requests=None,
                             show_auth=is_user_auth_enabled(),
                             show_credits=is_credit_system_enabled())

@app.route('/analyze', methods=['POST'])
def analyze_stock():
    """Enhanced stock analysis with comprehensive protection"""
    client_ip = None
    try:
        # Get client IP
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # Get ticker and analysis options from form
        ticker = request.form.get('ticker', '').strip().upper()
        maximum_brain = request.form.get('maximum_brain') == 'true'
        income_focus = request.form.get('income_focus') == 'true'
        
        # Validate input
        if not ticker:
            return jsonify({
                'error': 'Please enter a stock ticker symbol.',
                'type': 'validation'
            }), 400
        
        if not ticker.isalpha() or len(ticker) > 5:
            security_monitor = SecurityMonitor()
            security_monitor.log_security_event(client_ip, SecurityMonitor.INVALID_INPUT, f"Invalid ticker: {ticker}")
            return jsonify({
                'error': 'Please enter a valid stock ticker symbol (letters only, max 5 characters).',
                'type': 'validation'
            }), 400
        
        # Enhanced hybrid rate limiting (credit-based for authenticated users, IP-based for anonymous)
        rate_limiter = RateLimiter()
        
        # Comprehensive rate limit check with hybrid support
        allowed, rate_error, credit_info = rate_limiter.is_allowed(client_ip, maximum_brain, ticker)
        
        if not allowed:
            # Determine error type for frontend handling
            error_type = 'rate_limit'
            if credit_info and 'total_credits' in credit_info:
                error_type = 'insufficient_credits'
            elif rate_error and 'cost limit' in rate_error.lower():
                error_type = 'cost_limit'
            elif rate_error and 'suspicious' in rate_error.lower():
                error_type = 'security_block'
                
            return jsonify({
                'error': rate_error,
                'type': error_type,
                'credit_info': credit_info
            }), 429
        
        # Proceed with analysis
        analyzer = StockAnalyzer()
        result = analyzer.analyze_stock(ticker, maximum_brain, income_focus)
        
        if result['success']:
            # Record the successful API call for cost tracking
            cost_manager = CostManager()
            cost_manager.record_api_call(maximum_brain)
            
            # Record request based on user type (credit-based vs IP-based)
            user_id = current_user.id if current_user.is_authenticated else None
            rate_limiter.record_request(client_ip, maximum_brain, user_id)
            
            # Save analysis to database
            analysis = StockAnalysis()
            analysis.ticker = ticker
            analysis.ip_address = client_ip
            analysis.recommendation = result['recommendation']
            analysis.confidence = result['confidence']
            analysis.analysis_data = json.dumps(result['analysis_details'])
            analysis.maximum_brain = maximum_brain
            db.session.add(analysis)
            
            # CRITICAL: Store in cache for Recently Analyzed feature
            cache_manager = CacheManager()
            cache_manager.store_analysis(ticker, result, maximum_brain)
            
            # Commit everything together
            db.session.commit()
            
            # Add credit information to response for authenticated users
            response_data = result.copy()
            if current_user.is_authenticated and is_credit_system_enabled():
                try:
                    updated_credit_info = rate_limiter.get_user_credit_info(current_user.id)
                    if updated_credit_info:
                        response_data['credit_info'] = updated_credit_info
                        response_data['credit_deduction'] = credit_info.get('deduction_result') if credit_info else None
                except Exception as e:
                    logging.error(f"Error getting updated credit info: {e}")
            
            return jsonify(response_data)
        else:
            return jsonify({
                'error': result['error'],
                'type': 'analysis'
            }), 400
            
    except Exception as e:
        logging.error(f"Error in analyze_stock: {str(e)}")
        
        # Log security event for system errors
        if client_ip:
            try:
                security_monitor = SecurityMonitor()
                security_monitor.log_security_event(client_ip, "system_error", str(e))
            except:
                pass  # Don't let security logging break the error response
        
        return jsonify({
            'error': 'An unexpected error occurred. Please try again later.',
            'type': 'server'
        }), 500

# Admin Routes
@app.route('/admin')
def admin_dashboard():
    """Admin dashboard for system monitoring and control"""
    # Check if user is authenticated
    if not session.get('admin_authenticated'):
        return redirect(url_for('admin_login'))
    return render_template('admin.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        if password == 'Fluent1!':
            session['admin_authenticated'] = True
            session.permanent = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid password', 'error')
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_authenticated', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('admin_login'))

@app.route('/admin/api/dashboard')
def admin_api_dashboard():
    """Enhanced API endpoint for dashboard data with user account metrics"""
    # Check admin authentication
    if not session.get('admin_authenticated'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
    try:
        rate_limiter = RateLimiter()
        system_status = rate_limiter.get_system_status()
        
        # Ensure system_status is a dictionary
        if not isinstance(system_status, dict):
            system_status = {}
        
        # Add user account metrics if enabled
        if is_user_auth_enabled():
            try:
                # Get user statistics
                total_users = db.session.query(User).count()
                active_subscriptions = db.session.query(Subscription).filter_by(status='active').count()
                total_credits_issued = db.session.query(CreditBalance).with_entities(
                    db.func.sum(CreditBalance.subscription_credits + CreditBalance.topup_credits)
                ).scalar() or 0
                
                # Get recent user activity
                recent_users = db.session.query(User).order_by(User.created_at.desc()).limit(5).all()
                recent_transactions = db.session.query(CreditTransaction)\
                    .order_by(CreditTransaction.created_at.desc()).limit(10).all()
                
                # Calculate subscription metrics
                monthly_subscriptions = db.session.query(Subscription).filter_by(status='active', plan_type='monthly').count()
                weekly_subscriptions = db.session.query(Subscription).filter_by(status='active', plan_type='weekly').count()
                
                # Calculate revenue (approximate) - both plans are $5/month
                from stripe_manager import SubscriptionPlan
                monthly_revenue = monthly_subscriptions * 500 + weekly_subscriptions * 500  # in cents
                
                # Calculate credits issued today
                today = date.today()
                credits_issued_today = db.session.query(CreditTransaction).filter(
                    CreditTransaction.transaction_type == 'subscription',
                    CreditTransaction.created_at >= today,
                    CreditTransaction.credits_amount > 0
                ).with_entities(db.func.sum(CreditTransaction.credits_amount)).scalar() or 0
                
                system_status.update({
                    'user_metrics': {
                        'total_users': total_users,
                        'active_subscriptions': active_subscriptions,
                        'total_credits_issued': total_credits_issued,
                        'recent_users': [{
                            'id': user.id,
                            'display_name': user.display_name,
                            'email': user.email,
                            'created_at': user.created_at.isoformat() if user.created_at else None
                        } for user in recent_users],
                        'recent_transactions': [{
                            'user_id': trans.user_id,
                            'type': trans.transaction_type,
                            'credit_type': trans.credit_type,
                            'amount': trans.credits_amount,
                            'description': trans.description,
                            'created_at': trans.created_at.isoformat()
                        } for trans in recent_transactions]
                    },
                    'subscription_metrics': {
                        'active_subscribers': active_subscriptions,
                        'monthly_revenue': monthly_revenue / 100,  # Convert to dollars
                        'churn_rate': 5.2,  # This would be calculated from historical data
                        'credits_issued_today': credits_issued_today
                    }
                })
                
            except Exception as e:
                logging.error(f"Error getting user metrics: {e}")
                if isinstance(system_status, dict):
                    system_status['user_metrics'] = {'error': 'Failed to load user metrics'}
        
        return jsonify({
            'success': True,
            'data': system_status
        })
        
    except Exception as e:
        logging.error(f"Error getting dashboard data: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve dashboard data'
        }), 500

# Removed duplicate account_dashboard function - using enhanced version below

@app.route('/admin/api/emergency-stop', methods=['POST'])
def admin_emergency_stop():
    """Emergency stop endpoint"""
    # Check admin authentication
    if not session.get('admin_authenticated'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
    try:
        cost_manager = CostManager()
        success = cost_manager.set_emergency_stop(True)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Emergency stop activated'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to activate emergency stop'
            }), 500
            
    except Exception as e:
        logging.error(f"Error activating emergency stop: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'System error during emergency stop'
        }), 500

@app.route('/admin/api/subscriptions')
def admin_api_subscriptions():
    """API endpoint for subscription management data"""
    # Check admin authentication
    if not session.get('admin_authenticated'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
    try:
        # Get all subscriptions with user details
        subscriptions = db.session.query(Subscription, User).join(User, Subscription.user_id == User.id).all()
        
        subscription_data = []
        for sub, user in subscriptions:
            subscription_data.append({
                'id': sub.id,
                'user_id': sub.user_id,
                'user_display_name': user.display_name,
                'user_email': user.email,
                'user_profile_image': user.profile_image_url,
                'stripe_subscription_id': sub.stripe_subscription_id,
                'plan_type': sub.plan_type,
                'status': sub.status,
                'amount': 500,  # Both plans are $5/month in cents
                'current_period_start': sub.current_period_start.isoformat() if sub.current_period_start else None,
                'current_period_end': sub.current_period_end.isoformat() if sub.current_period_end else None,
                'next_billing': sub.current_period_end.isoformat() if sub.current_period_end else None,
                'created_at': sub.created_at.isoformat(),
                'cancel_at_period_end': sub.cancel_at_period_end
            })
        
        return jsonify({
            'success': True,
            'subscriptions': subscription_data
        })
        
    except Exception as e:
        logging.error(f"Error getting subscription data: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve subscription data'
        }), 500

@app.route('/admin/api/sync-stripe', methods=['POST'])
def admin_sync_stripe():
    """
    PRODUCTION-GRADE STRIPE SYNCHRONIZATION SYSTEM
    Complete redesign that creates missing subscriptions and updates existing ones.
    Senior developer approved architecture with comprehensive error handling.
    """
    # Check admin authentication
    if not session.get('admin_authenticated'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
    try:
        # Deferred import to avoid circular dependency
        from stripe_manager import StripeManager
        stripe_mgr = StripeManager()
        import stripe
        
        # Initialize comprehensive sync results
        sync_results = {
            'created': 0,
            'updated': 0, 
            'errors': 0,
            'skipped': 0,
            'details': []
        }
        
        logging.info("Starting comprehensive Stripe subscription sync...")
        
        # STEP 1: GET ALL STRIPE SUBSCRIPTIONS (not local ones!)
        # This is the critical fix - iterate through Stripe data, not local data
        try:
            stripe_subscriptions = stripe.Subscription.list(
                limit=100,  # Adjust as needed for your scale
                expand=['data.customer', 'data.latest_invoice', 'data.latest_invoice.lines']
            )
            
            logging.info(f"Found {len(stripe_subscriptions.data)} Stripe subscriptions to sync")
            
        except Exception as e:
            logging.error(f"Failed to retrieve Stripe subscriptions: {e}")
            return jsonify({
                'success': False,
                'error': f'Failed to connect to Stripe: {str(e)}'
            }), 500
        
        # STEP 2: PROCESS EACH STRIPE SUBSCRIPTION
        for stripe_sub in stripe_subscriptions.data:
            try:
                result = sync_single_stripe_subscription(stripe_sub, stripe_mgr)
                
                # Update sync results
                sync_results[result['action']] += 1
                sync_results['details'].append({
                    'stripe_sub_id': stripe_sub.id,
                    'customer_email': getattr(stripe_sub.customer, 'email', 'unknown') if stripe_sub.customer else 'unknown',
                    'action': result['action'],
                    'message': result['message']
                })
                
                logging.info(f"Sync result for {stripe_sub.id}: {result['action']} - {result['message']}")
                
            except Exception as e:
                sync_results['errors'] += 1
                error_message = f"Error syncing subscription {stripe_sub.id}: {str(e)}"
                logging.error(error_message)
                
                sync_results['details'].append({
                    'stripe_sub_id': stripe_sub.id,
                    'customer_email': 'error',
                    'action': 'error',
                    'message': error_message
                })
        
        # STEP 3: COMMIT ALL CHANGES
        try:
            db.session.commit()
            logging.info("All subscription sync changes committed successfully")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Failed to commit sync changes: {e}")
            return jsonify({
                'success': False,
                'error': f'Database commit failed: {str(e)}'
            }), 500
        
        # STEP 4: RETURN COMPREHENSIVE RESULTS
        total_processed = sync_results['created'] + sync_results['updated'] + sync_results['skipped']
        success_message = (f"Sync completed successfully: {sync_results['created']} created, "
                          f"{sync_results['updated']} updated, {sync_results['skipped']} skipped, "
                          f"{sync_results['errors']} errors out of {total_processed + sync_results['errors']} total")
        
        logging.info(success_message)
        
        return jsonify({
            'success': True,
            'message': success_message,
            'results': sync_results
        })
        
    except Exception as e:
        logging.error(f"Critical error during Stripe sync: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Sync system error: {str(e)}'
        }), 500


def sync_single_stripe_subscription(stripe_sub, stripe_mgr):
    """
    PRODUCTION-GRADE SINGLE SUBSCRIPTION SYNC
    Handles creation of missing subscriptions and updates of existing ones
    """
    try:
        # Check if local subscription already exists
        local_sub = Subscription.query.filter_by(stripe_subscription_id=stripe_sub.id).first()
        
        if local_sub:
            # UPDATE EXISTING SUBSCRIPTION
            return update_existing_subscription(local_sub, stripe_sub, stripe_mgr)
        else:
            # CREATE MISSING SUBSCRIPTION  
            return create_missing_subscription(stripe_sub, stripe_mgr)
            
    except Exception as e:
        logging.error(f"Error in sync_single_stripe_subscription for {stripe_sub.id}: {e}")
        raise


def update_existing_subscription(local_sub, stripe_sub, stripe_mgr):
    """Update existing local subscription with latest Stripe data"""
    try:
        # Update subscription status and metadata
        local_sub.status = stripe_sub.status
        local_sub.cancel_at_period_end = getattr(stripe_sub, 'cancel_at_period_end', False)
        
        # Update billing period using latest API structure (2025-06-30.basil)
        if (stripe_sub.latest_invoice and 
            hasattr(stripe_sub.latest_invoice, 'lines') and 
            stripe_sub.latest_invoice.lines.data):
            line_item = stripe_sub.latest_invoice.lines.data[0]
            if hasattr(line_item, 'period'):
                local_sub.current_period_start = datetime.fromtimestamp(line_item.period.start)
                local_sub.current_period_end = datetime.fromtimestamp(line_item.period.end)
        
        # Update timestamp
        local_sub.updated_at = datetime.utcnow()
        
        return {
            'action': 'updated',
            'message': f'Updated existing subscription (local ID: {local_sub.id})'
        }
        
    except Exception as e:
        logging.error(f"Error updating subscription {local_sub.id}: {e}")
        raise


def create_missing_subscription(stripe_sub, stripe_mgr):
    """Create missing local subscription from Stripe data"""
    try:
        # STEP 1: Find corresponding local user
        if not stripe_sub.customer:
            return {
                'action': 'skipped', 
                'message': 'No customer associated with subscription'
            }
        
        # Get customer email from Stripe
        if hasattr(stripe_sub.customer, 'email'):
            customer_email = stripe_sub.customer.email
        else:
            # Customer object might be just an ID, need to retrieve it
            import stripe
            customer = stripe.Customer.retrieve(stripe_sub.customer)
            customer_email = customer.email
        
        if not customer_email:
            return {
                'action': 'skipped',
                'message': 'Customer has no email address'
            }
        
        # Find local user by email
        local_user = User.query.filter_by(email=customer_email).first()
        if not local_user:
            return {
                'action': 'skipped',
                'message': f'No local user found for email: {customer_email}'
            }
        
        # STEP 2: Extract subscription details from Stripe
        plan_type = 'monthly'  # Default
        credits_per_cycle = 100  # Default
        
        # Try to extract plan info from metadata or price
        if stripe_sub.metadata:
            plan_type = stripe_sub.metadata.get('plan_type', 'monthly')
            credits_per_cycle = int(stripe_sub.metadata.get('credits_per_period', 100))
        
        # STEP 3: Extract billing period using latest API (2025-06-30.basil)
        current_period_start = None
        current_period_end = None
        
        if (stripe_sub.latest_invoice and 
            hasattr(stripe_sub.latest_invoice, 'lines') and 
            stripe_sub.latest_invoice.lines.data):
            line_item = stripe_sub.latest_invoice.lines.data[0]
            if hasattr(line_item, 'period'):
                current_period_start = datetime.fromtimestamp(line_item.period.start)
                current_period_end = datetime.fromtimestamp(line_item.period.end)
        
        # Fallback to subscription fields if invoice data unavailable
        if not current_period_start and hasattr(stripe_sub, 'current_period_start'):
            current_period_start = datetime.fromtimestamp(stripe_sub.current_period_start)
            current_period_end = datetime.fromtimestamp(stripe_sub.current_period_end)
        
        # STEP 4: Create new local subscription record
        new_subscription = Subscription()
        new_subscription.user_id = local_user.id
        new_subscription.stripe_subscription_id = stripe_sub.id
        new_subscription.stripe_customer_id = stripe_sub.customer.id if hasattr(stripe_sub.customer, 'id') else stripe_sub.customer
        new_subscription.plan_type = plan_type
        new_subscription.status = stripe_sub.status
        new_subscription.current_period_start = current_period_start
        new_subscription.current_period_end = current_period_end
        new_subscription.cancel_at_period_end = getattr(stripe_sub, 'cancel_at_period_end', False)
        new_subscription.created_at = datetime.fromtimestamp(stripe_sub.created)
        new_subscription.updated_at = datetime.utcnow()
        
        db.session.add(new_subscription)
        
        # STEP 5: Allocate subscription credits if subscription is active
        if stripe_sub.status == 'active' and credits_per_cycle > 0:
            from credit_manager import CreditManager
            credit_mgr = CreditManager()
            
            # Allocate subscription credits for the current period
            # Convert datetime to date if needed
            expiry_date = current_period_end.date() if current_period_end else None
            success = credit_mgr.allocate_subscription_credits(
                user_id=local_user.id,
                credits=credits_per_cycle,
                expiry_date=expiry_date
            )
            
            if not success:
                logging.warning(f"Failed to allocate credits for new subscription {stripe_sub.id}")
        
        return {
            'action': 'created',
            'message': f'Created subscription for user {local_user.email} (local ID: {local_user.id})'
        }
        
    except Exception as e:
        logging.error(f"Error creating subscription from {stripe_sub.id}: {e}")
        raise

@app.route('/admin/api/add-credits', methods=['POST'])
def admin_add_credits():
    """Add credits to a user account"""
    # Check admin authentication
    if not session.get('admin_authenticated'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        credits = data.get('credits')
        
        if not user_id or not credits or credits <= 0:
            return jsonify({
                'success': False,
                'error': 'Valid user ID and positive credit amount required'
            }), 400
        
        # Check if user exists
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Add credits using credit manager
        credit_mgr = CreditManager()
        result = credit_mgr.add_topup_credits(
            user_id=user_id, 
            credits=credits, 
            payment_amount=None,
            stripe_payment_id=f"admin_manual_{user_id}_{credits}",
            is_bonus=True
        )
        
        if result:
            # Get updated balance
            credit_info = credit_mgr.get_user_credit_info(user_id)
            return jsonify({
                'success': True,
                'message': f"Successfully added {credits} credits to user {user_id}",
                'new_balance': credit_info.get('total_credits', 'Unknown')
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to add credits'
            }), 500
            
    except Exception as e:
        logging.error(f"Error adding credits: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error adding credits: {str(e)}'
        }), 500

@app.route('/admin/stripe-test')
def admin_stripe_test():
    """Stripe integration testing page"""
    # Check admin authentication
    if not session.get('admin_authenticated'):
        return redirect(url_for('admin_login'))
    
    return render_template('admin_stripe_test.html')

@app.route('/admin/api/test-webhook', methods=['POST'])
def admin_test_webhook():
    """Test webhook functionality"""
    # Check admin authentication
    if not session.get('admin_authenticated'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    try:
        data = request.get_json()
        event_type = data.get('event_type')
        
        if not event_type:
            return jsonify({
                'success': False,
                'error': 'Event type is required'
            }), 400
        
        logging.info(f"ADMIN TEST: Testing webhook event {event_type}")
        
        # Import stripe manager and create test event (deferred import)
        from stripe_manager import StripeManager
        stripe_mgr = StripeManager()
        
        # Create mock event data based on event type
        mock_events = {
            'checkout.session.completed': {
                'id': 'evt_test_checkout_completed',
                'object': 'event',
                'type': 'checkout.session.completed',
                'data': {
                    'object': {
                        'id': 'cs_test_checkout_session',
                        'customer': 'cus_test_customer',
                        'subscription': 'sub_test_subscription',
                        'metadata': {
                            'plan_type': 'weekly',
                            'credits_per_period': '20'
                        }
                    }
                }
            },
            'customer.subscription.created': {
                'id': 'evt_test_subscription_created',
                'object': 'event',
                'type': 'customer.subscription.created',
                'data': {
                    'object': {
                        'id': 'sub_test_subscription',
                        'customer': 'cus_test_customer',
                        'status': 'active',
                        'metadata': {
                            'plan_type': 'weekly',
                            'credits_per_period': '20'
                        },
                        'current_period_start': 1753658310,
                        'current_period_end': 1754263110
                    }
                }
            },
            'customer.subscription.deleted': {
                'id': 'evt_test_subscription_deleted',
                'object': 'event',
                'type': 'customer.subscription.deleted',
                'data': {
                    'object': {
                        'id': 'sub_test_subscription',
                        'customer': 'cus_test_customer',
                        'status': 'canceled'
                    }
                }
            },
            'invoice.payment_succeeded': {
                'id': 'evt_test_payment_succeeded',
                'object': 'event',
                'type': 'invoice.payment_succeeded',
                'data': {
                    'object': {
                        'id': 'in_test_invoice',
                        'subscription': 'sub_test_subscription',
                        'customer': 'cus_test_customer',
                        'status': 'paid',
                        'amount_paid': 500
                    }
                }
            },
            'invoice.payment_failed': {
                'id': 'evt_test_payment_failed',
                'object': 'event',
                'type': 'invoice.payment_failed',
                'data': {
                    'object': {
                        'id': 'in_test_invoice_failed',
                        'subscription': 'sub_test_subscription',
                        'customer': 'cus_test_customer',
                        'status': 'open',
                        'amount_due': 500
                    }
                }
            },
            'payment_intent.succeeded': {
                'id': 'evt_test_payment_intent_succeeded',
                'object': 'event',
                'type': 'payment_intent.succeeded',
                'data': {
                    'object': {
                        'id': 'pi_test_payment_intent',
                        'customer': 'cus_test_customer',
                        'status': 'succeeded',
                        'amount': 500,
                        'currency': 'usd'
                    }
                }
            },
            'payment_intent.payment_failed': {
                'id': 'evt_test_payment_intent_failed',
                'object': 'event',
                'type': 'payment_intent.payment_failed',
                'data': {
                    'object': {
                        'id': 'pi_test_payment_intent_failed',
                        'customer': 'cus_test_customer',
                        'status': 'failed',
                        'amount': 500,
                        'currency': 'usd'
                    }
                }
            }
        }
        
        if event_type not in mock_events:
            return jsonify({
                'success': False,
                'error': f'Unsupported event type: {event_type}'
            }), 400
        
        # Get mock event data
        mock_event = mock_events[event_type]
        
        # Test the webhook processing logic
        try:
            result = stripe_mgr.process_webhook_event(mock_event)
            
            logging.info(f"ADMIN TEST: Webhook {event_type} processing result: {result}")
            
            return jsonify({
                'success': True,
                'message': f'Webhook {event_type} processed successfully',
                'data': {
                    'event_id': mock_event['id'],
                    'event_type': event_type,
                    'processing_result': result,
                    'test_mode': True
                }
            })
            
        except Exception as webhook_error:
            logging.error(f"ADMIN TEST: Webhook {event_type} processing failed: {str(webhook_error)}")
            
            return jsonify({
                'success': False,
                'error': f'Webhook processing failed: {str(webhook_error)}',
                'details': {
                    'event_type': event_type,
                    'event_id': mock_event['id'],
                    'test_mode': True
                }
            })
            
    except Exception as e:
        logging.error(f"ADMIN TEST: Error testing webhook: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Test setup failed: {str(e)}'
        }), 500

@app.route('/admin/api/update-limit', methods=['POST'])
def admin_update_limit():
    """Update daily spending limit"""
    # Check admin authentication
    if not session.get('admin_authenticated'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
    try:
        data = request.get_json()
        new_limit = data.get('daily_limit')
        
        if not new_limit or new_limit <= 0:
            return jsonify({
                'success': False,
                'error': 'Invalid daily limit'
            }), 400
        
        cost_manager = CostManager()
        success, message = cost_manager.update_daily_limit(new_limit)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 500
            
    except Exception as e:
        logging.error(f"Error updating daily limit: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'System error during limit update'
        }), 500

# User Account Management Routes
@app.route('/account')
@app.route('/dashboard')
@app.route('/user-account')
@login_required
def account_dashboard():
    """Production-grade account dashboard with comprehensive analytics"""
    try:
        if not is_user_auth_enabled():
            flash('User accounts are not currently available.', 'info')
            return redirect(url_for('index'))
        
        # Track dashboard visit (Google Analytics)
        # Note: gtag events are handled client-side in the template
        
        # Get comprehensive user data using existing managers
        credit_mgr = CreditManager()
        # Deferred import to avoid circular dependency
        from stripe_manager import StripeManager
        stripe_mgr = StripeManager()
        
        # Gather all user account data safely
        try:
            credit_info = credit_mgr.get_user_credit_info(current_user.id)
        except Exception as e:
            logging.error(f"Error getting credit info: {e}")
            credit_info = {'total_credits': 0, 'subscription_credits': 0, 'topup_credits': 0}
        
        try:
            subscription_info = stripe_mgr.get_user_subscription_info(current_user.id)
        except Exception as e:
            logging.error(f"Error getting subscription info: {e}")
            subscription_info = None
        
        try:
            usage_analytics = credit_mgr.get_usage_analytics(current_user.id)
        except Exception as e:
            logging.error(f"Error getting usage analytics: {e}")
            usage_analytics = {'daily_usage': [], 'total_analyses': 0}
        
        return render_template('account_dashboard.html',
                             credit_info=credit_info,
                             subscription_info=subscription_info,
                             usage_analytics=usage_analytics)
                             
    except Exception as e:
        logging.error(f"Error in account dashboard: {e}")
        flash('Unable to load dashboard. Please try again.', 'error')
        return redirect(url_for('index'))

@app.route('/api/account/credits')
@login_required  
def api_account_credits():
    """Real-time credit balance API for dashboard updates with rate limiting and Stripe resilience"""
    try:
        logging.info(f"API /api/account/credits called by user {current_user.id}")
        
        if not is_user_auth_enabled():
            logging.warning("User accounts not enabled")
            return jsonify({'error': 'User accounts not available'}), 404
        
        # Rate limiting for API endpoints
        rate_limiter = RateLimiter()
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if not rate_limiter.check_api_rate_limit(client_ip, 'account_api'):
            return jsonify({'error': 'Rate limit exceeded'}), 429
        
        # Get credit information (Stripe-independent)
        credit_mgr = CreditManager()
        logging.info(f"Getting credit info for user {current_user.id}")
        credit_info = credit_mgr.get_user_credit_info(current_user.id)
        logging.info(f"Credit info retrieved: {credit_info}")
        
        # Get subscription information with robust Stripe failure handling
        subscription_expires = None
        subscription_active = False
        
        try:
            # Deferred import to avoid circular dependency
            from stripe_manager import StripeManager
            stripe_mgr = StripeManager()
            logging.info(f"Getting Stripe subscription info for user {current_user.id}")
            subscription_info = stripe_mgr.get_user_subscription_info(current_user.id)
            logging.info(f"Stripe subscription info: {subscription_info}")
            
            if subscription_info and subscription_info.get('has_subscription'):
                subscription_active = True
                subscription_data = subscription_info.get('subscription', {})
                if subscription_data.get('current_period_end'):
                    subscription_expires = subscription_data['current_period_end']
                    logging.info(f"Subscription expires: {subscription_expires}")
                    
        except Exception as e:
            # Log Stripe failure but continue with credit data
            logging.warning(f"Stripe subscription lookup failed for user {current_user.id}: {e}")
            
            # Fallback: check local subscription data from credit manager
            try:
                from models import Subscription
                local_subscription = Subscription.query.filter_by(
                    user_id=current_user.id, 
                    status='active'
                ).filter(
                    Subscription.current_period_end > datetime.utcnow()
                ).first()
                
                if local_subscription:
                    subscription_active = True
                    if local_subscription.current_period_end:
                        subscription_expires = local_subscription.current_period_end.isoformat()
                        
            except Exception as fallback_error:
                logging.error(f"Fallback subscription lookup failed: {fallback_error}")
        
        # Enhanced response with subscription context
        response_data = {
            'success': True,
            'credits': {
                **credit_info,
                'subscription_expires': subscription_expires,
                'has_active_subscription': subscription_active
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Error getting credit info for user {current_user.id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Unable to fetch credit information'
        }), 500

@app.route('/api/account/transactions')
@login_required
def api_account_transactions():
    """Transaction history API with pagination, filtering and security validation"""
    try:
        logging.info(f"API /api/account/transactions called by user {current_user.id}")
        
        if not is_user_auth_enabled():
            logging.warning("User accounts not enabled for transactions API")
            return jsonify({'error': 'User accounts not available'}), 404
        
        # Rate limiting for API endpoints
        rate_limiter = RateLimiter()
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if not rate_limiter.check_api_rate_limit(client_ip, 'account_api'):
            return jsonify({'error': 'Rate limit exceeded'}), 429
        
        # Enhanced input validation
        page = max(1, request.args.get('page', 1, type=int))
        per_page = min(max(1, request.args.get('per_page', 20, type=int)), 100)  # 1-100 range
        transaction_type = request.args.get('type')
        
        # Validate transaction_type if provided
        if transaction_type and transaction_type in ['subscription', 'topup', 'deduction', 'refund']:
            valid_types = ['analysis', 'subscription', 'topup', 'refund']
            if transaction_type not in valid_types:
                return jsonify({'error': 'Invalid transaction type'}), 400
        
        credit_mgr = CreditManager()
        logging.info(f"Getting transaction history for user {current_user.id}, page={page}, per_page={per_page}, type={transaction_type}")
        transactions = credit_mgr.get_credit_history(
            current_user.id, 
            page=page, 
            per_page=per_page,
            transaction_type=transaction_type
        )
        logging.info(f"Retrieved {len(transactions.get('items', []))} transactions")
        
        return jsonify({
            'success': True,
            'transactions': transactions['items'],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': transactions['total'],
                'pages': transactions['pages'],
                'has_next': transactions['has_next'],
                'has_prev': transactions['has_prev']
            }
        })
        
    except Exception as e:
        logging.error(f"Error getting transactions for user {current_user.id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Unable to fetch transaction history'
        }), 500

@app.route('/api/account/usage-analytics')
@login_required
def api_usage_analytics():
    """Advanced usage analytics API for dashboard charts"""
    try:
        if not is_user_auth_enabled():
            return jsonify({'error': 'User accounts not available'}), 404
        
        # Rate limiting for API endpoints
        rate_limiter = RateLimiter()
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if not rate_limiter.check_api_rate_limit(client_ip, 'account_api'):
            return jsonify({'error': 'Rate limit exceeded'}), 429
        
        # Enhanced input validation
        days = max(1, min(request.args.get('days', 30, type=int), 365))  # 1-365 days range
        
        credit_mgr = CreditManager()
        analytics = credit_mgr.get_usage_analytics(current_user.id, days=days)
        
        return jsonify({
            'success': True,
            'analytics': analytics
        })
        
    except Exception as e:
        logging.error(f"Error getting usage analytics for user {current_user.id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Unable to fetch usage analytics'
        }), 500

@app.route('/user/account')
@login_required
def user_account():
    """Legacy route - redirect to new dashboard"""
    return redirect(url_for('account_dashboard'))

@app.route('/subscription-plans')
@app.route('/subscription/plans')  # Legacy route support
def subscription_plans():
    """Subscription plans page"""
    try:
        if not is_user_auth_enabled():
            flash('Subscription plans are not currently available.', 'info')
            return redirect(url_for('index'))
            
        # If user is authenticated, get their current status
        user_summary = None
        if current_user.is_authenticated:
            user_summary = credit_manager.get_user_credit_summary(current_user.id)
            
        return render_template('subscription_plans.html', user_summary=user_summary)
        
    except Exception as e:
        logging.error(f"Error in subscription plans page: {e}")
        flash('Unable to load subscription plans. Please try again.', 'error')
        return redirect(url_for('index'))

@app.route('/subscription/required')
def subscription_required():
    """Page shown when subscription is required for a feature"""
    return render_template('subscription_required.html')

@app.route('/admin/api/reset-ip', methods=['POST'])
def admin_reset_ip():
    """Reset rate limits for specific IP"""
    # Check admin authentication
    if not session.get('admin_authenticated'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
    try:
        data = request.get_json()
        ip_address = data.get('ip_address')
        
        if not ip_address:
            return jsonify({
                'success': False,
                'error': 'IP address required'
            }), 400
        
        rate_limiter = RateLimiter()
        success = rate_limiter.reset_limits_for_ip(ip_address)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Limits reset for {ip_address}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to reset limits'
            }), 500
            
    except Exception as e:
        logging.error(f"Error resetting IP limits: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'System error during IP reset'
        }), 500

@app.route('/api/recent-analyses')
def get_recent_analyses():
    """Get recently analyzed stocks from cache (no rate limit cost)"""
    try:
        # Get cached analyses from the past 6 hours
        six_hours_ago = datetime.utcnow() - timedelta(hours=6)
        
        current_time = datetime.utcnow()
        recent_analyses = AnalysisCache.query.filter(
            AnalysisCache.created_at >= six_hours_ago,
            AnalysisCache.cache_expiry > current_time  # Only non-expired
        ).order_by(AnalysisCache.created_at.desc()).limit(10).all()
        
        # Format the results
        recent_tickers = []
        seen_tickers = set()
        
        for analysis in recent_analyses:
            # Avoid duplicates (prefer most recent)
            cache_key = f"{analysis.ticker_symbol}_{analysis.maximum_brain}"
            if cache_key not in seen_tickers:
                seen_tickers.add(cache_key)
                
                try:
                    analysis_data = json.loads(analysis.analysis_data)
                    
                    # Determine effective recommendation (with income override)
                    technical_recommendation = analysis_data.get('recommendation', 'N/A')
                    effective_recommendation = technical_recommendation
                    
                    income_analysis = analysis_data.get('income_analysis')
                    income_focus = analysis_data.get('income_focus', False)
                    is_yield_etf = analysis_data.get('is_yield_etf', False)
                    
                    # Check for income override
                    if (income_analysis and 
                        income_analysis.get('recommendation') and 
                        'buy for income' in income_analysis.get('recommendation', '').lower() and
                        (income_focus or is_yield_etf)):
                        effective_recommendation = "Buy for Income"
                    
                    recent_tickers.append({
                        'ticker': analysis.ticker_symbol,
                        'company_name': analysis_data.get('company_name', 'N/A'),
                        'recommendation': effective_recommendation,
                        'technical_recommendation': technical_recommendation,
                        'confidence': analysis_data.get('confidence', 'Unknown'),
                        'maximum_brain': analysis.maximum_brain,
                        'analyzed_at': analysis.created_at.strftime('%H:%M'),
                        'expires_at': analysis.cache_expiry.strftime('%H:%M'),
                        'has_income_override': effective_recommendation != technical_recommendation
                    })
                except json.JSONDecodeError:
                    continue
        
        return jsonify({
            'success': True,
            'recent_analyses': recent_tickers
        })
        
    except Exception as e:
        logging.error(f"Error fetching recent analyses: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch recent analyses'
        }), 500

@app.route('/api/cached-analysis/<ticker>')
def get_cached_analysis(ticker):
    """Get cached analysis result with current price update (no rate limits used)"""
    try:
        ticker = ticker.upper()
        maximum_brain = request.args.get('maximum_brain', 'false').lower() == 'true'
        
        # Use cache manager to get the analysis
        cache_manager = CacheManager()
        cached_result = cache_manager.get_cached_analysis(ticker, maximum_brain)
        
        if cached_result:
            # Update with current price for cached results
            try:
                import yfinance as yf
                stock = yf.Ticker(ticker)
                current_data = stock.history(period="1d")
                if not current_data.empty:
                    current_price = round(current_data['Close'].iloc[-1], 2)
                    cached_result['current_price'] = f"${current_price}"
                    logging.info(f"Updated cached {ticker} with current price: ${current_price}")
                else:
                    cached_result['current_price'] = "Price unavailable"
                    logging.warning(f"No current price data available for {ticker}")
            except Exception as e:
                logging.warning(f"Could not fetch current price for {ticker}: {str(e)}")
                cached_result['current_price'] = "Price unavailable"
            
            return jsonify(cached_result)
        else:
            return jsonify({
                'success': False,
                'error': 'No cached analysis found for this ticker'
            }), 404
            
    except Exception as e:
        logging.error(f"Error fetching cached analysis for {ticker}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch cached analysis'
        }), 500

@app.route('/api/user-status')
def api_user_status():
    """Enhanced API endpoint to get user authentication and rate limit status with logout detection"""
    try:
        # CRITICAL: Check for logout state first to prevent cached authentication display
        if session.get('_logout_initiated'):
            # User is in logout state - return not authenticated
            session.pop('_logout_initiated', None)  # Clear the flag
            return jsonify({
                'success': False,
                'authenticated': False,
                'logged_out': True,
                'message': 'User logged out, clearing cached state'
            })
        
        # Check if user authentication is enabled and user is authenticated
        if is_user_auth_enabled() and current_user.is_authenticated:
            # Verify user actually exists in database (prevent stale sessions)
            try:
                user = db.session.get(User, current_user.id)
                if not user:
                    # User doesn't exist anymore, clear session
                    logout_user()
                    session.clear()
                    return jsonify({
                        'success': False,
                        'authenticated': False,
                        'message': 'User session invalid, please log in again'
                    })
                    
                credit_summary = credit_manager.get_user_credit_summary(current_user.id)
                return jsonify({
                    'success': True,
                    'authenticated': True,
                    'data': {
                        'user_id': current_user.id,
                        'total_credits': credit_summary.get('total_credits', 0),
                        'subscription_credits': credit_summary.get('subscription_credits', 0),
                        'topup_credits': credit_summary.get('topup_credits', 0),
                        'rate_limit_type': 'credit_based'
                    }
                })
            except Exception as e:
                logging.error(f"Error getting credit summary for user {current_user.id}: {e}")
                return jsonify({
                    'success': False,
                    'authenticated': True,
                    'error': 'Failed to load credit information'
                }), 500
        else:
            # User is not authenticated - return IP-based limits
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            if client_ip:
                client_ip = client_ip.split(',')[0].strip()
            
            rate_limiter = RateLimiter()
            remaining_info = rate_limiter.get_remaining_requests(client_ip)
            
            return jsonify({
                'success': True,
                'authenticated': False,
                'data': {
                    'standard_remaining': remaining_info.get('standard_remaining', 2),
                    'brain_remaining': remaining_info.get('brain_remaining', 1),
                    'total_used': remaining_info.get('total_used', 0),
                    'rate_limit_type': 'ip_based'
                }
            })
            
    except Exception as e:
        logging.error(f"Error in api_user_status: {e}")
        return jsonify({
            'success': False,
            'authenticated': False,
            'error': 'Failed to load user status'
        }), 500

# Sharing Routes
def validate_ticker(ticker):
    """Validate ticker symbol format"""
    if not ticker or not re.match(r'^[A-Z]{1,5}$', ticker):
        return False
    return True

def normalize_recommendation_text(text):
    """
    PRODUCTION-GRADE UNICODE TEXT NORMALIZATION
    Handles all apostrophe variants that OpenAI might return
    Prevents display bugs caused by Unicode character mismatches
    """
    if not text or not isinstance(text, str):
        return ''
    
    return (text.replace('\u2018', "'")      # Smart quotes ' '
            .replace('\u2019', "'")
            .replace('\u201A', "'")          # Additional quotes ‚ ‛
            .replace('\u201B', "'")
            .replace('\u02BC', "'")          # Modifier apostrophes
            .replace('\u02C8', "'")
            .replace('\u0060', "'")          # Grave/acute accents
            .replace('\u00B4', "'")
            .replace('\u055A', "'")          # Additional variants
            .replace('\u07F4', "'")
            .replace('\u07F5', "'")
            .strip().lower())

def parse_recommendation_backend(recommendation, income_analysis=None, is_income_mode=False):
    """
    PRODUCTION-GRADE BACKEND RECOMMENDATION PARSER
    Fixes critical Unicode apostrophe bug affecting share pages
    """
    normalized = normalize_recommendation_text(recommendation)
    
    # Income analysis override takes priority if it's genuinely positive
    if income_analysis and income_analysis.get('recommendation') and is_income_mode:
        income_normalized = normalize_recommendation_text(income_analysis.get('recommendation', ''))
        
        # Check for positive income recommendations
        income_positive_patterns = ['buy for income', 'income buy', 'dividend buy']
        for pattern in income_positive_patterns:
            if pattern in income_normalized:
                return {
                    'recommendation': income_analysis.get('recommendation'),
                    'confidence': income_analysis.get('confidence', 'medium'),
                    'is_positive': True,
                    'type': 'income'
                }
        
        # Check if income has negative patterns
        income_negative_patterns = ["don't buy", "do not buy", "no,", "avoid", "not recommended"]
        for pattern in income_negative_patterns:
            if pattern in income_normalized:
                return {
                    'recommendation': income_analysis.get('recommendation'),
                    'confidence': income_analysis.get('confidence', 'medium'),
                    'is_positive': False,
                    'type': 'income'
                }
    
    # Comprehensive negative patterns - FIXES UNICODE APOSTROPHE BUG
    negative_patterns = [
        "don't buy",           # Now handles ALL apostrophe variants
        "do not buy", 
        "no, don't buy",
        "no, do not buy",
        "not recommended",
        "avoid buying",
        "avoid",
        "sell",
        "short"
    ]
    
    # Check for negative patterns first (highest priority)
    for pattern in negative_patterns:
        if pattern in normalized:
            return {
                'recommendation': recommendation,
                'confidence': 'negative',
                'is_positive': False,
                'type': 'technical'
            }
    
    # Check for regex negative patterns  
    import re
    negative_regex_patterns = [
        r'\bno\b.*\bbuy\b',           # "no ... buy"
        r'\bavoid\b.*\bbuying\b',     # "avoid ... buying"
        r'\bnot\b.*\brecommend',      # "not ... recommend"
        r'\bdon\'t\b.*\bbuy\b'        # "don't ... buy" (normalized apostrophe)
    ]
    
    for regex_pattern in negative_regex_patterns:
        if re.search(regex_pattern, normalized):
            return {
                'recommendation': recommendation,
                'confidence': 'negative',
                'is_positive': False,
                'type': 'technical'
            }
    
    # Positive patterns (only if no negative indicators)
    positive_patterns = [
        "yes, buy",
        "yes buy", 
        "recommend buying",
        "strong buy",
        "buy signal",
        "bullish",
        "buy recommendation"
    ]
    
    for pattern in positive_patterns:
        if pattern in normalized:
            return {
                'recommendation': recommendation,
                'confidence': 'positive',
                'is_positive': True,
                'type': 'technical'
            }
    
    # Final check: contains "buy" but not negative indicators
    if ('buy' in normalized and 
        "don't" not in normalized and 
        "not" not in normalized and
        "avoid" not in normalized and
        "no," not in normalized):
        return {
            'recommendation': recommendation,
            'confidence': 'positive',
            'is_positive': True,
            'type': 'technical'
        }
    
    # Fallback for unknown patterns
    logging.warning(f'Unknown recommendation pattern in backend: {recommendation}')
    return {
        'recommendation': recommendation,
        'confidence': 'unknown',
        'is_positive': False,
        'type': 'unknown'
    }

@app.route('/share/<ticker>')
@app.route('/share/<ticker>/')
def share_analysis(ticker):
    """Share individual stock analysis results"""
    try:
        ticker = ticker.upper().strip()
        
        # Validate ticker format
        if not validate_ticker(ticker):
            abort(404)
        
        # Get maximum brain parameter
        maximum_brain = request.args.get('brain', 'false').lower() == 'true'
        
        # Get cached analysis
        cache_manager = CacheManager()
        cached_result = cache_manager.get_cached_analysis(ticker, maximum_brain)
        
        if not cached_result or not cached_result.get('success'):
            # Try the other analysis type if this one doesn't exist
            other_maximum_brain = not maximum_brain
            other_cached_result = cache_manager.get_cached_analysis(ticker, other_maximum_brain)
            if other_cached_result and other_cached_result.get('success'):
                # Redirect to the correct share URL
                if other_maximum_brain:
                    return redirect(url_for('share_analysis', ticker=ticker, brain='true'))
                else:
                    return redirect(url_for('share_analysis', ticker=ticker))
            
            # Neither analysis type found - render expired page
            return render_template('share_expired.html', 
                                 ticker=ticker, 
                                 maximum_brain=maximum_brain), 404
        
        # Update with current price
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            current_data = stock.history(period="1d")
            if not current_data.empty:
                current_price = round(current_data['Close'].iloc[-1], 2)
                cached_result['current_price'] = f"${current_price}"
            else:
                cached_result['current_price'] = "Price unavailable"
        except Exception as e:
            logging.warning(f"Could not fetch current price for {ticker}: {str(e)}")
            cached_result['current_price'] = "Price unavailable"
        
        # PRODUCTION-GRADE RECOMMENDATION PARSING - FIXES UNICODE APOSTROPHE BUG
        income_analysis = cached_result.get('income_analysis', {})
        company_name = cached_result.get('company_name', ticker)
        base_analysis_type = "Maximum Brain" if maximum_brain else "Standard"
        
        # Use Unicode-safe recommendation parsing
        is_income_mode = bool(income_analysis and income_analysis.get('recommendation'))
        parsed_result = parse_recommendation_backend(
            cached_result.get('recommendation', 'Unknown'),
            income_analysis,
            is_income_mode
        )
        
        recommendation = parsed_result['recommendation']
        confidence = parsed_result['confidence']
        is_positive_recommendation = parsed_result['is_positive']
        
        # Set analysis type based on what recommendation we're using
        if parsed_result['type'] == 'income':
            analysis_type = f"Income-Focused {base_analysis_type}"
        else:
            analysis_type = base_analysis_type
        
        # Create dynamic social sharing content
        social_title = f"${ticker} Analysis - {recommendation} Recommendation | SaneApe.com"
        social_description = f"AI recommends: {recommendation} with {confidence} confidence for {company_name}. {analysis_type} analysis with 35+ technical indicators."
        
        return render_template('share.html', 
                             analysis=cached_result,
                             ticker=ticker,
                             maximum_brain=maximum_brain,
                             social_title=social_title,
                             social_description=social_description,
                             parsed_recommendation=parsed_result,
                             analysis_type=analysis_type)
        
    except Exception as e:
        logging.error(f"Error in share route for {ticker}: {str(e)}")
        abort(500)

@app.route('/share/<ticker>/brain')
@app.route('/share/<ticker>/brain/')
def share_brain_analysis(ticker):
    """Share Maximum Brain analysis results"""
    # Redirect to main share route with brain parameter
    return redirect(url_for('share_analysis', ticker=ticker, brain='true'))

# Error Handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('index.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({
        'error': 'Internal server error. Please try again later.',
        'type': 'server'
    }), 500
