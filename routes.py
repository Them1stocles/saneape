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
from stripe_manager import StripeManager
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
                
                # Calculate revenue (approximate)
                from stripe_manager import SubscriptionPlan
                monthly_revenue = monthly_subscriptions * 500 + weekly_subscriptions * 125  # in cents
                
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
        subscriptions = db.session.query(Subscription).join(User).all()
        
        subscription_data = []
        for sub in subscriptions:
            subscription_data.append({
                'id': sub.id,
                'user_id': sub.user_id,
                'user_display_name': sub.user.display_name,
                'user_email': sub.user.email,
                'user_profile_image': sub.user.profile_image_url,
                'stripe_subscription_id': sub.stripe_subscription_id,
                'plan_type': sub.plan_type,
                'status': sub.status,
                'amount': 500 if sub.plan_type == 'monthly' else 125,  # Amount in cents
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
    """Real-time credit balance API for dashboard updates with rate limiting"""
    try:
        if not is_user_auth_enabled():
            return jsonify({'error': 'User accounts not available'}), 404
        
        # Rate limiting for API endpoints
        rate_limiter = RateLimiter()
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if not rate_limiter.check_api_rate_limit(client_ip, 'account_api'):
            return jsonify({'error': 'Rate limit exceeded'}), 429
        
        credit_mgr = CreditManager()
        credit_info = credit_mgr.get_user_credit_info(current_user.id)
        
        return jsonify({
            'success': True,
            'credits': credit_info
        })
        
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
        if not is_user_auth_enabled():
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
        transactions = credit_mgr.get_credit_history(
            current_user.id, 
            page=page, 
            per_page=per_page,
            transaction_type=transaction_type or 'all' if transaction_type else None
        )
        
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
            AnalysisCache.created_at >= six_hours_ago
        ).filter(
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
    """API endpoint for user status information"""
    try:
        # Get client IP
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # Direct database query for accurate status
        today = date.today()
        rate_limit = RateLimit.query.filter_by(
            ip_address=client_ip,
            date_created=today
        ).first()
        
        if rate_limit:
            standard_remaining = max(0, 6 - rate_limit.request_count)
            brain_remaining = max(0, 2 - rate_limit.maximum_brain_count)
        else:
            standard_remaining = 6
            brain_remaining = 2
        
        return jsonify({
            'success': True,
            'data': {
                'standard_remaining': standard_remaining,
                'brain_remaining': brain_remaining,
                'total_used': (rate_limit.request_count + rate_limit.maximum_brain_count) if rate_limit else 0
            }
        })
    except Exception as e:
        app.logger.error(f"Error getting user status: {str(e)}")
        return jsonify({
            'error': 'Failed to get user status',
            'success': False
        }), 500

# Sharing Routes
def validate_ticker(ticker):
    """Validate ticker symbol format"""
    if not ticker or not re.match(r'^[A-Z]{1,5}$', ticker):
        return False
    return True

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
        
        # Prepare social meta data - prioritize income analysis if available
        income_analysis = cached_result.get('income_analysis', {})
        income_recommendation = income_analysis.get('recommendation', '')
        company_name = cached_result.get('company_name', ticker)
        base_analysis_type = "Maximum Brain" if maximum_brain else "Standard"
        
        # Use income analysis recommendation if it's a positive "Buy" recommendation
        if income_recommendation and 'buy' in income_recommendation.lower():
            recommendation = income_recommendation
            confidence = income_analysis.get('confidence', 'medium')
            analysis_type = f"Income-Focused {base_analysis_type}"
        else:
            # Fall back to technical analysis
            recommendation = cached_result.get('recommendation', 'Unknown')
            confidence = cached_result.get('confidence', 'Unknown')
            analysis_type = base_analysis_type
        
        # Create dynamic social sharing content
        social_title = f"${ticker} Analysis - {recommendation} Recommendation | SaneApe.com"
        social_description = f"AI recommends: {recommendation} with {confidence} confidence for {company_name}. {analysis_type} analysis with 35+ technical indicators."
        
        return render_template('share.html', 
                             analysis=cached_result,
                             ticker=ticker,
                             maximum_brain=maximum_brain,
                             social_title=social_title,
                             social_description=social_description)
        
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
