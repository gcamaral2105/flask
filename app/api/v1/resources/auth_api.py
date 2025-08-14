"""
Authentication API
=================

Authentication endpoints for the ERP Bauxita system.
"""

from flask import Blueprint, request
from datetime import datetime

from app.middleware.auth import AuthService, MockUserService
from app.api.v1.utils import (
    api_response, validate_json_request, error_handler
)

# Create blueprint
bp = Blueprint('auth_api', __name__, url_prefix='/auth')


@bp.route('/login', methods=['POST'])
@error_handler
def login():
    """
    Authenticate user and return JWT token.
    
    Request Body:
        {
            "username": "string",
            "password": "string"
        }
    
    Response:
        {
            "success": true,
            "message": "Login successful",
            "data": {
                "token": "jwt_token_string",
                "user": {
                    "id": 1,
                    "username": "admin",
                    "role": "admin",
                    "email": "admin@bauxita-erp.com"
                },
                "expires_in": 3600
            }
        }
    """
    # Validate request data
    data = validate_json_request(['username', 'password'])
    
    # Authenticate user
    user = MockUserService.authenticate_user(data['username'], data['password'])
    
    if not user:
        return api_response(
            data=None,
            message="Invalid credentials",
            status_code=401
        )
    
    # Generate token
    token = AuthService.generate_token(user, expires_in=3600)
    
    return api_response(
        data={
            'token': token,
            'user': user,
            'expires_in': 3600,
            'token_type': 'Bearer'
        },
        message="Login successful"
    )


@bp.route('/logout', methods=['POST'])
@error_handler
def logout():
    """
    Logout user (client-side token removal).
    
    Note: Since we're using stateless JWT tokens, logout is handled
    client-side by removing the token. In a production system,
    you might want to implement token blacklisting.
    """
    return api_response(
        data=None,
        message="Logout successful"
    )


@bp.route('/refresh', methods=['POST'])
@error_handler
def refresh_token():
    """
    Refresh JWT token.
    
    Headers:
        Authorization: Bearer <current_token>
    
    Response:
        {
            "success": true,
            "message": "Token refreshed successfully",
            "data": {
                "token": "new_jwt_token_string",
                "expires_in": 3600
            }
        }
    """
    # Get current token from header
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return api_response(
            data=None,
            message="Missing or invalid authorization header",
            status_code=401
        )
    
    current_token = auth_header.split(' ')[1]
    
    try:
        # Verify current token
        payload = AuthService.verify_token(current_token)
        
        # Get user data
        user_id = payload.get('user_id')
        user = MockUserService.get_user_by_id(user_id)
        
        if not user:
            return api_response(
                data=None,
                message="User not found",
                status_code=404
            )
        
        # Generate new token
        new_token = AuthService.generate_token(user, expires_in=3600)
        
        return api_response(
            data={
                'token': new_token,
                'expires_in': 3600,
                'token_type': 'Bearer'
            },
            message="Token refreshed successfully"
        )
        
    except Exception as e:
        return api_response(
            data=None,
            message="Invalid or expired token",
            status_code=401
        )


@bp.route('/me', methods=['GET'])
@error_handler
def get_current_user():
    """
    Get current user information.
    
    Headers:
        Authorization: Bearer <token>
    
    Response:
        {
            "success": true,
            "message": "User information retrieved successfully",
            "data": {
                "user": {
                    "id": 1,
                    "username": "admin",
                    "role": "admin",
                    "email": "admin@bauxita-erp.com"
                }
            }
        }
    """
    # Get token from header
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return api_response(
            data=None,
            message="Authentication required",
            status_code=401
        )
    
    token = auth_header.split(' ')[1]
    
    try:
        # Verify token
        payload = AuthService.verify_token(token)
        
        # Get user data
        user_id = payload.get('user_id')
        user = MockUserService.get_user_by_id(user_id)
        
        if not user:
            return api_response(
                data=None,
                message="User not found",
                status_code=404
            )
        
        return api_response(
            data={'user': user},
            message="User information retrieved successfully"
        )
        
    except Exception as e:
        return api_response(
            data=None,
            message="Invalid or expired token",
            status_code=401
        )


@bp.route('/users', methods=['GET'])
@error_handler
def list_users():
    """
    List all users (admin only).
    
    Headers:
        Authorization: Bearer <admin_token>
    
    Response:
        {
            "success": true,
            "message": "Users retrieved successfully",
            "data": {
                "users": [
                    {
                        "id": 1,
                        "username": "admin",
                        "role": "admin",
                        "email": "admin@bauxita-erp.com"
                    }
                ]
            }
        }
    """
    # Get and verify token
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return api_response(
            data=None,
            message="Authentication required",
            status_code=401
        )
    
    token = auth_header.split(' ')[1]
    
    try:
        # Verify token
        payload = AuthService.verify_token(token)
        
        # Check if user has admin role
        if payload.get('role') != 'admin':
            return api_response(
                data=None,
                message="Admin access required",
                status_code=403
            )
        
        # Get all users
        users = []
        for user_data in MockUserService.MOCK_USERS.values():
            users.append({
                'id': user_data['id'],
                'username': user_data['username'],
                'role': user_data['role'],
                'email': user_data['email']
            })
        
        return api_response(
            data={
                'users': users,
                'total': len(users)
            },
            message="Users retrieved successfully"
        )
        
    except Exception as e:
        return api_response(
            data=None,
            message="Invalid or expired token",
            status_code=401
        )


@bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint (no authentication required).
    
    Response:
        {
            "success": true,
            "message": "Authentication service is healthy",
            "data": {
                "status": "healthy",
                "timestamp": "2025-08-14T14:30:00.000Z"
            }
        }
    """
    return api_response(
        data={
            'status': 'healthy',
            'service': 'authentication',
            'version': '1.0.0'
        },
        message="Authentication service is healthy"
    )

