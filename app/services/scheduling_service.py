"""
Scheduling Service
=================

Advanced scheduling service for coordinating VLDs, Lineups, and Shuttle operations.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from dataclasses import dataclass
from enum import Enum

from app.repository.vld_repository import VLDRepository
from app.repository.lineup_repository import LineupRepository
from app.repository.shuttle_repository import ShuttleRepository, ShuttleOperationRepository
from app.repository.capesize_repository import CapesizeRepository
from app.repository.production_repository import ProductionRepository
from app.models.vld import VLD, VLDStatus
from app.models.lineup import Lineup, LineupStatus
from app.models.shuttle import Shuttle, ShuttleOperation
from app.models.capesize import CapesizeVessel


class SchedulingPriority(Enum):
    """Scheduling priority levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class SchedulingConstraint:
    """Represents a scheduling constraint."""
    type: str
    description: str
    severity: SchedulingPriority
    affected_entities: List[int]
    resolution_suggestions: List[str]


@dataclass
class SchedulingRecommendation:
    """Represents a scheduling recommendation."""
    type: str
    description: str
    impact: str
    priority: SchedulingPriority
    implementation_steps: List[str]


class SchedulingService:
    """Service for advanced scheduling operations."""
    
    def __init__(self):
        self.vld_repo = VLDRepository()
        self.lineup_repo = LineupRepository()
        self.shuttle_repo = ShuttleRepository()
        self.shuttle_operation_repo = ShuttleOperationRepository()
        self.capesize_repo = CapesizeRepository()
        self.production_repo = ProductionRepository()
    
    def generate_master_schedule(self, production_id: int, start_date: date, 
                                end_date: date) -> Dict[str, Any]:
        """Generate comprehensive master schedule."""
        # Get all relevant data
        vlds = self.vld_repo.get_by_date_range(start_date, end_date, production_id)
        lineups = self.lineup_repo.get_by_date_range(start_date, end_date)
        shuttle_operations = self.shuttle_operation_repo.get_by_date_range(start_date, end_date)
        capesize_operations = self.capesize_repo.get_by_date_range(start_date, end_date)
        
        # Create daily schedule
        daily_schedule = {}
        current_date = start_date
        
        while current_date <= end_date:
            date_str = current_date.isoformat()
            
            # VLDs for this date
            date_vlds = [v for v in vlds if v.vld_date == current_date]
            
            # Lineups for this date
            date_lineups = [l for l in lineups if l.eta and l.eta.date() == current_date]
            
            # Shuttle operations for this date
            date_shuttle_ops = [
                s for s in shuttle_operations 
                if s.load_start_at and s.load_start_at.date() == current_date
            ]
            
            # Capesize operations for this date
            date_capesize_ops = [
                c for c in capesize_operations 
                if c.eta and c.eta.date() == current_date
            ]
            
            daily_schedule[date_str] = {
                'date': date_str,
                'vlds': [self._format_vld_for_schedule(v) for v in date_vlds],
                'lineups': [self._format_lineup_for_schedule(l) for l in date_lineups],
                'shuttle_operations': [self._format_shuttle_op_for_schedule(s) for s in date_shuttle_ops],
                'capesize_operations': [self._format_capesize_op_for_schedule(c) for c in date_capesize_ops],
                'capacity_analysis': self._analyze_daily_capacity(
                    date_vlds, date_lineups, date_shuttle_ops
                )
            }
            
            current_date += timedelta(days=1)
        
        # Generate constraints and recommendations
        constraints = self._identify_scheduling_constraints(
            vlds, lineups, shuttle_operations, capesize_operations
        )
        recommendations = self._generate_scheduling_recommendations(constraints)
        
        # Calculate summary metrics
        summary = self._calculate_schedule_summary(daily_schedule, constraints)
        
        return {
            'success': True,
            'master_schedule': {
                'production_id': production_id,
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': (end_date - start_date).days + 1
                },
                'daily_schedule': daily_schedule,
                'summary': summary,
                'constraints': [self._format_constraint(c) for c in constraints],
                'recommendations': [self._format_recommendation(r) for r in recommendations]
            }
        }
    
    def optimize_vld_lineup_coordination(self, production_id: int, 
                                       optimization_window_days: int = 30) -> Dict[str, Any]:
        """Optimize coordination between VLDs and Lineups."""
        end_date = date.today() + timedelta(days=optimization_window_days)
        start_date = date.today()
        
        # Get VLDs and Lineups
        vlds = self.vld_repo.get_by_date_range(start_date, end_date, production_id)
        lineups = self.lineup_repo.get_by_date_range(start_date, end_date)
        
        # Identify coordination opportunities
        coordination_opportunities = []
        
        for vld in vlds:
            if vld.status in [VLDStatus.NARROWED, VLDStatus.NOMINATED]:
                # Find potential lineup matches
                potential_lineups = [
                    l for l in lineups 
                    if (l.vld_id is None and 
                        l.partner_id == vld.current_partner_id and
                        l.status in [LineupStatus.SCHEDULED, LineupStatus.ETA_RECEIVED])
                ]
                
                if potential_lineups:
                    coordination_opportunities.append({
                        'vld_id': vld.id,
                        'vld_date': vld.vld_date.isoformat(),
                        'partner_name': vld.current_partner.name if vld.current_partner else None,
                        'vessel_name': vld.vessel_name,
                        'potential_lineups': [
                            {
                                'lineup_id': l.id,
                                'vessel_name': l.vessel_name,
                                'eta': l.eta.isoformat() if l.eta else None,
                                'berth_id': l.berth_id,
                                'compatibility_score': self._calculate_vld_lineup_compatibility(vld, l)
                            }
                            for l in potential_lineups
                        ]
                    })
        
        # Generate optimization recommendations
        optimization_recommendations = []
        
        for opportunity in coordination_opportunities:
            best_lineup = max(
                opportunity['potential_lineups'],
                key=lambda x: x['compatibility_score']
            )
            
            if best_lineup['compatibility_score'] > 0.7:  # High compatibility threshold
                optimization_recommendations.append({
                    'type': 'vld_lineup_coordination',
                    'priority': SchedulingPriority.HIGH,
                    'description': f"Link VLD {opportunity['vld_id']} with Lineup {best_lineup['lineup_id']}",
                    'expected_benefit': 'Improved coordination and reduced delays',
                    'implementation': {
                        'action': 'update_lineup_vld_reference',
                        'vld_id': opportunity['vld_id'],
                        'lineup_id': best_lineup['lineup_id']
                    }
                })
        
        return {
            'success': True,
            'optimization': {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'coordination_opportunities': coordination_opportunities,
                'recommendations': optimization_recommendations,
                'summary': {
                    'total_vlds_analyzed': len(vlds),
                    'coordination_opportunities_found': len(coordination_opportunities),
                    'high_priority_recommendations': len(optimization_recommendations)
                }
            }
        }
    
    def plan_shuttle_capesize_coordination(self, time_horizon_days: int = 60) -> Dict[str, Any]:
        """Plan coordination between shuttle operations and capesize vessels."""
        end_date = date.today() + timedelta(days=time_horizon_days)
        start_date = date.today()
        
        # Get active and scheduled capesize operations
        capesize_operations = self.capesize_repo.get_by_date_range(start_date, end_date)
        available_shuttles = self.shuttle_repo.get_available_shuttles()
        
        coordination_plan = []
        
        for capesize_op in capesize_operations:
            if capesize_op.status in ['scheduled', 'arrived', 'loading']:
                remaining_tonnage = capesize_op.target_tonnage - capesize_op.current_tonnage
                
                if remaining_tonnage > 0:
                    # Calculate shuttle requirements
                    avg_shuttle_capacity = 15000
                    shuttles_needed = max(1, round(remaining_tonnage / avg_shuttle_capacity))
                    
                    # Check shuttle availability
                    if len(available_shuttles) >= shuttles_needed:
                        # Create coordination plan
                        shuttle_plan = []
                        for i in range(min(shuttles_needed, len(available_shuttles))):
                            shuttle = available_shuttles[i]
                            planned_tonnage = min(avg_shuttle_capacity, remaining_tonnage)
                            
                            # Estimate timing
                            start_time = datetime.utcnow() + timedelta(hours=i * 6)
                            
                            shuttle_plan.append({
                                'shuttle_id': shuttle.id,
                                'shuttle_name': shuttle.vessel.name if shuttle.vessel else None,
                                'planned_tonnage': planned_tonnage,
                                'estimated_start': start_time.isoformat(),
                                'sequence': i + 1
                            })
                            
                            remaining_tonnage -= planned_tonnage
                        
                        coordination_plan.append({
                            'capesize_operation_id': capesize_op.id,
                            'cape_vessel_name': capesize_op.cape_vessel.name if capesize_op.cape_vessel else None,
                            'target_tonnage': capesize_op.target_tonnage,
                            'current_tonnage': capesize_op.current_tonnage,
                            'remaining_tonnage': capesize_op.target_tonnage - capesize_op.current_tonnage,
                            'shuttle_plan': shuttle_plan,
                            'estimated_completion': (
                                datetime.utcnow() + timedelta(hours=len(shuttle_plan) * 24)
                            ).isoformat()
                        })
        
        # Generate efficiency recommendations
        efficiency_recommendations = []
        
        # Check for optimization opportunities
        total_shuttles_required = sum(len(plan['shuttle_plan']) for plan in coordination_plan)
        if total_shuttles_required > len(available_shuttles):
            efficiency_recommendations.append({
                'type': 'shuttle_capacity_constraint',
                'priority': SchedulingPriority.HIGH,
                'description': f'Insufficient shuttles: need {total_shuttles_required}, have {len(available_shuttles)}',
                'suggestions': [
                    'Consider staggering capesize arrivals',
                    'Optimize shuttle cycle times',
                    'Evaluate additional shuttle capacity'
                ]
            })
        
        return {
            'success': True,
            'coordination_plan': {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'capesize_shuttle_coordination': coordination_plan,
                'efficiency_recommendations': efficiency_recommendations,
                'resource_summary': {
                    'available_shuttles': len(available_shuttles),
                    'shuttles_required': total_shuttles_required,
                    'utilization_rate': (total_shuttles_required / len(available_shuttles) * 100) if available_shuttles else 0
                }
            }
        }
    
    def generate_capacity_forecast(self, production_id: int, 
                                  forecast_days: int = 90) -> Dict[str, Any]:
        """Generate capacity forecast for production planning."""
        end_date = date.today() + timedelta(days=forecast_days)
        start_date = date.today()
        
        # Get historical data for trend analysis
        historical_start = start_date - timedelta(days=90)
        historical_vlds = self.vld_repo.get_completed_vlds(historical_start, start_date)
        
        # Calculate historical averages
        if historical_vlds:
            avg_daily_tonnage = sum(v.actual_tonnage or v.planned_tonnage for v in historical_vlds) / 90
            avg_vlds_per_day = len(historical_vlds) / 90
        else:
            avg_daily_tonnage = 180000  # Default assumption
            avg_vlds_per_day = 3
        
        # Get future VLDs
        future_vlds = self.vld_repo.get_by_date_range(start_date, end_date, production_id)
        
        # Generate daily forecast
        daily_forecast = {}
        current_date = start_date
        
        while current_date <= end_date:
            date_str = current_date.isoformat()
            
            # VLDs scheduled for this date
            date_vlds = [v for v in future_vlds if v.vld_date == current_date]
            
            # Calculate planned tonnage
            planned_tonnage = sum(v.planned_tonnage for v in date_vlds)
            
            # Estimate capacity utilization
            max_daily_capacity = 200000  # Assumed maximum daily capacity
            utilization_rate = (planned_tonnage / max_daily_capacity * 100) if planned_tonnage > 0 else 0
            
            # Identify potential issues
            issues = []
            if utilization_rate > 90:
                issues.append('High capacity utilization - potential bottleneck')
            if len(date_vlds) > 3:
                issues.append('Multiple VLDs scheduled - coordination required')
            if utilization_rate < 30 and len(date_vlds) > 0:
                issues.append('Low utilization - optimization opportunity')
            
            daily_forecast[date_str] = {
                'date': date_str,
                'planned_tonnage': planned_tonnage,
                'vld_count': len(date_vlds),
                'utilization_rate': round(utilization_rate, 2),
                'capacity_status': self._determine_capacity_status(utilization_rate),
                'issues': issues,
                'vlds': [
                    {
                        'id': v.id,
                        'partner_name': v.current_partner.name if v.current_partner else None,
                        'planned_tonnage': v.planned_tonnage,
                        'status': v.status.value
                    }
                    for v in date_vlds
                ]
            }
            
            current_date += timedelta(days=1)
        
        # Calculate forecast summary
        total_planned_tonnage = sum(day['planned_tonnage'] for day in daily_forecast.values())
        avg_utilization = sum(day['utilization_rate'] for day in daily_forecast.values()) / len(daily_forecast)
        high_utilization_days = len([day for day in daily_forecast.values() if day['utilization_rate'] > 80])
        
        return {
            'success': True,
            'capacity_forecast': {
                'production_id': production_id,
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': forecast_days
                },
                'daily_forecast': daily_forecast,
                'summary': {
                    'total_planned_tonnage': total_planned_tonnage,
                    'average_utilization_rate': round(avg_utilization, 2),
                    'high_utilization_days': high_utilization_days,
                    'total_vlds': sum(day['vld_count'] for day in daily_forecast.values()),
                    'peak_day': max(daily_forecast.items(), key=lambda x: x[1]['planned_tonnage'])[0] if daily_forecast else None
                },
                'trends': {
                    'historical_avg_daily_tonnage': round(avg_daily_tonnage, 0),
                    'historical_avg_vlds_per_day': round(avg_vlds_per_day, 2)
                }
            }
        }
    
    def identify_critical_path_issues(self, production_id: int, 
                                     analysis_days: int = 30) -> Dict[str, Any]:
        """Identify critical path issues in the scheduling chain."""
        end_date = date.today() + timedelta(days=analysis_days)
        start_date = date.today()
        
        # Get all relevant data
        vlds = self.vld_repo.get_by_date_range(start_date, end_date, production_id)
        lineups = self.lineup_repo.get_by_date_range(start_date, end_date)
        shuttle_operations = self.shuttle_operation_repo.get_active_operations()
        
        critical_issues = []
        
        # Check VLD critical path issues
        for vld in vlds:
            days_to_vld = (vld.vld_date - date.today()).days
            
            if vld.status == VLDStatus.PLANNED and days_to_vld <= 7:
                critical_issues.append({
                    'type': 'vld_narrow_deadline',
                    'severity': SchedulingPriority.HIGH,
                    'entity_type': 'vld',
                    'entity_id': vld.id,
                    'description': f'VLD {vld.id} needs narrowing within {days_to_vld} days',
                    'impact': 'Potential delay in vessel nomination',
                    'deadline': vld.vld_date.isoformat()
                })
            
            if vld.status == VLDStatus.NARROWED and days_to_vld <= 3:
                critical_issues.append({
                    'type': 'vessel_nomination_deadline',
                    'severity': SchedulingPriority.CRITICAL,
                    'entity_type': 'vld',
                    'entity_id': vld.id,
                    'description': f'VLD {vld.id} needs vessel nomination within {days_to_vld} days',
                    'impact': 'Risk of VLD cancellation or deferral',
                    'deadline': vld.vld_date.isoformat()
                })
        
        # Check lineup critical path issues
        for lineup in lineups:
            if lineup.eta and lineup.status == LineupStatus.SCHEDULED:
                hours_to_eta = (lineup.eta - datetime.utcnow()).total_seconds() / 3600
                
                if hours_to_eta <= 24 and not lineup.vld_id:
                    critical_issues.append({
                        'type': 'lineup_vld_coordination',
                        'severity': SchedulingPriority.HIGH,
                        'entity_type': 'lineup',
                        'entity_id': lineup.id,
                        'description': f'Lineup {lineup.id} arriving in {hours_to_eta:.1f}h without VLD coordination',
                        'impact': 'Potential loading delays',
                        'deadline': lineup.eta.isoformat()
                    })
        
        # Check shuttle operation critical path issues
        for shuttle_op in shuttle_operations:
            if shuttle_op.load_start_at and not shuttle_op.load_end_at:
                loading_hours = (datetime.utcnow() - shuttle_op.load_start_at).total_seconds() / 3600
                
                if loading_hours > 8:  # Typical loading should complete within 8 hours
                    critical_issues.append({
                        'type': 'extended_shuttle_loading',
                        'severity': SchedulingPriority.MEDIUM,
                        'entity_type': 'shuttle_operation',
                        'entity_id': shuttle_op.id,
                        'description': f'Shuttle operation {shuttle_op.id} loading for {loading_hours:.1f}h',
                        'impact': 'Potential shuttle availability constraint',
                        'deadline': None
                    })
        
        # Sort by severity and deadline
        critical_issues.sort(key=lambda x: (x['severity'].value, x['deadline'] or '9999-12-31'), reverse=True)
        
        # Generate action plan
        action_plan = []
        for issue in critical_issues[:5]:  # Top 5 critical issues
            if issue['type'] == 'vld_narrow_deadline':
                action_plan.append({
                    'issue_id': f"{issue['entity_type']}_{issue['entity_id']}",
                    'priority': issue['severity'].name,
                    'action': 'Contact partner for narrow period selection',
                    'responsible': 'Operations Team',
                    'deadline': issue['deadline']
                })
            elif issue['type'] == 'vessel_nomination_deadline':
                action_plan.append({
                    'issue_id': f"{issue['entity_type']}_{issue['entity_id']}",
                    'priority': issue['severity'].name,
                    'action': 'Expedite vessel nomination process',
                    'responsible': 'Commercial Team',
                    'deadline': issue['deadline']
                })
        
        return {
            'success': True,
            'critical_path_analysis': {
                'analysis_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'critical_issues': critical_issues,
                'action_plan': action_plan,
                'summary': {
                    'total_issues': len(critical_issues),
                    'critical_issues': len([i for i in critical_issues if i['severity'] == SchedulingPriority.CRITICAL]),
                    'high_priority_issues': len([i for i in critical_issues if i['severity'] == SchedulingPriority.HIGH]),
                    'immediate_action_required': len([i for i in critical_issues if i['deadline'] and 
                                                    datetime.fromisoformat(i['deadline']).date() <= date.today() + timedelta(days=3)])
                }
            }
        }
    
    def _format_vld_for_schedule(self, vld: VLD) -> Dict[str, Any]:
        """Format VLD for schedule display."""
        return {
            'id': vld.id,
            'partner_name': vld.current_partner.name if vld.current_partner else None,
            'vessel_name': vld.vessel_name,
            'planned_tonnage': vld.planned_tonnage,
            'status': vld.status.value
        }
    
    def _format_lineup_for_schedule(self, lineup: Lineup) -> Dict[str, Any]:
        """Format lineup for schedule display."""
        return {
            'id': lineup.id,
            'vessel_name': lineup.vessel_name,
            'partner_name': lineup.partner.name if lineup.partner else None,
            'eta': lineup.eta.isoformat() if lineup.eta else None,
            'berth_id': lineup.berth_id,
            'status': lineup.status.value
        }
    
    def _format_shuttle_op_for_schedule(self, shuttle_op: ShuttleOperation) -> Dict[str, Any]:
        """Format shuttle operation for schedule display."""
        return {
            'id': shuttle_op.id,
            'shuttle_name': shuttle_op.shuttle.vessel.name if shuttle_op.shuttle and shuttle_op.shuttle.vessel else None,
            'cape_vessel_name': shuttle_op.cape_vessel_name,
            'volume': shuttle_op.volume,
            'status': self._determine_shuttle_status(shuttle_op)
        }
    
    def _format_capesize_op_for_schedule(self, capesize_op) -> Dict[str, Any]:
        """Format capesize operation for schedule display."""
        return {
            'id': capesize_op.id,
            'cape_vessel_name': capesize_op.cape_vessel.name if capesize_op.cape_vessel else None,
            'target_tonnage': capesize_op.target_tonnage,
            'anchorage_location': capesize_op.anchorage_location,
            'status': capesize_op.status.value
        }
    
    def _analyze_daily_capacity(self, vlds: List[VLD], lineups: List[Lineup], 
                               shuttle_ops: List[ShuttleOperation]) -> Dict[str, Any]:
        """Analyze daily capacity utilization."""
        total_vld_tonnage = sum(v.planned_tonnage for v in vlds)
        total_lineup_tonnage = sum(l.planned_tonnage or 0 for l in lineups)
        total_shuttle_volume = sum(s.volume or 0 for s in shuttle_ops)
        
        max_daily_capacity = 200000  # Assumed maximum
        utilization = (total_vld_tonnage / max_daily_capacity * 100) if total_vld_tonnage > 0 else 0
        
        return {
            'total_vld_tonnage': total_vld_tonnage,
            'total_lineup_tonnage': total_lineup_tonnage,
            'total_shuttle_volume': total_shuttle_volume,
            'capacity_utilization': round(utilization, 2),
            'status': self._determine_capacity_status(utilization)
        }
    
    def _determine_capacity_status(self, utilization_rate: float) -> str:
        """Determine capacity status based on utilization rate."""
        if utilization_rate >= 90:
            return 'critical'
        elif utilization_rate >= 70:
            return 'high'
        elif utilization_rate >= 40:
            return 'normal'
        else:
            return 'low'
    
    def _calculate_vld_lineup_compatibility(self, vld: VLD, lineup: Lineup) -> float:
        """Calculate compatibility score between VLD and lineup."""
        score = 0.0
        
        # Partner match
        if vld.current_partner_id == lineup.partner_id:
            score += 0.4
        
        # Vessel name match
        if vld.vessel_name and lineup.vessel_name and vld.vessel_name == lineup.vessel_name:
            score += 0.3
        
        # Date proximity
        if lineup.eta and vld.vld_date:
            date_diff = abs((lineup.eta.date() - vld.vld_date).days)
            if date_diff <= 1:
                score += 0.3
            elif date_diff <= 3:
                score += 0.2
            elif date_diff <= 7:
                score += 0.1
        
        return min(1.0, score)
    
    def _identify_scheduling_constraints(self, vlds: List[VLD], lineups: List[Lineup],
                                       shuttle_ops: List[ShuttleOperation], 
                                       capesize_ops: List) -> List[SchedulingConstraint]:
        """Identify scheduling constraints."""
        constraints = []
        
        # Check for VLD clustering
        vld_dates = {}
        for vld in vlds:
            date_str = vld.vld_date.isoformat()
            vld_dates[date_str] = vld_dates.get(date_str, 0) + 1
        
        for date_str, count in vld_dates.items():
            if count > 3:
                constraints.append(SchedulingConstraint(
                    type='vld_clustering',
                    description=f'{count} VLDs scheduled on {date_str}',
                    severity=SchedulingPriority.HIGH,
                    affected_entities=[v.id for v in vlds if v.vld_date.isoformat() == date_str],
                    resolution_suggestions=['Redistribute VLDs across adjacent dates', 'Increase daily capacity']
                ))
        
        return constraints
    
    def _generate_scheduling_recommendations(self, constraints: List[SchedulingConstraint]) -> List[SchedulingRecommendation]:
        """Generate scheduling recommendations based on constraints."""
        recommendations = []
        
        for constraint in constraints:
            if constraint.type == 'vld_clustering':
                recommendations.append(SchedulingRecommendation(
                    type='redistribute_vlds',
                    description='Redistribute clustered VLDs to optimize capacity utilization',
                    impact='Reduced port congestion and improved efficiency',
                    priority=SchedulingPriority.HIGH,
                    implementation_steps=[
                        'Identify VLDs that can be moved',
                        'Coordinate with partners for date changes',
                        'Update VLD schedule'
                    ]
                ))
        
        return recommendations
    
    def _calculate_schedule_summary(self, daily_schedule: Dict[str, Any], 
                                   constraints: List[SchedulingConstraint]) -> Dict[str, Any]:
        """Calculate schedule summary metrics."""
        total_vlds = sum(len(day['vlds']) for day in daily_schedule.values())
        total_lineups = sum(len(day['lineups']) for day in daily_schedule.values())
        total_tonnage = sum(day['capacity_analysis']['total_vld_tonnage'] for day in daily_schedule.values())
        
        avg_utilization = sum(
            day['capacity_analysis']['capacity_utilization'] for day in daily_schedule.values()
        ) / len(daily_schedule) if daily_schedule else 0
        
        return {
            'total_vlds': total_vlds,
            'total_lineups': total_lineups,
            'total_planned_tonnage': total_tonnage,
            'average_capacity_utilization': round(avg_utilization, 2),
            'total_constraints': len(constraints),
            'high_priority_constraints': len([c for c in constraints if c.severity == SchedulingPriority.HIGH])
        }
    
    def _format_constraint(self, constraint: SchedulingConstraint) -> Dict[str, Any]:
        """Format constraint for API response."""
        return {
            'type': constraint.type,
            'description': constraint.description,
            'severity': constraint.severity.name,
            'affected_entities': constraint.affected_entities,
            'resolution_suggestions': constraint.resolution_suggestions
        }
    
    def _format_recommendation(self, recommendation: SchedulingRecommendation) -> Dict[str, Any]:
        """Format recommendation for API response."""
        return {
            'type': recommendation.type,
            'description': recommendation.description,
            'impact': recommendation.impact,
            'priority': recommendation.priority.name,
            'implementation_steps': recommendation.implementation_steps
        }
    
    def _determine_shuttle_status(self, shuttle_op: ShuttleOperation) -> str:
        """Determine shuttle operation status."""
        if shuttle_op.return_at:
            return 'completed'
        elif shuttle_op.discharge_end_at:
            return 'returning'
        elif shuttle_op.discharge_start_at:
            return 'discharging'
        elif shuttle_op.sail_out_at:
            return 'transit'
        elif shuttle_op.load_end_at:
            return 'loaded'
        elif shuttle_op.load_start_at:
            return 'loading'
        else:
            return 'planned'

