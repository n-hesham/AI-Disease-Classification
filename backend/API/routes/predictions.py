from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import io
import numpy as np
from PIL import Image
from tensorflow.keras.preprocessing import image
from models import db, Prediction
from config import Config
from utils.model_loader import model, class_names
from flasgger import swag_from  

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
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    try:
        # قراءة ومعالجة الصورة
        file = request.files['file']
        try:
            img = Image.open(io.BytesIO(file.read()))
            img = img.convert('RGB')  # تأكد من أنها صورة ملونة
        except IOError:
            return jsonify({"error": "Invalid image format"}), 415

        img = img.resize(Config.IMG_SIZE)
        img_array = image.img_to_array(img) / 255.0
        img_array = np.expand_dims(img_array, axis=0)

        # تنفيذ التنبؤ
        pred = model.predict(img_array)
        predicted_class = np.argmax(pred, axis=1)[0]
        confidence = round(float(np.max(pred)) * 100, 2)

        # التحقق من الفهرس الصحيح
        diagnosis = class_names[predicted_class] if predicted_class < len(class_names) else "Unknown"

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
        return jsonify({"error": str(e)}), 500
