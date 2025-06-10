from flask import Blueprint, request, jsonify, redirect, url_for, current_app, session, make_response
from flask_jwt_extended import create_access_token, jwt_required, get_jwt, get_jwt_identity
from models.patient import Patient, PasswordResetToken
from extensions import db, mail, bcrypt, jwt, logger # Use shared logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
import requests
from datetime import datetime, timedelta, timezone
from flask_mail import Message
import secrets
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests
from google.oauth2 import id_token
import pathlib
import os
import json
import urllib.parse
import re # Import re for regex validation

auth_bp = Blueprint('auth', __name__, url_prefix='/auth') # Define url_prefix here

# Constants for Google OAuth
SCOPES = ['openid',
          'https://www.googleapis.com/auth/userinfo.email',
          'https://www.googleapis.com/auth/userinfo.profile']

# --- HELPER FUNCTIONS ---
# auth.py

# --- HELPER FUNCTIONS ---
def get_google_flow():
    client_secrets_file = current_app.config.get('GOOGLE_CLIENT_SECRETS_FILE')
    if not client_secrets_file or not os.path.exists(client_secrets_file):
        logger.error(f"Google client secrets file not found or not configured: {client_secrets_file}")
        raise FileNotFoundError("Google client secrets file not found.")

    # الطريقة الموصى بها: الاعتماد على BACKEND_BASE_URL من .env
    backend_base_url = current_app.config.get('BACKEND_BASE_URL')
    callback_path_segment = '/auth/google/callback' # مسار الكول باك ثابت

    if backend_base_url:
        redirect_uri = f"{backend_base_url.rstrip('/')}{callback_path_segment}"
    else:
        # كحل بديل إذا لم يتم تعيين BACKEND_BASE_URL (غير مثالي لـ ngrok)
        logger.warning("BACKEND_BASE_URL not set in config. Attempting to generate redirect_uri with url_for(). "
                       "For ngrok or reverse proxies, BACKEND_BASE_URL is strongly recommended.")
        try:
            # هذا يتطلب أن يكون لدى Flask وعي بعنوانه الخارجي، مثلاً عبر SERVER_NAME أو Werkzeug's ProxyFix
            redirect_uri = url_for('auth.google_callback', _external=True)
        except RuntimeError as e:
            logger.error(f"Could not generate external URL for google_callback. "
                         f"Ensure SERVER_NAME is configured or BACKEND_BASE_URL is set in .env. Error: {e}")
            # إذا كان BACKEND_BASE_URL مطلوبًا للغاية، يمكنك رفع خطأ هنا
            raise RuntimeError("Could not determine Google redirect URI for OAuth flow. BACKEND_BASE_URL is missing.") from e

    logger.info(f"Using Google redirect URI for flow: {redirect_uri}")

    try:
        flow = Flow.from_client_secrets_file(
            client_secrets_file=client_secrets_file,
            scopes=SCOPES,
            redirect_uri=redirect_uri  # هذا هو redirect_uri الذي سيتم استخدامه
        )
        return flow
    except ValueError as ve: # قد يحدث هذا إذا كان redirect_uri غير موجود في client_secret.json
        logger.error(f"ValueError creating Google flow. Check if redirect_uri ('{redirect_uri}') "
                     f"is listed in client_secret.json. Error: {ve}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating Google flow: {e}", exc_info=True)
        raise


def get_frontend_base_url():
    """
    Dynamically gets the base URL for the frontend from config.
    Falls back to a default if not set.
    """
    config_url = current_app.config.get('FRONTEND_URL')
    if config_url:
        return config_url.rstrip('/')
    else:
        logger.warning("FRONTEND_URL not set in config. Falling back to 'http://localhost:3000'. "
                       "Ensure FRONTEND_URL is set in .env for correct link generation.")
        return "http://localhost:3000" # أو أي قيمة افتراضية تراها مناسبة

# ... (بقية الكود في auth.py كما هو) ...

# --- Rate Limiting Placeholder ---
# Add rate limiting using Flask-Limiter or similar in production
# Example decorator (apply to login, register, forgot-password): @limiter.limit("5 per minute")

@auth_bp.route('/login', methods=['POST'])
# @limiter.limit("10 per minute") # Example placeholder
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    identifier = data.get('identifier')
    password = data.get('password')

    if not identifier or not password:
        return jsonify({"error": "Username/email and password required"}), 400

    # Use lowercase for email comparison if identifier might be email
    identifier_lower = identifier.strip().lower()
    identifier_strip = identifier.strip()

    patient = Patient.query.filter(
        or_(Patient.username == identifier_strip, Patient.email == identifier_lower)
    ).first()

    if patient and patient.password and patient.check_password(password):
        access_token = create_access_token(identity=patient.username)
        logger.info(f"Successful login for user: {patient.username}")
        return jsonify({
            "message": "Login successful",
            "access_token": access_token,
            "user": patient.to_dict() # Use a method on the model for serialization
        }), 200
    elif patient and not patient.password and patient.google_id:
         logger.warning(f"Login attempt for Google-linked account ({identifier}) with password.")
         return jsonify({"error": "Please log in using your Google account."}), 401
    else:
        logger.warning(f"Invalid login attempt for identifier: {identifier}")
        return jsonify({"error": "Invalid credentials"}), 401

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    # Basic logout using the in-memory blocklist (See extensions.py note)
    try:
        jti = get_jwt()["jti"]
        username = get_jwt_identity()
        # Ensure the blocklist attribute exists on the app
        if not hasattr(current_app, 'jwt_blocklist'):
            current_app.jwt_blocklist = set() # Initialize if missing (should be done in factory)

        current_app.jwt_blocklist.add(jti)
        logger.info(f"User {username} logged out. JTI {jti} added to in-memory blocklist.")
        # NOTE: For production, use a persistent blocklist (Redis, DB).
        return jsonify({"message": "Logged out successfully"}), 200
    except Exception as e:
        logger.error(f"Error during logout: {e}", exc_info=True)
        return jsonify({"error": "Logout failed"}), 500


@auth_bp.route('/register', methods=['POST'])
# @limiter.limit("5 per hour") # Example placeholder
def register():
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid JSON payload"}), 400

    required_fields = ['username', 'password', 'name', 'email', 'password_confirmation']
    missing_fields = [f for f in required_fields if not data.get(f)]
    if missing_fields:
        return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400

    # --- Input Validation & Sanitization ---
    username = data['username'].strip()
    password = data['password'] # Keep original for checks
    name = data['name'].strip()
    email = data['email'].strip().lower()
    password_confirmation = data['password_confirmation']
    phone = data.get('phone', '').strip() or None # Store None if empty after stripping

    # Password Policy
    if len(password) < 6: return jsonify({"error": "Password must be at least 6 characters."}), 400
    if password != password_confirmation: return jsonify({"error": "Passwords do not match"}), 400

    # Username Format Validation (Example: alphanumeric, underscore, dot, hyphen)
    if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
         return jsonify({"error": "Invalid username format. Use letters, numbers, and . - _"}), 400

    # Email Format Validation (Basic)
    # Consider a more robust library like 'email-validator' if needed
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return jsonify({"error": "Invalid email format."}), 400

    # Check if email is already linked to a Google account
    existing_google_user = Patient.query.filter(Patient.email == email, Patient.google_id != None).first()
    if existing_google_user:
        logger.warning(f"Registration attempt failed: Email {email} already linked to a Google account.")
        return jsonify({"error": "This email is registered via Google Sign-In. Please log in with Google."}), 409 # 409 Conflict

    # --- Create Patient ---
    try:
        new_patient = Patient(
            username=username,
            name=name,
            email=email,
            phone=phone
            # profile_picture uses default from model
        )
        new_patient.set_password(password) # Hash password
        db.session.add(new_patient)
        db.session.commit()

        logger.info(f"New user registered successfully: {username} ({email})")
        access_token = create_access_token(identity=new_patient.username)
        return jsonify({
            "message": "Account created successfully",
            "access_token": access_token,
            "user": new_patient.to_dict() # Use serialization method
        }), 201 # 201 Created

    except IntegrityError as e:
        db.session.rollback()
        logger.warning(f"Registration failed due to integrity error: {e}")
        # Check which constraint failed (more robust check might be needed depending on DB)
        existing_user_email = Patient.query.filter_by(email=email).first()
        existing_user_username = Patient.query.filter_by(username=username).first()
        error_msg = "An account with this email already exists." if existing_user_email else \
                    "This username is already taken." if existing_user_username else \
                    "A database conflict occurred. Please try different details."
        return jsonify({"error": error_msg}), 409 # 409 Conflict
    except ValueError as ve: # Catch password hashing errors (e.g., from set_password)
        db.session.rollback()
        logger.error(f"Registration failed for {username}: Password error - {ve}")
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error during registration for {username}: {str(e)}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred during registration."}), 500


# === Google OAuth Routes ===

@auth_bp.route('/google/login')
def google_login():
    """Initiates the Google OAuth 2.0 authentication flow."""
    try:
        flow = get_google_flow()
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(16)
        session['oauth_state'] = state # Store state in server-side session

        authorization_url, generated_state = flow.authorization_url(
            access_type='offline', # Request refresh token if needed later
            prompt='select_account', # Force account selection
            state=state # Pass the generated state to Google
        )

        logger.info(f"Redirecting user to Google for authentication. State: {state}")
        return redirect(authorization_url)
    except FileNotFoundError as e:
        logger.error(f"Google OAuth Error: Client secrets file missing. {e}")
        # Redirect to an error page or return JSON
        return jsonify({"error": "Google authentication setup error. Please contact support."}), 500
    except Exception as e:
        logger.error(f"Error initiating Google login: {e}", exc_info=True)
        return jsonify({"error": "Could not initiate Google login."}), 500


@auth_bp.route('/google/callback')
def google_callback():
    """Handles the callback from Google after user authentication."""
    logger.info(f"Received callback from Google. URL: {request.url}")
    frontend_base_url = get_frontend_base_url()

    # --- Error Handling: Check for Google's error response ---
    google_error = request.args.get('error')
    if google_error:
        logger.error(f"Google returned an error during OAuth callback: {google_error}")
        error_param = urllib.parse.quote(f"Google authentication failed: {google_error}")
        error_url = f"{frontend_base_url}/?error={error_param}" # Redirect to frontend with error
        return redirect(error_url)

    # --- CSRF Protection: Verify State ---
    state_from_session = session.pop('oauth_state', None)
    state_from_google = request.args.get('state')

    if not state_from_session:
        logger.error("OAuth State missing from session. Possible session issue or direct access attempt.")
        error_param = urllib.parse.quote("Authentication session expired or invalid. Please try again.")
        error_url = f"{frontend_base_url}/?error={error_param}"
        return redirect(error_url)

    if not state_from_google or state_from_session != state_from_google:
        logger.error(f"OAuth State mismatch. Session: '{state_from_session}', Google: '{state_from_google}'. Possible CSRF attack.")
        error_param = urllib.parse.quote("Authentication security check failed. Please try again.")
        error_url = f"{frontend_base_url}/?error={error_param}"
        return redirect(error_url)

    # --- Authorization Code Exchange ---
    try:
        flow = get_google_flow()
        # Use the full callback URL to fetch the token
        flow.fetch_token(authorization_response=request.url)
        logger.info("Successfully exchanged authorization code for tokens.")

        credentials = flow.credentials
        if not credentials or not credentials.id_token:
             logger.error("Failed to obtain ID token from Google.")
             raise ValueError("Missing ID token from Google response.")

        # --- Verify ID Token and Get User Info ---
        request_session = google.auth.transport.requests.Request(session=requests.session())
        id_info = id_token.verify_oauth2_token(
            credentials.id_token,
            request_session,
            credentials.client_id,
            clock_skew_in_seconds=10 # Allow small clock differences
        )

        google_id = id_info.get('sub')
        email = id_info.get('email')
        email_verified = id_info.get('email_verified')
        name = id_info.get('name')
        picture = id_info.get('picture') # Google profile picture URL

        # --- Validate Essential Information ---
        if not google_id or not email:
            logger.error(f"Google ID token missing 'sub' ({google_id}) or 'email' ({email}).")
            raise ValueError("Essential information (ID, Email) missing from Google profile.")
        if not email_verified:
            logger.warning(f"Google email '{email}' is not verified. Proceeding cautiously.")
            # Decide policy: Allow unverified? Reject? Require verification step?
            # For now, allow but log.

        logger.info(f"Google user info retrieved: ID={google_id}, Email={email}, Name={name}")

        # --- Find or Create/Update Patient Record ---
        patient = Patient.find_by_google_id(google_id)
        needs_commit = False

        if not patient:
            # No patient with this Google ID exists. Check by email.
            patient = Patient.query.filter_by(email=email).first()
            if patient:
                # Email exists. Link Google ID if it's a standard account.
                if patient.password and not patient.google_id:
                     logger.info(f"Linking Google ID {google_id} to existing standard account {email}")
                     patient.google_id = google_id
                     # Optionally update name/picture if Google's is preferred and current one is default
                     if name and patient.name != name: patient.name = name
                     if picture and patient.profile_picture == patient.get_default_profile_pic_value():
                         patient.profile_picture = picture # Store Google URL
                     needs_commit = True
                elif patient.google_id and patient.google_id != google_id:
                     # Conflict: Email already linked to a *different* Google ID. Critical error.
                     logger.error(f"CRITICAL: Email {email} already linked to Google ID {patient.google_id}, but new attempt from {google_id}.")
                     error_param = urllib.parse.quote("This email is already associated with a different Google account.")
                     error_url = f"{frontend_base_url}/?error={error_param}"
                     return redirect(error_url)
                # else: Email exists and is already linked to THIS Google ID. No linking change needed.
                # Still might need profile update below.

            else:
                # No existing account by Google ID or email. Create a new patient.
                logger.info(f"Creating new patient from Google Sign-In for email {email}")
                try:
                    # Use a dedicated class method for clarity if preferred
                    patient = Patient.create_from_google({
                        'sub': google_id, 'email': email, 'name': name, 'picture': picture
                    })
                    db.session.add(patient)
                    needs_commit = True # Mark for commit
                    logger.info(f"New patient created with username: {patient.username}")
                except (ValueError, RuntimeError, IntegrityError) as create_err:
                    db.session.rollback()
                    logger.error(f"Failed to create patient from Google data: {create_err}", exc_info=True)
                    error_param = urllib.parse.quote("Failed to create user account from Google profile.")
                    error_url = f"{frontend_base_url}/?error={error_param}"
                    return redirect(error_url)

        # --- Update Existing Patient Info (if needed) ---
        # This handles both newly linked accounts and existing Google users
        if patient: # Ensure patient exists before updating
            updated = False
            if name and patient.name != name:
                patient.name = name
                updated = True
            # Update picture only if Google provides one and it differs from the current one
            # Don't overwrite a custom uploaded picture with the Google one unless desired.
            # Current logic updates if picture provided by Google differs.
            if picture and patient.profile_picture != picture:
                 # Maybe only update if current is default or also a Google URL? Policy decision.
                 # This replaces any existing picture (local or google) with the latest from google.
                 patient.profile_picture = picture
                 updated = True
            if updated:
                 logger.info(f"Updating profile details for patient {patient.username} from Google data.")
                 needs_commit = True


        # --- Commit DB Changes ---
        if needs_commit:
            try:
                db.session.commit()
                logger.info(f"Database changes committed for patient {patient.username} after Google Sign-In.")
            except IntegrityError as ie:
                 db.session.rollback()
                 # This might happen if a race condition occurred (e.g., username clash)
                 logger.error(f"DB integrity error during Google commit for {email}: {ie}", exc_info=True)
                 error_param = urllib.parse.quote("Database conflict occurred while saving user data.")
                 error_url = f"{frontend_base_url}/?error={error_param}"
                 return redirect(error_url)
            except Exception as e:
                db.session.rollback()
                logger.error(f"DB error during Google commit for {email}: {e}", exc_info=True)
                error_param = urllib.parse.quote("Database error occurred while saving user data.")
                error_url = f"{frontend_base_url}/?error={error_param}"
                return redirect(error_url)

        # --- Create JWT Token ---
        if not patient: # Should not happen if error handling above is correct
            logger.error("Patient object is None before JWT creation in Google callback.")
            error_param = urllib.parse.quote("User authentication failed unexpectedly.")
            error_url = f"{frontend_base_url}/?error={error_param}"
            return redirect(error_url)

        access_token = create_access_token(identity=patient.username)
        logger.info(f"Generated JWT for Google authenticated user: {patient.username}")

        # --- Redirect to Frontend with Token & User Info ---
        # Pass token and user data in the URL hash fragment for frontend JS to parse
        user_data_for_frontend = patient.to_dict() # Use serialization method

        # URL-encode the JSON string of user data
        encoded_user_data = urllib.parse.quote(json.dumps(user_data_for_frontend))

        # Construct the redirect URL (using hash fragment #)
        frontend_redirect_url = f"{frontend_base_url}/#token={access_token}&user={encoded_user_data}"
        logger.info(f"Redirecting to frontend: {frontend_base_url}/#token=...&user=...")

        response = make_response(redirect(frontend_redirect_url))
        # Potentially set secure, HttpOnly cookies here if needed (e.g., for refresh tokens)
        return response

    except ValueError as ve: # Catch specific errors like token verification failure
        db.session.rollback()
        logger.error(f"Value error during Google callback processing: {ve}", exc_info=True)
        error_param = urllib.parse.quote(f"Authentication error: {ve}")
        error_url = f"{frontend_base_url}/?error={error_param}"
        return redirect(error_url)
    except Exception as e:
        db.session.rollback() # Ensure rollback on any unexpected error
        logger.error(f"Critical error during Google callback processing: {e}", exc_info=True)
        error_param = urllib.parse.quote("An unexpected error occurred during Google Sign-In.")
        error_url = f"{frontend_base_url}/?error={error_param}"
        return redirect(error_url)


# --- Password Reset Routes ---

@auth_bp.route('/forgot-password', methods=['POST'])
# @limiter.limit("3 per hour") # Example placeholder
def forgot_password():
    """Handles the request to send a password reset link."""
    data = request.get_json()
    if not data or not data.get('email'):
        return jsonify({"error": "Email is required"}), 400

    email = data['email'].strip().lower()
    # Basic email format check
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return jsonify({"error": "Invalid email format."}), 400

    patient = Patient.query.filter_by(email=email).first()
    reset_link_sent = False # Flag to track if link sending was attempted

    if not patient:
        logger.info(f"Password reset requested for non-existent email: {email}")
        # Do not reveal if email exists - return generic message
    elif not patient.password and patient.google_id:
        logger.info(f"Password reset requested for Google-linked account: {email}. Not sending link.")
        # Return specific error *only* for Google accounts, as they cannot reset this way.
        return jsonify({"error": "This account uses Google Sign-In. Password reset is not applicable via email."}), 400
    elif not patient.password:
        # Edge case: Account exists but has no password and no Google ID (should ideally not happen)
         logger.warning(f"Password reset requested for account {email} with no password and no Google ID. Not sending link.")
         # Return generic message
    else:
        # Account exists and uses standard password - proceed
        try:
            # Invalidate previous tokens for this user
            PasswordResetToken.query.filter_by(user_id=patient.id).delete()

            # Create new token
            token_value = secrets.token_urlsafe(32)
            expires = datetime.now(timezone.utc) + timedelta(hours=1) # 1-hour expiry
            reset_token = PasswordResetToken(user_id=patient.id, token=token_value, expires_at=expires)
            db.session.add(reset_token)
            db.session.commit()

            # --- Link Generation ---
            # IMPORTANT: The frontend needs to handle this URL format.
            # It receives "?token=VALUE" but the reset endpoint is "/reset-password/<token>"
            # Frontend JS must extract VALUE from the query param and make a POST request to the correct endpoint.
            frontend_base = get_frontend_base_url()
            # Using query parameter as per original code, document frontend requirement:
            reset_url = f"{frontend_base}/?resetToken={token_value}" # Use a distinct param name
            # Alternative (requires frontend change AND endpoint change):
            # reset_url = f"{frontend_base}/reset-password/{token_value}"
            logger.info(f"Generated password reset URL (query param format): {reset_url} for {email}")

            # --- Send Email ---
            msg = Message(
                subject="Password Reset Request - Radiology DX",
                sender=current_app.config['MAIL_DEFAULT_SENDER'],
                recipients=[patient.email]
            )
            # Ensure email body is clean
            msg.body = (
                f"You requested a password reset for your Radiology DX account associated with {patient.email}.\n\n"
                f"Please click the link below or paste it into your browser to set a new password:\n"
                f"{reset_url}\n\n"
                f"This link is valid for 1 hour.\n\n"
                f"If you did not request this, please ignore this email. Your password will remain unchanged.\n\n"
                f"Thank you,\nThe Radiology DX Team"
            )
            # Consider using HTML templates for better formatting: msg.html = render_template(...)

            mail.send(msg)
            logger.info(f"Password reset email sent successfully to {email}")
            reset_link_sent = True

        except Exception as e:
            db.session.rollback() # Rollback token creation on error
            logger.error(f"Error processing password reset for {email}: {e}", exc_info=True)
            # Do not expose internal errors to the user
            return jsonify({"error": "Could not process password reset request due to a server error."}), 500

    # Always return a generic success message unless it was a specific known issue (like Google account)
    # This prevents attackers from enumerating registered emails.
    return jsonify({"message": "If an account exists for this email and uses password login, a reset link has been sent. Please check your inbox (and spam folder)."}), 200


@auth_bp.route('/reset-password/<token>', methods=['POST'])
def reset_password(token):
    """Handles setting the new password using a valid reset token from the URL path."""
    logger.info(f"Attempting password reset with token: {token[:6]}...") # Log partial token

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request format."}), 400

    new_password = data.get('password')
    password_confirmation = data.get('password_confirmation')

    # --- Validation ---
    if not new_password or not password_confirmation:
        return jsonify({"error": "New password and confirmation are required."}), 400
    if new_password != password_confirmation:
        return jsonify({"error": "Passwords do not match."}), 400
    if len(new_password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    # --- Token Validation ---
    reset_token = PasswordResetToken.query.filter_by(token=token).first()

    if not reset_token:
        logger.warning(f"Password reset attempt with invalid token: {token[:6]}...")
        return jsonify({"error": "Password reset link is invalid or has already been used. Please request a new one."}), 400 # 400 Bad Request

    if reset_token.is_expired():
        logger.warning(f"Password reset attempt with expired token: {token[:6]}...")
        # Clean up expired token
        db.session.delete(reset_token)
        db.session.commit()
        return jsonify({"error": "Password reset link has expired. Please request a new one."}), 400 # 400 Bad Request

    # --- Find Patient ---
    patient = Patient.query.get(reset_token.user_id)
    if not patient:
         # This indicates a data inconsistency (token exists for deleted user)
         logger.error(f"Password reset token {token[:6]}... linked to non-existent user ID {reset_token.user_id}. Deleting token.")
         db.session.delete(reset_token)
         db.session.commit()
         # Return generic invalid link error
         return jsonify({"error": "Password reset link is invalid."}), 400

    # --- Update Password ---
    try:
        patient.set_password(new_password)
        db.session.delete(reset_token) # Invalidate token immediately after use
        db.session.commit()
        logger.info(f"Password successfully reset for user {patient.username} (Token: {token[:6]}...)")
        # Send success message - user can now log in
        return jsonify({"message": "Password updated successfully. You can now log in with your new password."}), 200
    except ValueError as ve: # Catch password hashing errors
         db.session.rollback()
         logger.error(f"Error hashing new password during reset for token {token[:6]}...: {ve}", exc_info=True)
         return jsonify({"error": "Failed to set new password due to validation error."}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating password during reset for token {token[:6]}...: {e}", exc_info=True)
        return jsonify({"error": "Failed to update password due to a server error."}), 500

# Example/Test route for sending email - Remove in production
@auth_bp.route('/send_email_test')
def send_email_test():
    # Ensure MAIL config is set before using this
    if not all([current_app.config.get('MAIL_SERVER'), current_app.config.get('MAIL_USERNAME')]):
         return "Mail configuration is incomplete. Cannot send test email.", 500
    try:
        msg = Message(
            subject="Test Email from Radiology DX",
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=["test@example.com"], # CHANGE TO A REAL TEST ADDRESS
            body="This is a test email sent from the Flask application."
        )
        mail.send(msg)
        logger.info("Test email sent successfully.")
        return "Test email sent!", 200
    except Exception as e:
        logger.error(f"Failed to send test email: {e}", exc_info=True)
        return f"Failed to send test email: {e}", 500