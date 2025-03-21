from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import os
import cv2
import numpy as np
import tensorflow as tf
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv
from flask import session
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename

# تحميل المتغيرات من ملف .env
load_dotenv()

# تحسين إدارة المسارات باستخدام مسارات نسبية
template_dir = r'C:\Users\Nour Hesham\Downloads\New folder\backend\templates'

# إعدادات التطبيق
app = Flask(__name__, template_folder=template_dir)

# تحميل إعدادات قاعدة البيانات من متغيرات البيئة
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'sqlite:///patients.db')  # default to SQLite
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your_default_secret_key_here')  # Secure secret key from environment
app.config['UPLOAD_FOLDER'] = os.path.join('uploads')  # تحسين مسار المجلد باستخدام مسار نسبي
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# إضافة خيارات للأمان
app.config['SESSION_COOKIE_SECURE'] = True  # إذا كان التطبيق يعمل عبر HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # فقط متصفح الويب يمكنه الوصول إلى ملفات تعريف الارتباط

# تأكد من تحميل المتغيرات
if not app.config['JWT_SECRET_KEY']:
    raise ValueError("JWT_SECRET_KEY is not set in the environment variables.")

# Initialize extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)
bcrypt = Bcrypt(app)  # تعريف واحد فقط لـ bcrypt مع سياق التطبيق
# Initialize Migrate
migrate = Migrate(app, db)

# Load the TensorFlow model
model_path = r'C:\Users\Nour Hesham\Downloads\New folder\models\save_model\model_classification.h5'
model = tf.keras.models.load_model(model_path)

# Class names for predictions
class_names = {
    0: "Bacterial Pneumonia",
    1: "Corona Virus Disease",
    2: "Edema",
    3: "Lung Opacity",
    4: "Normal",
    5: "Tuberculosis",
    6: "Viral Pneumonia"
}

# Database models
class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120))  # Ensure this column exists
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    profile_picture = db.Column(db.String(200))
    medical_histories = db.relationship('MedicalHistory', backref='patient', lazy=True)
    notifications = db.relationship('Notification', backref='patient', lazy=True)

    def __repr__(self):
        return f'<Patient {self.username}>'

    # Method to hash the password before storing it
    def set_password(self, password):
        try:
            self.password = bcrypt.generate_password_hash(password).decode('utf-8')
        except Exception as e:
            raise ValueError("Error while hashing password: " + str(e))

    # Method to check if the entered password matches the stored hash
    def check_password(self, password):
        try:
            return bcrypt.check_password_hash(self.password, password)
        except Exception as e:
            raise ValueError("Error while checking password: " + str(e))

class MedicalHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'))
    image_path = db.Column(db.String(200))
    diagnosis = db.Column(db.String(200))

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'))
    message = db.Column(db.String(200))
    read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Create the database tables for notifications and patients
with app.app_context():
    db.create_all()

# Image processing function
def process_image(file_path):
    img = cv2.imread(file_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (240, 240))
    img = img / 255.0
    return np.expand_dims(img, axis=0)

# Helper function to check allowed file extensions
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Routes
@app.route('/')
def home():
    return render_template('index.html')

# تسجيل مستخدم جديد
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Check if required fields are present
    if not data.get('username') or not data.get('password') or not data.get('name') or not data.get('email'):
        return jsonify({"error": "Username, password, name, and email are required"}), 400
    
    # Check if optional fields are present
    phone = data.get('phone')  # Optional field
    profile_picture = data.get('profile_picture')  # Optional field

    try:
        # Create new patient instance and set password using the set_password method
        new_patient = Patient(
            username=data['username'],
            name=data['name'],  # Required field
            email=data['email'],  # Required field
            phone=phone,  # Optional field
            profile_picture=profile_picture  # Optional field
        )
        new_patient.set_password(data['password'])  # Hash the password before saving

        # Add to the database
        db.session.add(new_patient)
        db.session.commit()
        return jsonify({"message": "User created successfully"}), 201
    
    except IntegrityError:
        db.session.rollback()  # Rollback in case of a conflict (e.g., duplicate username or email)
        return jsonify({"error": "Username or email already exists"}), 400
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# تسجيل الدخول
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    # التحقق من وجود المريض في قاعدة البيانات
    patient = Patient.query.filter_by(username=data['username']).first()

    if patient and patient.check_password(data['password']):  # استخدام طريقة check_password من كلاس Patient
        # إنشاء توكين الوصول (JWT)
        access_token = create_access_token(identity=data['username'])
        return jsonify(access_token=access_token), 200

    # في حال كانت البيانات غير صحيحة
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/update_profile', methods=['GET', 'POST'])
@jwt_required()  # استخدام JWT بدلاً من session
def update_profile():
    # استخدام JWT للتحقق من هوية المستخدم
    patient_username = get_jwt_identity()
    patient = Patient.query.filter_by(username=patient_username).first()

    if not patient:
        return jsonify({'message': 'Patient not found'}), 404

    if request.method == 'POST':
        # التحقق من وجود الحقول المطلوبة في طلب POST
        if 'username' in request.form:
            patient.username = request.form['username']
        if 'phone' in request.form:
            patient.phone = request.form['phone']

        # التعامل مع الصورة الشخصية الجديدة إذا كانت موجودة
        if 'profile_picture' in request.files:
            profile_picture = request.files['profile_picture']
            if profile_picture and allowed_file(profile_picture.filename):  # التحقق من نوع الملف
                # التحقق من اسم الملف وتخزينه بشكل آمن
                picture_filename = secure_filename(profile_picture.filename)
                picture_path = os.path.join(app.config['UPLOAD_FOLDER'], picture_filename)
                profile_picture.save(picture_path)
                patient.profile_picture = picture_filename  # تحديث الصورة في قاعدة البيانات
            else:
                return jsonify({'error': 'Invalid file type'}), 400

        # حفظ التعديلات في قاعدة البيانات
        db.session.commit()

        return jsonify({
            'message': 'Profile updated successfully',
            'username': patient.username,
            'phone': patient.phone,
            'profile_picture': patient.profile_picture
        }), 200

    # إذا كانت الطريقة هي GET، إرجاع بيانات المستخدم الحالية
    return jsonify({
        'username': patient.username,
        'phone': patient.phone,
        'profile_picture': patient.profile_picture
    })

@app.route('/upload', methods=['POST'])
@jwt_required()
def upload_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400
    
    # التحقق من نوع الملف
    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed"}), 400

    # Save the uploaded file
    filename = secure_filename(file.filename)  # تأمين اسم الملف
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(save_path)

    # Process the image
    processed_image = process_image(save_path)
    
    # Make a prediction
    prediction = model.predict(processed_image)
    predicted_class = np.argmax(prediction, axis=1)[0]
    diagnosis = class_names[predicted_class]

    # Save the medical history
    patient = Patient.query.filter_by(username=get_jwt_identity()).first()
    new_record = MedicalHistory(
        patient_id=patient.id,
        image_path=filename,
        diagnosis=diagnosis
    )
    db.session.add(new_record)
    db.session.commit()

    return jsonify({
        "diagnosis": diagnosis,
        "confidence": float(np.max(prediction)),
        "image_url": f"/uploads/{filename}"
    })

@app.route('/uploads/<filename>')
def serve_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# View the medical history of a patient
@app.route('/history', methods=['GET'])
@jwt_required()
def get_medical_history():
    # الحصول على هوية المستخدم من التوكن
    patient_username = get_jwt_identity()
    patient = Patient.query.filter_by(username=patient_username).first()
    
    if not patient:
        return jsonify({"error": "Patient not found"}), 404  # إذا لم يتم العثور على المريض

    # استعلام جميع السجلات الطبية المرتبطة بالمريض
    histories = MedicalHistory.query.filter_by(patient_id=patient.id).all()

    if not histories:
        return jsonify({"message": "No medical history available"}), 200  # في حال لم يكن هناك سجل طبي للمريض

    # بناء قائمة من السجلات الطبية
    history_list = [{"image_path": history.image_path, "diagnosis": history.diagnosis} for history in histories]

    return jsonify({"medical_history": history_list}), 200

# Update user password
@app.route('/update_password', methods=['PUT'])
@jwt_required()
def update_password():
    data = request.get_json()
    
    # تحقق من وجود كلمة مرور جديدة
    if not data.get('new_password'):
        return jsonify({"error": "New password is required"}), 400
    
    # تحقق من وجود كلمة مرور قديمة
    if not data.get('current_password'):
        return jsonify({"error": "Current password is required"}), 400

    patient = Patient.query.filter_by(username=get_jwt_identity()).first()

    if patient:
        # تحقق من صحة كلمة المرور القديمة باستخدام الطريقة المعرفة في كلاس Patient
        if not patient.check_password(data.get('current_password')):
            return jsonify({"error": "Current password is incorrect"}), 400
        
        # تحديث كلمة المرور الجديدة باستخدام الطريقة المعرفة في كلاس Patient
        patient.set_password(data['new_password'])
        db.session.commit()

        return jsonify({"message": "Password updated successfully"}), 200
    
    return jsonify({"error": "User not found"}), 404


# Function to send notifications
def send_notification(patient_id, message):
    if not message or len(message.strip()) == 0:  # التحقق من أن الرسالة ليست فارغة
        return False
    new_notification = Notification(
        patient_id=patient_id,
        message=message,
        timestamp=datetime.utcnow(),
        read=False  # تحديد أن الإشعار غير مقروء عند إنشائه
    )
    db.session.add(new_notification)
    db.session.commit()
    return True

# Example route to create a notification
@app.route('/send_notification', methods=['POST'])
@jwt_required()
def create_notification():
    data = request.get_json()
    patient = Patient.query.filter_by(username=get_jwt_identity()).first()
    
    if patient:
        if send_notification(patient.id, data['message']):
            return jsonify({"message": "Notification sent successfully"})
        else:
            return jsonify({"error": "Invalid message"}), 400
    return jsonify({"error": "User not found"}), 404

# Route to get notifications
@app.route('/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    patient = Patient.query.filter_by(username=get_jwt_identity()).first()
    
    if patient:
        notifications = Notification.query.filter_by(patient_id=patient.id).all()
        notification_list = [{"message": notification.message, 
                             "timestamp": notification.timestamp, 
                             "read": notification.read} for notification in notifications]
        return jsonify({"notifications": notification_list})
    return jsonify({"error": "User not found"}), 404

# Route to mark a notification as read
@app.route('/mark_notification_read/<int:notification_id>', methods=['PUT'])
@jwt_required()
def mark_notification_read(notification_id):
    patient = Patient.query.filter_by(username=get_jwt_identity()).first()
    
    if patient:
        notification = Notification.query.filter_by(id=notification_id, patient_id=patient.id).first()
        if notification:
            notification.read = True
            notification.updated_at = datetime.utcnow()  # إضافة التاريخ لتحديث الإشعار
            db.session.commit()
            return jsonify({"message": "Notification marked as read"})
        return jsonify({"error": "Notification not found"}), 404
    return jsonify({"error": "User not found"}), 404

# Delete user account
@app.route('/delete_user', methods=['DELETE'])
@jwt_required()
def delete_user():
    data = request.get_json()
    patient = Patient.query.filter_by(username=get_jwt_identity()).first()
    
    if patient:
        # التأكد من أن المستخدم يرسل كلمة مرور للتحقق قبل الحذف - استخدام طريقة check_password
        if not patient.check_password(data.get('password')):
            return jsonify({"error": "Incorrect password"}), 401
        
        # حذف الإشعارات المرتبطة بالمستخدم
        notifications = Notification.query.filter_by(patient_id=patient.id).all()
        for notification in notifications:
            db.session.delete(notification)
        
        # حذف تاريخ الطب المرتبط بالمستخدم
        medical_histories = MedicalHistory.query.filter_by(patient_id=patient.id).all()
        for history in medical_histories:
            db.session.delete(history)

        # حذف حساب المستخدم
        db.session.delete(patient)
        db.session.commit()
        
        return jsonify({"message": "User deleted successfully"})
    
    return jsonify({"error": "User not found"}), 404

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True) 
    app.run(debug=True)