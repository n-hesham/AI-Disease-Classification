# backend/routes/profile.py
from flask import Blueprint, request, jsonify, url_for, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from models.patient import Patient, Notification, MedicalHistory
from routes.image import allowed_file 
from extensions import db, logger 
import os
import uuid
import re

profile_bp = Blueprint('profile', __name__, url_prefix='/profile')

# Basic email format validation (Keep this)
def is_valid_email(email):
    """Validates email format using regex."""
    # Slightly improved regex for common cases
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_regex, email) is not None

# --- Helper Function for Profile Picture URL ---
def generate_profile_picture_url(profile_picture_value):
    """
    Generates the correct absolute profile picture URL.
    Handles external URLs (Google) and local filenames.
    Args:
        profile_picture_value (str): The value stored in the patient's profile_picture field.
    Returns:
        str or None: The absolute URL or None if no picture or error.
    """
    if not profile_picture_value or profile_picture_value == 'default_profile.png':
        return None # Return None for default or empty

    # If it's already a full external URL (like from Google)
    if profile_picture_value.startswith(('http://', 'https://')):
        return profile_picture_value

    # Otherwise, assume it's a local filename and generate URL via the image serving endpoint
    try:
        with current_app.app_context(): # Ensure context for url_for if needed
            return url_for('image.serve_image', filename=profile_picture_value, _external=True)
    except Exception as url_error:
        current_app.logger.error(f"Error generating URL for local profile picture '{profile_picture_value}': {str(url_error)}")
        return None # Fallback if URL generation fails

# === Endpoint: Fetch User Profile ===
@profile_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """
    Fetches the profile information for the currently authenticated user.
    Returns:
        JSON: User profile data or an error message.
    """
    current_username = None
    try:
        current_username = get_jwt_identity()
        if not current_username:
            current_app.logger.warning("get_profile: JWT token missing user identity.")
            return jsonify({"error": "Invalid token or user identity missing"}), 401

        patient = Patient.query.filter_by(username=current_username).first()
        if not patient:
            current_app.logger.warning(f"get_profile: Patient profile not found for username: {current_username}")
            return jsonify({"error": "Patient profile not found"}), 404

        # --- CORRECTED: Use helper function to get URL ---
        profile_pic_url = generate_profile_picture_url(patient.profile_picture)
        # --- END CORRECTION ---

        # Prepare the data to be returned
        # Send both the raw stored value and the generated URL for flexibility
        profile_data = {
            "id": patient.id,
            "username": patient.username,
            "name": patient.name,
            "email": patient.email,
            "phone": patient.phone,
            "profile_picture": patient.profile_picture, # Raw value (URL or filename)
            "profile_picture_url": profile_pic_url # Generated absolute URL (or None)
        }

        return jsonify(profile_data), 200

    except Exception as e:
        # Log the error with traceback for debugging
        current_app.logger.error(f"Error fetching profile for {current_username}: {str(e)}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred while fetching the profile."}), 500

# === Endpoint: Update User Profile ===
@profile_bp.route('/update_profile', methods=['POST'])
@jwt_required()
def update_profile():
    """
    Updates profile info (name, phone, profile picture).
    Expects multipart/form-data.
    Returns JSON with success message and updated user data or an error message.
    """
    current_username = get_jwt_identity()
    if not current_username: # Should not happen with @jwt_required, but check
        return jsonify({"error": "Invalid token or user identity missing"}), 401

    patient = Patient.query.filter_by(username=current_username).first()
    if not patient:
        current_app.logger.warning(f"update_profile: Patient profile not found for username: {current_username}")
        return jsonify({"error": "Patient profile not found"}), 404

    needs_commit = False
    updated_fields_log = []
    upload_folder = current_app.config.get('UPLOAD_FOLDER')

    if not upload_folder:
         current_app.logger.error("update_profile: UPLOAD_FOLDER not configured.")
         return jsonify({"error": "Server configuration error (upload folder)."}), 500

    try:
        # --- Process Form Data ---
        new_name = request.form.get('name')
        new_phone = request.form.get('phone')

        if new_name is not None:
            new_name = new_name.strip()
            if not new_name: # Check if name is empty after stripping
                 return jsonify({"error": "Name cannot be empty"}), 400
            if new_name != patient.name:
                patient.name = new_name
                needs_commit = True
                updated_fields_log.append('name')

        if new_phone is not None:
             new_phone = new_phone.strip()
             if new_phone != (patient.phone or ''): # Compare with existing or empty string
                 patient.phone = new_phone if new_phone else None # Store None if empty
                 needs_commit = True
                 updated_fields_log.append('phone')

        # --- Process File Upload ---
        new_profile_pic_filename = None
        old_picture_to_delete = None # Store filename to delete AFTER commit
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename: # Check if a file was actually selected
                if allowed_file(file.filename):
                    filename_base = secure_filename(file.filename)
                    unique_suffix = uuid.uuid4().hex[:8]
                    new_profile_pic_filename = f"{unique_suffix}_{filename_base}"
                    save_path = os.path.join(upload_folder, new_profile_pic_filename)

                    # Store old picture path for deletion later if needed
                    if patient.profile_picture and \
                       patient.profile_picture != 'default_profile.png' and \
                       not patient.profile_picture.startswith(('http://', 'https://')):
                        old_picture_to_delete = os.path.join(upload_folder, patient.profile_picture)

                    # Save the new picture file
                    try:
                        os.makedirs(upload_folder, exist_ok=True) # Ensure directory exists
                        file.save(save_path)
                        logger.info(f"Saved new profile picture: {save_path}")
                        # Update patient record with the NEW FILENAME
                        patient.profile_picture = new_profile_pic_filename
                        needs_commit = True
                        updated_fields_log.append('profile_picture')
                    except Exception as save_err:
                         logger.error(f"Error saving profile picture {save_path}: {save_err}", exc_info=True)
                         # Don't proceed if saving failed
                         return jsonify({"error": "Failed to save new profile picture."}), 500
                else:
                    return jsonify({"error": "Invalid file type for profile picture."}), 400
            # else: No file selected, empty filename, ignore.

        # --- Commit Changes to Database ---
        if needs_commit:
            try:
                db.session.commit()
                logger.info(f"Profile updated for {current_username}. Fields: {', '.join(updated_fields_log)}")

                # --- Delete Old Picture File (AFTER successful commit) ---
                if old_picture_to_delete and os.path.exists(old_picture_to_delete):
                    try:
                        os.remove(old_picture_to_delete)
                        logger.info(f"Deleted old profile picture file: {old_picture_to_delete}")
                    except Exception as del_err:
                        # Log error but don't fail the request
                        logger.error(f"Error deleting old profile picture {old_picture_to_delete}: {del_err}")

            except Exception as db_error:
                db.session.rollback()
                logger.error(f"Database error updating profile for {current_username}: {str(db_error)}", exc_info=True)
                return jsonify({"error": "Failed to save profile changes to the database."}), 500

        # --- Prepare and Return Response ---
        # Fetch potentially updated patient data (or refresh existing)
        db.session.refresh(patient) # Ensure patient object reflects committed state

        # Generate the correct URL for the response using the helper
        final_profile_picture_url = generate_profile_picture_url(patient.profile_picture)

        response_user_data = {
            "id": patient.id,
            "username": patient.username,
            "name": patient.name,
            "email": patient.email,
            "phone": patient.phone,
            "profile_picture": patient.profile_picture, # Send raw value
            "profile_picture_url": final_profile_picture_url # Send generated absolute URL
        }

        return jsonify({
            "message": "Profile updated successfully" if needs_commit else "No changes detected.",
            "user": response_user_data
        }), 200

    except Exception as e:
        # Catch unexpected errors during the process
        db.session.rollback() # Rollback just in case
        logger.error(f"Unexpected error updating profile for {current_username}: {str(e)}", exc_info=True)
        return jsonify({"error": "An unexpected server error occurred."}), 500


# === Endpoint: Update User Password ===
@profile_bp.route('/update_password', methods=['PUT'])
@jwt_required()
def update_password():
    """Updates the password for the currently authenticated user."""
    patient_username = get_jwt_identity()
    logger.info(f"Attempting password update for user: {patient_username}")
    data = request.get_json()

    if not data:
        logger.warning(f"Update password ({patient_username}): No JSON data.")
        return jsonify({"error": "Invalid request format."}), 400

    current_password = data.get('current_password')
    new_password = data.get('new_password')
    # Optional: Backend validation for password confirmation
    # password_confirmation = data.get('password_confirmation')

    if not current_password or not new_password:
        logger.warning(f"Update password ({patient_username}): Missing fields.")
        return jsonify({"error": "Current password and new password are required."}), 400
    # Add length check on backend too
    if len(new_password) < 6:
        return jsonify({"error": "New password must be at least 6 characters."}), 400
    # if new_password != password_confirmation: # Uncomment if frontend doesn't validate confirmation
    #     return jsonify({"error": "New passwords do not match."}), 400

    patient = Patient.query.filter_by(username=patient_username).first()
    if not patient:
        logger.error(f"Update password ({patient_username}): User not found.")
        return jsonify({"error": "User not found"}), 404

    # Check if the user has a password set (might be a Google-only user)
    if not patient.password:
         logger.warning(f"Update password ({patient_username}): Attempted password change for account without a password (Google Sign-In?).")
         return jsonify({"error": "Password cannot be changed for this account type."}), 400 # 400 or 403 might be appropriate

    if not patient.check_password(current_password):
        logger.warning(f"Update password ({patient_username}): Incorrect current password.")
        return jsonify({"error": "Incorrect current password"}), 401

    try:
        patient.set_password(new_password) # Hashes the new password
        db.session.commit()
        logger.info(f"Update password ({patient_username}): Success.")
        return jsonify({"message": "Password updated successfully"}), 200
    except ValueError as ve: # Catch specific errors from set_password if any
         logger.error(f"Update password ({patient_username}): Validation error - {ve}")
         return jsonify({"error": str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Update password ({patient_username}): DB error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to update password due to a server error"}), 500


@profile_bp.route('/delete_user', methods=['DELETE'])
@jwt_required()
def delete_user():
    """
    Deletes the user account and associated data.
    Requires password confirmation for standard accounts.
    Allows deletion without password for Google-only accounts (assumes frontend confirmation).
    """
    patient_username = get_jwt_identity()
    logger.info(f"Attempting account deletion for user: {patient_username}")

    patient = Patient.query.filter_by(username=patient_username).first()
    if not patient:
        logger.error(f"Delete user ({patient_username}): User not found despite valid JWT.")
        return jsonify({"error": "User not found"}), 404

    is_google_account = not patient.password and patient.google_id
    data = request.get_json() # Get JSON data AFTER finding the patient

    # --- Confirmation Logic ---
    if not is_google_account:
        # --- Standard Account: Requires Password ---
        if not data:
            logger.warning(f"Delete user ({patient_username}): No JSON data received for standard account.")
            return jsonify({"error": "Password confirmation required."}), 400

        password = data.get('password')
        if not password:
            logger.warning(f"Delete user ({patient_username}): Password not provided for standard account deletion.")
            return jsonify({"error": "Password is required to delete this account"}), 400

        if not hasattr(patient, 'check_password'): # Defensive check
             logger.error(f"Delete user ({patient_username}): Patient model missing 'check_password'.")
             return jsonify({"error": "Server configuration error."}), 500

        if not patient.check_password(password):
            logger.warning(f"Delete user ({patient_username}): Incorrect password provided.")
            return jsonify({"error": "Incorrect password"}), 401 # Use 401 Unauthorized

        logger.info(f"Delete user ({patient_username}): Password verified for standard account.")
        # Proceed to deletion

    else:
        # --- Google Account: No Password Check Needed (Frontend should confirm) ---
        # We assume the frontend has adequately confirmed the user's intent.
        # No password is required or expected in the request body for Google users.
        logger.info(f"Delete user ({patient_username}): Proceeding with deletion for Google account (no password check).")
        # Proceed to deletion

    # --- Deletion Process ---
    try:
        patient_id_for_deletion = patient.id
        profile_pic_to_delete = patient.profile_picture # Get value before deletion
        upload_folder = current_app.config.get('UPLOAD_FOLDER')
        logger.info(f"Delete user ({patient_username}): Deleting patient record.")
        db.session.delete(patient)
        db.session.commit() # Commit the deletion
        logger.info(f"Delete user ({patient_username}): Database records deleted successfully.")

        if upload_folder and profile_pic_to_delete and \
           profile_pic_to_delete != 'default_profile.png' and \
           not profile_pic_to_delete.startswith(('http://', 'https://')):
            file_path = os.path.join(upload_folder, profile_pic_to_delete)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Delete user ({patient_username}): Deleted profile picture file '{file_path}'.")
                except OSError as e:
                    logger.error(f"Delete user ({patient_username}): Error deleting profile picture file '{file_path}': {str(e)}")
            else:
                 logger.warning(f"Delete user ({patient_username}): Profile picture file '{file_path}' not found for cleanup.")

        # Optionally add the user's JTI to a longer-term blocklist if needed

        return jsonify({"message": "User account and associated data deleted successfully"}), 200

    except Exception as e:
        db.session.rollback() # Rollback any partial changes
        logger.error(f"Delete user ({patient_username}): Error during deletion process: {str(e)}", exc_info=True)
        return jsonify({'error': f'Failed to delete user account due to a server error'}), 500