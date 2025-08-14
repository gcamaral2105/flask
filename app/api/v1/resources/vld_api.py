"""
VLD API
=======

RESTful API for VLD (Vessel Loading Date) management with comprehensive
scheduling, planning, and optimization capabilities.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, date, timedelta
from typing import Dict, Any

from app.services.vld_service import VLDService
from app.api.v1.utils import api_response, validate_json, handle_api_error
from app.middleware.auth import require_auth, require_role

vld_bp = Blueprint('vld', __name__, url_prefix='/vlds')
vld_service = VLDService()


@vld_bp.route('', methods=['GET'])
@require_auth
def get_vlds():
    """Get VLDs with filtering options."""
    try:
        # Query parameters
        status = request.args.get('status')
        partner_id = request.args.get('partner_id', type=int)
        production_id = request.args.get('production_id', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        start_date_obj = None
        end_date_obj = None
        
        if start_date:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        if end_date:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        if status:
            from app.models.vld import VLDStatus
            try:
                status_enum = VLDStatus(status)
                vlds = vld_service.vld_repo.get_by_status(status_enum)
            except ValueError:
                return api_response(False, "Invalid status value", error_code=400)
        elif partner_id:
            vlds = vld_service.vld_repo.get_by_partner(partner_id, start_date_obj, end_date_obj)
        elif production_id:
            vlds = vld_service.vld_repo.get_by_production(production_id, start_date_obj, end_date_obj)
        elif start_date_obj and end_date_obj:
            vlds = vld_service.vld_repo.get_by_date_range(start_date_obj, end_date_obj, production_id)
        else:
            # Default: get current month VLDs
            today = date.today()
            start_date_obj = today.replace(day=1)
            end_date_obj = (start_date_obj + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            vlds = vld_service.vld_repo.get_by_date_range(start_date_obj, end_date_obj)
        
        vlds_data = []
        for vld in vlds:
            vld_data = vld.to_dict()
            vlds_data.append(vld_data)
        
        return api_response(True, "VLDs retrieved successfully", {
            'vlds': vlds_data,
            'total': len(vlds_data),
            'filters': {
                'status': status,
                'partner_id': partner_id,
                'production_id': production_id,
                'start_date': start_date,
                'end_date': end_date
            }
        })
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/<int:vld_id>', methods=['GET'])
@require_auth
def get_vld(vld_id: int):
    """Get specific VLD details."""
    try:
        vld = vld_service.vld_repo.get_by_id(vld_id)
        if not vld:
            return api_response(False, "VLD not found", error_code=404)
        
        vld_data = vld.to_dict()
        
        return api_response(True, "VLD retrieved successfully", {
            'vld': vld_data
        })
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/schedule', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def create_vld_schedule():
    """Create VLD schedule for a production."""
    try:
        data = validate_json(request, required_fields=['production_id', 'partner_allocations'])
        
        result = vld_service.create_vld_schedule(
            production_id=data['production_id'],
            partner_allocations=data['partner_allocations']
        )
        
        return api_response(
            result['success'],
            result['message'],
            {
                'created_vlds': result['created_vlds'],
                'vlds': result['vlds'],
                'errors': result['errors']
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/<int:vld_id>/narrow', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def set_narrow_period(vld_id: int):
    """Set narrow period for a VLD."""
    try:
        data = validate_json(request, required_fields=['narrow_start', 'narrow_end'])
        
        narrow_start = datetime.strptime(data['narrow_start'], '%Y-%m-%d').date()
        narrow_end = datetime.strptime(data['narrow_end'], '%Y-%m-%d').date()
        
        result = vld_service.set_narrow_period(
            vld_id=vld_id,
            narrow_start=narrow_start,
            narrow_end=narrow_end,
            exception_reason=data.get('exception_reason')
        )
        
        return api_response(
            result['success'],
            result['message'],
            {
                'vld': result['vld'],
                'narrow_period': result['narrow_period']
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/<int:vld_id>/nominate', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def nominate_vessel(vld_id: int):
    """Nominate vessel for a VLD."""
    try:
        data = validate_json(request, required_fields=['vessel_name'])
        
        result = vld_service.nominate_vessel(
            vld_id=vld_id,
            vessel_name=data['vessel_name'],
            imo=data.get('imo')
        )
        
        return api_response(
            result['success'],
            result['message'],
            {
                'vld': result['vld'],
                'vessel': result['vessel']
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/<int:vld_id>/defer', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def defer_vld(vld_id: int):
    """Defer VLD to a new date."""
    try:
        data = validate_json(request, required_fields=['new_date', 'reason'])
        
        new_date = datetime.strptime(data['new_date'], '%Y-%m-%d').date()
        
        result = vld_service.defer_vld(
            vld_id=vld_id,
            new_date=new_date,
            reason=data['reason']
        )
        
        return api_response(
            result['success'],
            result['message'],
            {
                'vld': result['vld'],
                'deferral': result.get('deferral'),
                'conflicts': result.get('conflicts')
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/<int:vld_id>/reassign', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def reassign_vld(vld_id: int):
    """Reassign VLD to a different partner."""
    try:
        data = validate_json(request, required_fields=['new_partner_id', 'reason'])
        
        result = vld_service.reassign_vld(
            vld_id=vld_id,
            new_partner_id=data['new_partner_id'],
            reason=data['reason']
        )
        
        return api_response(
            result['success'],
            result['message'],
            {
                'vld': result['vld'],
                'reassignment': result.get('reassignment'),
                'conflicts': result.get('conflicts')
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/<int:vld_id>/cancel', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def cancel_vld(vld_id: int):
    """Cancel a VLD."""
    try:
        data = validate_json(request, required_fields=['reason'])
        
        result = vld_service.cancel_vld(
            vld_id=vld_id,
            reason=data['reason']
        )
        
        return api_response(
            result['success'],
            result['message'],
            {
                'vld': result['vld'],
                'cancellation': result['cancellation']
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/<int:vld_id>/restore', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def restore_cancelled_vld(vld_id: int):
    """Restore a cancelled VLD."""
    try:
        data = validate_json(request, required_fields=['reason'])
        
        result = vld_service.restore_cancelled_vld(
            vld_id=vld_id,
            reason=data['reason']
        )
        
        return api_response(
            result['success'],
            result['message'],
            {
                'vld': result['vld'],
                'restoration': result.get('restoration'),
                'conflicts': result.get('conflicts')
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/<int:vld_id>/complete', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def complete_vld_loading(vld_id: int):
    """Complete VLD loading with actual results."""
    try:
        data = validate_json(request, required_fields=['actual_tonnage'])
        
        result = vld_service.complete_vld_loading(
            vld_id=vld_id,
            actual_tonnage=data['actual_tonnage'],
            moisture_content=data.get('moisture_content'),
            loader_number=data.get('loader_number')
        )
        
        return api_response(
            result['success'],
            result['message'],
            {
                'vld': result['vld'],
                'completion': result['completion']
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/planned', methods=['GET'])
@require_auth
def get_planned_vlds():
    """Get planned VLDs."""
    try:
        production_id = request.args.get('production_id', type=int)
        partner_id = request.args.get('partner_id', type=int)
        
        from app.models.vld import VLDStatus
        planned_vlds = vld_service.vld_repo.get_by_status(VLDStatus.PLANNED)
        
        # Apply additional filters
        if production_id:
            planned_vlds = [v for v in planned_vlds if v.production_id == production_id]
        if partner_id:
            planned_vlds = [v for v in planned_vlds if v.current_partner_id == partner_id]
        
        vlds_data = []
        for vld in planned_vlds:
            vld_data = vld.to_dict()
            vlds_data.append(vld_data)
        
        return api_response(True, "Planned VLDs retrieved successfully", {
            'planned_vlds': vlds_data,
            'total': len(vlds_data)
        })
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/narrowed', methods=['GET'])
@require_auth
def get_narrowed_vlds():
    """Get narrowed VLDs."""
    try:
        from app.models.vld import VLDStatus
        narrowed_vlds = vld_service.vld_repo.get_by_status(VLDStatus.NARROWED)
        
        vlds_data = []
        for vld in narrowed_vlds:
            vld_data = vld.to_dict()
            vlds_data.append(vld_data)
        
        return api_response(True, "Narrowed VLDs retrieved successfully", {
            'narrowed_vlds': vlds_data,
            'total': len(vlds_data)
        })
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/nominated', methods=['GET'])
@require_auth
def get_nominated_vlds():
    """Get nominated VLDs."""
    try:
        from app.models.vld import VLDStatus
        nominated_vlds = vld_service.vld_repo.get_by_status(VLDStatus.NOMINATED)
        
        vlds_data = []
        for vld in nominated_vlds:
            vld_data = vld.to_dict()
            vlds_data.append(vld_data)
        
        return api_response(True, "Nominated VLDs retrieved successfully", {
            'nominated_vlds': vlds_data,
            'total': len(vlds_data)
        })
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/loading', methods=['GET'])
@require_auth
def get_loading_vlds():
    """Get VLDs currently loading."""
    try:
        from app.models.vld import VLDStatus
        loading_vlds = vld_service.vld_repo.get_by_status(VLDStatus.LOADING)
        
        vlds_data = []
        for vld in loading_vlds:
            vld_data = vld.to_dict()
            vlds_data.append(vld_data)
        
        return api_response(True, "Loading VLDs retrieved successfully", {
            'loading_vlds': vlds_data,
            'total': len(vlds_data)
        })
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/completed', methods=['GET'])
@require_auth
def get_completed_vlds():
    """Get completed VLDs."""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        start_date_obj = None
        end_date_obj = None
        
        if start_date:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        if end_date:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        from app.models.vld import VLDStatus
        completed_vlds = vld_service.vld_repo.get_completed_vlds(start_date_obj, end_date_obj)
        
        vlds_data = []
        for vld in completed_vlds:
            vld_data = vld.to_dict()
            vlds_data.append(vld_data)
        
        return api_response(True, "Completed VLDs retrieved successfully", {
            'completed_vlds': vlds_data,
            'total': len(vlds_data),
            'period': {
                'start_date': start_date,
                'end_date': end_date
            }
        })
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/cancelled', methods=['GET'])
@require_auth
def get_cancelled_vlds():
    """Get cancelled VLDs."""
    try:
        from app.models.vld import VLDStatus
        cancelled_vlds = vld_service.vld_repo.get_by_status(VLDStatus.CANCELLED)
        
        vlds_data = []
        for vld in cancelled_vlds:
            vld_data = vld.to_dict()
            vlds_data.append(vld_data)
        
        return api_response(True, "Cancelled VLDs retrieved successfully", {
            'cancelled_vlds': vlds_data,
            'total': len(vlds_data)
        })
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/carried-over', methods=['GET'])
@require_auth
def get_carried_over_vlds():
    """Get carried over VLDs."""
    try:
        carried_over_vlds = vld_service.vld_repo.get_carried_over_vlds()
        
        vlds_data = []
        for vld in carried_over_vlds:
            vld_data = vld.to_dict()
            vlds_data.append(vld_data)
        
        return api_response(True, "Carried over VLDs retrieved successfully", {
            'carried_over_vlds': vlds_data,
            'total': len(vlds_data)
        })
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/overdue', methods=['GET'])
@require_auth
def get_overdue_vlds():
    """Get overdue VLDs."""
    try:
        overdue_vlds = vld_service.vld_repo.get_overdue_vlds()
        
        vlds_data = []
        for vld in overdue_vlds:
            vld_data = vld.to_dict()
            vlds_data.append(vld_data)
        
        return api_response(True, "Overdue VLDs retrieved successfully", {
            'overdue_vlds': vlds_data,
            'total': len(vlds_data)
        })
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/statistics', methods=['GET'])
@require_auth
def get_vld_statistics():
    """Get VLD statistics."""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        production_id = request.args.get('production_id', type=int)
        
        start_date_obj = None
        end_date_obj = None
        
        if start_date:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        if end_date:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        stats = vld_service.vld_repo.get_vld_statistics(start_date_obj, end_date_obj, production_id)
        
        return api_response(True, "VLD statistics retrieved successfully", {
            'statistics': stats,
            'period': {
                'start_date': start_date,
                'end_date': end_date
            }
        })
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/optimize/<int:production_id>', methods=['GET'])
@require_auth
def get_schedule_optimization(production_id: int):
    """Get VLD schedule optimization analysis."""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        start_date_obj = None
        end_date_obj = None
        
        if start_date:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        if end_date:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        result = vld_service.get_vld_schedule_optimization(
            production_id, start_date_obj, end_date_obj
        )
        
        return api_response(
            result['success'],
            "Schedule optimization analysis completed",
            {
                'period': result['period'],
                'analysis': result['analysis'],
                'issues': result['issues'],
                'optimizations': result['optimizations'],
                'recommendations': result['recommendations']
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/calendar/<int:year>/<int:month>', methods=['GET'])
@require_auth
def get_monthly_calendar(year: int, month: int):
    """Get VLD calendar for a specific month."""
    try:
        production_id = request.args.get('production_id', type=int)
        
        result = vld_service.get_monthly_vld_calendar(year, month, production_id)
        
        return api_response(
            result['success'],
            f"VLD calendar for {year}-{month:02d}",
            {
                'calendar': result['schedule'],
                'daily_capacity': result['daily_capacity'],
                'insights': result['insights'],
                'summary': result['summary']
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/partners/<int:partner_id>/performance', methods=['GET'])
@require_auth
def get_partner_vld_performance(partner_id: int):
    """Get partner VLD performance metrics."""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        start_date_obj = None
        end_date_obj = None
        
        if start_date:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        if end_date:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        performance = vld_service.vld_repo.get_partner_vld_performance(
            partner_id, start_date_obj, end_date_obj
        )
        
        return api_response(True, "Partner VLD performance retrieved successfully", {
            'performance': performance
        })
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/search', methods=['GET'])
@require_auth
def search_vlds():
    """Search VLDs by vessel name or other criteria."""
    try:
        search_term = request.args.get('q', '').strip()
        if not search_term:
            return api_response(False, "Search term is required", error_code=400)
        
        vlds = vld_service.vld_repo.search_vlds(search_term)
        
        vlds_data = []
        for vld in vlds:
            vld_data = vld.to_dict()
            vlds_data.append(vld_data)
        
        return api_response(True, f"Search results for '{search_term}'", {
            'vlds': vlds_data,
            'total': len(vlds_data),
            'search_term': search_term
        })
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/upcoming', methods=['GET'])
@require_auth
def get_upcoming_vlds():
    """Get upcoming VLDs."""
    try:
        days_ahead = request.args.get('days', 30, type=int)
        
        upcoming = vld_service.vld_repo.get_upcoming_vlds(days_ahead)
        
        vlds_data = []
        for vld in upcoming:
            vld_data = vld.to_dict()
            vlds_data.append(vld_data)
        
        return api_response(True, f"Upcoming VLDs for next {days_ahead} days", {
            'upcoming_vlds': vlds_data,
            'total': len(vlds_data),
            'days_ahead': days_ahead
        })
        
    except Exception as e:
        return handle_api_error(e)


@vld_bp.route('/conflicts', methods=['GET'])
@require_auth
def get_vld_conflicts():
    """Get VLD conflicts analysis."""
    try:
        production_id = request.args.get('production_id', type=int)
        
        conflicts = vld_service.vld_repo.get_vld_conflicts(production_id)
        
        return api_response(True, "VLD conflicts analyzed", {
            'conflicts': conflicts,
            'total_conflicts': len(conflicts)
        })
        
    except Exception as e:
        return handle_api_error(e)

