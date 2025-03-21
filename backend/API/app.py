from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flasgger import Swagger
from flask_jwt_extended import jwt_required, get_jwt_identity
from authlib.integrations.flask_client import OAuth
from datetime import timedelta
from config import Config
from models import db
import os

# استيراد Blueprints
from routes.auth import auth_bp
from routes.predictions import predictions_bp
from routes.diseases import diseases_bp
from routes.social_auth import social_auth_bp
from routes.notifications import notifications_bp
from routes.profile import profile_bp

# تعطيل تحذيرات TensorFlow لتحسين الأداء
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

# -------------------- تهيئة التطبيق --------------------
app = Flask(__name__)
app.config.from_object(Config)

# ✅ حماية الجلسات (يجب تفعيلها في الإنتاج)
app.config['SESSION_COOKIE_SECURE'] = False  # غيّر إلى True عند نشر التطبيق
app.secret_key = os.getenv('SECRET_KEY', 'secret-key-fallback')

# -------------------- إعدادات CORS --------------------
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)


# -------------------- إعدادات JWT --------------------
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'super-secret-key')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)  # ✅ صلاحية التوكن لمدة ساعة
jwt = JWTManager(app)

# -------------------- إعدادات OAuth --------------------
oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={'scope': 'email profile'}
)

# -------------------- تهيئة قاعدة البيانات --------------------
db.init_app(app)

# ✅ التأكد من إنشاء الجداول عند بدء التطبيق
with app.app_context():
    db.create_all()

# -------------------- إعدادات Swagger --------------------
swagger_config = {
    "swagger": "2.0",
    "info": {
        "title": "AI Disease Classification API",
        "description": "API لتشخيص الأمراض باستخدام الذكاء الاصطناعي",
        "version": "1.0.0",
        "contact": {
            "name": "فريق الدعم",
            "email": "support@medicalai.com"
        },
    },
    "basePath": "/",
    "schemes": ["http", "https"],
    "securityDefinitions": {
        "BearerAuth": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header"
        }
    },
    "security": [{"BearerAuth": []}]
}

Swagger(app, template=swagger_config)

# -------------------- تسجيل Blueprints --------------------
blueprints = [
    (auth_bp, "/api/auth"),
    (predictions_bp, "/api/predictions"),
    (diseases_bp, "/api/diseases"),
    (social_auth_bp, "/api/auth/social"),
    (notifications_bp, "/api/notifications"),
    (profile_bp, "/api/profile")
]

for blueprint, url_prefix in blueprints:
    app.register_blueprint(blueprint, url_prefix=url_prefix)

# -------------------- معالجة الأخطاء --------------------
@app.errorhandler(404)
def not_found(e):
    return jsonify({
        "status": "error",
        "message": "المورد غير موجود"
    }), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({
        "status": "error",
        "message": "خطأ داخلي في الخادم"
    }), 500

# ✅ معالجة طلبات غير المصرح بها
@app.errorhandler(401)
def unauthorized(e):
    return jsonify({
        "status": "error",
        "message": "غير مصرح لك بالوصول"
    }), 401

# ✅ نقطة نهاية للتحقق من صحة التوكن
@app.route('/api/auth/check-token', methods=['GET'])
@jwt_required()
def check_token():
    return jsonify({"message": "🔑 Token is valid"}), 200

# -------------------- نقطة النهاية الأساسية --------------------
@app.route('/')
def home():
    """الصفحة الرئيسية للـ API"""
    return """
    <div style="text-align: center; padding: 50px;">
        <h1>🚀 نظام تشخيص الأمراض بالذكاء الاصطناعي</h1>
        <p>قم بزيارة <a href="/apidocs/">التوثيق التفاعلي</a> لاختبار API</p>
    </div>
    """

# -------------------- تشغيل التطبيق --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
