"""
Logging Configuration
====================

Centralized logging configuration for the ERP Bauxita system.
"""

import logging
import logging.handlers
import os
from datetime import datetime
from flask import request, g
from typing import Optional


class RequestFormatter(logging.Formatter):
    """Custom formatter that includes request context."""
    
    def format(self, record):
        # Add request context if available
        if hasattr(g, 'current_user') and g.current_user:
            record.user_id = g.current_user.get('id', 'anonymous')
            record.username = g.current_user.get('username', 'anonymous')
        else:
            record.user_id = 'anonymous'
            record.username = 'anonymous'
        
        # Add request info if available
        try:
            record.method = request.method
            record.url = request.url
            record.remote_addr = request.remote_addr
        except RuntimeError:
            # Outside request context
            record.method = 'N/A'
            record.url = 'N/A'
            record.remote_addr = 'N/A'
        
        return super().format(record)


def setup_logging(app):
    """Set up logging configuration for the Flask application."""
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(app.instance_path), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(level=logging.INFO)
    
    # Create formatters
    detailed_formatter = RequestFormatter(
        fmt='%(asctime)s [%(levelname)s] %(name)s - %(username)s (%(user_id)s) - '
            '%(method)s %(url)s - %(remote_addr)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Application logger
    app_logger = logging.getLogger('erp_bauxita')
    app_logger.setLevel(logging.INFO)
    
    # File handler for application logs
    app_file_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'app.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    app_file_handler.setFormatter(detailed_formatter)
    app_file_handler.setLevel(logging.INFO)
    app_logger.addHandler(app_file_handler)
    
    # Error logger
    error_logger = logging.getLogger('erp_bauxita.errors')
    error_logger.setLevel(logging.ERROR)
    
    # File handler for errors
    error_file_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'errors.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10
    )
    error_file_handler.setFormatter(detailed_formatter)
    error_file_handler.setLevel(logging.ERROR)
    error_logger.addHandler(error_file_handler)
    
    # API logger
    api_logger = logging.getLogger('erp_bauxita.api')
    api_logger.setLevel(logging.INFO)
    
    # File handler for API logs
    api_file_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'api.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    api_file_handler.setFormatter(detailed_formatter)
    api_file_handler.setLevel(logging.INFO)
    api_logger.addHandler(api_file_handler)
    
    # Database logger
    db_logger = logging.getLogger('erp_bauxita.database')
    db_logger.setLevel(logging.INFO)
    
    # File handler for database logs
    db_file_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'database.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    db_file_handler.setFormatter(simple_formatter)
    db_file_handler.setLevel(logging.INFO)
    db_logger.addHandler(db_file_handler)
    
    # Console handler for development
    if app.config.get('DEBUG', False):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(simple_formatter)
        console_handler.setLevel(logging.INFO)
        
        app_logger.addHandler(console_handler)
        api_logger.addHandler(console_handler)
    
    # Set up Flask's logger
    app.logger.handlers = []
    app.logger.addHandler(app_file_handler)
    if app.config.get('DEBUG', False):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(simple_formatter)
        app.logger.addHandler(console_handler)
    
    app.logger.setLevel(logging.INFO)
    
    # Suppress some noisy loggers
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    app.logger.info("Logging configuration completed")


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name under the erp_bauxita namespace."""
    return logging.getLogger(f'erp_bauxita.{name}')


def log_api_request(endpoint: str, method: str, status_code: int, 
                   duration: Optional[float] = None):
    """Log API request details."""
    logger = get_logger('api')
    
    user_info = "anonymous"
    if hasattr(g, 'current_user') and g.current_user:
        user_info = f"{g.current_user.get('username')} ({g.current_user.get('id')})"
    
    message = f"{method} {endpoint} - {status_code}"
    if duration:
        message += f" - {duration:.3f}s"
    
    if status_code >= 400:
        logger.warning(f"{message} - User: {user_info}")
    else:
        logger.info(f"{message} - User: {user_info}")


def log_database_operation(operation: str, table: str, record_id: Optional[int] = None,
                          details: Optional[str] = None):
    """Log database operations."""
    logger = get_logger('database')
    
    user_info = "system"
    if hasattr(g, 'current_user') and g.current_user:
        user_info = f"{g.current_user.get('username')} ({g.current_user.get('id')})"
    
    message = f"{operation.upper()} {table}"
    if record_id:
        message += f" (ID: {record_id})"
    if details:
        message += f" - {details}"
    
    logger.info(f"{message} - User: {user_info}")


def log_business_event(event: str, details: Optional[str] = None, 
                      level: str = 'info'):
    """Log business events."""
    logger = get_logger('business')
    
    user_info = "system"
    if hasattr(g, 'current_user') and g.current_user:
        user_info = f"{g.current_user.get('username')} ({g.current_user.get('id')})"
    
    message = f"BUSINESS EVENT: {event}"
    if details:
        message += f" - {details}"
    message += f" - User: {user_info}"
    
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(log_level, message)


def log_security_event(event: str, details: Optional[str] = None, 
                      level: str = 'warning'):
    """Log security-related events."""
    logger = get_logger('security')
    
    user_info = "anonymous"
    if hasattr(g, 'current_user') and g.current_user:
        user_info = f"{g.current_user.get('username')} ({g.current_user.get('id')})"
    
    remote_addr = getattr(request, 'remote_addr', 'unknown') if request else 'unknown'
    
    message = f"SECURITY EVENT: {event}"
    if details:
        message += f" - {details}"
    message += f" - User: {user_info} - IP: {remote_addr}"
    
    log_level = getattr(logging, level.upper(), logging.WARNING)
    logger.log(log_level, message)

