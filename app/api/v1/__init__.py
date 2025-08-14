"""
API v1 Module
============

Version 1 of the ERP Bauxita API.
"""

from flask import Blueprint
from flask_cors import CORS

# Create API v1 blueprint
api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')

# Enable CORS for all API endpoints
CORS(api_v1, origins='*')

# Import resources to register routes
from .resources import production_api, vessel_api, partner_api, auth_api

# Register resource blueprints
api_v1.register_blueprint(production_api.bp)
api_v1.register_blueprint(vessel_api.bp)
api_v1.register_blueprint(partner_api.bp)
api_v1.register_blueprint(auth_api.bp)

