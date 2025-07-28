"""
Production-grade Replit authentication system with comprehensive error handling.
Integrates with user accounts, credit system, and session management.
"""

import jwt
import os
import uuid
import logging
from functools import wraps
from urllib.parse import urlencode
from datetime import datetime

from flask import g, session, redirect, request, render_template, url_for, flash, jsonify
from flask_dance.consumer import OAuth2ConsumerBlueprint, oauth_authorized, oauth_error
from flask_dance.consumer.storage import BaseStorage
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError
from sqlalchemy.exc import NoResultFound
from werkzeug.local import LocalProxy

from app import app, db
from models import OAuth, User, CreditBalance, UserRateLimit, CreditTransaction
from feature_flags import is_user_auth_enabled
from monitoring import monitoring, record_user_action

logger = logging.getLogger(__name__)

# Initialize Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'replit_auth.login'

@login_manager.unauthorized_handler
def unauthorized():
    """Handle unauthorized access for both regular and AJAX requests"""
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json':
        return jsonify({'error': 'Authentication required'}), 401
    # Regular request - redirect to login
    return redirect(url_for('replit_auth.login', next=request.url))
login_manager.login_message = 'Please log in to access your account and credits.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    try:
        return db.session.get(User, user_id)
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {e}")
        return None

class UserSessionStorage(BaseStorage):
    """Enhanced storage for OAuth tokens with error handling"""
    
    def get(self, blueprint):
        """Retrieve OAuth token for current user"""
        if not current_user.is_authenticated:
            return None
            
        try:
            token = db.session.query(OAuth).filter_by(
                user_id=current_user.get_id(),
                browser_session_key=g.browser_session_key,
                provider=blueprint.name,
            ).one().token
            return token
        except NoResultFound:
            logger.debug(f"No OAuth token found for user {current_user.get_id()}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving OAuth token: {e}")
            return None

    def set(self, blueprint, token):
        """Store OAuth token for current user"""
        if not current_user.is_authenticated:
            logger.warning("Attempted to store OAuth token for unauthenticated user")
            return
            
        try:
            # Remove existing token
            db.session.query(OAuth).filter_by(
                user_id=current_user.get_id(),
                browser_session_key=g.browser_session_key,
                provider=blueprint.name,
            ).delete()
            
            # Create new token entry
            new_oauth = OAuth()
            new_oauth.user_id = current_user.get_id()
            new_oauth.browser_session_key = g.browser_session_key
            new_oauth.provider = blueprint.name
            new_oauth.token = token
            
            db.session.add(new_oauth)
            db.session.commit()
            
            logger.debug(f"OAuth token stored for user {current_user.get_id()}")
            
        except Exception as e:
            logger.error(f"Error storing OAuth token: {e}")
            db.session.rollback()

    def delete(self, blueprint):
        """Delete OAuth token for current user"""
        if not current_user.is_authenticated:
            return
            
        try:
            db.session.query(OAuth).filter_by(
                user_id=current_user.get_id(),
                browser_session_key=g.browser_session_key,
                provider=blueprint.name
            ).delete()
            db.session.commit()
            
            logger.debug(f"OAuth token deleted for user {current_user.get_id()}")
            
        except Exception as e:
            logger.error(f"Error deleting OAuth token: {e}")
            db.session.rollback()

def make_replit_blueprint():
    """Create Replit OAuth blueprint with production configuration"""
    
    # Validate required environment variables
    try:
        repl_id = os.environ['REPL_ID']
    except KeyError:
        logger.error("REPL_ID environment variable is required for Replit authentication")
        raise SystemExit("REPL_ID environment variable must be set")

    issuer_url = os.environ.get('ISSUER_URL', "https://replit.com/oidc")
    
    logger.info(f"Initializing Replit OAuth with REPL_ID: {repl_id}")

    replit_bp = OAuth2ConsumerBlueprint(
        "replit_auth",
        __name__,
        client_id=repl_id,
        client_secret=None,
        base_url=issuer_url,
        authorization_url_params={
            "prompt": "login consent",
            "app_name": "SaneApe.com",
        },
        token_url=issuer_url + "/token",
        token_url_params={
            "auth": (),
            "include_client_id": True,
        },
        auto_refresh_url=issuer_url + "/token",
        auto_refresh_kwargs={
            "client_id": repl_id,
        },
        authorization_url=issuer_url + "/auth",
        use_pkce=True,
        code_challenge_method="S256",
        scope=["openid", "profile", "email", "offline_access"],
        storage=UserSessionStorage(),
    )

    @replit_bp.before_app_request
    def set_applocal_session():
        """Initialize session and user context"""
        # Check if user authentication is enabled
        if not is_user_auth_enabled():
            return
            
        # Initialize browser session key
        if '_browser_session_key' not in session:
            session['_browser_session_key'] = uuid.uuid4().hex
        session.modified = True
        g.browser_session_key = session['_browser_session_key']
        g.flask_dance_replit = replit_bp.session
        
        # Update last activity for authenticated users
        if current_user.is_authenticated:
            try:
                current_user.last_login = datetime.utcnow()
                db.session.commit()
            except Exception as e:
                logger.error(f"Error updating user last login: {e}")
                db.session.rollback()

    @replit_bp.route("/logout")
    def logout():
        """Enhanced logout with comprehensive cleanup"""
        user_id = current_user.get_id() if current_user.is_authenticated else None
        
        try:
            # Clear OAuth token
            if hasattr(replit_bp, 'token') and replit_bp.token:
                del replit_bp.token
                
            # Log out user
            logout_user()
            
            # Clear session data
            session.clear()
            
            # Record logout event
            if user_id:
                record_user_action('logout', user_id)
                
            logger.info(f"User {user_id} logged out successfully")
            
        except Exception as e:
            logger.error(f"Error during logout for user {user_id}: {e}")

        # Force immediate redirect to clear browser cache
        # Instead of redirecting to Replit logout (which can cause browser caching issues),
        # redirect directly to home with cache-busting headers
        from flask import make_response
        
        response = make_response(redirect(url_for('index', _external=True)))
        
        # Add cache-busting headers to force page reload
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response

    @replit_bp.route("/error")
    def error():
        """Handle OAuth errors"""
        error_description = request.args.get('error_description', 'Authentication failed')
        logger.warning(f"OAuth error: {error_description}")
        
        flash(f"Authentication error: {error_description}", 'error')
        return render_template("auth_error.html", error_description=error_description), 403

    return replit_bp

def save_user(user_claims):
    """Save or update user from OAuth claims with comprehensive setup"""
    try:
        # Extract user data from claims
        user_id = user_claims['sub']
        email = user_claims.get('email')
        first_name = user_claims.get('first_name')
        last_name = user_claims.get('last_name')
        profile_image_url = user_claims.get('profile_image_url')
        
        logger.info(f"Processing user {user_id} from OAuth claims")
        
        # Create or update user
        user = db.session.get(User, user_id)
        if not user:
            user = User(id=user_id)
            logger.info(f"Creating new user {user_id}")
            
        # Update user data
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.profile_image_url = profile_image_url
        user.updated_at = datetime.utcnow()
        
        # Use merge for upsert operation
        merged_user = db.session.merge(user)
        
        # Initialize credit balance if new user
        if not merged_user.credit_balance:
            credit_balance = CreditBalance(
                user_id=merged_user.id,
                subscription_credits=0,
                topup_credits=0
            )
            db.session.add(credit_balance)
            logger.info(f"Created credit balance for new user {user_id}")
            
            # Record welcome credit transaction
            welcome_transaction = CreditTransaction(
                user_id=merged_user.id,
                transaction_type='welcome_bonus',
                credit_type='topup',
                credits_amount=0,  # No initial credits, but track the account creation
                description='Account created - ready for subscription or top-up purchases'
            )
            db.session.add(welcome_transaction)
        
        # Initialize user rate limiting if new user
        if not db.session.query(UserRateLimit).filter_by(user_id=merged_user.id).first():
            user_rate_limit = UserRateLimit(user_id=merged_user.id)
            db.session.add(user_rate_limit)
            logger.info(f"Created rate limit tracking for user {user_id}")
        
        db.session.commit()
        
        # Record login event
        record_user_action('login', merged_user.id)
        
        logger.info(f"User {user_id} saved/updated successfully")
        return merged_user
        
    except Exception as e:
        logger.error(f"Error saving user {user_claims.get('sub', 'unknown')}: {e}")
        db.session.rollback()
        monitoring.system_monitor.record_error('user_save_error', str(e), {'user_claims': user_claims})
        raise

@oauth_authorized.connect
def logged_in(blueprint, token):
    """Handle successful OAuth authorization"""
    try:
        # Decode user claims from ID token
        user_claims = jwt.decode(token['id_token'], options={"verify_signature": False})
        logger.info(f"User {user_claims.get('sub')} authenticated successfully")
        
        # Save/update user and initialize account
        user = save_user(user_claims)
        
        # Log in user
        login_user(user, remember=True)
        
        # Store OAuth token
        blueprint.token = token
        
        # Flash welcome message for new users
        if not user.last_login or (datetime.utcnow() - user.last_login).days > 30:
            flash(f"Welcome back, {user.display_name}!", 'success')
        
        # Redirect to intended page or home
        next_url = session.pop("next_url", None)
        if next_url:
            return redirect(next_url)
        else:
            return redirect(url_for('index'))
            
    except Exception as e:
        logger.error(f"Error during OAuth login: {e}")
        monitoring.create_alert('error', 'OAuth Login Failed', str(e), {'token': token})
        return redirect(url_for('replit_auth.error'))

@oauth_error.connect
def handle_error(blueprint, error, error_description=None, error_uri=None):
    """Handle OAuth errors with comprehensive logging"""
    logger.error(f"OAuth error: {error}, description: {error_description}, uri: {error_uri}")
    
    monitoring.create_alert(
        'warning', 
        'OAuth Authentication Error',
        f"OAuth error: {error}",
        {
            'error': error,
            'error_description': error_description,
            'error_uri': error_uri
        }
    )
    
    return redirect(url_for('replit_auth.error'))

def require_login(f):
    """Decorator requiring user authentication with feature flag support"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user authentication is enabled
        if not is_user_auth_enabled():
            # If user auth is disabled, allow access
            return f(*args, **kwargs)
            
        if not current_user.is_authenticated:
            session["next_url"] = get_next_navigation_url(request)
            flash("Please log in to access your account and credits.", 'info')
            return redirect(url_for('replit_auth.login'))

        # Check token expiration and refresh if needed
        try:
            if hasattr(replit, 'token') and replit.token:
                expires_in = replit.token.get('expires_in', 0)
                if expires_in < 300:  # Less than 5 minutes remaining
                    refresh_token_url = os.environ.get('ISSUER_URL', "https://replit.com/oidc") + "/token"
                    token = replit.refresh_token(
                        token_url=refresh_token_url,
                        client_id=os.environ['REPL_ID']
                    )
                    replit.token_updater(token)
                    logger.debug(f"Refreshed token for user {current_user.get_id()}")
                    
        except InvalidGrantError:
            # If refresh token is invalid, user needs to re-login
            logout_user()
            session["next_url"] = get_next_navigation_url(request)
            flash("Your session has expired. Please log in again.", 'warning')
            return redirect(url_for('replit_auth.login'))
        except Exception as e:
            logger.error(f"Error refreshing token for user {current_user.get_id()}: {e}")

        return f(*args, **kwargs)

    return decorated_function

def require_subscription(f):
    """Decorator requiring active subscription"""
    @wraps(f)
    @require_login
    def decorated_function(*args, **kwargs):
        if not current_user.has_active_subscription():
            flash("This feature requires an active subscription.", 'warning')
            return redirect(url_for('subscription_required'))
        return f(*args, **kwargs)
    return decorated_function

def get_next_navigation_url(request):
    """Get appropriate redirect URL after login"""
    is_navigation_url = (
        request.headers.get('Sec-Fetch-Mode') == 'navigate' and 
        request.headers.get('Sec-Fetch-Dest') == 'document'
    )
    if is_navigation_url:
        return request.url
    return request.referrer or request.url

# Create global proxy for easy access
replit = LocalProxy(lambda: g.flask_dance_replit)

def init_auth(app):
    """Initialize authentication system with app"""
    if not is_user_auth_enabled():
        logger.info("User authentication is disabled by feature flag")
        return None
        
    try:
        blueprint = make_replit_blueprint()
        app.register_blueprint(blueprint, url_prefix="/auth")
        logger.info("Replit authentication blueprint registered successfully")
        return blueprint
    except Exception as e:
        logger.error(f"Failed to initialize authentication: {e}")
        monitoring.create_alert('critical', 'Authentication Init Failed', str(e))
        return None

# Initialize with app
auth_blueprint = init_auth(app)