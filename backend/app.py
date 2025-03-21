from flask import Flask, render_template_string, request, jsonify, redirect, url_for
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
from datetime import datetime
import openai
import os
import re
import io
import numpy as np
from PIL import Image
from tensorflow.keras.preprocessing import image
from dotenv import load_dotenv

# تحميل متغيرات البيئة
load_dotenv()

# -------------------- تهيئة التطبيق --------------------
app = Flask(__name__)
CORS(app)

# -------------------- الإعدادات --------------------
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///medical.db')
app.config['JWT_SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')
app.config['MODEL_PATH'] = r"model_classification.h5"
app.config['IMG_SIZE'] = (240, 240)

# -------------------- تهيئة الملحقات --------------------
db = SQLAlchemy(app)
jwt = JWTManager(app)
oauth = OAuth(app)

# -------------------- نماذج قاعدة البيانات --------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    social_id = db.Column(db.String(100))
    social_provider = db.Column(db.String(20))

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    prediction = db.Column(db.String(100))
    confidence = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# -------------------- إعدادات OAuth --------------------
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# -------------------- مسارات API --------------------
@app.route('/')
def home():
    return render_template_string(index_html)

@app.route('/favicon.ico')
def favicon():
    return '', 404  # تجاهل طلب الأيقونة

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"error": "بيانات ناقصة"}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({"error": "البريد الإلكتروني موجود مسبقًا"}), 409

    user = User(
        email=data['email'],
        password=generate_password_hash(data['password'])
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "تم إنشاء الحساب بنجاح"}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()

    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({"error": "بيانات الاعتماد غير صحيحة"}), 401

    access_token = create_access_token(identity=user.id)
    return jsonify(access_token=access_token, user_id=user.id), 200

@app.route('/api/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "المستخدم غير موجود"}), 404

    if 'name' in data:
        user.name = data['name'].strip()
    
    if 'phone' in data:
        if not re.match(r"^\+?\d{7,15}$", data['phone']):
            return jsonify({"error": "رقم الهاتف غير صالح"}), 400
        user.phone = data['phone']
    
    db.session.commit()
    return jsonify({"message": "تم تحديث الملف الشخصي"}), 200

@app.route('/api/predict', methods=['POST'])
@jwt_required()
def predict():
    if 'file' not in request.files:
        return jsonify({"error": "لم يتم تحميل ملف"}), 400

    try:
        file = request.files['file']
        img = Image.open(io.BytesIO(file.read())).convert('RGB').resize(app.config['IMG_SIZE'])
        img_array = image.img_to_array(img) / 255.0
        img_array = np.expand_dims(img_array, axis=0)

        # (يمكنك إضافة نموذج الذكاء الاصطناعي الحقيقي هنا)
        diagnosis = "مرض افتراضي"
        confidence = 95.5

        user_id = get_jwt_identity()
        new_pred = Prediction(
            user_id=user_id,
            prediction=diagnosis,
            confidence=confidence
        )
        db.session.add(new_pred)
        db.session.commit()

        return jsonify({"diagnosis": diagnosis, "confidence": confidence}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/diseases/<string:disease_name>', methods=['GET'])
def get_disease(disease_name):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{
                "role": "user",
                "content": f"""قدم معلومات طبية مفصلة عن {disease_name} تشمل:
                1. التعريف
                2. الأعراض
                3. الأسباب
                4. الوقاية
                5. العلاجات
                6. متى يجب زيارة الطبيب"""
            }],
            temperature=0.3,
            max_tokens=500
        )
        info = response.choices[0].message.content
        return jsonify({"disease": disease_name, "information": info}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------- مسارات OAuth --------------------
@app.route('/login/google')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/login/google/callback')
def google_callback():
    try:
        token = google.authorize_access_token()
        user_info = google.parse_id_token(token)
        
        user = User.query.filter_by(email=user_info['email']).first()
        if not user:
            user = User(
                email=user_info['email'],
                name=user_info.get('name', 'مستخدم جديد'),
                social_id=user_info['sub'],
                social_provider='google'
            )
            db.session.add(user)
            db.session.commit()
        
        access_token = create_access_token(identity=user.id)
        # إعادة التوجيه مع التوكن في العنوان
        return redirect(f"/dashboard?token={access_token}")
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------- صفحة Dashboard --------------------
@app.route('/dashboard')
@jwt_required(optional=True)
def dashboard():
    return render_template_string(dashboard_html)

# -------------------- واجهات HTML مدمجة --------------------
index_html = """
<!DOCTYPE html>
<html dir="rtl">
<head>
    <title>نظام تصنيف الأمراض</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .container { border: 1px solid #ddd; padding: 20px; border-radius: 8px; }
        .form-group { margin: 10px 0; }
        input, button { padding: 8px; margin: 5px; width: 100%; }
        .prediction { background: #f0f0f0; padding: 15px; margin: 10px 0; }
        .error { color: red; }
    </style>
</head>
<body>
    <div class="container">
        <h1>نظام تصنيف الأمراض بالذكاء الاصطناعي</h1>
        
        <div id="authSection">
            <h2>تسجيل/تسجيل الدخول</h2>
            <input type="email" id="email" placeholder="البريد الإلكتروني">
            <input type="password" id="password" placeholder="كلمة المرور">
            <button onclick="register()">تسجيل جديد</button>
            <button onclick="login()">تسجيل الدخول</button>
            <button onclick="window.location.href='/login/google'">الدخول عبر جوجل</button>
            <p id="loginError" class="error"></p>
        </div>

        <div id="mainApp" style="display:none;">
            <h2>تحميل صورة طبية</h2>
            <input type="file" id="imageFile" accept="image/*">
            <button onclick="predict()">تحليل الصورة</button>
            <div class="prediction" id="predictionResult"></div>
            
            <h2>البحث عن مرض</h2>
            <input type="text" id="diseaseName" placeholder="اسم المرض">
            <button onclick="getDiseaseInfo()">الحصول على معلومات</button>
            <div class="prediction" id="diseaseInfo"></div>
        </div>
    </div>

    <script>
        async function register() {
            const response = await fetch('/api/register', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    email: document.getElementById('email').value,
                    password: document.getElementById('password').value
                })
            });
            alert(await response.text());
        }

        async function login() {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    email: document.getElementById('email').value,
                    password: document.getElementById('password').value
                })
            });

            // استرداد التوكن من العنوان وتخزينه
const urlParams = new URLSearchParams(window.location.search);
const token = urlParams.get('token');
if (token) {
    localStorage.setItem('token', token);
    window.history.replaceState({}, document.title, "/dashboard");
}

// تسجيل الخروج
function logout() {
    localStorage.removeItem('token');
    window.location.href = '/';
}
            
            if(response.ok) {
                const data = await response.json();
                localStorage.setItem('token', data.access_token);
                document.getElementById('authSection').style.display = 'none';
                document.getElementById('mainApp').style.display = 'block';
            } else {
                document.getElementById('loginError').textContent = 'فشل تسجيل الدخول!';
            }
        }

        async function predict() {
            const token = localStorage.getItem('token');
            if (!token) {
                alert('الرجاء تسجيل الدخول أولاً');
                return;
            }
            
            const formData = new FormData();
            formData.append('file', document.getElementById('imageFile').files[0]);
            
            try {
                const response = await fetch('/api/predict', {
                    method: 'POST',
                    headers: {'Authorization': 'Bearer ' + token},
                    body: formData
                });
                
                const result = await response.json();
                document.getElementById('predictionResult').innerHTML = `
                    <strong>التشخيص:</strong> ${result.diagnosis}<br>
                    <strong>مستوى الثقة:</strong> ${result.confidence}%
                `;
            } catch (error) {
                alert('حدث خطأ أثناء التحليل');
            }
        }

        async function getDiseaseInfo() {
            const disease = document.getElementById('diseaseName').value;
            try {
                const response = await fetch(`/api/diseases/${disease}`);
                const data = await response.json();
                document.getElementById('diseaseInfo').innerHTML = `
                    <h3>${data.disease}</h3>
                    <p>${data.information.replace(/\n/g, '<br>')}</p>
                `;
            } catch (error) {
                alert('حدث خطأ أثناء جلب المعلومات');
            }
        }
    </script>
</body>
</html>
"""

dashboard_html = """
<!DOCTYPE html>
<html dir="rtl">
<head>
    <title>لوحة التحكم</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        button { padding: 10px; margin: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>مرحبا بك في لوحة التحكم</h1>
        <button onclick="logout()">تسجيل الخروج</button>
        <!-- يمكنك إضافة المزيد من العناصر هنا -->
    </div>
    <script>
        // استرداد التوكن من العنوان
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('token');
        if (token) {
            localStorage.setItem('token', token);
        }

        function logout() {
            localStorage.removeItem('token');
            window.location.href = '/';
        }
    </script>
</body>
</html>
"""

# -------------------- تشغيل التطبيق --------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)