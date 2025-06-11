# app.py
from flask import Flask, render_template
import os
import pathlib
from extensions import db, jwt, bcrypt, mail, cors, oauth, logger  # Assuming extensions.py initializes these
from config import ActiveConfig

BASE_DIR = pathlib.Path(__file__).parent.resolve()
template_dir = BASE_DIR / 'templates'

app = Flask(__name__,
            template_folder=template_dir,
            instance_relative_config=False)

app.config.from_object(ActiveConfig)

# Log critical configurations being used
app.logger.info(f"Flask App '{__name__}' running with {ActiveConfig.__name__}")
app.logger.info(f"SECRET_KEY is {'SET' if app.config.get('SECRET_KEY') and 'default' not in app.config.get('SECRET_KEY') else 'NOT SET SECURELY'}")
app.logger.info(f"JWT_SECRET_KEY is {'SET' if app.config.get('JWT_SECRET_KEY') and 'default' not in app.config.get('JWT_SECRET_KEY') else 'NOT SET SECURELY'}")
app.logger.info(f"DATABASE_URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
app.logger.info(f"UPLOAD_FOLDER: {app.config.get('UPLOAD_FOLDER')}")
app.logger.info(f"FRONTEND_URLS: {app.config.get('FRONTEND_URLS')}")
app.logger.info(f"BACKEND_BASE_URL: {app.config.get('BACKEND_BASE_URL')}")
app.logger.info(f"GOOGLE_CLIENT_SECRETS_FILE: {app.config.get('GOOGLE_CLIENT_SECRETS_FILE')} - Exists: {os.path.exists(app.config.get('GOOGLE_CLIENT_SECRETS_FILE', ''))}")

# Initialize extensions
db.init_app(app)
jwt.init_app(app)
bcrypt.init_app(app)
mail.init_app(app)

# CORS Configuration
# Use specific origins from config for better security
frontend_urls = [
    url.strip() for url in app.config.get('FRONTEND_URLS', '').split(',')
    if url.strip()
]  # Split comma-separated FRONTEND_URLS from .env
cors_origins = frontend_urls if frontend_urls else ['http://localhost:3000']  # Fallback to default if empty

# Add backend origin to support local template
backend_base_url = app.config.get('BACKEND_BASE_URL', 'https://127.0.0.1:5000')
cors_origins.append(backend_base_url.rstrip('/'))  # Add backend origin

if not frontend_urls and app.debug:
    cors_origins = "*"  # Fallback for dev if no FRONTEND_URLS
    app.logger.warning("CORS origins set to '*' due to missing FRONTEND_URLS in debug mode.")

cors.init_app(app, supports_credentials=True, resources={r"/*": {"origins": cors_origins}})
app.logger.info(f"CORS configured for origins: {cors_origins}")

oauth.init_app(app)  # Initialize Authlib's OAuth registry

# Import models AFTER db is initialized with app and BEFORE create_all
from models.patient import Patient, MedicalHistory, Notification, PasswordResetToken

with app.app_context():
    try:
        app.logger.info("Attempting db.create_all()...")
        db.create_all()
        app.logger.info(f"Database tables ensured (or already existed) in: {app.config['SQLALCHEMY_DATABASE_URI']}")
    except Exception as e:
        app.logger.error(f"!!! Error during db.create_all(): {e}", exc_info=True)

from services.consultation_service import DiseaseConsultation
try:
    consultation_service_instance = DiseaseConsultation()  # Assumes API key is handled by the service
    app.consultation_service = consultation_service_instance
    logger.info("DiseaseConsultation service attached to Flask app.")
except Exception as e:  # Catch broader exception for service init
    logger.error(f"Failed to initialize DiseaseConsultation service: {e}", exc_info=True)
    app.consultation_service = None

# Import and register blueprints
from routes.auth import auth_bp
from routes.image import image_bp
from routes.history import history_bp
from routes.consultation import consultation_bp
from routes.profile import profile_bp
from routes.notifications import notifications_bp

app.register_blueprint(auth_bp)  # url_prefix is already in the blueprint
app.register_blueprint(image_bp, url_prefix='/image')
app.register_blueprint(history_bp, url_prefix='/history')
app.register_blueprint(consultation_bp, url_prefix='/consultation')
app.register_blueprint(profile_bp)  # url_prefix is already in the blueprint
app.register_blueprint(notifications_bp, url_prefix='/notifications')

@app.route('/')
def home():
    # Serves the local template for testing
    return render_template('index.html')  # Ensure templates/index.html exists

# JWT Blocklist setup (in-memory, consider persistent for production)
if not hasattr(app, 'jwt_blocklist'):  # Initialize if not done by extensions
    app.jwt_blocklist = set()

@jwt.token_in_blocklist_loader
def check_if_token_in_blocklist(jwt_header, jwt_payload: dict) -> bool:
    jti = jwt_payload["jti"]
    return jti in app.jwt_blocklist

if __name__ == '__main__':
    # Ensure UPLOAD_FOLDER exists
    upload_dir = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
        app.logger.info(f"Created UPLOAD_FOLDER at {upload_dir}")

    app.logger.info("Running Flask with HTTP (Debug mode).")
    ssl_cert_path = os.path.join(BASE_DIR, 'cert.pem')
    ssl_key_path = os.path.join(BASE_DIR, 'key.pem')
    
    app.run(ssl_context=(ssl_cert_path, ssl_key_path))