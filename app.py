import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
from datetime import timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

from extensions import db

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.permanent_session_lifetime = timedelta(hours=8)  # Admin sessions expire after 8 hours
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
database_url = os.environ.get("DATABASE_URL", "sqlite:///shouldibuy.db")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

# Import models to ensure they are registered with SQLAlchemy
import models
from extensions import Base

# Import routes after app initialization
from routes import *

if __name__ == "__main__":
    with app.app_context():
        # Create tables using Base.metadata which holds the model definitions
        Base.metadata.create_all(bind=db.engine)
    app.run(host='0.0.0.0', port=5002, debug=False, use_reloader=False)
