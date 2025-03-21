from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    create_refresh_token,
    get_jwt_identity
)
from models import db, User
from flasgger import swag_from
import re
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

def validate_email(email):
    """Validates email format using regex."""
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validates password complexity (min 8 chars, letters and numbers)."""
    if len(password) < 8:
        return False
    if not re.search("[a-zA-Z]", password) or not re.search("[0-9]", password):
        return False
    return True

@auth_bp.route('/register', methods=['POST'])
@swag_from({
    'tags': ['Authentication'],
    'summary': 'Register a new user',
    'description': 'Creates a new user account with email and password after validation.',
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'email': {'type': 'string', 'example': 'user@example.com'},
                    'password': {'type': 'string', 'example': 'SecurePass123'}
                },
                'required': ['email', 'password']
            }
        }
    ],
    'responses': {
        201: {'description': 'User created successfully'},
        400: {'description': 'Invalid input data'},
        409: {'description': 'Email already exists'},
        500: {'description': 'Server error'}
    }
})
def register():
    """
    Registers a new user with validated email and password.
    """
    data = request.get_json()
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({"error": "Email and password are required"}), 400

    email = data['email'].strip().lower()
    password = data['password']

    if not validate_email(email):
        return jsonify({"error": "Invalid email format"}), 400

    if not validate_password(password):
        return jsonify({
            "error": "Password must be at least 8 characters and include both letters and numbers"
        }), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    try:
        user = User(
        email=email,
        password=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        return jsonify({"message": "User created successfully"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Server error: Unable to create user"}), 500

@auth_bp.route('/login', methods=['POST'])
@swag_from({
    'tags': ['Authentication'],
    'summary': 'Authenticate user',
    'description': 'Returns JWT access and refresh tokens upon successful authentication.',
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'email': {'type': 'string', 'example': 'user@example.com'},
                    'password': {'type': 'string', 'example': 'SecurePass123'}
                },
                'required': ['email', 'password']
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Login successful',
            'schema': {
                'type': 'object',
                'properties': {
                    'access_token': {'type': 'string', 'example': 'eyJhbGciOiJI...'},
                    'refresh_token': {'type': 'string', 'example': 'eyJhbGciOiJI...'},
                    'user_id': {'type': 'integer', 'example': 1},
                    'email': {'type': 'string', 'example': 'user@example.com'}
                }
            }
        },
        400: {'description': 'Missing credentials'},
        401: {'description': 'Invalid credentials'}
    }
})
def login():
    """
    Authenticates user and returns JWT tokens.
    """
    data = request.get_json()
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({"error": "Email and password required"}), 400

    email = data['email'].strip().lower()
    password = data['password']

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password, password):
        return jsonify({"error": "Invalid email or password"}), 401

    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()

    # Generate tokens
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_id": user.id,
        "email": user.email
    }), 200

@auth_bp.route('/refresh', methods=['POST'])
@swag_from({
    'tags': ['Authentication'],
    'summary': 'Refresh access token',
    'description': 'Generates new access token using refresh token.',
    'security': [{'BearerAuth': []}],
    'responses': {
        200: {
            'description': 'Token refreshed',
            'schema': {
                'type': 'object',
                'properties': {
                    'access_token': {'type': 'string', 'example': 'eyJhbGciOiJI...'}
                }
            }
        },
        401: {'description': 'Invalid refresh token'}
    }
})
@jwt_required(refresh=True)
def refresh():
    """
    Generates new access token using refresh token.
    """
    current_user = get_jwt_identity()
    new_token = create_access_token(identity=current_user)
    return jsonify({"access_token": new_token}), 200

@auth_bp.route('/protected', methods=['GET'])
@swag_from({
    'tags': ['Authentication'],
    'summary': 'Protected endpoint',
    'description': 'Accessible only with valid JWT token.',
    'security': [{'BearerAuth': []}],
    'responses': {
        200: {'description': 'Access granted'},
        401: {'description': 'Missing or invalid token'}
    }
})
@jwt_required()
def protected():
    """
    Example protected endpoint requiring JWT authentication.
    """
    return jsonify({"message": "Protected content accessed successfully"}), 200