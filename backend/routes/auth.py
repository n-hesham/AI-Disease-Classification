from flask import Blueprint, request, jsonify, redirect, url_for, current_app, session, make_response
from flask_jwt_extended import create_access_token, jwt_required, get_jwt, get_jwt_identity
from models.patient import Patient, PasswordResetToken
from extensions import db, mail, bcrypt, jwt, logger
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
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
import re
from itsdangerous import URLSafeTimedSerializer

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Constants for Google OAuth
SCOPES = ['openid',
          'https://www.googleapis.com/auth/userinfo.email',
          'https://www.googleapis.com/auth/userinfo.profile']

# --- HELPER FUNCTIONS ---
def get_google_flow():
    client_secrets_file = current_app.config.get('GOOGLE_CLIENT_SECRETS_FILE')
    if not client_secrets_file or not os.path.exists(client_secrets_file):
        logger.error(f"Google client secrets file not found or not configured: {client_secrets_file}")
        raise FileNotFoundError("Google client secrets file not found.")

    backend_base_url = current_app.config.get('BACKEND_BASE_URL')
    callback_path_segment = '/auth/google/callback'

    if backend_base_url:
        redirect_uri = f"{backend_base_url.rstrip('/')}{callback_path_segment}"
    else:
        logger.warning("BACKEND_BASE_URL not set in config. Attempting to generate redirect_uri with url_for().")
        try:
            redirect_uri = url_for('auth.google_callback', _external=True)
        except RuntimeError as e:
            logger.error(f"Could not generate external URL for google_callback. Error: {e}")
            raise RuntimeError("Could not determine Google redirect URI for OAuth flow.") from e

    logger.info(f"Using Google redirect URI for flow: {redirect_uri}")

    try:
        flow = Flow.from_client_secrets_file(
            client_secrets_file=client_secrets_file,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        return flow
    except ValueError as ve:
        logger.error(f"ValueError creating Google flow. Check if redirect_uri '{redirect_uri}' is listed in client_secret.json. Error: {ve}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating Google flow: {e}", exc_info=True)
        raise

def get_frontend_base_url(request_origin=None, referer=None):
    """
    Determines the frontend base URL for redirection.
    Uses session's initial origin if set, otherwise checks Origin/Referer, defaults to BACKEND_BASE_URL.
    """
    frontend_urls = [
        url.strip() for url in current_app.config.get('FRONTEND_URLS', '').split(',')
        if url.strip()
    ]
    backend_base_url = current_app.config.get('BACKEND_BASE_URL', 'https://127.0.0.1:5000').rstrip('/')

    # Log headers for debugging
    logger.debug(f"get_frontend_base_url: Origin={request_origin}, Referer={referer}, Session Origin={session.get('frontend_origin')}")

    # Use origin stored in session (set during /auth/google/login)
    session_origin = session.get('frontend_origin')
    if session_origin:
        if session_origin.startswith(backend_base_url):
            logger.info(f"Using session origin (local template): {backend_base_url}")
            return backend_base_url
        if session_origin in frontend_urls:
            logger.info(f"Using session origin (frontend): {session_origin}")
            return session_origin.rstrip('/')
        logger.warning(f"Invalid session origin: {session_origin}. Ignoring.")

    # Check Origin header
    if request_origin:
        if request_origin.startswith(backend_base_url):
            logger.info(f"Request Origin matches BACKEND_BASE_URL: {backend_base_url}")
            return backend_base_url
        if request_origin in frontend_urls:
            logger.info(f"Request Origin matches frontend URL: {request_origin}")
            return request_origin.rstrip('/')
        logger.warning(f"Unknown Origin header: {request_origin}")

    # Check Referer header
    if referer:
        if referer.startswith(backend_base_url):
            logger.info(f"Request Referer matches BACKEND_BASE_URL: {backend_base_url}")
            return backend_base_url
        for frontend_url in frontend_urls:
            if referer.startswith(frontend_url):
                logger.info(f"Request Referer matches frontend URL: {frontend_url}")
                return frontend_url.rstrip('/')
        logger.warning(f"Unknown Referer header: {referer}")

    # Default to BACKEND_BASE_URL (local template) instead of frontend
    logger.info(f"No valid Origin/Referer/Session origin. Defaulting to BACKEND_BASE_URL: {backend_base_url}")
    return backend_base_url

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    identifier = data.get('identifier')
    password = data.get('password')

    if not identifier or not password:
        return jsonify({"error": "Username/email and password required"}), 400

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
            "user": patient.to_dict()
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
    try:
        jti = get_jwt()["jti"]
        username = get_jwt_identity()
        if not hasattr(current_app, 'jwt_blocklist'):
            current_app.jwt_blocklist = set()
        current_app.jwt_blocklist.add(jti)
        logger.info(f"User {username} logged out. JTI {jti} added to in-memory blocklist.")
        return jsonify({"message": "Logged out successfully"}), 200
    except Exception as e:
        logger.error(f"Error during logout: {e}", exc_info=True)
        return jsonify({"error": "Logout failed"}), 500

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    required_fields = ['username', 'password', 'name', 'email', 'password_confirmation']
    missing_fields = [f for f in required_fields if not data.get(f)]
    if missing_fields:
        return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400

    username = data['username'].strip()
    password = data['password']
    name = data['name'].strip()
    email = data['email'].strip().lower()
    password_confirmation = data['password_confirmation']
    phone = data.get('phone', '').strip() or None

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400
    if password != password_confirmation:
        return jsonify({"error": "Passwords do not match"}), 400
    if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
        return jsonify({"error": "Invalid username format. Use letters, numbers, and . - _"}), 400
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return jsonify({"error": "Invalid email format."}), 400

    existing_google_user = Patient.query.filter(Patient.email == email, Patient.google_id != None).first()
    if existing_google_user:
        logger.warning(f"Registration attempt failed: Email {email} already linked to a Google account.")
        return jsonify({"error": "This email is registered via Google Sign-In. Please log in with Google."}), 409

    try:
        new_patient = Patient(
            username=username,
            name=name,
            email=email,
            phone=phone
        )
        new_patient.set_password(password)
        db.session.add(new_patient)
        db.session.commit()

        logger.info(f"New user registered successfully: {username} ({email})")
        access_token = create_access_token(identity=new_patient.username)
        return jsonify({
            "message": "Account created successfully",
            "access_token": access_token,
            "user": new_patient.to_dict()
        }), 201
    except IntegrityError as e:
        db.session.rollback()
        logger.warning(f"Registration failed due to integrity error: {e}")
        existing_user_email = Patient.query.filter_by(email=email).first()
        existing_user_username = Patient.query.filter_by(username=username).first()
        error_msg = "An account with this email already exists." if existing_user_email else \
                    "This username is already taken." if existing_user_username else \
                    "A database conflict occurred. Please try different details."
        return jsonify({"error": error_msg}), 409
    except ValueError as ve:
        db.session.rollback()
        logger.error(f"Registration failed for {username}: Password error - {ve}")
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error during registration for {username}: {str(e)}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred during registration."}), 500

@auth_bp.route('/google/login')
def google_login():
    try:
        flow = get_google_flow()
        state = secrets.token_urlsafe(16)
        session['auth_state'] = state

        # Store the request origin in session
        request_origin = request.headers.get('Origin')
        request_referer = request.headers.get('Referer')
        backend_base_url = current_app.config.get('BACKEND_BASE_URL', 'https://127.0.0.1:5000').rstrip('/')
        frontend_urls = [
            url.strip() for url in current_app.config.get('FRONTEND_URLS', '').split(',')
            if url.strip()
        ]

        if request_origin and (request_origin.startswith(backend_base_url) or request_origin in frontend_urls):
            session['frontend_origin'] = request_origin
            logger.info(f"Stored Origin in session: {request_origin}")
        elif request_referer and (request_referer.startswith(backend_base_url) or any(request_referer.startswith(url) for url in frontend_urls)):
            session['frontend_origin'] = backend_base_url if request_referer.startswith(backend_base_url) else next((url for url in frontend_urls if request_referer.startswith(url)), None)
            logger.info(f"Stored Referer-based origin in session: {session['frontend_origin']}")
        else:
            session['frontend_origin'] = backend_base_url
            logger.info(f"No valid Origin/Referer. Stored default origin in session: {backend_base_url}")

        authorization_url, generated_state = flow.authorization_url(
            access_type='offline',
            prompt='select_account',
            state=state
        )
        logger.info(f"Redirecting user to Google for authentication. State: {state}")
        return redirect(authorization_url)
    except FileNotFoundError as e:
        logger.error(f"Google OAuth Error: Client secrets file missing. {e}")
        return jsonify({"error": "Google authentication setup error. Please contact support."}), 500
    except Exception as e:
        logger.error(f"Error initiating Google login: {e}", exc_info=True)
        return jsonify({"error": "Could not initiate Google login."}), 500

@auth_bp.route('/google/callback')
def google_callback():
    logger.info(f"Received callback from Google. URL: {request.url}")
    request_origin = request.headers.get('Origin')
    request_referer = request.headers.get('Referer')
    frontend_base_url = get_frontend_base_url(request_origin, request_referer)

    google_error = request.args.get('error')
    if google_error:
        logger.error(f"Google returned an error during OAuth callback: {google_error}")
        error_param = urllib.parse.quote(f"Google authentication failed: {google_error}")
        error_url = f"{frontend_base_url}/?error={error_param}"
        return redirect(error_url)

    state_from_session = session.pop('auth_state', None)
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

    try:
        flow = get_google_flow()
        flow.fetch_token(authorization_response=request.url)
        logger.info("Successfully exchanged authorization code for tokens.")

        credentials = flow.credentials
        if not credentials or not credentials.id_token:
            logger.error("Failed to obtain ID token from Google.")
            raise ValueError("Missing ID token from Google response.")

        request_session = google.auth.transport.requests.Request(session=requests.session())
        id_info = id_token.verify_oauth2_token(
            credentials.id_token,
            request_session,
            credentials.client_id,
            clock_skew_in_seconds=10
        )

        google_id = id_info.get('sub')
        email = id_info.get('email')
        email_verified = id_info.get('email_verified')
        name = id_info.get('name')
        picture = id_info.get('picture')

        if not google_id or not email:
            logger.error(f"Google ID token missing 'sub' ({google_id}) or 'email' ({email}).")
            raise ValueError("Essential information (ID, Email) missing from Google profile.")
        if not email_verified:
            logger.warning(f"Google email '{email}' is not verified. Proceeding cautiously.")

        logger.info(f"Google user info retrieved: ID={google_id}, Email={email}, Name={name}")

        patient = Patient.find_by_google_id(google_id)
        needs_commit = False

        if not patient:
            patient = Patient.query.filter_by(email=email).first()
            if patient:
                if patient.password and not patient.google_id:
                    logger.info(f"Linking Google ID {google_id} to existing standard account {email}")
                    patient.google_id = google_id
                    if name and patient.name != name:
                        patient.name = name
                    if picture and patient.profile_picture == patient.get_default_profile_pic_value():
                        patient.profile_picture = picture
                    needs_commit = True
                elif patient.google_id and patient.google_id != google_id:
                    logger.error(f"CRITICAL: Email {email} already linked to Google ID {patient.google_id}, but new attempt from {google_id}.")
                    error_param = urllib.parse.quote("This email is already associated with a different Google account.")
                    error_url = f"{frontend_base_url}/?error={error_param}"
                    return redirect(error_url)
            else:
                logger.info(f"Creating new patient from Google Sign-In for email {email}")
                try:
                    patient = Patient.create_from_google({
                        'sub': google_id, 'email': email, 'name': name, 'picture': picture
                    })
                    db.session.add(patient)
                    needs_commit = True
                    logger.info(f"New patient created with username: {patient.username}")
                except (ValueError, RuntimeError, IntegrityError) as create_err:
                    db.session.rollback()
                    logger.error(f"Failed to create patient from Google data: {create_err}", exc_info=True)
                    error_param = urllib.parse.quote("Failed to create user account from Google profile.")
                    error_url = f"{frontend_base_url}/?error={error_param}"
                    return redirect(error_url)

        if patient:
            updated = False
            if name and patient.name != name:
                patient.name = name
                updated = True
            if picture and patient.profile_picture != picture:
                patient.profile_picture = picture
                updated = True
            if updated:
                logger.info(f"Updating profile details for patient {patient.username} from Google data.")
                needs_commit = True

        if needs_commit:
            try:
                db.session.commit()
                logger.info(f"Database changes committed for patient {patient.username} after Google Sign-In.")
            except IntegrityError as ie:
                db.session.rollback()
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

        if not patient:
            logger.error("Patient object is None before JWT creation in Google callback.")
            error_param = urllib.parse.quote("User authentication failed unexpectedly.")
            error_url = f"{frontend_base_url}/?error={error_param}"
            return redirect(error_url)

        access_token = create_access_token(identity=patient.username)
        logger.info(f"Generated JWT for Google authenticated user: {patient.username}")

        user_data_for_frontend = patient.to_dict()
        encoded_user_data = urllib.parse.quote(json.dumps(user_data_for_frontend))
        frontend_redirect_url = f"{frontend_base_url}/#token={access_token}&user={encoded_user_data}"
        logger.info(f"Redirecting to frontend: {frontend_base_url}/#token=...&user=...")

        # Clear session origin after use
        session.pop('frontend_origin', None)

        response = make_response(redirect(frontend_redirect_url))
        return response
    except ValueError as ve:
        db.session.rollback()
        logger.error(f"Value error during Google callback processing: {ve}", exc_info=True)
        error_param = urllib.parse.quote(f"Authentication error: {ve}")
        error_url = f"{frontend_base_url}/?error={error_param}"
        return redirect(error_url)
    except Exception as e:
        db.session.rollback()
        logger.error(f"Critical error during Google callback processing: {e}", exc_info=True)
        error_param = urllib.parse.quote("An unexpected error occurred during Google Sign-In.")
        error_url = f"{frontend_base_url}/?error={error_param}"
        return redirect(error_url)

def generate_reset_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='password-reset-salt')

def verify_reset_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=expiration)
        return email
    except Exception as e:
        return None

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.json.get('email')
    if not email:
        return jsonify({'error': 'Please enter your email address first.'}), 400

    patient = Patient.query.filter_by(email=email).first()
    if not patient:
        return jsonify({'error': 'Email not found! Please check and try again.'}), 404

    try:
        token = generate_reset_token(email)
        reset_link = url_for('auth.reset_password', token=token, _external=True)
        msg = Message('Password Reset Request', sender='noreply@wakenbake.com', recipients=[email])
        msg.body = f'Click the link to reset your password: {reset_link}'
        mail.send(msg)
        return jsonify({'message': 'Password reset link has been sent to your email!'}), 200
    except Exception as e:
        current_app.logger.error(f"Error sending email: {str(e)}")
        return jsonify({'error': 'An error occurred while sending email. Please try again.'}), 500

@auth_bp.route('/reset-password/<token>', methods=['POST'])
def reset_password():
    email = verify_reset_token(token)
    if not email:
        return jsonify({'error': 'Invalid or expired token'}), 400

    new_password = request.json.get('new_password')
    confirm_password = request.json.get('confirm_password')

    if not new_password or not confirm_password:
        return jsonify({'error': 'Please provide both new password and confirmation.'}), 400

    if new_password != confirm_password:
        return jsonify({'error': 'Passwords do not match!'}), 400

    hashed_password = generate_password_hash(new_password)
    patient = Patient.query.filter_by(email=email).first()
    if patient:
        patient.password = hashed_password
        db.session.commit()
        return jsonify({'message': 'Your password has been updated!'}), 200
    return jsonify({'error': 'User not found.'}), 404

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    current_user = get_jwt_identity()
    patient = Patient.query.filter_by(username=current_user).first()

    if not patient:
        return jsonify({'error': 'Please login first.'}), 401

    current_password = request.json.get('currentPassword')
    new_password = request.json.get('newPassword')
    confirm_password = request.json.get('confirmNewPassword')

    if not current_password or not new_password or not confirm_password:
        return jsonify({'error': 'Please provide all required fields.'}), 400

    if new_password != confirm_password:
        return jsonify({'error': 'New passwords do not match!'}), 400

    if not check_password_hash(patient.password, current_password):
        return jsonify({'error': 'Current password is incorrect!'}), 403

    patient.password = generate_password_hash(new_password)
    db.session.commit()
    return jsonify({'message': 'Your password has been changed successfully!'}), 200