from flask import Flask
from .extensions import db, migrate
import app.models

from .main import main_bp

def create_app(config_class='config.Config'):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    # Set up logging
    from app.utils.logging_config import setup_logging
    setup_logging(app)

    # Register error handlers
    from app.middleware.error_handler import register_error_handlers, register_request_logging
    register_error_handlers(app)
    register_request_logging(app)

    # Register authentication middleware
    from app.middleware.auth import register_auth_middleware
    register_auth_middleware(app)

    with app.app_context():
        from app.main import main_bp
        from app.api.v1 import api_v1

        app.register_blueprint(main_bp, url_prefix="/")
        app.register_blueprint(api_v1)
        

    return app
