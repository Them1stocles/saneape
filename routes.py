from flask import render_template, request, jsonify, flash, redirect, url_for, session
from app import app
from extensions import db
import logging
from stock_analyzer import StockAnalyzer
from rate_limiter import RateLimiter
from models import StockAnalysis, SystemLimits, RateLimit, AnalysisCache
from cost_manager import CostManager
from cache_manager import CacheManager
from security_monitor import SecurityMonitor
from datetime import date, datetime
import json
import os

# Initialize managers
rate_limiter = RateLimiter()
cost_manager = CostManager()
cache_manager = CacheManager()
security_monitor = SecurityMonitor()

@app.route('/')
def index():
    """Main page with IP-based rate limiting info"""
    try:
        # Get client IP
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # Get remaining requests for this IP
        remaining_info = rate_limiter.get_remaining_requests(client_ip)
        
        return render_template('index.html', remaining_requests=remaining_info)
        
    except Exception as e:
        logging.error(f"Error in index route: {str(e)}")
        return render_template('index.html', remaining_requests=None)

@app.route('/analyze', methods=['POST'])
def analyze_stock():
    """Stock analysis endpoint"""
    client_ip = None
    try:
        # Get client IP
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # Get ticker and analysis options from form or JSON
        if request.is_json:
            data = request.get_json()
            ticker = data.get('ticker', '').strip().upper()
            maximum_brain = data.get('maximum_brain') == 'maximum_brain' or data.get('mode') == 'maximum_brain'
            income_focus = data.get('income_focus') == 'true' or data.get('mode') == 'income'
        else:
            ticker = request.form.get('ticker', '').strip().upper()
            maximum_brain = request.form.get('maximum_brain') == 'true'
            income_focus = request.form.get('income_focus') == 'true'
        
        # Validate input
        if not ticker:
            return jsonify({'error': 'Please enter a stock ticker symbol.', 'type': 'validation'}), 400
        
        if not ticker.isalpha() or len(ticker) > 5:
            security_monitor.log_security_event(client_ip, SecurityMonitor.INVALID_INPUT, f"Invalid ticker: {ticker}")
            return jsonify({'error': 'Please enter a valid stock ticker symbol (letters only, max 5 characters).', 'type': 'validation'}), 400
        
        # Admin bypass check
        is_admin = session.get('admin_authenticated', False)
        
        if not is_admin:
            # Rate limit check
            allowed, error_message = rate_limiter.is_allowed(client_ip, maximum_brain, ticker)
            if not allowed:
                return jsonify({'error': error_message, 'type': 'rate_limit'}), 429
        
        # Check cache first
        cached_result = cache_manager.get_cached_analysis(ticker, maximum_brain)
        if cached_result:
            logging.info(f"Serving cached result for {ticker}")
            # Even for cache hits, we might want to track usage if we were strict, but for now let's be generous with cache
            return jsonify(cached_result)

        # Proceed with analysis
        analyzer = StockAnalyzer()
        result = analyzer.analyze_stock(ticker, maximum_brain, income_focus)
        
        if result['success']:
            # Record the successful API call for cost tracking
            cost_manager.record_api_call(maximum_brain)
            
            # Record request for rate limiting (if not admin)
            if not is_admin:
                rate_limiter.record_request(client_ip, maximum_brain)
            
            # Save analysis to database
            analysis = StockAnalysis()
            analysis.ticker = ticker
            analysis.ip_address = client_ip
            analysis.recommendation = result['recommendation']
            analysis.confidence = result['confidence']
            analysis.analysis_data = json.dumps(result['analysis_details'])
            analysis.maximum_brain = maximum_brain
            db.session.add(analysis)
            
            # Store in cache
            cache_manager.store_analysis(ticker, result, maximum_brain)
            
            db.session.commit()
            
            return jsonify(result)
        else:
            return jsonify({'error': result['error'], 'type': 'analysis'}), 400
            
    except Exception as e:
        logging.error(f"Error in analyze_stock: {str(e)}")
        if client_ip:
            security_monitor.log_security_event(client_ip, "system_error", str(e))
        return jsonify({'error': 'An unexpected error occurred. Please try again later.', 'type': 'server'}), 500

# Admin Routes
@app.route('/admin')
def admin_dashboard():
    """Admin dashboard"""
    if not session.get('admin_authenticated'):
        return redirect(url_for('admin_login'))
    return render_template('admin.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'Fluent1!') # Fallback for dev
        
        if password == admin_password:
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
    """API endpoint for dashboard data"""
    if not session.get('admin_authenticated'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
    try:
        system_status = rate_limiter.get_system_status()
        return jsonify({'success': True, 'data': system_status})
    except Exception as e:
        logging.error(f"Error getting dashboard data: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to retrieve dashboard data'}), 500

@app.route('/admin/api/emergency-stop', methods=['POST'])
def admin_emergency_stop():
    """Emergency stop endpoint"""
    if not session.get('admin_authenticated'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
    try:
        success = cost_manager.set_emergency_stop(True)
        return jsonify({'success': success, 'message': 'Emergency stop activated' if success else 'Failed'})
    except Exception as e:
        logging.error(f"Error activating emergency stop: {str(e)}")
        return jsonify({'success': False, 'error': 'System error'}), 500
