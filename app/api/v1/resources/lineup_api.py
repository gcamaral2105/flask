"""
Lineup API
==========

RESTful API for Lineup management with CBG-specific operations.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, date
from typing import Dict, Any

from app.services.lineup_service import LineupService
from app.api.v1.utils import api_response, validate_json, handle_api_error
from app.middleware.auth import require_auth, require_role

lineup_bp = Blueprint('lineup', __name__, url_prefix='/lineups')
lineup_service = LineupService()


@lineup_bp.route('', methods=['GET'])
@require_auth
def get_lineups():
    """Get current lineup with filtering options."""
    try:
        # Query parameters
        limit = request.args.get('limit', 50, type=int)
        status = request.args.get('status')
        berth_id = request.args.get('berth_id', type=int)
        partner_id = request.args.get('partner_id', type=int)
        
        if status:
            from app.models.lineup import LineupStatus
            try:
                status_enum = LineupStatus(status)
                lineups = lineup_service.lineup_repo.get_by_status(status_enum)
            except ValueError:
                return api_response(False, "Invalid status value", error_code=400)
        elif berth_id:
            lineups = lineup_service.lineup_repo.get_by_berth(berth_id)
        elif partner_id:
            lineups = lineup_service.lineup_repo.get_by_partner(partner_id)
        else:
            lineups = lineup_service.get_current_lineup(limit)
        
        return api_response(True, "Lineups retrieved successfully", {
            'lineups': lineups,
            'total': len(lineups)
        })
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/<int:lineup_id>', methods=['GET'])
@require_auth
def get_lineup(lineup_id: int):
    """Get specific lineup details."""
    try:
        lineup = lineup_service.lineup_repo.get_by_id(lineup_id)
        if not lineup:
            return api_response(False, "Lineup not found", error_code=404)
        
        lineup_data = lineup.to_dict(
            expand=['partner', 'product', 'berth', 'vld'],
            with_metrics=True
        )
        
        return api_response(True, "Lineup retrieved successfully", {
            'lineup': lineup_data
        })
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def create_lineup():
    """Create lineup from VLD."""
    try:
        data = validate_json(request, required_fields=['vld_id', 'berth_id'])
        
        result = lineup_service.create_lineup_from_vld(
            vld_id=data['vld_id'],
            berth_id=data['berth_id'],
            eta=datetime.fromisoformat(data['eta']) if data.get('eta') else None,
            vessel_id=data.get('vessel_id')
        )
        
        return api_response(
            result['success'], 
            result['message'], 
            {'lineup': result['lineup']}
        )
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/<int:lineup_id>/arrival', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def update_arrival(lineup_id: int):
    """Update vessel arrival information."""
    try:
        data = validate_json(request, required_fields=['ata'])
        
        result = lineup_service.update_vessel_arrival(
            lineup_id=lineup_id,
            ata=datetime.fromisoformat(data['ata']),
            vessel_name=data.get('vessel_name')
        )
        
        return api_response(
            result['success'],
            result['message'],
            {
                'lineup': result['lineup'],
                'delay_hours': result.get('delay_hours')
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/<int:lineup_id>/nor', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def tender_nor(lineup_id: int):
    """Tender Notice of Readiness."""
    try:
        data = request.get_json() or {}
        
        nor_time = None
        if data.get('nor_time'):
            nor_time = datetime.fromisoformat(data['nor_time'])
        
        result = lineup_service.tender_nor(lineup_id, nor_time)
        
        return api_response(
            result['success'],
            result['message'],
            {
                'lineup': result['lineup'],
                'waiting_hours': result.get('waiting_hours')
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/<int:lineup_id>/berth', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def berth_vessel(lineup_id: int):
    """Berth a vessel."""
    try:
        data = request.get_json() or {}
        
        atb = None
        etb = None
        if data.get('atb'):
            atb = datetime.fromisoformat(data['atb'])
        if data.get('etb'):
            etb = datetime.fromisoformat(data['etb'])
        
        result = lineup_service.berth_vessel(lineup_id, atb, etb)
        
        return api_response(
            result['success'],
            result['message'],
            {'lineup': result['lineup']}
        )
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/<int:lineup_id>/loading/start', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def start_loading(lineup_id: int):
    """Start loading operations."""
    try:
        data = request.get_json() or {}
        
        loading_start = None
        if data.get('loading_start'):
            loading_start = datetime.fromisoformat(data['loading_start'])
        
        result = lineup_service.start_loading(lineup_id, loading_start)
        
        return api_response(
            result['success'],
            result['message'],
            {'lineup': result['lineup']}
        )
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/<int:lineup_id>/loading/complete', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def complete_loading(lineup_id: int):
    """Complete loading operations."""
    try:
        data = validate_json(request, required_fields=['actual_tonnage'])
        
        loading_completion = None
        if data.get('loading_completion'):
            loading_completion = datetime.fromisoformat(data['loading_completion'])
        
        result = lineup_service.complete_loading(
            lineup_id=lineup_id,
            actual_tonnage=data['actual_tonnage'],
            loading_completion=loading_completion,
            moisture_content=data.get('moisture_content')
        )
        
        return api_response(
            result['success'],
            result['message'],
            {
                'lineup': result['lineup'],
                'performance_metrics': result['performance_metrics']
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/<int:lineup_id>/departure', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def vessel_departure(lineup_id: int):
    """Record vessel departure."""
    try:
        data = request.get_json() or {}
        
        ats = None
        if data.get('ats'):
            ats = datetime.fromisoformat(data['ats'])
        
        result = lineup_service.vessel_departure(lineup_id, ats)
        
        return api_response(
            result['success'],
            result['message'],
            {
                'lineup': result['lineup'],
                'port_stay_hours': result.get('port_stay_hours')
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/current', methods=['GET'])
@require_auth
def get_current_lineup():
    """Get current active lineup."""
    try:
        limit = request.args.get('limit', 50, type=int)
        lineups = lineup_service.get_current_lineup(limit)
        
        return api_response(True, "Current lineup retrieved successfully", {
            'lineups': lineups,
            'total': len(lineups)
        })
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/waiting', methods=['GET'])
@require_auth
def get_waiting_vessels():
    """Get vessels waiting for berth."""
    try:
        waiting_vessels = lineup_service.lineup_repo.get_waiting_for_berth()
        
        vessels_data = []
        for lineup in waiting_vessels:
            lineup_data = lineup.to_dict(expand=['partner'], with_metrics=True)
            vessels_data.append(lineup_data)
        
        return api_response(True, "Waiting vessels retrieved successfully", {
            'waiting_vessels': vessels_data,
            'total': len(vessels_data)
        })
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/overdue', methods=['GET'])
@require_auth
def get_overdue_vessels():
    """Get overdue vessels."""
    try:
        overdue_vessels = lineup_service.lineup_repo.get_overdue_vessels()
        
        vessels_data = []
        for lineup in overdue_vessels:
            lineup_data = lineup.to_dict(expand=['partner'], with_metrics=True)
            vessels_data.append(lineup_data)
        
        return api_response(True, "Overdue vessels retrieved successfully", {
            'overdue_vessels': vessels_data,
            'total': len(vessels_data)
        })
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/loading', methods=['GET'])
@require_auth
def get_loading_vessels():
    """Get vessels currently loading."""
    try:
        loading_vessels = lineup_service.lineup_repo.get_active_loading()
        
        vessels_data = []
        for lineup in loading_vessels:
            lineup_data = lineup.to_dict(expand=['partner', 'berth'], with_metrics=True)
            vessels_data.append(lineup_data)
        
        return api_response(True, "Loading vessels retrieved successfully", {
            'loading_vessels': vessels_data,
            'total': len(vessels_data)
        })
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/optimize', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def optimize_lineup():
    """Optimize lineup sequence."""
    try:
        data = request.get_json() or {}
        berth_id = data.get('berth_id')
        
        result = lineup_service.optimize_lineup_sequence(berth_id)
        
        return api_response(
            result['success'],
            "Lineup optimization completed",
            {
                'optimized_sequence': result['optimized_sequence'],
                'total_vessels': result['total_vessels'],
                'optimization_criteria': result['optimization_criteria']
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/conflicts', methods=['GET'])
@require_auth
def get_lineup_conflicts():
    """Get lineup conflicts analysis."""
    try:
        result = lineup_service.get_lineup_conflicts()
        
        return api_response(
            result['success'],
            "Lineup conflicts analyzed",
            {
                'conflicts': result['conflicts'],
                'total_conflicts': result['total_conflicts'],
                'severity_levels': result['severity_levels']
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/statistics', methods=['GET'])
@require_auth
def get_lineup_statistics():
    """Get lineup statistics."""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        start_date_obj = None
        end_date_obj = None
        
        if start_date:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        if end_date:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        stats = lineup_service.lineup_repo.get_lineup_statistics(start_date_obj, end_date_obj)
        
        return api_response(True, "Lineup statistics retrieved successfully", {
            'statistics': stats,
            'period': {
                'start_date': start_date,
                'end_date': end_date
            }
        })
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/berths/<int:berth_id>/utilization', methods=['GET'])
@require_auth
def get_berth_utilization(berth_id: int):
    """Get berth utilization report."""
    try:
        start_date = request.args.get('start_date', required=True)
        end_date = request.args.get('end_date', required=True)
        
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        utilization = lineup_service.lineup_repo.get_berth_utilization(
            berth_id, start_date_obj, end_date_obj
        )
        
        return api_response(True, "Berth utilization retrieved successfully", {
            'utilization': utilization
        })
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/berths/utilization/report', methods=['GET'])
@require_auth
def get_berth_utilization_report():
    """Get comprehensive berth utilization report."""
    try:
        start_date = request.args.get('start_date', required=True)
        end_date = request.args.get('end_date', required=True)
        
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        result = lineup_service.get_berth_utilization_report(start_date_obj, end_date_obj)
        
        return api_response(
            result['success'],
            "Berth utilization report generated",
            {
                'period': result['period'],
                'berth_reports': result['berth_reports'],
                'fleet_summary': result['fleet_summary']
            }
        )
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/partners/<int:partner_id>/performance', methods=['GET'])
@require_auth
def get_partner_performance(partner_id: int):
    """Get partner performance in lineup operations."""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        start_date_obj = None
        end_date_obj = None
        
        if start_date:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        if end_date:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        performance = lineup_service.lineup_repo.get_partner_performance(
            partner_id, start_date_obj, end_date_obj
        )
        
        return api_response(True, "Partner performance retrieved successfully", {
            'performance': performance
        })
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/search', methods=['GET'])
@require_auth
def search_lineups():
    """Search lineups by vessel name or partner."""
    try:
        search_term = request.args.get('q', '').strip()
        if not search_term:
            return api_response(False, "Search term is required", error_code=400)
        
        lineups = lineup_service.lineup_repo.search_by_vessel_or_partner(search_term)
        
        lineups_data = []
        for lineup in lineups:
            lineup_data = lineup.to_dict(expand=['partner'], with_metrics=True)
            lineups_data.append(lineup_data)
        
        return api_response(True, f"Search results for '{search_term}'", {
            'lineups': lineups_data,
            'total': len(lineups_data),
            'search_term': search_term
        })
        
    except Exception as e:
        return handle_api_error(e)


@lineup_bp.route('/upcoming', methods=['GET'])
@require_auth
def get_upcoming_arrivals():
    """Get upcoming vessel arrivals."""
    try:
        days_ahead = request.args.get('days', 7, type=int)
        
        upcoming = lineup_service.lineup_repo.get_upcoming_arrivals(days_ahead)
        
        arrivals_data = []
        for lineup in upcoming:
            lineup_data = lineup.to_dict(expand=['partner'], with_metrics=True)
            arrivals_data.append(lineup_data)
        
        return api_response(True, f"Upcoming arrivals for next {days_ahead} days", {
            'upcoming_arrivals': arrivals_data,
            'total': len(arrivals_data),
            'days_ahead': days_ahead
        })
        
    except Exception as e:
        return handle_api_error(e)

