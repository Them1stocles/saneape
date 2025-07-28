#!/usr/bin/env python3
"""Fix database by creating all tables"""
import os
import sys

# Remove existing database
if os.path.exists('shouldibuy.db'):
    os.remove('shouldibuy.db')
    print("Removed old database")

# Import app and models
from app import app, db
from models import *

with app.app_context():
    print("Creating all tables...")
    
    # Create all tables
    db.create_all()
    
    # Verify tables
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    print(f"\nCreated {len(tables)} tables:")
    for table in sorted(tables):
        print(f"  ✓ {table}")
    
    # Check critical tables
    critical_tables = ['users', 'oauth_tokens', 'subscriptions', 'credit_balances']
    missing = [t for t in critical_tables if t not in tables]
    
    if missing:
        print(f"\n⚠️  WARNING: Missing critical tables: {', '.join(missing)}")
        sys.exit(1)
    else:
        print("\n✅ All critical tables created successfully!")