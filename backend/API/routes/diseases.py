from flask import Blueprint, jsonify
from flasgger import swag_from  # ✅ إضافة Flasgger
from services.disease_info import get_disease_info

diseases_bp = Blueprint('diseases', __name__, url_prefix='/api/diseases')

@diseases_bp.route('/<string:disease_name>', methods=['GET'])
@swag_from({
    'tags': ['Diseases'],
    'summary': 'Get disease information',
    'description': 'Retrieves detailed information about a specified disease.',
    'parameters': [
        {
            'name': 'disease_name',
            'in': 'path',
            'type': 'string',
            'required': True,
            'description': 'Name of the disease to fetch information for.'
        }
    ],
    'responses': {
        200: {
            'description': 'Disease information retrieved successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'example': 'success'},
                    'disease': {'type': 'string', 'example': 'Diabetes'},
                    'information': {'type': 'string', 'example': 'Chronic disease affecting blood sugar levels'}
                }
            }
        },
        500: {'description': 'Internal server error'}
    }
})
def get_disease(disease_name):
    """Get disease information"""
    try:
        info = get_disease_info(disease_name)
        return jsonify({
            "status": "success",
            "disease": disease_name,
            "information": info
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
