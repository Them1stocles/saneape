from app import db
from datetime import datetime

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
