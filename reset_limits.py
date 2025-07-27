#!/usr/bin/env python3
"""
Simple script to reset rate limits for testing
Usage: python3 reset_limits.py
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def reset_limits():
    """Reset all rate limits by clearing the database table"""
    try:
        from app import app, db
        from models import RateLimit
        
        with app.app_context():
            print("Resetting all rate limits...")
            deleted_count = db.session.query(RateLimit).delete()
            db.session.commit()
            print(f"✓ Cleared {deleted_count} rate limit records")
            print("✓ All users now have fresh daily limits!")
            
    except ImportError as e:
        print(f"Error importing modules: {e}")
        print("Make sure you're running this from the project root directory")
        return False
    except Exception as e:
        print(f"Error resetting limits: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = reset_limits()
    sys.exit(0 if success else 1)