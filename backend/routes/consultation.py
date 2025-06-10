from flask import Blueprint, request, jsonify, current_app # Import current_app
from flask_jwt_extended import jwt_required
from models.patient import MedicalHistory # Import MedicalHistory for record update
from extensions import db, logger # Import logger

consultation_bp = Blueprint('consultation', __name__)

@consultation_bp.route('/consult', methods=['POST'])
@jwt_required()
def consult_disease():
    # Access the shared service instance via current_app
    consultation_service = current_app.consultation_service
    if not consultation_service:
         logger.error("Consultation service not available in /consult route.")
         return jsonify({'error': 'Consultation service is currently unavailable.'}), 503 # Service Unavailable

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON payload'}), 400

    disease_name = data.get('disease_name', '').strip()

    if not disease_name:
        logger.warning("Received /consult request with empty disease_name.")
        return jsonify({'error': 'Disease name is required'}), 400

    try:
        logger.info(f"Processing consultation request for: {disease_name}")
        consultation = consultation_service.get_disease_analysis(disease_name) # Use shared instance

        if consultation is None:
             # Service might return None on API error or empty content
             logger.warning(f"No consultation content returned for disease: {disease_name}")
             # Return 404 Not Found might be more appropriate than 500 if the service tried but found nothing
             return jsonify({'error': f'Could not retrieve consultation details for "{disease_name}".'}), 404

        logger.info(f"Successfully retrieved consultation for: {disease_name}")
        return jsonify({
            'status': 'success',
            'disease': disease_name,
            'consultation': consultation # Return the text from the service
        }), 200

    except Exception as e:
        logger.error(f"Unexpected error in /consult route for disease '{disease_name}': {str(e)}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred while processing the consultation request.'}), 500