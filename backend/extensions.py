# extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth # For Google OAuth
import logging

db = SQLAlchemy()
jwt = JWTManager()
bcrypt = Bcrypt()
mail = Mail()
cors = CORS()
oauth = OAuth() # Authlib OAuth registry

# Basic Logger Setup (customize as needed)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(name)s %(module)s L%(lineno)d: %(message)s')
logger = logging.getLogger(__name__) # Or 'app' if you prefer a common app logger

def init_extensions(app):
    """
    Initializes all extensions with the Flask app.
    This function can be called from your app factory if you use one.
    If not using an app factory, direct .init_app(app) calls in app.py are also fine.
    """
    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)
    mail.init_app(app)
    cors.init_app(app, supports_credentials=True) # Basic init, specific config in app.py
    oauth.init_app(app)

    # You might also initialize app.jwt_blocklist here
    if not hasattr(app, 'jwt_blocklist'):
        app.jwt_blocklist = set()

    # Example of how oauth could register Google client here if not done in auth.py
    # But current approach of get_google_flow in auth.py is also valid
    # google_client_id = app.config.get('GOOGLE_CLIENT_ID')
    # google_client_secret = app.config.get('GOOGLE_CLIENT_SECRET')
    # if google_client_id and google_client_secret:
    #     oauth.register(
    #         name='google',
    #         client_id=google_client_id,
    #         client_secret=google_client_secret,
    #         server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    #         client_kwargs={'scope': 'openid email profile'}
    #     )
    # else:
    #     logger.warning("Google OAuth client ID or secret not configured in extensions.py.")