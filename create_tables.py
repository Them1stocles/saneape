#!/usr/bin/env python3
"""Create all database tables"""
from app import app, db
from models import *

with app.app_context():
    # Drop all tables and recreate them
    print("Creating all database tables...")
    db.create_all()
    
    # Verify tables were created
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"Created tables: {', '.join(tables)}")
    
    # Verify oauth_tokens table specifically
    if 'oauth_tokens' in tables:
        print("✓ oauth_tokens table created successfully")
    else:
        print("✗ ERROR: oauth_tokens table not created!")
    
    if 'users' in tables:
        print("✓ users table created successfully")
    else:
        print("✗ ERROR: users table not created!")