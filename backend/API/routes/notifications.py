from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import Notification
from flasgger import swag_from  # ✅ استيراد Flasgger

notifications_bp = Blueprint('notifications', __name__, url_prefix='/api')

@notifications_bp.route('/notifications', methods=['GET'])
@jwt_required()
@swag_from({
    'tags': ['Notifications'],
    'summary': 'Get User Notifications',
    'description': 'Retrieve the last 10 notifications for the authenticated user.',
    'security': [{'BearerAuth': []}],  # ✅ إضافة توثيق التوكن JWT
    'responses': {
        200: {
            'description': 'List of user notifications',
            'schema': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer', 'example': 1},
                        'message': {'type': 'string', 'example': 'New prediction available'},
                        'timestamp': {'type': 'string', 'format': 'date-time', 'example': '2025-03-20T18:03:15Z'}
                    }
                }
            }
        },
        401: {'description': 'Unauthorized - Token is missing or invalid'}
    }
})
def get_notifications():
    """Get the last 10 notifications for the authenticated user"""
    user_id = get_jwt_identity()
    notifications = Notification.query.filter_by(user_id=user_id).order_by(Notification.timestamp.desc()).limit(10).all()
    
    return jsonify([{
        "id": n.id,
        "message": n.message,
        "timestamp": n.timestamp.isoformat()
    } for n in notifications]), 200
