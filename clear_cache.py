#!/usr/bin/env python3
import sys
sys.path.append('.')

from app import app, db
from models import AnalysisCache

with app.app_context():
    try:
        # Clear analysis cache so user can re-test TSLA with fixed indicators
        AnalysisCache.query.delete()
        db.session.commit()
        print("✓ Analysis cache cleared - TSLA can now be re-analyzed with fixed indicators")
        
    except Exception as e:
        print(f"Error: {e}")
        db.session.rollback()
    finally:
        db.session.close()