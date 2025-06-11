import os
import pathlib
from dotenv import load_dotenv
from datetime import timedelta

# Load environment variables from .env file at the beginning
load_dotenv()

BASE_DIR = pathlib.Path(__file__).parent.resolve()  # Directory of this config.py file
DATABASE_PATH = BASE_DIR / "patients.db"  # Path relative to this config.py
# Default path for client_secret.json relative to this config.py
DEFAULT_CLIENT_SECRETS_FILE_PATH = BASE_DIR / "client_secret.json"

class Config:
    """Base configuration settings."""
    # Security keys - CRITICAL: Set these to strong, random, unique values in .env
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev_default_flask_secret_key_CHANGE_ME')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev_default_jwt_secret_key_CHANGE_ME')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)
    DEBUG = False
    TESTING = False

    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or f'sqlite:///{DATABASE_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File Uploads
    UPLOAD_FOLDER = BASE_DIR / os.getenv('UPLOAD_FOLDER_NAME', 'Uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UNKNOWN_CONFIDENCE_THRESHOLD = float(os.getenv('UNKNOWN_CONFIDENCE_THRESHOLD', 0.5))

    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    GOOGLE_CLIENT_SECRETS_FILE = os.getenv('GOOGLE_CLIENT_SECRETS_FILE_PATH') or str(DEFAULT_CLIENT_SECRETS_FILE_PATH)
    FRONTEND_URLS = os.getenv('FRONTEND_URLS', 'http://localhost:3000')  # Comma-separated list of frontend URLs
    BACKEND_BASE_URL = os.getenv('BACKEND_BASE_URL', 'https://127.0.0.1:5000')  # Backend origin

    # Flask-Mail Configuration
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't']
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'false').lower() in ['true', '1', 't']
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')  # CRITICAL: Use App Password for Gmail

    # Construct default sender carefully
    _mail_sender_name = os.getenv('MAIL_SENDER_NAME', 'Your App Name')
    _mail_sender_address = os.getenv('MAIL_SENDER_EMAIL') or MAIL_USERNAME
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER') or \
                          (f"{_mail_sender_name} <{_mail_sender_address}>" if _mail_sender_address else 'noreply@example.com')

    # Session Cookie Security
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    CORS_ALLOW_ALL_ORIGINS = True  # Custom flag
    SESSION_COOKIE_SECURE = False
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev_jwt_secret_key_CHANGE_IN_ENV')

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    CORS_ALLOWED_ORIGINS = [url.strip() for url in Config.FRONTEND_URLS.split(',') if url.strip()] + [Config.BACKEND_BASE_URL.rstrip('/')] if Config.FRONTEND_URLS else []
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    if JWT_SECRET_KEY is None:
        print("CRITICAL WARNING: JWT_SECRET_KEY is not set for ProductionConfig!")

# Determine active configuration based on FLASK_ENV
FLASK_ENV = os.getenv('FLASK_ENV', 'development').lower()

if FLASK_ENV == 'production':
    ActiveConfig = ProductionConfig
    if not ActiveConfig.JWT_SECRET_KEY or 'default' in ActiveConfig.JWT_SECRET_KEY or \
       not ActiveConfig.SECRET_KEY or 'default' in ActiveConfig.SECRET_KEY:
        raise ValueError("CRITICAL: SECRET_KEY and/or JWT_SECRET_KEY are not securely set for production. Update your .env file.")
    print("INFO: Loading Production Configuration.")
else:
    ActiveConfig = DevelopmentConfig
    print("INFO: Loading Development Configuration.")