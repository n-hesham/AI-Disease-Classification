from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User
import re
from flasgger import swag_from  # ✅ استيراد Flasgger

profile_bp = Blueprint('profile', __name__, url_prefix='/api')

@profile_bp.route('/profile', methods=['PUT'])
@jwt_required()
@swag_from({
    'tags': ['Profile'],
    'summary': 'Update User Profile',
    'description': 'Allows an authenticated user to update their profile details such as name and phone number.',
    'security': [{'BearerAuth': []}],  # ✅ تأمين التوكن JWT
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string', 'example': 'John Doe'},
                    'phone': {'type': 'string', 'example': '+123456789'}
                }
            }
        }
    ],
    'responses': {
        200: {'description': 'Profile updated successfully'},
        400: {'description': 'Invalid input data'},
        404: {'description': 'User not found'},
        401: {'description': 'Unauthorized - Token is missing or invalid'}
    }
})
def update_profile():
    """Update User Profile"""
    user_id = get_jwt_identity()
    data = request.get_json()

    # التحقق من صحة البيانات المدخلة
    if not data:
        return jsonify({"error": "Invalid input data"}), 400

    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        # التحقق من صحة الاسم
        if 'name' in data:
            if not isinstance(data['name'], str) or not data['name'].strip():
                return jsonify({"error": "Invalid name"}), 400
            user.name = data['name'].strip()

        # التحقق من صحة رقم الهاتف
        if 'phone' in data:
            phone_pattern = r"^\+?\d{7,15}$"  # ✅ السماح فقط بأرقام تتراوح بين 7 و 15 رقم
            if not re.match(phone_pattern, data['phone']):
                return jsonify({"error": "Invalid phone number format"}), 400
            user.phone = data['phone']

        db.session.commit()
        return jsonify({"message": "Profile updated"}), 200

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
