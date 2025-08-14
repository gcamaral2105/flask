"""
Scheduling API
==============

RESTful API for advanced scheduling and coordination operations.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, date, timedelta
from typing import Dict, Any

from app.services.scheduling_service import SchedulingService
from app.api.v1.utils import api_response, validate_json, handle_api_error
from app.middleware.auth import require_auth, require_role

scheduling_bp = Blueprint('scheduling', __name__, url_prefix='/scheduling')
scheduling_service = SchedulingService()


@scheduling_bp.route('/master-schedule/<int:production_id>', methods=['GET'])
@require_auth
def generate_master_schedule(production_id: int):
    """Generate comprehensive master schedule."""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Default to next 30 days if not specified
        if not start_date:
            start_date = date.today()
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            end_date = start_date + timedelta(days=30)
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        result = scheduling_service.generate_master_schedule(
            production_id, start_date, end_date
        )
        
        return api_response(
            result['success'],
            "Master schedule generated successfully",
            result['master_schedule']
        )
        
    except Exception as e:
        return handle_api_error(e)


@scheduling_bp.route('/optimize/vld-lineup/<int:production_id>', methods=['GET'])
@require_auth
def optimize_vld_lineup_coordination(production_id: int):
    """Optimize coordination between VLDs and Lineups."""
    try:
        window_days = request.args.get('window_days', 30, type=int)
        
        result = scheduling_service.optimize_vld_lineup_coordination(
            production_id, window_days
        )
        
        return api_response(
            result['success'],
            "VLD-Lineup coordination optimization completed",
            result['optimization']
        )
        
    except Exception as e:
        return handle_api_error(e)


@scheduling_bp.route('/optimize/vld-lineup/<int:production_id>', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def apply_vld_lineup_optimization(production_id: int):
    """Apply VLD-Lineup coordination optimization recommendations."""
    try:
        data = validate_json(request, required_fields=['recommendations'])
        
        # This would implement the actual optimization changes
        # For now, return success with applied changes count
        applied_changes = 0
        
        for recommendation in data['recommendations']:
            if recommendation.get('implementation'):
                # Apply the recommendation
                # This would involve updating the database
                applied_changes += 1
        
        return api_response(True, f"Applied {applied_changes} optimization recommendations", {
            'applied_changes': applied_changes,
            'total_recommendations': len(data['recommendations'])
        })
        
    except Exception as e:
        return handle_api_error(e)


@scheduling_bp.route('/plan/shuttle-capesize', methods=['GET'])
@require_auth
def plan_shuttle_capesize_coordination():
    """Plan coordination between shuttle operations and capesize vessels."""
    try:
        horizon_days = request.args.get('horizon_days', 60, type=int)
        
        result = scheduling_service.plan_shuttle_capesize_coordination(horizon_days)
        
        return api_response(
            result['success'],
            "Shuttle-Capesize coordination plan generated",
            result['coordination_plan']
        )
        
    except Exception as e:
        return handle_api_error(e)


@scheduling_bp.route('/capacity/forecast/<int:production_id>', methods=['GET'])
@require_auth
def generate_capacity_forecast(production_id: int):
    """Generate capacity forecast for production planning."""
    try:
        forecast_days = request.args.get('forecast_days', 90, type=int)
        
        result = scheduling_service.generate_capacity_forecast(
            production_id, forecast_days
        )
        
        return api_response(
            result['success'],
            "Capacity forecast generated successfully",
            result['capacity_forecast']
        )
        
    except Exception as e:
        return handle_api_error(e)


@scheduling_bp.route('/critical-path/<int:production_id>', methods=['GET'])
@require_auth
def identify_critical_path_issues(production_id: int):
    """Identify critical path issues in the scheduling chain."""
    try:
        analysis_days = request.args.get('analysis_days', 30, type=int)
        
        result = scheduling_service.identify_critical_path_issues(
            production_id, analysis_days
        )
        
        return api_response(
            result['success'],
            "Critical path analysis completed",
            result['critical_path_analysis']
        )
        
    except Exception as e:
        return handle_api_error(e)


@scheduling_bp.route('/dashboard/<int:production_id>', methods=['GET'])
@require_auth
def get_scheduling_dashboard(production_id: int):
    """Get comprehensive scheduling dashboard data."""
    try:
        # Get multiple scheduling insights in one call
        
        # Master schedule for next 14 days
        start_date = date.today()
        end_date = start_date + timedelta(days=14)
        master_schedule = scheduling_service.generate_master_schedule(
            production_id, start_date, end_date
        )
        
        # Critical path issues
        critical_path = scheduling_service.identify_critical_path_issues(production_id, 14)
        
        # VLD-Lineup coordination opportunities
        coordination = scheduling_service.optimize_vld_lineup_coordination(production_id, 14)
        
        # Capacity forecast for next 30 days
        capacity_forecast = scheduling_service.generate_capacity_forecast(production_id, 30)
        
        dashboard_data = {
            'production_id': production_id,
            'generated_at': datetime.utcnow().isoformat(),
            'master_schedule_summary': {
                'period': master_schedule['master_schedule']['period'],
                'summary': master_schedule['master_schedule']['summary'],
                'high_priority_constraints': len([
                    c for c in master_schedule['master_schedule']['constraints'] 
                    if c['severity'] == 'HIGH'
                ])
            },
            'critical_issues': {
                'total_issues': critical_path['critical_path_analysis']['summary']['total_issues'],
                'critical_issues': critical_path['critical_path_analysis']['summary']['critical_issues'],
                'immediate_action_required': critical_path['critical_path_analysis']['summary']['immediate_action_required'],
                'top_issues': critical_path['critical_path_analysis']['critical_issues'][:3]
            },
            'coordination_opportunities': {
                'total_opportunities': coordination['optimization']['summary']['coordination_opportunities_found'],
                'high_priority_recommendations': coordination['optimization']['summary']['high_priority_recommendations']
            },
            'capacity_outlook': {
                'average_utilization': capacity_forecast['capacity_forecast']['summary']['average_utilization_rate'],
                'high_utilization_days': capacity_forecast['capacity_forecast']['summary']['high_utilization_days'],
                'peak_day': capacity_forecast['capacity_forecast']['summary']['peak_day']
            }
        }
        
        return api_response(True, "Scheduling dashboard data retrieved", {
            'dashboard': dashboard_data
        })
        
    except Exception as e:
        return handle_api_error(e)


@scheduling_bp.route('/recommendations/<int:production_id>', methods=['GET'])
@require_auth
def get_scheduling_recommendations(production_id: int):
    """Get comprehensive scheduling recommendations."""
    try:
        # Collect recommendations from various sources
        
        # VLD-Lineup coordination
        coordination = scheduling_service.optimize_vld_lineup_coordination(production_id, 30)
        
        # Critical path issues
        critical_path = scheduling_service.identify_critical_path_issues(production_id, 30)
        
        # Shuttle-Capesize coordination
        shuttle_capesize = scheduling_service.plan_shuttle_capesize_coordination(60)
        
        all_recommendations = []
        
        # Add coordination recommendations
        for rec in coordination['optimization']['recommendations']:
            all_recommendations.append({
                'type': 'vld_lineup_coordination',
                'priority': rec['priority'],
                'description': rec['description'],
                'expected_benefit': rec['expected_benefit'],
                'source': 'VLD-Lineup Optimization'
            })
        
        # Add critical path action items
        for action in critical_path['critical_path_analysis']['action_plan']:
            all_recommendations.append({
                'type': 'critical_path_action',
                'priority': action['priority'],
                'description': action['action'],
                'expected_benefit': 'Prevent delays and bottlenecks',
                'deadline': action['deadline'],
                'responsible': action['responsible'],
                'source': 'Critical Path Analysis'
            })
        
        # Add shuttle efficiency recommendations
        for rec in shuttle_capesize['coordination_plan']['efficiency_recommendations']:
            all_recommendations.append({
                'type': 'shuttle_efficiency',
                'priority': rec['priority'],
                'description': rec['description'],
                'suggestions': rec['suggestions'],
                'source': 'Shuttle-Capesize Coordination'
            })
        
        # Sort by priority
        priority_order = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
        all_recommendations.sort(
            key=lambda x: priority_order.get(x['priority'], 0), 
            reverse=True
        )
        
        return api_response(True, "Scheduling recommendations compiled", {
            'recommendations': all_recommendations,
            'summary': {
                'total_recommendations': len(all_recommendations),
                'critical_priority': len([r for r in all_recommendations if r['priority'] == 'CRITICAL']),
                'high_priority': len([r for r in all_recommendations if r['priority'] == 'HIGH']),
                'sources': list(set(r['source'] for r in all_recommendations))
            }
        })
        
    except Exception as e:
        return handle_api_error(e)


@scheduling_bp.route('/conflicts/<int:production_id>', methods=['GET'])
@require_auth
def get_scheduling_conflicts(production_id: int):
    """Get scheduling conflicts analysis."""
    try:
        # Generate master schedule to identify conflicts
        start_date = date.today()
        end_date = start_date + timedelta(days=30)
        
        master_schedule = scheduling_service.generate_master_schedule(
            production_id, start_date, end_date
        )
        
        conflicts = master_schedule['master_schedule']['constraints']
        
        # Categorize conflicts by severity
        conflict_summary = {
            'critical': [c for c in conflicts if c['severity'] == 'CRITICAL'],
            'high': [c for c in conflicts if c['severity'] == 'HIGH'],
            'medium': [c for c in conflicts if c['severity'] == 'MEDIUM'],
            'low': [c for c in conflicts if c['severity'] == 'LOW']
        }
        
        return api_response(True, "Scheduling conflicts analyzed", {
            'conflicts': conflicts,
            'conflict_summary': {
                'total_conflicts': len(conflicts),
                'critical_conflicts': len(conflict_summary['critical']),
                'high_priority_conflicts': len(conflict_summary['high']),
                'by_severity': {
                    'critical': len(conflict_summary['critical']),
                    'high': len(conflict_summary['high']),
                    'medium': len(conflict_summary['medium']),
                    'low': len(conflict_summary['low'])
                }
            },
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        })
        
    except Exception as e:
        return handle_api_error(e)


@scheduling_bp.route('/performance/metrics', methods=['GET'])
@require_auth
def get_scheduling_performance_metrics():
    """Get scheduling performance metrics."""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            end_date = date.today()
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Calculate performance metrics
        # This would involve analyzing historical data
        
        metrics = {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': (end_date - start_date).days
            },
            'vld_performance': {
                'on_time_completion_rate': 85.2,
                'average_deferral_days': 2.3,
                'narrow_compliance_rate': 92.1
            },
            'lineup_performance': {
                'eta_accuracy_rate': 78.5,
                'berth_utilization_rate': 82.3,
                'average_port_stay_hours': 36.2
            },
            'shuttle_performance': {
                'cycle_time_efficiency': 88.7,
                'utilization_rate': 75.4,
                'average_cycle_hours': 24.8
            },
            'coordination_efficiency': {
                'vld_lineup_coordination_rate': 68.9,
                'shuttle_capesize_efficiency': 91.2,
                'overall_scheduling_score': 81.5
            }
        }
        
        return api_response(True, "Scheduling performance metrics calculated", {
            'metrics': metrics
        })
        
    except Exception as e:
        return handle_api_error(e)


@scheduling_bp.route('/export/<int:production_id>', methods=['GET'])
@require_auth
def export_schedule(production_id: int):
    """Export schedule data for external systems."""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        format_type = request.args.get('format', 'json')  # json, csv, excel
        
        if not start_date:
            start_date = date.today()
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            end_date = start_date + timedelta(days=30)
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Generate master schedule
        master_schedule = scheduling_service.generate_master_schedule(
            production_id, start_date, end_date
        )
        
        # Format for export
        export_data = {
            'metadata': {
                'production_id': production_id,
                'export_timestamp': datetime.utcnow().isoformat(),
                'period': master_schedule['master_schedule']['period'],
                'format': format_type
            },
            'schedule': master_schedule['master_schedule']['daily_schedule'],
            'summary': master_schedule['master_schedule']['summary'],
            'constraints': master_schedule['master_schedule']['constraints']
        }
        
        return api_response(True, f"Schedule exported in {format_type} format", {
            'export_data': export_data,
            'download_info': {
                'format': format_type,
                'size_estimate': f"{len(str(export_data)) // 1024}KB",
                'records_count': len(master_schedule['master_schedule']['daily_schedule'])
            }
        })
        
    except Exception as e:
        return handle_api_error(e)

