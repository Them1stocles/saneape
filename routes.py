from flask import render_template, request, jsonify, flash, redirect, url_for
from app import app, db
import logging
from stock_analyzer import StockAnalyzer
from rate_limiter import RateLimiter
from models import StockAnalysis, SystemLimits
from cost_manager import CostManager
from cache_manager import CacheManager
from security_monitor import SecurityMonitor
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
        
        # Initialize enhanced rate limiter
        rate_limiter = RateLimiter()
        
        # Check cache first (saves API calls and costs)
        cached_result = rate_limiter.check_cache_first(ticker, maximum_brain)
        if cached_result:
            return jsonify(cached_result)
        
        # Check all rate limits and protections
        allowed, error_msg = rate_limiter.is_allowed(client_ip, maximum_brain)
        if not allowed:
            return jsonify({
                'error': error_msg,
                'type': 'rate_limit'
            }), 429
        
        # Proceed with analysis
        analyzer = StockAnalyzer()
        result = analyzer.analyze_stock(ticker, maximum_brain)
        
        if result['success']:
            # Record the successful request (updates all tracking systems)
            rate_limiter.record_request(client_ip, maximum_brain)
            
            # Cache the result for 6 hours
            rate_limiter.cache_result(ticker, result, maximum_brain)
            
            # Save analysis to database
            analysis = StockAnalysis()
            analysis.ticker = ticker
            analysis.ip_address = client_ip
            analysis.recommendation = result['recommendation']
            analysis.confidence = result['confidence']
            analysis.analysis_data = json.dumps(result['analysis_details'])
            analysis.maximum_brain = maximum_brain
            db.session.add(analysis)
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

@app.route('/api/user-status')
def api_user_status():
    """API endpoint for user status information"""
    try:
        # Get client IP
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
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
