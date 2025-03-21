from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import os
import io
import numpy as np
import cv2
from PIL import Image
import tensorflow as tf
from models import db, Prediction
from config import Config
from utils.model_loader import load_ai_model
from flasgger import swag_from  

# تحميل الموديل مرة واحدة عند بدء التشغيل
model = load_ai_model()

# أسماء التصنيفات
class_names = {
    0: "Bacterial Pneumonia",
    1: "COVID-19",
    2: "Edema",
    3: "Lung Opacity",
    4: "Normal",
    5: "Tuberculosis",
    6: "Viral Pneumonia"
}

# إنشاء Blueprint لـ API
predictions_bp = Blueprint('predictions', __name__)

@predictions_bp.route('/predict', methods=['POST'])
@jwt_required()
@swag_from({
    'tags': ['Prediction'],
    'summary': 'Predict Disease from Image',
    'description': 'Uploads an image and returns the AI-based disease prediction.',
    'consumes': ['multipart/form-data'],
    'security': [{'BearerAuth': []}],  
    'parameters': [
        {
            'name': 'file',
            'in': 'formData',
            'type': 'file',
            'required': True,
            'description': 'The image file for disease classification'
        }
    ],
    'responses': {
        200: {
            'description': 'Prediction result',
            'schema': {
                'type': 'object',
                'properties': {
                    'diagnosis': {'type': 'string', 'example': 'Pneumonia'},
                    'confidence': {'type': 'number', 'example': 95.2}
                }
            }
        },
        400: {'description': 'No file uploaded'},
        415: {'description': 'Invalid image format'},
        500: {'description': 'Server error'}
    }
})
def predict():
    """Predict Disease from an Uploaded Image"""
    print("🔍 Received request headers:", request.headers)  
    print("📂 Received request files:", request.files)  

    # التحقق من إرسال ملف الصورة
    if 'file' not in request.files:
        print("❌ No file uploaded!")
        return jsonify({"error": "No file uploaded"}), 400

    try:
        file = request.files['file']
        print(f"📁 Received file: {file.filename}, Type: {file.content_type}")

        # التحقق من نوع الملف
        allowed_extensions = {"jpg", "jpeg", "png"}
        file_extension = file.filename.rsplit('.', 1)[-1].lower()
        if file_extension not in allowed_extensions:
            print("❌ Unsupported file format!")
            return jsonify({"error": "Unsupported file format"}), 415

        # قراءة الصورة باستخدام OpenCV
        file_content = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(file_content, cv2.IMREAD_COLOR)
        if img is None:
            print("❌ Invalid image format!")
            return jsonify({"error": "Invalid image format"}), 415

        # تحويل BGR إلى RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, Config.IMG_SIZE)  # إعادة تحجيم الصورة
        img = img / 255.0  # تطبيع القيم بين 0 و 1
        img_array = np.expand_dims(img, axis=0)  # إضافة بُعد جديد للمصفوفة

        # تنفيذ التنبؤ
        print("🤖 Running model prediction...")
        predictions = model.predict(img_array)
        print("✅ Prediction raw output:", predictions)

        predicted_class = np.argmax(predictions, axis=1)[0]
        confidence = round(float(np.max(predictions)) * 100, 2)

        # التحقق من الفهرس الصحيح
        if predicted_class < len(class_names):
            diagnosis = class_names[predicted_class]
        else:
            diagnosis = "Unknown"

        print(f"🎯 Diagnosis: {diagnosis}, Confidence: {confidence}%")

        # حفظ التنبؤ في قاعدة البيانات
        user_id = get_jwt_identity()
        new_pred = Prediction(
            user_id=user_id,
            prediction=diagnosis,
            confidence=confidence,
            image_path=file.filename
        )
        db.session.add(new_pred)
        db.session.commit()

        return jsonify({
            "diagnosis": diagnosis,
            "confidence": confidence
        }), 200

    except Exception as e:
        print(f"❌ Server error: {str(e)}")
        return jsonify({"error": str(e)}), 500
