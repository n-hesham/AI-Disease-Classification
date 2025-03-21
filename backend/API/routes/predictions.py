from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import io
import numpy as np
import cv2
from PIL import Image
import tensorflow as tf
from models import db, Prediction
from flasgger import swag_from  

# تعريف Blueprint
predictions_bp = Blueprint('predictions', __name__)

# تحميل الموديل مباشرة داخل هذا الملف
MODEL_PATH = r"models\save_model\model_classification.h5"  # تأكد من وضع المسار الصحيح للموديل
model = tf.keras.models.load_model(MODEL_PATH)

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
        400: {'description': 'No file uploaded or invalid file'},
        415: {'description': 'Invalid image format'},
        500: {'description': 'Server error'}
    }
})
def predict():
    """Predict Disease from an Uploaded Image"""
    print("🔍 Received request headers:", request.headers)  
    print("📂 Received request files:", request.files.keys())  

    if 'file' not in request.files:
        print("❌ No file uploaded!")
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']

    if file.filename == '' or file.content_length == 0:
        print("❌ Empty file uploaded!")
        return jsonify({"error": "Uploaded file is empty"}), 400

    print(f"📁 Received file: {file.filename}, Type: {file.content_type}")

    allowed_extensions = {"jpg", "jpeg", "png"}
    file_extension = file.filename.rsplit('.', 1)[-1].lower()
    if file_extension not in allowed_extensions:
        print("❌ Unsupported file format!")
        return jsonify({"error": "Unsupported file format"}), 415

    try:
        file.stream.seek(0)
        img = Image.open(io.BytesIO(file.read()))
        img.verify()
        img = img.convert('RGB')
        img = img.resize(240,240)
        img_array = np.array(img) / 255.0
        img_array = np.expand_dims(img_array, axis=0)
    except Exception as e:
        print(f"❌ Image processing error: {str(e)}")
        return jsonify({"error": "Invalid or corrupted image file"}), 400

    try:
        print("🤖 Running model prediction...")
        predictions = model.predict(img_array)
        print("✅ Prediction raw output:", predictions)

        predicted_class = np.argmax(predictions, axis=1)[0]
        confidence = round(float(np.max(predictions)) * 100, 2)
        diagnosis = class_names.get(predicted_class, "Unknown")

        print(f"🎯 Diagnosis: {diagnosis}, Confidence: {confidence}%")

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
        print(f"❌ Model prediction error: {str(e)}")
        return jsonify({"error": "Error during prediction"}), 500