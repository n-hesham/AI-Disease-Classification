from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from models import db, User
from flasgger import swag_from  # ✅ استيراد Flasgger

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
@swag_from({
    'tags': ['Authentication'],
    'summary': 'Register a new user',
    'description': 'Creates a new user account with an email and password.',
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'email': {'type': 'string', 'example': 'user@example.com'},
                    'password': {'type': 'string', 'example': '123456'}
                }
            }
        }
    ],
    'responses': {
        201: {'description': 'User created successfully'},
        400: {'description': 'Missing data'},
        409: {'description': 'Email already exists'}
    }
})
def register():
    """Register a new user"""
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"error": "Missing data"}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({"error": "Email already exists"}), 409

    user = User(
        email=data['email'],
        password=generate_password_hash(data['password'])
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "User created"}), 201

@auth_bp.route('/login', methods=['POST'])
@swag_from({
    'tags': ['Authentication'],
    'summary': 'User Login',
    'description': 'Authenticates a user and returns an access token.',
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'email': {'type': 'string', 'example': 'user@example.com'},
                    'password': {'type': 'string', 'example': '123456'}
                }
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
                    'user_id': {'type': 'integer', 'example': 1}
                }
            }
        },
        401: {'description': 'Invalid credentials'}
    }
})
def login():
    """User Login"""
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()

    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({"error": "Invalid credentials"}), 401

    access_token = create_access_token(identity=user.id)
    return jsonify({
        "access_token": access_token,
        "user_id": user.id
    }), 200
