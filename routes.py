from flask import render_template, request, jsonify, flash, redirect, url_for
from app import app, db
import logging
from stock_analyzer import StockAnalyzer
from rate_limiter import RateLimiter
from models import StockAnalysis, SystemLimits, RateLimit, AnalysisCache
from cost_manager import CostManager
from cache_manager import CacheManager
from security_monitor import SecurityMonitor
from datetime import date, datetime, timedelta
import json

@app.route('/')
def index():
    """Main application page with rate limit information"""
    try:
        # Get client IP
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # Get remaining requests for this IP
        rate_limiter = RateLimiter()
        remaining_info = rate_limiter.get_remaining_requests(client_ip)
        
        return render_template('index.html', remaining_requests=remaining_info)
        
    except Exception as e:
        logging.error(f"Error in index route: {str(e)}")
        return render_template('index.html', remaining_requests=None)

@app.route('/analyze', methods=['POST'])
def analyze_stock():
    """Enhanced stock analysis with comprehensive protection"""
    client_ip = None
    try:
        # Get client IP
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # Get ticker and maximum brain option from form
        ticker = request.form.get('ticker', '').strip().upper()
        maximum_brain = request.form.get('maximum_brain') == 'true'
        
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
        
        # Simple rate limit check first (performance critical)
        rate_limiter = RateLimiter()
        
        # Quick IP-based rate limit check
        today = date.today()
        rate_limit = RateLimit.query.filter_by(
            ip_address=client_ip,
            date_created=today
        ).first()
        
        if rate_limit:
            if maximum_brain and rate_limit.maximum_brain_count >= 1:
                return jsonify({
                    'error': 'Maximum Brain analysis limit exceeded. You can only make 1 Maximum Brain analysis per day.',
                    'type': 'rate_limit'
                }), 429
            elif not maximum_brain and rate_limit.request_count >= 2:
                return jsonify({
                    'error': 'Daily limit exceeded. You can only make 2 requests per day.',
                    'type': 'rate_limit'
                }), 429
        
        # Proceed with analysis
        analyzer = StockAnalyzer()
        result = analyzer.analyze_stock(ticker, maximum_brain)
        
        if result['success']:
            # Record the successful request (simple database update)
            if rate_limit:
                if maximum_brain:
                    rate_limit.maximum_brain_count += 1
                else:
                    rate_limit.request_count += 1
                rate_limit.last_request = datetime.utcnow()
            else:
                rate_limit = RateLimit()
                rate_limit.ip_address = client_ip
                rate_limit.request_count = 1 if not maximum_brain else 0
                rate_limit.maximum_brain_count = 1 if maximum_brain else 0
                rate_limit.last_request = datetime.utcnow()
                rate_limit.date_created = today
                db.session.add(rate_limit)
            
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
            
            return jsonify(result)
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
    return render_template('admin.html')

@app.route('/admin/api/dashboard')
def admin_api_dashboard():
    """API endpoint for dashboard data"""
    try:
        rate_limiter = RateLimiter()
        system_status = rate_limiter.get_system_status()
        
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

@app.route('/admin/api/emergency-stop', methods=['POST'])
def admin_emergency_stop():
    """Emergency stop endpoint"""
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

@app.route('/admin/api/update-limit', methods=['POST'])
def admin_update_limit():
    """Update daily spending limit"""
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

@app.route('/admin/api/reset-ip', methods=['POST'])
def admin_reset_ip():
    """Reset rate limits for specific IP"""
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
        
        recent_analyses = AnalysisCache.query.filter(
            AnalysisCache.created_at >= six_hours_ago,
            AnalysisCache.cache_expiry > datetime.utcnow()  # Only non-expired
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
                    recent_tickers.append({
                        'ticker': analysis.ticker_symbol,
                        'company_name': analysis_data.get('company_name', 'N/A'),
                        'recommendation': analysis_data.get('recommendation', 'N/A'),
                        'confidence': analysis_data.get('confidence', 'Unknown'),
                        'maximum_brain': analysis.maximum_brain,
                        'analyzed_at': analysis.created_at.strftime('%H:%M'),
                        'expires_at': analysis.cache_expiry.strftime('%H:%M')
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
    """Get cached analysis result without using rate limits"""
    try:
        ticker = ticker.upper()
        maximum_brain = request.args.get('maximum_brain', 'false').lower() == 'true'
        
        # Use cache manager to get the analysis
        cache_manager = CacheManager()
        cached_result = cache_manager.get_cached_analysis(ticker, maximum_brain)
        
        if cached_result:
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
            standard_remaining = max(0, 2 - rate_limit.request_count)
            brain_remaining = max(0, 1 - rate_limit.maximum_brain_count)
        else:
            standard_remaining = 2
            brain_remaining = 1
        
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
        
        rate_limiter = RateLimiter()
        remaining_info = rate_limiter.get_remaining_requests(client_ip)
        
        return jsonify({
            'success': True,
            'data': remaining_info
        })
        
    except Exception as e:
        logging.error(f"Error getting user status: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve user status'
        }), 500

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
