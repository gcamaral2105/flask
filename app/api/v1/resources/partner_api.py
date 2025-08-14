"""
Partner API
==========

RESTful API endpoints for Partner management in the ERP Bauxita system.
"""

from flask import Blueprint, request
from typing import Dict, Any

from app.services import PartnerService
from app.api.v1.utils import (
    api_response, handle_api_error, validate_json_request, 
    validate_query_params, serialize_model, error_handler
)

# Create blueprint
bp = Blueprint('partner_api', __name__, url_prefix='/partners')

# Initialize service
partner_service = PartnerService()


@bp.route('', methods=['GET'])
@error_handler
def list_partners():
    """
    List partners with optional filtering.
    
    Query Parameters:
        - entity_type: Filter by entity type (HALCO, OFFTAKER, etc.)
        - with_vessels: Filter partners who own vessels (true/false)
        - active_only: Filter only active partners (true/false)
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20)
    """
    # Validate query parameters
    params = validate_query_params({
        'entity_type': {'type': str, 'required': False},
        'with_vessels': {'type': bool, 'required': False},
        'active_only': {'type': bool, 'default': True},
        'page': {'type': int, 'default': 1, 'min_value': 1},
        'per_page': {'type': int, 'default': 20, 'min_value': 1, 'max_value': 100}
    })
    
    # Get partners based on filters
    if params['entity_type']:
        partners = partner_service.partner_repo.get_by_entity_type(params['entity_type'])
    elif params['with_vessels']:
        partners = partner_service.partner_repo.get_vessel_owners()
    else:
        partners = partner_service.partner_repo.get_active()
    
    # Serialize results
    serialized_partners = [serialize_model(partner) for partner in partners]
    
    return api_response(
        data={
            'partners': serialized_partners,
            'total': len(serialized_partners)
        },
        message="Partners retrieved successfully"
    )


@bp.route('/<int:partner_id>', methods=['GET'])
@error_handler
def get_partner(partner_id: int):
    """Get a specific partner by ID."""
    partner = partner_service.partner_repo.get_by_id(partner_id)
    
    if not partner:
        return api_response(
            data=None,
            message="Partner not found",
            status_code=404
        )
    
    return api_response(
        data={'partner': serialize_model(partner)},
        message="Partner retrieved successfully"
    )


@bp.route('', methods=['POST'])
@error_handler
def create_partner():
    """Create a new partner."""
    # Validate request data
    data = validate_json_request(['name'])
    
    # Extract entity data if provided
    entity_data = data.pop('entity', None)
    
    # Create partner
    partner = partner_service.create_partner(data, entity_data)
    
    return api_response(
        data={'partner': serialize_model(partner)},
        message="Partner created successfully",
        status_code=201
    )


@bp.route('/<int:partner_id>', methods=['PUT'])
@error_handler
def update_partner(partner_id: int):
    """Update a partner."""
    # Validate request data
    data = validate_json_request()
    
    # Update partner
    partner = partner_service.update_partner(partner_id, data)
    
    return api_response(
        data={'partner': serialize_model(partner)},
        message="Partner updated successfully"
    )


@bp.route('/<int:partner_id>', methods=['DELETE'])
@error_handler
def delete_partner(partner_id: int):
    """Delete (soft delete) a partner."""
    success = partner_service.partner_repo.delete(partner_id)
    
    if not success:
        return api_response(
            data=None,
            message="Partner not found",
            status_code=404
        )
    
    return api_response(
        data=None,
        message="Partner deleted successfully"
    )


@bp.route('/<int:partner_id>/entity', methods=['PUT'])
@error_handler
def update_partner_entity(partner_id: int):
    """Update partner entity information."""
    # Validate request data
    data = validate_json_request()
    
    # Update entity
    partner = partner_service.update_partner_entity(partner_id, data)
    
    return api_response(
        data={'partner': serialize_model(partner)},
        message="Partner entity updated successfully"
    )


@bp.route('/<int:partner_id>/portfolio', methods=['GET'])
@error_handler
def get_partner_portfolio(partner_id: int):
    """Get comprehensive partner portfolio information."""
    portfolio = partner_service.get_partner_portfolio(partner_id)
    
    return api_response(
        data={'portfolio': portfolio},
        message="Partner portfolio retrieved successfully"
    )


@bp.route('/<int:partner_id>/performance', methods=['GET'])
@error_handler
def evaluate_partner_performance(partner_id: int):
    """Evaluate partner performance."""
    # Validate query parameters
    params = validate_query_params({
        'period_days': {'type': int, 'default': 365, 'min_value': 1, 'max_value': 1825}
    })
    
    # Evaluate performance
    evaluation = partner_service.evaluate_partner_performance(
        partner_id, params['period_days']
    )
    
    return api_response(
        data={'performance_evaluation': evaluation},
        message="Partner performance evaluated successfully"
    )


@bp.route('/<int:partner_id>/contracts', methods=['GET'])
@error_handler
def get_partner_contracts(partner_id: int):
    """Get partner contracts summary."""
    contracts_summary = partner_service.get_partner_contracts_summary(partner_id)
    
    return api_response(
        data={'contracts_summary': contracts_summary},
        message="Partner contracts retrieved successfully"
    )


@bp.route('/<int:partner_id>/enrollments', methods=['GET'])
@error_handler
def get_partner_enrollments(partner_id: int):
    """Get partner production enrollments."""
    enrollments = partner_service.partner_repo.get_production_enrollments(partner_id)
    serialized_enrollments = [serialize_model(enrollment) for enrollment in enrollments]
    
    return api_response(
        data={
            'enrollments': serialized_enrollments,
            'total': len(serialized_enrollments)
        },
        message="Partner enrollments retrieved successfully"
    )


@bp.route('/<int:partner_id>/vessels', methods=['GET'])
@error_handler
def get_partner_vessels(partner_id: int):
    """Get vessels owned by a partner."""
    vessels = partner_service.partner_repo.vessel_repo.get_by_owner(partner_id)
    serialized_vessels = [serialize_model(vessel) for vessel in vessels]
    
    return api_response(
        data={
            'vessels': serialized_vessels,
            'total': len(serialized_vessels)
        },
        message="Partner vessels retrieved successfully"
    )


@bp.route('/<int:partner_id>/history', methods=['GET'])
@error_handler
def get_partnership_history(partner_id: int):
    """Get complete partnership history."""
    history = partner_service.partner_repo.get_partnership_history(partner_id)
    
    return api_response(
        data={'partnership_history': history},
        message="Partnership history retrieved successfully"
    )


@bp.route('/halco-buyers', methods=['GET'])
@error_handler
def get_halco_buyers():
    """Get all HALCO buyer partners."""
    partners = partner_service.partner_repo.get_halco_buyers()
    serialized_partners = [serialize_model(partner) for partner in partners]
    
    return api_response(
        data={
            'partners': serialized_partners,
            'total': len(serialized_partners)
        },
        message="HALCO buyers retrieved successfully"
    )


@bp.route('/offtakers', methods=['GET'])
@error_handler
def get_offtakers():
    """Get all offtaker partners."""
    partners = partner_service.partner_repo.get_offtakers()
    serialized_partners = [serialize_model(partner) for partner in partners]
    
    return api_response(
        data={
            'partners': serialized_partners,
            'total': len(serialized_partners)
        },
        message="Offtakers retrieved successfully"
    )


@bp.route('/vessel-owners', methods=['GET'])
@error_handler
def get_vessel_owners():
    """Get partners who own vessels."""
    partners = partner_service.partner_repo.get_vessel_owners()
    serialized_partners = [serialize_model(partner) for partner in partners]
    
    return api_response(
        data={
            'partners': serialized_partners,
            'total': len(serialized_partners)
        },
        message="Vessel owners retrieved successfully"
    )


@bp.route('/active-production', methods=['GET'])
@error_handler
def get_active_production_partners():
    """Get partners enrolled in active productions."""
    partners = partner_service.partner_repo.get_active_production_partners()
    serialized_partners = [serialize_model(partner) for partner in partners]
    
    return api_response(
        data={
            'partners': serialized_partners,
            'total': len(serialized_partners)
        },
        message="Active production partners retrieved successfully"
    )


@bp.route('/statistics', methods=['GET'])
@error_handler
def get_partner_statistics():
    """Get partner statistics."""
    stats = partner_service.partner_repo.get_partner_statistics()
    
    return api_response(
        data={'statistics': stats},
        message="Partner statistics retrieved successfully"
    )


@bp.route('/relationships/analysis', methods=['GET'])
@error_handler
def analyze_partner_relationships():
    """Analyze partner relationships and network."""
    analysis = partner_service.analyze_partner_relationships()
    
    return api_response(
        data={'relationship_analysis': analysis},
        message="Partner relationship analysis completed successfully"
    )


@bp.route('/recommendations', methods=['POST'])
@error_handler
def recommend_partners():
    """Recommend partners based on requirements."""
    # Validate request data
    data = validate_json_request(['requirements'])
    
    # Get recommendations
    recommendations = partner_service.recommend_partner_matches(data['requirements'])
    
    return api_response(
        data={
            'recommendations': recommendations,
            'total': len(recommendations)
        },
        message="Partner recommendations generated successfully"
    )


@bp.route('/search', methods=['GET'])
@error_handler
def search_partners():
    """Search partners by name pattern."""
    # Validate query parameters
    params = validate_query_params({
        'q': {'type': str, 'required': True}
    })
    
    partners = partner_service.partner_repo.search_by_name(params['q'])
    serialized_partners = [serialize_model(partner) for partner in partners]
    
    return api_response(
        data={
            'partners': serialized_partners,
            'total': len(serialized_partners),
            'query': params['q']
        },
        message="Search completed successfully"
    )


@bp.route('/by-contract-volume', methods=['GET'])
@error_handler
def get_partners_by_contract_volume():
    """Get partners filtered by contract volume."""
    # Validate query parameters
    params = validate_query_params({
        'min_volume': {'type': int, 'required': False, 'min_value': 0},
        'max_volume': {'type': int, 'required': False, 'min_value': 0}
    })
    
    partners = partner_service.partner_repo.get_partners_by_contract_volume(
        params['min_volume'], params['max_volume']
    )
    serialized_partners = [serialize_model(partner) for partner in partners]
    
    return api_response(
        data={
            'partners': serialized_partners,
            'total': len(serialized_partners),
            'filters': {
                'min_volume': params['min_volume'],
                'max_volume': params['max_volume']
            }
        },
        message="Partners retrieved successfully"
    )


@bp.route('/production/<int:production_id>', methods=['GET'])
@error_handler
def get_partners_in_production(production_id: int):
    """Get partners enrolled in a specific production."""
    partners = partner_service.partner_repo.get_enrolled_in_production(production_id)
    serialized_partners = [serialize_model(partner) for partner in partners]
    
    return api_response(
        data={
            'partners': serialized_partners,
            'total': len(serialized_partners),
            'production_id': production_id
        },
        message="Production partners retrieved successfully"
    )

