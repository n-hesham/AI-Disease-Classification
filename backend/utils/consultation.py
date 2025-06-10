# utils/consultation_utils.py
import logging
from flask import current_app # Use current_app to access services initialized on app

# Use Flask's logger if available within request context, otherwise standard logging
# logger = current_app.logger if current_app else logging.getLogger(__name__)
# For simplicity during init, using standard logger might be safer
logger = logging.getLogger(__name__)


def get_consultation(diagnosis):
    """Fetch consultation based on diagnosis using the shared service instance."""
    if not diagnosis or not isinstance(diagnosis, str) or diagnosis.strip().lower() == "normal":
        logger.info(f"Skipping consultation fetch for diagnosis: {diagnosis}")
        return None # Return None for normal or invalid diagnosis

    diagnosis = diagnosis.strip()

    try:
        # Access the consultation_service instance attached to the current app
        if hasattr(current_app, 'consultation_service') and current_app.consultation_service:
             logger.info(f"Util: Requesting consultation for diagnosis: {diagnosis}")
             consultation_text = current_app.consultation_service.get_disease_analysis(diagnosis)
             if consultation_text:
                 logger.info(f"Util: Received consultation for diagnosis: {diagnosis}")
                 return consultation_text
             else:
                 logger.warning(f"Util: Consultation service returned None for diagnosis: {diagnosis}")
                 return None # Return None if service fails or returns nothing
        else:
             logger.error("Consultation service not initialized or available on current_app.")
             return None
    except AttributeError:
         logger.error("current_app context not available or consultation_service not attached.")
         return None
    except Exception as e:
        logger.error(f"Util: Failed to fetch consultation for '{diagnosis}': {str(e)}", exc_info=True)
        return None

# --- Parsing Functions ---
# These functions might be unnecessary if the AI consistently follows the structured prompt.
# The raw, structured text from the AI might be better to display directly.
# Keep them if you find the AI doesn't follow the structure reliably, or if you
# need to extract specific pieces of information programmatically later.

def parse_consultation(text):
    """(Optional) Parse consultation text into structured sections"""
    # ... your existing parsing logic ...
    logger.warning("parse_consultation function called - consider if direct AI output is sufficient.")
    if not text: return {}
    # ... rest of your implementation ...

def extract_section(text, keywords):
    """(Optional) Extract a section based on keywords"""
    # ... your existing extraction logic ...
     if not text: return None
     # ... rest of your implementation ...