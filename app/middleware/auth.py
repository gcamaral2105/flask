"""
Authentication Middleware
========================

Basic authentication middleware for the ERP Bauxita system.
"""

import jwt
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app, g
from werkzeug.security import check_password_hash, generate_password_hash

logger = logging.getLogger(__name__)


class AuthService:
    """Service for handling authentication operations."""
    
    @staticmethod
    def generate_token(user_data: dict, expires_in: int = 3600) -> str:
        """
        Generate JWT token for user.
        
        Args:
            user_data: User information to encode in token
            expires_in: Token expiration time in seconds
            
        Returns:
            JWT token string
        """
        payload = {
            'user_id': user_data.get('id'),
            'username': user_data.get('username'),
            'role': user_data.get('role', 'user'),
            'exp': datetime.utcnow() + timedelta(seconds=expires_in),
            'iat': datetime.utcnow()
        }
        
        secret_key = current_app.config.get('SECRET_KEY', 'dev-secret')
        return jwt.encode(payload, secret_key, algorithm='HS256')
    
    @staticmethod
    def verify_token(token: str) -> dict:
        """
        Verify JWT token and return payload.
        
        Args:
            token: JWT token string
            
        Returns:
            Token payload if valid
            
        Raises:
            jwt.ExpiredSignatureError: If token is expired
            jwt.InvalidTokenError: If token is invalid
        """
        secret_key = current_app.config.get('SECRET_KEY', 'dev-secret')
        return jwt.decode(token, secret_key, algorithms=['HS256'])
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password for storage."""
        return generate_password_hash(password)
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        return check_password_hash(password_hash, password)


def get_token_from_request() -> str:
    """Extract token from request headers."""
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header.split(' ')[1]
    return None


def authenticate_request():
    """Authenticate current request and set user context."""
    token = get_token_from_request()
    
    if not token:
        return None
    
    try:
        payload = AuthService.verify_token(token)
        g.current_user = {
            'id': payload.get('user_id'),
            'username': payload.get('username'),
            'role': payload.get('role'),
            'authenticated': True
        }
        return g.current_user
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid token")
        return None


def require_auth(f):
    """
    Decorator to require authentication for endpoint.
    
    Usage:
        @require_auth
        def protected_endpoint():
            return "This requires authentication"
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = authenticate_request()
        if not user:
            return jsonify({
                'success': False,
                'message': 'Authentication required',
                'error': {
                    'code': 401,
                    'type': 'Unauthorized',
                    'description': 'Valid authentication token required'
                },
                'timestamp': datetime.utcnow().isoformat()
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_role(required_role: str):
    """
    Decorator to require specific role for endpoint.
    
    Args:
        required_role: Role required to access endpoint
        
    Usage:
        @require_role('admin')
        def admin_only_endpoint():
            return "This requires admin role"
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = authenticate_request()
            if not user:
                return jsonify({
                    'success': False,
                    'message': 'Authentication required',
                    'error': {
                        'code': 401,
                        'type': 'Unauthorized',
                        'description': 'Valid authentication token required'
                    },
                    'timestamp': datetime.utcnow().isoformat()
                }), 401
            
            if user.get('role') != required_role:
                return jsonify({
                    'success': False,
                    'message': 'Insufficient permissions',
                    'error': {
                        'code': 403,
                        'type': 'Forbidden',
                        'description': f'Role "{required_role}" required'
                    },
                    'timestamp': datetime.utcnow().isoformat()
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def optional_auth(f):
    """
    Decorator to optionally authenticate request.
    Sets user context if token is provided and valid, but doesn't require it.
    
    Usage:
        @optional_auth
        def public_endpoint():
            user = getattr(g, 'current_user', None)
            if user:
                return f"Hello {user['username']}"
            return "Hello anonymous user"
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        authenticate_request()  # Sets g.current_user if token is valid
        return f(*args, **kwargs)
    
    return decorated_function


class MockUserService:
    """
    Mock user service for development/testing.
    In production, this would be replaced with a proper user management system.
    """
    
    # Mock users for development
    MOCK_USERS = {
        'admin': {
            'id': 1,
            'username': 'admin',
            'password_hash': generate_password_hash('admin123'),
            'role': 'admin',
            'email': 'admin@bauxita-erp.com'
        },
        'operator': {
            'id': 2,
            'username': 'operator',
            'password_hash': generate_password_hash('operator123'),
            'role': 'operator',
            'email': 'operator@bauxita-erp.com'
        },
        'viewer': {
            'id': 3,
            'username': 'viewer',
            'password_hash': generate_password_hash('viewer123'),
            'role': 'viewer',
            'email': 'viewer@bauxita-erp.com'
        }
    }
    
    @classmethod
    def authenticate_user(cls, username: str, password: str) -> dict:
        """
        Authenticate user with username and password.
        
        Args:
            username: Username
            password: Plain text password
            
        Returns:
            User data if authentication successful, None otherwise
        """
        user = cls.MOCK_USERS.get(username)
        if user and AuthService.verify_password(password, user['password_hash']):
            # Return user data without password hash
            return {
                'id': user['id'],
                'username': user['username'],
                'role': user['role'],
                'email': user['email']
            }
        return None
    
    @classmethod
    def get_user_by_id(cls, user_id: int) -> dict:
        """Get user by ID."""
        for user in cls.MOCK_USERS.values():
            if user['id'] == user_id:
                return {
                    'id': user['id'],
                    'username': user['username'],
                    'role': user['role'],
                    'email': user['email']
                }
        return None
    
    @classmethod
    def get_user_by_username(cls, username: str) -> dict:
        """Get user by username."""
        user = cls.MOCK_USERS.get(username)
        if user:
            return {
                'id': user['id'],
                'username': user['username'],
                'role': user['role'],
                'email': user['email']
            }
        return None


def register_auth_middleware(app):
    """Register authentication middleware with Flask app."""
    
    @app.before_request
    def before_request():
        """Set up authentication context before each request."""
        # Skip authentication for certain endpoints
        exempt_endpoints = [
            'auth.login',
            'auth.health',
            'main.home'
        ]
        
        if request.endpoint in exempt_endpoints:
            return
        
        # For API endpoints, try to authenticate
        if request.path.startswith('/api/'):
            authenticate_request()


def get_current_user():
    """Get current authenticated user from request context."""
    return getattr(g, 'current_user', None)


def is_authenticated():
    """Check if current request is authenticated."""
    user = get_current_user()
    return user is not None and user.get('authenticated', False)


def has_role(role: str):
    """Check if current user has specific role."""
    user = get_current_user()
    return user is not None and user.get('role') == role

