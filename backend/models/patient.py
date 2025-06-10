import re 
from extensions import db, bcrypt, logger # Use shared logger
from datetime import datetime, timezone, timedelta
from flask import url_for, current_app # Added current_app
import secrets

# --- Database Models ---

class Patient(db.Model):
    __tablename__ = 'patient'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=True) # Allow null initially, Google might provide it
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(200), nullable=True) # Nullable for Google Sign-In users
    google_id = db.Column(db.String(200), unique=True, nullable=True, index=True) # Index for faster lookup
    phone = db.Column(db.String(30), nullable=True) # Increased length slightly
    profile_picture = db.Column(db.String(255), default='default_profile.png', nullable=False) # Increased length for potential URLs
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # --- Relationships ---
    # lazy='dynamic' allows querying the relationship before loading all items (good for large sets)
    # cascade='all, delete-orphan' ensures related objects are deleted when the patient is deleted
    medical_histories = db.relationship('MedicalHistory', backref='patient', lazy='dynamic', cascade="all, delete-orphan")
    notifications = db.relationship('Notification', backref='patient', lazy='dynamic', cascade="all, delete-orphan")
    password_reset_tokens = db.relationship('PasswordResetToken', backref='patient', lazy='dynamic', cascade="all, delete-orphan")

    # --- Class Methods ---
    @classmethod
    def find_by_google_id(cls, google_id):
        """Finds a patient by their unique Google ID."""
        if not google_id: return None
        return cls.query.filter_by(google_id=google_id).first()

    @classmethod
    def create_from_google(cls, userinfo):
        """
        Creates a new Patient instance from Google user info, without committing.
        Handles potential username collisions.
        """
        email = userinfo.get('email')
        google_id = userinfo.get('sub') # Google ID
        if not email or not google_id:
             raise ValueError("Email and Google ID (sub) are required to create user from Google info.")

        # Attempt to generate a unique username based on email prefix
        # Remove common invalid characters and truncate if needed
        base_username = re.sub(r'[^\w.-]', '', email.split('@')[0]).lower()[:50] # Limit base length
        if not base_username: # Handle cases where email prefix is empty after cleaning
             base_username = f"user{secrets.token_hex(4)}"

        username = base_username
        counter = 1
        max_attempts = 100 # Safety limit

        # Check if username already exists
        while cls.query.filter_by(username=username).first() and counter <= max_attempts:
            username = f"{base_username}{counter}"
            counter += 1

        if counter > max_attempts:
            logger.error(f"Could not generate unique username for email {email} after {max_attempts} attempts.")
            raise RuntimeError(f"Failed to generate a unique username for email {email}.")

        # Use Google picture URL directly if available, otherwise default
        profile_pic = userinfo.get('picture', cls.get_default_profile_pic_value())

        user = cls(
            username=username,
            name=userinfo.get('name', ''), # Get name from Google, default to empty string
            email=email,
            google_id=google_id,
            profile_picture=profile_pic,
            password=None # No password for Google-created accounts initially
        )
        logger.info(f"Prepared new Patient object from Google: username={username}, email={email}")
        return user

    @staticmethod
    def get_default_profile_pic_value():
        """Returns the default value for profile_picture."""
        # Accessing default directly can be tricky, defining it statically is safer
        return 'default_profile.png'

    # --- Instance Methods ---
    def set_password(self, password):
        """Hashes and sets the user's password using bcrypt."""
        if not password:
             # Allow explicitly setting password to None (e.g., if account converts)
             self.password = None
             logger.info(f"Password explicitly set to None for user {self.username}")
             return
        if len(password) < 6: # Enforce minimum length before hashing
             raise ValueError("Password must be at least 6 characters long.")
        try:
            # Generate hash with bcrypt's default rounds
            self.password = bcrypt.generate_password_hash(password).decode('utf-8')
        except Exception as e:
            logger.error(f"Error hashing password for user {self.username}: {e}", exc_info=True)
            raise ValueError("Error occurred while securing password.")

    def check_password(self, password_to_check):
        """Checks if the provided password matches the stored hash."""
        if not self.password:
            logger.debug(f"Password check failed for user {self.username}: No password set.")
            return False # User has no password set (e.g., Google Sign-In only)
        if not password_to_check:
            logger.debug(f"Password check failed for user {self.username}: Provided password was empty.")
            return False # Cannot check against an empty or None password
        try:
            return bcrypt.check_password_hash(self.password, password_to_check)
        except Exception as e:
            # Log error but return False for security
            logger.error(f"Error during check_password for user {self.username}: {e}", exc_info=True)
            return False

    def to_dict(self):
        """Serializes Patient object to a dictionary suitable for API responses."""
        # Note: generate_profile_picture_url helper should be called in the route
        # to get the absolute URL if needed. This dict contains the raw value.
        return {
            "id": self.id,
            "username": self.username,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "profile_picture": self.profile_picture, # Raw value (filename or URL)
            # "profile_picture_url": self.get_profile_picture_url(), # URL generation moved to routes
            "google_id": self.google_id,
            "has_password": bool(self.password), # Indicate if a password is set
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<Patient id={self.id} username={self.username} email={self.email}>'


class MedicalHistory(db.Model):
    __tablename__ = 'medical_history'

    id = db.Column(db.Integer, primary_key=True)
    # Ensure FK constraint references the correct table name and column
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id', ondelete='CASCADE'), nullable=False, index=True)
    image_path = db.Column(db.String(255), nullable=False) # Stored filename
    diagnosis = db.Column(db.String(200), nullable=False)
    confidence = db.Column(db.Float, nullable=True) # Allow null confidence
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    consultation = db.Column(db.Text, nullable=True) # Store consultation text

    # Removed get_image_url - URL generation belongs in the route using url_for

    def serialize(self):
        """Serializes the medical history record for API responses."""
        # URL generation is handled by the route (e.g., get_medical_history)
        return {
            "id": self.id,
            # "image_url": url_for('image.serve_image', filename=self.image_path, _external=True), # Generate URL in route
            "image_filename": self.image_path, # Send filename, let route generate URL
            "diagnosis": self.diagnosis,
            "confidence": round(float(self.confidence), 4) if self.confidence is not None else None,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "patient_id": self.patient_id, # Keep if useful for client, otherwise remove
            "consultation": self.consultation
        }

    def __repr__(self):
        return f'<MedicalHistory id={self.id} patient_id={self.patient_id} diagnosis={self.diagnosis}>'


class Notification(db.Model):
    __tablename__ = 'notification'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id', ondelete='CASCADE'), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False) # Use Text for potentially longer messages
    read = db.Column(db.Boolean, default=False, nullable=False, index=True) # Index for filtering unread
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True) # Index for sorting

    def serialize(self):
         """Serializes the notification record to a dictionary."""
         return {
             "id": self.id,
             # "patient_id": self.patient_id, # Usually not needed by the receiving user
             "message": self.message,
             "read": self.read,
             "timestamp": self.timestamp.isoformat() if self.timestamp else None,
         }

    def __repr__(self):
        return f'<Notification id={self.id} patient_id={self.patient_id} read={self.read}>'


class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_token'

    id = db.Column(db.Integer, primary_key=True)
    # Ensure FK constraint references the correct table name and column
    user_id = db.Column(db.Integer, db.ForeignKey('patient.id', ondelete='CASCADE'), nullable=False, index=True) # Index user_id
    token = db.Column(db.String(128), unique=True, nullable=False, index=True) # Index token for lookup
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def is_expired(self):
        """Checks if the token has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    def __repr__(self):
         return f'<PasswordResetToken id={self.id} user_id={self.user_id} expired={self.is_expired()}>'