from extensions import db
from models.patient import Notification
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

def send_notification(patient_id, message):
    """
    Creates and saves a new notification for a patient.

    Args:
        patient_id (int): The ID of the patient to notify.
        message (str): The notification message.

    Returns:
        bool: True if the notification was sent, False otherwise.
    """
    if not message or not message.strip():
        logger.warning("Attempted to send empty notification message.")
        return False
        
    try:
        new_notification = Notification(
            patient_id=patient_id,
            message=message.strip(), # Ensure no leading/trailing whitespace
            timestamp=datetime.now(timezone.utc),
            read=False
        )
        db.session.add(new_notification)
        db.session.commit()
        logger.info(f"Notification sent to patient {patient_id}: '{message[:50]}...'")
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to send notification to patient {patient_id}: {str(e)}")
        return False

