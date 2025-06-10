import os
import pathlib
from dotenv import load_dotenv
from datetime import timedelta

# Load environment variables from .env file at the beginning
load_dotenv()

BASE_DIR = pathlib.Path(__file__).parent.resolve() # Directory of this config.py file
DATABASE_PATH = BASE_DIR / "patients.db" # Path relative to this config.py
# Default path for client_secret.json relative to this config.py
# This can be overridden by GOOGLE_CLIENT_SECRETS_FILE_PATH in .env
DEFAULT_CLIENT_SECRETS_FILE_PATH = BASE_DIR / "client_secret.json"

class Config:
    """Base configuration settings."""
    # Security keys - CRITICAL: Set these to strong, random, unique values in .env
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev_default_flask_secret_key_CHANGE_ME')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev_default_jwt_secret_key_CHANGE_ME') # Ensure JWT_SECRET_KEY is also loaded
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)
    DEBUG = False
    TESTING = False

    # Database configuration
    # DATABASE_URL from .env takes precedence, otherwise defaults to local SQLite
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or f'sqlite:///{DATABASE_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File Uploads
    # UPLOAD_FOLDER defaults to 'Uploads' directory in the same dir as config.py
    UPLOAD_FOLDER = BASE_DIR / os.getenv('UPLOAD_FOLDER_NAME', 'Uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UNKNOWN_CONFIDENCE_THRESHOLD = float(os.getenv('UNKNOWN_CONFIDENCE_THRESHOLD', 0.5))

    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    # Path to client_secret.json, can be overridden by .env
    GOOGLE_CLIENT_SECRETS_FILE = os.getenv('GOOGLE_CLIENT_SECRETS_FILE_PATH') or str(DEFAULT_CLIENT_SECRETS_FILE_PATH)
    # FRONTEND_URL is crucial for generating correct redirect URIs for Google and password reset
    FRONTEND_URL = os.getenv('FRONTEND_URL') # e.g., 'http://localhost:3000' or your ngrok URL
    # BACKEND_BASE_URL will be your ngrok URL for the backend
    BACKEND_BASE_URL = os.getenv('BACKEND_BASE_URL') # Add this line

    # Flask-Mail Configuration
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't']
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'false').lower() in ['true', '1', 't']
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD') # CRITICAL: Use App Password for Gmail

    # Construct default sender carefully
    _mail_sender_name = os.getenv('MAIL_SENDER_NAME', 'Your App Name')
    _mail_sender_address = os.getenv('MAIL_SENDER_EMAIL') or MAIL_USERNAME # Fallback to MAIL_USERNAME
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER') or \
                          (f"{_mail_sender_name} <{_mail_sender_address}>" if _mail_sender_address else 'noreply@example.com')


    # Session Cookie Security
    # SESSION_COOKIE_SECURE defaults to False for dev, True for prod (see below)
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax' # Recommended for most cases

    # Application specific settings (can be added here)
    # OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY') # This is used by DiseaseConsultation service directly

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    # For development, allow relaxed CORS settings if needed (handled in app.py)
    CORS_ALLOW_ALL_ORIGINS = True # Custom flag
    SESSION_COOKIE_SECURE = False # Often false for local HTTP dev
    # For dev, JWT_SECRET_KEY can be simpler, but still recommend setting in .env
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev_jwt_secret_key_CHANGE_IN_ENV')


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True # Enforce HTTPS for session cookies in production
    # In production, CORS origins should be specific, e.g., from FRONTEND_URL
    CORS_ALLOWED_ORIGINS = [Config.FRONTEND_URL] if Config.FRONTEND_URL else []
    # CRITICAL: Ensure JWT_SECRET_KEY is set to a strong, unique value in .env for production
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY') # This will be None if not set, causing issues if not handled
    if JWT_SECRET_KEY is None:
        # This print will only show when the class is defined, not ideal for runtime check
        # A runtime check or assertion in app factory for essential prod keys is better
        print("CRITICAL WARNING: JWT_SECRET_KEY is not set for ProductionConfig!")


# Determine active configuration based on FLASK_ENV
FLASK_ENV = os.getenv('FLASK_ENV', 'development').lower()

if FLASK_ENV == 'production':
    ActiveConfig = ProductionConfig
    # Add a check for critical production keys
    if not ActiveConfig.JWT_SECRET_KEY or 'default' in ActiveConfig.JWT_SECRET_KEY or \
       not ActiveConfig.SECRET_KEY or 'default' in ActiveConfig.SECRET_KEY:
        raise ValueError("CRITICAL: SECRET_KEY and/or JWT_SECRET_KEY are not securely set for production. Update your .env file.")
    print("INFO: Loading Production Configuration.")
else:
    ActiveConfig = DevelopmentConfig
    print("INFO: Loading Development Configuration.")