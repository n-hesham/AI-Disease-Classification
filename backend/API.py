import os
import sqlite3
import tensorflow as tf
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
import numpy as np
from flask import Flask, request, jsonify, session
import io
from PIL import Image
from werkzeug.security import generate_password_hash, check_password_hash
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.code.get_disease_info import get_disease_info

app = Flask(__name__)
app.secret_key = "secret_key"

DATABASE = "patients.db"

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

model_path = r"E:\\capstone proj\\model\\my_model.h5"
model = None
try:
    model = load_model(model_path)
    print("✅ Model loaded successfully!")
except Exception as e:
    print(f"❌ Error loading model: {e}")

class_names = {
    0: "Bacterial Pneumonia",
    1: "Corona Virus Disease",
    2: "Edema",
    3: "Lung Opacity",
    4: "Normal",
    5: "Tuberculosis",
    6: "Viral Pneumonia"
}

IMG_SIZE = (240, 240)

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

    if user and check_password_hash(user[1], password):
        session["user_id"] = user[0]
        session["username"] = username
        return jsonify({"message": "Login successful"}), 200
    return jsonify({"error": "Invalid username or password"}), 401

@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    full_name = data.get("full_name")
    age = data.get("age")
    medical_history = data.get("medical_history", "")

    try:
        age = int(age)
    except ValueError:
        return jsonify({"error": "Age must be a valid number"}), 400

    password_hash = generate_password_hash(password)

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            return jsonify({"error": "Username already exists"}), 400

        cursor.execute("INSERT INTO users (username, password, full_name, age, medical_history) VALUES (?, ?, ?, ?, ?)",
                       (username, password_hash, full_name, age, medical_history))
        conn.commit()

    return jsonify({"message": "User registered successfully"}), 201

@app.route("/api/logout", methods=["POST"])
def logout():
    session.pop("username", None)
    return jsonify({"message": "Logged out successfully"}), 200

@app.route("/api/predict", methods=["POST"])
def predict():
    if model is None:
        return jsonify({"error": "Model is currently unavailable"}), 500

    if "file" not in request.files:
        return jsonify({"error": "No file was provided"}), 400

    file = request.files["file"]
    try:
        img = Image.open(io.BytesIO(file.read()))
        if img.mode != "RGB":
            img = img.convert("RGB")
        img = img.resize(IMG_SIZE)
        img = image.img_to_array(img)
        img = np.expand_dims(img, axis=0) / 255.0

        prediction = model.predict(img)
        predicted_class = np.argmax(prediction, axis=1)[0]
        confidence = round(float(np.max(prediction)), 2) * 100
        predicted_label = class_names.get(predicted_class, "Unknown")

        disease_info = get_disease_info(predicted_label)

        if "username" in session:
            username = session["username"]
            with sqlite3.connect(DATABASE) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO predictions (username, image_path, prediction, confidence) VALUES (?, ?, ?, ?)",
                               (username, "uploaded_image.jpg", predicted_label, confidence))
                conn.commit()

        return jsonify({"prediction": predicted_label, "confidence": confidence, "disease_info": disease_info}), 200
    except Exception as e:
        print(f"❌ Error processing image: {e}")
        return jsonify({"error": "An error occurred while processing the image"}), 400

@app.route("/api/history", methods=["GET"])
def history():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    username = session["username"]
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM predictions WHERE username = ? ORDER BY timestamp DESC", (username,))
        predictions = cursor.fetchall()

    return jsonify({"history": predictions}), 200

if __name__ == "__main__":
    init_db()
    app.run(debug=True)