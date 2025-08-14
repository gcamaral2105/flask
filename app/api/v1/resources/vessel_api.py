"""
Vessel API
=========

RESTful API endpoints for Vessel management in the ERP Bauxita system.
"""

from flask import Blueprint, request
from typing import Dict, Any

from app.services import VesselService
from app.api.v1.utils import (
    api_response, handle_api_error, validate_json_request, 
    validate_query_params, serialize_model, error_handler
)

# Create blueprint
bp = Blueprint('vessel_api', __name__, url_prefix='/vessels')

# Initialize service
vessel_service = VesselService()


@bp.route('', methods=['GET'])
@error_handler
def list_vessels():
    """
    List vessels with optional filtering.
    
    Query Parameters:
        - type: Filter by vessel type (shuttle, panamax, capesize)
        - status: Filter by vessel status (active, inactive, maintenance, retired)
        - owner_id: Filter by owner partner ID
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20)
    """
    # Validate query parameters
    params = validate_query_params({
        'type': {'type': str, 'required': False, 
                'choices': ['shuttle', 'panamax', 'capesize']},
        'status': {'type': str, 'required': False,
                  'choices': ['active', 'inactive', 'maintenance', 'retired']},
        'owner_id': {'type': int, 'required': False},
        'page': {'type': int, 'default': 1, 'min_value': 1},
        'per_page': {'type': int, 'default': 20, 'min_value': 1, 'max_value': 100}
    })
    
    # Get vessels based on filters
    if params['type']:
        from app.models.vessel import VesselType
        vessel_type = VesselType(params['type'])
        vessels = vessel_service.vessel_repo.get_by_type(vessel_type)
    elif params['status']:
        from app.models.vessel import VesselStatus
        vessel_status = VesselStatus(params['status'])
        vessels = vessel_service.vessel_repo.get_by_status(vessel_status)
    elif params['owner_id']:
        vessels = vessel_service.vessel_repo.get_by_owner(params['owner_id'])
    else:
        vessels = vessel_service.vessel_repo.get_active()
    
    # Serialize results
    serialized_vessels = [serialize_model(vessel) for vessel in vessels]
    
    return api_response(
        data={
            'vessels': serialized_vessels,
            'total': len(serialized_vessels)
        },
        message="Vessels retrieved successfully"
    )


@bp.route('/<int:vessel_id>', methods=['GET'])
@error_handler
def get_vessel(vessel_id: int):
    """Get a specific vessel by ID."""
    vessel = vessel_service.vessel_repo.get_by_id(vessel_id)
    
    if not vessel:
        return api_response(
            data=None,
            message="Vessel not found",
            status_code=404
        )
    
    return api_response(
        data={'vessel': serialize_model(vessel)},
        message="Vessel retrieved successfully"
    )


@bp.route('', methods=['POST'])
@error_handler
def create_vessel():
    """Create a new vessel."""
    # Validate request data
    data = validate_json_request(['name', 'vtype'])
    
    # Create vessel
    vessel = vessel_service.create_vessel(data)
    
    return api_response(
        data={'vessel': serialize_model(vessel)},
        message="Vessel created successfully",
        status_code=201
    )


@bp.route('/<int:vessel_id>', methods=['PUT'])
@error_handler
def update_vessel(vessel_id: int):
    """Update a vessel."""
    # Validate request data
    data = validate_json_request()
    
    # Update vessel
    vessel = vessel_service.vessel_repo.update(vessel_id, **data)
    
    if not vessel:
        return api_response(
            data=None,
            message="Vessel not found",
            status_code=404
        )
    
    return api_response(
        data={'vessel': serialize_model(vessel)},
        message="Vessel updated successfully"
    )


@bp.route('/<int:vessel_id>', methods=['DELETE'])
@error_handler
def delete_vessel(vessel_id: int):
    """Delete (soft delete) a vessel."""
    success = vessel_service.vessel_repo.delete(vessel_id)
    
    if not success:
        return api_response(
            data=None,
            message="Vessel not found",
            status_code=404
        )
    
    return api_response(
        data=None,
        message="Vessel deleted successfully"
    )


@bp.route('/<int:vessel_id>/specifications', methods=['PUT'])
@error_handler
def update_vessel_specifications(vessel_id: int):
    """Update vessel specifications."""
    # Validate request data
    data = validate_json_request()
    
    # Update specifications
    vessel = vessel_service.update_vessel_specifications(vessel_id, data)
    
    return api_response(
        data={'vessel': serialize_model(vessel)},
        message="Vessel specifications updated successfully"
    )


@bp.route('/<int:vessel_id>/status', methods=['PUT'])
@error_handler
def change_vessel_status(vessel_id: int):
    """Change vessel status."""
    # Validate request data
    data = validate_json_request(['status'])
    
    from app.models.vessel import VesselStatus
    new_status = VesselStatus(data['status'])
    reason = data.get('reason')
    
    # Change status
    vessel = vessel_service.change_vessel_status(vessel_id, new_status, reason)
    
    return api_response(
        data={'vessel': serialize_model(vessel)},
        message="Vessel status updated successfully"
    )


@bp.route('/<int:vessel_id>/owner', methods=['PUT'])
@error_handler
def assign_vessel_owner(vessel_id: int):
    """Assign owner to a vessel."""
    # Validate request data
    data = validate_json_request(['owner_partner_id'])
    
    # Assign owner
    vessel = vessel_service.assign_vessel_owner(vessel_id, data['owner_partner_id'])
    
    return api_response(
        data={'vessel': serialize_model(vessel)},
        message="Vessel owner assigned successfully"
    )


@bp.route('/<int:vessel_id>/owner', methods=['DELETE'])
@error_handler
def remove_vessel_owner(vessel_id: int):
    """Remove owner from a vessel."""
    vessel = vessel_service.vessel_repo.remove_owner(vessel_id)
    
    if not vessel:
        return api_response(
            data=None,
            message="Vessel not found",
            status_code=404
        )
    
    return api_response(
        data={'vessel': serialize_model(vessel)},
        message="Vessel owner removed successfully"
    )


@bp.route('/<int:vessel_id>/maintenance', methods=['POST'])
@error_handler
def schedule_maintenance(vessel_id: int):
    """Schedule maintenance for a vessel."""
    # Validate request data
    data = validate_json_request([
        'scheduled_start', 'estimated_duration_days', 'maintenance_type'
    ])
    
    # Schedule maintenance
    maintenance_schedule = vessel_service.schedule_maintenance(vessel_id, data)
    
    return api_response(
        data={'maintenance_schedule': maintenance_schedule},
        message="Maintenance scheduled successfully",
        status_code=201
    )


@bp.route('/<int:vessel_id>/performance', methods=['GET'])
@error_handler
def get_vessel_performance(vessel_id: int):
    """Get vessel performance report."""
    # Validate query parameters
    params = validate_query_params({
        'period_days': {'type': int, 'default': 365, 'min_value': 1, 'max_value': 1825}
    })
    
    # Get performance report
    report = vessel_service.get_vessel_performance_report(vessel_id, params['period_days'])
    
    return api_response(
        data={'performance_report': report},
        message="Vessel performance report generated successfully"
    )


@bp.route('/fleet/overview', methods=['GET'])
@error_handler
def get_fleet_overview():
    """Get fleet overview."""
    # Validate query parameters
    params = validate_query_params({
        'owner_id': {'type': int, 'required': False}
    })
    
    # Get fleet overview
    overview = vessel_service.get_fleet_overview(params['owner_id'])
    
    return api_response(
        data={'fleet_overview': overview},
        message="Fleet overview retrieved successfully"
    )


@bp.route('/fleet/optimize', methods=['POST'])
@error_handler
def optimize_fleet_allocation():
    """Optimize fleet allocation based on requirements."""
    # Validate request data
    data = validate_json_request(['requirements'])
    
    # Optimize allocation
    optimization_result = vessel_service.optimize_fleet_allocation(data['requirements'])
    
    return api_response(
        data={'optimization_result': optimization_result},
        message="Fleet allocation optimized successfully"
    )


@bp.route('/statistics', methods=['GET'])
@error_handler
def get_vessel_statistics():
    """Get vessel statistics."""
    stats = vessel_service.vessel_repo.get_vessel_statistics()
    
    return api_response(
        data={'statistics': stats},
        message="Vessel statistics retrieved successfully"
    )


@bp.route('/search', methods=['GET'])
@error_handler
def search_vessels():
    """Search vessels by name pattern."""
    # Validate query parameters
    params = validate_query_params({
        'q': {'type': str, 'required': True}
    })
    
    vessels = vessel_service.vessel_repo.search_by_name(params['q'])
    serialized_vessels = [serialize_model(vessel) for vessel in vessels]
    
    return api_response(
        data={
            'vessels': serialized_vessels,
            'total': len(serialized_vessels),
            'query': params['q']
        },
        message="Search completed successfully"
    )


@bp.route('/by-imo/<string:imo>', methods=['GET'])
@error_handler
def get_vessel_by_imo(imo: str):
    """Get vessel by IMO number."""
    vessel = vessel_service.vessel_repo.get_by_imo(imo)
    
    if not vessel:
        return api_response(
            data=None,
            message="Vessel not found",
            status_code=404
        )
    
    return api_response(
        data={'vessel': serialize_model(vessel)},
        message="Vessel retrieved successfully"
    )


@bp.route('/by-dwt-range', methods=['GET'])
@error_handler
def get_vessels_by_dwt_range():
    """Get vessels within a DWT range."""
    # Validate query parameters
    params = validate_query_params({
        'min_dwt': {'type': int, 'required': False, 'min_value': 0},
        'max_dwt': {'type': int, 'required': False, 'min_value': 0}
    })
    
    vessels = vessel_service.vessel_repo.get_by_dwt_range(
        params['min_dwt'], params['max_dwt']
    )
    serialized_vessels = [serialize_model(vessel) for vessel in vessels]
    
    return api_response(
        data={
            'vessels': serialized_vessels,
            'total': len(serialized_vessels),
            'filters': {
                'min_dwt': params['min_dwt'],
                'max_dwt': params['max_dwt']
            }
        },
        message="Vessels retrieved successfully"
    )


@bp.route('/available', methods=['GET'])
@error_handler
def get_available_vessels():
    """Get vessels available for operations."""
    vessels = vessel_service.vessel_repo.get_available_vessels()
    serialized_vessels = [serialize_model(vessel) for vessel in vessels]
    
    return api_response(
        data={
            'vessels': serialized_vessels,
            'total': len(serialized_vessels)
        },
        message="Available vessels retrieved successfully"
    )


@bp.route('/maintenance', methods=['GET'])
@error_handler
def get_vessels_in_maintenance():
    """Get vessels currently in maintenance."""
    vessels = vessel_service.vessel_repo.get_vessels_needing_maintenance()
    serialized_vessels = [serialize_model(vessel) for vessel in vessels]
    
    return api_response(
        data={
            'vessels': serialized_vessels,
            'total': len(serialized_vessels)
        },
        message="Vessels in maintenance retrieved successfully"
    )

