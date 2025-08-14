"""
API Utilities
=============

Common utilities for API endpoints in the ERP Bauxita system.
"""

from functools import wraps
from typing import Dict, Any, Optional, Tuple
from flask import jsonify, request
from datetime import datetime
import traceback


def api_response(data: Any = None, message: str = "Success", 
                status_code: int = 200, errors: Optional[Dict] = None) -> Tuple[Dict, int]:
    """
    Standardized API response format.
    
    Args:
        data: Response data
        message: Response message
        status_code: HTTP status code
        errors: Error details if any
        
    Returns:
        Tuple of (response_dict, status_code)
    """
    response = {
        'success': status_code < 400,
        'message': message,
        'timestamp': datetime.utcnow().isoformat(),
        'data': data
    }
    
    if errors:
        response['errors'] = errors
    
    return response, status_code


def handle_api_error(error: Exception, message: str = "An error occurred") -> Tuple[Dict, int]:
    """
    Handle API errors with standardized response.
    
    Args:
        error: Exception that occurred
        message: Custom error message
        
    Returns:
        Tuple of (error_response, status_code)
    """
    error_details = {
        'type': type(error).__name__,
        'message': str(error)
    }
    
    # Determine status code based on error type
    if isinstance(error, ValueError):
        status_code = 400
    elif isinstance(error, FileNotFoundError):
        status_code = 404
    elif isinstance(error, PermissionError):
        status_code = 403
    else:
        status_code = 500
        # Add traceback for server errors in development
        error_details['traceback'] = traceback.format_exc()
    
    return api_response(
        data=None,
        message=message,
        status_code=status_code,
        errors=error_details
    )


def validate_json_request(required_fields: Optional[list] = None) -> Dict[str, Any]:
    """
    Validate JSON request data.
    
    Args:
        required_fields: List of required field names
        
    Returns:
        Validated JSON data
        
    Raises:
        ValueError: If validation fails
    """
    if not request.is_json:
        raise ValueError("Request must be JSON")
    
    data = request.get_json()
    if not data:
        raise ValueError("Request body cannot be empty")
    
    if required_fields:
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
    
    return data


def validate_query_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and convert query parameters.
    
    Args:
        params: Dictionary of parameter definitions
        
    Returns:
        Validated parameters
    """
    validated = {}
    
    for param_name, param_config in params.items():
        value = request.args.get(param_name)
        
        if value is None:
            if param_config.get('required', False):
                raise ValueError(f"Missing required parameter: {param_name}")
            validated[param_name] = param_config.get('default')
            continue
        
        # Type conversion
        param_type = param_config.get('type', str)
        try:
            if param_type == int:
                validated[param_name] = int(value)
            elif param_type == float:
                validated[param_name] = float(value)
            elif param_type == bool:
                validated[param_name] = value.lower() in ('true', '1', 'yes', 'on')
            else:
                validated[param_name] = value
        except (ValueError, TypeError):
            raise ValueError(f"Invalid type for parameter {param_name}: expected {param_type.__name__}")
        
        # Validation
        if 'choices' in param_config:
            if validated[param_name] not in param_config['choices']:
                raise ValueError(f"Invalid value for {param_name}: must be one of {param_config['choices']}")
        
        if 'min_value' in param_config:
            if validated[param_name] < param_config['min_value']:
                raise ValueError(f"Value for {param_name} must be >= {param_config['min_value']}")
        
        if 'max_value' in param_config:
            if validated[param_name] > param_config['max_value']:
                raise ValueError(f"Value for {param_name} must be <= {param_config['max_value']}")
    
    return validated


def paginate_query(query, page: int = 1, per_page: int = 20, max_per_page: int = 100):
    """
    Paginate SQLAlchemy query results.
    
    Args:
        query: SQLAlchemy query object
        page: Page number (1-based)
        per_page: Items per page
        max_per_page: Maximum items per page
        
    Returns:
        Pagination object with results
    """
    if per_page > max_per_page:
        per_page = max_per_page
    
    if page < 1:
        page = 1
    
    return query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )


def serialize_model(model, include_audit: bool = False) -> Dict[str, Any]:
    """
    Serialize SQLAlchemy model to dictionary.
    
    Args:
        model: SQLAlchemy model instance
        include_audit: Whether to include audit fields
        
    Returns:
        Serialized model data
    """
    if hasattr(model, 'to_dict'):
        return model.to_dict(include_audit=include_audit)
    
    # Fallback serialization
    result = {}
    for column in model.__table__.columns:
        if not include_audit and column.name in {
            'created_at', 'updated_at', 'created_by', 
            'updated_by', 'deleted_at', 'deleted_by'
        }:
            continue
        
        value = getattr(model, column.name)
        if isinstance(value, datetime):
            result[column.name] = value.isoformat()
        else:
            result[column.name] = value
    
    return result


def serialize_pagination(pagination, serializer_func=None) -> Dict[str, Any]:
    """
    Serialize pagination object.
    
    Args:
        pagination: SQLAlchemy pagination object
        serializer_func: Function to serialize individual items
        
    Returns:
        Serialized pagination data
    """
    items = pagination.items
    if serializer_func:
        items = [serializer_func(item) for item in items]
    elif items and hasattr(items[0], 'to_dict'):
        items = [item.to_dict() for item in items]
    
    return {
        'items': items,
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total_pages': pagination.pages,
            'total_items': pagination.total,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'prev_page': pagination.prev_num if pagination.has_prev else None,
            'next_page': pagination.next_num if pagination.has_next else None
        }
    }


def error_handler(f):
    """
    Decorator to handle API errors consistently.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            return handle_api_error(e)
    
    return decorated_function


class APIException(Exception):
    """Custom API exception with status code."""
    
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

