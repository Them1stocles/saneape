from flask import render_template, request, jsonify, flash, redirect, url_for, session
from app import app
from extensions import db
import logging
from stock_analyzer import StockAnalyzer
from rate_limiter import RateLimiter
from models import StockAnalysis, SystemLimits, RateLimit, AnalysisCache, AnalysisJob
from cost_manager import CostManager
from cache_manager import CacheManager
from security_monitor import SecurityMonitor
from datetime import date, datetime
import json
import os
import threading
import uuid
import uuid
import shortuuid
import time

# Initialize managers
rate_limiter = RateLimiter()
cost_manager = CostManager()
cache_manager = CacheManager()
security_monitor = SecurityMonitor()

def run_analysis_background(job_id, app_context, ticker, maximum_brain):
    """Background worker for running analysis"""
    with app_context:
        try:
            logging.info(f"Starting background analysis for job {job_id}")
            job = db.session.get(AnalysisJob, job_id)
            if not job:
                logging.error(f"Job {job_id} not found")
                return

            job.status = 'processing'
            job.logs = job.logs + [f"Job started for {ticker}..."]
            db.session.commit()

            def progress_callback(msg):
                # Re-fetch job to avoid stale data
                current_job = db.session.get(AnalysisJob, job_id)
                if current_job:
                    current_job.logs = current_job.logs + [msg]
                    db.session.commit()

            analyzer = StockAnalyzer()
            result = analyzer.analyze_stock(ticker, maximum_brain, progress_callback)

            # Re-fetch job one last time
            job = db.session.get(AnalysisJob, job_id)
            
            if result['success']:
                job.status = 'completed'
                job.result = result
                job.logs = job.logs + ["Analysis completed successfully."]
                
                # Record successful API call
                cost_manager.record_api_call(maximum_brain)
                
                # Save to main history table (legacy support)
                analysis = StockAnalysis()
                analysis.ticker = ticker
                analysis.ip_address = 'async_job' # We lose original IP in thread, could pass it if needed
                analysis.recommendation = result['recommendation']
                analysis.confidence = result['confidence']
                analysis.analysis_data = json.dumps(result['analysis_details'])
                analysis.maximum_brain = maximum_brain
                db.session.add(analysis)
                
                # Cache result
                cache_manager.store_analysis(ticker, result, maximum_brain)
                
            else:
                job.status = 'failed'
                job.error = result.get('error', 'Unknown error')
                job.logs = job.logs + [f"Analysis failed: {job.error}"]

            db.session.commit()
            logging.info(f"Job {job_id} finished with status: {job.status}")

        except Exception as e:
            logging.error(f"Background job failed: {str(e)}")
            # Try to record failure
            try:
                job = db.session.get(AnalysisJob, job_id)
                if job:
                    job.status = 'failed'
                    job.error = str(e)
                    job.logs = job.logs + [f"Critical error: {str(e)}"]
                    db.session.commit()
            except:
                pass

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
    """Start async stock analysis"""
    client_ip = None
    try:
        # Get client IP
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # Get ticker and analysis options
        if request.is_json:
            data = request.get_json()
            ticker = data.get('ticker', '').strip().upper()
            maximum_brain = data.get('maximum_brain') == 'maximum_brain' or data.get('mode') == 'maximum_brain'
        else:
            ticker = request.form.get('ticker', '').strip().upper()
            maximum_brain = request.form.get('maximum_brain') == 'true'
        
        # Validate input
        if not ticker:
            return jsonify({'error': 'Please enter a stock ticker symbol.', 'type': 'validation'}), 400
        
        if not ticker.isalpha() or len(ticker) > 5:
            security_monitor.log_security_event(client_ip, SecurityMonitor.INVALID_INPUT, f"Invalid ticker: {ticker}")
            return jsonify({'error': 'Please enter a valid stock ticker symbol (letters only, max 5 characters).', 'type': 'validation'}), 400
        
        # Rate limit check
        is_admin = session.get('admin_authenticated', False)
        if not is_admin:
            allowed, error_message = rate_limiter.is_allowed(client_ip, maximum_brain, ticker)
            if not allowed:
                return jsonify({'error': error_message, 'type': 'rate_limit'}), 429
            rate_limiter.record_request(client_ip, maximum_brain)

        # Check cache first (Fast path)
        cached_result = cache_manager.get_cached_analysis(ticker, maximum_brain)
        if cached_result:
            logging.info(f"Serving cached result for {ticker}")
            return jsonify({'cached': True, 'result': cached_result})

        # Create Job
        job_id = str(uuid.uuid4())
        short_id = shortuuid.ShortUUID().random(length=8)
        
        job = AnalysisJob(
            id=job_id,
            short_id=short_id,
            ticker=ticker,
            mode='maximum_brain' if maximum_brain else 'standard',
            status='pending',
            logs=[f"Request received for {ticker}."]
        )
        db.session.add(job)
        db.session.commit()

        # Spawn background thread
        # We must pass app.app_context() to the thread so it can access the DB
        thread = threading.Thread(
            target=run_analysis_background,
            args=(job_id, app.app_context(), ticker, maximum_brain)
        )
        thread.start()

        return jsonify({
            'job_id': job_id,
            'short_id': short_id,
            'status': 'pending'
        })
            
    except Exception as e:
        logging.error(f"Error in analyze_stock: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred.', 'type': 'server'}), 500

@app.route('/analysis/status/<job_id>', methods=['GET'])
def get_analysis_status(job_id):
    """Poll for job status"""
    try:
        job = db.session.get(AnalysisJob, job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify({
            'status': job.status,
            'logs': job.logs,
            'result': job.result if job.status == 'completed' else None,
            'short_id': job.short_id,
            'error': job.error
        })
    except Exception as e:
        logging.error(f"Error checking status: {str(e)}")
        return jsonify({'error': 'Server error checking status'}), 500

@app.route('/share/<short_id>')
def share_result(short_id):
    """Render a shared analysis result"""
    try:
        # Find job by short_id
        stmt = db.select(AnalysisJob).where(AnalysisJob.short_id == short_id)
        job = db.session.execute(stmt).scalar_one_or_none()
        
        if not job:
            return render_template('share_result.html', error="Analysis not found"), 404
            
        if job.status != 'completed' or not job.result:
            return render_template('share_result.html', error="Analysis not ready or failed"), 404
            
        # Calculate age
        age = datetime.utcnow() - job.created_at
        age_minutes = int(age.total_seconds() / 60)
        age_hours = age_minutes // 60
        
        # Determine freshness/confidence
        if age_minutes < 15:
            freshness = "FRESH"
            freshness_color = "rec-buy" # Green
            confidence_pct = 100
            message = "Actionable Intelligence"
        elif age_minutes < 60:
            freshness = "COOLING"
            freshness_color = "rec-hold" # Yellow
            confidence_pct = 75
            message = "Verify Current Price"
        elif age_hours < 4:
            freshness = "STALE"
            freshness_color = "rec-sell" # Orange/Redish
            confidence_pct = 40
            message = "Trend Shift Likely"
        else:
            freshness = "HISTORICAL"
            freshness_color = "rec-sell" # Red
            confidence_pct = 0
            message = "Archive Only - Do Not Trade"
            
        return render_template('share_result.html', 
                             job=job, 
                             result=job.result,
                             age_str=f"{age_hours}h {age_minutes % 60}m ago" if age_hours > 0 else f"{age_minutes}m ago",
                             freshness=freshness,
                             freshness_color=freshness_color,
                             confidence_pct=confidence_pct,
                             message=message)
                             
    except Exception as e:
        logging.error(f"Error rendering share page: {e}")
        return render_template('share_result.html', error="System Error"), 500

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
