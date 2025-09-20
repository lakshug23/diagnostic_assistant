"""
Authentication and security utilities for MedSAGE application
"""
import hashlib
import secrets
import re
from functools import wraps
from flask import session, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import jwt

class SecurityManager:
    """Handles authentication and security operations."""
    
    @staticmethod
    def generate_secure_token():
        """Generate a cryptographically secure token."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_password(password):
        """Hash a password using werkzeug's secure method."""
        return generate_password_hash(password)
    
    @staticmethod
    def verify_password(password_hash, password):
        """Verify a password against its hash."""
        return check_password_hash(password_hash, password)
    
    @staticmethod
    def validate_file_type(filename):
        """Validate uploaded file type."""
        if not filename:
            return False
        
        allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', set())
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in allowed_extensions
    
    @staticmethod
    def sanitize_filename(filename):
        """Sanitize filename to prevent directory traversal."""
        # Remove path components and keep only filename
        filename = filename.split('/')[-1].split('\\')[-1]
        # Remove potentially dangerous characters
        filename = re.sub(r'[^\w\-_\.]', '', filename)
        return filename
    
    @staticmethod
    def validate_input(data, required_fields):
        """Validate required input fields."""
        missing_fields = []
        for field in required_fields:
            if field not in data or not data[field]:
                missing_fields.append(field)
        return missing_fields
    
    @staticmethod
    def generate_session_token():
        """Generate a secure session token."""
        return secrets.token_hex(32)

def require_auth(f):
    """Decorator to require authentication for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Check session timeout
        if 'last_activity' in session:
            last_activity = datetime.fromisoformat(session['last_activity'])
            if datetime.now() - last_activity > timedelta(hours=2):
                session.clear()
                return jsonify({'error': 'Session expired'}), 401
        
        session['last_activity'] = datetime.now().isoformat()
        return f(*args, **kwargs)
    return decorated_function

def rate_limit(max_requests=100, window_minutes=60):
    """Simple rate limiting decorator."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            
            # In production, implement Redis-based rate limiting
            # For now, this is a basic implementation
            rate_limit_key = f"rate_limit:{client_ip}:{f.__name__}"
            
            # This would be stored in Redis in production
            # For now, we'll allow all requests but log them
            current_app.logger.info(f"Rate limit check for {client_ip} on {f.__name__}")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_medical_data(data):
    """Validate medical data inputs."""
    errors = []
    
    # Age validation
    if 'age' in data:
        try:
            age = int(data['age'])
            if age < 0 or age > 150:
                errors.append("Age must be between 0 and 150")
        except (ValueError, TypeError):
            errors.append("Age must be a valid number")
    
    # Weight validation
    if 'weight' in data:
        try:
            weight = float(data['weight'])
            if weight < 0 or weight > 1000:
                errors.append("Weight must be between 0 and 1000 kg")
        except (ValueError, TypeError):
            errors.append("Weight must be a valid number")
    
    # Height validation
    if 'height' in data:
        try:
            height = float(data['height'])
            if height < 0 or height > 300:
                errors.append("Height must be between 0 and 300 cm")
        except (ValueError, TypeError):
            errors.append("Height must be a valid number")
    
    # Symptoms validation
    if 'symptoms' in data:
        symptoms = data['symptoms']
        if isinstance(symptoms, str):
            symptoms = [s.strip() for s in symptoms.split(',')]
        if not symptoms or len(symptoms) == 0:
            errors.append("At least one symptom is required")
        elif len(symptoms) > 20:
            errors.append("Maximum 20 symptoms allowed")
    
    return errors
