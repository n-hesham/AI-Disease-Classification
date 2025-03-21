from flask import Blueprint, request, jsonify, redirect, url_for, session
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    create_refresh_token,
    get_jwt_identity)
from authlib.integrations.flask_client import OAuth
from models import db, User
import json
from config import Config
import os
from flasgger import swag_from  # ✅ استيراد Flasgger

social_auth_bp = Blueprint('social_auth', __name__)

oauth = OAuth()

# ✅ إعداد Google OAuth
# في ملف routes/social_auth.py
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile',
        'redirect_uri': 'http://localhost:5000/api/auth/social/google/callback'  # تأكد من المطابقة
    }
)

# ✅ إعداد Facebook OAuth
facebook = oauth.register(
    name='facebook',
    client_id=Config.FACEBOOK_CLIENT_ID,
    client_secret=Config.FACEBOOK_CLIENT_SECRET,
    access_token_url='https://graph.facebook.com/oauth/access_token',
    authorize_url='https://www.facebook.com/dialog/oauth',
    api_base_url='https://graph.facebook.com/',
    client_kwargs={'scope': 'email public_profile'}
)

# ✅ إعداد Apple OAuth
apple = oauth.register(
    name='apple',
    client_id=Config.APPLE_CLIENT_ID,
    client_secret=Config.APPLE_CLIENT_SECRET,
    server_metadata_url='https://appleid.apple.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'email name'}
)

# ✅ توثيق Google OAuth Login
@social_auth_bp.route('/login/google')
@swag_from({
    'tags': ['OAuth Login'],
    'summary': 'Google OAuth Login',
    'description': 'Redirects the user to Google for authentication and returns an access token.',
    'responses': {302: {'description': 'Redirect to Google login page'}}
})
def google_login():
    redirect_uri = url_for('social_auth.google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@social_auth_bp.route('/login/google/callback')
@swag_from({
    'tags': ['OAuth Login'],
    'summary': 'Google OAuth Callback',
    'description': 'Handles Google login callback and returns an access token.',
    'responses': {302: {'description': 'Redirect to frontend with access token'}}
})
def google_callback():
    try:
        token = google.authorize_access_token()
        user_info = google.parse_id_token(token)

        if not user_info or 'email' not in user_info:
            return jsonify({"error": "Failed to retrieve user info"}), 400

        user = User.query.filter_by(email=user_info['email']).first()
        if not user:
            user = User(
                email=user_info['email'],
                name=user_info.get('name', ''),
                avatar=user_info.get('picture', ''),
                social_id=user_info['sub'],
                social_provider='google'
            )
            db.session.add(user)
            db.session.commit()

        access_token = create_access_token(identity=user.id)
        return redirect(f"YOUR_FRONTEND_URL/oauth-callback?token={access_token}")

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ توثيق Facebook OAuth Login
@social_auth_bp.route('/login/facebook')
@swag_from({
    'tags': ['OAuth Login'],
    'summary': 'Facebook OAuth Login',
    'description': 'Redirects the user to Facebook for authentication and returns an access token.',
    'responses': {302: {'description': 'Redirect to Facebook login page'}}
})
def facebook_login():
    redirect_uri = url_for('social_auth.facebook_callback', _external=True)
    return facebook.authorize_redirect(redirect_uri)

@social_auth_bp.route('/login/facebook/callback')
@swag_from({
    'tags': ['OAuth Login'],
    'summary': 'Facebook OAuth Callback',
    'description': 'Handles Facebook login callback and returns an access token.',
    'responses': {302: {'description': 'Redirect to frontend with access token'}}
})
def facebook_callback():
    try:
        token = facebook.authorize_access_token()
        resp = facebook.get('me', params={'fields': 'id,name,email,picture'})
        user_info = resp.json()

        if not user_info or 'email' not in user_info:
            return jsonify({"error": "Failed to retrieve user info"}), 400

        user = User.query.filter_by(email=user_info['email']).first()
        if not user:
            user = User(
                email=user_info['email'],
                name=user_info.get('name', ''),
                avatar=user_info.get('picture', {}).get('data', {}).get('url', ''),
                social_id=user_info['id'],
                social_provider='facebook'
            )
            db.session.add(user)
            db.session.commit()

        access_token = create_access_token(identity=user.id)
        return redirect(f"YOUR_FRONTEND_URL/oauth-callback?token={access_token}")

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ توثيق Apple OAuth Login
@social_auth_bp.route('/login/apple')
@swag_from({
    'tags': ['OAuth Login'],
    'summary': 'Apple OAuth Login',
    'description': 'Redirects the user to Apple for authentication and returns an access token.',
    'responses': {302: {'description': 'Redirect to Apple login page'}}
})
def apple_login():
    redirect_uri = url_for('social_auth.apple_callback', _external=True)
    return apple.authorize_redirect(redirect_uri)

@social_auth_bp.route('/login/apple/callback')
@swag_from({
    'tags': ['OAuth Login'],
    'summary': 'Apple OAuth Callback',
    'description': 'Handles Apple login callback and returns an access token.',
    'responses': {302: {'description': 'Redirect to frontend with access token'}}
})
def apple_callback():
    try:
        token = apple.authorize_access_token()
        user_info = apple.parse_id_token(token)

        if not user_info or 'email' not in user_info:
            return jsonify({"error": "Failed to retrieve user info"}), 400

        user = User.query.filter_by(email=user_info['email']).first()
        if not user:
            user = User(
                email=user_info['email'],
                name=user_info.get('name', {}).get('firstName', '') + ' ' + user_info.get('name', {}).get('lastName', ''),
                social_id=user_info['sub'],
                social_provider='apple'
            )
            db.session.add(user)
            db.session.commit()

        access_token = create_access_token(identity=user.id)
        return redirect(f"YOUR_FRONTEND_URL/oauth-callback?token={access_token}")

    except Exception as e:
        return jsonify({"error": str(e)}), 500
