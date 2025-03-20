from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flasgger import Swagger
from authlib.integrations.flask_client import OAuth  # ✅ استيراد OAuth
from config import Config
from models import db
from routes.auth import auth_bp
from routes.predictions import predictions_bp
from routes.diseases import diseases_bp
from routes.social_auth import social_auth_bp, oauth  # ✅ استيراد OAuth من ملف المسارات
from routes.notifications import notifications_bp
from routes.profile import profile_bp

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# ✅ تهيئة OAuth قبل تسجيل المسارات
oauth.init_app(app)  

# ✅ إعداد Swagger
swagger_config = {
    "swagger": "2.0",
    "info": {
        "title": "AI Disease Classification API",
        "description": "API for disease classification using AI models",
        "version": "1.0.0",
        "contact": {
            "name": "Your Name",
            "email": "your_email@example.com"
        },
    },
    "basePath": "/",  
    "schemes": ["http"],  
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/"
}
swagger = Swagger(app, template=swagger_config)

# ✅ تهيئة JWT
jwt = JWTManager(app)

# ✅ تهيئة قاعدة البيانات
db.init_app(app)

# ✅ تسجيل المسارات (Blueprints)
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(predictions_bp, url_prefix='/api')
app.register_blueprint(diseases_bp, url_prefix='/api/diseases')
app.register_blueprint(social_auth_bp, url_prefix='/api/auth')
app.register_blueprint(notifications_bp, url_prefix='/api')
app.register_blueprint(profile_bp, url_prefix='/api')

# ✅ نقطة البداية
@app.route('/')
def home():
    """API Home
    ---
    responses:
      200:
        description: API is running successfully
    """
    return "🚀 AI Disease Classification API is running!"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
