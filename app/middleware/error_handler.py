"""
Error Handler Middleware
=======================

Global error handling middleware for the ERP Bauxita system.
"""

import logging
import traceback
from datetime import datetime
from flask import jsonify, request, current_app
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError

# Configure logger
logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """Register global error handlers for the Flask application."""
    
    @app.errorhandler(400)
    def bad_request(error):
        """Handle 400 Bad Request errors."""
        return jsonify({
            'success': False,
            'message': 'Bad Request',
            'error': {
                'code': 400,
                'type': 'BadRequest',
                'description': str(error.description) if hasattr(error, 'description') else 'Invalid request'
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        """Handle 401 Unauthorized errors."""
        return jsonify({
            'success': False,
            'message': 'Unauthorized',
            'error': {
                'code': 401,
                'type': 'Unauthorized',
                'description': 'Authentication required'
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        """Handle 403 Forbidden errors."""
        return jsonify({
            'success': False,
            'message': 'Forbidden',
            'error': {
                'code': 403,
                'type': 'Forbidden',
                'description': 'Access denied'
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 403
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 Not Found errors."""
        return jsonify({
            'success': False,
            'message': 'Not Found',
            'error': {
                'code': 404,
                'type': 'NotFound',
                'description': 'The requested resource was not found'
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """Handle 405 Method Not Allowed errors."""
        return jsonify({
            'success': False,
            'message': 'Method Not Allowed',
            'error': {
                'code': 405,
                'type': 'MethodNotAllowed',
                'description': f'Method {request.method} not allowed for this endpoint'
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 405
    
    @app.errorhandler(422)
    def unprocessable_entity(error):
        """Handle 422 Unprocessable Entity errors."""
        return jsonify({
            'success': False,
            'message': 'Unprocessable Entity',
            'error': {
                'code': 422,
                'type': 'UnprocessableEntity',
                'description': 'The request was well-formed but contains semantic errors'
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 422
    
    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle 500 Internal Server Error."""
        # Log the error
        logger.error(f"Internal Server Error: {str(error)}")
        logger.error(f"Request: {request.method} {request.url}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Return error response
        error_response = {
            'success': False,
            'message': 'Internal Server Error',
            'error': {
                'code': 500,
                'type': 'InternalServerError',
                'description': 'An unexpected error occurred'
            },
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Include traceback in development mode
        if current_app.config.get('DEBUG', False):
            error_response['error']['traceback'] = traceback.format_exc()
        
        return jsonify(error_response), 500
    
    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(error):
        """Handle SQLAlchemy database errors."""
        logger.error(f"Database Error: {str(error)}")
        logger.error(f"Request: {request.method} {request.url}")
        
        # Rollback the session
        from app.extensions import db
        db.session.rollback()
        
        return jsonify({
            'success': False,
            'message': 'Database Error',
            'error': {
                'code': 500,
                'type': 'DatabaseError',
                'description': 'A database error occurred'
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 500
    
    @app.errorhandler(ValueError)
    def handle_value_error(error):
        """Handle ValueError exceptions."""
        logger.warning(f"Value Error: {str(error)}")
        
        return jsonify({
            'success': False,
            'message': 'Validation Error',
            'error': {
                'code': 400,
                'type': 'ValueError',
                'description': str(error)
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 400
    
    @app.errorhandler(KeyError)
    def handle_key_error(error):
        """Handle KeyError exceptions."""
        logger.warning(f"Key Error: {str(error)}")
        
        return jsonify({
            'success': False,
            'message': 'Missing Required Field',
            'error': {
                'code': 400,
                'type': 'KeyError',
                'description': f'Missing required field: {str(error)}'
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 400
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        """Handle generic HTTP exceptions."""
        return jsonify({
            'success': False,
            'message': error.name,
            'error': {
                'code': error.code,
                'type': error.name,
                'description': error.description
            },
            'timestamp': datetime.utcnow().isoformat()
        }), error.code
    
    @app.errorhandler(Exception)
    def handle_generic_exception(error):
        """Handle any unhandled exceptions."""
        logger.error(f"Unhandled Exception: {str(error)}")
        logger.error(f"Request: {request.method} {request.url}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        error_response = {
            'success': False,
            'message': 'Unexpected Error',
            'error': {
                'code': 500,
                'type': type(error).__name__,
                'description': 'An unexpected error occurred'
            },
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Include error details in development mode
        if current_app.config.get('DEBUG', False):
            error_response['error']['description'] = str(error)
            error_response['error']['traceback'] = traceback.format_exc()
        
        return jsonify(error_response), 500


def log_request_info():
    """Log request information for debugging."""
    if current_app.config.get('DEBUG', False):
        logger.info(f"Request: {request.method} {request.url}")
        if request.is_json:
            logger.info(f"Request Body: {request.get_json()}")
        logger.info(f"Request Headers: {dict(request.headers)}")


def register_request_logging(app):
    """Register request logging middleware."""
    
    @app.before_request
    def before_request():
        """Log request information before processing."""
        log_request_info()
    
    @app.after_request
    def after_request(response):
        """Log response information after processing."""
        if current_app.config.get('DEBUG', False):
            logger.info(f"Response Status: {response.status_code}")
        return response

