"""
Production API
=============

RESTful API endpoints for Production management in the ERP Bauxita system.
"""

from flask import Blueprint, request
from typing import Dict, Any

from app.services import ProductionService
from app.api.v1.utils import (
    api_response, handle_api_error, validate_json_request, 
    validate_query_params, serialize_model, error_handler
)

# Create blueprint
bp = Blueprint('production_api', __name__, url_prefix='/productions')

# Initialize service
production_service = ProductionService()


@bp.route('', methods=['GET'])
@error_handler
def list_productions():
    """
    List productions with optional filtering and pagination.
    
    Query Parameters:
        - year: Filter by contractual year
        - status: Filter by production status
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20)
    """
    # Validate query parameters
    params = validate_query_params({
        'year': {'type': int, 'required': False},
        'status': {'type': str, 'required': False, 
                  'choices': ['draft', 'planned', 'active', 'completed', 'archived']},
        'page': {'type': int, 'default': 1, 'min_value': 1},
        'per_page': {'type': int, 'default': 20, 'min_value': 1, 'max_value': 100}
    })
    
    # Get productions based on filters
    if params['year']:
        productions = production_service.production_repo.get_by_year(params['year'])
    elif params['status']:
        from app.models.production import ProductionStatus
        status_enum = ProductionStatus(params['status'])
        productions = production_service.production_repo.get_by_status(status_enum)
    else:
        productions = production_service.production_repo.get_active()
    
    # Serialize results
    serialized_productions = [serialize_model(prod) for prod in productions]
    
    return api_response(
        data={
            'productions': serialized_productions,
            'total': len(serialized_productions)
        },
        message="Productions retrieved successfully"
    )


@bp.route('/<int:production_id>', methods=['GET'])
@error_handler
def get_production(production_id: int):
    """Get a specific production by ID."""
    production = production_service.production_repo.get_by_id(production_id)
    
    if not production:
        return api_response(
            data=None,
            message="Production not found",
            status_code=404
        )
    
    return api_response(
        data={'production': serialize_model(production)},
        message="Production retrieved successfully"
    )


@bp.route('', methods=['POST'])
@error_handler
def create_production():
    """Create a new production scenario."""
    # Validate request data
    data = validate_json_request([
        'scenario_name', 'contractual_year', 'total_planned_tonnage',
        'start_date_contractual_year', 'end_date_contractual_year'
    ])
    
    # Convert date strings to date objects
    from datetime import datetime
    if isinstance(data['start_date_contractual_year'], str):
        data['start_date_contractual_year'] = datetime.fromisoformat(
            data['start_date_contractual_year']
        ).date()
    
    if isinstance(data['end_date_contractual_year'], str):
        data['end_date_contractual_year'] = datetime.fromisoformat(
            data['end_date_contractual_year']
        ).date()
    
    # Create production
    production = production_service.create_production_scenario(data)
    
    return api_response(
        data={'production': serialize_model(production)},
        message="Production scenario created successfully",
        status_code=201
    )


@bp.route('/<int:production_id>', methods=['PUT'])
@error_handler
def update_production(production_id: int):
    """Update a production scenario."""
    # Validate request data
    data = validate_json_request()
    
    # Convert date strings if present
    from datetime import datetime
    for date_field in ['start_date_contractual_year', 'end_date_contractual_year']:
        if date_field in data and isinstance(data[date_field], str):
            data[date_field] = datetime.fromisoformat(data[date_field]).date()
    
    # Update production
    production = production_service.production_repo.update(production_id, **data)
    
    if not production:
        return api_response(
            data=None,
            message="Production not found",
            status_code=404
        )
    
    return api_response(
        data={'production': serialize_model(production)},
        message="Production updated successfully"
    )


@bp.route('/<int:production_id>', methods=['DELETE'])
@error_handler
def delete_production(production_id: int):
    """Delete (soft delete) a production scenario."""
    success = production_service.production_repo.delete(production_id)
    
    if not success:
        return api_response(
            data=None,
            message="Production not found",
            status_code=404
        )
    
    return api_response(
        data=None,
        message="Production deleted successfully"
    )


@bp.route('/<int:production_id>/activate', methods=['POST'])
@error_handler
def activate_production(production_id: int):
    """Activate a production scenario."""
    production = production_service.activate_production_scenario(production_id)
    
    return api_response(
        data={'production': serialize_model(production)},
        message="Production scenario activated successfully"
    )


@bp.route('/<int:production_id>/complete', methods=['POST'])
@error_handler
def complete_production(production_id: int):
    """Complete a production scenario."""
    production = production_service.complete_production_scenario(production_id)
    
    return api_response(
        data={'production': serialize_model(production)},
        message="Production scenario completed successfully"
    )


@bp.route('/<int:production_id>/partners', methods=['GET'])
@error_handler
def list_production_partners(production_id: int):
    """List partners enrolled in a production."""
    production = production_service.production_repo.get_by_id(production_id)
    
    if not production:
        return api_response(
            data=None,
            message="Production not found",
            status_code=404
        )
    
    partners = []
    for enrollment in production.enrolled_partners:
        partner_data = serialize_model(enrollment.partner) if enrollment.partner else {}
        partner_data['enrollment'] = serialize_model(enrollment)
        partners.append(partner_data)
    
    return api_response(
        data={
            'partners': partners,
            'total': len(partners)
        },
        message="Production partners retrieved successfully"
    )


@bp.route('/<int:production_id>/partners', methods=['POST'])
@error_handler
def enroll_partner(production_id: int):
    """Enroll a partner in a production scenario."""
    # Validate request data
    data = validate_json_request([
        'partner_id', 'vessel_size_t', 'minimum_tonnage'
    ])
    
    # Enroll partner
    enrollment = production_service.enroll_partner_in_production(
        production_id, 
        data['partner_id'], 
        {k: v for k, v in data.items() if k != 'partner_id'}
    )
    
    return api_response(
        data={'enrollment': serialize_model(enrollment)},
        message="Partner enrolled successfully",
        status_code=201
    )


@bp.route('/<int:production_id>/partners/<int:partner_id>', methods=['PUT'])
@error_handler
def update_partner_enrollment(production_id: int, partner_id: int):
    """Update partner enrollment in a production."""
    # Validate request data
    data = validate_json_request()
    
    # Update enrollment
    enrollment = production_service.update_partner_enrollment(
        production_id, partner_id, data
    )
    
    return api_response(
        data={'enrollment': serialize_model(enrollment)},
        message="Partner enrollment updated successfully"
    )


@bp.route('/<int:production_id>/partners/<int:partner_id>', methods=['DELETE'])
@error_handler
def remove_partner_enrollment(production_id: int, partner_id: int):
    """Remove partner enrollment from a production."""
    enrollment = production_service.production_repo.get_partner_enrollment(
        production_id, partner_id
    )
    
    if not enrollment:
        return api_response(
            data=None,
            message="Partner enrollment not found",
            status_code=404
        )
    
    # Delete enrollment
    from app.extensions import db
    db.session.delete(enrollment)
    db.session.commit()
    
    return api_response(
        data=None,
        message="Partner enrollment removed successfully"
    )


@bp.route('/<int:production_id>/metrics', methods=['GET'])
@error_handler
def get_production_metrics(production_id: int):
    """Get comprehensive metrics for a production scenario."""
    metrics = production_service.calculate_production_metrics(production_id)
    
    return api_response(
        data={'metrics': metrics},
        message="Production metrics calculated successfully"
    )


@bp.route('/<int:production_id>/copy', methods=['POST'])
@error_handler
def copy_production(production_id: int):
    """Create a copy of an existing production scenario."""
    # Validate request data
    data = validate_json_request(['new_scenario_name'])
    
    new_year = data.get('new_year')
    new_production = production_service.production_repo.create_scenario_copy(
        production_id, 
        data['new_scenario_name'], 
        new_year
    )
    
    if not new_production:
        return api_response(
            data=None,
            message="Source production not found",
            status_code=404
        )
    
    return api_response(
        data={'production': serialize_model(new_production)},
        message="Production scenario copied successfully",
        status_code=201
    )


@bp.route('/dashboard', methods=['GET'])
@error_handler
def get_dashboard_data():
    """Get dashboard data for production management."""
    # Validate query parameters
    params = validate_query_params({
        'year': {'type': int, 'required': False}
    })
    
    dashboard_data = production_service.get_production_dashboard_data(params['year'])
    
    return api_response(
        data={'dashboard': dashboard_data},
        message="Dashboard data retrieved successfully"
    )


@bp.route('/statistics', methods=['GET'])
@error_handler
def get_production_statistics():
    """Get production statistics."""
    # Validate query parameters
    params = validate_query_params({
        'year': {'type': int, 'required': False}
    })
    
    stats = production_service.production_repo.get_production_statistics(params['year'])
    
    return api_response(
        data={'statistics': stats},
        message="Production statistics retrieved successfully"
    )


@bp.route('/search', methods=['GET'])
@error_handler
def search_productions():
    """Search productions by name pattern."""
    # Validate query parameters
    params = validate_query_params({
        'q': {'type': str, 'required': True}
    })
    
    productions = production_service.production_repo.search_by_name(params['q'])
    serialized_productions = [serialize_model(prod) for prod in productions]
    
    return api_response(
        data={
            'productions': serialized_productions,
            'total': len(serialized_productions),
            'query': params['q']
        },
        message="Search completed successfully"
    )

