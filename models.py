from app import db
from datetime import datetime, timedelta

class RateLimit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    request_count = db.Column(db.Integer, default=0, nullable=False)
    maximum_brain_count = db.Column(db.Integer, default=0, nullable=False)
    last_request = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    date_created = db.Column(db.Date, default=datetime.utcnow().date, nullable=False)

    def __repr__(self):
        return f'<RateLimit {self.ip_address}: {self.request_count}/{self.maximum_brain_count}>'

class StockAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=False)
    recommendation = db.Column(db.String(20), nullable=False)
    confidence = db.Column(db.String(10), nullable=False)
    analysis_data = db.Column(db.Text, nullable=False)
    maximum_brain = db.Column(db.Boolean, default=False, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        brain_mode = " (Max Brain)" if self.maximum_brain else ""
        return f'<StockAnalysis {self.ticker}: {self.recommendation}{brain_mode}>'

class SystemLimits(db.Model):
    """Global daily API tracking and spend limits"""
    id = db.Column(db.Integer, primary_key=True)
    daily_api_calls = db.Column(db.Integer, default=0, nullable=False)
    daily_cost_estimate = db.Column(db.Float, default=0.0, nullable=False)
    max_daily_cost = db.Column(db.Float, default=25.0, nullable=False)
    emergency_stop = db.Column(db.Boolean, default=False, nullable=False)
    date_created = db.Column(db.Date, default=datetime.utcnow().date, nullable=False, unique=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<SystemLimits {self.date_created}: {self.daily_api_calls} calls, ${self.daily_cost_estimate:.2f}>'

class AnalysisCache(db.Model):
    """6-hour cache for duplicate analysis prevention"""
    id = db.Column(db.Integer, primary_key=True)
    ticker_symbol = db.Column(db.String(10), nullable=False, index=True)
    maximum_brain = db.Column(db.Boolean, default=False, nullable=False)
    analysis_data = db.Column(db.Text, nullable=False)
    cache_expiry = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.cache_expiry:
            self.cache_expiry = datetime.utcnow() + timedelta(hours=6)

    @property
    def is_expired(self):
        return datetime.utcnow() > self.cache_expiry

    def __repr__(self):
        brain_mode = " (Max Brain)" if self.maximum_brain else ""
        return f'<AnalysisCache {self.ticker_symbol}{brain_mode}: expires {self.cache_expiry}>'

class SecurityLog(db.Model):
    """Suspicious activity tracking"""
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    event_count = db.Column(db.Integer, default=1, nullable=False)
    event_details = db.Column(db.Text)
    last_attempt = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    date_created = db.Column(db.Date, default=datetime.utcnow().date, nullable=False)

    def __repr__(self):
        return f'<SecurityLog {self.ip_address}: {self.event_type} x{self.event_count}>'
