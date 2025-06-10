from flask import Blueprint, request, jsonify, current_app, send_from_directory, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.patient import Patient, MedicalHistory
from utils.image_processing import preprocess_image
from utils.notifications import send_notification as util_send_notification
from werkzeug.utils import secure_filename
import os
import uuid
import tensorflow as tf
import numpy as np
from datetime import datetime, timezone
from extensions import db, logger
import cv2

image_bp = Blueprint('image', __name__)

classification_model = None
autoencoder_model = None

def load_models():
    global classification_model, autoencoder_model

    if classification_model is None:
        try:
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            base_dir = os.path.dirname(current_file_dir)
            model_path = os.path.join(base_dir, 'model_ML', 'save_model', 'model_classification.h5')

            if not os.path.exists(model_path):
                logger.error(f"Classification model file not found: {model_path}")
            else:
                classification_model = tf.keras.models.load_model(model_path, compile=False)
                logger.info(f"Classification model loaded successfully from: {model_path}")
        except Exception as e:
            logger.error(f"Classification model load failed: {e}", exc_info=True)

    if autoencoder_model is None:
        try:
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            base_dir = os.path.dirname(current_file_dir)
            autoencoder_path = os.path.join(base_dir, 'model_ML', 'save_model', 'autoencoder_model.h5')

            if not os.path.exists(autoencoder_path):
                logger.error(f"Autoencoder model file not found: {autoencoder_path}")
            else:
                autoencoder_model = tf.keras.models.load_model(autoencoder_path, compile=False)
                logger.info(f"Autoencoder model loaded successfully from: {autoencoder_path}")
        except Exception as e:
            logger.error(f"Autoencoder model load failed: {e}", exc_info=True)

load_models()

class_names = {
    0: "Bacterial Pneumonia", 1: "Corona Virus Disease", 2: "Edema",
    3: "Lung Opacity", 4: "Normal", 5: "Tuberculosis", 6: "Viral Pneumonia"
}

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@image_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_image():
    if classification_model is None or autoencoder_model is None:
        load_models()
        if classification_model is None or autoencoder_model is None:
            logger.critical("One or more ML models are unavailable.")
            return jsonify({"error": "Service temporarily unavailable due to model loading issues.", "status": "error"}), 503

    if 'image' not in request.files:
        return jsonify({"error": "No image uploaded.", "status": "error"}), 400

    file = request.files['image']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type.", "status": "error"}), 400
    
    try:
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        if file_length > current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024):
            return jsonify({"error": "File exceeds maximum size limit.", "status": "error"}), 413
        file.seek(0)
    except Exception as e:
        logger.error(f"File size check error: {e}", exc_info=True)
        return jsonify({"error": "Could not verify file size.", "status": "error"}), 500

    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    os.makedirs(upload_folder, exist_ok=True)

    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4().hex[:8]}_{filename}"
    filepath = os.path.join(upload_folder, unique_filename)

    try:
        file.save(filepath)
    except Exception as e:
        logger.error(f"File save failed for {filepath}: {e}", exc_info=True)
        return jsonify({"error": "Failed to save the uploaded image.", "status": "error"}), 500

    try:
        img = cv2.imread(filepath)
        if img is None:
            raise ValueError("Could not read the saved image file. It might be corrupted or in an unsupported format.")
            
        image_array = preprocess_image(img)
        
        if image_array.ndim == 3:
            image_array = np.expand_dims(image_array, axis=0)

        reconstructed_array = autoencoder_model.predict(image_array)
        
        reconstruction_error = float(np.mean(np.square(reconstructed_array - image_array)))
        
        threshold = current_app.config.get('AUTOENCODER_THRESHOLD', 0.001) 
        
        logger.info(f"Image reconstruction error: {reconstruction_error:.6f} (Threshold: {threshold:.6f})")

        if reconstruction_error > threshold:
            logger.warning(f"Anomaly detected. Image rejected. Error ({reconstruction_error}) > Threshold ({threshold})")
            os.remove(filepath)
            return jsonify({
                "status": "error",
                "error": "Unknown Image Type",
                "message": "The uploaded image does not appear to be a valid chest X-ray or is of poor quality. Please upload a different image."
            }), 400

        logger.info("Image passed autoencoder validation. Proceeding to classification.")
        
        prediction = classification_model.predict(image_array)

        logger.info(f"Raw model output: {prediction[0]}")
        logger.info(f"Prediction shape: {prediction.shape}")

        # تحقق إذا كانت القيم أكبر من 1، طبق softmax، وإلا استخدم القيم كما هي
        if np.any(prediction[0] > 1) or np.any(prediction[0] < 0):
            probabilities = tf.nn.softmax(prediction[0]).numpy()
            logger.info(f"Probabilities after softmax: {probabilities}")
        else:
            probabilities = prediction[0]
            logger.info(f"Probabilities assumed from model output: {probabilities}")

        confidence = float(np.max(probabilities))
        logger.info(f"Confidence (max probability): {confidence}")

        confidence = np.clip(confidence, 0, 1)
        confidence_percentage = round(confidence * 100, 2)
        logger.info(f"Confidence percentage: {confidence_percentage}%")

        index = int(np.argmax(probabilities))
        diagnosis = class_names.get(index, "Unknown")

        consultation = ""
        warnings = []
        if diagnosis != "Normal":
            try:
                consultation = current_app.consultation_service.get_disease_analysis(diagnosis)
                if not consultation:
                    warnings.append("Consultation information is not available for this diagnosis.")
            except Exception as e:
                warnings.append("Could not retrieve consultation details due to a service error.")
                logger.error(f"Consultation service error: {e}", exc_info=True)
        else:
            consultation = "No specific consultation is required for a 'Normal' diagnosis. Follow general health guidelines."

    except Exception as e:
        logger.error(f"Image processing or prediction pipeline failed: {e}", exc_info=True)
        if os.path.exists(filepath): 
            os.remove(filepath)
        return jsonify({"error": "An error occurred during image analysis.", "status": "error"}), 500

    try:
        username = get_jwt_identity()
        patient = Patient.query.filter_by(username=username).first()
        if not patient:
            os.remove(filepath)
            return jsonify({"error": "User associated with the token not found.", "status": "error"}), 404

        record = MedicalHistory(
            patient_id=patient.id,
            image_path=unique_filename,
            diagnosis=diagnosis,
            confidence=confidence_percentage,
            timestamp=datetime.now(timezone.utc),
            consultation=consultation
        )
        db.session.add(record)
        db.session.commit()

        msg = f"New diagnosis result available: {diagnosis}. Confidence: {confidence_percentage}%"
        if not util_send_notification(patient.id, msg):
            warnings.append("Failed to send notification.")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Database operation failed: {e}", exc_info=True)
        if os.path.exists(filepath): 
            os.remove(filepath)
        return jsonify({"error": "Failed to save the diagnosis record.", "status": "error"}), 500

    return jsonify({
        "status": "success",
        "diagnosis": diagnosis,
        "confidence": confidence_percentage,
        "confidence_str": f"{confidence_percentage}%",
        "consultation": consultation,
        "record_id": record.id,
        "timestamp": record.timestamp.isoformat(),
        "warnings": warnings
    }), 200



@image_bp.route('/Uploads/<path:filename>')
def serve_image(filename):
    if not filename or '..' in filename or filename.startswith('/'):
        logger.warning(f"Invalid filename requested: {filename}")
        abort(400, description="Invalid filename.")

    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if not upload_folder:
         logger.error("UPLOAD_FOLDER not configured.")
         abort(500, description="Server configuration error.")

    file_path = os.path.join(upload_folder, filename)
    if not os.path.abspath(file_path).startswith(os.path.abspath(upload_folder)):
        logger.error(f"Directory traversal attempt detected: {filename}")
        abort(403)

    try:
        return send_from_directory(upload_folder, filename)
    except FileNotFoundError:
        logger.warning(f"Image not found: {filename} in {upload_folder}")
        abort(404, description="Image not found.")
    except Exception as e:
         logger.error(f"Error serving image {filename}: {e}", exc_info=True)
         abort(500, description="Internal server error.")
