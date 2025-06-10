from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.patient import Patient, Notification
from extensions import db
from datetime import datetime, timezone

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('', methods=['GET'])
@jwt_required()
def get_notifications():
    current_username = get_jwt_identity()
    patient = Patient.query.filter_by(username=current_username).first()
    if not patient:
        return jsonify({"error": "User not found"}), 404

    # Order by timestamp descending to show newest first
    notifications = Notification.query.filter_by(patient_id=patient.id)\
                                  .order_by(Notification.timestamp.desc())\
                                  .all()
    notification_list = []
    for notification in notifications:
        notification_list.append({
            "id": notification.id,  # <<< --- ADD THIS LINE --- <<<
            "message": notification.message,
            "timestamp": notification.timestamp.isoformat(), # Already good
            "read": notification.read
        })
    return jsonify({"notifications": notification_list, "status": "success"}) # Added status


@notifications_bp.route('/send_notification', methods=['POST'])
@jwt_required()
def create_notification():
    data = request.get_json()
    patient = Patient.query.filter_by(username=get_jwt_identity()).first()
    if patient:
        if send_notification(patient.id, data['message']):
            return jsonify({"message": "Notification sent successfully"})
        else:
            return jsonify({"error": "Invalid message"}), 400
    return jsonify({"error": "User not found"}), 404

@notifications_bp.route('/mark_notification_read/<int:notification_id>', methods=['PUT'])
@jwt_required()
def mark_notification_read(notification_id):
    patient = Patient.query.filter_by(username=get_jwt_identity()).first()
    if not patient:
        return jsonify({"error": "User not found"}), 404

    notification = Notification.query.filter_by(id=notification_id, patient_id=patient.id).first()
    if notification:
        notification.read = True
        notification.timestamp = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({"message": "Notification marked as read"})
    return jsonify({"error": "Notification not found"}), 404

def send_notification(patient_id, message):
    if not message.strip():
        return False
    new_notification = Notification(
        patient_id=patient_id,
        message=message,
        timestamp=datetime.now(timezone.utc),
        read=False
    )
    db.session.add(new_notification)
    db.session.commit()
    return True