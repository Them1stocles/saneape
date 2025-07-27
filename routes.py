from flask import render_template, request, jsonify, flash, redirect, url_for
from app import app, db
import logging
from stock_analyzer import StockAnalyzer
from rate_limiter import RateLimiter
from models import StockAnalysis
import json

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_stock():
    try:
        # Get client IP
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # Check rate limit
        rate_limiter = RateLimiter()
        if not rate_limiter.is_allowed(client_ip):
            return jsonify({
                'error': 'Rate limit exceeded. You can only make 2 requests per day. Please try again tomorrow.',
                'type': 'rate_limit'
            }), 429
        
        # Get ticker from form
        ticker = request.form.get('ticker', '').strip().upper()
        
        if not ticker:
            return jsonify({
                'error': 'Please enter a stock ticker symbol.',
                'type': 'validation'
            }), 400
        
        # Validate ticker format (basic validation)
        if not ticker.isalpha() or len(ticker) > 5:
            return jsonify({
                'error': 'Please enter a valid stock ticker symbol (letters only, max 5 characters).',
                'type': 'validation'
            }), 400
        
        # Initialize stock analyzer
        analyzer = StockAnalyzer()
        
        # Fetch and analyze stock data
        result = analyzer.analyze_stock(ticker)
        
        if result['success']:
            # Record the request
            rate_limiter.record_request(client_ip)
            
            # Save analysis to database
            analysis = StockAnalysis()
            analysis.ticker = ticker
            analysis.ip_address = client_ip
            analysis.recommendation = result['recommendation']
            analysis.confidence = result['confidence']
            analysis.analysis_data = json.dumps(result['analysis_details'])
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
        return jsonify({
            'error': 'An unexpected error occurred. Please try again later.',
            'type': 'server'
        }), 500

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
