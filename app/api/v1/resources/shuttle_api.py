"""
Shuttle API
===========

RESTful API for Shuttle and transloader operations management.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, date
from typing import Dict, Any

from app.services.shuttle_service import ShuttleService
from app.api.v1.utils import api_response, validate_json, handle_api_error
from app.middleware.auth import require_auth, require_role

shuttle_bp = Blueprint('shuttle', __name__, url_prefix='/shuttles')
shuttle_service = ShuttleService()


@shuttle_bp.route('', methods=['GET'])
@require_auth
def get_shuttles():
    """Get shuttle fleet information."""
    try:
        status = request.args.get('status')
        
        if status:
            from app.models.shuttle import ShuttleStatus
            try:
                status_enum = ShuttleStatus(status)
                shuttles = shuttle_service.shuttle_repo.get_by_status(status_enum)
            except ValueError:
                return api_response(False, "Invalid status value", error_code=400)
        else:
            shuttles = shuttle_service.shuttle_repo.get_active_shuttles()
        
        shuttles_data = []
        for shuttle in shuttles:
            shuttle_data = {
                'id': shuttle.id,
                'vessel_name': shuttle.vessel.name if shuttle.vessel else None,
                'vessel_id': shuttle.vessel_id,
                'status': shuttle.status.value,
                'target_loading_rate_tph': shuttle.target_loading_rate_tph,
                'target_discharge_rate_tph': shuttle.target_discharge_rate_tph
            }
            shuttles_data.append(shuttle_data)
        
        return api_response(True, "Shuttles retrieved successfully", {
            'shuttles': shuttles_data,
            'total': len(shuttles_data)
        })
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/<int:shuttle_id>', methods=['GET'])
@require_auth
def get_shuttle(shuttle_id: int):
    """Get specific shuttle details."""
    try:
        shuttle = shuttle_service.shuttle_repo.get_by_id(shuttle_id)
        if not shuttle:
            return api_response(False, "Shuttle not found", error_code=404)
        
        shuttle_data = {
            'id': shuttle.id,
            'vessel_name': shuttle.vessel.name if shuttle.vessel else None,
            'vessel_id': shuttle.vessel_id,
            'status': shuttle.status.value,
            'target_loading_rate_tph': shuttle.target_loading_rate_tph,
            'target_discharge_rate_tph': shuttle.target_discharge_rate_tph,
            'vessel_details': {
                'dwt': shuttle.vessel.dwt if shuttle.vessel else None,
                'loa': shuttle.vessel.loa if shuttle.vessel else None,
                'beam': shuttle.vessel.beam if shuttle.vessel else None
            } if shuttle.vessel else None
        }
        
        return api_response(True, "Shuttle retrieved successfully", {
            'shuttle': shuttle_data
        })
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/fleet/status', methods=['GET'])
@require_auth
def get_fleet_status():
    """Get comprehensive shuttle fleet status."""
    try:
        result = shuttle_service.get_fleet_status()
        
        return api_response(
            result['success'],
            "Fleet status retrieved successfully",
            {
                'fleet_status': result['fleet_status'],
                'summary': result['summary']
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/available', methods=['GET'])
@require_auth
def get_available_shuttles():
    """Get available shuttles for operations."""
    try:
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        date_from_obj = None
        date_to_obj = None
        
        if date_from:
            date_from_obj = datetime.fromisoformat(date_from)
        if date_to:
            date_to_obj = datetime.fromisoformat(date_to)
        
        available_shuttles = shuttle_service.shuttle_repo.get_available_shuttles(
            date_from_obj, date_to_obj
        )
        
        shuttles_data = []
        for shuttle in available_shuttles:
            shuttle_data = {
                'id': shuttle.id,
                'vessel_name': shuttle.vessel.name if shuttle.vessel else None,
                'status': shuttle.status.value,
                'target_loading_rate_tph': shuttle.target_loading_rate_tph,
                'target_discharge_rate_tph': shuttle.target_discharge_rate_tph
            }
            shuttles_data.append(shuttle_data)
        
        return api_response(True, "Available shuttles retrieved successfully", {
            'available_shuttles': shuttles_data,
            'total': len(shuttles_data),
            'time_window': {
                'from': date_from,
                'to': date_to
            }
        })
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/alcoa', methods=['GET'])
@require_auth
def get_alcoa_shuttles():
    """Get Alcoa-operated shuttles (CSL Argosy and CSL Acadian)."""
    try:
        alcoa_shuttles = shuttle_service.shuttle_repo.get_alcoa_shuttles()
        
        shuttles_data = []
        for shuttle in alcoa_shuttles:
            shuttle_data = {
                'id': shuttle.id,
                'vessel_name': shuttle.vessel.name if shuttle.vessel else None,
                'status': shuttle.status.value,
                'target_loading_rate_tph': shuttle.target_loading_rate_tph,
                'target_discharge_rate_tph': shuttle.target_discharge_rate_tph
            }
            shuttles_data.append(shuttle_data)
        
        return api_response(True, "Alcoa shuttles retrieved successfully", {
            'alcoa_shuttles': shuttles_data,
            'total': len(shuttles_data)
        })
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/statistics', methods=['GET'])
@require_auth
def get_shuttle_statistics():
    """Get shuttle fleet statistics."""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        start_date_obj = None
        end_date_obj = None
        
        if start_date:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        if end_date:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        stats = shuttle_service.shuttle_repo.get_shuttle_statistics(start_date_obj, end_date_obj)
        
        return api_response(True, "Shuttle statistics retrieved successfully", {
            'statistics': stats,
            'period': {
                'start_date': start_date,
                'end_date': end_date
            }
        })
        
    except Exception as e:
        return handle_api_error(e)


# Shuttle Operations Endpoints

@shuttle_bp.route('/operations', methods=['GET'])
@require_auth
def get_shuttle_operations():
    """Get shuttle operations."""
    try:
        status = request.args.get('status', 'active')
        shuttle_id = request.args.get('shuttle_id', type=int)
        cape_vessel = request.args.get('cape_vessel')
        
        if status == 'active':
            operations = shuttle_service.operation_repo.get_active_operations()
        elif shuttle_id:
            operations = shuttle_service.operation_repo.get_by_shuttle(shuttle_id)
        elif cape_vessel:
            operations = shuttle_service.operation_repo.get_by_capesize_vessel(cape_vessel)
        else:
            # Get recent operations
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
            operations = shuttle_service.operation_repo.get_completed_operations(start_date, end_date)
        
        operations_data = []
        for operation in operations:
            op_data = shuttle_service._format_operation_response(operation)
            operations_data.append(op_data)
        
        return api_response(True, "Shuttle operations retrieved successfully", {
            'operations': operations_data,
            'total': len(operations_data)
        })
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/operations', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def create_shuttle_operation():
    """Create a new shuttle operation."""
    try:
        data = validate_json(request, required_fields=['shuttle_id', 'cape_vessel_name'])
        
        result = shuttle_service.create_shuttle_operation(
            shuttle_id=data['shuttle_id'],
            cape_vessel_name=data['cape_vessel_name'],
            loading_lineup_id=data.get('loading_lineup_id'),
            cape_operation_id=data.get('cape_operation_id'),
            planned_volume=data.get('planned_volume')
        )
        
        return api_response(
            result['success'],
            result['message'],
            {'operation': result['operation']}
        )
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/operations/<int:operation_id>', methods=['GET'])
@require_auth
def get_shuttle_operation(operation_id: int):
    """Get specific shuttle operation details."""
    try:
        operation = shuttle_service.operation_repo.get_by_id(operation_id)
        if not operation:
            return api_response(False, "Operation not found", error_code=404)
        
        operation_data = shuttle_service._format_operation_response(operation)
        
        return api_response(True, "Operation retrieved successfully", {
            'operation': operation_data
        })
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/operations/<int:operation_id>/loading/start', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def start_loading_operation(operation_id: int):
    """Start shuttle loading at CBG."""
    try:
        result = shuttle_service.start_loading_operation(operation_id)
        
        return api_response(
            result['success'],
            result['message'],
            {'operation': result['operation']}
        )
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/operations/<int:operation_id>/loading/complete', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def complete_loading_operation(operation_id: int):
    """Complete shuttle loading at CBG."""
    try:
        data = validate_json(request, required_fields=['actual_volume'])
        
        result = shuttle_service.complete_loading_operation(
            operation_id, data['actual_volume']
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


@shuttle_bp.route('/operations/<int:operation_id>/transit/start', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def start_transit(operation_id: int):
    """Start shuttle transit to anchorage."""
    try:
        result = shuttle_service.start_transit(operation_id)
        
        return api_response(
            result['success'],
            result['message'],
            {'operation': result['operation']}
        )
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/operations/<int:operation_id>/discharge/start', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def start_discharge_operation(operation_id: int):
    """Start shuttle discharge to capesize vessel."""
    try:
        result = shuttle_service.start_discharge_operation(operation_id)
        
        return api_response(
            result['success'],
            result['message'],
            {'operation': result['operation']}
        )
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/operations/<int:operation_id>/discharge/complete', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def complete_discharge_operation(operation_id: int):
    """Complete shuttle discharge to capesize vessel."""
    try:
        result = shuttle_service.complete_discharge_operation(operation_id)
        
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


@shuttle_bp.route('/operations/<int:operation_id>/complete', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def complete_shuttle_cycle(operation_id: int):
    """Complete entire shuttle cycle (return to CBG)."""
    try:
        result = shuttle_service.complete_shuttle_cycle(operation_id)
        
        return api_response(
            result['success'],
            result['message'],
            {
                'operation': result['operation'],
                'cycle_metrics': result['cycle_metrics']
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/operations/sublet', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def create_sublet_operation():
    """Create a sublet shuttle operation."""
    try:
        data = validate_json(request, required_fields=[
            'shuttle_id', 'cape_vessel_name', 'sublet_partner_id', 'sublet_vld_id'
        ])
        
        result = shuttle_service.create_sublet_operation(
            shuttle_id=data['shuttle_id'],
            cape_vessel_name=data['cape_vessel_name'],
            sublet_partner_id=data['sublet_partner_id'],
            sublet_vld_id=data['sublet_vld_id'],
            planned_volume=data.get('planned_volume')
        )
        
        return api_response(
            result['success'],
            result['message'],
            {'operation': result['operation']}
        )
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/operations/sublet', methods=['GET'])
@require_auth
def get_sublet_operations():
    """Get sublet operations."""
    try:
        partner_id = request.args.get('partner_id', type=int)
        
        sublet_operations = shuttle_service.operation_repo.get_sublet_operations(partner_id)
        
        operations_data = []
        for operation in sublet_operations:
            op_data = shuttle_service._format_operation_response(operation)
            op_data['sublet_partner'] = {
                'id': operation.sublet_partner.id,
                'name': operation.sublet_partner.name
            } if operation.sublet_partner else None
            operations_data.append(op_data)
        
        return api_response(True, "Sublet operations retrieved successfully", {
            'sublet_operations': operations_data,
            'total': len(operations_data)
        })
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/operations/<int:operation_id>/performance', methods=['GET'])
@require_auth
def get_operation_performance(operation_id: int):
    """Get performance metrics for a specific operation."""
    try:
        performance = shuttle_service.operation_repo.get_operation_performance(operation_id)
        
        if not performance:
            return api_response(False, "Operation not found", error_code=404)
        
        return api_response(True, "Operation performance retrieved successfully", {
            'performance': performance
        })
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/<int:shuttle_id>/utilization', methods=['GET'])
@require_auth
def get_shuttle_utilization(shuttle_id: int):
    """Get shuttle utilization for a period."""
    try:
        start_date = request.args.get('start_date', required=True)
        end_date = request.args.get('end_date', required=True)
        
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        utilization = shuttle_service.operation_repo.get_shuttle_utilization(
            shuttle_id, start_date_obj, end_date_obj
        )
        
        return api_response(True, "Shuttle utilization retrieved successfully", {
            'utilization': utilization
        })
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/utilization/report', methods=['GET'])
@require_auth
def get_utilization_report():
    """Generate shuttle utilization report."""
    try:
        start_date = request.args.get('start_date', required=True)
        end_date = request.args.get('end_date', required=True)
        
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        result = shuttle_service.get_shuttle_utilization_report(start_date_obj, end_date_obj)
        
        return api_response(
            result['success'],
            "Shuttle utilization report generated",
            {
                'period': result['period'],
                'shuttle_reports': result['shuttle_reports'],
                'fleet_summary': result['fleet_summary']
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/capesize/<cape_vessel_name>/analysis', methods=['GET'])
@require_auth
def get_capesize_completion_analysis(cape_vessel_name: str):
    """Analyze shuttle operations for capesize completion."""
    try:
        result = shuttle_service.get_capesize_completion_analysis(cape_vessel_name)
        
        return api_response(
            result['success'],
            result.get('message', 'Analysis completed'),
            {'analysis': result.get('analysis')}
        )
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/optimize/allocation', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def optimize_shuttle_allocation():
    """Optimize shuttle allocation based on requirements."""
    try:
        data = validate_json(request, required_fields=['total_capacity'])
        
        result = shuttle_service.optimize_shuttle_allocation(data)
        
        return api_response(
            result['success'],
            result.get('message', 'Allocation optimization completed'),
            {
                'requirements': result.get('requirements'),
                'allocation': result.get('allocation'),
                'summary': result.get('summary')
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@shuttle_bp.route('/capesize/<int:capesize_id>/plan', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def plan_capesize_loading(capesize_id: int):
    """Plan shuttle operations for a capesize vessel loading."""
    try:
        result = shuttle_service.plan_capesize_loading(capesize_id)
        
        return api_response(
            result['success'],
            result['message'],
            {
                'capesize_vessel': result.get('capesize_vessel'),
                'plan': result.get('plan'),
                'summary': result.get('summary')
            }
        )
        
    except Exception as e:
        return handle_api_error(e)

