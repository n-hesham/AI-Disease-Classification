from flask import Blueprint, jsonify, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.patient import Patient, MedicalHistory
from extensions import db
from flask import current_app
import os

history_bp = Blueprint('history', __name__)

@history_bp.route('', methods=['GET'])
@jwt_required()
def get_medical_history():
    try:
        patient = Patient.query.filter_by(username=get_jwt_identity()).first()
        if not patient:
            return jsonify({"error": "Patient not found"}), 404

        histories = MedicalHistory.query.filter_by(
            patient_id=patient.id
        ).order_by(
            MedicalHistory.timestamp.desc()
        ).all()

        history_data = []
        for record in histories:
            try:
                image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], record.image_path)
                if not os.path.exists(image_path):
                    current_app.logger.warning(f"Image not found: {record.image_path}")
                    image_url = None
                else:
                    image_url = url_for('image.serve_image', filename=record.image_path, _external=True)

                history_data.append({
                    "id": record.id,
                    "image_url": image_url,
                    "diagnosis": record.diagnosis,
                    "confidence": round(float(record.confidence), 4) if record.confidence else None,
                    "timestamp": record.timestamp.isoformat() if record.timestamp else None,
                })
            except Exception as e:
                current_app.logger.error(f"Error processing record {record.id}: {str(e)}")
                continue

        return jsonify({
            "status": "success",
            "medical_history": history_data,
            "count": len(history_data)
        })

    except Exception as e:
        current_app.logger.error(f"Error in get_medical_history: {str(e)}")
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500

@history_bp.route('/<int:record_id>', methods=['DELETE'])
@jwt_required()
def delete_medical_history(record_id):
    try:
        current_user = get_jwt_identity()
        patient = Patient.query.filter_by(username=current_user).first()
        if not patient:
            return jsonify({"error": "Patient not found"}), 404

        record = MedicalHistory.query.filter_by(
            id=record_id,
            patient_id=patient.id
        ).first()

        if not record:
            return jsonify({"error": "Record not found or does not belong to the patient"}), 404

        if record.image_path:
            try:
                image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], record.image_path)
                if os.path.exists(image_path):
                    os.remove(image_path)
                    current_app.logger.info(f"Image file deleted: {image_path}")
            except Exception as e:
                current_app.logger.error(f"Error deleting image file: {str(e)}")

        db.session.delete(record)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Record deleted successfully",
            "deleted_id": record_id
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting medical record: {str(e)}")
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500