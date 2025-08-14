"""
Capesize API
============

RESTful API for Capesize vessel operations management.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, date
from typing import Dict, Any

from app.services.capesize_service import CapesizeService
from app.api.v1.utils import api_response, validate_json, handle_api_error
from app.middleware.auth import require_auth, require_role

capesize_bp = Blueprint('capesize', __name__, url_prefix='/capesize')
capesize_service = CapesizeService()


@capesize_bp.route('/operations', methods=['GET'])
@require_auth
def get_capesize_operations():
    """Get capesize operations."""
    try:
        status = request.args.get('status', 'active')
        anchorage = request.args.get('anchorage')
        
        if status == 'active':
            result = capesize_service.get_active_operations()
            operations = result['active_operations']
        elif anchorage:
            result = capesize_service.get_anchorage_status(anchorage)
            operations = result['active_operations']
        else:
            # Get all operations for a date range
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            if start_date and end_date:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                operations = capesize_service.capesize_repo.get_by_date_range(start_date_obj, end_date_obj)
                operations = [capesize_service._format_operation_response(op) for op in operations]
            else:
                result = capesize_service.get_active_operations()
                operations = result['active_operations']
        
        return api_response(True, "Capesize operations retrieved successfully", {
            'operations': operations,
            'total': len(operations)
        })
        
    except Exception as e:
        return handle_api_error(e)


@capesize_bp.route('/operations', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def create_capesize_operation():
    """Create a new capesize operation."""
    try:
        data = validate_json(request, required_fields=[
            'cape_vessel_id', 'target_tonnage', 'anchorage_location'
        ])
        
        eta = None
        if data.get('eta'):
            eta = datetime.fromisoformat(data['eta'])
        
        result = capesize_service.create_capesize_operation(
            cape_vessel_id=data['cape_vessel_id'],
            target_tonnage=data['target_tonnage'],
            anchorage_location=data['anchorage_location'],
            eta=eta
        )
        
        return api_response(
            result['success'],
            result['message'],
            {'operation': result['operation']}
        )
        
    except Exception as e:
        return handle_api_error(e)


@capesize_bp.route('/operations/<int:operation_id>', methods=['GET'])
@require_auth
def get_capesize_operation(operation_id: int):
    """Get detailed information about a capesize operation."""
    try:
        result = capesize_service.get_operation_details(operation_id)
        
        return api_response(
            result['success'],
            "Operation details retrieved successfully",
            {
                'operation': result['operation'],
                'shuttle_operations': result['shuttle_operations'],
                'progress': result['progress']
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@capesize_bp.route('/operations/<int:operation_id>/arrival', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def update_arrival(operation_id: int):
    """Update capesize vessel arrival at anchorage."""
    try:
        data = validate_json(request, required_fields=['ata'])
        
        ata = datetime.fromisoformat(data['ata'])
        
        result = capesize_service.update_arrival(operation_id, ata)
        
        return api_response(
            result['success'],
            result['message'],
            {
                'operation': result['operation'],
                'delay_hours': result.get('delay_hours')
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@capesize_bp.route('/operations/<int:operation_id>/loading/start', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def start_loading_operations(operation_id: int):
    """Start loading operations for capesize vessel."""
    try:
        result = capesize_service.start_loading_operations(operation_id)
        
        return api_response(
            result['success'],
            result['message'],
            {'operation': result['operation']}
        )
        
    except Exception as e:
        return handle_api_error(e)


@capesize_bp.route('/operations/<int:operation_id>/loading/complete', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def complete_loading_operations(operation_id: int):
    """Complete loading operations for capesize vessel."""
    try:
        data = validate_json(request, required_fields=['final_tonnage'])
        
        result = capesize_service.complete_loading_operations(
            operation_id, data['final_tonnage']
        )
        
        return api_response(
            result['success'],
            result['message'],
            {
                'operation': result['operation'],
                'performance': result['performance']
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@capesize_bp.route('/operations/<int:operation_id>/departure', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def vessel_departure(operation_id: int):
    """Record capesize vessel departure."""
    try:
        data = request.get_json() or {}
        
        ats = None
        if data.get('ats'):
            ats = datetime.fromisoformat(data['ats'])
        
        result = capesize_service.vessel_departure(operation_id, ats)
        
        return api_response(
            result['success'],
            result['message'],
            {
                'operation': result['operation'],
                'anchorage_hours': result.get('anchorage_hours')
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@capesize_bp.route('/operations/<int:operation_id>/forecast', methods=['GET'])
@require_auth
def get_completion_forecast(operation_id: int):
    """Get completion forecast for a capesize operation."""
    try:
        result = capesize_service.get_completion_forecast(operation_id)
        
        return api_response(
            result['success'],
            result.get('message', 'Forecast generated successfully'),
            {'forecast': result.get('forecast')}
        )
        
    except Exception as e:
        return handle_api_error(e)


@capesize_bp.route('/operations/<int:operation_id>/efficiency', methods=['GET'])
@require_auth
def get_efficiency_analysis(operation_id: int):
    """Analyze efficiency of a capesize operation."""
    try:
        result = capesize_service.get_efficiency_analysis(operation_id)
        
        return api_response(
            result['success'],
            result.get('message', 'Efficiency analysis completed'),
            {'analysis': result.get('analysis')}
        )
        
    except Exception as e:
        return handle_api_error(e)


@capesize_bp.route('/anchorages/<anchorage_location>/status', methods=['GET'])
@require_auth
def get_anchorage_status(anchorage_location: str):
    """Get status of vessels at a specific anchorage."""
    try:
        result = capesize_service.get_anchorage_status(anchorage_location)
        
        return api_response(
            result['success'],
            f"Anchorage status for {anchorage_location}",
            {
                'anchorage_location': result['anchorage_location'],
                'active_operations': result['active_operations'],
                'total_vessels': result['total_vessels'],
                'total_capacity': result['total_capacity']
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@capesize_bp.route('/statistics', methods=['GET'])
@require_auth
def get_capesize_statistics():
    """Get capesize operations statistics."""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        start_date_obj = None
        end_date_obj = None
        
        if start_date:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        if end_date:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        result = capesize_service.get_capesize_statistics(start_date_obj, end_date_obj)
        
        return api_response(
            result['success'],
            "Capesize statistics retrieved successfully",
            {
                'statistics': result['statistics'],
                'period': result['period']
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@capesize_bp.route('/vessels', methods=['GET'])
@require_auth
def get_capesize_vessels():
    """Get capesize vessels."""
    try:
        vessels = capesize_service.capesize_repo.get_all_vessels()
        
        vessels_data = []
        for vessel in vessels:
            vessel_data = {
                'id': vessel.id,
                'name': vessel.name,
                'imo': vessel.imo,
                'dwt': vessel.dwt,
                'loa': vessel.loa,
                'beam': vessel.beam,
                'draft': vessel.draft
            }
            vessels_data.append(vessel_data)
        
        return api_response(True, "Capesize vessels retrieved successfully", {
            'vessels': vessels_data,
            'total': len(vessels_data)
        })
        
    except Exception as e:
        return handle_api_error(e)


@capesize_bp.route('/vessels/<int:vessel_id>', methods=['GET'])
@require_auth
def get_capesize_vessel(vessel_id: int):
    """Get specific capesize vessel details."""
    try:
        vessel = capesize_service.capesize_repo.get_vessel_by_id(vessel_id)
        if not vessel:
            return api_response(False, "Vessel not found", error_code=404)
        
        # Get recent operations for this vessel
        recent_operations = capesize_service.capesize_repo.get_vessel_operations(vessel_id, limit=10)
        
        vessel_data = {
            'id': vessel.id,
            'name': vessel.name,
            'imo': vessel.imo,
            'dwt': vessel.dwt,
            'loa': vessel.loa,
            'beam': vessel.beam,
            'draft': vessel.draft,
            'recent_operations': [
                capesize_service._format_operation_response(op) for op in recent_operations
            ]
        }
        
        return api_response(True, "Vessel details retrieved successfully", {
            'vessel': vessel_data
        })
        
    except Exception as e:
        return handle_api_error(e)


@capesize_bp.route('/performance/summary', methods=['GET'])
@require_auth
def get_performance_summary():
    """Get performance summary for all capesize operations."""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        start_date_obj = None
        end_date_obj = None
        
        if start_date:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        if end_date:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        performance_summary = capesize_service.capesize_repo.get_performance_summary(
            start_date_obj, end_date_obj
        )
        
        return api_response(True, "Performance summary retrieved successfully", {
            'performance_summary': performance_summary,
            'period': {
                'start_date': start_date,
                'end_date': end_date
            }
        })
        
    except Exception as e:
        return handle_api_error(e)


@capesize_bp.route('/search', methods=['GET'])
@require_auth
def search_capesize_operations():
    """Search capesize operations by vessel name or other criteria."""
    try:
        search_term = request.args.get('q', '').strip()
        if not search_term:
            return api_response(False, "Search term is required", error_code=400)
        
        operations = capesize_service.capesize_repo.search_operations(search_term)
        
        operations_data = []
        for operation in operations:
            op_data = capesize_service._format_operation_response(operation)
            operations_data.append(op_data)
        
        return api_response(True, f"Search results for '{search_term}'", {
            'operations': operations_data,
            'total': len(operations_data),
            'search_term': search_term
        })
        
    except Exception as e:
        return handle_api_error(e)

