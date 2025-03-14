import os
import sqlite3
import tensorflow as tf
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
import numpy as np
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import io
from PIL import Image
from werkzeug.security import generate_password_hash, check_password_hash  # تم إضافته
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.code.get_disease_info import get_disease_info


# تهيئة تطبيق Flask
template_dir = os.path.abspath("frontend-web/templates")
app = Flask(__name__, template_folder=template_dir)
app.secret_key = "secret_key"  # مفتاح الجلسة

# قاعدة البيانات
DATABASE = "patients.db"

# إنشاء قاعدة البيانات والجداول إذا لم تكن موجودة
def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                full_name TEXT NOT NULL,
                age INTEGER NOT NULL,
                medical_history TEXT
            )"""
        )
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                image_path TEXT NOT NULL,
                prediction TEXT NOT NULL,
                confidence REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (username) REFERENCES users (username)
            )"""
        )
        conn.commit()

# تحميل النموذج
model_path = r"E:\capstone proj\model\my_model.h5"
model = None
try:
    model = load_model(model_path)
    print("✅ Model loaded successfully!")
except Exception as e:
    print(f"❌ Error loading model: {e}")

# أسماء التصنيفات
class_names = {
    0: "Bacterial Pneumonia",
    1: "Corona Virus Disease",
    2: "Edema",
    3: "Lung Opacity",
    4: "Normal",
    5: "Tuberculosis",
    6: "Viral Pneumonia"
}

# حجم الصورة المطلوب للنموذج
IMG_SIZE = (240, 240)

# الصفحة الرئيسية
@app.route("/")
def home():
    return render_template("index.html", prediction=None, confidence=None)

# صفحة تسجيل الدخول
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user:
            stored_password_hash = user[1]
            if check_password_hash(stored_password_hash, password):
                session["user_id"] = user[0]
                session["username"] = username  # تصحيح تعيين اسم المستخدم
                return redirect(url_for("history"))  # تأكد من أن لديك دالة `dashboard`
            else:
                return render_template("login.html", error="Invalid password.")
        else:
            return render_template("login.html", error="User not found.")

    return render_template("login.html")


# صفحة إنشاء الحساب
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        full_name = request.form["full_name"]
        age = request.form["age"]
        medical_history = request.form.get("medical_history", "")

        try:
            age = int(age)  # التأكد من أن العمر عدد صحيح
        except ValueError:
            return render_template("signup.html", error="Age must be a valid number.")

        # تشفير كلمة المرور قبل حفظها في قاعدة البيانات
        password_hash = generate_password_hash(password)

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            existing_user = cursor.fetchone()

            if existing_user:
                return render_template("signup.html", error="Username already exists. Choose another.")

            cursor.execute(
                "INSERT INTO users (username, password, full_name, age, medical_history) VALUES (?, ?, ?, ?, ?)",
                (username, password_hash, full_name, age, medical_history)
            )
            conn.commit()

        return redirect(url_for("login"))

    return render_template("signup.html")

# تسجيل الخروج
@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))

# التنبؤ بالصورة
@app.route("/predict", methods=["POST"])
def predict():
    if model is None:
        return jsonify({"error": "Model is currently unavailable"}), 500

    if "file" not in request.files:
        return jsonify({"error": "No file was provided"}), 400

    file = request.files["file"]
    
    try:
        img = Image.open(io.BytesIO(file.read()))

        # تحويل الصورة إلى RGB إذا لم تكن بالفعل
        if img.mode != "RGB":
            img = img.convert("RGB")

        img = img.resize(IMG_SIZE)
        img = image.img_to_array(img)
        img = np.expand_dims(img, axis=0)
        img = img / 255.0  # تطبيع البيانات

        # إجراء التنبؤ
        prediction = model.predict(img)
        predicted_class = np.argmax(prediction, axis=1)[0]
        confidence = round(float(np.max(prediction)), 2) * 100

        predicted_label = class_names.get(predicted_class, "Unknown")

        # 🔹 استدعاء API للحصول على معلومات المرض
        disease_info = get_disease_info(predicted_label)

        # حفظ التنبؤ في قاعدة البيانات إذا كان المستخدم مسجل الدخول
        if "username" in session:
            username = session["username"]
            with sqlite3.connect(DATABASE) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO predictions (username, image_path, prediction, confidence) VALUES (?, ?, ?, ?)",
                    (username, "uploaded_image.jpg", predicted_label, confidence),
                )
                conn.commit()

        # 🔹 إرسال معلومات المرض إلى القالب
        return render_template("index.html", prediction=predicted_label, confidence=confidence, disease_info=disease_info)

    except Exception as e:
        print(f"❌ Error processing image: {e}")
        return jsonify({"error": "An error occurred while processing the image"}), 400

# سجل تاريخ المريض
@app.route("/history")
def history():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM predictions WHERE username = ? ORDER BY timestamp DESC", (username,))
        predictions = cursor.fetchall()

    return render_template("history.html", predictions=predictions)

# تشغيل التطبيق
if __name__ == "__main__":
    init_db()  # إنشاء قاعدة البيانات عند تشغيل التطبيق
    app.run(debug=True)
