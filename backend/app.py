from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
import io
import numpy as np
from PIL import Image
from tensorflow.keras.preprocessing import image
from tensorflow.keras.models import load_model

# إعداد التطبيق
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)

# تحميل نموذج الذكاء الاصطناعي
MODEL_PATH = "model.h5"  # استبدلها بمسار النموذج الخاص بك
model = load_model(MODEL_PATH)
class_names = {0: "Healthy", 1: "Pneumonia"}  # استبدلها بالأسماء الفعلية

# 📌 نموذج المستخدم
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=True)

# 📌 نموذج الإشعارات
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)

# 📌 الصفحة الرئيسية
@app.route('/')
def home():
    return render_template('index.html')

# 📌 تسجيل مستخدم جديد
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        if User.query.filter_by(email=email).first():
            flash("Email already exists!", "danger")
            return redirect(url_for('register'))
        new_user = User(email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

# 📌 تسجيل الدخول
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash("Login successful!", "success")
            return redirect(url_for('profile'))
        flash("Invalid credentials!", "danger")
    return render_template('login.html')

# 📌 تسجيل الخروج
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))

# 📌 صفحة الملف الشخصي
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash("Please log in to view your profile.", "warning")
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('profile.html', user=user)

# 📌 صفحة التنبؤ بالأمراض
@app.route('/predict', methods=['GET', 'POST'])
def predict():
    diagnosis = None
    confidence = None

    if request.method == 'POST' and 'file' in request.files:
        file = request.files['file']
        img = Image.open(io.BytesIO(file.read())).convert('RGB')
        img = img.resize((224, 224))  # غير الحجم حسب النموذج الخاص بك
        img_array = image.img_to_array(img) / 255.0
        img_array = np.expand_dims(img_array, axis=0)

        pred = model.predict(img_array)
        predicted_class = np.argmax(pred, axis=1)[0]
        confidence = round(float(np.max(pred)) * 100, 2)
        diagnosis = class_names.get(predicted_class, "Unknown")

    return render_template('predict.html', diagnosis=diagnosis, confidence=confidence)

# 📌 صفحة الإشعارات
@app.route('/notifications')
def notifications():
    if 'user_id' not in session:
        flash("Please log in to view notifications.", "warning")
        return redirect(url_for('login'))
    user_notifications = Notification.query.filter_by(user_id=session['user_id']).all()
    return render_template('notifications.html', notifications=user_notifications)

# 📌 تشغيل التطبيق
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
